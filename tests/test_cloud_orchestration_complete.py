import asyncio
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import types
import unittest
from unittest.mock import patch

from continuum.cloud_orchestration import (
    admit_remediation_plan, canonical_request, independent_contract_verifier, invoke, live_adk_investigator,
    live_adk_supplier_assessor, production_supplier_evidence_cache,
    validate_investigation, workload_service_account,
)
from continuum.standard import build_contract_bundle
from continuum.contract import artifact_digest
from continuum.models import digest
from continuum.supplier_assurance import ExternalToolError, FirestoreEvidenceCache
from tests.incident_fixtures import incident_extension
from tests.selection_fixtures import selection_extensions
from tests.test_verification_engine import Reader, observations


class _Credentials:
    def __init__(self, service=None, signer=None):
        self.service_account_email, self.signer_email, self.refreshed = service, signer, False
    def refresh(self, request): self.refreshed = True


class CloudOrchestrationCompleteTests(unittest.TestCase):
    def test_production_supplier_cache_is_lazy_and_project_bound(self):
        production_supplier_evidence_cache.cache_clear()
        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": ""}):
            self.assertIsNone(production_supplier_evidence_cache())
        production_supplier_evidence_cache.cache_clear()
        client = object()
        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "project"}), \
             patch("google.cloud.firestore.Client", return_value=client) as factory:
            cache = production_supplier_evidence_cache()
            self.assertIsInstance(cache, FirestoreEvidenceCache)
            self.assertIs(production_supplier_evidence_cache(), cache)
            factory.assert_called_once_with(project="project")
        production_supplier_evidence_cache.cache_clear()

    def test_workload_identity_default_provider_signer_and_fail_closed(self):
        credentials = _Credentials(signer="signer@example.com")
        with patch("google.auth.default", return_value=(credentials, "p")):
            self.assertEqual(workload_service_account(), "signer@example.com")
        self.assertTrue(credentials.refreshed)
        for identity in (None, "default"):
            creds = _Credentials(service=identity)
            with self.assertRaisesRegex(RuntimeError, "WORKLOAD_IDENTITY_UNAVAILABLE"):
                workload_service_account(credentials_provider=lambda: (creds, "p"), request_factory=object)

    def test_invoke_sync_async_and_invalid_results(self):
        self.assertEqual(asyncio.run(invoke(lambda p, i: {"ok": i}, {}, "id")), {"ok": "id"})
        async def adapter(payload, identity): return {"payload": payload}
        self.assertEqual(asyncio.run(invoke(adapter, {"x": 1}, "id")), {"payload": {"x": 1}})
        with self.assertRaisesRegex(ValueError, "ADAPTER_RESULT_INVALID"):
            asyncio.run(invoke(lambda p, i: [], {}, "id"))

    def test_investigation_validation_and_canonical_request(self):
        complete = {"hypotheses": [], "evidence_ids": [], "unsupported_assumptions": [],
                    "risk": "low", "reversibility": "high", "proposed_actions": [],
                    "successor_choice": {}}
        self.assertIs(validate_investigation(complete), complete)
        for invalid, code in [({}, "INVESTIGATION_RESULT_INVALID"),
                              ({**complete, "evidence_ids": "bad"}, "INVESTIGATION_RESULT_INVALID"),
                              ({**complete, "authority_grant": {}}, "INVESTIGATION_ASSERTS_AUTHORITY")]:
            with self.assertRaisesRegex(ValueError, code): validate_investigation(invalid)
        self.assertEqual(canonical_request({"é": 1}, "id"), b'{"identity":"id","payload":{"\xc3\xa9":1}}')
        assessment = incident_extension()["incident_assessment"]
        self.assertEqual(admit_remediation_plan({"proposed_actions": ["request_operator_review"]}, assessment),
                         "request_operator_review")
        for actions, code in ((None, "REMEDIATION_PLAN_SCHEMA_INVALID"),
                              ([], "REMEDIATION_PLAN_SCHEMA_INVALID"),
                              (["unknown"], "REMEDIATION_NOT_ALLOWED"),
                              (["request_operator_review", "initiate_governed_succession"],
                               "REMEDIATION_PLAN_SCHEMA_INVALID")):
            with self.assertRaisesRegex(RuntimeError, code):
                admit_remediation_plan({"proposed_actions": actions}, assessment)

    def _adk_modules(self, outputs):
        class SessionService:
            async def create_session(self, **kwargs): self.kwargs = kwargs
        class Event:
            def __init__(self, final, text=None, content=True):
                self.final = final
                self.content = types.SimpleNamespace(parts=[types.SimpleNamespace(text=text)]) if content else None
            def is_final_response(self): return self.final
        class Runner:
            def __init__(self, **kwargs): pass
            async def run_async(self, **kwargs):
                for item in outputs:
                    yield Event(*item)
        runners = types.ModuleType("google.adk.runners"); runners.Runner = Runner
        sessions = types.ModuleType("google.adk.sessions"); sessions.InMemorySessionService = SessionService
        genai_types = types.ModuleType("google.genai.types")
        genai_types.Content = lambda **kwargs: kwargs; genai_types.Part = lambda **kwargs: kwargs
        genai = types.ModuleType("google.genai"); genai.types = genai_types
        app_agent = types.ModuleType("app.agent")
        app_agent.root_agent = object(); app_agent.supplier_agent = object()
        return {"google.adk.runners": runners, "google.adk.sessions": sessions,
                "google.genai": genai, "google.genai.types": genai_types, "app.agent": app_agent}

    def test_live_adk_investigator_success_and_all_response_failures(self):
        valid = json.dumps({"hypotheses": [], "evidence_ids": [], "unsupported_assumptions": [],
                            "risk": "low", "reversibility": "high", "proposed_actions": [],
                            "successor_choice": {}})
        cases = [
            ([(False, "ignored", True), (True, valid, True)], None),
            ([], "INVESTIGATION_RESULT_MISSING"),
            ([(True, "not-json", True)], "INVESTIGATION_RESULT_NOT_JSON"),
            ([(True, "[]", True)], "INVESTIGATION_RESULT_INVALID"),
            ([(True, None, True)], "INVESTIGATION_RESULT_NOT_JSON"),
            ([(True, valid, False)], "INVESTIGATION_RESULT_MISSING"),
        ]
        for outputs, error in cases:
            with self.subTest(error=error), patch.dict(sys.modules, self._adk_modules(outputs)):
                if error:
                    with self.assertRaisesRegex(ValueError, error):
                        asyncio.run(live_adk_investigator({"e": 1}, "worker@example.com"))
                else:
                    self.assertEqual(asyncio.run(live_adk_investigator({"e": 1}, "worker@example.com"))["risk"], "low")

    def test_live_supplier_agent_uses_external_tools_and_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "SUPPLIER_APPLICATION_REQUIRED"):
            asyncio.run(live_adk_supplier_assessor({}, "worker@example.com"))
        application = {"lei": "W38RGI023J3WT1HWRP32", "country_code": "DE",
                       "vat_number": "129274202"}
        with patch("continuum.cloud_orchestration.lookup_gleif", side_effect=OSError("offline")):
            held = asyncio.run(live_adk_supplier_assessor(
                {"application": application}, "worker@example.com", cache=object()))
            self.assertEqual(held["status"], "HOLD")
            self.assertEqual(held["reason_code"], "SUPPLIER_TOOL_UNAVAILABLE")
            self.assertFalse(held["model_invoked"])
        with patch("continuum.cloud_orchestration.lookup_gleif",
                   side_effect=ExternalToolError("GLEIF_TIMEOUT", retryable=True)), \
             patch("continuum.cloud_orchestration.production_supplier_evidence_cache",
                   return_value=None):
            held = asyncio.run(live_adk_supplier_assessor(
                {"application": application}, "worker@example.com", cache=None))
            self.assertEqual(held["reason_code"], "GLEIF_TIMEOUT")
        valid = json.dumps({"recommendation": "ONBOARD"})
        cases = [
            ([(True, valid, True)], None),
            ([], "SUPPLIER_ASSESSMENT_MISSING"),
            ([(True, "not-json", True)], "SUPPLIER_ASSESSMENT_NOT_JSON"),
            ([(True, "[]", True)], "SUPPLIER_MODEL_RESULT_INVALID"),
            ([(True, valid, False)], "SUPPLIER_ASSESSMENT_MISSING"),
        ]
        for outputs, error in cases:
            with self.subTest(error=error), patch.dict(sys.modules, self._adk_modules(outputs)), \
                 patch("continuum.cloud_orchestration.lookup_gleif", return_value={"evidence_ref": "g"}), \
                 patch("continuum.cloud_orchestration.check_eu_vat", return_value={"evidence_ref": "v"}), \
                 patch("continuum.cloud_orchestration.admit_supplier_assessment",
                       return_value={"status": "VERIFIED"}) as admit:
                if error:
                    with self.assertRaisesRegex(ValueError, error):
                        asyncio.run(live_adk_supplier_assessor(
                            {"run_id": "r", "application": application}, "worker@example.com"))
                else:
                    result = asyncio.run(live_adk_supplier_assessor(
                        {"run_id": "r", "application": application}, "worker@example.com"))
                    self.assertEqual(result["status"], "VERIFIED")
                    admit.assert_called_once()

    def test_independent_verifier_requires_pre_attestation_bundle_and_direct_reads(self):
        with self.assertRaisesRegex(ValueError, "CONTRACT_BUNDLE_REQUIRED"):
            independent_contract_verifier({}, "v")
        with TemporaryDirectory() as directory:
            bundle = build_contract_bundle(Path(directory))
        bundle["artifacts"] = [a for a in bundle["artifacts"] if a["artifact_type"] != "continuity_attestation"]
        receipt = next(a for a in bundle["artifacts"] if a["artifact_type"] == "execution_receipt")
        receipt["extensions"] = {"continuum.dev/compliance": {"evidence_id": "compliance-1",
            "obligation_id": "obl-1", "document_hash": "sha256:compliance-document"}}
        receipt["digest"] = {"alg": "sha-256", "value": artifact_digest(receipt)}
        manifest = next(a for a in bundle["artifacts"] if a["artifact_type"] == "succession_manifest")
        selection, governance = selection_extensions(
            manifest["body"]["successor"]["principal_id"])
        reconstruction = {"succession_id": "s",
            "successor_principal": manifest["body"]["successor"]["principal_id"],
            "purpose": "p", "allowed_scopes": ["vendor.approved"],
            "decisions": [{"included": True}, {"included": False}]}
        reconstruction["receipt_digest"] = digest(reconstruction)
        manifest["extensions"] = {"continuum.dev/successor-selection": selection,
                                  "continuum.dev/selection-governance": governance,
                                  "continuum.dev/context-reconstruction": reconstruction,
                                  "continuum.dev/incident-evidence": incident_extension("obl-1")}
        manifest["digest"] = {"alg": "sha-256", "value": artifact_digest(manifest)}
        state = observations(bundle)
        with self.assertRaisesRegex(ValueError, "RUN_ID_REQUIRED"):
            independent_contract_verifier({"bundle": bundle}, "verifier@example.com", Reader(**state))
        with patch.dict("os.environ", {}, clear=True), self.assertRaisesRegex(RuntimeError, "CLOUD_PROJECT_NOT_CONFIGURED"):
            independent_contract_verifier({"run_id": "r", "bundle": bundle}, "verifier@example.com")
        with patch.dict("os.environ", {"GOOGLE_CLOUD_PROJECT": "p"}), \
             patch("google.cloud.firestore.Client", return_value=object()), \
             patch("continuum.cloud_orchestration.FirestoreVerificationReader", return_value=Reader(**state)):
            self.assertEqual(independent_contract_verifier(
                {"run_id": "r", "bundle": bundle}, "verifier@example.com")["status"], "PASS")
        result = independent_contract_verifier({"run_id": "r", "bundle": bundle},
                                               "verifier@example.com", Reader(**state))
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["bundle"]["artifacts"][-1]["issuer"], "mailto:verifier@example.com")


if __name__ == "__main__": unittest.main()

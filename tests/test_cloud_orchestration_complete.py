import asyncio
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import types
import unittest
from unittest.mock import patch

from continuum.cloud_orchestration import (
    admit_remediation_plan, canonical_request, independent_contract_verifier, invoke, live_adk_investigator,
    validate_investigation, workload_service_account,
)
from continuum.standard import build_contract_bundle
from continuum.contract import artifact_digest
from tests.test_verification_engine import Reader, observations


class _Credentials:
    def __init__(self, service=None, signer=None):
        self.service_account_email, self.signer_email, self.refreshed = service, signer, False
    def refresh(self, request): self.refreshed = True


class CloudOrchestrationCompleteTests(unittest.TestCase):
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
                    "risk": "low", "reversibility": "high", "proposed_actions": []}
        self.assertIs(validate_investigation(complete), complete)
        for invalid, code in [({}, "INVESTIGATION_RESULT_INVALID"),
                              ({**complete, "evidence_ids": "bad"}, "INVESTIGATION_RESULT_INVALID"),
                              ({**complete, "authority_grant": {}}, "INVESTIGATION_ASSERTS_AUTHORITY")]:
            with self.assertRaisesRegex(ValueError, code): validate_investigation(invalid)
        self.assertEqual(canonical_request({"é": 1}, "id"), b'{"identity":"id","payload":{"\xc3\xa9":1}}')
        self.assertEqual(admit_remediation_plan({"proposed_actions": ["request_operator_review"]}),
                         "request_operator_review")
        for actions in (None, [], ["unknown"], ["request_operator_review", "initiate_governed_succession"]):
            with self.assertRaisesRegex(ValueError, "REMEDIATION_PLAN_UNSUPPORTED"):
                admit_remediation_plan({"proposed_actions": actions})

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
        app_agent = types.ModuleType("app.agent"); app_agent.root_agent = object()
        return {"google.adk.runners": runners, "google.adk.sessions": sessions,
                "google.genai": genai, "google.genai.types": genai_types, "app.agent": app_agent}

    def test_live_adk_investigator_success_and_all_response_failures(self):
        valid = json.dumps({"hypotheses": [], "evidence_ids": [], "unsupported_assumptions": [],
                            "risk": "low", "reversibility": "high", "proposed_actions": []})
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

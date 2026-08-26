"""Behavioral coverage for defensive and recovery paths not hit by golden flows."""
from __future__ import annotations

import runpy
import sys
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from continuum.api import ScenarioService, create_app
from continuum.conformance import (
    _broken_reference, _cross_tenant_denied, _fabricated_citation,
    _idempotency_conflict, _one_successor_wins, _run,
    _roundtrip_bundle, _self_attestation_rejected, _unsupported_feature,
)
from continuum.contract import (
    ContractError, artifact_digest, authorize_grant,
    canonical_bytes, make_envelope, validate_body, validate_envelope,
    verify_ed25519,
)
from continuum.core import (
    ActionGateway, AgentRegistry, EventStore, MemoryGateway, VendorRegistry,
    validate_manifest,
)
from continuum.models import AgentStatus, AgentVersion, Denied, Event, TransferManifest
from continuum.recovery import RecoveryRuntime
from continuum.scenario import run_scenario
from continuum.standard import build_contract_bundle, mutate_copy, verify_bundle


ISSUED = "2026-08-17T10:05:00Z"


def agent(version="v1", status=AgentStatus.ACTIVE, epoch=7, tenant="acme"):
    return AgentVersion("agent", version, tenant, status, epoch, "sha256:x", f"{version}@acme",
                        ("vendor.create",), ("approved",))


class CoreDefensivePathTests(unittest.TestCase):
    def test_event_store_duplicate_conflict_version_and_invalid_event(self):
        event = Event("e1", "created", "a", 1, ISSUED, "actor", "c", None, {"x": 1})
        store = EventStore()
        self.assertIs(store.append(event), event)
        self.assertIs(store.append(event), event)
        conflict = Event("e1", "created", "a", 1, ISSUED, "actor", "c", None, {"x": 2})
        with self.assertRaisesRegex(ValueError, "EVENT_ID_CONTENT_CONFLICT"):
            store.append(conflict)
        with self.assertRaisesRegex(ValueError, "AGGREGATE_VERSION_CONFLICT"):
            EventStore().append(Event("e2", "created", "a", 2, ISSUED, "actor", "c", None, {}))
        object.__setattr__(event, "payload_hash", "invalid")
        self.assertFalse(store.verify())
        self.assertEqual(store.types(), ["created"])

    def test_registry_all_registration_transition_and_authorization_failures(self):
        registry = AgentRegistry(); registry.register(agent())
        with self.assertRaisesRegex(ValueError, "IMMUTABLE_VERSION_EXISTS"):
            registry.register(agent())
        with self.assertRaisesRegex(ValueError, "ACTIVE_VERSION_EXISTS"):
            registry.register(agent("v2"))
        with self.assertRaisesRegex(Denied, "CAPABILITY_DENIED"):
            registry.authorize("acme", "v1", 7, "missing")
        with self.assertRaisesRegex(Denied, "STALE_FENCE"):
            registry.fence("v1", 6)
        registered = agent("v2", AgentStatus.REGISTERED, 0)
        registry.register(registered)
        with self.assertRaisesRegex(ValueError, "SUCCESSOR_NOT_REGISTERED"):
            registry.activate("v1", 8)
        with self.assertRaisesRegex(ValueError, "ACTIVE_VERSION_EXISTS"):
            registry.activate("v2", 8)
        with self.assertRaisesRegex(ValueError, "RETIRE_REQUIRES_QUARANTINE"):
            registry.retire("v1")

    def test_memory_and_action_preconditions_and_durable_conflicts(self):
        memory = MemoryGateway()
        with self.assertRaisesRegex(Denied, "SCOPE_DENIED"):
            memory.retrieve("v1", "approved")
        memory.grant("v1", ["approved"])
        self.assertEqual(memory.retrieve("v1", "approved"), ["authorized:approved"])
        with TemporaryDirectory() as directory:
            provider = VendorRegistry(Path(directory) / "vendor.db")
            registry = AgentRegistry(); registry.register(agent())
            gateway = ActionGateway(registry, provider)
            base = dict(tenant="acme", version="v1", epoch=7, vendor="one",
                        idempotency_key="key", decision_id="decision")
            for changed, code in [({"idempotency_key": ""}, "IDEMPOTENCY_KEY_REQUIRED"),
                                  ({"decision_id": ""}, "POLICY_DECISION_REQUIRED")]:
                with self.assertRaisesRegex(Denied, code):
                    gateway.create_vendor(**(base | changed))
            ref, duplicate = gateway.create_vendor(**base)
            self.assertFalse(duplicate)
            self.assertEqual(provider.find_execution("missing"), None)
            restarted = ActionGateway(registry, provider)
            self.assertEqual(restarted.create_vendor(**base), (ref, True))
            with self.assertRaisesRegex(Denied, "IDEMPOTENCY_KEY_CONFLICT"):
                restarted.create_vendor(**(base | {"vendor": "two"}))
            durable_conflict = ActionGateway(registry, provider)
            with self.assertRaisesRegex(Denied, "IDEMPOTENCY_KEY_CONFLICT"):
                durable_conflict.create_vendor(**(base | {"vendor": "two"}))
            with self.assertRaisesRegex(Denied, "PROVIDER_IDEMPOTENCY_CONFLICT"):
                provider.create("acme", "one", "other-execution", "other-hash")
            provider.close()

    def test_manifest_must_include_every_forbidden_class(self):
        incomplete = TransferManifest("s", "v1", "v2", 1, 2, (("o", 1),), (),
                                      ("secret",), ("e",), "d")
        with self.assertRaisesRegex(Denied, "MANIFEST_EXCLUSIONS_INCOMPLETE"):
            validate_manifest(incomplete)


class ContractDefensivePathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = TemporaryDirectory()
        cls.bundle = build_contract_bundle(Path(cls.directory.name))

    @classmethod
    def tearDownClass(cls): cls.directory.cleanup()

    def test_json_uri_timestamp_and_envelope_failures(self):
        for value, code in [({1: "x"}, "NON_STRING_KEY"), ({"x": object()}, "UNSUPPORTED_JSON_TYPE")]:
            with self.assertRaisesRegex(ContractError, code): canonical_bytes(value)
        base = self.bundle["artifacts"][0]
        for changed, code in [
            ({"extra": True}, "ENVELOPE_FIELDS_INVALID"),
            ({"protocol": "other"}, "UNSUPPORTED_PROTOCOL"),
            ({"artifact_type": "other"}, "UNKNOWN_ARTIFACT_TYPE"),
            ({"artifact_id": "relative"}, "INVALID_URI"),
            ({"issued_at": "2026-08-17"}, "UTC_Z_REQUIRED"),
            ({"issued_at": "not-a-dateZ"}, "INVALID_TIMESTAMP"),
            ({"required_features": ["b", "a", "a"]}, "REQUIRED_FEATURES_NOT_CANONICAL"),
        ]:
            item = deepcopy(base); item.update(changed)
            if "extra" not in changed and code not in {"ENVELOPE_FIELDS_INVALID", "UNSUPPORTED_PROTOCOL", "UNKNOWN_ARTIFACT_TYPE", "INVALID_URI", "UTC_Z_REQUIRED", "INVALID_TIMESTAMP", "REQUIRED_FEATURES_NOT_CANONICAL"}:
                item["digest"]["value"] = artifact_digest(item)
            with self.assertRaisesRegex(ContractError, code): validate_envelope(item)
        with self.assertRaisesRegex(ContractError, "UNKNOWN_ARTIFACT_TYPE"):
            make_envelope("other", "urn:x", "urn:i", ISSUED, {})

    def test_body_schema_and_invariants(self):
        with self.assertRaisesRegex(ContractError, "MISSING_BODY_FIELDS"):
            validate_body("obligation", {})
        body = deepcopy(self.bundle["artifacts"][0]["body"])
        body["extra"] = True
        with self.assertRaisesRegex(ContractError, "UNKNOWN_BODY_FIELDS"):
            validate_body("obligation", body)
        body.pop("extra"); body["revision"] = 0
        with self.assertRaisesRegex(ContractError, "INVALID_REVISION"): validate_body("obligation", body)
        grant = deepcopy(next(a for a in self.bundle["artifacts"] if a["artifact_type"] == "authority_grant")["body"])
        grant["status"] = "BAD"
        with self.assertRaisesRegex(ContractError, "INVALID_GRANT_STATUS"): validate_body("authority_grant", grant)
        manifest = deepcopy(next(a for a in self.bundle["artifacts"] if a["artifact_type"] == "succession_manifest")["body"])
        manifest["successor"]["epoch"] = manifest["predecessor"]["epoch"]
        with self.assertRaisesRegex(ContractError, "NON_MONOTONIC_EPOCH"): validate_body("succession_manifest", manifest)
        revocation = deepcopy(next(a for a in self.bundle["artifacts"] if a["artifact_type"] == "revocation_proof")["body"])
        revocation["enforcement_points"] = []
        with self.assertRaisesRegex(ContractError, "REVOCATION_PROOF_INCOMPLETE"): validate_body("revocation_proof", revocation)
        att = deepcopy(next(a for a in self.bundle["artifacts"] if a["artifact_type"] == "continuity_attestation")["body"])
        att["guarantees"]["obligation_preserved"] = False
        with self.assertRaisesRegex(ContractError, "VERIFIED_GUARANTEES_INVALID"): validate_body("continuity_attestation", att)
        att["outcome"] = "FAILED"
        validate_body("continuity_attestation", att)
        with self.assertRaisesRegex(ContractError, "UNKNOWN_ARTIFACT_TYPE"): validate_body("other", {})

    def test_grant_authorization_every_denial(self):
        grant = next(a for a in self.bundle["artifacts"] if a["artifact_type"] == "authority_grant")
        args = dict(now="2026-08-17T10:30:00Z", tenant_id="acme",
                    principal="urn:continuum:principal:acme:procurement:v18",
                    authority_domain="urn:continuum:authority:acme:procurement-agent", epoch=42,
                    obligation_id="urn:continuum:obligation:acme:vendor-042", capability="vendor.create",
                    memory_scope="vendor.approved", purpose="complete vendor-042 onboarding")
        authorize_grant(grant, **args)
        receipt = next(a for a in self.bundle["artifacts"] if a["artifact_type"] == "execution_receipt")
        with self.assertRaisesRegex(ContractError, "NOT_AUTHORITY_GRANT"): authorize_grant(receipt, **args)
        cases = [
            ({"tenant_id": "other"}, "RESOURCE_NOT_FOUND"),
            ({"status": "REVOKED"}, "GRANT_NOT_ACTIVE"),
            ({"subject_principal": "urn:other"}, "AUTHORITY_BINDING_MISMATCH"),
        ]
        for body_change, code in cases:
            changed = deepcopy(grant); changed["body"].update(body_change); changed["digest"]["value"] = artifact_digest(changed)
            with self.assertRaisesRegex(ContractError, code): authorize_grant(changed, **args)
        with self.assertRaisesRegex(ContractError, "GRANT_EXPIRED_OR_NOT_YET_VALID"):
            authorize_grant(grant, **(args | {"now": "2026-08-17T12:00:00Z"}))
        for changed in ({"obligation_id": "other"}, {"capability": "other"},
                        {"memory_scope": "other"}, {"purpose": "other"}):
            with self.assertRaisesRegex(ContractError, "GRANT_SCOPE_MISMATCH"):
                authorize_grant(grant, **(args | changed))

    def test_signature_algorithm_and_bundle_failures_and_mutation_helper(self):
        unsigned = deepcopy(self.bundle["artifacts"][0])
        unsigned["signatures"] = [{"alg": "other", "key_id": "urn:key", "signed_at": ISSUED, "value": ""}]
        with self.assertRaisesRegex(ContractError, "UNSUPPORTED_SIGNATURE_ALGORITHM"):
            verify_ed25519(unsigned, lambda _: None)
        with self.assertRaisesRegex(ContractError, "BUNDLE_ARTIFACT_SET_INCOMPLETE"):
            verify_bundle({"artifacts": []})
        changed = deepcopy(self.bundle)
        att = next(a for a in changed["artifacts"] if a["artifact_type"] == "continuity_attestation")
        att["body"]["obligation"]["artifact_id"] = "urn:missing"
        att["digest"]["value"] = artifact_digest(att)
        with self.assertRaisesRegex(ContractError, "BROKEN_ARTIFACT_REFERENCE"): verify_bundle(changed)
        self.assertEqual(mutate_copy(self.bundle, "obligation", "status", "OPEN")["artifacts"][0]["body"]["status"], "OPEN")


class RuntimeAndInterfacePathTests(unittest.TestCase):
    def test_api_lookup_and_environment_defaults(self):
        with TemporaryDirectory() as directory:
            service = ScenarioService(Path(directory))
            with self.assertRaisesRegex(Exception, "RUN_NOT_FOUND"): service.get("missing")
            with patch.dict("os.environ", {"CONTINUUM_DATA_DIR": directory, "CONTINUUM_DEMO_MODE": "1"}, clear=True):
                client = TestClient(create_app())
                run_id = client.post("/api/scenarios").json()["run_id"]
                self.assertEqual(client.get(f"/api/scenarios/{run_id}").status_code, 200)

    def test_cli_entrypoint(self):
        with TemporaryDirectory() as directory, patch.object(sys, "argv", ["continuum", "--output", directory]), patch("builtins.print") as output:
            runpy.run_module("continuum.__main__", run_name="__main__")
        self.assertIn('"outcome": "VERIFIED"', output.call_args.args[0])

    def test_recovery_missing_and_cas_conflict(self):
        with TemporaryDirectory() as directory:
            runtime = RecoveryRuntime(Path(directory) / "journal.db")
            with self.assertRaisesRegex(ValueError, "SUCCESSION_NOT_FOUND"): runtime.state("missing")
            runtime.initialize("s")
            original = runtime.connection
            fake_cursor = Mock(rowcount=0)
            fake = Mock(); fake.__enter__ = Mock(return_value=fake); fake.__exit__ = Mock(return_value=False)
            fake.execute.return_value = fake_cursor
            runtime.connection = fake
            with patch.object(runtime, "state", return_value=("OPEN", "v17", 41, "AT_RISK")), self.assertRaisesRegex(ValueError, "SUCCESSION_CAS_CONFLICT"):
                runtime.resume("s")
            runtime.connection = original; runtime.close()

    def test_temporary_scenario_cleanup_paths(self):
        self.assertEqual(run_scenario(signals=("missed_evidence",))["outcome"], "INVESTIGATE_HOLD")
        self.assertEqual(run_scenario()["outcome"], "VERIFIED")

    def test_conformance_failure_helpers_return_false_when_dependencies_do_not_raise(self):
        self.assertEqual(_run("x", "C0", "false", lambda: False).status, "FAIL")
        self.assertEqual(_run("x", "C0", "error", lambda: 1 / 0).status, "FAIL")
        registry = Mock(); registry.authorize.return_value = object()
        with patch("continuum.conformance._registry", return_value=registry): self.assertFalse(_cross_tenant_denied())
        with patch("continuum.core.decide_compromise", return_value=object()): self.assertFalse(_fabricated_citation())
        with patch("continuum.conformance.validate_envelope", return_value=None): self.assertFalse(_unsupported_feature(self._bundle()))
        with patch("continuum.conformance.verify_bundle", return_value=None):
            self.assertFalse(_broken_reference(self._bundle())); self.assertFalse(_self_attestation_rejected(self._bundle()))
        self.assertTrue(_roundtrip_bundle(self._bundle()))
        with TemporaryDirectory() as directory, patch("continuum.conformance.ActionGateway.create_vendor", return_value=("p", False)):
            self.assertFalse(_idempotency_conflict(Path(directory) / "idempotency"))
        losing = AgentRegistry(); losing.register(agent())
        with patch("continuum.conformance._registry", return_value=losing), patch.object(losing, "activate", return_value=None):
            self.assertFalse(_one_successor_wins())

    def test_conformance_level_progression_stops_after_a_failed_level(self):
        from continuum.conformance import CaseResult, run_conformance
        calls = 0
        def result(case_id, level, assertion, fn):
            nonlocal calls; calls += 1
            return CaseResult(case_id, level, "FAIL" if calls == 1 else "PASS", assertion, "forced", 0, "0" * 64)
        with TemporaryDirectory() as directory, patch("continuum.conformance._run", side_effect=result):
            report = run_conformance(Path(directory))
        self.assertIsNone(report["highest_level"])
        self.assertTrue(all(level["status"] == "FAIL" for level in report["levels"].values()))

    def test_conformance_detects_a_broken_validator_as_a_failed_case(self):
        from continuum.conformance import run_conformance
        bundle = self._bundle()
        with TemporaryDirectory() as scenario_dir:
            canonical = run_scenario(Path(scenario_dir))
        with TemporaryDirectory() as output, \
             patch("continuum.conformance.build_contract_bundle", return_value=bundle), \
             patch("continuum.conformance.run_scenario", return_value=canonical), \
             patch("continuum.conformance.validate_envelope", return_value=None):
            report = run_conformance(Path(output))
        self.assertEqual(next(case for case in report["cases"] if case["id"] == "O02")["status"], "FAIL")

    def _bundle(self):
        with TemporaryDirectory() as directory: return build_contract_bundle(Path(directory))


if __name__ == "__main__":
    unittest.main()

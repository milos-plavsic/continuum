from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from unittest.mock import patch
import unittest
import json
from pathlib import Path

from fastapi.testclient import TestClient

from continuum.evidence import (
    EVIDENCE_PROFILE, EvidenceAuthentication, EvidenceDescriptor, EvidenceRecord,
    EvidenceRule, EvidenceTrustPolicy, assess_evidence, describe_evidence,
    evidence_record_from_dict,
)
from continuum.incident_policy import (
    INCIDENT_POLICY_ID, REVIEW, SUCCESSION, assess_incident, describe_lifecycle_events,
    validate_incident_receipt, verify_incident_evidence_chain,
)
from continuum.local_app import app
from continuum.local_runtime import (
    DeterministicInvestigator, LocalAuthority, LocalEffects, LocalIndependentVerifier,
    LocalLifecycleEvidence, LocalScenarioStore, run_local_succession,
)
from continuum.models import digest
from continuum.stress import _assert_invariants, _validated_conflict, run_concurrent_stress
from tests.incident_fixtures import incident_extension
from tests.test_verification_engine import pre_bundle
from continuum.verification import IndependentVerificationEngine


NOW = "2026-08-17T10:05:00Z"


def base_record() -> EvidenceRecord:
    return describe_evidence(
        evidence_id="e1", evidence_type="signal", subject="obligation", issuer="issuer",
        source_authority="ledger", observed_at="2026-08-17T10:04:30Z",
        expires_at="2026-08-17T10:06:00Z", payload={"value": 1},
        authentication_kind="digest", authentication_reference="event:e1",
        trust_policy="policy/1")


def base_policy() -> EvidenceTrustPolicy:
    return EvidenceTrustPolicy("policy/1", (
        EvidenceRule("signal", ("issuer",), ("ledger",), ("digest",), 60),))


class EvidenceProfileTests(unittest.TestCase):
    def test_round_trip_and_empty_receipt(self):
        record = base_record()
        self.assertEqual(evidence_record_from_dict(record.to_dict()), record)
        receipt = assess_evidence([record], base_policy(), now=NOW, expected_subject="obligation")
        self.assertTrue(receipt.valid)
        self.assertEqual(receipt.trusted_ids, ("e1",))
        self.assertFalse(assess_evidence([], base_policy(), now=NOW).valid)
        root = Path(__file__).resolve().parents[1]
        golden = json.loads((root / "fixtures/evidence-descriptor-v1.json").read_text())
        parsed = evidence_record_from_dict(golden)
        self.assertEqual(parsed.descriptor.profile, EVIDENCE_PROFILE)
        self.assertEqual(parsed.descriptor.payload_digest,
                         "sha256:" + digest(parsed.payload))
        schema = json.loads((root / "schemas/evidence-descriptor-v1.schema.json").read_text())
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["descriptor"]["properties"]["profile"]["const"],
                         EVIDENCE_PROFILE)

    def test_closed_record_schema_rejects_every_shape_and_type_boundary(self):
        good = base_record().to_dict()
        variants = [None, {}, {**good, "extra": 1},
                    {**good, "descriptor": []},
                    {**good, "descriptor": {**good["descriptor"], "extra": 1}},
                    {**good, "payload": []},
                    {**good, "descriptor": {**good["descriptor"], "authentication": []}},
                    {**good, "descriptor": {**good["descriptor"],
                     "authentication": {"kind": "digest"}}},
                    {**good, "descriptor": {**good["descriptor"], "issuer": 1}},
                    {**good, "descriptor": {**good["descriptor"],
                     "authentication": {"kind": 1, "reference": "e"}}}]
        for value in variants:
            with self.subTest(value=value), self.assertRaisesRegex(
                    ValueError, "EVIDENCE_RECORD_SCHEMA_INVALID"):
                evidence_record_from_dict(value)  # type: ignore[arg-type]

    def test_policy_and_timestamp_definitions_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "EVIDENCE_TIME_UTC_Z_REQUIRED"):
            assess_evidence([], base_policy(), now="2026-08-17")
        invalid_policies = [
            EvidenceTrustPolicy("", ()), EvidenceTrustPolicy("p", (), -1),
            EvidenceTrustPolicy("p", (EvidenceRule("x", ("i",), ("s",), ("a",), 1),
                                      EvidenceRule("x", ("i",), ("s",), ("a",), 1))),
            EvidenceTrustPolicy("p", (EvidenceRule("", ("i",), ("s",), ("a",), 1),)),
            EvidenceTrustPolicy("p", (EvidenceRule("x", (), ("s",), ("a",), 1),)),
            EvidenceTrustPolicy("p", (EvidenceRule("x", ("i",), (), ("a",), 1),)),
            EvidenceTrustPolicy("p", (EvidenceRule("x", ("i",), ("s",), (), 1),)),
            EvidenceTrustPolicy("p", (EvidenceRule("x", ("i",), ("s",), ("a",), -1),)),
        ]
        for policy in invalid_policies:
            with self.subTest(policy=policy), self.assertRaisesRegex(
                    ValueError, "EVIDENCE_TRUST_POLICY_INVALID"):
                assess_evidence([], policy, now=NOW)

    def test_each_trust_freshness_and_integrity_reason_is_explicit(self):
        record = base_record()
        descriptor = replace(
            record.descriptor, evidence_id="", evidence_type="unknown", subject="other",
            issuer="other", source_authority="other", observed_at="2026-08-17T10:07:00Z",
            expires_at="2026-08-17T10:06:00Z", payload_digest="bad",
            authentication=EvidenceAuthentication("", ""), trust_policy="other",
            profile="other")
        assessed = assess_evidence([EvidenceRecord(descriptor, record.payload)], base_policy(),
                                   now=NOW, expected_subject="obligation")
        reasons = set(assessed.assessments[0].reason_codes)
        self.assertTrue({"EVIDENCE_ID_INVALID_OR_DUPLICATE", "EVIDENCE_PROFILE_UNSUPPORTED",
                         "EVIDENCE_TYPE_UNTRUSTED", "EVIDENCE_POLICY_MISMATCH",
                         "EVIDENCE_SUBJECT_MISMATCH", "EVIDENCE_DIGEST_MALFORMED",
                         "EVIDENCE_AUTHENTICATION_MISSING", "EVIDENCE_EXPIRY_INVALID",
                         "EVIDENCE_FROM_FUTURE"}.issubset(reasons))
        mismatch = EvidenceRecord(replace(record.descriptor, payload_digest="sha256:" + "0" * 64),
                                  record.payload)
        untrusted = EvidenceRecord(replace(
            record.descriptor, issuer="bad", source_authority="bad",
            authentication=EvidenceAuthentication("bad", "ref"),
            observed_at="2026-08-17T10:00:00Z", expires_at="2026-08-17T10:04:00Z"),
            record.payload)
        duplicate = replace(record, descriptor=replace(record.descriptor, evidence_id="e1"))
        result = assess_evidence([record, duplicate, mismatch, untrusted], base_policy(), now=NOW)
        all_reasons = {reason for item in result.assessments for reason in item.reason_codes}
        self.assertTrue({"EVIDENCE_ID_INVALID_OR_DUPLICATE", "EVIDENCE_PAYLOAD_DIGEST_MISMATCH",
                         "EVIDENCE_ISSUER_UNTRUSTED", "EVIDENCE_SOURCE_AUTHORITY_UNTRUSTED",
                         "EVIDENCE_AUTHENTICATION_UNTRUSTED", "EVIDENCE_EXPIRED",
                         "EVIDENCE_TOO_OLD"}.issubset(all_reasons))
        invalid_time = EvidenceRecord(replace(record.descriptor, observed_at="bad"), record.payload)
        self.assertIn("EVIDENCE_TIME_INVALID", assess_evidence(
            [invalid_time], base_policy(), now=NOW).assessments[0].reason_codes)


class IncidentPolicyTests(unittest.TestCase):
    def test_missing_or_untrusted_signals_can_only_request_review(self):
        records = describe_lifecycle_events([
            {"type": "action.denied", "source": "action-gateway"}],
            subject="o", assessed_at=NOW)
        receipt, validation = assess_incident(records, assessed_at=NOW, subject="o")
        self.assertTrue(validation["valid"])
        self.assertEqual(receipt.allowed_remediations, (REVIEW,))
        broken = replace(records[0], descriptor=replace(records[0].descriptor, issuer="bad"))
        receipt, validation = assess_incident([broken], assessed_at=NOW, subject="o")
        self.assertFalse(validation["valid"])
        self.assertEqual(receipt.reason_codes, ("EVIDENCE_UNTRUSTED",))

    def test_incident_receipt_rejects_schema_digest_types_and_policy_substitution(self):
        good = incident_extension()["incident_assessment"]
        variants = [({}, "SCHEMA"), ({**good, "receipt_digest": "bad"}, "DIGEST")]
        malformed = {**good, "signal_types": "bad"}
        body = {key: malformed[key] for key in malformed if key != "receipt_digest"}
        malformed["receipt_digest"] = digest(body); variants.append((malformed, "SCHEMA"))
        malformed = {**good, "evidence_valid": 1}
        body = {key: malformed[key] for key in malformed if key != "receipt_digest"}
        malformed["receipt_digest"] = digest(body); variants.append((malformed, "SCHEMA"))
        policy = {**good, "allowed_remediations": [REVIEW]}
        body = {key: policy[key] for key in policy if key != "receipt_digest"}
        policy["receipt_digest"] = digest(body); variants.append((policy, "POLICY_MISMATCH"))
        for value, code in variants:
            with self.subTest(code=code), self.assertRaisesRegex(RuntimeError, code):
                validate_incident_receipt(value)

    def test_exported_chain_is_fully_recomputed_and_mutation_fails(self):
        extension = incident_extension()
        verify_incident_evidence_chain(records=extension["records"],
            evidence_receipt=extension["evidence_validation"],
            incident_receipt=extension["incident_assessment"], subject=extension["subject"])
        with self.assertRaisesRegex(RuntimeError, "CHAIN_SCHEMA"):
            verify_incident_evidence_chain(records=[], evidence_receipt=[],
                incident_receipt={}, subject="o")  # type: ignore[arg-type]
        malformed = deepcopy(extension); malformed["records"][0] = {}
        with self.assertRaisesRegex(RuntimeError, "CHAIN_SCHEMA"):
            verify_incident_evidence_chain(records=malformed["records"],
                evidence_receipt=malformed["evidence_validation"],
                incident_receipt=malformed["incident_assessment"], subject=malformed["subject"])
        changed = deepcopy(extension); changed["evidence_validation"]["records_digest"] = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "VALIDATION_RECEIPT_MISMATCH"):
            verify_incident_evidence_chain(records=changed["records"],
                evidence_receipt=changed["evidence_validation"],
                incident_receipt=changed["incident_assessment"], subject=changed["subject"])

    def test_exported_chain_survives_json_and_firestore_array_normalization(self):
        extension = incident_extension()
        durable = json.loads(json.dumps(extension))
        verify_incident_evidence_chain(
            records=durable["records"],
            evidence_receipt=durable["evidence_validation"],
            incident_receipt=durable["incident_assessment"],
            subject=durable["subject"],
        )
        self.assertIsInstance(
            durable["evidence_validation"]["assessments"][0]["reason_codes"], list)
        self.assertIsInstance(durable["incident_assessment"]["signal_types"], list)
        changed = deepcopy(extension); changed["incident_assessment"]["receipt_digest"] = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "INCIDENT_EVIDENCE_CHAIN_MISMATCH"):
            verify_incident_evidence_chain(records=changed["records"],
                evidence_receipt=changed["evidence_validation"],
                incident_receipt=changed["incident_assessment"], subject=changed["subject"])


class LocalRuntimeAndStressTests(unittest.TestCase):
    def test_complete_local_profile_and_http_surface(self):
        result = run_local_succession("local-test")
        self.assertEqual((result["phase"], result["provider_observation"]["effect_count"]),
                         ("VERIFIED", 1))
        client = TestClient(app)
        self.assertEqual(client.get("/health").json()["profile"], "reference-local-container/1")
        self.assertEqual(client.post("/runs/http-test").json()["phase"], "VERIFIED")
        with patch("continuum.local_app.run_local_succession", side_effect=ValueError("conflict")):
            self.assertEqual(client.post("/runs/bad").status_code, 409)

    def test_local_defensive_paths(self):
        store = LocalScenarioStore(); self.assertIsNone(store.load("missing"))
        value = {"run_id": "r", "phase": "A"}; store.create(value)
        self.assertTrue(store.create(value)[1])
        with self.assertRaisesRegex(RuntimeError, "CAS_CONFLICT"):
            store.advance("r", "B", "C", {}, {})
        evidence = LocalLifecycleEvidence(); request = {
            "run_id": "r", "obligation_id": "o", "now": "2026-08-17T10:00:00Z",
            "deadline": "2026-08-17T10:01:00Z"}
        evidence.record_initial(request); self.assertIsNone(evidence.detect_missing(request))
        later = {**request, "now": "2026-08-17T10:02:00Z"}
        first = evidence.detect_missing(later); self.assertEqual(evidence.detect_missing(later), first)
        investigator = DeterministicInvestigator()
        with self.assertRaisesRegex(ValueError, "INPUT_INVALID"):
            investigator.investigate({})
        proposal = investigator.investigate({"allowed_remediations": [REVIEW],
            "eligible_candidates": [{"trust_score": 1, "candidate_id": "c",
                                     "evidence_refs": ["image:c", "health:c", "other:c"]}],
            "evidence": [{"type": "x"}], "selection_objective": "safe"})
        self.assertEqual(proposal["proposed_actions"], [REVIEW])
        authority = LocalAuthority(); self.assertEqual(authority.decide([])["outcome"], "HOLD")
        self.assertEqual(authority.decide([{"kind": "investigation.observed",
            "evidence": {"incident_assessment": {}, "selected_plan": SUCCESSION}}])["outcome"], "HOLD")
        self.assertEqual(authority.decide([{"kind": "investigation.observed",
            "evidence": {"incident_assessment": incident_extension()["incident_assessment"],
                         "selected_plan": REVIEW}}])["outcome"], "HOLD")
        authority.revoked_through = 5
        with self.assertRaisesRegex(ValueError, "EPOCH_INVALID"):
            authority.activate_successor({"epoch": 5, "principal": "v"})
        effects = LocalEffects(); request_effect = {"idempotency_key": "k", "request_digest": "a",
            "vendor_id": "v", "compliance_evidence_id": "e"}
        self.assertEqual(effects.reconcile(request_effect), {"effect_count": 0})
        self.assertEqual(effects.execute(request_effect)["state"], "DISPATCHED")
        self.assertEqual(effects.execute(request_effect)["state"], "DEDUPLICATED")
        with self.assertRaisesRegex(ValueError, "IDEMPOTENCY_CONFLICT"):
            effects.execute({**request_effect, "request_digest": "b"})
        verifier = LocalIndependentVerifier()
        self.assertEqual(verifier.verify({"bundle": {}, "provider_observation": {}})["status"], "FAIL")

    def test_concurrent_invariants_and_fail_closed_helpers(self):
        result = run_concurrent_stress(run_count=4, attempts_per_run=3)
        self.assertEqual(result.to_dict()["profile"], "continuum/concurrent-stress/1")
        self.assertEqual((result.provider_effects, result.deduplicated_attempts,
                          result.conflicts_rejected), (4, 8, 4))
        with self.assertRaisesRegex(ValueError, "DIMENSIONS_TOO_SMALL"):
            run_concurrent_stress(run_count=1, attempts_per_run=2)
        self.assertEqual(_validated_conflict(ValueError("SDK_IDEMPOTENCY_CONFLICT")), 1)
        with self.assertRaisesRegex(ValueError, "other"):
            _validated_conflict(ValueError("other"))
        broken = {"profile": "continuum/concurrent-stress/1", "run_count": 2,
                  "attempts_per_run": 2, "provider_effects": 1,
                  "deduplicated_attempts": 2, "conflicts_rejected": 2,
                  "isolated_provider_refs": 2}
        with self.assertRaisesRegex(RuntimeError, "INVARIANT_VIOLATED"):
            _assert_invariants(broken)

    def test_verifier_rejects_incident_extension_schema_and_recomputed_chain(self):
        bundle = pre_bundle()
        manifest = next(item for item in bundle["artifacts"]
                        if item["artifact_type"] == "succession_manifest")
        bad_schema = deepcopy(manifest)
        bad_schema["extensions"]["continuum.dev/incident-evidence"]["extra"] = True
        with self.assertRaisesRegex(Exception, "INCIDENT_EVIDENCE_SCHEMA_INVALID"):
            IndependentVerificationEngine._validate_handoff_extensions(bad_schema)
        bad_chain = deepcopy(manifest)
        bad_chain["extensions"]["continuum.dev/incident-evidence"]["evidence_validation"][
            "records_digest"] = "0" * 64
        with self.assertRaisesRegex(Exception, "EVIDENCE_VALIDATION_RECEIPT_MISMATCH"):
            IndependentVerificationEngine._validate_handoff_extensions(bad_chain)


if __name__ == "__main__":
    unittest.main()

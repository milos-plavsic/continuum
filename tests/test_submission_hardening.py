from dataclasses import replace
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from continuum.external_queue import GitHubIssueWorkQueue
from continuum.fleet_registry import FleetPublication, FirestoreFleetCatalog, InMemoryFleetCatalog
from continuum.model_armor import DeterministicInputGuard, GoogleModelArmorGuard, RAW_ATTACK_FIXTURE
from continuum.models import AgentStatus, digest
from continuum.succession_selection import (SuccessorCandidate, SuccessionRequirements,
    SelectionGovernancePolicy, SelectionObjective, admit_successor_choice,
    assess_candidates, canonical_selection_objective, govern_successor_selection,
    validate_selection_governance_receipt)


def candidate(principal, recovery, assurance, department):
    del department
    return SuccessorCandidate(principal, "1", "acme", AgentStatus.REGISTERED,
        "sha256:" + principal, principal + "@example", ("vendor.create",),
        ("vendor.approved",), ("procurement",), ("EU",), ("continuity/1",),
        "HEALTHY", 90, (f"build:{principal}", f"health:{principal}",
        f"recovery:{principal}:{recovery}s", f"assurance:{principal}:{assurance.lower()}",
        f"warm-state:{principal}:warm"), recovery, assurance, "WARM")


class Response:
    def __init__(self, body): self.body = body
    def __enter__(self): return self
    def __exit__(self, *args): return None
    def read(self): return json.dumps(self.body).encode()


class SubmissionHardeningTests(unittest.TestCase):
    def test_selection_governance_records_baseline_deviation_and_review_boundary(self):
        fast = candidate("fast", 12, "HIGH", "finance")
        assured = candidate("assured", 80, "VERY_HIGH", "security")
        requirements = SuccessionRequirements("acme", "old", "vendor.create", "vendor.approved",
                                              "procurement", "EU", "continuity/1")
        receipt = assess_candidates((fast, assured), requirements)
        sandbox = govern_successor_selection(
            selected_candidate_id="fast", receipt=receipt, model_available=True,
            decision_scope="SANDBOX_ONLY",
            value_at_risk={"currency": "EUR", "amount": 250000})
        self.assertEqual(sandbox["outcome"], "APPROVED")
        self.assertEqual(sandbox["deterministic_baseline_candidate_id"], "assured")
        self.assertTrue(sandbox["deviates_from_baseline"])
        self.assertEqual(sandbox["reason_code"], "SANDBOX_AUTONOMY")
        held = govern_successor_selection(
            selected_candidate_id="fast", receipt=receipt, model_available=True,
            decision_scope="PRODUCTION",
            value_at_risk={"currency": "EUR", "amount": 250000})
        self.assertEqual((held["outcome"], held["reason_code"]),
                         ("HOLD", "HUMAN_APPROVAL_REQUIRED"))
        approved = govern_successor_selection(
            selected_candidate_id="fast", receipt=receipt, model_available=True,
            decision_scope="PRODUCTION", human_approved=True,
            value_at_risk={"currency": "EUR", "amount": 250000})
        self.assertEqual(approved["reason_code"], "HUMAN_APPROVED")
        below = govern_successor_selection(
            selected_candidate_id="assured", receipt=receipt, model_available=True,
            decision_scope="PRODUCTION",
            value_at_risk={"currency": "EUR", "amount": 1})
        self.assertEqual(below["reason_code"], "BELOW_REVIEW_THRESHOLD")
        unavailable = govern_successor_selection(
            selected_candidate_id=None, receipt=receipt, model_available=False,
            decision_scope="SANDBOX_ONLY",
            value_at_risk={"currency": "EUR", "amount": 250000})
        self.assertEqual((unavailable["outcome"], unavailable["reason_code"]),
                         ("HOLD", "MODEL_UNAVAILABLE"))

    def test_selection_governance_rejects_invalid_policy_state_and_inputs(self):
        with self.assertRaisesRegex(ValueError, "POLICY_INVALID"):
            SelectionGovernancePolicy(policy_id="", production_review_amount=0)
        valid = candidate("valid", 12, "HIGH", "x")
        requirements = SuccessionRequirements("acme", "old", "vendor.create", "vendor.approved",
                                              "procurement", "EU", "continuity/1")
        receipt = assess_candidates((valid,), requirements)
        invalid_inputs = [
            {"decision_scope": "UNKNOWN", "value_at_risk": {"amount": 1}},
            {"decision_scope": "PRODUCTION", "value_at_risk": {"amount": True}},
            {"decision_scope": "PRODUCTION", "value_at_risk": {"amount": -1}},
        ]
        for values in invalid_inputs:
            with self.assertRaisesRegex(ValueError, "INPUT_INVALID"):
                govern_successor_selection(selected_candidate_id="valid", receipt=receipt,
                    model_available=True, **values)
        with self.assertRaisesRegex(Exception, "CHOICE_INVALID"):
            govern_successor_selection(selected_candidate_id="unknown", receipt=receipt,
                model_available=True, decision_scope="SANDBOX_ONLY",
                value_at_risk={"amount": 1})
        with self.assertRaisesRegex(Exception, "MODEL_STATE_INVALID"):
            govern_successor_selection(selected_candidate_id="valid", receipt=receipt,
                model_available=False, decision_scope="SANDBOX_ONLY",
                value_at_risk={"amount": 1})
        empty = assess_candidates((replace(valid, health="DOWN"),), requirements)
        with self.assertRaisesRegex(Exception, "NO_ELIGIBLE"):
            govern_successor_selection(selected_candidate_id=None, receipt=empty,
                model_available=False, decision_scope="SANDBOX_ONLY",
                value_at_risk={"amount": 1})

    def test_independent_selection_governance_recomputation_rejects_every_boundary(self):
        receipt = assess_candidates((candidate("fast", 12, "HIGH", "x"),
            candidate("assured", 80, "VERY_HIGH", "x")),
            SuccessionRequirements("acme", "old", "vendor.create", "vendor.approved",
                                   "procurement", "EU", "continuity/1"))
        assessment = receipt.to_dict()
        valid = govern_successor_selection(selected_candidate_id="fast", receipt=receipt,
            model_available=True, decision_scope="SANDBOX_ONLY",
            value_at_risk={"currency": "EUR", "amount": 250000})
        self.assertEqual(validate_selection_governance_receipt(
            governance=valid, assessment=assessment, successor_id="fast"), valid)

        def signed(**changes):
            value = {**valid, **changes}
            value["receipt_digest"] = digest({key: item for key, item in value.items()
                                               if key != "receipt_digest"})
            return value

        cases = [
            (None, assessment, "fast", "RECEIPT_SCHEMA_INVALID"),
            ({**valid, "extra": True}, assessment, "fast", "RECEIPT_SCHEMA_INVALID"),
            (valid, None, "fast", "ASSESSMENT_MISMATCH"),
            (valid, {**assessment, "receipt_digest": "other"}, "fast", "ASSESSMENT_MISMATCH"),
            ({**valid, "receipt_digest": "bad"}, assessment, "fast", "RECEIPT_DIGEST_MISMATCH"),
            (valid, {**assessment, "assessments": []}, "fast", "BASELINE_INVALID"),
            (valid, {**assessment, "assessments": [{"eligible": True}]}, "fast", "BASELINE_INVALID"),
            (valid, assessment, "other", "SUCCESSOR_MISMATCH"),
            (signed(selected_candidate_id="missing"), assessment, "missing", "SUCCESSOR_MISMATCH"),
            (signed(deterministic_baseline_candidate_id="fast"), assessment, "fast", "BASELINE_MISMATCH"),
            (signed(deviates_from_baseline=False), assessment, "fast", "BASELINE_MISMATCH"),
            (signed(outcome="HOLD"), assessment, "fast", "NOT_APPROVED"),
            (signed(model_available=False), assessment, "fast", "NOT_APPROVED"),
            (signed(decision_scope="OTHER"), assessment, "fast", "INPUT_INVALID"),
            (signed(value_at_risk={"amount": True}), assessment, "fast", "INPUT_INVALID"),
            (signed(value_at_risk={"amount": -1}), assessment, "fast", "INPUT_INVALID"),
            (signed(reason_code="OTHER"), assessment, "fast", "REASON_INVALID"),
            (signed(decision_scope="PRODUCTION", reason_code="HUMAN_APPROVED"),
             assessment, "fast", "REASON_INVALID"),
        ]
        for governance, current_assessment, successor, code in cases:
            with self.subTest(code=code), self.assertRaisesRegex(Exception, code):
                validate_selection_governance_receipt(
                    governance=governance, assessment=current_assessment,
                    successor_id=successor)
    def test_raw_attack_is_blocked_before_model_and_google_response_is_fail_closed(self):
        local = DeterministicInputGuard().sanitize(text=RAW_ATTACK_FIXTURE, run_id="r")
        self.assertFalse(local["allowed_to_model"])
        google = GoogleModelArmorGuard(project="p", location="us-central1", template="t",
            post=lambda u, p: {"sanitizationResult": {"filterMatchState": "MATCH_FOUND",
                "filterResults": {"pi_and_jailbreak": {"piAndJailbreakFilterResult": {
                    "executionState": "EXECUTION_SUCCESS"}}}}})
        receipt = google.sanitize(text=RAW_ATTACK_FIXTURE, run_id="r")
        self.assertEqual(receipt["provider"], "google-model-armor")
        with self.assertRaisesRegex(ValueError, "INCONCLUSIVE"):
            GoogleModelArmorGuard(project="p", location="x", template="t",
                post=lambda u, p: {"sanitizationResult": {}}).sanitize(text="x", run_id="r")

    def test_cross_department_catalog_and_tradeoff_are_separate_from_eligibility(self):
        fast = candidate("fast", 12, "HIGH", "finance")
        assured = candidate("assured", 80, "VERY_HIGH", "security")
        catalog = InMemoryFleetCatalog((
            FleetPublication("finance", "fin", "2026-08-27T00:00:00Z", fast),
            FleetPublication("security", "sec", "2026-08-27T00:00:00Z", assured)))
        requirements = SuccessionRequirements("acme", "old", "vendor.create", "vendor.approved",
                                              "procurement", "EU", "continuity/1")
        receipt = assess_candidates(catalog.discover(requirements), requirements)
        manifest = sorted({ref for item in receipt.assessments for ref in item.evidence_refs})
        objective = canonical_selection_objective()
        choice = {"selected_candidate_id": "fast", "evidence_manifest_refs": manifest,
            "supporting_citations": [
                {"claim":"RECOVERY_READINESS", "evidence_refs":["recovery:fast:12s"]},
                {"claim":"ASSURANCE_PROFILE", "evidence_refs":["assurance:fast:high"]}],
            "rationale":"restore rapidly with high assurance", "objective": objective.objective_id}
        self.assertEqual(admit_successor_choice(choice, receipt, objective), "fast")
        choice["objective"] = "max-trust"
        with self.assertRaisesRegex(Exception, "OBJECTIVE_MISMATCH"):
            admit_successor_choice(choice, receipt, objective)
        foreign = replace(fast, principal_id="foreign", tenant_id="other")
        self.assertEqual(InMemoryFleetCatalog((FleetPublication(
            "finance", "fin", "2026-08-27T00:00:00Z", foreign),)).discover(requirements), ())

    def test_external_queue_converges_one_reversible_resource(self):
        calls = []
        def opener(request, timeout):
            calls.append((request, timeout))
            payload = json.loads(request.data)
            return Response({**payload, "html_url": "https://github.test/o/r/issues/7", "number": 7})
        queue = GitHubIssueWorkQueue(repository="o/r", issue_number=7, token="secret", opener=opener)
        request = {"run_id":"r", "request_digest":"d", "compliance_evidence_id":"c"}
        first, second = queue.converge(request), queue.converge(request)
        self.assertEqual(first, second)
        self.assertEqual(first["reversible_action"], "close issue")
        self.assertEqual(len(calls), 2)

    def test_model_armor_validates_configuration_and_input(self):
        with self.assertRaisesRegex(ValueError, "CONFIG"):
            GoogleModelArmorGuard(project="", location="x", template="t", post=lambda u, p: {})
        guard = GoogleModelArmorGuard(project="p", location="x", template="t", post=lambda u, p: {})
        with self.assertRaisesRegex(ValueError, "INPUT"):
            guard.sanitize(text="", run_id="r")
        with self.assertRaisesRegex(ValueError, "RESPONSE_INVALID"):
            GoogleModelArmorGuard(project="p", location="x", template="t",
                post=lambda u, p: {}).sanitize(text="x", run_id="r")

    def test_firestore_catalog_is_immutable_queryable_and_conflict_safe(self):
        data = {}
        class Snapshot:
            def __init__(self, key): self.key = key
            @property
            def id(self): return self.key
            @property
            def create_time(self): return data[self.key].get("_created", "")
            @property
            def exists(self): return self.key in data
            def to_dict(self):
                return {key: value for key, value in
                        json.loads(json.dumps(data[self.key], default=lambda x: x.value)).items()
                        if key != "_created"}
        class Doc:
            def __init__(self, key): self.key = key
            def get(self): return Snapshot(self.key)
            def create(self, value): data[self.key] = value
        class Query:
            def stream(self): return [Snapshot(key) for key, value in data.items()
                if value["candidate"]["tenant_id"] == "acme"]
        class Collection:
            def document(self, key): return Doc(key)
            def where(self, *args): return Query()
        class DB:
            def collection(self, name): return Collection()
        publication = FleetPublication("finance", "fin", "2026-08-27T00:00:00Z",
                                       candidate("fleet", 20, "HIGH", "finance"))
        catalog = FirestoreFleetCatalog(DB())
        self.assertEqual(catalog.publish(publication), catalog.publish(publication))
        requirements = SuccessionRequirements("acme", "old", "vendor.create", "vendor.approved",
                                              "procurement", "EU", "continuity/1")
        self.assertEqual(catalog.discover(requirements)[0].principal_id, "fleet")
        newer = FleetPublication("finance", "fin", "2026-08-28T00:00:00Z",
                                  candidate("fleet", 25, "HIGH", "finance"))
        catalog.publish(newer)
        data[publication.publication_id]["_created"] = "2026-08-27T00:00:00Z"
        data[newer.publication_id]["_created"] = "2026-08-28T00:00:00Z"
        stale = FleetPublication("finance", "fin", "2026-08-26T00:00:00Z",
                                 candidate("fleet", 30, "HIGH", "finance"))
        catalog.publish(stale)
        data[stale.publication_id]["_created"] = "2026-08-26T00:00:00Z"
        self.assertEqual(catalog.discover(requirements)[0].recovery_time_seconds, 25)
        data[publication.publication_id]["owner"] = "attacker"
        with self.assertRaisesRegex(ValueError, "CONFLICT"): catalog.publish(publication)
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            InMemoryFleetCatalog((publication, publication))

    def test_external_queue_rejects_bad_configuration_and_provider_drift(self):
        with self.assertRaisesRegex(ValueError, "CONFIG"):
            GitHubIssueWorkQueue(repository="bad", issue_number=0, token="")
        queue = GitHubIssueWorkQueue(repository="o/r", issue_number=7, token="secret",
            opener=lambda req, timeout: Response({"state":"closed", "body":"x", "title":"x"}))
        with self.assertRaisesRegex(ValueError, "RECONCILIATION"):
            queue.converge({"run_id":"r", "request_digest":"d", "compliance_evidence_id":"c"})

    def test_tradeoff_contract_rejects_invalid_profiles_and_unsupported_choice(self):
        with self.assertRaisesRegex(ValueError, "OBJECTIVE_INVALID"):
            SelectionObjective("", "x", ("one",), ("UNKNOWN",))
        with self.assertRaisesRegex(ValueError, "TRADEOFF_PROFILE_INVALID"):
            candidate("bad", 0, "HIGH", "x")
        item = candidate("fast", 12, "HIGH", "x")
        requirements = SuccessionRequirements("acme", "old", "vendor.create", "vendor.approved",
                                              "procurement", "EU", "continuity/1")
        receipt = assess_candidates((item,), requirements)
        objective = canonical_selection_objective()
        base = {"selected_candidate_id":"fast", "evidence_manifest_refs":list(item.evidence_refs),
            "rationale":"x", "objective":objective.objective_id}
        with self.assertRaisesRegex(Exception, "TRADEOFF_UNSUPPORTED"):
            admit_successor_choice({**base, "supporting_citations":[
                {"claim":"BUILD_PROVENANCE", "evidence_refs":["build:fast"]}]}, receipt, objective)
        other = candidate("other", 12, "HIGH", "x")
        both = assess_candidates((other, item), requirements)
        all_refs = sorted(set(item.evidence_refs) | set(other.evidence_refs))
        with self.assertRaisesRegex(Exception, "SELECTED_SUPPORT_MISSING"):
            admit_successor_choice({**base, "evidence_manifest_refs":all_refs,
                "supporting_citations":[
                    {"claim":"RECOVERY_READINESS", "evidence_refs":["recovery:other:12s"]},
                    {"claim":"ASSURANCE_PROFILE", "evidence_refs":["assurance:other:high"]}]},
                both, objective)


if __name__ == "__main__": unittest.main()

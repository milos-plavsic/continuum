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
from continuum.models import AgentStatus
from continuum.succession_selection import (SuccessorCandidate, SuccessionRequirements,
    SelectionObjective, admit_successor_choice, assess_candidates, canonical_selection_objective)


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

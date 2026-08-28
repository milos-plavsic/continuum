from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from continuum.context_reconstruction import ContextItem, reconstruct_context
from continuum.contract import canonical_bytes
from continuum.external_witness import (
    content_digest, validate_external_statement, validate_review_request,
    verify_sigstore_statement,
)
from continuum.models import AgentStatus, Denied
from continuum.sdk import ContinuumClient, InProcessContinuum
from continuum.resilience import FaultResult, run_resilience_lab
from continuum.succession_selection import (
    SuccessorCandidate, SuccessionRequirements, admit_successor_choice,
    assess_candidates, model_candidate_view,
)
from continuum.witness import WitnessVerdict, aggregate_witnesses


def candidate(candidate_id="urn:agent:v18", **changes):
    values = dict(
        principal_id=candidate_id, version=candidate_id.rsplit(":", 1)[-1],
        tenant_id="acme", status=AgentStatus.REGISTERED,
        artifact_digest="sha256:" + candidate_id[-3:],
        service_identity=candidate_id + "@example", capabilities=("vendor.create",),
        memory_scopes=("vendor.approved",), authority_domains=("procurement",),
        jurisdictions=("EU",), contract_profiles=("continuity/1",), health="HEALTHY",
        trust_score=90, evidence_refs=("health:" + candidate_id, "build:" + candidate_id),
    )
    values.update(changes)
    return SuccessorCandidate(**values)


def requirements():
    return SuccessionRequirements(
        tenant_id="acme", predecessor_principal="urn:agent:v17",
        capability="vendor.create", memory_scope="vendor.approved",
        authority_domain="procurement", jurisdiction="EU",
        contract_profile="continuity/1", minimum_trust_score=80)


class SuccessorSelectionTests(unittest.TestCase):
    def test_multiple_candidates_are_assessed_before_model_choice(self):
        good = candidate()
        wrong_region = candidate("urn:agent:v19", jurisdictions=("US",))
        unhealthy = candidate("urn:agent:v20", health="DEGRADED")
        receipt = assess_candidates([unhealthy, good, wrong_region], requirements())
        self.assertEqual(receipt.eligible_ids, (good.principal_id,))
        reasons = {item.candidate_id: item.reason_codes for item in receipt.assessments}
        self.assertEqual(reasons[good.principal_id], ("ELIGIBLE",))
        self.assertEqual(reasons[wrong_region.principal_id], ("JURISDICTION_MISMATCH",))
        self.assertEqual(reasons[unhealthy.principal_id], ("HEALTH_UNVERIFIED",))
        self.assertEqual(model_candidate_view([wrong_region, good, unhealthy], receipt)[0]["candidate_id"], good.principal_id)
        choice = {"selected_candidate_id": good.principal_id,
                  "evidence_manifest_refs": list(good.evidence_refs),
                  "supporting_citations": [{"claim": "BUILD_PROVENANCE",
                                             "evidence_refs": [good.evidence_refs[1]]}],
                  "rationale": "highest verified trust", "objective": "assurance"}
        self.assertEqual(admit_successor_choice(choice, receipt), good.principal_id)
        self.assertEqual(receipt.to_dict()["eligible_ids"], [good.principal_id])
        self.assertIsInstance(canonical_bytes(receipt.to_dict()), bytes)

    def test_every_deterministic_rejection_is_visible(self):
        bad = candidate(
            "urn:agent:v17", tenant_id="other", status=AgentStatus.ACTIVE,
            health="UNKNOWN", capabilities=(), memory_scopes=(), authority_domains=(),
            jurisdictions=(), contract_profiles=(), trust_score=1)
        assessment = assess_candidates([bad], requirements()).assessments[0]
        self.assertFalse(assessment.eligible)
        self.assertEqual(set(assessment.reason_codes), {
            "PREDECESSOR_INELIGIBLE", "TENANT_MISMATCH", "LIFECYCLE_INELIGIBLE",
            "HEALTH_UNVERIFIED", "CAPABILITY_MISSING", "MEMORY_SCOPE_MISSING",
            "AUTHORITY_DOMAIN_MISMATCH", "JURISDICTION_MISMATCH",
            "CONTRACT_PROFILE_UNSUPPORTED", "TRUST_FLOOR_NOT_MET"})

    def test_candidate_and_choice_inputs_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "CANDIDATE_IDENTITY_INVALID"):
            candidate(principal_id="")
        for score in (-1, 101):
            with self.assertRaisesRegex(ValueError, "CANDIDATE_TRUST_SCORE_INVALID"):
                candidate(trust_score=score)
        with self.assertRaisesRegex(ValueError, "CANDIDATE_EVIDENCE_REQUIRED"):
            candidate(evidence_refs=())
        with self.assertRaisesRegex(ValueError, "CANDIDATE_PRINCIPAL_DUPLICATE"):
            assess_candidates([candidate(), candidate()], requirements())
        good = candidate()
        bad = candidate("urn:agent:v19", health="BAD")
        receipt = assess_candidates([good, bad], requirements())
        def choice(selected, manifest, citations):
            return {"selected_candidate_id": selected, "evidence_manifest_refs": manifest,
                    "supporting_citations": citations, "rationale": "x", "objective": "x"}
        build_citation = [{"claim": "BUILD_PROVENANCE",
                           "evidence_refs": [good.evidence_refs[1]]}]
        cases = [
            ({}, "SUCCESSOR_CHOICE_SCHEMA_INVALID"),
            ({"selected_candidate_id": 1, "evidence_manifest_refs": [],
              "supporting_citations": [], "rationale": "x", "objective": "x"},
             "SUCCESSOR_CHOICE_SCHEMA_INVALID"),
            (choice("unknown", ["x"], [{"claim": "BUILD_PROVENANCE",
                                         "evidence_refs": ["x"]}]),
             "SUCCESSOR_CHOICE_UNKNOWN"),
            (choice(bad.principal_id, list(bad.evidence_refs),
                    [{"claim": "BUILD_PROVENANCE", "evidence_refs": [bad.evidence_refs[1]]}]),
             "SUCCESSOR_CHOICE_INELIGIBLE"),
            (choice(good.principal_id, ["fabricated"], build_citation),
             "SUCCESSOR_CHOICE_EVIDENCE_INCOMPLETE"),
            (choice(good.principal_id, [good.evidence_refs[0]], build_citation),
             "SUCCESSOR_CHOICE_EVIDENCE_INCOMPLETE"),
            (choice(good.principal_id, [*good.evidence_refs, good.evidence_refs[0]],
                    build_citation), "SUCCESSOR_CHOICE_MANIFEST_INVALID"),
            (choice(good.principal_id, list(good.evidence_refs),
                    [{"claim": "BUILD_PROVENANCE", "evidence_refs": ["fabricated"]}]),
             "SUCCESSOR_CHOICE_CITATION_INVALID"),
            (choice(good.principal_id, list(good.evidence_refs), [{}]),
             "SUCCESSOR_CHOICE_CITATION_INVALID"),
            (choice(good.principal_id, list(good.evidence_refs),
                    [{"claim": "HEALTH_ATTESTED", "evidence_refs": [good.evidence_refs[1]]}]),
             "SUCCESSOR_CHOICE_CITATION_INVALID"),
            (choice(good.principal_id, list(good.evidence_refs), [*build_citation, *build_citation]),
             "SUCCESSOR_CHOICE_CITATION_DUPLICATE"),
        ]
        for value, code in cases:
            with self.subTest(code=code), self.assertRaisesRegex(Denied, code):
                admit_successor_choice(value, receipt)


class ContextReconstructionTests(unittest.TestCase):
    def test_only_minimum_authorized_context_crosses(self):
        now = datetime(2026, 8, 26, tzinfo=timezone.utc)
        base = ContextItem("obligation", "vendor.approved", "onboard vendor-042",
                           "sha256:obligation", "event:obligation")
        items = [
            base,
            replace(base, item_id="secret", classification="SECRET"),
            replace(base, item_id="raw", classification="RAW_UNTRUSTED"),
            replace(base, item_id="inference", classification="MODEL_INFERENCE"),
            replace(base, item_id="revoked", revoked=True),
            replace(base, item_id="untrusted", trusted=False),
            replace(base, item_id="nontransfer", transferable=False),
            replace(base, item_id="scope", scope="agent.private"),
            replace(base, item_id="purpose", purpose="unrelated"),
            replace(base, item_id="stale", expires_at=(now - timedelta(seconds=1)).isoformat()),
            replace(base, item_id="fresh", expires_at=(now + timedelta(seconds=1)).isoformat()),
            replace(base, item_id="missing", value_digest=""),
        ]
        receipt = reconstruct_context(
            succession_id="s1", successor_principal="urn:agent:v18",
            purpose="onboard vendor-042", allowed_scopes=["vendor.approved"],
            items=items, now=now)
        self.assertEqual(receipt.included_item_ids, ("fresh", "obligation"))
        self.assertEqual(len(receipt.excluded_item_ids), 10)
        self.assertEqual(receipt.to_dict()["included_item_ids"], ["fresh", "obligation"])
        self.assertTrue(receipt.receipt_digest)

    def test_reconstruction_rejects_invalid_identity_and_duplicate_items(self):
        item = ContextItem("one", "scope", "purpose", "sha256:value", "event:1")
        with self.assertRaisesRegex(ValueError, "RECONSTRUCTION_IDENTITY_INVALID"):
            reconstruct_context(succession_id="", successor_principal="p", purpose="x",
                                allowed_scopes=["scope"], items=[item])
        with self.assertRaisesRegex(ValueError, "CONTEXT_ITEM_DUPLICATE"):
            reconstruct_context(succession_id="s", successor_principal="p", purpose="x",
                                allowed_scopes=["scope"], items=[item, item])


class PortableSdkTests(unittest.TestCase):
    def setUp(self):
        self.effects = []
        self.runtime = InProcessContinuum(lambda body: self.effects.append(body) or "local://effect/1")
        self.client = ContinuumClient(self.runtime)
        self.registration = dict(principal_id="agent:v1", tenant_id="acme",
                                 capabilities=("send",), artifact_digest="sha256:v1")

    def test_three_calls_are_cloud_neutral_and_idempotent(self):
        self.client.register_agent(**self.registration)
        self.client.record_obligation(
            obligation_id="o1", tenant_id="acme", owner_principal="agent:v1",
            required_evidence=("approved",), value_at_risk={"amount": 250000, "currency": "EUR"})
        kwargs = dict(obligation_id="o1", principal_id="agent:v1", capability="send",
                      idempotency_key="effect-1", payload={"message": "approved"})
        self.assertFalse(self.client.execute_idempotent(**kwargs)["deduplicated"])
        self.assertTrue(self.client.execute_idempotent(**kwargs)["deduplicated"])
        self.assertEqual(len(self.effects), 1)
        self.assertEqual(self.runtime.evidence()["profile"], "continuum-local-sdk/1")

    def test_sdk_boundary_conflicts_and_denials(self):
        with self.assertRaisesRegex(ValueError, "SDK_AGENT_REGISTRATION_INVALID"):
            self.runtime.register_agent({})
        self.client.register_agent(**self.registration)
        self.client.register_agent(**self.registration)
        with self.assertRaisesRegex(ValueError, "SDK_AGENT_IMMUTABLE_CONFLICT"):
            self.client.register_agent(**{**self.registration, "artifact_digest": "different"})
        with self.assertRaisesRegex(ValueError, "SDK_OBLIGATION_INVALID"):
            self.runtime.record_obligation({})
        obligation = dict(obligation_id="o1", tenant_id="acme", owner_principal="agent:v1",
                          required_evidence=("approved",), value_at_risk={"amount": 1})
        self.client.record_obligation(**obligation)
        self.client.record_obligation(**obligation)
        with self.assertRaisesRegex(ValueError, "SDK_OBLIGATION_IMMUTABLE_CONFLICT"):
            self.client.record_obligation(**{**obligation, "value_at_risk": {"amount": 2}})
        with self.assertRaisesRegex(ValueError, "SDK_EXECUTION_INVALID"):
            self.runtime.execute_idempotent({})
        request = dict(obligation_id="missing", principal_id="agent:v1", capability="send",
                       idempotency_key="k", payload={})
        with self.assertRaisesRegex(ValueError, "SDK_RESOURCE_NOT_FOUND"):
            self.runtime.execute_idempotent(request)
        self.runtime.obligations["o1"]["owner_principal"] = "other"
        with self.assertRaisesRegex(PermissionError, "SDK_AUTHORITY_DENIED"):
            self.runtime.execute_idempotent({**request, "obligation_id": "o1"})
        self.runtime.obligations["o1"]["owner_principal"] = "agent:v1"
        with self.assertRaisesRegex(PermissionError, "SDK_CAPABILITY_DENIED"):
            self.runtime.execute_idempotent({**request, "obligation_id": "o1", "capability": "delete"})
        valid = {**request, "obligation_id": "o1"}
        self.runtime.execute_idempotent(valid)
        with self.assertRaisesRegex(ValueError, "SDK_IDEMPOTENCY_CONFLICT"):
            self.runtime.execute_idempotent({**valid, "payload": {"changed": True}})

    def test_example_runs_without_credentials(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, str(root / "examples/local_sdk_consumer.py")],
            cwd=root, env={"PYTHONPATH": str(root / "src")}, capture_output=True,
            text=True, check=True)
        output = json.loads(result.stdout)
        self.assertEqual(output["effect_count"], 1)
        self.assertTrue(output["second"]["deduplicated"])


class WitnessAggregationTests(unittest.TestCase):
    def verdict(self, principal, outcome="VERIFIED", bundle="bundle"):
        return WitnessVerdict(principal, bundle, outcome, principal + ":digest")

    def test_threshold_dissent_and_failure_are_explicit(self):
        verified = aggregate_witnesses([self.verdict("a"), self.verdict("b")],
                                       bundle_digest="bundle", threshold=2)
        self.assertEqual(verified["outcome"], "VERIFIED")
        self.assertFalse(verified["dissent"])
        inconclusive = aggregate_witnesses([self.verdict("a")], bundle_digest="bundle", threshold=2)
        self.assertEqual(inconclusive["outcome"], "INCONCLUSIVE")
        failed = aggregate_witnesses([self.verdict("a"), self.verdict("b", "FAILED")],
                                     bundle_digest="bundle", threshold=2)
        self.assertEqual(failed["outcome"], "FAILED")
        self.assertTrue(failed["dissent"])

    def test_invalid_witness_sets_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "WITNESS_THRESHOLD_INVALID"):
            aggregate_witnesses([], bundle_digest="b", threshold=0)
        with self.assertRaisesRegex(ValueError, "WITNESS_BUNDLE_MISMATCH"):
            aggregate_witnesses([self.verdict("a")], bundle_digest="other", threshold=1)
        with self.assertRaisesRegex(ValueError, "WITNESS_OUTCOME_INVALID"):
            aggregate_witnesses([self.verdict("a", "UNKNOWN")], bundle_digest="bundle", threshold=1)
        with self.assertRaisesRegex(ValueError, "WITNESS_EQUIVOCATION"):
            aggregate_witnesses([self.verdict("a"), self.verdict("a", "FAILED")],
                                bundle_digest="bundle", threshold=1)
        duplicate = self.verdict("a")
        result = aggregate_witnesses([duplicate, duplicate], bundle_digest="bundle", threshold=1)
        self.assertEqual(result["distinct_witnesses"], 1)

        request = json.loads((Path(__file__).resolve().parents[1] /
                              "docs/review/external-witness-request.json").read_text())
        self.assertEqual(validate_review_request(request)["request_digest"], request["request_digest"])
        reviewer = {"identity": "reviewer@example.com", "issuer": "https://accounts.example.test",
                    "display_name": "Independent Reviewer", "affiliation": "",
                    "relationship": "NO_PROJECT_ROLE", "conflicts": "none",
                    "independence_declared": True}
        statement = {
            "schema": "continuum/external-witness-statement/1.0", "statement_id": "review-001",
            "request_digest": request["request_digest"], "reviewer": reviewer,
            "reviewed_at": "2026-08-28T01:00:00Z", "expires_at": "2026-09-01T01:00:00Z",
            "verdict": "VERIFIED", "claim_results": [{
                "claim": request["claim_scope"][0], "status": "PASS",
                "evidence_refs": ["report.json"], "finding": "digest matched"}],
            "findings": [], "statement_digest": ""}
        statement["statement_digest"] = content_digest(statement, omitted="statement_digest")
        now = datetime(2026, 8, 28, 2, tzinfo=timezone.utc)
        self.assertEqual(validate_external_statement(
            statement, request=request, expected_identity=reviewer["identity"],
            expected_issuer=reviewer["issuer"], now=now)["verdict"], "VERIFIED")

        def request_error(change, code):
            value = json.loads(json.dumps(request)); change(value)
            with self.assertRaisesRegex(ValueError, code): validate_review_request(value)
        request_error(lambda value: value.update(extra=True), "REQUEST_SCHEMA")
        request_error(lambda value: value.update(schema="old"), "REQUEST_SCHEMA")
        request_error(lambda value: value.update(subject={}), "REQUEST_SUBJECT")
        request_error(lambda value: value.update(claim_scope=[]), "REQUEST_SCOPE")
        request_error(lambda value: value.update(review_tasks=[1]), "REQUEST_SCOPE")
        request_error(lambda value: value.update(non_claims=[""]), "REQUEST_SCOPE")
        request_error(lambda value: value.update(request_digest="bad"), "REQUEST_DIGEST")

        def statement_error(change, code, *, identity=reviewer["identity"],
                            issuer=reviewer["issuer"], clock=now):
            value = json.loads(json.dumps(statement)); change(value)
            if code != "STATEMENT_DIGEST":
                value["statement_digest"] = content_digest(value, omitted="statement_digest")
            with self.assertRaisesRegex(ValueError, code):
                validate_external_statement(value, request=request, expected_identity=identity,
                                            expected_issuer=issuer, now=clock)
        statement_error(lambda value: value.update(extra=True), "STATEMENT_SCHEMA")
        statement_error(lambda value: value.update(schema="old"), "STATEMENT_SCHEMA")
        statement_error(lambda value: value.update(reviewer={}), "REVIEWER_SCHEMA")
        statement_error(lambda value: None, "SIGNER_POLICY", identity="other")
        statement_error(lambda value: None, "SIGNER_POLICY", issuer="https://other")
        statement_error(lambda value: value["reviewer"].update(independence_declared=False),
                        "INDEPENDENCE_UNDECLARED")
        statement_error(lambda value: value.update(request_digest="sha256:" + "0" * 64),
                        "SUBJECT_MISMATCH")
        statement_error(lambda value: value.update(verdict="UNKNOWN"), "VERDICT_INVALID")
        statement_error(lambda value: value.update(claim_results=[]), "CLAIMS_INVALID")
        statement_error(lambda value: value.update(claim_results=["bad"]), "CLAIMS_INVALID")
        statement_error(lambda value: value["claim_results"][0].update(extra=True), "CLAIMS_INVALID")
        statement_error(lambda value: value["claim_results"][0].update(claim="OTHER"), "CLAIMS_INVALID")
        statement_error(lambda value: value.update(claim_results=[value["claim_results"][0]] * 2),
                        "CLAIMS_INVALID")
        statement_error(lambda value: value["claim_results"][0].update(status="UNKNOWN"),
                        "CLAIMS_INVALID")
        statement_error(lambda value: value["claim_results"][0].update(evidence_refs="bad"),
                        "CLAIMS_INVALID")
        statement_error(lambda value: value["claim_results"][0].update(evidence_refs=["x", "x"]),
                        "CLAIMS_INVALID")
        statement_error(lambda value: value["claim_results"][0].update(evidence_refs=[1]),
                        "CLAIMS_INVALID")
        statement_error(lambda value: value.update(reviewed_at=1), "TIME_INVALID")
        statement_error(lambda value: value.update(reviewed_at="bad"), "TIME_INVALID")
        statement_error(lambda value: value.update(reviewed_at="garbageZ"), "TIME_INVALID")
        statement_error(lambda value: value.update(expires_at=value["reviewed_at"]),
                        "STATEMENT_EXPIRED")
        statement_error(lambda value: None, "STATEMENT_EXPIRED",
                        clock=datetime(2026, 9, 2, tzinfo=timezone.utc))
        statement_error(lambda value: value.update(statement_digest="bad"), "STATEMENT_DIGEST")

        with TemporaryDirectory() as temporary:
            statement_path = Path(temporary) / "statement.json"
            bundle_path = Path(temporary) / "bundle.json"
            statement_path.write_text(json.dumps(statement)); bundle_path.write_text("{}")
            calls = []
            def runner(command, **kwargs):
                calls.append((command, kwargs))
                return subprocess.CompletedProcess(command, 0, "verified", "")
            verified = verify_sigstore_statement(
                statement_path=statement_path, bundle_path=bundle_path, request=request,
                expected_identity=reviewer["identity"], expected_issuer=reviewer["issuer"],
                runner=runner, now=now)
            self.assertEqual(verified["statement_digest"], statement["statement_digest"])
            self.assertEqual(calls[0][0][:2], ["cosign", "verify-blob"])
            def failed_runner(command, **kwargs):
                return subprocess.CompletedProcess(command, 1, "", "no")
            with self.assertRaisesRegex(ValueError, "SIGSTORE_VERIFICATION_FAILED"):
                verify_sigstore_statement(
                    statement_path=statement_path, bundle_path=bundle_path, request=request,
                    expected_identity=reviewer["identity"], expected_issuer=reviewer["issuer"],
                    runner=failed_runner, now=now)


class ResilienceLabTests(unittest.TestCase):
    def test_every_fault_is_distinct_measured_and_safe_or_explicit(self):
        report = run_resilience_lab()
        self.assertEqual(report["summary"], {"executed": 10, "safe_or_explicit": 10,
                                              "duplicate_effects": 0})
        cases = report["cases"]
        self.assertEqual(len({item["input_digest"] for item in cases}), 10)
        self.assertIn("NOT_BYZANTINE_CONSENSUS", report["declared_boundary"])

    def test_duplicate_fault_fixtures_are_rejected(self):
        same = FaultResult("x", "f", "INCONCLUSIVE_HOLD", "safe", 0, "same", "r")
        with patch("continuum.resilience.CASES", (lambda: same, lambda: same)):
            with self.assertRaisesRegex(RuntimeError, "FAULT_FIXTURES_NOT_DISTINCT"):
                run_resilience_lab()


if __name__ == "__main__":
    unittest.main()

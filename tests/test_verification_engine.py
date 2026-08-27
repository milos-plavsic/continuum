from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from continuum.contract import artifact_digest
from continuum.models import digest
from continuum.standard import build_contract_bundle
from continuum.verification import IndependentVerificationEngine
from continuum.verification import FirestoreVerificationReader
from tests.test_cloud_adapters_complete import Firestore


class Reader:
    def __init__(self, authority=None, compliance=None, provider=None):
        self.authority = authority
        self.compliance = compliance
        self.provider = provider
        self.reads: list[str] = []

    def read_authority(self, run_id): self.reads.append(f"authority:{run_id}"); return self.authority
    def read_compliance(self, run_id): self.reads.append(f"compliance:{run_id}"); return self.compliance
    def read_provider(self, run_id): self.reads.append(f"provider:{run_id}"); return self.provider


def pre_bundle():
    with TemporaryDirectory() as directory:
        full = build_contract_bundle(Path(directory))
    bundle = deepcopy(full)
    bundle["profile"] = "reference-google-cloud"
    bundle["artifacts"] = [
        item for item in bundle["artifacts"]
        if item["artifact_type"] != "continuity_attestation"
    ]
    receipt = next(item for item in bundle["artifacts"] if item["artifact_type"] == "execution_receipt")
    receipt["extensions"] = {"continuum.dev/compliance": {
        "evidence_id": "compliance-1", "obligation_id": "obl-1",
        "document_hash": "sha256:compliance-document",
    }}
    receipt["digest"] = {"alg": "sha-256", "value": artifact_digest(receipt)}
    manifest = next(item for item in bundle["artifacts"] if item["artifact_type"] == "succession_manifest")
    selection = {"requirements_digest": "requirements", "candidates_digest": "candidates",
                 "assessments": [{"candidate_id": manifest["body"]["successor"]["principal_id"],
                                   "eligible": True}]}
    selection["receipt_digest"] = digest({"requirements": selection["requirements_digest"],
                                           "candidates": selection["candidates_digest"],
                                           "assessments": selection["assessments"]})
    reconstruction = {"succession_id": "s", "successor_principal": manifest["body"]["successor"]["principal_id"],
                      "purpose": "p", "allowed_scopes": ["vendor.approved"],
                      "decisions": [{"item_id": "obligation", "included": True},
                                    {"item_id": "raw", "included": False}]}
    reconstruction["receipt_digest"] = digest({key: reconstruction[key] for key in (
        "succession_id", "successor_principal", "purpose", "allowed_scopes", "decisions")})
    manifest["extensions"] = {"continuum.dev/successor-selection": selection,
                              "continuum.dev/context-reconstruction": reconstruction}
    manifest["digest"] = {"alg": "sha-256", "value": artifact_digest(manifest)}
    return bundle


def observations(bundle):
    manifest = next(item for item in bundle["artifacts"] if item["artifact_type"] == "succession_manifest")
    receipt = next(item for item in bundle["artifacts"] if item["artifact_type"] == "execution_receipt")
    return {
        "authority": {
            "active_principal": manifest["body"]["successor"]["principal_id"],
            "epoch": manifest["body"]["successor"]["epoch"],
            "revoked_through_epoch": manifest["body"]["predecessor"]["epoch"],
        },
        "compliance": {"status": "VERIFIED", "evidence_id": "compliance-1",
                       "obligation_id": "obl-1", "document_hash": "sha256:compliance-document"},
        "provider": {"effect_count": 1, "provider_ref": receipt["body"]["provider"]["resource_ref"],
                     "request_digest": receipt["body"]["request_digest"],
                     "compliance_evidence_id": "compliance-1"},
    }


class IndependentVerificationEngineTests(unittest.TestCase):
    def test_verifier_alone_issues_sixth_artifact_after_three_direct_reads(self):
        bundle = pre_bundle(); state = observations(bundle)
        reader = Reader(**state)
        engine = IndependentVerificationEngine(reader, clock=lambda: "2026-08-17T10:06:00Z")
        result = engine.verify(run_id="run-1", bundle=bundle,
                               verifier_principal="urn:continuum:principal:independent-verifier")
        self.assertEqual(result["outcome"], "VERIFIED")
        self.assertEqual(reader.reads, ["authority:run-1", "compliance:run-1", "provider:run-1"])
        self.assertEqual(len(bundle["artifacts"]), 5)
        self.assertEqual(len(result["bundle"]["artifacts"]), 6)
        self.assertEqual(result["bundle"]["artifacts"][-1]["issuer"],
                         "urn:continuum:principal:independent-verifier")

    def test_missing_provider_state_is_inconclusive_and_issues_no_attestation(self):
        bundle = pre_bundle(); state = observations(bundle); state["provider"] = None
        result = IndependentVerificationEngine(Reader(**state)).verify(
            run_id="run-1", bundle=bundle,
            verifier_principal="urn:continuum:principal:independent-verifier")
        self.assertEqual(result["outcome"], "INCONCLUSIVE")
        self.assertNotIn("bundle", result)

    def test_supplier_assurance_decision_pack_is_independently_bound(self):
        bundle = pre_bundle(); state = observations(bundle)
        receipt = next(item for item in bundle["artifacts"]
                       if item["artifact_type"] == "execution_receipt")
        claim = receipt["extensions"]["continuum.dev/compliance"]
        claim.update({"workflow": "SUPPLIER_ASSURANCE_AGENT",
                      "decision_scope": "SANDBOX_ONLY", "recommendation": "ONBOARD",
                      "decision_pack_digest": "sha256:decision-pack"})
        receipt["digest"] = {"alg": "sha-256", "value": artifact_digest(receipt)}
        state["compliance"].update({key: claim[key] for key in (
            "workflow", "decision_scope", "recommendation", "decision_pack_digest")})
        result = IndependentVerificationEngine(Reader(**state)).verify(
            run_id="run-1", bundle=bundle, verifier_principal="urn:verifier")
        criteria = result["bundle"]["artifacts"][-1]["body"]["verification"]["criteria_results"]
        self.assertIn({"criterion_id": "supplier-assurance-admitted", "passed": True}, criteria)
        state["compliance"]["decision_pack_digest"] = "substituted"
        failure = IndependentVerificationEngine(Reader(**state)).verify(
            run_id="run-1", bundle=bundle, verifier_principal="urn:verifier")
        self.assertIn("SUPPLIER_ASSURANCE_STATE_MISMATCH", failure["reason_codes"])

    def test_mutated_claim_or_provider_contradiction_fails_closed(self):
        bundle = pre_bundle(); state = observations(bundle)
        changed = deepcopy(bundle)
        changed["artifacts"][0]["body"]["status"] = "OPEN"
        invalid = IndependentVerificationEngine(Reader(**state)).verify(
            run_id="run-1", bundle=changed,
            verifier_principal="urn:continuum:principal:independent-verifier")
        self.assertEqual(invalid["outcome"], "FAILED")
        self.assertIn("DIGEST_MISMATCH", invalid["reason_codes"])
        state["provider"]["effect_count"] = 2
        contradicted = IndependentVerificationEngine(Reader(**state)).verify(
            run_id="run-1", bundle=bundle,
            verifier_principal="urn:continuum:principal:independent-verifier")
        self.assertEqual(contradicted["reason_codes"], ["PROVIDER_STATE_MISMATCH"])

    def test_all_structural_and_semantic_contradictions_are_explicit(self):
        bundle = pre_bundle(); state = observations(bundle)
        engine = IndependentVerificationEngine(Reader(**state))
        self.assertEqual(engine.verify(run_id="r", bundle={"protocol": "other", "artifacts": []},
            verifier_principal="urn:v")["reason_codes"], ["UNSUPPORTED_PROTOCOL"])
        self.assertEqual(engine.verify(run_id="r", bundle={"protocol": "continuum/0.1-draft", "artifacts": []},
            verifier_principal="urn:v")["reason_codes"], ["PRE_ATTESTATION_ARTIFACT_SET_INVALID"])
        duplicate = deepcopy(bundle)
        duplicate["artifacts"][1]["artifact_id"] = duplicate["artifacts"][0]["artifact_id"]
        duplicate["artifacts"][1]["digest"] = {"alg": "sha-256", "value": artifact_digest(duplicate["artifacts"][1])}
        self.assertIn("DUPLICATE_ARTIFACT_ID", engine.verify(run_id="r", bundle=duplicate,
            verifier_principal="urn:v")["reason_codes"])
        broken = deepcopy(bundle)
        manifest = next(a for a in broken["artifacts"] if a["artifact_type"] == "succession_manifest")
        manifest["body"]["obligations"][0]["digest"]["value"] = "0" * 64
        manifest["digest"] = {"alg": "sha-256", "value": artifact_digest(manifest)}
        self.assertIn("BROKEN_ARTIFACT_REFERENCE", engine.verify(run_id="r", bundle=broken,
            verifier_principal="urn:v")["reason_codes"])
        self.assertEqual(engine._reason(Exception("!"), "FALLBACK"), "FALLBACK")

        valid_manifest = next(a for a in bundle["artifacts"] if a["artifact_type"] == "succession_manifest")
        mutations = []
        missing = deepcopy(valid_manifest); missing["extensions"] = {}; mutations.append((missing, "HANDOFF_EVIDENCE_MISSING"))
        bad_selection = deepcopy(valid_manifest); bad_selection["extensions"]["continuum.dev/successor-selection"]["receipt_digest"] = "bad"; mutations.append((bad_selection, "SUCCESSOR_ASSESSMENT_DIGEST_MISMATCH"))
        bad_context = deepcopy(valid_manifest); bad_context["extensions"]["continuum.dev/context-reconstruction"]["receipt_digest"] = "bad"; mutations.append((bad_context, "CONTEXT_RECONSTRUCTION_DIGEST_MISMATCH"))
        wrong_successor = deepcopy(valid_manifest)
        context = wrong_successor["extensions"]["continuum.dev/context-reconstruction"]
        context["successor_principal"] = "urn:other"
        context["receipt_digest"] = digest({key: context[key] for key in (
            "succession_id", "successor_principal", "purpose", "allowed_scopes", "decisions")})
        mutations.append((wrong_successor, "CONTEXT_SUCCESSOR_MISMATCH"))
        for decisions in ("bad", [{"included": True}], [{"included": False}]):
            incomplete = deepcopy(valid_manifest)
            context = incomplete["extensions"]["continuum.dev/context-reconstruction"]
            context["decisions"] = decisions
            context["receipt_digest"] = digest({key: context[key] for key in (
                "succession_id", "successor_principal", "purpose", "allowed_scopes", "decisions")})
            mutations.append((incomplete, "CONTEXT_DECISIONS_INCOMPLETE"))
        for changed, code in mutations:
            with self.subTest(code=code), self.assertRaisesRegex(Exception, code):
                engine._validate_handoff_extensions(changed)

        indexed = engine._validate_pre_attestation_bundle(bundle)
        variants = [
            ({**state["authority"], "epoch": -1}, state["compliance"], state["provider"], "AUTHORITY_STATE_MISMATCH"),
            (state["authority"], state["compliance"], state["provider"], "GRANT_SUCCESSOR_BINDING_MISMATCH"),
            (state["authority"], state["compliance"], state["provider"], "REVOCATION_STATE_MISMATCH"),
            (state["authority"], {**state["compliance"], "status": "FAILED"}, state["provider"], "COMPLIANCE_STATE_MISMATCH"),
            (state["authority"], state["compliance"], state["provider"], "EXECUTION_SUCCESSOR_BINDING_MISMATCH"),
        ]
        for index, (authority, compliance, provider, code) in enumerate(variants):
            changed = deepcopy(indexed)
            if index == 1: changed["authority_grant"]["body"]["status"] = "REVOKED"
            if index == 2: changed["revocation_proof"]["body"]["status"] = "PENDING"
            if index == 4: changed["execution_receipt"]["body"]["disposition"] = "FAILED"
            self.assertIn(code, engine._compare(changed, authority, compliance, provider))

    def test_firestore_reader_distinguishes_absence_duplicates_and_one_effect(self):
        db = Firestore(); reader = FirestoreVerificationReader(db)
        self.assertIsNone(reader.read_authority("r"))
        self.assertIsNone(reader.read_compliance("r"))
        self.assertIsNone(reader.read_provider("r"))
        db.data["continuity_authority/a"] = {"run_id": "r", "epoch": 1}
        self.assertEqual(reader.read_authority("r")["epoch"], 1)
        db.data["continuity_authority/b"] = {"run_id": "r", "epoch": 2}
        self.assertEqual(reader.read_authority("r"), {"observation_count": 2})
        db.data["continuity_compliance/r"] = {"status": "VERIFIED"}
        self.assertEqual(reader.read_compliance("r")["status"], "VERIFIED")
        db.data["continuity_sandbox_vendors/a"] = {"run_id": "r", "provider_ref": "p"}
        self.assertEqual(reader.read_provider("r")["effect_count"], 1)
        db.data["continuity_sandbox_vendors/b"] = {"run_id": "r", "provider_ref": "q"}
        self.assertEqual(reader.read_provider("r")["effect_count"], 2)


if __name__ == "__main__":
    unittest.main()

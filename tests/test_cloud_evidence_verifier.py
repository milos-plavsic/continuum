from __future__ import annotations

import base64
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from continuum.contract import artifact_digest, canonical_bytes
from continuum.standard import build_contract_bundle
from tests.selection_fixtures import selection_extensions


SCRIPT = Path(__file__).parents[1] / "scripts" / "cloud" / "verify-evidence.py"
SPEC = importlib.util.spec_from_file_location("cloud_evidence_verifier", SCRIPT)
assert SPEC and SPEC.loader
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class CloudEvidenceVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.scope = {"project_id": "continuum-proof", "region": "us-central1",
                      "run_id": "run-001", "trace_id": "a" * 32,
                      "git_commit": "1" * 40, "protocol": "continuum/0.1-draft"}
        image = "sha256:" + "2" * 64
        build = {"git_commit": self.scope["git_commit"], "protocol": self.scope["protocol"]}
        image_reference = "registry.example/continuum@" + image
        run = lambda role, account: {"project_id": self.scope["project_id"],
                                     "region": self.scope["region"], "role": role,
                                     "service": f"continuum-{role}",
                                     "revision": f"continuum-{role}-00001-abc",
                                     "ready": True, "service_account": account,
                                     "image_digest": image,
                                     "image_reference": image_reference,
                                     "build_info": build}
        contract_bundle = build_contract_bundle(self.directory / "contract-fixture")
        contract_bundle["profile"] = "reference-google-cloud"
        receipt = next(item for item in contract_bundle["artifacts"]
                       if item["artifact_type"] == "execution_receipt")
        receipt["extensions"] = {"continuum.dev/compliance": {
            "workflow": "SUPPLIER_ASSURANCE_AGENT", "decision_scope": "SANDBOX_ONLY",
            "recommendation": "ONBOARD", "decision_pack_digest": "3" * 64,
        }}
        receipt["digest"] = {"alg": "sha-256", "value": artifact_digest(receipt)}
        attestation = next(item for item in contract_bundle["artifacts"]
                           if item["artifact_type"] == "continuity_attestation")
        manifest = next(item for item in contract_bundle["artifacts"]
                        if item["artifact_type"] == "succession_manifest")
        selection, governance = selection_extensions(
            manifest["body"]["successor"]["principal_id"])
        manifest["extensions"] = {
            "continuum.dev/successor-selection": selection,
            "continuum.dev/selection-governance": governance,
        }
        manifest["digest"] = {"alg": "sha-256", "value": artifact_digest(manifest)}
        attestation["body"]["succession_manifest"]["digest"] = manifest["digest"]
        attestation["body"]["execution_receipts"][0]["digest"] = receipt["digest"]
        attestation["digest"] = {"alg": "sha-256", "value": artifact_digest(attestation)}
        self.objects = {
            "build-provenance": {"image_summary": {
                "digest": image, "fully_qualified_digest": image_reference,
                "slsa_build_level": 3,
            }, "provenance_summary": {"provenance": [{
                "build": {"inTotoSlsaProvenanceV1": {"buildType": "cloud-build"}},
                "envelope": {
                    "payload": base64.urlsafe_b64encode(json.dumps({
                        "subject": [{"digest": {"sha256": "2" * 64}}],
                    }).encode()).decode().rstrip("="),
                    "signatures": [{"keyid": "google-cloud-build", "sig": "signed"}],
                },
            }]}},
            "cloud-run-control": run("control", "control@example.iam.gserviceaccount.com"),
            "cloud-run-v17": run("agent-v17", "v17@example.iam.gserviceaccount.com"),
            "cloud-run-v18": run("agent-v18", "v18@example.iam.gserviceaccount.com"),
            "cloud-run-v19": run("agent-v19", "v19@example.iam.gserviceaccount.com"),
            "cloud-run-verifier": run("verifier", "verifier@example.iam.gserviceaccount.com"),
            "firestore-event": {"run_id": "run-001", "event_id": "evt-001"},
            "firestore-projection": {"run_id": "run-001", "last_event_id": "evt-001"},
            "firestore-outbox": {"run_id": "run-001", "event_id": "evt-001", "status": "PUBLISHED"},
            "pubsub-publish": {"run_id": "run-001", "event_id": "evt-001", "message_id": "msg-001"},
            "pubsub-deliveries": {"run_id": "run-001", "deliveries": [
                {"message_id": "msg-001", "delivery_id": "delivery-1"},
                {"message_id": "msg-001", "delivery_id": "delivery-2"}]},
            "vertex-call": {"run_id": "run-001", "provider": "vertex-ai",
                            "model": "gemini-3.6-flash",
                            "service_account": "v18@example.iam.gserviceaccount.com",
                            "incident_assessment_digest": "1" * 64,
                            "evidence_event_ids": ["evt-001"],
                            "proposed_actions": ["initiate_governed_succession"],
                            "selected_candidate_id": "v18",
                            "evidence_manifest_refs": [
                                "cloud-run:https://continuum-agent-v18-fixture",
                                "identity:v18@example.iam.gserviceaccount.com"],
                            "supporting_citations": [{
                                "claim": "RUNTIME_IDENTITY",
                                "evidence_refs": ["identity:v18@example.iam.gserviceaccount.com"],
                            }]},
            "model-armor": {"run_id": "run-001", "provider": "google-model-armor",
                            "template": "projects/p/locations/us/templates/continuum",
                            "execution_state": "EXECUTION_SUCCESS", "match_state": "MATCH_FOUND",
                            "allowed_to_model": False, "receipt_digest": "6" * 64},
            "external-work-item": {"run_id": "run-001", "effect_count": 1,
                                   "provider": "github-issues", "state": "OPEN",
                                   "provider_ref": "https://github.com/o/r/issues/41",
                                   "request_digest": "7" * 64},
            "supplier-assurance": {
                "run_id": "run-001", "workflow": "SUPPLIER_ASSURANCE_AGENT",
                "model": "gemini-3.6-flash",
                "service_account": "v18@example.iam.gserviceaccount.com",
                "decision_scope": "SANDBOX_ONLY", "recommendation": "ONBOARD",
                "decision_pack_digest": "3" * 64,
                "tools": [
                    {"tool": "gleif.lei-records.read",
                     "source_url": "https://api.gleif.org/api/v1/lei-records/W38RGI023J3WT1HWRP32",
                     "evidence_ref": "sha256:" + "4" * 64,
                     "availability_mode": "LIVE", "observed_at": "2026-08-27T12:00:00Z",
                     "freshness_expires_at": "2026-08-28T12:00:00Z",
                     "cached_from_evidence_ref": None},
                    {"tool": "ec.vies.check-vat-number",
                     "source_url": "https://ec.europa.eu/taxation_customs/vies/rest-api/check-vat-number",
                     "evidence_ref": "sha256:" + "5" * 64,
                     "availability_mode": "LIVE", "observed_at": "2026-08-27T12:00:00Z",
                     "freshness_expires_at": "2026-08-28T12:00:00Z",
                     "cached_from_evidence_ref": None},
                ],
            },
            "trace-export": {"run_id": "run-001", "trace_id": "a" * 32,
                             "spans": [{"name": name} for name in
                                       ("continuum.missing_event_published",
                                        "continuum.investigated", "continuum.authorized",
                                        "continuum.predecessor_fenced",
                                        "continuum.successor_active",
                                        "continuum.contract_exported")]},
            "contract-export": {"run_id": "run-001", "protocol": "continuum/0.1-draft",
                                "status": "PASS", "bundle": contract_bundle,
                                "report_digest": {"alg": "sha-256",
                                                  "value": sha256(canonical_bytes(contract_bundle)).hexdigest()}},
        }

    def tearDown(self):
        self.temp.cleanup()

    def write_bundle(self, objects=None):
        objects = self.objects if objects is None else objects
        object_dir = self.directory / "objects"
        object_dir.mkdir(parents=True, exist_ok=True)
        manifest = []
        for object_id, value in objects.items():
            data = canonical_bytes(value)
            digest = sha256(data).hexdigest()
            (object_dir / digest).write_bytes(data)
            manifest.append({"object_id": object_id, "kind": object_id,
                             "source_authority": "observed", "media_type": "application/json",
                             "sha256": digest, "size": len(data),
                             "collected_at": "2026-08-17T12:00:00Z"})
        bundle = {"schema": "continuum/cloud-evidence/0.1",
                  "bundle_id": "urn:continuum:cloud-evidence:run-001",
                  "captured_at": "2026-08-17T12:00:00Z",
                  "profile": "reference-google-cloud",
                  "canonicalization_profile": "urn:ietf:rfc:8785",
                  "scope": self.scope,
                  "collector": {"name": "fixture", "version": "1",
                                "started_at": "2026-08-17T12:00:00Z",
                                "finished_at": "2026-08-17T12:00:01Z"},
                  "objects": manifest, "collection_errors": [],
                  "declared_non_claims": sorted(verifier.BASE_NON_CLAIMS)}
        digest = sha256(b"continuum-cloud-evidence\x000.1\x00" + canonical_bytes(bundle)).hexdigest()
        bundle["bundle_digest"] = {"alg": "sha-256", "value": digest}
        (self.directory / "bundle.json").write_text(json.dumps(bundle))

    def test_complete_golden_bundle_passes(self):
        self.write_bundle()
        result = verifier.verify(self.directory)
        self.assertEqual("PASS", result["overall"])
        self.assertEqual([], result["reason_codes"])
        self.assertFalse(result["verifier"]["network_used"])
        self.assertFalse(result["verifier"]["credentials_used"])

    def test_absent_evidence_is_not_assessed(self):
        result = verifier.verify(self.directory)
        self.assertEqual("NOT_ASSESSED", result["overall"])
        self.assertIn("BUNDLE_MISSING", result["reason_codes"])

    def test_missing_mandatory_object_is_not_assessed(self):
        objects = deepcopy(self.objects)
        del objects["vertex-call"]
        self.write_bundle(objects)
        result = verifier.verify(self.directory)
        self.assertEqual("NOT_ASSESSED", result["overall"])
        self.assertEqual(["vertex-call"], result["missing_mandatory_objects"])

    def test_semantic_contradiction_fails(self):
        objects = deepcopy(self.objects)
        objects["vertex-call"]["model"] = "gemini-2.5-flash"
        self.write_bundle(objects)
        result = verifier.verify(self.directory)
        self.assertEqual("FAIL", result["overall"])
        self.assertIn("VERTEX_MODEL_TOO_OLD", result["reason_codes"])

    def test_supplier_assurance_must_be_official_identity_bound_and_receipt_bound(self):
        cases = (
            ("service_account", "attacker@example.iam.gserviceaccount.com",
             "SUPPLIER_SUCCESSOR_IDENTITY_MISMATCH"),
            ("decision_scope", "PRODUCTION", "SUPPLIER_SCOPE_NOT_SANDBOXED"),
            ("decision_pack_digest", "invalid", "SUPPLIER_DECISION_PACK_DIGEST_INVALID"),
        )
        for field, value, reason in cases:
            with self.subTest(field=field):
                objects = deepcopy(self.objects)
                objects["supplier-assurance"][field] = value
                self.write_bundle(objects)
                result = verifier.verify(self.directory)
                self.assertEqual("FAIL", result["overall"])
                self.assertIn(reason, result["reason_codes"])

        objects = deepcopy(self.objects)
        objects["supplier-assurance"]["tools"][0]["source_url"] = "https://example.invalid"
        self.write_bundle(objects)
        result = verifier.verify(self.directory)
        self.assertIn("SUPPLIER_OFFICIAL_TOOL_EVIDENCE_INVALID", result["reason_codes"])

        objects = deepcopy(self.objects)
        objects["supplier-assurance"]["tools"][0]["availability_mode"] = "UNKNOWN"
        self.write_bundle(objects)
        result = verifier.verify(self.directory)
        self.assertIn("SUPPLIER_TOOL_AVAILABILITY_INVALID", result["reason_codes"])

        objects = deepcopy(self.objects)
        contract = objects["contract-export"]["bundle"]
        manifest = next(item for item in contract["artifacts"]
                        if item["artifact_type"] == "succession_manifest")
        manifest["extensions"]["continuum.dev/selection-governance"]["receipt_digest"] = "bad"
        manifest["digest"] = {"alg": "sha-256", "value": artifact_digest(manifest)}
        attestation = next(item for item in contract["artifacts"]
                           if item["artifact_type"] == "continuity_attestation")
        attestation["body"]["succession_manifest"]["digest"] = manifest["digest"]
        attestation["digest"] = {"alg": "sha-256", "value": artifact_digest(attestation)}
        objects["contract-export"]["report_digest"] = {"alg": "sha-256",
            "value": sha256(canonical_bytes(contract)).hexdigest()}
        self.write_bundle(objects)
        result = verifier.verify(self.directory)
        self.assertIn("SELECTION_GOVERNANCE_RECEIPT_DIGEST_MISMATCH",
                      result["reason_codes"])

    def test_selected_successor_must_bind_cloud_identity_and_contract(self):
        objects = deepcopy(self.objects)
        objects["vertex-call"]["evidence_manifest_refs"] = ["cloud-run:https://continuum-agent-v18"]
        self.write_bundle(objects)
        result = verifier.verify(self.directory)
        self.assertEqual("FAIL", result["overall"])
        self.assertIn("VERTEX_CANDIDATE_IDENTITY_UNPROVEN", result["reason_codes"])

        objects = deepcopy(self.objects)
        objects["vertex-call"]["selected_candidate_id"] = "v19"
        objects["vertex-call"]["evidence_manifest_refs"] = [
            "cloud-run:https://continuum-agent-v19-fixture",
            "identity:v19@example.iam.gserviceaccount.com"]
        self.write_bundle(objects)
        result = verifier.verify(self.directory)
        self.assertIn("CONTRACT_SELECTED_SUCCESSOR_MISMATCH", result["reason_codes"])
        self.assertIn("CONTRACT_EXECUTING_SUCCESSOR_MISMATCH", result["reason_codes"])

    def test_vertex_incident_assessment_must_be_digest_bound(self):
        objects = deepcopy(self.objects)
        objects["vertex-call"]["incident_assessment_digest"] = "unbound"
        self.write_bundle(objects)
        result = verifier.verify(self.directory)
        self.assertIn("VERTEX_INCIDENT_ASSESSMENT_UNBOUND", result["reason_codes"])

    def test_selective_citations_are_claim_bound_and_cannot_be_fabricated(self):
        for citations, reason in (
            ([{"claim": "BUILD_PROVENANCE", "evidence_refs": [
                "identity:v18@example.iam.gserviceaccount.com"]}],
             "VERTEX_SUPPORTING_CITATION_INVALID"),
            ([{"claim": "RUNTIME_IDENTITY", "evidence_refs": ["fabricated"]}],
             "VERTEX_SUPPORTING_CITATION_INVALID"),
            ([{"claim": "RUNTIME_IDENTITY", "evidence_refs": [
                "identity:v18@example.iam.gserviceaccount.com"]}] * 2,
             "VERTEX_SUPPORTING_CITATION_DUPLICATE"),
        ):
            objects = deepcopy(self.objects)
            objects["vertex-call"]["supporting_citations"] = citations
            self.write_bundle(objects)
            result = verifier.verify(self.directory)
            with self.subTest(reason=reason):
                self.assertIn(reason, result["reason_codes"])

    def test_slsa_provenance_must_bind_the_deployed_image(self):
        objects = deepcopy(self.objects)
        payload = json.dumps({"subject": [{"digest": {"sha256": "9" * 64}}]}).encode()
        objects["build-provenance"]["provenance_summary"]["provenance"][0][
            "envelope"]["payload"] = base64.urlsafe_b64encode(payload).decode().rstrip("=")
        self.write_bundle(objects)
        result = verifier.verify(self.directory)
        self.assertIn("BUILD_PROVENANCE_IMAGE_MISMATCH", result["reason_codes"])

    def test_content_mutation_fails_integrity(self):
        self.write_bundle()
        bundle = json.loads((self.directory / "bundle.json").read_text())
        entry = next(item for item in bundle["objects"] if item["object_id"] == "firestore-event")
        (self.directory / "objects" / entry["sha256"]).write_text("{}")
        result = verifier.verify(self.directory)
        self.assertEqual("FAIL", result["overall"])
        self.assertIn("OBJECT_INTEGRITY_FAILED:firestore-event", result["reason_codes"])


if __name__ == "__main__":
    unittest.main()

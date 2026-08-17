from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from continuum.contract import canonical_bytes
from continuum.standard import build_contract_bundle


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
        run = lambda role, account: {"project_id": self.scope["project_id"],
                                     "region": self.scope["region"], "role": role,
                                     "ready": True, "service_account": account,
                                     "image_digest": image, "build_info": build}
        contract_bundle = build_contract_bundle(self.directory / "contract-fixture")
        contract_bundle["profile"] = "reference-google-cloud"
        self.objects = {
            "cloud-run-control": run("control", "control@example.iam.gserviceaccount.com"),
            "cloud-run-v17": run("agent-v17", "v17@example.iam.gserviceaccount.com"),
            "cloud-run-v18": run("agent-v18", "v18@example.iam.gserviceaccount.com"),
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
                            "evidence_event_ids": ["evt-001"]},
            "trace-export": {"run_id": "run-001", "trace_id": "a" * 32,
                             "spans": [{"name": name} for name in
                                       ("investigation", "policy", "succession", "verification")]},
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
                  "profile": "reference-google-cloud", "scope": self.scope,
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

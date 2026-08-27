from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / "scripts" / "cloud" / "collect_evidence.py"
SPEC = importlib.util.spec_from_file_location("cloud_evidence_collector", SCRIPT)
assert SPEC and SPEC.loader
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


def load_script(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPT.parent / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


packager = load_script("cloud_evidence_packager_for_collector", "package-evidence.py")
verifier = load_script("cloud_evidence_verifier_for_collector", "verify-evidence.py")


class FakeRunner:
    def __init__(self, scope, *, omit=()):
        self.scope = scope
        self.omit = set(omit)
        self.commands = []

    def json(self, argv):
        argv = list(argv)
        self.commands.append(argv)
        if argv[1:4] == ["run", "services", "describe"]:
            service = argv[4]
            role = {"control": "control", "v17": "agent-v17", "v18": "agent-v18",
                    "v19": "agent-v19", "verifier": "verifier"}[service]
            return {"metadata": {"name": service},
                    "spec": {"template": {"spec": {
                        "serviceAccountName": f"{role}@example.iam.gserviceaccount.com",
                        "containers": [{"env": [
                            {"name": "GIT_SHA", "value": "1" * 40},
                            {"name": "CONTINUUM_PROTOCOL", "value": "continuum/0.1-draft"},
                        ]}]} }},
                    "status": {"latestReadyRevisionName": f"{service}-00001",
                               "conditions": [{"type": "Ready", "status": "True"}]}}
        if argv[1:4] == ["run", "revisions", "describe"]:
            return {"metadata": {"name": argv[4]},
                    "status": {"imageDigest": "registry.example/image@sha256:" + "2" * 64}}
        if argv[1:3] == ["logging", "read"]:
            object_id = next(value for value in collector.RUN_OBJECTS
                             if f'object_id="{value}"' in argv[3])
            if object_id in self.omit:
                return []
            payload = {"run_id": self.scope.run_id, "object_id": object_id}
            return [{"jsonPayload": {"continuum_evidence": {
                "run_id": self.scope.run_id, "object_id": object_id, "payload": payload}}}]
        raise AssertionError(argv)


class FakeTraceReader:
    def __init__(self, scope): self.scope = scope
    def read(self, scope):
        return {"run_id": scope.run_id, "trace_id": scope.trace_id,
                "spans": [{"name": "continuum.investigated"}], "source": "cloud-trace-api"}


class EvidenceCollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.destination = Path(self.temp.name)
        self.scope = collector.CaptureScope("proof-project", "us-central1", "run-1", "a" * 32)
        self.services = {
            "cloud-run-control": ("control", "control"),
            "cloud-run-v17": ("agent-v17", "v17"),
            "cloud-run-v18": ("agent-v18", "v18"),
            "cloud-run-v19": ("agent-v19", "v19"),
            "cloud-run-verifier": ("verifier", "verifier"),
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_collects_all_exact_objects_with_read_only_commands(self):
        runner = FakeRunner(self.scope)
        report = collector.collect(self.scope, self.destination, runner, services=self.services,
                                   trace_reader=FakeTraceReader(self.scope))
        self.assertEqual(14, len(report["captured"]))
        self.assertEqual({}, report["unavailable"])
        self.assertEqual(14, len([path for path in self.destination.glob("*.json")
                                  if not path.name.startswith(".")]))
        for command in runner.commands:
            self.assertIn(command[1], {"run", "logging"})
            self.assertNotIn("auth", command)
            self.assertNotIn("print-access-token", command)
        logging_commands = [c for c in runner.commands if c[1] == "logging"]
        self.assertTrue(all(f'run_id="{self.scope.run_id}"' in c[3] for c in logging_commands))

    def test_partial_capture_omits_missing_object(self):
        runner = FakeRunner(self.scope, omit={"vertex-call"})
        report = collector.collect(self.scope, self.destination, runner, services=self.services,
                                   trace_reader=FakeTraceReader(self.scope))
        self.assertEqual("not_observed", report["unavailable"]["vertex-call"])
        self.assertFalse((self.destination / "vertex-call.json").exists())
        self.assertTrue((self.destination / ".capture-report.json").exists())

        bundle_dir = self.destination / "bundle"
        bundle = packager.package(self.destination, bundle_dir, project=self.scope.project,
                                  region=self.scope.region, run_id=self.scope.run_id,
                                  trace_id=self.scope.trace_id, git_commit="1" * 40)
        self.assertEqual("continuum/0.1-draft", bundle["scope"]["protocol"])
        result = verifier.verify(bundle_dir)
        self.assertEqual("NOT_ASSESSED", result["overall"])
        self.assertEqual(["vertex-call"], result["missing_mandatory_objects"])

    def test_rejects_conflicting_duplicate_observations(self):
        entries = [
            {"jsonPayload": {"continuum_evidence": {"run_id": "run-1", "object_id": "vertex-call",
                                                       "payload": {"run_id": "run-1", "model": "a"}}}},
            {"jsonPayload": {"continuum_evidence": {"run_id": "run-1", "object_id": "vertex-call",
                                                       "payload": {"run_id": "run-1", "model": "b"}}}},
        ]
        with self.assertRaises(ValueError):
            collector._logged_payload(entries, self.scope, "vertex-call")


if __name__ == "__main__":
    unittest.main()

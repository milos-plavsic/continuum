from copy import deepcopy
from pathlib import Path
import sys
import unittest

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from continuum.cloud_scenario_service import DurableCloudScenarioService
from continuum.cloud_app import create_cloud_app


class Store:
    def __init__(self): self.runs, self.events = {}, {}
    def create(self, run):
        prior = self.runs.get(run["run_id"])
        if prior is not None: return deepcopy(prior), True
        self.runs[run["run_id"]] = deepcopy(run); self.events[run["run_id"]] = []
        return deepcopy(run), False
    def load(self, run_id):
        return deepcopy(self.runs.get(run_id))
    def advance(self, run_id, expected_phase, next_phase, patch, observation):
        run = self.runs[run_id]
        if run["phase"] != expected_phase: raise RuntimeError("CAS_CONFLICT")
        run.update(deepcopy(patch)); run["phase"] = next_phase
        self.events[run_id].append(deepcopy(observation))
        return deepcopy(run)
    def observations(self, run_id): return deepcopy(self.events[run_id])


class Investigator:
    calls = 0
    def investigate(self, request):
        self.calls += 1
        return {"evidence_ids": [item["event_id"] if "event_id" in item else item["type"]
                                 for item in request["evidence"]],
                "hypothesis": "compromised"}


class Evidence:
    def observe(self, request):
        return [
            {"type": "document.injection_detected", "source": "document-ingress"},
            {"type": "action.denied", "source": "action-gateway"},
            {"type": "expectation.missed", "source": "negative-space-sentinel"},
        ]


class Authority:
    def decide(self, evidence): return {"outcome": "APPROVE_SUCCESSION", "decision_id": "decision-1"}
    def fence_predecessor(self, request): return {"status": "FENCED", "revoked_through_epoch": 41}
    def activate_successor(self, request): return {"status": "ACTIVE", "epoch": 42}
    def attempt_action(self, request): return {"allowed": False, "reason": "STALE_EPOCH"}
    def attempt_memory(self, request): return {"allowed": False, "reason": "MEMORY_REVOKED",
                                               "candidates_examined": 0}


class Effects:
    def __init__(self): self.execute_calls = 0; self.reconcile_calls = 0
    def execute(self, request): self.execute_calls += 1; return {"state": "DISPATCHED"}
    def reconcile(self, request):
        self.reconcile_calls += 1
        return {"effect_count": 1, "provider_ref": "vendor://acme/vendor-042",
                "request_digest": request["request_digest"]}


class Exporter:
    def __init__(self): self.observations = None
    def export(self, run, observations):
        self.observations = observations
        return {"profile": "reference-google-cloud", "artifacts": [{"type": "observed-chain"}]}


class Verifier:
    def __init__(self): self.request = None
    def verify(self, request):
        self.request = request
        return {"status": "PASS", "outcome": "VERIFIED",
                "verifier_principal": "verifier@project.iam.gserviceaccount.com"}


class CloudScenarioServiceTests(unittest.TestCase):
    def setUp(self):
        self.store, self.investigator, self.effects = Store(), Investigator(), Effects()
        self.exporter, self.verifier = Exporter(), Verifier()
        self.service = DurableCloudScenarioService(
            store=self.store, evidence=Evidence(), investigator=self.investigator,
            authority=Authority(),
            effects=self.effects, exporter=self.exporter, verifier=self.verifier)

    def test_run_persists_observed_lifecycle_and_independent_verification(self):
        result = self.service.run("run-001")
        self.assertEqual(result["phase"], "VERIFIED")
        self.assertEqual(result["provider_observation"]["effect_count"], 1)
        self.assertEqual(result["verification"]["status"], "PASS")
        self.assertEqual([event["kind"] for event in self.store.events["run-001"]], [
            "investigation.observed", "policy.decision_observed",
            "predecessor.denials_observed", "successor.activation_observed",
            "provider.effect_observed", "contract.exported",
            "independent.verification_observed"])
        self.assertEqual(self.verifier.request["provider_observation"]["effect_count"], 1)
        self.assertTrue(any(event["kind"] == "predecessor.denials_observed"
                            for event in self.exporter.observations))

    def test_retry_of_completed_run_does_not_repeat_effect(self):
        first = self.service.run("run-retry")
        second = self.service.run("run-retry")
        self.assertEqual(first, second)
        self.assertEqual(self.effects.execute_calls, 1)
        self.assertEqual(self.investigator.calls, 1)

    def test_dispatch_acknowledgement_cannot_author_success(self):
        self.effects.reconcile = lambda request: {"effect_count": 0, "provider_ref": None}
        with self.assertRaisesRegex(ValueError, "PROVIDER_EFFECT_NOT_OBSERVED_ONCE"):
            self.service.run("run-no-effect")
        self.assertEqual(self.store.runs["run-no-effect"]["phase"], "SUCCESSOR_ACTIVE")
        self.assertIsNone(self.verifier.request)

    def test_incomplete_investigation_cannot_trigger_policy_or_mutation(self):
        self.investigator.investigate = lambda request: {"evidence_types": ["expectation.missed"]}
        with self.assertRaisesRegex(ValueError, "INVESTIGATION_EVIDENCE_INCOMPLETE"):
            self.service.run("run-silence-only")
        self.assertEqual(self.store.runs["run-silence-only"]["phase"], "CREATED")
        self.assertEqual(self.effects.execute_calls, 0)

    def test_verifier_result_requires_independent_identity(self):
        self.verifier.verify = lambda request: {"status": "PASS"}
        with self.assertRaisesRegex(ValueError, "VERIFIER_IDENTITY_MISSING"):
            self.service.run("run-self-claim")
        self.assertEqual(self.store.runs["run-self-claim"]["phase"], "CONTRACT_EXPORTED")

    def test_control_api_accepts_only_server_owned_run_command(self):
        client = TestClient(create_cloud_app(role="control", scenario_service=self.service))
        rejected = client.post("/cloud-smoke/start", json={"run_id": "api-run", "success": True})
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(self.store.runs, {})
        started = client.post("/cloud-smoke/start", json={"run_id": "api-run"})
        self.assertEqual(started.status_code, 200)
        status = client.get("/cloud-smoke/api-run")
        self.assertEqual(status.json(), started.json())

    def test_control_api_fails_closed_without_production_ports(self):
        client = TestClient(create_cloud_app(role="control", scenario_service=None))
        response = client.post("/cloud-smoke/start", json={"run_id": "api-run"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["code"], "SCENARIO_SERVICE_NOT_CONFIGURED")


if __name__ == "__main__":
    unittest.main()

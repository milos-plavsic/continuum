from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from continuum.cloud_scenario_service import DurableCloudScenarioService, FirestoreScenarioStore, ScenarioConflict
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

    def test_run_identity_status_and_phase_fail_closed(self):
        for run_id in ("", "x" * 129):
            with self.assertRaisesRegex(ValueError, "RUN_ID_INVALID"): self.service.run(run_id)
        self.store.runs["conflict"] = {**self.service._new_run("conflict"), "command_digest": "other"}
        with self.assertRaisesRegex(ScenarioConflict, "RUN_ID_CONTENT_CONFLICT"): self.service.run("conflict")
        with self.assertRaisesRegex(KeyError, "RUN_NOT_FOUND"): self.service.status("missing")
        with self.assertRaisesRegex(ScenarioConflict, "SCENARIO_PHASE_INVALID"):
            self.service._advance({**self.service._new_run("bad"), "phase": "UNKNOWN"})

    def test_every_observation_gate_rejects_contradiction(self):
        def current(phase):
            return {**self.service._new_run("gate"), "phase": phase,
                    "decision": {"decision_id": "d"},
                    "provider_observation": {"effect_count": 1, "provider_ref": "p", "request_digest": "r"},
                    "contract_bundle": {"profile": "reference-google-cloud", "artifacts": [{}]}}
        for evidence in ("bad", ["bad"]):
            self.service.evidence.observe = lambda request, value=evidence: value
            with self.assertRaisesRegex(ValueError, "LIFECYCLE_EVIDENCE_INVALID"): self.service._advance(current("CREATED"))
        self.service.evidence = Evidence()
        self.store.events["gate"] = []
        for decision in ({"outcome": "HOLD", "decision_id": "d"},
                         {"outcome": "APPROVE_SUCCESSION", "decision_id": None}):
            self.service.authority.decide = lambda evidence, value=decision: value
            with self.assertRaisesRegex(ValueError, "SUCCESSION_NOT_AUTHORIZED"): self.service._advance(current("INVESTIGATED"))
        self.service.authority = Authority()
        for fenced in ({"status": "BAD", "revoked_through_epoch": 41},
                       {"status": "FENCED", "revoked_through_epoch": 40}):
            self.service.authority.fence_predecessor = lambda request, value=fenced: value
            with self.assertRaisesRegex(ValueError, "PREDECESSOR_FENCE_NOT_OBSERVED"): self.service._advance(current("AUTHORIZED"))
        self.service.authority = Authority()
        for action in ({"allowed": True, "reason": "STALE_EPOCH"}, {"allowed": False, "reason": "OTHER"}):
            self.service.authority.attempt_action = lambda request, value=action: value
            with self.assertRaisesRegex(ValueError, "PREDECESSOR_ACTION_DENIAL_NOT_OBSERVED"): self.service._advance(current("AUTHORIZED"))
        self.service.authority = Authority()
        for memory in ({"allowed": True, "reason": "MEMORY_REVOKED", "candidates_examined": 0},
                       {"allowed": False, "reason": "OTHER", "candidates_examined": 0},
                       {"allowed": False, "reason": "MEMORY_REVOKED", "candidates_examined": 1}):
            self.service.authority.attempt_memory = lambda request, value=memory: value
            with self.assertRaisesRegex(ValueError, "PREDECESSOR_MEMORY_DENIAL_NOT_OBSERVED"): self.service._advance(current("AUTHORIZED"))
        self.service.authority = Authority()
        for activation in ({"status": "BAD", "epoch": 42}, {"status": "ACTIVE", "epoch": 41}):
            self.service.authority.activate_successor = lambda request, value=activation: value
            with self.assertRaisesRegex(ValueError, "SUCCESSOR_ACTIVATION_NOT_OBSERVED"): self.service._advance(current("PREDECESSOR_FENCED"))
        self.service.authority = Authority()
        for observation in ({"effect_count": 2, "provider_ref": "p"}, {"effect_count": 1, "provider_ref": None}):
            self.service.effects.reconcile = lambda request, value=observation: value
            with self.assertRaisesRegex(ValueError, "PROVIDER_EFFECT_NOT_OBSERVED_ONCE"): self.service._advance(current("SUCCESSOR_ACTIVE"))
        self.service.effects = Effects()
        for bundle in ({"profile": "wrong", "artifacts": [{}]}, {"profile": "reference-google-cloud", "artifacts": []}):
            self.service.exporter.export = lambda run, observations, value=bundle: value
            with self.assertRaisesRegex(ValueError, "CONTRACT_EXPORT_INVALID"): self.service._advance(current("EFFECT_OBSERVED"))
        self.service.exporter = Exporter()
        for result, code in [({"status": "OTHER", "verifier_principal": "v"}, "VERIFIER_RESULT_INVALID"),
                             ({"status": "FAIL", "outcome": "VERIFIED", "verifier_principal": "v"}, "CONTINUITY_NOT_VERIFIED"),
                             ({"status": "PASS", "outcome": "FAILED", "verifier_principal": "v"}, "CONTINUITY_NOT_VERIFIED")]:
            self.service.verifier.verify = lambda request, value=result: value
            with self.assertRaisesRegex(ValueError, code): self.service._advance(current("CONTRACT_EXPORTED"))


class _Snap:
    def __init__(self, client, path): self.client, self.path, self.id = client, path, path.rsplit("/", 1)[-1]
    @property
    def exists(self): return self.path in self.client.data
    def to_dict(self): return deepcopy(self.client.data[self.path])


class _Doc:
    def __init__(self, client, path): self.client, self.path, self.id = client, path, path.rsplit("/", 1)[-1]
    def get(self, transaction=None): return _Snap(self.client, self.path)
    def collection(self, name): return _Coll(self.client, f"{self.path}/{name}")


class _Query:
    def __init__(self, client, prefix): self.client, self.prefix = client, prefix
    def order_by(self, field): self.field = field; return self
    def stream(self):
        prefix = self.prefix + "/"
        values = [_Snap(self.client, path) for path in self.client.data if path.startswith(prefix) and "/" not in path[len(prefix):]]
        return sorted(values, key=lambda item: item.to_dict().get(self.field, 0))


class _Coll:
    def __init__(self, client, path): self.client, self.path = client, path
    def document(self, key): return _Doc(self.client, f"{self.path}/{key}")
    def order_by(self, field): return _Query(self.client, self.path).order_by(field)


class _Txn:
    def __init__(self, client): self.client = client
    def create(self, ref, value):
        if ref.path in self.client.data: raise RuntimeError("exists")
        self.client.data[ref.path] = deepcopy(value)
    def update(self, ref, value): self.client.data[ref.path].update(deepcopy(value))


class _Client:
    def __init__(self): self.data = {}
    def collection(self, name): return _Coll(self, name)
    def transaction(self): return _Txn(self)


class FirestoreScenarioStoreTests(unittest.TestCase):
    def setUp(self):
        self.modules = patch("google.cloud.firestore.transactional", lambda fn: fn)
        self.modules.start(); self.client = _Client(); self.store = FirestoreScenarioStore(self.client)
    def tearDown(self): self.modules.stop()

    def test_create_load_advance_observe_and_all_conflicts(self):
        run = {"run_id": "r", "phase": "CREATED", "revision": 0}
        self.assertEqual(self.store.create(run), (run, False))
        self.assertEqual(self.store.create(run), (run, True))
        self.assertEqual(self.store.load("r"), run); self.assertIsNone(self.store.load("missing"))
        observation = {"sequence": 1, "kind": "k"}
        updated = self.store.advance("r", "CREATED", "NEXT", {"revision": 1}, observation)
        self.assertEqual(updated["phase"], "NEXT"); self.assertEqual(self.store.observations("r"), [observation])
        with self.assertRaisesRegex(ScenarioConflict, "RUN_NOT_FOUND"):
            self.store.advance("missing", "CREATED", "NEXT", {}, observation)
        with self.assertRaisesRegex(ScenarioConflict, "RUN_PHASE_CONFLICT"):
            self.store.advance("r", "CREATED", "NEXT", {}, {"sequence": 2})
        self.client.data["continuity_runs/r"]["phase"] = "CREATED"
        with self.assertRaisesRegex(ScenarioConflict, "OBSERVATION_SEQUENCE_CONFLICT"):
            self.store.advance("r", "CREATED", "NEXT", {}, observation)


if __name__ == "__main__":
    unittest.main()

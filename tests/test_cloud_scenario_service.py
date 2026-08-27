from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from continuum.cloud_scenario_service import (CanonicalCloudScenario, DurableCloudScenarioService,
    FirestoreScenarioStore, ScenarioConflict, canonical_context_items,
    canonical_run_command, canonical_run_correlation_id, canonical_successor_candidates)
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
        selected = max(request["eligible_candidates"], key=lambda item: item["trust_score"])
        return {"evidence_ids": [item["event_id"] if "event_id" in item else item["type"]
                                 for item in request["evidence"]],
                "hypothesis": "compromised",
                "proposed_actions": ["initiate_governed_succession"],
                "successor_choice": {"selected_candidate_id": selected["candidate_id"],
                    "candidate_evidence_refs": selected["evidence_refs"],
                    "rationale": "highest verified trust", "objective": request["selection_objective"]}}


class Evidence:
    def record_initial(self, request):
        return [
            {"type": "document.injection_detected", "source": "document-ingress"},
            {"type": "action.denied", "source": "action-gateway"},
        ]
    def detect_missing(self, request):
        if datetime.fromisoformat(request["now"].replace("Z", "+00:00")) < datetime.fromisoformat(request["deadline"].replace("Z", "+00:00")):
            return None
        return {"type": "expectation.missed", "event_type": "expectation.missed",
                "event_id": "missed-1", "run_id": request["run_id"]}
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
                "request_digest": request["request_digest"],
                "compliance_evidence_id": request["compliance_evidence_id"]}


class Compliance:
    def verify(self, request):
        return {"status": "VERIFIED", "evidence_id": "compliance-1",
                "document_hash": "sha256:document", "obligation_id": request["obligation_id"],
                "workflow": "SUPPLIER_ASSURANCE_AGENT", "decision_scope": "SANDBOX_ONLY",
                "recommendation": "ONBOARD", "decision_pack_digest": "pack"}


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
    def test_run_and_trace_identity_share_one_server_owned_command(self):
        command = canonical_run_command("trace-run")
        self.assertNotIn("successor", command)
        self.assertEqual(32, len(canonical_run_correlation_id("trace-run")))
        custom = CanonicalCloudScenario(tenant_id="other")
        self.assertNotEqual(canonical_run_correlation_id("trace-run"),
                            canonical_run_correlation_id("trace-run", custom))

    def setUp(self):
        self.now = datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc)
        self.store, self.investigator, self.effects = Store(), Investigator(), Effects()
        self.exporter, self.verifier = Exporter(), Verifier()
        self.service = DurableCloudScenarioService(
            store=self.store, evidence=Evidence(), investigator=self.investigator,
            authority=Authority(),
            compliance=Compliance(), effects=self.effects, exporter=self.exporter,
            verifier=self.verifier, clock=lambda: self.now)

    def complete(self, run_id):
        started = self.service.run(run_id)
        self.assertEqual(started["phase"], "WAITING_FOR_DEADLINE")
        self.now += timedelta(seconds=9)
        published = self.service.tick(run_id)
        self.assertEqual(published["phase"], "MISSING_EVENT_PUBLISHED")
        return self.service.handle_event({"run_id": run_id, "event_type": "expectation.missed"})

    def test_run_persists_observed_lifecycle_and_independent_verification(self):
        result = self.complete("run-001")
        self.assertEqual(result["phase"], "VERIFIED")
        self.assertEqual(result["provider_observation"]["effect_count"], 1)
        self.assertEqual(result["verification"]["status"], "PASS")
        self.assertEqual(result["supplier_assurance"]["workflow"], "SUPPLIER_ASSURANCE_AGENT")
        self.assertEqual(result["business_impact"]["effect_scope"], "SANDBOX_ONLY")
        self.assertEqual([event["kind"] for event in self.store.events["run-001"]], [
            "expectation.persisted", "missing_event.published",
            "investigation.observed", "policy.decision_observed",
            "predecessor.denials_observed", "successor.activation_observed",
            "context.reconstruction_observed",
            "compliance.evidence_verified",
            "provider.effect_observed", "contract.exported",
            "independent.verification_observed"])
        self.assertEqual(self.verifier.request["provider_observation"]["effect_count"], 1)
        self.assertTrue(any(event["kind"] == "predecessor.denials_observed"
                            for event in self.exporter.observations))

    def test_retry_of_completed_run_does_not_repeat_effect(self):
        first = self.complete("run-retry")
        second = self.service.run("run-retry")
        self.assertEqual(first, second)
        self.assertEqual(self.service.tick("run-retry"), first)
        self.assertEqual(self.effects.execute_calls, 1)
        self.assertEqual(self.investigator.calls, 1)

    def test_dispatch_acknowledgement_cannot_author_success(self):
        self.effects.reconcile = lambda request: {"effect_count": 0, "provider_ref": None}
        with self.assertRaisesRegex(ValueError, "PROVIDER_EFFECT_NOT_OBSERVED_ONCE"):
            self.complete("run-no-effect")
        self.assertEqual(self.store.runs["run-no-effect"]["phase"], "COMPLIANCE_VERIFIED")
        self.assertIsNone(self.verifier.request)

    def test_incomplete_investigation_cannot_trigger_policy_or_mutation(self):
        self.investigator.investigate = lambda request: {"evidence_types": ["expectation.missed"]}
        with self.assertRaisesRegex(ValueError, "INVESTIGATION_EVIDENCE_INCOMPLETE"):
            self.complete("run-silence-only")
        self.assertEqual(self.store.runs["run-silence-only"]["phase"], "MISSING_EVENT_PUBLISHED")
        self.assertEqual(self.effects.execute_calls, 0)

    def test_verifier_result_requires_independent_identity(self):
        self.verifier.verify = lambda request: {"status": "PASS"}
        with self.assertRaisesRegex(ValueError, "VERIFIER_IDENTITY_MISSING"):
            self.complete("run-self-claim")
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

    def test_start_schedules_one_external_deadline_tick_when_configured(self):
        scheduler = Mock()
        scheduler.schedule.return_value = {"mode": "cloud-tasks", "task_name": "task"}
        self.service.deadline_scheduler = scheduler
        result = self.service.run("scheduled")
        self.assertEqual(result["phase"], "WAITING_FOR_DEADLINE")
        scheduler.schedule.assert_called_once()

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
        with self.assertRaisesRegex(KeyError, "RUN_NOT_FOUND"): self.service.tick("missing")
        with self.assertRaisesRegex(KeyError, "RUN_NOT_FOUND"):
            self.service.handle_event({"run_id": "missing", "event_type": "expectation.missed"})
        waiting = self.service.run("waiting")
        self.assertEqual(self.service.tick("waiting"), waiting)
        self.assertEqual(self.service.handle_event({"run_id": "waiting", "event_type": "other"}), waiting)
        self.assertEqual(self.service.handle_event({"run_id": "waiting", "event_type": "expectation.missed"}), waiting)
        with self.assertRaisesRegex(ScenarioConflict, "SCENARIO_PHASE_INVALID"):
            self.service._advance({**self.service._new_run("bad"), "phase": "UNKNOWN"})

    def test_every_observation_gate_rejects_contradiction(self):
        def current(phase):
            return {**self.service._new_run("gate"), "phase": phase,
                    "successor": "v18", "candidate_assessment": {"receipt_digest": "candidate"},
                    "decision": {"decision_id": "d"},
                    "compliance": {"status": "VERIFIED", "evidence_id": "e", "document_hash": "h"},
                    "context_reconstruction": {"receipt_digest": "context"},
                    "provider_observation": {"effect_count": 1, "provider_ref": "p", "request_digest": "r", "compliance_evidence_id": "e"},
                    "contract_bundle": {"profile": "reference-google-cloud", "artifacts": [{}]}}
        for evidence in ("bad", ["bad"]):
            self.service.evidence.observe = lambda request, value=evidence: value
            with self.assertRaisesRegex(ValueError, "LIFECYCLE_EVIDENCE_INVALID"): self.service._advance(current("MISSING_EVENT_PUBLISHED"))
        self.service.evidence = Evidence()
        self.store.events["gate"] = []
        for decision in ({"outcome": "HOLD", "decision_id": "d"},
                         {"outcome": "APPROVE_SUCCESSION", "decision_id": None}):
            self.service.authority.decide = lambda evidence, value=decision: value
            with self.assertRaisesRegex(ValueError, "SUCCESSION_NOT_AUTHORIZED"): self.service._advance(current("INVESTIGATED"))
        self.service.authority = Authority()
        self.service.investigator.investigate = lambda request: {
            "evidence_types": [item["type"] for item in request["evidence"]],
            "proposed_actions": ["request_operator_review"], "successor_choice": {}}
        with self.assertRaisesRegex(ValueError, "INVESTIGATION_RECOMMENDS_HOLD"):
            self.service._advance(current("MISSING_EVENT_PUBLISHED"))
        self.service.investigator = Investigator()
        self.service.successor_candidates = tuple(replace(item, health="DOWN")
                                                  for item in canonical_successor_candidates())
        with self.assertRaisesRegex(ValueError, "NO_ELIGIBLE_SUCCESSOR"):
            self.service._advance(current("MISSING_EVENT_PUBLISHED"))
        self.service.successor_candidates = canonical_successor_candidates()
        self.service.investigator.investigate = lambda request: {
            "evidence_types": [item["type"] for item in request["evidence"]],
            "proposed_actions": ["initiate_governed_succession"],
            "successor_choice": {"selected_candidate_id": "unknown",
                "candidate_evidence_refs": ["unknown"], "rationale": "x", "objective": "x"}}
        with self.assertRaisesRegex(ValueError, "SUCCESSOR_CHOICE_UNKNOWN"):
            self.service._advance(current("MISSING_EVENT_PUBLISHED"))
        self.service.investigator = Investigator()
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
        self.service.context_items = tuple(replace(item, classification="SECRET")
                                           for item in canonical_context_items())
        with self.assertRaisesRegex(ValueError, "CONTEXT_RECONSTRUCTION_INCOMPLETE"):
            self.service._advance(current("SUCCESSOR_ACTIVE"))
        self.service.context_items = (canonical_context_items()[0],)
        with self.assertRaisesRegex(ValueError, "CONTEXT_RECONSTRUCTION_INCOMPLETE"):
            self.service._advance(current("SUCCESSOR_ACTIVE"))
        self.service.context_items = canonical_context_items()
        self.service.compliance.verify = lambda request: {"status": "FAILED"}
        with self.assertRaisesRegex(ValueError, "COMPLIANCE_EVIDENCE_NOT_VERIFIED"):
            self.service._advance(current("CONTEXT_RECONSTRUCTED"))
        self.service.compliance = Compliance()
        for observation in ({"effect_count": 2, "provider_ref": "p"}, {"effect_count": 1, "provider_ref": None}):
            self.service.effects.reconcile = lambda request, value=observation: value
            with self.assertRaisesRegex(ValueError, "PROVIDER_EFFECT_NOT_OBSERVED_ONCE"): self.service._advance(current("COMPLIANCE_VERIFIED"))
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

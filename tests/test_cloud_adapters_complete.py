from __future__ import annotations

from copy import deepcopy
import os
import unittest
from unittest.mock import patch

from continuum.cloud_scenario_adapters import (
    AuthenticatedJsonClient, CloudTasksDeadlineScheduler, FirestoreAuthority, FirestoreLifecycleEvidence,
    FirestoreCompliance, FirestoreSandboxEffects, ObservedContractExporter, RemoteInvestigator,
    RemoteSupplierAssurance, RemoteVerifier, RoutedFirestoreSandboxEffects,
    RemoteCanonicalControlPlane, build_production_judge_controller,
    build_production_scenario_service, google_id_token,
)
from continuum.cloud_gateway import FirestoreActionGateway
from continuum.contract import canonical_bytes
from hashlib import sha256
from continuum.standard import verify_bundle
from tests.incident_fixtures import incident_extension


class Snapshot:
    def __init__(self, client, path): self.client, self.path, self.id = client, path, path.rsplit("/", 1)[-1]
    @property
    def exists(self): return self.path in self.client.data
    def to_dict(self): return deepcopy(self.client.data.get(self.path))


class Document:
    def __init__(self, client, path): self.client, self.path, self.id = client, path, path.rsplit("/", 1)[-1]
    def get(self, transaction=None): return Snapshot(self.client, self.path)
    def create(self, value):
        hook = self.client.create_hooks.pop(self.path, None)
        if hook: return hook(self, value)
        if self.path in self.client.data: raise RuntimeError("exists")
        self.client.data[self.path] = deepcopy(value)
    def set(self, value, merge=False):
        if merge: self.client.data.setdefault(self.path, {}).update(deepcopy(value))
        else: self.client.data[self.path] = deepcopy(value)


class Query:
    def __init__(self, client, prefix, predicate=lambda value: True): self.client, self.prefix, self.predicate = client, prefix, predicate
    def stream(self):
        prefix = self.prefix + "/"
        return [Snapshot(self.client, path) for path, value in self.client.data.items()
                if path.startswith(prefix) and "/" not in path[len(prefix):] and self.predicate(value)]


class Collection:
    def __init__(self, client, path): self.client, self.path = client, path
    def document(self, key): return Document(self.client, f"{self.path}/{key}")
    def where(self, field, operator, expected):
        self.client.last_where = (field, operator, expected)
        return Query(self.client, self.path, lambda value: value.get(field) == expected)


class Firestore:
    def __init__(self): self.data, self.create_hooks, self.last_where = {}, {}, None
    def collection(self, name): return Collection(self, name)
    def transaction(self): return Transaction(self)


class Transaction:
    def __init__(self, client): self.client = client
    def create(self, ref, value): return ref.create(value)
    def set(self, ref, value, merge=False): return ref.set(value, merge=merge)


class Publisher:
    def __init__(self): self.events = []
    def publish(self, event): self.events.append(deepcopy(event)); return f"m{len(self.events)}"


class Workload:
    def __init__(self, actor): self.actor, self.calls = actor, []
    def post(self, url, payload, *, run_id):
        self.calls.append((url, payload, run_id))
        return {"actor": self.actor, **({"state": "DISPATCHED"} if payload.get("operation") else {})}


def request(run="run-1"):
    return {"run_id": run, "correlation_id": "a" * 32, "obligation_id": "o",
            "tenant_id": "acme", "principal": "v17", "epoch": 41,
            "decision_id": "d", "idempotency_key": "key", "request_digest": "digest",
            "operation": "vendor.create"}


class CloudAdapterCompleteTests(unittest.TestCase):
    def setUp(self):
        self.transactional = patch("google.cloud.firestore.transactional", lambda fn: fn)
        self.transactional.start()

    def tearDown(self):
        self.transactional.stop()

    def test_authenticated_json_client_without_trace_and_invalid_response(self):
        observed = {}
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def read(self): return b"[]"
        def opener(req, timeout): observed["request"] = req; return Response()
        client = AuthenticatedJsonClient(lambda audience: "token", opener)
        with self.assertRaisesRegex(ValueError, "WORKER_RESPONSE_INVALID"):
            client.post("https://worker.run.app/path", {"correlation_id": "not-trace"}, run_id="r")
        self.assertIsNone(observed["request"].get_header("Traceparent"))
        with self.assertRaisesRegex(ValueError, "WORKER_RESPONSE_INVALID"):
            client.get("https://worker.run.app/path", run_id="r")
        self.assertEqual(observed["request"].method, "GET")
        class Good(Response):
            def read(self): return b'{"status":"ok"}'
        client.opener = lambda req, timeout: Good()
        self.assertEqual(client.get("https://worker.run.app/path", run_id="r"), {"status":"ok"})

    def test_remote_canonical_control_and_judge_factory_are_fail_closed(self):
        class Client:
            def post(self, url, payload, *, run_id):
                return {"run_id": run_id, "url": url, "payload": payload}
            def get(self, url, *, run_id): return {"run_id": run_id, "url": url}
        remote = RemoteCanonicalControlPlane(Client(), "https://control/")
        self.assertEqual(remote.start("r")["payload"], {"run_id": "r"})
        self.assertTrue(remote.status("r")["url"].endswith("/cloud-smoke/r"))
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(build_production_judge_controller())
        environment = {"GOOGLE_CLOUD_PROJECT": "p", "CONTINUUM_CONTROL_URL": "https://control",
                       "CONTINUUM_JUDGE_HMAC_SECRET": "x" * 32}
        db = Firestore()
        with patch.dict(os.environ, environment, clear=True), \
             patch("google.cloud.firestore.Client", return_value=db):
            controller = build_production_judge_controller()
        self.assertIsNotNone(controller)
        self.assertIs(controller.quota.client, db)

    def test_lifecycle_evidence_create_reuse_emission_and_content_conflict(self):
        db, publisher = Firestore(), Publisher(); adapter = FirestoreLifecycleEvidence(db, publisher)
        command = {**request(), "deadline": "2026-08-26T10:00:00Z", "now": "2026-08-26T10:00:01Z"}
        adapter.record_initial(command); adapter.detect_missing(command)
        observed = adapter.observe(command)
        self.assertEqual(len(observed), 3); self.assertEqual(len(publisher.events), 3)
        self.assertEqual(len(adapter.record_initial(command)), 2)
        self.assertEqual(adapter.observe(command), observed); self.assertEqual(len(publisher.events), 3)
        path = next(path for path, value in db.data.items() if path.startswith("continuity_events/") and value["event_type"] == "action.denied")
        db.data[path]["source"] = "tampered"
        with self.assertRaisesRegex(ValueError, "LIFECYCLE_EVENT_CONTENT_CONFLICT"):
            adapter.record_initial(command)

        early = {**request("early"), "deadline": "2026-08-26T10:00:01Z",
                 "now": "2026-08-26T10:00:00Z"}
        adapter = FirestoreLifecycleEvidence(Firestore(), Publisher())
        adapter.record_initial(early)
        self.assertIsNone(adapter.detect_missing(early))
        verified_event = {"event_id": "verified", "event_type": "compliance.evidence_verified",
                          "correlation_id": early["correlation_id"]}
        adapter.client.data["continuity_events/verified"] = verified_event
        self.assertIsNone(adapter.detect_missing({**early, "now": "2026-08-26T10:00:02Z"}))

    def test_lifecycle_event_and_outbox_create_races_and_incomplete_query(self):
        db, publisher = Firestore(), Publisher(); adapter = FirestoreLifecycleEvidence(db, publisher)
        first_type = sorted(adapter.INITIAL)[0]
        import hashlib
        from continuum.contract import canonical_bytes
        event_id = hashlib.sha256(canonical_bytes({"run_id": "race", "event_type": first_type})).hexdigest()
        event_path = f"continuity_events/{event_id}"
        def event_race(doc, value): db.data[doc.path] = deepcopy(value); raise RuntimeError("race")
        db.create_hooks[event_path] = event_race
        outbox_path = f"continuity_outbox/{event_id}"
        def outbox_race(doc, value): db.data[doc.path] = deepcopy(value); raise RuntimeError("race")
        db.create_hooks[outbox_path] = outbox_race
        command = {**request("race"), "deadline": "2026-08-26T10:00:00Z", "now": "2026-08-26T10:00:01Z"}
        with self.assertRaisesRegex(RuntimeError, "race"):
            adapter.record_initial(command)

        clean = Firestore(); adapter = FirestoreLifecycleEvidence(clean, Publisher())
        adapter.record_initial(command); adapter.detect_missing(command)
        self.assertEqual(len(adapter.observe(command)), 3)

        broken = Firestore(); adapter = FirestoreLifecycleEvidence(broken, Publisher())
        broken.create_hooks[event_path] = lambda doc, value: (_ for _ in ()).throw(RuntimeError("lost"))
        with self.assertRaisesRegex(RuntimeError, "lost"): adapter.record_initial(command)

        incomplete = Firestore(); adapter = FirestoreLifecycleEvidence(incomplete, Publisher())
        original_where = Collection.where
        with patch.object(Collection, "where", lambda self, *args: Query(self.client, self.path, lambda value: False)):
            with self.assertRaisesRegex(ValueError, "LIFECYCLE_EVIDENCE_INCOMPLETE"): adapter.observe(request("incomplete"))
        self.assertIsNotNone(original_where)

    def test_transaction_race_reuses_identical_event_and_rejects_substitution(self):
        command = {**request("txn-race"), "deadline": "2026-08-26T10:00:00Z"}
        event_type = "action.denied"
        event_id = sha256(canonical_bytes({"run_id": "txn-race", "event_type": event_type})).hexdigest()
        event_path = f"continuity_events/{event_id}"
        expected = {"event_id": event_id, "event_type": event_type, "run_id": "txn-race",
                    "correlation_id": "a" * 32, "obligation_id": "o",
                    "source": "procurement-succession-v1", "redelivery_probe": False,
                    "deadline": "2026-08-26T10:00:00Z"}
        original = Document.get
        for substituted in (False, True):
            with self.subTest(substituted=substituted):
                db = Firestore(); adapter = FirestoreLifecycleEvidence(db, Publisher()); calls = 0
                def raced(doc, transaction=None):
                    nonlocal calls
                    if doc.path == event_path:
                        calls += 1
                        if calls == 2:
                            db.data[event_path] = {**expected, **({"source": "attacker"} if substituted else {})}
                    return original(doc, transaction=transaction)
                with patch.object(Document, "get", raced):
                    if substituted:
                        with self.assertRaisesRegex(ValueError, "LIFECYCLE_EVENT_CONTENT_CONFLICT"):
                            adapter._record(command, event_type)
                    else:
                        self.assertEqual(adapter._record(command, event_type), expected)

    def test_outbox_race_with_wrong_event_is_rejected(self):
        db, publisher = Firestore(), Publisher(); adapter = FirestoreLifecycleEvidence(db, publisher)
        import hashlib
        from continuum.contract import canonical_bytes
        first_type = sorted(adapter.INITIAL)[0]
        event_id = hashlib.sha256(canonical_bytes({"run_id": "race2", "event_type": first_type})).hexdigest()
        path = f"continuity_outbox/{event_id}"
        def wrong(doc, value): db.data[doc.path] = {**value, "event_id": "other"}; raise RuntimeError("race")
        db.create_hooks[path] = wrong
        with self.assertRaisesRegex(RuntimeError, "race"): adapter.record_initial({**request("race2"), "deadline": "2026-08-26T10:00:00Z"})

    def test_remote_investigator_authority_and_all_denials(self):
        class Client:
            def post(self, url, payload, *, run_id):
                return {"actor": "v18@example", "proposal": {
                    "evidence_ids": ["e1"],
                    "proposed_actions": ["initiate_governed_succession"],
                    "successor_choice": {"selected_candidate_id": "v18",
                        "evidence_manifest_refs": ["build:v18", "health:v18"],
                        "supporting_citations": [{"claim": "BUILD_PROVENANCE",
                                                  "evidence_refs": ["build:v18"]}]}}}
        proposal = RemoteInvestigator(Client(), "https://v18").investigate({
            "run_id": "r", "incident_assessment_receipt": {
                "receipt_digest": incident_extension()["incident_assessment"]["receipt_digest"]}})
        self.assertEqual(proposal["evidence_ids"], ["e1"])

        db = Firestore(); workload = Workload("v17@example")
        authority = FirestoreAuthority(db, workload, "https://v17", "v17@example")
        self.assertEqual(authority.decide([])["outcome"], "HOLD")
        self.assertEqual(authority.decide([{"evidence": {
            "incident_assessment": {"unexpected": True}}}])["outcome"], "HOLD")
        evidence = [{"kind": "investigation.observed", "evidence": {
            "signals": [{"event_type": value} for value in FirestoreLifecycleEvidence.REQUIRED],
            "selected_plan": "initiate_governed_succession",
            "incident_assessment": incident_extension()["incident_assessment"]}}]
        self.assertEqual(authority.decide(evidence)["outcome"], "APPROVE_SUCCESSION")
        mismatch = deepcopy(evidence)
        mismatch[0]["evidence"]["signals"] = []
        self.assertEqual(authority.decide(mismatch)["outcome"], "HOLD")
        with self.assertRaisesRegex(ValueError, "PREDECESSOR_NOT_FENCED"): authority.activate_successor(request())
        authority.fence_predecessor(request())
        with self.assertRaisesRegex(ValueError, "AUTHORITY_EPOCH_REGRESSION"):
            authority.fence_predecessor({**request(), "epoch": 40})
        with self.assertRaisesRegex(ValueError, "SUCCESSOR_EPOCH_NOT_MONOTONIC"):
            authority.activate_successor({**request(), "principal": "v18", "epoch": 41})
        activated = authority.activate_successor({**request(), "principal": "v18", "epoch": 42})
        self.assertEqual(activated["status"], "ACTIVE")
        self.assertFalse(authority.attempt_action(request())["allowed"])
        self.assertFalse(authority.attempt_memory(request())["allowed"])
        self.assertTrue(authority.attempt_action({**request(), "epoch": 42})["allowed"])
        self.assertTrue(authority.attempt_memory({**request(), "epoch": 42})["allowed"])
        authority.predecessor_identity = "other"
        with self.assertRaisesRegex(ValueError, "PREDECESSOR_IDENTITY_MISMATCH"): authority.attempt_action(request())
        with self.assertRaisesRegex(ValueError, "PREDECESSOR_IDENTITY_MISMATCH"): authority.attempt_memory(request())

    def test_sandbox_effects_identity_idempotency_and_reconciliation(self):
        db = Firestore(); workload = Workload("v18@example")
        effects = FirestoreSandboxEffects(db, workload, "https://v18", "v18@example")
        req = request()
        self.assertEqual(effects.reconcile(req), {"effect_count": 0, "provider_ref": None})
        self.assertEqual(effects.execute(req)["state"], "DISPATCHED")
        ref = effects._ref(req)
        ref.create({"provider_ref": f"firestore://continuity_sandbox_vendors/{ref.id}",
                    "request_digest": "digest", "run_id": "run-1",
                    "compliance_evidence_id": "e1"})
        self.assertEqual(effects.execute(req)["state"], "DISPATCHED")
        self.assertEqual(effects.reconcile(req)["effect_count"], 1)
        with self.assertRaisesRegex(ValueError, "PROVIDER_DIGEST_CONFLICT"):
            effects.reconcile({**req, "request_digest": "other"})
        effects.successor_identity = "other"
        with self.assertRaisesRegex(ValueError, "SUCCESSOR_IDENTITY_MISMATCH"): effects.execute(req)
        effects.successor_identity = "v18@example"
        class InvalidWorkload:
            def post(self, *args, **kwargs): return {"actor": "v18@example", "state": "UNKNOWN"}
        effects.workload_client = InvalidWorkload()
        with self.assertRaisesRegex(ValueError, "ACTION_GATEWAY_RESULT_INVALID"):
            effects.execute(req)

        routed_workload = Workload("v18@example")
        routed = RoutedFirestoreSandboxEffects(db, routed_workload,
                                               {"v18": ("https://v18", "v18@example")})
        self.assertEqual(routed.execute({**req, "principal": "v18"})["state"], "DISPATCHED")
        with self.assertRaisesRegex(ValueError, "SUCCESSOR_ROUTE_NOT_CONFIGURED"):
            routed.execute({**req, "principal": "unknown"})
        routed.routes["v18"] = ("https://v18", "other@example")
        with self.assertRaisesRegex(ValueError, "SUCCESSOR_IDENTITY_MISMATCH"):
            routed.execute({**req, "principal": "v18"})
        routed.routes["v18"] = ("https://v18", "v18@example")
        routed.workload_client = InvalidWorkload()
        with self.assertRaisesRegex(ValueError, "ACTION_GATEWAY_RESULT_INVALID"):
            routed.execute({**req, "principal": "v18"})

    def test_compliance_adapter_and_transactional_action_gateway(self):
        db = Firestore()
        compliance = FirestoreCompliance(db)
        command = {"run_id": "r", "tenant_id": "acme", "obligation_id": "o",
                   "vendor_id": "vendor-042"}
        evidence = compliance.verify(command)
        self.assertEqual(compliance.verify(command), evidence)
        db.data["continuity_compliance/r"]["status"] = "FAILED"
        with self.assertRaisesRegex(ValueError, "COMPLIANCE_EVIDENCE_CONFLICT"):
            compliance.verify(command)
        db.data["continuity_compliance/r"] = evidence
        db.data["continuity_authority/acme"] = {
            "status": "ACTIVE", "active_principal": "v18", "epoch": 42,
            "decision_id": "d", "run_id": "r",
        }
        base = {"run_id": "r", "correlation_id": "a" * 32, "tenant_id": "acme",
                "principal": "v18", "epoch": 42, "obligation_id": "o",
                "decision_id": "d", "idempotency_key": "key", "operation": "vendor.create",
                "vendor_id": "vendor-042", "compliance_evidence_id": evidence["evidence_id"],
                "compliance_document_hash": evidence["document_hash"],
                "context_receipt_digest": "sha256:context"}
        req = {**base, "request_digest": sha256(canonical_bytes(base)).hexdigest()}
        def changed(**values):
            unsigned = {**base, **values}
            return {**unsigned, "request_digest": sha256(canonical_bytes(unsigned)).hexdigest()}
        gateway = FirestoreActionGateway(db, expected_actor="v18@example")
        first = gateway.execute_vendor_create(req, actor="v18@example")
        self.assertEqual(first["state"], "DISPATCHED")
        provider_path = next(key for key in db.data if key.startswith("continuity_sandbox_vendors/"))
        self.assertEqual("sha256:context", db.data[provider_path]["context_receipt_digest"])
        self.assertEqual(gateway.execute_vendor_create(req, actor="v18@example")["state"], "DEDUPLICATED")
        external = type("Queue", (), {"converge": lambda self, request: {
            "provider":"github-issues", "provider_ref":"https://github.test/o/r/issues/7",
            "resource_id":"7", "state":"OPEN"}})()
        external_result = FirestoreActionGateway(
            db, expected_actor="v18@example", external_queue=external).execute_vendor_create(
                req, actor="v18@example")
        self.assertEqual(external_result["provider"], "github-issues")
        self.assertEqual(db.data[provider_path]["external_effect"]["resource_id"], "7")
        with self.assertRaisesRegex(ValueError, "ACTION_REQUEST_INVALID"):
            gateway.execute_vendor_create({"run_id": "r"}, actor="v18@example")
        with self.assertRaisesRegex(ValueError, "ACTION_REQUEST_DIGEST_MISMATCH"):
            gateway.execute_vendor_create({**req, "request_digest": "other"}, actor="v18@example")
        with self.assertRaisesRegex(ValueError, "WORKLOAD_IDENTITY_DENIED"):
            gateway.execute_vendor_create(req, actor="other@example")
        db.data[provider_path]["actor"] = "substituted@example"
        with self.assertRaisesRegex(ValueError, "IDEMPOTENCY_KEY_CONFLICT"):
            gateway.execute_vendor_create(req, actor="v18@example")
        db.data[provider_path]["actor"] = "v18@example"
        db.data["continuity_authority/acme"]["status"] = "FENCED"
        with self.assertRaisesRegex(ValueError, "AUTHORITY_PRECONDITION_FAILED"):
            gateway.execute_vendor_create(changed(idempotency_key="other"), actor="v18@example")
        db.data["continuity_authority/acme"]["status"] = "ACTIVE"
        db.data["continuity_compliance/r"]["status"] = "FAILED"
        with self.assertRaisesRegex(ValueError, "COMPLIANCE_PRECONDITION_FAILED"):
            gateway.execute_vendor_create(changed(idempotency_key="other"), actor="v18@example")

    def test_remote_supplier_agent_is_identity_bound_persisted_and_conflict_safe(self):
        db = Firestore()
        assurance = {"workflow": "SUPPLIER_ASSURANCE_AGENT", "status": "VERIFIED",
            "decision_scope": "SANDBOX_ONLY", "recommendation": "ONBOARD",
            "vendor_id": "vendor-042", "evidence_id": "e", "document_hash": "d",
            "decision_pack_digest": "pack", "tool_observations": [
                {"tool": "gleif", "source_url": "https://gleif", "evidence_ref": "g"}]}
        class Client:
            actor = "v18@example"
            result = assurance
            def post(self, url, payload, *, run_id):
                self.last = (url, payload, run_id)
                return {"actor": self.actor, "assurance": self.result}
        client = Client()
        adapter = RemoteSupplierAssurance(db, client,
            {"v18": ("https://v18", "v18@example")})
        request_value = {"run_id": "r", "tenant_id": "acme", "obligation_id": "o",
                         "vendor_id": "vendor-042", "successor": "v18", "application": {}}
        first = adapter.verify(request_value)
        self.assertEqual(adapter.verify(request_value), first)
        self.assertEqual(client.last[0], "https://v18/internal/assess-supplier")
        with self.assertRaisesRegex(ValueError, "SUPPLIER_ASSURANCE_ROUTE_NOT_CONFIGURED"):
            adapter.verify({**request_value, "successor": "unknown"})
        client.actor = "other"
        with self.assertRaisesRegex(ValueError, "SUPPLIER_ASSESSOR_IDENTITY_MISMATCH"):
            adapter.verify({**request_value, "run_id": "other"})
        client.actor = "v18@example"; client.result = {"status": "FAILED"}
        with self.assertRaisesRegex(ValueError, "SUPPLIER_ASSURANCE_RESULT_INVALID"):
            adapter.verify({**request_value, "run_id": "other"})
        client.result = assurance
        db.data["continuity_compliance/r"]["status"] = "FAILED"
        with self.assertRaisesRegex(ValueError, "SUPPLIER_ASSURANCE_EVIDENCE_CONFLICT"):
            adapter.verify(request_value)

    def test_observed_export_remote_verification_and_google_token(self):
        run = {**request(), "predecessor": "v17", "predecessor_epoch": 41,
               "successor": "v18", "successor_epoch": 42,
               "deadline": "2026-08-26T10:05:00Z",
               "candidate_assessment": {"requirements_digest": "req", "candidates_digest": "cand",
                   "assessments": [], "eligible_ids": ["v18"], "receipt_digest": "selection"},
               "context_reconstruction": {"succession_id": "r", "successor_principal": "v18",
                   "purpose": "complete vendor onboarding", "allowed_scopes": ["vendor.approved"],
                   "receipt_digest": "context", "decisions": [
                       {"item_id": "obligation", "included": True, "reason_code": "AUTHORIZED_MINIMUM"},
                       {"item_id": "raw", "included": False, "reason_code": "CLASS_RAW_UNTRUSTED_EXCLUDED"}]},
               "compliance": {"evidence_id": "e1", "document_hash": "doc",
                   "workflow": "SUPPLIER_ASSURANCE_AGENT", "decision_scope": "SANDBOX_ONLY",
                   "recommendation": "ONBOARD", "decision_pack_digest": "pack"},
               "decision": {"outcome": "APPROVE_SUCCESSION", "decision_id": "d"},
               "evidence_records": incident_extension()["records"],
               "evidence_validation": incident_extension()["evidence_validation"],
               "incident_assessment": incident_extension()["incident_assessment"],
               "provider_observation": {"effect_count": 1, "provider_ref": "firestore://vendor/1", "request_digest": "digest", "compliance_evidence_id": "e1"}}
        exporter = ObservedContractExporter("mailto:control@example", "mailto:verifier@example")
        bundle = exporter.export(run, [{"sequence": 1, "kind": "observed"}])
        self.assertEqual(len(bundle["artifacts"]), 5)
        receipt = next(item for item in bundle["artifacts"]
                       if item["artifact_type"] == "execution_receipt")
        self.assertEqual(receipt["extensions"]["continuum.dev/compliance"]
                         ["decision_pack_digest"], "pack")
        basic_run = deepcopy(run)
        basic_run["compliance"] = {"evidence_id": "e1", "document_hash": "doc"}
        basic_bundle = exporter.export(basic_run, [{"sequence": 1, "kind": "observed"}])
        basic_receipt = next(item for item in basic_bundle["artifacts"]
                             if item["artifact_type"] == "execution_receipt")
        self.assertNotIn("workflow", basic_receipt["extensions"]["continuum.dev/compliance"])
        class Client:
            response = {"verification": {"status": "PASS", "outcome": "VERIFIED", "bundle": {"artifacts": []}}, "actor": "verifier@example"}
            def post(self, *args, **kwargs): return self.response
        verifier = RemoteVerifier(Client(), "https://verifier", "fallback@example")
        self.assertEqual(verifier.verify({"run_id": "r", "correlation_id": "a" * 32, "bundle": bundle})["verifier_principal"], "verifier@example")
        Client.response = {"verification": {"status": "FAIL"}}
        self.assertEqual(verifier.verify({"run_id": "r", "correlation_id": "a" * 32, "bundle": bundle})["verifier_principal"], "fallback@example")
        with patch("google.oauth2.id_token.fetch_id_token", return_value="token") as fetch:
            self.assertEqual(google_id_token("audience"), "token"); self.assertEqual(fetch.call_args.args[1], "audience")

    def test_cloud_tasks_scheduler_is_deterministic_and_duplicate_safe(self):
        class Task:
            name = "projects/p/locations/r/queues/q/tasks/created"
        class Client:
            duplicate = False
            def queue_path(self, *parts): return "/".join(parts)
            def task_path(self, *parts): return "/".join(parts)
            def create_task(self, **kwargs):
                if self.duplicate:
                    from google.api_core.exceptions import AlreadyExists
                    raise AlreadyExists("exists")
                self.request = kwargs; return Task()
        client = Client(); scheduler = CloudTasksDeadlineScheduler(client, project="p", region="r",
            queue="q", control_url="https://control.run.app", oidc_service_account="push@example")
        first = scheduler.schedule(run_id="run", deadline="2026-08-26T10:00:08Z")
        self.assertEqual(first["task_name"], Task.name)
        self.assertEqual(client.request["task"]["http_request"]["oidc_token"]["audience"],
                         "https://control.run.app")
        client.duplicate = True
        self.assertIn("sentinel-", scheduler.schedule(
            run_id="run", deadline="2026-08-26T10:00:08Z")["task_name"])

    def test_production_factory_builds_complete_graph(self):
        required = {"GOOGLE_CLOUD_PROJECT": "p", "CONTINUUM_V17_URL": "https://v17",
                    "CONTINUUM_V18_URL": "https://v18", "CONTINUUM_V19_URL": "https://v19",
                    "CONTINUUM_VERIFIER_URL": "https://verifier",
                    "CONTINUUM_CONTROL_IDENTITY": "control@example", "CONTINUUM_V17_IDENTITY": "v17@example",
                    "CONTINUUM_V18_IDENTITY": "v18@example", "CONTINUUM_V19_IDENTITY": "v19@example",
                    "CONTINUUM_VERIFIER_IDENTITY": "verifier@example",
                    "CONTINUUM_CONTROL_URL": "https://control", "CONTINUUM_DEADLINE_QUEUE": "q",
                    "CONTINUUM_PUBSUB_PUSH_IDENTITY": "push@example", "CONTINUUM_REGION": "r",
                    "CONTINUUM_IMAGE_DIGEST": "sha256:" + "1" * 64,
                    "CONTINUUM_MODEL_ARMOR_TEMPLATE": "continuum-ingress"}
        db = Firestore()
        with patch.dict(os.environ, required, clear=True), \
             patch("google.cloud.firestore.Client", return_value=db), \
             patch("google.cloud.tasks_v2.CloudTasksClient", return_value=object()), \
             patch("continuum.cloud_scenario_adapters.PubSubLifecyclePublisher", return_value=Publisher()):
            service = build_production_scenario_service()
        self.assertIsNotNone(service); self.assertIs(service.store.client, db)
        self.assertEqual("v18@example", service.successor_candidates[0].service_identity)
        self.assertEqual("sha256:" + "1" * 64, service.successor_candidates[1].artifact_digest)
        self.assertIn("https://v19", service.successor_candidates[1].evidence_refs[1])
        self.assertIsInstance(service.compliance, RemoteSupplierAssurance)
        class Credentials:
            token = "access"
            def refresh(self, request): self.refreshed = request
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def read(self): return b'{"sanitizationResult":{"filterMatchState":"MATCH_FOUND","filterResults":{"pi_and_jailbreak":{"piAndJailbreakFilterResult":{"executionState":"EXECUTION_SUCCESS"}}}}}'
        credentials = Credentials()
        with patch("google.auth.default", return_value=(credentials, "p")), \
             patch("continuum.cloud_scenario_adapters.urlopen", return_value=Response()):
            receipt = service.input_guard.sanitize(text="attack", run_id="r")
        self.assertEqual(receipt["match_state"], "MATCH_FOUND")
        with patch("google.auth.default", return_value=(credentials, "p")), \
             patch("continuum.cloud_scenario_adapters.urlopen", return_value=type(
                 "Bad", (), {"__enter__":lambda s:s, "__exit__":lambda s,*a:None,
                              "read":lambda s:b'[]'})()):
            with self.assertRaisesRegex(ValueError, "MODEL_ARMOR_RESPONSE_INVALID"):
                service.input_guard.sanitize(text="attack", run_id="r")


if __name__ == "__main__": unittest.main()

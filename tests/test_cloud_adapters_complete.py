from __future__ import annotations

from copy import deepcopy
import os
import unittest
from unittest.mock import patch

from continuum.cloud_scenario_adapters import (
    AuthenticatedJsonClient, FirestoreAuthority, FirestoreLifecycleEvidence,
    FirestoreSandboxEffects, ObservedContractExporter, RemoteInvestigator,
    RemoteVerifier, build_production_scenario_service, google_id_token,
)
from continuum.standard import verify_bundle


class Snapshot:
    def __init__(self, client, path): self.client, self.path, self.id = client, path, path.rsplit("/", 1)[-1]
    @property
    def exists(self): return self.path in self.client.data
    def to_dict(self): return deepcopy(self.client.data.get(self.path))


class Document:
    def __init__(self, client, path): self.client, self.path, self.id = client, path, path.rsplit("/", 1)[-1]
    def get(self): return Snapshot(self.client, self.path)
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


class Publisher:
    def __init__(self): self.events = []
    def publish(self, event): self.events.append(deepcopy(event)); return f"m{len(self.events)}"


class Workload:
    def __init__(self, actor): self.actor, self.calls = actor, []
    def post(self, url, payload, *, run_id): self.calls.append((url, payload, run_id)); return {"actor": self.actor}


def request(run="run-1"):
    return {"run_id": run, "correlation_id": "a" * 32, "obligation_id": "o",
            "tenant_id": "acme", "principal": "v17", "epoch": 41,
            "decision_id": "d", "idempotency_key": "key", "request_digest": "digest"}


class CloudAdapterCompleteTests(unittest.TestCase):
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

    def test_lifecycle_evidence_create_reuse_emission_and_content_conflict(self):
        db, publisher = Firestore(), Publisher(); adapter = FirestoreLifecycleEvidence(db, publisher)
        observed = adapter.observe(request())
        self.assertEqual(len(observed), 3); self.assertEqual(len(publisher.events), 3)
        self.assertEqual(adapter.observe(request()), observed); self.assertEqual(len(publisher.events), 3)
        path = next(path for path, value in db.data.items() if path.startswith("continuity_events/") and value["event_type"] == "action.denied")
        db.data[path]["source"] = "tampered"
        with self.assertRaisesRegex(ValueError, "LIFECYCLE_EVENT_CONTENT_CONFLICT"): adapter.observe(request())

    def test_lifecycle_event_and_outbox_create_races_and_incomplete_query(self):
        db, publisher = Firestore(), Publisher(); adapter = FirestoreLifecycleEvidence(db, publisher)
        first_type = sorted(adapter.REQUIRED)[0]
        import hashlib
        from continuum.contract import canonical_bytes
        event_id = hashlib.sha256(canonical_bytes({"run_id": "race", "event_type": first_type})).hexdigest()
        event_path = f"continuity_events/{event_id}"
        def event_race(doc, value): db.data[doc.path] = deepcopy(value); raise RuntimeError("race")
        db.create_hooks[event_path] = event_race
        outbox_path = f"continuity_outbox/{event_id}"
        def outbox_race(doc, value): db.data[doc.path] = deepcopy(value); raise RuntimeError("race")
        db.create_hooks[outbox_path] = outbox_race
        self.assertEqual(len(adapter.observe(request("race"))), 3)

        broken = Firestore(); adapter = FirestoreLifecycleEvidence(broken, Publisher())
        broken.create_hooks[event_path] = lambda doc, value: (_ for _ in ()).throw(RuntimeError("lost"))
        with self.assertRaisesRegex(RuntimeError, "lost"): adapter.observe(request("race"))

        incomplete = Firestore(); adapter = FirestoreLifecycleEvidence(incomplete, Publisher())
        original_where = Collection.where
        with patch.object(Collection, "where", lambda self, *args: Query(self.client, self.path, lambda value: False)):
            with self.assertRaisesRegex(ValueError, "LIFECYCLE_EVIDENCE_INCOMPLETE"): adapter.observe(request("incomplete"))
        self.assertIsNotNone(original_where)

    def test_outbox_race_with_wrong_event_is_rejected(self):
        db, publisher = Firestore(), Publisher(); adapter = FirestoreLifecycleEvidence(db, publisher)
        import hashlib
        from continuum.contract import canonical_bytes
        first_type = sorted(adapter.REQUIRED)[0]
        event_id = hashlib.sha256(canonical_bytes({"run_id": "race2", "event_type": first_type})).hexdigest()
        path = f"continuity_outbox/{event_id}"
        def wrong(doc, value): db.data[doc.path] = {**value, "event_id": "other"}; raise RuntimeError("race")
        db.create_hooks[path] = wrong
        with self.assertRaisesRegex(RuntimeError, "race"): adapter.observe(request("race2"))

    def test_remote_investigator_authority_and_all_denials(self):
        class Client:
            def post(self, url, payload, *, run_id):
                return {"actor": "v18@example", "proposal": {"evidence_ids": ["e1"]}}
        proposal = RemoteInvestigator(Client(), "https://v18").investigate({"run_id": "r"})
        self.assertEqual(proposal["evidence_ids"], ["e1"])

        db = Firestore(); workload = Workload("v17@example")
        authority = FirestoreAuthority(db, workload, "https://v17", "v17@example")
        self.assertEqual(authority.decide([])["outcome"], "HOLD")
        evidence = [{"evidence": {"signals": [{"event_type": value} for value in FirestoreLifecycleEvidence.REQUIRED]}}]
        self.assertEqual(authority.decide(evidence)["outcome"], "APPROVE_SUCCESSION")
        with self.assertRaisesRegex(ValueError, "PREDECESSOR_NOT_FENCED"): authority.activate_successor(request())
        authority.fence_predecessor(request())
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
        self.assertEqual(effects.execute(req)["state"], "DEDUPLICATED")
        self.assertEqual(effects.reconcile(req)["effect_count"], 1)
        with self.assertRaisesRegex(ValueError, "IDEMPOTENCY_KEY_CONFLICT"):
            effects.execute({**req, "request_digest": "other"})
        with self.assertRaisesRegex(ValueError, "PROVIDER_DIGEST_CONFLICT"):
            effects.reconcile({**req, "request_digest": "other"})
        effects.successor_identity = "other"
        with self.assertRaisesRegex(ValueError, "SUCCESSOR_IDENTITY_MISMATCH"): effects.execute(req)

    def test_observed_export_remote_verification_and_google_token(self):
        run = {**request(), "predecessor": "v17", "predecessor_epoch": 41,
               "successor": "v18", "successor_epoch": 42,
               "decision": {"outcome": "APPROVE_SUCCESSION", "decision_id": "d"},
               "provider_observation": {"effect_count": 1, "provider_ref": "firestore://vendor/1", "request_digest": "digest"}}
        exporter = ObservedContractExporter("mailto:control@example", "mailto:verifier@example")
        bundle = exporter.export(run, [{"sequence": 1, "kind": "observed"}]); verify_bundle(bundle)
        class Client:
            response = {"verification": {"status": "PASS", "outcome": "VERIFIED"}, "actor": "verifier@example"}
            def post(self, *args, **kwargs): return self.response
        verifier = RemoteVerifier(Client(), "https://verifier", "fallback@example")
        self.assertEqual(verifier.verify({"run_id": "r", "correlation_id": "a" * 32, "bundle": bundle})["verifier_principal"], "verifier@example")
        Client.response = {"verification": {"status": "FAIL"}}
        self.assertEqual(verifier.verify({"run_id": "r", "correlation_id": "a" * 32, "bundle": bundle})["verifier_principal"], "fallback@example")
        with patch("google.oauth2.id_token.fetch_id_token", return_value="token") as fetch:
            self.assertEqual(google_id_token("audience"), "token"); self.assertEqual(fetch.call_args.args[1], "audience")

    def test_production_factory_builds_complete_graph(self):
        required = {"GOOGLE_CLOUD_PROJECT": "p", "CONTINUUM_V17_URL": "https://v17",
                    "CONTINUUM_V18_URL": "https://v18", "CONTINUUM_VERIFIER_URL": "https://verifier",
                    "CONTINUUM_CONTROL_IDENTITY": "control@example", "CONTINUUM_V17_IDENTITY": "v17@example",
                    "CONTINUUM_V18_IDENTITY": "v18@example", "CONTINUUM_VERIFIER_IDENTITY": "verifier@example"}
        db = Firestore()
        with patch.dict(os.environ, required, clear=True), \
             patch("google.cloud.firestore.Client", return_value=db), \
             patch("continuum.cloud_scenario_adapters.PubSubLifecyclePublisher", return_value=Publisher()):
            service = build_production_scenario_service()
        self.assertIsNotNone(service); self.assertIs(service.store.client, db)


if __name__ == "__main__": unittest.main()

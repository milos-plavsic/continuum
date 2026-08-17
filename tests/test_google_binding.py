from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from continuum.google_binding import (
    FirestoreContinuityStore,
    GoogleBindingConfig,
    OutboxDispatcher,
    PubSubLifecyclePublisher,
)


class _Future:
    def result(self, timeout):
        return f"message:{timeout}"


class _Publisher:
    def __init__(self):
        self.call = None

    def topic_path(self, project, topic):
        return f"projects/{project}/topics/{topic}"

    def publish(self, path, data, **attributes):
        self.call = (path, data, attributes)
        return _Future()


class _Snapshot:
    def __init__(self, reference):
        self.reference = reference
        self.id = reference.id
        self.exists = reference.id in reference.collection.documents

    def to_dict(self):
        return dict(self.reference.collection.documents[self.id])


class _Document:
    def __init__(self, collection, document_id):
        self.collection, self.id = collection, document_id

    def get(self, transaction=None):
        return _Snapshot(self)

    def update(self, updates):
        self.collection.documents[self.id].update(updates)


class _Query:
    def __init__(self, collection):
        self.collection, self.maximum, self.predicate = collection, 20, lambda value: True

    def where(self, field, operator, expected):
        if operator == "==":
            self.predicate = lambda value: value.get(field) == expected
        elif operator == "in":
            self.predicate = lambda value: value.get(field) in expected
        return self

    def limit(self, maximum):
        self.maximum = maximum
        return self

    def stream(self):
        refs = [_Document(self.collection, key) for key, value in self.collection.documents.items()
                if self.predicate(value)]
        return [_Snapshot(ref) for ref in refs[:self.maximum]]


class _Collection:
    def __init__(self):
        self.documents = {}

    def document(self, document_id):
        return _Document(self, document_id)

    def where(self, *args, **kwargs):
        return _Query(self).where(*args, **kwargs)


class _Transaction:
    def create(self, reference, value):
        if reference.id in reference.collection.documents:
            raise RuntimeError("already exists")
        reference.collection.documents[reference.id] = dict(value)

    def update(self, reference, updates):
        reference.collection.documents[reference.id].update(updates)

    def set(self, reference, value):
        reference.collection.documents[reference.id] = dict(value)


class _Firestore:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return self.collections.setdefault(name, _Collection())

    def transaction(self):
        return _Transaction()


class _EffectPublisher:
    def __init__(self, fail=False):
        self.calls, self.fail = 0, fail

    def publish(self, event):
        self.calls += 1
        if self.fail:
            raise TimeoutError("ambiguous")
        return "pubsub-1"


class GoogleBindingTests(unittest.TestCase):
    def setUp(self):
        self.firestore = _Firestore()
        self.store = FirestoreContinuityStore(
            GoogleBindingConfig("project", "events"), self.firestore)
        google = types.ModuleType("google")
        cloud = types.ModuleType("google.cloud")
        firestore = types.ModuleType("google.cloud.firestore")
        firestore.transactional = lambda fn: fn
        cloud.firestore = firestore
        google.cloud = cloud
        self.google_modules = patch.dict(sys.modules, {
            "google": google, "google.cloud": cloud, "google.cloud.firestore": firestore,
        })
        self.google_modules.start()

    def tearDown(self):
        self.google_modules.stop()

    def test_pubsub_adapter_publishes_canonical_event_and_trace_attributes(self):
        client = _Publisher()
        adapter = PubSubLifecyclePublisher(GoogleBindingConfig("project", "events"), client)
        message = adapter.publish({"event_type": "identity.fenced", "correlation_id": "trace-1", "schema_version": 1})
        self.assertEqual(message, "message:30")
        self.assertEqual(client.call[0], "projects/project/topics/events")
        self.assertEqual(client.call[2]["correlation_id"], "trace-1")
        self.assertEqual(client.call[1], b'{"correlation_id":"trace-1","event_type":"identity.fenced","schema_version":1}')

    def _reserve(self):
        return self.store.reserve_execution(scope="tenant/action", idempotency_key="key-1",
                                            request_digest="digest-a", record={"trace_id": "t"})

    def test_inbox_redelivery_is_deduplicated_and_substitution_rejected(self):
        args = dict(message_id="m1", event_digest="d1", event_id="e1",
                    received_at="2026-08-17T10:00:00Z")
        self.assertTrue(self.store.accept_inbox(**args))
        self.assertFalse(self.store.accept_inbox(**args))
        with self.assertRaisesRegex(ValueError, "MESSAGE_ID_CONTENT_CONFLICT"):
            self.store.accept_inbox(**{**args, "event_digest": "different"})
        self.store.mark_inbox_processed(message_id="m1", event_digest="d1",
                                        processed_at="2026-08-17T10:00:01Z")
        self.store.mark_inbox_processed(message_id="m1", event_digest="d1",
                                        processed_at="2026-08-17T10:00:02Z")

    def test_execution_lease_fences_concurrent_and_stale_workers(self):
        self._reserve()
        first = self.store.acquire_execution_lease(
            scope="tenant/action", idempotency_key="key-1", request_digest="digest-a",
            worker_id="worker-a", now="2026-08-17T10:00:00Z",
            lease_expires_at="2026-08-17T10:01:00Z")
        self.assertEqual(first["state"], "DISPATCHING")
        blocked = self.store.acquire_execution_lease(
            scope="tenant/action", idempotency_key="key-1", request_digest="digest-a",
            worker_id="worker-b", now="2026-08-17T10:00:30Z",
            lease_expires_at="2026-08-17T10:01:30Z")
        self.assertIsNone(blocked)
        takeover = self.store.acquire_execution_lease(
            scope="tenant/action", idempotency_key="key-1", request_digest="digest-a",
            worker_id="worker-b", now="2026-08-17T10:01:00Z",
            lease_expires_at="2026-08-17T10:02:00Z")
        self.assertEqual(takeover["lease_owner"], "worker-b")
        with self.assertRaisesRegex(ValueError, "EXECUTION_LEASE_LOST"):
            self.store.record_execution_outcome(
                scope="tenant/action", idempotency_key="key-1", request_digest="digest-a",
                state="CONFIRMED", provider_ref="p1", observed_at="2026-08-17T10:01:01Z",
                worker_id="worker-a")

    def test_unknown_execution_can_only_be_reconciled_not_blindly_redispatched(self):
        self._reserve()
        self.store.acquire_execution_lease(
            scope="tenant/action", idempotency_key="key-1", request_digest="digest-a",
            worker_id="worker-a", now="2026-08-17T10:00:00Z",
            lease_expires_at="2026-08-17T10:01:00Z")
        self.store.record_execution_outcome(
            scope="tenant/action", idempotency_key="key-1", request_digest="digest-a",
            state="UNKNOWN", provider_ref="lookup-key", observed_at="2026-08-17T10:00:10Z",
            worker_id="worker-a")
        claim = self.store.acquire_execution_lease(
            scope="tenant/action", idempotency_key="key-1", request_digest="digest-a",
            worker_id="reconciler", now="2026-08-17T10:00:11Z",
            lease_expires_at="2026-08-17T10:01:11Z")
        self.assertEqual(claim["state"], "RECONCILING")
        self.store.record_execution_outcome(
            scope="tenant/action", idempotency_key="key-1", request_digest="digest-a",
            state="RECONCILED", provider_ref="provider-object-1",
            observed_at="2026-08-17T10:00:12Z", worker_id="reconciler")
        self.assertIsNone(self.store.acquire_execution_lease(
            scope="tenant/action", idempotency_key="key-1", request_digest="digest-a",
            worker_id="worker-c", now="2026-08-17T10:02:00Z",
            lease_expires_at="2026-08-17T10:03:00Z"))

    def test_outbox_failure_releases_for_retry_and_publish_is_terminal(self):
        outbox = self.firestore.collection("continuity_outbox")
        outbox.documents["e1"] = {"event": {"event_id": "e1"}, "status": "PENDING", "attempts": 0}
        failed = _EffectPublisher(fail=True)
        dispatcher = OutboxDispatcher(self.store, failed)
        self.assertEqual(dispatcher.dispatch(
            worker_id="w1", published_at="2026-08-17T10:00:00Z",
            lease_expires_at="2026-08-17T10:01:00Z", retry_at="2026-08-17T10:00:10Z"), 0)
        self.assertEqual(outbox.documents["e1"]["status"], "PENDING")
        publisher = _EffectPublisher()
        dispatcher = OutboxDispatcher(self.store, publisher)
        self.assertEqual(dispatcher.dispatch(
            worker_id="w2", published_at="2026-08-17T10:00:10Z",
            lease_expires_at="2026-08-17T10:01:10Z", retry_at="2026-08-17T10:00:20Z"), 1)
        self.assertEqual(outbox.documents["e1"]["status"], "PUBLISHED")
        self.assertEqual(publisher.calls, 1)

    def test_expired_outbox_lease_is_recovered_after_dispatcher_crash(self):
        outbox = self.firestore.collection("continuity_outbox")
        outbox.documents["e1"] = {
            "event": {"event_id": "e1"}, "status": "PUBLISHING", "attempts": 1,
            "lease_owner": "dead-worker", "lease_expires_at": "2026-08-17T10:00:05Z",
        }
        publisher = _EffectPublisher()
        count = OutboxDispatcher(self.store, publisher).dispatch(
            worker_id="recovery-worker", published_at="2026-08-17T10:00:06Z",
            lease_expires_at="2026-08-17T10:01:06Z", retry_at="2026-08-17T10:00:16Z")
        self.assertEqual(count, 1)
        self.assertEqual(outbox.documents["e1"]["status"], "PUBLISHED")
        self.assertEqual(outbox.documents["e1"]["attempts"], 2)


if __name__ == "__main__":
    unittest.main()

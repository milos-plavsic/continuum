"""Google Cloud adapters for the Continuity Contract reference binding.

Imports are lazy so the deterministic profile remains credential-free. Deployed
Cloud Run workloads use Application Default Credentials from their assigned
user-managed service identities; this module never reads service-account keys.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contract import canonical_bytes


@dataclass(frozen=True)
class GoogleBindingConfig:
    project_id: str
    topic_id: str
    database: str = "(default)"
    event_collection: str = "continuity_events"
    aggregate_collection: str = "continuity_aggregates"
    outbox_collection: str = "continuity_outbox"


class FirestoreContinuityStore:
    def __init__(self, config: GoogleBindingConfig, client: Any | None = None):
        if client is None:
            from google.cloud import firestore
            client = firestore.Client(project=config.project_id, database=config.database)
        self.client, self.config = client, config

    def append_with_projection(self, *, event: dict[str, Any], aggregate_key: str,
                               expected_version: int, projection: dict[str, Any]) -> None:
        """Atomically append event, CAS projection, and enqueue an outbox record."""
        from google.cloud import firestore
        event_ref = self.client.collection(self.config.event_collection).document(event["event_id"])
        aggregate_ref = self.client.collection(self.config.aggregate_collection).document(aggregate_key)
        outbox_ref = self.client.collection(self.config.outbox_collection).document(event["event_id"])
        transaction = self.client.transaction()

        @firestore.transactional
        def commit(txn: Any) -> None:
            existing_event = event_ref.get(transaction=txn)
            if existing_event.exists:
                if existing_event.to_dict() != event:
                    raise ValueError("EVENT_ID_CONTENT_CONFLICT")
                return
            aggregate = aggregate_ref.get(transaction=txn)
            current = aggregate.to_dict().get("version", 0) if aggregate.exists else 0
            if current != expected_version:
                raise ValueError("AGGREGATE_VERSION_CONFLICT")
            txn.create(event_ref, event)
            txn.set(aggregate_ref, {**projection, "version": expected_version + 1})
            txn.create(outbox_ref, {"event": event, "status": "PENDING", "attempts": 0})

        commit(transaction)

    def accept_inbox(self, *, message_id: str, event_digest: str,
                     event_id: str, received_at: str) -> bool:
        """Persist Pub/Sub message identity before applying it; reject substitution."""
        from google.cloud import firestore
        reference = self.client.collection("continuity_inbox").document(message_id)
        transaction = self.client.transaction()

        @firestore.transactional
        def accept(txn: Any) -> bool:
            existing = reference.get(transaction=txn)
            if existing.exists:
                stored = existing.to_dict()
                if stored["event_digest"] != event_digest or stored["event_id"] != event_id:
                    raise ValueError("MESSAGE_ID_CONTENT_CONFLICT")
                return False
            txn.create(reference, {"event_digest": event_digest, "event_id": event_id,
                                   "received_at": received_at, "status": "RECEIVED"})
            return True

        return accept(transaction)

    def reserve_execution(self, *, scope: str, idempotency_key: str,
                          request_digest: str, record: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        """Durably reserve an effect before dispatch; same key/digest reuses it."""
        from google.cloud import firestore
        document_id = __import__("hashlib").sha256(f"{scope}\0{idempotency_key}".encode()).hexdigest()
        reference = self.client.collection("continuity_executions").document(document_id)
        transaction = self.client.transaction()

        @firestore.transactional
        def reserve(txn: Any) -> tuple[dict[str, Any], bool]:
            existing = reference.get(transaction=txn)
            if existing.exists:
                stored = existing.to_dict()
                if stored["request_digest"] != request_digest:
                    raise ValueError("IDEMPOTENCY_KEY_CONFLICT")
                return stored, True
            reserved = {**record, "scope": scope, "idempotency_key": idempotency_key,
                        "request_digest": request_digest, "state": "RESERVED", "attempts": 0}
            txn.create(reference, reserved)
            return reserved, False

        return reserve(transaction)

    def record_execution_outcome(self, *, scope: str, idempotency_key: str,
                                 request_digest: str, state: str,
                                 provider_ref: str | None, observed_at: str) -> None:
        if state not in {"CONFIRMED", "UNKNOWN", "FAILED", "RECONCILED"}:
            raise ValueError("INVALID_EXECUTION_STATE")
        from google.cloud import firestore
        document_id = __import__("hashlib").sha256(f"{scope}\0{idempotency_key}".encode()).hexdigest()
        reference = self.client.collection("continuity_executions").document(document_id)
        transaction = self.client.transaction()

        @firestore.transactional
        def update(txn: Any) -> None:
            snapshot = reference.get(transaction=txn)
            if not snapshot.exists:
                raise ValueError("EXECUTION_NOT_RESERVED")
            stored = snapshot.to_dict()
            if stored["request_digest"] != request_digest:
                raise ValueError("IDEMPOTENCY_KEY_CONFLICT")
            txn.update(reference, {"state": state, "provider_ref": provider_ref,
                                   "observed_at": observed_at, "attempts": stored.get("attempts", 0) + 1})

        update(transaction)

    def pending_outbox(self, limit: int = 20) -> list[tuple[str, dict[str, Any]]]:
        query = (self.client.collection(self.config.outbox_collection)
                 .where("status", "==", "PENDING").limit(limit))
        return [(snapshot.id, snapshot.to_dict()) for snapshot in query.stream()]

    def mark_outbox_published(self, event_id: str, message_id: str, published_at: str) -> None:
        self.client.collection(self.config.outbox_collection).document(event_id).update(
            {"status": "PUBLISHED", "message_id": message_id, "published_at": published_at}
        )


class PubSubLifecyclePublisher:
    def __init__(self, config: GoogleBindingConfig, client: Any | None = None):
        if client is None:
            from google.cloud import pubsub_v1
            client = pubsub_v1.PublisherClient()
        self.client, self.config = client, config
        self.topic_path = client.topic_path(config.project_id, config.topic_id)

    def publish(self, event: dict[str, Any]) -> str:
        future = self.client.publish(
            self.topic_path, canonical_bytes(event),
            event_type=str(event["event_type"]), correlation_id=str(event["correlation_id"]),
            schema_version=str(event.get("schema_version", 1)),
        )
        return future.result(timeout=30)


class OutboxDispatcher:
    """At-least-once dispatcher; durable inbox/event idempotency absorbs retries."""
    def __init__(self, store: FirestoreContinuityStore, publisher: PubSubLifecyclePublisher):
        self.store, self.publisher = store, publisher

    def dispatch(self, published_at: str, limit: int = 20) -> int:
        published = 0
        for event_id, item in self.store.pending_outbox(limit):
            message_id = self.publisher.publish(item["event"])
            self.store.mark_outbox_published(event_id, message_id, published_at)
            published += 1
        return published


def verify_cloud_run_identity_token(token: str, audience: str) -> dict[str, Any]:
    """Verify Google-signed ID token and its audience; caller maps email server-side."""
    from google.auth.transport import requests
    from google.oauth2 import id_token
    claims = id_token.verify_oauth2_token(token, requests.Request(), audience=audience)
    if not claims.get("email_verified") or not claims.get("email"):
        raise ValueError("WORKLOAD_IDENTITY_UNVERIFIED")
    return claims

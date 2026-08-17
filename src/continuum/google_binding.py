"""Google Cloud adapters for the Continuity Contract reference binding.

Imports are lazy so the deterministic profile remains credential-free. Deployed
Cloud Run workloads use Application Default Credentials from their assigned
user-managed service identities; this module never reads service-account keys.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
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

    def mark_inbox_processed(self, *, message_id: str, event_digest: str,
                             processed_at: str) -> None:
        """Complete inbox processing without allowing a redelivery to substitute content."""
        from google.cloud import firestore
        reference = self.client.collection("continuity_inbox").document(message_id)
        transaction = self.client.transaction()

        @firestore.transactional
        def complete(txn: Any) -> None:
            snapshot = reference.get(transaction=txn)
            if not snapshot.exists:
                raise ValueError("INBOX_MESSAGE_NOT_RECEIVED")
            stored = snapshot.to_dict()
            if stored["event_digest"] != event_digest:
                raise ValueError("MESSAGE_ID_CONTENT_CONFLICT")
            if stored.get("status") == "PROCESSED":
                return
            txn.update(reference, {"status": "PROCESSED", "processed_at": processed_at})

        complete(transaction)

    def reserve_execution(self, *, scope: str, idempotency_key: str,
                          request_digest: str, record: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        """Durably reserve an effect before dispatch; same key/digest reuses it."""
        from google.cloud import firestore
        document_id = _execution_document_id(scope, idempotency_key)
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
                        "request_digest": request_digest, "state": "RESERVED", "attempts": 0,
                        "lease_owner": None, "lease_expires_at": None}
            txn.create(reference, reserved)
            return reserved, False

        return reserve(transaction)

    def acquire_execution_lease(self, *, scope: str, idempotency_key: str,
                                request_digest: str, worker_id: str, now: str,
                                lease_expires_at: str) -> dict[str, Any] | None:
        """Claim dispatch/reconciliation, including safe takeover of an expired lease."""
        _validate_lease_window(now, lease_expires_at)
        from google.cloud import firestore
        reference = self.client.collection("continuity_executions").document(
            _execution_document_id(scope, idempotency_key))
        transaction = self.client.transaction()

        @firestore.transactional
        def acquire(txn: Any) -> dict[str, Any] | None:
            snapshot = reference.get(transaction=txn)
            if not snapshot.exists:
                raise ValueError("EXECUTION_NOT_RESERVED")
            stored = snapshot.to_dict()
            if stored["request_digest"] != request_digest:
                raise ValueError("IDEMPOTENCY_KEY_CONFLICT")
            state = stored["state"]
            if state in {"CONFIRMED", "RECONCILED", "FAILED"}:
                return None
            if state not in {"RESERVED", "UNKNOWN", "DISPATCHING", "RECONCILING"}:
                raise ValueError("INVALID_EXECUTION_STATE")
            if not _lease_available(stored, worker_id, now):
                return None
            next_state = "RECONCILING" if state in {"UNKNOWN", "RECONCILING"} else "DISPATCHING"
            claimed = {**stored, "state": next_state, "lease_owner": worker_id,
                       "lease_expires_at": lease_expires_at,
                       "attempts": stored.get("attempts", 0) + 1}
            txn.update(reference, {key: claimed[key] for key in
                                   ("state", "lease_owner", "lease_expires_at", "attempts")})
            return claimed

        return acquire(transaction)

    def record_execution_outcome(self, *, scope: str, idempotency_key: str,
                                 request_digest: str, state: str,
                                 provider_ref: str | None, observed_at: str,
                                 worker_id: str | None = None) -> None:
        if state not in {"CONFIRMED", "UNKNOWN", "FAILED", "RECONCILED"}:
            raise ValueError("INVALID_EXECUTION_STATE")
        from google.cloud import firestore
        document_id = _execution_document_id(scope, idempotency_key)
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
            if worker_id is not None and stored.get("lease_owner") != worker_id:
                raise ValueError("EXECUTION_LEASE_LOST")
            current = stored["state"]
            allowed = {
                "DISPATCHING": {"CONFIRMED", "UNKNOWN", "FAILED"},
                "RECONCILING": {"RECONCILED", "UNKNOWN", "FAILED"},
                # Backward-compatible completion for reservations created before leases.
                "RESERVED": {"CONFIRMED", "UNKNOWN", "FAILED"},
            }
            if state not in allowed.get(current, set()):
                raise ValueError("INVALID_EXECUTION_TRANSITION")
            txn.update(reference, {"state": state, "provider_ref": provider_ref,
                                   "observed_at": observed_at, "lease_owner": None,
                                   "lease_expires_at": None})

        update(transaction)

    def pending_outbox(self, limit: int = 20) -> list[tuple[str, dict[str, Any]]]:
        query = (self.client.collection(self.config.outbox_collection)
                 .where("status", "==", "PENDING").limit(limit))
        return [(snapshot.id, snapshot.to_dict()) for snapshot in query.stream()]

    def dispatchable_outbox(self, *, now: str, limit: int = 20) -> list[tuple[str, dict[str, Any]]]:
        """Return pending work plus expired publish claims so crashes cannot strand events."""
        instant = _parse_timestamp(now)
        query = (self.client.collection(self.config.outbox_collection)
                 .where("status", "in", ["PENDING", "PUBLISHING"]).limit(limit))
        candidates = []
        for snapshot in query.stream():
            item = snapshot.to_dict()
            retry_at = item.get("retry_at")
            lease_expires_at = item.get("lease_expires_at")
            if retry_at and _parse_timestamp(retry_at) > instant:
                continue
            if item["status"] == "PUBLISHING" and lease_expires_at and \
                    _parse_timestamp(lease_expires_at) > instant:
                continue
            candidates.append((snapshot.id, item))
        return candidates

    def acquire_outbox_lease(self, *, event_id: str, worker_id: str, now: str,
                             lease_expires_at: str) -> dict[str, Any] | None:
        """Claim one publish attempt; an expired PUBLISHING claim is recoverable."""
        _validate_lease_window(now, lease_expires_at)
        from google.cloud import firestore
        reference = self.client.collection(self.config.outbox_collection).document(event_id)
        transaction = self.client.transaction()

        @firestore.transactional
        def acquire(txn: Any) -> dict[str, Any] | None:
            snapshot = reference.get(transaction=txn)
            if not snapshot.exists:
                raise ValueError("OUTBOX_EVENT_NOT_FOUND")
            stored = snapshot.to_dict()
            if stored["status"] == "PUBLISHED":
                return None
            if stored["status"] not in {"PENDING", "PUBLISHING"}:
                raise ValueError("INVALID_OUTBOX_STATE")
            if not _lease_available(stored, worker_id, now):
                return None
            claimed = {**stored, "status": "PUBLISHING", "lease_owner": worker_id,
                       "lease_expires_at": lease_expires_at,
                       "attempts": stored.get("attempts", 0) + 1}
            txn.update(reference, {key: claimed[key] for key in
                                   ("status", "lease_owner", "lease_expires_at", "attempts")})
            return claimed

        return acquire(transaction)

    def mark_outbox_published(self, event_id: str, message_id: str, published_at: str,
                              worker_id: str | None = None) -> None:
        self._finish_outbox(event_id, worker_id, {"status": "PUBLISHED",
                            "message_id": message_id, "published_at": published_at,
                            "lease_owner": None, "lease_expires_at": None})

    def release_outbox(self, *, event_id: str, worker_id: str, error: str,
                       retry_at: str) -> None:
        self._finish_outbox(event_id, worker_id, {"status": "PENDING", "last_error": error,
                            "retry_at": retry_at, "lease_owner": None, "lease_expires_at": None})

    def _finish_outbox(self, event_id: str, worker_id: str | None,
                       updates: dict[str, Any]) -> None:
        from google.cloud import firestore
        reference = self.client.collection(self.config.outbox_collection).document(event_id)
        transaction = self.client.transaction()

        @firestore.transactional
        def finish(txn: Any) -> None:
            snapshot = reference.get(transaction=txn)
            if not snapshot.exists:
                raise ValueError("OUTBOX_EVENT_NOT_FOUND")
            stored = snapshot.to_dict()
            if worker_id is not None and stored.get("lease_owner") != worker_id:
                raise ValueError("OUTBOX_LEASE_LOST")
            if stored["status"] == "PUBLISHED" and updates["status"] == "PUBLISHED":
                if stored.get("message_id") != updates["message_id"]:
                    raise ValueError("OUTBOX_MESSAGE_ID_CONFLICT")
                return
            if stored["status"] not in {"PENDING", "PUBLISHING"}:
                raise ValueError("INVALID_OUTBOX_STATE")
            txn.update(reference, updates)

        finish(transaction)


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

    def dispatch(self, *, worker_id: str, published_at: str, lease_expires_at: str,
                 retry_at: str, limit: int = 20) -> int:
        published = 0
        for event_id, item in self.store.dispatchable_outbox(now=published_at, limit=limit):
            claimed = self.store.acquire_outbox_lease(
                event_id=event_id, worker_id=worker_id, now=published_at,
                lease_expires_at=lease_expires_at)
            if claimed is None:
                continue
            try:
                message_id = self.publisher.publish(claimed["event"])
            except Exception as error:
                self.store.release_outbox(event_id=event_id, worker_id=worker_id,
                                          error=type(error).__name__, retry_at=retry_at)
                continue
            self.store.mark_outbox_published(event_id, message_id, published_at, worker_id)
            published += 1
        return published


def _execution_document_id(scope: str, idempotency_key: str) -> str:
    return hashlib.sha256(f"{scope}\0{idempotency_key}".encode()).hexdigest()


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as error:
        raise ValueError("INVALID_LEASE_TIMESTAMP") from error
    if parsed.tzinfo is None:
        raise ValueError("INVALID_LEASE_TIMESTAMP")
    return parsed


def _validate_lease_window(now: str, lease_expires_at: str) -> None:
    if _parse_timestamp(lease_expires_at) <= _parse_timestamp(now):
        raise ValueError("INVALID_LEASE_WINDOW")


def _lease_available(stored: dict[str, Any], worker_id: str, now: str) -> bool:
    owner = stored.get("lease_owner")
    expiration = stored.get("lease_expires_at")
    return not owner or owner == worker_id or not expiration or _parse_timestamp(expiration) <= _parse_timestamp(now)


def verify_cloud_run_identity_token(token: str, audience: str) -> dict[str, Any]:
    """Verify Google-signed ID token and its audience; caller maps email server-side."""
    from google.auth.transport import requests
    from google.oauth2 import id_token
    claims = id_token.verify_oauth2_token(token, requests.Request(), audience=audience)
    if not claims.get("email_verified") or not claims.get("email"):
        raise ValueError("WORKLOAD_IDENTITY_UNVERIFIED")
    return claims

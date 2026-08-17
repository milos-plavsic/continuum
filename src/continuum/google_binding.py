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


def verify_cloud_run_identity_token(token: str, audience: str) -> dict[str, Any]:
    """Verify Google-signed ID token and its audience; caller maps email server-side."""
    from google.auth.transport import requests
    from google.oauth2 import id_token
    claims = id_token.verify_oauth2_token(token, requests.Request(), audience=audience)
    if not claims.get("email_verified") or not claims.get("email"):
        raise ValueError("WORKLOAD_IDENTITY_UNVERIFIED")
    return claims

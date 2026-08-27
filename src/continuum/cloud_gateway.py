"""Transactional Google Cloud action gateway for effect-bearing agent calls."""
from __future__ import annotations

from hashlib import sha256
from typing import Any

from .contract import canonical_bytes


class FirestoreActionGateway:
    """Atomically enforces authority, compliance, and idempotency before mutation."""

    def __init__(self, client: Any, *, expected_actor: str | None = None,
                 external_queue: Any | None = None):
        self.client = client
        self.expected_actor = expected_actor
        self.external_queue = external_queue

    def execute_vendor_create(self, request: dict[str, Any], *, actor: str) -> dict[str, Any]:
        if self.expected_actor is not None and actor != self.expected_actor:
            raise ValueError("WORKLOAD_IDENTITY_DENIED")
        required = {
            "run_id", "tenant_id", "principal", "epoch", "obligation_id",
            "decision_id", "idempotency_key", "operation", "vendor_id",
            "compliance_evidence_id", "compliance_document_hash",
            "context_receipt_digest", "request_digest",
        }
        if set(request) - {"correlation_id"} != required or request["operation"] != "vendor.create":
            raise ValueError("ACTION_REQUEST_INVALID")
        unsigned = {key: value for key, value in request.items() if key != "request_digest"}
        if request["request_digest"] != sha256(canonical_bytes(unsigned)).hexdigest():
            raise ValueError("ACTION_REQUEST_DIGEST_MISMATCH")
        from google.cloud import firestore
        authority_ref = self.client.collection("continuity_authority").document(request["tenant_id"])
        compliance_ref = self.client.collection("continuity_compliance").document(request["run_id"])
        key = sha256(
            f'{request["tenant_id"]}\0{request["run_id"]}\0{request["idempotency_key"]}'.encode()
        ).hexdigest()
        provider_ref = self.client.collection("continuity_sandbox_vendors").document(key)
        transaction = self.client.transaction()

        @firestore.transactional
        def commit(txn: Any) -> dict[str, Any]:
            authority_snapshot = authority_ref.get(transaction=txn)
            compliance_snapshot = compliance_ref.get(transaction=txn)
            provider_snapshot = provider_ref.get(transaction=txn)
            authority = authority_snapshot.to_dict() if authority_snapshot.exists else {}
            compliance = compliance_snapshot.to_dict() if compliance_snapshot.exists else {}
            if (authority.get("status") != "ACTIVE" or
                    authority.get("active_principal") != request["principal"] or
                    authority.get("epoch") != request["epoch"] or
                    authority.get("decision_id") != request["decision_id"]):
                raise ValueError("AUTHORITY_PRECONDITION_FAILED")
            if (compliance.get("status") != "VERIFIED" or
                    compliance.get("tenant_id") != request["tenant_id"] or
                    compliance.get("obligation_id") != request["obligation_id"] or
                    compliance.get("vendor_id") != request["vendor_id"] or
                    compliance.get("evidence_id") != request["compliance_evidence_id"] or
                    compliance.get("document_hash") != request["compliance_document_hash"]):
                raise ValueError("COMPLIANCE_PRECONDITION_FAILED")
            record = {
                "provider_ref": f"firestore://continuity_sandbox_vendors/{key}",
                "request_digest": request["request_digest"],
                "run_id": request["run_id"],
                "tenant_id": request["tenant_id"],
                "obligation_id": request["obligation_id"],
                "vendor_id": request["vendor_id"],
                "principal": request["principal"],
                "epoch": request["epoch"],
                "decision_id": request["decision_id"],
                "compliance_evidence_id": request["compliance_evidence_id"],
                "context_receipt_digest": request["context_receipt_digest"],
                "actor": actor,
            }
            if provider_snapshot.exists:
                existing = provider_snapshot.to_dict()
                # Provider enrichment is appended after the transaction.  Compare
                # the immutable request projection, not later observation fields,
                # so a Pub/Sub retry converges instead of becoming a false conflict.
                if any(existing.get(field) != value for field, value in record.items()):
                    raise ValueError("IDEMPOTENCY_KEY_CONFLICT")
                return {"state": "DEDUPLICATED", "provider_ref": existing["provider_ref"]}
            txn.create(provider_ref, record)
            return {"state": "DISPATCHED", "provider_ref": record["provider_ref"]}

        admitted = commit(transaction)
        if self.external_queue is None:
            return {**admitted, "actor": actor}
        external = self.external_queue.converge(request)
        provider_ref.set({"external_effect": external}, merge=True)
        # Keep the action-gateway disposition distinct from provider lifecycle
        # state (OPEN/CLOSED); callers authorize only DISPATCHED/DEDUPLICATED.
        provider_state = external.get("state")
        provider_fields = {key: value for key, value in external.items() if key != "state"}
        return {**admitted, **provider_fields, "provider_state": provider_state, "actor": actor}

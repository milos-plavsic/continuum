"""
Continuum: Read-Only Evidence Provider Boundary
File: verification/provider.py
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional

try:
    from google.cloud import firestore
except ImportError:
    firestore = None


class EvidenceProvider(ABC):
    """Abstract Read-Only Boundary for Ground Truth Verification."""

    @abstractmethod
    def get_agent_fencing_status(self, tenant_id: str, agent_id: str) -> bool:
        pass

    @abstractmethod
    def get_side_effect_count(self, tenant_id: str, obligation_id: str, effect_type: str) -> int:
        pass

    @abstractmethod
    def is_telemetry_complete(self, tenant_id: str, obligation_id: str) -> bool:
        pass

    @abstractmethod
    def get_nonce_used(self, tenant_id: str, nonce: str) -> bool:
        pass

    @abstractmethod
    def record_nonce(self, tenant_id: str, nonce: str, ttl_seconds: int) -> None:
        pass


class FirestoreEvidenceProvider(EvidenceProvider):
    """Production Read-Only Evidence Provider backed by Google Cloud Firestore."""

    def __init__(self, firestore_db_client: Optional[Any] = None):
        if firestore_db_client is None and firestore is not None:
            self.db = firestore.Client()
        else:
            self.db = firestore_db_client

    def get_agent_fencing_status(self, tenant_id: str, agent_id: str) -> bool:
        if not self.db:
            return False
        doc_ref = (
            self.db.collection("tenants")
            .document(tenant_id)
            .collection("authority_records")
            .document(agent_id)
        )
        snap = doc_ref.get()
        if not snap.exists:
            return False
        data = snap.to_dict() or {}
        return data.get("status") in ["QUARANTINED", "REVOKED"] or data.get("fenced") is True

    def get_side_effect_count(self, tenant_id: str, obligation_id: str, effect_type: str) -> int:
        if not self.db:
            return 0
        col_ref = (
            self.db.collection("tenants")
            .document(tenant_id)
            .collection("promise_ledger")
            .document(obligation_id)
            .collection("executed_effects")
        )
        query = col_ref.where("effect_type", "==", effect_type)
        return len(list(query.stream()))

    def is_telemetry_complete(self, tenant_id: str, obligation_id: str) -> bool:
        if not self.db:
            return False
        doc_ref = (
            self.db.collection("tenants")
            .document(tenant_id)
            .collection("promise_ledger")
            .document(obligation_id)
        )
        snap = doc_ref.get()
        if not snap.exists:
            return False
        data = snap.to_dict() or {}
        return data.get("telemetry_complete") is True

    def get_nonce_used(self, tenant_id: str, nonce: str) -> bool:
        if not self.db:
            return False
        doc_ref = (
            self.db.collection("tenants")
            .document(tenant_id)
            .collection("used_nonces")
            .document(nonce)
        )
        return doc_ref.get().exists

    def record_nonce(self, tenant_id: str, nonce: str, ttl_seconds: int) -> None:
        if not self.db:
            return
        doc_ref = (
            self.db.collection("tenants")
            .document(tenant_id)
            .collection("used_nonces")
            .document(nonce)
        )
        doc_ref.set({"consumed_at": datetime.now(timezone.utc).isoformat(), "ttl": ttl_seconds})
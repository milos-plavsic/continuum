"""
Continuum: Read-Only Evidence Provider Boundary
File: verification/provider.py
"""

from abc import ABC, abstractmethod
from typing import Any, Optional
from pydantic import BaseModel

try:
    from google.cloud import firestore
except ImportError:
    firestore = None


class AuthorityBinding(BaseModel):
    """Authoritative agent relationship from system records."""
    predecessor_id: str
    successor_id: str
    authority_domain: str


class EvidenceProvider(ABC):
    """Strictly Read-Only Boundary for Ground Truth Evidence."""

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
    def get_authority_binding(self, tenant_id: str, obligation_id: str) -> Optional[AuthorityBinding]:
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

    def get_authority_binding(self, tenant_id: str, obligation_id: str) -> Optional[AuthorityBinding]:
        if not self.db:
            return None
        doc_ref = (
            self.db.collection("tenants")
            .document(tenant_id)
            .collection("promise_ledger")
            .document(obligation_id)
        )
        snap = doc_ref.get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        return AuthorityBinding(
            predecessor_id=data.get("predecessor_id", ""),
            successor_id=data.get("successor_id", ""),
            authority_domain=tenant_id
        )
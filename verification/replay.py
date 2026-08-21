"""
Continuum: Replay Protection Guard
File: verification/replay.py
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional

try:
    from google.cloud import firestore
except ImportError:
    firestore = None


class ReplayGuard(ABC):
    """Abstract interface for atomic single-use nonce consumption."""

    @abstractmethod
    def consume_nonce(self, tenant_id: str, nonce: str, ttl_seconds: int) -> bool:
        """
        Atomically attempts to consume a nonce.
        Returns True if successfully consumed (fresh request).
        Returns False if the nonce was already used (replay attack).
        """
        pass


class FirestoreReplayGuard(ReplayGuard):
    """Production ReplayGuard using Firestore atomic creation."""

    def __init__(self, firestore_db_client: Optional[Any] = None):
        if firestore_db_client is None and firestore is not None:
            self.db = firestore.Client()
        else:
            self.db = firestore_db_client

    def consume_nonce(self, tenant_id: str, nonce: str, ttl_seconds: int) -> bool:
        if not self.db:
            return True  # Fallback for mock environments

        doc_ref = (
            self.db.collection("tenants")
            .document(tenant_id)
            .collection("used_nonces")
            .document(nonce)
        )

        try:
            # Atomic create: fails if document already exists
            doc_ref.create({
                "consumed_at": datetime.now(timezone.utc).isoformat(),
                "ttl_seconds": ttl_seconds
            })
            return True
        except Exception:
            return False  # Document exists or transaction failed -> Replay detected
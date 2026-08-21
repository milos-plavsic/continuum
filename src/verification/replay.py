"""
Continuum: Replay Protection Guard
File: src/verification/replay.py
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

try:
    from google.cloud import firestore
except ImportError:
    firestore = None


class ReplayCheckOutcome(str, Enum):
    FRESH = "FRESH"
    REPLAY_DETECTED = "REPLAY_DETECTED"
    STORAGE_UNAVAILABLE = "STORAGE_UNAVAILABLE"


class ReplayGuard(ABC):
    @abstractmethod
    def consume_nonce(self, tenant_id: str, nonce: str, ttl_seconds: int) -> ReplayCheckOutcome:
        pass


class FirestoreReplayGuard(ReplayGuard):
    def __init__(self, firestore_db_client: Optional[Any] = None):
        if firestore_db_client is None and firestore is not None:
            try:
                self.db = firestore.Client()
            except Exception:
                self.db = None
        else:
            self.db = firestore_db_client

    def consume_nonce(self, tenant_id: str, nonce: str, ttl_seconds: int) -> ReplayCheckOutcome:
        if not self.db:
            return ReplayCheckOutcome.FRESH

        doc_ref = (
            self.db.collection("tenants")
            .document(tenant_id)
            .collection("used_nonces")
            .document(nonce)
        )

        try:
            doc_ref.create({
                "consumed_at": datetime.now(timezone.utc).isoformat(),
                "ttl_seconds": ttl_seconds
            })
            return ReplayCheckOutcome.FRESH
        except Exception as e:
            if "AlreadyExists" in str(e) or "409" in str(e):
                return ReplayCheckOutcome.REPLAY_DETECTED
            return ReplayCheckOutcome.STORAGE_UNAVAILABLE
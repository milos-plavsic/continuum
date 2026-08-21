"""
Continuum: Verification Schemas & Canonicalization
File: verification/schemas.py
"""

from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    QUARANTINED = "QUARANTINED"


class VerificationRequest(BaseModel):
    """Execution request payload evaluated against ground-truth evidence."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    obligation_id: str
    tenant_id: str
    executor_id: str
    predecessor_id: str
    successor_id: str
    target_effect_type: str
    nonce: str
    issued_at: str
    ttl_seconds: int = 300


class VerificationResult(BaseModel):
    """Canonical verification output payload with immutable digest binding."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    status: VerificationStatus
    obligation_id: str
    tenant_id: str
    verifier_id: str
    predecessor_id: str
    successor_id: str
    predecessor_fenced: bool
    execution_count: int
    telemetry_verified: bool
    nonce: str
    timestamp: str
    reasoning: str
    digest: Optional[str] = None

    def canonical_bytes(self) -> bytes:
        """
        Continuum Contract 1.0 Canonicalization Rule:
        Serializes schema fields with lexicographically sorted keys and compact
        separators (',', ':') excluding the digest field itself.
        """
        data = self.model_dump(exclude={"digest"}, mode="json")
        canonical_json = json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False
        )
        return canonical_json.encode("utf-8")

    def compute_digest(self) -> str:
        """Computes SHA-256 digest over Contract 1.0 canonical bytes."""
        return hashlib.sha256(self.canonical_bytes()).hexdigest()
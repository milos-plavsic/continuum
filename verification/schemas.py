"""
Continuum: Independent Verification & Evidence-Chain Evaluation
File: verification/schemas.py

Pydantic v2 data models for zero-trust evidence digests, fencing records,
and three-valued continuity attestations.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict


class VerificationVerdict(str, Enum):
    """Explicit three-valued verification outcome enum."""
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"


class EvidenceDigest(BaseModel):
    """Cryptographic payload digest recomputed from raw event logs."""
    model_config = ConfigDict(extra="forbid")

    digest_hash: str = Field(..., description="SHA-256 hash of canonicalized payload")
    algorithm: str = Field("sha256", description="Hash algorithm used for verification")
    canonical_keys: List[str] = Field(..., description="Sorted keys included in canonicalization")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ContinuityAttestation(BaseModel):
    """
    Independent Evidence-Chain Attestation proving safe agent succession,
    zero-knowledge memory quarantine, and at-most-once execution.
    """
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    attestation_id: str = Field(..., description="Unique UUID4 identifier for this verification record")
    obligation_id: str = Field(..., description="Target obligation tracking ID from the Promise Ledger")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    verdict: VerificationVerdict = Field(..., description="VERIFIED | FAILED | INCONCLUSIVE")

    predecessor_id: str = Field("procurement-agent-v17", description="ID of quarantined predecessor")
    successor_id: str = Field("procurement-agent-v18", description="ID of clean successor agent")
    
    predecessor_fenced: bool = Field(..., description="True if predecessor tokens are verified REVOKED")
    at_most_once_verified: bool = Field(..., description="True if side effect execution count == 1")
    
    computed_digest: EvidenceDigest = Field(..., description="Recomputed digest object")
    
    trace_id: str = Field(..., description="OpenTelemetry Trace ID for cross-cloud verification")
    span_id: str = Field(..., description="OpenTelemetry Span ID recording the attestation event")

    def to_firestore_dict(self) -> Dict[str, Any]:
        """Serializes attestation for Firestore storage."""
        data = self.model_dump(mode="json")
        data["timestamp"] = self.timestamp.isoformat()
        return data
    
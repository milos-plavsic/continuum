"""
Continuum: Verification Schemas & Canonicalization
File: src/verification/schemas.py
"""

from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    QUARANTINED = "QUARANTINED"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"


class VerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    obligation_id: str
    tenant_id: str
    executor_id: str
    predecessor_id: str
    successor_id: str
    target_effect_type: str
    nonce: str
    issued_at: datetime
    ttl_seconds: int = Field(default=300, gt=0, le=86400)

    @field_validator("issued_at")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)


class VerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

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
    digest: str

    def canonical_bytes(self) -> bytes:
        data = self.model_dump(exclude={"digest"}, mode="json")
        canonical_json = json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False
        )
        return canonical_json.encode("utf-8")

    @classmethod
    def create(
        cls,
        status: VerificationStatus,
        obligation_id: str,
        tenant_id: str,
        verifier_id: str,
        predecessor_id: str,
        successor_id: str,
        predecessor_fenced: bool,
        execution_count: int,
        telemetry_verified: bool,
        nonce: str,
        timestamp: str,
        reasoning: str,
    ) -> "VerificationResult":
        payload = {
            "status": status.value if isinstance(status, Enum) else status,
            "obligation_id": obligation_id,
            "tenant_id": tenant_id,
            "verifier_id": verifier_id,
            "predecessor_id": predecessor_id,
            "successor_id": successor_id,
            "predecessor_fenced": predecessor_fenced,
            "execution_count": execution_count,
            "telemetry_verified": telemetry_verified,
            "nonce": nonce,
            "timestamp": timestamp,
            "reasoning": reasoning,
        }
        data_to_hash = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        digest_hash = hashlib.sha256(data_to_hash).hexdigest()
        
        return cls(
            status=status,
            obligation_id=obligation_id,
            tenant_id=tenant_id,
            verifier_id=verifier_id,
            predecessor_id=predecessor_id,
            successor_id=successor_id,
            predecessor_fenced=predecessor_fenced,
            execution_count=execution_count,
            telemetry_verified=telemetry_verified,
            nonce=nonce,
            timestamp=timestamp,
            reasoning=reasoning,
            digest=digest_hash
        )
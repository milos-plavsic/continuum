from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

from .canonicalization import canonical_json_text, canonical_sha256


def canonical(value: Any) -> str:
    """Compatibility name for the single RFC 8785 canonicalization boundary."""
    return canonical_json_text(value)


def digest(value: Any) -> str:
    return canonical_sha256(value)


class AgentStatus(StrEnum):
    REGISTERED = "REGISTERED"
    ACTIVE = "ACTIVE"
    QUARANTINED = "QUARANTINED"
    DRAINING = "DRAINING"
    RETIRED = "RETIRED"


class ObligationStatus(StrEnum):
    OPEN = "OPEN"
    AT_RISK = "AT_RISK"
    TRANSFERRING = "TRANSFERRING"
    EXECUTING = "EXECUTING"
    DISCHARGED = "DISCHARGED"


@dataclass(frozen=True)
class AgentVersion:
    agent_id: str
    version: str
    tenant_id: str
    status: AgentStatus
    epoch: int
    artifact_digest: str
    service_identity: str
    capabilities: tuple[str, ...]
    memory_scopes: tuple[str, ...]
    predecessor_version: str | None = None


@dataclass
class Obligation:
    obligation_id: str
    tenant_id: str
    owner_version: str
    revision: int
    required_evidence: tuple[str, ...]
    status: ObligationStatus = ObligationStatus.OPEN


@dataclass(frozen=True)
class Event:
    event_id: str
    event_type: str
    aggregate_id: str
    aggregate_version: int
    occurred_at: str
    actor: str
    correlation_id: str
    causation_id: str | None
    payload: dict[str, Any]
    schema_version: int = 1
    payload_hash: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload_hash", digest(self.payload))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def valid(self) -> bool:
        return self.payload_hash == digest(self.payload)


@dataclass(frozen=True)
class PolicyDecision:
    decision_id: str
    outcome: str
    reason_codes: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    policy_version: str = "compromise-succession/1"


@dataclass(frozen=True)
class TransferManifest:
    succession_id: str
    predecessor_version: str
    successor_version: str
    source_epoch: int
    target_epoch: int
    obligations: tuple[tuple[str, int], ...]
    memory_grants: tuple[str, ...]
    excluded_memory: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    decision_id: str
    manifest_hash: str = field(init=False)

    def __post_init__(self) -> None:
        values = {
            "succession_id": self.succession_id,
            "predecessor_version": self.predecessor_version,
            "successor_version": self.successor_version,
            "source_epoch": self.source_epoch,
            "target_epoch": self.target_epoch,
            "obligations": self.obligations,
            "memory_grants": self.memory_grants,
            "excluded_memory": self.excluded_memory,
            "evidence_ids": self.evidence_ids,
            "decision_id": self.decision_id,
        }
        object.__setattr__(self, "manifest_hash", digest(values))


class Denied(RuntimeError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)

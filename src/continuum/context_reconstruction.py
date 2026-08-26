"""Minimum-authorized context reconstruction for a successor handoff."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from .models import digest


@dataclass(frozen=True)
class ContextItem:
    item_id: str
    scope: str
    purpose: str
    value_digest: str
    evidence_ref: str
    classification: str = "AUTHORIZED_FACT"
    trusted: bool = True
    transferable: bool = True
    revoked: bool = False
    expires_at: str | None = None


@dataclass(frozen=True)
class ContextDecision:
    item_id: str
    value_digest: str
    evidence_ref: str
    included: bool
    reason_code: str


@dataclass(frozen=True)
class ReconstructionReceipt:
    succession_id: str
    successor_principal: str
    purpose: str
    allowed_scopes: tuple[str, ...]
    decisions: tuple[ContextDecision, ...]
    receipt_digest: str

    @property
    def included_item_ids(self) -> tuple[str, ...]:
        return tuple(item.item_id for item in self.decisions if item.included)

    @property
    def excluded_item_ids(self) -> tuple[str, ...]:
        return tuple(item.item_id for item in self.decisions if not item.included)

    def to_dict(self) -> dict[str, Any]:
        return {
            "succession_id": self.succession_id,
            "successor_principal": self.successor_principal,
            "purpose": self.purpose,
            "allowed_scopes": list(self.allowed_scopes),
            "decisions": [asdict(item) for item in self.decisions],
            "included_item_ids": list(self.included_item_ids),
            "excluded_item_ids": list(self.excluded_item_ids),
            "receipt_digest": self.receipt_digest,
        }


def reconstruct_context(*, succession_id: str, successor_principal: str,
                        purpose: str, allowed_scopes: Iterable[str],
                        items: Iterable[ContextItem], now: datetime | None = None
                        ) -> ReconstructionReceipt:
    if not succession_id or not successor_principal or not purpose:
        raise ValueError("RECONSTRUCTION_IDENTITY_INVALID")
    instant = now or datetime.now(timezone.utc)
    scopes = tuple(sorted(set(allowed_scopes)))
    seen: set[str] = set()
    decisions: list[ContextDecision] = []
    for item in sorted(items, key=lambda value: value.item_id):
        if item.item_id in seen:
            raise ValueError("CONTEXT_ITEM_DUPLICATE")
        seen.add(item.item_id)
        reason = _exclusion_reason(item, purpose=purpose, scopes=scopes, now=instant)
        decisions.append(ContextDecision(
            item_id=item.item_id,
            value_digest=item.value_digest,
            evidence_ref=item.evidence_ref,
            included=reason is None,
            reason_code="AUTHORIZED_MINIMUM" if reason is None else reason,
        ))
    body = {
        "succession_id": succession_id,
        "successor_principal": successor_principal,
        "purpose": purpose,
        "allowed_scopes": scopes,
        "decisions": [asdict(item) for item in decisions],
    }
    return ReconstructionReceipt(succession_id, successor_principal, purpose, scopes,
                                 tuple(decisions), digest(body))


def _exclusion_reason(item: ContextItem, *, purpose: str, scopes: tuple[str, ...],
                      now: datetime) -> str | None:
    if item.classification in {"SECRET", "RAW_UNTRUSTED", "MODEL_INFERENCE"}:
        return f"CLASS_{item.classification}_EXCLUDED"
    if item.revoked:
        return "REVOKED"
    if not item.trusted:
        return "UNTRUSTED"
    if not item.transferable:
        return "NON_TRANSFERABLE"
    if item.scope not in scopes:
        return "SCOPE_NOT_GRANTED"
    if item.purpose != purpose:
        return "PURPOSE_MISMATCH"
    if item.expires_at is not None:
        expiry = datetime.fromisoformat(item.expires_at.replace("Z", "+00:00"))
        if expiry <= now:
            return "STALE"
    if not item.value_digest or not item.evidence_ref:
        return "PROVENANCE_INCOMPLETE"
    return None

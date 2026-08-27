"""Formal, policy-versioned evidence descriptors and deterministic trust receipts."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import re
from typing import Any, Iterable

from .models import digest


EVIDENCE_PROFILE = "continuum/evidence-descriptor/1"
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")


def _utc(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("EVIDENCE_TIME_UTC_Z_REQUIRED")
    return datetime.fromisoformat(value[:-1] + "+00:00")


@dataclass(frozen=True)
class EvidenceAuthentication:
    kind: str
    reference: str


@dataclass(frozen=True)
class EvidenceDescriptor:
    evidence_id: str
    evidence_type: str
    subject: str
    issuer: str
    source_authority: str
    observed_at: str
    expires_at: str
    payload_digest: str
    authentication: EvidenceAuthentication
    trust_policy: str
    profile: str = EVIDENCE_PROFILE

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceRecord:
    descriptor: EvidenceDescriptor
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"descriptor": self.descriptor.to_dict(), "payload": self.payload}


def evidence_record_from_dict(value: dict[str, Any]) -> EvidenceRecord:
    """Parse an untrusted descriptor with an exact, closed schema."""
    if not isinstance(value, dict) or set(value) != {"descriptor", "payload"}:
        raise ValueError("EVIDENCE_RECORD_SCHEMA_INVALID")
    descriptor = value["descriptor"]
    payload = value["payload"]
    fields = {
        "evidence_id", "evidence_type", "subject", "issuer", "source_authority",
        "observed_at", "expires_at", "payload_digest", "authentication",
        "trust_policy", "profile",
    }
    if not isinstance(descriptor, dict) or set(descriptor) != fields or not isinstance(payload, dict):
        raise ValueError("EVIDENCE_RECORD_SCHEMA_INVALID")
    authentication = descriptor["authentication"]
    if not isinstance(authentication, dict) or set(authentication) != {"kind", "reference"}:
        raise ValueError("EVIDENCE_RECORD_SCHEMA_INVALID")
    if any(not isinstance(descriptor[key], str) for key in fields - {"authentication"}) or any(
            not isinstance(authentication[key], str) for key in authentication):
        raise ValueError("EVIDENCE_RECORD_SCHEMA_INVALID")
    return EvidenceRecord(EvidenceDescriptor(
        evidence_id=descriptor["evidence_id"], evidence_type=descriptor["evidence_type"],
        subject=descriptor["subject"], issuer=descriptor["issuer"],
        source_authority=descriptor["source_authority"], observed_at=descriptor["observed_at"],
        expires_at=descriptor["expires_at"], payload_digest=descriptor["payload_digest"],
        authentication=EvidenceAuthentication(**authentication),
        trust_policy=descriptor["trust_policy"], profile=descriptor["profile"],
    ), payload)


@dataclass(frozen=True)
class EvidenceRule:
    evidence_type: str
    issuers: tuple[str, ...]
    source_authorities: tuple[str, ...]
    authentication_kinds: tuple[str, ...]
    maximum_age_seconds: int


@dataclass(frozen=True)
class EvidenceTrustPolicy:
    policy_id: str
    rules: tuple[EvidenceRule, ...]
    maximum_future_skew_seconds: int = 30


@dataclass(frozen=True)
class EvidenceAssessment:
    evidence_id: str
    evidence_type: str
    trusted: bool
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceValidationReceipt:
    policy_id: str
    assessed_at: str
    assessments: tuple[EvidenceAssessment, ...]
    records_digest: str
    receipt_digest: str

    @property
    def trusted_ids(self) -> tuple[str, ...]:
        return tuple(item.evidence_id for item in self.assessments if item.trusted)

    @property
    def valid(self) -> bool:
        return bool(self.assessments) and all(item.trusted for item in self.assessments)

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "assessed_at": self.assessed_at,
            "assessments": [asdict(item) for item in self.assessments],
            "trusted_ids": list(self.trusted_ids),
            "valid": self.valid,
            "records_digest": self.records_digest,
            "receipt_digest": self.receipt_digest,
        }


def describe_evidence(*, evidence_id: str, evidence_type: str, subject: str,
                      issuer: str, source_authority: str, observed_at: str,
                      expires_at: str, payload: dict[str, Any],
                      authentication_kind: str, authentication_reference: str,
                      trust_policy: str) -> EvidenceRecord:
    """Create a descriptor whose digest binds the exact canonical payload."""
    return EvidenceRecord(EvidenceDescriptor(
        evidence_id=evidence_id,
        evidence_type=evidence_type,
        subject=subject,
        issuer=issuer,
        source_authority=source_authority,
        observed_at=observed_at,
        expires_at=expires_at,
        payload_digest=f"sha256:{digest(payload)}",
        authentication=EvidenceAuthentication(authentication_kind, authentication_reference),
        trust_policy=trust_policy,
    ), payload)


def assess_evidence(records: Iterable[EvidenceRecord], policy: EvidenceTrustPolicy, *,
                    now: str, expected_subject: str | None = None) -> EvidenceValidationReceipt:
    """Evaluate trust, provenance, freshness and payload integrity without I/O."""
    instant = _utc(now)
    if not policy.policy_id or policy.maximum_future_skew_seconds < 0:
        raise ValueError("EVIDENCE_TRUST_POLICY_INVALID")
    rules = {rule.evidence_type: rule for rule in policy.rules}
    if len(rules) != len(policy.rules) or any(
            not rule.evidence_type or not rule.issuers or not rule.source_authorities
            or not rule.authentication_kinds or rule.maximum_age_seconds < 0
            for rule in policy.rules):
        raise ValueError("EVIDENCE_TRUST_POLICY_INVALID")
    ordered = sorted(records, key=lambda item: item.descriptor.evidence_id)
    seen: set[str] = set()
    assessments: list[EvidenceAssessment] = []
    for record in ordered:
        descriptor = record.descriptor
        reasons: list[str] = []
        if not descriptor.evidence_id or descriptor.evidence_id in seen:
            reasons.append("EVIDENCE_ID_INVALID_OR_DUPLICATE")
        seen.add(descriptor.evidence_id)
        if descriptor.profile != EVIDENCE_PROFILE:
            reasons.append("EVIDENCE_PROFILE_UNSUPPORTED")
        rule = rules.get(descriptor.evidence_type)
        if rule is None:
            reasons.append("EVIDENCE_TYPE_UNTRUSTED")
        if descriptor.trust_policy != policy.policy_id:
            reasons.append("EVIDENCE_POLICY_MISMATCH")
        if expected_subject is not None and descriptor.subject != expected_subject:
            reasons.append("EVIDENCE_SUBJECT_MISMATCH")
        if not _SHA256.fullmatch(descriptor.payload_digest):
            reasons.append("EVIDENCE_DIGEST_MALFORMED")
        elif descriptor.payload_digest != f"sha256:{digest(record.payload)}":
            reasons.append("EVIDENCE_PAYLOAD_DIGEST_MISMATCH")
        authentication = descriptor.authentication
        if not authentication.kind or not authentication.reference:
            reasons.append("EVIDENCE_AUTHENTICATION_MISSING")
        if rule is not None:
            if descriptor.issuer not in rule.issuers:
                reasons.append("EVIDENCE_ISSUER_UNTRUSTED")
            if descriptor.source_authority not in rule.source_authorities:
                reasons.append("EVIDENCE_SOURCE_AUTHORITY_UNTRUSTED")
            if authentication.kind not in rule.authentication_kinds:
                reasons.append("EVIDENCE_AUTHENTICATION_UNTRUSTED")
        try:
            observed = _utc(descriptor.observed_at)
            expires = _utc(descriptor.expires_at)
            if expires <= observed:
                reasons.append("EVIDENCE_EXPIRY_INVALID")
            if observed > instant + timedelta(seconds=policy.maximum_future_skew_seconds):
                reasons.append("EVIDENCE_FROM_FUTURE")
            if expires <= instant:
                reasons.append("EVIDENCE_EXPIRED")
            if rule is not None and instant - observed > timedelta(seconds=rule.maximum_age_seconds):
                reasons.append("EVIDENCE_TOO_OLD")
        except (TypeError, ValueError):
            reasons.append("EVIDENCE_TIME_INVALID")
        assessments.append(EvidenceAssessment(
            descriptor.evidence_id, descriptor.evidence_type, not reasons,
            tuple(dict.fromkeys(reasons)) if reasons else ("TRUSTED",),
        ))
    record_body = [item.to_dict() for item in ordered]
    records_digest = digest(record_body)
    assessment_body = [asdict(item) for item in assessments]
    receipt_digest = digest({
        "policy_id": policy.policy_id, "assessed_at": now,
        "records_digest": records_digest, "assessments": assessment_body,
    })
    return EvidenceValidationReceipt(
        policy.policy_id, now, tuple(assessments), records_digest, receipt_digest)

"""Deterministic incident assessment; models receive policy output, never policy prose."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from .evidence import (EvidenceRecord, EvidenceRule, EvidenceTrustPolicy,
                       assess_evidence, describe_evidence, evidence_record_from_dict)
from .models import Denied, digest


INCIDENT_POLICY_ID = "continuum/incident-policy/1"
LIFECYCLE_TRUST_POLICY_ID = "continuum/lifecycle-evidence-trust/1"
REQUIRED_COMPROMISE_SIGNALS = (
    "action.denied", "document.injection_detected", "expectation.missed",
)
REVIEW = "request_operator_review"
SUCCESSION = "initiate_governed_succession"


@dataclass(frozen=True)
class IncidentAssessmentReceipt:
    policy_id: str
    evidence_receipt_digest: str
    evidence_valid: bool
    signal_types: tuple[str, ...]
    verdict: str
    reason_codes: tuple[str, ...]
    allowed_remediations: tuple[str, ...]
    receipt_digest: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def lifecycle_trust_policy() -> EvidenceTrustPolicy:
    issuers = {
        "document.injection_detected": ("document-ingress", "procurement-succession-v1"),
        "action.denied": ("action-gateway", "procurement-succession-v1"),
        "expectation.missed": ("negative-space-sentinel", "procurement-succession-v1"),
    }
    return EvidenceTrustPolicy(
        LIFECYCLE_TRUST_POLICY_ID,
        tuple(EvidenceRule(signal, issuers[signal], ("CONTINUUM_EVENT_LEDGER",),
                           ("CONTENT_DIGEST",), 900)
              for signal in REQUIRED_COMPROMISE_SIGNALS),
    )


def describe_lifecycle_events(events: Iterable[dict[str, Any]], *, subject: str,
                              assessed_at: str) -> tuple[EvidenceRecord, ...]:
    instant = datetime.fromisoformat(assessed_at.replace("Z", "+00:00"))
    expires = (instant + timedelta(minutes=15)).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    records = []
    for position, event in enumerate(events):
        event_type = event.get("event_type", event.get("type"))
        event_id = event.get("event_id") or digest({"position": position, "event": event})
        source = str(event.get("source", "unknown"))
        records.append(describe_evidence(
            evidence_id=str(event_id), evidence_type=str(event_type), subject=subject,
            issuer=source, source_authority="CONTINUUM_EVENT_LEDGER",
            observed_at=assessed_at, expires_at=expires, payload=event,
            authentication_kind="CONTENT_DIGEST",
            authentication_reference=f"event:{event_id}",
            trust_policy=LIFECYCLE_TRUST_POLICY_ID,
        ))
    return tuple(records)


def assess_incident(records: Iterable[EvidenceRecord], *, assessed_at: str,
                    subject: str) -> tuple[IncidentAssessmentReceipt, dict[str, Any]]:
    material = tuple(records)
    policy = lifecycle_trust_policy()
    evidence_receipt = assess_evidence(material, policy, now=assessed_at,
                                       expected_subject=subject)
    trusted_types = tuple(sorted(item.descriptor.evidence_type for item in material
                                 if item.descriptor.evidence_id in evidence_receipt.trusted_ids))
    required = set(REQUIRED_COMPROMISE_SIGNALS)
    observed = set(trusted_types)
    compromised = evidence_receipt.valid and required.issubset(observed)
    verdict = "CORRELATED_COMPROMISE" if compromised else "INSUFFICIENT_TRUSTED_EVIDENCE"
    reasons = ("CORRELATED_COMPROMISE_SIGNALS",) if compromised else (
        "EVIDENCE_UNTRUSTED" if not evidence_receipt.valid else "REQUIRED_SIGNALS_MISSING",
    )
    allowed = (SUCCESSION, REVIEW) if compromised else (REVIEW,)
    body = {
        "policy_id": INCIDENT_POLICY_ID,
        "evidence_receipt_digest": evidence_receipt.receipt_digest,
        "evidence_valid": evidence_receipt.valid,
        "signal_types": trusted_types,
        "verdict": verdict,
        "reason_codes": reasons,
        "allowed_remediations": allowed,
    }
    receipt = IncidentAssessmentReceipt(
        INCIDENT_POLICY_ID, evidence_receipt.receipt_digest, evidence_receipt.valid, trusted_types,
        verdict, reasons, allowed, digest(body),
    )
    return receipt, evidence_receipt.to_dict()


def validate_incident_receipt(receipt: dict[str, Any]) -> IncidentAssessmentReceipt:
    required = {"policy_id", "evidence_receipt_digest", "evidence_valid", "signal_types", "verdict",
                "reason_codes", "allowed_remediations", "receipt_digest"}
    if set(receipt) != required:
        raise Denied("INCIDENT_ASSESSMENT_SCHEMA_INVALID")
    body = {key: receipt[key] for key in required - {"receipt_digest"}}
    if receipt.get("policy_id") != INCIDENT_POLICY_ID or digest(body) != receipt.get("receipt_digest"):
        raise Denied("INCIDENT_ASSESSMENT_DIGEST_INVALID")
    signals = receipt.get("signal_types")
    reasons = receipt.get("reason_codes")
    allowed = receipt.get("allowed_remediations")
    if (not isinstance(signals, (list, tuple)) or not isinstance(reasons, (list, tuple))
            or not isinstance(allowed, (list, tuple))):
        raise Denied("INCIDENT_ASSESSMENT_SCHEMA_INVALID")
    if (not isinstance(receipt.get("evidence_valid"), bool)
            or not isinstance(receipt.get("evidence_receipt_digest"), str)
            or len(receipt["evidence_receipt_digest"]) != 64):
        raise Denied("INCIDENT_ASSESSMENT_SCHEMA_INVALID")
    compromised = receipt["evidence_valid"] and set(REQUIRED_COMPROMISE_SIGNALS).issubset(signals)
    expected = (SUCCESSION, REVIEW) if compromised else (REVIEW,)
    expected_verdict = "CORRELATED_COMPROMISE" if compromised else "INSUFFICIENT_TRUSTED_EVIDENCE"
    expected_reasons = (("CORRELATED_COMPROMISE_SIGNALS",) if compromised else
                        (("EVIDENCE_UNTRUSTED",) if not receipt["evidence_valid"] else
                         ("REQUIRED_SIGNALS_MISSING",)))
    if (tuple(allowed) != expected or receipt.get("verdict") != expected_verdict
            or tuple(reasons) != expected_reasons):
        raise Denied("INCIDENT_ASSESSMENT_POLICY_MISMATCH")
    return IncidentAssessmentReceipt(
        str(receipt["policy_id"]), str(receipt["evidence_receipt_digest"]),
        receipt["evidence_valid"],
        tuple(signals), str(receipt["verdict"]), tuple(reasons), tuple(allowed),
        str(receipt["receipt_digest"]),
    )


def admit_model_remediation(proposal: dict[str, Any], receipt: dict[str, Any]) -> str:
    assessment = validate_incident_receipt(receipt)
    actions = proposal.get("proposed_actions")
    if not isinstance(actions, list) or len(actions) != 1:
        raise Denied("REMEDIATION_PLAN_SCHEMA_INVALID")
    selected = actions[0]
    if selected not in assessment.allowed_remediations:
        raise Denied("REMEDIATION_NOT_ALLOWED")
    return str(selected)


def verify_incident_evidence_chain(*, records: list[dict[str, Any]],
                                   evidence_receipt: dict[str, Any],
                                   incident_receipt: dict[str, Any],
                                   subject: str) -> None:
    """Recompute both receipts from exported evidence; accept no self-asserted trust."""
    if not isinstance(evidence_receipt, dict) or not isinstance(records, list):
        raise Denied("INCIDENT_EVIDENCE_CHAIN_SCHEMA_INVALID")
    try:
        parsed = tuple(evidence_record_from_dict(item) for item in records)
        assessed_at = evidence_receipt["assessed_at"]
        recomputed = assess_evidence(parsed, lifecycle_trust_policy(), now=assessed_at,
                                     expected_subject=subject)
    except (KeyError, TypeError, ValueError) as error:
        raise Denied("INCIDENT_EVIDENCE_CHAIN_SCHEMA_INVALID") from error
    if recomputed.to_dict() != evidence_receipt:
        raise Denied("EVIDENCE_VALIDATION_RECEIPT_MISMATCH")
    assessment, validation = assess_incident(parsed, assessed_at=assessed_at, subject=subject)
    if validation != evidence_receipt or assessment.to_dict() != incident_receipt:
        raise Denied("INCIDENT_EVIDENCE_CHAIN_MISMATCH")
    validate_incident_receipt(incident_receipt)

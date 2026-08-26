"""Bounded, evidence-backed successor discovery and model-choice admission."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from .models import AgentStatus, Denied, digest


@dataclass(frozen=True)
class SuccessorCandidate:
    principal_id: str
    version: str
    tenant_id: str
    status: AgentStatus
    artifact_digest: str
    service_identity: str
    capabilities: tuple[str, ...]
    memory_scopes: tuple[str, ...]
    authority_domains: tuple[str, ...]
    jurisdictions: tuple[str, ...]
    contract_profiles: tuple[str, ...]
    health: str
    trust_score: int
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.principal_id or not self.version or not self.artifact_digest:
            raise ValueError("CANDIDATE_IDENTITY_INVALID")
        if not 0 <= self.trust_score <= 100:
            raise ValueError("CANDIDATE_TRUST_SCORE_INVALID")
        if not self.evidence_refs:
            raise ValueError("CANDIDATE_EVIDENCE_REQUIRED")


@dataclass(frozen=True)
class SuccessionRequirements:
    tenant_id: str
    predecessor_principal: str
    capability: str
    memory_scope: str
    authority_domain: str
    jurisdiction: str
    contract_profile: str
    minimum_trust_score: int = 80


@dataclass(frozen=True)
class CandidateAssessment:
    candidate_id: str
    version: str
    eligible: bool
    reason_codes: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    trust_score: int


@dataclass(frozen=True)
class AssessmentReceipt:
    requirements_digest: str
    candidates_digest: str
    assessments: tuple[CandidateAssessment, ...]
    receipt_digest: str

    @property
    def eligible_ids(self) -> tuple[str, ...]:
        return tuple(item.candidate_id for item in self.assessments if item.eligible)

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirements_digest": self.requirements_digest,
            "candidates_digest": self.candidates_digest,
            "assessments": [{
                "candidate_id": item.candidate_id,
                "version": item.version,
                "eligible": item.eligible,
                "reason_codes": list(item.reason_codes),
                "evidence_refs": list(item.evidence_refs),
                "trust_score": item.trust_score,
            } for item in self.assessments],
            "eligible_ids": list(self.eligible_ids),
            "receipt_digest": self.receipt_digest,
        }


def assess_candidates(candidates: Iterable[SuccessorCandidate],
                      requirements: SuccessionRequirements) -> AssessmentReceipt:
    """Evaluate every candidate deterministically before any model sees it."""
    ordered = sorted(candidates, key=lambda item: item.principal_id)
    seen: set[str] = set()
    assessments: list[CandidateAssessment] = []
    for candidate in ordered:
        if candidate.principal_id in seen:
            raise ValueError("CANDIDATE_PRINCIPAL_DUPLICATE")
        seen.add(candidate.principal_id)
        reasons: list[str] = []
        checks = (
            (candidate.principal_id == requirements.predecessor_principal, "PREDECESSOR_INELIGIBLE"),
            (candidate.tenant_id != requirements.tenant_id, "TENANT_MISMATCH"),
            (candidate.status != AgentStatus.REGISTERED, "LIFECYCLE_INELIGIBLE"),
            (candidate.health != "HEALTHY", "HEALTH_UNVERIFIED"),
            (requirements.capability not in candidate.capabilities, "CAPABILITY_MISSING"),
            (requirements.memory_scope not in candidate.memory_scopes, "MEMORY_SCOPE_MISSING"),
            (requirements.authority_domain not in candidate.authority_domains, "AUTHORITY_DOMAIN_MISMATCH"),
            (requirements.jurisdiction not in candidate.jurisdictions, "JURISDICTION_MISMATCH"),
            (requirements.contract_profile not in candidate.contract_profiles, "CONTRACT_PROFILE_UNSUPPORTED"),
            (candidate.trust_score < requirements.minimum_trust_score, "TRUST_FLOOR_NOT_MET"),
        )
        reasons.extend(code for failed, code in checks if failed)
        assessments.append(CandidateAssessment(
            candidate_id=candidate.principal_id,
            version=candidate.version,
            eligible=not reasons,
            reason_codes=tuple(reasons) if reasons else ("ELIGIBLE",),
            evidence_refs=tuple(sorted(candidate.evidence_refs)),
            trust_score=candidate.trust_score,
        ))
    requirement_body = asdict(requirements)
    candidate_body = [asdict(item) for item in ordered]
    assessment_body = [asdict(item) for item in assessments]
    requirements_digest = digest(requirement_body)
    candidates_digest = digest(candidate_body)
    return AssessmentReceipt(
        requirements_digest=requirements_digest,
        candidates_digest=candidates_digest,
        assessments=tuple(assessments),
        receipt_digest=digest({"requirements": requirements_digest,
                               "candidates": candidates_digest,
                               "assessments": assessment_body}),
    )


def model_candidate_view(candidates: Iterable[SuccessorCandidate],
                         receipt: AssessmentReceipt) -> list[dict[str, Any]]:
    """Return only eligible, bounded facts; rejected records never reach Gemini."""
    eligible = set(receipt.eligible_ids)
    return [
        {
            "candidate_id": item.principal_id,
            "version": item.version,
            "trust_score": item.trust_score,
            "capabilities": list(item.capabilities),
            "jurisdictions": list(item.jurisdictions),
            "evidence_refs": list(sorted(item.evidence_refs)),
        }
        for item in sorted(candidates, key=lambda value: value.principal_id)
        if item.principal_id in eligible
    ]


def admit_successor_choice(choice: dict[str, Any], receipt: AssessmentReceipt) -> str:
    """Validate the non-authoritative model choice against the policy receipt."""
    if set(choice) != {"selected_candidate_id", "candidate_evidence_refs", "rationale", "objective"}:
        raise Denied("SUCCESSOR_CHOICE_SCHEMA_INVALID")
    selected = choice.get("selected_candidate_id")
    citations = choice.get("candidate_evidence_refs")
    if not isinstance(selected, str) or not isinstance(citations, list) or not citations:
        raise Denied("SUCCESSOR_CHOICE_SCHEMA_INVALID")
    assessment = next((item for item in receipt.assessments
                       if item.candidate_id == selected), None)
    if assessment is None:
        raise Denied("SUCCESSOR_CHOICE_UNKNOWN")
    if not assessment.eligible:
        raise Denied("SUCCESSOR_CHOICE_INELIGIBLE")
    if not set(citations).issubset(set(assessment.evidence_refs)):
        raise Denied("SUCCESSOR_CHOICE_CITATION_INVALID")
    if not set(assessment.evidence_refs).issubset(set(citations)):
        raise Denied("SUCCESSOR_CHOICE_EVIDENCE_INCOMPLETE")
    return selected

"""Bounded, evidence-backed successor discovery and model-choice admission."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from .models import AgentStatus, Denied, digest


SUPPORT_CLAIMS: dict[str, tuple[str, ...]] = {
    "BUILD_PROVENANCE": ("build:", "image:"),
    "HEALTH_ATTESTED": ("health:",),
    "RUNTIME_IDENTITY": ("identity:",),
    "SERVICE_REVISION": ("cloud-run:",),
}


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
    """Validate complete consideration separately from selective support.

    ``evidence_manifest_refs`` proves which bounded evidence entered the model
    context. ``supporting_citations`` binds individual model claims to the
    subset that materially supports them. Neither field grants authority.
    """
    if set(choice) != {"selected_candidate_id", "evidence_manifest_refs",
                       "supporting_citations", "rationale", "objective"}:
        raise Denied("SUCCESSOR_CHOICE_SCHEMA_INVALID")
    selected = choice.get("selected_candidate_id")
    manifest = choice.get("evidence_manifest_refs")
    citations = choice.get("supporting_citations")
    if (not isinstance(selected, str) or not isinstance(manifest, list) or not manifest
            or not isinstance(citations, list) or not citations
            or not isinstance(choice.get("rationale"), str) or not choice["rationale"].strip()
            or not isinstance(choice.get("objective"), str) or not choice["objective"].strip()):
        raise Denied("SUCCESSOR_CHOICE_SCHEMA_INVALID")
    assessment = next((item for item in receipt.assessments
                       if item.candidate_id == selected), None)
    if assessment is None:
        raise Denied("SUCCESSOR_CHOICE_UNKNOWN")
    if not assessment.eligible:
        raise Denied("SUCCESSOR_CHOICE_INELIGIBLE")
    if (any(not isinstance(item, str) or not item for item in manifest)
            or len(manifest) != len(set(manifest))):
        raise Denied("SUCCESSOR_CHOICE_MANIFEST_INVALID")
    if set(manifest) != set(assessment.evidence_refs):
        raise Denied("SUCCESSOR_CHOICE_EVIDENCE_INCOMPLETE")
    cited_refs: list[str] = []
    claims: list[str] = []
    for citation in citations:
        if (not isinstance(citation, dict) or set(citation) != {"claim", "evidence_refs"}
                or not isinstance(citation.get("claim"), str)
                or citation["claim"] not in SUPPORT_CLAIMS
                or not isinstance(citation.get("evidence_refs"), list)
                or not citation["evidence_refs"]):
            raise Denied("SUCCESSOR_CHOICE_CITATION_INVALID")
        claim = citation["claim"]
        refs = citation["evidence_refs"]
        if (any(not isinstance(ref, str) or ref not in manifest for ref in refs)
                or len(refs) != len(set(refs))
                or any(not ref.startswith(SUPPORT_CLAIMS[claim]) for ref in refs)):
            raise Denied("SUCCESSOR_CHOICE_CITATION_INVALID")
        claims.append(claim)
        cited_refs.extend(refs)
    if len(claims) != len(set(claims)) or len(cited_refs) != len(set(cited_refs)):
        raise Denied("SUCCESSOR_CHOICE_CITATION_DUPLICATE")
    return selected

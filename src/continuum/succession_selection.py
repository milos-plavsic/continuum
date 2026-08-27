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
    "RECOVERY_READINESS": ("recovery:",),
    "ASSURANCE_PROFILE": ("assurance:",),
    "WARM_STATE": ("warm-state:",),
}


@dataclass(frozen=True)
class SelectionObjective:
    objective_id: str
    statement: str
    tradeoff_dimensions: tuple[str, ...]
    required_support_claims: tuple[str, ...]

    def __post_init__(self) -> None:
        if (not self.objective_id or not self.statement or len(self.tradeoff_dimensions) < 2 or
                len(set(self.tradeoff_dimensions)) != len(self.tradeoff_dimensions) or
                not self.required_support_claims or any(
                    claim not in SUPPORT_CLAIMS for claim in self.required_support_claims)):
            raise ValueError("SELECTION_OBJECTIVE_INVALID")

    def to_dict(self) -> dict[str, Any]:
        body = asdict(self)
        return {**body, "tradeoff_dimensions": list(self.tradeoff_dimensions),
                "required_support_claims": list(self.required_support_claims),
                "objective_digest": digest(body)}


def canonical_selection_objective() -> SelectionObjective:
    return SelectionObjective(
        objective_id="eu-supplier-continuity-balanced/1",
        statement=("Choose the eligible successor that best balances rapid recovery of the "
                   "EUR 250,000 obligation with independently evidenced assurance; do not "
                   "reduce the decision to a single trust score."),
        tradeoff_dimensions=("recovery_time_seconds", "assurance_level", "warm_state",
                             "trust_score"),
        required_support_claims=("RECOVERY_READINESS", "ASSURANCE_PROFILE"),
    )


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
    recovery_time_seconds: int = 60
    assurance_level: str = "STANDARD"
    warm_state: str = "COLD"

    def __post_init__(self) -> None:
        if not self.principal_id or not self.version or not self.artifact_digest:
            raise ValueError("CANDIDATE_IDENTITY_INVALID")
        if not 0 <= self.trust_score <= 100:
            raise ValueError("CANDIDATE_TRUST_SCORE_INVALID")
        if not self.evidence_refs:
            raise ValueError("CANDIDATE_EVIDENCE_REQUIRED")
        if (self.recovery_time_seconds <= 0 or self.assurance_level not in {
                "STANDARD", "HIGH", "VERY_HIGH"} or self.warm_state not in {"COLD", "WARM"}):
            raise ValueError("CANDIDATE_TRADEOFF_PROFILE_INVALID")


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
    recovery_time_seconds: int
    assurance_level: str
    warm_state: str


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
                "recovery_time_seconds": item.recovery_time_seconds,
                "assurance_level": item.assurance_level,
                "warm_state": item.warm_state,
            } for item in self.assessments],
            "eligible_ids": list(self.eligible_ids),
            "receipt_digest": self.receipt_digest,
        }


@dataclass(frozen=True)
class SelectionGovernancePolicy:
    """Policy for model availability, deterministic comparison and human review."""

    policy_id: str = "successor-selection-governance/1"
    production_review_amount: int = 100_000

    def __post_init__(self) -> None:
        if not self.policy_id or self.production_review_amount <= 0:
            raise ValueError("SELECTION_GOVERNANCE_POLICY_INVALID")


def govern_successor_selection(*, selected_candidate_id: str | None,
                               receipt: AssessmentReceipt,
                               model_available: bool,
                               decision_scope: str,
                               value_at_risk: dict[str, Any],
                               human_approved: bool = False,
                               policy: SelectionGovernancePolicy = SelectionGovernancePolicy()
                               ) -> dict[str, Any]:
    """Bind model choice to a deterministic baseline and explicit review boundary."""
    eligible = [item for item in receipt.assessments if item.eligible]
    if not eligible:
        raise Denied("SELECTION_GOVERNANCE_NO_ELIGIBLE_CANDIDATE")
    assurance_rank = {"STANDARD": 1, "HIGH": 2, "VERY_HIGH": 3}
    baseline = sorted(eligible, key=lambda item: (
        -assurance_rank[item.assurance_level], -item.trust_score,
        item.recovery_time_seconds, item.candidate_id))[0]
    amount = value_at_risk.get("amount")
    if (decision_scope not in {"SANDBOX_ONLY", "PRODUCTION"}
            or not isinstance(amount, int) or isinstance(amount, bool) or amount < 0):
        raise ValueError("SELECTION_GOVERNANCE_INPUT_INVALID")
    if not model_available:
        if selected_candidate_id is not None:
            raise Denied("SELECTION_GOVERNANCE_MODEL_STATE_INVALID")
        outcome, reason = "HOLD", "MODEL_UNAVAILABLE"
        selected = None
    else:
        selected = next((item for item in eligible
                         if item.candidate_id == selected_candidate_id), None)
        if selected is None:
            raise Denied("SELECTION_GOVERNANCE_CHOICE_INVALID")
        review_required = (decision_scope == "PRODUCTION"
                           and amount >= policy.production_review_amount)
        if review_required and not human_approved:
            outcome, reason = "HOLD", "HUMAN_APPROVAL_REQUIRED"
        else:
            outcome = "APPROVED"
            reason = ("HUMAN_APPROVED" if review_required
                      else "SANDBOX_AUTONOMY" if decision_scope == "SANDBOX_ONLY"
                      else "BELOW_REVIEW_THRESHOLD")
    body = {
        "policy_id": policy.policy_id,
        "assessment_receipt_digest": receipt.receipt_digest,
        "deterministic_baseline_candidate_id": baseline.candidate_id,
        "selected_candidate_id": selected_candidate_id,
        "deviates_from_baseline": (selected_candidate_id is not None
                                    and selected_candidate_id != baseline.candidate_id),
        "decision_scope": decision_scope,
        "value_at_risk": value_at_risk,
        "model_available": model_available,
        "human_approved": human_approved,
        "outcome": outcome,
        "reason_code": reason,
    }
    return {**body, "receipt_digest": digest(body)}


def validate_selection_governance_receipt(*, governance: Any,
                                          assessment: Any,
                                          successor_id: str) -> dict[str, Any]:
    """Independently recompute a selection-governance receipt.

    This deliberately accepts serialized contract data rather than internal
    dataclasses so a verifier does not have to trust the selection process that
    originally created the receipt.
    """
    required = {
        "policy_id", "assessment_receipt_digest",
        "deterministic_baseline_candidate_id", "selected_candidate_id",
        "deviates_from_baseline", "decision_scope", "value_at_risk",
        "model_available", "human_approved", "outcome", "reason_code",
        "receipt_digest",
    }
    if not isinstance(governance, dict) or set(governance) != required:
        raise Denied("SELECTION_GOVERNANCE_RECEIPT_SCHEMA_INVALID")
    if (not isinstance(assessment, dict)
            or governance["assessment_receipt_digest"] != assessment.get("receipt_digest")):
        raise Denied("SELECTION_GOVERNANCE_ASSESSMENT_MISMATCH")
    body = {key: governance[key] for key in required - {"receipt_digest"}}
    if governance["receipt_digest"] != digest(body):
        raise Denied("SELECTION_GOVERNANCE_RECEIPT_DIGEST_MISMATCH")
    eligible = [item for item in assessment.get("assessments", [])
                if isinstance(item, dict) and item.get("eligible") is True]
    assurance_rank = {"STANDARD": 1, "HIGH": 2, "VERY_HIGH": 3}
    try:
        baseline = sorted(eligible, key=lambda item: (
            -assurance_rank[item["assurance_level"]], -item["trust_score"],
            item["recovery_time_seconds"], item["candidate_id"]))[0]
    except (IndexError, KeyError, TypeError) as error:
        raise Denied("SELECTION_GOVERNANCE_BASELINE_INVALID") from error
    selected = governance["selected_candidate_id"]
    if (selected != successor_id
            or not any(item.get("candidate_id") == selected for item in eligible)):
        raise Denied("SELECTION_GOVERNANCE_SUCCESSOR_MISMATCH")
    expected_deviation = selected != baseline["candidate_id"]
    if (governance["deterministic_baseline_candidate_id"] != baseline["candidate_id"]
            or governance["deviates_from_baseline"] is not expected_deviation):
        raise Denied("SELECTION_GOVERNANCE_BASELINE_MISMATCH")
    if governance["outcome"] != "APPROVED" or governance["model_available"] is not True:
        raise Denied("SELECTION_GOVERNANCE_NOT_APPROVED")
    scope = governance["decision_scope"]
    amount = governance.get("value_at_risk", {}).get("amount")
    if (scope not in {"SANDBOX_ONLY", "PRODUCTION"}
            or not isinstance(amount, int) or isinstance(amount, bool) or amount < 0):
        raise Denied("SELECTION_GOVERNANCE_INPUT_INVALID")
    if (scope == "SANDBOX_ONLY" and governance["reason_code"] != "SANDBOX_AUTONOMY"):
        raise Denied("SELECTION_GOVERNANCE_REASON_INVALID")
    if (scope == "PRODUCTION" and governance["reason_code"] == "HUMAN_APPROVED"
            and governance["human_approved"] is not True):
        raise Denied("SELECTION_GOVERNANCE_REASON_INVALID")
    return governance


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
            recovery_time_seconds=candidate.recovery_time_seconds,
            assurance_level=candidate.assurance_level,
            warm_state=candidate.warm_state,
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
            "recovery_time_seconds": item.recovery_time_seconds,
            "assurance_level": item.assurance_level,
            "warm_state": item.warm_state,
            "capabilities": list(item.capabilities),
            "jurisdictions": list(item.jurisdictions),
            "evidence_refs": list(sorted(item.evidence_refs)),
        }
        for item in sorted(candidates, key=lambda value: value.principal_id)
        if item.principal_id in eligible
    ]


def admit_successor_choice(choice: dict[str, Any], receipt: AssessmentReceipt,
                           objective: SelectionObjective | None = None) -> str:
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
    eligible_manifest = {reference for item in receipt.assessments if item.eligible
                         for reference in item.evidence_refs}
    if set(manifest) != eligible_manifest:
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
    if objective is not None:
        if choice["objective"] != objective.objective_id:
            raise Denied("SUCCESSOR_CHOICE_OBJECTIVE_MISMATCH")
        if not set(objective.required_support_claims).issubset(claims):
            raise Denied("SUCCESSOR_CHOICE_TRADEOFF_UNSUPPORTED")
        selected_refs = set(assessment.evidence_refs)
        if not selected_refs.intersection(cited_refs):
            raise Denied("SUCCESSOR_CHOICE_SELECTED_SUPPORT_MISSING")
    return selected

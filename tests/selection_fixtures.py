"""Complete selection receipts shared by independent-verifier tests."""
from continuum.models import digest


def selection_extensions(successor: str) -> tuple[dict, dict]:
    assessments = [{
        "candidate_id": successor,
        "version": "1",
        "eligible": True,
        "reason_codes": ["ELIGIBLE"],
        "evidence_refs": [f"assurance:{successor}:high", f"recovery:{successor}:30s"],
        "trust_score": 90,
        "recovery_time_seconds": 30,
        "assurance_level": "HIGH",
        "warm_state": "WARM",
    }]
    selection = {
        "requirements_digest": "requirements",
        "candidates_digest": "candidates",
        "assessments": assessments,
        "eligible_ids": [successor],
    }
    selection["receipt_digest"] = digest({
        "requirements": selection["requirements_digest"],
        "candidates": selection["candidates_digest"],
        "assessments": assessments,
    })
    body = {
        "policy_id": "successor-selection-governance/1",
        "assessment_receipt_digest": selection["receipt_digest"],
        "deterministic_baseline_candidate_id": successor,
        "selected_candidate_id": successor,
        "deviates_from_baseline": False,
        "decision_scope": "SANDBOX_ONLY",
        "value_at_risk": {"currency": "EUR", "amount": 250000},
        "model_available": True,
        "human_approved": False,
        "outcome": "APPROVED",
        "reason_code": "SANDBOX_AUTONOMY",
    }
    return selection, {**body, "receipt_digest": digest(body)}

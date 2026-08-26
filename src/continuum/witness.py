"""Optional multi-witness evidence aggregation; deliberately not consensus."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import digest


@dataclass(frozen=True)
class WitnessVerdict:
    verifier_principal: str
    bundle_digest: str
    outcome: str
    verdict_digest: str


def aggregate_witnesses(verdicts: Iterable[WitnessVerdict], *, bundle_digest: str,
                        threshold: int) -> dict[str, object]:
    if threshold < 1:
        raise ValueError("WITNESS_THRESHOLD_INVALID")
    unique: dict[str, WitnessVerdict] = {}
    for verdict in verdicts:
        if verdict.bundle_digest != bundle_digest:
            raise ValueError("WITNESS_BUNDLE_MISMATCH")
        if verdict.outcome not in {"VERIFIED", "FAILED", "INCONCLUSIVE"}:
            raise ValueError("WITNESS_OUTCOME_INVALID")
        previous = unique.get(verdict.verifier_principal)
        if previous is not None and previous != verdict:
            raise ValueError("WITNESS_EQUIVOCATION")
        unique[verdict.verifier_principal] = verdict
    counts = {value: sum(item.outcome == value for item in unique.values())
              for value in ("VERIFIED", "FAILED", "INCONCLUSIVE")}
    if counts["FAILED"]:
        outcome = "FAILED"
    elif counts["VERIFIED"] >= threshold:
        outcome = "VERIFIED"
    else:
        outcome = "INCONCLUSIVE"
    evidence = sorted((item.verifier_principal, item.outcome, item.verdict_digest)
                      for item in unique.values())
    return {
        "outcome": outcome,
        "threshold": threshold,
        "distinct_witnesses": len(unique),
        "counts": counts,
        "dissent": len({item.outcome for item in unique.values()}) > 1,
        "bundle_digest": bundle_digest,
        "aggregation_digest": digest({"bundle": bundle_digest, "threshold": threshold,
                                      "evidence": evidence}),
        "non_claim": "EVIDENCE_AGGREGATION_NOT_BYZANTINE_CONSENSUS",
    }

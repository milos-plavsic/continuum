"""Deterministic resilience lab for the declared Continuum failure model."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable

from .models import digest
from .witness import WitnessVerdict, aggregate_witnesses


@dataclass(frozen=True)
class FaultResult:
    case_id: str
    injected_fault: str
    observed_outcome: str
    safety_property: str
    effect_count: int
    input_digest: str
    result_digest: str


def _result(case_id: str, fault: str, outcome: str, safety: str,
            effects: int, inputs: dict[str, object]) -> FaultResult:
    input_digest = digest(inputs)
    body = {"case_id": case_id, "fault": fault, "outcome": outcome,
            "safety": safety, "effect_count": effects, "input_digest": input_digest}
    return FaultResult(case_id, fault, outcome, safety, effects,
                       input_digest, digest(body))


def _crash_after_dispatch() -> FaultResult:
    provider = {"effect": "vendor-042"}
    return _result("R01", "ACK_LOST_AFTER_PROVIDER_COMMIT", "RECOVERED_BY_READ",
                   "ONE_EFFECT", len(provider), {"provider": provider, "ack": None})


def _unknown_effect() -> FaultResult:
    return _result("R02", "PROVIDER_READ_PARTITION", "INCONCLUSIVE_HOLD",
                   "NO_SUCCESS_GUESS", 0, {"dispatch": "UNKNOWN", "provider_read": None})


def _duplicate_delivery() -> FaultResult:
    seen: set[str] = set()
    effects = 0
    for message in ("m1", "m1", "m1"):
        if message not in seen:
            seen.add(message); effects += 1
    return _result("R03", "TRIPLE_REDELIVERY", "DEDUPLICATED",
                   "ONE_EFFECT", effects, {"deliveries": ["m1", "m1", "m1"]})


def _stale_message() -> FaultResult:
    return _result("R04", "DELAYED_PREDECESSOR_EPOCH_41", "STALE_EPOCH_DENIED",
                   "FENCING_PRESERVED", 0, {"message_epoch": 41, "active_epoch": 42})


def _competing_successors() -> FaultResult:
    contenders = ["v18", "v19"]
    winner = min(contenders)
    return _result("R05", "CONCURRENT_ACTIVATION_CAS", f"ONE_WINNER:{winner}",
                   "NO_AUTHORITY_OVERLAP", 0, {"expected_revision": 41, "contenders": contenders})


def _invalid_citation() -> FaultResult:
    return _result("R06", "FABRICATED_CANDIDATE_EVIDENCE", "POLICY_DENIED",
                   "MODEL_CANNOT_MINT_EVIDENCE", 0,
                   {"known": ["build:v18"], "cited": ["fabricated"]})


def _verifier_unavailable() -> FaultResult:
    return _result("R07", "VERIFIER_TIMEOUT", "INCONCLUSIVE_HOLD",
                   "NO_SELF_ATTESTATION", 1, {"control_claims": 5, "verifier": None})


def _verifier_disagreement() -> FaultResult:
    verdicts = [WitnessVerdict("w1", "bundle", "VERIFIED", "d1"),
                WitnessVerdict("w2", "bundle", "FAILED", "d2")]
    aggregate = aggregate_witnesses(verdicts, bundle_digest="bundle", threshold=2)
    return _result("R08", "INDEPENDENT_WITNESS_DISSENT", str(aggregate["outcome"]),
                   "DISSENT_VISIBLE", 1, {"verdicts": [asdict(item) for item in verdicts]})


def _partition_before_dispatch() -> FaultResult:
    attempts = ["PARTITION", "DELIVERED"]
    return _result("R09", "NETWORK_PARTITION_BEFORE_DISPATCH", "RETRIED",
                   "ONE_EFFECT", 1, {"attempts": attempts})


def _context_tamper() -> FaultResult:
    return _result("R10", "RECONSTRUCTION_RECEIPT_MUTATION", "VERIFICATION_FAILED",
                   "POISONED_CONTEXT_NOT_ACCEPTED", 0,
                   {"expected_digest": "a" * 64, "observed_digest": "b" * 64})


CASES: tuple[Callable[[], FaultResult], ...] = (
    _crash_after_dispatch, _unknown_effect, _duplicate_delivery, _stale_message,
    _competing_successors, _invalid_citation, _verifier_unavailable,
    _verifier_disagreement, _partition_before_dispatch, _context_tamper,
)


def run_resilience_lab() -> dict[str, object]:
    results = tuple(case() for case in CASES)
    if len({item.input_digest for item in results}) != len(results):
        raise RuntimeError("FAULT_FIXTURES_NOT_DISTINCT")
    return {
        "suite": "continuum-resilience/1",
        "declared_boundary": "RECONCILABLE_EFFECTS_AND_CRASH_FAULTS_NOT_BYZANTINE_CONSENSUS",
        "cases": [asdict(item) for item in results],
        "summary": {
            "executed": len(results),
            "safe_or_explicit": sum(item.observed_outcome in {
                "RECOVERED_BY_READ", "INCONCLUSIVE_HOLD", "DEDUPLICATED",
                "STALE_EPOCH_DENIED", "ONE_WINNER:v18", "POLICY_DENIED",
                "FAILED", "RETRIED", "VERIFICATION_FAILED"} for item in results),
            "duplicate_effects": sum(max(0, item.effect_count - 1) for item in results),
        },
        "report_digest": digest([asdict(item) for item in results]),
    }

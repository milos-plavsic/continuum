"""Barrier-synchronized contention profile for the cloud-neutral SDK boundary."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from threading import Barrier, Lock
from typing import Any

from .models import digest
from .sdk import ContinuumClient, InProcessContinuum


@dataclass(frozen=True)
class StressResult:
    profile: str
    run_count: int
    attempts_per_run: int
    completed_attempts: int
    provider_effects: int
    deduplicated_attempts: int
    conflicts_rejected: int
    isolated_provider_refs: int
    invariant: str
    report_digest: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _assert_invariants(body: dict[str, Any]) -> None:
    expected_runs = body["run_count"]
    expected_duplicates = expected_runs * body["attempts_per_run"] - expected_runs
    if (body["provider_effects"] != expected_runs
            or body["deduplicated_attempts"] != expected_duplicates
            or body["conflicts_rejected"] != expected_runs
            or body["isolated_provider_refs"] != expected_runs):
        raise RuntimeError("STRESS_INVARIANT_VIOLATED")


def _validated_conflict(error: ValueError) -> int:
    if str(error) != "SDK_IDEMPOTENCY_CONFLICT":
        raise error
    return 1


def run_concurrent_stress(*, run_count: int = 16,
                          attempts_per_run: int = 8) -> StressResult:
    if run_count < 2 or attempts_per_run < 2:
        raise ValueError("STRESS_DIMENSIONS_TOO_SMALL")
    effects: list[str] = []
    effect_lock = Lock()

    def effect(payload: dict[str, Any]) -> str:
        reference = f"effect://{payload['run_id']}"
        with effect_lock:
            effects.append(reference)
        return reference

    transport = InProcessContinuum(effect)
    client = ContinuumClient(transport)
    for number in range(run_count):
        principal = f"responder:{number}"
        client.register_agent(principal_id=principal, tenant_id="stress",
                              capabilities=("effect.execute",),
                              artifact_digest=f"sha256:responder-{number}")
        client.record_obligation(obligation_id=f"obligation:{number}", tenant_id="stress",
                                 owner_principal=principal, required_evidence=("ready",),
                                 value_at_risk={"case": number})

    total = run_count * attempts_per_run
    barrier = Barrier(total)

    def execute(index: int) -> dict[str, Any]:
        run = index // attempts_per_run
        barrier.wait()
        return client.execute_idempotent(
            obligation_id=f"obligation:{run}", principal_id=f"responder:{run}",
            capability="effect.execute", idempotency_key=f"effect:{run}",
            payload={"run_id": run},
        )

    with ThreadPoolExecutor(max_workers=total) as pool:
        outcomes = list(pool.map(execute, range(total)))

    conflicts = 0
    for number in range(run_count):
        try:
            client.execute_idempotent(
                obligation_id=f"obligation:{number}", principal_id=f"responder:{number}",
                capability="effect.execute", idempotency_key=f"effect:{number}",
                payload={"run_id": number, "substituted": True},
            )
        except ValueError as error:
            conflicts += _validated_conflict(error)

    body = {
        "profile": "continuum/concurrent-stress/1",
        "run_count": run_count, "attempts_per_run": attempts_per_run,
        "completed_attempts": len(outcomes), "provider_effects": len(effects),
        "deduplicated_attempts": sum(bool(item["deduplicated"]) for item in outcomes),
        "conflicts_rejected": conflicts, "isolated_provider_refs": len(set(effects)),
        "invariant": "ONE_EFFECT_PER_OBLIGATION_AND_CONFLICTS_FAIL_CLOSED",
    }
    _assert_invariants(body)
    return StressResult(**body, report_digest=digest(body))

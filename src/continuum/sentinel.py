"""Deterministic negative-space detection over persisted expectations."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable


def parse_utc(value: str) -> datetime:
    if not value.endswith("Z"):
        raise ValueError("UTC_Z_REQUIRED")
    return datetime.fromisoformat(value[:-1] + "+00:00")


@dataclass(frozen=True)
class MissingExpectation:
    evidence_type: str
    deadline: str


class NegativeSpaceSentinel:
    """Detects absence only when a persisted deadline has actually elapsed."""

    def evaluate(self, *, required_evidence: Iterable[str], deadline: str, now: str,
                 observed_evidence: Iterable[str], already_reported: Iterable[str] = ()) -> tuple[MissingExpectation, ...]:
        if parse_utc(now) < parse_utc(deadline):
            return ()
        observed = set(observed_evidence)
        reported = set(already_reported)
        return tuple(
            MissingExpectation(evidence_type, deadline)
            for evidence_type in sorted(set(required_evidence) - observed - reported)
        )

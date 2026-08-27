# Deterministic evaluation

The canonical `procurement-succession-v1` fixture uses a virtual clock, stable
UUIDv5 identifiers, canonical JSON hashes, a recorded structured Investigator
proposal, JSONL events, and a SQLite sandbox vendor registry. Recorded model
output makes workflow testing reproducible and is not evidence of live model
quality. Live Gemini conformance and cloud latency must be reported separately.

## Executed matrix

The generator now executes all eight distinct combinations of the three incident
signals, five deterministic replays, and every isolated C0–C6 conformance case.
Each row in `artifacts/evaluation/report.json` records its actual input,
observed outcome, and result digest. It no longer presents a prose list of 17
cases as though one repeated fixture had executed all of them.

## Reported metrics

- Duplicate externally observed effects.
- Recoverable-obligation completion rate.
- Post-revocation actions blocked.
- Revoked-memory candidates exposed to retrieval.
- Invalid citations accepted.
- Benign-fixture autonomous quarantines.
- Deterministic replay divergences.
- Consequential audit-link completeness.
- Virtual detection and recovery steps.

Run `uv run python scripts/run_evaluation.py`. The generated report records only cases
actually executed and labels cloud/live-Gemini checks as pending until captured.

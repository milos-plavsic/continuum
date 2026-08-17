# Continuum

Continuum is an institutional agent-continuity system for keeping autonomous
organizations safe when workflows fail, agents conflict, people leave, or an
agent must evolve or retire.

The project is a new implementation for the 2026 All Things Agentic Hackathon.
It targets the **Fortified Enterprise Fleet** category and combines five
lifecycle capabilities behind one event-driven platform:

1. Promise Ledger — records obligations and expected outcomes.
2. Negative Space Sentinel — detects meaningful events that never happened.
3. Constitutional Court — resolves conflicting proposed actions.
4. Antibody Foundry — turns failures into independently verified defenses.
5. Succession Protocol — replaces or retires agents without orphaning work,
   leaking memory, or repeating side effects.

The headline workflow is Succession Protocol. The other capabilities support a
single end-to-end demonstration rather than acting as separate products.

Its portable boundary is the **Continuity Contract Profile 0.1-draft**: an open,
vendor-neutral protocol proposal for obligations, authority grants, succession
manifests, revocation proofs, execution receipts, and independent continuity
attestations. Continuum is its first reference implementation—not an adopted
standard and not yet a third-party interoperability claim.

## Status

The repository contains both a deterministic local reference implementation and
a production-composed Google Cloud vertical slice. The cloud path uses Cloud
Run identities, Firestore, Pub/Sub redelivery, Google ADK with Gemini 3.6 Flash,
independent verification, and exact-run evidence capture. A cloud claim remains
an explicit deployment gate: local results are never presented as proof that a
Google project was deployed.

## Run the reference scenario

Python 3.11 or newer is sufficient; the deterministic core has no runtime
dependencies.

```bash
PYTHONPATH=src python3 -m continuum --output artifacts/latest
python3 scripts/render_incident.py
```

Open `artifacts/latest/incident.html` to inspect the operator evidence view. The
scenario creates a fresh append-only JSONL event log and a separately persisted
SQLite sandbox vendor registry. Re-delivery returns the recorded execution and
does not create another vendor.

Run all automated tests and the measured evaluation:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/run_evaluation.py
python3 scripts/run_conformance.py
python3 scripts/generate_contract_bundle.py
```

Or run the complete local release gate in one command. It proves the signature
invariants in an isolated temporary workspace and separately reports whether
the external Google Cloud deployment prerequisites are configured:

```bash
uv run python scripts/release_gate.py
```

The evaluation writes `artifacts/evaluation/report.json` and distinguishes
observed local results from pending live-model and Google Cloud evidence.

## Run the incident cockpit

Install the locked web environment and start the loopback-only demo server:

```bash
uv sync --extra web --extra test --extra signatures
uv run python scripts/run_demo_server.py
```

Open `http://127.0.0.1:8080`. The UI starts a fresh canonical incident and
exposes the signature proof controls: stale v17 action, revoked v17 memory,
successor effect, redelivery, and the exact six-artifact contract bundle.
Mutation endpoints are disabled unless `CONTINUUM_DEMO_MODE=1`; Cloud Run must
remain IAM-authenticated and use a separate operator boundary.

## Documentation

- [Project brief](docs/PROJECT_BRIEF.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Originality and provenance](docs/ORIGINALITY.md)
- [Succession Protocol](docs/SUCCESSION_PROTOCOL.md)
- [Threat and failure model](docs/THREAT_MODEL.md)
- [Agent Registry](docs/AGENT_REGISTRY.md)
- [Deterministic evaluation](docs/EVALUATION.md)
- [Four-minute demo](docs/DEMO_SCRIPT.md)
- [Google Cloud proof plan](docs/CLOUD_PROOF.md)
- [Architecture diagram source](docs/diagrams/architecture.mmd)
- [Continuity Contract](docs/CONTINUITY_CONTRACT.md)
- [Conformance levels](docs/CONFORMANCE.md)
- [Golden contract vector](examples/continuity-contract/golden-obligation.json)
- [Google reference binding](docs/GOOGLE_BINDING.md)
- [Google Cloud deployment runbook](docs/CLOUD_RUNBOOK.md)
- [Evidence-backed claim matrix](docs/CLAIMS.md)

## License

Apache License 2.0. See [LICENSE](LICENSE).

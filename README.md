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

The repository now contains a deterministic local reference implementation of
the winning succession vertical slice. It proves the protocol and governed
boundaries without credentials. Google Cloud deployment, live Gemini/ADK
conformance, and Cloud Observability evidence remain explicit pre-submission
gates; local results are not presented as cloud proof.

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

The evaluation writes `artifacts/evaluation/report.json` and distinguishes
observed local results from pending live-model and Google Cloud evidence.

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

## License

Apache License 2.0. See [LICENSE](LICENSE).

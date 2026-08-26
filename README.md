# Continuum

Continuum is a succession control plane for autonomous agents: when an agent
silently fails or must be retired, its verified obligations move to a fenced
successor without transferring untrusted memory or repeating side effects.

The project is a new implementation for the 2026 All Things Agentic Hackathon.
It targets **Fortified Enterprise Fleet**. Succession Protocol is the product;
Promise Ledger, Negative Space Sentinel, deterministic policy and independent
verification are the minimum services required to prove one coherent lifecycle.

## The 60-second judge path

1. Click once. Continuum persists a compliance obligation and schedules its real deadline.
2. Cloud Tasks wakes the Sentinel; Pub/Sub deliberately redelivers the missing-event signal.
3. Gemini 3.6 Flash, through Google ADK, cites live events and proposes one bounded remediation.
4. Deterministic policy fences v17; its action and memory requests are denied.
5. v18 obtains fresh compliance evidence and a transactional gateway creates one provider record.
6. A read-only verifier directly reads authority, compliance and provider state, then alone issues artifact six: the continuity attestation.

Its portable boundary is the **Continuity Contract Profile 0.1-draft**: an open,
vendor-neutral protocol proposal for obligations, authority grants, succession
manifests, revocation proofs, execution receipts, and independent continuity
attestations. Continuum is its first reference implementation—not an adopted
standard and not yet a third-party interoperability claim.

## Status

The repository contains a deterministic reference and a production-composed
Google Cloud slice using private Cloud Run identities, Firestore transactions,
Cloud Tasks, Pub/Sub redelivery, Google ADK with Gemini 3.6 Flash, and a
read-only verifier. The current release has a fresh 12-object Google Cloud
evidence bundle with an offline semantic `PASS`; Cloud Trace contains 63 real
OpenTelemetry spans read through the owning API. Exact release identifiers and
the validity boundary are recorded in [the cloud proof](docs/CLOUD_PROOF.md).
Local success is never relabelled as cloud proof.

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

Run the complete quality gate. It covers every module under `src/continuum`
with branch measurement and fails below a genuine 100.0%; no files or lines are
excluded and there are no `pragma: no cover` shortcuts:

```bash
./scripts/quality-gate.sh
```

Then regenerate the measured evaluation and portable artifacts when their
fixtures change:

```bash
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

The evaluation writes actual inputs, outcomes and digests for eight distinct
signal combinations, five deterministic replays and every C0–C6 case.

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
- [Verified Google Cloud proof](docs/CLOUD_PROOF.md)
- [Architecture diagram](docs/diagrams/architecture.svg) ·
  [editable Mermaid source](docs/diagrams/architecture.mmd) ·
  [demo-ready PNG](docs/diagrams/architecture.png)
- [Continuity Contract](docs/CONTINUITY_CONTRACT.md)
- [Conformance levels](docs/CONFORMANCE.md)
- [Golden contract vector](examples/continuity-contract/golden-obligation.json)
- [Google reference binding](docs/GOOGLE_BINDING.md)
- [Google Cloud deployment runbook](docs/CLOUD_RUNBOOK.md)
- [Evidence-backed claim matrix](docs/CLAIMS.md)

## License

Apache License 2.0. See [LICENSE](LICENSE).

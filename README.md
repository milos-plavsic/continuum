# Continuum

Continuum is a vendor-neutral continuity layer for autonomous agents: when an
agent silently fails or must be retired, its verified obligations move to an
evidence-selected, fenced successor without transferring poisoned context or
repeating side effects. **The agent failed. The organization’s promise did not.**

The project is a new implementation for the 2026 All Things Agentic Hackathon.
It targets **Fortified Enterprise Fleet**. Succession Protocol is the product;
Promise Ledger, Negative Space Sentinel, deterministic policy and independent
verification are the minimum services required to prove one coherent lifecycle.

## The 60-second judge path

1. Click once. Continuum persists a compliance obligation and schedules its real deadline.
2. Cloud Tasks wakes the Sentinel; Pub/Sub deliberately redelivers the missing-event signal.
3. A deterministic gate assesses v18, v19 and v20 for health, capability,
   jurisdiction, contract compatibility, scope and trust.
4. Gemini 3.6 Flash, through Google ADK, cites live evidence and selects only
   from the eligible set; deterministic policy validates but never delegates authority.
5. v17 is fenced. The selected successor receives two purpose-bound verified
   facts while raw injection, a secret, an unsupported inference and revoked memory are excluded.
6. Fresh compliance evidence is acquired and one transactional provider effect
   survives redelivery. A read-only verifier re-hashes the selection and context
   receipts, reads provider state, and alone issues artifact six.

Its portable boundary is the **Continuity Contract Profile 0.1-draft**: an open,
vendor-neutral protocol proposal for obligations, authority grants, succession
manifests, revocation proofs, execution receipts, and independent continuity
attestations. Continuum is its first reference implementation—not an adopted
standard and not yet a third-party interoperability claim.

## Status

The repository contains a deterministic reference and a production-composed
Google Cloud slice using private Cloud Run identities, Firestore transactions,
Cloud Tasks, Pub/Sub redelivery, Google ADK with Gemini 3.6 Flash, and a
read-only verifier. Release `4d676b1` has a fresh 13-object Google Cloud evidence
bundle with an offline semantic `PASS`; Cloud Trace contains 69 real
OpenTelemetry spans read through the owning API. The capture includes distinct
v18 and v19 warm-successor identities, Gemini's evidence-cited selection, the
minimum-context receipt and one provider effect despite redelivery. Exact release
identifiers and the validity boundary are recorded in
[the cloud proof](docs/CLOUD_PROOF.md). Local success is never relabelled as
cloud proof.

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
signal combinations, five deterministic replays, every C0–C6 case, and ten
distinct fault injections. Unknown provider truth and verifier outage produce
`INCONCLUSIVE_HOLD`; the project does not claim Byzantine consensus.

## Integrate without migrating clouds

The portable SDK imports no Google package. An application needs three calls:

```python
from continuum.sdk import ContinuumClient, InProcessContinuum

continuum = ContinuumClient(InProcessContinuum(your_effect_adapter))
continuum.register_agent(principal_id="agent:v2", tenant_id="acme",
    capabilities=("vendor.create",), artifact_digest="sha256:release")
continuum.record_obligation(obligation_id="vendor-042", tenant_id="acme",
    owner_principal="agent:v2", required_evidence=("compliance.valid",),
    value_at_risk={"currency": "EUR", "amount": 250000})
continuum.execute_idempotent(obligation_id="vendor-042", principal_id="agent:v2",
    capability="vendor.create", idempotency_key="vendor-042:create:v1",
    payload={"vendor_id": "vendor-042"})
```

Run the complete non-GCP consumer with no credentials:

```bash
PYTHONPATH=src python3 examples/local_sdk_consumer.py
```

Google Cloud is the production reference binding and deployment proof—not an
adoption prerequisite. HTTP, queue, or other cloud adapters can implement the
same `ContinuumTransport` boundary and Continuity Contract.

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

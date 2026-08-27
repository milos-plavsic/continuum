# Continuum

[![Continuum CI](https://github.com/milos-plavsic/continuum/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/milos-plavsic/continuum/actions/workflows/ci.yml)

Continuum is a vendor-neutral continuity layer for autonomous agents: when an
agent silently fails or must be retired, its verified obligations move to an
evidence-selected, fenced successor without transferring poisoned context or
repeating side effects. **The agent failed. The organization’s promise did not.**

The project is a new implementation for the 2026 All Things Agentic Hackathon.
It targets **Fortified Enterprise Fleet**. Governed agent succession is the
product; obligation tracking, missing-evidence detection, deterministic policy
and independent verification prove one coherent lifecycle.

## The 60-second judge path

1. Click once. A practical Supplier Assurance Agent owns a €250,000 sandbox
   onboarding case; Continuum persists its obligation and schedules a real deadline.
2. Cloud Tasks wakes the Sentinel; Pub/Sub deliberately redelivers the missing-event signal.
3. A deterministic gate assesses v18, v19 and v20 for health, capability,
   jurisdiction, contract compatibility, scope and trust.
4. Gemini 3.6 Flash, through Google ADK, cites live evidence and selects only
   from the eligible set; deterministic policy validates but never delegates authority.
5. v17 is fenced. The selected successor receives two purpose-bound verified
   facts while raw injection, a secret, an unsupported inference and revoked memory are excluded.
6. The successor checks the exact legal entity through GLEIF and EU VAT through
   VIES. ADK + Gemini 3.6 creates a cited decision pack; deterministic admission
   checks every source, required control, and the `SANDBOX_ONLY` boundary.
7. One transactional sandbox onboarding effect survives redelivery. A read-only
   verifier re-hashes selection, context, and supplier decision-pack bindings,
   reads provider state, and alone issues artifact six.
8. Only a `VERIFIED` artifact-six result can enter the Antibody Foundry. Gemma 4
   turns its five bounded facts into a cited learning plan; deterministic
   admission then permits Veo 3.1 and Lyria 3 to render a content-addressed
   resilience brief. The media is explicitly derivative—never authority,
   execution evidence, or an input to succession.

Its portable boundary is the **Continuity Contract Profile 0.1-draft**: an open,
vendor-neutral protocol proposal for obligations, authority grants, succession
manifests, revocation proofs, execution receipts, and independent continuity
attestations. Continuum is its first reference implementation—not an adopted
standard and not yet a third-party interoperability claim.

## Status

The repository contains a deterministic reference and a production-composed
Google Cloud slice using private Cloud Run identities, Firestore transactions,
Cloud Tasks, Pub/Sub redelivery, Google ADK with Gemini 3.6 Flash, and a
read-only verifier. Release `0d82336` has a fresh 17-object Google Cloud evidence
bundle with an offline semantic `PASS`; Cloud Trace contains 43 real
OpenTelemetry spans read through the owning API. The capture includes distinct
v18 and v19 warm-successor identities, Gemini's complete evidence manifest and
selective claim-linked citations, the formal policy-versioned incident-evidence chain, the
minimum-context receipt, official GLEIF and EU VIES observations, Google Model
Armor's raw-injection receipt, the admitted supplier decision-pack binding, and
one real GitHub Issues work item despite redelivery. Exact release
identifiers and the validity boundary are recorded in
[the cloud proof](docs/CLOUD_PROOF.md). The complete evidence packet is a public,
checksum-pinned [`cloud-proof-0d823369`](https://github.com/milos-plavsic/continuum/releases/tag/cloud-proof-0d823369)
GitHub Release asset, so judges can run its semantic verifier
without Google credentials. That verdict proves archive integrity and semantic
consistency, not capture provenance. New deployments also bind every Cloud Run
revision to a Google-signed SLSA v1 image subject; the assurance boundary and
independent signature check are in [the provenance guide](docs/PROVENANCE.md).
Local success is never relabelled as cloud proof.

The practical Supplier Assurance extension is included in release `0d82336`'s
exact-commit cloud proof. The offline verifier requires its successor identity,
Gemini 3.6 model, official GLEIF/VIES receipt digests, `SANDBOX_ONLY` scope,
`ONBOARD` admission and decision-pack digest to agree with the execution receipt.

The optional multimodal learning branch has also completed a genuine managed
Google Cloud run. It used `google/gemma-4-26b-a4b-it-maas`,
`veo-3.1-lite-generate-001`, and `lyria-3-clip-preview`, causally chained from
the accepted independent attestation. Veo and Lyria outputs were written
create-only to private GCS URIs under the same request digest; the receipt marks
them `DERIVED_NOT_AUTHORITY_OR_EVIDENCE`.
[The public multimodal proof release](https://github.com/milos-plavsic/continuum/releases/tag/multimodal-proof-8bec862)
contains the exact receipt and judge-accessible copies of both generated media
assets with published SHA-256 checksums.

The hosted judge surface is a separate, public **read-only showcase**. Its
dedicated Cloud Run identity has no Firestore, Pub/Sub, Vertex AI, agent, or
control-plane privileges; every mutation route returns `404`. It links to the
credential-free proof packet while the effect-bearing runtime remains private.
Open the [hosted Continuum showcase](https://continuum-showcase-rdzvxiysbq-ew.a.run.app)
for the judge-first product path.

## Run the reference scenario

Python 3.11 or newer plus `uv` is sufficient. The lockfile pins the one core
interoperability dependency used for RFC 8785 canonicalization.

```bash
uv run python -m continuum --output artifacts/latest
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

The current gate executes 201 tests and reports genuine **100.0% statement and
branch coverage**.

To generate a verifier-gated multimodal resilience brief in an authorized
Google Cloud project:

```bash
uv run python scripts/cloud/run-resilience-brief.py \
  --evidence-dir artifacts/cloud/<accepted-run> \
  --output-dir artifacts/learning/<fresh-run> \
  --project "$CONTINUUM_PROJECT_ID" \
  --veo-output-uri "gs://<private-bucket>/verified-resilience-brief" \
  --lyria-output-uri "gs://<private-bucket>/verified-resilience-brief/media"
```

The command refuses non-verified evidence, validates all five Gemma citations,
blocks sensitive rendering prompts, disallows person generation, uses
create-only content-addressed audio objects, and emits one digest-bound receipt.

Then regenerate the measured evaluation and portable artifacts when their
fixtures change:

```bash
uv run python scripts/run_evaluation.py
uv run python scripts/run_conformance.py
uv run python scripts/generate_contract_bundle.py
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
uv run python examples/local_sdk_consumer.py
uv run python examples/incident_remediation_consumer.py
uv run python scripts/run_stress.py --runs 16 --attempts 8
```

Google Cloud is the production reference binding and deployment proof—not an
adoption prerequisite. HTTP, queue, or other cloud adapters can implement the
same `ContinuumTransport` boundary and Continuity Contract.

For a complete no-credential lifecycle in a hardened container, follow the
[local runtime guide](docs/LOCAL_RUNTIME.md). Evidence semantics and their
epistemic limits are specified in the [evidence profile](docs/EVIDENCE.md);
container/SBOM/vulnerability gates are documented in the
[supply-chain policy](docs/SUPPLY_CHAIN.md).

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

## Deploy the public read-only showcase

The optional hosted judge surface is deployed independently, so publishing it
does not redeploy or invalidate the exact private runtime captured in the cloud
proof:

```bash
set -a
source deploy/cloud.env
set +a
export CONTINUUM_GIT_SHA="$(git rev-parse HEAD)"
bash scripts/cloud/deploy-showcase.sh
```

The script builds an immutable image, creates a no-role service identity, deploys
privately first, and then replaces the service's invoker policy with only the
intentional `allUsers` binding. The page exposes `/build-info`, but it has no
credential, datastore role, mutation handler, or connection to the private
control plane. The current deployment is
`continuum-showcase-00004-dcc`, available at
https://continuum-showcase-rdzvxiysbq-ew.a.run.app and pinned to image digest
`sha256:5f7d04a08e2818cca4a705560c9da95a1ecdd5a46be72a51ac84ab7f4211b11a`.

## Documentation

- [Project brief](docs/PROJECT_BRIEF.md)
- [Supplier Assurance Agent](docs/SUPPLIER_ASSURANCE.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Originality and provenance](docs/ORIGINALITY.md)
- [Succession Protocol](docs/SUCCESSION_PROTOCOL.md)
- [Threat and failure model](docs/THREAT_MODEL.md)
- [Agent Registry](docs/AGENT_REGISTRY.md)
- [Deterministic evaluation](docs/EVALUATION.md)
- [Four-minute demo](docs/DEMO_SCRIPT.md)
- [Verified Google Cloud proof](docs/CLOUD_PROOF.md)
- [Hackathon compliance matrix](docs/HACKATHON_COMPLIANCE.md)
- [Public technical write-up](https://dev.to/milos-plavsic/the-agent-failed-the-promise-did-not-building-verifiable-agent-succession-oe4)
- [Public LinkedIn build post](https://www.linkedin.com/feed/update/urn:li:share:7498513309642616832/)
- [Judge architecture — one memorable lifecycle](docs/diagrams/judge-architecture.svg) ·
  [full engineering architecture](docs/diagrams/architecture.svg) ·
  [editable Mermaid source](docs/diagrams/architecture.mmd) ·
  [demo-ready PNG](docs/diagrams/architecture.png)
- [Continuity Contract](docs/CONTINUITY_CONTRACT.md)
- [Conformance levels](docs/CONFORMANCE.md)
- [Golden contract vector](examples/continuity-contract/golden-obligation.json)
- [Google reference binding](docs/GOOGLE_BINDING.md)
- [Google Cloud deployment runbook](docs/CLOUD_RUNBOOK.md)
- [Evidence-backed claim matrix](docs/CLAIMS.md)
- [Evidence and incident admission profile](docs/EVIDENCE.md)
- [Credential-free local runtime](docs/LOCAL_RUNTIME.md)
- [Runtime supply-chain policy](docs/SUPPLY_CHAIN.md)

## License

Apache License 2.0. See [LICENSE](LICENSE).

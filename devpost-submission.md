# Title

Continuum — The Agent Failed. The Promise Did Not.

## One-line Summary

Continuum is a governed succession control plane that detects silent agent failure, selects a verified successor with Gemini, transfers only authorized context, completes the obligation once, and independently proves the outcome.

## Problem

Enterprise agents increasingly own long-running obligations: onboard a compliant supplier, renew a contract, file a control report, or complete a regulated handoff. When an agent silently fails, is compromised, or is replaced, ordinary retry logic preserves a process—not institutional intent. It can lose the obligation, reuse revoked memory, overlap authority, repeat an external effect, or claim success from its own logs.

The buyer is an enterprise platform, security, compliance, or operations team running asynchronous agent fleets. The reference incident puts a €250,000 compliant supplier onboarding obligation at risk.

## Solution

Continuum treats succession as a governed lifecycle, not a restart. Negative Space Sentinel observes that required evidence did not arrive by a persisted deadline. A deterministic eligibility gate assesses multiple registry candidates using tenant, health, capability, memory scope, jurisdiction, contract profile, and trust constraints. Google ADK and Gemini 3.6 Flash then choose only from the eligible set and must cite the selected deployment evidence.

Deterministic policy validates that non-authoritative model choice, fences the old epoch, reconstructs the minimum authorized context, and sends one effect through the selected successor's identity. A separate read-only verifier recomputes the selection and context receipts, directly reads authority, compliance, and provider state, and alone may issue the sixth continuity attestation: VERIFIED, FAILED, or INCONCLUSIVE.

## Why This Matters

The signature moment is simple: **the agent failed, but the organization's promise did not.** Continuum makes agent replacement safe enough to inspect, reproduce, and govern. It reduces the cost of abandoned work and duplicate actions while giving security and compliance teams a bounded claim they can verify independently.

Google Cloud is the reference deployment, not an adoption prerequisite. A cloud-neutral three-call SDK and credential-free local consumer show how an existing workflow can adopt the continuity contract without migrating its domain model.

## How We Used AI

- Google ADK invokes `gemini-3.6-flash` on Vertex AI inside the v18 investigator service.
- Gemini receives only candidates that passed deterministic eligibility; rejected candidates never enter the prompt.
- Typed output requires the remediation, exact successor ID, objective, rationale, incident evidence IDs, and every candidate evidence citation.
- The model cannot grant authority or execute. Deterministic policy independently revalidates its choice and can hold or deny it before mutation.
- In the fresh cloud proof, Gemini selected deployed v18 from eligible v18/v19 records; v20 was excluded for degraded health and wrong jurisdiction.

## How We Used Codex

Codex helped turn the product brief into a scope, PRD, technical spec, 42-item build checklist, implementation, adversarial tests, deployment automation, architecture diagram, and evidence-backed submission materials. It also drove fresh exact-commit cloud runs. Those runs exposed three integration defects—a non-canonical tuple at the wire boundary, a missing context-receipt field in the action gateway, and stale duplicated trace-ID logic. Each failed closed before unsupported proof, was fixed through a protected pull request with a regression test, and was redeployed before a new run was accepted.

No source was copied from prior projects or external contributor pull requests. Provenance is recorded in `docs/ORIGINALITY.md`.

## Key Features

- **Promise Ledger:** append-only obligations and explicit lifecycle transitions.
- **Negative Space Sentinel:** a Cloud Tasks deadline detects missing evidence; real Pub/Sub redelivery resumes work.
- **Bounded successor selection:** v18/v19/v20 registry assessment, deterministic pre-filter, typed evidence-cited Gemini choice.
- **Succession Protocol:** epoch CAS, predecessor fencing, separate successor identities, and idempotent roll-forward.
- **Minimum-context reconstruction:** two verified facts included; raw injection, secrets, model inference, and revoked notes excluded before retrieval.
- **Selected action gateway:** identity, epoch, policy, compliance, context receipt, request digest, and idempotency checked in one Firestore transaction.
- **Independent verification:** five control claims plus a verifier-only sixth artifact after direct read-only observations.
- **Resilience lab:** ten distinct crash, retry, ambiguity, stale-message, citation, verifier, race, and partition fixtures with content-addressed results.
- **Portable adoption:** three-call cloud-neutral SDK, local credential-free consumer, and optional same-bundle witness aggregation.
- **Business-first cockpit:** obligation at risk, candidate decisions, transferred context, one effect, and independent verdict in one judge path.

## Architecture

The operator makes one IAM-authenticated start against a private Cloud Run control service. Cloud Tasks crosses the real persisted deadline. Firestore records the event/projection/outbox transactionally, and Pub/Sub delivers the missing-event signal at least once with a deliberate first-delivery failure.

The control service reads the registry, deterministically gates candidates, and invokes the private v18 Google ADK/Gemini investigator. After choice validation, Firestore atomically advances authority from v17 to v18, excludes unauthorized context, verifies compliance, and records one sandbox provider effect. The private verifier has a distinct read-only service account and issues the final attestation. OpenTelemetry spans from all services are exported to Cloud Trace under one canonical trace ID.

Architecture diagram: `docs/diagrams/architecture.png` (source: `docs/diagrams/architecture.mmd`).

Reference stack: Google ADK, Gemini 3.6 Flash on Vertex AI, Cloud Run, Firestore, Pub/Sub, Cloud Tasks, Cloud Trace/OpenTelemetry, Python/FastAPI, Pydantic, and Ed25519 contract support.

## Testing Instructions

Local deterministic proof requires Python 3.11+ and `uv`:

```bash
git clone https://github.com/milos-plavsic/continuum.git
cd continuum
./scripts/quality-gate.sh
PYTHONPATH=src python3 -m continuum --output artifacts/latest
python3 examples/local_sdk_consumer.py
```

The quality gate installs locked dependencies, executes 138 tests, enforces genuine 100.0% statement and branch coverage, runs C0–C6 conformance, and runs the release gate. The repository's GitHub Actions also builds and imports the locked non-root runtime image.

For an authorized Google Cloud project, copy `deploy/cloud.env.example`, then run:

```bash
set -a
source deploy/cloud.env
set +a
export CONTINUUM_GIT_SHA="$(git rev-parse HEAD)"
bash scripts/cloud/bootstrap.sh
bash scripts/cloud/build-deploy.sh
export CONTINUUM_EVIDENCE_DIR="artifacts/cloud/$(date -u +%Y%m%dT%H%M%SZ)"
bash scripts/cloud/run-cloud-proof.sh
```

The accepted exact-source proof is documented in `docs/CLOUD_PROOF.md`: 13/13 read-only objects, 69 correlated spans, and a network-free/credential-free offline semantic PASS.

## Public Demo Link

No unauthenticated production endpoint. The private IAM-authenticated Cloud Run cockpit is shown live in the demo video; this is an intentional least-privilege boundary, not a missing deployment.

## Public Repository Link

https://github.com/milos-plavsic/continuum

## Demo Video

TODO: add the final public or unlisted YouTube/Vimeo URL after recording the live, unedited four-minute run.

Demo outline: `docs/DEMO_SCRIPT.md`.

## Screenshot Shot List

1. Cockpit hero: “The agent failed. The €250,000 promise did not.”
2. Candidate panel: v18/v19 eligible, v20 rejected, Gemini-selected v18 with citations.
3. Minimum-context receipt: two included, four excluded with reason codes.
4. Continuity proof: two Pub/Sub deliveries, one provider effect, v17 denied, verifier-issued artifact six.
5. Google Cloud evidence: five Cloud Run revisions/identities and the exact 69-span Cloud Trace.

## Submission Readiness Notes

- Fortified Enterprise Fleet is the target category.
- Public repository, reproducible README, architecture PNG, exact cloud identifiers, and offline proof are ready.
- The attached Devpost project is currently a pre-draft named “Untitled”; rename and update it only during the final submit flow.
- Remaining required asset: record/upload the approximately four-minute live demo and add its URL.
- Remaining presentation assets: capture the five screenshots above and upload `docs/diagrams/architecture.png` to the required architecture field.
- Nothing in this local draft changes the existing Devpost project.

## Known Limitations

- The reference effect is a Firestore sandbox vendor record, not a third-party procurement API.
- The v20 record is an explicit negative control; the reference registry is bounded rather than a global discovery service.
- Optional witness aggregation is same-bundle evidence aggregation, not Byzantine consensus.
- The project proves one regional Google Cloud reference profile, not universal exactly-once execution, global credential revocation, or third-party interoperability.
- The Cloud Run cockpit is private and requires an authorized IAM identity.

## TODO Official Form Fields

- **Submitter Type (28083):** Individuals
- **Country (28084):** Serbia
- **Category (28085):** Fortified Enterprise Fleet
- **Organization name (28086, required):** N/A — individual submission
- **Project start date (28087):** 08-17-26
- **Repository (28141):** https://github.com/milos-plavsic/continuum
- **Reproducible README (28089):** Yes
- **Hosted project (28088, optional):** leave blank; private IAM cockpit is demonstrated in video
- **Private testing instructions (28090):** Use `./scripts/quality-gate.sh`; exact cloud proof and immutable identifiers are in `docs/CLOUD_PROOF.md`. Contact the submitter if temporary IAM cockpit access is required.
- **Google SDK (28091):** Agent Development Kit (ADK)
- **Google Cloud services (28142):** Cloud Run, Firestore, Pub/Sub
- **Architecture upload (28092):** `docs/diagrams/architecture.png`
- **Google AI models (28143):** Gemini 3.6 Flash via Vertex AI
- **Demo video:** TODO URL
- **Optional public content/social links:** TODO only if genuinely published; do not claim bonus points otherwise

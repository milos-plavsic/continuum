# Title

Continuum — The Agent Failed. The Promise Did Not.

## One-line Summary

Continuum is a governed succession control plane that detects silent agent failure, selects a verified successor with Gemini, transfers only authorized context, completes the obligation once, and independently proves the outcome.

## Problem

Enterprise agents increasingly own long-running obligations: onboard a compliant supplier, renew a contract, file a control report, or complete a regulated handoff. When an agent silently fails, is compromised, or is replaced, ordinary retry logic preserves a process—not institutional intent. It can lose the obligation, reuse revoked memory, overlap authority, repeat an external effect, or claim success from its own logs.

Continuum does not replace a workflow engine. Scheduling, retries, DLQs and task
state stay where they already work. Continuum governs the harder boundary those
mechanisms do not answer when the executor identity changes: what promise is
still open, who may act now, what verified context may cross, and who separately
verified the effect.

The buyer is an enterprise platform, security, compliance, or operations team running asynchronous agent fleets. The reference incident puts a €250,000 compliant supplier onboarding obligation at risk.

## Solution

Continuum treats succession as a governed lifecycle, not a restart. A persisted deadline monitor detects that required evidence did not arrive. A deterministic eligibility gate assesses multiple registry candidates using tenant, health, capability, memory scope, jurisdiction, contract profile, and trust constraints. Google ADK and Gemini 3.6 Flash then choose only from the eligible set and must cite the selected deployment evidence.

Deterministic policy validates that non-authoritative model choice, fences the old epoch, reconstructs the minimum authorized context, and sends one effect through the selected successor's identity. A separate read-only verifier recomputes the selection and context receipts, directly reads authority, compliance, and provider state, and alone may issue the sixth continuity attestation: VERIFIED, FAILED, or INCONCLUSIVE.

The selection record also names a deterministic comparison baseline, whether
Gemini deviated from it, the value at risk, and the applicable human-review
boundary. A production high-impact choice cannot proceed on model output alone;
the hackathon effect remains explicitly reversible and `SANDBOX_ONLY`.

## Why This Matters

The signature moment is simple: **the agent failed, but the organization's promise did not.** Continuum makes agent replacement safe enough to inspect, reproduce, and govern. It reduces the cost of abandoned work and duplicate actions while giving security and compliance teams a bounded claim they can verify independently.

Google Cloud is the reference deployment, not an adoption prerequisite. A cloud-neutral three-call SDK and credential-free local consumer show how an existing workflow can adopt the continuity contract without migrating its domain model.

## How We Used AI

- Google ADK invokes `gemini-3.6-flash` on Vertex AI inside the investigator service.
- Gemini receives only candidates that passed deterministic eligibility; rejected candidates never enter the prompt.
- Typed output requires the remediation, exact successor ID, objective, rationale, incident evidence IDs, and every candidate evidence citation.
- The model cannot grant authority or execute. Deterministic policy independently revalidates its choice and can hold or deny it before mutation.
- In the fresh cloud proof, Gemini selected warm v19 from eligible v18/v19 records through an explicit 18-second-recovery versus very-high-assurance trade-off; v20 was excluded for degraded health and wrong jurisdiction.
- After independent verification, Gemma 4 produced a five-citation resilience
  plan that deterministically admitted the exact Veo 3.1 Lite and Lyria 3 calls.
  Their digest-bound receipt and generated media are public at
  https://github.com/milos-plavsic/continuum/releases/tag/multimodal-proof-8bec862.
  The outputs are explicitly derivative and cannot become authority or evidence.

## How We Used Codex

Codex helped turn the product brief into a scope, PRD, technical spec, 59-item build checklist, implementation, adversarial tests, deployment automation, architecture diagram, and evidence-backed submission materials. It also drove fresh exact-commit cloud runs. Those runs exposed integration defects at canonicalization, context receipt, trace correlation, immutable fleet publication, provider reconciliation, credential formatting, and verifier projection boundaries. Each failed closed before unsupported proof, was fixed through a protected pull request with a regression test, and was redeployed before a new run was accepted.

No source was copied from prior projects or external contributor pull requests. Provenance is recorded in `docs/ORIGINALITY.md`.

## Key Features

- **Obligation continuity:** append-only commitments and explicit lifecycle transitions.
- **Missing-evidence detection:** a Cloud Tasks deadline detects silence; real Pub/Sub redelivery resumes work.
- **Bounded successor selection:** v18/v19/v20 registry assessment, deterministic pre-filter, typed evidence-cited Gemini choice.
- **Succession Protocol:** epoch CAS, predecessor fencing, separate successor identities, and idempotent roll-forward.
- **Raw-input defense and minimum context:** Google Model Armor blocks prompt injection before Gemini; two verified facts are included while secrets, unsupported inference, and revoked notes are excluded before retrieval.
- **Selected action gateway:** identity, epoch, policy, compliance, context receipt, request digest, and idempotency checked in one Firestore transaction.
- **Independent verification:** five control claims plus a verifier-only sixth artifact after direct read-only observations.
- **Verified Resilience Brief:** only a verifier-issued `VERIFIED` bundle can
  drive Gemma 4; deterministic citation admission then causally invokes Veo 3.1
  and Lyria 3 for content-addressed post-incident training media that is never
  authority or execution evidence.
- **Resilience lab:** ten distinct crash, retry, ambiguity, stale-message, citation, verifier, race, and partition fixtures with content-addressed results.
- **Portable adoption:** three-call cloud-neutral SDK, local credential-free consumer, and optional same-bundle witness aggregation.
- **Enterprise queue effect:** two deliveries reconcile to one reversible synthetic GitHub issue that the independent verifier reads directly.
- **Business-first cockpit:** obligation at risk, candidate decisions, transferred context, one external effect, and independent verdict in one judge path.

## Architecture

The operator makes one IAM-authenticated start against a private Cloud Run control service. Cloud Tasks crosses the real persisted deadline. Firestore records the event/projection/outbox transactionally, and Pub/Sub delivers the missing-event signal at least once with a deliberate first-delivery failure.

The control service resumes a Firestore-backed cross-department fleet catalog after a simulated 21-day dormancy, deterministically gates candidates, and invokes the private Google ADK/Gemini investigator. After choice validation, Firestore atomically advances authority from v17 to selected successor v19, excludes unauthorized context, verifies official GLEIF/VIES observations, and reconciles one synthetic GitHub work item. The private verifier has a distinct read-only service account, reads the external provider independently, and issues the final attestation. OpenTelemetry spans from all services are exported to Cloud Trace under one canonical trace ID.

Architecture diagram: `docs/diagrams/architecture.png` (source: `docs/diagrams/architecture.mmd`).

Reference stack: Google ADK, Gemini 3.6 Flash on Vertex AI, Gemma 4, Veo 3.1
Lite, Lyria 3, Cloud Run, Firestore, Pub/Sub, Cloud Tasks, Cloud Trace/OpenTelemetry,
Cloud Storage, Python/FastAPI, Pydantic, and Ed25519 contract support.

## Data Sources

- The successor registry's immutable deployment records: service endpoint,
  workload identity, image digest, health, capabilities, jurisdiction, contract
  profile, authorized scope, and trust score.
- Firestore append-only lifecycle events, projections, authority epochs,
  compliance evidence, context receipts, outbox/inbox delivery records, and the
  external-provider reconciliation record.
- Cloud Tasks deadline metadata and Pub/Sub message/delivery identity.
- Google ADK/Gemini request and typed response metadata from Vertex AI.
- Cloud Run service/revision identities and correlated OpenTelemetry spans read
  from the owning Google Cloud APIs.

The canonical demonstration uses a synthetic supplier and obligation, official
public GLEIF and EU VIES observations, and one synthetic GitHub issue; it does
not ingest personal data, confidential enterprise records, or a production
procurement system.

## Findings and Learnings

Persistence is not continuity: durable state can still preserve stale
authority, poisoned context, or a duplicated effect. The useful boundary is an
explicit contract that separates an obligation, model recommendation,
deterministic authority decision, execution receipt, and independent verdict.

We also learned that an LLM becomes more operationally credible when its choice
is causal but bounded. Gemini changes which eligible workload is activated, yet
cannot admit an ineligible candidate, grant itself authority, execute the
effect, or attest success. Finally, real cloud proof exposed integration defects
that deterministic local tests did not: wire canonicalization, a missing
context-receipt field, and duplicated trace-ID logic. Each failed closed and was
converted into a regression test before the accepted run.

## Why I Built It

I built Continuum because useful agents need more than intelligence;
institutions need continuity. I hope the Continuity Contract can become a
standard—and that it will yield when a demonstrably stronger standard earns the
right to succeed it. Even standards should have succession plans.

## Testing Instructions

Local deterministic proof requires Python 3.11+ and `uv`:

```bash
git clone https://github.com/milos-plavsic/continuum.git
cd continuum
./scripts/quality-gate.sh
PYTHONPATH=src python3 -m continuum --output artifacts/latest
python3 examples/local_sdk_consumer.py
```

The quality gate installs locked dependencies, executes 215 tests, enforces genuine 100.0% statement and branch coverage, runs C0–C6 conformance, and runs the release gate. The repository's GitHub Actions also builds and imports the locked non-root runtime image. Regular CI deliberately has no GCP credentials or billable cloud authority and uses deterministic provider ports/test doubles; it does not re-execute or prove the separate exact-commit live-GCP capture. The exact downloaded main-CI coverage packet—including XML, JSON, browsable HTML, complete source/measured inventories and nested checksums—is public at https://github.com/milos-plavsic/continuum/releases/tag/quality-proof-12e116b. Coverage proves measured execution, not semantic correctness, production fitness, complete threat coverage, live-cloud behavior, capture provenance, or uncompromised infrastructure.

The published cloud packet is first-party evidence. Its offline verifier checks integrity and declared semantic consistency, not capture provenance. A Sigstore keyless, identity-pinned external-witness workflow is available, but its current status is `AWAITING_EXTERNAL_WITNESS`; no independent external endorsement is claimed.

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

The accepted application commit is `d4d7d52`. Its exact-source proof is documented in `docs/CLOUD_PROOF.md`: 17 read-only objects, 174 correlated spans, and a network-free/credential-free offline semantic PASS. GLEIF was live; the unavailable VIES call used a transparently labelled, freshness-bound observation from a prior independently verified live run. The complete security-audited packet is publicly downloadable from the checksum-pinned `cloud-proof-d4d7d52` GitHub Release. The separate `multimodal-proof-8bec862` release publishes the exact Gemma/Veo/Lyria receipt and both generated assets with SHA-256 checksums.

## Hosted Project

A public, presentation-only Cloud Run showcase is deployed with a dedicated
no-role identity and no mutation surface. It links to the checksum-pinned proof
packet; the IAM-authenticated control plane and effect-bearing agents remain
private by design.

Hosted URL: https://continuum-showcase-rdzvxiysbq-ew.a.run.app

The live surface is revision `continuum-showcase-00006-drz`, pinned to source
commit `524194190d5360451e4784f48b14163e7bc6e5ee` and immutable image digest
`sha256:9d171a0451382b935c000ec9dc7d9db9629351fd29180c1e6984786487d2d17d`.

Judge-facing Devpost project page: https://devpost.com/software/continuum-lq35x2

## Public Repository Link

https://github.com/milos-plavsic/continuum

## Demo Video

TODO: add the final **public** YouTube/Vimeo URL after recording the live,
unedited, no-longer-than-four-minute run. Unlisted is not sufficient under the
host's final checklist.

Current replacement production: `docs/video/07_PROOF_FIRST_PRODUCTION.md`,
with the locked timed narration in `docs/video/08_PROOF_FIRST_SCRIPT.md` and
the capture/publication gate in `docs/video/09_PROOF_FIRST_RUNBOOK.md`.
The revised clean 3:54.04 local candidate has been rendered and accepted;
captions are ready at `docs/video/10_PROOF_FIRST_CAPTIONS.srt`. The public URL
remains deliberately unset until publication and hosted-playback verification.

## Screenshot Shot List

1. Cockpit hero: “The agent failed. The €250,000 promise did not.”
2. Candidate panel: v18/v19 eligible, v20 rejected, Gemini-selected v19 with citations and an explicit recovery/assurance trade-off.
3. Minimum-context receipt: two included, four excluded with reason codes.
4. Continuity proof: two Pub/Sub deliveries, one provider effect, v17 denied, verifier-issued artifact six.
5. Supplier decision pack: official GLEIF/VIES receipts, Gemini recommendation, deterministic sandbox admission.
6. Google Cloud evidence: five Cloud Run revisions/identities, 17-object offline PASS, and the exact 174-span Cloud Trace.

## Submission Readiness Notes

- Fortified Enterprise Fleet is the target category.
- Public repository, reproducible README, architecture PNG, exact cloud identifiers, and a downloadable offline-verifiable proof packet are ready.
- The Devpost project page is published as “Continuum” with the workflow-first description, technology stack, repository, and public proof-release links. Live `submitted_at` remains empty, so it is not yet a verified hackathon entry.
- Remaining required asset work: publish the accepted master publicly, upload
  the sidecar captions, verify hosted playback, and add its URL.
- The architecture asset is finalized at `docs/diagrams/architecture.png`; its required form upload and all drafted field answers will be applied with the final video submission because Devpost's submission API validates the complete form atomically.
- A 1920×1080, 25 fps, 3:54.04 H.264/AAC clean candidate has passed encoded-frame
  review for its metadata opening, click, successor selection, handoff,
  supplier, non-obscuring cut disclosures, effect, verifier, exact-release,
  architecture, all four derivative-proof stages, and metadata close.
  Its SHA-256 is
  `fb8795fdddf7bc5bac7314c94a5564e737bd761f5e947db08954e26d08395617`.
  The final URL remains intentionally unset until public playback is verified.

## Known Limitations

- The reference effect is a reversible synthetic GitHub work item, not a production procurement API transaction.
- The catalog spans bounded departmental publications and a 21-day dormant-resume fixture; it is not an unbounded global marketplace.
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
- **Hosted project (28088, optional):** https://continuum-showcase-rdzvxiysbq-ew.a.run.app
- **Private testing instructions (28090):** Use the release-scoped judge-run credential supplied only in this private field to trigger one bounded canonical cloud run, or run `./scripts/quality-gate.sh`; exact cloud proof, immutable identifiers, public packet URL, archive checksum, and credential-free verification command are in `docs/CLOUD_PROOF.md`.
- **Google SDK (28091):** Agent Development Kit (ADK)
- **Google Cloud service (28142):** Cloud Run (primary selection if the live field permits only one; the project also uses Firestore and Pub/Sub)
- **Architecture upload (28092):** `docs/diagrams/architecture.png`
- **Google AI models (28143):** Gemini 3.6 Flash via Vertex AI; Gemma 4 26B A4B
  IT (`gemma-4-26b-a4b-it-maas`); Veo 3.1 Lite
  (`veo-3.1-lite-generate-001`); Lyria 3 Clip Preview
  (`lyria-3-clip-preview`)
- **Demo video:** TODO URL
- **Optional public content (28106):** https://dev.to/milos-plavsic/the-agent-failed-the-promise-did-not-building-verifiable-agent-succession-oe4
- **Optional social post (28107):** https://www.linkedin.com/feed/update/urn:li:share:7498513309642616832/

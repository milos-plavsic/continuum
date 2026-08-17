# Build notes

## 2026-08-17

- Participant authorized all seven priority outcomes and autonomous execution.
- No deepening rounds; requirements were derived from the prior critical review.
- Selected a standard-library deterministic reference core to minimize setup risk.
- Chose epoch fencing, immutable manifests, optimistic versions, idempotent gateway,
  pre-retrieval authorization, append-only evidence, and roll-forward recovery.
- Work from three design agents was used as review input; all repository code and
  documentation in this build are newly authored for Continuum.
- Implemented nine automated tests covering the canonical flow, negative causal
  controls, deterministic replay, fencing, tenant isolation, memory pre-filtering,
  idempotency conflicts, and manifest exclusions.
- Ran 22 evaluation scenarios: canonical, benign silence, and 20 exact replays.
  Observed zero duplicate effects, zero benign-silence quarantines, zero revoked
  candidates exposed, and zero replay divergence.
- Cloud Run, Firestore, Pub/Sub, Vertex AI/ADK, and Cloud Trace evidence remains a
  deliberately visible deployment gate; no local simulation is labeled cloud proof.

## Continuity Contract round

- Locked the north star as an open succession and continuity protocol proposal.
- Added all six portable artifacts, strict envelopes, golden canonical vector,
  domain-separated digests, optional Ed25519 content signatures, and independent
  attestation-chain verification.
- Corrected registry activation scope, duplicate event conflict handling, event
  sequence verification, and restart-safe provider reconciliation.
- Added a 21-case cumulative C0–C6 `reference-local` conformance profile with
  explicit boundary claims and non-claims. It does not assert Google Cloud,
  live-model, external trust-anchor, or third-party interoperability conformance.
- Strengthened weak certification edges with an actual SQLite crash/restart
  succession journal, competing-successor admission, grant expiry/purpose checks,
  and fabricated-citation rejection.
- Added the Google reference binding: an ADK Investigator using Gemini 3.6 Flash,
  transactional Firestore event/projection/outbox adapter, canonical Pub/Sub
  publisher, and Cloud Run ID-token verifier. These adapters are implemented but
  their cloud profile remains unassessed until deployed evidence exists.

## Incident cockpit round

- Added a same-origin FastAPI control plane and a no-build vanilla incident
  cockpit for the signature moment.
- The UI reads server-produced evidence and exposes live predecessor action,
  predecessor memory, redelivery, and contract-bundle proof controls.
- Added fail-closed demo-mode gating, health/build metadata, API tests, a locked
  `uv` environment, and a non-root Cloud Run-compatible container image.
- Verified 20 tests, a real Uvicorn HTTP smoke run, Docker build, and container
  health response. Cloud IAM and deployed evidence remain separate gates.

## Google Cloud proof extension

- Added Firestore-backed execution and outbox leases, stale-worker fencing,
  UNKNOWN-to-reconciliation handling, retry scheduling, and inbox substitution
  detection. The declared guarantee remains bounded to reconcilable adapters.
- Tightened Pub/Sub ingestion around exact subscription, canonical payload,
  matching attributes, and verified push identity before any inbox mutation.
- Added workload-derived agent identity, a lazy live Google ADK/Gemini path,
  non-authoritative typed proposals, and a separate verifier-role endpoint that
  recomputes contract linkage under its own workload identity.
- Replaced presence-only evidence checks with semantic offline predicates for
  Cloud Run, Firestore, Pub/Sub redelivery, Vertex AI, trace continuity, and the
  contract export. Complete golden evidence passes; absence stays NOT_ASSESSED;
  contradictions and content mutation fail.
- Added a temporary-capture, content-addressed bundle packager and wired the
  full Pub/Sub subscription resource into deployment. Verified 40 tests before
  final integration, shell syntax, compilation, secret patterns, and a complete
  container build. No live Google Cloud evidence is claimed without deployment.

## Deployment-complete vertical slice

- Added a server-owned, resumable cloud scenario with Firestore phase CAS and
  append-only observations. The public command accepts only a run identifier;
  evidence, model proposal, policy, authority, provider state, artifacts, and
  verification are obtained from configured production ports.
- Wired the production composition to immutable canonical incident events,
  authenticated v18 ADK/Gemini investigation, persisted epoch fencing, an
  idempotent Firestore sandbox provider with read reconciliation, six observed
  contract artifacts, and an independently authenticated verifier service.
- Added deliberate Pub/Sub redelivery for one marked lifecycle event, durable
  inbox deduplication, and structured exact-run evidence records. The collector
  retries boundedly for asynchronous logs, packages only the 12 mandatory
  objects, and the offline verifier recomputes the full six-artifact bundle.
- Hardened deployment with digest pinning, exact private invocation policies,
  a validated single operator principal, scoped verifier read access, OIDC push
  identity, fail-closed readiness, and correlated run/trace metadata.
- Added one-command local and cloud proof entry points plus an explicit claim
  matrix. Local verification can complete without credentials; cloud PASS still
  requires an authenticated project because this workspace has no `gcloud`
  installation or configured Google Cloud account.

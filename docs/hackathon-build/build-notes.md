# Build notes

## Standards-readiness hardening — August 27

- Moved incident classification and the allowed-remediation set entirely out of
  Gemini into versioned deterministic policy receipts. ADK now receives policy
  output, never natural-language policy authority.
- Added a closed Evidence Descriptor 1 schema, golden vector, trust/freshness
  evaluation and verifier-side recomputation of the complete exported chain.
- Added a second service-remediation domain, a barrier-synchronized 128-attempt
  contention proof, and a complete credential-free local lifecycle/container.
- Bounded Google ADK, rebuilt the image as non-root multi-stage targets, and
  added pinned SPDX SBOM plus actionable HIGH/CRITICAL vulnerability gates.
- Protected PRs #34–#36 passed both required checks. The final gate ran 181
  tests at genuine 100.0% statement/branch coverage, plus conformance, release,
  locked-image, SBOM and HIGH/CRITICAL vulnerability gates.
- Exact application source `a1e00ac188c5597150fb7c6de142224d086c4995`
  was deployed as image
  `sha256:608e941c082a7d675db8ccf0d9bd9807026437958a91affd473abfbdef44c996`.
  Fresh run `standards-a1e00ac-20260827T163808Z` reached independent
  `VERIFIED`; all 15 mandatory objects and 89 correlated spans were captured.
- The credential-free offline verifier returned `PASS` for bundle
  `urn:uuid:b23e074f-4441-4e69-9b33-f12ebb316c5b`, and Google's Hosted Worker
  DSSE signature independently returned `Verified OK`. The checksummed packet
  is public as release `cloud-proof-a1e00ac`; capture provenance remains
  explicitly outside the offline verifier's claim.
- The separate no-role public showcase was advanced to revision
  `continuum-showcase-00003-rql` and now links that exact packet; a live
  mutation probe returned `404` and the showcase identity has no project role.

## Practical-agent golden cloud proof — August 27

- Protected PRs #21 and #22 added the practical Supplier Assurance & Onboarding
  Agent and made its exact-run decision evidence mandatory; GitHub CI and the
  local release gate passed 159 tests at genuine 100.0% statement/branch coverage.
- Exact application source `5e579f4cdcb3b85d07f6e80fc6ff825dd85da463` was deployed across
  five private, identity-separated Cloud Run services on image digest
  `sha256:f83ba3d1e9405fdece32f1fbe064a70c0dc9b92cb681475f7f7730d24b7e9328`.
- Fresh run `supplier-slsa-20260827T142325Z` completed autonomously: official
  GLEIF and EU VIES observations fed an ADK + Gemini 3.6 decision pack,
  deterministic policy admitted it only for `SANDBOX_ONLY`, v18 executed once
  despite two Pub/Sub deliveries, v17 stayed fenced, and the verifier alone
  issued the sixth artifact.
- Read-only capture produced 15 content-addressed mandatory objects and 124
  exact-trace spans. The network-free, credential-free verifier returned `PASS`
  for bundle `urn:uuid:10271531-a3fc-42f3-baa3-87c753ef113b`; the packet is
  published as the `cloud-proof-5e579f4` GitHub Release. The 15th mandatory
  object is the Google-signed SLSA v1 build statement bound to all five
  revision image digests; the manual-upload source-provenance limit is explicit.

## Golden cloud proof — August 26

- PRs #6–#9 passed protected-branch coverage/release and reproducible-image
  checks before merge. Two real integration mismatches and one proof-query drift
  were discovered by fresh cloud runs, fixed with regression tests, and never
  relabelled as successful evidence.
- Exact source `0ceda492a439466bef4536f695f86d2a7b8f01e4` was deployed across
  five private, identity-separated Cloud Run services on image digest
  `sha256:ddc57999674ec755ffc92a9c004d7265ada06ff56424f9ee46121c7b511a7b96`.
- Fresh run `golden-0ceda49-20260826-182725` reached independent `VERIFIED`:
  Gemini selected deployable v18 from eligible v18/v19 candidates, v20 was
  rejected, two facts crossed, four context classes were excluded, v17 was
  denied, and two Pub/Sub deliveries produced one provider effect.
- Read-only capture produced 13 content-addressed objects and 104 exact-trace
  spans. The network-free, credential-free verifier returned `PASS` for bundle
  `urn:uuid:be58870d-6398-4bf5-a1a2-90dc3eca3e86`. A security-audited packet
  with nested checksums is prepared as the `cloud-proof-0ceda49` release asset.

## Golden-standard extension — August 26

- The participant explicitly authorized full autonomous implementation beyond the
  prior scope wherever it measurably improves winning probability.
- The remaining critical risks were translated into items 33–42: dynamic bounded
  successor selection, minimum-context reconstruction, migration-free adoption,
  resilience evidence, optional independent witnesses, and a business-first demo.
- Planning mode remains autonomous, with automated verification and commentary
  checkpoints rather than manual look-at-it pauses. The signature line is:
  “The agent failed, but the organization’s promise did not.”
- No deepening interview was necessary because the participant had already directed
  the exact quality bar and authorized the expanded winning scope.
- Implemented three candidate records and a content-addressed deterministic gate;
  v18 and v19 are eligible and separately routable, while v20 is rejected before
  the model for health and jurisdiction.
- Gemini's typed output now includes an exact successor and candidate citations.
  The lifecycle stores that choice, activates it, and routes effects through its
  distinct Cloud Run identity; invalid choices do not reach policy or mutation.
- Added a reconstruction receipt with two canonical included facts and four
  excluded context classes. The independent verifier recomputes both selection
  and reconstruction receipt digests from the manifest.
- Added a cloud-neutral SDK/local consumer, ten-case resilience lab, optional
  same-bundle witness aggregation, quantified cockpit, and updated architecture.
- Verification checkpoint: 136 tests, genuine 100.0% statement/branch coverage,
  C0–C6 conformance, release gate PASS, shell/compile checks, and a successful
  non-root production image build/import smoke. Item 42 remains the live gate.

## August 26 winner-hardening release proof

- GitHub Actions passed the genuine 100.0% statement/branch gate, all 124 tests,
  C0–C6 conformance, release checks, clean-tree/credential audit, and locked
  non-root container build.
- Deployed source `501a80ce50496a39cc822a69fc73ec7d44267dbd` as four private,
  identity-separated Cloud Run services on image digest
  `sha256:4c538b4cd6e9f86323913f017bdf21fc5a80c07968104c798b9b67ce662706e7`.
- Fresh run `run-20260826T021240Z` was driven by Cloud Tasks and real Pub/Sub
  redelivery, invoked ADK + `gemini-3.6-flash`, denied v17, executed one v18
  effect, and received the verifier-only sixth artifact.
- Read-only collection captured all 12 mandatory objects and 63 Cloud Trace API
  spans. Offline verification returned PASS for bundle
  `urn:uuid:5ac2c145-e8b1-4e19-a468-6d71f3c27430`.

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
- Historical checkpoint: ran 22 evaluation scenarios under the earlier suite.
  The current report executes all eight signal combinations, five deterministic
  replays, and every C0–C6 conformance case, recording actual inputs and outputs.
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
  idempotent Firestore sandbox provider with read reconciliation, five observed
  contract artifacts, and an independently authenticated verifier service.
- Added deliberate Pub/Sub redelivery for one marked lifecycle event, durable
  inbox deduplication, and structured exact-run evidence records. The collector
  retries boundedly for asynchronous logs, packages only the 12 mandatory
  pre-attestation objects; the independent verifier authors artifact six only
  after direct reads, and the offline verifier recomputes the final bundle.
- Hardened deployment with digest pinning, exact private invocation policies,
  a validated single operator principal, scoped verifier read access, OIDC push
  identity, fail-closed readiness, and correlated run/trace metadata.
- Added one-command local and cloud proof entry points plus an explicit claim
  matrix. Local verification can complete without credentials; cloud PASS still
  requires an authenticated project because this workspace has no `gcloud`
  installation or configured Google Cloud account.

## Release recapture hardening

- A live at-least-once delivery produced three legitimate attempts and exposed
  that a changing aggregate log could yield conflicting evidence objects. The
  run correctly remained `NOT_ASSESSED`; no favorable observation was selected.
- Added a Firestore-transactional, one-time redelivery evidence claim. Any
  number of retries remains deduplicated while exactly one immutable observation
  proves at least two attempts. Added repeated-delivery and defensive-path tests.
- Made the Google binding test doubles self-contained so identity-token tests
  no longer depend on suite import order. The full production source remains
  subject to genuine 100% line and branch coverage before cloud deployment.

## Winner-hardening plan

- The participant explicitly authorized every item from the skeptical winning
  review plus mandatory CI and a production-grade independent verifier.
- Planning remains autonomous with automated checkpoints and no manual pause.
  The signature moment is one operator start followed by real deadline detection,
  compliance remediation, succession, stale-agent denial, redelivery-safe effect,
  and verifier-issued attestation.
- PR #5 by `phahim1` was reviewed as comparative design input only. No source was
  copied or merged. Continuum's new verifier will be authored independently and
  integrated with the current five-artifact/provider/authority cloud boundary.

## Winner-hardening implementation checkpoint — August 26

- Fresh, bound compliance evidence is now a hard gateway prerequisite.
- Cloud Tasks owns the delayed Sentinel callback; Pub/Sub redelivery causally
  resumes the effect-bearing lifecycle.
- v18 owns a Firestore transaction that jointly checks action input, authority
  epoch, policy, compliance binding and idempotency.
- Control exports five claims. The original read-only verifier directly reads
  authority, compliance and provider state and alone issues artifact six.
- Gemini recommends one bounded action; deterministic admission of that action
  changes the next permitted transition without granting model authority.
- Synthetic trace evidence was removed. Real OpenTelemetry spans export to
  Cloud Trace and capture reads the exact trace from the owning API.
- A one-click cockpit, pinned least-privilege CI, distinct measured cases and
  succession-first narrative are implemented.
- Local gate checkpoint: 124 tests, genuine 100.0% statement/branch coverage,
  and release gate PASS.
- External gates remain: final push and green CI, exact-commit deployment,
  fresh autonomous cloud run, direct evidence recapture and rehearsal.

## Public judge surface — August 26

- Added a sixth, independently deployed read-only showcase; it does not alter
  or redeploy the five private canonical services or their accepted proof.
- Cloud Run revision `continuum-showcase-00001-z9j` runs exact source commit
  `b00866f90353bc936fde5c4799e2ba5fba99cb81` at immutable image digest
  `sha256:3ba085bd39f147bef5d9e7bbdea9ea7513913e14e9ad401f26c19cbbab0bb0bb`.
- Live probes returned `200` only for the showcase and health/build metadata;
  docs, OpenAPI, cloud-smoke, and internal verifier routes returned `404`.
- The dedicated identity has no project role. Only this service has the
  intentional public `roles/run.invoker` binding.
- PR #15 merged four green CI checks after 140 tests, genuine 100.0% statement
  and branch coverage, conformance C0–C6, release-gate PASS, and a reproducible
  runtime-image build.

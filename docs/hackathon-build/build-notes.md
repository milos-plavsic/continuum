# Build notes

## Final auditability and rollback plan — August 28

- The participant requested every improvement from the release-PR critique while
  explicitly preserving the complete technical architecture.
- Items 67–70 add durable source-complete coverage evidence, an append-only failed-run
  ledger with functional PR lineage, a plain-language no-role blast-radius proof and an
  explicit-target rollback that is dry-run by default and verifies security after apply.
- This is a proof-surface and operations hardening round. It does not remove, simplify or
  replace any lifecycle, verifier, fleet, model, observability or multimodal capability.
- The first complete local gate still ran all 215 tests at 100.0% statement and branch
  coverage. Its new packet enumerated all 39 `src/continuum` modules, 4,152/4,152
  statements and 1,154/1,154 branches. An initial metadata-only defect counted 162 tests
  because an executed script lacked the repository root on `sys.path`; it did not affect
  coverage or the test run, and the packager now fails on discovery errors and reports 215.
- Both rollback targets passed read-only GCP preflight. A live reversible drill moved
  100% traffic from `continuum-showcase-00006-drz` to `00005-bg9`, verified the exact
  served revision, mutation `404`, exact public service policy and zero project roles,
  then restored `00006-drz` and independently repeated every postcondition. Both local
  receipts are generated cloud state and remain ignored.
- The first downloaded main-CI coverage artifact exposed that GitHub's artifact action
  omits hidden files by default: Coverage.py's generated `html/.gitignore` was present in
  `SHA256SUMS` but absent from the download. The provisional release had zero downloads
  and was immediately removed rather than mislabeled as proof. CI now explicitly includes
  hidden files; publication must repeat from a green exact-commit run and pass every nested
  checksum after download before a durable release is created.
- PRs #56 and #57 passed protected CI and merged. Exact main run `33125745852`
  uploaded the corrected complete packet; every nested checksum passed after download.
  The deterministic archive is public as `quality-proof-12e116b`, with SHA-256
  `192a0668c4176f81380aecf54daad2b3da67cd753480b00cf2c0d40e0e95cd76`.
  Items 67–70 are complete; no product capability or current cloud-proof fact changed.

## Submission hardening checkpoint — August 27

- Added a quota-bound, expiring-capability judge gateway with no arbitrary
  command surface.
- Added Google Model Armor fail-closed raw-input screening, cross-department
  Firestore fleet discovery, a real two-candidate Gemini recovery/assurance
  trade-off, and a 21-day dormant-resume proof.
- Added an idempotent, reversible GitHub Issues work-queue adapter; live provider
  evidence remains gated on deployment in checklist item 56.
- Added an independent TypeScript consumer, sparse judge architecture, and a
  machine-audited release-truth manifest.
- Complete gate: 201 tests, genuine 100.0% statement and branch coverage,
  TypeScript interop, C0–C6 conformance, and release gate all PASS.

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

## Submission-truth and fleet-utility hardening — August 27

- The participant explicitly authorized every non-video correction from the fierce
  judge review. Video production is deliberately deferred until the new release truth
  and fresh cloud run exist.
- The autonomous checklist now covers a single release manifest, bounded judge access,
  a genuine Gemini trade-off, cross-department fleet discovery, dormant recovery,
  Google Model Armor on raw input, a reversible external work-queue effect,
  independent-language interoperability, and a sparse judge diagram.
- Scope remains one supplier-succession lifecycle. The additions deepen the same
  obligation rather than create a second live demo or generic fleet product.
- Item 51 established `docs/submission/current-release.json` as the only mutable
  release-fact source and added a release-gate audit over README, Devpost draft,
  compliance matrix and public showcase. The audit rejects every known superseded
  run/count/revision marker; mutation and repository tests pass.

## Canonical non-video release — August 27

- Application commit `0d8233695eeae0980088f3209f531181852a4a60` was built once
  as image digest
  `sha256:c54bfc0b6baa85291fcecfc643641fe59972dc33806d75917dd21ae33fc4a010`
  and deployed to all five private roles with distinct workload identities.
- Fresh run `judge-devpost26-0d823369-ce4b14a8e848` completed the full supplier
  lifecycle. Gemini selected warm successor v19 through an explicit
  recovery-time versus assurance trade-off; v20 failed the deterministic gate.
- Google Model Armor stopped the raw injection before model access. Two Pub/Sub
  deliveries reconciled to one reversible GitHub issue, and the read-only
  verifier independently observed that provider state before issuing `VERIFIED`.
- The public `cloud-proof-0d823369` release contains 17 mandatory objects and 43
  correlated Cloud Trace spans. Its network-free, credential-free verifier
  returned `PASS`; capture provenance remains explicitly outside that offline
  verdict.
- The locked local gate passed 201 tests at genuine 100.0% statement and branch
  coverage. Video production remains intentionally deferred.
- PR #49 passed both protected CI workflows and merged as `3e41cce`. The public
  no-role showcase was rebuilt from that exact source as revision
  `continuum-showcase-00005-bg9`, and live read-back confirmed the current v19,
  Model Armor, GitHub queue and proof facts.
- Devpost project version 6 was updated and read back through the authenticated
  API. It contains the same application commit, 17-object/43-span proof, 201-test
  gate, v19 trade-off, Model Armor receipt, GitHub Issue #41 and proof release;
  the video remains unset and the hackathon submission remains a draft.

## External resilience and positioning plan — August 27

- The participant explicitly requested every improvement from the latest skeptical
  review while preserving the complete technical architecture and named services.
- Items 60–66 add bounded official-registry access, freshness-bound durable fallback,
  a workflow-engine companion bridge, model-selection governance, explicit trust
  assumptions, layered judge language and a fresh exact-release proof.
- Technical depth is not being reduced. The presentation boundary will become simpler
  while the full protocol, verifier, observability, supply-chain and multimodal branches
  remain available as secondary evidence.
- Items 60–65 are complete. GLEIF/VIES use bounded retry budgets and a freshness-
  and identity-bound Firestore cache; outages become persisted HOLDs before Gemini
  or mutation. The cloud-neutral workflow bridge, model baseline/deviation/approval
  receipt, independent recomputation, trust profile, proof ceiling, and layered
  README/showcase framing are implemented.
- The full gate now executes 215 Python tests plus the cross-language suite at
  genuine 100.0% statement and branch coverage. Item 66 remains active: protected
  merge, exact-commit deployment, fresh proof, release/showcase/Devpost truth sync.
  Video remains deliberately deferred.
- The first post-merge cloud attempt `judge-final-ec17dcc-20260827T215707Z`
  stopped safely at `CONTEXT_RECONSTRUCTED`: GLEIF produced a LIVE cached record,
  while VIES returned its structured `MS_UNAVAILABLE` outage response. That response
  exposed one remaining semantic-error path still expressed as a raw `ValueError`.
  No compliance record, provider effect, contract, or attestation was issued.
- The follow-up hotfix classifies VIES semantic availability codes, retries transient
  codes inside the same wall-clock budget, and converts exhaustion to the normal
  pre-model HOLD. Malformed GLEIF/VIES payloads now share the stable external-tool
  taxonomy. Regression tests preserve the observed outage shape.
- The next exact-commit run `judge-final-9de7d14-20260827T221526Z` completed the
  governed lifecycle internally but was correctly rated `NOT_ASSESSED` by the
  offline verifier because the deployment had not enabled the mandatory external
  GitHub work queue. Sixteen objects were captured; no external-work-item was
  invented or substituted with the Firestore sandbox projection.
- After enabling the pre-provisioned reversible GitHub Issue #41, run
  `judge-final-github-9de7d14-20260827T223000Z` reached verified compliance and
  fenced/activated v19 but stopped before the effect. A CLI-fed Secret Manager
  value retained its terminal newline, producing a rejected bearer header and
  repeated 409 responses. The adapter now normalizes surrounding secret whitespace,
  rejects embedded whitespace at configuration time, and regression-tests the exact
  Authorization header before another fresh run is attempted.
- Application commit `d4d7d52e56c3d3c123a708a279be6bda7189e647` was then built
  as Google-signed image digest
  `sha256:4c4b63c7ddaa9a77b26856cc5e99beae9531dac9aff92aac4d773d79b00aa595`
  and deployed across all five private workload identities.
- Fresh run `judge-final-d4d7d52-20260827T223700Z` reached independent
  `VERIFIED`. The packet has all 17 mandatory objects and 174 correlated Cloud
  Trace spans. GLEIF was `LIVE`; VIES was transparently
  `CACHED_WITHIN_POLICY` from a still-fresh observation bound to the prior
  independently verified attestation. Two Pub/Sub deliveries converged on one
  reversible GitHub Issue #41 effect, v17 action and memory were denied, and the
  independently recomputed selection-governance receipt approved the sandbox
  deviation from deterministic baseline v18 to warm v19.
- Credential-free/network-free offline verification returned `PASS` with report
  digest `sha256:405be9a12df92369488b1a5da2b1f592a6eb9e9e962df23df2d1bc50bd7a5401`.
  Public release `cloud-proof-d4d7d52` is archive-pinned at
  `14d2005d1a1360528e2ae84ad72c485ff92963a5ecd9e48121cd56edf790d3f6`.
- Devpost project version 7 was updated and read back with the exact application,
  proof, availability modes, workflow companion, trust ceiling and 215-test gate;
  video and formal submission remain unset. The no-role public showcase was
  redeployed as `continuum-showcase-00006-drz` from source `5241941`; live
  read-back matched the release, mutation returned `404`, and its identity has no
  project role. Item 66 is complete; video remains deliberately deferred.

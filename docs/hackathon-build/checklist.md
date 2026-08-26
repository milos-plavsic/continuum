# Autonomous build checklist

Mode: autonomous  
Verification pauses: none; run automated checks after each cohesive batch  
Git cadence: no commits without participant request  
Wow moment: retired v17 is denied twice while v18 produces one externally observed effect under the declared failure model

- [x] **1. Freeze succession protocol**
  Spec ref: `spec.md > Contracts`
  What to build: State machines, manifest, fencing, failure recovery, bounded guarantee.
  Acceptance: Ordering and guarantees are precise and auditable.
  Verify: Cross-check protocol invariants against architecture and tests.
- [x] **2. Define fixture and threat model**
  Spec ref: `spec.md > Canonical flow`
  What to build: Canonical incident, negative controls, threat/failure matrix.
  Acceptance: Missing evidence alone never causes quarantine.
  Verify: Policy unit tests.
- [x] **3. Implement event and registry primitives**
  Spec ref: `spec.md > Architecture`
  What to build: Canonical events, registry projection, lineage, epochs.
  Acceptance: Versions are immutable and only one is active.
  Verify: Registry and integrity tests.
- [x] **4. Implement governed boundaries**
  Spec ref: `spec.md > Contracts`
  What to build: Action gateway, persistent sandbox adapter, memory pre-filter.
  Acceptance: Duplicate effect is one; stale and revoked callers are denied.
  Verify: Gateway tests.
- [x] **5. Implement succession scenario**
  Spec ref: `spec.md > Canonical flow`
  What to build: Complete deterministic orchestration and evidence timeline.
  Acceptance: Obligation is discharged by v18 with linked evidence.
  Verify: Golden scenario test and CLI run.
- [x] **6. Build evaluation report**
  Spec ref: `spec.md > Verification`
  What to build: Evaluation cases, metrics, explicit not-yet-run cloud checks.
  Acceptance: Claims distinguish observed local evidence from planned cloud evidence.
  Verify: Full test suite and report generation.
- [x] **7. Build judge-facing artifacts**
  Spec ref: `prd.md > Acceptance outcomes`
  What to build: Incident view, architecture diagram, 240-second storyboard, cloud proof plan.
  Acceptance: All seven requested deliverables are reproducible from README.
  Verify: Generate artifacts and inspect links/output.
- [x] **8. Devpost handoff readiness**
  Spec ref: `prd.md > User and outcome`
  What to build: Reproducible setup, provenance update, state/build notes.
  Acceptance: Clean test run and no secrets/generated cloud state.
  Verify: `python -m unittest discover -s tests -v` and repository audit.

## Continuity Contract extension — autonomous

- [x] **9. Freeze the protocol proposal**
  Spec ref: `spec.md > Continuity Contract extension`
  What to build: Normative positioning, envelope, six artifact semantics, authority model, compatibility, and non-claims.
  Acceptance: Vendor-neutral contract is separate from the Google reference binding.
  Verify: Protocol tests and document audit.
- [x] **10. Implement portable artifacts and signatures**
  Spec ref: `spec.md > Continuity Contract extension`
  What to build: Strict canonical subset, domain-separated digests, builders, validators, references, Ed25519 adapter.
  Acceptance: Mutation/key substitution/unknown features fail closed.
  Verify: Contract unit tests and golden vector.
- [x] **11. Implement independent attestation**
  Spec ref: `spec.md > Continuity Contract extension`
  What to build: Provider receipt, revocation proof, bundle resolver, independent verification, executor exclusion.
  Acceptance: Complete chain verifies; missing/altered/self-issued chain fails.
  Verify: C6 conformance cases.
- [x] **12. Implement cumulative conformance**
  Spec ref: `spec.md > Continuity Contract extension`
  What to build: Isolated C0–C6 runner, report schema/digest, claims and non-claims.
  Acceptance: All 21 declared local cases pass without importing cloud/live-model evidence.
  Verify: `python3 scripts/run_conformance.py`.

## Google Cloud proof extension — autonomous

- [x] **13. Make cloud delivery and execution durable**
  What to build: transactional leases, outbox retries, inbox dedupe, execution reconciliation.
  Acceptance: crash/redelivery/concurrency tests prove one provider effect under the declared adapter contract.
  Verify: focused Google binding tests.
- [x] **14. Implement authenticated cloud orchestration**
  What to build: workload-derived agent identity, strict Pub/Sub envelope validation, live ADK investigation path, and separately authorized verifier role.
  Acceptance: caller-supplied identity cannot alter authority; malformed evidence fails before mutation.
  Verify: cloud API tests with injected token/model/provider adapters.
- [x] **15. Implement semantic offline cloud verification**
  What to build: content-addressed bundle checks for Cloud Run, Firestore, Pub/Sub, Vertex, trace, identity, and contract evidence.
  Acceptance: complete golden evidence passes; absence is NOT_ASSESSED; contradictions and mutations fail.
  Verify: offline verifier fixture tests with network and credentials unavailable.
- [x] **16. Close the reproducible cloud-proof loop**
  What to build: collector/runbook/deployment wiring and adapter-level end-to-end smoke fixture.
  Acceptance: clean checkout can deploy or produce an honest NOT_ASSESSED report without fabricated cloud state.
  Verify: full tests, container smoke, shell validation, secret audit.

## Deployment-complete vertical slice — autonomous

- [x] **17. Implement the durable cloud scenario service**
  What to build: control commands that persist the canonical lifecycle, invoke the live investigator, enforce predecessor denials, execute/reconcile the successor effect, and request independent verification.
  Acceptance: one run produces linked Firestore/provider/contract observations without client-authored success fields.
  Verify: black-box service tests over injected durable ports.
- [x] **18. Implement complete evidence capture**
  What to build: read-only collector for the exact run's Cloud Run, Firestore, Pub/Sub/log, Vertex, trace, identity, build, and contract objects.
  Acceptance: collector output maps directly to all semantic verifier predicates; partial capture remains NOT_ASSESSED.
  Verify: command-construction and content-addressed packaging tests.
- [x] **19. Lock deployment security and observability**
  What to build: narrow service invocation bindings, verifier read-only access, structured trace/run correlation, readiness, and immutable deployment metadata.
  Acceptance: no public service, key file, request-trusted identity, or executor self-verification path.
  Verify: deployment-script static tests and API security tests.
- [x] **20. Release-grade verification and handoff**
  What to build: one-command local proof, one-command cloud run/capture/verify flow, complete runbook, provenance/build notes, and claim matrix.
  Acceptance: clean test/container/audit run and explicit external deployment prerequisite only.
  Verify: full suite plus generated local artifacts and clean Git state after commit.

## Winner-hardening release — autonomous

- [x] **21. Correct the obligation and remediation semantics**
  Spec ref: `spec.md > Winner-hardening release`
  What to build: Make fresh compliance acquisition and validation a prerequisite to vendor creation and attestation.
  Acceptance: Missing or invalid compliance evidence cannot discharge onboarding; escalation remains safe.
  Verify: canonical, missing, invalid, and stale compliance tests.
- [ ] **22. Implement a real temporal Negative Space Sentinel**
  Spec ref: `spec.md > Winner-hardening release`
  What to build: Persist deadlines and expected evidence; add an idempotent scheduler tick that observes absence after real time.
  Acceptance: scenario start cannot author `expectation.missed`; early and duplicate ticks are harmless.
  Verify: virtual-clock unit tests and deployed Cloud Scheduler invocation proof.
- [x] **23. Make the Google lifecycle literally event driven**
  Spec ref: `spec.md > Winner-hardening release`
  What to build: Use transactional event/projection/outbox persistence and let Pub/Sub delivery advance the effect-bearing workflow.
  Acceptance: a duplicate delivered message reaches the same transition and produces one provider effect.
  Verify: crash, retry, redelivery, and direct Firestore state tests.
- [x] **24. Centralize transactional authority enforcement**
  Spec ref: `spec.md > Winner-hardening release`
  What to build: One gateway CAS over tenant/authority domain with workload-derived principal and full execution preconditions.
  Acceptance: v17 receives `STALE_EPOCH`; v18 succeeds; races and forged identities fail closed.
  Verify: gateway concurrency and authenticated black-box tests.
- [x] **25. Implement the independent Verification Engine**
  Spec ref: `spec.md > Winner-hardening release`
  What to build: Original read-only engine that verifies five input artifacts and provider/authority/compliance state, then issues the sole attestation.
  Acceptance: control cannot pre-author attestation; verdicts are VERIFIED, FAILED, or INCONCLUSIVE; all digests and observations are independently recomputed.
  Verify: mutation, omission, expiry, signer separation, replay, and read-only integration tests.
- [x] **26. Make Gemini causally useful but non-authoritative**
  Spec ref: `spec.md > Winner-hardening release`
  What to build: Bounded remediation-plan schema, citation validation, deterministic admission, and explicit HOLD paths.
  Acceptance: selected plan changes the permitted next transition; fabricated citations and unsupported plans cannot mutate state.
  Verify: model-output ablation and policy tests.
- [ ] **27. Replace synthetic observability with owned evidence**
  Spec ref: `spec.md > Winner-hardening release`
  What to build: Real OpenTelemetry spans and direct Firestore/Trace collection with precise source-authority labels.
  Acceptance: trace and state are retrieved from owning Google APIs for the exact run and revision.
  Verify: collector provenance tests and a live correlated trace capture.
- [x] **28. Build the one-click cloud cockpit**
  Spec ref: `spec.md > Winner-hardening release`
  What to build: Cloud-backed asynchronous start/status UI showing each autonomous phase and signature proof without additional action buttons.
  Acceptance: one start visibly reaches attestation while showing compliance, denials, deliveries, and one effect.
  Verify: browser smoke plus API phase-progression tests.
- [x] **29. Execute a truthful adversarial evaluation matrix**
  Spec ref: `spec.md > Winner-hardening release`
  What to build: Distinct runnable cases for silence, bad citations, competing successors, provider ambiguity, expiry, races, duplicates, and verifier disagreement.
  Acceptance: report contains actual per-case inputs/outcomes and no duplicated fixture labels.
  Verify: regenerate report and independently compare case digests.
- [ ] **30. Enforce continuous verification in GitHub Actions**
  Spec ref: `spec.md > Winner-hardening release`
  What to build: Least-privilege pinned workflow for locked quality, conformance, release, syntax, secret, and container gates with concurrency cancellation.
  Acceptance: every PR and main push runs; workflow has read-only default permissions and no cloud credentials.
  Verify: local workflow audit, commit/push, and successful GitHub check run.
- [x] **31. Simplify and synchronize judge-facing claims**
  Spec ref: `spec.md > Winner-hardening release`
  What to build: Succession-first README, rubric map, explicit limitations, current diagram, executable demo story, and sanitized evidence publication plan.
  Acceptance: no stale run, unsupported Foundry headline, or inaccessible proof is presented as current.
  Verify: claims-to-evidence audit against exact release metadata.
- [ ] **32. Deploy, recapture, and prepare the Devpost handoff**
  Spec ref: `prd.md > Acceptance outcomes`
  What to build: Deploy exact final commit, run the one-touch scenario, capture owned evidence, publish a sanitized bundle, and freeze the four-minute narrative.
  Acceptance: source, image, services, run, bundle, CI and judge links all agree and independently verify.
  Verify: live unedited rehearsal, offline PASS, green required CI, and clean Git state.

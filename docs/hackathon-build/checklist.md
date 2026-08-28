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
  Verify: `uv run python scripts/run_conformance.py`.

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
- [x] **22. Implement a real temporal Negative Space Sentinel**
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
- [x] **27. Replace synthetic observability with owned evidence**
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
- [x] **30. Enforce continuous verification in GitHub Actions**
  Spec ref: `spec.md > Winner-hardening release`
  What to build: Least-privilege pinned workflow for locked quality, conformance, release, syntax, secret, and container gates with concurrency cancellation.
  Acceptance: every PR and main push runs; workflow has read-only default permissions and no cloud credentials.
  Verify: local workflow audit, commit/push, and successful GitHub check run.
- [x] **31. Simplify and synchronize judge-facing claims**
  Spec ref: `spec.md > Winner-hardening release`
  What to build: Succession-first README, rubric map, explicit limitations, current diagram, executable demo story, and sanitized evidence publication plan.
  Acceptance: no stale run, unsupported Foundry headline, or inaccessible proof is presented as current.
  Verify: claims-to-evidence audit against exact release metadata.
- [x] **32. Deploy, recapture, and prepare the Devpost handoff**
  Spec ref: `prd.md > Acceptance outcomes`
  What to build: Deploy exact final commit, run the one-touch scenario, capture owned evidence, publish a sanitized bundle, and freeze the four-minute narrative.
  Acceptance: source, image, services, run, bundle, CI and judge links all agree and independently verify.
  Verify: live unedited rehearsal, offline PASS, green required CI, and clean Git state.

## Golden-standard extension — autonomous

- [x] **33. Implement bounded successor discovery and eligibility**
  Spec ref: `spec.md > Golden-standard extension`
  What to build: Immutable candidate records, deterministic assessment receipt, stable fail-closed rejection reasons, and registry integration.
  Acceptance: Multiple candidates are assessed and only compatible, authorized, healthy candidates can reach model selection.
  Verify: Candidate permutation, rejection, mutation, and empty-set tests.
- [x] **34. Make Gemini choose the successor causally**
  Spec ref: `spec.md > Golden-standard extension`
  What to build: Typed candidate choice, bounded prompt, citation validation, policy admission, HOLD paths, and cloud lifecycle wiring.
  Acceptance: A valid Gemini choice changes the activated principal; unknown, rejected, malformed, or uncited choices cannot mutate state.
  Verify: Model ablation, adversarial output, scenario, and API tests.
- [x] **35. Prove minimum authorized context reconstruction**
  Spec ref: `spec.md > Golden-standard extension`
  What to build: Purpose/freshness/trust/scope filters, inclusion/exclusion receipt, digests, manifest linkage, and verifier checks.
  Acceptance: The successor gets enough verified state to resume while poisoned, revoked, secret, stale, and unrelated context never crosses the boundary.
  Verify: Context classification, tamper, omission, and end-to-end verification tests.
- [x] **36. Ship the migration-free SDK and local consumer**
  Spec ref: `spec.md > Golden-standard extension`
  What to build: Three-call vendor-neutral SDK, in-process adapter, local consumer example, and portable contract export.
  Acceptance: The example completes without Google packages or credentials and emits independently verifiable artifacts.
  Verify: Isolated import, example subprocess, idempotency, and contract verification tests.
- [x] **37. Expand the resilience and ambiguity lab**
  Spec ref: `spec.md > Golden-standard extension`
  What to build: Distinct crash, retry, delayed/stale message, competing successor, invalid citation, unknown effect, verifier outage/disagreement, and partition fixtures.
  Acceptance: Every case has a unique input digest and a measured safe result; unknown truth is INCONCLUSIVE.
  Verify: Regenerated evaluation report and digest/coverage audit.
- [x] **38. Add optional independent witness aggregation**
  Spec ref: `spec.md > Golden-standard extension`
  What to build: Same-bundle verifier verdict aggregation, principal uniqueness, threshold rules, dissent evidence, and explicit non-consensus language.
  Acceptance: Duplicate identities, mixed bundles, insufficient quorum, and dissent fail or remain inconclusive as specified.
  Verify: Quorum truth-table and signature-boundary tests.
- [x] **39. Rebuild the cockpit around business impact**
  Spec ref: `spec.md > Golden-standard extension`
  What to build: Obligation-at-risk, succession-decision, and continuity-proof panels with quantified value and infrastructure drill-down.
  Acceptance: A judge can explain the problem, autonomous decision, transferred context, and verified outcome after a 60-second path.
  Verify: Browser/API smoke, accessibility checks, and narrative audit.
- [x] **40. Publish polished architecture and adoption proof**
  Spec ref: `spec.md > Golden-standard extension`
  What to build: Clean source-controlled architecture diagram, SDK quickstart, threat/guarantee matrix, claims map, provenance, and four-minute story.
  Acceptance: GCP is visibly the reference deployment rather than an adoption prerequisite; every headline claim points to executable evidence.
  Verify: Diagram render, link checker, release gate, and originality audit.
- [x] **41. Pass exhaustive release verification**
  Spec ref: `prd.md > Acceptance outcomes`
  What to build: Complete tests for new behavior while preserving genuine 100% statement/branch coverage and every existing CI gate.
  Acceptance: Quality, conformance, security, container, local runtime, and release checks all pass from a clean checkout.
  Verify: Locked quality workflow and reproducible image build.
- [x] **42. Merge, deploy, and capture the golden run**
  Spec ref: `prd.md > Acceptance outcomes`
  What to build: Protected-branch PR, green CI merge, exact-commit Cloud Run deployment, fresh canonical run, sanitized bundle, and demo rehearsal.
  Acceptance: Commit, image, candidate decision, context receipt, effect, identities, logs/traces, independent verdict, and published checksums all agree.
  Verify: Required GitHub checks, offline PASS, live unedited rehearsal, and clean main.

## Standards-readiness hardening — autonomous

- [x] **43. Remove the remediation policy table from the model boundary**
  Spec ref: `spec.md > Standards-readiness hardening`
  What to build: Deterministic incident assessment, content-addressed receipt, allowed-remediation set, bounded model context, and independent policy admission.
  Acceptance: Gemini may explain or rank only already-admissible choices; model output cannot create an allowed remediation or alter the incident verdict.
  Verify: Truth-table, mutation, ablation, malformed-output, and lifecycle tests.
- [x] **44. Formalize evidence and trust policy**
  Spec ref: `spec.md > Standards-readiness hardening`
  What to build: Versioned evidence descriptors for issuer, subject, type, source authority, observation/expiry, payload digest, signature reference, and trust-policy version, plus deterministic validation receipts.
  Acceptance: Unknown issuers/types, stale/future evidence, digest substitution, duplicate IDs, and missing authentication fail closed with stable reasons.
  Verify: Golden vector, boundary tests, receipt mutation tests, and cloud adapter checks.
- [x] **45. Prove a second domain without diluting the live demo**
  Spec ref: `spec.md > Standards-readiness hardening`
  What to build: A cloud-neutral incident-remediation consumer that preserves a service-restoration obligation and executes one idempotent rollback effect through the same SDK/contract boundary.
  Acceptance: No procurement constants or Google packages are required and both domains emit independently verifiable evidence.
  Verify: Isolated subprocess, domain-independence assertions, and duplicate-effect test.
- [x] **46. Add deterministic concurrent multi-run stress evidence**
  Spec ref: `spec.md > Standards-readiness hardening`
  What to build: Barrier-synchronized multi-run/idempotency contention harness with measured outcomes and digest-bound report.
  Acceptance: Concurrent duplicate requests converge to one effect per obligation, cross-run keys remain isolated, and conflicts fail visibly.
  Verify: Repeated stress run, invariant assertions, and report regeneration.
- [x] **47. Ship a fully local container profile**
  Spec ref: `spec.md > Standards-readiness hardening`
  What to build: Deterministic investigator adapter, local composition, health/run endpoints, Docker Compose profile, and credential-free smoke command.
  Acceptance: A clean machine can execute the full local succession path without Google credentials or network model access.
  Verify: Local process test and Docker Compose/container smoke.
- [x] **48. Harden dependencies and runtime supply chain**
  Spec ref: `spec.md > Standards-readiness hardening`
  What to build: Bounded ADK dependency, locked environment, multi-stage non-root image, OCI metadata, SBOM generation, vulnerability scan, and pinned CI actions.
  Acceptance: Runtime excludes build tooling/caches, SBOM is generated from the final image, and HIGH/CRITICAL findings gate CI under a documented policy.
  Verify: Locked sync, reproducible build, image inspection, SBOM, and scanner execution.
- [x] **49. Synchronize normative and judge-facing documentation**
  Spec ref: `spec.md > Standards-readiness hardening`
  What to build: Evidence specification, architecture/adoption boundary, expanded claims matrix, explicit epistemic limits, runbooks, and originality note.
  Acceptance: Every new claim links to executable evidence and no one-shot demo is represented as universal production proof.
  Verify: Link/claim audit and release gate.
- [x] **50. Pass, merge, deploy, and recapture the hardened release**
  Spec ref: `prd.md > Acceptance outcomes`
  What to build: Genuine 100% statement/branch coverage, all conformance/stress/container/security gates, protected PR, exact-commit deployment, fresh canonical capture, and public checksummed evidence.
  Acceptance: Code, CI, image, cloud run, proof release, and documentation identify the same hardened application release.
  Verify: Green required checks, offline PASS, signature verification, and clean `main`.

## Submission-truth and fleet-utility hardening — autonomous

- [x] **51. Establish one machine-checked release truth**
  Spec ref: `spec.md > Submission-truth and fleet-utility hardening`
  What to build: A versioned release manifest for application source, image, run,
  evidence release, object/span/test counts and hosted revision, plus a release
  audit that rejects stale judge-facing claims.
  Acceptance: README, Devpost draft, compliance matrix, showcase and public copy
  derive every mutable release fact from one manifest; incompatible historical
  numbers are explicitly labelled archival or absent.
  Verify: Mutation tests, release gate and repository-wide stale-claim scan.
- [x] **52. Ship a bounded judge-executable cloud sandbox**
  Spec ref: `spec.md > Submission-truth and fleet-utility hardening`
  What to build: A separate least-privilege Cloud Run judge gateway that accepts
  only the server-owned canonical command, requires an expiring capability token,
  enforces an atomic quota, and exposes read-only phase polling.
  Acceptance: Judges can start and observe a fresh run without control-plane IAM;
  arbitrary payloads, replay beyond quota, internal routes and direct mutation fail
  closed, while the public showcase identity retains zero project roles.
  Verify: Auth/quota/abuse tests, IAM audit, live start/status smoke and cost cap.
- [x] **53. Make Gemini resolve a genuine bounded trade-off**
  Spec ref: `spec.md > Submission-truth and fleet-utility hardening`
  What to build: Competing eligible successors with different recovery-time,
  assurance, jurisdictional and warm-state evidence; a code-authored objective;
  claim-linked model citations; and deterministic admission of either defensible
  choice.
  Acceptance: No scalar trust maximum predetermines the answer; changing the
  incident objective can change the admitted successor, while malformed reasoning,
  unsupported trade-offs and ineligible choices cannot advance authority.
  Verify: Objective ablation, candidate permutation, counterfactual and cloud tests.
- [x] **54. Implement an enterprise fleet catalog and dormant-resume proof**
  Spec ref: `spec.md > Submission-truth and fleet-utility hardening`
  What to build: Department-owned immutable agent publications, version lineage,
  capability discovery and deterministic assessment through a portable registry
  port, plus a 21-day dormant-obligation fixture resumed from persisted state.
  Acceptance: The succession service discovers rather than owns candidates; at
  least three departments can publish versions; an old obligation resumes without
  process memory or timestamp fabrication.
  Verify: Cross-department isolation, lineage, discovery, dormant restart and adapter tests.
- [x] **55. Put Google Model Armor on the raw-input boundary**
  Spec ref: `spec.md > Submission-truth and fleet-utility hardening`
  What to build: A production Model Armor prompt-sanitization port, deterministic
  fail-closed admission receipt, raw adversarial supplier document path and local
  deterministic substitute.
  Acceptance: The raw attack is submitted to Model Armor before classification or
  model access; MATCH, skipped execution, malformed response and unavailable service
  cannot reach context or Gemini; the exact template and result digest are evidenced.
  Verify: Raw attack/clean input/mutation/outage tests and live Model Armor receipt.
- [x] **56. Execute a real reversible enterprise queue effect**
  Spec ref: `spec.md > Submission-truth and fleet-utility hardening`
  What to build: A provider-neutral work-item port and a GitHub Issues reference
  adapter that creates or reconciles one synthetic supplier-review ticket with a
  stable idempotency marker and reversible close operation.
  Acceptance: Redelivery produces one external ticket, not one Firestore stand-in;
  provider reconciliation is independently readable; no token or real supplier data
  enters source, logs or evidence.
  Verify: Contract tests, mocked API faults, live synthetic issue, duplicate delivery
  and cleanup/close proof.
- [x] **57. Publish an independent-language interoperability consumer**
  Spec ref: `spec.md > Submission-truth and fleet-utility hardening`
  What to build: A minimal TypeScript consumer that implements the public contract
  without importing Python or Google packages, verifies the golden RFC 8785 vector,
  registers a departmental agent, records a dormant obligation and executes an
  idempotent effect against the local transport.
  Acceptance: The independent client passes the same conformance artifacts and its
  failures expose stable protocol reasons; it is described as first-party
  interoperability evidence, not external adoption.
  Verify: Locked Node test, cross-language digest equality and CI job.
- [x] **58. Replace the judge diagram with one memorable lifecycle**
  Spec ref: `spec.md > Submission-truth and fleet-utility hardening`
  What to build: A sparse judge-facing diagram and narrative led by obligation,
  fenced predecessor, bounded successor, one real queue effect and independent
  proof; detailed service topology remains a secondary technical diagram.
  Acceptance: The primary diagram is readable at 1080p and contains one sentence of
  product meaning, while internal service names cannot obscure Succession Protocol.
  Verify: Render dimensions, text audit, link audit and 13-inch readability check.
- [x] **59. Pass, deploy, recapture and synchronize the non-video submission truth**
  Spec ref: `prd.md > Acceptance outcomes`
  What to build: Full locked gates, protected merge, exact-commit cloud deployment,
  fresh canonical run, public checksummed proof, current showcase, Devpost text and
  all non-video form assets.
  Acceptance: One release manifest agrees with code, CI, image, services, run,
  Model Armor, external ticket, proof release, hosted access and public Devpost copy.
  Video was intentionally unset at this non-video checkpoint; final production
  and public YouTube publication were subsequently completed.
  Verify: Green required checks, offline PASS, live judge smoke, public-copy readback,
  architecture asset check and clean `main`.

## External resilience and category-positioning hardening — autonomous

- [x] **60. Make official registry access bounded and fail closed**
  Spec ref: `spec.md > External-dependency and positioning hardening`
  What to build: Stable external-tool errors, retryable HTTP/network classification,
  per-attempt timeout, total budget and nonblocking invocation.
  Acceptance: Timeout, DNS, 429/5xx, 4xx and malformed JSON never escape as raw errors;
  only transient failures retry and every terminal path has a stable code.
  Verify: Deterministic retry/budget/error taxonomy tests at genuine 100% coverage.
- [x] **61. Add freshness-bound durable registry evidence fallback**
  Spec ref: `spec.md > External-dependency and positioning hardening`
  What to build: Cache port, in-memory and Firestore adapters, LIVE/CACHED receipts,
  explicit stale/unavailable HOLD and persistence of availability provenance.
  Acceptance: A fresh cached official observation can continue under policy; stale,
  missing, corrupted or substituted cache state reaches neither Gemini nor execution.
  Verify: Cache mutation/freshness/outage tests and cloud composition tests.
- [x] **62. Ship a workflow-engine companion integration**
  Spec ref: `spec.md > External-dependency and positioning hardening`
  What to build: Engine-neutral bridge example and responsibility matrix distinguishing
  task durability from obligation, authority, memory and attestation continuity.
  Acceptance: Existing engine events map to the three-call contract without Google
  packages, replacing the engine or claiming external adoption.
  Verify: Isolated subprocess, duplicate task/idempotency and boundary tests.
- [x] **63. Formalize model-selection governance and human review**
  Spec ref: `spec.md > External-dependency and positioning hardening`
  What to build: Deterministic comparison baseline, deviation receipt, production-impact
  approval rule and fail-closed model-unavailable decision.
  Acceptance: Gemini remains causally useful in the sandbox but cannot become the legal
  authority rationale; production/high-impact deviation requires explicit approval.
  Verify: Decision truth table, ablation, threshold and lifecycle receipt tests.
- [x] **64. Publish trust assumptions and precise proof semantics**
  Spec ref: `spec.md > External-dependency and positioning hardening`
  What to build: Machine-readable trust profile, verifier output linkage, threat/claim
  matrix and public language describing exactly what proof does and does not establish.
  Acceptance: No surface implies upstream truth, uncompromised infrastructure, capture
  provenance or Byzantine assurance from an internally consistent bundle.
  Verify: Schema/mutation tests and release-surface claim audit.
- [x] **65. Simplify the primary story without removing technical depth**
  Spec ref: `spec.md > External-dependency and positioning hardening`
  What to build: Workflow-engine comparison, four-question product framing and layered
  navigation that retains every named service and bonus branch as secondary material.
  Acceptance: The first judge path needs no internal jargon; complete architecture and
  evidence remain linked and unchanged in scope.
  Verify: README/showcase text audit, link check, release gate and clean full quality gate.
- [x] **66. Merge, deploy and recapture the resilient release**
  Spec ref: `prd.md > Acceptance outcomes`
  What to build: Protected PR, exact-commit deployment, fresh canonical run, proof bundle,
  showcase and Devpost synchronization; video was deferred at this checkpoint
  and was subsequently completed, published and attached to Devpost.
  Acceptance: Application, source, services, external modes, model-governance receipt,
  run, proof and public copy agree through the single release manifest.
  Verify: Required CI, live API-outage drill, fresh offline PASS, judge smoke and clean main.

## Final auditability and rollback hardening — autonomous

- [x] **67. Publish durable, scope-complete coverage evidence**
  Spec ref: `spec.md > Final auditability and rollback hardening`
  What to build: Machine-readable XML/JSON, human-readable HTML/Markdown, measured-source
  inventory, cryptographic manifest, CI job summary and retained workflow artifact.
  Acceptance: A reviewer can verify that every Python module under `src/continuum` is
  measured with statement and branch coverage, with no omissions or coverage pragmas;
  the gate still fails below 100.0%.
  Verify: Coverage-evidence unit tests, full quality gate and public CI artifact.
- [x] **68. Publish failed-run lineage and release-PR context**
  Spec ref: `spec.md > Final auditability and rollback hardening`
  What to build: A concise failure ledger for the two pre-canonical attempts, causal
  lessons, fixes, non-claims and links to the functional implementation PR lineage.
  Acceptance: Failed attempts remain visibly failed and the documentation-only release
  pin cannot be mistaken for the implementation history.
  Verify: Link/release audit, exact run identifiers and merged PR description read-back.
- [x] **69. Make the no-role security boundary self-explanatory**
  Spec ref: `spec.md > Final auditability and rollback hardening`
  What to build: A plain-language blast-radius statement and machine-checked IAM
  expectations across README, runbook and threat model.
  Acceptance: A judge can state exactly why public invocation is safe: compromise of the
  showcase cannot read Firestore, call Vertex AI, publish Pub/Sub, invoke private agents,
  or mutate the control plane through project IAM.
  Verify: Documentation assertions, deployment-security tests and live IAM read-back.
- [x] **70. Ship a reversible, fail-closed showcase rollback**
  Spec ref: `spec.md > Final auditability and rollback hardening`
  What to build: An explicit-target, dry-run-by-default rollback command that validates
  revision ownership/readiness, switches traffic only with `--apply`, and verifies build
  identity, absent mutation surface, exact public invoker policy and zero project roles.
  Acceptance: Invalid or ambiguous targets cannot mutate traffic; a known-good revision
  can be restored and the current revision re-applied with an auditable local receipt.
  Verify: Unit/static tests, shell syntax, dry-run against Cloud Run and a reversible live drill.

## Independent-audit closure — autonomous

- [x] **71. Publish the community trust and governance surface**
  Spec ref: `spec.md > Independent-audit closure`
  What to build: Contribution, vulnerability-reporting, conduct and project-governance
  policies, plus review ownership and pull-request provenance prompts.
  Acceptance: A contributor can determine how to propose code, report a vulnerability,
  resolve a governance dispute and preserve hackathon originality without private context.
  Verify: Link, policy-content and repository-template checks.
- [x] **72. Establish one machine-verifiable configuration inventory**
  Spec ref: `spec.md > Independent-audit closure`
  What to build: JSON Schema 2020-12, canonical inventory, generated operator reference and
  a static scanner covering Python, shell, workflow, Docker and example environment usage.
  Acceptance: Undeclared variables, duplicate names, secret defaults, unsafe evidence
  exposure and stale generated documentation fail the release gate.
  Verify: Schema validation, mutation fixtures, source scan and deterministic regeneration.
- [x] **73. Make the complete test path warning-free**
  Spec ref: `spec.md > Independent-audit closure`
  What to build: Supported Starlette/httpx2 test transport and a warnings-as-errors gate.
  Acceptance: The FastAPI test client emits no compatibility deprecation and any future
  warning fails local and hosted CI instead of being normalized as noise.
  Verify: Locked dependency audit and full suite with `PYTHONWARNINGS=error`.
- [x] **74. Separate CI assurance from live-cloud assurance in code**
  Spec ref: `spec.md > Independent-audit closure`
  What to build: Versioned assurance-profile schema and manifest distinguishing mocked,
  credential-free regular CI from manually captured exact-commit Google Cloud evidence.
  Acceptance: CI cannot claim live GCP execution; cloud proof cannot inherit CI guarantees;
  every profile states trust roots, evidence, non-claims, cost and credential boundary.
  Verify: Machine mutation checks, release-gate integration and CI summary readback.
- [x] **75. Bind coverage claims to their epistemic ceiling**
  Spec ref: `spec.md > Independent-audit closure`
  What to build: Machine-required non-claims and cross-links from coverage to conformance,
  adversarial, stress, cloud and independent-verification evidence.
  Acceptance: No release surface can present 100% execution coverage as proof of semantic
  correctness, production fitness, live-cloud execution or complete threat coverage.
  Verify: Assurance-schema validation and judge-surface claim audit.
- [x] **76. Ship a cryptographically verifiable external-witness workflow**
  Spec ref: `spec.md > Independent-audit closure`
  What to build: Content-addressed review request, external statement schema, conflict and
  scope declaration, Sigstore keyless verification command, witness registry and status gate.
  Acceptance: Only the expected OIDC identity and issuer can authenticate a statement over
  the exact release digest; unsigned first-party material remains explicitly `AWAITING` and
  can never be labelled independent review.
  Verify: Canonicalization, identity/issuer/digest/expiry mutation tests and offline status audit.
- [x] **77. Pass and merge the independent-audit release**
  Spec ref: `prd.md > Acceptance outcomes`
  What to build: Exhaustive warning-free quality, schema, conformance, release, container,
  secret and supply-chain gates through a protected pull request.
  Acceptance: Required checks pass, merged `main` contains every audit control, and no
  generated credential, cloud state or fabricated third-party endorsement is committed.
  Verify: Green GitHub checks, post-merge readback and clean worktree.

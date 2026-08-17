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

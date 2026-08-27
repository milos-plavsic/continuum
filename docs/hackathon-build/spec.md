# Technical specification

## Architecture

Use a deterministic Python domain core with ports for an append-only event store,
agent registry, memory authorization, policy, and sandbox side-effect provider.
The local reference path has no cloud credentials and uses JSONL plus SQLite.
Production adapters map those ports to Firestore transactions/outbox, Pub/Sub,
Cloud Run service identity, Vertex AI Gemini via Google ADK, and Cloud Observability.

## Contracts

- Every event has a canonical payload hash, correlation ID, causation ID, aggregate
  version, actor, and deterministic timestamp/identifier under fixtures.
- Every consequential request carries tenant, agent version, authority epoch,
  obligation revision, policy decision, trace ID, and idempotency key.
- Gemini returns a typed, evidence-cited proposal. Policy code alone authorizes.
- The action gateway validates active identity, current epoch, capability, tenant,
  decision, and request digest before provider dispatch.
- Memory grants are filtered before retrieval.

## Canonical flow

Register v17 active at epoch 41 and v18 staged. Record a vendor-compliance
obligation and a malicious document. Deny v17's bypass action. Advance a virtual
clock beyond the evidence deadline. Investigate, approve quarantine, fence v17,
commit a hashed manifest, activate v18 at epoch 42, create the vendor record,
redeliver the command, verify one record, and deny v17 action and memory access.

## Verification

Standard-library unit and scenario tests verify causal policy, transition order,
manifest integrity, idempotency conflicts, duplicate effects, fencing, memory
revocation, tenant isolation, event integrity, and deterministic replay.

## Continuity Contract extension

The portable boundary uses six versioned, content-addressed artifact envelopes,
a restricted integer-only canonical JSON profile, optional Ed25519 signatures,
independent reference verification, published golden vectors, and cumulative
profile-specific conformance. Local C6 demonstrates only the declared sandbox
boundaries; Google Cloud, live-model, and third-party interoperability profiles
require separate evidence.

## Winner-hardening release

- The canonical obligation is to obtain and independently validate compliance
  evidence before vendor creation. Missing evidence can never be discharged by
  the downstream effect alone.
- A persisted deadline is evaluated by a separately invoked sentinel tick. The
  tick emits `expectation.missed` only after reading the absence of the expected
  evidence; scenario creation cannot manufacture that observation.
- The Google path uses the transactional event/projection/outbox adapter. Pub/Sub
  delivery advances the durable lifecycle, and the same message is deliberately
  redelivered through the effect-bearing path.
- One centralized gateway transaction revalidates tenant, authority domain,
  workload principal, epoch, capability, obligation revision, policy decision,
  request digest, and idempotency key immediately before provider dispatch.
- Gemini selects a bounded remediation plan and cites observed event identifiers.
  Deterministic policy validates the selection; the model never grants authority.
- Control exports five pre-attestation artifacts. A read-only verifier resolves
  their digests, reads authority/compliance/provider observations independently,
  returns `VERIFIED`, `FAILED`, or `INCONCLUSIVE`, and alone issues the continuity
  attestation.
- Evidence collection reads Firestore and Cloud Trace from their owning Google
  APIs. Application-authored logs are identified as logs, never relabeled as
  provider-authoritative state.
- A cloud-backed cockpit starts once and polls durable phases through completion.
  It exposes the live model proposal, gateway denials, delivery attempts, provider
  effect count, verification verdict, and correlated trace without extra proof clicks.
- CI runs locked tests, genuine 100% line/branch coverage, conformance, release
  audit, compile/shell checks, secret scanning, and a container build on every PR
  and push to main. Branch protection can require the resulting check.

## Golden-standard extension

- The registry exposes immutable `SuccessorCandidate` records with workload identity,
  artifact digest, capabilities, authority domains, jurisdictions, health evidence,
  supported contract profiles, memory scopes, and evidence references.
- A deterministic eligibility engine produces an ordered assessment receipt and stable
  rejections for predecessor identity, lifecycle, health, capability, jurisdiction,
  contract compatibility, memory scope, and trust floor. Only eligible records reach
  Gemini. The model returns a typed candidate choice and evidence citations; validation
  proves the candidate and citations came from that bounded set before policy admission.
- A reconstruction engine resolves authorized context items by digest. It includes only
  fresh, transferable, purpose-bound facts within the successor grant and emits explicit
  exclusions for untrusted, secret, stale, revoked, out-of-purpose, or unsupported items.
  The receipt is linked into the succession manifest and independent verification.
- The portable SDK defines `register_agent`, `record_obligation`, and
  `execute_idempotent`; transports are ports, not cloud imports. An in-process local
  runtime executes a complete consumer example and exports the same six-artifact contract
  profile without credentials.
- A resilience lab injects faults at durable boundaries and records unique input digests,
  decisions, safety properties, and observed outcomes. Network ambiguity resolves through
  provider reads or remains INCONCLUSIVE; it never guesses success.
- Optional witness aggregation requires a configured threshold of distinct verifier
  principals signing the same bundle digest and reports dissent. This is an evidence
  aggregation profile, not Byzantine consensus.
- The cockpit leads with a EUR 250,000 supplier onboarding obligation, deadline, risk,
  candidate assessments, selected successor, excluded context, duplicate effect count,
  and independent verdict. Provider implementation evidence remains available as a
  secondary proof layer.

## Standards-readiness hardening

- A deterministic incident assessor validates formal evidence descriptors and
  authors a content-addressed receipt containing the incident verdict and exact
  allowed remediation set. The model receives that set as immutable context; it
  may explain or rank choices but cannot expand it. Policy admission recomputes
  the receipt and never depends on a natural-language rule.
- Every evidence descriptor declares a protocol version, immutable ID, evidence
  type, subject, issuer, source authority, observation and expiry timestamps,
  canonical payload digest, authentication reference, and trust-policy version.
  A deterministic trust policy rejects unknown authorities, stale/future items,
  unsupported types, malformed digests, duplicate identities, and missing
  authentication before evidence reaches policy or a model.
- Portability is tested with a second incident-remediation domain using the same
  three-call SDK and evidence boundary, while the supplier workflow remains the
  only live judge narrative.
- A barrier-synchronized stress profile measures concurrent runs, duplicate
  idempotency keys, semantic conflicts, isolation, and effect counts. Results are
  content-addressed and reproducible; this is bounded contention evidence, not a
  global linearizability or Byzantine-fault claim.
- A local container profile composes deterministic adapters and exposes a
  credential-free full lifecycle. Google ADK/Gemini remains the required live
  production reference, not a local prerequisite.
- The production image is multi-stage, non-root, lockfile-built and OCI-labelled.
  CI generates an SPDX JSON SBOM from the final image and gates documented
  actionable HIGH/CRITICAL vulnerabilities with pinned scanner tooling.

## Submission-truth and fleet-utility hardening

- Mutable submission facts live in one machine-readable release manifest and are
  checked against every judge-facing surface. Historical runs remain provenance,
  never an unlabeled alternative current truth.
- A separate public judge gateway has no generic proxy or arbitrary command surface.
  It authorizes an expiring capability by digest, atomically accounts a small run
  quota, invokes only the private server-owned canonical lifecycle, and exposes only
  sanitized status.
- Successor choice is a multi-attribute decision rather than a disguised maximum.
  Code supplies the incident objective and admissible candidates; Gemini must make a
  claim-linked trade-off that deterministic admission can verify but not preselect.
- The registry is an independent fleet catalog port. Department publishers own
  immutable version records and lineage; succession discovers compatible versions.
  A persisted 21-day fixture proves recovery independent of process lifetime.
- Raw untrusted input crosses Google Model Armor before classification or model
  access. Only a successful, no-match sanitization receipt can admit it; unavailable,
  skipped, malformed or matched results fail closed.
- The reference business effect is one reversible synthetic ticket in an external
  enterprise work queue. Firestore remains the transactional gateway ledger, not the
  claimed external provider.
- A first-party TypeScript consumer independently implements and verifies the public
  contract. It is interoperability evidence, not a claim of third-party adoption.
- The primary architecture asset explains one succession lifecycle; full cloud and
  protocol topology is retained as secondary engineering evidence.

## External-dependency and positioning hardening

- Official registry reads use a bounded retry policy with per-attempt timeout,
  total wall-clock budget, retryable-status classification and stable public reason
  codes. A durable cache may supply only a still-fresh, content-addressed prior
  observation; stale or absent evidence produces an explicit HOLD and no model or
  action call.
- Every supplier observation declares `LIVE` or `CACHED_WITHIN_POLICY`, local
  observation time, policy expiry and provenance. The decision pack and independent
  verifier bind that availability mode and freshness; a cache is resilience, never
  silent substitution.
- Continuum is a governance layer beside a workflow engine, not a scheduler
  replacement. A first-party engine bridge maps engine task identity, obligation and
  idempotency into the three-call protocol while leaving retries, timers and task
  execution with the host engine.
- Model choice is advisory optimization among already eligible candidates. A
  deterministic comparison baseline, explicit deviation receipt, production-impact
  approval threshold and HOLD-on-model-unavailability policy make the legal authority
  decision independent of model prose.
- Assurance claims name their trust roots and epistemic ceiling: content and semantic
  consistency are assessed; capture provenance, infrastructure compromise, upstream
  factual truth and Byzantine consensus are not inferred.
- The complete technical architecture remains intact. Primary judge surfaces explain
  promise, authority, memory and one effect first; named supporting services and
  multimodal bonus branches remain available as secondary depth.

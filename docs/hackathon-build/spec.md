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

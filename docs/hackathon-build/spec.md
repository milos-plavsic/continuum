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

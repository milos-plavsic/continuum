# Architecture direction

## Logical flow

```text
Domain events
    |
    v
Promise Ledger ----> Negative Space Sentinel
    |                         |
    +---------- evidence <----+
                              v
                    Investigator agents
                              |
                       action proposals
                              v
                    Constitutional Court
                              |
                      governed decision
                              v
                   Policy / Action Gateway
                       |              |
                       v              v
               verified action   human approval
                       |
             +---------+----------+
             v                    v
      Antibody Foundry     Succession Protocol
             |                    |
             +---------+----------+
                       v
             Evidence and audit timeline
```

## Initial Google stack hypothesis

- Google ADK for multi-agent orchestration
- Gemini 3.5 Flash for evidence synthesis, policy reasoning, and test generation
- Cloud Run for independently deployable services
- Pub/Sub for lifecycle and domain events
- Firestore for the initial event/state projection
- Cloud Scheduler for temporal expectation checks
- Secret Manager and service identities for least-privilege access
- OpenTelemetry traces exported to Google Cloud Observability

This is a hypothesis, not a locked design. Validate current service availability
and hackathon access before implementation.

## Reference implementation boundary

The repository's deterministic reference path implements the domain protocol
with a JSONL append-only event adapter and a separately persisted SQLite sandbox
provider. These are reproducible substitutes for local evaluation, not claims
of deployed Google infrastructure. The corresponding production ports are:

| Reference boundary | Google Cloud target |
|---|---|
| JSONL events and in-memory projection | Firestore events, transactional projections, and outbox |
| Deterministic delivery/replay | Pub/Sub at-least-once delivery |
| Recorded typed investigation evidence | Google ADK agent using Gemini 3.5+ on Vertex AI |
| Logical service identity and epoch | Cloud Run user-managed identity plus gateway fencing |
| Local timeline | OpenTelemetry to Cloud Trace and Logging |
| SQLite vendor registry | Controlled, reconcilable external provider adapter |

The core remains deterministic and dependency-free. Cloud adapters must preserve
the same contracts and pass adapter conformance tests before their evidence can
be marked complete.

## Portable protocol boundary

The Continuity Contract sits outside the runtime projections. It exports six
content-addressed artifacts: obligation, authority grant, succession manifest,
revocation proof, execution receipt, and continuity attestation. Internal
Firestore documents or Python dataclasses are not wire contracts.

The executor produces a receipt but cannot attest its own success. A separately
authorized verifier reads provider state, resolves every referenced digest, and
issues a verified, failed, or inconclusive attestation. Signatures bind content
to a key; deployment trust policy determines whether that key is authoritative.

## Shared primitives

- Append-only event envelope
- Obligation with expected evidence and deadline
- Action proposal with risk and reversibility metadata
- Policy decision with evidence references
- Idempotent execution record
- Agent identity and lifecycle state
- Memory grant, revocation, and transfer record
- Evaluation case and promotion decision

## Safety invariants

- No side effect without an idempotency key.
- No destructive action without an explicit policy decision.
- Revoked memory is excluded before semantic retrieval.
- A retired identity cannot act or read transferred memory.
- Candidate defenses run in shadow evaluation before promotion.
- Every autonomous action links to evidence, policy, execution, and verification.

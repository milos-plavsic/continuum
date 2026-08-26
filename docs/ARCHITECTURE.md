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

## Implemented Google reference stack

- Google ADK for multi-agent orchestration
- Gemini 3.6 Flash for bounded evidence synthesis and successor recommendation
- Cloud Run for independently deployable services
- Pub/Sub for lifecycle and domain events
- Firestore for the initial event/state projection
- Cloud Tasks for persisted, real-time deadline callbacks
- Cloud Run service identities and IAM for least-privilege access
- OpenTelemetry spans exported through the Google Cloud Trace exporter

The cloud path is an implemented reference binding. A release claim is valid
only after that exact commit is deployed and a fresh exact-run evidence bundle
passes the offline semantic verifier.

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

The Continuity Contract sits outside the runtime projections. The control plane
exports exactly five pre-attestation, content-addressed artifacts: obligation,
authority grant, succession manifest, revocation proof, and execution receipt.
The independent verifier recomputes every digest, directly reads authority,
compliance, and provider state, and only then authors the sixth artifact—the
continuity attestation. Internal Firestore documents or Python dataclasses are
not wire contracts.

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

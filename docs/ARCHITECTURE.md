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

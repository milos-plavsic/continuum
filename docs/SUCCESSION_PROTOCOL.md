# Succession Protocol

Continuum transfers a valid obligation to a new agent generation without
transferring unauthorized memory or permitting duplicate effects through its
governed gateway.

## Bounded guarantee

For effects executed exclusively through the Action Gateway with a stable
idempotency key and a reconcilable provider adapter, retries and at-least-once
delivery produce at most one externally observed effect. Every approved
obligation ends verified or in an explicit failure state. Continuum does not
claim universal distributed exactly-once execution.

## State and authority

An agent version is `REGISTERED`, `ACTIVE`, `QUARANTINED`, `DRAINING`, or
`RETIRED`. Authority is the tuple `(tenant, agent, version, epoch)`. A lease
coordinates healthy workers; a monotonically increasing epoch fences an old,
partitioned, or compromised worker.

A succession moves through:

```text
PROPOSED -> APPROVED -> FENCED -> RECONCILED -> PREPARED
         -> COMMITTED -> VERIFIED
```

Pre-commit failures may terminate explicitly. After commit, recovery always
rolls forward through a new succession and higher epoch.

## Immutable transfer manifest

The canonical, hashed manifest pins:

- predecessor and successor versions and epochs;
- obligation IDs and revisions;
- evidence and policy-decision references;
- minimum-purpose memory grants and expirations;
- explicitly excluded memory IDs/classifications;
- in-flight execution keys and reconciliation state.

Any change produces a new manifest version and policy evaluation.

## Ordered handoff

1. Propose succession with evidence and intended successor.
2. Bind policy approval to evidence, risk, reversibility, and policy version.
3. Increment the epoch, quarantine/drain the predecessor, and revoke its grants.
4. Reconcile reserved, dispatched, unknown, and completed effects by idempotency key.
5. Build and hash the minimum transfer manifest.
6. Validate successor health, tenant, capabilities, memory scopes, and deployment identity.
7. Atomically commit ownership, successor activation, manifest, and outbox record.
8. Execute through the gateway after validating identity, epoch, revision, policy,
   capability, memory scope, request digest, and idempotency key.
9. Read provider state and append verification evidence.

## Invariants

1. No more than one generation has executable authority for an obligation.
2. Revocation and fencing precede successor activation after suspected compromise.
3. A quarantined or retired generation cannot act or retrieve memory.
4. Memory authorization filters grant IDs before semantic retrieval.
5. The same idempotency key with a different request digest is rejected.
6. Ownership changes only through an approved, committed manifest.
7. Every consequential transition links evidence, proposal, decision, execution,
   and verification.
8. Epochs never decrement and event history is never rewritten.

## Failure handling

| Failure | Safe behavior |
|---|---|
| Crash before fencing | Retry the same succession command. |
| Crash after fencing | Keep predecessor fenced and resume from recorded state. |
| Duplicate event | Conditional transition is a no-op; gateway returns prior result. |
| Unknown provider result | Reconcile by provider reference/key; never retry blindly. |
| Manifest or policy changed | Fail optimistic precondition; rebuild and reapprove. |
| Successor unhealthy pre-commit | Keep fenced and select another eligible version. |
| Successor fails post-commit | Start a higher-epoch succession and roll forward. |
| Publish after commit fails | Transactional outbox retries publication. |
| Verification mismatch | Keep obligation incomplete and propose correction/escalation. |

Reversible domain effects use explicit compensating actions with their own
decision and idempotency key. A disproved compromise does not restore an old
epoch; reinstatement requires a fresh governed generation.


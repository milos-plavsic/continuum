# Threat and failure model

Continuum distinguishes evidence absence, operational failure, and compromise.
An overdue expectation changes an obligation to `AT_RISK` and starts an
investigation; it never independently authorizes quarantine.

| Class | Required signals | Autonomous response | Human boundary |
|---|---|---|---|
| Benign upstream delay | Missed evidence only | Investigate and hold | Optional escalation |
| Agent crash | Heartbeat loss plus unfinished obligation | Drain/succeed if policy permits | Unknown effects |
| Prompt injection | Injection marker, anomalous tool attempt, and missed evidence | Deny action, quarantine, succeed | Ambiguous evidence |
| Compromised credential | Principal anomaly or stale epoch | Deny and quarantine | Credential incident review |
| Duplicate delivery | Repeated stable idempotency key | Return recorded result | Digest conflict |
| Provider ambiguity | Dispatch without confirmed response | Reconcile provider state | Unreconcilable effect |
| Malicious memory | Untrusted/revoked classification | Exclude before retrieval | Requested exception |
| Successor failure | Health loss after commit | Higher-epoch roll-forward | No eligible successor |
| Cross-tenant request | Tenant mismatch | Deny without resource disclosure | Never autonomous transfer |
| Invalid model proposal | Schema/citation failure | Fail closed; operator task | Required to continue |
| Candidate registry poisoning | Unknown digest, stale health, wrong jurisdiction/profile | Reject before model prompt | Registry trust-anchor repair |
| Context laundering | Secret, raw, inferred, stale, revoked, or out-of-purpose item | Exclude before retrieval and attest decision | Explicit new grant and evidence |
| Verifier outage/disagreement | Missing verdict or dissent over one bundle | `INCONCLUSIVE`/`FAILED`; no self-attestation | Independent evidence review |
| Bounded network partition | Timeout before/after dispatch | Retry before dispatch; reconcile after dispatch | Unreadable provider remains `INCONCLUSIVE` |
| Public showcase compromise | Arbitrary execution under the showcase workload identity | No Firestore read, Vertex call, Pub/Sub publish, private-service invocation, secret access, or control mutation is authorized; mutation routes are absent | Remove public service IAM binding, inspect logs, and roll traffic to an audited revision |

The deterministic policy approves compromise succession only when all three
canonical evidence classes are cited. Gemini may rank hypotheses and generate a
typed proposal, but it cannot authorize execution.

Continuum tolerates crash/retry faults within a declared reconcilable-effect
boundary. Optional witness aggregation makes disagreement visible; it is not a
Byzantine-consensus protocol and does not defend against a compromised trust root.

The showcase row depends on two independently checked controls: its Cloud Run service IAM
contains only the intentional public invoker binding, while its workload principal appears
in no project IAM binding. “Publicly invokable” and “authorized to use project resources”
are separate relationships. The rollback runbook revalidates both after every traffic move.

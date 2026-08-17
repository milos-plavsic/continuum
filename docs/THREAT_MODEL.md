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

The deterministic policy approves compromise succession only when all three
canonical evidence classes are cited. Gemini may rank hypotheses and generate a
typed proposal, but it cannot authorize execution.


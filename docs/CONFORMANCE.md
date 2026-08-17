# Continuity Conformance 0.1-draft

Conformance is cumulative and profile-specific. Evidence from different runs or
profiles cannot be combined into one certification. `NOT_ASSESSED` is never a
pass, and a level passes only if it and every lower level pass.

| Level | Demonstrated property |
|---|---|
| C0 Observable | Typed artifacts, digest validation, deterministic replay |
| C1 Recoverable | Obligation persists and reaches a visible terminal outcome |
| C2 Fenced | Stale predecessor cannot act; one successor is authoritative |
| C3 Confidential | Forbidden context excluded; revoked reads pre-filtered; tenant isolated |
| C4 Idempotent | Redelivery/restart reconciles to one provider effect |
| C5 Governed | Negative controls and required-feature failures close safely |
| C6 Attested | Independent complete chain; broken links/self-attestation rejected |

The `reference-local` profile exercises a SQLite sandbox provider and logical
epoch identity boundary. Its C6 result means all declared local cases pass; it
does not certify cloud workload identity, a production vector database,
third-party interoperability, live Gemini behavior, or an external trust anchor.

```bash
python3 scripts/run_conformance.py
```

The harness creates isolated stores, evaluates durable evidence, includes
negative controls, reports every mandatory case, and writes a canonical report
digest to `artifacts/conformance/conformance-report.json`.

## Anti-gaming rules

- Fresh stores and a fixed suite/spec digest.
- Denial must prove no provider effect or retrieval candidate exposure.
- Every mandatory case and non-claim appears in the report.
- Recorded model output cannot earn a live-model claim.
- Cloud and local evidence cannot be combined across profiles.


# Credential-free local runtime

The local profile composes the complete durable lifecycle with deterministic,
in-process adapters. It is a portability and reproducibility proof, not Google
Cloud evidence and not a substitute for the live Gemini demonstration.

```bash
docker compose -f compose.local.yaml up --build --wait
curl -X POST http://127.0.0.1:8080/runs/my-fresh-run
docker compose -f compose.local.yaml down
```

The container is non-root, read-only, drops every Linux capability, sets
`no-new-privileges`, and needs neither credentials nor model/network access.
The response reaches `VERIFIED`, contains one provider effect, predecessor
action/memory denials, deterministic evidence/incident receipts, successor
selection and context reconstruction.

Two domain and concurrency checks are separately executable:

```bash
uv run python examples/incident_remediation_consumer.py
uv run python scripts/run_stress.py --runs 16 --attempts 8
```

The first applies the three-call SDK to service rollback without procurement or
Google constants. The second synchronizes 128 attempts behind a barrier and
requires one effect per obligation, isolated keys, visible semantic conflicts,
and a digest-bound report.

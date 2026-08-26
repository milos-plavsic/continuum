# Originality and provenance

Continuum was initialized on August 17, 2026 as a new repository for the All
Things Agentic Hackathon submission period.

## Prior-work relationship

The project is informed by general lessons learned while building earlier agent
systems, including RecallOps and LineageGuard: governed memory, explicit state
invalidation, human approval, evidence trails, observability, and reproducible
evaluation. No source code, assets, deployment configuration, or documentation
from those projects was copied into this repository at initialization.

Continuum has a distinct product purpose, user workflow, data model, Google
Cloud architecture, and implementation.

## Pre-existing material register

No non-standard pre-existing material is currently incorporated.

For every future incorporation, record:

- Source and URL
- Copyright owner and license
- Exact files or components used
- Whether modified
- Why it is necessary
- Date incorporated

Standard open-source frameworks and libraries must remain declared through the
project’s dependency manifests and license notices.

## External review provenance

PR #5 from `phahim1` was inspected as comparative design input for independent
verification boundaries. No source from that PR was copied or merged. The
current five-claim/read-only-provider/sole-attestation engine in
`src/continuum/verification.py` was authored independently here; the review
influenced only the decision to make three-valued verdicts and the read-only
boundary explicit.

## August 17, 2026 implementation note

The deterministic succession core, fixtures, tests, documentation, Mermaid
diagram source, and rendering/evaluation scripts were authored new in this
repository during the submission period. The deterministic runtime uses only
the Python standard library. Design patterns such as fencing tokens, idempotency keys,
transactional outbox, optimistic concurrency, least-privilege capabilities, and
saga-style roll-forward recovery are established industry patterns rather than
copied project material. No source or assets from RecallOps, LineageGuard, or
another project were incorporated.

## Continuity Contract implementation note

The Continuity Contract Profile 0.1-draft, restricted canonicalization profile,
schema, golden vector, artifact builders, bundle verifier, Ed25519 adapter, and
cumulative conformance harness were authored new for Continuum on August 17,
2026. The optional `cryptography` dependency is declared in `pyproject.toml` and
is used only for standard Ed25519 primitives; no third-party source was copied.

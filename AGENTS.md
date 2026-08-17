# Continuum agent handoff

Read `docs/PROJECT_BRIEF.md`, `docs/ARCHITECTURE.md`, and
`docs/ORIGINALITY.md` before planning or implementing work.

## Non-negotiable constraints

- This must remain a new implementation created for the All Things Agentic
  Hackathon submission period (August 3–31, 2026).
- Do not copy source code from RecallOps, LineageGuard, or other prior projects.
- If any non-standard pre-existing work is incorporated, record it immediately
  in `docs/ORIGINALITY.md` with its origin, license, files, and role.
- Use Gemini 3.5 or newer, at least one Google agent framework, and at least one
  Google Cloud infrastructure service.
- Optimize for autonomous action, architectural discipline, reproducibility,
  visible failure handling, and a live unedited demonstration.
- Prefer one coherent vertical slice over five shallow feature demonstrations.

## Product direction

Continuum safely carries institutional intent across agent failures and
lifecycle transitions. Succession Protocol is the product headline. Promise
Ledger, Negative Space Sentinel, Constitutional Court, and Antibody Foundry are
supporting services in the same lifecycle.

## Working style

- Make consequential actions reversible and auditable.
- Use append-only events and explicit state transitions.
- Require idempotency keys for side effects.
- Separate proposals, policy decisions, execution, and verification.
- Prefer deterministic evaluation fixtures over unverifiable claims.
- Never commit secrets, credentials, or generated cloud state.

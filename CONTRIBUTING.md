# Contributing to Continuum

Continuum welcomes narrowly scoped contributions that preserve its central guarantee:
an unfinished obligation may move to a successor only after the predecessor is fenced,
the minimum authorized context is reconstructed, and the resulting effect is independently
verifiable under the declared trust model.

## Before opening a change

1. Read `AGENTS.md`, `docs/PROJECT_BRIEF.md`, `docs/ARCHITECTURE.md`,
   `docs/ORIGINALITY.md`, `SECURITY.md`, and `GOVERNANCE.md`.
2. Open an issue for changes to a public contract, trust boundary, dependency, evidence
   claim, or cloud resource. Security reports follow `SECURITY.md`, never a public issue.
3. Keep one coherent vertical slice. Do not add an agent, model, or service solely to
   increase a technology count.
4. Never commit credentials, personal data, generated cloud state, private evidence, or
   unsigned material described as independent review.

## Provenance and originality

All source written for this repository must be original or used under a compatible license.
If a change incorporates non-standard pre-existing material, update
`docs/ORIGINALITY.md` in the same commit with its origin, copyright owner, license,
exact files, modifications, and role. General ideas and established engineering patterns
do not require source attribution; copied text, code, media, fixtures, and templates do.

By submitting a contribution, you certify that you have the right to submit it under the
repository's Apache-2.0 license and that the commit metadata truthfully identifies its
authors. AI-assisted work must be reviewed by the submitting human, tested, and disclosed
in the pull request when it materially shaped code, prose, or media.

## Development workflow

```bash
git switch -c feature/short-purpose
./scripts/quality-gate.sh
git diff --check
```

The locked quality gate runs the TypeScript interoperability consumer, all Python tests
with warnings as errors, genuine 100.0% statement and branch coverage over every module
under `src/continuum`, conformance, release-truth, configuration, assurance, and witness
audits. Coverage proves measured execution, not semantic correctness; the distinct gates
remain necessary.

Pull requests must:

- explain the user or assurance outcome and the smallest trust boundary changed;
- include negative and failure-path tests, not only a happy path;
- make state changes append-only, transitions explicit, and side effects idempotent;
- update schemas, fixtures, threat/claim documentation, and originality records together;
- identify rollout and rollback for operational changes;
- pass required checks and receive review from the relevant `CODEOWNERS` entry;
- avoid force-pushes after review unless the reviewer is notified of the new commit range.

The live Google Cloud lifecycle is deliberately not executed by regular pull-request CI.
It requires credentials, project authority, network services, and billable resources.
Changes that affect the Google binding therefore also need the manual exact-commit proof
procedure in `docs/CLOUD_RUNBOOK.md`; regular CI must not be represented as that proof.

## Review standard

Reviewers check correctness, fail-closed behavior, least privilege, privacy, provenance,
backward compatibility, observable failure, and whether the stated evidence supports the
claim. Maintainers may request a design note for protocol or governance changes. Small,
reversible commits are preferred, but commits must not split a safety invariant across an
unreviewable intermediate state.

See `GOVERNANCE.md` for decision rights and `CODE_OF_CONDUCT.md` for community conduct.

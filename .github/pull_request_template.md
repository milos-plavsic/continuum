## Outcome

<!-- What user, protocol, security, or assurance outcome changes? -->

## Trust boundary and failure behavior

<!-- Smallest boundary changed; fail-closed behavior; negative paths tested. -->

## Verification

- [ ] `./scripts/quality-gate.sh`
- [ ] New behavior and failure paths are tested
- [ ] Rollout and rollback are documented when operational state changes
- [ ] No credential, personal data, generated cloud state, or private evidence is committed

## Provenance and disclosure

- [ ] Work is original or `docs/ORIGINALITY.md` records every incorporated source/license
- [ ] Material AI assistance is disclosed and human-reviewed
- [ ] Authorship and co-author trailers are accurate
- [ ] Claims name their evidence and non-claims

## Live-cloud impact

<!-- Does this require a fresh exact-commit GCP run? Regular CI is not live-cloud proof. -->

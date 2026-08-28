# Project governance

## Purpose and principles

Continuum is an Apache-2.0 reference implementation and 0.1-draft protocol profile for
governed agent succession. Governance follows the same principles as the product:
explicit authority, least privilege, append-only decisions, independently inspectable
evidence, reversible operations, and no silent promotion of uncertain claims.

## Roles

- **Maintainer:** Milos Plavsic is the current project maintainer and release authority.
- **Contributor:** anyone whose accepted code, documentation, tests, design, or media is
  recorded in Git history and attribution.
- **Reviewer:** a maintainer-designated contributor reviewing a particular change. Review
  authority is scoped to that change and does not imply release authority.
- **Security responder:** the maintainer or a named delegate handling a private report.
- **External witness:** an independent person who reviews an exact release packet and signs
  a bounded statement. A witness has no project authority and is not a maintainer merely by
  signing.

Roles, current ownership, and protected paths are reflected in `.github/CODEOWNERS`.
GitHub or Devpost team membership, authorship, prize allocation, and governance authority
are distinct facts and must be recorded separately rather than inferred from one another.

## Decisions

Routine, reversible implementation decisions use pull-request review and required CI.
The maintainer decides after considering written technical objections. The following need
an Architecture Decision Record or equivalent design note, explicit maintainer approval,
and migration/rollback guidance:

- changing a public contract, canonicalization, signature, or conformance level;
- weakening an authority, identity, privacy, verification, or evidence boundary;
- adding a required provider, model, external service, or persistent data category;
- changing license, governance, disclosure policy, or a headline assurance claim.

Security fixes may merge under an embargoed advisory before public detail is available.
The eventual public record must explain the affected versions without disclosing secrets.

## Releases and assurance

A release requires green protected checks, an immutable source commit, a clean dependency
lock, provenance and originality review, and synchronized release truth. Regular CI is
credential-free and does not prove live GCP behavior. A cloud-proof release is a separately
authorized exact-commit operation. An external-witness claim requires a valid independent
signature; first-party artifacts cannot satisfy it.

The maintainer may roll back or revoke a release when a safety invariant, credential,
dependency, or evidence claim is compromised. Historical evidence remains append-only and
is marked failed or superseded rather than rewritten.

## Conflicts and appeals

Participants disclose financial, employment, judging, or authorship conflicts relevant to
a decision. A conflicted reviewer should abstain. Technical objections should name the
invariant, evidence, and smallest safe alternative. The maintainer records the final reason
on the issue or pull request. Conduct and security matters follow their private policies.

## Succession and bus factor

The current single-maintainer model is a disclosed project risk. Before adding a second
release maintainer, that person must have sustained reviewed contributions, security-policy
familiarity, hardware-backed MFA, and explicit acceptance recorded in a pull request.
Repository transfer requires verification of protected-branch rules, secrets, release keys,
Devpost ownership, and outstanding advisories; credentials are rotated, never handed over.

If the maintainer is unavailable, contributors may fork under Apache-2.0, but cannot claim
to publish an official Continuum release until project control is explicitly transferred.

## Amendments

Governance changes use a public pull request with rationale and a minimum seven-day comment
period, except urgent security corrections. The repository history is the decision log.

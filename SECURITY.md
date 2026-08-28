# Security policy

## Supported versions

Until the 0.1 protocol profile reaches a tagged stable release, security fixes are applied
to the latest commit on `main` only. Historical cloud-proof archives are immutable evidence
and are not retroactively patched; a superseding release records the correction.

| Version | Supported |
| --- | --- |
| latest `main` | yes |
| older commits and proof archives | no; retained for audit |

## Report a vulnerability privately

Do not open a public issue for a suspected vulnerability, leaked credential, unsafe judge
capability, identity-policy error, or evidence that contains personal or secret data.

Use the repository's **Security → Report a vulnerability** private-reporting form. If that
facility is unavailable, email `milos.plavsic@googlemail.com` with subject
`[Continuum security]` and request an encrypted channel before sending sensitive material.
Do not include live credentials or exploit another person's project.

Include, when safe:

- affected commit, component, deployment profile, and exact preconditions;
- minimal reproduction and expected versus observed result;
- impact on authority, memory, verification, privacy, availability, or supply chain;
- whether the report concerns a currently reachable service;
- suggested remediation or disclosure constraints.

The maintainer will acknowledge a complete report within three business days, provide an
initial severity assessment within seven, and coordinate a target fix/disclosure date.
These are response objectives, not a guarantee. Credit is offered unless the reporter
prefers anonymity or the report is ineligible.

## Scope and safe harbor

In scope are the Continuity Contract implementation, canonicalization and signatures,
authority/fencing gateways, context reconstruction, verifier, judge capability, external
queue, cloud deployment policy, evidence packaging, and supply chain.

Good-faith research is welcome when it:

- uses local fixtures or infrastructure the researcher owns or is authorized to test;
- avoids privacy violations, denial of service, social engineering, persistence, and data
  destruction;
- stops after demonstrating the minimum evidence needed;
- gives reasonable time to remediate before disclosure.

The public showcase is read-only. It is not authorization to probe Google Cloud identities,
private Cloud Run services, Devpost, GitHub accounts, GLEIF, VIES, or other third parties.
No bug bounty or monetary reward is promised.

## Security invariants and evidence ceiling

- Requests never grant their own identity or authority.
- The predecessor is fenced before successor activation.
- Effects require an idempotency key and transactional authorization.
- Raw untrusted input crosses Model Armor before a model or memory boundary.
- The executor cannot issue its own continuity attestation.
- Secrets are forbidden from source, logs, public evidence, and configuration defaults.

Offline verification establishes integrity and semantic consistency under declared inputs.
It does not establish capture provenance, uncompromised infrastructure, upstream factual
truth, or Byzantine consensus. See `docs/TRUST_ASSUMPTIONS.md` and `docs/THREAT_MODEL.md`.

## Dependency and release security

Dependencies are lockfile-resolved; CI builds the non-root runtime image, emits an SPDX
SBOM, and rejects actionable HIGH/CRITICAL vulnerabilities under the documented policy.
CI actions are commit-pinned. Cloud secrets belong in Secret Manager and workload identity
replaces service-account key files. See `docs/SUPPLY_CHAIN.md`.

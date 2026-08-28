# CI and cloud assurance boundary

Continuum uses three deliberately separate assurance profiles. Their machine-readable
source is `config/assurance-profiles.json`; `scripts/check_assurance_profiles.py` prevents
one profile from silently inheriting another profile's claims.

| Profile | Trigger | Credentials / cost | What it actually establishes |
| --- | --- | --- | --- |
| regular CI | every pull request and main push | none / none | locked tests, deterministic integration ports, conformance, measured coverage, local container, SBOM and vulnerability policy |
| live GCP proof | authorized manual run | Google identity / potentially billable | exact-commit behavior observed through Cloud Run, Firestore, Pub/Sub, Vertex AI and Cloud Trace and packaged for offline verification |
| external witness | independent reviewer | reviewer's keyless OIDC identity / none | only after signature: who reviewed which exact release, declared scope, verdict and conflicts |

## Why regular CI does not run the cloud lifecycle

A real lifecycle needs project IAM, Secret Manager, private Cloud Run invocation, a Vertex
AI model call, Pub/Sub redelivery, Firestore mutation, Cloud Tasks, Model Armor, tracing and
an external reversible work item. Giving those authorities to untrusted pull-request code
would violate least privilege and create uncontrolled cost and secret-exfiltration risk.

CI therefore uses deterministic in-memory or fake provider ports and a credential-free local
container. Those tests exercise orchestration, failures and adapter contracts; they do not
claim to exercise Google infrastructure. The live profile is run separately against an exact
deployed commit and published as first-party evidence. The current application proof remains
bound through `docs/submission/current-release.json`.

## Coverage is not correctness

100% statement and branch coverage means every declared Python source location and measured
branch ran under the suite. It does not prove semantic correctness, production fitness,
complete threat coverage, live-cloud behavior, capture provenance, or uncompromised trust
roots. Continuum uses separate contract conformance, adversarial, resilience, stress, cloud,
offline-verification, supply-chain and external-witness controls because those are different
questions. See `docs/QUALITY_PROOF.md`.

## Current external-review status

The protocol and exact-release review request are ready, but no independent reviewer has yet
supplied an accepted Sigstore statement. The machine-readable status is
`AWAITING_EXTERNAL_WITNESS`. First-party test signatures, repository CI, and the internal
read-only verifier cannot change that status.

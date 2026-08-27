# Canonical cloud-run failure ledger

This is an append-only record of unsuccessful attempts immediately preceding the
current canonical proof. A failed run is never renamed, omitted, or counted as proof.
The accepted release remains the single current truth in
[`docs/submission/current-release.json`](submission/current-release.json).

## What failed, and what changed

| Attempt | Observed terminal state | Why it was not proof | Corrective change | What the failure demonstrated |
|---|---|---|---|---|
| `judge-final-ec17dcc-20260827T215707Z` | `CONTEXT_RECONSTRUCTED`; no compliance record, effect, contract, or attestation | VIES returned the real `MS_UNAVAILABLE` semantic outage response. One path still surfaced that response as a raw `ValueError`. | [PR #52](https://github.com/milos-plavsic/continuum/pull/52) classified semantic availability responses, retried only transient cases within the wall-clock budget, and converted exhaustion to the normal pre-model `HOLD`. | An upstream outage could not reach Gemini or mutation, but the public error taxonomy was incomplete. |
| `judge-final-9de7d14-20260827T221526Z` | Lifecycle completed internally; offline verdict `NOT_ASSESSED`; 16 of 17 mandatory objects | The deployment had no configured external GitHub work queue. The external-work-item object was absent; the Firestore sandbox projection was deliberately not accepted as a substitute. | The pre-provisioned reversible [GitHub Issue #41](https://github.com/milos-plavsic/continuum/issues/41) was enabled as the real queue effect. | Completeness is fail-closed: a coherent internal lifecycle cannot be promoted when one mandatory external observation is missing. |
| `judge-final-github-9de7d14-20260827T223000Z` | Compliance verified and v19 activated; stopped before the external effect after repeated `409` responses | A CLI-fed Secret Manager value retained a terminal newline, producing an invalid bearer header. | [PR #53](https://github.com/milos-plavsic/continuum/pull/53) normalizes surrounding secret whitespace, rejects embedded whitespace, and regression-tests the exact Authorization header. | Authority moved safely, but a malformed provider credential could not be treated as a successful or ambiguous effect. |

The subsequent exact-commit run
`judge-final-d4d7d52-20260827T223700Z` reached independent `VERIFIED`; its
credential-free packet is the public
[`cloud-proof-d4d7d52`](https://github.com/milos-plavsic/continuum/releases/tag/cloud-proof-d4d7d52)
release. That packet proves the claims stated by its verifier; it does not retroactively
turn the attempts above into successful runs.

## Functional lineage versus release pin

The small final documentation PR is not presented as the implementation:

1. [PR #51](https://github.com/milos-plavsic/continuum/pull/51) implemented bounded
   external evidence, cache policy, workflow-engine integration, selection governance,
   trust semantics, and the simplified judge boundary.
2. [PR #52](https://github.com/milos-plavsic/continuum/pull/52) fixed the observed VIES
   semantic-outage path.
3. [PR #53](https://github.com/milos-plavsic/continuum/pull/53) fixed the observed
   Secret Manager/provider-header path.
4. [PR #54](https://github.com/milos-plavsic/continuum/pull/54) published the accepted
   exact-commit cloud proof and synchronized its machine-readable release facts.
5. [PR #55](https://github.com/milos-plavsic/continuum/pull/55) only pinned the final
   no-role showcase revision and Devpost read-back. Its documentation-only size is
   intentional and must not be used as a proxy for the project's engineering depth.

Detailed chronological notes remain in
[`docs/hackathon-build/build-notes.md`](hackathon-build/build-notes.md). Cloud capture
provenance and the offline verifier's epistemic ceiling remain explicit in
[`docs/CLOUD_PROOF.md`](CLOUD_PROOF.md).

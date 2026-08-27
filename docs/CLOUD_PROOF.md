# Google Cloud deployment proof

## Current verified release

A fresh autonomous reference run completed on August 27, 2026 and passed both
the separately deployed verifier and the credential-free, network-free offline
semantic verifier.

- Project `project-0775d12a-00a3-48d2-b13`, region `europe-west1`.
- Run `judge-devpost26-0d823369-ce4b14a8e848`; canonical trace
  `232574755dc80097fd74e292b103ce2a`.
- Deployed source commit
  `0d8233695eeae0980088f3209f531181852a4a60`.
- Immutable image digest
  `sha256:c54bfc0b6baa85291fcecfc643641fe59972dc33806d75917dd21ae33fc4a010`.
- Cloud Build `2115c7bf-1bd3-4fd7-96af-332feac7cd3b`, with verified
  provenance requested and SLSA build level 3 reported by Artifact Registry.
- Bundle `urn:uuid:2b0fdafa-a3d0-40d2-89c7-8a3a2ceb7734`; bundle digest
  `sha256:acc0f540fa662270c4703f7bc026a89d46e4b8a8fefc0636ccae4dc38e84951e`.
- Offline result `PASS`; report digest
  `sha256:9cc453ea31a1dced264412be1f1215fc01120d58e418d735113a395868bb3e60`.

The five ready services were independently read from the Cloud Run API:

| Role | Ready revision | User-managed service identity |
|---|---|---|
| Control | `continuum-control-00056-vhd` | `continuum-control@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |
| Predecessor v17 | `continuum-agent-v17-00028-2c4` | `continuum-v17@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |
| Successor v18 | `continuum-agent-v18-00057-hp4` | `continuum-v18@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |
| Warm successor v19 | `continuum-agent-v19-00048-5b6` | `continuum-v19@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |
| Independent verifier | `continuum-verifier-00028-ccw` | `continuum-verifier@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |

All five revisions reported the same source commit, protocol and immutable
image digest. The content-addressed mandatory objects establish internal
consistency of:

- a real Google ADK call to `gemini-3.6-flash` from the v18 investigator
  identity, proposing only `initiate_governed_succession`, and selecting warm
  v19 from the eligible v18/v19 set through an explicit 18-second recovery
  versus very-high-assurance trade-off; v20 was rejected before model access;
- a Google Model Armor `MATCH_FOUND` receipt proving the raw injection fixture
  was denied before Gemini, plus a separately reconciled GitHub issue #41;
- a closed, policy-versioned evidence chain whose issuer, subject, type,
  authority, freshness, payload digest and authentication reference were
  recomputed by the independent verifier before incident policy admission;
- a verifier-recomputed minimum-context receipt: two verified facts included and
  raw untrusted input, a secret, model inference and revoked memory excluded;
- a practical successor-agent workflow that queried the official GLEIF and EU
  VIES endpoints, used ADK + `gemini-3.6-flash` for a cited decision pack, and
  passed deterministic admission only under `SANDBOX_ONLY`; its content digest
  and selected workload identity are bound to the execution receipt;
- an owning-API Firestore event, matching projection, and published outbox;
- two deliveries of Pub/Sub message `21369624131526467`;
- one reconciled provider effect despite redelivery;
- v17 action denial with `STALE_EPOCH` and revoked-memory denial;
- five control-authored pre-attestation artifacts followed by the verifier-only
  sixth artifact after direct authority, compliance, and provider reads;
- 43 spans read directly from the Cloud Trace API, including
  `generate_content gemini-3.6-flash`, all succession lifecycle spans, action
  gateway calls, and the separate verifier call.

The raw capture is retained locally at
`artifacts/cloud/judge-0d823369-20260827T200349Z` and
is intentionally gitignored: repository policy forbids committing generated
cloud state. The complete security-audited, content-addressed packet is published
as a [GitHub Release asset](https://github.com/milos-plavsic/continuum/releases/download/cloud-proof-0d823369/continuum-cloud-proof-0d823369.tar.gz),
with archive SHA-256
`699911068eb642fdbae224afd84c2db23e658f396ddf3325f45c08172a157069`.
Judges can therefore reproduce the offline verdict without Google credentials.

## Reproduction and validity boundary

```bash
set -a
source deploy/cloud.env
set +a
export CONTINUUM_GIT_SHA="$(git rev-parse HEAD)"
bash scripts/cloud/bootstrap.sh
bash scripts/cloud/build-deploy.sh
export CONTINUUM_EVIDENCE_DIR="artifacts/cloud/$(date -u +%Y%m%dT%H%M%SZ)"
bash scripts/cloud/run-cloud-proof.sh
```

`run-cloud-proof.sh` starts once and then only observes. Cloud Tasks crosses
the persisted deadline, Pub/Sub resumes the effect-bearing lifecycle after a
deliberate first-delivery failure, and the independent verifier alone issues
the attestation. The collector reads exact-run objects from Google APIs and
Cloud Logging; the final verifier performs no network or credential access.
Consequently its `PASS` proves content integrity and cross-object semantic
consistency, not that the capture itself came from those APIs. New deployments
also require a Google-signed SLSA v1 statement whose subject matches the image
digest read from every Cloud Run revision. The signature for this release was
independently checked with Google's pinned Hosted Worker KMS public key and
OpenSSL (`Verified OK`). Because this build used manual `gcloud` source upload,
that authentication is not represented as cryptographic GitHub-source
provenance. See [PROVENANCE.md](PROVENANCE.md).

This proof applies only to the deployed source commit and image digest named
above. Any newer application release must be deployed and recaptured; local
tests or a historical bundle never inherit a cloud verdict.

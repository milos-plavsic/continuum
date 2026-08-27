# Google Cloud deployment proof

## Current verified release

A fresh autonomous reference run completed on August 27, 2026 and passed both
the separately deployed verifier and the credential-free, network-free offline
semantic verifier.

- Project `project-0775d12a-00a3-48d2-b13`, region `europe-west1`.
- Run `supplier-golden-20260827T023539Z`; canonical trace
  `86ef84df3fe1ddf17761b558cb08c678`.
- Deployed source commit
  `abb44720631cd54c6837b20d0b9870919f6a6b5b`.
- Immutable image digest
  `sha256:e3be7452fd1b619de5c0a0632a6f488f02938276e95313d7eea7e1fef6262021`.
- Bundle `urn:uuid:a3f1b86a-7f71-442d-be06-59f5c042d089`; bundle digest
  `sha256:b7b7901ae9f5ac64ddc7b76c9a9b9444e28422a4918e3dbffd628471ea260a1e`.
- Offline result `PASS`; report digest
  `sha256:989d258c8f42b164ceed0f180140f48ea87f709ae26d7997a1265af6ad8d08f6`.

The five ready services were independently read from the Cloud Run API:

| Role | Ready revision | User-managed service identity |
|---|---|---|
| Control | `continuum-control-00030-f96` | `continuum-control@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |
| Predecessor v17 | `continuum-agent-v17-00015-wdn` | `continuum-v17@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |
| Successor v18 | `continuum-agent-v18-00025-xzd` | `continuum-v18@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |
| Warm successor v19 | `continuum-agent-v19-00016-w28` | `continuum-v19@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |
| Independent verifier | `continuum-verifier-00015-w5r` | `continuum-verifier@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |

All five revisions reported the same source commit, protocol and immutable
image digest. The content-addressed mandatory objects establish internal
consistency of:

- a real Google ADK call to `gemini-3.6-flash` from the v18 identity, proposing
  only `initiate_governed_succession`, and selecting v18 from the eligible
  v18/v19 set with a complete evidence manifest plus selective, claim-linked
  citations; v20 was rejected before model access;
- a verifier-recomputed minimum-context receipt: two verified facts included and
  raw untrusted input, a secret, model inference and revoked memory excluded;
- a practical successor-agent workflow that queried the official GLEIF and EU
  VIES endpoints, used ADK + `gemini-3.6-flash` for a cited decision pack, and
  passed deterministic admission only under `SANDBOX_ONLY`; its content digest
  and selected workload identity are bound to the execution receipt;
- an owning-API Firestore event, matching projection, and published outbox;
- two deliveries of Pub/Sub message `21359656145852778`;
- one reconciled provider effect despite redelivery;
- v17 action denial with `STALE_EPOCH` and revoked-memory denial;
- five control-authored pre-attestation artifacts followed by the verifier-only
  sixth artifact after direct authority, compliance, and provider reads;
- 118 spans read directly from the Cloud Trace API, including
  `generate_content gemini-3.6-flash`, all succession lifecycle spans, action
  gateway calls, and the separate verifier call.

The raw capture is retained locally at
`artifacts/cloud/supplier-golden-20260827T023539Z` and
is intentionally gitignored: repository policy forbids committing generated
cloud state. The complete security-audited, content-addressed packet is published
as a [GitHub Release asset](https://github.com/milos-plavsic/continuum/releases/download/cloud-proof-abb4472/continuum-cloud-proof-abb4472.tar.gz),
with archive SHA-256
`5f7b34322c0122349a73d9fea43f89cd4ef053ea5179d42603ae0c799536f697`.
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
digest read from every Cloud Run revision. See [PROVENANCE.md](PROVENANCE.md).

This proof applies only to the deployed source commit and image digest named
above. Any newer application release must be deployed and recaptured; local
tests or a historical bundle never inherit a cloud verdict.

# Google Cloud deployment proof

## Current verified release

A fresh autonomous reference run completed on August 26, 2026 and passed both
the separately deployed verifier and the credential-free, network-free offline
semantic verifier.

- Project `project-0775d12a-00a3-48d2-b13`, region `europe-west1`.
- Run `golden-0ceda49-20260826-182725`; canonical trace
  `caa315c2c9181abd25091a46f59eceb6`.
- Deployed source commit
  `0ceda492a439466bef4536f695f86d2a7b8f01e4`.
- Immutable image digest
  `sha256:ddc57999674ec755ffc92a9c004d7265ada06ff56424f9ee46121c7b511a7b96`.
- Bundle `urn:uuid:be58870d-6398-4bf5-a1a2-90dc3eca3e86`; bundle digest
  `sha256:5402436105058196b2665c1e8242b6edf46178775bbee7fbba3d6ecd7f511be9`.
- Offline result `PASS`; report digest
  `sha256:683f27d5c4fe265a961f153dc069be23ae14e5160a9a34ba6898b4a47ae7261d`.

The five ready services were independently read from the Cloud Run API:

| Role | Ready revision | User-managed service identity |
|---|---|---|
| Control | `continuum-control-00024-5d7` | `continuum-control@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |
| Predecessor v17 | `continuum-agent-v17-00012-x6r` | `continuum-v17@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |
| Successor v18 | `continuum-agent-v18-00019-cjw` | `continuum-v18@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |
| Warm successor v19 | `continuum-agent-v19-00010-8sj` | `continuum-v19@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |
| Independent verifier | `continuum-verifier-00012-njg` | `continuum-verifier@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |

All five revisions reported the same source commit, protocol and immutable
image digest. The 13 content-addressed mandatory objects prove:

- a real Google ADK call to `gemini-3.6-flash` from the v18 identity, citing all
  exact incident evidence, proposing only `initiate_governed_succession`, and
  selecting v18 from the eligible v18/v19 set with Cloud Run, identity and image
  citations; v20 was rejected for health and jurisdiction before model access;
- a verifier-recomputed minimum-context receipt: two verified facts included and
  raw untrusted input, a secret, model inference and revoked memory excluded;
- an owning-API Firestore event, matching projection, and published outbox;
- two deliveries of Pub/Sub message `21350299420507528`;
- one reconciled provider effect despite redelivery;
- v17 action denial with `STALE_EPOCH` and revoked-memory denial;
- five control-authored pre-attestation artifacts followed by the verifier-only
  sixth artifact after direct authority, compliance, and provider reads;
- 104 spans read directly from the Cloud Trace API, including
  `generate_content gemini-3.6-flash`, all succession lifecycle spans, action
  gateway calls, and the separate verifier call.

The raw capture is retained locally at
`artifacts/cloud/golden-0ceda49-20260826-182725` and
is intentionally gitignored: repository policy forbids committing generated
cloud state. The complete security-audited, content-addressed packet is published
as a [GitHub Release asset](https://github.com/milos-plavsic/continuum/releases/download/cloud-proof-0ceda49/continuum-cloud-proof-0ceda49.tar.gz),
with archive SHA-256
`8a466cf1ef015f866e63e4fb08cb40458a09fe90ba2713ba1d638c39feb86be5`.
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

This proof applies only to the deployed source commit and image digest named
above. Any newer application release must be deployed and recaptured; local
tests or a historical bundle never inherit a cloud verdict.

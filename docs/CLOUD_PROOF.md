# Google Cloud deployment proof

## Current verified release

A fresh autonomous reference run completed on August 26, 2026 and passed both
the separately deployed verifier and the credential-free, network-free offline
semantic verifier.

- Project `project-0775d12a-00a3-48d2-b13`, region `europe-west1`.
- Run `golden-4d676b1-20260826-04`; canonical trace
  `4d9f2269e752107a926bd5ef90030b54`.
- Deployed source commit
  `4d676b1ed4bbf2394dbac777fcaa1499f54f560b`.
- Immutable image digest
  `sha256:b87b7ce0242a98abe1e35427f3e3447c3f43c55ea8bb25c3a0be04bf23f66e92`.
- Bundle `urn:uuid:e8cf6157-2a35-46ad-a399-4a35d5b56988`; bundle digest
  `sha256:63e21f44bfd8285fd2513e982f181a8a17311b6216a8258b0971d12e8fde07bc`.
- Offline result `PASS`; report digest
  `sha256:33709f67cf9a6a31b50925efb60d728ee28593f2e093d0d1c3d77bbad7fcf483`.

The five ready services were independently read from the Cloud Run API:

| Role | Ready revision | User-managed service identity |
|---|---|---|
| Control | `continuum-control-00022-bb7` | `continuum-control@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |
| Predecessor v17 | `continuum-agent-v17-00011-mdk` | `continuum-v17@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |
| Successor v18 | `continuum-agent-v18-00017-sn5` | `continuum-v18@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |
| Warm successor v19 | `continuum-agent-v19-00008-ncl` | `continuum-v19@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |
| Independent verifier | `continuum-verifier-00011-gkt` | `continuum-verifier@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |

All five revisions reported the same source commit, protocol and immutable
image digest. The 13 content-addressed mandatory objects prove:

- a real Google ADK call to `gemini-3.6-flash` from the v18 identity, citing all
  exact incident evidence, proposing only `initiate_governed_succession`, and
  selecting v18 from the eligible v18/v19 set with Cloud Run, identity and image
  citations; v20 was rejected for health and jurisdiction before model access;
- a verifier-recomputed minimum-context receipt: two verified facts included and
  raw untrusted input, a secret, model inference and revoked memory excluded;
- an owning-API Firestore event, matching projection, and published outbox;
- two deliveries of Pub/Sub message `21341560616619773`;
- one reconciled provider effect despite redelivery;
- v17 action denial with `STALE_EPOCH` and revoked-memory denial;
- five control-authored pre-attestation artifacts followed by the verifier-only
  sixth artifact after direct authority, compliance, and provider reads;
- 69 spans read directly from the Cloud Trace API, including
  `generate_content gemini-3.6-flash`, all succession lifecycle spans, action
  gateway calls, and the separate verifier call.

The raw capture is retained locally at
`artifacts/cloud/golden-4d676b1-20260826-04` and
is intentionally gitignored: repository policy forbids committing generated
cloud state. The identifiers and digests above are safe, reproducible
fingerprints; the content-addressed bundle can be supplied separately to judges.

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

# Google Cloud deployment proof

## Current verified release

A fresh autonomous reference run completed on August 26, 2026 and passed both
the separately deployed verifier and the credential-free, network-free offline
semantic verifier.

- Project `project-0775d12a-00a3-48d2-b13`, region `europe-west1`.
- Run `run-20260826T021240Z`; canonical trace
  `41d27518e9dad2c02a10cffe3c82c534`.
- Deployed source commit
  `501a80ce50496a39cc822a69fc73ec7d44267dbd`.
- Immutable image digest
  `sha256:4c538b4cd6e9f86323913f017bdf21fc5a80c07968104c798b9b67ce662706e7`.
- Bundle `urn:uuid:5ac2c145-e8b1-4e19-a468-6d71f3c27430`; bundle digest
  `sha256:5052d0bfbc261c7880981e2ab545fe620e818f7a189866026ed97434738ac2da`.
- Offline result `PASS`; report digest
  `sha256:b6c53e6805b6497c21361503f49be782b0433e33569f96d0e52ee4cd8c80ac32`.

The four ready services were independently read from the Cloud Run API:

| Role | Ready revision | User-managed service identity |
|---|---|---|
| Control | `continuum-control-00014-q8t` | `continuum-control@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |
| Predecessor v17 | `continuum-agent-v17-00007-8tk` | `continuum-v17@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |
| Successor v18 | `continuum-agent-v18-00009-x79` | `continuum-v18@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |
| Independent verifier | `continuum-verifier-00007-vq9` | `continuum-verifier@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |

All four revisions reported the same source commit, protocol and immutable
image digest. The 12 content-addressed mandatory objects prove:

- a real Google ADK call to `gemini-3.6-flash` from the v18 identity, citing all
  three exact event IDs and proposing only `initiate_governed_succession`;
- an owning-API Firestore event, matching projection, and published outbox;
- two deliveries of Pub/Sub message `21335889119988474`;
- one reconciled provider effect despite redelivery;
- v17 action denial with `STALE_EPOCH` and revoked-memory denial;
- five control-authored pre-attestation artifacts followed by the verifier-only
  sixth artifact after direct authority, compliance, and provider reads;
- 63 spans read directly from the Cloud Trace API, including
  `generate_content gemini-3.6-flash`, all succession lifecycle spans, action
  gateway calls, and the separate verifier call.

The raw capture is retained locally at `artifacts/cloud/20260826T022245Z` and
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

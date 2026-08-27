# Google Cloud deployment proof

## Current verified release

A fresh autonomous reference run completed on August 27, 2026 and passed both
the separately deployed verifier and the credential-free, network-free offline
semantic verifier.

- Project `project-0775d12a-00a3-48d2-b13`, region `europe-west1`.
- Run `supplier-slsa-20260827T142325Z`; canonical trace
  `d9ea0337191b678fe497ca815e67ece4`.
- Deployed source commit
  `5e579f4cdcb3b85d07f6e80fc6ff825dd85da463`.
- Immutable image digest
  `sha256:f83ba3d1e9405fdece32f1fbe064a70c0dc9b92cb681475f7f7730d24b7e9328`.
- Cloud Build `09e308d5-409d-4b37-94c6-d3577636000b`, with verified
  provenance requested and SLSA build level 3 reported by Artifact Registry.
- Bundle `urn:uuid:10271531-a3fc-42f3-baa3-87c753ef113b`; bundle digest
  `sha256:0b474c98764433ebd868048b3045a246b0ba3a0f65612873ee26f3b3cc48e26f`.
- Offline result `PASS`; report digest
  `sha256:26953a4f8f94f6862b7e7b9e03b31d9c0182992035ec144f57920310fa42d82e`.

The five ready services were independently read from the Cloud Run API:

| Role | Ready revision | User-managed service identity |
|---|---|---|
| Control | `continuum-control-00040-m2g` | `continuum-control@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |
| Predecessor v17 | `continuum-agent-v17-00020-gcj` | `continuum-v17@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |
| Successor v18 | `continuum-agent-v18-00035-84f` | `continuum-v18@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |
| Warm successor v19 | `continuum-agent-v19-00026-299` | `continuum-v19@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |
| Independent verifier | `continuum-verifier-00020-t75` | `continuum-verifier@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |

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
- two deliveries of Pub/Sub message `21367815037712071`;
- one reconciled provider effect despite redelivery;
- v17 action denial with `STALE_EPOCH` and revoked-memory denial;
- five control-authored pre-attestation artifacts followed by the verifier-only
  sixth artifact after direct authority, compliance, and provider reads;
- 124 spans read directly from the Cloud Trace API, including
  `generate_content gemini-3.6-flash`, all succession lifecycle spans, action
  gateway calls, and the separate verifier call.

The raw capture is retained locally at
`artifacts/cloud/supplier-slsa-20260827T142325Z` and
is intentionally gitignored: repository policy forbids committing generated
cloud state. The complete security-audited, content-addressed packet is published
as a [GitHub Release asset](https://github.com/milos-plavsic/continuum/releases/download/cloud-proof-5e579f4/continuum-cloud-proof-5e579f4.tar.gz),
with archive SHA-256
`41c404b56af0b2cfc5073c88df73bc89b29e60b9f20572d4b5acc61ebb8e3e02`.
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

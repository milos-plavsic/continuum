# Google Cloud deployment proof

## Current verified release

A fresh autonomous reference run completed on August 27, 2026 and passed both
the separately deployed verifier and the credential-free, network-free offline
semantic verifier.

- Project `project-0775d12a-00a3-48d2-b13`, region `europe-west1`.
- Run `standards-a1e00ac-20260827T163808Z`; canonical trace
  `7f2154874a7a8f4e9ad6b8dea480625c`.
- Deployed source commit
  `a1e00ac188c5597150fb7c6de142224d086c4995`.
- Immutable image digest
  `sha256:608e941c082a7d675db8ccf0d9bd9807026437958a91affd473abfbdef44c996`.
- Cloud Build `d930ff76-b1e8-4de0-86ee-c33a970d1fdd`, with verified
  provenance requested and SLSA build level 3 reported by Artifact Registry.
- Bundle `urn:uuid:b23e074f-4441-4e69-9b33-f12ebb316c5b`; bundle digest
  `sha256:08d6aad22e89bd757508ba26f05d2481cd99cc33e5f4f303c74f9264c0ee6b3c`.
- Offline result `PASS`; report digest
  `sha256:3e0e01fdf19c10446a8b0a8e69bee8179ad0749dac64a5047b306f75df87f5a8`.

The five ready services were independently read from the Cloud Run API:

| Role | Ready revision | User-managed service identity |
|---|---|---|
| Control | `continuum-control-00046-575` | `continuum-control@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |
| Predecessor v17 | `continuum-agent-v17-00023-v2t` | `continuum-v17@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |
| Successor v18 | `continuum-agent-v18-00041-pbz` | `continuum-v18@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |
| Warm successor v19 | `continuum-agent-v19-00032-qjs` | `continuum-v19@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |
| Independent verifier | `continuum-verifier-00023-zvk` | `continuum-verifier@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |

All five revisions reported the same source commit, protocol and immutable
image digest. The content-addressed mandatory objects establish internal
consistency of:

- a real Google ADK call to `gemini-3.6-flash` from the v18 identity, proposing
  only `initiate_governed_succession`, and selecting v18 from the eligible
  v18/v19 set with a complete evidence manifest plus selective, claim-linked
  citations; v20 was rejected before model access;
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
- 89 spans read directly from the Cloud Trace API, including
  `generate_content gemini-3.6-flash`, all succession lifecycle spans, action
  gateway calls, and the separate verifier call.

The raw capture is retained locally at
`artifacts/cloud/standards-a1e00ac-20260827T163808Z` and
is intentionally gitignored: repository policy forbids committing generated
cloud state. The complete security-audited, content-addressed packet is published
as a [GitHub Release asset](https://github.com/milos-plavsic/continuum/releases/download/cloud-proof-a1e00ac/continuum-cloud-proof-a1e00ac.tar.gz),
with archive SHA-256
`fd64cafab0c030bf73775c46699276176552dd180f1c898bf5a48f399a8cea8a`.
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

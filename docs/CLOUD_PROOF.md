# Google Cloud deployment proof

## Current verified release

A fresh autonomous reference run completed on August 27, 2026 and passed both
the separately deployed verifier and the credential-free, network-free offline
semantic verifier.

- Project `project-0775d12a-00a3-48d2-b13`, region `europe-west1`.
- Run `judge-final-d4d7d52-20260827T223700Z`; canonical trace
  `ff88d5ebd20687d1b468cd5f5f66a7c1`.
- Deployed source commit
  `d4d7d52e56c3d3c123a708a279be6bda7189e647`.
- Immutable image digest
  `sha256:4c4b63c7ddaa9a77b26856cc5e99beae9531dac9aff92aac4d773d79b00aa595`.
- Cloud Build `4736fd56-509c-4600-a55c-076c56970abf`, with verified
  provenance requested and SLSA build level 3 reported by Artifact Registry.
- Bundle `urn:uuid:70c3cde9-5071-417a-bebb-b8408ede9749`; bundle digest
  `sha256:9d3bda17cdbb24c2c619a97d9425b92164e17314968aa87c971e587d40df2504`.
- Offline result `PASS`; report digest
  `sha256:405be9a12df92369488b1a5da2b1f592a6eb9e9e962df23df2d1bc50bd7a5401`.

The five ready services were independently read from the Cloud Run API:

| Role | Ready revision | User-managed service identity |
|---|---|---|
| Control | `continuum-control-00062-s6x` | `continuum-control@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |
| Predecessor v17 | `continuum-agent-v17-00031-nld` | `continuum-v17@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |
| Successor v18 | `continuum-agent-v18-00065-6d9` | `continuum-v18@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |
| Warm successor v19 | `continuum-agent-v19-00056-k97` | `continuum-v19@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |
| Independent verifier | `continuum-verifier-00031-qlq` | `continuum-verifier@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com` |

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
  VIES endpoints, obtained GLEIF `LIVE`, and—because VIES reported
  `MS_UNAVAILABLE`—used a still-fresh `CACHED_WITHIN_POLICY` observation from
  prior independently verified run `judge-devpost26-0d823369-ce4b14a8e848`;
  the cache receipt binds its source evidence and attestation rather than
  relabelling it live. ADK + `gemini-3.6-flash` produced a cited decision pack and
  passed deterministic admission only under `SANDBOX_ONLY`; its content digest
  and selected workload identity are bound to the execution receipt;
- an owning-API Firestore event, matching projection, and published outbox;
- two deliveries of Pub/Sub message `21375039210423441`;
- one reconciled provider effect despite redelivery;
- v17 action denial with `STALE_EPOCH` and revoked-memory denial;
- five control-authored pre-attestation artifacts followed by the verifier-only
  sixth artifact after direct authority, compliance, and provider reads;
- 174 spans read directly from the Cloud Trace API, including
  `generate_content gemini-3.6-flash`, all succession lifecycle spans, action
  gateway calls, and the separate verifier call.

The raw capture is retained locally at
`artifacts/cloud/judge-final-d4d7d52-20260827T223700Z` and
is intentionally gitignored: repository policy forbids committing generated
cloud state. The complete security-audited, content-addressed packet is published
as a [GitHub Release asset](https://github.com/milos-plavsic/continuum/releases/download/cloud-proof-d4d7d52/continuum-cloud-proof-d4d7d52.tar.gz),
with archive SHA-256
`14d2005d1a1360528e2ae84ad72c485ff92963a5ecd9e48121cd56edf790d3f6`.
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

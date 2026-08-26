# Google Cloud deployment proof

## Immutable historical capture

A fresh reference-Google-Cloud run completed at `2026-08-25T23:33:59Z`:

- project `project-0775d12a-00a3-48d2-b13`, region `europe-west1`;
- run `run-20260825T233359Z`, deployed source commit
  `277212d4183a01bcf81ad202f1ca0779c154a05f`;
- immutable image digest
  `sha256:bc861eb7641a99f95e46b566e5f1cb17c5413f561de045a8acfa0a80267363fb`;
- ready revisions `continuum-control-00006-bn2`,
  `continuum-agent-v17-00003-t7l`, `continuum-agent-v18-00003-lww`, and
  `continuum-verifier-00003-vzj`, each running as its distinct user-managed
  service account;
- all 12 mandatory evidence objects captured, including the real
  `gemini-3.6-flash` Vertex call, Firestore event/outbox/projection, two Pub/Sub
  delivery attempts, one effect receipt, predecessor denial, contract export,
  and correlated trace export;
- offline, credential-free, network-free verification result `PASS`, bundle
  `urn:uuid:3583e3ef-1214-4df5-a9c9-4d1bcf72a694`, report digest
  `sha256:dc781cfc38fe4be752b723871bb06d0ab8c448af52d053fa541cae7e521259f8`.

The raw capture remains locally at `artifacts/cloud/20260825T233358Z` and is
intentionally gitignored: repository policy forbids committing generated cloud
state. The capture is reproducible with `scripts/cloud/run-cloud-proof.sh`, and
the content-addressed bundle can be supplied separately to judges.

This record proves only the source commit and image digest named above. A newer
release must be deployed and recaptured from a clean run; its local `report.json`
is authoritative only when `overall` is `PASS` and its scoped Git commit matches
the ready Cloud Run revisions. The repository never inherits a historical cloud
verdict or commits generated provider state.

The local reference implementation proves domain behavior, while the capture
above proves the deployed reference binding. Future releases must repeat the
capture rather than inheriting its result.

## Target topology

- Cloud Run control plane and distinct v17/v18 agent services.
- Distinct user-managed, least-privilege service identities; no key files.
- Artifact Registry images addressed by immutable digest.
- Firestore event authority plus transactional projections/outbox.
- Pub/Sub at-least-once lifecycle delivery and visible redelivery.
- Vertex AI Gemini 3.5+ orchestrated by Google ADK for typed, cited proposals.
- OpenTelemetry traces/logs exported to Google Cloud Observability.

## Evidence bundle

- Project ID, region, deployment timestamp, and Git commit.
- Cloud Run ready revisions, service accounts, and image digests.
- Artifact Registry digests matching registry records.
- Sanitized IAM bindings and enabled APIs.
- Pub/Sub topic/subscription and one redelivery trace.
- Firestore event and projection for the same run ID.
- `/health` and `/build-info` responses containing no secrets.
- Trace Explorer view spanning investigation through verification.

## Acceptance gate

At least one event must cross Pub/Sub, one event/projection must persist in
Firestore, one cited proposal must use Vertex AI from a Cloud Run identity, v17
and v18 must authenticate as distinct principals, and registry digests must
match their deployed revisions. Do not mark these complete until observed.

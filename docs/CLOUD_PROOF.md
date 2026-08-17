# Google Cloud deployment proof plan

The local reference implementation proves domain behavior, not cloud deployment.
A winning submission must separately capture the following observed evidence.

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


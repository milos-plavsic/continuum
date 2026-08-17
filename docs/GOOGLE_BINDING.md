# Google reference binding

The vendor-neutral Continuity Contract is bound to Google Cloud as follows:

- Google ADK `Agent` with Gemini 3.6 Flash produces evidence-cited proposals.
- Cloud Run uses distinct user-managed service identities for v17, v18, control
  plane, and verifier workloads.
- Firestore transactionally appends an event, compare-and-swaps its aggregate
  projection, and writes an outbox entry.
- Pub/Sub transports canonical lifecycle events with at-least-once delivery.
- Gateways verify Google-signed ID tokens for the configured Cloud Run audience,
  then map the authenticated service-account email to a registry principal.
- OpenTelemetry exports the common run/trace ID to Cloud Observability.

Cloud Run deployments must use Application Default Credentials from assigned
service identities. Never set `GOOGLE_APPLICATION_CREDENTIALS` or deploy a key
file. Epoch fencing remains the immediate application authorization boundary;
IAM credential invalidation is separate.

The source adapters are implemented, but the `reference-google-cloud` profile
cannot pass until real project IDs, revisions, identities, Firestore writes,
Pub/Sub redelivery, Vertex AI calls, and traces are captured from deployment.

Official implementation references:

- https://google.github.io/agents-cli/guide/project-structure/
- https://docs.cloud.google.com/python/docs/reference/firestore/latest/google.cloud.firestore_v1.client.Client
- https://docs.cloud.google.com/pubsub/docs/publisher
- https://docs.cloud.google.com/run/docs/securing/service-identity

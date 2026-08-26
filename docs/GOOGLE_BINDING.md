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
- Cloud Tasks invokes the control service only after the persisted expectation
  deadline; the operator does not simulate time or manually advance the run.
- OpenTelemetry exports lifecycle and HTTP spans under the canonical run trace
  ID through the Google Cloud Trace API.

Cloud Run deployments must use Application Default Credentials from assigned
service identities. Never set `GOOGLE_APPLICATION_CREDENTIALS` or deploy a key
file. Epoch fencing remains the immediate application authorization boundary;
IAM credential invalidation is separate.

Source adapters and the prior reference deployment exist, but the current
`reference-google-cloud` release remains unproven until its exact commit is
deployed and fresh project IDs, revisions, identities, Firestore writes,
Pub/Sub redelivery, Vertex AI calls, and traces are captured.

The cloud surface includes authenticated wrapped-push decoding, message-ID and
payload-digest conflict detection, Firestore execution records guarded by one
authority + compliance + idempotency transaction, transactional
event/projection/outbox writes, and an at-least-once outbox dispatcher. The
separately deployed verifier has read-only Firestore access and produces
VERIFIED, FAILED, or INCONCLUSIVE. A second offline evidence verifier uses no
Google credentials or network access and returns `NOT_ASSESSED` rather than
inferring cloud truth from source code or missing captures.

Official implementation references:

- https://google.github.io/agents-cli/guide/project-structure/
- https://docs.cloud.google.com/python/docs/reference/firestore/latest/google.cloud.firestore_v1.client.Client
- https://docs.cloud.google.com/pubsub/docs/publisher
- https://docs.cloud.google.com/run/docs/securing/service-identity

# Minimum operational Agent Registry

The registry is an append-only event projection inside the Continuum control
plane, not a decorative standalone microservice. A logical agent has immutable
versions. Each version binds:

- tenant, owning team, purpose, predecessor/successor lineage;
- exact Google ADK and Gemini model identifiers;
- Artifact Registry URI and immutable digest;
- Cloud Run service, revision, and distinct service identity;
- lifecycle state, current fencing epoch, health, and last-seen evidence;
- action capabilities, memory scopes, and policy-bundle version.

Required operations are register version, list/inspect lineage, resolve an
eligible successor, activate, quarantine, and record heartbeat. Mutations
require an idempotency key, expected epoch, authenticated principal, evidence or
policy reference, and trace ID.

Every action and memory request carries tenant, agent/version, epoch,
obligation, decision, idempotency key, and trace ID. The gateway fails closed if
status, epoch, principal, tenant, capability, scope, decision binding, or request
digest differs from the registry projection.

Cloud IAM authenticates and limits each workload; registry epochs provide
immediate application-level revocation. The demo must not depend on live IAM
binding propagation. No service-account keys belong in source, images, or
environment variables; deployed Cloud Run services use user-managed service
identities and Application Default Credentials.


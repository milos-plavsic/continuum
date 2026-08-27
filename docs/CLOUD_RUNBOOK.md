# Google Cloud deployment runbook

The scripts create source-controlled infrastructure configuration but never
commit generated project state, credentials, service YAML, image digests, or
evidence captures. Capture first lands in a temporary directory and is packaged
as SHA-256-addressed JSON objects. Offline verification performs no network or
credential access.

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

Copy `deploy/cloud.env.example` to an ignored `deploy/cloud.env` and provide a
real project, region, and Firestore location. The deployment uses one immutable
image for four private Cloud Run services with distinct user-managed identities:
control, v17, v18, and independent verifier. Pub/Sub push uses a fifth identity.
Set `CONTINUUM_OPERATOR_MEMBER` to one exact IAM member (for example,
`user:operator@example.com`) permitted to start and inspect control-plane runs.
The deployment replaces the control invoker policy with only that operator and
the dedicated Pub/Sub push identity.

`run-cloud-proof.sh` derives a fresh run and trace identifier, obtains an
audience-bound operator ID token, invokes the server-owned scenario command,
requires independent `PASS`, then performs read-only exact-run collection and
offline semantic verification. It never places the token in the evidence
bundle or writes it to disk.
Every revision is pinned to an Artifact Registry digest and exposes the source
commit, digest, deployment ID, protocol version, Cloud Run revision, and service
name through `/build-info`. `/ready` fails closed when immutable metadata or a
role-specific configuration value is absent.

## Public judge showcase

The effect-bearing services stay private. A sixth, independently deployed Cloud
Run service may expose the static read-only judge page without changing the
validated five-service runtime:

```bash
export CONTINUUM_GIT_SHA="$(git rev-parse HEAD)"
bash scripts/cloud/deploy-showcase.sh
```

`deploy-showcase.sh` builds and resolves an immutable image, assigns a dedicated
`continuum-showcase` service account with no project role, deploys it privately,
and then replaces only that service's invoker policy with `allUsers`. The
showcase has no Firestore, Pub/Sub, Vertex AI, worker, verifier, or control-plane
configuration. All state-changing and internal endpoints therefore fail closed
with `404`; the page links to the separately released credential-free evidence
packet instead of claiming to execute the historical run.

The currently published judge surface is
https://continuum-showcase-rdzvxiysbq-ew.a.run.app. Revision
`continuum-showcase-00006-drz` runs source commit
`524194190d5360451e4784f48b14163e7bc6e5ee` as immutable image digest
`sha256:9d171a0451382b935c000ec9dc7d9db9629351fd29180c1e6984786487d2d17d`.
Its service identity is
`continuum-showcase@project-0775d12a-00a3-48d2-b13.iam.gserviceaccount.com`;
the identity has no project-level role. The page points to the exact hardened
`cloud-proof-d4d7d52` packet. Its mutation probe returns `404`; the service IAM
policy contains only the intentional `allUsers`/`roles/run.invoker` binding.

“No project-level role” is a concrete blast-radius statement, not a reassuring
label. Even if arbitrary code execution were obtained inside the public showcase,
its workload identity has no project IAM grant with which to read Firestore, call
Vertex AI, publish Pub/Sub, invoke the private agent/control services, access their
secrets, or mutate control-plane state. Public `roles/run.invoker` is attached to the
showcase *service*, allowing people to request only this deployment; it grants the
showcase identity no permission over another resource.

## Showcase rollback

Rollback never rebuilds an image and never accepts a tag. It shifts traffic to one
explicit, already-Ready revision after checking that the revision belongs to
`continuum-showcase`, uses the dedicated no-role identity, the service IAM policy is
exactly `allUsers`/`roles/run.invoker`, and the identity has zero project-level roles.
The command is read-only unless `--apply` is present:

```bash
uv run python scripts/cloud/rollback_showcase.py \
  --project "$CONTINUUM_PROJECT_ID" \
  --region "$CONTINUUM_REGION" \
  --target-revision continuum-showcase-00005-bg9

# Review the JSON plan, then perform and verify the rollback.
uv run python scripts/cloud/rollback_showcase.py \
  --project "$CONTINUUM_PROJECT_ID" \
  --region "$CONTINUUM_REGION" \
  --target-revision continuum-showcase-00005-bg9 \
  --apply
```

After the traffic update, the command waits until `/build-info` identifies the exact
target revision, requires the mutation probe to remain `404`, re-reads both service and
project IAM, and writes an ignored JSON receipt under `artifacts/cloud/`. Re-applying
the current known-good revision uses the same command with
`--target-revision continuum-showcase-00006-drz --apply`. The underlying Cloud Run
operation is:

```bash
gcloud run services update-traffic continuum-showcase \
  --project "$CONTINUUM_PROJECT_ID" --region "$CONTINUUM_REGION" \
  --to-revisions continuum-showcase-00005-bg9=100
```

## Evidence interpretation

The initial smoke captures infrastructure objects only, so the verifier should
return `NOT_ASSESSED` for the full cloud profile. `PASS` is allowed only when all
mandatory run-specific Firestore, Pub/Sub redelivery, Vertex AI, trace, and
Continuity Contract objects are captured and content-addressed. An observed
contradiction returns `FAIL`; absence never becomes a false pass.

## Safety

- Never set `GOOGLE_APPLICATION_CREDENTIALS` on Cloud Run.
- Services remain private; grant `roles/run.invoker` narrowly.
- The presentation-only showcase is the sole intentional public exception. Its
  no-role identity and absent mutation surface are enforced in tests and in its
  full replacement IAM policy.
- Authenticated service URLs retain default ingress so control-to-worker calls
  work without pretending a VPC path exists; IAM, not network reachability, is
  the demonstrated access boundary.
- Deployment replaces each invocation policy: only Pub/Sub may invoke control,
  and only control may invoke v17, v18, or the verifier. Stale public or group
  bindings are not preserved.
- v17 receives no direct Firestore, Pub/Sub, Cloud Tasks, or Vertex role.
- v18 receives Vertex invocation and Firestore transaction rights because the
  action gateway executes inside its service boundary; its ADC identity must
  exactly equal the configured v18 workload identity.
- The control identity receives datastore, Pub/Sub publishing, Cloud Tasks
  enqueue, and trace-export roles; it does not call Vertex AI.
- The independent verifier receives `roles/datastore.viewer` only; it cannot
  mutate evidence, publish lifecycle events, execute actions, or call Vertex.
- Pub/Sub token minting is scoped to the dedicated push service account and the
  Google-managed Pub/Sub service agent.
- Requests may carry `X-Continuum-Run-ID` and W3C `traceparent`; the service
  validates them and emits structured correlation logs and response headers.
- Run `gcloud` commands from an explicitly selected project and review the IAM
  bindings before deployment.

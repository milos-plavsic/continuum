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
export CONTINUUM_RUN_ID='<run returned by the cloud scenario>'
export CONTINUUM_TRACE_ID='<trace correlated with that run>'
bash scripts/cloud/run-smoke.sh
python3 scripts/cloud/verify-evidence.py "$CONTINUUM_EVIDENCE_DIR"
```

Copy `deploy/cloud.env.example` to an ignored `deploy/cloud.env` and provide a
real project, region, and Firestore location. The deployment uses one immutable
image for four private Cloud Run services with distinct user-managed identities:
control, v17, v18, and independent verifier. Pub/Sub push uses a fifth identity.

## Evidence interpretation

The initial smoke captures infrastructure objects only, so the verifier should
return `NOT_ASSESSED` for the full cloud profile. `PASS` is allowed only when all
mandatory run-specific Firestore, Pub/Sub redelivery, Vertex AI, trace, and
Continuity Contract objects are captured and content-addressed. An observed
contradiction returns `FAIL`; absence never becomes a false pass.

## Safety

- Never set `GOOGLE_APPLICATION_CREDENTIALS` on Cloud Run.
- Services remain private; grant `roles/run.invoker` narrowly.
- v17 and v18 receive no direct Firestore or Pub/Sub roles.
- The control identity receives only datastore, publishing, and Vertex AI roles.
- Run `gcloud` commands from an explicitly selected project and review the IAM
  bindings before deployment.

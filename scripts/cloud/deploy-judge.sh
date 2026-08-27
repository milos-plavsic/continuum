#!/usr/bin/env bash
set -euo pipefail

: "${CONTINUUM_PROJECT_ID:?set CONTINUUM_PROJECT_ID}"
: "${CONTINUUM_REGION:?set CONTINUUM_REGION}"
: "${CONTINUUM_GIT_SHA:?set CONTINUUM_GIT_SHA to the exact source commit}"
: "${CONTINUUM_CONTROL_URL:?set CONTINUUM_CONTROL_URL}"
: "${CONTINUUM_OPERATOR_MEMBER:?set CONTINUUM_OPERATOR_MEMBER}"
: "${CONTINUUM_PUBSUB_PUSH_ACCOUNT:?set CONTINUUM_PUBSUB_PUSH_ACCOUNT}"

repository="${CONTINUUM_ARTIFACT_REPOSITORY:-continuum}"
image="${CONTINUUM_JUDGE_IMAGE:-continuum-judge}"
service="${CONTINUUM_JUDGE_SERVICE:-continuum-judge}"
account="${CONTINUUM_JUDGE_ACCOUNT:-continuum-judge}"
secret_name="${CONTINUUM_JUDGE_SECRET_NAME:-continuum-judge-hmac}"
account_email="$account@$CONTINUUM_PROJECT_ID.iam.gserviceaccount.com"
push_identity="$CONTINUUM_PUBSUB_PUSH_ACCOUNT@$CONTINUUM_PROJECT_ID.iam.gserviceaccount.com"
image_tag="$CONTINUUM_REGION-docker.pkg.dev/$CONTINUUM_PROJECT_ID/$repository/$image:$CONTINUUM_GIT_SHA"

[[ "$(git rev-parse HEAD)" == "$CONTINUUM_GIT_SHA" ]] || {
  echo "CONTINUUM_GIT_SHA does not match checkout" >&2; exit 2;
}
[[ "$CONTINUUM_OPERATOR_MEMBER" =~ ^(user|serviceAccount):[A-Za-z0-9._%+@-]+$ ]] || {
  echo "CONTINUUM_OPERATOR_MEMBER must be one explicit principal" >&2; exit 2;
}

private_dir="${CONTINUUM_PRIVATE_ARTIFACT_DIR:-artifacts/private}"
secret_file="$private_dir/judge-hmac.secret"
token_file="$private_dir/judge-capability.txt"
mkdir -p "$private_dir"
chmod 700 "$private_dir"
if [[ ! -s "$secret_file" ]]; then
  umask 077
  printf '%s' "$(openssl rand -hex 32)" >"$secret_file"
fi
secret="$(tr -d '\r\n' <"$secret_file")"
[[ "$secret" =~ ^[0-9a-f]{64}$ ]] || {
  echo "Judge secret must be exactly 32 random bytes encoded as hex" >&2; exit 2; }
printf '%s' "$secret" >"$secret_file"

gcloud services enable modelarmor.googleapis.com secretmanager.googleapis.com \
  --project "$CONTINUUM_PROJECT_ID" --quiet
if ! gcloud iam service-accounts describe "$account_email" \
  --project "$CONTINUUM_PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$account" --project "$CONTINUUM_PROJECT_ID" \
    --display-name "Continuum bounded public judge gateway"
fi
if ! gcloud secrets describe "$secret_name" --project "$CONTINUUM_PROJECT_ID" >/dev/null 2>&1; then
  gcloud secrets create "$secret_name" --project "$CONTINUUM_PROJECT_ID" \
    --replication-policy automatic
fi
gcloud secrets versions add "$secret_name" --project "$CONTINUUM_PROJECT_ID" \
  --data-file "$secret_file" >/dev/null
gcloud secrets add-iam-policy-binding "$secret_name" --project "$CONTINUUM_PROJECT_ID" \
  --member "serviceAccount:$account_email" --role roles/secretmanager.secretAccessor \
  --quiet >/dev/null
gcloud projects add-iam-policy-binding "$CONTINUUM_PROJECT_ID" \
  --member "serviceAccount:$account_email" --role roles/datastore.user \
  --condition=None --quiet >/dev/null

gcloud builds submit --project "$CONTINUUM_PROJECT_ID" --tag "$image_tag" .
digest="$(gcloud artifacts docker images describe "$image_tag" \
  --project "$CONTINUUM_PROJECT_ID" --format='value(image_summary.digest)')"
[[ "$digest" == sha256:* ]] || { echo "Could not resolve immutable image digest" >&2; exit 3; }
image_ref="${image_tag%:*}@$digest"
deployment_id="$CONTINUUM_GIT_SHA@$digest"

# Deploy privately, then replace the complete public invocation policy. The
# service accepts only an expiring signed capability and a server-owned command.
gcloud run deploy "$service" --project "$CONTINUUM_PROJECT_ID" \
  --region "$CONTINUUM_REGION" --image "$image_ref" \
  --service-account "$account_email" --no-allow-unauthenticated \
  --min-instances 0 --max-instances 1 --concurrency 10 --timeout 60 \
  --set-secrets "CONTINUUM_JUDGE_HMAC_SECRET=$secret_name:latest" \
  --set-env-vars "CONTINUUM_ROLE=judge,CONTINUUM_CONTROL_URL=$CONTINUUM_CONTROL_URL,GIT_SHA=$CONTINUUM_GIT_SHA,CONTINUUM_IMAGE_DIGEST=$digest,CONTINUUM_DEPLOYMENT_ID=$deployment_id,CONTINUUM_PROTOCOL=continuum/0.1-draft,OTEL_SERVICE_NAME=$service,CONTINUUM_OBSERVABILITY_ENABLED=false,GOOGLE_CLOUD_PROJECT=$CONTINUUM_PROJECT_ID"

policy_dir="$(mktemp -d)"
trap 'rm -rf -- "$policy_dir"' EXIT
printf '%s\n' 'bindings:' '- members:' '  - allUsers' \
  '  role: roles/run.invoker' 'version: 1' >"$policy_dir/judge.yaml"
gcloud run services set-iam-policy "$service" "$policy_dir/judge.yaml" \
  --project "$CONTINUUM_PROJECT_ID" --region "$CONTINUUM_REGION" --quiet >/dev/null

# Replace the private control invocation policy with the exact three principals:
# Pub/Sub push, the named operator, and this bounded judge gateway.
printf '%s\n' 'bindings:' '- members:' \
  "  - serviceAccount:$push_identity" "  - $CONTINUUM_OPERATOR_MEMBER" \
  "  - serviceAccount:$account_email" '  role: roles/run.invoker' \
  'version: 1' >"$policy_dir/control.yaml"
gcloud run services set-iam-policy "${CONTINUUM_CONTROL_SERVICE:-continuum-control}" \
  "$policy_dir/control.yaml" --project "$CONTINUUM_PROJECT_ID" \
  --region "$CONTINUUM_REGION" --quiet >/dev/null

grant_jti="${CONTINUUM_JUDGE_GRANT_JTI:-devpost26-${CONTINUUM_GIT_SHA:0:8}}"
CONTINUUM_JUDGE_HMAC_SECRET="$secret" uv run python scripts/issue_judge_capability.py \
  --jti "$grant_jti" --hours "${CONTINUUM_JUDGE_TOKEN_HOURS:-720}" \
  --max-runs "${CONTINUUM_JUDGE_MAX_RUNS:-3}" >"$token_file"
chmod 600 "$secret_file" "$token_file"
url="$(gcloud run services describe "$service" --project "$CONTINUUM_PROJECT_ID" \
  --region "$CONTINUUM_REGION" --format='value(status.url)')"
printf 'JUDGE_URL=%s\nIMAGE_DIGEST=%s\nCAPABILITY_FILE=%s\n' "$url" "$digest" "$token_file"

#!/usr/bin/env bash
set -euo pipefail

: "${CONTINUUM_PROJECT_ID:?set CONTINUUM_PROJECT_ID}"
: "${CONTINUUM_REGION:?set CONTINUUM_REGION}"
: "${CONTINUUM_GIT_SHA:?set CONTINUUM_GIT_SHA to the exact source commit}"
: "${CONTINUUM_OPERATOR_MEMBER:?set CONTINUUM_OPERATOR_MEMBER, for example user:operator@example.com}"
if [[ ! "$CONTINUUM_OPERATOR_MEMBER" =~ ^(user|serviceAccount):[A-Za-z0-9._%+@-]+$ ]]; then
  echo "CONTINUUM_OPERATOR_MEMBER must be one exact user: or serviceAccount: principal" >&2
  exit 2
fi

repository="${CONTINUUM_ARTIFACT_REPOSITORY:-continuum}"
image="${CONTINUUM_IMAGE:-continuum-control-plane}"
topic="${CONTINUUM_LIFECYCLE_TOPIC:-continuum-lifecycle}"
control_service="${CONTINUUM_CONTROL_SERVICE:-continuum-control}"
v17_service="${CONTINUUM_V17_SERVICE:-continuum-agent-v17}"
v18_service="${CONTINUUM_V18_SERVICE:-continuum-agent-v18}"
verifier_service="${CONTINUUM_VERIFIER_SERVICE:-continuum-verifier}"
subscription="${CONTINUUM_PUSH_SUBSCRIPTION:-continuum-control-push}"
image_tag="$CONTINUUM_REGION-docker.pkg.dev/$CONTINUUM_PROJECT_ID/$repository/$image:$CONTINUUM_GIT_SHA"

if [[ "$(git rev-parse HEAD)" != "$CONTINUUM_GIT_SHA" ]]; then
  echo "CONTINUUM_GIT_SHA does not match checkout" >&2; exit 2
fi

gcloud builds submit --project "$CONTINUUM_PROJECT_ID" --tag "$image_tag" .
digest="$(gcloud artifacts docker images describe "$image_tag" --project "$CONTINUUM_PROJECT_ID" --format='value(image_summary.digest)')"
[[ "$digest" == sha256:* ]] || { echo "Could not resolve immutable image digest" >&2; exit 3; }
image_ref="${image_tag%:*}@$digest"
deployment_id="$CONTINUUM_GIT_SHA@$digest"

deploy_role() {
  local service="$1" account="$2" role="$3"
  gcloud run deploy "$service" --project "$CONTINUUM_PROJECT_ID" --region "$CONTINUUM_REGION" \
    --image "$image_ref" --service-account "$account@$CONTINUUM_PROJECT_ID.iam.gserviceaccount.com" \
    --no-allow-unauthenticated \
    --min-instances 0 --max-instances 3 --concurrency 20 \
    --set-env-vars "CONTINUUM_ROLE=$role,GIT_SHA=$CONTINUUM_GIT_SHA,CONTINUUM_IMAGE_DIGEST=$digest,CONTINUUM_DEPLOYMENT_ID=$deployment_id,CONTINUUM_PROTOCOL=continuum/0.1-draft,CONTINUUM_LIFECYCLE_TOPIC=$topic,OTEL_SERVICE_NAME=$service,CONTINUUM_OBSERVABILITY_ENABLED=true"
}

deploy_role "$control_service" continuum-control control
deploy_role "$v17_service" continuum-v17 agent-v17
deploy_role "$v18_service" continuum-v18 agent-v18
deploy_role "$verifier_service" continuum-verifier verifier

control_url="$(gcloud run services describe "$control_service" --project "$CONTINUUM_PROJECT_ID" --region "$CONTINUUM_REGION" --format='value(status.url)')"
v17_url="$(gcloud run services describe "$v17_service" --project "$CONTINUUM_PROJECT_ID" --region "$CONTINUUM_REGION" --format='value(status.url)')"
v18_url="$(gcloud run services describe "$v18_service" --project "$CONTINUUM_PROJECT_ID" --region "$CONTINUUM_REGION" --format='value(status.url)')"
verifier_url="$(gcloud run services describe "$verifier_service" --project "$CONTINUUM_PROJECT_ID" --region "$CONTINUUM_REGION" --format='value(status.url)')"
push_identity="continuum-pubsub-push@$CONTINUUM_PROJECT_ID.iam.gserviceaccount.com"
control_identity="continuum-control@$CONTINUUM_PROJECT_ID.iam.gserviceaccount.com"
v17_identity="continuum-v17@$CONTINUUM_PROJECT_ID.iam.gserviceaccount.com"
v18_identity="continuum-v18@$CONTINUUM_PROJECT_ID.iam.gserviceaccount.com"
verifier_identity="continuum-verifier@$CONTINUUM_PROJECT_ID.iam.gserviceaccount.com"

# Replace, rather than append to, each service invocation policy. This prevents
# stale public or broad group bindings from surviving a redeployment.
policy_dir="$(mktemp -d)"
trap 'rm -rf -- "$policy_dir"' EXIT
write_invoker_policy() {
  local destination="$1"; shift
  printf '%s\n' 'bindings:' '- members:' >"$destination"
  for member in "$@"; do
    printf '  - %s\n' "$member" >>"$destination"
  done
  printf '%s\n' '  role: roles/run.invoker' 'version: 1' >>"$destination"
}
write_invoker_policy "$policy_dir/control.yaml" "serviceAccount:$push_identity" "$CONTINUUM_OPERATOR_MEMBER"
write_invoker_policy "$policy_dir/agent-v17.yaml" "serviceAccount:$control_identity"
write_invoker_policy "$policy_dir/agent-v18.yaml" "serviceAccount:$control_identity"
write_invoker_policy "$policy_dir/verifier.yaml" "serviceAccount:$control_identity"
for binding in \
  "$control_service:$policy_dir/control.yaml" \
  "$v17_service:$policy_dir/agent-v17.yaml" \
  "$v18_service:$policy_dir/agent-v18.yaml" \
  "$verifier_service:$policy_dir/verifier.yaml"; do
  service="${binding%%:*}"
  policy="${binding#*:}"
  gcloud run services set-iam-policy "$service" "$policy" \
    --project "$CONTINUUM_PROJECT_ID" --region "$CONTINUUM_REGION" >/dev/null
done

full_subscription="projects/$CONTINUUM_PROJECT_ID/subscriptions/$subscription"
common_env="GOOGLE_CLOUD_PROJECT=$CONTINUUM_PROJECT_ID,CONTINUUM_CONTROL_AUDIENCE=$control_url,CONTINUUM_PUBSUB_PUSH_IDENTITY=$push_identity,CONTINUUM_PUSH_SUBSCRIPTION=$full_subscription,CONTINUUM_FORCE_REDELIVERY=1,CONTINUUM_V17_URL=$v17_url,CONTINUUM_V18_URL=$v18_url,CONTINUUM_VERIFIER_URL=$verifier_url,CONTINUUM_CONTROL_IDENTITY=$control_identity,CONTINUUM_V17_IDENTITY=$v17_identity,CONTINUUM_V18_IDENTITY=$v18_identity,CONTINUUM_VERIFIER_IDENTITY=$verifier_identity"
gcloud run services update "$control_service" --project "$CONTINUUM_PROJECT_ID" --region "$CONTINUUM_REGION" --update-env-vars "$common_env" >/dev/null

if gcloud pubsub subscriptions describe "$subscription" --project "$CONTINUUM_PROJECT_ID" >/dev/null 2>&1; then
  gcloud pubsub subscriptions update "$subscription" --project "$CONTINUUM_PROJECT_ID" \
    --push-endpoint "$control_url/pubsub/push" --push-auth-service-account "$push_identity" --push-auth-token-audience "$control_url"
else
  gcloud pubsub subscriptions create "$subscription" --project "$CONTINUUM_PROJECT_ID" --topic "$topic" \
    --push-endpoint "$control_url/pubsub/push" --push-auth-service-account "$push_identity" --push-auth-token-audience "$control_url"
fi

printf 'CONTROL_URL=%s\nIMAGE_DIGEST=%s\n' "$control_url" "$digest"

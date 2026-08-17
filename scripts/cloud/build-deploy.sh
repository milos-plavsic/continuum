#!/usr/bin/env bash
set -euo pipefail

: "${CONTINUUM_PROJECT_ID:?set CONTINUUM_PROJECT_ID}"
: "${CONTINUUM_REGION:?set CONTINUUM_REGION}"
: "${CONTINUUM_GIT_SHA:?set CONTINUUM_GIT_SHA to the exact source commit}"

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

deploy_role() {
  local service="$1" account="$2" role="$3"
  gcloud run deploy "$service" --project "$CONTINUUM_PROJECT_ID" --region "$CONTINUUM_REGION" \
    --image "$image_ref" --service-account "$account@$CONTINUUM_PROJECT_ID.iam.gserviceaccount.com" \
    --no-allow-unauthenticated --set-env-vars "CONTINUUM_ROLE=$role,GIT_SHA=$CONTINUUM_GIT_SHA,CONTINUUM_IMAGE_DIGEST=$digest,CONTINUUM_LIFECYCLE_TOPIC=$topic"
}

deploy_role "$control_service" continuum-control control
deploy_role "$v17_service" continuum-v17 agent-v17
deploy_role "$v18_service" continuum-v18 agent-v18
deploy_role "$verifier_service" continuum-verifier verifier

control_url="$(gcloud run services describe "$control_service" --project "$CONTINUUM_PROJECT_ID" --region "$CONTINUUM_REGION" --format='value(status.url)')"
push_identity="continuum-pubsub-push@$CONTINUUM_PROJECT_ID.iam.gserviceaccount.com"
gcloud run services add-iam-policy-binding "$control_service" --project "$CONTINUUM_PROJECT_ID" --region "$CONTINUUM_REGION" \
  --member "serviceAccount:$push_identity" --role roles/run.invoker >/dev/null

full_subscription="projects/$CONTINUUM_PROJECT_ID/subscriptions/$subscription"
common_env="CONTINUUM_CONTROL_AUDIENCE=$control_url,CONTINUUM_PUBSUB_PUSH_IDENTITY=$push_identity,CONTINUUM_PUSH_SUBSCRIPTION=$full_subscription"
gcloud run services update "$control_service" --project "$CONTINUUM_PROJECT_ID" --region "$CONTINUUM_REGION" --update-env-vars "$common_env" >/dev/null

if gcloud pubsub subscriptions describe "$subscription" --project "$CONTINUUM_PROJECT_ID" >/dev/null 2>&1; then
  gcloud pubsub subscriptions update "$subscription" --project "$CONTINUUM_PROJECT_ID" \
    --push-endpoint "$control_url/pubsub/push" --push-auth-service-account "$push_identity" --push-auth-token-audience "$control_url"
else
  gcloud pubsub subscriptions create "$subscription" --project "$CONTINUUM_PROJECT_ID" --topic "$topic" \
    --push-endpoint "$control_url/pubsub/push" --push-auth-service-account "$push_identity" --push-auth-token-audience "$control_url"
fi

printf 'CONTROL_URL=%s\nIMAGE_DIGEST=%s\n' "$control_url" "$digest"

#!/usr/bin/env bash
set -euo pipefail

: "${CONTINUUM_PROJECT_ID:?set CONTINUUM_PROJECT_ID}"
: "${CONTINUUM_REGION:?set CONTINUUM_REGION}"
: "${CONTINUUM_GIT_SHA:?set CONTINUUM_GIT_SHA to the exact source commit}"

repository="${CONTINUUM_ARTIFACT_REPOSITORY:-continuum}"
image="${CONTINUUM_SHOWCASE_IMAGE:-continuum-showcase}"
service="${CONTINUUM_SHOWCASE_SERVICE:-continuum-showcase}"
account="${CONTINUUM_SHOWCASE_ACCOUNT:-continuum-showcase}"
account_email="$account@$CONTINUUM_PROJECT_ID.iam.gserviceaccount.com"
image_tag="$CONTINUUM_REGION-docker.pkg.dev/$CONTINUUM_PROJECT_ID/$repository/$image:$CONTINUUM_GIT_SHA"

if [[ "$(git rev-parse HEAD)" != "$CONTINUUM_GIT_SHA" ]]; then
  echo "CONTINUUM_GIT_SHA does not match checkout" >&2
  exit 2
fi

if ! gcloud iam service-accounts describe "$account_email" \
  --project "$CONTINUUM_PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$account" --project "$CONTINUUM_PROJECT_ID" \
    --display-name "Continuum public read-only showcase"
fi

gcloud builds submit --project "$CONTINUUM_PROJECT_ID" --tag "$image_tag" .
digest="$(gcloud artifacts docker images describe "$image_tag" \
  --project "$CONTINUUM_PROJECT_ID" --format='value(image_summary.digest)')"
[[ "$digest" == sha256:* ]] || { echo "Could not resolve immutable image digest" >&2; exit 3; }
image_ref="${image_tag%:*}@$digest"
deployment_id="$CONTINUUM_GIT_SHA@$digest"

# Deploy private first, then replace the entire invocation policy with the one
# intentionally public binding. No runtime role is granted to this identity.
gcloud run deploy "$service" --project "$CONTINUUM_PROJECT_ID" \
  --region "$CONTINUUM_REGION" --image "$image_ref" \
  --service-account "$account_email" --no-allow-unauthenticated \
  --min-instances 0 --max-instances 2 --concurrency 40 \
  --set-env-vars "CONTINUUM_ROLE=showcase,GIT_SHA=$CONTINUUM_GIT_SHA,CONTINUUM_IMAGE_DIGEST=$digest,CONTINUUM_DEPLOYMENT_ID=$deployment_id,CONTINUUM_PROTOCOL=continuum/0.1-draft,OTEL_SERVICE_NAME=$service,CONTINUUM_OBSERVABILITY_ENABLED=false,GOOGLE_CLOUD_PROJECT=$CONTINUUM_PROJECT_ID"

policy_dir="$(mktemp -d)"
trap 'rm -rf -- "$policy_dir"' EXIT
printf '%s\n' \
  'bindings:' \
  '- members:' \
  '  - allUsers' \
  '  role: roles/run.invoker' \
  'version: 1' >"$policy_dir/showcase.yaml"
gcloud run services set-iam-policy "$service" "$policy_dir/showcase.yaml" \
  --project "$CONTINUUM_PROJECT_ID" --region "$CONTINUUM_REGION" --quiet >/dev/null

url="$(gcloud run services describe "$service" --project "$CONTINUUM_PROJECT_ID" \
  --region "$CONTINUUM_REGION" --format='value(status.url)')"
printf 'SHOWCASE_URL=%s\nIMAGE_DIGEST=%s\n' "$url" "$digest"

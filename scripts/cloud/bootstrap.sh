#!/usr/bin/env bash
set -euo pipefail

: "${CONTINUUM_PROJECT_ID:?set CONTINUUM_PROJECT_ID}"
: "${CONTINUUM_REGION:?set CONTINUUM_REGION}"
: "${CONTINUUM_FIRESTORE_LOCATION:?set CONTINUUM_FIRESTORE_LOCATION}"

repository="${CONTINUUM_ARTIFACT_REPOSITORY:-continuum}"
topic="${CONTINUUM_LIFECYCLE_TOPIC:-continuum-lifecycle}"

gcloud services enable --project "$CONTINUUM_PROJECT_ID" \
  run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com \
  firestore.googleapis.com pubsub.googleapis.com aiplatform.googleapis.com

if ! gcloud artifacts repositories describe "$repository" --project "$CONTINUUM_PROJECT_ID" --location "$CONTINUUM_REGION" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$repository" --project "$CONTINUUM_PROJECT_ID" \
    --location "$CONTINUUM_REGION" --repository-format docker
fi

if ! gcloud firestore databases describe --project "$CONTINUUM_PROJECT_ID" --database='(default)' >/dev/null 2>&1; then
  gcloud firestore databases create --project "$CONTINUUM_PROJECT_ID" --database='(default)' \
    --location "$CONTINUUM_FIRESTORE_LOCATION" --type=firestore-native
fi

for account in continuum-control continuum-v17 continuum-v18 continuum-verifier continuum-pubsub-push; do
  if ! gcloud iam service-accounts describe "$account@$CONTINUUM_PROJECT_ID.iam.gserviceaccount.com" --project "$CONTINUUM_PROJECT_ID" >/dev/null 2>&1; then
    gcloud iam service-accounts create "$account" --project "$CONTINUUM_PROJECT_ID" --display-name "$account"
  fi
done

control="continuum-control@$CONTINUUM_PROJECT_ID.iam.gserviceaccount.com"
verifier="continuum-verifier@$CONTINUUM_PROJECT_ID.iam.gserviceaccount.com"
push_identity="continuum-pubsub-push@$CONTINUUM_PROJECT_ID.iam.gserviceaccount.com"
for role in roles/datastore.user roles/pubsub.publisher roles/aiplatform.user; do
  gcloud projects add-iam-policy-binding "$CONTINUUM_PROJECT_ID" --member "serviceAccount:$control" --role "$role" --condition=None >/dev/null
done

# The independent verifier can resolve persisted evidence, but cannot publish,
# execute, or call Vertex. Its application role is additionally enforced by the
# verifier-only HTTP surface.
gcloud projects add-iam-policy-binding "$CONTINUUM_PROJECT_ID" \
  --member "serviceAccount:$verifier" --role roles/datastore.viewer --condition=None >/dev/null

# Pub/Sub's managed service agent needs permission to mint an OIDC token as the
# dedicated push identity. Do not grant this to the runtime identities.
project_number="$(gcloud projects describe "$CONTINUUM_PROJECT_ID" --format='value(projectNumber)')"
[[ "$project_number" =~ ^[0-9]+$ ]] || { echo "Could not resolve project number" >&2; exit 2; }
pubsub_service_agent="service-$project_number@gcp-sa-pubsub.iam.gserviceaccount.com"
gcloud iam service-accounts add-iam-policy-binding "$push_identity" \
  --project "$CONTINUUM_PROJECT_ID" \
  --member "serviceAccount:$pubsub_service_agent" \
  --role roles/iam.serviceAccountTokenCreator >/dev/null

if ! gcloud pubsub topics describe "$topic" --project "$CONTINUUM_PROJECT_ID" >/dev/null 2>&1; then
  gcloud pubsub topics create "$topic" --project "$CONTINUUM_PROJECT_ID"
fi

echo "Bootstrap complete for $CONTINUUM_PROJECT_ID in $CONTINUUM_REGION"

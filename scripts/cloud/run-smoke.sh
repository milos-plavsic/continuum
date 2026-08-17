#!/usr/bin/env bash
set -euo pipefail

: "${CONTINUUM_PROJECT_ID:?set CONTINUUM_PROJECT_ID}"
: "${CONTINUUM_REGION:?set CONTINUUM_REGION}"
: "${CONTINUUM_EVIDENCE_DIR:?set CONTINUUM_EVIDENCE_DIR to a new artifacts/cloud path}"

mkdir -p "$CONTINUUM_EVIDENCE_DIR/objects"
for service in "${CONTINUUM_CONTROL_SERVICE:-continuum-control}" "${CONTINUUM_V17_SERVICE:-continuum-agent-v17}" "${CONTINUUM_V18_SERVICE:-continuum-agent-v18}" "${CONTINUUM_VERIFIER_SERVICE:-continuum-verifier}"; do
  gcloud run services describe "$service" --project "$CONTINUUM_PROJECT_ID" --region "$CONTINUUM_REGION" --format=json \
    > "$CONTINUUM_EVIDENCE_DIR/objects/cloud-run-$service.json"
done
gcloud pubsub topics describe "${CONTINUUM_LIFECYCLE_TOPIC:-continuum-lifecycle}" --project "$CONTINUUM_PROJECT_ID" --format=json \
  > "$CONTINUUM_EVIDENCE_DIR/objects/pubsub-topic.json"
gcloud pubsub subscriptions describe "${CONTINUUM_PUSH_SUBSCRIPTION:-continuum-control-push}" --project "$CONTINUUM_PROJECT_ID" --format=json \
  > "$CONTINUUM_EVIDENCE_DIR/objects/pubsub-subscription.json"

echo "Infrastructure evidence captured in $CONTINUUM_EVIDENCE_DIR. Run-specific evidence remains NOT_ASSESSED until the cloud scenario is invoked."

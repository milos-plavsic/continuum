#!/usr/bin/env bash
set -euo pipefail

: "${CONTINUUM_PROJECT_ID:?set CONTINUUM_PROJECT_ID}"
: "${CONTINUUM_REGION:?set CONTINUUM_REGION}"
: "${CONTINUUM_EVIDENCE_DIR:?set CONTINUUM_EVIDENCE_DIR to a new artifacts/cloud path}"
: "${CONTINUUM_RUN_ID:?set CONTINUUM_RUN_ID to the invoked cloud scenario run}"
: "${CONTINUUM_TRACE_ID:?set CONTINUUM_TRACE_ID to that run's trace}"
: "${CONTINUUM_GIT_SHA:?set CONTINUUM_GIT_SHA to the deployed commit}"

capture_dir="$(mktemp -d)"
trap 'rm -rf "$capture_dir"' EXIT
for pair in "cloud-run-control:${CONTINUUM_CONTROL_SERVICE:-continuum-control}" "cloud-run-v17:${CONTINUUM_V17_SERVICE:-continuum-agent-v17}" "cloud-run-v18:${CONTINUUM_V18_SERVICE:-continuum-agent-v18}" "cloud-run-verifier:${CONTINUUM_VERIFIER_SERVICE:-continuum-verifier}"; do
  object_id="${pair%%:*}"; service="${pair#*:}"
  gcloud run services describe "$service" --project "$CONTINUUM_PROJECT_ID" --region "$CONTINUUM_REGION" --format=json \
    > "$capture_dir/$object_id.json"
done
gcloud services list --enabled --project "$CONTINUUM_PROJECT_ID" --format=json > "$capture_dir/enabled-services.json"
gcloud projects get-iam-policy "$CONTINUUM_PROJECT_ID" --format=json > "$capture_dir/iam-policy.json"

python3 scripts/cloud/package-evidence.py "$capture_dir" "$CONTINUUM_EVIDENCE_DIR" \
  --project "$CONTINUUM_PROJECT_ID" --region "$CONTINUUM_REGION" \
  --run-id "$CONTINUUM_RUN_ID" --trace-id "$CONTINUUM_TRACE_ID" --git-commit "$CONTINUUM_GIT_SHA"

echo "Content-addressed infrastructure evidence captured. Missing run evidence remains NOT_ASSESSED."

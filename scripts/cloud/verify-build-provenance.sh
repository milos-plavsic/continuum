#!/usr/bin/env bash
set -euo pipefail

: "${CONTINUUM_IMAGE_AT_DIGEST:?set the immutable Artifact Registry image reference}"
: "${CONTINUUM_EXPECTED_SOURCE_URI:?set the source URI declared by the build}"

command -v slsa-verifier >/dev/null || {
  echo "slsa-verifier 2.1+ is required for independent signature verification" >&2
  exit 2
}

provenance_file="$(mktemp)"
trap 'rm -f -- "$provenance_file"' EXIT
gcloud artifacts docker images describe "$CONTINUUM_IMAGE_AT_DIGEST" \
  --show-provenance --format=json >"$provenance_file"
slsa-verifier verify-image "$CONTINUUM_IMAGE_AT_DIGEST" \
  --provenance-path "$provenance_file" \
  --source-uri "$CONTINUUM_EXPECTED_SOURCE_URI" \
  --builder-id https://cloudbuild.googleapis.com/GoogleHostedWorker

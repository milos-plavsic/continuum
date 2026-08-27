#!/usr/bin/env bash
set -euo pipefail

: "${CONTINUUM_IMAGE_AT_DIGEST:?set the immutable Artifact Registry image reference}"
: "${CONTINUUM_EXPECTED_SOURCE_URI:?set the source URI declared by the build}"

command -v slsa-verifier >/dev/null || {
  echo "slsa-verifier 2.1+ is required for independent signature verification" >&2
  exit 2
}

provenance_file="$(mktemp)"
verifier_output="$(mktemp)"
trap 'rm -f -- "$provenance_file" "$verifier_output"' EXIT
gcloud artifacts docker images describe "$CONTINUUM_IMAGE_AT_DIGEST" \
  --show-provenance --format=json >"$provenance_file"

# slsa-verifier 2.7.1 can emit a textual FAILED result for a manual
# `gcloud builds submit` source while still returning process status zero after
# authenticating the Google signature. Treat only its explicit terminal PASS as
# success; a zero exit code alone is not an assurance result.
set +e
slsa-verifier verify-image "$CONTINUUM_IMAGE_AT_DIGEST" \
  --provenance-path "$provenance_file" \
  --source-uri "$CONTINUUM_EXPECTED_SOURCE_URI" \
  --builder-id https://cloudbuild.googleapis.com/GoogleHostedWorker \
  >"$verifier_output" 2>&1
verifier_status=$?
set -e
cat "$verifier_output"
if [[ "$verifier_status" -ne 0 ]] || \
   ! grep -Fxq 'PASSED: Verified SLSA provenance' "$verifier_output"; then
  echo "SLSA source-and-builder verification did not produce an explicit PASS" >&2
  exit 1
fi

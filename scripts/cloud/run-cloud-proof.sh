#!/usr/bin/env bash
set -euo pipefail

: "${CONTINUUM_PROJECT_ID:?set CONTINUUM_PROJECT_ID}"
: "${CONTINUUM_REGION:?set CONTINUUM_REGION}"
: "${CONTINUUM_GIT_SHA:?set CONTINUUM_GIT_SHA to the deployed commit}"
: "${CONTINUUM_EVIDENCE_DIR:?set CONTINUUM_EVIDENCE_DIR to a new artifacts/cloud path}"

control_service="${CONTINUUM_CONTROL_SERVICE:-continuum-control}"
control_url="$(gcloud run services describe "$control_service" --project "$CONTINUUM_PROJECT_ID" \
  --region "$CONTINUUM_REGION" --format='value(status.url)')"
[[ "$control_url" == https://* ]] || { echo "Control service URL unavailable" >&2; exit 2; }

run_id="${CONTINUUM_RUN_ID:-run-$(date -u +%Y%m%dT%H%M%SZ)}"
[[ "$run_id" =~ ^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$ ]] || {
  echo "CONTINUUM_RUN_ID is invalid" >&2; exit 2;
}
trace_id="$(uv run python - "$run_id" <<'PY'
import sys
from continuum.cloud_scenario_service import canonical_run_correlation_id
print(canonical_run_correlation_id(sys.argv[1]))
PY
)"
if [[ "${CONTINUUM_OPERATOR_MEMBER:-}" == serviceAccount:* ]]; then
  token="$(gcloud auth print-identity-token --audiences="$control_url")"
else
  token="$(gcloud auth print-identity-token)"
fi
response_file="$(mktemp)"
trap 'rm -f -- "$response_file"' EXIT

printf 'header = "Authorization: Bearer %s"\n' "$token" | \
curl --config - --fail-with-body --silent --show-error --request POST "$control_url/cloud-smoke/start" \
  --header 'Content-Type: application/json' \
  --header "X-Continuum-Run-ID: $run_id" \
  --header "traceparent: 00-$trace_id-0000000000000001-01" \
  --data "{\"run_id\":\"$run_id\"}" >"$response_file"

python3 - "$response_file" <<'PY'
import json, pathlib, sys
result = json.loads(pathlib.Path(sys.argv[1]).read_text())
if result.get("phase") != "WAITING_FOR_DEADLINE":
    raise SystemExit(f'cloud scenario did not persist its deadline: {result.get("phase")}')
PY

# Cloud Tasks crosses the real deadline and Pub/Sub redelivery resumes the run.
# The operator only observes; it does not tick or advance lifecycle state.
for attempt in $(seq 1 90); do
  printf 'header = "Authorization: Bearer %s"\n' "$token" | \
  curl --config - --fail-with-body --silent --show-error \
    --header "X-Continuum-Run-ID: $run_id" \
    --header "traceparent: 00-$trace_id-0000000000000001-01" \
    "$control_url/cloud-smoke/$run_id" >"$response_file"
  phase="$(python3 - "$response_file" <<'PY'
import json, pathlib, sys
print(json.loads(pathlib.Path(sys.argv[1]).read_text()).get("phase", ""))
PY
)"
  if [[ "$phase" == VERIFIED ]]; then
    break
  fi
  if [[ "$phase" == FAILED ]]; then
    echo "cloud scenario entered FAILED" >&2; exit 3
  fi
  sleep 2
done

python3 - "$response_file" <<'PY'
import json, pathlib, sys
result = json.loads(pathlib.Path(sys.argv[1]).read_text())
verification = result.get("verification", {})
if (result.get("phase") != "VERIFIED" or verification.get("status") != "PASS"
        or verification.get("outcome") != "VERIFIED"):
    raise SystemExit(f'cloud scenario did not reach independent PASS: {result.get("phase")}')
PY

export CONTINUUM_RUN_ID="$run_id" CONTINUUM_TRACE_ID="$trace_id"
bash scripts/cloud/run-smoke.sh

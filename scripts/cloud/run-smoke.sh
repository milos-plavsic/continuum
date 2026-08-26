#!/usr/bin/env bash
set -euo pipefail

: "${CONTINUUM_PROJECT_ID:?set CONTINUUM_PROJECT_ID}"
: "${CONTINUUM_REGION:?set CONTINUUM_REGION}"
: "${CONTINUUM_EVIDENCE_DIR:?set CONTINUUM_EVIDENCE_DIR to a new artifacts/cloud path}"
: "${CONTINUUM_RUN_ID:?set CONTINUUM_RUN_ID to the invoked cloud scenario run}"
: "${CONTINUUM_TRACE_ID:?set CONTINUUM_TRACE_ID to the trace for that run}"
: "${CONTINUUM_GIT_SHA:?set CONTINUUM_GIT_SHA to the deployed commit}"

capture_dir="$(mktemp -d)"
trap 'rm -rf "$capture_dir"' EXIT
uv run --extra google python scripts/cloud/collect_evidence.py "$capture_dir" \
  --project "$CONTINUUM_PROJECT_ID" --region "$CONTINUUM_REGION" \
  --run-id "$CONTINUUM_RUN_ID" --trace-id "$CONTINUUM_TRACE_ID" \
  --control-service "${CONTINUUM_CONTROL_SERVICE:-continuum-control}" \
  --v17-service "${CONTINUUM_V17_SERVICE:-continuum-agent-v17}" \
  --v18-service "${CONTINUUM_V18_SERVICE:-continuum-agent-v18}" \
  --verifier-service "${CONTINUUM_VERIFIER_SERVICE:-continuum-verifier}"

python3 scripts/cloud/package-evidence.py "$capture_dir" "$CONTINUUM_EVIDENCE_DIR" \
  --project "$CONTINUUM_PROJECT_ID" --region "$CONTINUUM_REGION" \
  --run-id "$CONTINUUM_RUN_ID" --trace-id "$CONTINUUM_TRACE_ID" --git-commit "$CONTINUUM_GIT_SHA"

python3 scripts/cloud/verify-evidence.py "$CONTINUUM_EVIDENCE_DIR"
python3 - "$CONTINUUM_EVIDENCE_DIR/report.json" <<'PY'
import json, pathlib, sys
report = json.loads(pathlib.Path(sys.argv[1]).read_text())
if report.get("overall") != "PASS":
    raise SystemExit(f'cloud proof is {report.get("overall")}; inspect report.json')
PY
echo "Read-only exact-run evidence captured with semantic PASS."

#!/usr/bin/env bash
set -euo pipefail
npm test --prefix interop/typescript

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

UV_ARGS=(--extra google --extra web --extra signatures --extra test)

uv sync --locked "${UV_ARGS[@]}"
cleanup() {
  uv run "${UV_ARGS[@]}" coverage erase
}
trap cleanup EXIT
coverage_dir="$ROOT_DIR/artifacts/coverage"
rm -rf "$coverage_dir"
mkdir -p "$coverage_dir"
uv run "${UV_ARGS[@]}" coverage erase
uv run "${UV_ARGS[@]}" coverage run -m unittest discover -s tests -v
uv run "${UV_ARGS[@]}" coverage report
uv run "${UV_ARGS[@]}" coverage json --pretty-print -o "$coverage_dir/coverage.json"
uv run "${UV_ARGS[@]}" coverage xml -o "$coverage_dir/coverage.xml"
uv run "${UV_ARGS[@]}" coverage html -d "$coverage_dir/html"
uv run "${UV_ARGS[@]}" python scripts/build_coverage_evidence.py \
  --coverage-json "$coverage_dir/coverage.json" \
  --output "$coverage_dir"
uv run "${UV_ARGS[@]}" python scripts/release_gate.py
uv run "${UV_ARGS[@]}" python scripts/check_release_truth.py

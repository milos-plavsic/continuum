#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

UV_ARGS=(--extra google --extra web --extra signatures --extra test)

uv sync --locked "${UV_ARGS[@]}"
uv run "${UV_ARGS[@]}" coverage erase
uv run "${UV_ARGS[@]}" coverage run -m unittest discover -s tests -v
uv run "${UV_ARGS[@]}" coverage report
uv run "${UV_ARGS[@]}" python scripts/release_gate.py

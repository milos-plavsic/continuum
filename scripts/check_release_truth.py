#!/usr/bin/env python3
"""Fail if a judge-facing surface contradicts the canonical release manifest."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from continuum.release_truth import audit_judge_surfaces, load_release_truth, release_summary


def main() -> int:
    truth = load_release_truth(ROOT / "docs/submission/current-release.json")
    failures = audit_judge_surfaces(ROOT, truth)
    report = {"schema": truth["schema"], "status": "PASS" if not failures else "FAIL",
              "summary": release_summary(truth), "reason_codes": list(failures)}
    print(json.dumps(report, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

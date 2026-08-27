#!/usr/bin/env python3
from __future__ import annotations

import json
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from continuum.stress import run_concurrent_stress


parser = argparse.ArgumentParser(description="Run deterministic Continuum contention checks")
parser.add_argument("--runs", type=int, default=16)
parser.add_argument("--attempts", type=int, default=8)
arguments = parser.parse_args()
result = run_concurrent_stress(run_count=arguments.runs,
                               attempts_per_run=arguments.attempts)
output = ROOT / "artifacts" / "evaluation" / "concurrent-stress.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n")
print(json.dumps(result.to_dict(), indent=2, sort_keys=True))

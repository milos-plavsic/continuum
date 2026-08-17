#!/usr/bin/env python3
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from continuum.conformance import run_conformance

report = run_conformance(ROOT / "artifacts" / "conformance")
print(json.dumps({"profile": report["profile"], "highest_level": report["highest_level"],
                  "levels": report["levels"], "report_digest": report["report_digest"]}, indent=2))

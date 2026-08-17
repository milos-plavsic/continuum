#!/usr/bin/env python3
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from continuum.standard import build_contract_bundle

output = ROOT / "artifacts" / "contract"
output.mkdir(parents=True, exist_ok=True)
bundle = build_contract_bundle(output)
destination = output / "continuity-contract-bundle.json"
destination.write_text(json.dumps(bundle, indent=2) + "\n")
print(destination)

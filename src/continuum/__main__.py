import argparse
import json
from pathlib import Path

from .scenario import run_scenario

parser = argparse.ArgumentParser(description="Run the Continuum deterministic succession fixture")
parser.add_argument("--output", type=Path, default=Path("artifacts/latest"))
args = parser.parse_args()
print(json.dumps(run_scenario(args.output), indent=2, default=str))


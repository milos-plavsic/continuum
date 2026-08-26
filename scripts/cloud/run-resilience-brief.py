#!/usr/bin/env python3
"""Create a verifier-gated Gemma -> Veo/Lyria resilience brief."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from continuum.resilience_brief import (  # noqa: E402
    GemmaLearningPlanner, LyriaLearningRenderer, VeoLearningRenderer,
    VerifiedResilienceBrief,
    gcs_binary_sink,
)


def contract_export(evidence_dir: Path) -> dict:
    manifest = json.loads((evidence_dir / "bundle.json").read_text())
    matches = [item for item in manifest["objects"] if item["object_id"] == "contract-export"]
    if len(matches) != 1:
        raise ValueError("CONTRACT_EXPORT_REFERENCE_INVALID")
    path = evidence_dir / "objects" / matches[0]["sha256"]
    value = json.loads(path.read_text())
    if value.get("status") != "PASS" or not isinstance(value.get("bundle"), dict):
        raise ValueError("VERIFIED_CONTRACT_EXPORT_REQUIRED")
    return {**value, "outcome": "VERIFIED"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--veo-output-uri", required=True)
    parser.add_argument("--lyria-output-uri", required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)

    service = VerifiedResilienceBrief(
        GemmaLearningPlanner(args.project),
        VeoLearningRenderer(args.project, args.veo_output_uri),
        LyriaLearningRenderer(args.project, gcs_binary_sink(args.lyria_output_uri)),
    )
    receipt = service.create(contract_export(args.evidence_dir))
    receipt_path = args.output_dir / "verified-resilience-brief.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(receipt_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

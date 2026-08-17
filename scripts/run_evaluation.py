#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from continuum.scenario import run_scenario

OUTPUT = ROOT / "artifacts" / "evaluation"
if OUTPUT.exists():
    shutil.rmtree(OUTPUT)
OUTPUT.mkdir(parents=True)

canonical = run_scenario(OUTPUT / "canonical")
silence = run_scenario(OUTPUT / "silence-only", signals=("missed_evidence",))
replays = [run_scenario(OUTPUT / f"replay-{number}") for number in range(20)]
baseline = [(item["manifest_hash"], item["timeline"]) for item in replays]
divergences = sum(value != baseline[0] for value in baseline)

report = {
    "suite": "procurement-succession-v1",
    "observed_local": {
        "scenario_runs_executed": 22,
        "canonical_verified": canonical["outcome"] == "VERIFIED",
        "external_duplicate_effects": canonical["vendor_count"] - 1,
        "post_revocation_actions_blocked": int("STALE_FENCE" in canonical["denials"]),
        "post_revocation_memory_blocked": int("GRANT_REVOKED" in canonical["denials"]),
        "revoked_memory_candidates_exposed": canonical["revoked_candidates_exposed"],
        "benign_silence_quarantines": int(silence.get("quarantined", False)),
        "replay_divergences": divergences,
        "event_integrity": canonical["events_valid"],
    },
    "pending_external_evidence": [
        "live Gemini schema-valid and citation-grounding rates",
        "Cloud Run deployment and distinct service identities",
        "Firestore transaction and Pub/Sub redelivery integration",
        "Cloud Trace latency and complete span correlation",
    ],
}
(OUTPUT / "report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))

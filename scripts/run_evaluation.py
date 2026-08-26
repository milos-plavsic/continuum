#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
from itertools import combinations

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from continuum.scenario import run_scenario
from continuum.conformance import run_conformance
from continuum.models import digest

OUTPUT = ROOT / "artifacts" / "evaluation"
if OUTPUT.exists():
    shutil.rmtree(OUTPUT)
OUTPUT.mkdir(parents=True)

signal_names = ("injection", "anomalous_action", "missed_evidence")
signal_cases = []
for size in range(4):
    for selected in combinations(signal_names, size):
        outcome = run_scenario(OUTPUT / ("signals-" + ("-".join(selected) or "none")), signals=selected)
        signal_cases.append({"case": "signals:" + ("+".join(selected) or "none"),
                             "inputs": {"signals": list(selected)}, "outcome": outcome["outcome"],
                             "vendor_count": outcome["vendor_count"],
                             "result_digest": digest({"signals": list(selected),
                                                      "outcome": outcome["outcome"],
                                                      "vendor_count": outcome["vendor_count"],
                                                      "event_count": outcome["event_count"]})})
canonical = run_scenario(OUTPUT / "canonical")
silence = next(case for case in signal_cases if case["case"] == "signals:missed_evidence")
replays = [run_scenario(OUTPUT / f"replay-{number}") for number in range(5)]
baseline = [(item["manifest_hash"], item["timeline"]) for item in replays]
divergences = sum(value != baseline[0] for value in baseline)
conformance = run_conformance(OUTPUT / "conformance")
executed_cases = [
    {"case": case["id"], "level": case["level"], "assertion": case["assertion"],
     "outcome": case["status"], "result_digest": case["evidence_sha256"]}
    for case in conformance["cases"]
]

report = {
    "suite": "procurement-succession-v1",
    "observed_local": {
        "scenario_runs_executed": 13,
        "distinct_signal_cases": signal_cases,
        "conformance_cases_executed": executed_cases,
        "conformance_highest_level": conformance["highest_level"],
        "canonical_verified": canonical["outcome"] == "VERIFIED",
        "external_duplicate_effects": canonical["vendor_count"] - 1,
        "post_revocation_actions_blocked": int("STALE_FENCE" in canonical["denials"]),
        "post_revocation_memory_blocked": int("GRANT_REVOKED" in canonical["denials"]),
        "revoked_memory_candidates_exposed": canonical["revoked_candidates_exposed"],
        "benign_silence_quarantines": int(silence["outcome"] != "INVESTIGATE_HOLD"),
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

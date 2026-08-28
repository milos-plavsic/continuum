#!/usr/bin/env python3
"""Run the complete local release gate and report the external cloud prerequisite."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from continuum.conformance import run_conformance
from continuum.release_truth import audit_judge_surfaces, load_release_truth
from continuum.scenario import run_scenario
from continuum.standard import build_contract_bundle, verify_bundle
from continuum.trust_profile import load_trust_profile


def evaluate_local(workspace: Path) -> dict:
    scenario = run_scenario(workspace / "scenario")
    conformance = run_conformance(workspace / "conformance")
    bundle = build_contract_bundle(workspace / "contract")
    verify_bundle(bundle)
    trust_profile = load_trust_profile(ROOT / "docs/trust-profile.json")
    assertions = {
        "scenario_verified": scenario["outcome"] == "VERIFIED",
        "one_provider_effect": scenario["vendor_count"] == 1,
        "predecessor_action_denied": "STALE_FENCE" in scenario["denials"],
        "predecessor_memory_denied": "GRANT_REVOKED" in scenario["denials"],
        "event_integrity": scenario["events_valid"],
        "local_conformance_c6": conformance["highest_level"] == "C6",
        "six_artifact_contract": len(bundle["artifacts"]) == 6,
        "trust_ceiling_declared": bool(trust_profile["profile_digest"]),
    }
    return {"status": "PASS" if all(assertions.values()) else "FAIL",
            "assertions": assertions,
            "conformance_report_digest": conformance["report_digest"]}


def cloud_readiness() -> dict:
    missing = []
    if shutil.which("gcloud") is None:
        missing.append("GCLOUD_CLI")
    for name in ("CONTINUUM_PROJECT_ID", "CONTINUUM_REGION", "CONTINUUM_FIRESTORE_LOCATION"):
        if not os.getenv(name):
            missing.append(name)
    return {"status": "READY" if not missing else "EXTERNAL_PREREQUISITE_REQUIRED",
            "missing": missing}


def repository_controls() -> dict:
    commands = {
        "configuration_inventory": [sys.executable, "scripts/check_configuration.py", "--check"],
        "assurance_profiles": [sys.executable, "scripts/check_assurance_profiles.py"],
        "external_witness": [sys.executable, "scripts/verify_external_witness.py"],
    }
    results = {}
    for name, command in commands.items():
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        results[name] = "PASS" if completed.returncode == 0 else "FAIL"
    return {"status": "PASS" if all(value == "PASS" for value in results.values()) else "FAIL",
            "controls": results}


def main() -> int:
    warning_environment = {**os.environ, "PYTHONWARNINGS": "error"}
    tests = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=ROOT,
        env=warning_environment)
    with TemporaryDirectory(prefix="continuum-release-") as temporary:
        local = evaluate_local(Path(temporary)) if tests.returncode == 0 else {
            "status": "FAIL", "assertions": {"unit_tests": False}}
    truth = load_release_truth(ROOT / "docs/submission/current-release.json")
    truth_failures = audit_judge_surfaces(ROOT, truth)
    controls = repository_controls()
    report = {"schema": "continuum/release-gate/0.1", "unit_tests": {
                  "status": "PASS" if tests.returncode == 0 else "FAIL"},
              "submission_truth": {"status": "PASS" if not truth_failures else "FAIL",
                                   "reason_codes": list(truth_failures)},
              "repository_controls": controls, "reference_local": local,
              "google_cloud": cloud_readiness(),
              "overall": "PASS" if (tests.returncode == 0 and local["status"] == "PASS"
                                      and not truth_failures and controls["status"] == "PASS") else "FAIL"}
    print(json.dumps(report, indent=2))
    return 0 if report["overall"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Fail closed when CI, cloud, coverage, or witness assurance is overstated."""
from __future__ import annotations

import json
from pathlib import Path
import sys

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config/assurance-profiles.json"
SCHEMA = ROOT / "schemas/assurance-profiles-v1.schema.json"
REQUIRED_CI_NON_CLAIMS = {
    "semantic correctness follows from coverage", "production fitness",
    "live Google Cloud execution", "complete threat coverage", "capture provenance",
}
REQUIRED_CLOUD_NON_CLAIMS = {
    "regular CI re-executes this cloud lifecycle",
    "capture provenance is independently authenticated",
    "Google infrastructure was uncompromised", "Byzantine consensus",
}


def audit(root: Path = ROOT) -> list[str]:
    schema = json.loads((root / SCHEMA.relative_to(ROOT)).read_text())
    manifest = json.loads((root / MANIFEST.relative_to(ROOT)).read_text())
    failures = [f"ASSURANCE_SCHEMA:{error.json_path}:{error.message}" for error in
                Draft202012Validator(schema).iter_errors(manifest)]
    profiles = manifest.get("profiles", [])
    ids = [profile.get("id") for profile in profiles]
    if ids != sorted(ids) or len(ids) != len(set(ids)):
        failures.append("ASSURANCE_PROFILE_ORDER_OR_DUPLICATE")
    by_id = {profile.get("id"): profile for profile in profiles}
    ci = by_id.get("regular-ci", {})
    if any((ci.get("credentials"), ci.get("billable"), ci.get("live_google_cloud"))):
        failures.append("REGULAR_CI_BOUNDARY_INVALID")
    if not ci.get("test_doubles"):
        failures.append("REGULAR_CI_DOUBLES_UNDECLARED")
    if not REQUIRED_CI_NON_CLAIMS.issubset(set(ci.get("non_claims", []))):
        failures.append("REGULAR_CI_NON_CLAIMS_INCOMPLETE")
    cloud = by_id.get("live-gcp-proof", {})
    if not all((cloud.get("credentials"), cloud.get("billable"),
                cloud.get("live_google_cloud"))) or cloud.get("test_doubles"):
        failures.append("LIVE_GCP_BOUNDARY_INVALID")
    if not REQUIRED_CLOUD_NON_CLAIMS.issubset(set(cloud.get("non_claims", []))):
        failures.append("LIVE_GCP_NON_CLAIMS_INCOMPLETE")
    witness = by_id.get("external-witness", {})
    registry_path = witness.get("witness_registry", "")
    registry = json.loads((root / registry_path).read_text()) if registry_path and (root / registry_path).is_file() else {}
    accepted = registry.get("accepted_witnesses", [])
    expected_status = "ATTESTED" if accepted else "AWAITING_EXTERNAL_WITNESS"
    if witness.get("status") != expected_status or registry.get("status") != expected_status:
        failures.append("EXTERNAL_WITNESS_STATUS_MISMATCH")
    for key in ("release_manifest",):
        path = cloud.get(key, "")
        if not path or not (root / path).is_file():
            failures.append(f"ASSURANCE_REFERENCE_MISSING:{key}")
    return sorted(failures)


def main() -> int:
    failures = audit()
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    manifest = json.loads(MANIFEST.read_text())
    print(json.dumps({"status": "PASS", "profiles": len(manifest["profiles"]),
                      "live_cloud_in_regular_ci": False,
                      "external_witness_status": manifest["profiles"][0]["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

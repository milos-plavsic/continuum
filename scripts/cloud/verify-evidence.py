#!/usr/bin/env python3
"""Offline consistency verifier: never imports Google SDKs or uses credentials."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from continuum.contract import canonical_bytes

MANDATORY = {
    "cloud-run-control", "cloud-run-v17", "cloud-run-v18", "cloud-run-verifier",
    "firestore-event", "firestore-projection", "firestore-outbox",
    "pubsub-publish", "pubsub-deliveries", "vertex-call", "trace-export",
    "contract-export",
}
BASE_NON_CLAIMS = {"third_party_interoperability", "universal_exactly_once",
                   "global_credential_revocation", "tamper_proof"}


def verify(directory: Path) -> dict:
    manifest_path = directory / "bundle.json"
    if not manifest_path.exists():
        return report("unknown", "NOT_ASSESSED", [], sorted(MANDATORY), ["BUNDLE_MISSING"])
    try:
        bundle = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError):
        return report("unknown", "FAIL", [], [], ["BUNDLE_INVALID_JSON"])
    errors: list[str] = []
    if bundle.get("schema") != "continuum/cloud-evidence/0.1" or bundle.get("profile") != "reference-google-cloud":
        errors.append("BUNDLE_SCHEMA_INVALID")
    if not BASE_NON_CLAIMS.issubset(set(bundle.get("declared_non_claims", []))):
        errors.append("BASE_NON_CLAIMS_MISSING")
    unsigned = deepcopy(bundle); supplied = unsigned.pop("bundle_digest", None)
    expected = sha256(b"continuum-cloud-evidence\x000.1\x00" + canonical_bytes(unsigned)).hexdigest()
    if supplied != {"alg": "sha-256", "value": expected}:
        errors.append("BUNDLE_DIGEST_MISMATCH")
    seen: set[str] = set()
    for item in bundle.get("objects", []):
        object_id, digest = item.get("object_id"), item.get("sha256")
        if not object_id or object_id in seen or not isinstance(digest, str):
            errors.append("OBJECT_MANIFEST_INVALID"); continue
        seen.add(object_id)
        path = directory / "objects" / digest
        try: data = path.read_bytes()
        except OSError: errors.append(f"OBJECT_MISSING:{object_id}"); continue
        if len(data) != item.get("size") or sha256(data).hexdigest() != digest:
            errors.append(f"OBJECT_INTEGRITY_FAILED:{object_id}")
    missing = sorted(MANDATORY - seen)
    # Presence and integrity are necessary, but do not establish the semantic
    # cloud predicates (identity separation, model version, redelivery, etc.).
    # Until those checks are implemented, a complete bundle must remain NA.
    if not errors and not missing:
        errors.append("SEMANTIC_CLOUD_PREDICATES_NOT_IMPLEMENTED")
    overall = "FAIL" if errors and errors != ["SEMANTIC_CLOUD_PREDICATES_NOT_IMPLEMENTED"] else "NOT_ASSESSED"
    return report(bundle.get("bundle_id", "unknown"), overall, sorted(seen), missing, errors)


def report(bundle_id: str, overall: str, present: list[str], missing: list[str], errors: list[str]) -> dict:
    result = {"schema": "continuum/cloud-evidence-report/0.1", "bundle_id": bundle_id,
              "verifier": {"name": "continuum-offline-cloud-verifier", "version": "0.1",
                           "credentials_used": False, "network_used": False},
              "overall": overall, "present_objects": present, "missing_mandatory_objects": missing,
              "reason_codes": errors, "evidence_capture_not_reperformed": True}
    result["report_digest"] = {"alg": "sha-256", "value": sha256(canonical_bytes(result)).hexdigest()}
    return result


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify-evidence.py EVIDENCE_DIRECTORY")
    destination = Path(sys.argv[1])
    result = verify(destination)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if result["overall"] == "FAIL" else 0)

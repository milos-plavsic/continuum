#!/usr/bin/env python3
"""Offline semantic verifier; it never imports cloud SDKs or uses credentials."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from typing import Any

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
ROLES = {"cloud-run-control": "control", "cloud-run-v17": "agent-v17",
         "cloud-run-v18": "agent-v18", "cloud-run-verifier": "verifier"}
IMAGE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
GIT_COMMIT = re.compile(r"^[0-9a-f]{7,64}$")


def _same(value: Any, expected: Any, code: str, errors: list[str]) -> None:
    if value != expected:
        errors.append(code)


def _semantic(bundle: dict, objects: dict[str, dict]) -> list[str]:
    """Return contradictions. Called only when every mandatory object is valid JSON."""
    errors: list[str] = []
    scope = bundle.get("scope")
    if not isinstance(scope, dict):
        return ["SCOPE_INVALID"]
    required_scope = ("project_id", "region", "run_id", "trace_id", "git_commit", "protocol")
    if any(not isinstance(scope.get(key), str) or not scope[key] for key in required_scope):
        return ["SCOPE_INVALID"]
    if not GIT_COMMIT.fullmatch(scope["git_commit"]):
        errors.append("GIT_COMMIT_INVALID")

    identities: set[str] = set()
    images: set[str] = set()
    for object_id, role in ROLES.items():
        value = objects[object_id]
        _same(value.get("project_id"), scope["project_id"], f"CLOUD_RUN_PROJECT_MISMATCH:{object_id}", errors)
        _same(value.get("region"), scope["region"], f"CLOUD_RUN_REGION_MISMATCH:{object_id}", errors)
        _same(value.get("role"), role, f"CLOUD_RUN_ROLE_MISMATCH:{object_id}", errors)
        _same(value.get("ready"), True, f"CLOUD_RUN_NOT_READY:{object_id}", errors)
        identity, digest = value.get("service_account"), value.get("image_digest")
        if not isinstance(identity, str) or not identity:
            errors.append(f"CLOUD_RUN_IDENTITY_INVALID:{object_id}")
        elif identity in identities:
            errors.append("CLOUD_RUN_IDENTITIES_NOT_DISTINCT")
        else:
            identities.add(identity)
        if not isinstance(digest, str) or not IMAGE_DIGEST.fullmatch(digest):
            errors.append(f"IMAGE_DIGEST_INVALID:{object_id}")
        else:
            images.add(digest)
        build = value.get("build_info", {})
        _same(build.get("git_commit"), scope["git_commit"], f"BUILD_COMMIT_MISMATCH:{object_id}", errors)
        _same(build.get("protocol"), scope["protocol"], f"BUILD_PROTOCOL_MISMATCH:{object_id}", errors)
    if len(images) != 1:
        errors.append("DEPLOYED_IMAGE_DIGEST_MISMATCH")

    event, projection, outbox = (objects["firestore-event"], objects["firestore-projection"],
                                  objects["firestore-outbox"])
    for object_id, value in (("firestore-event", event), ("firestore-projection", projection),
                             ("firestore-outbox", outbox)):
        _same(value.get("run_id"), scope["run_id"], f"RUN_ID_MISMATCH:{object_id}", errors)
    event_id = event.get("event_id")
    if not isinstance(event_id, str) or not event_id:
        errors.append("FIRESTORE_EVENT_ID_INVALID")
    _same(projection.get("last_event_id"), event_id, "PROJECTION_EVENT_MISMATCH", errors)
    _same(outbox.get("event_id"), event_id, "OUTBOX_EVENT_MISMATCH", errors)
    _same(outbox.get("status"), "PUBLISHED", "OUTBOX_NOT_PUBLISHED", errors)

    publish, deliveries = objects["pubsub-publish"], objects["pubsub-deliveries"]
    message_id = publish.get("message_id")
    _same(publish.get("event_id"), event_id, "PUBSUB_EVENT_MISMATCH", errors)
    _same(publish.get("run_id"), scope["run_id"], "RUN_ID_MISMATCH:pubsub-publish", errors)
    attempts = deliveries.get("deliveries")
    if (not isinstance(message_id, str) or not message_id or not isinstance(attempts, list)
            or len(attempts) < 2):
        errors.append("PUBSUB_REDELIVERY_NOT_PROVEN")
    else:
        if any(item.get("message_id") != message_id for item in attempts if isinstance(item, dict)):
            errors.append("PUBSUB_MESSAGE_ID_MISMATCH")
        if any(not isinstance(item, dict) for item in attempts):
            errors.append("PUBSUB_DELIVERY_INVALID")
        delivery_ids = [item.get("delivery_id") for item in attempts if isinstance(item, dict)]
        if any(not item for item in delivery_ids) or len(set(delivery_ids)) != len(delivery_ids):
            errors.append("PUBSUB_REDELIVERY_NOT_PROVEN")
        _same(deliveries.get("run_id"), scope["run_id"], "RUN_ID_MISMATCH:pubsub-deliveries", errors)

    vertex = objects["vertex-call"]
    _same(vertex.get("run_id"), scope["run_id"], "RUN_ID_MISMATCH:vertex-call", errors)
    _same(vertex.get("provider"), "vertex-ai", "VERTEX_PROVIDER_INVALID", errors)
    model = vertex.get("model")
    match = re.search(r"gemini-(\d+)(?:\.(\d+))?", model or "")
    if not match or (int(match.group(1)), int(match.group(2) or 0)) < (3, 5):
        errors.append("VERTEX_MODEL_TOO_OLD")
    if vertex.get("service_account") != objects["cloud-run-control"].get("service_account"):
        errors.append("VERTEX_IDENTITY_MISMATCH")
    citations = vertex.get("evidence_event_ids")
    if not isinstance(citations, list) or event_id not in citations:
        errors.append("VERTEX_EVIDENCE_CITATION_MISSING")

    trace = objects["trace-export"]
    _same(trace.get("trace_id"), scope["trace_id"], "TRACE_ID_MISMATCH", errors)
    _same(trace.get("run_id"), scope["run_id"], "RUN_ID_MISMATCH:trace-export", errors)
    spans = trace.get("spans")
    required_spans = {"investigation", "policy", "succession", "verification"}
    names = {span.get("name") for span in spans if isinstance(span, dict)} if isinstance(spans, list) else set()
    if not required_spans.issubset(names):
        errors.append("TRACE_LIFECYCLE_INCOMPLETE")

    contract = objects["contract-export"]
    _same(contract.get("run_id"), scope["run_id"], "RUN_ID_MISMATCH:contract-export", errors)
    _same(contract.get("protocol"), scope["protocol"], "CONTRACT_PROTOCOL_MISMATCH", errors)
    _same(contract.get("status"), "PASS", "CONTRACT_NOT_PASSING", errors)
    if not isinstance(contract.get("report_digest"), dict):
        errors.append("CONTRACT_REPORT_DIGEST_MISSING")
    return sorted(set(errors))


def verify(directory: Path) -> dict:
    manifest_path = directory / "bundle.json"
    if not manifest_path.exists():
        return report("unknown", "NOT_ASSESSED", [], sorted(MANDATORY), ["BUNDLE_MISSING"])
    try:
        bundle = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError):
        return report("unknown", "FAIL", [], [], ["BUNDLE_INVALID_JSON"])
    if not isinstance(bundle, dict):
        return report("unknown", "FAIL", [], [], ["BUNDLE_INVALID"])
    errors: list[str] = []
    if bundle.get("schema") != "continuum/cloud-evidence/0.1" or bundle.get("profile") != "reference-google-cloud":
        errors.append("BUNDLE_SCHEMA_INVALID")
    non_claims = bundle.get("declared_non_claims")
    if not isinstance(non_claims, list) or not BASE_NON_CLAIMS.issubset(
            {item for item in non_claims if isinstance(item, str)}):
        errors.append("BASE_NON_CLAIMS_MISSING")
    unsigned = deepcopy(bundle)
    supplied = unsigned.pop("bundle_digest", None)
    try:
        expected = sha256(b"continuum-cloud-evidence\x000.1\x00" + canonical_bytes(unsigned)).hexdigest()
    except (TypeError, ValueError):
        expected = None
        errors.append("BUNDLE_CANONICALIZATION_FAILED")
    if expected is None or supplied != {"alg": "sha-256", "value": expected}:
        errors.append("BUNDLE_DIGEST_MISMATCH")
    if bundle.get("collection_errors"):
        errors.append("COLLECTION_ERRORS_REPORTED")
    seen: set[str] = set()
    decoded: dict[str, dict] = {}
    items = bundle.get("objects")
    if not isinstance(items, list):
        errors.append("OBJECT_MANIFEST_INVALID")
        items = []
    for item in items:
        if not isinstance(item, dict):
            errors.append("OBJECT_MANIFEST_INVALID")
            continue
        object_id, digest = item.get("object_id"), item.get("sha256")
        if not object_id or object_id in seen or not isinstance(digest, str):
            errors.append("OBJECT_MANIFEST_INVALID")
            continue
        seen.add(object_id)
        path = directory / "objects" / digest
        try:
            data = path.read_bytes()
        except OSError:
            errors.append(f"OBJECT_MISSING:{object_id}")
            continue
        if len(data) != item.get("size") or sha256(data).hexdigest() != digest:
            errors.append(f"OBJECT_INTEGRITY_FAILED:{object_id}")
            continue
        try:
            value = json.loads(data)
        except json.JSONDecodeError:
            errors.append(f"OBJECT_INVALID_JSON:{object_id}")
            continue
        if not isinstance(value, dict):
            errors.append(f"OBJECT_INVALID:{object_id}")
            continue
        decoded[object_id] = value
    missing = sorted(MANDATORY - seen)
    if not errors and not missing and MANDATORY.issubset(decoded):
        errors.extend(_semantic(bundle, decoded))
    overall = "FAIL" if errors else ("NOT_ASSESSED" if missing else "PASS")
    return report(bundle.get("bundle_id", "unknown"), overall, sorted(seen), missing, sorted(set(errors)))


def report(bundle_id: str, overall: str, present: list[str], missing: list[str], errors: list[str]) -> dict:
    result = {"schema": "continuum/cloud-evidence-report/0.1", "bundle_id": bundle_id,
              "verifier": {"name": "continuum-offline-cloud-verifier", "version": "0.2",
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

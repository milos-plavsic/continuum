#!/usr/bin/env python3
"""Offline semantic verifier; it never imports cloud SDKs or uses credentials."""
from __future__ import annotations

from copy import deepcopy
import base64
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from continuum.contract import canonical_bytes
from continuum.canonicalization import PROFILE as CANONICALIZATION_PROFILE
from continuum.standard import verify_bundle
from continuum.succession_selection import SUPPORT_CLAIMS

MANDATORY = {
    "cloud-run-control", "cloud-run-v17", "cloud-run-v18", "cloud-run-v19", "cloud-run-verifier",
    "firestore-event", "firestore-projection", "firestore-outbox",
    "pubsub-publish", "pubsub-deliveries", "vertex-call", "trace-export",
    "supplier-assurance", "contract-export",
    "build-provenance",
}
BASE_NON_CLAIMS = {"third_party_interoperability", "universal_exactly_once",
                   "global_credential_revocation", "tamper_proof"}
ROLES = {"cloud-run-control": "control", "cloud-run-v17": "agent-v17",
         "cloud-run-v18": "agent-v18", "cloud-run-v19": "agent-v19",
         "cloud-run-verifier": "verifier"}
IMAGE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
GIT_COMMIT = re.compile(r"^[0-9a-f]{7,64}$")


def _same(value: Any, expected: Any, code: str, errors: list[str]) -> None:
    if value != expected:
        errors.append(code)


def _provenance_subjects(value: dict[str, Any], errors: list[str]) -> set[str]:
    summary = value.get("provenance_summary")
    entries = summary.get("provenance") if isinstance(summary, dict) else None
    if not isinstance(entries, list) or not entries:
        errors.append("BUILD_PROVENANCE_MISSING")
        return set()
    subjects: set[str] = set()
    found_v1 = False
    for entry in entries:
        build = entry.get("build") if isinstance(entry, dict) else None
        statement = build.get("intotoStatement") if isinstance(build, dict) else None
        envelope = entry.get("envelope") if isinstance(entry, dict) else None
        if not isinstance(statement, dict) or not isinstance(envelope, dict):
            continue
        if statement.get("predicateType") == "https://slsa.dev/provenance/v1":
            found_v1 = True
        signatures = envelope.get("signatures")
        payload = envelope.get("payload")
        if (not isinstance(signatures, list) or not signatures
                or any(not isinstance(item, dict) or not item.get("sig") for item in signatures)
                or not isinstance(payload, str) or not payload):
            errors.append("BUILD_PROVENANCE_DSSE_INCOMPLETE")
            continue
        try:
            padding = "=" * (-len(payload) % 4)
            decoded = json.loads(base64.urlsafe_b64decode(payload + padding))
        except (ValueError, json.JSONDecodeError):
            errors.append("BUILD_PROVENANCE_PAYLOAD_INVALID")
            continue
        for subject in decoded.get("subject", []) if isinstance(decoded, dict) else []:
            digest = subject.get("digest", {}).get("sha256") if isinstance(subject, dict) else None
            if isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest):
                subjects.add(f"sha256:{digest}")
    if not found_v1:
        errors.append("BUILD_PROVENANCE_SLSA_V1_MISSING")
    return subjects


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
    image_references: set[str] = set()
    services: set[str] = set()
    revisions: set[str] = set()
    for object_id, role in ROLES.items():
        value = objects[object_id]
        _same(value.get("project_id"), scope["project_id"], f"CLOUD_RUN_PROJECT_MISMATCH:{object_id}", errors)
        _same(value.get("region"), scope["region"], f"CLOUD_RUN_REGION_MISMATCH:{object_id}", errors)
        _same(value.get("role"), role, f"CLOUD_RUN_ROLE_MISMATCH:{object_id}", errors)
        _same(value.get("ready"), True, f"CLOUD_RUN_NOT_READY:{object_id}", errors)
        service, revision = value.get("service"), value.get("revision")
        if not isinstance(service, str) or not service:
            errors.append(f"CLOUD_RUN_SERVICE_INVALID:{object_id}")
        elif service in services:
            errors.append("CLOUD_RUN_SERVICES_NOT_DISTINCT")
        else:
            services.add(service)
        if not isinstance(revision, str) or not revision.startswith(f"{service}-"):
            errors.append(f"CLOUD_RUN_REVISION_INVALID:{object_id}")
        elif revision in revisions:
            errors.append("CLOUD_RUN_REVISIONS_NOT_DISTINCT")
        else:
            revisions.add(revision)
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
        image_reference = value.get("image_reference")
        if (not isinstance(image_reference, str) or not isinstance(digest, str)
                or not image_reference.endswith(f"@{digest}")):
            errors.append(f"IMAGE_REFERENCE_INVALID:{object_id}")
        else:
            image_references.add(image_reference)
        build = value.get("build_info", {})
        _same(build.get("git_commit"), scope["git_commit"], f"BUILD_COMMIT_MISMATCH:{object_id}", errors)
        _same(build.get("protocol"), scope["protocol"], f"BUILD_PROTOCOL_MISMATCH:{object_id}", errors)
    if len(images) != 1:
        errors.append("DEPLOYED_IMAGE_DIGEST_MISMATCH")
    if len(image_references) != 1:
        errors.append("DEPLOYED_IMAGE_REFERENCE_MISMATCH")
    provenance = objects["build-provenance"]
    provenance_subjects = _provenance_subjects(provenance, errors)
    if images and not images.issubset(provenance_subjects):
        errors.append("BUILD_PROVENANCE_IMAGE_MISMATCH")
    image_summary = provenance.get("image_summary")
    if not isinstance(image_summary, dict):
        errors.append("BUILD_PROVENANCE_IMAGE_SUMMARY_MISSING")
    else:
        if images and image_summary.get("digest") not in images:
            errors.append("BUILD_PROVENANCE_SUMMARY_DIGEST_MISMATCH")
        if image_references and image_summary.get("fully_qualified_digest") not in image_references:
            errors.append("BUILD_PROVENANCE_SUMMARY_REFERENCE_MISMATCH")

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
    if vertex.get("service_account") != objects["cloud-run-v18"].get("service_account"):
        errors.append("VERTEX_IDENTITY_MISMATCH")
    citations = vertex.get("evidence_event_ids")
    if not isinstance(citations, list) or event_id not in citations:
        errors.append("VERTEX_EVIDENCE_CITATION_MISSING")
    if vertex.get("proposed_actions") != ["initiate_governed_succession"]:
        errors.append("VERTEX_REMEDIATION_NOT_ADMITTED")
    selected = vertex.get("selected_candidate_id")
    if selected not in {"v18", "v19"}:
        errors.append("VERTEX_SUCCESSOR_CHOICE_INVALID")
    manifest_refs = vertex.get("evidence_manifest_refs")
    if (not isinstance(manifest_refs, list) or not manifest_refs
            or any(not isinstance(ref, str) or not ref for ref in manifest_refs)
            or len(set(manifest_refs)) != len(manifest_refs)):
        errors.append("VERTEX_EVIDENCE_MANIFEST_INVALID")
    elif selected in {"v18", "v19"}:
        selected_run = objects[f"cloud-run-{selected}"]
        expected_identity_ref = f'identity:{selected_run.get("service_account")}'
        expected_service_ref = f'cloud-run:https://continuum-{"agent-" if selected else ""}{selected}'
        if expected_identity_ref not in manifest_refs:
            errors.append("VERTEX_CANDIDATE_IDENTITY_UNPROVEN")
        if not any(isinstance(ref, str) and ref.startswith(expected_service_ref)
                   for ref in manifest_refs):
            errors.append("VERTEX_CANDIDATE_SERVICE_UNPROVEN")
    supporting = vertex.get("supporting_citations")
    if not isinstance(supporting, list) or not supporting:
        errors.append("VERTEX_SUPPORTING_CITATION_INVALID")
    elif isinstance(manifest_refs, list):
        seen_claims: set[str] = set()
        seen_refs: set[str] = set()
        for citation in supporting:
            if not isinstance(citation, dict) or set(citation) != {"claim", "evidence_refs"}:
                errors.append("VERTEX_SUPPORTING_CITATION_INVALID")
                continue
            claim, refs = citation.get("claim"), citation.get("evidence_refs")
            prefixes = SUPPORT_CLAIMS.get(claim) if isinstance(claim, str) else None
            if (prefixes is None or not isinstance(refs, list) or not refs
                    or any(not isinstance(ref, str) or ref not in manifest_refs
                           or not ref.startswith(prefixes) for ref in refs)):
                errors.append("VERTEX_SUPPORTING_CITATION_INVALID")
                continue
            if claim in seen_claims or any(ref in seen_refs for ref in refs):
                errors.append("VERTEX_SUPPORTING_CITATION_DUPLICATE")
            seen_claims.add(claim)
            seen_refs.update(refs)

    supplier = objects["supplier-assurance"]
    _same(supplier.get("run_id"), scope["run_id"], "RUN_ID_MISMATCH:supplier-assurance", errors)
    _same(supplier.get("workflow"), "SUPPLIER_ASSURANCE_AGENT",
          "SUPPLIER_WORKFLOW_INVALID", errors)
    _same(supplier.get("decision_scope"), "SANDBOX_ONLY",
          "SUPPLIER_SCOPE_NOT_SANDBOXED", errors)
    _same(supplier.get("recommendation"), "ONBOARD",
          "SUPPLIER_RECOMMENDATION_NOT_ADMITTED", errors)
    supplier_model = supplier.get("model")
    supplier_match = re.search(r"gemini-(\d+)(?:\.(\d+))?", supplier_model or "")
    if (not supplier_match or
            (int(supplier_match.group(1)), int(supplier_match.group(2) or 0)) < (3, 5)):
        errors.append("SUPPLIER_MODEL_TOO_OLD")
    decision_pack_digest = supplier.get("decision_pack_digest")
    if not isinstance(decision_pack_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", decision_pack_digest):
        errors.append("SUPPLIER_DECISION_PACK_DIGEST_INVALID")
    if selected in {"v18", "v19"} and supplier.get("service_account") != objects[
            f"cloud-run-{selected}"].get("service_account"):
        errors.append("SUPPLIER_SUCCESSOR_IDENTITY_MISMATCH")
    tools = supplier.get("tools")
    expected_tools = {
        ("gleif.lei-records.read",
         "https://api.gleif.org/api/v1/lei-records/W38RGI023J3WT1HWRP32"),
        ("ec.vies.check-vat-number",
         "https://ec.europa.eu/taxation_customs/vies/rest-api/check-vat-number"),
    }
    if not isinstance(tools, list) or {
            (item.get("tool"), item.get("source_url"))
            for item in tools if isinstance(item, dict)} != expected_tools:
        errors.append("SUPPLIER_OFFICIAL_TOOL_EVIDENCE_INVALID")
    elif any(not isinstance(item.get("evidence_ref"), str)
             or not re.fullmatch(r"sha256:[0-9a-f]{64}", item["evidence_ref"])
             for item in tools):
        errors.append("SUPPLIER_TOOL_RECEIPT_INVALID")

    trace = objects["trace-export"]
    _same(trace.get("trace_id"), scope["trace_id"], "TRACE_ID_MISMATCH", errors)
    _same(trace.get("run_id"), scope["run_id"], "RUN_ID_MISMATCH:trace-export", errors)
    spans = trace.get("spans")
    required_spans = {
        "continuum.missing_event_published", "continuum.investigated",
        "continuum.authorized", "continuum.predecessor_fenced",
        "continuum.successor_active", "continuum.contract_exported",
    }
    names = {span.get("name") for span in spans if isinstance(span, dict)} if isinstance(spans, list) else set()
    if not required_spans.issubset(names):
        errors.append("TRACE_LIFECYCLE_INCOMPLETE")

    contract = objects["contract-export"]
    _same(contract.get("run_id"), scope["run_id"], "RUN_ID_MISMATCH:contract-export", errors)
    _same(contract.get("protocol"), scope["protocol"], "CONTRACT_PROTOCOL_MISMATCH", errors)
    _same(contract.get("status"), "PASS", "CONTRACT_NOT_PASSING", errors)
    if not isinstance(contract.get("report_digest"), dict):
        errors.append("CONTRACT_REPORT_DIGEST_MISSING")
    cloud_bundle = contract.get("bundle")
    if not isinstance(cloud_bundle, dict):
        errors.append("CONTRACT_BUNDLE_MISSING")
    else:
        try:
            verify_bundle(cloud_bundle)
        except (KeyError, TypeError, ValueError):
            errors.append("CONTRACT_BUNDLE_INVALID")
        if cloud_bundle.get("profile") != "reference-google-cloud":
            errors.append("CONTRACT_PROFILE_INVALID")
        attestations = [artifact for artifact in cloud_bundle.get("artifacts", [])
                        if isinstance(artifact, dict) and artifact.get("artifact_type") == "continuity_attestation"]
        if len(attestations) != 1 or attestations[0].get("body", {}).get("outcome") != "VERIFIED":
            errors.append("CONTRACT_ATTESTATION_NOT_VERIFIED")
        expected_contract_digest = {"alg": "sha-256",
                                    "value": sha256(canonical_bytes(cloud_bundle)).hexdigest()}
        if contract.get("report_digest") != expected_contract_digest:
            errors.append("CONTRACT_REPORT_DIGEST_MISMATCH")
        artifacts = {artifact.get("artifact_type"): artifact
                     for artifact in cloud_bundle.get("artifacts", []) if isinstance(artifact, dict)}
        manifest = artifacts.get("succession_manifest", {}).get("body", {})
        receipt = artifacts.get("execution_receipt", {}).get("body", {})
        receipt_envelope = artifacts.get("execution_receipt", {})
        manifest_successor = manifest.get("successor", {}).get("principal_id")
        executing_principal = receipt.get("executing_principal")
        if selected in {"v18", "v19"}:
            accepted_principals = {selected, f"urn:continuum:principal:acme:procurement:{selected}"}
            if manifest_successor not in accepted_principals:
                errors.append("CONTRACT_SELECTED_SUCCESSOR_MISMATCH")
            if executing_principal not in accepted_principals:
                errors.append("CONTRACT_EXECUTING_SUCCESSOR_MISMATCH")
        compliance = receipt_envelope.get("extensions", {}).get(
            "continuum.dev/compliance", {})
        if compliance.get("workflow") != supplier.get("workflow"):
            errors.append("CONTRACT_SUPPLIER_WORKFLOW_MISMATCH")
        if compliance.get("decision_scope") != supplier.get("decision_scope"):
            errors.append("CONTRACT_SUPPLIER_SCOPE_MISMATCH")
        if compliance.get("recommendation") != supplier.get("recommendation"):
            errors.append("CONTRACT_SUPPLIER_RECOMMENDATION_MISMATCH")
        if compliance.get("decision_pack_digest") != decision_pack_digest:
            errors.append("CONTRACT_SUPPLIER_DECISION_PACK_MISMATCH")
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
    if (bundle.get("schema") != "continuum/cloud-evidence/0.1"
            or bundle.get("profile") != "reference-google-cloud"
            or bundle.get("canonicalization_profile") != CANONICALIZATION_PROFILE):
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
              "reason_codes": errors, "evidence_capture_not_reperformed": True,
              "assurance": {
                  "content_integrity": "ASSESSED",
                  "semantic_consistency": "ASSESSED",
                  "capture_provenance": "NOT_REPERFORMED",
              }}
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

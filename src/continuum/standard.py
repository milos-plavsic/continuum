"""Reference construction and independent verification of portable artifacts."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any

from .contract import ContractError, artifact_ref, canonical_bytes, make_envelope, validate_envelope
from .scenario import load_fixture, run_scenario

ISSUED = "2026-08-17T10:05:00Z"
ISSUER = "urn:continuum:principal:acme:control-plane"
DOMAIN = "urn:continuum:authority:acme:procurement-agent"
DECISION = {"artifact_id": "urn:continuum:decision:acme:succession-v17-v18",
            "digest": {"alg": "sha-256", "value": sha256(b"decision-v1").hexdigest()},
            "policy_version": "compromise-succession/1", "outcome": "APPROVE_SUCCESSION"}


def build_contract_bundle(workdir: Path) -> dict[str, Any]:
    result = run_scenario(workdir / "scenario")
    fixture = load_fixture()
    obligation = make_envelope("obligation", "urn:continuum:obligation:acme:vendor-042", ISSUER, ISSUED, {
        "tenant_id": "acme", "subject": "vendor-042 compliance onboarding", "revision": 2,
        "owner": {"principal_id": "urn:continuum:principal:acme:procurement:v18", "authority_domain": DOMAIN, "epoch": 42},
        "description": "Onboard vendor only after verified compliance evidence", "deadline": fixture["deadline"],
        "completion_criteria": [{"criterion_id": "vendor-created", "evidence_type": "provider-observation", "verifier_role": "independent-verifier"}],
        "allowed_effects": ["vendor.create"], "compensation": {"mode": "HUMAN"}, "status": "DISCHARGED",
    })
    grant = make_envelope("authority_grant", "urn:continuum:grant:acme:v18:vendor-042", ISSUER, ISSUED, {
        "tenant_id": "acme", "grant_id": "grant-v18-vendor-042",
        "subject_principal": "urn:continuum:principal:acme:procurement:v18", "authority_domain": DOMAIN,
        "epoch": 42, "obligation_ids": [obligation["artifact_id"]], "capabilities": ["vendor.create"],
        "memory_scopes": ["vendor.approved"], "purpose": "complete vendor-042 onboarding",
        "not_before": "2026-08-17T10:05:00Z", "expires_at": "2026-08-17T11:05:00Z",
        "policy_decision": DECISION, "status": "ACTIVE",
    })
    manifest = make_envelope("succession_manifest", "urn:continuum:succession:acme:v17-v18", ISSUER, ISSUED, {
        "succession_id": "succession-v17-v18", "tenant_id": "acme", "authority_domain": DOMAIN,
        "predecessor": {"principal_id": "urn:continuum:principal:acme:procurement:v17", "epoch": 41},
        "successor": {"principal_id": "urn:continuum:principal:acme:procurement:v18", "epoch": 42},
        "obligations": [artifact_ref(obligation)], "included_grants": [artifact_ref(grant)],
        "excluded_context": [{"reference_or_class": value, "reason_code": "NON_TRANSFERABLE"}
                             for value in ["raw_untrusted_document", "revoked_private_notes", "secret"]],
        "in_flight_effects": [],
        "evidence_refs": [{"event_id": e["event_id"], "event_type": e["event_type"],
                           "digest": {"alg": "sha-256", "value": e["payload_hash"]}}
                          for e in result["timeline"] if e["event_type"] in {"document.injection_detected", "action.denied", "expectation.missed"}],
        "policy_decision": DECISION, "created_from_registry_revision": 42, "state": "COMMITTED",
    })
    revocation = make_envelope("revocation_proof", "urn:continuum:revocation:acme:v17:42", ISSUER, ISSUED, {
        "tenant_id": "acme", "authority_domain": DOMAIN,
        "revoked_principal": "urn:continuum:principal:acme:procurement:v17", "revoked_through_epoch": 41,
        "registry_revision": 42, "effective_at": ISSUED, "revoked_grant_ids": ["grant-v17-private"],
        "enforcement_points": [
            {"id": "action-gateway", "kind": "ACTION", "observation_ref": "event:authorization.denied"},
            {"id": "memory-gateway", "kind": "MEMORY", "observation_ref": "event:retrieval.denied"}],
        "policy_decision": DECISION, "status": "ENFORCED",
    })
    receipt = make_envelope("execution_receipt", "urn:continuum:receipt:acme:vendor-042", ISSUER, ISSUED, {
        "tenant_id": "acme", "obligation": artifact_ref(obligation),
        "executing_principal": "urn:continuum:principal:acme:procurement:v18", "authority_domain": DOMAIN,
        "epoch": 42, "decision": DECISION, "idempotency_key": fixture["idempotency_key"],
        "request_digest": sha256(b"vendor-042-create-v1").hexdigest(),
        "execution_id": "exec-vendor-042", "provider": {"adapter": "sandbox-sqlite/1", "operation": "vendor.create", "resource_ref": "vendor://acme/vendor-042"},
        "disposition": "EXECUTED", "observed_at": ISSUED,
        "provider_receipt_digest": sha256(b"vendor://acme/vendor-042").hexdigest(),
    })
    attestation = make_envelope("continuity_attestation", "urn:continuum:attestation:acme:vendor-042", "urn:continuum:principal:acme:independent-verifier", ISSUED, {
        "tenant_id": "acme", "obligation": artifact_ref(obligation), "succession_manifest": artifact_ref(manifest),
        "revocation_proofs": [artifact_ref(revocation)], "execution_receipts": [artifact_ref(receipt)],
        "policy_decision": DECISION,
        "verification": {"verifier_principal": "urn:continuum:principal:acme:independent-verifier",
                         "independent_of_executor": True,
                         "criteria_results": [{"criterion_id": "vendor-created", "passed": result["vendor_count"] == 1}],
                         "provider_observation_refs": ["vendor://acme/vendor-042"], "verified_at": ISSUED},
        "guarantees": {"obligation_preserved": result["obligation_status"] == "DISCHARGED",
                       "authority_overlap": "NONE", "unauthorized_context_transferred": False,
                       "externally_observed_effect_count": result["vendor_count"], "evidence_chain_complete": True},
        "outcome": "VERIFIED",
    })
    bundle = {"profile": "reference-local", "protocol": "continuum/0.1-draft",
              "artifacts": [obligation, grant, manifest, revocation, receipt, attestation]}
    verify_bundle(bundle)
    return bundle


def verify_bundle(bundle: dict[str, Any]) -> None:
    artifacts = bundle.get("artifacts", [])
    if len(artifacts) != 6 or {a["artifact_type"] for a in artifacts} != {
        "obligation", "authority_grant", "succession_manifest", "revocation_proof", "execution_receipt", "continuity_attestation"}:
        raise ContractError("BUNDLE_ARTIFACT_SET_INCOMPLETE")
    index = {}
    for artifact in artifacts:
        validate_envelope(artifact)
        index[artifact["artifact_id"]] = artifact
    attestation = next(a for a in artifacts if a["artifact_type"] == "continuity_attestation")
    refs = [attestation["body"]["obligation"], attestation["body"]["succession_manifest"],
            *attestation["body"]["revocation_proofs"], *attestation["body"]["execution_receipts"]]
    for ref in refs:
        target = index.get(ref["artifact_id"])
        if not target or target["digest"] != ref["digest"]:
            raise ContractError("BROKEN_ARTIFACT_REFERENCE")
    if attestation["body"]["verification"]["verifier_principal"] == next(
        a for a in artifacts if a["artifact_type"] == "execution_receipt")["body"]["executing_principal"]:
        raise ContractError("EXECUTOR_SELF_ATTESTATION")


def mutate_copy(bundle: dict[str, Any], artifact_type: str, body_key: str, value: Any) -> dict[str, Any]:
    changed = deepcopy(bundle)
    artifact = next(a for a in changed["artifacts"] if a["artifact_type"] == artifact_type)
    artifact["body"][body_key] = value
    return changed


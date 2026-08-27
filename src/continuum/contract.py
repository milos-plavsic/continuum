"""Continuity Contract Profile 0.1-draft portable artifacts.

Every digest and signature uses the repository-wide RFC 8785 boundary.  Wire
schemas—not a competing serializer—decide which values a particular artifact
may contain.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from typing import Any, Callable
from urllib.parse import urlparse

from .canonicalization import CanonicalizationError, canonical_json_bytes

PROTOCOL = "continuum/0.1-draft"
MEDIA_TYPE = "application/vnd.continuum.contract+json"
DOMAIN = b"continuum-contract\x00continuum/0.1-draft\x00"
ARTIFACT_TYPES = {"obligation", "authority_grant", "succession_manifest",
                  "revocation_proof", "execution_receipt", "continuity_attestation"}


class ContractError(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    """Compatibility API backed exclusively by RFC 8785."""
    try:
        return canonical_json_bytes(value)
    except CanonicalizationError as error:
        raise ContractError(f"CANONICALIZATION_FAILED:{error}") from error


def artifact_digest(envelope: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in envelope.items() if key not in {"digest", "signatures"}}
    return sha256(DOMAIN + canonical_bytes(unsigned)).hexdigest()


def _require_uri(value: str, name: str) -> None:
    if not value or not urlparse(value).scheme:
        raise ContractError(f"INVALID_URI:{name}")


def _require_utc(value: str, name: str) -> None:
    if not value.endswith("Z"):
        raise ContractError(f"UTC_Z_REQUIRED:{name}")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ContractError(f"INVALID_TIMESTAMP:{name}") from error


def make_envelope(artifact_type: str, artifact_id: str, issuer: str,
                  issued_at: str, body: dict[str, Any], *,
                  required_features: list[str] | None = None,
                  extensions: dict[str, Any] | None = None) -> dict[str, Any]:
    if artifact_type not in ARTIFACT_TYPES:
        raise ContractError("UNKNOWN_ARTIFACT_TYPE")
    _require_uri(artifact_id, "artifact_id"); _require_uri(issuer, "issuer"); _require_utc(issued_at, "issued_at")
    envelope: dict[str, Any] = {
        "protocol": PROTOCOL, "artifact_type": artifact_type,
        "schema": f"https://continuum.dev/schema/0.1/{artifact_type}.json",
        "artifact_id": artifact_id, "issued_at": issued_at, "issuer": issuer,
        "body": body, "required_features": sorted(set(required_features or [])),
        "extensions": extensions or {}, "signatures": [],
    }
    envelope["digest"] = {"alg": "sha-256", "value": artifact_digest(envelope)}
    validate_envelope(envelope)
    return envelope


def validate_envelope(envelope: dict[str, Any], supported_features: set[str] | None = None) -> None:
    required = {"protocol", "artifact_type", "schema", "artifact_id", "issued_at", "issuer",
                "body", "required_features", "extensions", "digest", "signatures"}
    if set(envelope) != required:
        raise ContractError("ENVELOPE_FIELDS_INVALID")
    if envelope["protocol"] != PROTOCOL:
        raise ContractError("UNSUPPORTED_PROTOCOL")
    if envelope["artifact_type"] not in ARTIFACT_TYPES:
        raise ContractError("UNKNOWN_ARTIFACT_TYPE")
    _require_uri(envelope["artifact_id"], "artifact_id"); _require_uri(envelope["issuer"], "issuer"); _require_utc(envelope["issued_at"], "issued_at")
    features = envelope["required_features"]
    if features != sorted(set(features)):
        raise ContractError("REQUIRED_FEATURES_NOT_CANONICAL")
    if set(features) - (supported_features or set()):
        raise ContractError("UNSUPPORTED_REQUIRED_FEATURE")
    if envelope["digest"] != {"alg": "sha-256", "value": artifact_digest(envelope)}:
        raise ContractError("DIGEST_MISMATCH")
    validate_body(envelope["artifact_type"], envelope["body"])


def artifact_ref(envelope: dict[str, Any]) -> dict[str, Any]:
    validate_envelope(envelope)
    return {"artifact_id": envelope["artifact_id"], "artifact_type": envelope["artifact_type"],
            "digest": deepcopy(envelope["digest"])}


def _fields(body: dict[str, Any], required: set[str], optional: set[str] = frozenset()) -> None:
    if required - set(body):
        raise ContractError("MISSING_BODY_FIELDS:" + ",".join(sorted(required - set(body))))
    if set(body) - required - optional:
        raise ContractError("UNKNOWN_BODY_FIELDS:" + ",".join(sorted(set(body) - required - optional)))


def validate_body(kind: str, body: dict[str, Any]) -> None:
    if kind == "obligation":
        _fields(body, {"tenant_id", "subject", "revision", "owner", "description", "deadline", "completion_criteria", "allowed_effects", "compensation", "status"}, {"predecessor_revision_digest"})
        if body["revision"] < 1: raise ContractError("INVALID_REVISION")
        _require_utc(body["deadline"], "deadline")
    elif kind == "authority_grant":
        _fields(body, {"tenant_id", "grant_id", "subject_principal", "authority_domain", "epoch", "obligation_ids", "capabilities", "memory_scopes", "purpose", "not_before", "expires_at", "policy_decision", "status"}, {"constraints"})
        _require_utc(body["not_before"], "not_before"); _require_utc(body["expires_at"], "expires_at")
        if body["status"] not in {"ACTIVE", "REVOKED", "EXPIRED"}: raise ContractError("INVALID_GRANT_STATUS")
    elif kind == "succession_manifest":
        _fields(body, {"succession_id", "tenant_id", "authority_domain", "predecessor", "successor", "obligations", "included_grants", "excluded_context", "in_flight_effects", "evidence_refs", "policy_decision", "created_from_registry_revision", "state"})
        if body["successor"]["epoch"] <= body["predecessor"]["epoch"]: raise ContractError("NON_MONOTONIC_EPOCH")
    elif kind == "revocation_proof":
        _fields(body, {"tenant_id", "authority_domain", "revoked_principal", "revoked_through_epoch", "registry_revision", "effective_at", "revoked_grant_ids", "enforcement_points", "policy_decision", "status"})
        kinds = {point["kind"] for point in body["enforcement_points"]}
        if body["status"] == "ENFORCED" and not {"ACTION", "MEMORY"}.issubset(kinds): raise ContractError("REVOCATION_PROOF_INCOMPLETE")
    elif kind == "execution_receipt":
        _fields(body, {"tenant_id", "obligation", "executing_principal", "authority_domain", "epoch", "decision", "idempotency_key", "request_digest", "execution_id", "provider", "disposition", "observed_at"}, {"prior_receipt", "provider_receipt_digest", "error_reason"})
        _require_utc(body["observed_at"], "observed_at")
    elif kind == "continuity_attestation":
        _fields(body, {"tenant_id", "obligation", "succession_manifest", "revocation_proofs", "execution_receipts", "policy_decision", "verification", "guarantees", "outcome"})
        verification, guarantees = body["verification"], body["guarantees"]
        if body["outcome"] == "VERIFIED":
            if not verification.get("independent_of_executor"): raise ContractError("EXECUTOR_SELF_ATTESTATION")
            if not guarantees.get("obligation_preserved") or not guarantees.get("evidence_chain_complete") or guarantees.get("authority_overlap") != "NONE" or guarantees.get("unauthorized_context_transferred"):
                raise ContractError("VERIFIED_GUARANTEES_INVALID")
    else:
        raise ContractError("UNKNOWN_ARTIFACT_TYPE")


def authorize_grant(grant: dict[str, Any], *, now: str, tenant_id: str,
                    principal: str, authority_domain: str, epoch: int,
                    obligation_id: str, capability: str, memory_scope: str,
                    purpose: str) -> None:
    validate_envelope(grant)
    if grant["artifact_type"] != "authority_grant": raise ContractError("NOT_AUTHORITY_GRANT")
    body = grant["body"]
    if body["tenant_id"] != tenant_id: raise ContractError("RESOURCE_NOT_FOUND")
    if body["status"] != "ACTIVE": raise ContractError("GRANT_NOT_ACTIVE")
    if body["subject_principal"] != principal or body["authority_domain"] != authority_domain or body["epoch"] != epoch:
        raise ContractError("AUTHORITY_BINDING_MISMATCH")
    if not (body["not_before"] <= now < body["expires_at"]): raise ContractError("GRANT_EXPIRED_OR_NOT_YET_VALID")
    if obligation_id not in body["obligation_ids"] or capability not in body["capabilities"] or memory_scope not in body["memory_scopes"] or purpose != body["purpose"]:
        raise ContractError("GRANT_SCOPE_MISMATCH")


def sign_ed25519(envelope: dict[str, Any], private_key: Any, key_id: str, signed_at: str) -> dict[str, Any]:
    """Add a content-binding signature; signer trust and truth remain external."""
    validate_envelope(envelope); _require_uri(key_id, "key_id"); _require_utc(signed_at, "signed_at")
    signed = deepcopy(envelope)
    raw = private_key.sign(bytes.fromhex(envelope["digest"]["value"]))
    signed["signatures"].append({"alg": "Ed25519", "key_id": key_id, "signed_at": signed_at,
                                  "value": base64.urlsafe_b64encode(raw).decode().rstrip("=")})
    return signed


def verify_ed25519(envelope: dict[str, Any], key_resolver: Callable[[str], Any]) -> None:
    validate_envelope(envelope)
    for signature in envelope["signatures"]:
        if signature["alg"] != "Ed25519": raise ContractError("UNSUPPORTED_SIGNATURE_ALGORITHM")
        padding = "=" * (-len(signature["value"]) % 4)
        try:
            key_resolver(signature["key_id"]).verify(base64.urlsafe_b64decode(signature["value"] + padding), bytes.fromhex(envelope["digest"]["value"]))
        except Exception as error:
            raise ContractError("SIGNATURE_INVALID") from error

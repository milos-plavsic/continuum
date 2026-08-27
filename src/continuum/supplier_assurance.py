"""Supplier-assurance domain workflow protected by the Continuity Contract.

The external registry clients are read-only tools. Gemini may explain and
organize their evidence, but deterministic admission alone can authorize the
sandbox onboarding request consumed by the action gateway.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Callable
from urllib.request import Request, urlopen

from .contract import canonical_bytes


GLEIF_RECORD_URL = "https://api.gleif.org/api/v1/lei-records/{lei}"
VIES_CHECK_URL = "https://ec.europa.eu/taxation_customs/vies/rest-api/check-vat-number"
_LEI = re.compile(r"^[0-9A-Z]{20}$")
_COUNTRY = re.compile(r"^[A-Z]{2}$")
_VAT = re.compile(r"^[0-9A-Z]{2,14}$")


class SupplierAssuranceDenied(ValueError):
    """The supplied evidence cannot authorize onboarding."""


def canonical_supplier_application() -> dict[str, Any]:
    """Return the server-owned sandbox application used by the live demo.

    Siemens AG's identity and VAT number are checked against public sources;
    the application itself is explicitly synthetic and cannot represent a real
    procurement decision or relationship.
    """
    documents = [
        {
            "document_id": "supplier-declaration-v1",
            "document_type": "supplier_declaration",
            "classification": "SYNTHETIC_SANDBOX",
            "content": (
                "The supplier accepts the anti-bribery, information-security, "
                "data-processing, and bank-change callback controls for this "
                "sandbox onboarding evaluation."
            ),
        },
        {
            "document_id": "procurement-scope-v1",
            "document_type": "procurement_scope",
            "classification": "SYNTHETIC_SANDBOX",
            "content": (
                "Evaluate legal identity and EU VAT status for a EUR 250000 "
                "industrial-components sandbox engagement. Do not create a real "
                "commercial relationship or send a message to the entity."
            ),
        },
    ]
    return {
        "schema": "continuum/supplier-application/1",
        "application_id": "supplier-assurance-042",
        "vendor_id": "vendor-042",
        "legal_name": "Siemens Aktiengesellschaft",
        "lei": "W38RGI023J3WT1HWRP32",
        "country_code": "DE",
        "vat_number": "129274202",
        "contract_value": {"currency": "EUR", "amount": 250000},
        "requested_action": "vendor.create",
        "decision_scope": "SANDBOX_ONLY",
        "required_controls": [
            "anti_bribery", "information_security", "data_processing",
            "bank_change_callback",
        ],
        "documents": documents,
        "disclosure": (
            "Hackathon sandbox application using public registry identifiers; "
            "not a real supplier decision or claimed commercial relationship."
        ),
    }


def application_digest(application: dict[str, Any]) -> str:
    return sha256(canonical_bytes(application)).hexdigest()


def _read_json(request: Request, opener: Callable[..., Any]) -> dict[str, Any]:
    with opener(request, timeout=20) as response:
        payload = json.loads(response.read())
    if not isinstance(payload, dict):
        raise ValueError("EXTERNAL_TOOL_RESPONSE_INVALID")
    return payload


def lookup_gleif(lei: str, *, opener: Callable[..., Any] = urlopen) -> dict[str, Any]:
    """Read and normalize one exact LEI record from GLEIF's public API."""
    if not isinstance(lei, str) or not _LEI.fullmatch(lei):
        raise ValueError("LEI_INVALID")
    url = GLEIF_RECORD_URL.format(lei=lei)
    payload = _read_json(Request(url, headers={"Accept": "application/vnd.api+json"}), opener)
    try:
        data = payload["data"]
        attributes = data["attributes"]
        entity = attributes["entity"]
        registration = attributes["registration"]
        normalized = {
            "tool": "gleif.lei-records.read",
            "source_url": url,
            "lei": str(data["id"]),
            "legal_name": str(entity["legalName"]["name"]),
            "country_code": str(entity["legalAddress"]["country"]),
            "entity_status": str(entity["status"]),
            "registration_status": str(registration["status"]),
            "next_renewal_at": str(registration.get("nextRenewalDate") or ""),
        }
    except (KeyError, TypeError) as error:
        raise ValueError("GLEIF_RESPONSE_INVALID") from error
    if normalized["lei"] != lei:
        raise ValueError("GLEIF_IDENTITY_SUBSTITUTION")
    return _with_receipt(normalized)


def check_eu_vat(country_code: str, vat_number: str, *,
                 opener: Callable[..., Any] = urlopen) -> dict[str, Any]:
    """Check one VAT number using the European Commission VIES REST service."""
    if (not isinstance(country_code, str) or not _COUNTRY.fullmatch(country_code)
            or not isinstance(vat_number, str) or not _VAT.fullmatch(vat_number)):
        raise ValueError("VAT_IDENTIFIER_INVALID")
    body = canonical_bytes({"countryCode": country_code, "vatNumber": vat_number})
    request = Request(VIES_CHECK_URL, data=body, method="POST", headers={
        "Accept": "application/json", "Content-Type": "application/json",
    })
    payload = _read_json(request, opener)
    if not isinstance(payload.get("valid"), bool):
        raise ValueError("VIES_RESPONSE_INVALID")
    normalized = {
        "tool": "ec.vies.check-vat-number",
        "source_url": VIES_CHECK_URL,
        "country_code": country_code,
        "vat_number": vat_number,
        "valid": payload["valid"],
        "request_date": str(payload.get("requestDate") or ""),
        "name": str(payload.get("name") or ""),
        "address": str(payload.get("address") or ""),
        "user_error": payload.get("userError"),
    }
    return _with_receipt(normalized)


def _with_receipt(value: dict[str, Any]) -> dict[str, Any]:
    digest = sha256(canonical_bytes(value)).hexdigest()
    return {**value, "evidence_ref": f"sha256:{digest}"}


def model_supplier_view(application: dict[str, Any], gleif: dict[str, Any],
                        vies: dict[str, Any]) -> dict[str, Any]:
    """Expose only purpose-bound inputs and normalized tool observations."""
    return {
        "application": application,
        "application_evidence_ref": f"sha256:{application_digest(application)}",
        "external_tool_observations": [gleif, vies],
        "task": (
            "Assess this sandbox supplier application, cite every supplied evidence "
            "reference, identify missing controls, and recommend ONBOARD or HOLD."
        ),
    }


def validate_model_assessment(result: dict[str, Any]) -> dict[str, Any]:
    required = {
        "recommendation", "legal_identity_match", "country_match",
        "vat_valid", "controls_satisfied", "missing_requirements",
        "risk_summary", "evidence_refs", "proposed_action",
    }
    if (not isinstance(result, dict) or set(result) != required
            or result.get("recommendation") not in {"ONBOARD", "HOLD"}
            or result.get("proposed_action") not in {"vendor.create", "none"}
            or any(not isinstance(result.get(key), bool)
                   for key in ("legal_identity_match", "country_match", "vat_valid"))
            or not isinstance(result.get("controls_satisfied"), list)
            or not isinstance(result.get("missing_requirements"), list)
            or not isinstance(result.get("evidence_refs"), list)
            or not isinstance(result.get("risk_summary"), str)):
        raise ValueError("SUPPLIER_MODEL_RESULT_INVALID")
    return result


def admit_supplier_assessment(*, application: dict[str, Any], gleif: dict[str, Any],
                              vies: dict[str, Any], model_result: dict[str, Any],
                              actor: str) -> dict[str, Any]:
    """Deterministically admit a model-authored decision pack."""
    assessment = validate_model_assessment(model_result)
    expected_refs = {
        f"sha256:{application_digest(application)}",
        str(gleif.get("evidence_ref", "")), str(vies.get("evidence_ref", "")),
    }
    actual_refs = assessment["evidence_refs"]
    controls = set(application.get("required_controls", []))
    legal_match = _normalized_name(application.get("legal_name")) == _normalized_name(gleif.get("legal_name"))
    country_match = application.get("country_code") == gleif.get("country_code")
    external_ok = (
        gleif.get("lei") == application.get("lei")
        and gleif.get("entity_status") == "ACTIVE"
        and gleif.get("registration_status") in {"ISSUED", "LAPSED"}
        and vies.get("country_code") == application.get("country_code")
        and vies.get("vat_number") == application.get("vat_number")
        and vies.get("valid") is True
    )
    model_consistent = (
        assessment["recommendation"] == "ONBOARD"
        and assessment["proposed_action"] == "vendor.create"
        and assessment["legal_identity_match"] is legal_match
        and assessment["country_match"] is country_match
        and assessment["vat_valid"] is True
        and set(assessment["controls_satisfied"]) == controls
        and assessment["missing_requirements"] == []
        and len(actual_refs) == len(set(actual_refs))
        and set(actual_refs) == expected_refs
    )
    if (application.get("decision_scope") != "SANDBOX_ONLY" or not legal_match
            or not country_match or not external_ok or not model_consistent):
        raise SupplierAssuranceDenied("SUPPLIER_ASSURANCE_HOLD")
    decision_material = {
        "application_id": application["application_id"],
        "vendor_id": application["vendor_id"],
        "decision_scope": application["decision_scope"],
        "recommendation": assessment["recommendation"],
        "proposed_action": assessment["proposed_action"],
        "evidence_refs": actual_refs,
        "controls_satisfied": assessment["controls_satisfied"],
        "actor": actor,
    }
    decision_pack_digest = sha256(canonical_bytes(decision_material)).hexdigest()
    evidence_id = sha256(canonical_bytes({
        "application": application_digest(application),
        "decision_pack": decision_pack_digest,
    })).hexdigest()
    return {
        "workflow": "SUPPLIER_ASSURANCE_AGENT",
        "status": "VERIFIED",
        "recommendation": "ONBOARD",
        "decision_scope": "SANDBOX_ONLY",
        "evidence_id": evidence_id,
        "document_hash": application_digest(application),
        "decision_pack_digest": decision_pack_digest,
        "actor": actor,
        "application_id": application["application_id"],
        "vendor_id": application["vendor_id"],
        "legal_name": application["legal_name"],
        "tool_observations": [gleif, vies],
        "model_assessment": assessment,
    }


def _normalized_name(value: Any) -> str:
    return "".join(character for character in str(value).casefold() if character.isalnum())

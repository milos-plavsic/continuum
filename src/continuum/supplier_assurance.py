"""Supplier-assurance domain workflow protected by the Continuity Contract.

The external registry clients are read-only tools. Gemini may explain and
organize their evidence, but deterministic admission alone can authorize the
sandbox onboarding request consumed by the action gateway.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from http.client import IncompleteRead
import json
import re
from time import monotonic, sleep
from typing import Any, Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .contract import canonical_bytes


GLEIF_RECORD_URL = "https://api.gleif.org/api/v1/lei-records/{lei}"
VIES_CHECK_URL = "https://ec.europa.eu/taxation_customs/vies/rest-api/check-vat-number"
_LEI = re.compile(r"^[0-9A-Z]{20}$")
_COUNTRY = re.compile(r"^[A-Z]{2}$")
_VAT = re.compile(r"^[0-9A-Z]{2,14}$")


class SupplierAssuranceDenied(ValueError):
    """The supplied evidence cannot authorize onboarding."""


class ExternalToolError(RuntimeError):
    """Stable fail-closed error from an official external evidence source."""

    def __init__(self, code: str, *, retryable: bool) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class ExternalToolPolicy:
    """Bound both latency and retries for one read-only official API call."""

    per_attempt_timeout_seconds: float = 5.0
    total_budget_seconds: float = 12.0
    backoff_seconds: tuple[float, ...] = (0.0, 0.25, 0.75)
    evidence_ttl_seconds: int = 86_400

    def __post_init__(self) -> None:
        if (self.per_attempt_timeout_seconds <= 0 or self.total_budget_seconds <= 0
                or not self.backoff_seconds or any(value < 0 for value in self.backoff_seconds)
                or self.evidence_ttl_seconds <= 0):
            raise ValueError("EXTERNAL_TOOL_POLICY_INVALID")


class EvidenceCache(Protocol):
    """Durable port for last-known-good, content-addressed tool observations."""

    def get(self, key: str) -> dict[str, Any] | None: ...
    def put(self, key: str, observation: dict[str, Any]) -> None: ...


class InMemoryEvidenceCache:
    """Deterministic local cache used by conformance and fault tests."""

    def __init__(self) -> None:
        self._values: dict[str, dict[str, Any]] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        value = self._values.get(key)
        return json.loads(json.dumps(value)) if value is not None else None

    def put(self, key: str, observation: dict[str, Any]) -> None:
        self._values[key] = json.loads(json.dumps(observation))


class FirestoreEvidenceCache:
    """Small Firestore adapter; official evidence remains independently rechecked."""

    def __init__(self, client: Any, collection: str = "continuity_external_evidence") -> None:
        self.client, self.collection = client, collection

    def _document(self, key: str) -> Any:
        identifier = sha256(key.encode("utf-8")).hexdigest()
        return self.client.collection(self.collection).document(identifier)

    def get(self, key: str) -> dict[str, Any] | None:
        snapshot = self._document(key).get()
        if not snapshot.exists:
            return None
        record = snapshot.to_dict()
        if not isinstance(record, dict) or record.get("cache_key") != key:
            raise ExternalToolError("EXTERNAL_EVIDENCE_CACHE_CORRUPT", retryable=False)
        observation = record.get("observation")
        if not isinstance(observation, dict):
            raise ExternalToolError("EXTERNAL_EVIDENCE_CACHE_CORRUPT", retryable=False)
        return observation

    def put(self, key: str, observation: dict[str, Any]) -> None:
        self._document(key).set({"cache_key": key, "observation": observation})


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


def _read_json(request: Request, opener: Callable[..., Any], *, source: str,
               policy: ExternalToolPolicy = ExternalToolPolicy(),
               sleeper: Callable[[float], None] = sleep,
               clock: Callable[[], float] = monotonic,
               response_error: Callable[[dict[str, Any]], ExternalToolError | None]
               | None = None) -> dict[str, Any]:
    """Fetch JSON with a fixed retry schedule and total wall-clock budget."""
    started = clock()
    attempts = len(policy.backoff_seconds)
    attempt = 0
    while True:
        remaining = policy.total_budget_seconds - (clock() - started)
        if remaining <= 0:
            raise ExternalToolError(f"{source}_TIME_BUDGET_EXHAUSTED", retryable=False)
        timeout = min(policy.per_attempt_timeout_seconds, remaining)
        error: ExternalToolError | None = None
        try:
            with opener(request, timeout=timeout) as response:
                status = getattr(response, "status", 200)
                if isinstance(status, int) and status >= 400:
                    retryable = status == 429 or 500 <= status <= 599
                    error = ExternalToolError(
                        f"{source}_HTTP_{status}", retryable=retryable)
                else:
                    try:
                        payload = json.loads(response.read())
                    except (json.JSONDecodeError, UnicodeDecodeError, IncompleteRead,
                            TypeError) as malformed:
                        raise ExternalToolError(
                            f"{source}_RESPONSE_INVALID", retryable=False) from malformed
                    if not isinstance(payload, dict):
                        raise ExternalToolError(
                            f"{source}_RESPONSE_INVALID", retryable=False)
                    error = response_error(payload) if response_error is not None else None
                    if error is None:
                        return payload
        except HTTPError as failure:
            status = int(failure.code)
            error = ExternalToolError(
                f"{source}_HTTP_{status}", retryable=status == 429 or 500 <= status <= 599)
        except (TimeoutError, URLError, OSError) as failure:
            timed_out = isinstance(failure, TimeoutError) or "timed out" in str(failure).lower()
            error = ExternalToolError(
                f"{source}_{'TIMEOUT' if timed_out else 'UNAVAILABLE'}", retryable=True)
        assert error is not None
        final_attempt = attempt + 1 == attempts
        if not error.retryable or final_attempt:
            raise error
        delay = policy.backoff_seconds[attempt + 1]
        if clock() - started + delay >= policy.total_budget_seconds:
            raise ExternalToolError(f"{source}_TIME_BUDGET_EXHAUSTED", retryable=False)
        sleeper(delay)
        attempt += 1


def lookup_gleif(lei: str, *, opener: Callable[..., Any] = urlopen,
                 policy: ExternalToolPolicy = ExternalToolPolicy(),
                 sleeper: Callable[[float], None] = sleep,
                 clock: Callable[[], float] = monotonic) -> dict[str, Any]:
    """Read and normalize one exact LEI record from GLEIF's public API."""
    if not isinstance(lei, str) or not _LEI.fullmatch(lei):
        raise ValueError("LEI_INVALID")
    url = GLEIF_RECORD_URL.format(lei=lei)
    payload = _read_json(Request(url, headers={"Accept": "application/vnd.api+json"}),
                         opener, source="GLEIF", policy=policy, sleeper=sleeper, clock=clock)
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
        raise ExternalToolError("GLEIF_RESPONSE_INVALID", retryable=False) from error
    if normalized["lei"] != lei:
        raise ExternalToolError("GLEIF_IDENTITY_SUBSTITUTION", retryable=False)
    return _with_receipt(normalized)


def check_eu_vat(country_code: str, vat_number: str, *,
                 opener: Callable[..., Any] = urlopen,
                 policy: ExternalToolPolicy = ExternalToolPolicy(),
                 sleeper: Callable[[float], None] = sleep,
                 clock: Callable[[], float] = monotonic) -> dict[str, Any]:
    """Check one VAT number using the European Commission VIES REST service."""
    if (not isinstance(country_code, str) or not _COUNTRY.fullmatch(country_code)
            or not isinstance(vat_number, str) or not _VAT.fullmatch(vat_number)):
        raise ValueError("VAT_IDENTIFIER_INVALID")
    body = canonical_bytes({"countryCode": country_code, "vatNumber": vat_number})
    request = Request(VIES_CHECK_URL, data=body, method="POST", headers={
        "Accept": "application/json", "Content-Type": "application/json",
    })
    def semantic_error(payload: dict[str, Any]) -> ExternalToolError | None:
        if payload.get("actionSucceed") is not False:
            return None
        wrappers = payload.get("errorWrappers")
        codes = [item.get("error") for item in wrappers
                 if isinstance(item, dict)] if isinstance(wrappers, list) else []
        code = next((item for item in codes if isinstance(item, str) and item),
                    "UPSTREAM_REJECTED")
        retryable = code in {"MS_UNAVAILABLE", "TIMEOUT", "SERVER_BUSY"}
        return ExternalToolError(f"VIES_UPSTREAM_{code}", retryable=retryable)

    payload = _read_json(request, opener, source="VIES", policy=policy,
                         sleeper=sleeper, clock=clock, response_error=semantic_error)
    if not isinstance(payload.get("valid"), bool):
        raise ExternalToolError("VIES_RESPONSE_INVALID", retryable=False)
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


def resolve_tool_observation(*, cache_key: str, fetch: Callable[[], dict[str, Any]],
                             cache: EvidenceCache | None,
                             now: datetime,
                             policy: ExternalToolPolicy = ExternalToolPolicy()) -> dict[str, Any]:
    """Return live evidence or an explicitly derived, still-fresh cached receipt."""
    if now.tzinfo is None:
        raise ValueError("EXTERNAL_EVIDENCE_TIME_INVALID")
    observed_at = now.astimezone(timezone.utc)
    try:
        raw = fetch()
    except ExternalToolError as failure:
        if cache is None:
            raise
        cached = cache.get(cache_key)
        if cached is None:
            raise
        return _admit_cached_observation(cached, cache_key=cache_key,
                                         now=observed_at, failure=failure)
    base = {key: value for key, value in raw.items() if key != "evidence_ref"}
    live = _with_receipt({
        **base,
        "availability_mode": "LIVE",
        "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
        "freshness_expires_at": (
            observed_at + timedelta(seconds=policy.evidence_ttl_seconds)
        ).isoformat().replace("+00:00", "Z"),
    })
    if cache is not None:
        cache.put(cache_key, live)
    return live


def _admit_cached_observation(cached: dict[str, Any], *, cache_key: str,
                              now: datetime, failure: ExternalToolError) -> dict[str, Any]:
    try:
        evidence_ref = cached["evidence_ref"]
        unsigned = {key: value for key, value in cached.items() if key != "evidence_ref"}
        expiry = datetime.fromisoformat(str(cached["freshness_expires_at"]).replace("Z", "+00:00"))
        observed = datetime.fromisoformat(str(cached["observed_at"]).replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError) as error:
        raise ExternalToolError("EXTERNAL_EVIDENCE_CACHE_CORRUPT", retryable=False) from error
    expected_ref = _with_receipt(unsigned)["evidence_ref"]
    if (cached.get("availability_mode") != "LIVE" or evidence_ref != expected_ref
            or observed.tzinfo is None or expiry.tzinfo is None or expiry <= observed):
        raise ExternalToolError("EXTERNAL_EVIDENCE_CACHE_CORRUPT", retryable=False)
    if not _observation_matches_cache_key(cached, cache_key):
        raise ExternalToolError("EXTERNAL_EVIDENCE_CACHE_SUBSTITUTED", retryable=False)
    if now >= expiry:
        raise ExternalToolError("EXTERNAL_EVIDENCE_CACHE_STALE", retryable=False)
    derived = {
        **{key: value for key, value in unsigned.items()
           if key not in {"availability_mode", "freshness_expires_at"}},
        "availability_mode": "CACHED_WITHIN_POLICY",
        "freshness_expires_at": expiry.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "cached_from_evidence_ref": evidence_ref,
        "live_error_code": failure.code,
        "cache_key_digest": sha256(cache_key.encode("utf-8")).hexdigest(),
    }
    return _with_receipt(derived)


def _observation_matches_cache_key(observation: dict[str, Any], cache_key: str) -> bool:
    """Prevent a valid observation from being replayed under another cache key."""
    if cache_key.startswith("gleif:"):
        return (observation.get("tool") == "gleif.lei-records.read"
                and observation.get("lei") == cache_key.removeprefix("gleif:"))
    if cache_key.startswith("vies:"):
        parts = cache_key.split(":", 2)
        return (len(parts) == 3
                and observation.get("tool") == "ec.vies.check-vat-number"
                and observation.get("country_code") == parts[1]
                and observation.get("vat_number") == parts[2])
    return False


def supplier_evidence_cache_keys(application: dict[str, Any]) -> tuple[str, str]:
    return (f"gleif:{application.get('lei', '')}",
            f"vies:{application.get('country_code', '')}:{application.get('vat_number', '')}")


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
        and _availability_receipt_valid(gleif)
        and _availability_receipt_valid(vies)
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


def _availability_receipt_valid(observation: dict[str, Any]) -> bool:
    mode = observation.get("availability_mode")
    try:
        observed = datetime.fromisoformat(
            str(observation["observed_at"]).replace("Z", "+00:00"))
        expiry = datetime.fromisoformat(
            str(observation["freshness_expires_at"]).replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError):
        return False
    if observed.tzinfo is None or expiry.tzinfo is None or expiry <= observed:
        return False
    if mode == "LIVE":
        return "cached_from_evidence_ref" not in observation
    return (mode == "CACHED_WITHIN_POLICY"
            and isinstance(observation.get("cached_from_evidence_ref"), str)
            and str(observation["cached_from_evidence_ref"]).startswith("sha256:")
            and isinstance(observation.get("live_error_code"), str))

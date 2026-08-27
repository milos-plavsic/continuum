"""Strict reader for the public assurance trust profile."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import digest


REQUIRED_NOT_ASSESSED = {
    "capture-provenance-by-offline-verifier",
    "upstream-factual-truth",
    "absence-of-cloud-control-plane-compromise",
    "absence-of-model-compromise",
    "byzantine-consensus",
    "universal-exactly-once-execution",
}


def validate_trust_profile(value: Any) -> dict[str, Any]:
    if (not isinstance(value, dict) or set(value) != {
            "schema", "profile_id", "trust_roots", "assessed_claims", "not_assessed"}
            or value.get("schema") != "continuum/trust-profile/1"
            or not isinstance(value.get("profile_id"), str) or not value["profile_id"]):
        raise ValueError("TRUST_PROFILE_SCHEMA_INVALID")
    roots = value.get("trust_roots")
    if not isinstance(roots, list) or not roots:
        raise ValueError("TRUST_PROFILE_ROOTS_INVALID")
    root_ids: list[str] = []
    for root in roots:
        if (not isinstance(root, dict) or set(root) != {
                "id", "role", "assumption", "compromise_impact"}
                or any(not isinstance(root.get(key), str) or not root[key].strip()
                       for key in ("id", "role", "assumption", "compromise_impact"))):
            raise ValueError("TRUST_PROFILE_ROOTS_INVALID")
        root_ids.append(root["id"])
    if len(root_ids) != len(set(root_ids)):
        raise ValueError("TRUST_PROFILE_ROOTS_DUPLICATE")
    for field in ("assessed_claims", "not_assessed"):
        entries = value.get(field)
        if (not isinstance(entries, list) or not entries
                or any(not isinstance(item, str) or not item for item in entries)
                or len(entries) != len(set(entries))):
            raise ValueError("TRUST_PROFILE_CLAIMS_INVALID")
    if not REQUIRED_NOT_ASSESSED.issubset(value["not_assessed"]):
        raise ValueError("TRUST_PROFILE_CEILING_INCOMPLETE")
    return {**value, "profile_digest": digest(value)}


def load_trust_profile(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("TRUST_PROFILE_UNREADABLE") from error
    return validate_trust_profile(value)

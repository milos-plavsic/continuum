"""One canonical JSON boundary for every digest and signature in Continuum.

RFC 8785 (JCS) supplies the cross-language wire representation.  Callers may
apply a domain separator before hashing, but must never introduce another JSON
serializer for security-relevant bytes.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any

import rfc8785


PROFILE = "urn:ietf:rfc:8785"


class CanonicalizationError(ValueError):
    """The value is outside the RFC 8785/I-JSON domain."""


def canonical_json_bytes(value: Any) -> bytes:
    """Return the RFC 8785 representation or fail closed."""
    try:
        return rfc8785.dumps(value)
    except (rfc8785.CanonicalizationError, TypeError, ValueError) as error:
        raise CanonicalizationError(str(error)) from error


def canonical_json_text(value: Any) -> str:
    return canonical_json_bytes(value).decode("utf-8")


def canonical_sha256(value: Any, *, domain: bytes = b"") -> str:
    return sha256(domain + canonical_json_bytes(value)).hexdigest()

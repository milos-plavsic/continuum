"""Identity-pinned external review statements; signatures are verified by Sigstore."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Callable, Mapping

from .contract import canonical_bytes

STATEMENT_KEYS = frozenset({
    "schema", "statement_id", "request_digest", "reviewer", "reviewed_at",
    "expires_at", "verdict", "claim_results", "findings", "statement_digest",
})
REVIEWER_KEYS = frozenset({
    "identity", "issuer", "display_name", "affiliation", "relationship",
    "conflicts", "independence_declared",
})
CLAIM_KEYS = frozenset({"claim", "status", "evidence_refs", "finding"})


def content_digest(value: Mapping[str, object], *, omitted: str) -> str:
    """Return a domain-neutral SHA-256 identifier over strict canonical JSON."""
    import hashlib
    payload = {key: item for key, item in value.items() if key != omitted}
    return "sha256:" + hashlib.sha256(canonical_bytes(payload)).hexdigest()


def validate_review_request(request: Mapping[str, object]) -> dict[str, object]:
    """Validate that an exact release request is complete and content addressed."""
    required = {"schema", "request_id", "created_at", "subject", "claim_scope",
                "review_tasks", "non_claims", "request_digest"}
    if set(request) != required or request.get("schema") != "continuum/external-review-request/1.0":
        raise ValueError("WITNESS_REQUEST_SCHEMA_INVALID")
    subject = request.get("subject")
    subject_keys = {"application_commit", "image_digest", "run_id", "trace_id",
                    "proof_release_tag", "archive_sha256", "report_digest"}
    if not isinstance(subject, dict) or set(subject) != subject_keys:
        raise ValueError("WITNESS_REQUEST_SUBJECT_INVALID")
    lists = (request.get("claim_scope"), request.get("review_tasks"), request.get("non_claims"))
    if any(not isinstance(items, list) or not items or
           any(not isinstance(item, str) or not item for item in items) for items in lists):
        raise ValueError("WITNESS_REQUEST_SCOPE_INVALID")
    if request.get("request_digest") != content_digest(request, omitted="request_digest"):
        raise ValueError("WITNESS_REQUEST_DIGEST_MISMATCH")
    return dict(request)


def _instant(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("WITNESS_TIME_INVALID")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ValueError("WITNESS_TIME_INVALID") from error
    return parsed.astimezone(timezone.utc)


def validate_external_statement(
    statement: Mapping[str, object], *, request: Mapping[str, object],
    expected_identity: str, expected_issuer: str, now: datetime | None = None,
) -> dict[str, object]:
    """Validate semantics before any cryptographic identity claim is accepted."""
    validate_review_request(request)
    if set(statement) != STATEMENT_KEYS or statement.get("schema") != "continuum/external-witness-statement/1.0":
        raise ValueError("WITNESS_STATEMENT_SCHEMA_INVALID")
    reviewer = statement.get("reviewer")
    if not isinstance(reviewer, dict) or set(reviewer) != REVIEWER_KEYS:
        raise ValueError("WITNESS_REVIEWER_SCHEMA_INVALID")
    if (reviewer.get("identity") != expected_identity or
            reviewer.get("issuer") != expected_issuer):
        raise ValueError("WITNESS_SIGNER_POLICY_MISMATCH")
    if reviewer.get("independence_declared") is not True:
        raise ValueError("WITNESS_INDEPENDENCE_UNDECLARED")
    if statement.get("request_digest") != request["request_digest"]:
        raise ValueError("WITNESS_SUBJECT_MISMATCH")
    if statement.get("verdict") not in {"VERIFIED", "FAILED", "INCONCLUSIVE"}:
        raise ValueError("WITNESS_VERDICT_INVALID")
    claims = statement.get("claim_results")
    if not isinstance(claims, list) or not claims:
        raise ValueError("WITNESS_CLAIMS_INVALID")
    allowed = set(request["claim_scope"])
    seen: set[str] = set()
    for claim in claims:
        if not isinstance(claim, dict) or set(claim) != CLAIM_KEYS:
            raise ValueError("WITNESS_CLAIMS_INVALID")
        name, status, refs = claim.get("claim"), claim.get("status"), claim.get("evidence_refs")
        if name not in allowed or name in seen or status not in {"PASS", "FAIL", "NOT_ASSESSED"}:
            raise ValueError("WITNESS_CLAIMS_INVALID")
        if not isinstance(refs, list) or len(refs) != len(set(refs)) or any(not isinstance(ref, str) for ref in refs):
            raise ValueError("WITNESS_CLAIMS_INVALID")
        seen.add(str(name))
    reviewed, expires = _instant(statement.get("reviewed_at")), _instant(statement.get("expires_at"))
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if expires <= reviewed or current > expires:
        raise ValueError("WITNESS_STATEMENT_EXPIRED")
    if statement.get("statement_digest") != content_digest(statement, omitted="statement_digest"):
        raise ValueError("WITNESS_STATEMENT_DIGEST_MISMATCH")
    return dict(statement)


def verify_sigstore_statement(
    *, statement_path: Path, bundle_path: Path, request: Mapping[str, object],
    expected_identity: str, expected_issuer: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    now: datetime | None = None,
) -> dict[str, object]:
    """Verify statement semantics and a Sigstore keyless identity/transparency bundle."""
    statement = json.loads(statement_path.read_text())
    validated = validate_external_statement(
        statement, request=request, expected_identity=expected_identity,
        expected_issuer=expected_issuer, now=now)
    command = ["cosign", "verify-blob", "--bundle", str(bundle_path),
               "--certificate-identity", expected_identity,
               "--certificate-oidc-issuer", expected_issuer, str(statement_path)]
    result = runner(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise ValueError("WITNESS_SIGSTORE_VERIFICATION_FAILED")
    return validated

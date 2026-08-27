"""Capability-scoped, quota-limited access to the canonical cloud demonstration."""
from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
import re
import secrets
from typing import Any, Callable, Protocol

from .contract import canonical_bytes


AUDIENCE = "continuum-judge"
SCOPE = "canonical-run:start"
_JTI = re.compile(r"^[A-Za-z0-9_-]{8,32}$")
_RUN_ID = re.compile(r"^judge-[A-Za-z0-9_-]{8,32}-[0-9a-f]{12}$")


class JudgeAccessDenied(ValueError):
    """A public judge request failed a stable authorization or quota boundary."""


@dataclass(frozen=True)
class JudgeClaims:
    jti: str
    expires_at: int
    max_runs: int


class JudgeQuota(Protocol):
    def consume(self, claims: JudgeClaims, run_id: str) -> None: ...
    def owns(self, claims: JudgeClaims, run_id: str) -> bool: ...


class CanonicalControlPlane(Protocol):
    def start(self, run_id: str) -> dict[str, Any]: ...
    def status(self, run_id: str) -> dict[str, Any]: ...


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    try:
        return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    except (ValueError, UnicodeEncodeError) as error:
        raise JudgeAccessDenied("JUDGE_TOKEN_MALFORMED") from error


def issue_judge_token(*, secret: str, jti: str, expires_at: int, max_runs: int = 3) -> str:
    """Issue a compact first-party capability; callers keep the secret outside source."""
    if len(secret.encode()) < 32:
        raise JudgeAccessDenied("JUDGE_SECRET_TOO_SHORT")
    if not _JTI.fullmatch(jti) or not isinstance(expires_at, int) or not 1 <= max_runs <= 5:
        raise JudgeAccessDenied("JUDGE_CLAIMS_INVALID")
    body = canonical_bytes({"aud": AUDIENCE, "exp": expires_at, "jti": jti,
                            "max_runs": max_runs, "scope": SCOPE})
    signature = hmac.digest(secret.encode(), body, "sha256")
    return f"{_encode(body)}.{_encode(signature)}"


def verify_judge_token(token: str, *, secret: str, now: int) -> JudgeClaims:
    if len(secret.encode()) < 32:
        raise JudgeAccessDenied("JUDGE_CONFIGURATION_INVALID")
    parts = token.split(".")
    if len(parts) != 2:
        raise JudgeAccessDenied("JUDGE_TOKEN_MALFORMED")
    body, supplied = _decode(parts[0]), _decode(parts[1])
    expected = hmac.digest(secret.encode(), body, "sha256")
    if not hmac.compare_digest(supplied, expected):
        raise JudgeAccessDenied("JUDGE_TOKEN_INVALID")
    try:
        value = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise JudgeAccessDenied("JUDGE_TOKEN_MALFORMED") from error
    if (not isinstance(value, dict) or canonical_bytes(value) != body or
            set(value) != {"aud", "exp", "jti", "max_runs", "scope"} or
            value["aud"] != AUDIENCE or value["scope"] != SCOPE or
            not _JTI.fullmatch(str(value["jti"])) or
            not isinstance(value["exp"], int) or not isinstance(value["max_runs"], int) or
            not 1 <= value["max_runs"] <= 5):
        raise JudgeAccessDenied("JUDGE_CLAIMS_INVALID")
    if now >= value["exp"]:
        raise JudgeAccessDenied("JUDGE_TOKEN_EXPIRED")
    return JudgeClaims(value["jti"], value["exp"], value["max_runs"])


class InMemoryJudgeQuota:
    """Deterministic test/local quota with the same observable contract as Firestore."""
    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}

    def consume(self, claims: JudgeClaims, run_id: str) -> None:
        record = self.records.setdefault(claims.jti, {
            "expires_at": claims.expires_at, "max_runs": claims.max_runs, "runs": []})
        if (record["expires_at"] != claims.expires_at or record["max_runs"] != claims.max_runs):
            raise JudgeAccessDenied("JUDGE_GRANT_CONFLICT")
        if run_id in record["runs"]:
            return
        if len(record["runs"]) >= claims.max_runs:
            raise JudgeAccessDenied("JUDGE_QUOTA_EXHAUSTED")
        record["runs"].append(run_id)

    def owns(self, claims: JudgeClaims, run_id: str) -> bool:
        return run_id in self.records.get(claims.jti, {}).get("runs", [])


class FirestoreJudgeQuota:
    """Atomic, replay-safe cost boundary for the intentionally public judge service."""
    def __init__(self, client: Any, collection: str = "continuity_judge_grants"):
        self.client, self.collection = client, collection

    def _ref(self, claims: JudgeClaims) -> Any:
        return self.client.collection(self.collection).document(sha256(claims.jti.encode()).hexdigest())

    def consume(self, claims: JudgeClaims, run_id: str) -> None:
        from google.cloud import firestore
        reference = self._ref(claims)
        transaction = self.client.transaction()

        @firestore.transactional
        def commit(txn: Any) -> None:
            snapshot = reference.get(transaction=txn)
            value = snapshot.to_dict() if snapshot.exists else {
                "jti_digest": sha256(claims.jti.encode()).hexdigest(),
                "expires_at": claims.expires_at, "max_runs": claims.max_runs, "runs": []}
            if (value.get("expires_at") != claims.expires_at or
                    value.get("max_runs") != claims.max_runs):
                raise JudgeAccessDenied("JUDGE_GRANT_CONFLICT")
            runs = value.get("runs")
            if not isinstance(runs, list):
                raise JudgeAccessDenied("JUDGE_GRANT_CORRUPT")
            if run_id not in runs:
                if len(runs) >= claims.max_runs:
                    raise JudgeAccessDenied("JUDGE_QUOTA_EXHAUSTED")
                runs = [*runs, run_id]
            txn.set(reference, {**value, "runs": runs, "used": len(runs)})

        commit(transaction)

    def owns(self, claims: JudgeClaims, run_id: str) -> bool:
        snapshot = self._ref(claims).get()
        return bool(snapshot.exists and run_id in (snapshot.to_dict() or {}).get("runs", []))


class JudgeController:
    def __init__(self, *, secret: str, quota: JudgeQuota, control: CanonicalControlPlane,
                 clock: Callable[[], int] | None = None,
                 nonce: Callable[[], str] | None = None):
        self.secret, self.quota, self.control = secret, quota, control
        self.clock = clock or (lambda: int(datetime.now(timezone.utc).timestamp()))
        self.nonce = nonce or (lambda: secrets.token_hex(6))

    def _claims(self, token: str) -> JudgeClaims:
        return verify_judge_token(token, secret=self.secret, now=self.clock())

    def start(self, token: str) -> dict[str, Any]:
        claims = self._claims(token)
        run_id = f"judge-{claims.jti}-{self.nonce()}"
        if not _RUN_ID.fullmatch(run_id):
            raise JudgeAccessDenied("JUDGE_NONCE_INVALID")
        self.quota.consume(claims, run_id)
        result = self.control.start(run_id)
        return {**result, "judge_access": {"run_id": run_id,
                "expires_at": claims.expires_at, "maximum_runs": claims.max_runs}}

    def status(self, token: str, run_id: str) -> dict[str, Any]:
        claims = self._claims(token)
        if not _RUN_ID.fullmatch(run_id) or not self.quota.owns(claims, run_id):
            raise JudgeAccessDenied("JUDGE_RUN_DENIED")
        return self.control.status(run_id)

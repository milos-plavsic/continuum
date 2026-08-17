"""Role-aware Cloud Run surface for authenticated lifecycle delivery."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import json
import os
from typing import Any, Callable

from fastapi import FastAPI, Header, HTTPException, Request, Response

from .contract import canonical_bytes
from .cloud_orchestration import (Investigator, Verifier, independent_contract_verifier, invoke, live_adk_investigator,
                                  validate_investigation, workload_service_account)
from .google_binding import FirestoreContinuityStore, GoogleBindingConfig, verify_cloud_run_identity_token


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def decode_pubsub_push(payload: dict[str, Any], *, expected_subscription: str) -> tuple[str, dict[str, Any]]:
    try:
        if set(payload) - {"message", "subscription", "deliveryAttempt"}:
            raise ValueError("INVALID_PUBSUB_ENVELOPE")
        if payload["subscription"] != expected_subscription or not expected_subscription:
            raise ValueError("PUBSUB_SUBSCRIPTION_DENIED")
        message = payload["message"]
        if not isinstance(message, dict) or set(message) - {
                "data", "messageId", "publishTime", "attributes", "orderingKey"}:
            raise ValueError("INVALID_PUBSUB_ENVELOPE")
        message_id = str(message["messageId"])
        if not message_id or not str(message["publishTime"]).endswith("Z"):
            raise ValueError("INVALID_PUBSUB_ENVELOPE")
        raw = base64.b64decode(message["data"], validate=True)
        event = json.loads(raw)
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("INVALID_PUBSUB_ENVELOPE") from error
    required = {"event_id", "event_type", "correlation_id"}
    if not isinstance(event, dict) or not required.issubset(event) or canonical_bytes(event) != raw:
        raise ValueError("INVALID_LIFECYCLE_EVENT")
    attributes = message.get("attributes", {})
    expected_attributes = {
        "event_type": str(event["event_type"]),
        "correlation_id": str(event["correlation_id"]),
        "schema_version": str(event.get("schema_version", 1)),
    }
    if attributes != expected_attributes:
        raise ValueError("PUBSUB_ATTRIBUTE_MISMATCH")
    return message_id, event


def create_cloud_app(*, store: Any | None = None,
                     token_verifier: Callable[[str, str], dict[str, Any]] = verify_cloud_run_identity_token,
                     role: str | None = None,
                     identity_resolver: Callable[[], str] = workload_service_account,
                     investigator: Investigator | None = live_adk_investigator,
                     verifier: Verifier | None = independent_contract_verifier) -> FastAPI:
    active_role = role or os.getenv("CONTINUUM_ROLE", "control")
    project = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    audience = os.getenv("CONTINUUM_CONTROL_AUDIENCE", "")
    push_identity = os.getenv("CONTINUUM_PUBSUB_PUSH_IDENTITY", "")
    push_subscription = os.getenv("CONTINUUM_PUSH_SUBSCRIPTION", "")
    topic = os.getenv("CONTINUUM_LIFECYCLE_TOPIC", "continuum-lifecycle")

    def repository() -> Any:
        nonlocal store
        if store is None:
            if not project:
                raise HTTPException(status_code=503, detail={"code": "CLOUD_PROJECT_NOT_CONFIGURED"})
            store = FirestoreContinuityStore(GoogleBindingConfig(project, topic))
        return store

    app = FastAPI(title=f"Continuum Cloud Role: {active_role}", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "role": active_role}

    @app.get("/build-info")
    def build_info() -> dict[str, Any]:
        return {"role": active_role, "revision": os.getenv("K_REVISION", "unknown"),
                "service": os.getenv("K_SERVICE", "unknown"), "git_sha": os.getenv("GIT_SHA", "unknown"),
                "image_digest": os.getenv("CONTINUUM_IMAGE_DIGEST", "unknown")}

    @app.post("/pubsub/push", status_code=204)
    async def pubsub_push(request: Request, authorization: str | None = Header(default=None)) -> Response:
        if active_role != "control":
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})
        if not authorization or not authorization.startswith("Bearer ") or not audience or not push_identity:
            raise HTTPException(status_code=401, detail={"code": "PUSH_AUTH_REQUIRED"})
        try:
            claims = token_verifier(authorization.removeprefix("Bearer "), audience)
        except Exception as error:
            raise HTTPException(status_code=401, detail={"code": "PUSH_TOKEN_INVALID"}) from error
        if claims.get("email") != push_identity:
            raise HTTPException(status_code=403, detail={"code": "PUSH_IDENTITY_DENIED"})
        try:
            message_id, event = decode_pubsub_push(
                await request.json(), expected_subscription=push_subscription)
        except (ValueError, json.JSONDecodeError) as error:
            raise HTTPException(status_code=400, detail={"code": str(error)}) from error
        digest = __import__("hashlib").sha256(canonical_bytes(event)).hexdigest()
        repository().accept_inbox(message_id=message_id, event_digest=digest,
                                  event_id=event["event_id"], received_at=_utc_now())
        return Response(status_code=204)

    @app.post("/internal/attempt-action")
    def attempt_action() -> dict[str, Any]:
        if active_role not in {"agent-v17", "agent-v18"}:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})
        try:
            identity = identity_resolver()
        except Exception as error:
            raise HTTPException(status_code=503, detail={"code": "WORKLOAD_IDENTITY_UNAVAILABLE"}) from error
        return {"role": active_role, "actor": identity, "request": "vendor.create",
                "authority_source": "application-default-credentials"}

    @app.post("/internal/investigate")
    async def investigate(request: Request) -> dict[str, Any]:
        if active_role not in {"agent-v17", "agent-v18"}:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})
        if investigator is None:
            raise HTTPException(status_code=503, detail={"code": "LIVE_INVESTIGATOR_NOT_CONFIGURED"})
        try:
            identity = identity_resolver()
            proposal = validate_investigation(await invoke(investigator, await request.json(), identity))
        except (ValueError, RuntimeError, json.JSONDecodeError) as error:
            raise HTTPException(status_code=422, detail={"code": str(error)}) from error
        return {"actor": identity, "proposal": proposal}

    @app.post("/internal/verify")
    async def verify(request: Request) -> dict[str, Any]:
        if active_role != "verifier":
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})
        if verifier is None:
            raise HTTPException(status_code=503, detail={"code": "VERIFIER_NOT_CONFIGURED"})
        try:
            identity = identity_resolver()
            result = await invoke(verifier, await request.json(), identity)
        except (ValueError, RuntimeError, json.JSONDecodeError) as error:
            raise HTTPException(status_code=422, detail={"code": str(error)}) from error
        return {"actor": identity, "verification": result}

    return app


app = create_cloud_app()

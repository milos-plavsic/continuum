"""Role-aware Cloud Run surface for authenticated lifecycle delivery."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import json
import os
from typing import Any, Callable

from fastapi import FastAPI, Header, HTTPException, Request, Response

from .contract import canonical_bytes
from .google_binding import FirestoreContinuityStore, GoogleBindingConfig, verify_cloud_run_identity_token


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def decode_pubsub_push(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    try:
        message = payload["message"]
        message_id = str(message["messageId"])
        raw = base64.b64decode(message["data"], validate=True)
        event = json.loads(raw)
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("INVALID_PUBSUB_ENVELOPE") from error
    required = {"event_id", "event_type", "correlation_id"}
    if not required.issubset(event):
        raise ValueError("INVALID_LIFECYCLE_EVENT")
    return message_id, event


def create_cloud_app(*, store: Any | None = None,
                     token_verifier: Callable[[str, str], dict[str, Any]] = verify_cloud_run_identity_token,
                     role: str | None = None) -> FastAPI:
    active_role = role or os.getenv("CONTINUUM_ROLE", "control")
    project = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    audience = os.getenv("CONTINUUM_CONTROL_AUDIENCE", "")
    push_identity = os.getenv("CONTINUUM_PUBSUB_PUSH_IDENTITY", "")
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
        claims = token_verifier(authorization.removeprefix("Bearer "), audience)
        if claims.get("email") != push_identity:
            raise HTTPException(status_code=403, detail={"code": "PUSH_IDENTITY_DENIED"})
        try:
            message_id, event = decode_pubsub_push(await request.json())
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
        return {"role": active_role, "request": "vendor.create", "authority_source": "authenticated workload identity"}

    return app


app = create_cloud_app()

"""Role-aware Cloud Run surface for authenticated lifecycle delivery."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import json
import logging
import os
import re
from typing import Any, Callable

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path

from .contract import canonical_bytes
from .cloud_orchestration import (Investigator, SupplierAssessor, Verifier,
                                  independent_contract_verifier, invoke, live_adk_investigator,
                                  live_adk_supplier_assessor, validate_investigation,
                                  workload_service_account)
from .google_binding import FirestoreContinuityStore, GoogleBindingConfig, verify_cloud_run_identity_token
from .observability import configure_cloud_tracing


_LOG = logging.getLogger("continuum.cloud")
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_TRACEPARENT = re.compile(r"^00-([0-9a-f]{32})-[0-9a-f]{16}-0[01]$")
_GIT_SHA = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")
_IMAGE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


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
                "data", "messageId", "message_id", "publishTime", "publish_time",
                "attributes", "orderingKey", "ordering_key"}:
            raise ValueError("INVALID_PUBSUB_ENVELOPE")
        if message.get("message_id", message["messageId"]) != message["messageId"]:
            raise ValueError("INVALID_PUBSUB_ENVELOPE")
        if message.get("publish_time", message["publishTime"]) != message["publishTime"]:
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
                     supplier_assessor: SupplierAssessor | None = live_adk_supplier_assessor,
                     verifier: Verifier | None = independent_contract_verifier,
                     scenario_service: Any | None = None,
                     action_gateway: Any | None = None,
                     judge_controller: Any | None = None) -> FastAPI:
    active_role = role or os.getenv("CONTINUUM_ROLE", "control")
    project = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    audience = os.getenv("CONTINUUM_CONTROL_AUDIENCE", "")
    push_identity = os.getenv("CONTINUUM_PUBSUB_PUSH_IDENTITY", "")
    push_subscription = os.getenv("CONTINUUM_PUSH_SUBSCRIPTION", "")
    topic = os.getenv("CONTINUUM_LIFECYCLE_TOPIC", "continuum-lifecycle")
    if active_role == "control" and scenario_service is None:
        from .cloud_scenario_adapters import build_production_scenario_service
        scenario_service = build_production_scenario_service()
    if active_role == "judge" and judge_controller is None:
        from .cloud_scenario_adapters import build_production_judge_controller
        judge_controller = build_production_judge_controller()

    def repository() -> Any:
        nonlocal store
        if store is None:
            if not project:
                raise HTTPException(status_code=503, detail={"code": "CLOUD_PROJECT_NOT_CONFIGURED"})
            store = FirestoreContinuityStore(GoogleBindingConfig(project, topic))
        return store

    is_showcase = active_role == "showcase"
    is_judge = active_role == "judge"
    is_public_surface = is_showcase or is_judge
    app = FastAPI(
        title=f"Continuum Cloud Role: {active_role}", version="0.1.0",
        docs_url=None if is_public_surface else "/docs",
        redoc_url=None if is_public_surface else "/redoc",
        openapi_url=None if is_public_surface else "/openapi.json",
    )

    @app.get("/", include_in_schema=False)
    def cloud_cockpit() -> Any:
        if is_showcase:
            return FileResponse(Path(__file__).parent / "static" / "public_showcase.html")
        if is_judge:
            return FileResponse(Path(__file__).parent / "static" / "judge_gateway.html")
        if active_role != "control":
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})
        return FileResponse(Path(__file__).parent / "static" / "cloud_cockpit.html")

    @app.middleware("http")
    async def correlation_boundary(request: Request, call_next: Callable[..., Any]) -> Response:
        run_id = request.headers.get("x-continuum-run-id", "")
        traceparent = request.headers.get("traceparent", "")
        if run_id and not _RUN_ID.fullmatch(run_id):
            return JSONResponse(status_code=400, content={"detail": {"code": "INVALID_RUN_ID"}})
        match = _TRACEPARENT.fullmatch(traceparent) if traceparent else None
        if traceparent and match is None:
            return JSONResponse(status_code=400, content={"detail": {"code": "INVALID_TRACEPARENT"}})
        trace_id = match.group(1) if match else ""
        response = await call_next(request)
        if is_public_surface:
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; style-src 'unsafe-inline'; "
                + ("script-src 'unsafe-inline'; connect-src 'self'; " if is_judge else "")
                + "img-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
            )
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["X-Content-Type-Options"] = "nosniff"
        if run_id:
            response.headers["X-Continuum-Run-ID"] = run_id
        if trace_id:
            response.headers["X-Cloud-Trace-Context"] = f"{trace_id}/0;o=1"
        _LOG.info(json.dumps({"event": "http_request", "service": os.getenv("K_SERVICE", "unknown"),
                              "revision": os.getenv("K_REVISION", "unknown"), "role": active_role,
                              "run_id": run_id or None, "trace_id": trace_id or None,
                              "method": request.method, "path": request.url.path,
                              "status": response.status_code}, sort_keys=True, separators=(",", ":")))
        return response

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "role": active_role}

    @app.get("/ready")
    def ready() -> dict[str, Any]:
        values = {
            "project": project,
            "git_sha": os.getenv("GIT_SHA", ""),
            "image_digest": os.getenv("CONTINUUM_IMAGE_DIGEST", ""),
            "deployment_id": os.getenv("CONTINUUM_DEPLOYMENT_ID", ""),
            "protocol": os.getenv("CONTINUUM_PROTOCOL", ""),
            "service": os.getenv("K_SERVICE", ""),
            "revision": os.getenv("K_REVISION", ""),
        }
        invalid = [key for key, value in values.items() if not value]
        if values["git_sha"] and not _GIT_SHA.fullmatch(values["git_sha"]):
            invalid.append("git_sha")
        if values["image_digest"] and not _IMAGE_DIGEST.fullmatch(values["image_digest"]):
            invalid.append("image_digest")
        expected_deployment = f'{values["git_sha"]}@{values["image_digest"]}'
        if values["deployment_id"] and values["deployment_id"] != expected_deployment:
            invalid.append("deployment_id")
        if values["protocol"] and values["protocol"] != "continuum/0.1-draft":
            invalid.append("protocol")
        if active_role == "control" and (not audience or not push_identity or not push_subscription):
            invalid.append("push_configuration")
        if active_role == "control" and scenario_service is None:
            invalid.append("scenario_service")
        if active_role == "judge" and judge_controller is None:
            invalid.append("judge_controller")
        if invalid:
            raise HTTPException(status_code=503, detail={"code": "DEPLOYMENT_NOT_READY",
                                                         "invalid": sorted(set(invalid))})
        return {"status": "ready", "role": active_role, "deployment_id": values["deployment_id"]}

    @app.get("/build-info")
    def build_info() -> dict[str, Any]:
        return {"role": active_role, "revision": os.getenv("K_REVISION", "unknown"),
                "service": os.getenv("K_SERVICE", "unknown"), "git_sha": os.getenv("GIT_SHA", "unknown"),
                "image_digest": os.getenv("CONTINUUM_IMAGE_DIGEST", "unknown"),
                "deployment_id": os.getenv("CONTINUUM_DEPLOYMENT_ID", "unknown"),
                "protocol": os.getenv("CONTINUUM_PROTOCOL", "unknown")}

    # The public service is a deliberately smaller application, not the private
    # application with authorization checks bolted on. No mutation or internal
    # route is registered in this role.
    if is_showcase:
        return app

    if is_judge:
        from .judge_access import JudgeAccessDenied

        def capability(value: str | None) -> str:
            if not value:
                raise HTTPException(status_code=401, detail={"code": "JUDGE_CAPABILITY_REQUIRED"})
            return value

        @app.post("/judge/runs")
        async def start_judge_run(request: Request,
                                  judge_capability: str | None = Header(
                                      default=None, alias="X-Continuum-Judge-Capability")) -> dict[str, Any]:
            if judge_controller is None:
                raise HTTPException(status_code=503, detail={"code": "JUDGE_GATEWAY_NOT_CONFIGURED"})
            try:
                payload = await request.json()
            except (json.JSONDecodeError, UnicodeDecodeError) as error:
                raise HTTPException(status_code=400, detail={"code": "JUDGE_COMMAND_INVALID"}) from error
            if payload != {}:
                raise HTTPException(status_code=400, detail={"code": "JUDGE_COMMAND_INVALID"})
            try:
                return judge_controller.start(capability(judge_capability))
            except JudgeAccessDenied as error:
                code = str(error)
                status = 429 if code == "JUDGE_QUOTA_EXHAUSTED" else 403
                raise HTTPException(status_code=status, detail={"code": code}) from error
            except (ValueError, RuntimeError) as error:
                raise HTTPException(status_code=502, detail={"code": "CONTROL_PLANE_UNAVAILABLE"}) from error

        @app.get("/judge/runs/{run_id}")
        def judge_run_status(run_id: str,
                             judge_capability: str | None = Header(
                                 default=None, alias="X-Continuum-Judge-Capability")) -> dict[str, Any]:
            if judge_controller is None:
                raise HTTPException(status_code=503, detail={"code": "JUDGE_GATEWAY_NOT_CONFIGURED"})
            try:
                return judge_controller.status(capability(judge_capability), run_id)
            except JudgeAccessDenied as error:
                raise HTTPException(status_code=403, detail={"code": str(error)}) from error
            except (ValueError, RuntimeError) as error:
                raise HTTPException(status_code=502, detail={"code": "CONTROL_PLANE_UNAVAILABLE"}) from error

        return app

    @app.post("/cloud-smoke/start")
    async def start_cloud_scenario(request: Request) -> dict[str, Any]:
        if active_role != "control":
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})
        if scenario_service is None:
            raise HTTPException(status_code=503, detail={"code": "SCENARIO_SERVICE_NOT_CONFIGURED"})
        try:
            payload = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise HTTPException(status_code=400, detail={"code": "SCENARIO_COMMAND_INVALID"}) from error
        if (not isinstance(payload, dict) or set(payload) != {"run_id"} or
                not isinstance(payload["run_id"], str) or
                not _RUN_ID.fullmatch(payload["run_id"])):
            raise HTTPException(status_code=400, detail={"code": "SCENARIO_COMMAND_INVALID"})
        try:
            return scenario_service.run(payload["run_id"])
        except (ValueError, RuntimeError) as error:
            raise HTTPException(status_code=409, detail={"code": str(error)}) from error

    @app.get("/cloud-smoke/{run_id}")
    def cloud_scenario_status(run_id: str) -> dict[str, Any]:
        if active_role != "control":
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})
        if scenario_service is None:
            raise HTTPException(status_code=503, detail={"code": "SCENARIO_SERVICE_NOT_CONFIGURED"})
        if not _RUN_ID.fullmatch(run_id):
            raise HTTPException(status_code=400, detail={"code": "INVALID_RUN_ID"})
        try:
            return scenario_service.status(run_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail={"code": "RUN_NOT_FOUND"}) from error

    @app.post("/cloud-smoke/{run_id}/tick")
    def tick_cloud_scenario(run_id: str) -> dict[str, Any]:
        if active_role != "control":
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})
        if scenario_service is None:
            raise HTTPException(status_code=503, detail={"code": "SCENARIO_SERVICE_NOT_CONFIGURED"})
        try:
            return scenario_service.tick(run_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail={"code": "RUN_NOT_FOUND"}) from error

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
        accepted = repository().accept_inbox(message_id=message_id, event_digest=digest,
                                             event_id=event["event_id"], received_at=_utc_now())
        inbox = repository().inbox_record(message_id)
        already_processed = bool(inbox and inbox.get("status") == "PROCESSED")
        redelivery_probe = (os.getenv("CONTINUUM_FORCE_REDELIVERY") == "1" and
                            event.get("redelivery_probe") is True)
        if accepted and redelivery_probe:
            raise HTTPException(status_code=503, detail={"code": "DELIBERATE_REDELIVERY_PROBE"})
        if not already_processed and scenario_service is not None:
            try:
                scenario_service.handle_event(event)
            except KeyError as error:
                raise HTTPException(status_code=409, detail={"code": "RUN_NOT_FOUND"}) from error
        repository().mark_inbox_processed(message_id=message_id, event_digest=digest,
                                          processed_at=_utc_now())
        if redelivery_probe:
            count = repository().claim_redelivery_evidence(
                message_id=message_id, event_digest=digest, emitted_at=_utc_now())
            if count is not None:
                evidence_run_id = str(event.get("run_id", event["correlation_id"]))
                payload = {"run_id": evidence_run_id, "deliveries": [
                    {"message_id": message_id, "delivery_id": f"{message_id}:{number}"}
                    for number in range(1, count + 1)]}
                print(json.dumps({"continuum_evidence": {
                    "run_id": evidence_run_id, "object_id": "pubsub-deliveries",
                    "payload": payload}}, sort_keys=True, separators=(",", ":")), flush=True)
        return Response(status_code=204)

    @app.post("/internal/attempt-action")
    async def attempt_action(request: Request) -> dict[str, Any]:
        if active_role not in {"agent-v17", "agent-v18", "agent-v19"}:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})
        try:
            identity = identity_resolver()
        except Exception as error:
            raise HTTPException(status_code=503, detail={"code": "WORKLOAD_IDENTITY_UNAVAILABLE"}) from error
        if active_role in {"agent-v18", "agent-v19"}:
            nonlocal action_gateway
            if action_gateway is None and project:
                from google.cloud import firestore
                from .cloud_gateway import FirestoreActionGateway
                external_queue = None
                if (os.getenv("CONTINUUM_GITHUB_REPOSITORY") and
                        os.getenv("CONTINUUM_GITHUB_ISSUE_NUMBER") and
                        os.getenv("CONTINUUM_GITHUB_PROVIDER_TOKEN")):
                    from .external_queue import GitHubIssueWorkQueue
                    external_queue = GitHubIssueWorkQueue(
                        repository=os.environ["CONTINUUM_GITHUB_REPOSITORY"],
                        issue_number=int(os.environ["CONTINUUM_GITHUB_ISSUE_NUMBER"]),
                        token=os.environ["CONTINUUM_GITHUB_PROVIDER_TOKEN"])
                action_gateway = FirestoreActionGateway(
                    firestore.Client(project=project),
                    expected_actor=os.getenv(
                        "CONTINUUM_V18_IDENTITY" if active_role == "agent-v18"
                        else "CONTINUUM_V19_IDENTITY") or None,
                    external_queue=external_queue)
            if action_gateway is None:
                raise HTTPException(status_code=503, detail={"code": "ACTION_GATEWAY_NOT_CONFIGURED"})
            try:
                result = action_gateway.execute_vendor_create(await request.json(), actor=identity)
            except (ValueError, json.JSONDecodeError) as error:
                raise HTTPException(status_code=409, detail={"code": str(error)}) from error
            return {**result, "role": active_role, "authority_source": "firestore-transaction"}
        return {"role": active_role, "actor": identity, "request": "vendor.create",
                "authority_source": "application-default-credentials"}

    @app.post("/internal/attempt-memory")
    def attempt_memory() -> dict[str, Any]:
        if active_role not in {"agent-v17", "agent-v18", "agent-v19"}:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})
        try:
            identity = identity_resolver()
        except Exception as error:
            raise HTTPException(status_code=503, detail={"code": "WORKLOAD_IDENTITY_UNAVAILABLE"}) from error
        return {"role": active_role, "actor": identity, "request": "vendor.approved",
                "authority_source": "application-default-credentials"}

    @app.post("/internal/investigate")
    async def investigate(request: Request) -> dict[str, Any]:
        if active_role not in {"agent-v17", "agent-v18", "agent-v19"}:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})
        if investigator is None:
            raise HTTPException(status_code=503, detail={"code": "LIVE_INVESTIGATOR_NOT_CONFIGURED"})
        try:
            identity = identity_resolver()
            proposal = validate_investigation(await invoke(investigator, await request.json(), identity))
        except (ValueError, RuntimeError, json.JSONDecodeError) as error:
            raise HTTPException(status_code=422, detail={"code": str(error)}) from error
        return {"actor": identity, "proposal": proposal}

    @app.post("/internal/assess-supplier")
    async def assess_supplier(request: Request) -> dict[str, Any]:
        if active_role not in {"agent-v18", "agent-v19"}:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})
        if supplier_assessor is None:
            raise HTTPException(status_code=503, detail={"code": "SUPPLIER_ASSESSOR_NOT_CONFIGURED"})
        try:
            identity = identity_resolver()
            assurance = await invoke(supplier_assessor, await request.json(), identity)
        except (ValueError, RuntimeError, json.JSONDecodeError) as error:
            raise HTTPException(status_code=422, detail={"code": str(error)}) from error
        return {"actor": identity, "assurance": assurance}

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

    configure_cloud_tracing(app)
    return app


app = create_cloud_app()

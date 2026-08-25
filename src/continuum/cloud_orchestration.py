"""Authenticated adapters for the live Google Cloud orchestration boundary."""
from __future__ import annotations

import inspect
import hashlib
import json
from typing import Any, Awaitable, Callable

from .contract import canonical_bytes
from .standard import verify_bundle


Investigator = Callable[[dict[str, Any], str], dict[str, Any] | Awaitable[dict[str, Any]]]
Verifier = Callable[[dict[str, Any], str], dict[str, Any] | Awaitable[dict[str, Any]]]


def workload_service_account(*, credentials_provider: Callable[[], tuple[Any, Any]] | None = None,
                             request_factory: Callable[[], Any] | None = None) -> str:
    """Return the service identity attached to this workload via ADC.

    No request field or long-lived key participates in the authority decision.
    """
    if credentials_provider is None or request_factory is None:
        import google.auth
        from google.auth.transport.requests import Request
        credentials_provider = google.auth.default
        request_factory = Request

    credentials, _ = credentials_provider()
    credentials.refresh(request_factory())
    identity = (getattr(credentials, "service_account_email", None)
                or getattr(credentials, "signer_email", None))
    if not identity or identity == "default":
        raise RuntimeError("WORKLOAD_IDENTITY_UNAVAILABLE")
    return str(identity)


async def invoke(adapter: Investigator | Verifier, payload: dict[str, Any],
                 workload_identity: str) -> dict[str, Any]:
    result = adapter(payload, workload_identity)
    if inspect.isawaitable(result):
        result = await result
    if not isinstance(result, dict):
        raise ValueError("ADAPTER_RESULT_INVALID")
    return result


def validate_investigation(result: dict[str, Any]) -> dict[str, Any]:
    """Keep model output non-authoritative and evidence-cited."""
    required = {"hypotheses", "evidence_ids", "unsupported_assumptions", "risk",
                "reversibility", "proposed_actions"}
    if not required.issubset(result) or not isinstance(result["evidence_ids"], list):
        raise ValueError("INVESTIGATION_RESULT_INVALID")
    forbidden = {"policy_decision", "authority_grant", "execution_receipt"}
    if forbidden.intersection(result):
        raise ValueError("INVESTIGATION_ASSERTS_AUTHORITY")
    return result


async def live_adk_investigator(payload: dict[str, Any], workload_identity: str) -> dict[str, Any]:
    """Run the deployed Gemini investigator through Google ADK.

    Imports stay lazy so offline conformance never acquires credentials or makes
    a model call. The caller validates the returned proposal before using it.
    """
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types
    from app.agent import root_agent

    session_id = hashlib.sha256(
        canonical_request(payload, workload_identity)).hexdigest()[:32]
    sessions = InMemorySessionService()
    await sessions.create_session(
        app_name="continuum", user_id=workload_identity, session_id=session_id)
    runner = Runner(agent=root_agent, app_name="continuum", session_service=sessions)
    prompt = json.dumps({"task": "investigate_lifecycle_event", "evidence": payload},
                        sort_keys=True, separators=(",", ":"))
    final_text: str | None = None
    async for event in runner.run_async(
            user_id=workload_identity, session_id=session_id,
            new_message=types.Content(role="user", parts=[types.Part(text=prompt)])):
        if event.is_final_response() and event.content:
            final_text = "".join(part.text or "" for part in event.content.parts)
    if final_text is None:
        raise ValueError("INVESTIGATION_RESULT_MISSING")
    try:
        result = json.loads(final_text)
    except json.JSONDecodeError as error:
        raise ValueError("INVESTIGATION_RESULT_NOT_JSON") from error
    if not isinstance(result, dict):
        raise ValueError("INVESTIGATION_RESULT_INVALID")
    return result


def canonical_request(payload: dict[str, Any], workload_identity: str) -> bytes:
    return json.dumps({"identity": workload_identity, "payload": payload}, sort_keys=True,
                      separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def independent_contract_verifier(payload: dict[str, Any], workload_identity: str) -> dict[str, Any]:
    """Recompute a submitted contract chain from the verifier workload."""
    bundle = payload.get("bundle")
    if not isinstance(bundle, dict):
        raise ValueError("CONTRACT_BUNDLE_REQUIRED")
    verify_bundle(bundle)
    attestation = next(
        artifact for artifact in bundle["artifacts"]
        if artifact["artifact_type"] == "continuity_attestation")
    declared = attestation["body"]["verification"]["verifier_principal"]
    if declared not in {workload_identity, f"mailto:{workload_identity}"}:
        raise ValueError("VERIFIER_IDENTITY_MISMATCH")
    return {"status": "PASS", "outcome": attestation["body"]["outcome"],
            "attestation_digest": attestation["digest"],
            "bundle_digest": hashlib.sha256(canonical_bytes(bundle)).hexdigest()}

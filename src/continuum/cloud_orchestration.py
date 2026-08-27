"""Authenticated adapters for the live Google Cloud orchestration boundary."""
from __future__ import annotations

import inspect
import hashlib
import json
from typing import Any, Awaitable, Callable

from .contract import canonical_bytes
from .incident_policy import admit_model_remediation
from .verification import FirestoreVerificationReader, IndependentVerificationEngine
from .supplier_assurance import (
    admit_supplier_assessment, check_eu_vat, lookup_gleif, model_supplier_view,
)


Investigator = Callable[[dict[str, Any], str], dict[str, Any] | Awaitable[dict[str, Any]]]
Verifier = Callable[[dict[str, Any], str], dict[str, Any] | Awaitable[dict[str, Any]]]
SupplierAssessor = Callable[[dict[str, Any], str], dict[str, Any] | Awaitable[dict[str, Any]]]


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
                "reversibility", "proposed_actions", "successor_choice"}
    if (not required.issubset(result) or not isinstance(result["evidence_ids"], list)
            or not isinstance(result["proposed_actions"], list)
            or not isinstance(result["successor_choice"], dict)):
        raise ValueError("INVESTIGATION_RESULT_INVALID")
    forbidden = {"policy_decision", "authority_grant", "execution_receipt"}
    if forbidden.intersection(result):
        raise ValueError("INVESTIGATION_ASSERTS_AUTHORITY")
    return result


def admit_remediation_plan(proposal: dict[str, Any],
                           incident_assessment: dict[str, Any]) -> str:
    """Admit a model choice only inside the code-authored remediation set."""
    return admit_model_remediation(proposal, incident_assessment)


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


async def live_adk_supplier_assessor(payload: dict[str, Any],
                                     workload_identity: str) -> dict[str, Any]:
    """Run the practical supplier workflow with live tools and bounded Gemini synthesis."""
    application = payload.get("application")
    if not isinstance(application, dict):
        raise ValueError("SUPPLIER_APPLICATION_REQUIRED")
    try:
        gleif = lookup_gleif(str(application.get("lei", "")))
        vies = check_eu_vat(str(application.get("country_code", "")),
                            str(application.get("vat_number", "")))
    except OSError as error:
        raise RuntimeError("SUPPLIER_TOOL_UNAVAILABLE") from error

    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types
    from app.agent import supplier_agent

    view = model_supplier_view(application, gleif, vies)
    session_id = hashlib.sha256(canonical_request(
        {"run_id": payload.get("run_id"), "supplier": view}, workload_identity)).hexdigest()[:32]
    sessions = InMemorySessionService()
    await sessions.create_session(
        app_name="continuum", user_id=workload_identity, session_id=session_id)
    runner = Runner(agent=supplier_agent, app_name="continuum", session_service=sessions)
    prompt = json.dumps({"task": "assess_supplier_for_sandbox_onboarding", **view},
                        sort_keys=True, separators=(",", ":"))
    final_text: str | None = None
    async for event in runner.run_async(
            user_id=workload_identity, session_id=session_id,
            new_message=types.Content(role="user", parts=[types.Part(text=prompt)])):
        if event.is_final_response() and event.content:
            final_text = "".join(part.text or "" for part in event.content.parts)
    if final_text is None:
        raise ValueError("SUPPLIER_ASSESSMENT_MISSING")
    try:
        result = json.loads(final_text)
    except json.JSONDecodeError as error:
        raise ValueError("SUPPLIER_ASSESSMENT_NOT_JSON") from error
    if not isinstance(result, dict):
        raise ValueError("SUPPLIER_MODEL_RESULT_INVALID")
    return admit_supplier_assessment(
        application=application, gleif=gleif, vies=vies,
        model_result=result, actor=workload_identity)


def canonical_request(payload: dict[str, Any], workload_identity: str) -> bytes:
    return canonical_bytes({"identity": workload_identity, "payload": payload})


def independent_contract_verifier(payload: dict[str, Any], workload_identity: str,
                                  reader: Any | None = None) -> dict[str, Any]:
    """Read provider state and issue (never consume) the continuity attestation."""
    bundle = payload.get("bundle")
    if not isinstance(bundle, dict):
        raise ValueError("CONTRACT_BUNDLE_REQUIRED")
    run_id = payload.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("RUN_ID_REQUIRED")
    if reader is None:
        import os
        from google.cloud import firestore
        project = os.getenv("GOOGLE_CLOUD_PROJECT", "")
        if not project:
            raise RuntimeError("CLOUD_PROJECT_NOT_CONFIGURED")
        reader = FirestoreVerificationReader(firestore.Client(project=project))
    principal = workload_identity if ":" in workload_identity else f"mailto:{workload_identity}"
    return IndependentVerificationEngine(reader).verify(
        run_id=run_id, bundle=bundle, verifier_principal=principal)

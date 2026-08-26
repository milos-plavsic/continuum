"""Verifier-gated, multimodal post-incident learning artifacts.

The Antibody Foundry may explain a verified outcome, but it cannot participate
in authority, execution, or attestation.  Gemma proposes a cited learning plan;
deterministic admission then permits Veo and Lyria to render derivative media.
"""
from __future__ import annotations

import base64
import json
from hashlib import sha256
from time import sleep
from typing import Any, Callable, Protocol
from urllib.parse import quote

from .contract import canonical_bytes, validate_envelope


GEMMA_MODEL = "google/gemma-4-26b-a4b-it-maas"
VEO_MODEL = "veo-3.1-lite-generate-001"
LYRIA_MODEL = "lyria-3-clip-preview"
REQUIRED_FACTS = {
    "obligation-preserved",
    "successor-activated",
    "predecessor-revoked",
    "provider-effect-once",
    "independently-verified",
}


class JsonPoster(Protocol):
    def __call__(self, url: str, payload: dict[str, Any]) -> dict[str, Any]: ...


class BinarySink(Protocol):
    def __call__(self, name: str, content: bytes, mime_type: str) -> str: ...


class LearningPlanner(Protocol):
    def plan(self, evidence: dict[str, Any]) -> dict[str, Any]: ...


class MediaRenderer(Protocol):
    def render(self, prompt: str, request_digest: str) -> dict[str, Any]: ...


def authorized_json_post(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POST JSON using ADC; imports stay lazy for credential-free local tests."""
    import google.auth
    from google.auth.transport.requests import AuthorizedSession

    credentials, _ = google.auth.default(
        scopes=("https://www.googleapis.com/auth/cloud-platform",))
    response = AuthorizedSession(credentials).post(url, json=payload, timeout=180)
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict):
        raise ValueError("MODEL_RESPONSE_INVALID")
    return body


def authorized_gcs_upload(bucket: str, object_name: str, content: bytes,
                          mime_type: str) -> None:
    """Upload one immutable media object using ADC and the JSON API."""
    import google.auth
    from google.auth.transport.requests import AuthorizedSession

    credentials, _ = google.auth.default(
        scopes=("https://www.googleapis.com/auth/cloud-platform",))
    url = ("https://storage.googleapis.com/upload/storage/v1/b/"
           f"{quote(bucket, safe='')}/o")
    response = AuthorizedSession(credentials).post(
        url, params={"uploadType": "media", "name": object_name,
                     "ifGenerationMatch": "0"},
        data=content, headers={"Content-Type": mime_type}, timeout=180)
    response.raise_for_status()


def gcs_binary_sink(output_uri: str, *,
                    upload: Callable[[str, str, bytes, str], None] =
                    authorized_gcs_upload) -> BinarySink:
    """Build a content-addressed, create-only GCS sink for Lyria output."""
    if not output_uri.startswith("gs://"):
        raise ValueError("MEDIA_OUTPUT_URI_INVALID")
    location = output_uri[5:].strip("/")
    bucket, separator, prefix = location.partition("/")
    if not bucket:
        raise ValueError("MEDIA_OUTPUT_URI_INVALID")

    def sink(name: str, content: bytes, mime_type: str) -> str:
        suffixes = {"audio/mpeg": ".mp3", "audio/wav": ".wav"}
        if mime_type not in suffixes:
            raise ValueError("MEDIA_MIME_INVALID")
        digest = sha256(content).hexdigest()
        filename = f"{name}-{digest}{suffixes[mime_type]}"
        object_name = f"{prefix}/{filename}" if separator else filename
        upload(bucket, object_name, content, mime_type)
        return f"gs://{bucket}/{object_name}"

    return sink


def _artifact_by_type(bundle: dict[str, Any], artifact_type: str) -> dict[str, Any]:
    values = [item for item in bundle["artifacts"]
              if item.get("artifact_type") == artifact_type]
    if len(values) != 1:
        raise ValueError("VERIFIED_ARTIFACT_SET_INVALID")
    return values[0]


def verified_learning_evidence(result: dict[str, Any]) -> dict[str, Any]:
    """Reduce a verifier-issued bundle to five non-sensitive, bounded facts."""
    if result.get("status") != "PASS" or result.get("outcome") != "VERIFIED":
        raise ValueError("VERIFIED_RESULT_REQUIRED")
    bundle = result.get("bundle")
    if (not isinstance(bundle, dict) or bundle.get("protocol") != "continuum/0.1-draft"
            or not isinstance(bundle.get("artifacts"), list)
            or len(bundle["artifacts"]) != 6):
        raise ValueError("VERIFIED_BUNDLE_REQUIRED")
    for artifact in bundle["artifacts"]:
        validate_envelope(artifact)
    obligation = _artifact_by_type(bundle, "obligation")
    manifest = _artifact_by_type(bundle, "succession_manifest")
    revocation = _artifact_by_type(bundle, "revocation_proof")
    receipt = _artifact_by_type(bundle, "execution_receipt")
    attestation = _artifact_by_type(bundle, "continuity_attestation")
    verification = attestation["body"].get("verification", {})
    guarantees = attestation["body"].get("guarantees", {})
    if (attestation["body"].get("outcome") != "VERIFIED"
            or not verification.get("independent_of_executor")
            or guarantees != {
                "obligation_preserved": True,
                "authority_overlap": "NONE",
                "unauthorized_context_transferred": False,
                "externally_observed_effect_count": 1,
                "evidence_chain_complete": True,
            }):
        raise ValueError("ATTESTATION_NOT_ADMISSIBLE")
    successor = manifest["body"]["successor"]
    predecessor = manifest["body"]["predecessor"]
    facts = {
        "obligation-preserved": (
            f"Obligation {obligation['artifact_id']} remained preserved."),
        "successor-activated": (
            f"Successor {successor['principal_id']} activated at epoch {successor['epoch']}."),
        "predecessor-revoked": (
            f"Predecessor {predecessor['principal_id']} was revoked through epoch "
            f"{revocation['body']['revoked_through_epoch']}."),
        "provider-effect-once": (
            f"Provider effect {receipt['body']['provider']['resource_ref']} occurred once."),
        "independently-verified": (
            f"Independent verifier {verification['verifier_principal']} issued the attestation."),
    }
    return {
        "schema": "continuum/verified-learning-evidence/0.1",
        "attestation_digest": attestation["digest"],
        "facts": facts,
        "restriction": "DERIVATIVE_ONLY_NOT_AUTHORITY_OR_EVIDENCE",
    }


def admit_learning_plan(plan: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    """Validate citations and bounded rendering prompts before media generation."""
    required = {"headline", "lesson", "regression_test", "fact_ids",
                "video_prompt", "music_prompt"}
    if set(plan) != required:
        raise ValueError("LEARNING_PLAN_SCHEMA_INVALID")
    for key in required - {"fact_ids"}:
        if not isinstance(plan[key], str) or not plan[key].strip() or len(plan[key]) > 900:
            raise ValueError("LEARNING_PLAN_TEXT_INVALID")
    citations = plan["fact_ids"]
    if (not isinstance(citations, list) or set(citations) != REQUIRED_FACTS
            or len(citations) != len(REQUIRED_FACTS)
            or set(evidence.get("facts", {})) != REQUIRED_FACTS):
        raise ValueError("LEARNING_PLAN_CITATIONS_INVALID")
    if any(token in (plan["video_prompt"] + plan["music_prompt"]).lower()
           for token in ("password", "secret", "credential", "api key")):
        raise ValueError("LEARNING_PLAN_SENSITIVE_PROMPT")
    return {key: plan[key] for key in (
        "headline", "lesson", "regression_test", "fact_ids",
        "video_prompt", "music_prompt")}


class GemmaLearningPlanner:
    def __init__(self, project: str, *, post: JsonPoster = authorized_json_post):
        self.project = project
        self.post = post

    def plan(self, evidence: dict[str, Any]) -> dict[str, Any]:
        url = ("https://aiplatform.googleapis.com/v1/projects/"
               f"{self.project}/locations/global/endpoints/openapi/chat/completions")
        prompt = {
            "task": "Create a verified resilience training brief from only the supplied facts.",
            "rules": [
                "Return one JSON object and no prose outside it.",
                "Cite every supplied fact ID exactly once in fact_ids.",
                "Do not add people, secrets, credentials, brands, causes, or outcomes.",
                "video_prompt must describe an abstract 16:9 enterprise workflow animation.",
                "music_prompt must describe calm instrumental music with no vocals.",
            ],
            "schema": {
                "headline": "string", "lesson": "string", "regression_test": "string",
                "fact_ids": sorted(REQUIRED_FACTS), "video_prompt": "string",
                "music_prompt": "string",
            },
            "evidence": evidence,
        }
        response = self.post(url, {
            "model": GEMMA_MODEL,
            "messages": [{"role": "user", "content": json.dumps(
                prompt, sort_keys=True, separators=(",", ":"))}],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        })
        try:
            content = response["choices"][0]["message"]["content"]
            plan = json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise ValueError("GEMMA_PLAN_INVALID") from error
        if not isinstance(plan, dict):
            raise ValueError("GEMMA_PLAN_INVALID")
        return plan


def _find_gcs_uri(value: Any) -> str | None:
    if isinstance(value, str) and value.startswith("gs://"):
        return value
    if isinstance(value, dict):
        for child in value.values():
            found = _find_gcs_uri(child)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = _find_gcs_uri(child)
            if found:
                return found
    return None


class VeoLearningRenderer:
    def __init__(self, project: str, output_uri: str, *,
                 post: JsonPoster = authorized_json_post,
                 wait: Callable[[float], None] = sleep, max_polls: int = 40):
        if not output_uri.startswith("gs://"):
            raise ValueError("VEO_OUTPUT_URI_INVALID")
        self.project, self.output_uri = project, output_uri.rstrip("/")
        self.post, self.wait, self.max_polls = post, wait, max_polls

    def render(self, prompt: str, request_digest: str) -> dict[str, Any]:
        base = (f"https://us-central1-aiplatform.googleapis.com/v1/projects/{self.project}"
                f"/locations/us-central1/publishers/google/models/{VEO_MODEL}")
        started = self.post(f"{base}:predictLongRunning", {
            "instances": [{"prompt": prompt}],
            "parameters": {"storageUri": f"{self.output_uri}/{request_digest}/video/",
                           "sampleCount": 1, "durationSeconds": 4,
                           "aspectRatio": "16:9", "resolution": "720p",
                           "personGeneration": "disallow"},
        })
        operation = started.get("name")
        if not isinstance(operation, str) or not operation:
            raise ValueError("VEO_OPERATION_INVALID")
        for _ in range(self.max_polls):
            state = self.post(f"{base}:fetchPredictOperation", {"operationName": operation})
            if state.get("done"):
                if state.get("error"):
                    # Preserve the bounded provider diagnostic for an auditable
                    # failure while never echoing the request payload or auth.
                    diagnostic = json.dumps(
                        state["error"], sort_keys=True, separators=(",", ":"))[:500]
                    raise RuntimeError(f"VEO_GENERATION_FAILED:{diagnostic}")
                uri = _find_gcs_uri(state.get("response"))
                if not uri:
                    raise ValueError("VEO_OUTPUT_MISSING")
                return {"model": VEO_MODEL, "operation": operation, "uri": uri,
                        "request_digest": request_digest}
            self.wait(15)
        raise TimeoutError("VEO_GENERATION_TIMEOUT")


class LyriaLearningRenderer:
    def __init__(self, project: str, sink: BinarySink, *,
                 post: JsonPoster = authorized_json_post):
        self.project, self.sink, self.post = project, sink, post

    def render(self, prompt: str, request_digest: str) -> dict[str, Any]:
        response = self.post(
            f"https://aiplatform.googleapis.com/v1beta1/projects/{self.project}"
            "/locations/global/interactions",
            {"model": LYRIA_MODEL, "input": [{"type": "text", "text": prompt}]})
        if response.get("status") != "completed" or response.get("model") != LYRIA_MODEL:
            raise ValueError("LYRIA_RESPONSE_INVALID")
        outputs = response.get("outputs")
        audio = next((item for item in outputs if isinstance(item, dict)
                      and item.get("type") == "audio"), None) if isinstance(outputs, list) else None
        if not audio or not isinstance(audio.get("data"), str):
            raise ValueError("LYRIA_AUDIO_MISSING")
        try:
            content = base64.b64decode(audio["data"], validate=True)
        except ValueError as error:
            raise ValueError("LYRIA_AUDIO_INVALID") from error
        if not content:
            raise ValueError("LYRIA_AUDIO_INVALID")
        mime_type = audio.get("mime_type")
        if mime_type not in {"audio/mpeg", "audio/wav"}:
            raise ValueError("LYRIA_MIME_INVALID")
        uri = self.sink(f"{request_digest}-lyria", content, mime_type)
        return {"model": LYRIA_MODEL, "uri": uri, "mime_type": mime_type,
                "sha256": sha256(content).hexdigest(), "request_digest": request_digest}


class VerifiedResilienceBrief:
    def __init__(self, planner: LearningPlanner, video: MediaRenderer, music: MediaRenderer):
        self.planner, self.video, self.music = planner, video, music

    def create(self, verification_result: dict[str, Any]) -> dict[str, Any]:
        evidence = verified_learning_evidence(verification_result)
        plan = admit_learning_plan(self.planner.plan(evidence), evidence)
        request_digest = sha256(canonical_bytes({
            "evidence": evidence, "plan": plan,
            "models": [GEMMA_MODEL, VEO_MODEL, LYRIA_MODEL],
        })).hexdigest()
        video = self.video.render(plan["video_prompt"], request_digest)
        music = self.music.render(plan["music_prompt"], request_digest)
        result = {
            "schema": "continuum/verified-resilience-brief/0.1",
            "status": "DERIVED_NOT_AUTHORITY_OR_EVIDENCE",
            "attestation_digest": evidence["attestation_digest"],
            "request_digest": request_digest,
            "planner": {"model": GEMMA_MODEL, "plan": plan},
            "media": {"video": video, "music": music},
        }
        return {**result, "receipt_digest": sha256(canonical_bytes(result)).hexdigest()}

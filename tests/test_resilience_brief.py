from __future__ import annotations

import base64
from copy import deepcopy
import unittest

from continuum.contract import artifact_digest
from continuum.resilience_brief import (
    GEMMA_MODEL, LYRIA_MODEL, VEO_MODEL, GemmaLearningPlanner,
    LyriaLearningRenderer, VeoLearningRenderer, VerifiedResilienceBrief,
    _find_gcs_uri, admit_learning_plan, authorized_gcs_upload,
    authorized_json_post, gcs_binary_sink,
    verified_learning_evidence,
)
from tests.test_verification_engine import Reader, observations, pre_bundle
from continuum.verification import IndependentVerificationEngine


def verified_result():
    bundle = pre_bundle()
    return IndependentVerificationEngine(
        Reader(**observations(bundle)), clock=lambda: "2026-08-17T10:06:00Z").verify(
            run_id="run-1", bundle=bundle, verifier_principal="urn:independent")


def plan():
    return {
        "headline": "The promise survived the handoff",
        "lesson": "Fence authority before reconstructing minimum context.",
        "regression_test": "Repeat delivery and assert one provider effect.",
        "fact_ids": ["obligation-preserved", "successor-activated",
                     "predecessor-revoked", "provider-effect-once",
                     "independently-verified"],
        "video_prompt": "Abstract 16:9 workflow, failed node hands a glowing ledger to a successor.",
        "music_prompt": "Calm instrumental pulse, restrained, no vocals.",
    }


class Poster:
    def __init__(self, responses): self.responses = list(responses); self.calls = []
    def __call__(self, url, payload):
        self.calls.append((url, payload))
        value = self.responses.pop(0)
        if isinstance(value, Exception): raise value
        return value


class Renderer:
    def __init__(self, kind): self.kind = kind; self.calls = []
    def render(self, prompt, request_digest):
        self.calls.append((prompt, request_digest))
        return {"model": self.kind, "uri": f"gs://proof/{self.kind}"}


class ResilienceBriefTests(unittest.TestCase):
    def test_verified_bundle_causally_drives_all_three_models(self):
        planner = type("Planner", (), {"plan": lambda self, evidence: plan()})()
        video, music = Renderer(VEO_MODEL), Renderer(LYRIA_MODEL)
        result = VerifiedResilienceBrief(planner, video, music).create(verified_result())
        self.assertEqual(result["planner"]["model"], GEMMA_MODEL)
        self.assertEqual(result["status"], "DERIVED_NOT_AUTHORITY_OR_EVIDENCE")
        self.assertEqual(video.calls[0][1], result["request_digest"])
        self.assertEqual(music.calls[0][1], result["request_digest"])
        self.assertEqual(len(result["receipt_digest"]), 64)

    def test_learning_requires_exact_verified_attestation(self):
        good = verified_result()
        variants = [
            {}, {**good, "status": "FAIL"}, {**good, "outcome": "FAILED"},
            {**good, "bundle": None},
            {**good, "bundle": {"protocol": "other", "artifacts": []}},
        ]
        for value in variants:
            with self.subTest(value=value), self.assertRaises(ValueError):
                verified_learning_evidence(value)
        for mutation in ("outcome", "independent", "guarantees"):
            changed = deepcopy(good)
            att = changed["bundle"]["artifacts"][-1]
            if mutation == "outcome": att["body"]["outcome"] = "FAILED"
            elif mutation == "independent": att["body"]["verification"]["independent_of_executor"] = False
            else: att["body"]["guarantees"]["evidence_chain_complete"] = False
            att["digest"] = {"alg": "sha-256", "value": artifact_digest(att)}
            expected = ("ATTESTATION_NOT_ADMISSIBLE" if mutation == "outcome"
                        else "EXECUTOR_SELF_ATTESTATION" if mutation == "independent"
                        else "VERIFIED_GUARANTEES_INVALID")
            with self.subTest(mutation=mutation), self.assertRaisesRegex(
                    ValueError, expected):
                verified_learning_evidence(changed)
        duplicate = deepcopy(good)
        receipt = next(item for item in duplicate["bundle"]["artifacts"]
                       if item["artifact_type"] == "execution_receipt")
        obligation_index = next(index for index, item in enumerate(duplicate["bundle"]["artifacts"])
                                if item["artifact_type"] == "obligation")
        duplicate["bundle"]["artifacts"][obligation_index] = deepcopy(receipt)
        with self.assertRaisesRegex(ValueError, "VERIFIED_ARTIFACT_SET_INVALID"):
            verified_learning_evidence(duplicate)

    def test_plan_admission_rejects_schema_text_citations_and_secrets(self):
        evidence = verified_learning_evidence(verified_result())
        self.assertEqual(admit_learning_plan(plan(), evidence)["headline"], plan()["headline"])
        variants = []
        changed = plan(); changed["extra"] = "x"; variants.append((changed, "SCHEMA"))
        for value in ("", 1, "x" * 901):
            changed = plan(); changed["headline"] = value; variants.append((changed, "TEXT"))
        changed = plan(); changed["fact_ids"] = "bad"; variants.append((changed, "CITATIONS"))
        changed = plan(); changed["fact_ids"] = changed["fact_ids"][:-1]; variants.append((changed, "CITATIONS"))
        changed = plan(); changed["fact_ids"].append(changed["fact_ids"][0]); variants.append((changed, "CITATIONS"))
        changed = plan(); changed["video_prompt"] = "show an API key"; variants.append((changed, "SENSITIVE"))
        for value, reason in variants:
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                admit_learning_plan(value, evidence)
        broken_evidence = {**evidence, "facts": {}}
        with self.assertRaisesRegex(ValueError, "CITATIONS"):
            admit_learning_plan(plan(), broken_evidence)

    def test_gemma_adapter_uses_managed_model_and_strict_json(self):
        posterior = Poster([{"choices": [{"message": {"content": __import__("json").dumps(plan())}}]}])
        result = GemmaLearningPlanner("p", post=posterior).plan({"facts": {}})
        self.assertEqual(result, plan())
        self.assertIn("/projects/p/locations/global/", posterior.calls[0][0])
        self.assertEqual(posterior.calls[0][1]["model"], GEMMA_MODEL)
        for response in ({}, {"choices": []}, {"choices": [{"message": {"content": "[1]"}}]}):
            with self.subTest(response=response), self.assertRaisesRegex(ValueError, "GEMMA_PLAN_INVALID"):
                GemmaLearningPlanner("p", post=Poster([response])).plan({})

    def test_veo_adapter_polls_fixed_quota_operation(self):
        post = Poster([
            {"name": "operations/1"}, {"done": False},
            {"done": True, "response": {"videos": [{"gcsUri": "gs://b/v.mp4"}]}},
        ])
        waits = []
        result = VeoLearningRenderer("p", "gs://b/out/", post=post,
                                     wait=waits.append, max_polls=2).render("prompt", "digest")
        self.assertEqual(result["uri"], "gs://b/v.mp4")
        self.assertEqual(waits, [15])
        self.assertEqual(post.calls[0][1]["parameters"]["personGeneration"], "disallow")
        self.assertEqual(_find_gcs_uri([{"x": "no"}, "gs://nested"]), "gs://nested")
        self.assertIsNone(_find_gcs_uri(["no-uri-here"]))
        self.assertIsNone(_find_gcs_uri(1))

    def test_veo_adapter_fails_closed_for_every_terminal_path(self):
        with self.assertRaisesRegex(ValueError, "OUTPUT_URI"):
            VeoLearningRenderer("p", "https://bucket")
        cases = [
            ([{}], ValueError, "OPERATION"),
            ([{"name": "o"}, {"done": True, "error": {"code": 1}}], RuntimeError, "FAILED"),
            ([{"name": "o"}, {"done": True, "response": {}}], ValueError, "OUTPUT"),
            ([{"name": "o"}, {"done": False}], TimeoutError, "TIMEOUT"),
        ]
        for responses, kind, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(kind, message):
                VeoLearningRenderer("p", "gs://b", post=Poster(responses),
                                    wait=lambda _: None, max_polls=1).render("p", "d")

    def test_lyria_adapter_persists_content_addressed_audio(self):
        saved = []
        sink = lambda name, content, mime: saved.append((name, content, mime)) or "gs://b/a.mp3"
        response = {"status": "completed", "model": LYRIA_MODEL, "outputs": [
            {"type": "text", "text": "description"},
            {"type": "audio", "mime_type": "audio/mpeg",
             "data": base64.b64encode(b"music").decode()},
        ]}
        result = LyriaLearningRenderer("p", sink, post=Poster([response])).render("calm", "digest")
        self.assertEqual(result["uri"], "gs://b/a.mp3")
        self.assertEqual(saved[0], ("digest-lyria", b"music", "audio/mpeg"))
        self.assertEqual(len(result["sha256"]), 64)

    def test_gcs_media_sink_is_create_only_and_content_addressed(self):
        uploads = []
        upload = lambda *values: uploads.append(values)
        sink = gcs_binary_sink("gs://proof/media/", upload=upload)
        uri = sink("brief", b"music", "audio/mpeg")
        digest = __import__("hashlib").sha256(b"music").hexdigest()
        self.assertEqual(uri, f"gs://proof/media/brief-{digest}.mp3")
        self.assertEqual(uploads, [("proof", f"media/brief-{digest}.mp3",
                                    b"music", "audio/mpeg")])
        root_sink = gcs_binary_sink("gs://proof", upload=upload)
        self.assertTrue(root_sink("brief", b"wave", "audio/wav").startswith("gs://proof/brief-"))
        for value in ("https://proof", "gs://"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "OUTPUT_URI"):
                gcs_binary_sink(value, upload=upload)
        with self.assertRaisesRegex(ValueError, "MEDIA_MIME"):
            sink("brief", b"x", "video/mp4")

    def test_lyria_adapter_rejects_invalid_responses(self):
        valid = {"status": "completed", "model": LYRIA_MODEL, "outputs": [
            {"type": "audio", "mime_type": "audio/wav",
             "data": base64.b64encode(b"x").decode()}]}
        variants = [
            ({}, "RESPONSE"),
            ({**valid, "model": "other"}, "RESPONSE"),
            ({**valid, "outputs": None}, "AUDIO_MISSING"),
            ({**valid, "outputs": [{}]}, "AUDIO_MISSING"),
            ({**valid, "outputs": [{"type": "audio", "data": "!"}]}, "AUDIO_INVALID"),
            ({**valid, "outputs": [{"type": "audio", "data": ""}]}, "AUDIO_INVALID"),
            ({**valid, "outputs": [{"type": "audio", "data": base64.b64encode(b"x").decode(),
                                     "mime_type": "video/mp4"}]}, "MIME_INVALID"),
        ]
        for response, message in variants:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                LyriaLearningRenderer("p", lambda *_: "uri", post=Poster([response])).render("p", "d")

    def test_authorized_transport_validates_response_shape(self):
        from unittest.mock import MagicMock, patch
        credentials = object(); response = MagicMock(); response.json.return_value = []
        session = MagicMock(); session.return_value.post.return_value = response
        with patch("google.auth.default", return_value=(credentials, "p")), \
                patch("google.auth.transport.requests.AuthorizedSession", session), \
                self.assertRaisesRegex(ValueError, "MODEL_RESPONSE_INVALID"):
             authorized_json_post("u", {})
        response.json.return_value = {"ok": True}
        with patch("google.auth.default", return_value=(credentials, "p")), \
                patch("google.auth.transport.requests.AuthorizedSession", session):
            self.assertEqual(authorized_json_post("u", {}), {"ok": True})
        response.raise_for_status.assert_called()

    def test_authorized_gcs_upload_is_immutable_and_uses_adc(self):
        from unittest.mock import MagicMock, patch
        credentials = object(); response = MagicMock(); session = MagicMock()
        session.return_value.post.return_value = response
        with patch("google.auth.default", return_value=(credentials, "p")), \
                patch("google.auth.transport.requests.AuthorizedSession", session):
            authorized_gcs_upload("proof bucket", "media/a.mp3", b"audio", "audio/mpeg")
        call = session.return_value.post.call_args
        self.assertIn("proof%20bucket", call.args[0])
        self.assertEqual(call.kwargs["params"]["ifGenerationMatch"], "0")
        self.assertEqual(call.kwargs["data"], b"audio")
        response.raise_for_status.assert_called_once()


if __name__ == "__main__":
    unittest.main()

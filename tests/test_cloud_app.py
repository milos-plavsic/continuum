import base64
from contextlib import redirect_stdout
from io import StringIO
import json
import os
from unittest.mock import patch
import unittest

from fastapi.testclient import TestClient

from continuum.cloud_app import create_cloud_app, decode_pubsub_push
from continuum.cloud_orchestration import workload_service_account


class _Store:
    def __init__(self):
        self.messages = {}

    def accept_inbox(self, **item):
        current = self.messages.get(item["message_id"])
        if current and current["event_digest"] != item["event_digest"]:
            raise ValueError("MESSAGE_ID_CONTENT_CONFLICT")
        if current:
            current["delivery_count"] = current.get("delivery_count", 1) + 1
            return False
        self.messages[item["message_id"]] = {**item, "delivery_count": 1}
        return True

    def mark_inbox_processed(self, **item):
        self.messages[item["message_id"]]["status"] = "PROCESSED"

    def inbox_record(self, message_id):
        return self.messages.get(message_id)

    def claim_redelivery_evidence(self, **item):
        current = self.messages[item["message_id"]]
        if current["event_digest"] != item["event_digest"]:
            raise ValueError("MESSAGE_ID_CONTENT_CONFLICT")
        if current["delivery_count"] < 2 or current.get("redelivery_evidence_emitted"):
            return None
        current["redelivery_evidence_emitted"] = True
        return current["delivery_count"]


def _payload(event, message_id="m1"):
    raw = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return {"subscription": "projects/p/subscriptions/control",
            "message": {"messageId": message_id, "publishTime": "2026-08-17T12:00:00Z",
                        "attributes": {"event_type": str(event.get("event_type", "")),
                                       "correlation_id": str(event.get("correlation_id", "")),
                                       "schema_version": str(event.get("schema_version", 1))},
                        "data": base64.b64encode(raw).decode()}}


class CloudAppTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {
            "CONTINUUM_CONTROL_AUDIENCE": "https://control.run.app",
            "CONTINUUM_PUBSUB_PUSH_IDENTITY": "push@example.iam.gserviceaccount.com",
            "CONTINUUM_PUSH_SUBSCRIPTION": "projects/p/subscriptions/control",
        })
        self.environment.start()
        self.store = _Store()
        self.client = TestClient(create_cloud_app(store=self.store, role="control",
            identity_resolver=lambda: "control@example.iam.gserviceaccount.com",
            token_verifier=lambda token, audience: {"email": "push@example.iam.gserviceaccount.com",
                                                    "aud": audience, "token": token}))

    def tearDown(self):
        self.environment.stop()

    def test_workload_identity_refreshes_adc_before_reading_email(self):
        class Credentials:
            service_account_email = "default"
            signer_email = None
            def refresh(self, _request):
                self.service_account_email = "continuum-v18@example.iam.gserviceaccount.com"
        credentials = Credentials()
        self.assertEqual(workload_service_account(
            credentials_provider=lambda: (credentials, "project"), request_factory=object),
            "continuum-v18@example.iam.gserviceaccount.com")

    def test_authenticated_push_is_deduplicated_by_message_id(self):
        event = {"event_id": "e1", "event_type": "identity.fenced", "correlation_id": "r1"}
        headers = {"Authorization": "Bearer signed-token"}
        self.assertEqual(self.client.post("/pubsub/push", json=_payload(event), headers=headers).status_code, 204)
        self.assertEqual(self.client.post("/pubsub/push", json=_payload(event), headers=headers).status_code, 204)
        self.assertEqual(len(self.store.messages), 1)

    def test_real_google_push_aliases_are_accepted_but_must_match(self):
        event = {"event_id": "e-alias", "event_type": "identity.fenced", "correlation_id": "r1"}
        payload = _payload(event)
        payload["message"]["message_id"] = payload["message"]["messageId"]
        payload["message"]["publish_time"] = payload["message"]["publishTime"]
        headers = {"Authorization": "Bearer signed-token"}
        self.assertEqual(self.client.post("/pubsub/push", json=payload, headers=headers).status_code, 204)
        payload["message"]["message_id"] = "substituted"
        self.assertEqual(self.client.post("/pubsub/push", json=payload, headers=headers).status_code, 400)

    def test_marked_event_forces_one_real_pubsub_redelivery(self):
        event = {"event_id": "e-redelivery", "event_type": "expectation.missed",
                 "correlation_id": "trace", "run_id": "run-redelivery",
                 "redelivery_probe": True}
        headers = {"Authorization": "Bearer signed-token"}
        output = StringIO()
        with redirect_stdout(output), patch.dict(os.environ, {"CONTINUUM_FORCE_REDELIVERY": "1"}):
            self.assertEqual(self.client.post("/pubsub/push", json=_payload(event), headers=headers).status_code, 503)
            self.assertEqual(self.client.post("/pubsub/push", json=_payload(event), headers=headers).status_code, 204)
            self.assertEqual(self.client.post("/pubsub/push", json=_payload(event), headers=headers).status_code, 204)
        self.assertEqual(self.store.inbox_record("m1")["delivery_count"], 3)
        self.assertEqual(output.getvalue().count('"object_id":"pubsub-deliveries"'), 1)

    def test_push_rejects_wrong_workload_identity(self):
        client = TestClient(create_cloud_app(store=self.store, role="control",
            token_verifier=lambda token, audience: {"email": "attacker@example.com"}))
        response = client.post("/pubsub/push", json=_payload({}), headers={"Authorization": "Bearer token"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["code"], "PUSH_IDENTITY_DENIED")

    def test_push_rejects_invalid_signed_token_before_mutation(self):
        client = TestClient(create_cloud_app(store=self.store, role="control",
            token_verifier=lambda token, audience: (_ for _ in ()).throw(ValueError("bad token"))))
        response = client.post("/pubsub/push", json=_payload({}),
                               headers={"Authorization": "Bearer bad"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"]["code"], "PUSH_TOKEN_INVALID")
        self.assertEqual(self.store.messages, {})

    def test_invalid_push_fails_before_inbox(self):
        headers = {"Authorization": "Bearer signed-token"}
        response = self.client.post("/pubsub/push", json={"message": {"messageId": "m1", "data": "!!!"}}, headers=headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.store.messages, {})

    def test_push_rejects_wrong_subscription_and_attribute_substitution(self):
        event = {"event_id": "e1", "event_type": "identity.fenced", "correlation_id": "r1"}
        headers = {"Authorization": "Bearer signed-token"}
        wrong_subscription = _payload(event)
        wrong_subscription["subscription"] = "projects/p/subscriptions/attacker"
        response = self.client.post("/pubsub/push", json=wrong_subscription, headers=headers)
        self.assertEqual(response.status_code, 400)
        substituted = _payload(event)
        substituted["message"]["attributes"]["event_type"] = "authority.granted"
        response = self.client.post("/pubsub/push", json=substituted, headers=headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.store.messages, {})

    def test_agent_role_cannot_accept_pubsub(self):
        agent = TestClient(create_cloud_app(store=self.store, role="agent-v17",
                                           identity_resolver=lambda: "v17@example.com"))
        self.assertEqual(agent.post("/pubsub/push").status_code, 404)
        self.assertEqual(agent.get("/").status_code, 404)
        result = agent.post("/internal/attempt-action", json={"actor": "forged@example.com"}).json()
        self.assertEqual(result["role"], "agent-v17")
        self.assertEqual(result["actor"], "v17@example.com")
        memory = agent.post("/internal/attempt-memory", json={"actor": "forged@example.com"}).json()
        self.assertEqual(memory["actor"], "v17@example.com")

    def test_control_root_serves_one_click_cloud_cockpit(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("One click", response.text)
        self.assertIn("SAME-RUN GOOGLE CLOUD PROOF", response.text)
        self.assertIn("The executor cannot grade its own homework", response.text)
        self.assertIn("predecessor.denials_observed", response.text)
        self.assertIn("cursor-halo", response.text)
        self.assertIn("GLEIF and EU VIES receipts", response.text)
        self.assertIn("Two deliveries converge on one effect", response.text)

    def test_public_showcase_is_static_hardened_and_has_no_mutation_surface(self):
        showcase = TestClient(create_cloud_app(role="showcase"))
        response = showcase.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Public read-only showcase", response.text)
        self.assertIn("17 required objects", response.text)
        self.assertIn("cloud-proof-d4d7d52", response.text)
        self.assertIn("v19 selected", response.text)
        self.assertIn("one GitHub issue", response.text)
        self.assertIn("default-src 'none'", response.headers["Content-Security-Policy"])
        self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(showcase.get("/docs").status_code, 404)
        self.assertEqual(showcase.get("/openapi.json").status_code, 404)
        self.assertEqual(showcase.get("/cloud-smoke/x").status_code, 404)
        self.assertEqual(showcase.post("/cloud-smoke/start", json={"run_id": "x"}).status_code, 404)
        self.assertEqual(showcase.post("/cloud-smoke/x/tick").status_code, 404)
        self.assertEqual(showcase.post("/pubsub/push", json={}).status_code, 404)
        self.assertEqual(showcase.post("/internal/attempt-action", json={}).status_code, 404)
        self.assertEqual(showcase.post("/internal/attempt-memory").status_code, 404)
        self.assertEqual(showcase.post("/internal/investigate", json={}).status_code, 404)
        self.assertEqual(showcase.post("/internal/assess-supplier", json={}).status_code, 404)
        self.assertEqual(showcase.post("/internal/verify", json={}).status_code, 404)

    def test_live_investigation_is_injected_typed_and_workload_derived(self):
        observed = {}
        async def investigate(payload, identity):
            observed.update(payload=payload, identity=identity)
            return {"hypotheses": ["deadline missed"], "evidence_ids": ["e1"],
                    "unsupported_assumptions": [], "risk": "medium", "reversibility": "high",
                    "proposed_actions": ["review"], "successor_choice": {}}
        agent = TestClient(create_cloud_app(role="agent-v18", investigator=investigate,
            identity_resolver=lambda: "v18@example.iam.gserviceaccount.com"))
        response = agent.post("/internal/investigate", json={"event_id": "e1", "actor": "forged"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["actor"], "v18@example.iam.gserviceaccount.com")
        self.assertEqual(observed["identity"], "v18@example.iam.gserviceaccount.com")

    def test_investigator_cannot_assert_authority(self):
        def investigate(payload, identity):
            return {"hypotheses": [], "evidence_ids": [], "unsupported_assumptions": [],
                    "risk": "low", "reversibility": "high", "proposed_actions": [],
                    "successor_choice": {},
                    "policy_decision": "APPROVE"}
        agent = TestClient(create_cloud_app(role="agent-v18", investigator=investigate,
                                           identity_resolver=lambda: "v18@example.com"))
        response = agent.post("/internal/investigate", json={"event_id": "e1"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["code"], "INVESTIGATION_ASSERTS_AUTHORITY")

    def test_supplier_assurance_agent_is_typed_workload_derived_and_role_separated(self):
        observed = {}
        async def assess(payload, identity):
            observed.update(payload=payload, identity=identity)
            return {"workflow": "SUPPLIER_ASSURANCE_AGENT", "status": "VERIFIED"}
        agent = TestClient(create_cloud_app(role="agent-v18", supplier_assessor=assess,
            identity_resolver=lambda: "v18@example.iam.gserviceaccount.com"))
        response = agent.post("/internal/assess-supplier", json={"application": {"id": "a"}})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["actor"], "v18@example.iam.gserviceaccount.com")
        self.assertEqual(observed["identity"], "v18@example.iam.gserviceaccount.com")
        control = TestClient(create_cloud_app(role="control", scenario_service=unittest.mock.Mock(),
                                              supplier_assessor=assess))
        self.assertEqual(control.post("/internal/assess-supplier", json={}).status_code, 404)
        unavailable = TestClient(create_cloud_app(role="agent-v19", supplier_assessor=None))
        self.assertEqual(unavailable.post("/internal/assess-supplier", json={}).status_code, 503)
        failing = TestClient(create_cloud_app(role="agent-v19",
            supplier_assessor=lambda payload, identity: (_ for _ in ()).throw(ValueError("bad")),
            identity_resolver=lambda: "v19@example"))
        self.assertEqual(failing.post("/internal/assess-supplier", json={}).status_code, 422)

    def test_verifier_endpoint_is_role_separated(self):
        adapter = lambda payload, identity: {"status": "PASS", "subject": payload["digest"]}
        agent = TestClient(create_cloud_app(role="agent-v18", verifier=adapter,
                                           identity_resolver=lambda: "agent@example.com"))
        self.assertEqual(agent.post("/internal/verify", json={"digest": "abc"}).status_code, 404)
        verifier = TestClient(create_cloud_app(role="verifier", verifier=adapter,
            identity_resolver=lambda: "verifier@example.iam.gserviceaccount.com"))
        response = verifier.post("/internal/verify", json={"digest": "abc"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["actor"], "verifier@example.iam.gserviceaccount.com")

    def test_decoder_rejects_every_structural_boundary(self):
        event = {"event_id": "e", "event_type": "t", "correlation_id": "c"}
        valid = _payload(event)
        mutations = []
        extra = json.loads(json.dumps(valid)); extra["extra"] = 1; mutations.append(extra)
        wrong_message = json.loads(json.dumps(valid)); wrong_message["message"] = []; mutations.append(wrong_message)
        message_extra = json.loads(json.dumps(valid)); message_extra["message"]["extra"] = 1; mutations.append(message_extra)
        alias_time = json.loads(json.dumps(valid)); alias_time["message"]["publish_time"] = "different"; mutations.append(alias_time)
        empty_id = json.loads(json.dumps(valid)); empty_id["message"]["messageId"] = ""; mutations.append(empty_id)
        bad_time = json.loads(json.dumps(valid)); bad_time["message"]["publishTime"] = "not-utc"; mutations.append(bad_time)
        invalid_data = json.loads(json.dumps(valid)); invalid_data["message"]["data"] = "!!!"; mutations.append(invalid_data)
        for payload in mutations:
            with self.subTest(payload=payload), self.assertRaisesRegex(ValueError, "INVALID_PUBSUB_ENVELOPE"):
                decode_pubsub_push(payload, expected_subscription="projects/p/subscriptions/control")
        for bad_event in [[], {"event_id": "e"}, {**event, "unsupported": object()}]:
            if isinstance(bad_event, dict) and "unsupported" in bad_event:
                raw = b'{"correlation_id":"c","event_id":"e","event_type":"t", "unsupported": 1}'
                payload = _payload(event); payload["message"]["data"] = base64.b64encode(raw).decode()
            else:
                payload = _payload(event); raw = json.dumps(bad_event).encode(); payload["message"]["data"] = base64.b64encode(raw).decode()
            with self.assertRaisesRegex(ValueError, "INVALID_LIFECYCLE_EVENT"):
                decode_pubsub_push(payload, expected_subscription="projects/p/subscriptions/control")

    def test_correlation_boundary_rejects_invalid_values_and_emits_headers(self):
        self.assertEqual(self.client.get("/health", headers={"X-Continuum-Run-ID": "bad id"}).status_code, 400)
        self.assertEqual(self.client.get("/health", headers={"traceparent": "bad"}).status_code, 400)
        trace = "a" * 32
        response = self.client.get("/health", headers={"X-Continuum-Run-ID": "run:1", "traceparent": f"00-{trace}-0000000000000001-01"})
        self.assertEqual(response.headers["X-Continuum-Run-ID"], "run:1")
        self.assertEqual(response.headers["X-Cloud-Trace-Context"], f"{trace}/0;o=1")

    def test_readiness_reports_each_invalid_deployment_field_and_accepts_valid_agent(self):
        bad = {"GOOGLE_CLOUD_PROJECT": "p", "GIT_SHA": "bad", "CONTINUUM_IMAGE_DIGEST": "bad",
               "CONTINUUM_DEPLOYMENT_ID": "mismatch", "CONTINUUM_PROTOCOL": "bad",
               "K_SERVICE": "s", "K_REVISION": "r"}
        with patch.dict(os.environ, bad, clear=True):
            response = TestClient(create_cloud_app(role="control", scenario_service=None)).get("/ready")
        self.assertEqual(response.status_code, 503)
        self.assertTrue({"git_sha", "image_digest", "deployment_id", "protocol", "push_configuration", "scenario_service"}.issubset(response.json()["detail"]["invalid"]))
        sha = "a" * 40; digest = "sha256:" + "b" * 64
        good = {"GOOGLE_CLOUD_PROJECT": "p", "GIT_SHA": sha, "CONTINUUM_IMAGE_DIGEST": digest,
                "CONTINUUM_DEPLOYMENT_ID": f"{sha}@{digest}", "CONTINUUM_PROTOCOL": "continuum/0.1-draft",
                "K_SERVICE": "agent", "K_REVISION": "agent-1"}
        with patch.dict(os.environ, good, clear=True):
            client = TestClient(create_cloud_app(role="agent-v18"))
            self.assertEqual(client.get("/ready").json()["status"], "ready")
            self.assertEqual(client.get("/build-info").json()["revision"], "agent-1")

    def test_cloud_scenario_http_failure_paths(self):
        service = unittest.mock.Mock()
        service.run.side_effect = ValueError("RUN_CONFLICT")
        service.status.side_effect = KeyError("missing")
        control = TestClient(create_cloud_app(role="control", scenario_service=service))
        self.assertEqual(control.post("/cloud-smoke/start", content=b"not-json", headers={"content-type": "application/json"}).status_code, 400)
        self.assertEqual(control.post("/cloud-smoke/start", json={"run_id": "bad id"}).status_code, 400)
        self.assertEqual(control.post("/cloud-smoke/start", json={"run_id": "valid"}).status_code, 409)
        self.assertEqual(control.get("/cloud-smoke/bad id").status_code, 400)
        self.assertEqual(control.get("/cloud-smoke/missing").status_code, 404)
        agent = TestClient(create_cloud_app(role="agent-v18"))
        self.assertEqual(agent.post("/cloud-smoke/start", json={"run_id": "x"}).status_code, 404)
        self.assertEqual(agent.get("/cloud-smoke/x").status_code, 404)
        self.assertEqual(agent.post("/cloud-smoke/x/tick").status_code, 404)
        service.tick.return_value = {"phase": "WAITING_FOR_DEADLINE"}
        self.assertEqual(control.post("/cloud-smoke/valid/tick").json()["phase"], "WAITING_FOR_DEADLINE")
        service.tick.side_effect = KeyError("missing")
        self.assertEqual(control.post("/cloud-smoke/missing/tick").status_code, 404)
        without_service = TestClient(create_cloud_app(role="control", scenario_service=None))
        self.assertEqual(without_service.post("/cloud-smoke/x/tick").status_code, 503)

    def test_role_endpoint_configuration_and_identity_failures(self):
        control = TestClient(create_cloud_app(role="control", scenario_service=unittest.mock.Mock()))
        self.assertEqual(control.post("/internal/attempt-action").status_code, 404)
        self.assertEqual(control.post("/internal/attempt-memory").status_code, 404)
        failing = lambda: (_ for _ in ()).throw(RuntimeError("adc"))
        agent = TestClient(create_cloud_app(role="agent-v17", identity_resolver=failing))
        self.assertEqual(agent.post("/internal/attempt-action").status_code, 503)
        self.assertEqual(agent.post("/internal/attempt-memory").status_code, 503)
        self.assertEqual(agent.post("/internal/investigate", json={}).status_code, 422)
        no_investigator = TestClient(create_cloud_app(role="agent-v18", investigator=None))
        self.assertEqual(no_investigator.post("/internal/investigate", json={}).status_code, 503)
        self.assertEqual(control.post("/internal/investigate", json={}).status_code, 404)
        no_verifier = TestClient(create_cloud_app(role="verifier", verifier=None))
        self.assertEqual(no_verifier.post("/internal/verify", json={}).status_code, 503)
        bad_verifier = TestClient(create_cloud_app(role="verifier", verifier=lambda p, i: (_ for _ in ()).throw(ValueError("bad")), identity_resolver=lambda: "v"))
        self.assertEqual(bad_verifier.post("/internal/verify", json={}).status_code, 422)

    def test_v18_action_endpoint_uses_injected_transactional_gateway_and_fails_closed(self):
        gateway = unittest.mock.Mock()
        gateway.execute_vendor_create.return_value = {
            "state": "DISPATCHED", "actor": "v18@example.com", "provider_ref": "p"}
        agent = TestClient(create_cloud_app(role="agent-v18", action_gateway=gateway,
            identity_resolver=lambda: "v18@example.com"))
        self.assertEqual(agent.post("/internal/attempt-action", json={"request": 1}).json()["state"], "DISPATCHED")
        gateway.execute_vendor_create.side_effect = ValueError("DENIED")
        self.assertEqual(agent.post("/internal/attempt-action", json={}).status_code, 409)
        unavailable = TestClient(create_cloud_app(role="agent-v18", action_gateway=None,
            identity_resolver=lambda: "v18@example.com"))
        self.assertEqual(unavailable.post("/internal/attempt-action", json={}).status_code, 503)
        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "p"}), \
             patch("google.cloud.firestore.Client", return_value=object()), \
             patch("continuum.cloud_gateway.FirestoreActionGateway", return_value=gateway):
            lazy = TestClient(create_cloud_app(role="agent-v18",
                identity_resolver=lambda: "v18@example.com"))
            gateway.execute_vendor_create.side_effect = None
            self.assertEqual(lazy.post("/internal/attempt-action", json={}).status_code, 200)
        provider = unittest.mock.Mock()
        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT":"p",
                "CONTINUUM_GITHUB_REPOSITORY":"o/r", "CONTINUUM_GITHUB_ISSUE_NUMBER":"7",
                "CONTINUUM_GITHUB_PROVIDER_TOKEN":"token"}), \
             patch("google.cloud.firestore.Client", return_value=object()), \
             patch("continuum.external_queue.GitHubIssueWorkQueue", return_value=provider) as queue, \
             patch("continuum.cloud_gateway.FirestoreActionGateway", return_value=gateway) as factory:
            external = TestClient(create_cloud_app(role="agent-v19",
                identity_resolver=lambda: "v19@example.com"))
            self.assertEqual(external.post("/internal/attempt-action", json={}).status_code, 200)
        queue.assert_called_once_with(repository="o/r", issue_number=7, token="token")
        self.assertIs(factory.call_args.kwargs["external_queue"], provider)

    def test_pubsub_event_causally_resumes_scenario_and_missing_run_is_rejected(self):
        service = unittest.mock.Mock()
        service.handle_event.side_effect = KeyError("missing")
        client = TestClient(create_cloud_app(store=_Store(), role="control", scenario_service=service,
            token_verifier=lambda token, audience: {"email": "push@example.iam.gserviceaccount.com"}))
        event = {"event_id": "e-causal", "event_type": "expectation.missed",
                 "correlation_id": "trace", "run_id": "missing"}
        response = client.post("/pubsub/push", json=_payload(event),
                               headers={"Authorization": "Bearer token"})
        self.assertEqual(response.status_code, 409)
        service.handle_event.side_effect = None
        service.reset_mock(); store = _Store()
        client = TestClient(create_cloud_app(store=store, role="control", scenario_service=service,
            token_verifier=lambda token, audience: {"email": "push@example.iam.gserviceaccount.com"}))
        self.assertEqual(client.post("/pubsub/push", json=_payload(event),
                                    headers={"Authorization": "Bearer token"}).status_code, 204)
        self.assertEqual(client.post("/pubsub/push", json=_payload(event),
                                    headers={"Authorization": "Bearer token"}).status_code, 204)
        service.handle_event.assert_called_once()

    def test_push_requires_bearer_and_lazy_repository_requires_project(self):
        self.assertEqual(self.client.post("/pubsub/push", json={}).status_code, 401)
        event = {"event_id": "e", "event_type": "t", "correlation_id": "c"}
        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": ""}):
            client = TestClient(create_cloud_app(store=None, role="control", scenario_service=unittest.mock.Mock(),
                token_verifier=lambda token, audience: {"email": "push@example.iam.gserviceaccount.com"}))
            self.assertEqual(client.post("/pubsub/push", json=_payload(event), headers={"Authorization": "Bearer token"}).status_code, 503)
        lazy_store = _Store()
        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "p"}), \
             patch("continuum.cloud_app.FirestoreContinuityStore", return_value=lazy_store):
            client = TestClient(create_cloud_app(store=None, role="control", scenario_service=unittest.mock.Mock(),
                token_verifier=lambda token, audience: {"email": "push@example.iam.gserviceaccount.com"}))
            self.assertEqual(client.post("/pubsub/push", json=_payload(event), headers={"Authorization": "Bearer token"}).status_code, 204)
        without_service = TestClient(create_cloud_app(role="control", scenario_service=None))
        self.assertEqual(without_service.get("/cloud-smoke/missing").status_code, 503)


if __name__ == "__main__":
    unittest.main()

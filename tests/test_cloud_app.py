import base64
import json
import os
from pathlib import Path
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

    def test_marked_event_forces_one_real_pubsub_redelivery(self):
        event = {"event_id": "e-redelivery", "event_type": "expectation.missed",
                 "correlation_id": "trace", "run_id": "run-redelivery",
                 "redelivery_probe": True}
        headers = {"Authorization": "Bearer signed-token"}
        with patch.dict(os.environ, {"CONTINUUM_FORCE_REDELIVERY": "1"}):
            self.assertEqual(self.client.post("/pubsub/push", json=_payload(event), headers=headers).status_code, 503)
            self.assertEqual(self.client.post("/pubsub/push", json=_payload(event), headers=headers).status_code, 204)
        self.assertEqual(self.store.inbox_record("m1")["delivery_count"], 2)

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
        result = agent.post("/internal/attempt-action", json={"actor": "forged@example.com"}).json()
        self.assertEqual(result["role"], "agent-v17")
        self.assertEqual(result["actor"], "v17@example.com")
        memory = agent.post("/internal/attempt-memory", json={"actor": "forged@example.com"}).json()
        self.assertEqual(memory["actor"], "v17@example.com")

    def test_live_investigation_is_injected_typed_and_workload_derived(self):
        observed = {}
        async def investigate(payload, identity):
            observed.update(payload=payload, identity=identity)
            return {"hypotheses": ["deadline missed"], "evidence_ids": ["e1"],
                    "unsupported_assumptions": [], "risk": "medium", "reversibility": "high",
                    "proposed_actions": ["review"]}
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
                    "policy_decision": "APPROVE"}
        agent = TestClient(create_cloud_app(role="agent-v18", investigator=investigate,
                                           identity_resolver=lambda: "v18@example.com"))
        response = agent.post("/internal/investigate", json={"event_id": "e1"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["code"], "INVESTIGATION_ASSERTS_AUTHORITY")

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


if __name__ == "__main__":
    unittest.main()

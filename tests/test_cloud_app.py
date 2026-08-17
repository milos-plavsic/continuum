import base64
import json
import os
from pathlib import Path
from unittest.mock import patch
import unittest

from fastapi.testclient import TestClient

from continuum.cloud_app import create_cloud_app, decode_pubsub_push


class _Store:
    def __init__(self):
        self.messages = {}

    def accept_inbox(self, **item):
        current = self.messages.get(item["message_id"])
        if current and current["event_digest"] != item["event_digest"]:
            raise ValueError("MESSAGE_ID_CONTENT_CONFLICT")
        if current:
            return False
        self.messages[item["message_id"]] = item
        return True


def _payload(event, message_id="m1"):
    return {"message": {"messageId": message_id,
                        "data": base64.b64encode(json.dumps(event).encode()).decode()}}


class CloudAppTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {
            "CONTINUUM_CONTROL_AUDIENCE": "https://control.run.app",
            "CONTINUUM_PUBSUB_PUSH_IDENTITY": "push@example.iam.gserviceaccount.com",
        })
        self.environment.start()
        self.store = _Store()
        self.client = TestClient(create_cloud_app(store=self.store, role="control",
            token_verifier=lambda token, audience: {"email": "push@example.iam.gserviceaccount.com",
                                                    "aud": audience, "token": token}))

    def tearDown(self):
        self.environment.stop()

    def test_authenticated_push_is_deduplicated_by_message_id(self):
        event = {"event_id": "e1", "event_type": "identity.fenced", "correlation_id": "r1"}
        headers = {"Authorization": "Bearer signed-token"}
        self.assertEqual(self.client.post("/pubsub/push", json=_payload(event), headers=headers).status_code, 204)
        self.assertEqual(self.client.post("/pubsub/push", json=_payload(event), headers=headers).status_code, 204)
        self.assertEqual(len(self.store.messages), 1)

    def test_push_rejects_wrong_workload_identity(self):
        client = TestClient(create_cloud_app(store=self.store, role="control",
            token_verifier=lambda token, audience: {"email": "attacker@example.com"}))
        response = client.post("/pubsub/push", json=_payload({}), headers={"Authorization": "Bearer token"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["code"], "PUSH_IDENTITY_DENIED")

    def test_invalid_push_fails_before_inbox(self):
        headers = {"Authorization": "Bearer signed-token"}
        response = self.client.post("/pubsub/push", json={"message": {"messageId": "m1", "data": "!!!"}}, headers=headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.store.messages, {})

    def test_agent_role_cannot_accept_pubsub(self):
        agent = TestClient(create_cloud_app(store=self.store, role="agent-v17"))
        self.assertEqual(agent.post("/pubsub/push").status_code, 404)
        self.assertEqual(agent.post("/internal/attempt-action").json()["role"], "agent-v17")


if __name__ == "__main__":
    unittest.main()

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi.testclient import TestClient

from continuum.api import create_app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.client = TestClient(create_app(data_root=Path(self.directory.name), demo_mode=True))

    def tearDown(self):
        self.directory.cleanup()

    def test_signature_moment_is_backed_by_server_evidence(self):
        started = self.client.post("/api/scenarios")
        self.assertEqual(started.status_code, 201)
        snapshot = started.json(); run_id = snapshot["run_id"]
        self.assertEqual(snapshot["provider"], {"vendor_count": 1, "duplicate_effects": 0})
        self.assertEqual(snapshot["attestation"]["body"]["outcome"], "VERIFIED")

        action = self.client.post(f"/api/scenarios/{run_id}/predecessor/action")
        self.assertEqual(action.status_code, 403)
        self.assertEqual(action.json()["detail"]["code"], "STALE_FENCE")
        self.assertFalse(action.json()["detail"]["effect_performed"])

        memory = self.client.post(f"/api/scenarios/{run_id}/predecessor/memory")
        self.assertEqual(memory.status_code, 403)
        self.assertEqual(memory.json()["detail"]["candidates_considered"], 0)

        replay = self.client.post(f"/api/scenarios/{run_id}/redeliver").json()
        self.assertEqual(replay, {"disposition": "DEDUPLICATED", "new_external_effect": False, "vendor_count": 1})
        self.assertEqual(len(self.client.get(f"/api/scenarios/{run_id}/contract").json()["artifacts"]), 6)

    def test_demo_mutations_fail_closed_by_default(self):
        client = TestClient(create_app(data_root=Path(self.directory.name), demo_mode=False))
        response = client.post("/api/scenarios")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["code"], "DEMO_MODE_DISABLED")

    def test_health_build_info_and_cockpit(self):
        self.assertEqual(self.client.get("/health").json()["status"], "ok")
        info = self.client.get("/build-info").json()
        self.assertEqual(info["framework"], "google-adk")
        page = self.client.get("/")
        self.assertIn("Agents can fail", page.text)


if __name__ == "__main__":
    unittest.main()

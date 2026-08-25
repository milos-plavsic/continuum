import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from continuum.cloud_scenario_adapters import AuthenticatedJsonClient, build_production_scenario_service


class Response:
    def __enter__(self): return self
    def __exit__(self, *args): return None
    def read(self): return json.dumps({"proposal": {"evidence_ids": ["e1"]}}).encode()


class CloudScenarioAdapterTests(unittest.TestCase):
    def test_private_worker_client_uses_adc_token_and_run_correlation(self):
        observed = {}
        def open_request(request, timeout):
            observed.update(request=request, timeout=timeout)
            return Response()
        client = AuthenticatedJsonClient(lambda audience: f"token-for:{audience}", open_request)
        result = client.post("https://v18.run.app/internal/investigate", {"event_id": "e1", "correlation_id": "a" * 32},
                             run_id="run-1")
        self.assertIn("proposal", result)
        self.assertEqual(observed["request"].get_header("Authorization"),
                         "Bearer token-for:https://v18.run.app")
        self.assertEqual(observed["request"].get_header("X-continuum-run-id"), "run-1")
        self.assertEqual(observed["request"].get_header("Traceparent"),
                         f"00-{'a' * 32}-0000000000000001-01")

    def test_production_factory_fails_closed_when_invocation_graph_is_incomplete(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(build_production_scenario_service())


if __name__ == "__main__":
    unittest.main()

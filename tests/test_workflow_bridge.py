from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest

from continuum.sdk import ContinuumClient, InProcessContinuum
from continuum.workflow_bridge import WorkflowEngineBridge, WorkflowTask


class WorkflowBridgeTests(unittest.TestCase):
    def task(self, **changes):
        values = dict(engine="temporal-compatible", namespace="operations",
            workflow_id="incident-7", task_id="restore", tenant_id="acme",
            principal_id="recovery-agent:v2", capability="service.restore",
            artifact_digest="sha256:v2", required_evidence=("health.recovered",),
            value_at_risk={"service": "checkout"})
        values.update(changes)
        return WorkflowTask(**values)

    def test_bridge_preserves_engine_ownership_and_converges_redelivery(self):
        effects = []
        runtime = InProcessContinuum(lambda payload: effects.append(payload) or "service://ok")
        bridge = WorkflowEngineBridge(ContinuumClient(runtime)); task = self.task()
        binding = bridge.bind(task)
        self.assertEqual(binding["host_engine_owns"], ["schedule", "timer", "retry", "task_state"])
        self.assertNotIn("retry", binding["continuum_owns"])
        first = bridge.complete(task, {"revision": "safe"})
        second = bridge.complete(task, {"revision": "safe"})
        self.assertFalse(first["continuity_receipt"]["deduplicated"])
        self.assertTrue(second["continuity_receipt"]["deduplicated"])
        self.assertEqual(len(effects), 1)
        with self.assertRaisesRegex(ValueError, "SDK_IDEMPOTENCY_CONFLICT"):
            bridge.complete(task, {"revision": "substituted"})
        with self.assertRaisesRegex(ValueError, "WORKFLOW_EFFECT_PAYLOAD_INVALID"):
            bridge.complete(task, [])

    def test_task_contract_and_example_are_cloud_neutral(self):
        invalid = [
            {"engine": ""}, {"namespace": "bad space"}, {"artifact_digest": ""},
            {"required_evidence": ()}, {"value_at_risk": []},
        ]
        for changes in invalid:
            with self.assertRaisesRegex(ValueError, "WORKFLOW_TASK_INVALID"):
                self.task(**changes)
        task = self.task()
        self.assertEqual(task.obligation_id,
                         "temporal-compatible:operations:incident-7:restore")
        self.assertNotIn("attempt", task.idempotency_key)
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, str(root / "examples/workflow_engine_companion.py")],
            cwd=root, check=True, capture_output=True, text=True)
        output = json.loads(result.stdout)
        self.assertEqual(output["effect_count"], 1)
        self.assertTrue(output["redelivery"]["continuity_receipt"]["deduplicated"])


if __name__ == "__main__":
    unittest.main()

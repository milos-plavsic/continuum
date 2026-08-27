"""Engine-neutral companion example; no Google or workflow-vendor package required."""
from __future__ import annotations

import json

from continuum.sdk import ContinuumClient, InProcessContinuum
from continuum.workflow_bridge import WorkflowEngineBridge, WorkflowTask


def run() -> dict:
    effects: list[dict] = []
    runtime = InProcessContinuum(
        lambda payload: effects.append(payload) or "queue://supplier-review/42")
    bridge = WorkflowEngineBridge(ContinuumClient(runtime))
    task = WorkflowTask(
        engine="workflow-engine", namespace="procurement", workflow_id="supplier-42",
        task_id="approve-review", tenant_id="acme", principal_id="procurement-agent:v19",
        capability="supplier.review.create", artifact_digest="sha256:agent-v19",
        required_evidence=("legal-identity.verified", "vat.verified"),
        value_at_risk={"currency": "EUR", "amount": 250000})
    binding = bridge.bind(task)
    first = bridge.complete(task, {"supplier_id": "synthetic-42"})
    redelivery = bridge.complete(task, {"supplier_id": "synthetic-42"})
    return {"binding": binding, "first": first, "redelivery": redelivery,
            "effect_count": len(effects), "evidence": runtime.evidence()}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))

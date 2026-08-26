"""Run with: python examples/local_sdk_consumer.py (no cloud credentials)."""
from __future__ import annotations

import json

from continuum.sdk import ContinuumClient, InProcessContinuum


def main() -> None:
    effects: list[dict[str, object]] = []

    def create_vendor(payload: dict[str, object]) -> str:
        effects.append(payload)
        return "local://vendors/vendor-042"

    runtime = InProcessContinuum(create_vendor)
    client = ContinuumClient(runtime)
    client.register_agent(
        principal_id="urn:example:career-agent:v2", tenant_id="example",
        capabilities=("vendor.create",), artifact_digest="sha256:example-v2")
    client.record_obligation(
        obligation_id="vendor-compliance-042", tenant_id="example",
        owner_principal="urn:example:career-agent:v2",
        required_evidence=("compliance.valid",),
        value_at_risk={"currency": "EUR", "amount": 250000})
    first = client.execute_idempotent(
        obligation_id="vendor-compliance-042",
        principal_id="urn:example:career-agent:v2", capability="vendor.create",
        idempotency_key="vendor-042:create:v1", payload={"vendor_id": "vendor-042"})
    second = client.execute_idempotent(
        obligation_id="vendor-compliance-042",
        principal_id="urn:example:career-agent:v2", capability="vendor.create",
        idempotency_key="vendor-042:create:v1", payload={"vendor_id": "vendor-042"})
    print(json.dumps({"first": first, "second": second, "effect_count": len(effects),
                      "evidence": runtime.evidence()}, sort_keys=True))


if __name__ == "__main__":
    main()

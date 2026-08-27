"""Second-domain proof: one rollback effect, no procurement or cloud dependency."""
from __future__ import annotations

import json

from continuum.sdk import ContinuumClient, InProcessContinuum


def run() -> dict:
    effects: list[dict] = []

    def rollback(payload: dict) -> str:
        effects.append(payload)
        return f"service://{payload['service']}/revision/{payload['target_revision']}"

    transport = InProcessContinuum(rollback)
    client = ContinuumClient(transport)
    client.register_agent(
        principal_id="incident-responder:v2", tenant_id="northwind",
        capabilities=("service.rollback",), artifact_digest="sha256:responder-v2",
    )
    client.record_obligation(
        obligation_id="restore-checkout-slo", tenant_id="northwind",
        owner_principal="incident-responder:v2",
        required_evidence=("deployment.regression_verified", "rollback.completed"),
        value_at_risk={"metric": "availability", "target": "99.95%"},
    )
    request = dict(
        obligation_id="restore-checkout-slo", principal_id="incident-responder:v2",
        capability="service.rollback", idempotency_key="checkout:rollback:2026-08-27",
        payload={"service": "checkout", "target_revision": "2026.08.26.4"},
    )
    first = client.execute_idempotent(**request)
    second = client.execute_idempotent(**request)
    return {"domain": "incident-remediation", "effect_count": len(effects),
            "first": first, "second": second, "evidence": transport.evidence()}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))

"""Cloud-neutral Continuum integration surface.

Applications need three calls: register an agent, record an obligation, and
execute a consequential effect with a stable idempotency key.  No cloud SDK is
imported here; hosted bindings implement the same transport protocol.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from .models import digest


class ContinuumTransport(Protocol):
    def register_agent(self, registration: dict[str, Any]) -> dict[str, Any]: ...
    def record_obligation(self, obligation: dict[str, Any]) -> dict[str, Any]: ...
    def execute_idempotent(self, request: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ContinuumClient:
    transport: ContinuumTransport

    def register_agent(self, *, principal_id: str, tenant_id: str,
                       capabilities: tuple[str, ...], artifact_digest: str) -> dict[str, Any]:
        return self.transport.register_agent({
            "principal_id": principal_id,
            "tenant_id": tenant_id,
            "capabilities": list(capabilities),
            "artifact_digest": artifact_digest,
        })

    def record_obligation(self, *, obligation_id: str, tenant_id: str,
                          owner_principal: str, required_evidence: tuple[str, ...],
                          value_at_risk: dict[str, Any]) -> dict[str, Any]:
        return self.transport.record_obligation({
            "obligation_id": obligation_id,
            "tenant_id": tenant_id,
            "owner_principal": owner_principal,
            "required_evidence": list(required_evidence),
            "value_at_risk": value_at_risk,
        })

    def execute_idempotent(self, *, obligation_id: str, principal_id: str,
                           capability: str, idempotency_key: str,
                           payload: dict[str, Any]) -> dict[str, Any]:
        return self.transport.execute_idempotent({
            "obligation_id": obligation_id,
            "principal_id": principal_id,
            "capability": capability,
            "idempotency_key": idempotency_key,
            "payload": payload,
        })


class InProcessContinuum:
    """Small reference transport proving adoption without a cloud migration."""

    def __init__(self, effect: Callable[[dict[str, Any]], str]):
        self.effect = effect
        self.agents: dict[str, dict[str, Any]] = {}
        self.obligations: dict[str, dict[str, Any]] = {}
        self.executions: dict[str, tuple[str, dict[str, Any]]] = {}
        self.events: list[dict[str, Any]] = []

    def register_agent(self, registration: dict[str, Any]) -> dict[str, Any]:
        required = {"principal_id", "tenant_id", "capabilities", "artifact_digest"}
        if set(registration) != required or not registration["principal_id"]:
            raise ValueError("SDK_AGENT_REGISTRATION_INVALID")
        principal = str(registration["principal_id"])
        prior = self.agents.get(principal)
        if prior is not None and prior != registration:
            raise ValueError("SDK_AGENT_IMMUTABLE_CONFLICT")
        self.agents[principal] = deepcopy(registration)
        return self._record("agent.registered", registration)

    def record_obligation(self, obligation: dict[str, Any]) -> dict[str, Any]:
        required = {"obligation_id", "tenant_id", "owner_principal",
                    "required_evidence", "value_at_risk"}
        if set(obligation) != required or obligation["owner_principal"] not in self.agents:
            raise ValueError("SDK_OBLIGATION_INVALID")
        obligation_id = str(obligation["obligation_id"])
        prior = self.obligations.get(obligation_id)
        if prior is not None and prior != obligation:
            raise ValueError("SDK_OBLIGATION_IMMUTABLE_CONFLICT")
        self.obligations[obligation_id] = deepcopy(obligation)
        return self._record("obligation.recorded", obligation)

    def execute_idempotent(self, request: dict[str, Any]) -> dict[str, Any]:
        required = {"obligation_id", "principal_id", "capability",
                    "idempotency_key", "payload"}
        if set(request) != required or not request["idempotency_key"]:
            raise ValueError("SDK_EXECUTION_INVALID")
        obligation = self.obligations.get(str(request["obligation_id"]))
        agent = self.agents.get(str(request["principal_id"]))
        if obligation is None or agent is None:
            raise ValueError("SDK_RESOURCE_NOT_FOUND")
        if obligation["owner_principal"] != request["principal_id"]:
            raise PermissionError("SDK_AUTHORITY_DENIED")
        if request["capability"] not in agent["capabilities"]:
            raise PermissionError("SDK_CAPABILITY_DENIED")
        request_digest = digest(request)
        key = str(request["idempotency_key"])
        prior = self.executions.get(key)
        if prior is not None:
            if prior[0] != request_digest:
                raise ValueError("SDK_IDEMPOTENCY_CONFLICT")
            return {**deepcopy(prior[1]), "deduplicated": True}
        provider_ref = self.effect(deepcopy(request["payload"]))
        receipt = self._record("effect.observed", {
            "obligation_id": request["obligation_id"],
            "principal_id": request["principal_id"],
            "request_digest": request_digest,
            "provider_ref": provider_ref,
        })
        result = {"provider_ref": provider_ref, "request_digest": request_digest,
                  "event_digest": receipt["event_digest"], "deduplicated": False}
        self.executions[key] = (request_digest, deepcopy(result))
        return result

    def evidence(self) -> dict[str, Any]:
        return {"profile": "continuum-local-sdk/1", "events": deepcopy(self.events),
                "chain_digest": digest(self.events)}

    def _record(self, event_type: str, body: dict[str, Any]) -> dict[str, Any]:
        event = {"sequence": len(self.events) + 1, "event_type": event_type,
                 "body": deepcopy(body)}
        event["event_digest"] = digest(event)
        self.events.append(event)
        return deepcopy(event)

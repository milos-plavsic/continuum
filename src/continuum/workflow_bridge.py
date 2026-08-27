"""Companion bridge for existing workflow engines.

The host engine keeps scheduling, retries, timers and task state. Continuum adds
an obligation, authority-bearing principal, stable effect identity and evidence
receipt around a task that may outlive or change executors.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from .sdk import ContinuumClient


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")


@dataclass(frozen=True)
class WorkflowTask:
    engine: str
    namespace: str
    workflow_id: str
    task_id: str
    tenant_id: str
    principal_id: str
    capability: str
    artifact_digest: str
    required_evidence: tuple[str, ...]
    value_at_risk: dict[str, Any]

    def __post_init__(self) -> None:
        identifiers = (self.engine, self.namespace, self.workflow_id, self.task_id,
                       self.tenant_id, self.principal_id, self.capability)
        if (any(not isinstance(value, str) or not _IDENTIFIER.fullmatch(value)
                for value in identifiers)
                or not isinstance(self.artifact_digest, str) or not self.artifact_digest
                or not self.required_evidence or not isinstance(self.value_at_risk, dict)):
            raise ValueError("WORKFLOW_TASK_INVALID")

    @property
    def obligation_id(self) -> str:
        return f"{self.engine}:{self.namespace}:{self.workflow_id}:{self.task_id}"

    @property
    def idempotency_key(self) -> str:
        # Deliberately excludes delivery/attempt number: retries converge.
        return f"{self.obligation_id}:effect:v1"


@dataclass(frozen=True)
class WorkflowEngineBridge:
    client: ContinuumClient

    def bind(self, task: WorkflowTask) -> dict[str, Any]:
        registration = self.client.register_agent(
            principal_id=task.principal_id, tenant_id=task.tenant_id,
            capabilities=(task.capability,), artifact_digest=task.artifact_digest)
        obligation = self.client.record_obligation(
            obligation_id=task.obligation_id, tenant_id=task.tenant_id,
            owner_principal=task.principal_id,
            required_evidence=task.required_evidence,
            value_at_risk=task.value_at_risk)
        return {
            "profile": "continuum-workflow-companion/1",
            "host_engine_owns": ["schedule", "timer", "retry", "task_state"],
            "continuum_owns": ["obligation", "authority", "memory_scope", "attestation"],
            "registration": registration,
            "obligation": obligation,
        }

    def complete(self, task: WorkflowTask, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("WORKFLOW_EFFECT_PAYLOAD_INVALID")
        receipt = self.client.execute_idempotent(
            obligation_id=task.obligation_id, principal_id=task.principal_id,
            capability=task.capability, idempotency_key=task.idempotency_key,
            payload=payload)
        return {
            "profile": "continuum-workflow-companion/1",
            "engine_ack": {"workflow_id": task.workflow_id, "task_id": task.task_id},
            "continuity_receipt": receipt,
        }

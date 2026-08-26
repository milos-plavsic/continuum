from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sqlite3
from typing import Iterable
from uuid import UUID, uuid5

from .models import (
    AgentStatus, AgentVersion, Denied, Event, PolicyDecision,
    TransferManifest, canonical, digest,
)

NAMESPACE = UUID("77265aca-4834-5ee3-9fc2-c1174f65f3e2")


class EventStore:
    def __init__(self, path: Path | None = None):
        self.path = path
        self.events: list[Event] = []

    def append(self, event: Event) -> Event:
        duplicate = next((item for item in self.events if item.event_id == event.event_id), None)
        if duplicate:
            if duplicate.to_dict() != event.to_dict():
                raise ValueError("EVENT_ID_CONTENT_CONFLICT")
            return duplicate
        expected = sum(e.aggregate_id == event.aggregate_id for e in self.events) + 1
        if event.aggregate_version != expected:
            raise ValueError("AGGREGATE_VERSION_CONFLICT")
        self.events.append(event)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(canonical(event.to_dict()) + "\n")
        return event

    def verify(self) -> bool:
        versions: dict[str, int] = {}
        for event in self.events:
            versions[event.aggregate_id] = versions.get(event.aggregate_id, 0) + 1
            if not event.valid() or event.aggregate_version != versions[event.aggregate_id]:
                return False
        return True

    def types(self) -> list[str]:
        return [event.event_type for event in self.events]


class AgentRegistry:
    def __init__(self):
        self.versions: dict[str, AgentVersion] = {}

    def register(self, version: AgentVersion) -> None:
        if version.version in self.versions:
            raise ValueError("IMMUTABLE_VERSION_EXISTS")
        if version.status == AgentStatus.ACTIVE and any(
            v.status == AgentStatus.ACTIVE and v.tenant_id == version.tenant_id
            and v.agent_id == version.agent_id for v in self.versions.values()
        ):
            raise ValueError("ACTIVE_VERSION_EXISTS")
        self.versions[version.version] = version

    def get(self, version: str) -> AgentVersion:
        return self.versions[version]

    def fence(self, version: str, expected_epoch: int) -> int:
        current = self.get(version)
        if current.epoch != expected_epoch or current.status != AgentStatus.ACTIVE:
            raise Denied("STALE_FENCE")
        next_epoch = expected_epoch + 1
        self.versions[version] = replace(current, status=AgentStatus.QUARANTINED, epoch=next_epoch)
        return next_epoch

    def activate(self, version: str, epoch: int) -> None:
        current = self.get(version)
        if current.status != AgentStatus.REGISTERED:
            raise ValueError("SUCCESSOR_NOT_REGISTERED")
        if any(v.status == AgentStatus.ACTIVE for v in self.versions.values()
               if v.tenant_id == current.tenant_id and v.agent_id == current.agent_id):
            raise ValueError("ACTIVE_VERSION_EXISTS")
        self.versions[version] = replace(current, status=AgentStatus.ACTIVE, epoch=epoch)

    def retire(self, version: str) -> None:
        current = self.get(version)
        if current.status != AgentStatus.QUARANTINED:
            raise ValueError("RETIRE_REQUIRES_QUARANTINE")
        self.versions[version] = replace(current, status=AgentStatus.RETIRED)

    def authorize(self, tenant: str, version: str, epoch: int, capability: str) -> AgentVersion:
        current = self.get(version)
        if current.tenant_id != tenant:
            raise Denied("RESOURCE_NOT_FOUND")
        if current.status != AgentStatus.ACTIVE or current.epoch != epoch:
            raise Denied("STALE_FENCE")
        if capability not in current.capabilities:
            raise Denied("CAPABILITY_DENIED")
        return current


class MemoryGateway:
    def __init__(self):
        self.grants: dict[str, set[str]] = {}
        self.revoked: set[str] = set()
        self.candidate_count = 0

    def grant(self, version: str, scopes: Iterable[str]) -> None:
        self.grants[version] = set(scopes)

    def revoke(self, version: str) -> None:
        self.revoked.add(version)

    def retrieve(self, version: str, scope: str) -> list[str]:
        if version in self.revoked:
            raise Denied("GRANT_REVOKED")
        if scope not in self.grants.get(version, set()):
            raise Denied("SCOPE_DENIED")
        self.candidate_count += 1
        return [f"authorized:{scope}"]


class VendorRegistry:
    """Persistent, separately stored provider boundary with idempotent writes."""
    def __init__(self, path: Path):
        self.connection = sqlite3.connect(path)
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS vendors (tenant TEXT, vendor TEXT, execution TEXT UNIQUE, payload_hash TEXT, PRIMARY KEY(tenant,vendor))"
        )

    def create(self, tenant: str, vendor: str, execution: str, payload_hash: str) -> str:
        self.connection.execute(
            "INSERT OR IGNORE INTO vendors VALUES (?,?,?,?)", (tenant, vendor, execution, payload_hash)
        )
        self.connection.commit()
        row = self.connection.execute("SELECT execution,payload_hash FROM vendors WHERE tenant=? AND vendor=?", (tenant, vendor)).fetchone()
        if row != (execution, payload_hash):
            raise Denied("PROVIDER_IDEMPOTENCY_CONFLICT")
        return f"vendor://{tenant}/{vendor}"

    def find_execution(self, execution: str) -> tuple[str, str] | None:
        row = self.connection.execute(
            "SELECT tenant,vendor,payload_hash FROM vendors WHERE execution=?", (execution,)
        ).fetchone()
        return (f"vendor://{row[0]}/{row[1]}", row[2]) if row else None

    def count(self) -> int:
        return self.connection.execute("SELECT COUNT(*) FROM vendors").fetchone()[0]

    def close(self) -> None:
        self.connection.close()


class ComplianceRegistry:
    """Append-only evidence boundary used as a hard action precondition."""

    def __init__(self):
        self._evidence: dict[str, tuple[str, str, str, str]] = {}

    def verify(self, *, evidence_id: str, tenant: str, obligation_id: str,
               subject: str, document_hash: str) -> str:
        if not evidence_id or not document_hash:
            raise Denied("COMPLIANCE_EVIDENCE_REQUIRED")
        binding = (tenant, obligation_id, subject, document_hash)
        previous = self._evidence.get(evidence_id)
        if previous is not None and previous != binding:
            raise Denied("COMPLIANCE_EVIDENCE_CONFLICT")
        self._evidence[evidence_id] = binding
        return digest({"evidence_id": evidence_id, "binding": binding, "status": "VERIFIED"})

    def authorize(self, *, evidence_id: str, tenant: str, obligation_id: str,
                  subject: str) -> str:
        if not evidence_id:
            raise Denied("COMPLIANCE_EVIDENCE_REQUIRED")
        evidence = self._evidence.get(evidence_id)
        if evidence is None:
            raise Denied("COMPLIANCE_EVIDENCE_NOT_VERIFIED")
        if evidence[:3] != (tenant, obligation_id, subject):
            raise Denied("COMPLIANCE_EVIDENCE_BINDING_MISMATCH")
        return evidence[3]


class ActionGateway:
    def __init__(self, registry: AgentRegistry, provider: VendorRegistry,
                 compliance: ComplianceRegistry):
        self.registry = registry
        self.provider = provider
        self.compliance = compliance
        self.executions: dict[str, tuple[str, str]] = {}

    def create_vendor(self, *, tenant: str, version: str, epoch: int, vendor: str,
                      obligation_id: str, compliance_evidence_id: str,
                      idempotency_key: str, decision_id: str) -> tuple[str, bool]:
        if not idempotency_key:
            raise Denied("IDEMPOTENCY_KEY_REQUIRED")
        if not decision_id:
            raise Denied("POLICY_DECISION_REQUIRED")
        self.registry.authorize(tenant, version, epoch, "vendor.create")
        evidence_hash = self.compliance.authorize(
            evidence_id=compliance_evidence_id,
            tenant=tenant,
            obligation_id=obligation_id,
            subject=vendor,
        )
        request_hash = digest({
            "tenant": tenant,
            "vendor": vendor,
            "obligation_id": obligation_id,
            "compliance_evidence_id": compliance_evidence_id,
            "compliance_document_hash": evidence_hash,
            "decision": decision_id,
        })
        previous = self.executions.get(idempotency_key)
        if previous:
            if previous[0] != request_hash:
                raise Denied("IDEMPOTENCY_KEY_CONFLICT")
            return previous[1], True
        execution_id = str(uuid5(NAMESPACE, idempotency_key))
        durable = self.provider.find_execution(execution_id)
        if durable:
            if durable[1] != request_hash:
                raise Denied("IDEMPOTENCY_KEY_CONFLICT")
            self.executions[idempotency_key] = (request_hash, durable[0])
            return durable[0], True
        provider_ref = self.provider.create(tenant, vendor, execution_id, request_hash)
        self.executions[idempotency_key] = (request_hash, provider_ref)
        return provider_ref, False


def decide_compromise(evidence: dict[str, str], known_event_ids: set[str]) -> PolicyDecision:
    if not set(evidence.values()).issubset(known_event_ids):
        raise Denied("FABRICATED_EVIDENCE_CITATION")
    required = {"injection", "anomalous_action", "missed_evidence"}
    approved = required.issubset(evidence)
    return PolicyDecision(
        decision_id=str(uuid5(NAMESPACE, "decision:" + canonical(evidence))),
        outcome="APPROVE_SUCCESSION" if approved else "INVESTIGATE_HOLD",
        reason_codes=("CORRELATED_COMPROMISE_SIGNALS",) if approved else ("INSUFFICIENT_EVIDENCE",),
        evidence_ids=tuple(sorted(evidence.values())),
    )


def validate_manifest(manifest: TransferManifest) -> None:
    forbidden = {"raw_untrusted_document", "secret", "revoked_private_notes"}
    if forbidden.intersection(manifest.memory_grants):
        raise Denied("UNSAFE_MANIFEST_CONTENT")
    if not forbidden.issubset(manifest.excluded_memory):
        raise Denied("MANIFEST_EXCLUSIONS_INCOMPLETE")

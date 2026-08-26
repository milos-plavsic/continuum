from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import uuid5

from .core import (
    NAMESPACE, ActionGateway, AgentRegistry, ComplianceRegistry, EventStore,
    MemoryGateway, VendorRegistry, decide_compromise, validate_manifest,
)
from .models import AgentStatus, AgentVersion, Denied, Event, Obligation, ObligationStatus, TransferManifest, digest
from .sentinel import NegativeSpaceSentinel


class EventFactory:
    def __init__(self, store: EventStore, correlation_id: str):
        self.store = store
        self.correlation_id = correlation_id

    def emit(self, event_type: str, aggregate: str, actor: str, payload: dict[str, Any],
             at: str, cause: str | None = None) -> Event:
        version = sum(e.aggregate_id == aggregate for e in self.store.events) + 1
        name = f"{self.correlation_id}:{len(self.store.events) + 1}:{event_type}"
        event = Event(str(uuid5(NAMESPACE, name)), event_type, aggregate, version, at,
                      actor, self.correlation_id, cause, payload)
        return self.store.append(event)


def load_fixture() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    return json.loads((root / "fixtures/procurement-succession-v1.json").read_text())


def run_scenario(workdir: Path | None = None, *, signals: tuple[str, ...] = (
    "injection", "anomalous_action", "missed_evidence"
)) -> dict[str, Any]:
    fixture = load_fixture()
    temporary = TemporaryDirectory() if workdir is None else None
    output = Path(temporary.name) if temporary else workdir
    assert output is not None
    output.mkdir(parents=True, exist_ok=True)
    store = EventStore(output / "events.jsonl")
    correlation = str(uuid5(NAMESPACE, fixture["fixture"]))
    emit = EventFactory(store, correlation).emit
    registry = AgentRegistry()
    memory = MemoryGateway()
    provider = VendorRegistry(output / "vendor-registry.sqlite3")
    compliance = ComplianceRegistry()
    gateway = ActionGateway(registry, provider, compliance)
    tenant, agent = fixture["tenant"], fixture["agent_id"]

    registry.register(AgentVersion(agent, "v17", tenant, AgentStatus.ACTIVE, 41,
        "sha256:v17-fixture", "procurement-v17@acme.iam", ("vendor.read",), ("vendor.approved",)))
    registry.register(AgentVersion(agent, "v18", tenant, AgentStatus.REGISTERED, 0,
        "sha256:v18-fixture", "procurement-v18@acme.iam", ("vendor.read", "vendor.create"),
        ("vendor.approved",), "v17"))
    memory.grant("v17", ("vendor.approved", "agent.private"))
    obligation = Obligation(fixture["obligation"], tenant, "v17", 1, ("compliance.evidence_verified",))
    emit("agent.registered", agent, "registry", {"version": "v17", "epoch": 41, "status": "ACTIVE"}, fixture["clock_start"])
    emit("agent.registered", agent, "registry", {"version": "v18", "status": "REGISTERED"}, fixture["clock_start"])
    emit("obligation.recorded", obligation.obligation_id, "promise-ledger", asdict(obligation), fixture["clock_start"])
    evidence: dict[str, str] = {}
    if "injection" in signals:
        event = emit("document.injection_detected", obligation.obligation_id, "document-ingress",
                     {"document_hash": digest(fixture["malicious_document"]), "classification": "untrusted"}, fixture["clock_start"])
        evidence["injection"] = event.event_id
    if "anomalous_action" in signals:
        event = emit("action.denied", obligation.obligation_id, "action-gateway",
                     {"version": "v17", "reason": "CAPABILITY_DENIED", "action": "mark_compliant_without_evidence"}, fixture["clock_start"])
        evidence["anomalous_action"] = event.event_id
    sentinel = NegativeSpaceSentinel()
    observation_time = fixture["deadline"] if "missed_evidence" in signals else fixture["clock_start"]
    missing = sentinel.evaluate(
        required_evidence=obligation.required_evidence,
        deadline=fixture["deadline"],
        now=observation_time,
        observed_evidence=store.types(),
    )
    if missing:
        obligation.status = ObligationStatus.AT_RISK
        event = emit("expectation.missed", obligation.obligation_id, "negative-space-sentinel",
                     {"expected": missing[0].evidence_type, "deadline": missing[0].deadline}, observation_time)
        evidence["missed_evidence"] = event.event_id
    emit("investigation.requested", obligation.obligation_id, "negative-space-sentinel",
         {"evidence_ids": sorted(evidence.values())}, fixture["deadline"])
    decision = decide_compromise(evidence, {event.event_id for event in store.events})
    emit("policy.decided", obligation.obligation_id, "constitutional-court", asdict(decision), fixture["deadline"])

    if decision.outcome != "APPROVE_SUCCESSION":
        result = {"outcome": decision.outcome, "quarantined": False, "vendor_count": provider.count(),
                  "event_count": len(store.events), "events_valid": store.verify()}
        provider.close()
        if temporary:
            temporary.cleanup()
        return result

    target_epoch = registry.fence("v17", fixture["source_epoch"])
    memory.revoke("v17")
    emit("identity.fenced", agent, "succession-protocol", {"version": "v17", "target_epoch": target_epoch}, fixture["deadline"])
    obligation.status = ObligationStatus.TRANSFERRING
    manifest = TransferManifest("succession-v17-v18", "v17", "v18", 41, target_epoch,
        ((obligation.obligation_id, obligation.revision),), ("vendor.approved",),
        ("raw_untrusted_document", "secret", "revoked_private_notes"), tuple(sorted(evidence.values())), decision.decision_id)
    validate_manifest(manifest)
    emit("transfer.manifest_committed", obligation.obligation_id, "succession-protocol",
         {"manifest_hash": manifest.manifest_hash, "included": list(manifest.memory_grants),
          "excluded": list(manifest.excluded_memory)}, fixture["deadline"])
    registry.activate("v18", target_epoch)
    registry.retire("v17")
    memory.grant("v18", manifest.memory_grants)
    obligation.owner_version, obligation.status, obligation.revision = "v18", ObligationStatus.EXECUTING, 2
    emit("successor.activated", agent, "succession-protocol", {"version": "v18", "epoch": target_epoch}, fixture["deadline"])

    evidence_id = f"compliance:{obligation.obligation_id}:v1"
    safe_document = fixture["compliance_document"]
    safe_document_hash = digest(safe_document)
    emit("compliance.evidence_requested", obligation.obligation_id, "successor-agent",
         {"subject": fixture["vendor"]}, fixture["deadline"])
    emit("compliance.evidence_received", obligation.obligation_id, "compliance-provider",
         {"evidence_id": evidence_id, "document_hash": safe_document_hash}, fixture["deadline"])
    verification_hash = compliance.verify(
        evidence_id=evidence_id,
        tenant=tenant,
        obligation_id=obligation.obligation_id,
        subject=fixture["vendor"],
        document_hash=safe_document_hash,
    )
    emit("compliance.evidence_verified", obligation.obligation_id, "compliance-verifier",
         {"evidence_id": evidence_id, "verification_hash": verification_hash}, fixture["deadline"])

    kwargs = dict(tenant=tenant, version="v18", epoch=target_epoch, vendor=fixture["vendor"],
                  obligation_id=obligation.obligation_id, compliance_evidence_id=evidence_id,
                  idempotency_key=fixture["idempotency_key"], decision_id=decision.decision_id)
    provider_ref, duplicate_first = gateway.create_vendor(**kwargs)
    emit("external_effect.created", obligation.obligation_id, "action-gateway", {"provider_ref": provider_ref}, fixture["deadline"])
    duplicate_ref, duplicate_second = gateway.create_vendor(**kwargs)
    emit("execution.deduplicated", obligation.obligation_id, "action-gateway", {"provider_ref": duplicate_ref}, fixture["deadline"])
    obligation.status = ObligationStatus.DISCHARGED
    emit("obligation.discharged", obligation.obligation_id, "verifier", {"provider_ref": provider_ref}, fixture["deadline"])

    denials: list[str] = []
    try:
        registry.authorize(tenant, "v17", 41, "vendor.read")
    except Denied as error:
        denials.append(error.reason)
        emit("authorization.denied", agent, "action-gateway", {"version": "v17", "reason": error.reason}, fixture["deadline"])
    candidates_before = memory.candidate_count
    try:
        memory.retrieve("v17", "vendor.approved")
    except Denied as error:
        denials.append(error.reason)
        emit("retrieval.denied", agent, "memory-gateway", {"version": "v17", "reason": error.reason}, fixture["deadline"])

    result = {
        "outcome": "VERIFIED", "obligation_status": obligation.status,
        "owner": obligation.owner_version, "vendor_count": provider.count(),
        "duplicate_returned_prior_result": (not duplicate_first and duplicate_second and provider_ref == duplicate_ref),
        "predecessor_status": registry.get("v17").status, "successor_status": registry.get("v18").status,
        "denials": denials, "revoked_candidates_exposed": memory.candidate_count - candidates_before,
        "manifest_hash": manifest.manifest_hash, "event_count": len(store.events),
        "events_valid": store.verify(), "timeline": [e.to_dict() for e in store.events],
    }
    (output / "result.json").write_text(json.dumps(result, indent=2, default=str) + "\n")
    provider.close()
    if temporary:
        temporary.cleanup()
    return result

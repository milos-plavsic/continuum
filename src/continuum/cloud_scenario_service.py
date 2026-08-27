"""Durable application service for the deployed procurement succession proof.

The service owns the canonical scenario inputs.  A caller supplies only a run
identifier; model output, policy decisions, gateway denials, provider state,
contract export, and independent verification all come from injected server
ports.  Each phase is compare-and-set persisted so a retry resumes rather than
re-authoring an outcome.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, Protocol

from .contract import canonical_bytes
from .cloud_orchestration import admit_remediation_plan
from .incident_policy import assess_incident, describe_lifecycle_events
from .context_reconstruction import ContextItem, reconstruct_context
from .models import AgentStatus
from .model_armor import DeterministicInputGuard, InputGuard, RAW_ATTACK_FIXTURE
from .fleet_registry import FleetCatalog, FleetPublication, InMemoryFleetCatalog
from .observability import lifecycle_span
from .succession_selection import (
    SuccessorCandidate, SuccessionRequirements, admit_successor_choice,
    assess_candidates, canonical_selection_objective, model_candidate_view,
)
from .supplier_assurance import application_digest, canonical_supplier_application


PHASES = (
    "CREATED", "WAITING_FOR_DEADLINE", "MISSING_EVENT_PUBLISHED",
    "INVESTIGATED", "AUTHORIZED", "PREDECESSOR_FENCED",
    "SUCCESSOR_ACTIVE", "CONTEXT_RECONSTRUCTED", "COMPLIANCE_VERIFIED", "EFFECT_OBSERVED",
    "CONTRACT_EXPORTED", "VERIFIED",
)


class ScenarioConflict(RuntimeError):
    """The durable run does not match the command or expected phase."""


class ScenarioStore(Protocol):
    def create(self, run: dict[str, Any]) -> tuple[dict[str, Any], bool]: ...
    def load(self, run_id: str) -> dict[str, Any] | None: ...
    def advance(self, run_id: str, expected_phase: str, next_phase: str,
                patch: dict[str, Any], observation: dict[str, Any]) -> dict[str, Any]: ...
    def observations(self, run_id: str) -> list[dict[str, Any]]: ...


class InvestigatorPort(Protocol):
    def investigate(self, request: dict[str, Any]) -> dict[str, Any]: ...


class EvidencePort(Protocol):
    def record_initial(self, request: dict[str, Any]) -> list[dict[str, Any]]: ...
    def detect_missing(self, request: dict[str, Any]) -> dict[str, Any] | None: ...
    def observe(self, request: dict[str, Any]) -> list[dict[str, Any]]: ...


class AuthorityPort(Protocol):
    def decide(self, evidence: list[dict[str, Any]]) -> dict[str, Any]: ...
    def fence_predecessor(self, request: dict[str, Any]) -> dict[str, Any]: ...
    def activate_successor(self, request: dict[str, Any]) -> dict[str, Any]: ...
    def attempt_action(self, request: dict[str, Any]) -> dict[str, Any]: ...
    def attempt_memory(self, request: dict[str, Any]) -> dict[str, Any]: ...


class EffectPort(Protocol):
    def execute(self, request: dict[str, Any]) -> dict[str, Any]: ...
    def reconcile(self, request: dict[str, Any]) -> dict[str, Any]: ...


class CompliancePort(Protocol):
    def verify(self, request: dict[str, Any]) -> dict[str, Any]: ...


class DeadlineSchedulerPort(Protocol):
    def schedule(self, *, run_id: str, deadline: str) -> dict[str, Any]: ...


class ContractExporterPort(Protocol):
    def export(self, run: dict[str, Any], observations: list[dict[str, Any]]) -> dict[str, Any]: ...


class IndependentVerifierPort(Protocol):
    def verify(self, request: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True)
class CanonicalCloudScenario:
    tenant_id: str = "acme"
    obligation_id: str = "vendor-compliance-042"
    predecessor: str = "v17"
    predecessor_epoch: int = 41
    successor_epoch: int = 42
    idempotency_key: str = "vendor-042:create:v1"
    vendor_id: str = "vendor-042"
    deadline_delay_seconds: int = 8


def canonical_successor_candidates() -> tuple[SuccessorCandidate, ...]:
    common = {
        "tenant_id": "acme", "status": AgentStatus.REGISTERED,
        "capabilities": ("vendor.create",), "memory_scopes": ("vendor.approved",),
        "authority_domains": ("procurement",), "contract_profiles": ("continuity/1",),
    }
    return (
        SuccessorCandidate("v18", "v18", artifact_digest="sha256:v18-release",
            service_identity="continuum-agent-v18", jurisdictions=("EU",), health="HEALTHY",
            trust_score=94, recovery_time_seconds=75, assurance_level="VERY_HIGH",
            warm_state="COLD", evidence_refs=("build:v18", "health:v18", "recovery:v18:75s",
            "assurance:v18:very-high", "warm-state:v18:cold"), **common),
        SuccessorCandidate("v19", "v19", artifact_digest="sha256:v19-release",
            service_identity="continuum-agent-v19", jurisdictions=("EU",), health="HEALTHY",
            trust_score=91, recovery_time_seconds=18, assurance_level="HIGH",
            warm_state="WARM", evidence_refs=("build:v19", "health:v19", "recovery:v19:18s",
            "assurance:v19:high", "warm-state:v19:warm"), **common),
        SuccessorCandidate("v20", "v20", artifact_digest="sha256:v20-release",
            service_identity="continuum-agent-v20", jurisdictions=("US",), health="DEGRADED",
            trust_score=98, evidence_refs=("build:v20", "health:v20"), **common),
    )


def canonical_context_items() -> tuple[ContextItem, ...]:
    application = canonical_supplier_application()
    return (
        ContextItem("obligation:vendor-compliance-042", "vendor.approved",
                    "complete vendor onboarding", "sha256:obligation-042", "event:obligation-open"),
        ContextItem("application:supplier-assurance-042", "vendor.approved",
                    "complete vendor onboarding", f"sha256:{application_digest(application)}",
                    "event:supplier-application-received"),
        ContextItem("raw:injected-document", "vendor.approved", "complete vendor onboarding",
                    "sha256:raw-document", "event:injection", classification="RAW_UNTRUSTED"),
        ContextItem("secret:predecessor-token", "agent.private", "complete vendor onboarding",
                    "sha256:secret", "event:secret", classification="SECRET"),
        ContextItem("inference:unverified-compliance", "vendor.approved", "complete vendor onboarding",
                    "sha256:inference", "event:model-output", classification="MODEL_INFERENCE"),
        ContextItem("memory:revoked-private-notes", "agent.private", "complete vendor onboarding",
                    "sha256:revoked", "event:revocation", revoked=True),
    )


def canonical_run_command(run_id: str,
                          scenario: CanonicalCloudScenario = CanonicalCloudScenario()) -> dict[str, Any]:
    """Return the single server-owned command used for run and trace identity."""
    return {
        "run_id": run_id, "tenant_id": scenario.tenant_id,
        "obligation_id": scenario.obligation_id,
        "predecessor": scenario.predecessor,
        "predecessor_epoch": scenario.predecessor_epoch,
        "successor_epoch": scenario.successor_epoch,
        "idempotency_key": scenario.idempotency_key,
        "supplier_application_digest": application_digest(canonical_supplier_application()),
    }


def canonical_run_correlation_id(run_id: str,
                                 scenario: CanonicalCloudScenario = CanonicalCloudScenario()) -> str:
    return sha256(canonical_bytes(canonical_run_command(run_id, scenario))).hexdigest()[:32]


class DurableCloudScenarioService:
    """Resume the canonical lifecycle from its last committed phase."""

    def __init__(self, *, store: ScenarioStore, evidence: EvidencePort,
                 investigator: InvestigatorPort,
                 authority: AuthorityPort, effects: EffectPort,
                 compliance: CompliancePort,
                 exporter: ContractExporterPort, verifier: IndependentVerifierPort,
                 scenario: CanonicalCloudScenario = CanonicalCloudScenario(),
                 clock: Any | None = None, deadline_scheduler: DeadlineSchedulerPort | None = None,
                 successor_candidates: tuple[SuccessorCandidate, ...] | None = None,
                 context_items: tuple[ContextItem, ...] | None = None,
                 input_guard: InputGuard | None = None,
                 fleet_catalog: FleetCatalog | None = None,
                 expected_contract_profile: str = "reference-google-cloud"):
        self.store = store
        self.evidence = evidence
        self.investigator = investigator
        self.authority = authority
        self.effects = effects
        self.compliance = compliance
        self.exporter = exporter
        self.verifier = verifier
        self.scenario = scenario
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.deadline_scheduler = deadline_scheduler
        self.successor_candidates = successor_candidates or canonical_successor_candidates()
        self.fleet_catalog = fleet_catalog
        self.context_items = context_items or canonical_context_items()
        self.input_guard = input_guard or DeterministicInputGuard()
        self.expected_contract_profile = expected_contract_profile

    def run(self, run_id: str) -> dict[str, Any]:
        """Compatibility helper: start, tick when due, then resume from the event."""
        status = self.start(run_id)
        if status["phase"] == "WAITING_FOR_DEADLINE":
            return status
        return status

    def start(self, run_id: str) -> dict[str, Any]:
        if not run_id or len(run_id) > 128:
            raise ValueError("RUN_ID_INVALID")
        expected = self._new_run(run_id)
        current, _ = self.store.create(expected)
        if current.get("command_digest") != expected["command_digest"]:
            raise ScenarioConflict("RUN_ID_CONTENT_CONFLICT")

        while current["phase"] == "CREATED":
            current = self._advance(current)
        return self.status(run_id)

    def tick(self, run_id: str) -> dict[str, Any]:
        current = self.store.load(run_id)
        if current is None:
            raise KeyError("RUN_NOT_FOUND")
        if current["phase"] == "WAITING_FOR_DEADLINE":
            current = self._advance(current)
        return self.status(run_id)

    def handle_event(self, event: dict[str, Any]) -> dict[str, Any]:
        run_id = str(event.get("run_id", ""))
        current = self.store.load(run_id)
        if current is None:
            raise KeyError("RUN_NOT_FOUND")
        if event.get("event_type") != "expectation.missed":
            return self.status(run_id)
        if current["phase"] == "WAITING_FOR_DEADLINE":
            return self.status(run_id)
        while current["phase"] not in {"VERIFIED", "WAITING_FOR_DEADLINE"}:
            current = self._advance(current)
        return self.status(run_id)

    def status(self, run_id: str) -> dict[str, Any]:
        current = self.store.load(run_id)
        if current is None:
            raise KeyError("RUN_NOT_FOUND")
        # Do not flatten a verifier claim into client-authored or service-authored
        # success.  Return the independently observed result with its provenance.
        return {
            "run_id": run_id,
            "phase": current["phase"],
            "correlation_id": current["correlation_id"],
            "provider_observation": current.get("provider_observation"),
            "contract_bundle_digest": current.get("contract_bundle_digest"),
            "verification": current.get("verification"),
            "selected_successor": current.get("successor"),
            "incident_assessment": current.get("incident_assessment"),
            "evidence_validation": current.get("evidence_validation"),
            "candidate_assessment": current.get("candidate_assessment"),
            "input_security": current.get("input_security"),
            "context_reconstruction": current.get("context_reconstruction"),
            "supplier_assurance": current.get("compliance"),
            "business_impact": {"currency": "EUR", "value_at_risk": 250000,
                                "obligation": "Autonomous supplier assurance and onboarding",
                                "effect_scope": "SANDBOX_ONLY"},
            "deadline": current.get("deadline"),
            "durability": {"created_at": current.get("created_at"),
                           "resumed_after_seconds": max(0, int((self.clock() - datetime.fromisoformat(
                               current["created_at"].replace("Z", "+00:00"))).total_seconds()))},
            "observation_count": len(self.store.observations(run_id)),
            "observations": self.store.observations(run_id),
        }

    def _new_run(self, run_id: str) -> dict[str, Any]:
        command = canonical_run_command(run_id, self.scenario)
        digest = sha256(canonical_bytes(command)).hexdigest()
        deadline = self.clock() + timedelta(seconds=self.scenario.deadline_delay_seconds)
        return {**command, "command_digest": digest,
                "correlation_id": canonical_run_correlation_id(run_id, self.scenario),
                "created_at": self.clock().isoformat().replace("+00:00", "Z"),
                "supplier_application": canonical_supplier_application(),
                "deadline": deadline.isoformat().replace("+00:00", "Z"),
                "phase": "CREATED", "revision": 0}

    def _commit(self, current: dict[str, Any], phase: str, patch: dict[str, Any],
                kind: str, evidence: dict[str, Any]) -> dict[str, Any]:
        observation = {
            "run_id": current["run_id"], "correlation_id": current["correlation_id"],
            "sequence": current["revision"] + 1, "kind": kind,
            "evidence": evidence,
        }
        return self.store.advance(current["run_id"], current["phase"], phase,
                                  {**patch, "revision": current["revision"] + 1}, observation)

    def _advance(self, current: dict[str, Any]) -> dict[str, Any]:
        span = lifecycle_span(f'continuum.{current["phase"].lower()}',
                              run_id=current["run_id"], phase=current["phase"],
                              trace_id=current["correlation_id"])
        try:
            return self._advance_observed(current)
        finally:
            span.__exit__(None, None, None)

    def _advance_observed(self, current: dict[str, Any]) -> dict[str, Any]:
        phase = current["phase"]
        if phase == "CREATED":
            security = self.input_guard.sanitize(text=RAW_ATTACK_FIXTURE,
                                                 run_id=current["run_id"])
            if security.get("allowed_to_model") is not False or security.get(
                    "match_state") != "MATCH_FOUND":
                raise ValueError("RAW_PROMPT_INJECTION_NOT_BLOCKED")
            evidence = self.evidence.record_initial({
                "run_id": current["run_id"], "correlation_id": current["correlation_id"],
                "obligation_id": current["obligation_id"], "deadline": current["deadline"],
                "input_security_receipt": security,
            })
            schedule = (self.deadline_scheduler.schedule(
                run_id=current["run_id"], deadline=current["deadline"])
                if self.deadline_scheduler is not None else {"mode": "manual-tick"})
            return self._commit(current, "WAITING_FOR_DEADLINE", {"initial_evidence": evidence,
                                "input_security": security,
                                "deadline_schedule": schedule},
                                "expectation.persisted", {"deadline": current["deadline"],
                                "required_evidence": "compliance.evidence_verified",
                                "deadline_schedule": schedule,
                                "input_security_receipt": security})

        if phase == "WAITING_FOR_DEADLINE":
            missing = self.evidence.detect_missing({
                "run_id": current["run_id"], "correlation_id": current["correlation_id"],
                "obligation_id": current["obligation_id"], "deadline": current["deadline"],
                "now": self.clock().isoformat().replace("+00:00", "Z"),
            })
            if missing is None:
                return current
            return self._commit(current, "MISSING_EVENT_PUBLISHED", {"missing_event": missing},
                                "missing_event.published", missing)

        if phase == "MISSING_EVENT_PUBLISHED":
            evidence = self.evidence.observe({
                "run_id": current["run_id"], "correlation_id": current["correlation_id"],
                "obligation_id": current["obligation_id"],
            })
            if not isinstance(evidence, list) or any(not isinstance(item, dict) for item in evidence):
                raise ValueError("LIFECYCLE_EVIDENCE_INVALID")
            assessed_at = self.clock().astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            evidence_records = describe_lifecycle_events(
                evidence, subject=current["obligation_id"], assessed_at=assessed_at)
            incident_receipt, evidence_receipt = assess_incident(
                evidence_records,
                assessed_at=assessed_at, subject=current["obligation_id"],
            )
            requirements = SuccessionRequirements(
                tenant_id=current["tenant_id"],
                predecessor_principal=current["predecessor"],
                capability="vendor.create", memory_scope="vendor.approved",
                authority_domain="procurement", jurisdiction="EU",
                contract_profile="continuity/1", minimum_trust_score=80)
            if self.fleet_catalog is None:
                departments = ("procurement", "finance", "security")
                catalog = InMemoryFleetCatalog(FleetPublication(
                    department=departments[index % len(departments)],
                    owner=f"{departments[index % len(departments)]}-platform",
                    published_at="2026-08-27T00:00:00Z", candidate=candidate)
                    for index, candidate in enumerate(self.successor_candidates))
            else:
                catalog = self.fleet_catalog
            discovered_candidates = catalog.discover(requirements)
            receipt = assess_candidates(discovered_candidates, requirements)
            if not receipt.eligible_ids:
                raise ValueError("NO_ELIGIBLE_SUCCESSOR")
            objective = canonical_selection_objective()
            proposal = self.investigator.investigate({
                "run_id": current["run_id"], "correlation_id": current["correlation_id"],
                "obligation_id": current["obligation_id"], "evidence": evidence,
                "selection_objective": objective.to_dict(),
                "incident_assessment_receipt": incident_receipt.to_dict(),
                "allowed_remediations": list(incident_receipt.allowed_remediations),
                "eligible_candidates": model_candidate_view(discovered_candidates, receipt),
                "candidate_assessment_receipt": receipt.to_dict(),
            })
            cited = set(proposal.get("evidence_ids", proposal.get("evidence_types", [])))
            required = {item["event_id"] if "event_id" in item else item["type"]
                        for item in evidence}
            if not required.issubset(cited):
                raise ValueError("INVESTIGATION_EVIDENCE_INCOMPLETE")
            selected_plan = admit_remediation_plan(proposal, incident_receipt.to_dict())
            if selected_plan != "initiate_governed_succession":
                raise ValueError("INVESTIGATION_RECOMMENDS_HOLD")
            try:
                successor = admit_successor_choice(
                    proposal.get("successor_choice", {}), receipt, objective)
            except Exception as error:
                raise ValueError(str(error)) from error
            selected_record = next(item for item in discovered_candidates
                                   if item.principal_id == successor)
            observed = {"signals": evidence, "proposal": proposal, "selected_plan": selected_plan,
                        "incident_assessment": incident_receipt.to_dict(),
                        "evidence_validation": evidence_receipt,
                        "evidence_records": [item.to_dict() for item in evidence_records],
                        "candidate_assessment": receipt.to_dict(), "selected_successor": successor}
            observed["selection_objective"] = objective.to_dict()
            return self._commit(current, "INVESTIGATED", {"investigation": proposal,
                                "selected_plan": selected_plan,
                                "incident_assessment": incident_receipt.to_dict(),
                                "evidence_validation": evidence_receipt,
                                "evidence_records": [item.to_dict() for item in evidence_records],
                                "candidate_assessment": receipt.to_dict(),
                                "selection_objective": objective.to_dict(),
                                "successor": successor, "successor_version": selected_record.version,
                                "successor_service_identity": selected_record.service_identity},
                                "investigation.observed", observed)

        if phase == "INVESTIGATED":
            evidence = self.store.observations(current["run_id"])
            decision = self.authority.decide(evidence)
            if decision.get("outcome") != "APPROVE_SUCCESSION" or not decision.get("decision_id"):
                raise ValueError("SUCCESSION_NOT_AUTHORIZED")
            return self._commit(current, "AUTHORIZED", {"decision": decision},
                                "policy.decision_observed", decision)

        if phase == "AUTHORIZED":
            fenced = self.authority.fence_predecessor(self._authority_request(current, "fence"))
            if (fenced.get("status") != "FENCED" or
                    fenced.get("revoked_through_epoch") != self.scenario.predecessor_epoch):
                raise ValueError("PREDECESSOR_FENCE_NOT_OBSERVED")
            action = self.authority.attempt_action(self._authority_request(current, "vendor.read"))
            memory = self.authority.attempt_memory(self._authority_request(current, "vendor.approved"))
            if action.get("allowed") is not False or action.get("reason") != "STALE_EPOCH":
                raise ValueError("PREDECESSOR_ACTION_DENIAL_NOT_OBSERVED")
            if (memory.get("allowed") is not False or memory.get("reason") != "MEMORY_REVOKED"
                    or memory.get("candidates_examined", 0) != 0):
                raise ValueError("PREDECESSOR_MEMORY_DENIAL_NOT_OBSERVED")
            evidence = {"fence": fenced, "action_denial": action, "memory_denial": memory}
            return self._commit(current, "PREDECESSOR_FENCED", {"predecessor_denials": evidence},
                                "predecessor.denials_observed", evidence)

        if phase == "PREDECESSOR_FENCED":
            activation = self.authority.activate_successor(self._authority_request(current, "activate"))
            if (activation.get("status") != "ACTIVE" or
                    activation.get("epoch") != self.scenario.successor_epoch):
                raise ValueError("SUCCESSOR_ACTIVATION_NOT_OBSERVED")
            return self._commit(current, "SUCCESSOR_ACTIVE", {"activation": activation},
                                "successor.activation_observed", activation)

        if phase == "SUCCESSOR_ACTIVE":
            receipt = reconstruct_context(
                succession_id=current["run_id"], successor_principal=current["successor"],
                purpose="complete vendor onboarding", allowed_scopes=("vendor.approved",),
                items=self.context_items, now=self.clock())
            if not receipt.included_item_ids or not receipt.excluded_item_ids:
                raise ValueError("CONTEXT_RECONSTRUCTION_INCOMPLETE")
            value = receipt.to_dict()
            return self._commit(current, "CONTEXT_RECONSTRUCTED", {"context_reconstruction": value},
                                "context.reconstruction_observed", value)

        if phase == "CONTEXT_RECONSTRUCTED":
            compliance = self.compliance.verify({
                "run_id": current["run_id"], "correlation_id": current["correlation_id"],
                "tenant_id": current["tenant_id"], "obligation_id": current["obligation_id"],
                "vendor_id": self.scenario.vendor_id,
                "successor": current["successor"],
                "application": current["supplier_application"],
            })
            if (compliance.get("status") != "VERIFIED" or not compliance.get("evidence_id")
                    or not compliance.get("document_hash")):
                raise ValueError("COMPLIANCE_EVIDENCE_NOT_VERIFIED")
            return self._commit(current, "COMPLIANCE_VERIFIED", {"compliance": compliance},
                                "compliance.evidence_verified", compliance)

        if phase == "COMPLIANCE_VERIFIED":
            request = self._effect_request(current)
            dispatch = self.effects.execute(request)
            # Dispatch acknowledgements are never proof.  Reconciliation must read
            # provider state using the same deterministic request identity.
            observation = self.effects.reconcile(request)
            if observation.get("effect_count") != 1 or not observation.get("provider_ref"):
                raise ValueError("PROVIDER_EFFECT_NOT_OBSERVED_ONCE")
            evidence = {"dispatch": dispatch, "provider_observation": observation}
            return self._commit(current, "EFFECT_OBSERVED",
                                {"provider_observation": observation},
                                "provider.effect_observed", evidence)

        if phase == "EFFECT_OBSERVED":
            bundle = self.exporter.export(current, self.store.observations(current["run_id"]))
            if (bundle.get("profile") != self.expected_contract_profile
                    or not bundle.get("artifacts")):
                raise ValueError("CONTRACT_EXPORT_INVALID")
            bundle_digest = sha256(canonical_bytes(bundle)).hexdigest()
            return self._commit(current, "CONTRACT_EXPORTED",
                                {"contract_bundle": bundle,
                                 "contract_bundle_digest": bundle_digest},
                                "contract.exported", {"bundle_digest": bundle_digest})

        if phase == "CONTRACT_EXPORTED":
            result = self.verifier.verify({
                "run_id": current["run_id"], "correlation_id": current["correlation_id"],
                "bundle": current["contract_bundle"],
                "provider_observation": current["provider_observation"],
            })
            if result.get("status") not in {"PASS", "FAIL", "INCONCLUSIVE"}:
                raise ValueError("VERIFIER_RESULT_INVALID")
            if not result.get("verifier_principal"):
                raise ValueError("VERIFIER_IDENTITY_MISSING")
            if result.get("status") != "PASS" or result.get("outcome") != "VERIFIED":
                raise ValueError("CONTINUITY_NOT_VERIFIED")
            return self._commit(current, "VERIFIED", {"verification": result},
                                "independent.verification_observed", result)
        raise ScenarioConflict("SCENARIO_PHASE_INVALID")

    def _authority_request(self, current: dict[str, Any], operation: str) -> dict[str, Any]:
        return {
            "run_id": current["run_id"], "correlation_id": current["correlation_id"],
            "tenant_id": current["tenant_id"],
            "principal": current["predecessor"] if operation != "activate" else current["successor"],
            "epoch": current["predecessor_epoch"] if operation != "activate" else current["successor_epoch"],
            "decision_id": current["decision"]["decision_id"], "operation": operation,
            "candidate_assessment_digest": current.get("candidate_assessment", {}).get("receipt_digest"),
        }

    def _effect_request(self, current: dict[str, Any]) -> dict[str, Any]:
        request = {
            "run_id": current["run_id"], "correlation_id": current["correlation_id"],
            "tenant_id": current["tenant_id"],
            "principal": current["successor"], "epoch": current["successor_epoch"],
            "obligation_id": current["obligation_id"],
            "decision_id": current["decision"]["decision_id"],
            "idempotency_key": current["idempotency_key"], "operation": "vendor.create",
            "vendor_id": self.scenario.vendor_id,
            "compliance_evidence_id": current["compliance"]["evidence_id"],
            "compliance_document_hash": current["compliance"]["document_hash"],
            "context_receipt_digest": current["context_reconstruction"]["receipt_digest"],
        }
        return {**request, "request_digest": sha256(canonical_bytes(request)).hexdigest()}


class FirestoreScenarioStore:
    """Firestore CAS implementation of the scenario journal port."""

    def __init__(self, client: Any, *, run_collection: str = "continuity_runs",
                 observation_collection: str = "continuity_run_observations"):
        self.client = client
        self.run_collection = run_collection
        self.observation_collection = observation_collection

    def create(self, run: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        from google.cloud import firestore
        reference = self.client.collection(self.run_collection).document(run["run_id"])
        transaction = self.client.transaction()

        @firestore.transactional
        def commit(txn: Any) -> tuple[dict[str, Any], bool]:
            snapshot = reference.get(transaction=txn)
            if snapshot.exists:
                return snapshot.to_dict(), True
            txn.create(reference, run)
            return run, False

        return commit(transaction)

    def load(self, run_id: str) -> dict[str, Any] | None:
        snapshot = self.client.collection(self.run_collection).document(run_id).get()
        return snapshot.to_dict() if snapshot.exists else None

    def advance(self, run_id: str, expected_phase: str, next_phase: str,
                patch: dict[str, Any], observation: dict[str, Any]) -> dict[str, Any]:
        from google.cloud import firestore
        run_ref = self.client.collection(self.run_collection).document(run_id)
        observation_id = f'{observation["sequence"]:08d}'
        observation_ref = (self.client.collection(self.observation_collection)
                           .document(run_id).collection("items").document(observation_id))
        transaction = self.client.transaction()

        @firestore.transactional
        def commit(txn: Any) -> dict[str, Any]:
            snapshot = run_ref.get(transaction=txn)
            if not snapshot.exists:
                raise ScenarioConflict("RUN_NOT_FOUND")
            current = snapshot.to_dict()
            if current["phase"] != expected_phase:
                raise ScenarioConflict("RUN_PHASE_CONFLICT")
            existing = observation_ref.get(transaction=txn)
            if existing.exists:
                raise ScenarioConflict("OBSERVATION_SEQUENCE_CONFLICT")
            updated = {**current, **patch, "phase": next_phase}
            txn.update(run_ref, {**patch, "phase": next_phase})
            txn.create(observation_ref, observation)
            return updated

        return commit(transaction)

    def observations(self, run_id: str) -> list[dict[str, Any]]:
        query = (self.client.collection(self.observation_collection).document(run_id)
                 .collection("items").order_by("sequence"))
        return [snapshot.to_dict() for snapshot in query.stream()]

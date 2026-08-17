"""Durable application service for the deployed procurement succession proof.

The service owns the canonical scenario inputs.  A caller supplies only a run
identifier; model output, policy decisions, gateway denials, provider state,
contract export, and independent verification all come from injected server
ports.  Each phase is compare-and-set persisted so a retry resumes rather than
re-authoring an outcome.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Protocol

from .contract import canonical_bytes


PHASES = (
    "CREATED", "INVESTIGATED", "AUTHORIZED", "PREDECESSOR_FENCED",
    "SUCCESSOR_ACTIVE", "EFFECT_OBSERVED", "CONTRACT_EXPORTED", "VERIFIED",
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
    successor: str = "v18"
    successor_epoch: int = 42
    idempotency_key: str = "vendor-042:create:v1"


class DurableCloudScenarioService:
    """Resume the canonical lifecycle from its last committed phase."""

    def __init__(self, *, store: ScenarioStore, evidence: EvidencePort,
                 investigator: InvestigatorPort,
                 authority: AuthorityPort, effects: EffectPort,
                 exporter: ContractExporterPort, verifier: IndependentVerifierPort,
                 scenario: CanonicalCloudScenario = CanonicalCloudScenario()):
        self.store = store
        self.evidence = evidence
        self.investigator = investigator
        self.authority = authority
        self.effects = effects
        self.exporter = exporter
        self.verifier = verifier
        self.scenario = scenario

    def run(self, run_id: str) -> dict[str, Any]:
        if not run_id or len(run_id) > 128:
            raise ValueError("RUN_ID_INVALID")
        expected = self._new_run(run_id)
        current, _ = self.store.create(expected)
        if current.get("command_digest") != expected["command_digest"]:
            raise ScenarioConflict("RUN_ID_CONTENT_CONFLICT")

        while current["phase"] != "VERIFIED":
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
            "observation_count": len(self.store.observations(run_id)),
        }

    def _new_run(self, run_id: str) -> dict[str, Any]:
        command = {
            "run_id": run_id, "tenant_id": self.scenario.tenant_id,
            "obligation_id": self.scenario.obligation_id,
            "predecessor": self.scenario.predecessor,
            "predecessor_epoch": self.scenario.predecessor_epoch,
            "successor": self.scenario.successor,
            "successor_epoch": self.scenario.successor_epoch,
            "idempotency_key": self.scenario.idempotency_key,
        }
        digest = sha256(canonical_bytes(command)).hexdigest()
        return {**command, "command_digest": digest, "correlation_id": digest[:32],
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
        phase = current["phase"]
        if phase == "CREATED":
            evidence = self.evidence.observe({
                "run_id": current["run_id"], "correlation_id": current["correlation_id"],
                "obligation_id": current["obligation_id"],
            })
            if not isinstance(evidence, list) or any(not isinstance(item, dict) for item in evidence):
                raise ValueError("LIFECYCLE_EVIDENCE_INVALID")
            proposal = self.investigator.investigate({
                "run_id": current["run_id"], "correlation_id": current["correlation_id"],
                "obligation_id": current["obligation_id"], "evidence": evidence,
            })
            cited = set(proposal.get("evidence_ids", proposal.get("evidence_types", [])))
            required = {item["event_id"] if "event_id" in item else item["type"]
                        for item in evidence}
            if not required.issubset(cited):
                raise ValueError("INVESTIGATION_EVIDENCE_INCOMPLETE")
            observed = {"signals": evidence, "proposal": proposal}
            return self._commit(current, "INVESTIGATED", {"investigation": proposal},
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
            if bundle.get("profile") != "reference-google-cloud" or not bundle.get("artifacts"):
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
            "run_id": current["run_id"], "tenant_id": current["tenant_id"],
            "principal": current["predecessor"] if operation != "activate" else current["successor"],
            "epoch": current["predecessor_epoch"] if operation != "activate" else current["successor_epoch"],
            "decision_id": current["decision"]["decision_id"], "operation": operation,
        }

    def _effect_request(self, current: dict[str, Any]) -> dict[str, Any]:
        request = {
            "run_id": current["run_id"], "tenant_id": current["tenant_id"],
            "principal": current["successor"], "epoch": current["successor_epoch"],
            "obligation_id": current["obligation_id"],
            "decision_id": current["decision"]["decision_id"],
            "idempotency_key": current["idempotency_key"], "operation": "vendor.create",
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

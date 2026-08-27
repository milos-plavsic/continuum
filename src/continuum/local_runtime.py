"""Credential-free composition of the complete durable succession lifecycle."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from threading import RLock
from typing import Any

from .cloud_scenario_service import CanonicalCloudScenario, DurableCloudScenarioService
from .contract import canonical_bytes
from .incident_policy import SUCCESSION, validate_incident_receipt
from .models import digest


LOCAL_NOW = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)


class LocalScenarioStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._runs: dict[str, dict[str, Any]] = {}
        self._observations: dict[str, list[dict[str, Any]]] = {}

    def create(self, run: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        with self._lock:
            prior = self._runs.get(run["run_id"])
            if prior is not None:
                return deepcopy(prior), True
            self._runs[run["run_id"]] = deepcopy(run)
            self._observations[run["run_id"]] = []
            return deepcopy(run), False

    def load(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            value = self._runs.get(run_id)
            return deepcopy(value) if value is not None else None

    def advance(self, run_id: str, expected_phase: str, next_phase: str,
                patch: dict[str, Any], observation: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            current = self._runs[run_id]
            if current["phase"] != expected_phase:
                raise RuntimeError("LOCAL_SCENARIO_CAS_CONFLICT")
            current.update(deepcopy(patch))
            current["phase"] = next_phase
            self._observations[run_id].append(deepcopy(observation))
            return deepcopy(current)

    def observations(self, run_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return deepcopy(self._observations[run_id])


class LocalLifecycleEvidence:
    def __init__(self) -> None:
        self.events: dict[str, list[dict[str, Any]]] = {}

    @staticmethod
    def _event(request: dict[str, Any], event_type: str, source: str) -> dict[str, Any]:
        body = {"run_id": request["run_id"], "event_type": event_type,
                "source": source, "obligation_id": request["obligation_id"]}
        return {**body, "event_id": digest(body), "type": event_type}

    def record_initial(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        events = [
            self._event(request, "document.injection_detected", "document-ingress"),
            self._event(request, "action.denied", "action-gateway"),
        ]
        self.events[request["run_id"]] = events
        return deepcopy(events)

    def detect_missing(self, request: dict[str, Any]) -> dict[str, Any] | None:
        now = datetime.fromisoformat(request["now"].replace("Z", "+00:00"))
        deadline = datetime.fromisoformat(request["deadline"].replace("Z", "+00:00"))
        if now < deadline:
            return None
        event = self._event(request, "expectation.missed", "negative-space-sentinel")
        if event not in self.events[request["run_id"]]:
            self.events[request["run_id"]].append(event)
        return deepcopy(event)

    def observe(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        return deepcopy(self.events[request["run_id"]])


class DeterministicInvestigator:
    """Offline model substitute that consumes policy output but owns no policy."""
    def investigate(self, request: dict[str, Any]) -> dict[str, Any]:
        allowed = request.get("allowed_remediations")
        candidates = request.get("eligible_candidates")
        if not isinstance(allowed, list) or not allowed or not isinstance(candidates, list) or not candidates:
            raise ValueError("LOCAL_INVESTIGATION_INPUT_INVALID")
        selected_action = SUCCESSION if SUCCESSION in allowed else allowed[0]
        candidate = sorted(candidates,
                           key=lambda item: (-int(item["trust_score"]), item["candidate_id"]))[0]
        evidence_ids = [item.get("event_id", item.get("type")) for item in request["evidence"]]
        references = list(candidate["evidence_refs"])
        citations = []
        for reference in references:
            if reference.startswith(("build:", "image:")):
                citations.append({"claim": "BUILD_PROVENANCE", "evidence_refs": [reference]})
            elif reference.startswith("health:"):
                citations.append({"claim": "HEALTH_ATTESTED", "evidence_refs": [reference]})
        return {
            "hypotheses": ["predecessor compromised", "upstream evidence delayed"],
            "evidence_ids": evidence_ids,
            "unsupported_assumptions": [],
            "risk": "bounded local sandbox",
            "reversibility": "successor can be fenced by a later epoch",
            "proposed_actions": [selected_action],
            "successor_choice": {
                "selected_candidate_id": candidate["candidate_id"],
                "evidence_manifest_refs": references,
                "supporting_citations": citations,
                "rationale": "highest trust among deterministically eligible candidates",
                "objective": request["selection_objective"],
            },
        }


class LocalAuthority:
    def __init__(self) -> None:
        self.active = "v17"
        self.revoked_through = -1

    def decide(self, evidence: list[dict[str, Any]]) -> dict[str, Any]:
        investigation = [item["evidence"] for item in evidence
                         if item.get("kind") == "investigation.observed"]
        if len(investigation) != 1:
            return {"outcome": "HOLD", "decision_id": None}
        item = investigation[0]
        try:
            receipt = validate_incident_receipt(item["incident_assessment"])
        except Exception:
            return {"outcome": "HOLD", "decision_id": None}
        if item.get("selected_plan") != SUCCESSION or SUCCESSION not in receipt.allowed_remediations:
            return {"outcome": "HOLD", "decision_id": None}
        return {"outcome": "APPROVE_SUCCESSION",
                "decision_id": "decision:" + digest(evidence),
                "incident_assessment_digest": receipt.receipt_digest}

    def fence_predecessor(self, request: dict[str, Any]) -> dict[str, Any]:
        self.revoked_through = max(self.revoked_through, int(request["epoch"]))
        return {"status": "FENCED", "revoked_through_epoch": self.revoked_through}

    def activate_successor(self, request: dict[str, Any]) -> dict[str, Any]:
        if int(request["epoch"]) <= self.revoked_through:
            raise ValueError("LOCAL_SUCCESSOR_EPOCH_INVALID")
        self.active = str(request["principal"])
        return {"status": "ACTIVE", "epoch": request["epoch"]}

    def attempt_action(self, request: dict[str, Any]) -> dict[str, Any]:
        return {"allowed": False, "reason": "STALE_EPOCH"}

    def attempt_memory(self, request: dict[str, Any]) -> dict[str, Any]:
        return {"allowed": False, "reason": "MEMORY_REVOKED", "candidates_examined": 0}


class LocalCompliance:
    def verify(self, request: dict[str, Any]) -> dict[str, Any]:
        evidence_id = digest({"run_id": request["run_id"], "vendor": request["vendor_id"]})
        return {"status": "VERIFIED", "evidence_id": evidence_id,
                "document_hash": "sha256:" + digest(request["application"]),
                "obligation_id": request["obligation_id"],
                "workflow": "SUPPLIER_ASSURANCE_AGENT", "decision_scope": "SANDBOX_ONLY",
                "recommendation": "ONBOARD", "decision_pack_digest": digest(request)}


class LocalEffects:
    def __init__(self) -> None:
        self._lock = RLock()
        self.effects: dict[str, dict[str, Any]] = {}

    def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            key = str(request["idempotency_key"])
            existing = self.effects.get(key)
            if existing is not None and existing["request_digest"] != request["request_digest"]:
                raise ValueError("LOCAL_EFFECT_IDEMPOTENCY_CONFLICT")
            if existing is None:
                self.effects[key] = {"request_digest": request["request_digest"],
                                     "provider_ref": f"local://vendor/{request['vendor_id']}",
                                     "compliance_evidence_id": request["compliance_evidence_id"]}
            return {"state": "DEDUPLICATED" if existing else "DISPATCHED"}

    def reconcile(self, request: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            record = self.effects.get(str(request["idempotency_key"]))
            if record is None:
                return {"effect_count": 0}
            return {**record, "effect_count": 1}


class LocalContractExporter:
    def export(self, run: dict[str, Any], observations: list[dict[str, Any]]) -> dict[str, Any]:
        artifact = {"artifact_type": "local_observed_chain", "run_id": run["run_id"],
                    "observation_digest": digest(observations),
                    "effect": run["provider_observation"]}
        return {"profile": "reference-local", "protocol": "continuum/0.1-draft",
                "artifacts": [{**artifact, "digest": digest(artifact)}]}


class LocalIndependentVerifier:
    def verify(self, request: dict[str, Any]) -> dict[str, Any]:
        bundle = request.get("bundle", {})
        provider = request.get("provider_observation", {})
        passed = (bundle.get("profile") == "reference-local"
                  and provider.get("effect_count") == 1
                  and bool(provider.get("provider_ref")))
        return {"status": "PASS" if passed else "FAIL",
                "outcome": "VERIFIED" if passed else "FAILED",
                "verifier_principal": "urn:continuum:local:independent-verifier",
                "bundle_digest": sha256(canonical_bytes(bundle)).hexdigest()}


def create_local_service() -> DurableCloudScenarioService:
    return DurableCloudScenarioService(
        store=LocalScenarioStore(), evidence=LocalLifecycleEvidence(),
        investigator=DeterministicInvestigator(), authority=LocalAuthority(),
        effects=LocalEffects(), compliance=LocalCompliance(),
        exporter=LocalContractExporter(), verifier=LocalIndependentVerifier(),
        scenario=CanonicalCloudScenario(deadline_delay_seconds=0),
        clock=lambda: LOCAL_NOW, expected_contract_profile="reference-local",
    )


def run_local_succession(run_id: str) -> dict[str, Any]:
    service = create_local_service()
    service.start(run_id)
    service.tick(run_id)
    result = service.handle_event({"run_id": run_id, "event_type": "expectation.missed"})
    return {**result, "profile": "reference-local-container/1"}

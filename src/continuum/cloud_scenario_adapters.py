"""Production composition for the durable Google Cloud scenario.

All observations are read from Firestore or authenticated worker services.  The
factory returns ``None`` unless the complete private invocation graph is
configured, keeping the deployed control plane fail closed.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .canonicalization import PROFILE as CANONICALIZATION_PROFILE
from .cloud_scenario_service import DurableCloudScenarioService, FirestoreScenarioStore
from .contract import artifact_ref, canonical_bytes, make_envelope
from .google_binding import GoogleBindingConfig, PubSubLifecyclePublisher
from .incident_policy import SUCCESSION, validate_incident_receipt
from .models import AgentStatus, digest
from .model_armor import GoogleModelArmorGuard
from .fleet_registry import FirestoreFleetCatalog, FleetPublication
from .succession_selection import SuccessorCandidate


def _emit(run_id: str, object_id: str, payload: dict[str, Any]) -> None:
    # A raw JSON stdout line is ingested by Cloud Logging as jsonPayload;
    # logger prefixes would demote this to textPayload and break exact capture.
    print(json.dumps({"continuum_evidence": {"run_id": run_id,
        "object_id": object_id, "payload": payload}}, sort_keys=True, separators=(",", ":")),
          flush=True)


class AuthenticatedJsonClient:
    def __init__(self, token: Callable[[str], str], opener: Callable[..., Any] = urlopen):
        self.token, self.opener = token, opener

    def post(self, url: str, payload: dict[str, Any], *, run_id: str) -> dict[str, Any]:
        parsed = urlsplit(url)
        audience = f"{parsed.scheme}://{parsed.netloc}"
        headers = {
            "Authorization": f"Bearer {self.token(audience)}", "Content-Type": "application/json",
            "X-Continuum-Run-ID": run_id,
        }
        trace_id = payload.get("correlation_id")
        if isinstance(trace_id, str) and len(trace_id) == 32 and all(c in "0123456789abcdef" for c in trace_id):
            headers["traceparent"] = f"00-{trace_id}-0000000000000001-01"
        request = Request(url, data=canonical_bytes(payload), method="POST", headers=headers)
        with self.opener(request, timeout=60) as response:
            result = json.loads(response.read())
        if not isinstance(result, dict):
            raise ValueError("WORKER_RESPONSE_INVALID")
        return result

    def get(self, url: str, *, run_id: str) -> dict[str, Any]:
        parsed = urlsplit(url)
        audience = f"{parsed.scheme}://{parsed.netloc}"
        request = Request(url, method="GET", headers={
            "Authorization": f"Bearer {self.token(audience)}",
            "X-Continuum-Run-ID": run_id,
        })
        with self.opener(request, timeout=60) as response:
            result = json.loads(response.read())
        if not isinstance(result, dict):
            raise ValueError("WORKER_RESPONSE_INVALID")
        return result


class FirestoreLifecycleEvidence:
    REQUIRED = {"document.injection_detected", "action.denied", "expectation.missed"}
    INITIAL = {"document.injection_detected", "action.denied"}

    def __init__(self, client: Any, publisher: Any, collection: str = "continuity_events"):
        self.client, self.publisher, self.collection = client, publisher, collection

    def _record(self, request: dict[str, Any], event_type: str) -> dict[str, Any]:
            event_id = sha256(canonical_bytes({"run_id": request["run_id"],
                                               "event_type": event_type})).hexdigest()
            event = {"event_id": event_id, "event_type": event_type,
                     "run_id": request["run_id"],
                     "correlation_id": request["correlation_id"],
                     "obligation_id": request["obligation_id"],
                     "source": "procurement-succession-v1",
                     "redelivery_probe": event_type == "expectation.missed",
                     "deadline": request.get("deadline")}
            reference = self.client.collection(self.collection).document(event_id)
            outbox = self.client.collection("continuity_outbox").document(event_id)
            projection = self.client.collection("continuity_projections").document(request["run_id"])
            existing = reference.get()
            if existing.exists and existing.to_dict() != event:
                raise ValueError("LIFECYCLE_EVENT_CONTENT_CONFLICT")
            if not existing.exists:
                from google.cloud import firestore
                transaction = self.client.transaction()

                @firestore.transactional
                def commit(txn: Any) -> None:
                    raced = reference.get(transaction=txn)
                    if raced.exists:
                        if raced.to_dict() != event:
                            raise ValueError("LIFECYCLE_EVENT_CONTENT_CONFLICT")
                        return
                    txn.create(reference, event)
                    txn.set(projection, {"run_id": request["run_id"],
                            "last_event_id": event_id, "last_event_type": event_type}, merge=True)
                    txn.create(outbox, {"run_id": request["run_id"], "event_id": event_id,
                                       "status": "PENDING"})

                commit(transaction)
            published = outbox.get()
            record = published.to_dict() or {}
            if record.get("status") != "PUBLISHED":
                message_id = self.publisher.publish({**event, "schema_version": 1})
                record = {"run_id": request["run_id"], "event_id": event_id,
                          "status": "PUBLISHED", "message_id": message_id}
                outbox.set(record)
            if event_type == "expectation.missed":
                _emit(request["run_id"], "firestore-event",
                      {"run_id": request["run_id"], "event_id": event_id})
                _emit(request["run_id"], "firestore-projection",
                      {"run_id": request["run_id"], "last_event_id": event_id})
                _emit(request["run_id"], "firestore-outbox",
                      {"run_id": request["run_id"], "event_id": event_id, "status": "PUBLISHED"})
                _emit(request["run_id"], "pubsub-publish",
                      {"run_id": request["run_id"], "event_id": event_id,
                       "message_id": record["message_id"]})
            return event

    def record_initial(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        security = request.get("input_security_receipt")
        if isinstance(security, dict):
            _emit(request["run_id"], "model-armor",
                  {"run_id": request["run_id"], **security})
        return [self._record(request, event_type) for event_type in sorted(self.INITIAL)]

    def detect_missing(self, request: dict[str, Any]) -> dict[str, Any] | None:
        deadline = datetime.fromisoformat(request["deadline"].replace("Z", "+00:00"))
        now = datetime.fromisoformat(request["now"].replace("Z", "+00:00"))
        if now < deadline:
            return None
        query = self.client.collection(self.collection).where(
            "correlation_id", "==", request["correlation_id"])
        if any(snapshot.to_dict().get("event_type") == "compliance.evidence_verified"
               for snapshot in query.stream()):
            return None
        return self._record(request, "expectation.missed")

    def observe(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        query = self.client.collection(self.collection).where(
            "correlation_id", "==", request["correlation_id"])
        events = [snapshot.to_dict() for snapshot in query.stream()]
        observed = {event.get("event_type") for event in events}
        if not self.REQUIRED.issubset(observed):
            raise ValueError("LIFECYCLE_EVIDENCE_INCOMPLETE")
        return sorted((event for event in events if event["event_type"] in self.REQUIRED),
                      key=lambda event: event["event_id"])


class RemoteInvestigator:
    def __init__(self, client: AuthenticatedJsonClient, url: str): self.client, self.url = client, url
    def investigate(self, request: dict[str, Any]) -> dict[str, Any]:
        response = self.client.post(f"{self.url}/internal/investigate", request,
                                    run_id=request["run_id"])
        proposal = response["proposal"]
        _emit(request["run_id"], "vertex-call", {"run_id": request["run_id"],
              "provider": "vertex-ai", "model": "gemini-3.6-flash",
              "service_account": response["actor"],
              "incident_assessment_digest": request["incident_assessment_receipt"]["receipt_digest"],
              "evidence_event_ids": proposal["evidence_ids"],
              "proposed_actions": proposal["proposed_actions"],
              "selected_candidate_id": proposal["successor_choice"]["selected_candidate_id"],
              "evidence_manifest_refs": proposal["successor_choice"]["evidence_manifest_refs"],
              "supporting_citations": proposal["successor_choice"]["supporting_citations"]})
        return proposal


class FirestoreAuthority:
    """Persisted registry boundary; policy is deterministic and evidence-gated."""
    def __init__(self, client: Any, workload_client: AuthenticatedJsonClient,
                 predecessor_url: str, predecessor_identity: str):
        self.client, self.workload_client = client, workload_client
        self.predecessor_url, self.predecessor_identity = predecessor_url, predecessor_identity
    def decide(self, evidence: list[dict[str, Any]]) -> dict[str, Any]:
        signals = set()
        selected_plans = set()
        incident_receipts = []
        for observation in evidence:
            for event in observation.get("evidence", {}).get("signals", []):
                signals.add(event.get("event_type"))
            selected = observation.get("evidence", {}).get("selected_plan")
            if selected: selected_plans.add(selected)
            incident = observation.get("evidence", {}).get("incident_assessment")
            if incident: incident_receipts.append(incident)
        if len(incident_receipts) != 1:
            return {"outcome": "HOLD", "decision_id": None}
        try:
            assessment = validate_incident_receipt(incident_receipts[0])
        except Exception:
            return {"outcome": "HOLD", "decision_id": None}
        if (not FirestoreLifecycleEvidence.REQUIRED.issubset(signals)
                or set(assessment.signal_types) != signals
                or selected_plans != {SUCCESSION}
                or SUCCESSION not in assessment.allowed_remediations):
            return {"outcome": "HOLD", "decision_id": None}
        digest = sha256(canonical_bytes(evidence)).hexdigest()
        return {"outcome": "APPROVE_SUCCESSION", "decision_id": f"decision:{digest}",
                "incident_assessment_digest": assessment.receipt_digest}
    def fence_predecessor(self, request: dict[str, Any]) -> dict[str, Any]:
        from google.cloud import firestore
        ref = self.client.collection("continuity_authority").document(request["tenant_id"])
        transaction = self.client.transaction()
        @firestore.transactional
        def commit(txn: Any) -> dict[str, Any]:
            current = ref.get(transaction=txn)
            state = current.to_dict() if current.exists else {}
            if state.get("revoked_through_epoch", -1) > request["epoch"]:
                raise ValueError("AUTHORITY_EPOCH_REGRESSION")
            updated = {**state, "predecessor": request["principal"],
                       "revoked_through_epoch": request["epoch"], "status": "FENCED",
                       "decision_id": request["decision_id"], "run_id": request["run_id"]}
            txn.set(ref, updated)
            return updated
        return commit(transaction)
    def activate_successor(self, request: dict[str, Any]) -> dict[str, Any]:
        from google.cloud import firestore
        ref = self.client.collection("continuity_authority").document(request["tenant_id"])
        transaction = self.client.transaction()
        @firestore.transactional
        def commit(txn: Any) -> dict[str, Any]:
            snapshot = ref.get(transaction=txn); state = snapshot.to_dict() if snapshot.exists else {}
            if state.get("status") != "FENCED": raise ValueError("PREDECESSOR_NOT_FENCED")
            if request["epoch"] <= state.get("revoked_through_epoch", -1):
                raise ValueError("SUCCESSOR_EPOCH_NOT_MONOTONIC")
            updated = {**state, "active_principal": request["principal"], "epoch": request["epoch"],
                       "status": "ACTIVE", "run_id": request["run_id"]}
            txn.set(ref, updated)
            return updated
        return commit(transaction)
    def attempt_action(self, request: dict[str, Any]) -> dict[str, Any]:
        observed = self.workload_client.post(f"{self.predecessor_url}/internal/attempt-action", {},
                                             run_id=request["run_id"])
        if observed.get("actor") != self.predecessor_identity:
            raise ValueError("PREDECESSOR_IDENTITY_MISMATCH")
        state = self.client.collection("continuity_authority").document(request["tenant_id"]).get().to_dict() or {}
        return ({"allowed": False, "reason": "STALE_EPOCH", "actor": observed["actor"]}
                if request["epoch"] <= state.get("revoked_through_epoch", -1) else {"allowed": True})
    def attempt_memory(self, request: dict[str, Any]) -> dict[str, Any]:
        observed = self.workload_client.post(f"{self.predecessor_url}/internal/attempt-memory", {},
                                             run_id=request["run_id"])
        if observed.get("actor") != self.predecessor_identity:
            raise ValueError("PREDECESSOR_IDENTITY_MISMATCH")
        state = self.client.collection("continuity_authority").document(request["tenant_id"]).get().to_dict() or {}
        return ({"allowed": False, "reason": "MEMORY_REVOKED", "actor": observed["actor"],
                 "candidates_examined": 0}
                if request["epoch"] <= state.get("revoked_through_epoch", -1) else {"allowed": True})


class FirestoreSandboxEffects:
    """Idempotent Firestore sandbox provider and independent read reconciliation."""
    def __init__(self, client: Any, workload_client: AuthenticatedJsonClient,
                 successor_url: str, successor_identity: str):
        self.client, self.workload_client = client, workload_client
        self.successor_url, self.successor_identity = successor_url, successor_identity
    def _ref(self, request: dict[str, Any]) -> Any:
        key = sha256(f'{request["tenant_id"]}\0{request["run_id"]}\0{request["idempotency_key"]}'.encode()).hexdigest()
        return self.client.collection("continuity_sandbox_vendors").document(key)
    def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        observed = self.workload_client.post(f"{self.successor_url}/internal/attempt-action", request,
                                             run_id=request["run_id"])
        if observed.get("actor") != self.successor_identity:
            raise ValueError("SUCCESSOR_IDENTITY_MISMATCH")
        if observed.get("state") not in {"DISPATCHED", "DEDUPLICATED"}:
            raise ValueError("ACTION_GATEWAY_RESULT_INVALID")
        return observed
    def reconcile(self, request: dict[str, Any]) -> dict[str, Any]:
        snapshot = self._ref(request).get()
        if not snapshot.exists: return {"effect_count": 0, "provider_ref": None}
        record = snapshot.to_dict()
        if record["request_digest"] != request["request_digest"]: raise ValueError("PROVIDER_DIGEST_CONFLICT")
        external = record.get("external_effect")
        provider_ref = (external.get("provider_ref") if isinstance(external, dict)
                        else record["provider_ref"])
        result = {"effect_count": 1, "provider_ref": provider_ref,
                "provider": external.get("provider") if isinstance(external, dict) else "firestore-sandbox",
                "request_digest": record["request_digest"],
                "compliance_evidence_id": record["compliance_evidence_id"]}
        if isinstance(external, dict):
            result.update({key: external[key] for key in ("resource_id", "state")
                           if key in external})
            _emit(request["run_id"], "external-work-item",
                  {"run_id": request["run_id"], **result})
        return result


class RoutedFirestoreSandboxEffects(FirestoreSandboxEffects):
    """Route the admitted logical principal to its distinct workload identity."""
    def __init__(self, client: Any, workload_client: AuthenticatedJsonClient,
                 routes: dict[str, tuple[str, str]]):
        super().__init__(client, workload_client, "", "")
        self.routes = dict(routes)

    def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        route = self.routes.get(str(request.get("principal")))
        if route is None:
            raise ValueError("SUCCESSOR_ROUTE_NOT_CONFIGURED")
        url, identity = route
        observed = self.workload_client.post(f"{url}/internal/attempt-action", request,
                                             run_id=request["run_id"])
        if observed.get("actor") != identity:
            raise ValueError("SUCCESSOR_IDENTITY_MISMATCH")
        if observed.get("state") not in {"DISPATCHED", "DEDUPLICATED"}:
            raise ValueError("ACTION_GATEWAY_RESULT_INVALID")
        return observed


class FirestoreCompliance:
    """Deterministic compliance provider fixture persisted independently of the run."""
    def __init__(self, client: Any): self.client = client
    def verify(self, request: dict[str, Any]) -> dict[str, Any]:
        evidence_id = sha256(canonical_bytes({"run_id": request["run_id"],
            "obligation_id": request["obligation_id"], "vendor_id": request["vendor_id"]})).hexdigest()
        document_hash = digest({"issuer": "continuum-demo-compliance-provider",
                                "subject": request["vendor_id"], "result": "PASS"})
        record = {"run_id": request["run_id"], "tenant_id": request["tenant_id"],
                  "obligation_id": request["obligation_id"], "vendor_id": request["vendor_id"],
                  "evidence_id": evidence_id, "document_hash": document_hash, "status": "VERIFIED"}
        ref = self.client.collection("continuity_compliance").document(request["run_id"])
        existing = ref.get()
        if existing.exists and existing.to_dict() != record:
            raise ValueError("COMPLIANCE_EVIDENCE_CONFLICT")
        if not existing.exists: ref.create(record)
        return record


class RemoteSupplierAssurance:
    """Invoke the admitted successor's practical agent and persist its decision pack."""
    def __init__(self, client: Any, workload_client: AuthenticatedJsonClient,
                 routes: dict[str, tuple[str, str]]):
        self.client, self.workload_client, self.routes = client, workload_client, dict(routes)

    def verify(self, request: dict[str, Any]) -> dict[str, Any]:
        route = self.routes.get(str(request.get("successor")))
        if route is None:
            raise ValueError("SUPPLIER_ASSURANCE_ROUTE_NOT_CONFIGURED")
        url, expected_identity = route
        response = self.workload_client.post(
            f"{url}/internal/assess-supplier", request, run_id=request["run_id"])
        if response.get("actor") != expected_identity:
            raise ValueError("SUPPLIER_ASSESSOR_IDENTITY_MISMATCH")
        assurance = response.get("assurance")
        if (isinstance(assurance, dict) and assurance.get("status") == "HOLD"
                and assurance.get("workflow") == "SUPPLIER_ASSURANCE_AGENT"
                and assurance.get("decision_scope") == "SANDBOX_ONLY"
                and assurance.get("model_invoked") is False
                and assurance.get("proposed_action") == "none"):
            reason = assurance.get("reason_code")
            if not isinstance(reason, str) or not reason:
                raise ValueError("SUPPLIER_ASSURANCE_HOLD_INVALID")
            hold = {**assurance, "run_id": request["run_id"],
                    "tenant_id": request["tenant_id"],
                    "obligation_id": request["obligation_id"],
                    "vendor_id": request["vendor_id"]}
            ref = self.client.collection("continuity_compliance_holds").document(request["run_id"])
            existing = ref.get()
            if existing.exists and existing.to_dict() != hold:
                raise ValueError("SUPPLIER_ASSURANCE_HOLD_CONFLICT")
            if not existing.exists:
                ref.create(hold)
            _emit(request["run_id"], "supplier-assurance-hold", {
                "run_id": request["run_id"], "reason_code": reason,
                "model_invoked": False, "proposed_action": "none",
            })
            raise ValueError(f"SUPPLIER_ASSURANCE_HOLD:{reason}")
        if (not isinstance(assurance, dict) or assurance.get("status") != "VERIFIED"
                or assurance.get("workflow") != "SUPPLIER_ASSURANCE_AGENT"
                or assurance.get("decision_scope") != "SANDBOX_ONLY"
                or assurance.get("vendor_id") != request["vendor_id"]):
            raise ValueError("SUPPLIER_ASSURANCE_RESULT_INVALID")
        record = {
            **assurance,
            "run_id": request["run_id"], "tenant_id": request["tenant_id"],
            "obligation_id": request["obligation_id"], "vendor_id": request["vendor_id"],
        }
        ref = self.client.collection("continuity_compliance").document(request["run_id"])
        existing = ref.get()
        if existing.exists and existing.to_dict() != record:
            raise ValueError("SUPPLIER_ASSURANCE_EVIDENCE_CONFLICT")
        if not existing.exists:
            ref.create(record)
        _emit(request["run_id"], "supplier-assurance", {
            "run_id": request["run_id"], "workflow": assurance["workflow"],
            "model": "gemini-3.6-flash", "service_account": response["actor"],
            "decision_scope": assurance["decision_scope"],
            "recommendation": assurance.get("recommendation"),
            "decision_pack_digest": assurance.get("decision_pack_digest"),
            "tools": [{"tool": item.get("tool"), "source_url": item.get("source_url"),
                       "evidence_ref": item.get("evidence_ref"),
                       "availability_mode": item.get("availability_mode"),
                       "observed_at": item.get("observed_at"),
                       "freshness_expires_at": item.get("freshness_expires_at"),
                       "cached_from_evidence_ref": item.get("cached_from_evidence_ref")}
                      for item in assurance.get("tool_observations", [])],
        })
        return record


class CloudTasksDeadlineScheduler:
    """Schedules the external Sentinel tick; request handling does not sleep."""
    def __init__(self, client: Any, *, project: str, region: str, queue: str,
                 control_url: str, oidc_service_account: str):
        self.client, self.project, self.region, self.queue = client, project, region, queue
        self.control_url, self.oidc_service_account = control_url, oidc_service_account
    def schedule(self, *, run_id: str, deadline: str) -> dict[str, Any]:
        from google.api_core.exceptions import AlreadyExists
        from google.protobuf.timestamp_pb2 import Timestamp
        parent = self.client.queue_path(self.project, self.region, self.queue)
        task_id = "sentinel-" + sha256(run_id.encode()).hexdigest()[:40]
        task_name = self.client.task_path(self.project, self.region, self.queue, task_id)
        timestamp = Timestamp(); timestamp.FromDatetime(datetime.fromisoformat(deadline.replace("Z", "+00:00")))
        task = {"name": task_name, "schedule_time": timestamp, "http_request": {
            "http_method": "POST", "url": f"{self.control_url}/cloud-smoke/{run_id}/tick",
            "oidc_token": {"service_account_email": self.oidc_service_account,
                           "audience": self.control_url}}}
        try:
            created = self.client.create_task(parent=parent, task=task)
            name = created.name
        except AlreadyExists:
            name = task_name
        return {"mode": "cloud-tasks", "task_name": name, "scheduled_at": deadline}


class ObservedContractExporter:
    """Export five claims; only the independent verifier may issue artifact six."""
    def __init__(self, issuer: str, verifier_principal: str):
        self.issuer, self.verifier_principal = issuer, verifier_principal
    def export(self, run: dict[str, Any], observations: list[dict[str, Any]]) -> dict[str, Any]:
        issued = datetime.now(timezone.utc)
        at = issued.isoformat().replace("+00:00", "Z")
        expires = (issued + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        base = f'urn:continuum:cloud:{run["run_id"]}'
        decision = {"artifact_id": f"{base}:decision", "digest": {"alg": "sha-256", "value": sha256(canonical_bytes(run["decision"])).hexdigest()}, "policy_version": "compromise-succession/1", "outcome": "APPROVE_SUCCESSION"}
        obligation = make_envelope("obligation", f"{base}:obligation", self.issuer, at, {"tenant_id": run["tenant_id"], "subject": run["obligation_id"], "revision": 2, "owner": {"principal_id": run["successor"], "authority_domain": f"{base}:authority", "epoch": run["successor_epoch"]}, "description": "Onboard vendor only after independently observed compliance evidence", "deadline": run["deadline"], "completion_criteria": [{"criterion_id": "compliance-verified", "evidence_type": "compliance-provider-observation", "verifier_role": "independent-verifier"}, {"criterion_id": "provider-effect-once", "evidence_type": "provider-observation", "verifier_role": "independent-verifier"}], "allowed_effects": ["vendor.create"], "compensation": {"mode": "HUMAN"}, "status": "DISCHARGED"})
        grant = make_envelope("authority_grant", f"{base}:grant", self.issuer, at, {"tenant_id": run["tenant_id"], "grant_id": f'{run["run_id"]}:grant', "subject_principal": run["successor"], "authority_domain": f"{base}:authority", "epoch": run["successor_epoch"], "obligation_ids": [obligation["artifact_id"]], "capabilities": ["vendor.create"], "memory_scopes": ["vendor.approved"], "purpose": "complete vendor onboarding", "not_before": at, "expires_at": expires, "policy_decision": decision, "status": "ACTIVE"})
        manifest = make_envelope("succession_manifest", f"{base}:manifest", self.issuer, at, {"succession_id": run["run_id"], "tenant_id": run["tenant_id"], "authority_domain": f"{base}:authority", "predecessor": {"principal_id": run["predecessor"], "epoch": run["predecessor_epoch"]}, "successor": {"principal_id": run["successor"], "epoch": run["successor_epoch"]}, "obligations": [artifact_ref(obligation)], "included_grants": [artifact_ref(grant)], "excluded_context": [{"reference_or_class": item["item_id"], "reason_code": item["reason_code"]} for item in run["context_reconstruction"]["decisions"] if not item["included"]], "in_flight_effects": [], "evidence_refs": [{"observation": item["sequence"], "kind": item["kind"]} for item in observations], "policy_decision": decision, "created_from_registry_revision": run["successor_epoch"], "state": "COMMITTED"}, extensions={"continuum.dev/successor-selection": run["candidate_assessment"], "continuum.dev/selection-governance": run["selection_governance"], "continuum.dev/context-reconstruction": run["context_reconstruction"], "continuum.dev/incident-evidence": {"subject": run["obligation_id"], "records": run["evidence_records"], "evidence_validation": run["evidence_validation"], "incident_assessment": run["incident_assessment"]}})
        revocation = make_envelope("revocation_proof", f"{base}:revocation", self.issuer, at, {"tenant_id": run["tenant_id"], "authority_domain": f"{base}:authority", "revoked_principal": run["predecessor"], "revoked_through_epoch": run["predecessor_epoch"], "registry_revision": run["successor_epoch"], "effective_at": at, "revoked_grant_ids": [], "enforcement_points": [{"id": "action-gateway", "kind": "ACTION", "observation_ref": "predecessor.denials_observed"}, {"id": "memory-gateway", "kind": "MEMORY", "observation_ref": "predecessor.denials_observed"}], "policy_decision": decision, "status": "ENFORCED"})
        provider = run["provider_observation"]
        compliance_extension = {
            "evidence_id": run["compliance"]["evidence_id"],
            "obligation_id": run["obligation_id"],
            "document_hash": run["compliance"]["document_hash"],
        }
        for key in ("workflow", "decision_scope", "recommendation", "decision_pack_digest"):
            if key in run["compliance"]:
                compliance_extension[key] = run["compliance"][key]
        receipt = make_envelope("execution_receipt", f"{base}:receipt", self.issuer, at, {"tenant_id": run["tenant_id"], "obligation": artifact_ref(obligation), "executing_principal": run["successor"], "authority_domain": f"{base}:authority", "epoch": run["successor_epoch"], "decision": decision, "idempotency_key": run["idempotency_key"], "request_digest": provider["request_digest"], "execution_id": run["run_id"], "provider": {"adapter": "firestore-sandbox/1", "operation": "vendor.create", "resource_ref": provider["provider_ref"]}, "disposition": "EXECUTED", "observed_at": at}, extensions={"continuum.dev/compliance": compliance_extension})
        return {"profile": "reference-google-cloud", "protocol": "continuum/0.1-draft",
                "canonicalization_profile": CANONICALIZATION_PROFILE,
                "artifacts": [obligation, grant, manifest, revocation, receipt]}


class RemoteVerifier:
    def __init__(self, client: AuthenticatedJsonClient, url: str, principal: str): self.client, self.url, self.principal = client, url, principal
    def verify(self, request: dict[str, Any]) -> dict[str, Any]:
        response = self.client.post(f"{self.url}/internal/verify", request, run_id=request["run_id"])
        result = response["verification"]
        observed = {**result, "verifier_principal": response.get("actor", self.principal)}
        if observed.get("status") == "PASS" and observed.get("outcome") == "VERIFIED":
            bundle = result["bundle"]
            _emit(request["run_id"], "contract-export", {"run_id": request["run_id"],
                  "protocol": "continuum/0.1-draft", "status": "PASS",
                  "bundle": bundle,
                  "report_digest": {"alg": "sha-256",
                                    "value": sha256(canonical_bytes(bundle)).hexdigest()}})
        return observed


def google_id_token(audience: str) -> str:
    from google.auth.transport.requests import Request as AuthRequest
    from google.oauth2.id_token import fetch_id_token
    return fetch_id_token(AuthRequest(), audience)


class RemoteCanonicalControlPlane:
    """The judge service can invoke only canonical start and sanitized status."""
    def __init__(self, client: AuthenticatedJsonClient, url: str):
        self.client, self.url = client, url.rstrip("/")

    def start(self, run_id: str) -> dict[str, Any]:
        return self.client.post(f"{self.url}/cloud-smoke/start", {"run_id": run_id}, run_id=run_id)

    def status(self, run_id: str) -> dict[str, Any]:
        return self.client.get(f"{self.url}/cloud-smoke/{run_id}", run_id=run_id)


def build_production_judge_controller() -> Any | None:
    project = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    control_url = os.getenv("CONTINUUM_CONTROL_URL", "")
    secret = os.getenv("CONTINUUM_JUDGE_HMAC_SECRET", "")
    if not project or not control_url or len(secret.encode()) < 32:
        return None
    from google.cloud import firestore
    from .judge_access import FirestoreJudgeQuota, JudgeController
    return JudgeController(
        secret=secret,
        quota=FirestoreJudgeQuota(firestore.Client(project=project)),
        control=RemoteCanonicalControlPlane(AuthenticatedJsonClient(google_id_token), control_url),
    )


def build_production_scenario_service() -> DurableCloudScenarioService | None:
    required = {name: os.getenv(name, "") for name in (
        "GOOGLE_CLOUD_PROJECT", "CONTINUUM_V17_URL", "CONTINUUM_V18_URL", "CONTINUUM_V19_URL", "CONTINUUM_VERIFIER_URL",
        "CONTINUUM_CONTROL_IDENTITY", "CONTINUUM_V17_IDENTITY", "CONTINUUM_V18_IDENTITY", "CONTINUUM_V19_IDENTITY",
        "CONTINUUM_VERIFIER_IDENTITY", "CONTINUUM_CONTROL_URL", "CONTINUUM_IMAGE_DIGEST",
        "CONTINUUM_DEADLINE_QUEUE", "CONTINUUM_PUBSUB_PUSH_IDENTITY",
        "CONTINUUM_MODEL_ARMOR_TEMPLATE")}
    if any(not value for value in required.values()): return None
    from google.cloud import firestore
    from google.cloud import tasks_v2
    db = firestore.Client(project=required["GOOGLE_CLOUD_PROJECT"])
    http = AuthenticatedJsonClient(google_id_token)
    def armor_post(url: str, payload: dict[str, Any]) -> dict[str, Any]:
        import google.auth
        from google.auth.transport.requests import Request as AuthRequest
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"])
        credentials.refresh(AuthRequest())
        request = Request(url, data=canonical_bytes(payload), method="POST", headers={
            "Authorization": f"Bearer {credentials.token}",
            "Content-Type": "application/json",
        })
        with urlopen(request, timeout=30) as response:
            result = json.loads(response.read())
        if not isinstance(result, dict):
            raise ValueError("MODEL_ARMOR_RESPONSE_INVALID")
        return result
    publisher = PubSubLifecyclePublisher(GoogleBindingConfig(
        required["GOOGLE_CLOUD_PROJECT"], os.getenv("CONTINUUM_LIFECYCLE_TOPIC", "continuum-lifecycle")))
    common = {
        "tenant_id": "acme", "status": AgentStatus.REGISTERED,
        "capabilities": ("vendor.create",), "memory_scopes": ("vendor.approved",),
        "authority_domains": ("procurement",), "contract_profiles": ("continuity/1",),
    }
    deployed_candidates = (
        SuccessorCandidate("v18", "v18", artifact_digest=required["CONTINUUM_IMAGE_DIGEST"],
            service_identity=required["CONTINUUM_V18_IDENTITY"], jurisdictions=("EU",),
            health="HEALTHY", trust_score=94, recovery_time_seconds=75,
            assurance_level="VERY_HIGH", warm_state="COLD",
            evidence_refs=(f'image:{required["CONTINUUM_IMAGE_DIGEST"]}',
                           f'cloud-run:{required["CONTINUUM_V18_URL"]}',
                           f'identity:{required["CONTINUUM_V18_IDENTITY"]}',
                           'recovery:v18:75s', 'assurance:v18:very-high',
                           'warm-state:v18:cold'), **common),
        SuccessorCandidate("v19", "v19", artifact_digest=required["CONTINUUM_IMAGE_DIGEST"],
            service_identity=required["CONTINUUM_V19_IDENTITY"], jurisdictions=("EU",),
            health="HEALTHY", trust_score=91, recovery_time_seconds=18,
            assurance_level="HIGH", warm_state="WARM",
            evidence_refs=(f'image:{required["CONTINUUM_IMAGE_DIGEST"]}',
                           f'cloud-run:{required["CONTINUUM_V19_URL"]}',
                           f'identity:{required["CONTINUUM_V19_IDENTITY"]}',
                           'recovery:v19:18s', 'assurance:v19:high',
                           'warm-state:v19:warm'), **common),
        # An explicit negative control proves that the deterministic gate, rather than
        # prompt wording, excludes an otherwise high-scoring but inadmissible agent.
        SuccessorCandidate("v20", "v20", artifact_digest="sha256:" + "0" * 64,
            service_identity="not-deployed", jurisdictions=("US",), health="DEGRADED",
            trust_score=98, evidence_refs=("registry:v20",), **common),
    )
    fleet_catalog = FirestoreFleetCatalog(db)
    for department, candidate in zip(("procurement", "finance", "security"),
                                     deployed_candidates, strict=True):
        fleet_catalog.publish(FleetPublication(department=department,
            owner=f"{department}-platform", published_at="2026-08-27T00:00:00Z",
            candidate=candidate))
    return DurableCloudScenarioService(
        store=FirestoreScenarioStore(db), evidence=FirestoreLifecycleEvidence(db, publisher),
        deadline_scheduler=CloudTasksDeadlineScheduler(tasks_v2.CloudTasksClient(),
            project=required["GOOGLE_CLOUD_PROJECT"], region=os.getenv("CONTINUUM_REGION", "us-central1"),
            queue=required["CONTINUUM_DEADLINE_QUEUE"], control_url=required["CONTINUUM_CONTROL_URL"],
            oidc_service_account=required["CONTINUUM_PUBSUB_PUSH_IDENTITY"]),
        investigator=RemoteInvestigator(http, required["CONTINUUM_V18_URL"]),
        authority=FirestoreAuthority(db, http, required["CONTINUUM_V17_URL"],
                                     required["CONTINUUM_V17_IDENTITY"]),
        compliance=RemoteSupplierAssurance(db, http, {
            "v18": (required["CONTINUUM_V18_URL"], required["CONTINUUM_V18_IDENTITY"]),
            "v19": (required["CONTINUUM_V19_URL"], required["CONTINUUM_V19_IDENTITY"]),
        }),
        effects=RoutedFirestoreSandboxEffects(db, http, {
            "v18": (required["CONTINUUM_V18_URL"], required["CONTINUUM_V18_IDENTITY"]),
            "v19": (required["CONTINUUM_V19_URL"], required["CONTINUUM_V19_IDENTITY"]),
        }),
        exporter=ObservedContractExporter(f'mailto:{required["CONTINUUM_CONTROL_IDENTITY"]}', f'mailto:{required["CONTINUUM_VERIFIER_IDENTITY"]}'),
        verifier=RemoteVerifier(http, required["CONTINUUM_VERIFIER_URL"], required["CONTINUUM_VERIFIER_IDENTITY"]),
        input_guard=GoogleModelArmorGuard(project=required["GOOGLE_CLOUD_PROJECT"],
            location=os.getenv("CONTINUUM_REGION", "us-central1"),
            template=required["CONTINUUM_MODEL_ARMOR_TEMPLATE"], post=armor_post),
        fleet_catalog=fleet_catalog,
        successor_candidates=deployed_candidates)

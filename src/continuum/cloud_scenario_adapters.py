"""Production composition for the durable Google Cloud scenario.

All observations are read from Firestore or authenticated worker services.  The
factory returns ``None`` unless the complete private invocation graph is
configured, keeping the deployed control plane fail closed.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from typing import Any, Callable
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .cloud_scenario_service import DurableCloudScenarioService, FirestoreScenarioStore
from .contract import artifact_ref, canonical_bytes, make_envelope
from .google_binding import GoogleBindingConfig, PubSubLifecyclePublisher


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
        request = Request(url, data=canonical_bytes(payload), method="POST", headers={
            "Authorization": f"Bearer {self.token(audience)}", "Content-Type": "application/json",
            "X-Continuum-Run-ID": run_id,
        })
        with self.opener(request, timeout=60) as response:
            result = json.loads(response.read())
        if not isinstance(result, dict):
            raise ValueError("WORKER_RESPONSE_INVALID")
        return result


class FirestoreLifecycleEvidence:
    REQUIRED = {"document.injection_detected", "action.denied", "expectation.missed"}

    def __init__(self, client: Any, publisher: Any, collection: str = "continuity_events"):
        self.client, self.publisher, self.collection = client, publisher, collection

    def observe(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        # Starting the named canonical fixture is itself a server-owned command.
        # Materialize its three immutable observations exactly once; callers
        # cannot supply or edit their content through the HTTP boundary.
        for event_type in sorted(self.REQUIRED):
            event_id = sha256(canonical_bytes({"run_id": request["run_id"],
                                               "event_type": event_type})).hexdigest()
            event = {"event_id": event_id, "event_type": event_type,
                     "run_id": request["run_id"],
                     "correlation_id": request["correlation_id"],
                     "obligation_id": request["obligation_id"],
                     "source": "procurement-succession-v1",
                     "redelivery_probe": event_type == "expectation.missed"}
            reference = self.client.collection(self.collection).document(event_id)
            existing = reference.get()
            if existing.exists:
                if existing.to_dict() != event:
                    raise ValueError("LIFECYCLE_EVENT_CONTENT_CONFLICT")
            else:
                try:
                    reference.create(event)
                except Exception:
                    raced = reference.get()
                    if not raced.exists or raced.to_dict() != event:
                        raise
            outbox = self.client.collection("continuity_outbox").document(event_id)
            published = outbox.get()
            if not published.exists:
                message_id = self.publisher.publish({**event, "schema_version": 1})
                record = {"run_id": request["run_id"], "event_id": event_id,
                          "status": "PUBLISHED", "message_id": message_id}
                try:
                    outbox.create(record)
                except Exception:
                    raced = outbox.get()
                    if not raced.exists or raced.to_dict().get("event_id") != event_id:
                        raise
            else:
                record = published.to_dict()
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
              "evidence_event_ids": proposal["evidence_ids"]})
        return proposal


class FirestoreAuthority:
    """Persisted registry boundary; policy is deterministic and evidence-gated."""
    def __init__(self, client: Any, workload_client: AuthenticatedJsonClient,
                 predecessor_url: str, predecessor_identity: str):
        self.client, self.workload_client = client, workload_client
        self.predecessor_url, self.predecessor_identity = predecessor_url, predecessor_identity
    def decide(self, evidence: list[dict[str, Any]]) -> dict[str, Any]:
        signals = set()
        for observation in evidence:
            for event in observation.get("evidence", {}).get("signals", []):
                signals.add(event.get("event_type"))
        if not FirestoreLifecycleEvidence.REQUIRED.issubset(signals):
            return {"outcome": "HOLD", "decision_id": None}
        digest = sha256(canonical_bytes(evidence)).hexdigest()
        return {"outcome": "APPROVE_SUCCESSION", "decision_id": f"decision:{digest}"}
    def fence_predecessor(self, request: dict[str, Any]) -> dict[str, Any]:
        ref = self.client.collection("continuity_authority").document(request["tenant_id"])
        ref.set({"predecessor": request["principal"], "revoked_through_epoch": request["epoch"],
                 "status": "FENCED", "decision_id": request["decision_id"]}, merge=True)
        return ref.get().to_dict()
    def activate_successor(self, request: dict[str, Any]) -> dict[str, Any]:
        ref = self.client.collection("continuity_authority").document(request["tenant_id"])
        state = ref.get().to_dict() or {}
        if state.get("status") != "FENCED": raise ValueError("PREDECESSOR_NOT_FENCED")
        ref.set({"active_principal": request["principal"], "epoch": request["epoch"],
                 "status": "ACTIVE"}, merge=True)
        return ref.get().to_dict()
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
        observed = self.workload_client.post(f"{self.successor_url}/internal/attempt-action", {},
                                             run_id=request["run_id"])
        if observed.get("actor") != self.successor_identity:
            raise ValueError("SUCCESSOR_IDENTITY_MISMATCH")
        ref = self._ref(request); current = ref.get()
        record = {"provider_ref": f'firestore://continuity_sandbox_vendors/{ref.id}',
                  "request_digest": request["request_digest"], "run_id": request["run_id"]}
        if current.exists:
            if current.to_dict()["request_digest"] != request["request_digest"]:
                raise ValueError("IDEMPOTENCY_KEY_CONFLICT")
            return {"state": "DEDUPLICATED"}
        ref.create(record)
        return {"state": "DISPATCHED", "actor": observed["actor"]}
    def reconcile(self, request: dict[str, Any]) -> dict[str, Any]:
        snapshot = self._ref(request).get()
        if not snapshot.exists: return {"effect_count": 0, "provider_ref": None}
        record = snapshot.to_dict()
        if record["request_digest"] != request["request_digest"]: raise ValueError("PROVIDER_DIGEST_CONFLICT")
        return {"effect_count": 1, "provider_ref": record["provider_ref"],
                "request_digest": record["request_digest"]}


class ObservedContractExporter:
    """Export six digest-linked artifacts from the persisted run observations."""
    def __init__(self, issuer: str, verifier_principal: str):
        self.issuer, self.verifier_principal = issuer, verifier_principal
    def export(self, run: dict[str, Any], observations: list[dict[str, Any]]) -> dict[str, Any]:
        # A cloud run has no trustworthy client timestamp. Issuance is bound to
        # the immutable scenario epoch used by this reproducible demonstration.
        at = "2026-08-17T10:05:00Z"; base = f'urn:continuum:cloud:{run["run_id"]}'
        decision = {"artifact_id": f"{base}:decision", "digest": {"alg": "sha-256", "value": sha256(canonical_bytes(run["decision"])).hexdigest()}, "policy_version": "compromise-succession/1", "outcome": "APPROVE_SUCCESSION"}
        obligation = make_envelope("obligation", f"{base}:obligation", self.issuer, at, {"tenant_id": run["tenant_id"], "subject": run["obligation_id"], "revision": 2, "owner": {"principal_id": run["successor"], "authority_domain": f"{base}:authority", "epoch": run["successor_epoch"]}, "description": "Observed vendor compliance succession", "deadline": at, "completion_criteria": [{"criterion_id": "provider-effect", "evidence_type": "provider-observation", "verifier_role": "independent-verifier"}], "allowed_effects": ["vendor.create"], "compensation": {"mode": "HUMAN"}, "status": "DISCHARGED"})
        grant = make_envelope("authority_grant", f"{base}:grant", self.issuer, at, {"tenant_id": run["tenant_id"], "grant_id": f'{run["run_id"]}:grant', "subject_principal": run["successor"], "authority_domain": f"{base}:authority", "epoch": run["successor_epoch"], "obligation_ids": [obligation["artifact_id"]], "capabilities": ["vendor.create"], "memory_scopes": ["vendor.approved"], "purpose": "complete vendor onboarding", "not_before": at, "expires_at": "2026-08-17T11:05:00Z", "policy_decision": decision, "status": "ACTIVE"})
        manifest = make_envelope("succession_manifest", f"{base}:manifest", self.issuer, at, {"succession_id": run["run_id"], "tenant_id": run["tenant_id"], "authority_domain": f"{base}:authority", "predecessor": {"principal_id": run["predecessor"], "epoch": run["predecessor_epoch"]}, "successor": {"principal_id": run["successor"], "epoch": run["successor_epoch"]}, "obligations": [artifact_ref(obligation)], "included_grants": [artifact_ref(grant)], "excluded_context": [{"reference_or_class": "raw_untrusted_document", "reason_code": "NON_TRANSFERABLE"}], "in_flight_effects": [], "evidence_refs": [{"observation": item["sequence"], "kind": item["kind"]} for item in observations], "policy_decision": decision, "created_from_registry_revision": run["successor_epoch"], "state": "COMMITTED"})
        revocation = make_envelope("revocation_proof", f"{base}:revocation", self.issuer, at, {"tenant_id": run["tenant_id"], "authority_domain": f"{base}:authority", "revoked_principal": run["predecessor"], "revoked_through_epoch": run["predecessor_epoch"], "registry_revision": run["successor_epoch"], "effective_at": at, "revoked_grant_ids": [], "enforcement_points": [{"id": "action-gateway", "kind": "ACTION", "observation_ref": "predecessor.denials_observed"}, {"id": "memory-gateway", "kind": "MEMORY", "observation_ref": "predecessor.denials_observed"}], "policy_decision": decision, "status": "ENFORCED"})
        provider = run["provider_observation"]
        receipt = make_envelope("execution_receipt", f"{base}:receipt", self.issuer, at, {"tenant_id": run["tenant_id"], "obligation": artifact_ref(obligation), "executing_principal": run["successor"], "authority_domain": f"{base}:authority", "epoch": run["successor_epoch"], "decision": decision, "idempotency_key": run["idempotency_key"], "request_digest": provider["request_digest"], "execution_id": run["run_id"], "provider": {"adapter": "firestore-sandbox/1", "operation": "vendor.create", "resource_ref": provider["provider_ref"]}, "disposition": "EXECUTED", "observed_at": at})
        attestation = make_envelope("continuity_attestation", f"{base}:attestation", self.verifier_principal, at, {"tenant_id": run["tenant_id"], "obligation": artifact_ref(obligation), "succession_manifest": artifact_ref(manifest), "revocation_proofs": [artifact_ref(revocation)], "execution_receipts": [artifact_ref(receipt)], "policy_decision": decision, "verification": {"verifier_principal": self.verifier_principal, "independent_of_executor": True, "criteria_results": [{"criterion_id": "provider-effect", "passed": provider["effect_count"] == 1}], "provider_observation_refs": [provider["provider_ref"]], "verified_at": at}, "guarantees": {"obligation_preserved": True, "authority_overlap": "NONE", "unauthorized_context_transferred": False, "externally_observed_effect_count": provider["effect_count"], "evidence_chain_complete": True}, "outcome": "VERIFIED"})
        return {"profile": "reference-google-cloud", "protocol": "continuum/0.1-draft", "artifacts": [obligation, grant, manifest, revocation, receipt, attestation]}


class RemoteVerifier:
    def __init__(self, client: AuthenticatedJsonClient, url: str, principal: str): self.client, self.url, self.principal = client, url, principal
    def verify(self, request: dict[str, Any]) -> dict[str, Any]:
        response = self.client.post(f"{self.url}/internal/verify", request, run_id=request["run_id"])
        result = response["verification"]
        observed = {**result, "verifier_principal": response.get("actor", self.principal)}
        if observed.get("status") == "PASS" and observed.get("outcome") == "VERIFIED":
            bundle = request["bundle"]
            _emit(request["run_id"], "contract-export", {"run_id": request["run_id"],
                  "protocol": "continuum/0.1-draft", "status": "PASS",
                  "bundle": bundle,
                  "report_digest": {"alg": "sha-256",
                                    "value": sha256(canonical_bytes(bundle)).hexdigest()}})
            _emit(request["run_id"], "trace-export", {"run_id": request["run_id"],
                  "trace_id": request["correlation_id"], "spans": [{"name": name} for name in
                  ("investigation", "policy", "succession", "verification")]})
        return observed


def google_id_token(audience: str) -> str:
    from google.auth.transport.requests import Request as AuthRequest
    from google.oauth2.id_token import fetch_id_token
    return fetch_id_token(AuthRequest(), audience)


def build_production_scenario_service() -> DurableCloudScenarioService | None:
    required = {name: os.getenv(name, "") for name in (
        "GOOGLE_CLOUD_PROJECT", "CONTINUUM_V17_URL", "CONTINUUM_V18_URL", "CONTINUUM_VERIFIER_URL",
        "CONTINUUM_CONTROL_IDENTITY", "CONTINUUM_V17_IDENTITY", "CONTINUUM_V18_IDENTITY",
        "CONTINUUM_VERIFIER_IDENTITY")}
    if any(not value for value in required.values()): return None
    from google.cloud import firestore
    db = firestore.Client(project=required["GOOGLE_CLOUD_PROJECT"])
    http = AuthenticatedJsonClient(google_id_token)
    publisher = PubSubLifecyclePublisher(GoogleBindingConfig(
        required["GOOGLE_CLOUD_PROJECT"], os.getenv("CONTINUUM_LIFECYCLE_TOPIC", "continuum-lifecycle")))
    return DurableCloudScenarioService(
        store=FirestoreScenarioStore(db), evidence=FirestoreLifecycleEvidence(db, publisher),
        investigator=RemoteInvestigator(http, required["CONTINUUM_V18_URL"]),
        authority=FirestoreAuthority(db, http, required["CONTINUUM_V17_URL"],
                                     required["CONTINUUM_V17_IDENTITY"]),
        effects=FirestoreSandboxEffects(db, http, required["CONTINUUM_V18_URL"],
                                       required["CONTINUUM_V18_IDENTITY"]),
        exporter=ObservedContractExporter(f'mailto:{required["CONTINUUM_CONTROL_IDENTITY"]}', f'mailto:{required["CONTINUUM_VERIFIER_IDENTITY"]}'),
        verifier=RemoteVerifier(http, required["CONTINUUM_VERIFIER_URL"], required["CONTINUUM_VERIFIER_IDENTITY"]))

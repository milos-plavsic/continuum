"""Independent, read-only continuity verification and attestation issuance."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Callable, Protocol

from .canonicalization import PROFILE as CANONICALIZATION_PROFILE
from .contract import ContractError, artifact_ref, canonical_bytes, make_envelope, validate_envelope
from .models import digest
from .incident_policy import verify_incident_evidence_chain
from .models import Denied
from .succession_selection import validate_selection_governance_receipt


PRE_ATTESTATION_TYPES = {
    "obligation", "authority_grant", "succession_manifest",
    "revocation_proof", "execution_receipt",
}


class VerificationReadPort(Protocol):
    def read_authority(self, run_id: str) -> dict[str, Any] | None: ...
    def read_compliance(self, run_id: str) -> dict[str, Any] | None: ...
    def read_provider(self, run_id: str) -> dict[str, Any] | None: ...


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class VerificationResult:
    status: str
    outcome: str
    reason_codes: tuple[str, ...]
    verifier_principal: str
    bundle: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status": self.status,
            "outcome": self.outcome,
            "verdict": self.outcome,
            "reason_codes": list(self.reason_codes),
            "verifier_principal": self.verifier_principal,
        }
        if self.bundle is not None:
            result["bundle"] = self.bundle
            attestation = self.bundle["artifacts"][-1]
            result["attestation_digest"] = attestation["digest"]
            result["bundle_digest"] = sha256(canonical_bytes(self.bundle)).hexdigest()
        return result


class IndependentVerificationEngine:
    """Recomputes evidence claims from provider state and alone issues attestation."""

    def __init__(self, reader: VerificationReadPort, *,
                 clock: Callable[[], str] = utc_now):
        self.reader = reader
        self.clock = clock

    def verify(self, *, run_id: str, bundle: dict[str, Any],
               verifier_principal: str) -> dict[str, Any]:
        try:
            indexed = self._validate_pre_attestation_bundle(bundle)
        except (ContractError, KeyError, TypeError, ValueError) as error:
            return VerificationResult(
                "FAIL", "FAILED", (self._reason(error, "ARTIFACT_CHAIN_INVALID"),),
                verifier_principal,
            ).to_dict()

        authority = self.reader.read_authority(run_id)
        compliance = self.reader.read_compliance(run_id)
        provider = self.reader.read_provider(run_id)
        missing = tuple(name for name, value in (
            ("AUTHORITY_OBSERVATION_MISSING", authority),
            ("COMPLIANCE_OBSERVATION_MISSING", compliance),
            ("PROVIDER_OBSERVATION_MISSING", provider),
        ) if value is None)
        if missing:
            return VerificationResult(
                "INCONCLUSIVE", "INCONCLUSIVE", missing, verifier_principal,
            ).to_dict()

        assert authority is not None and compliance is not None and provider is not None
        failures = self._compare(indexed, authority, compliance, provider)
        if failures:
            return VerificationResult(
                "FAIL", "FAILED", tuple(failures), verifier_principal,
            ).to_dict()

        artifacts = list(bundle["artifacts"])
        attestation = self._attestation(
            run_id, indexed, verifier_principal, provider, self.clock())
        verified_bundle = {**bundle, "artifacts": [*artifacts, attestation]}
        return VerificationResult(
            "PASS", "VERIFIED", ("INDEPENDENT_READS_MATCH",),
            verifier_principal, verified_bundle,
        ).to_dict()

    @staticmethod
    def _reason(error: Exception, fallback: str) -> str:
        value = str(error).split(":", 1)[0]
        return value if value and value.replace("_", "").isalnum() else fallback

    @staticmethod
    def _validate_pre_attestation_bundle(bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
        if bundle.get("protocol") != "continuum/0.1-draft":
            raise ContractError("UNSUPPORTED_PROTOCOL")
        if bundle.get("canonicalization_profile") != CANONICALIZATION_PROFILE:
            raise ContractError("UNSUPPORTED_CANONICALIZATION_PROFILE")
        artifacts = bundle.get("artifacts")
        if (not isinstance(artifacts, list) or len(artifacts) != 5 or
                {item.get("artifact_type") for item in artifacts if isinstance(item, dict)} != PRE_ATTESTATION_TYPES):
            raise ContractError("PRE_ATTESTATION_ARTIFACT_SET_INVALID")
        indexed: dict[str, dict[str, Any]] = {}
        for artifact in artifacts:
            validate_envelope(artifact)
            if artifact["artifact_id"] in indexed:
                raise ContractError("DUPLICATE_ARTIFACT_ID")
            indexed[artifact["artifact_id"]] = artifact
        by_type = {artifact["artifact_type"]: artifact for artifact in artifacts}
        obligation, grant, manifest, receipt = (
            by_type["obligation"], by_type["authority_grant"],
            by_type["succession_manifest"], by_type["execution_receipt"],
        )
        IndependentVerificationEngine._require_ref(manifest["body"]["obligations"][0], obligation)
        IndependentVerificationEngine._require_ref(manifest["body"]["included_grants"][0], grant)
        IndependentVerificationEngine._require_ref(receipt["body"]["obligation"], obligation)
        IndependentVerificationEngine._validate_handoff_extensions(manifest)
        return by_type

    @staticmethod
    def _validate_handoff_extensions(manifest: dict[str, Any]) -> None:
        extensions = manifest.get("extensions", {})
        selection = extensions.get("continuum.dev/successor-selection")
        selection_governance = extensions.get("continuum.dev/selection-governance")
        reconstruction = extensions.get("continuum.dev/context-reconstruction")
        incident = extensions.get("continuum.dev/incident-evidence")
        if (not isinstance(selection, dict) or not isinstance(selection_governance, dict)
                or not isinstance(reconstruction, dict)
                or not isinstance(incident, dict)):
            raise ContractError("HANDOFF_EVIDENCE_MISSING")
        if set(incident) != {"subject", "records", "evidence_validation", "incident_assessment"}:
            raise ContractError("INCIDENT_EVIDENCE_SCHEMA_INVALID")
        try:
            verify_incident_evidence_chain(
                records=incident["records"], evidence_receipt=incident["evidence_validation"],
                incident_receipt=incident["incident_assessment"], subject=incident["subject"])
        except Denied as error:
            raise ContractError(str(error)) from error
        selection_body = {
            "requirements": selection.get("requirements_digest"),
            "candidates": selection.get("candidates_digest"),
            "assessments": selection.get("assessments"),
        }
        if selection.get("receipt_digest") != digest(selection_body):
            raise ContractError("SUCCESSOR_ASSESSMENT_DIGEST_MISMATCH")
        try:
            validate_selection_governance_receipt(
                governance=selection_governance,
                assessment=selection,
                successor_id=manifest["body"]["successor"]["principal_id"],
            )
        except Denied as error:
            raise ContractError(str(error)) from error
        reconstruction_body = {
            "succession_id": reconstruction.get("succession_id"),
            "successor_principal": reconstruction.get("successor_principal"),
            "purpose": reconstruction.get("purpose"),
            "allowed_scopes": reconstruction.get("allowed_scopes"),
            "decisions": reconstruction.get("decisions"),
        }
        if reconstruction.get("receipt_digest") != digest(reconstruction_body):
            raise ContractError("CONTEXT_RECONSTRUCTION_DIGEST_MISMATCH")
        if reconstruction.get("successor_principal") != manifest["body"]["successor"]["principal_id"]:
            raise ContractError("CONTEXT_SUCCESSOR_MISMATCH")
        decisions = reconstruction.get("decisions")
        if (not isinstance(decisions, list) or not any(item.get("included") for item in decisions)
                or not any(not item.get("included") for item in decisions)):
            raise ContractError("CONTEXT_DECISIONS_INCOMPLETE")

    @staticmethod
    def _require_ref(reference: dict[str, Any], target: dict[str, Any]) -> None:
        if (reference.get("artifact_id") != target["artifact_id"] or
                reference.get("artifact_type") != target["artifact_type"] or
                reference.get("digest") != target["digest"]):
            raise ContractError("BROKEN_ARTIFACT_REFERENCE")

    @staticmethod
    def _compare(artifacts: dict[str, dict[str, Any]], authority: dict[str, Any],
                 compliance: dict[str, Any], provider: dict[str, Any]) -> list[str]:
        obligation = artifacts["obligation"]
        grant = artifacts["authority_grant"]
        manifest = artifacts["succession_manifest"]
        revocation = artifacts["revocation_proof"]
        receipt = artifacts["execution_receipt"]
        failures: list[str] = []
        successor = manifest["body"]["successor"]
        predecessor = manifest["body"]["predecessor"]
        if (authority.get("active_principal") != successor["principal_id"] or
                authority.get("epoch") != successor["epoch"] or
                authority.get("revoked_through_epoch", -1) < predecessor["epoch"]):
            failures.append("AUTHORITY_STATE_MISMATCH")
        if (grant["body"]["subject_principal"] != successor["principal_id"] or
                grant["body"]["epoch"] != successor["epoch"] or
                grant["body"]["status"] != "ACTIVE"):
            failures.append("GRANT_SUCCESSOR_BINDING_MISMATCH")
        if (revocation["body"]["revoked_principal"] != predecessor["principal_id"] or
                revocation["body"]["revoked_through_epoch"] < predecessor["epoch"] or
                revocation["body"]["status"] != "ENFORCED"):
            failures.append("REVOCATION_STATE_MISMATCH")
        compliance_claim = receipt.get("extensions", {}).get("continuum.dev/compliance", {})
        if (compliance.get("status") != "VERIFIED" or
                compliance.get("obligation_id") != compliance_claim.get("obligation_id") or
                compliance.get("evidence_id") != compliance_claim.get("evidence_id") or
                compliance.get("document_hash") != compliance_claim.get("document_hash")):
            failures.append("COMPLIANCE_STATE_MISMATCH")
        if "workflow" in compliance_claim and (
                compliance_claim.get("workflow") != "SUPPLIER_ASSURANCE_AGENT" or
                compliance_claim.get("decision_scope") != "SANDBOX_ONLY" or
                compliance_claim.get("recommendation") != "ONBOARD" or
                not compliance_claim.get("decision_pack_digest") or
                any(compliance.get(key) != compliance_claim.get(key) for key in (
                    "workflow", "decision_scope", "recommendation", "decision_pack_digest"))):
            failures.append("SUPPLIER_ASSURANCE_STATE_MISMATCH")
        provider_body = receipt["body"]["provider"]
        if (provider.get("effect_count") != 1 or
                provider.get("provider_ref") != provider_body["resource_ref"] or
                provider.get("request_digest") != receipt["body"]["request_digest"] or
                provider.get("compliance_evidence_id") != compliance.get("evidence_id")):
            failures.append("PROVIDER_STATE_MISMATCH")
        if (receipt["body"]["executing_principal"] != successor["principal_id"] or
                receipt["body"]["epoch"] != successor["epoch"] or
                receipt["body"]["disposition"] != "EXECUTED"):
            failures.append("EXECUTION_SUCCESSOR_BINDING_MISMATCH")
        return failures

    @staticmethod
    def _attestation(run_id: str, artifacts: dict[str, dict[str, Any]],
                     verifier_principal: str, provider: dict[str, Any],
                     issued_at: str) -> dict[str, Any]:
        obligation = artifacts["obligation"]
        manifest = artifacts["succession_manifest"]
        revocation = artifacts["revocation_proof"]
        receipt = artifacts["execution_receipt"]
        return make_envelope(
            "continuity_attestation",
            f"urn:continuum:cloud:{run_id}:attestation",
            verifier_principal,
            issued_at,
            {
                "tenant_id": obligation["body"]["tenant_id"],
                "obligation": artifact_ref(obligation),
                "succession_manifest": artifact_ref(manifest),
                "revocation_proofs": [artifact_ref(revocation)],
                "execution_receipts": [artifact_ref(receipt)],
                "policy_decision": manifest["body"]["policy_decision"],
                "verification": {
                    "verifier_principal": verifier_principal,
                    "independent_of_executor": verifier_principal != receipt["body"]["executing_principal"],
                    "criteria_results": [
                        {"criterion_id": "compliance-verified", "passed": True},
                        {"criterion_id": "provider-effect-once", "passed": True},
                        {"criterion_id": "predecessor-revoked", "passed": True},
                    ] + ([{"criterion_id": "supplier-assurance-admitted", "passed": True}]
                         if receipt.get("extensions", {}).get(
                             "continuum.dev/compliance", {}).get("workflow")
                         == "SUPPLIER_ASSURANCE_AGENT" else []),
                    "provider_observation_refs": [provider["provider_ref"]],
                    "verified_at": issued_at,
                },
                "guarantees": {
                    "obligation_preserved": True,
                    "authority_overlap": "NONE",
                    "unauthorized_context_transferred": False,
                    "externally_observed_effect_count": 1,
                    "evidence_chain_complete": True,
                },
                "outcome": "VERIFIED",
            },
        )


class FirestoreVerificationReader:
    """Read-only evidence adapter intended for the verifier service account."""

    def __init__(self, client: Any):
        self.client = client

    @staticmethod
    def _single(query: Any) -> dict[str, Any] | None:
        values = [snapshot.to_dict() for snapshot in query.stream()]
        if not values:
            return None
        if len(values) != 1:
            return {"observation_count": len(values)}
        return values[0]

    def read_authority(self, run_id: str) -> dict[str, Any] | None:
        return self._single(self.client.collection("continuity_authority").where(
            "run_id", "==", run_id))

    def read_compliance(self, run_id: str) -> dict[str, Any] | None:
        snapshot = self.client.collection("continuity_compliance").document(run_id).get()
        return snapshot.to_dict() if snapshot.exists else None

    def read_provider(self, run_id: str) -> dict[str, Any] | None:
        values = [snapshot.to_dict() for snapshot in self.client.collection(
            "continuity_sandbox_vendors").where("run_id", "==", run_id).stream()]
        if not values:
            return None
        first = values[0]
        external = first.get("external_effect")
        observed = ({**first, **external}
                    if isinstance(external, dict) else first)
        return {**observed, "effect_count": len(values)}

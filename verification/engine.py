"""
Continuum: Independent Verification Engine
File: verification/engine.py

Read-only verifier that recomputes evidence digests and enforces
fencing validation without invoking execution pathways.
"""

import hashlib
import json
from typing import Dict, Any
from datetime import datetime, timezone
from verification.schemas import (
    VerificationVerdict,
    EvidenceDigest,
    ContinuityAttestation,
)


class IndependentVerifier:
    """Zero-trust, read-only audit engine for agent succession."""

    def __init__(self, firestore_db_client, otel_tracer):
        self.db = firestore_db_client
        self.tracer = otel_tracer

    @staticmethod
    def recompute_digest(payload: Dict[str, Any], timestamp_str: str, predecessor_id: str) -> EvidenceDigest:
        """Independently recalculates SHA-256 digest from raw payload bytes."""
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest_input = f"{canonical_json}|{timestamp_str}|{predecessor_id}".encode("utf-8")
        computed_hash = hashlib.sha256(digest_input).hexdigest()

        return EvidenceDigest(
            digest_hash=computed_hash,
            algorithm="sha256",
            canonical_keys=sorted(list(payload.keys())),
        )

    def verify_succession(
        self,
        attestation_id: str,
        obligation_id: str,
        raw_payload: Dict[str, Any],
        reported_digest: str,
        predecessor_fenced: bool,
        side_effect_count: int,
        telemetry_complete: bool,
        trace_id: str,
        span_id: str,
    ) -> ContinuityAttestation:
        """Evaluates raw evidence and returns a deterministic 3-valued verdict."""
        
        with self.tracer.start_as_current_span("verification.verify_succession") as otel_span:
            otel_span.set_attribute("continuum.obligation_id", obligation_id)

            if not telemetry_complete:
                otel_span.set_attribute("continuum.verdict", VerificationVerdict.INCONCLUSIVE)
                return self._build_attestation(
                    attestation_id, obligation_id, VerificationVerdict.INCONCLUSIVE,
                    raw_payload, predecessor_fenced=False, at_most_once=False,
                    trace_id=trace_id, span_id=span_id
                )

            now_iso = datetime.now(timezone.utc).isoformat()
            digest_obj = self.recompute_digest(raw_payload, now_iso, "procurement-agent-v17")

            hashes_match = (digest_obj.digest_hash == reported_digest)
            at_most_once = (side_effect_count == 1)

            if hashes_match and predecessor_fenced and at_most_once:
                verdict = VerificationVerdict.VERIFIED
            else:
                verdict = VerificationVerdict.FAILED

            otel_span.set_attribute("continuum.verdict", verdict)

            return ContinuityAttestation(
                attestation_id=attestation_id,
                obligation_id=obligation_id,
                verdict=verdict,
                predecessor_id="procurement-agent-v17",
                successor_id="procurement-agent-v18",
                predecessor_fenced=predecessor_fenced,
                at_most_once_verified=at_most_once,
                computed_digest=digest_obj,
                trace_id=trace_id,
                span_id=span_id,
            )

    def _build_attestation(self, attestation_id, obligation_id, verdict, payload, predecessor_fenced, at_most_once, trace_id, span_id):
        now_iso = datetime.now(timezone.utc).isoformat()
        digest_obj = self.recompute_digest(payload, now_iso, "procurement-agent-v17")
        return ContinuityAttestation(
            attestation_id=attestation_id,
            obligation_id=obligation_id,
            verdict=verdict,
            predecessor_fenced=predecessor_fenced,
            at_most_once_verified=at_most_once,
            computed_digest=digest_obj,
            trace_id=trace_id,
            span_id=span_id,
        )



    
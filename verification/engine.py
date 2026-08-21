"""
Continuum: Verification Engine
File: verification/engine.py
"""

from datetime import datetime, timezone
import logging
from typing import Optional
from verification.schemas import (
    VerificationRequest,
    VerificationResult,
    VerificationStatus,
)
from verification.provider import EvidenceProvider
from verification.replay import ReplayGuard

logger = logging.getLogger("VerificationEngine")


class VerificationEngine:
    def __init__(self, verifier_id: str, provider: EvidenceProvider, replay_guard: ReplayGuard):
        self.verifier_id = verifier_id
        self.provider = provider
        self.replay_guard = replay_guard

    def verify_execution(
        self,
        request: VerificationRequest,
        current_time_iso: Optional[str] = None
    ) -> VerificationResult:
        now_dt = (
            datetime.fromisoformat(current_time_iso)
            if current_time_iso
            else datetime.now(timezone.utc)
        )
        now_iso = now_dt.isoformat()

        # Guard 1: Executor Cannot Be Self-Verifier
        if request.executor_id == self.verifier_id:
            return self._build_result(
                request=request,
                status=VerificationStatus.REJECTED,
                predecessor_fenced=False,
                execution_count=-1,
                telemetry_verified=False,
                timestamp=now_iso,
                reasoning="Conflict of Interest: Executor cannot act as self-verifier."
            )

        # Guard 2: Request Timestamp & TTL Expiration Check
        age_seconds = (now_dt - request.issued_at).total_seconds()
        if age_seconds < 0 or age_seconds > request.ttl_seconds:
            return self._build_result(
                request=request,
                status=VerificationStatus.REJECTED,
                predecessor_fenced=False,
                execution_count=-1,
                telemetry_verified=False,
                timestamp=now_iso,
                reasoning=f"Request expired or invalid timestamp. Age: {age_seconds}s (TTL: {request.ttl_seconds}s)."
            )

        # Guard 3: Atomic Nonce Consumption (Replay Protection)
        if not self.replay_guard.consume_nonce(request.tenant_id, request.nonce, request.ttl_seconds):
            return self._build_result(
                request=request,
                status=VerificationStatus.REJECTED,
                predecessor_fenced=False,
                execution_count=-1,
                telemetry_verified=False,
                timestamp=now_iso,
                reasoning=f"Replay Attack Detected: Nonce '{request.nonce}' has already been consumed."
            )

        # Guard 4: Authoritative Identity Binding Verification
        auth_binding = self.provider.get_authority_binding(request.tenant_id, request.obligation_id)
        if auth_binding:
            if request.predecessor_id != auth_binding.predecessor_id or request.successor_id != auth_binding.successor_id:
                return self._build_result(
                    request=request,
                    status=VerificationStatus.REJECTED,
                    predecessor_fenced=False,
                    execution_count=-1,
                    telemetry_verified=False,
                    timestamp=now_iso,
                    reasoning=f"Authority Mismatch: Binding ({auth_binding.predecessor_id} -> {auth_binding.successor_id}) does not match request."
                )

        # Query Ground Truth via EvidenceProvider Boundary
        is_fenced = self.provider.get_agent_fencing_status(
            tenant_id=request.tenant_id,
            agent_id=request.predecessor_id
        )
        side_effect_count = self.provider.get_side_effect_count(
            tenant_id=request.tenant_id,
            obligation_id=request.obligation_id,
            effect_type=request.target_effect_type
        )
        telemetry_ok = self.provider.is_telemetry_complete(
            tenant_id=request.tenant_id,
            obligation_id=request.obligation_id
        )

        # Guard 5: Predecessor Must Be Fenced
        if not is_fenced:
            return self._build_result(
                request=request,
                status=VerificationStatus.QUARANTINED,
                predecessor_fenced=False,
                execution_count=side_effect_count,
                telemetry_verified=telemetry_ok,
                timestamp=now_iso,
                reasoning=f"Predecessor '{request.predecessor_id}' is NOT fenced in authority records."
            )

        # Guard 6: At-Most-Once Execution Safety Check
        if side_effect_count >= 1:
            return self._build_result(
                request=request,
                status=VerificationStatus.REJECTED,
                predecessor_fenced=True,
                execution_count=side_effect_count,
                telemetry_verified=telemetry_ok,
                timestamp=now_iso,
                reasoning=f"At-Most-Once Violation: Effect '{request.target_effect_type}' executed {side_effect_count} times."
            )

        # Guard 7: Telemetry Evidence Completeness Gating
        if not telemetry_ok:
            return self._build_result(
                request=request,
                status=VerificationStatus.QUARANTINED,
                predecessor_fenced=True,
                execution_count=side_effect_count,
                telemetry_verified=False,
                timestamp=now_iso,
                reasoning="Verification Incomplete: Telemetry evidence traces are missing or incomplete."
            )

        # Success: All Independent Evidence Validated
        return self._build_result(
            request=request,
            status=VerificationStatus.VERIFIED,
            predecessor_fenced=True,
            execution_count=0,
            telemetry_verified=True,
            timestamp=now_iso,
            reasoning="Independent Evidence Verified: Predecessor fenced, zero prior side-effects, telemetry complete."
        )

    def _build_result(
        self,
        request: VerificationRequest,
        status: VerificationStatus,
        predecessor_fenced: bool,
        execution_count: int,
        telemetry_verified: bool,
        timestamp: str,
        reasoning: str
    ) -> VerificationResult:
        result = VerificationResult(
            status=status,
            obligation_id=request.obligation_id,
            tenant_id=request.tenant_id,
            verifier_id=self.verifier_id,
            predecessor_id=request.predecessor_id,
            successor_id=request.successor_id,
            predecessor_fenced=predecessor_fenced,
            execution_count=execution_count,
            telemetry_verified=telemetry_verified,
            nonce=request.nonce,
            timestamp=timestamp,
            reasoning=reasoning,
            digest=None
        )
        result.digest = result.compute_digest()
        return result
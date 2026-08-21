"""
Continuum: Verification Engine
File: src/verification/engine.py
"""

from datetime import datetime, timezone
import logging
from typing import Optional, Callable
from verification.schemas import VerificationRequest, VerificationResult, VerificationStatus
from verification.provider import EvidenceProvider
from verification.replay import ReplayGuard, ReplayCheckOutcome

logger = logging.getLogger("VerificationEngine")


class VerificationEngine:
    def __init__(
        self,
        verifier_id: str,
        provider: EvidenceProvider,
        replay_guard: ReplayGuard,
        clock: Optional[Callable[[], datetime]] = None
    ):
        self.verifier_id = verifier_id
        self.provider = provider
        self.replay_guard = replay_guard
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def verify_execution(self, request: VerificationRequest) -> VerificationResult:
        now_dt = self.clock()
        now_iso = now_dt.isoformat()

        # Guard 1: Workload Identity Block (Executor Cannot Be Self-Verifier)
        if request.executor_id == self.verifier_id:
            return VerificationResult.create(
                status=VerificationStatus.REJECTED,
                obligation_id=request.obligation_id,
                tenant_id=request.tenant_id,
                verifier_id=self.verifier_id,
                predecessor_id=request.predecessor_id,
                successor_id=request.successor_id,
                predecessor_fenced=False,
                execution_count=-1,
                telemetry_verified=False,
                nonce=request.nonce,
                timestamp=now_iso,
                reasoning="Conflict of Interest: Authenticated executor identity matches verifier."
            )

        # Guard 2: Request Expiration & TTL Check
        age_seconds = (now_dt - request.issued_at).total_seconds()
        if age_seconds < 0 or age_seconds > request.ttl_seconds:
            return VerificationResult.create(
                status=VerificationStatus.REJECTED,
                obligation_id=request.obligation_id,
                tenant_id=request.tenant_id,
                verifier_id=self.verifier_id,
                predecessor_id=request.predecessor_id,
                successor_id=request.successor_id,
                predecessor_fenced=False,
                execution_count=-1,
                telemetry_verified=False,
                nonce=request.nonce,
                timestamp=now_iso,
                reasoning=f"Request expired or invalid timestamp. Age: {age_seconds}s (TTL: {request.ttl_seconds}s)."
            )

        # Guard 3: Atomic Replay Check with Storage Outage Handling
        replay_outcome = self.replay_guard.consume_nonce(request.tenant_id, request.nonce, request.ttl_seconds)
        if replay_outcome == ReplayCheckOutcome.REPLAY_DETECTED:
            return VerificationResult.create(
                status=VerificationStatus.REJECTED,
                obligation_id=request.obligation_id,
                tenant_id=request.tenant_id,
                verifier_id=self.verifier_id,
                predecessor_id=request.predecessor_id,
                successor_id=request.successor_id,
                predecessor_fenced=False,
                execution_count=-1,
                telemetry_verified=False,
                nonce=request.nonce,
                timestamp=now_iso,
                reasoning=f"Replay Attack Detected: Nonce '{request.nonce}' has already been consumed."
            )
        elif replay_outcome == ReplayCheckOutcome.STORAGE_UNAVAILABLE:
            return VerificationResult.create(
                status=VerificationStatus.INCONCLUSIVE,
                obligation_id=request.obligation_id,
                tenant_id=request.tenant_id,
                verifier_id=self.verifier_id,
                predecessor_id=request.predecessor_id,
                successor_id=request.successor_id,
                predecessor_fenced=False,
                execution_count=-1,
                telemetry_verified=False,
                nonce=request.nonce,
                timestamp=now_iso,
                reasoning="Evidence Storage Unavailable: Unable to access nonce registry."
            )

        # Guard 4: Authoritative Identity Binding (Fail Closed if Missing)
        auth_binding = self.provider.get_authority_binding(request.tenant_id, request.obligation_id)
        if auth_binding is None:
            return VerificationResult.create(
                status=VerificationStatus.QUARANTINED,
                obligation_id=request.obligation_id,
                tenant_id=request.tenant_id,
                verifier_id=self.verifier_id,
                predecessor_id=request.predecessor_id,
                successor_id=request.successor_id,
                predecessor_fenced=False,
                execution_count=-1,
                telemetry_verified=False,
                nonce=request.nonce,
                timestamp=now_iso,
                reasoning=f"Missing Evidence: No authoritative identity record found for obligation '{request.obligation_id}'."
            )

        if request.predecessor_id != auth_binding.predecessor_id or request.successor_id != auth_binding.successor_id:
            return VerificationResult.create(
                status=VerificationStatus.REJECTED,
                obligation_id=request.obligation_id,
                tenant_id=request.tenant_id,
                verifier_id=self.verifier_id,
                predecessor_id=request.predecessor_id,
                successor_id=request.successor_id,
                predecessor_fenced=False,
                execution_count=-1,
                telemetry_verified=False,
                nonce=request.nonce,
                timestamp=now_iso,
                reasoning=f"Authority Mismatch: Request claims ({request.predecessor_id} -> {request.successor_id}) but system binding specifies ({auth_binding.predecessor_id} -> {auth_binding.successor_id})."
            )

        # Query Ground-Truth Evidence Storage
        is_fenced = self.provider.get_agent_fencing_status(request.tenant_id, request.predecessor_id)
        side_effect_count = self.provider.get_side_effect_count(request.tenant_id, request.obligation_id, request.target_effect_type)
        telemetry_ok = self.provider.is_telemetry_complete(request.tenant_id, request.obligation_id)

        # Guard 5: Predecessor Must Be Fenced
        if not is_fenced:
            return VerificationResult.create(
                status=VerificationStatus.QUARANTINED,
                obligation_id=request.obligation_id,
                tenant_id=request.tenant_id,
                verifier_id=self.verifier_id,
                predecessor_id=request.predecessor_id,
                successor_id=request.successor_id,
                predecessor_fenced=False,
                execution_count=side_effect_count,
                telemetry_verified=telemetry_ok,
                nonce=request.nonce,
                timestamp=now_iso,
                reasoning=f"Predecessor '{request.predecessor_id}' is NOT fenced in authority records."
            )

        # Guard 6: At-Most-Once Execution Safety Check
        if side_effect_count >= 1:
            return VerificationResult.create(
                status=VerificationStatus.REJECTED,
                obligation_id=request.obligation_id,
                tenant_id=request.tenant_id,
                verifier_id=self.verifier_id,
                predecessor_id=request.predecessor_id,
                successor_id=request.successor_id,
                predecessor_fenced=True,
                execution_count=side_effect_count,
                telemetry_verified=telemetry_ok,
                nonce=request.nonce,
                timestamp=now_iso,
                reasoning=f"At-Most-Once Violation: Target effect '{request.target_effect_type}' has executed {side_effect_count} times."
            )

        # Guard 7: Telemetry Evidence Completeness
        if not telemetry_ok:
            return VerificationResult.create(
                status=VerificationStatus.QUARANTINED,
                obligation_id=request.obligation_id,
                tenant_id=request.tenant_id,
                verifier_id=self.verifier_id,
                predecessor_id=request.predecessor_id,
                successor_id=request.successor_id,
                predecessor_fenced=True,
                execution_count=side_effect_count,
                telemetry_verified=False,
                nonce=request.nonce,
                timestamp=now_iso,
                reasoning="Verification Incomplete: Telemetry trace evidence is missing or incomplete."
            )

        return VerificationResult.create(
            status=VerificationStatus.VERIFIED,
            obligation_id=request.obligation_id,
            tenant_id=request.tenant_id,
            verifier_id=self.verifier_id,
            predecessor_id=request.predecessor_id,
            successor_id=request.successor_id,
            predecessor_fenced=True,
            execution_count=0,
            telemetry_verified=True,
            nonce=request.nonce,
            timestamp=now_iso,
            reasoning="Independent Evidence Verified: Predecessor fenced, zero prior side-effects, telemetry complete."
        )
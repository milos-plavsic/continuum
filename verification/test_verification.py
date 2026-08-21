"""
Continuum: Verification Engine Red-Team Test Suite
File: verification/test_verification.py
"""

import pytest
from verification.schemas import VerificationRequest, VerificationStatus, VerificationResult
from verification.provider import EvidenceProvider
from verification.engine import VerificationEngine


class MockEvidenceProvider(EvidenceProvider):
    def __init__(self):
        self.fenced_agents = set()
        self.side_effects = {}
        self.telemetry_states = {}
        self.used_nonces = set()

    def get_agent_fencing_status(self, tenant_id: str, agent_id: str) -> bool:
        return (tenant_id, agent_id) in self.fenced_agents

    def get_side_effect_count(self, tenant_id: str, obligation_id: str, effect_type: str) -> int:
        return self.side_effects.get((tenant_id, obligation_id, effect_type), 0)

    def is_telemetry_complete(self, tenant_id: str, obligation_id: str) -> bool:
        return self.telemetry_states.get((tenant_id, obligation_id), True)

    def get_nonce_used(self, tenant_id: str, nonce: str) -> bool:
        return (tenant_id, nonce) in self.used_nonces

    def record_nonce(self, tenant_id: str, nonce: str, ttl_seconds: int) -> None:
        self.used_nonces.add((tenant_id, nonce))


@pytest.fixture
def mock_provider():
    return MockEvidenceProvider()


@pytest.fixture
def engine(mock_provider):
    return VerificationEngine(verifier_id="continuum-independent-verifier", provider=mock_provider)


def test_valid_verification_with_deterministic_clock(engine, mock_provider):
    timestamp_iso = "2026-08-21T18:00:00+00:00"
    mock_provider.fenced_agents.add(("tenant-alpha", "agent-v17"))

    req = VerificationRequest(
        obligation_id="obl-procure-1001",
        tenant_id="tenant-alpha",
        executor_id="orchestrator-agent",
        predecessor_id="agent-v17",
        successor_id="agent-v18",
        target_effect_type="VENDOR_PAYMENT",
        nonce="nonce-unique-001",
        issued_at=timestamp_iso,
        ttl_seconds=300
    )

    result = engine.verify_execution(req, current_time_iso=timestamp_iso)

    assert result.status == VerificationStatus.VERIFIED
    assert result.digest is not None
    assert result.digest == result.compute_digest()


def test_redteam_executor_cannot_self_verify(mock_provider):
    self_verifier_engine = VerificationEngine(verifier_id="malicious-agent", provider=mock_provider)
    timestamp_iso = "2026-08-21T18:00:00+00:00"

    req = VerificationRequest(
        obligation_id="obl-procure-1001",
        tenant_id="tenant-alpha",
        executor_id="malicious-agent",
        predecessor_id="agent-v17",
        successor_id="agent-v18",
        target_effect_type="VENDOR_PAYMENT",
        nonce="nonce-unique-002",
        issued_at=timestamp_iso
    )

    result = self_verifier_engine.verify_execution(req, current_time_iso=timestamp_iso)
    assert result.status == VerificationStatus.REJECTED
    assert "Conflict of Interest" in result.reasoning


def test_redteam_mutated_evidence_digest_mismatch():
    result = VerificationResult(
        status=VerificationStatus.VERIFIED,
        obligation_id="obl-procure-1001",
        tenant_id="tenant-alpha",
        verifier_id="verifier-id",
        predecessor_id="agent-v17",
        successor_id="agent-v18",
        predecessor_fenced=True,
        execution_count=0,
        telemetry_verified=True,
        nonce="nonce-1",
        timestamp="2026-08-21T18:00:00+00:00",
        reasoning="All valid",
        digest=None
    )
    result.digest = result.compute_digest()
    result.execution_count = 1
    assert result.compute_digest() != result.digest


def test_redteam_nonce_replay_attack(engine, mock_provider):
    timestamp_iso = "2026-08-21T18:00:00+00:00"
    mock_provider.fenced_agents.add(("tenant-alpha", "agent-v17"))

    req = VerificationRequest(
        obligation_id="obl-procure-1001",
        tenant_id="tenant-alpha",
        executor_id="orchestrator",
        predecessor_id="agent-v17",
        successor_id="agent-v18",
        target_effect_type="VENDOR_PAYMENT",
        nonce="reused-nonce-999",
        issued_at=timestamp_iso
    )

    res1 = engine.verify_execution(req, current_time_iso=timestamp_iso)
    assert res1.status == VerificationStatus.VERIFIED

    res2 = engine.verify_execution(req, current_time_iso=timestamp_iso)
    assert res2.status == VerificationStatus.REJECTED
    assert "Replay Attack Detected" in res2.reasoning
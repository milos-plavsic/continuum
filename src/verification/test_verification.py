"""
Continuum: Verification Engine Red-Team & Integration Test Suite
File: src/verification/test_verification.py
"""

from datetime import datetime, timezone
import pytest

from verification.schemas import VerificationRequest, VerificationStatus, VerificationResult
from verification.provider import EvidenceProvider, AuthorityBinding
from verification.replay import ReplayGuard, ReplayCheckOutcome
from verification.engine import VerificationEngine


class MockEvidenceProvider(EvidenceProvider):
    def __init__(self):
        self.fenced_agents = set()
        self.side_effects = {}
        self.telemetry_states = {}
        self.authority_bindings = {}

    def get_agent_fencing_status(self, tenant_id: str, agent_id: str) -> bool:
        return (tenant_id, agent_id) in self.fenced_agents

    def get_side_effect_count(self, tenant_id: str, obligation_id: str, effect_type: str) -> int:
        return self.side_effects.get((tenant_id, obligation_id, effect_type), 0)

    def is_telemetry_complete(self, tenant_id: str, obligation_id: str) -> bool:
        return self.telemetry_states.get((tenant_id, obligation_id), True)

    def get_authority_binding(self, tenant_id: str, obligation_id: str):
        return self.authority_bindings.get((tenant_id, obligation_id))


class MockReplayGuard(ReplayGuard):
    def __init__(self):
        self.used_nonces = set()

    def consume_nonce(self, tenant_id: str, nonce: str, ttl_seconds: int) -> ReplayCheckOutcome:
        key = (tenant_id, nonce)
        if key in self.used_nonces:
            return ReplayCheckOutcome.REPLAY_DETECTED
        self.used_nonces.add(key)
        return ReplayCheckOutcome.FRESH


@pytest.fixture
def mock_provider():
    return MockEvidenceProvider()


@pytest.fixture
def mock_replay():
    return MockReplayGuard()


@pytest.fixture
def fixed_time():
    return datetime(2026, 8, 21, 18, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def engine(mock_provider, mock_replay, fixed_time):
    return VerificationEngine(
        verifier_id="continuum-independent-verifier",
        provider=mock_provider,
        replay_guard=mock_replay,
        clock=lambda: fixed_time
    )


def test_valid_verification_with_injected_clock(engine, mock_provider, fixed_time):
    mock_provider.fenced_agents.add(("tenant-alpha", "agent-v17"))
    mock_provider.authority_bindings[("tenant-alpha", "obl-procure-1001")] = AuthorityBinding(
        predecessor_id="agent-v17", successor_id="agent-v18", authority_domain="tenant-alpha"
    )

    req = VerificationRequest(
        obligation_id="obl-procure-1001",
        tenant_id="tenant-alpha",
        executor_id="orchestrator-agent",
        predecessor_id="agent-v17",
        successor_id="agent-v18",
        target_effect_type="VENDOR_PAYMENT",
        nonce="nonce-unique-001",
        issued_at=fixed_time,
        ttl_seconds=300
    )

    result = engine.verify_execution(req)
    assert result.status == VerificationStatus.VERIFIED


def test_missing_authority_binding_fails_closed(engine, mock_provider, fixed_time):
    mock_provider.fenced_agents.add(("tenant-alpha", "agent-v17"))

    req = VerificationRequest(
        obligation_id="obl-procure-1001",
        tenant_id="tenant-alpha",
        executor_id="orchestrator",
        predecessor_id="agent-v17",
        successor_id="agent-v18",
        target_effect_type="VENDOR_PAYMENT",
        nonce="nonce-missing-auth",
        issued_at=fixed_time
    )

    result = engine.verify_execution(req)
    assert result.status == VerificationStatus.QUARANTINED
    assert "Missing Evidence" in result.reasoning


def test_redteam_executor_cannot_self_verify(mock_provider, mock_replay, fixed_time):
    self_verifier_engine = VerificationEngine(
        verifier_id="malicious-agent",
        provider=mock_provider,
        replay_guard=mock_replay,
        clock=lambda: fixed_time
    )

    req = VerificationRequest(
        obligation_id="obl-procure-1001",
        tenant_id="tenant-alpha",
        executor_id="malicious-agent",
        predecessor_id="agent-v17",
        successor_id="agent-v18",
        target_effect_type="VENDOR_PAYMENT",
        nonce="nonce-unique-002",
        issued_at=fixed_time
    )

    result = self_verifier_engine.verify_execution(req)
    assert result.status == VerificationStatus.REJECTED
    assert "Conflict of Interest" in result.reasoning


def test_redteam_telemetry_incomplete_triggers_quarantine(engine, mock_provider, fixed_time):
    mock_provider.fenced_agents.add(("tenant-alpha", "agent-v17"))
    mock_provider.authority_bindings[("tenant-alpha", "obl-procure-1001")] = AuthorityBinding(
        predecessor_id="agent-v17", successor_id="agent-v18", authority_domain="tenant-alpha"
    )
    mock_provider.telemetry_states[("tenant-alpha", "obl-procure-1001")] = False

    req = VerificationRequest(
        obligation_id="obl-procure-1001",
        tenant_id="tenant-alpha",
        executor_id="orchestrator",
        predecessor_id="agent-v17",
        successor_id="agent-v18",
        target_effect_type="VENDOR_PAYMENT",
        nonce="nonce-unique-telemetry",
        issued_at=fixed_time
    )

    result = engine.verify_execution(req)
    assert result.status == VerificationStatus.QUARANTINED
    assert "Telemetry trace evidence is missing" in result.reasoning


def test_redteam_nonce_replay_attack(engine, mock_provider, fixed_time):
    mock_provider.fenced_agents.add(("tenant-alpha", "agent-v17"))
    mock_provider.authority_bindings[("tenant-alpha", "obl-procure-1001")] = AuthorityBinding(
        predecessor_id="agent-v17", successor_id="agent-v18", authority_domain="tenant-alpha"
    )

    req = VerificationRequest(
        obligation_id="obl-procure-1001",
        tenant_id="tenant-alpha",
        executor_id="orchestrator",
        predecessor_id="agent-v17",
        successor_id="agent-v18",
        target_effect_type="VENDOR_PAYMENT",
        nonce="reused-nonce-999",
        issued_at=fixed_time
    )

    res1 = engine.verify_execution(req)
    assert res1.status == VerificationStatus.VERIFIED

    res2 = engine.verify_execution(req)
    assert res2.status == VerificationStatus.REJECTED
    assert "Replay Attack Detected" in res2.reasoning


def test_redteam_authority_binding_mismatch(engine, mock_provider, fixed_time):
    mock_provider.fenced_agents.add(("tenant-alpha", "agent-v17"))
    mock_provider.authority_bindings[("tenant-alpha", "obl-procure-1001")] = AuthorityBinding(
        predecessor_id="agent-v17", successor_id="agent-v18", authority_domain="tenant-alpha"
    )

    req = VerificationRequest(
        obligation_id="obl-procure-1001",
        tenant_id="tenant-alpha",
        executor_id="orchestrator",
        predecessor_id="agent-v17",
        successor_id="agent-rogue",
        target_effect_type="VENDOR_PAYMENT",
        nonce="nonce-spoof",
        issued_at=fixed_time
    )

    result = engine.verify_execution(req)
    assert result.status == VerificationStatus.REJECTED
    assert "Authority Mismatch" in result.reasoning


def test_redteam_cross_tenant_evidence_isolation(engine, mock_provider, fixed_time):
    mock_provider.fenced_agents.add(("tenant-beta", "agent-v17"))

    req = VerificationRequest(
        obligation_id="obl-procure-1001",
        tenant_id="tenant-alpha",
        executor_id="orchestrator",
        predecessor_id="agent-v17",
        successor_id="agent-v18",
        target_effect_type="VENDOR_PAYMENT",
        nonce="nonce-cross-tenant",
        issued_at=fixed_time
    )

    result = engine.verify_execution(req)
    assert result.status == VerificationStatus.QUARANTINED
    assert "Missing Evidence" in result.reasoning


def test_redteam_fabricated_side_effect_counter(engine, mock_provider, fixed_time):
    mock_provider.fenced_agents.add(("tenant-alpha", "agent-v17"))
    mock_provider.authority_bindings[("tenant-alpha", "obl-procure-1001")] = AuthorityBinding(
        predecessor_id="agent-v17", successor_id="agent-v18", authority_domain="tenant-alpha"
    )
    mock_provider.side_effects[("tenant-alpha", "obl-procure-1001", "VENDOR_PAYMENT")] = 1

    req = VerificationRequest(
        obligation_id="obl-procure-1001",
        tenant_id="tenant-alpha",
        executor_id="orchestrator",
        predecessor_id="agent-v17",
        successor_id="agent-v18",
        target_effect_type="VENDOR_PAYMENT",
        nonce="nonce-side-effect",
        issued_at=fixed_time
    )

    result = engine.verify_execution(req)
    assert result.status == VerificationStatus.REJECTED
    assert "At-Most-Once Violation" in result.reasoning


def test_redteam_expired_request_rejected(mock_provider, mock_replay):
    issued_time = datetime(2026, 8, 21, 17, 0, 0, tzinfo=timezone.utc)
    current_time = datetime(2026, 8, 21, 18, 0, 0, tzinfo=timezone.utc)

    engine_clock = VerificationEngine(
        verifier_id="continuum-independent-verifier",
        provider=mock_provider,
        replay_guard=mock_replay,
        clock=lambda: current_time
    )

    req = VerificationRequest(
        obligation_id="obl-procure-1001",
        tenant_id="tenant-alpha",
        executor_id="orchestrator",
        predecessor_id="agent-v17",
        successor_id="agent-v18",
        target_effect_type="VENDOR_PAYMENT",
        nonce="nonce-expired",
        issued_at=issued_time,
        ttl_seconds=300
    )

    result = engine_clock.verify_execution(req)
    assert result.status == VerificationStatus.REJECTED
    assert "Request expired" in result.reasoning


def test_redteam_pydantic_extra_fields_rejected():
    with pytest.raises(Exception):
        VerificationRequest(
            obligation_id="obl-procure-1001",
            tenant_id="tenant-alpha",
            executor_id="orchestrator",
            predecessor_id="agent-v17",
            successor_id="agent-v18",
            target_effect_type="VENDOR_PAYMENT",
            nonce="nonce-1",
            issued_at=datetime.now(timezone.utc),
            predecessor_fenced=True
        )
"""
Continuum: Verification Engine Integration & Red-Team Test Suite
File: tests/test_verification.py
"""

from datetime import datetime, timezone
import pytest

from continuum.verification.schemas import VerificationRequest, VerificationStatus, VerificationResult
from continuum.verification.provider import EvidenceProvider, AuthorityBinding
from continuum.verification.replay import ReplayGuard, ReplayCheckOutcome
from continuum.verification.engine import VerificationEngine


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


def test_invalid_externally_supplied_digest_fails_validation():
    with pytest.raises(ValueError, match="Digest mismatch"):
        VerificationResult(
            status=VerificationStatus.VERIFIED,
            obligation_id="obl-procure-1001",
            tenant_id="tenant-alpha",
            verifier_id="verifier",
            predecessor_id="agent-v17",
            successor_id="agent-v18",
            predecessor_fenced=True,
            execution_count=0,
            telemetry_verified=True,
            nonce="nonce-1",
            timestamp="2026-08-21T18:00:00+00:00",
            reasoning="Valid reason",
            digest="invalid_forged_hash_value"
        )
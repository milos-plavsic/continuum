"""
Continuum: Verification Red-Team Test Suite
File: verification/test_verification.py

PyTest test cases asserting VERIFIED, FAILED, and INCONCLUSIVE verdicts.
"""

import pytest
from unittest.mock import MagicMock
from verification.schemas import VerificationVerdict
from verification.engine import IndependentVerifier


@pytest.fixture
def mock_verifier():
    mock_db = MagicMock()
    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
    return IndependentVerifier(mock_db, mock_tracer)


def test_clean_succession_returns_verified(mock_verifier):
    """Tests that a valid handover with matching hashes outputs VERIFIED."""
    payload = {"vendor_id": "V-9901", "action": "ONBOARD"}
    now_iso = "2026-08-21T00:00:00Z"
    valid_digest = mock_verifier.recompute_digest(payload, now_iso, "procurement-agent-v17").digest_hash

    attestation = mock_verifier.verify_succession(
        attestation_id="att-001",
        obligation_id="obl-8821",
        raw_payload=payload,
        reported_digest=valid_digest,
        predecessor_fenced=True,
        side_effect_count=1,
        telemetry_complete=True,
        trace_id="trace-abc",
        span_id="span-123",
    )

    assert attestation.verdict == VerificationVerdict.VERIFIED
    assert attestation.predecessor_fenced is True
    assert attestation.at_most_once_verified is True


def test_stale_token_replay_returns_failed(mock_verifier):
    """Tests that an un-fenced predecessor or duplicate execution outputs FAILED."""
    payload = {"vendor_id": "V-9901", "action": "ONBOARD"}
    valid_digest = mock_verifier.recompute_digest(payload, "2026-08-21T00:00:00Z", "procurement-agent-v17").digest_hash

    attestation = mock_verifier.verify_succession(
        attestation_id="att-002",
        obligation_id="obl-8821",
        raw_payload=payload,
        reported_digest=valid_digest,
        predecessor_fenced=False,
        side_effect_count=2,
        telemetry_complete=True,
        trace_id="trace-abc",
        span_id="span-123",
    )

    assert attestation.verdict == VerificationVerdict.FAILED


def test_missing_telemetry_span_returns_inconclusive(mock_verifier):
    """Tests that gaps in Pub/Sub or OpenTelemetry traces output INCONCLUSIVE."""
    payload = {"vendor_id": "V-9901", "action": "ONBOARD"}

    attestation = mock_verifier.verify_succession(
        attestation_id="att-003",
        obligation_id="obl-8821",
        raw_payload=payload,
        reported_digest="fake-hash",
        predecessor_fenced=True,
        side_effect_count=1,
        telemetry_complete=False,
        trace_id="trace-abc",
        span_id="span-123",
    )

    assert attestation.verdict == VerificationVerdict.INCONCLUSIVE




    
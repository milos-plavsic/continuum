from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from continuum.core import ActionGateway, AgentRegistry, ComplianceRegistry, MemoryGateway, VendorRegistry, validate_manifest
from continuum.models import AgentStatus, AgentVersion, Denied, TransferManifest
from continuum.scenario import run_scenario
from continuum.sentinel import NegativeSpaceSentinel, parse_utc


class ScenarioTests(unittest.TestCase):
    def test_canonical_succession(self):
        with TemporaryDirectory() as directory:
            result = run_scenario(Path(directory))
        self.assertEqual(result["outcome"], "VERIFIED")
        self.assertEqual(result["owner"], "v18")
        self.assertEqual(result["vendor_count"], 1)
        self.assertTrue(result["duplicate_returned_prior_result"])
        self.assertEqual(result["denials"], ["STALE_FENCE", "GRANT_REVOKED"])
        self.assertEqual(result["revoked_candidates_exposed"], 0)
        self.assertTrue(result["events_valid"])

    def test_silence_alone_does_not_quarantine(self):
        with TemporaryDirectory() as directory:
            result = run_scenario(Path(directory), signals=("missed_evidence",))
        self.assertEqual(result["outcome"], "INVESTIGATE_HOLD")
        self.assertFalse(result["quarantined"])
        self.assertEqual(result["vendor_count"], 0)

    def test_any_missing_compromise_signal_holds(self):
        all_signals = {"injection", "anomalous_action", "missed_evidence"}
        for removed in all_signals:
            with self.subTest(removed=removed), TemporaryDirectory() as directory:
                result = run_scenario(Path(directory), signals=tuple(all_signals - {removed}))
                self.assertEqual(result["outcome"], "INVESTIGATE_HOLD")

    def test_deterministic_replay(self):
        with TemporaryDirectory() as left, TemporaryDirectory() as right:
            a = run_scenario(Path(left))
            b = run_scenario(Path(right))
        self.assertEqual(a["manifest_hash"], b["manifest_hash"])
        self.assertEqual(a["timeline"], b["timeline"])


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.registry = AgentRegistry()
        self.registry.register(AgentVersion("procurement", "v1", "acme", AgentStatus.ACTIVE, 7,
            "sha256:a", "v1@acme", ("vendor.create",), ("approved",)))

    def test_fencing_is_enforced_at_gateway(self):
        self.registry.fence("v1", 7)
        with self.assertRaisesRegex(Denied, "STALE_FENCE"):
            self.registry.authorize("acme", "v1", 7, "vendor.create")

    def test_cross_tenant_is_non_disclosing(self):
        with self.assertRaisesRegex(Denied, "RESOURCE_NOT_FOUND"):
            self.registry.authorize("other", "v1", 7, "vendor.create")

    def test_memory_revocation_happens_before_retrieval(self):
        gateway = MemoryGateway()
        gateway.grant("v1", ("approved",))
        gateway.revoke("v1")
        with self.assertRaisesRegex(Denied, "GRANT_REVOKED"):
            gateway.retrieve("v1", "approved")
        self.assertEqual(gateway.candidate_count, 0)

    def test_idempotency_key_cannot_change_meaning(self):
        with TemporaryDirectory() as directory:
            provider = VendorRegistry(Path(directory) / "vendors.sqlite3")
            compliance = ComplianceRegistry()
            compliance.verify(evidence_id="e1", tenant="acme", obligation_id="o1",
                              subject="one", document_hash="sha256:doc")
            gateway = ActionGateway(self.registry, provider, compliance)
            args = dict(tenant="acme", version="v1", epoch=7, vendor="one",
                        obligation_id="o1", compliance_evidence_id="e1",
                        idempotency_key="stable", decision_id="d1")
            gateway.create_vendor(**args)
            with self.assertRaisesRegex(Denied, "IDEMPOTENCY_KEY_CONFLICT"):
                gateway.create_vendor(**(args | {"decision_id": "d2"}))
            self.assertEqual(provider.count(), 1)
            provider.close()

    def test_manifest_rejects_untrusted_memory(self):
        unsafe = TransferManifest("s", "v1", "v2", 1, 2, (("o", 1),),
            ("raw_untrusted_document",), ("raw_untrusted_document", "secret", "revoked_private_notes"), ("e",), "d")
        with self.assertRaisesRegex(Denied, "UNSAFE_MANIFEST_CONTENT"):
            validate_manifest(unsafe)

    def test_negative_space_requires_elapsed_deadline_and_is_idempotent(self):
        sentinel = NegativeSpaceSentinel()
        args = dict(required_evidence=("compliance.evidence_verified",),
                    deadline="2026-08-17T10:05:00Z", observed_evidence=())
        self.assertEqual(sentinel.evaluate(**args, now="2026-08-17T10:04:59Z"), ())
        due = sentinel.evaluate(**args, now="2026-08-17T10:05:00Z")
        self.assertEqual(due[0].evidence_type, "compliance.evidence_verified")
        self.assertEqual(sentinel.evaluate(**args, now="2026-08-17T10:05:01Z",
                                           already_reported=(due[0].evidence_type,)), ())
        self.assertEqual(sentinel.evaluate(**(args | {"observed_evidence": ("compliance.evidence_verified",)}),
                                           now="2026-08-17T10:05:01Z"), ())
        with self.assertRaisesRegex(ValueError, "UTC_Z_REQUIRED"):
            parse_utc("2026-08-17T10:05:00+00:00")

    def test_compliance_registry_fails_closed_for_every_invalid_binding(self):
        from continuum.core import ComplianceRegistry
        compliance = ComplianceRegistry()
        for values in [dict(evidence_id="", document_hash="doc"),
                       dict(evidence_id="e", document_hash="")]:
            with self.assertRaisesRegex(Denied, "COMPLIANCE_EVIDENCE_REQUIRED"):
                compliance.verify(tenant="acme", obligation_id="o", subject="v", **values)
        compliance.verify(evidence_id="e", tenant="acme", obligation_id="o",
                          subject="v", document_hash="doc")
        with self.assertRaisesRegex(Denied, "COMPLIANCE_EVIDENCE_CONFLICT"):
            compliance.verify(evidence_id="e", tenant="acme", obligation_id="o",
                              subject="v", document_hash="other")
        with self.assertRaisesRegex(Denied, "COMPLIANCE_EVIDENCE_REQUIRED"):
            compliance.authorize(evidence_id="", tenant="acme", obligation_id="o", subject="v")
        with self.assertRaisesRegex(Denied, "COMPLIANCE_EVIDENCE_NOT_VERIFIED"):
            compliance.authorize(evidence_id="missing", tenant="acme", obligation_id="o", subject="v")
        with self.assertRaisesRegex(Denied, "COMPLIANCE_EVIDENCE_BINDING_MISMATCH"):
            compliance.authorize(evidence_id="e", tenant="other", obligation_id="o", subject="v")


if __name__ == "__main__":
    unittest.main()

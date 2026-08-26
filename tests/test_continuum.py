from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from continuum.core import ActionGateway, AgentRegistry, MemoryGateway, VendorRegistry, validate_manifest
from continuum.models import AgentStatus, AgentVersion, Denied, TransferManifest
from continuum.scenario import run_scenario


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
            gateway = ActionGateway(self.registry, provider)
            args = dict(tenant="acme", version="v1", epoch=7, vendor="one", idempotency_key="stable", decision_id="d1")
            gateway.create_vendor(**args)
            with self.assertRaisesRegex(Denied, "IDEMPOTENCY_KEY_CONFLICT"):
                gateway.create_vendor(**(args | {"vendor": "two"}))
            self.assertEqual(provider.count(), 1)
            provider.close()

    def test_manifest_rejects_untrusted_memory(self):
        unsafe = TransferManifest("s", "v1", "v2", 1, 2, (("o", 1),),
            ("raw_untrusted_document",), ("raw_untrusted_document", "secret", "revoked_private_notes"), ("e",), "d")
        with self.assertRaisesRegex(Denied, "UNSAFE_MANIFEST_CONTENT"):
            validate_manifest(unsafe)


if __name__ == "__main__":
    unittest.main()

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from continuum.contract import ContractError, artifact_digest, canonical_bytes, sign_ed25519, validate_envelope, verify_ed25519
from continuum.conformance import run_conformance
from continuum.standard import build_contract_bundle, verify_bundle


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.bundle = build_contract_bundle(Path(self.directory.name))

    def tearDown(self):
        self.directory.cleanup()

    def test_bundle_has_all_six_artifacts(self):
        verify_bundle(self.bundle)
        self.assertEqual(len(self.bundle["artifacts"]), 6)

    def test_mutation_breaks_content_digest(self):
        artifact = deepcopy(self.bundle["artifacts"][0])
        artifact["body"]["description"] = "mutated"
        with self.assertRaisesRegex(ContractError, "DIGEST_MISMATCH"):
            validate_envelope(artifact)

    def test_float_is_outside_canonical_subset(self):
        with self.assertRaisesRegex(ContractError, "FLOAT_NOT_ALLOWED"):
            canonical_bytes({"risk": 0.5})

    def test_published_golden_vector(self):
        path = Path(__file__).resolve().parents[1] / "examples/continuity-contract/golden-obligation.json"
        artifact = json.loads(path.read_text())
        validate_envelope(artifact)
        self.assertEqual(artifact_digest(artifact), "92ca54af049cb97734b56171a14161aad5d45d9a5b3d72e5b965abe9e8d2a174")

    def test_ed25519_signature_detects_substitution(self):
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        except ImportError:
            self.skipTest("signature extra not installed")
        private = Ed25519PrivateKey.generate(); public = private.public_key()
        artifact = sign_ed25519(self.bundle["artifacts"][0], private, "urn:key:test:1", "2026-08-17T10:06:00Z")
        verify_ed25519(artifact, lambda _: public)
        other = Ed25519PrivateKey.generate().public_key()
        with self.assertRaisesRegex(ContractError, "SIGNATURE_INVALID"):
            verify_ed25519(artifact, lambda _: other)

    def test_self_attestation_cannot_verify(self):
        artifact = next(a for a in self.bundle["artifacts"] if a["artifact_type"] == "continuity_attestation")
        artifact = deepcopy(artifact)
        artifact["body"]["verification"]["independent_of_executor"] = False
        artifact["digest"]["value"] = artifact_digest(artifact)
        with self.assertRaisesRegex(ContractError, "EXECUTOR_SELF_ATTESTATION"):
            validate_envelope(artifact)


class ConformanceTests(unittest.TestCase):
    def test_reference_profile_passes_declared_levels(self):
        with TemporaryDirectory() as directory:
            report = run_conformance(Path(directory))
        self.assertEqual(report["highest_level"], "C6")
        self.assertTrue(all(case["status"] == "PASS" for case in report["cases"]))
        self.assertIn("third-party interoperability", report["non_claims"])


if __name__ == "__main__":
    unittest.main()

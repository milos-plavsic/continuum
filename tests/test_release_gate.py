from importlib.util import module_from_spec, spec_from_file_location
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = spec_from_file_location("release_gate", ROOT / "scripts/release_gate.py")
MODULE = module_from_spec(SPEC); SPEC.loader.exec_module(MODULE)


class ReleaseGateTests(unittest.TestCase):
    def test_local_gate_proves_signature_invariants(self):
        with TemporaryDirectory() as temporary:
            result = MODULE.evaluate_local(Path(temporary))
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(all(result["assertions"].values()))
        controls = MODULE.repository_controls()
        self.assertEqual(controls["status"], "PASS")
        self.assertTrue(all(value == "PASS" for value in controls["controls"].values()))

    def test_cloud_readiness_names_external_prerequisites(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(MODULE.shutil, "which", return_value=None):
            result = MODULE.cloud_readiness()
        self.assertEqual(result["status"], "EXTERNAL_PREREQUISITE_REQUIRED")
        self.assertIn("GCLOUD_CLI", result["missing"])


if __name__ == "__main__":
    unittest.main()

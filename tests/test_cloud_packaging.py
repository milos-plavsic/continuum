from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = spec_from_file_location("package_evidence", ROOT / "scripts/cloud/package-evidence.py")
MODULE = module_from_spec(SPEC); SPEC.loader.exec_module(MODULE)


class CloudPackagingTests(unittest.TestCase):
    def test_packages_objects_by_digest_without_credentials(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary); source = root / "raw"; destination = root / "bundle"
            source.mkdir(); (source / "cloud-run-control.json").write_text('{"ready":true}\n')
            bundle = MODULE.package(source, destination, project="p", region="r", run_id="run",
                                    trace_id="trace", git_commit="a" * 40)
            item = bundle["objects"][0]
            self.assertEqual((destination / "objects" / item["sha256"]).read_text(), '{"ready":true}\n')
            self.assertEqual(json.loads((destination / "bundle.json").read_text())["scope"]["run_id"], "run")


if __name__ == "__main__":
    unittest.main()

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from continuum.release_truth import (
    JUDGE_FACING_PATHS, ReleaseTruthError, audit_judge_surfaces, load_release_truth,
    release_summary,
)


ROOT = Path(__file__).resolve().parents[1]


class ReleaseTruthTests(unittest.TestCase):
    def test_current_repository_has_one_release_truth(self):
        truth = load_release_truth(ROOT / "docs/submission/current-release.json")
        self.assertEqual(audit_judge_surfaces(ROOT, truth), ())
        self.assertIn("15 required objects", release_summary(truth))

    def test_manifest_and_surface_mutations_fail_closed(self):
        source = json.loads((ROOT / "docs/submission/current-release.json").read_text())
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / "current.json"
            for relative in JUDGE_FACING_PATHS:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text((ROOT / relative).read_text(), encoding="utf-8")
            manifest.write_text(json.dumps(source), encoding="utf-8")
            truth = load_release_truth(manifest)
            target = root / "README.md"
            target.write_text(target.read_text() + "\n159 tests\n", encoding="utf-8")
            self.assertIn("SUPERSEDED_RELEASE_FACT:README.md:159 tests",
                          audit_judge_surfaces(root, truth))
            source["run"]["trace_id"] = "not-a-trace"
            manifest.write_text(json.dumps(source), encoding="utf-8")
            with self.assertRaisesRegex(ReleaseTruthError, "RUN_IDENTITY_INVALID"):
                load_release_truth(manifest)

    def test_every_manifest_and_surface_boundary_fails_closed(self):
        original = json.loads((ROOT / "docs/submission/current-release.json").read_text())
        mutations = [
            (lambda v: v.update(extra=True), "SCHEMA_INVALID"),
            (lambda v: v.update(schema="old"), "VERSION_UNSUPPORTED"),
            (lambda v: v["application"].update(extra=True), "APPLICATION_RELEASE_INVALID"),
            (lambda v: v["application"].update(source_commit="bad"), "APPLICATION_IDENTITY_INVALID"),
            (lambda v: v["run"].update(extra=True), "RUN_RELEASE_INVALID"),
            (lambda v: v["proof"].update(archive_sha256="bad"), "PROOF_RELEASE_INVALID"),
            (lambda v: v["quality"].update(test_count=0), "QUALITY_RELEASE_INVALID"),
            (lambda v: v["showcase"].update(url="http://bad"), "SHOWCASE_RELEASE_INVALID"),
            (lambda v: v.update(superseded_markers=[]), "SUPERSEDED_MARKERS_INVALID"),
        ]
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "truth.json"
            for mutate, message in mutations:
                value = json.loads(json.dumps(original)); mutate(value)
                path.write_text(json.dumps(value))
                with self.assertRaisesRegex(ReleaseTruthError, message): load_release_truth(path)
            root = Path(temporary) / "root"
            root.mkdir()
            missing = audit_judge_surfaces(root, original)
            self.assertTrue(any(item.startswith("MISSING_JUDGE_SURFACE") for item in missing))
            for relative in JUDGE_FACING_PATHS:
                target = root / relative; target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("no current identifiers")
            self.assertTrue(any(item.startswith("CURRENT_RELEASE_FACT_MISSING")
                                for item in audit_judge_surfaces(root, original)))


if __name__ == "__main__":
    unittest.main()

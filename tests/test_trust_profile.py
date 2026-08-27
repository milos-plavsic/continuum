from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from continuum.trust_profile import load_trust_profile, validate_trust_profile


ROOT = Path(__file__).resolve().parents[1]


class TrustProfileTests(unittest.TestCase):
    def setUp(self):
        self.value = json.loads((ROOT / "docs/trust-profile.json").read_text())

    def test_repository_profile_is_complete_and_content_addressed(self):
        profile = load_trust_profile(ROOT / "docs/trust-profile.json")
        self.assertEqual(profile["schema"], "continuum/trust-profile/1")
        self.assertEqual(len(profile["profile_digest"]), 64)
        self.assertIn("upstream-factual-truth", profile["not_assessed"])

    def test_every_profile_boundary_fails_closed(self):
        mutations = [
            lambda value: value.update(extra=True),
            lambda value: value.update(schema="old"),
            lambda value: value.update(profile_id=""),
        ]
        for mutate in mutations:
            value = deepcopy(self.value); mutate(value)
            with self.assertRaisesRegex(ValueError, "SCHEMA_INVALID"):
                validate_trust_profile(value)
        for roots, error in (([], "ROOTS_INVALID"),
            ([{"id":"x"}], "ROOTS_INVALID"),
            ([self.value["trust_roots"][0], self.value["trust_roots"][0]], "ROOTS_DUPLICATE")):
            value = deepcopy(self.value); value["trust_roots"] = roots
            with self.assertRaisesRegex(ValueError, error): validate_trust_profile(value)
        for field in ("assessed_claims", "not_assessed"):
            value = deepcopy(self.value); value[field] = ["duplicate", "duplicate"]
            with self.assertRaisesRegex(ValueError, "CLAIMS_INVALID"):
                validate_trust_profile(value)
        value = deepcopy(self.value); value["not_assessed"] = ["upstream-factual-truth"]
        with self.assertRaisesRegex(ValueError, "CEILING_INCOMPLETE"):
            validate_trust_profile(value)
        with TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.json"
            with self.assertRaisesRegex(ValueError, "UNREADABLE"):
                load_trust_profile(missing)
            missing.write_text("not-json")
            with self.assertRaisesRegex(ValueError, "UNREADABLE"):
                load_trust_profile(missing)


if __name__ == "__main__":
    unittest.main()

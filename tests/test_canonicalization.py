from __future__ import annotations

import base64
from hashlib import sha256
import json
from pathlib import Path
import unittest

from continuum.canonicalization import (
    CanonicalizationError, PROFILE, canonical_json_bytes, canonical_json_text,
    canonical_sha256,
)
from continuum.contract import canonical_bytes
from continuum.models import canonical, digest


class CanonicalizationTests(unittest.TestCase):
    def test_cross_language_vectors_use_one_rfc8785_boundary(self):
        fixture = json.loads((Path(__file__).parents[1] / "fixtures" /
                              "canonicalization-rfc8785-v1.json").read_text())
        self.assertEqual(PROFILE, fixture["profile"])
        for vector in fixture["vectors"]:
            with self.subTest(vector=vector["name"]):
                rendered = canonical_json_bytes(vector["input"])
                self.assertEqual(base64.b64decode(vector["canonical_base64"]), rendered)
                self.assertEqual(vector["sha256"], sha256(rendered).hexdigest())
                self.assertEqual(rendered, canonical_bytes(vector["input"]))
                self.assertEqual(rendered.decode(), canonical(vector["input"]))
                self.assertEqual(vector["sha256"], digest(vector["input"]))
                self.assertEqual(vector["sha256"], canonical_sha256(vector["input"]))
                self.assertEqual(rendered.decode(), canonical_json_text(vector["input"]))

    def test_values_outside_ijson_fail_closed(self):
        invalid = (float("nan"), float("inf"), 2 ** 60, {1: "non-string"}, "\ud800")
        for value in invalid:
            with self.subTest(value=repr(value)), self.assertRaises(CanonicalizationError):
                canonical_json_bytes(value)

    def test_domain_separation_changes_digest_without_changing_json(self):
        value = {"artifact": "six"}
        self.assertNotEqual(canonical_sha256(value), canonical_sha256(value, domain=b"contract\0"))
        self.assertEqual('{"artifact":"six"}', canonical_json_text(value))


if __name__ == "__main__":
    unittest.main()

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from continuum.supplier_assurance import (
    SupplierAssuranceDenied, admit_supplier_assessment, application_digest,
    canonical_supplier_application, check_eu_vat, lookup_gleif,
    model_supplier_view, validate_model_assessment,
)


class Response:
    def __init__(self, payload): self.payload = payload
    def __enter__(self): return self
    def __exit__(self, *_args): return None
    def read(self): return json.dumps(self.payload).encode()


def opener_for(payload):
    return lambda request, timeout: Response(payload)


class SupplierAssuranceTests(unittest.TestCase):
    def setUp(self):
        self.application = canonical_supplier_application()
        self.gleif = lookup_gleif(self.application["lei"], opener=opener_for({
            "data": {"id": self.application["lei"], "attributes": {
                "entity": {"legalName": {"name": self.application["legal_name"]},
                           "legalAddress": {"country": "DE"}, "status": "ACTIVE"},
                "registration": {"status": "ISSUED", "nextRenewalDate": "2026-10-25T00:00:00Z"},
            }}
        }))
        self.vies = check_eu_vat("DE", self.application["vat_number"], opener=opener_for({
            "valid": True, "requestDate": "2026-08-27Z", "name": "---",
            "address": "---", "userError": None,
        }))
        self.result = {
            "recommendation": "ONBOARD", "legal_identity_match": True,
            "country_match": True, "vat_valid": True,
            "controls_satisfied": self.application["required_controls"],
            "missing_requirements": [], "risk_summary": "Public identity and VAT checks passed.",
            "evidence_refs": [f"sha256:{application_digest(self.application)}",
                              self.gleif["evidence_ref"], self.vies["evidence_ref"]],
            "proposed_action": "vendor.create",
        }

    def test_real_tool_receipts_feed_a_deterministically_admitted_decision_pack(self):
        view = model_supplier_view(self.application, self.gleif, self.vies)
        self.assertEqual(len(view["external_tool_observations"]), 2)
        admitted = admit_supplier_assessment(application=self.application, gleif=self.gleif,
            vies=self.vies, model_result=self.result, actor="v18@example.iam")
        self.assertEqual(admitted["workflow"], "SUPPLIER_ASSURANCE_AGENT")
        self.assertEqual(admitted["decision_scope"], "SANDBOX_ONLY")
        self.assertEqual(len(admitted["tool_observations"]), 2)

    def test_tool_inputs_and_responses_fail_closed(self):
        for lei in ("bad", 1):
            with self.assertRaisesRegex(ValueError, "LEI_INVALID"):
                lookup_gleif(lei, opener=opener_for({}))
        with self.assertRaisesRegex(ValueError, "GLEIF_RESPONSE_INVALID"):
            lookup_gleif(self.application["lei"], opener=opener_for({"data": {}}))
        substituted = {"data": {"id": "0" * 20, "attributes": {"entity": {
            "legalName": {"name": "x"}, "legalAddress": {"country": "DE"}, "status": "ACTIVE"},
            "registration": {"status": "ISSUED"}}}}
        with self.assertRaisesRegex(ValueError, "GLEIF_IDENTITY_SUBSTITUTION"):
            lookup_gleif(self.application["lei"], opener=opener_for(substituted))
        for country, vat in (("D", "1"), ("DE", "!"), (1, "123")):
            with self.assertRaisesRegex(ValueError, "VAT_IDENTIFIER_INVALID"):
                check_eu_vat(country, vat, opener=opener_for({}))
        with self.assertRaisesRegex(ValueError, "VIES_RESPONSE_INVALID"):
            check_eu_vat("DE", "123", opener=opener_for({"valid": "yes"}))
        with self.assertRaisesRegex(ValueError, "EXTERNAL_TOOL_RESPONSE_INVALID"):
            check_eu_vat("DE", "123", opener=opener_for([]))

    def test_model_schema_and_every_admission_invariant_are_enforced(self):
        malformed = dict(self.result); malformed["extra"] = True
        with self.assertRaisesRegex(ValueError, "SUPPLIER_MODEL_RESULT_INVALID"):
            validate_model_assessment(malformed)
        invalid_values = [
            {**self.result, "recommendation": "MAYBE"},
            {**self.result, "proposed_action": "email.send"},
            {**self.result, "vat_valid": "true"},
            {**self.result, "controls_satisfied": "all"},
            {**self.result, "missing_requirements": "none"},
            {**self.result, "evidence_refs": "refs"},
            {**self.result, "risk_summary": []},
        ]
        for result in invalid_values:
            with self.assertRaisesRegex(ValueError, "SUPPLIER_MODEL_RESULT_INVALID"):
                validate_model_assessment(result)
        denied = [
            ({**self.application, "decision_scope": "REAL"}, self.gleif, self.vies, self.result),
            (self.application, {**self.gleif, "legal_name": "Other"}, self.vies, self.result),
            (self.application, {**self.gleif, "country_code": "FR"}, self.vies, self.result),
            (self.application, {**self.gleif, "entity_status": "INACTIVE"}, self.vies, self.result),
            (self.application, {**self.gleif, "registration_status": "RETIRED"}, self.vies, self.result),
            (self.application, self.gleif, {**self.vies, "valid": False}, self.result),
            (self.application, self.gleif, {**self.vies, "country_code": "FR"}, self.result),
            (self.application, self.gleif, {**self.vies, "vat_number": "other"}, self.result),
            (self.application, self.gleif, self.vies, {**self.result, "recommendation": "HOLD",
                                                       "proposed_action": "none"}),
            (self.application, self.gleif, self.vies, {**self.result, "legal_identity_match": False}),
            (self.application, self.gleif, self.vies, {**self.result, "country_match": False}),
            (self.application, self.gleif, self.vies, {**self.result, "vat_valid": False}),
            (self.application, self.gleif, self.vies, {**self.result, "controls_satisfied": []}),
            (self.application, self.gleif, self.vies, {**self.result, "missing_requirements": ["x"]}),
            (self.application, self.gleif, self.vies, {**self.result,
                "evidence_refs": self.result["evidence_refs"] + [self.result["evidence_refs"][0]]}),
        ]
        for application, gleif, vies, result in denied:
            with self.assertRaisesRegex(SupplierAssuranceDenied, "SUPPLIER_ASSURANCE_HOLD"):
                admit_supplier_assessment(application=application, gleif=gleif, vies=vies,
                                          model_result=result, actor="agent")


if __name__ == "__main__":
    unittest.main()

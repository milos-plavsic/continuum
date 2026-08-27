import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from continuum.supplier_assurance import (
    ExternalToolError, ExternalToolPolicy, FirestoreEvidenceCache,
    InMemoryEvidenceCache, SupplierAssuranceDenied, admit_supplier_assessment,
    application_digest, canonical_supplier_application, check_eu_vat, lookup_gleif,
    model_supplier_view, resolve_tool_observation, supplier_evidence_cache_keys,
    validate_model_assessment,
)


class Response:
    def __init__(self, payload, status=200, raw=None):
        self.payload, self.status, self.raw = payload, status, raw
    def __enter__(self): return self
    def __exit__(self, *_args): return None
    def read(self):
        return self.raw if self.raw is not None else json.dumps(self.payload).encode()


def opener_for(payload):
    return lambda request, timeout: Response(payload)


class SupplierAssuranceTests(unittest.TestCase):
    def setUp(self):
        self.application = canonical_supplier_application()
        self.now = datetime(2026, 8, 27, 12, tzinfo=timezone.utc)
        raw_gleif = lambda: lookup_gleif(self.application["lei"], opener=opener_for({
            "data": {"id": self.application["lei"], "attributes": {
                "entity": {"legalName": {"name": self.application["legal_name"]},
                           "legalAddress": {"country": "DE"}, "status": "ACTIVE"},
                "registration": {"status": "ISSUED", "nextRenewalDate": "2026-10-25T00:00:00Z"},
            }}
        }))
        raw_vies = lambda: check_eu_vat("DE", self.application["vat_number"], opener=opener_for({
            "valid": True, "requestDate": "2026-08-27Z", "name": "---",
            "address": "---", "userError": None,
        }))
        self.gleif = resolve_tool_observation(
            cache_key="gleif:test", fetch=raw_gleif, cache=None, now=self.now)
        self.vies = resolve_tool_observation(
            cache_key="vies:test", fetch=raw_vies, cache=None, now=self.now)
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
        with self.assertRaisesRegex(ExternalToolError, "VIES_RESPONSE_INVALID"):
            check_eu_vat("DE", "123", opener=opener_for([]))

    def test_external_network_errors_are_bounded_and_stable(self):
        policy = ExternalToolPolicy(per_attempt_timeout_seconds=2, total_budget_seconds=8,
                                    backoff_seconds=(0, 0.1, 0.2), evidence_ttl_seconds=60)
        failures = [URLError("dns"), TimeoutError("timed out"),
                    HTTPError("https://vies", 503, "down", {}, None)]
        calls, delays = [], []
        def opener(request, timeout):
            calls.append(timeout)
            failure = failures.pop(0)
            raise failure
        with self.assertRaisesRegex(ExternalToolError, "VIES_HTTP_503") as caught:
            check_eu_vat("DE", "123", opener=opener, policy=policy,
                         sleeper=delays.append, clock=lambda: 0.0)
        self.assertTrue(caught.exception.retryable)
        self.assertEqual(calls, [2, 2, 2])
        self.assertEqual(delays, [0.1, 0.2])

        nonretry = lambda request, timeout: Response({}, status=400)
        with self.assertRaisesRegex(ExternalToolError, "VIES_HTTP_400") as denied:
            check_eu_vat("DE", "123", opener=nonretry, policy=policy,
                         sleeper=lambda _value: self.fail("must not retry"), clock=lambda: 0.0)
        self.assertFalse(denied.exception.retryable)

        with self.assertRaisesRegex(ExternalToolError, "GLEIF_RESPONSE_INVALID"):
            lookup_gleif(self.application["lei"],
                         opener=lambda request, timeout: Response({}, raw=b"not-json"))

    def test_external_budget_and_policy_validation_fail_closed(self):
        invalid = [
            {"per_attempt_timeout_seconds": 0}, {"total_budget_seconds": 0},
            {"backoff_seconds": ()}, {"backoff_seconds": (0, -1)},
            {"evidence_ttl_seconds": 0},
        ]
        for values in invalid:
            with self.assertRaisesRegex(ValueError, "EXTERNAL_TOOL_POLICY_INVALID"):
                ExternalToolPolicy(**values)
        moments = iter((0.0, 0.0, 0.95, 0.95))
        policy = ExternalToolPolicy(per_attempt_timeout_seconds=1, total_budget_seconds=1,
                                    backoff_seconds=(0, 0.1), evidence_ttl_seconds=60)
        with self.assertRaisesRegex(ExternalToolError, "VIES_TIME_BUDGET_EXHAUSTED"):
            check_eu_vat("DE", "123",
                         opener=lambda request, timeout: (_ for _ in ()).throw(URLError("dns")),
                         policy=policy, sleeper=lambda _value: None,
                         clock=lambda: next(moments))
        moments = iter((0.0, 2.0))
        with self.assertRaisesRegex(ExternalToolError, "GLEIF_TIME_BUDGET_EXHAUSTED"):
            lookup_gleif(self.application["lei"], opener=opener_for({}),
                         policy=policy, clock=lambda: next(moments))

    def test_cache_and_availability_receipt_structures_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "EXTERNAL_EVIDENCE_TIME_INVALID"):
            resolve_tool_observation(cache_key="x", fetch=lambda: self.gleif,
                                     cache=None, now=datetime(2026, 8, 27))
        with self.assertRaisesRegex(ExternalToolError, "GLEIF_UNAVAILABLE"):
            resolve_tool_observation(cache_key="x",
                fetch=lambda: (_ for _ in ()).throw(
                    ExternalToolError("GLEIF_UNAVAILABLE", retryable=True)),
                cache=None, now=self.now)
        invalid_cache = InMemoryEvidenceCache()
        invalid_cache.put("gleif:x", {"evidence_ref": "sha256:x"})
        with self.assertRaisesRegex(ExternalToolError, "CACHE_CORRUPT"):
            resolve_tool_observation(cache_key="gleif:x",
                fetch=lambda: (_ for _ in ()).throw(
                    ExternalToolError("GLEIF_UNAVAILABLE", retryable=True)),
                cache=invalid_cache, now=self.now)

        vies_key = f"vies:DE:{self.application['vat_number']}"
        cache = InMemoryEvidenceCache()
        live = resolve_tool_observation(cache_key=vies_key, fetch=lambda: self.vies,
                                        cache=cache, now=self.now)
        fallback = resolve_tool_observation(cache_key=vies_key,
            fetch=lambda: (_ for _ in ()).throw(
                ExternalToolError("VIES_UNAVAILABLE", retryable=True)),
            cache=cache, now=self.now + timedelta(seconds=1))
        self.assertEqual(fallback["availability_mode"], "CACHED_WITHIN_POLICY")
        cache.put("unknown:key", live)
        with self.assertRaisesRegex(ExternalToolError, "CACHE_SUBSTITUTED"):
            resolve_tool_observation(cache_key="unknown:key",
                fetch=lambda: (_ for _ in ()).throw(
                    ExternalToolError("VIES_UNAVAILABLE", retryable=True)),
                cache=cache, now=self.now + timedelta(seconds=1))

        invalid_observations = [
            {**self.gleif, "observed_at": "bad"},
            {**self.gleif, "freshness_expires_at": self.gleif["observed_at"]},
            {**self.gleif, "availability_mode": "UNKNOWN"},
            {**self.gleif, "availability_mode": "CACHED_WITHIN_POLICY"},
            {**self.gleif, "availability_mode": "CACHED_WITHIN_POLICY",
             "cached_from_evidence_ref": 1, "live_error_code": "x"},
        ]
        for observation in invalid_observations:
            with self.subTest(observation=observation), self.assertRaisesRegex(
                    SupplierAssuranceDenied, "SUPPLIER_ASSURANCE_HOLD"):
                admit_supplier_assessment(application=self.application, gleif=observation,
                    vies=self.vies, model_result=self.result, actor="agent")

    def test_live_cache_fallback_is_fresh_bound_content_addressed_and_isolated(self):
        cache = InMemoryEvidenceCache()
        key = f"gleif:{self.application['lei']}"
        live = resolve_tool_observation(cache_key=key, fetch=lambda: self.gleif,
                                        cache=cache, now=self.now,
                                        policy=ExternalToolPolicy(evidence_ttl_seconds=60))
        self.assertEqual(live["availability_mode"], "LIVE")
        fallback = resolve_tool_observation(
            cache_key=key,
            fetch=lambda: (_ for _ in ()).throw(
                ExternalToolError("GLEIF_UNAVAILABLE", retryable=True)),
            cache=cache, now=self.now + timedelta(seconds=30))
        self.assertEqual(fallback["availability_mode"], "CACHED_WITHIN_POLICY")
        self.assertEqual(fallback["cached_from_evidence_ref"], live["evidence_ref"])
        self.assertEqual(fallback["live_error_code"], "GLEIF_UNAVAILABLE")
        with self.assertRaisesRegex(ExternalToolError, "EXTERNAL_EVIDENCE_CACHE_STALE"):
            resolve_tool_observation(
                cache_key=key,
                fetch=lambda: (_ for _ in ()).throw(
                    ExternalToolError("GLEIF_UNAVAILABLE", retryable=True)),
                cache=cache, now=self.now + timedelta(seconds=61))
        with self.assertRaisesRegex(ExternalToolError, "GLEIF_UNAVAILABLE"):
            resolve_tool_observation(
                cache_key="missing", fetch=lambda: (_ for _ in ()).throw(
                    ExternalToolError("GLEIF_UNAVAILABLE", retryable=True)),
                cache=cache, now=self.now)
        cached = cache.get(key); cached["legal_name"] = "substituted"
        cache.put(key, cached)
        with self.assertRaisesRegex(ExternalToolError, "EXTERNAL_EVIDENCE_CACHE_CORRUPT"):
            resolve_tool_observation(
                cache_key=key, fetch=lambda: (_ for _ in ()).throw(
                    ExternalToolError("GLEIF_UNAVAILABLE", retryable=True)),
                cache=cache, now=self.now)
        cache.put("gleif:OTHER", live)
        with self.assertRaisesRegex(ExternalToolError, "CACHE_SUBSTITUTED"):
            resolve_tool_observation(
                cache_key="gleif:OTHER", fetch=lambda: (_ for _ in ()).throw(
                    ExternalToolError("GLEIF_UNAVAILABLE", retryable=True)),
                cache=cache, now=self.now + timedelta(seconds=30))
        cache.put(key, live)
        with self.assertRaisesRegex(ExternalToolError, "CACHE_STALE"):
            resolve_tool_observation(
                cache_key=key, fetch=lambda: (_ for _ in ()).throw(
                    ExternalToolError("GLEIF_UNAVAILABLE", retryable=True)),
                cache=cache, now=self.now + timedelta(seconds=60))
        self.assertEqual(supplier_evidence_cache_keys(self.application), (
            f"gleif:{self.application['lei']}",
            f"vies:DE:{self.application['vat_number']}"))

    def test_firestore_cache_rejects_missing_and_corrupt_records(self):
        class Snapshot:
            def __init__(self, value): self.value, self.exists = value, value is not None
            def to_dict(self): return self.value
        class Document:
            def __init__(self): self.value = None
            def get(self): return Snapshot(self.value)
            def set(self, value): self.value = value
        class Collection:
            def __init__(self): self.documents = {}
            def document(self, key): return self.documents.setdefault(key, Document())
        class Client:
            def __init__(self): self.value = Collection()
            def collection(self, name): self.name = name; return self.value
        client = Client(); cache = FirestoreEvidenceCache(client)
        self.assertIsNone(cache.get("key"))
        cache.put("key", self.gleif)
        self.assertEqual(cache.get("key"), self.gleif)
        document = next(iter(client.value.documents.values()))
        document.value["cache_key"] = "other"
        with self.assertRaisesRegex(ExternalToolError, "EXTERNAL_EVIDENCE_CACHE_CORRUPT"):
            cache.get("key")
        document.value = {"cache_key": "key", "observation": []}
        with self.assertRaisesRegex(ExternalToolError, "EXTERNAL_EVIDENCE_CACHE_CORRUPT"):
            cache.get("key")

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

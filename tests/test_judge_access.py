import base64
from copy import deepcopy
import json
from unittest.mock import patch
import unittest

from fastapi.testclient import TestClient

from continuum.cloud_app import create_cloud_app
from continuum.judge_access import (
    FirestoreJudgeQuota, InMemoryJudgeQuota, JudgeAccessDenied, JudgeClaims,
    JudgeController, issue_judge_token, verify_judge_token,
)


SECRET = "judge-secret-that-is-longer-than-thirty-two-bytes"


class Snapshot:
    def __init__(self, value): self.value = deepcopy(value)
    @property
    def exists(self): return self.value is not None
    def to_dict(self): return deepcopy(self.value)


class Document:
    def __init__(self, db, key): self.db, self.key = db, key
    def get(self, transaction=None): return Snapshot(self.db.data.get(self.key))


class Collection:
    def __init__(self, db): self.db = db
    def document(self, key): return Document(self.db, key)


class Transaction:
    def __init__(self, db): self.db = db
    def set(self, ref, value): self.db.data[ref.key] = deepcopy(value)


class Firestore:
    def __init__(self): self.data = {}
    def collection(self, name): self.collection_name = name; return Collection(self)
    def transaction(self): return Transaction(self)


class Control:
    def __init__(self): self.started = []
    def start(self, run_id): self.started.append(run_id); return {"run_id": run_id, "phase": "WAITING_FOR_DEADLINE"}
    def status(self, run_id): return {"run_id": run_id, "phase": "VERIFIED"}


class JudgeAccessTests(unittest.TestCase):
    def token(self, *, jti="devpost26", expires=200, maximum=2):
        return issue_judge_token(secret=SECRET, jti=jti, expires_at=expires, max_runs=maximum)

    def test_capability_round_trip_expiry_signature_and_configuration(self):
        token = self.token()
        self.assertEqual(verify_judge_token(token, secret=SECRET, now=100),
                         JudgeClaims("devpost26", 200, 2))
        with self.assertRaisesRegex(JudgeAccessDenied, "JUDGE_TOKEN_EXPIRED"):
            verify_judge_token(token, secret=SECRET, now=200)
        with self.assertRaisesRegex(JudgeAccessDenied, "JUDGE_TOKEN_INVALID"):
            verify_judge_token(token[:-1] + ("A" if token[-1] != "A" else "B"), secret=SECRET, now=100)
        with self.assertRaisesRegex(JudgeAccessDenied, "JUDGE_TOKEN_MALFORMED"):
            verify_judge_token("not-a-token", secret=SECRET, now=100)
        with self.assertRaisesRegex(JudgeAccessDenied, "JUDGE_CONFIGURATION_INVALID"):
            verify_judge_token(token, secret="short", now=100)
        with self.assertRaisesRegex(JudgeAccessDenied, "JUDGE_SECRET_TOO_SHORT"):
            issue_judge_token(secret="short", jti="devpost26", expires_at=200)

    def test_capability_rejects_invalid_claim_shapes_and_encoding(self):
        for values in [
            {"jti": "short", "expires_at": 200, "max_runs": 2},
            {"jti": "devpost26", "expires_at": "later", "max_runs": 2},
            {"jti": "devpost26", "expires_at": 200, "max_runs": 0},
        ]:
            with self.subTest(values=values), self.assertRaisesRegex(
                    JudgeAccessDenied, "JUDGE_CLAIMS_INVALID"):
                issue_judge_token(secret=SECRET, **values)
        raw = b'{"aud":"wrong","exp":200,"jti":"devpost26","max_runs":2,"scope":"canonical-run:start"}'
        body = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
        import hmac
        signature = base64.urlsafe_b64encode(hmac.digest(SECRET.encode(), raw, "sha256")).rstrip(b"=").decode()
        with self.assertRaisesRegex(JudgeAccessDenied, "JUDGE_CLAIMS_INVALID"):
            verify_judge_token(f"{body}.{signature}", secret=SECRET, now=100)
        malformed = base64.urlsafe_b64encode(b"not-json").rstrip(b"=").decode()
        signature = base64.urlsafe_b64encode(hmac.digest(SECRET.encode(), b"not-json", "sha256")).rstrip(b"=").decode()
        with self.assertRaisesRegex(JudgeAccessDenied, "JUDGE_TOKEN_MALFORMED"):
            verify_judge_token(f"{malformed}.{signature}", secret=SECRET, now=100)
        with self.assertRaisesRegex(JudgeAccessDenied, "JUDGE_TOKEN_MALFORMED"):
            verify_judge_token("%%%.%%%", secret=SECRET, now=100)

    def test_in_memory_quota_is_idempotent_bounded_and_conflict_safe(self):
        quota = InMemoryJudgeQuota(); claims = JudgeClaims("devpost26", 200, 2)
        quota.consume(claims, "run-1"); quota.consume(claims, "run-1")
        quota.consume(claims, "run-2")
        self.assertTrue(quota.owns(claims, "run-1")); self.assertFalse(quota.owns(claims, "other"))
        with self.assertRaisesRegex(JudgeAccessDenied, "JUDGE_QUOTA_EXHAUSTED"):
            quota.consume(claims, "run-3")
        with self.assertRaisesRegex(JudgeAccessDenied, "JUDGE_GRANT_CONFLICT"):
            quota.consume(JudgeClaims("devpost26", 201, 2), "run-3")

    def test_firestore_quota_is_atomic_bounded_and_detects_corruption(self):
        db = Firestore(); quota = FirestoreJudgeQuota(db); claims = JudgeClaims("devpost26", 200, 1)
        with patch("google.cloud.firestore.transactional", lambda fn: fn):
            quota.consume(claims, "run-1"); quota.consume(claims, "run-1")
            self.assertTrue(quota.owns(claims, "run-1"))
            with self.assertRaisesRegex(JudgeAccessDenied, "JUDGE_QUOTA_EXHAUSTED"):
                quota.consume(claims, "run-2")
            key = next(iter(db.data)); db.data[key]["expires_at"] = 201
            with self.assertRaisesRegex(JudgeAccessDenied, "JUDGE_GRANT_CONFLICT"):
                quota.consume(claims, "run-1")
            db.data[key]["expires_at"] = 200; db.data[key]["runs"] = "broken"
            with self.assertRaisesRegex(JudgeAccessDenied, "JUDGE_GRANT_CORRUPT"):
                quota.consume(claims, "run-1")
        self.assertFalse(FirestoreJudgeQuota(Firestore()).owns(claims, "none"))

    def test_controller_owns_run_and_exposes_only_canonical_command(self):
        quota, control = InMemoryJudgeQuota(), Control()
        controller = JudgeController(secret=SECRET, quota=quota, control=control,
                                     clock=lambda: 100, nonce=lambda: "abcdef123456")
        token = self.token()
        result = controller.start(token)
        self.assertEqual(result["run_id"], "judge-devpost26-abcdef123456")
        self.assertEqual(result["judge_access"]["maximum_runs"], 2)
        self.assertEqual(controller.status(token, result["run_id"])["phase"], "VERIFIED")
        with self.assertRaisesRegex(JudgeAccessDenied, "JUDGE_RUN_DENIED"):
            controller.status(token, "judge-devpost26-000000000000")
        bad = JudgeController(secret=SECRET, quota=quota, control=control,
                              clock=lambda: 100, nonce=lambda: "not-hex")
        with self.assertRaisesRegex(JudgeAccessDenied, "JUDGE_NONCE_INVALID"):
            bad.start(token)

    def test_public_judge_http_surface_has_no_generic_or_internal_routes(self):
        controller = JudgeController(secret=SECRET, quota=InMemoryJudgeQuota(), control=Control(),
                                     clock=lambda: 100, nonce=lambda: "abcdef123456")
        client = TestClient(create_cloud_app(role="judge", judge_controller=controller))
        self.assertEqual(client.get("/").status_code, 200)
        self.assertIn("connect-src 'self'", client.get("/").headers["content-security-policy"])
        self.assertEqual(client.get("/docs").status_code, 404)
        self.assertEqual(client.post("/internal/investigate", json={}).status_code, 404)
        self.assertEqual(client.post("/cloud-smoke/start", json={"run_id": "x"}).status_code, 404)
        self.assertEqual(client.post("/judge/runs", json={}).status_code, 401)
        token = self.token(); headers = {"X-Continuum-Judge-Capability": token}
        self.assertEqual(client.post("/judge/runs", content=b"bad", headers=headers).status_code, 400)
        self.assertEqual(client.post("/judge/runs", json={"payload": "forbidden"}, headers=headers).status_code, 400)
        started = client.post("/judge/runs", json={}, headers=headers)
        self.assertEqual(started.status_code, 200)
        run_id = started.json()["run_id"]
        self.assertEqual(client.get(f"/judge/runs/{run_id}", headers=headers).json()["phase"], "VERIFIED")
        self.assertEqual(client.get("/judge/runs/judge-devpost26-000000000000", headers=headers).status_code, 403)

    def test_public_judge_maps_quota_configuration_and_upstream_failures(self):
        class Denied:
            def start(self, token): raise JudgeAccessDenied("JUDGE_QUOTA_EXHAUSTED")
            def status(self, token, run): raise RuntimeError("upstream")
        client = TestClient(create_cloud_app(role="judge", judge_controller=Denied()))
        headers = {"X-Continuum-Judge-Capability": "token"}
        self.assertEqual(client.post("/judge/runs", json={}, headers=headers).status_code, 429)
        self.assertEqual(client.get("/judge/runs/judge-devpost26-000000000000", headers=headers).status_code, 502)
        Denied.start = lambda self, token: (_ for _ in ()).throw(RuntimeError("upstream"))
        self.assertEqual(client.post("/judge/runs", json={}, headers=headers).status_code, 502)
        with patch.dict("os.environ", {}, clear=True):
            unavailable = TestClient(create_cloud_app(role="judge", judge_controller=None))
        self.assertEqual(unavailable.post("/judge/runs", json={}, headers=headers).status_code, 503)
        self.assertEqual(unavailable.get("/judge/runs/judge-devpost26-000000000000", headers=headers).status_code, 503)
        self.assertEqual(unavailable.get("/ready").status_code, 503)


if __name__ == "__main__":
    unittest.main()

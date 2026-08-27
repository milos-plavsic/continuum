import os
from pathlib import Path
from unittest.mock import patch
import unittest

from fastapi.testclient import TestClient

from continuum.cloud_app import create_cloud_app


ROOT = Path(__file__).resolve().parents[1]


class DeploymentScriptSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bootstrap = (ROOT / "scripts/cloud/bootstrap.sh").read_text()
        cls.deploy = (ROOT / "scripts/cloud/build-deploy.sh").read_text()
        cls.showcase = (ROOT / "scripts/cloud/deploy-showcase.sh").read_text()
        cls.cloudbuild = (ROOT / "deploy/cloudbuild.yaml").read_text()
        cls.provenance_check = (ROOT / "scripts/cloud/verify-build-provenance.sh").read_text()

    def test_services_are_private_digest_pinned_and_replace_invoker_policy(self):
        self.assertIn('--image "$image_ref"', self.deploy)
        self.assertIn('--no-allow-unauthenticated', self.deploy)
        self.assertIn('gcloud run services set-iam-policy', self.deploy)
        self.assertNotIn('gcloud run services add-iam-policy-binding', self.deploy)
        self.assertNotIn('allUsers', self.deploy)
        self.assertNotIn('allAuthenticatedUsers', self.deploy)
        self.assertIn('^(user|serviceAccount):[A-Za-z0-9._%+@-]+$', self.deploy)

    def test_only_the_presentation_only_showcase_is_public(self):
        self.assertIn('CONTINUUM_ROLE=showcase', self.showcase)
        self.assertIn('--no-allow-unauthenticated', self.showcase)
        self.assertIn('gcloud run services set-iam-policy', self.showcase)
        self.assertIn('  - allUsers', self.showcase)
        self.assertNotIn('roles/datastore.', self.showcase)
        self.assertNotIn('roles/pubsub.', self.showcase)
        self.assertNotIn('roles/aiplatform.', self.showcase)
        self.assertNotIn('CONTINUUM_CONTROL_URL', self.showcase)
        self.assertNotIn('GOOGLE_APPLICATION_CREDENTIALS', self.showcase)
        self.assertIn('CONTINUUM_OBSERVABILITY_ENABLED=false', self.showcase)

    def test_invocation_graph_is_push_to_control_and_control_to_workers(self):
        self.assertIn('write_invoker_policy "$policy_dir/control.yaml" "serviceAccount:$push_identity" "$CONTINUUM_OPERATOR_MEMBER"', self.deploy)
        for role in ("agent-v17", "agent-v18", "agent-v19", "verifier"):
            self.assertIn(f'write_invoker_policy "$policy_dir/{role}.yaml" "serviceAccount:$control_identity"', self.deploy)

    def test_runtime_iam_separates_control_agents_and_verifier(self):
        self.assertIn('roles/datastore.viewer', self.bootstrap)
        self.assertIn('roles/iam.serviceAccountTokenCreator', self.bootstrap)
        self.assertIn('roles/cloudbuild.builds.builder', self.bootstrap)
        self.assertNotIn('serviceAccount:$verifier" --role roles/datastore.user', self.bootstrap)
        self.assertNotIn('serviceAccount:$verifier" --role roles/pubsub.publisher', self.bootstrap)
        self.assertNotIn('serviceAccount:$verifier" --role roles/aiplatform.user', self.bootstrap)
        self.assertNotIn('continuum-v17@$CONTINUUM_PROJECT_ID.iam.gserviceaccount.com" --role', self.bootstrap)
        self.assertIn('continuum-v18@$CONTINUUM_PROJECT_ID.iam.gserviceaccount.com', self.bootstrap)
        self.assertIn('continuum-v19@$CONTINUUM_PROJECT_ID.iam.gserviceaccount.com', self.bootstrap)

    def test_deployment_carries_immutable_and_observability_metadata(self):
        for name in ("GIT_SHA", "CONTINUUM_IMAGE_DIGEST", "CONTINUUM_DEPLOYMENT_ID",
                     "CONTINUUM_PROTOCOL", "OTEL_SERVICE_NAME", "CONTINUUM_OBSERVABILITY_ENABLED",
                     "GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION", "GOOGLE_GENAI_USE_VERTEXAI",
                     "CONTINUUM_V17_URL", "CONTINUUM_V18_URL", "CONTINUUM_V19_URL", "CONTINUUM_VERIFIER_URL", "CONTINUUM_CONTROL_IDENTITY",
                     "CONTINUUM_V17_IDENTITY",
                     "CONTINUUM_V18_IDENTITY",
                     "CONTINUUM_V19_IDENTITY",
                     "CONTINUUM_VERIFIER_IDENTITY"):
            self.assertIn(name, self.deploy)
        self.assertIn('image_ref="${image_tag%:*}@$digest"', self.deploy)
        self.assertNotIn('GOOGLE_APPLICATION_CREDENTIALS', self.bootstrap + self.deploy)

    def test_build_requires_google_signed_provenance_for_deployed_digest(self):
        self.assertIn("requestedVerifyOption: VERIFIED", self.cloudbuild)
        self.assertIn('images:', self.cloudbuild)
        self.assertIn('--show-provenance', self.deploy)
        self.assertIn('provenance_summary', self.deploy)
        self.assertIn('containeranalysis.googleapis.com', self.bootstrap)
        self.assertIn('slsa-verifier verify-image', self.provenance_check)
        self.assertIn('--source-uri "$CONTINUUM_EXPECTED_SOURCE_URI"', self.provenance_check)
        self.assertIn('--builder-id https://cloudbuild.googleapis.com/GoogleHostedWorker',
                      self.provenance_check)


class DeploymentReadinessTests(unittest.TestCase):
    def test_readiness_fails_closed_without_immutable_metadata(self):
        with patch.dict(os.environ, {}, clear=True):
            response = TestClient(create_cloud_app(role="agent-v18")).get("/ready")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["code"], "DEPLOYMENT_NOT_READY")

    def test_readiness_accepts_consistent_immutable_metadata(self):
        git_sha = "a" * 40
        digest = "sha256:" + "b" * 64
        environment = {
            "GOOGLE_CLOUD_PROJECT": "continuum-prod",
            "GIT_SHA": git_sha,
            "CONTINUUM_IMAGE_DIGEST": digest,
            "CONTINUUM_DEPLOYMENT_ID": f"{git_sha}@{digest}",
            "CONTINUUM_PROTOCOL": "continuum/0.1-draft",
            "K_SERVICE": "continuum-agent-v18",
            "K_REVISION": "continuum-agent-v18-00001",
        }
        with patch.dict(os.environ, environment, clear=True):
            response = TestClient(create_cloud_app(role="agent-v18")).get("/ready")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deployment_id"], f"{git_sha}@{digest}")

    def test_correlation_headers_are_validated_and_propagated(self):
        client = TestClient(create_cloud_app(role="agent-v18"))
        self.assertEqual(client.get("/health", headers={"X-Continuum-Run-ID": "bad id"}).status_code, 400)
        self.assertEqual(client.get("/health", headers={"traceparent": "forged"}).status_code, 400)
        trace_id = "1" * 32
        response = client.get("/health", headers={
            "X-Continuum-Run-ID": "run-20260817-001",
            "traceparent": f"00-{trace_id}-{'2' * 16}-01",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-Continuum-Run-ID"], "run-20260817-001")
        self.assertEqual(response.headers["X-Cloud-Trace-Context"], f"{trace_id}/0;o=1")


if __name__ == "__main__":
    unittest.main()

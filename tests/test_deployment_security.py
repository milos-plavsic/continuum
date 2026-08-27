import os
from pathlib import Path
import subprocess
import tempfile
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
        cls.google_signature_check = (
            ROOT / "scripts/cloud/verify-google-build-signature.sh"
        ).read_text()
        cls.cloud_proof = (ROOT / "scripts/cloud/run-cloud-proof.sh").read_text()
        cls.cloud_smoke = (ROOT / "scripts/cloud/run-smoke.sh").read_text()
        cls.ci = (ROOT / ".github/workflows/ci.yml").read_text()
        cls.dockerfile = (ROOT / "Dockerfile").read_text()
        cls.compose = (ROOT / "compose.local.yaml").read_text()
        cls.pyproject = (ROOT / "pyproject.toml").read_text()

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
        self.assertIn("python3 -c", self.deploy)
        self.assertNotIn("\npython -c", self.deploy)
        self.assertIn('containeranalysis.googleapis.com', self.bootstrap)
        self.assertIn('slsa-verifier verify-image', self.provenance_check)
        self.assertIn('--source-uri "$CONTINUUM_EXPECTED_SOURCE_URI"', self.provenance_check)
        self.assertIn('--builder-id https://cloudbuild.googleapis.com/GoogleHostedWorker',
                      self.provenance_check)
        self.assertIn("PASSED: Verified SLSA provenance", self.provenance_check)
        self.assertIn("verifier_status", self.provenance_check)
        self.assertIn("google-hosted-worker/cryptoKeyVersions/1",
                      self.google_signature_check)
        self.assertIn("https://slsa.dev/provenance/v1", self.google_signature_check)
        self.assertIn("expected_digest", self.google_signature_check)
        self.assertIn("openssl dgst -sha256 -verify", self.google_signature_check)
        self.assertIn('[[ "$verification_output" == "Verified OK" ]]',
                      self.google_signature_check)
        self.assertIn('uv run python - "$run_id"', self.cloud_proof)
        self.assertNotIn('PYTHONPATH=src python3', self.cloud_proof)
        self.assertIn('uv run python scripts/cloud/package-evidence.py', self.cloud_smoke)
        self.assertIn('uv run python scripts/cloud/verify-evidence.py', self.cloud_smoke)

    def test_slsa_wrapper_rejects_textual_failure_even_with_zero_exit(self):
        result = self._run_fake_slsa("FAILED: SLSA verification failed", 0)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("did not produce an explicit PASS", result.stderr)

    def test_slsa_wrapper_accepts_only_explicit_pass_and_zero_exit(self):
        result = self._run_fake_slsa("PASSED: Verified SLSA provenance", 0)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_runtime_supply_chain_and_local_profile_are_release_gates(self):
        self.assertIn("google-adk>=2.7.1,<2.8", self.pyproject)
        base = "python:3.12-slim@sha256:7a8b475003c4fe15a2cd4e55e5cfc2f3560bdc9333d624f24cdd6d4340fd7a17"
        self.assertIn(f"FROM {base} AS builder-base", self.dockerfile)
        self.assertIn(f"FROM {base} AS runtime-base", self.dockerfile)
        self.assertIn("USER continuum", self.dockerfile)
        self.assertIn("apt-get install --only-upgrade", self.dockerfile)
        self.assertIn("openssl libssl3t64 openssl-provider-legacy", self.dockerfile)
        self.assertIn("AS local-runtime", self.dockerfile)
        self.assertTrue(self.dockerfile.rstrip().endswith("FROM cloud-runtime AS final"))
        self.assertIn("grep -F 'continuum.cloud_app:app'", self.ci)
        self.assertIn("anchore/sbom-action@e22c389904149dbc22b58101806040fa8d37a610", self.ci)
        self.assertIn("aquasecurity/trivy-action@a9c7b0f06e461e9d4b4d1711f154ee024b8d7ab8", self.ci)
        self.assertIn("severity: HIGH,CRITICAL", self.ci)
        self.assertIn('exit-code: "1"', self.ci)
        self.assertIn("target: local-runtime", self.compose)
        self.assertIn("read_only: true", self.compose)
        self.assertIn("no-new-privileges:true", self.compose)

    def _run_fake_slsa(self, output: str, status: int):
        with tempfile.TemporaryDirectory() as directory:
            tools = Path(directory)
            gcloud = tools / "gcloud"
            gcloud.write_text("#!/usr/bin/env bash\nprintf '{}\\n'\n")
            gcloud.chmod(0o755)
            verifier = tools / "slsa-verifier"
            verifier.write_text(
                "#!/usr/bin/env bash\n"
                f"printf '%s\\n' {output!r}\n"
                f"exit {status}\n"
            )
            verifier.chmod(0o755)
            environment = os.environ | {
                "PATH": f"{tools}:{os.environ['PATH']}",
                "CONTINUUM_IMAGE_AT_DIGEST": "registry.example/image@sha256:" + "a" * 64,
                "CONTINUUM_EXPECTED_SOURCE_URI": "github.com/example/project",
            }
            return subprocess.run(
                ["bash", str(ROOT / "scripts/cloud/verify-build-provenance.sh")],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )


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

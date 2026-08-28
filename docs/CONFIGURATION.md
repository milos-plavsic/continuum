# Configuration inventory

Generated from `config/environment.json` by `scripts/check_configuration.py`.
Edit the JSON inventory, not this table. Values are never captured here.

Secrets have no defaults and are forbidden from public evidence. `required_in` names
the profiles in which an operator or platform must supply the value; an empty list
means optional. See `docs/CI_ASSURANCE.md` for profile boundaries.

| Variable | Owner / kind | Type | Required in | Default | Sensitivity / evidence | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `CONTINUUM_ARTIFACT_REPOSITORY` | deployment / operator-input | resource-name | cloud-deploy | `continuum` | public / include | Artifact Registry repository name used for built images. |
| `CONTINUUM_CONTROL_AUDIENCE` | application / runtime | url | cloud-runtime | `—` | internal / include | OIDC audience accepted by the private control service. |
| `CONTINUUM_CONTROL_IDENTITY` | application / runtime | email | cloud-runtime | `—` | public / include | Workload identity authorized as the control principal. |
| `CONTINUUM_CONTROL_SERVICE` | deployment / operator-input | resource-name | cloud-deploy, cloud-proof | `continuum-control` | public / include | Cloud Run service name for the control plane. |
| `CONTINUUM_CONTROL_URL` | application / runtime | url | cloud-runtime, judge-deploy | `—` | internal / include | Resolved private control-plane HTTPS endpoint. |
| `CONTINUUM_DATA_DIR` | application / runtime | path | local | `/tmp/continuum-runs` | internal / redact | Writable directory for deterministic local run artifacts. |
| `CONTINUUM_DEADLINE_QUEUE` | deployment / runtime | resource-name | cloud-runtime | `continuum-deadlines` | public / include | Cloud Tasks queue used for durable deadline checks. |
| `CONTINUUM_DEMO_MODE` | application / runtime | boolean | local | `false` | public / include | Explicitly enables the local demonstration mutation surface. |
| `CONTINUUM_DEPLOYMENT_ID` | deployment / runtime | identifier | cloud-runtime | `—` | public / include | Immutable source-and-image deployment correlation identifier. |
| `CONTINUUM_EVIDENCE_DIR` | evidence / operator-input | path | cloud-proof | `—` | internal / redact | New output directory for one private cloud evidence capture. |
| `CONTINUUM_EXPECTED_SOURCE_URI` | evidence / operator-input | url | cloud-proof | `—` | public / include | Expected source repository URI for provenance verification. |
| `CONTINUUM_FIRESTORE_LOCATION` | deployment / operator-input | identifier | cloud-bootstrap | `—` | public / include | Immutable Firestore database location selected at bootstrap. |
| `CONTINUUM_FORCE_REDELIVERY` | application / runtime | boolean | cloud-runtime | `true` | public / include | Enables the bounded Pub/Sub redelivery demonstration probe. |
| `CONTINUUM_GITHUB_ISSUE_NUMBER` | deployment / runtime | integer | cloud-runtime | `—` | public / include | Pre-provisioned reversible synthetic work-item issue number. |
| `CONTINUUM_GITHUB_PROVIDER_SECRET` | deployment / secret-reference | resource-name | cloud-deploy | `—` | internal / redact | Secret Manager resource containing the GitHub provider token. |
| `CONTINUUM_GITHUB_PROVIDER_TOKEN` | application / secret | string | cloud-runtime | `—` | secret / forbid | Runtime bearer token for the bounded GitHub Issues adapter. |
| `CONTINUUM_GITHUB_REPOSITORY` | application / runtime | identifier | cloud-runtime | `—` | public / include | Owner and repository for the synthetic work-item adapter. |
| `CONTINUUM_GIT_SHA` | deployment / operator-input | digest | cloud-deploy, cloud-proof, judge-deploy, showcase-deploy | `—` | public / include | Exact checked-out commit supplied to deployment and proof scripts. |
| `CONTINUUM_IMAGE` | deployment / operator-input | resource-name | cloud-deploy | `continuum-control-plane` | public / include | Artifact Registry image name for the private control runtime. |
| `CONTINUUM_IMAGE_AT_DIGEST` | evidence / operator-input | digest | cloud-proof | `—` | public / include | Immutable image reference submitted to provenance verification. |
| `CONTINUUM_IMAGE_DIGEST` | deployment / runtime | digest | cloud-runtime | `—` | public / include | Resolved immutable runtime image digest exposed for correlation. |
| `CONTINUUM_JUDGE_ACCOUNT` | judge-gateway / operator-input | resource-name | judge-deploy | `continuum-judge` | public / include | Service-account short name for the bounded judge gateway. |
| `CONTINUUM_JUDGE_GRANT_JTI` | judge-gateway / operator-input | identifier | judge-deploy | `—` | internal / redact | Unique identifier embedded in a judge capability grant. |
| `CONTINUUM_JUDGE_HMAC_SECRET` | judge-gateway / secret | string | cloud-runtime, judge-deploy | `—` | secret / forbid | Runtime key used to authenticate bounded judge capabilities. |
| `CONTINUUM_JUDGE_IMAGE` | judge-gateway / operator-input | resource-name | judge-deploy | `continuum-judge` | public / include | Artifact Registry image name for the judge gateway. |
| `CONTINUUM_JUDGE_MAX_RUNS` | judge-gateway / operator-input | integer | judge-deploy | `3` | public / include | Maximum starts authorized by one judge capability. |
| `CONTINUUM_JUDGE_SECRET_NAME` | judge-gateway / secret-reference | resource-name | judge-deploy | `continuum-judge-hmac` | internal / redact | Secret Manager resource holding the judge HMAC key. |
| `CONTINUUM_JUDGE_SERVICE` | judge-gateway / operator-input | resource-name | judge-deploy | `continuum-judge` | public / include | Cloud Run service name for the bounded judge gateway. |
| `CONTINUUM_JUDGE_TOKEN_HOURS` | judge-gateway / operator-input | duration-hours | judge-deploy | `720` | public / include | Lifetime in hours for an issued judge capability. |
| `CONTINUUM_LIFECYCLE_TOPIC` | deployment / runtime | resource-name | cloud-runtime | `continuum-lifecycle` | public / include | Pub/Sub topic carrying lifecycle transition notifications. |
| `CONTINUUM_MODEL_ARMOR_TEMPLATE` | deployment / runtime | resource-name | cloud-runtime | `continuum-ingress` | public / include | Google Model Armor template applied at raw-input ingress. |
| `CONTINUUM_OBSERVABILITY_ENABLED` | application / runtime | boolean | cloud-runtime | `true` | public / include | Enables Cloud Trace export for a deployed runtime role. |
| `CONTINUUM_OPERATOR_MEMBER` | deployment / operator-input | principal | cloud-deploy, judge-deploy | `—` | internal / redact | Exact human or workload principal granted operator invocation. |
| `CONTINUUM_PRIVATE_ARTIFACT_DIR` | judge-gateway / operator-input | path | judge-deploy | `artifacts/private` | internal / redact | Private local directory for generated judge capability files. |
| `CONTINUUM_PROJECT_ID` | deployment / operator-input | identifier | cloud-bootstrap, cloud-deploy, cloud-proof, judge-deploy, showcase-deploy | `—` | public / include | Operator-selected Google Cloud project identifier. |
| `CONTINUUM_PROTOCOL` | application / runtime | identifier | cloud-runtime | `continuum/0.1-draft` | public / include | Deployed Continuity Contract protocol profile identifier. |
| `CONTINUUM_PUBSUB_PUSH_ACCOUNT` | deployment / operator-input | resource-name | judge-deploy | `continuum-pubsub-push` | public / include | Service-account short name used for authenticated Pub/Sub push. |
| `CONTINUUM_PUBSUB_PUSH_IDENTITY` | application / runtime | email | cloud-runtime | `—` | public / include | Full workload identity accepted for Pub/Sub push delivery. |
| `CONTINUUM_PUSH_SUBSCRIPTION` | application / runtime | resource-name | cloud-runtime | `—` | public / include | Full Pub/Sub subscription resource accepted at ingress. |
| `CONTINUUM_REGION` | deployment / operator-input | identifier | cloud-bootstrap, cloud-deploy, cloud-proof, judge-deploy, showcase-deploy | `—` | public / include | Google Cloud region for runtime and evidence operations. |
| `CONTINUUM_ROLE` | application / runtime | identifier | cloud-runtime | `control` | public / include | Bounded runtime role selected for the shared container image. |
| `CONTINUUM_RUN_ID` | evidence / operator-input | identifier | cloud-proof | `—` | public / include | Exact lifecycle run selected for cloud evidence capture. |
| `CONTINUUM_SHOWCASE_ACCOUNT` | deployment / operator-input | resource-name | showcase-deploy | `continuum-showcase` | public / include | Service-account short name for the zero-role public showcase. |
| `CONTINUUM_SHOWCASE_IMAGE` | deployment / operator-input | resource-name | showcase-deploy | `continuum-showcase` | public / include | Artifact Registry image name for the public showcase. |
| `CONTINUUM_SHOWCASE_SERVICE` | deployment / operator-input | resource-name | showcase-deploy | `continuum-showcase` | public / include | Cloud Run service name for the public showcase. |
| `CONTINUUM_TRACE_ID` | evidence / operator-input | identifier | cloud-proof | `—` | public / include | Exact correlated Cloud Trace identifier selected for capture. |
| `CONTINUUM_V17_IDENTITY` | application / runtime | email | cloud-runtime | `—` | public / include | Full workload identity of the predecessor agent service. |
| `CONTINUUM_V17_SERVICE` | deployment / operator-input | resource-name | cloud-deploy, cloud-proof | `continuum-agent-v17` | public / include | Cloud Run service name for predecessor agent version 17. |
| `CONTINUUM_V17_URL` | application / runtime | url | cloud-runtime | `—` | internal / include | Resolved private endpoint for predecessor agent version 17. |
| `CONTINUUM_V18_IDENTITY` | application / runtime | email | cloud-runtime | `—` | public / include | Full workload identity of successor candidate version 18. |
| `CONTINUUM_V18_SERVICE` | deployment / operator-input | resource-name | cloud-deploy, cloud-proof | `continuum-agent-v18` | public / include | Cloud Run service name for successor candidate version 18. |
| `CONTINUUM_V18_URL` | application / runtime | url | cloud-runtime | `—` | internal / include | Resolved private endpoint for successor candidate version 18. |
| `CONTINUUM_V19_IDENTITY` | application / runtime | email | cloud-runtime | `—` | public / include | Full workload identity of successor candidate version 19. |
| `CONTINUUM_V19_SERVICE` | deployment / operator-input | resource-name | cloud-deploy, cloud-proof | `continuum-agent-v19` | public / include | Cloud Run service name for successor candidate version 19. |
| `CONTINUUM_V19_URL` | application / runtime | url | cloud-runtime | `—` | internal / include | Resolved private endpoint for successor candidate version 19. |
| `CONTINUUM_VERIFIER_IDENTITY` | application / runtime | email | cloud-runtime | `—` | public / include | Full workload identity of the read-only verifier service. |
| `CONTINUUM_VERIFIER_SERVICE` | deployment / operator-input | resource-name | cloud-deploy, cloud-proof | `continuum-verifier` | public / include | Cloud Run service name for the independent verifier role. |
| `CONTINUUM_VERIFIER_URL` | application / runtime | url | cloud-runtime | `—` | internal / include | Resolved private endpoint for the read-only verifier service. |
| `CONTINUUM_VIDEO_ID_TOKEN` | video / secret | string | video | `—` | secret / forbid | Short-lived private control identity token used only during capture. |
| `GIT_SHA` | platform / runtime | digest | cloud-runtime | `—` | public / include | Immutable deployed source commit exposed by the runtime. |
| `GOOGLE_CLOUD_LOCATION` | platform / runtime | identifier | cloud-runtime | `global` | public / include | Vertex AI location selected by Google client libraries. |
| `GOOGLE_CLOUD_PROJECT` | platform / platform-provided | identifier | cloud-runtime | `—` | public / include | Google-provided runtime project identifier for client libraries. |
| `GOOGLE_CLOUD_REGION` | platform / runtime | identifier | optional | `local` | public / include | Optional region exposed by the public read-only application. |
| `GOOGLE_GENAI_USE_VERTEXAI` | platform / runtime | boolean | cloud-runtime | `true` | public / include | Selects Vertex AI rather than developer-key Gemini transport. |
| `K_REVISION` | platform / platform-provided | identifier | cloud-runtime | `—` | public / include | Cloud Run supplied immutable serving revision name. |
| `K_SERVICE` | platform / platform-provided | identifier | cloud-runtime | `—` | public / include | Cloud Run supplied service name for request correlation. |
| `OTEL_SERVICE_NAME` | platform / runtime | identifier | cloud-runtime | `continuum` | public / include | OpenTelemetry logical service name attached to exported spans. |
| `PORT` | platform / platform-provided | integer | cloud-runtime, local | `8080` | public / include | HTTP listen port supplied by Cloud Run or local composition. |

## Machine checks

```bash
uv run --extra test python scripts/check_configuration.py --check
```

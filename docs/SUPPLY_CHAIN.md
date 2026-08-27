# Runtime supply-chain policy

`uv.lock` resolves the complete environment and `pyproject.toml` bounds Google
ADK to the reviewed `2.7.x` minor line. CI actions use immutable commit SHAs.

The Dockerfile pins its Python base by SHA-256 and uses separate build and
runtime stages. The runtime stage applies available Debian security upgrades
for its OpenSSL packages before dropping privileges. The final image contains
the application, its virtual environment, and no `uv`, compiler cache, source
checkout metadata, credentials, or generated cloud state. It runs as UID 10001
and carries OCI source, revision, creation, and license labels.

Every pull request and main push:

1. executes the locked 100% statement/branch, conformance and release gates;
2. builds and smoke-tests cloud and credential-free local targets;
3. verifies the runtime identity and import surface;
4. generates an SPDX JSON SBOM from the final image;
5. fails on actionable fixed HIGH or CRITICAL Trivy findings;
6. retains the SBOM as a CI artifact for 30 days.

`ignore-unfixed: true` makes the gate actionable: a base-image issue without an
upstream fix is reported but cannot be repaired by this repository. Fixed HIGH
or CRITICAL findings block the release.

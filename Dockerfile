FROM python:3.12-slim@sha256:7a8b475003c4fe15a2cd4e55e5cfc2f3560bdc9333d624f24cdd6d4340fd7a17 AS builder-base

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
WORKDIR /app
RUN pip install --no-cache-dir uv==0.12.3
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
COPY app ./app

FROM builder-base AS cloud-builder
RUN uv sync --frozen --no-dev --extra web --extra google --extra signatures \
    && find /app/.venv -type d -name __pycache__ -prune -exec rm -rf '{}' + \
    && find /app/.venv -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete

FROM builder-base AS local-builder
RUN uv sync --frozen --no-dev --extra web --extra signatures \
    && find /app/.venv -type d -name __pycache__ -prune -exec rm -rf '{}' + \
    && find /app/.venv -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete

FROM python:3.12-slim@sha256:7a8b475003c4fe15a2cd4e55e5cfc2f3560bdc9333d624f24cdd6d4340fd7a17 AS runtime-base
ARG VCS_REF=unknown
ARG BUILD_DATE=unknown
LABEL org.opencontainers.image.title="Continuum" \
      org.opencontainers.image.description="Governed succession control plane for enterprise agents" \
      org.opencontainers.image.source="https://github.com/milos-plavsic/continuum" \
      org.opencontainers.image.revision="$VCS_REF" \
      org.opencontainers.image.created="$BUILD_DATE" \
      org.opencontainers.image.licenses="Apache-2.0"
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PORT=8080
WORKDIR /app
RUN apt-get update \
    && apt-get install --only-upgrade --yes --no-install-recommends \
       openssl libssl3t64 openssl-provider-legacy \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 continuum
COPY --chown=continuum:continuum src ./src
COPY --chown=continuum:continuum app ./app
USER continuum
EXPOSE 8080

FROM runtime-base AS cloud-runtime
COPY --from=cloud-builder --chown=continuum:continuum /app/.venv /app/.venv
CMD ["sh", "-c", "module=continuum.api:app; if [ -n \"${CONTINUUM_ROLE:-}\" ]; then module=continuum.cloud_app:app; fi; exec uvicorn \"$module\" --host 0.0.0.0 --port ${PORT}"]

FROM runtime-base AS local-runtime
COPY --from=local-builder --chown=continuum:continuum /app/.venv /app/.venv
CMD ["sh", "-c", "exec uvicorn continuum.local_app:app --host 0.0.0.0 --port ${PORT}"]

# Keep the production target last: an unqualified `docker build .` must never
# silently select the credential-free local application for Cloud Run.
FROM cloud-runtime AS final

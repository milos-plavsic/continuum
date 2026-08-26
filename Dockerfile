FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PORT=8080

WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
COPY app ./app
RUN pip install --no-cache-dir uv==0.12.3 \
    && uv sync --frozen --no-dev --extra web --extra google --extra signatures \
    && useradd --create-home --uid 10001 continuum

ENV PATH="/app/.venv/bin:$PATH"
USER continuum
EXPOSE 8080
CMD ["sh", "-c", "module=continuum.api:app; if [ -n \"${CONTINUUM_ROLE:-}\" ]; then module=continuum.cloud_app:app; fi; exec uvicorn \"$module\" --host 0.0.0.0 --port ${PORT}"]

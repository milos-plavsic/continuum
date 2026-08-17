FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY app ./app
RUN pip install --no-cache-dir '.[web,google,signatures]' \
    && useradd --create-home --uid 10001 continuum

USER continuum
EXPOSE 8080
CMD ["sh", "-c", "module=continuum.api:app; if [ -n \"${CONTINUUM_ROLE:-}\" ]; then module=continuum.cloud_app:app; fi; exec uvicorn \"$module\" --host 0.0.0.0 --port ${PORT}"]

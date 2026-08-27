"""Loopback/container API for a complete no-credential Continuum lifecycle."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException

from .local_runtime import run_local_succession


app = FastAPI(title="Continuum local reference", docs_url=None, redoc_url=None)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "profile": "reference-local-container/1"}


@app.post("/runs/{run_id}")
def run(run_id: str) -> dict:
    try:
        return run_local_succession(run_id)
    except (KeyError, RuntimeError, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

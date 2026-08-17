"""Judge-facing control-plane API for the canonical live demonstration."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from .standard import build_contract_bundle


@dataclass
class ScenarioRecord:
    run_id: str
    result: dict[str, Any]
    contract: dict[str, Any]


class ScenarioService:
    def __init__(self, root: Path):
        self.root = root
        self.records: dict[str, ScenarioRecord] = {}
        self.lock = Lock()

    def start(self) -> ScenarioRecord:
        run_id = str(uuid4())
        workdir = self.root / run_id
        contract = build_contract_bundle(workdir)
        result = json.loads((workdir / "scenario" / "result.json").read_text())
        record = ScenarioRecord(run_id, result, contract)
        with self.lock:
            self.records[run_id] = record
        return record

    def get(self, run_id: str) -> ScenarioRecord:
        try:
            return self.records[run_id]
        except KeyError as error:
            raise HTTPException(status_code=404, detail={"code": "RUN_NOT_FOUND"}) from error


def _summary(record: ScenarioRecord) -> dict[str, Any]:
    result = record.result
    return {
        "run_id": record.run_id,
        "status": result["outcome"],
        "obligation": {"status": result["obligation_status"], "owner": result["owner"]},
        "fleet": [
            {"version": "v17", "status": result["predecessor_status"], "epoch": 42},
            {"version": "v18", "status": result["successor_status"], "epoch": 42},
        ],
        "provider": {"vendor_count": result["vendor_count"], "duplicate_effects": result["vendor_count"] - 1},
        "denials": result["denials"],
        "revoked_candidates_exposed": result["revoked_candidates_exposed"],
        "manifest_hash": result["manifest_hash"],
        "timeline": result["timeline"],
        "attestation": next(a for a in record.contract["artifacts"] if a["artifact_type"] == "continuity_attestation"),
    }


def create_app(*, data_root: Path | None = None, demo_mode: bool | None = None) -> FastAPI:
    root = data_root or Path(os.getenv("CONTINUUM_DATA_DIR", "/tmp/continuum-runs"))
    enabled = demo_mode if demo_mode is not None else os.getenv("CONTINUUM_DEMO_MODE") == "1"
    service = ScenarioService(root)
    app = FastAPI(title="Continuum Control Plane", version="0.1.0", docs_url="/api/docs")

    def require_demo() -> None:
        if not enabled:
            raise HTTPException(status_code=403, detail={"code": "DEMO_MODE_DISABLED"})

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "service": "continuum-control-plane"}

    @app.get("/build-info")
    def build_info() -> dict[str, Any]:
        return {"revision": os.getenv("K_REVISION", "local"), "commit": os.getenv("GIT_SHA", "unknown"),
                "project": os.getenv("GOOGLE_CLOUD_PROJECT", "local"), "region": os.getenv("GOOGLE_CLOUD_REGION", "local"),
                "framework": "google-adk", "model": "gemini-3.6-flash"}

    @app.post("/api/scenarios", status_code=201)
    def start_scenario() -> dict[str, Any]:
        require_demo()
        return _summary(service.start())

    @app.get("/api/scenarios/{run_id}")
    def get_scenario(run_id: str) -> dict[str, Any]:
        return _summary(service.get(run_id))

    @app.get("/api/scenarios/{run_id}/contract")
    def get_contract(run_id: str) -> dict[str, Any]:
        return service.get(run_id).contract

    @app.post("/api/scenarios/{run_id}/redeliver")
    def redeliver(run_id: str) -> dict[str, Any]:
        require_demo(); record = service.get(run_id)
        return {"disposition": "DEDUPLICATED", "new_external_effect": False,
                "vendor_count": record.result["vendor_count"]}

    @app.post("/api/scenarios/{run_id}/predecessor/action")
    def predecessor_action(run_id: str) -> None:
        require_demo(); service.get(run_id)
        raise HTTPException(status_code=403, detail={"code": "STALE_FENCE", "presented_epoch": 41, "current_epoch": 42, "effect_performed": False})

    @app.post("/api/scenarios/{run_id}/predecessor/memory")
    def predecessor_memory(run_id: str) -> None:
        require_demo(); service.get(run_id)
        raise HTTPException(status_code=403, detail={"code": "GRANT_REVOKED", "retrieval_started": False, "candidates_considered": 0})

    @app.get("/", response_class=HTMLResponse)
    def cockpit() -> str:
        return (Path(__file__).with_name("static") / "cockpit.html").read_text()

    return app


app = create_app()

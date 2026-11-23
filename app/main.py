"""FastAPI 服务：为画布前端提供工作流校验与运行接口。

启动：
    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .engine import WorkflowEngine, WorkflowError

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="AIGC Workflow MVP", version="0.1.0")


class WorkflowPayload(BaseModel):
    workflow: Dict[str, Any]


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/api/workflow/validate")
def validate(payload: WorkflowPayload) -> Dict[str, Any]:
    try:
        WorkflowEngine(payload.workflow)
        return {"valid": True}
    except WorkflowError as exc:
        return {"valid": False, "reason": str(exc)}


@app.post("/api/workflow/run")
def run_workflow(payload: WorkflowPayload) -> Dict[str, Any]:
    try:
        engine = WorkflowEngine(payload.workflow)
        result = engine.run()
    except WorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": result.status,
        "final_output": result.final_output,
        "error": result.error,
        "node_results": [
            {
                "node_id": r.node_id,
                "node_type": r.node_type,
                "status": r.status,
                "output": r.output,
                "error": r.error,
                "elapsed_ms": round(r.elapsed_ms, 2),
            }
            for r in result.node_results
        ],
    }


@app.get("/api/workflow/example")
def example_workflow() -> Dict[str, Any]:
    example_path = BASE_DIR / "examples" / "hello_poem.json"
    return json.loads(example_path.read_text(encoding="utf-8"))


# 静态画布页面
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

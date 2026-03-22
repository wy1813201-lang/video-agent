#!/usr/bin/env python3
"""n8n-friendly HTTP wrapper for video-agent.

目标：尽量复用现有 `cli.py` / `main.py`，不重写核心生产逻辑。

运行：
    uvicorn integrations.n8n_api:app --host 0.0.0.0 --port 8000

说明：
- `/api/v1/cli/run` 对齐 `python cli.py ...`
- `/api/v1/main/generate` 对齐 `python main.py generate ...`
- `/api/v1/runs/{run_id}` / `/logs` 用于给 n8n 轮询状态
- 默认支持同步执行；设置 `async_run=true` 可后台执行并返回 `run_id`
"""

from __future__ import annotations

import os
import shlex
import subprocess
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent
PYTHON_BIN = os.environ.get("VIDEO_AGENT_PYTHON", "python")
MAX_LOG_CHARS = int(os.environ.get("VIDEO_AGENT_MAX_LOG_CHARS", "50000"))

app = FastAPI(
    title="video-agent n8n API",
    version="0.1.0",
    description="Minimal HTTP wrapper that reuses cli.py and main.py for n8n integration.",
)


class RunRecord(BaseModel):
    run_id: str
    status: Literal["queued", "running", "success", "failed"]
    command: List[str]
    command_text: str
    entrypoint: Literal["cli", "main"]
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""


RUNS: Dict[str, RunRecord] = {}
RUN_LOCK = threading.Lock()


class CliRunRequest(BaseModel):
    step: Literal["all", "script", "character", "storyboard", "keyframe", "video", "assemble", "audit"] = "all"
    mode: Literal["sop", "efficient"] = "sop"
    topic: str = Field(default="重生千金复仇记")
    style: str = Field(default="情感")
    episodes: int = Field(default=3, ge=1)
    character_file: Optional[str] = Field(default=None, description="可选：已有角色母版 JSON 路径")
    async_run: bool = Field(default=False, description="true=后台运行，false=等待命令完成")


class MainGenerateRequest(BaseModel):
    topic: str
    style: Literal["情感", "悬疑", "搞笑", "科幻"] = "情感"
    episodes: int = Field(default=3, ge=1)
    output: str = Field(default="output")
    config: str = Field(default="config.yaml")
    auto_approve: bool = Field(default=False)
    async_run: bool = Field(default=False, description="true=后台运行，false=等待命令完成")


class StepPlanRequest(BaseModel):
    topic: str = "重生千金复仇记"
    style: str = "情感"
    episodes: int = Field(default=3, ge=1)
    step: Literal["script", "character", "storyboard", "keyframe", "video", "assemble", "audit"] = "storyboard"
    mode: Literal["sop", "efficient"] = "sop"


class RunResponse(BaseModel):
    ok: bool
    message: str
    run: RunRecord


def _utc_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"



def _trim_log(text: str) -> str:
    if len(text) <= MAX_LOG_CHARS:
        return text
    return text[-MAX_LOG_CHARS:]



def _build_cli_command(req: CliRunRequest) -> List[str]:
    command = [
        PYTHON_BIN,
        "cli.py",
        "--step",
        req.step,
        "--mode",
        req.mode,
        "--topic",
        req.topic,
        "--style",
        req.style,
        "--episodes",
        str(req.episodes),
    ]
    if req.character_file:
        command.extend(["--character-file", req.character_file])
    return command



def _build_main_generate_command(req: MainGenerateRequest) -> List[str]:
    command = [
        PYTHON_BIN,
        "main.py",
        "generate",
        "--topic",
        req.topic,
        "--style",
        req.style,
        "--episodes",
        str(req.episodes),
        "--output",
        req.output,
        "--config",
        req.config,
    ]
    if req.auto_approve:
        command.append("--auto-approve")
    return command



def _register_run(command: List[str], entrypoint: Literal["cli", "main"]) -> RunRecord:
    run_id = str(uuid.uuid4())
    record = RunRecord(
        run_id=run_id,
        status="queued",
        command=command,
        command_text=shlex.join(command),
        entrypoint=entrypoint,
        created_at=_utc_now(),
    )
    with RUN_LOCK:
        RUNS[run_id] = record
    return record



def _execute_sync(record: RunRecord) -> RunRecord:
    record.status = "running"
    record.started_at = _utc_now()
    completed = subprocess.run(
        record.command,
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
    )
    record.exit_code = completed.returncode
    record.stdout = _trim_log(completed.stdout or "")
    record.stderr = _trim_log(completed.stderr or "")
    record.finished_at = _utc_now()
    record.status = "success" if completed.returncode == 0 else "failed"
    with RUN_LOCK:
        RUNS[record.run_id] = record
    return record



def _execute_async(record: RunRecord) -> None:
    def runner() -> None:
        record.status = "running"
        record.started_at = _utc_now()
        with RUN_LOCK:
            RUNS[record.run_id] = record

        process = subprocess.Popen(
            record.command,
            cwd=str(BASE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = process.communicate()
        record.exit_code = process.returncode
        record.stdout = _trim_log(stdout or "")
        record.stderr = _trim_log(stderr or "")
        record.finished_at = _utc_now()
        record.status = "success" if process.returncode == 0 else "failed"
        with RUN_LOCK:
            RUNS[record.run_id] = record

    threading.Thread(target=runner, daemon=True).start()



def _start_run(command: List[str], entrypoint: Literal["cli", "main"], async_run: bool) -> RunRecord:
    record = _register_run(command, entrypoint)
    if async_run:
        _execute_async(record)
        return record
    return _execute_sync(record)



def _get_run_or_404(run_id: str) -> RunRecord:
    with RUN_LOCK:
        record = RUNS.get(run_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"run_id not found: {run_id}")
    return record


@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "video-agent n8n API",
        "version": "0.1.0",
        "base_dir": str(BASE_DIR),
        "note": "This is the integration layer only. n8n itself is not installed/deployed by this delivery.",
    }


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "status": "healthy", "time": _utc_now()}


@app.get("/api/v1/options")
def options() -> Dict[str, Any]:
    return {
        "cli": {
            "steps": ["all", "script", "character", "storyboard", "keyframe", "video", "assemble", "audit"],
            "modes": ["sop", "efficient"],
        },
        "main": {
            "commands": ["generate"],
            "styles": ["情感", "悬疑", "搞笑", "科幻"],
        },
        "n8n_parameter_mapping": {
            "topic": "短剧主题",
            "style": "风格",
            "episodes": "集数",
            "step": "cli.py 的阶段参数",
            "mode": "cli.py 的执行模式：sop / efficient",
            "auto_approve": "main.py generate 的自动审批开关",
        },
    }


@app.post("/api/v1/cli/run", response_model=RunResponse)
def run_cli(req: CliRunRequest) -> RunResponse:
    if req.mode == "efficient" and req.step != "all":
        raise HTTPException(status_code=400, detail="efficient mode currently supports step=all only, matching cli.py behavior")
    command = _build_cli_command(req)
    record = _start_run(command, entrypoint="cli", async_run=req.async_run)
    message = "CLI run started in background" if req.async_run else "CLI run finished"
    return RunResponse(ok=record.status != "failed", message=message, run=record)


@app.post("/api/v1/main/generate", response_model=RunResponse)
def run_main_generate(req: MainGenerateRequest) -> RunResponse:
    command = _build_main_generate_command(req)
    record = _start_run(command, entrypoint="main", async_run=req.async_run)
    message = "main.py generate started in background" if req.async_run else "main.py generate finished"
    return RunResponse(ok=record.status != "failed", message=message, run=record)


@app.post("/api/v1/n8n/step-plan")
def n8n_step_plan(req: StepPlanRequest) -> Dict[str, Any]:
    body = req.model_dump()
    cli_payload = {
        "step": req.step,
        "mode": req.mode,
        "topic": req.topic,
        "style": req.style,
        "episodes": req.episodes,
        "async_run": True,
    }
    return {
        "ok": True,
        "message": "Use this payload in n8n HTTP Request node to trigger a CLI stage.",
        "current_request": body,
        "http_request": {
            "method": "POST",
            "url": "http://127.0.0.1:8000/api/v1/cli/run",
            "json": cli_payload,
        },
        "examples": {
            "script_only": {**cli_payload, "step": "script"},
            "storyboard_only": {**cli_payload, "step": "storyboard"},
            "full_sop": {**cli_payload, "step": "all", "mode": "sop"},
            "minimal_efficient": {**cli_payload, "step": "all", "mode": "efficient"},
        },
    }


@app.get("/api/v1/runs")
def list_runs() -> Dict[str, Any]:
    with RUN_LOCK:
        runs = [record.model_dump() for record in RUNS.values()]
    runs.sort(key=lambda item: item["created_at"], reverse=True)
    return {"ok": True, "count": len(runs), "runs": runs}


@app.get("/api/v1/runs/{run_id}")
def get_run(run_id: str) -> Dict[str, Any]:
    record = _get_run_or_404(run_id)
    return {"ok": True, "run": record.model_dump()}


@app.get("/api/v1/runs/{run_id}/logs")
def get_run_logs(run_id: str) -> Dict[str, Any]:
    record = _get_run_or_404(run_id)
    return {
        "ok": True,
        "run_id": run_id,
        "status": record.status,
        "stdout": record.stdout,
        "stderr": record.stderr,
    }

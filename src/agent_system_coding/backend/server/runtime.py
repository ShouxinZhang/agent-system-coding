from __future__ import annotations

import json
import subprocess
import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO
from uuid import uuid4

from ..demo_repo import PARALLEL_CALCULUS_PROMPT, init_parallel_calculus_demo_repo
from ..snapshot import load_runtime_snapshot


@dataclass(frozen=True, slots=True)
class MonitorAppState:
    project_root: Path
    runtime_root: Path
    reasoning_effort: str
    sandbox: str
    initial_run_id: str | None = None


def create_run(app_state: MonitorAppState, prompt: str) -> dict[str, object]:
    normalized_prompt = prompt.strip() or PARALLEL_CALCULUS_PROMPT

    run_id = _new_run_id()
    runtime_dir = app_state.runtime_root / run_id
    demo_repo = runtime_dir / "demo-repo"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    init_parallel_calculus_demo_repo(demo_repo)

    meta = {
        "run_id": run_id,
        "prompt": normalized_prompt,
        "status": "starting",
        "created_at": _utc_now_iso(),
        "runtime_dir": str(runtime_dir),
    }
    _write_json(runtime_dir / "run.json", meta)

    log_path = runtime_dir / "process.log"
    log_handle = log_path.open("w", encoding="utf-8")
    command = [
        sys.executable,
        "-m",
        "agent_system_coding.cli",
        "--request",
        normalized_prompt,
        "--repo",
        str(demo_repo),
        "--runtime-dir",
        str(runtime_dir),
        "--schemas-dir",
        str(app_state.project_root / "schemas"),
        "--sandbox",
        app_state.sandbox,
        "--reasoning-effort",
        app_state.reasoning_effort,
    ]
    process = subprocess.Popen(
        command,
        cwd=app_state.project_root,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )

    meta["status"] = "running"
    meta["pid"] = process.pid
    _write_json(runtime_dir / "run.json", meta)

    thread = threading.Thread(
        target=_wait_for_process,
        args=(process, log_handle, runtime_dir),
        daemon=True,
    )
    thread.start()
    return {"ok": True, "run_id": run_id, "runtime_dir": str(runtime_dir)}


def load_snapshot(runtime_root: Path | str, run_id: str) -> dict[str, object] | None:
    runtime_dir = Path(runtime_root) / run_id
    if not runtime_dir.exists():
        return None

    snapshot = load_runtime_snapshot(runtime_dir) or _empty_snapshot(runtime_dir)
    run_meta_path = runtime_dir / "run.json"
    process_log_path = runtime_dir / "process.log"
    if run_meta_path.exists():
        snapshot["run"] = json.loads(run_meta_path.read_text(encoding="utf-8"))
    else:
        summary = snapshot.get("summary") or {}
        snapshot["run"] = {
            "run_id": run_id,
            "status": summary.get("final_status", "unknown"),
            "runtime_dir": str(runtime_dir),
        }
    snapshot["process_log_path"] = str(process_log_path)
    return snapshot


def list_runs(runtime_root: Path | str) -> list[dict[str, object]]:
    root = Path(runtime_root)
    runs: list[dict[str, object]] = []
    for run_dir in sorted(root.iterdir(), reverse=True):
        if not run_dir.is_dir():
            continue
        meta_path = run_dir / "run.json"
        summary_path = run_dir / "summary.json"
        events_path = run_dir / "traces" / "events.jsonl"
        if not meta_path.exists() and not summary_path.exists() and not events_path.exists():
            continue
        meta: dict[str, object] = {"run_id": run_dir.name, "status": "unknown", "runtime_dir": str(run_dir)}
        if meta_path.exists():
            meta.update(json.loads(meta_path.read_text(encoding="utf-8")))
        elif summary_path.exists():
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            meta["status"] = summary.get("final_status", "unknown")
        runs.append(meta)
    return runs


def read_artifact(runtime_root: Path | str, run_id: str, requested_path: str) -> dict[str, str]:
    runtime_dir = (Path(runtime_root) / run_id).resolve()
    artifact_path = Path(requested_path)
    if not artifact_path.is_absolute():
        artifact_path = runtime_dir / artifact_path
    artifact_path = artifact_path.resolve()
    allowed_roots = [runtime_dir, (runtime_dir / "demo-repo").resolve()]
    if not any(artifact_path.is_relative_to(root) for root in allowed_roots):
        raise PermissionError("Artifact path is outside runtime")
    if not artifact_path.exists() or artifact_path.is_dir():
        raise FileNotFoundError("Artifact not found")
    return {
        "path": str(artifact_path),
        "content": artifact_path.read_text(encoding="utf-8", errors="replace"),
    }


def read_run_log(runtime_root: Path | str, run_id: str) -> str:
    log_path = Path(runtime_root) / run_id / "process.log"
    if not log_path.exists():
        raise FileNotFoundError("Run log not found")
    return log_path.read_text(encoding="utf-8")


def _wait_for_process(process: subprocess.Popen[str], log_handle: TextIO, runtime_dir: Path) -> None:
    return_code = process.wait()
    log_handle.close()
    run_meta_path = runtime_dir / "run.json"
    meta = json.loads(run_meta_path.read_text(encoding="utf-8"))
    meta["finished_at"] = _utc_now_iso()
    meta["return_code"] = return_code
    summary_path = runtime_dir / "summary.json"
    if return_code == 0 and summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        meta["status"] = summary.get("final_status", "done")
    else:
        meta["status"] = "failed"
    _write_json(run_meta_path, meta)


def _empty_snapshot(runtime_dir: Path) -> dict[str, object]:
    return {
        "runtime_dir": str(runtime_dir),
        "events": [],
        "latest": {},
        "latest_state": {},
        "tasks": [],
        "batches": [],
        "node_statuses": {},
        "artifacts": [],
        "graph_text": "",
        "summary": None,
    }


def _new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%S-") + uuid4().hex[:6]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

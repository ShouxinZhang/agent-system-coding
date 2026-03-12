from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .visualization import write_latest_status


def trace_node(node_name: str):
    def decorator(func):
        def wrapper(state: dict[str, Any]) -> dict[str, Any]:
            runtime_dir = Path(state["runtime_dir"])
            trace_id = f"{_utc_now_compact()}-{node_name}-{uuid4().hex[:8]}"

            _write_trace_event(
                runtime_dir=runtime_dir,
                trace_id=trace_id,
                node_name=node_name,
                phase="start",
                state=state,
            )

            try:
                result = func(state)
            except Exception as exc:
                _write_trace_event(
                    runtime_dir=runtime_dir,
                    trace_id=trace_id,
                    node_name=node_name,
                    phase="error",
                    state=state,
                    payload={
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    },
                )
                raise

            trace_payload = result.pop("__trace__", None) if isinstance(result, dict) else None
            merged_state = dict(state)
            if isinstance(result, dict):
                merged_state.update(result)

            _write_trace_event(
                runtime_dir=runtime_dir,
                trace_id=trace_id,
                node_name=node_name,
                phase="end",
                state=merged_state,
                payload=trace_payload,
            )
            return result

        return wrapper

    return decorator


def _write_trace_event(
    *,
    runtime_dir: Path,
    trace_id: str,
    node_name: str,
    phase: str,
    state: dict[str, Any],
    payload: dict[str, Any] | None = None,
) -> None:
    traces_dir = runtime_dir / "traces"
    traces_dir.mkdir(parents=True, exist_ok=True)

    event = {
        "trace_id": trace_id,
        "timestamp": _utc_now_iso(),
        "node": node_name,
        "phase": phase,
        "state": _summarize_state(state),
    }
    if payload:
        event["payload"] = payload

    event_path = traces_dir / f"{trace_id}.{phase}.json"
    event_path.write_text(
        json.dumps(event, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    events_path = traces_dir / "events.jsonl"
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    write_latest_status(runtime_dir, event)


def _summarize_state(state: dict[str, Any]) -> dict[str, Any]:
    plan = state.get("plan") or {}
    tasks = plan.get("tasks", [])
    return {
        "user_request": state.get("user_request"),
        "current_task_id": state.get("current_task_id"),
        "final_status": state.get("final_status"),
        "tasks": [
            {
                "task_id": task.get("task_id"),
                "status": task.get("status"),
                "retries": task.get("retries", 0),
            }
            for task in tasks
        ],
    }


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc_now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")

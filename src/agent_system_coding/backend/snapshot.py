"""Snapshot — 从磁盘读取 events / transcripts / artifacts，聚合为统一数据快照。"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def load_runtime_snapshot(runtime_dir: Path) -> dict[str, Any] | None:
    events_path = runtime_dir / "traces" / "events.jsonl"
    if not events_path.exists():
        return None

    events = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))

    latest = events[-1] if events else {}
    latest_state = latest.get("state", {})
    graph_text = ""
    graph_path = runtime_dir / "graph.mmd"
    if graph_path.exists():
        graph_text = graph_path.read_text(encoding="utf-8")

    summary = None
    summary_path = runtime_dir / "summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))

    return {
        "runtime_dir": str(runtime_dir),
        "events": events,
        "latest": latest,
        "latest_state": latest_state,
        "tasks": latest_state.get("tasks", []),
        "batches": collect_batches(events),
        "node_statuses": collect_node_statuses(events),
        "node_details": collect_node_details(events),
        "artifacts": collect_artifacts(events),
        "conversations": collect_conversations(runtime_dir),
        "latest_conversation_id": pick_latest_conversation_id(runtime_dir, latest),
        "graph_text": graph_text,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Collectors
# ---------------------------------------------------------------------------


def collect_node_statuses(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    trace_completion: dict[str, str] = {}
    node_statuses: dict[str, dict[str, Any]] = {}

    for event in events:
        trace_id = event["trace_id"]
        node = event["node"]
        phase = event["phase"]
        node_entry = node_statuses.setdefault(
            node,
            {"status": "idle", "latest_timestamp": None, "open_traces": set()},
        )
        node_entry["latest_timestamp"] = event["timestamp"]
        if phase == "start":
            node_entry["open_traces"].add(trace_id)
        else:
            node_entry["open_traces"].discard(trace_id)
            trace_completion[trace_id] = phase
            if phase == "error":
                node_entry["status"] = "error"
            elif phase == "end" and node_entry["status"] != "error":
                node_entry["status"] = "success"

    for node, entry in node_statuses.items():
        if entry["open_traces"]:
            entry["status"] = "running"
        entry["open_traces"] = sorted(entry["open_traces"])

    return node_statuses


def collect_artifacts(events: list[dict[str, Any]]) -> list[str]:
    artifacts: list[str] = []
    for event in events:
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        if isinstance(payload.get("artifacts"), list):
            artifacts.extend(str(item) for item in payload["artifacts"])
    return sorted(set(artifacts))


def collect_node_details(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    details: dict[str, dict[str, Any]] = {}

    for event in events:
        node = event["node"]
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        state = event.get("state") if isinstance(event.get("state"), dict) else {}
        task_id = payload.get("task_id") or state.get("current_task_id")
        batch_id = payload.get("batch_id") or state.get("active_batch_id")

        entry = details.setdefault(
            node,
            {
                "node": node,
                "status": "idle",
                "latest_phase": None,
                "latest_timestamp": None,
                "open_traces": set(),
                "run_count": 0,
                "error_count": 0,
                "tasks": set(),
                "batches": set(),
                "recent_events": [],
            },
        )
        entry["latest_phase"] = event["phase"]
        entry["latest_timestamp"] = event["timestamp"]
        if event["phase"] == "start":
            entry["run_count"] += 1
            entry["open_traces"].add(event["trace_id"])
        else:
            entry["open_traces"].discard(event["trace_id"])
            if event["phase"] == "error":
                entry["error_count"] += 1
        if task_id:
            entry["tasks"].add(str(task_id))
        if batch_id:
            entry["batches"].add(str(batch_id))
        entry["recent_events"].append(
            {
                "timestamp": event["timestamp"],
                "phase": event["phase"],
                "task_id": task_id,
                "batch_id": batch_id,
                "trace_id": event["trace_id"],
            }
        )

    for entry in details.values():
        if entry["open_traces"]:
            entry["status"] = "running"
        elif entry["error_count"] > 0:
            entry["status"] = "error"
        elif entry["run_count"] > 0:
            entry["status"] = "success"
        entry["open_traces"] = sorted(entry["open_traces"])
        entry["tasks"] = sorted(entry["tasks"])
        entry["batches"] = sorted(entry["batches"])
        entry["recent_events"] = entry["recent_events"][-8:]

    return details


def collect_conversations(runtime_dir: Path) -> list[dict[str, Any]]:
    conversations: list[dict[str, Any]] = []

    run_meta_path = runtime_dir / "run.json"
    if run_meta_path.exists():
        run_meta = json.loads(run_meta_path.read_text(encoding="utf-8"))
        prompt = (run_meta.get("prompt") or "").strip()
        if prompt:
            conversations.append(
                {
                    "id": "user-request",
                    "title": "User Request",
                    "agent": "user",
                    "node": "request",
                    "task_id": None,
                    "status": run_meta.get("status", "submitted"),
                    "messages": [
                        {
                            "role": "user",
                            "label": "Prompt",
                            "content": prompt,
                        }
                    ],
                }
            )

    transcript_paths: list[Path] = []
    plan_transcript = runtime_dir / "agents" / "plan.codex.json"
    if plan_transcript.exists():
        transcript_paths.append(plan_transcript)
    transcript_paths.extend(sorted((runtime_dir / "tasks").glob("*.execute.codex.json")))
    transcript_paths.extend(sorted((runtime_dir / "tasks").glob("*.review.codex.json")))

    for path in transcript_paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        conversations.append(_transcript_to_conversation(path, data))

    if not transcript_paths:
        conversations.extend(_collect_fallback_conversations(runtime_dir))

    return conversations


def pick_latest_conversation_id(runtime_dir: Path, latest: dict[str, Any]) -> str | None:
    node = latest.get("node")
    payload = latest.get("payload") if isinstance(latest.get("payload"), dict) else {}
    state = latest.get("state") if isinstance(latest.get("state"), dict) else {}
    task_id = payload.get("task_id") or state.get("current_task_id")

    if node == "plan" and (runtime_dir / "agents" / "plan.codex.json").exists():
        return "plan.codex"

    if task_id and node in {"execute_task", "review_task"}:
        suffix = "execute" if node == "execute_task" else "review"
        path = runtime_dir / "tasks" / f"{task_id}.{suffix}.codex.json"
        if path.exists():
            return path.stem

    return "user-request"


def collect_batches(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    batches: dict[str, dict[str, Any]] = {}
    for event in events:
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        batch_id = payload.get("batch_id")
        if not batch_id:
            continue
        entry = batches.setdefault(batch_id, {"batch_id": batch_id, "task_ids": set(), "nodes": []})
        if "task_id" in payload:
            entry["task_ids"].add(payload["task_id"])
        for key in ["task_ids", "selected_task_ids", "updated_task_ids"]:
            if key in payload and isinstance(payload[key], list):
                entry["task_ids"].update(payload[key])
        entry["nodes"].append(f"{event['node']}:{event['phase']}")

    result = []
    for batch in batches.values():
        result.append(
            {
                "batch_id": batch["batch_id"],
                "task_ids": sorted(batch["task_ids"]),
                "nodes": batch["nodes"],
            }
        )
    result.sort(key=lambda item: item["batch_id"])
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _collect_fallback_conversations(runtime_dir: Path) -> list[dict[str, Any]]:
    conversations: list[dict[str, Any]] = []

    plan_path = runtime_dir / "plan.json"
    if plan_path.exists():
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        conversations.append(
            {
                "id": "plan-fallback",
                "title": "Root Planner",
                "agent": "planner",
                "node": "plan",
                "task_id": None,
                "status": "completed",
                "messages": [
                    {
                        "role": "assistant",
                        "label": "Plan Output",
                        "content": json.dumps(plan, ensure_ascii=False, indent=2),
                    }
                ],
            }
        )

    for dispatch_path in sorted((runtime_dir / "tasks").glob("*.dispatch.json")):
        task_id = dispatch_path.stem.split(".", 1)[0]
        result_path = runtime_dir / "tasks" / f"{task_id}.result.json"
        review_path = runtime_dir / "tasks" / f"{task_id}.review.json"
        dispatch = json.loads(dispatch_path.read_text(encoding="utf-8"))
        if result_path.exists():
            result = json.loads(result_path.read_text(encoding="utf-8"))
            conversations.append(
                {
                    "id": f"{task_id}-execute-fallback",
                    "title": f"Executor {task_id}",
                    "agent": "executor",
                    "node": "execute_task",
                    "task_id": task_id,
                    "status": "completed",
                    "messages": [
                        {
                            "role": "user",
                            "label": "Task",
                            "content": json.dumps(dispatch, ensure_ascii=False, indent=2),
                        },
                        {
                            "role": "assistant",
                            "label": "Execution Result",
                            "content": json.dumps(result, ensure_ascii=False, indent=2),
                        },
                    ],
                }
            )
        if review_path.exists():
            review = json.loads(review_path.read_text(encoding="utf-8"))
            conversations.append(
                {
                    "id": f"{task_id}-review-fallback",
                    "title": f"Reviewer {task_id}",
                    "agent": "reviewer",
                    "node": "review_task",
                    "task_id": task_id,
                    "status": "completed",
                    "messages": [
                        {
                            "role": "user",
                            "label": "Task",
                            "content": json.dumps(dispatch, ensure_ascii=False, indent=2),
                        },
                        {
                            "role": "assistant",
                            "label": "Review Result",
                            "content": json.dumps(review, ensure_ascii=False, indent=2),
                        },
                    ],
                }
            )

    return conversations


def _transcript_to_conversation(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    result = data.get("result")
    messages = []
    prompt = (data.get("prompt") or "").strip()
    if prompt:
        messages.append(
            {
                "role": "user",
                "label": "Prompt",
                "content": prompt,
            }
        )
    if result is not None:
        messages.append(
            {
                "role": "assistant",
                "label": "Result",
                "content": json.dumps(result, ensure_ascii=False, indent=2),
            }
        )
    stderr_text = (data.get("stderr") or "").strip()

    return {
        "id": path.stem,
        "title": data.get("title") or path.stem,
        "agent": data.get("agent") or "agent",
        "node": data.get("node") or "unknown",
        "task_id": data.get("task_id"),
        "status": data.get("status", "completed"),
        "path": str(path),
        "diagnostics": stderr_text or None,
        "messages": messages,
    }

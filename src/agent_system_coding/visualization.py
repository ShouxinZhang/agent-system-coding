from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_graph_mermaid(runtime_dir: Path, mermaid_text: str) -> Path:
    runtime_dir.mkdir(parents=True, exist_ok=True)
    output_path = runtime_dir / "graph.mmd"
    output_path.write_text(mermaid_text + "\n", encoding="utf-8")
    return output_path


def write_latest_status(runtime_dir: Path, event: dict[str, Any]) -> Path:
    output_path = runtime_dir / "traces" / "latest-status.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(event, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def write_trace_report(runtime_dir: Path) -> Path | None:
    events_path = runtime_dir / "traces" / "events.jsonl"
    if not events_path.exists():
        return None

    events = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))

    latest = events[-1] if events else {}
    latest_state = latest.get("state", {})
    report_lines = [
        "# Runtime Trace Report",
        "",
        f"- Runtime dir: `{runtime_dir}`",
        f"- Event count: `{len(events)}`",
        f"- Latest node: `{latest.get('node')}`",
        f"- Latest phase: `{latest.get('phase')}`",
        f"- Latest timestamp: `{latest.get('timestamp')}`",
        f"- Final status: `{latest_state.get('final_status')}`",
        "",
        "## Tasks",
        "",
    ]

    tasks = latest_state.get("tasks", [])
    if tasks:
        for task in tasks:
            report_lines.append(
                f"- `{task.get('task_id')}`: status=`{task.get('status')}`, retries=`{task.get('retries', 0)}`"
            )
    else:
        report_lines.append("- No tasks recorded")

    report_lines.extend(["", "## Timeline", ""])
    for event in events:
        report_lines.append(
            f"- `{event['timestamp']}` `{event['node']}` `{event['phase']}`{_payload_suffix(event.get('payload'))}"
        )

    output_path = runtime_dir / "trace-report.md"
    output_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return output_path


def _payload_suffix(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""

    keys = [
        "batch_id",
        "task_id",
        "task_ids",
        "selected_task_ids",
        "updated_task_ids",
        "final_status",
    ]
    parts = [f"{key}={payload[key]!r}" for key in keys if key in payload]
    return f" payload: {', '.join(parts)}" if parts else ""

"""Writers — 将数据写入磁盘文件（Mermaid、JSON、Markdown、HTML）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .snapshot import load_runtime_snapshot


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


def write_trace_viewer_html(runtime_dir: Path) -> Path | None:
    snapshot = load_runtime_snapshot(runtime_dir)
    if snapshot is None:
        return None

    output_path = runtime_dir / "trace-viewer.html"
    output_path.write_text(render_trace_viewer_html(snapshot, live=False), encoding="utf-8")
    return output_path


def render_trace_viewer_html(snapshot: dict[str, Any], *, live: bool) -> str:
    """Render a self-contained trace-viewer HTML page.

    Loads the frontend template and injects snapshot data + CSS/JS inline.
    """
    from ..frontend import load_trace_viewer_css, load_trace_viewer_js, load_trace_viewer_template

    runtime_dir = snapshot["runtime_dir"]
    events = snapshot["events"]
    latest = snapshot["latest"]
    latest_state = snapshot["latest_state"]
    tasks = snapshot["tasks"]
    batches = snapshot["batches"]
    mermaid_text = snapshot["graph_text"]

    timeline_rows = "\n".join(_render_timeline_row(event) for event in events)
    task_cards = "\n".join(_render_task_card(task) for task in tasks) or "<p>No tasks recorded.</p>"
    batch_cards = "\n".join(_render_batch_card(batch) for batch in batches) or "<p>No batches recorded.</p>"

    live_badge = '<div class="chip live">Live Polling</div>' if live else '<div class="chip">Static Export</div>'
    live_script = _live_script() if live else ""

    css_text = load_trace_viewer_css()
    js_text = load_trace_viewer_js()

    template = load_trace_viewer_template()
    return (
        template
        .replace("<!-- __CSS__ -->", f"<style>\n{css_text}\n</style>")
        .replace("<!-- __LIVE_BADGE__ -->", live_badge)
        .replace("<!-- __EVENT_COUNT__ -->", str(len(events)))
        .replace("<!-- __LATEST_NODE__ -->", str(latest.get("node")))
        .replace("<!-- __LATEST_PHASE__ -->", str(latest.get("phase")))
        .replace("<!-- __FINAL_STATUS__ -->", str(latest_state.get("final_status")))
        .replace("<!-- __RUNTIME_DIR__ -->", str(runtime_dir))
        .replace("<!-- __TASK_CARDS__ -->", task_cards)
        .replace("<!-- __BATCH_CARDS__ -->", batch_cards)
        .replace("<!-- __TIMELINE_ROWS__ -->", timeline_rows)
        .replace("<!-- __GRAPH_TEXT__ -->", _escape_html(mermaid_text))
        .replace("<!-- __LIVE_SCRIPT__ -->", live_script)
        .replace("<!-- __APP_JS__ -->", f"<script>\n{js_text}\n</script>")
    )


# ---------------------------------------------------------------------------
# Internal HTML helpers
# ---------------------------------------------------------------------------


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


def _render_task_card(task: dict[str, Any]) -> str:
    status = task.get("status")
    return (
        '<div class="task-card">'
        f"<h3>{_escape_html(str(task.get('task_id')))}</h3>"
        f'<p><span class="status {status}">{_escape_html(str(status))}</span> | retries={task.get("retries", 0)}</p>'
        "</div>"
    )


def _render_batch_card(batch: dict[str, Any]) -> str:
    task_chips = "".join(f'<span class="chip">{_escape_html(task_id)}</span>' for task_id in batch["task_ids"])
    node_lines = "<br>".join(_escape_html(node) for node in batch["nodes"])
    return (
        '<div class="batch-card">'
        f"<h3>{_escape_html(batch['batch_id'])}</h3>"
        f"<div>{task_chips}</div>"
        f"<p>{node_lines}</p>"
        "</div>"
    )


def _render_timeline_row(event: dict[str, Any]) -> str:
    payload = event.get("payload")
    payload_text = _escape_html(json.dumps(payload, ensure_ascii=False)) if payload else ""
    return (
        "<tr>"
        f"<td>{_escape_html(event['timestamp'])}</td>"
        f"<td>{_escape_html(event['node'])}</td>"
        f"<td>{_escape_html(event['phase'])}</td>"
        f"<td>{payload_text}</td>"
        "</tr>"
    )


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _live_script() -> str:
    return """<script>
const escapeHtml = (text) => String(text ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;");

function renderTaskCard(task) {
  return `<div class="task-card">
    <h3>${escapeHtml(task.task_id)}</h3>
    <p><span class="status ${escapeHtml(task.status)}">${escapeHtml(task.status)}</span> | retries=${task.retries ?? 0}</p>
  </div>`;
}

function renderBatchCard(batch) {
  const chips = (batch.task_ids || []).map((taskId) => `<span class="chip">${escapeHtml(taskId)}</span>`).join("");
  const nodes = (batch.nodes || []).map((node) => escapeHtml(node)).join("<br>");
  return `<div class="batch-card"><h3>${escapeHtml(batch.batch_id)}</h3><div>${chips}</div><p>${nodes}</p></div>`;
}

function renderTimelineRow(event) {
  const payload = event.payload ? escapeHtml(JSON.stringify(event.payload)) : "";
  return `<tr>
    <td>${escapeHtml(event.timestamp)}</td>
    <td>${escapeHtml(event.node)}</td>
    <td>${escapeHtml(event.phase)}</td>
    <td>${payload}</td>
  </tr>`;
}

async function refreshSnapshot() {
  const response = await fetch("/api/runtime", { cache: "no-store" });
  if (!response.ok) return;
  const snapshot = await response.json();

  document.getElementById("event-count").textContent = snapshot.events.length;
  document.getElementById("latest-node").textContent = snapshot.latest?.node ?? "";
  document.getElementById("latest-phase").textContent = snapshot.latest?.phase ?? "";
  document.getElementById("final-status").textContent = snapshot.latest_state?.final_status ?? "";
  document.getElementById("tasks-content").innerHTML = (snapshot.tasks || []).map(renderTaskCard).join("") || "<p>No tasks recorded.</p>";
  document.getElementById("batches-content").innerHTML = (snapshot.batches || []).map(renderBatchCard).join("") || "<p>No batches recorded.</p>";
  document.getElementById("timeline-body").innerHTML = (snapshot.events || []).map(renderTimelineRow).join("");
  document.getElementById("graph-text").textContent = snapshot.graph_text || "";
}

setInterval(refreshSnapshot, 1000);
</script>"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from agent_system_coding.demo_repo import (
    PARALLEL_CALCULUS_PROMPT,
    init_parallel_calculus_demo_repo,
)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    runtime_dir = repo_root / "runtime" / "calculus-smoke"
    demo_repo = runtime_dir / "demo-repo"
    derivative_path = demo_repo / "docs" / "derivative-answer.md"
    integral_path = demo_repo / "docs" / "integral-answer.md"
    summary_path = demo_repo / "docs" / "final-summary.md"
    cli_path = repo_root / ".venv" / "bin" / "agent-system-coding"

    if not cli_path.exists():
        raise SystemExit(f"Missing CLI entrypoint: {cli_path}")

    if runtime_dir.exists():
        shutil.rmtree(runtime_dir)
    init_parallel_calculus_demo_repo(demo_repo)

    request = PARALLEL_CALCULUS_PROMPT

    command = [
        str(cli_path),
        "--request",
        request,
        "--repo",
        str(demo_repo),
        "--runtime-dir",
        str(runtime_dir),
        "--schemas-dir",
        str(repo_root / "schemas"),
        "--sandbox",
        "workspace-write",
    ]

    subprocess.run(command, cwd=repo_root, check=True)

    summary = json.loads((runtime_dir / "summary.json").read_text(encoding="utf-8"))
    if summary["final_status"] != "done":
        raise SystemExit(f"Workflow did not finish successfully: {summary}")

    for path in [derivative_path, integral_path, summary_path]:
        if not path.exists():
            raise SystemExit(f"Missing expected file: {path}")

    derivative_text = derivative_path.read_text(encoding="utf-8")
    integral_text = integral_path.read_text(encoding="utf-8")
    summary_text = summary_path.read_text(encoding="utf-8")
    if "12" not in derivative_text:
        raise SystemExit("Derivative answer does not contain the expected result 12")
    if "2" not in integral_text:
        raise SystemExit("Integral answer does not contain the expected result 2")
    if "12" not in summary_text or "2" not in summary_text:
        raise SystemExit("Final summary does not mention both 12 and 2")

    events_path = runtime_dir / "traces" / "events.jsonl"
    if not events_path.exists():
        raise SystemExit(f"Missing trace events file: {events_path}")

    nodes_seen = set()
    parallel_batch_found = False
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if event["phase"] == "end":
            nodes_seen.add(event["node"])
            if event["node"] == "dispatch":
                payload = event.get("payload", {})
                if len(payload.get("selected_task_ids", [])) >= 2:
                    parallel_batch_found = True

    expected_nodes = {
        "plan",
        "dispatch",
        "execute_task",
        "dispatch_reviews",
        "review_task",
        "update",
        "finalize",
    }
    missing = sorted(expected_nodes - nodes_seen)
    if missing:
        raise SystemExit(f"Missing completed node traces: {missing}")
    if not parallel_batch_found:
        raise SystemExit("No dispatch batch selected multiple parallel tasks")

    print("Smoke test passed")
    print(f"Derivative file: {derivative_path}")
    print(f"Integral file: {integral_path}")
    print(f"Summary file: {summary_path}")
    print(f"Runtime dir: {runtime_dir}")
    print(f"Trace log: {events_path}")
    print(f"Trace viewer: {runtime_dir / 'trace-viewer.html'}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


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
    _init_demo_repo(demo_repo)

    request = (
        "请严格规划并完成 3 个任务。"
        "任务1：在 docs/derivative-answer.md 中用中文解答微积分题，求 f(x)=x^3 在 x=2 处的导数，必须明确写出答案 12。"
        "任务2：在 docs/integral-answer.md 中用中文解答微积分题，求定积分 ∫[0,2] x dx，必须明确写出答案 2。"
        "任务3：在 docs/final-summary.md 中用中文汇总前两题结论，必须同时提到 12 和 2。"
        "其中任务1和任务2互不依赖，必须并行；任务3 依赖任务1和任务2。"
        "除这 3 个文档和必要运行产物外，不要修改其他业务文件。"
    )

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


def _init_demo_repo(demo_repo: Path) -> None:
    (demo_repo / "docs").mkdir(parents=True, exist_ok=True)
    (demo_repo / "README.md").write_text("# calculus smoke demo\n", encoding="utf-8")
    (demo_repo / "docs" / "derivative-answer.md").write_text(
        "待填写\n",
        encoding="utf-8",
    )
    (demo_repo / "docs" / "integral-answer.md").write_text(
        "待填写\n",
        encoding="utf-8",
    )
    (demo_repo / "docs" / "final-summary.md").write_text(
        "待填写\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init"], cwd=demo_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "workflow-trace-smoke"],
        cwd=demo_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "workflow-trace-smoke@example.com"],
        cwd=demo_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "add", "."], cwd=demo_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init demo repo"],
        cwd=demo_repo,
        check=True,
        capture_output=True,
    )


if __name__ == "__main__":
    main()

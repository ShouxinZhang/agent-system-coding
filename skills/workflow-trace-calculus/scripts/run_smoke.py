from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    runtime_dir = repo_root / "runtime" / "calculus-smoke"
    demo_repo = runtime_dir / "demo-repo"
    answer_path = demo_repo / "docs" / "calculus-smoke-answer.md"
    cli_path = repo_root / ".venv" / "bin" / "agent-system-coding"

    if not cli_path.exists():
        raise SystemExit(f"Missing CLI entrypoint: {cli_path}")

    if runtime_dir.exists():
        shutil.rmtree(runtime_dir)
    _init_demo_repo(demo_repo)

    request = (
        "请在 docs/calculus-smoke-answer.md 中用中文解答一道简单微积分题："
        "求函数 f(x)=x^2 在 x=3 处的导数。"
        "必须明确写出答案 6。"
        "除了解答文件和必要运行产物，不要修改其他业务文件。"
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

    if not answer_path.exists():
        raise SystemExit(f"Missing answer file: {answer_path}")

    answer_text = answer_path.read_text(encoding="utf-8")
    if "6" not in answer_text:
        raise SystemExit("Answer file does not contain the expected derivative result 6")

    events_path = runtime_dir / "traces" / "events.jsonl"
    if not events_path.exists():
        raise SystemExit(f"Missing trace events file: {events_path}")

    nodes_seen = set()
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if event["phase"] == "end":
            nodes_seen.add(event["node"])

    expected_nodes = {"plan", "dispatch", "execute", "review", "update", "finalize"}
    missing = sorted(expected_nodes - nodes_seen)
    if missing:
        raise SystemExit(f"Missing completed node traces: {missing}")

    print("Smoke test passed")
    print(f"Answer file: {answer_path}")
    print(f"Runtime dir: {runtime_dir}")
    print(f"Trace log: {events_path}")


def _init_demo_repo(demo_repo: Path) -> None:
    (demo_repo / "docs").mkdir(parents=True, exist_ok=True)
    (demo_repo / "README.md").write_text("# calculus smoke demo\n", encoding="utf-8")
    (demo_repo / "docs" / "calculus-smoke-answer.md").write_text(
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

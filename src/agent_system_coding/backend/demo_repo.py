from __future__ import annotations

import subprocess
from pathlib import Path


PARALLEL_CALCULUS_PROMPT = (
    "请严格规划并完成 3 个任务。"
    "任务1：在 docs/derivative-answer.md 中用中文解答微积分题，求 f(x)=x^3 在 x=2 处的导数，必须明确写出答案 12。"
    "任务2：在 docs/integral-answer.md 中用中文解答微积分题，求定积分 ∫[0,2] x dx，必须明确写出答案 2。"
    "任务3：在 docs/final-summary.md 中用中文汇总前两题结论，必须同时提到 12 和 2。"
    "其中任务1和任务2互不依赖，必须并行；任务3 依赖任务1和任务2。"
    "除这 3 个文档和必要运行产物外，不要修改其他业务文件。"
)


def init_parallel_calculus_demo_repo(demo_repo: Path) -> None:
    (demo_repo / "docs").mkdir(parents=True, exist_ok=True)
    (demo_repo / "README.md").write_text("# calculus smoke demo\n", encoding="utf-8")
    (demo_repo / "docs" / "derivative-answer.md").write_text("待填写\n", encoding="utf-8")
    (demo_repo / "docs" / "integral-answer.md").write_text("待填写\n", encoding="utf-8")
    (demo_repo / "docs" / "final-summary.md").write_text("待填写\n", encoding="utf-8")
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

#!/usr/bin/env python3
"""Recommend which auto-work toolbox drawers to open for a task."""

from __future__ import annotations

import argparse


ROUTES = {
    "modular-arch": {
        "keywords": ("架构", "模块", "依赖", "接口", "边界", "architecture", "module", "interface"),
        "why": "适合处理模块边界、依赖方向和接口契约。",
    },
    "refactor-migration": {
        "keywords": ("重构", "迁移", "legacy", "旧系统", "切流", "refactor", "migration"),
        "why": "适合处理旧系统到新系统的承接、基线冻结和迁移进度。",
    },
    "python-quality-gate": {
        "keywords": ("质量", "lint", "pyright", "ruff", "校验", "检查", "质量门禁", "quality"),
        "why": "适合在 Python 改动后做统一静态检查。",
    },
    "session-log": {
        "keywords": ("日志", "记录", "复盘", "会话", "追溯", "log", "trace", "session"),
        "why": "适合记录任务上下文、摘要和相关文件。",
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Recommend auto-work toolbox routes")
    parser.add_argument("--task", required=True, help="Task summary in plain text")
    args = parser.parse_args()

    task = args.task.lower()
    matches: list[tuple[str, str]] = []
    for name, config in ROUTES.items():
        if any(keyword.lower() in task for keyword in config["keywords"]):
            matches.append((name, config["why"]))

    if not matches:
        print("Recommended route:")
        print("- auto-work-toolbox only")
        print("Why: 任务信息不足，先从工具箱入口人工分流。")
        return

    print("Recommended routes:")
    for name, why in matches:
        print(f"- {name}: {why}")


if __name__ == "__main__":
    main()

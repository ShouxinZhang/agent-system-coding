from __future__ import annotations

import argparse
import json
from pathlib import Path

from .backend.workflow import run_workflow


def main() -> None:
    parser = argparse.ArgumentParser(description="Minimal LangGraph + Codex CLI MVP")
    parser.add_argument("--request", required=True, help="User request for the graph coding system")
    parser.add_argument(
        "--repo",
        default=".",
        help="Repository path to operate on",
    )
    parser.add_argument(
        "--runtime-dir",
        default="runtime",
        help="Directory for generated plan and task artifacts",
    )
    parser.add_argument(
        "--schemas-dir",
        default="schemas",
        help="Directory containing Codex output schemas",
    )
    parser.add_argument(
        "--sandbox",
        default="workspace-write",
        choices=["read-only", "workspace-write", "danger-full-access"],
        help="Codex sandbox mode",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=2,
        help="Maximum review failures before a task becomes blocked",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Optional Codex model override",
    )
    parser.add_argument(
        "--reasoning-effort",
        default="high",
        choices=["low", "medium", "high", "xhigh"],
        help="Codex reasoning effort override; defaults to high for this project",
    )
    args = parser.parse_args()

    repo_path = Path(args.repo).resolve()
    runtime_dir = (repo_path / args.runtime_dir).resolve()
    schemas_dir = (repo_path / args.schemas_dir).resolve()
    runtime_dir.mkdir(parents=True, exist_ok=True)

    result = run_workflow(
        user_request=args.request,
        repo_path=repo_path,
        runtime_dir=runtime_dir,
        schemas_dir=schemas_dir,
        sandbox=args.sandbox,
        max_retries=args.max_retries,
        model=args.model,
        reasoning_effort=args.reasoning_effort,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

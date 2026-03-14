from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


class CodexCliError(RuntimeError):
    """Raised when Codex CLI returns a non-zero exit code."""


def run_codex_exec(
    *,
    repo_path: Path,
    prompt: str,
    output_schema_path: Path,
    output_path: Path,
    sandbox: str = "workspace-write",
    model: str | None = None,
    reasoning_effort: str = "high",
) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        "codex",
        "exec",
        "-C",
        str(repo_path),
        "--skip-git-repo-check",
        "--sandbox",
        sandbox,
        "-c",
        f'model_reasoning_effort="{reasoning_effort}"',
        "--output-schema",
        str(output_schema_path),
        "-o",
        str(output_path),
    ]

    if model:
        command.extend(["-m", model])

    command.append(prompt)

    completed = subprocess.run(
        command,
        cwd=repo_path,
        text=True,
        capture_output=True,
        check=False,
    )

    if completed.returncode != 0:
        raise CodexCliError(
            "Codex CLI failed.\n"
            f"Command: {' '.join(command)}\n"
            f"Exit code: {completed.returncode}\n"
            f"Stdout:\n{completed.stdout}\n"
            f"Stderr:\n{completed.stderr}"
        )

    return json.loads(output_path.read_text(encoding="utf-8"))

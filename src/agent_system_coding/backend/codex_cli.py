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
    transcript_path: Path | None = None,
    transcript_metadata: dict[str, Any] | None = None,
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

    transcript_payload = {
        "repo_path": str(repo_path),
        "output_schema_path": str(output_schema_path),
        "output_path": str(output_path),
        "sandbox": sandbox,
        "model": model,
        "reasoning_effort": reasoning_effort,
        "prompt": prompt,
    }
    if transcript_metadata:
        transcript_payload.update(transcript_metadata)

    if transcript_path is not None:
        _write_transcript(
            transcript_path,
            {
                **transcript_payload,
                "status": "running",
            },
        )

    completed = subprocess.run(
        command,
        cwd=repo_path,
        text=True,
        capture_output=True,
        check=False,
    )

    if completed.returncode != 0:
        if transcript_path is not None:
            _write_transcript(
                transcript_path,
                {
                    **transcript_payload,
                    "status": "error",
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                    "return_code": completed.returncode,
                },
            )
        raise CodexCliError(
            "Codex CLI failed.\n"
            f"Command: {' '.join(command)}\n"
            f"Exit code: {completed.returncode}\n"
            f"Stdout:\n{completed.stdout}\n"
            f"Stderr:\n{completed.stderr}"
        )

    result = json.loads(output_path.read_text(encoding="utf-8"))
    if transcript_path is not None:
        _write_transcript(
            transcript_path,
            {
                **transcript_payload,
                "status": "completed",
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "return_code": completed.returncode,
                "result": result,
            },
        )
    return result


def _write_transcript(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

from __future__ import annotations

import argparse
from pathlib import Path

from .backend.server.runtime import MonitorAppState
from .backend.server.http_handler import serve_dashboard


def main() -> None:
    args = _parse_args()
    app_state = _build_app_state(args)
    serve_dashboard(app_state, host=args.host, port=args.port)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive local dashboard for workflow runs")
    parser.add_argument("--runtime-root", default="runtime/live-runs", help="Directory that stores run directories")
    parser.add_argument("--runtime", default=None, help="Optional existing runtime dir to preselect")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8765, help="Bind port")
    parser.add_argument(
        "--reasoning-effort",
        default="high",
        choices=["low", "medium", "high", "xhigh"],
        help="Reasoning effort for new runs",
    )
    parser.add_argument(
        "--sandbox",
        default="workspace-write",
        choices=["read-only", "workspace-write", "danger-full-access"],
        help="Sandbox mode for new runs",
    )
    return parser.parse_args()


def _build_app_state(args: argparse.Namespace) -> MonitorAppState:
    project_root = Path(__file__).resolve().parents[2]
    runtime_root = Path(args.runtime_root).resolve()
    runtime_root.mkdir(parents=True, exist_ok=True)

    initial_run_id = None
    if args.runtime:
        runtime_dir = Path(args.runtime).resolve()
        runtime_root = runtime_dir.parent
        initial_run_id = runtime_dir.name

    return MonitorAppState(
        project_root=project_root,
        runtime_root=runtime_root,
        reasoning_effort=args.reasoning_effort,
        sandbox=args.sandbox,
        initial_run_id=initial_run_id,
    )


if __name__ == "__main__":
    main()

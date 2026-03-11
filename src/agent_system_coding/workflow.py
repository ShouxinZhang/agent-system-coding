from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from .codex_cli import run_codex_exec
from .prompts import build_execute_prompt, build_plan_prompt, build_review_prompt
from .tracing import trace_node


class WorkflowState(TypedDict, total=False):
    user_request: str
    repo_path: str
    runtime_dir: str
    schemas_dir: str
    model: str | None
    sandbox: str
    max_retries: int
    preexisting_paths: list[str]
    plan: dict[str, Any]
    current_task_id: str | None
    execution_result: dict[str, Any] | None
    review_result: dict[str, Any] | None
    observed_changed_files: list[str] | None
    finished: bool
    final_status: str


def run_workflow(
    *,
    user_request: str,
    repo_path: Path,
    runtime_dir: Path,
    schemas_dir: Path,
    sandbox: str,
    max_retries: int,
    model: str | None,
) -> WorkflowState:
    runtime_dir.mkdir(parents=True, exist_ok=True)
    preexisting_paths = _git_status_paths(repo_path)
    (runtime_dir / "baseline_repo_state.json").write_text(
        json.dumps({"dirty_paths": preexisting_paths}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    graph = StateGraph(WorkflowState)
    graph.add_node("plan", plan_node)
    graph.add_node("dispatch", dispatch_node)
    graph.add_node("execute", execute_node)
    graph.add_node("review", review_node)
    graph.add_node("update", update_plan_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "plan")
    graph.add_edge("plan", "dispatch")
    graph.add_conditional_edges(
        "dispatch",
        dispatch_router,
        {
            "execute": "execute",
            "finalize": "finalize",
        },
    )
    graph.add_edge("execute", "review")
    graph.add_edge("review", "update")
    graph.add_edge("update", "dispatch")
    graph.add_edge("finalize", END)

    app = graph.compile()
    return app.invoke(
        {
            "user_request": user_request,
            "repo_path": str(repo_path),
            "runtime_dir": str(runtime_dir),
            "schemas_dir": str(schemas_dir),
            "model": model,
            "sandbox": sandbox,
            "max_retries": max_retries,
            "preexisting_paths": preexisting_paths,
        }
    )


@trace_node("plan")
def plan_node(state: WorkflowState) -> WorkflowState:
    repo_path = Path(state["repo_path"])
    runtime_dir = Path(state["runtime_dir"])
    schemas_dir = Path(state["schemas_dir"])
    plan_path = runtime_dir / "plan.json"

    plan = run_codex_exec(
        repo_path=repo_path,
        prompt=build_plan_prompt(state["user_request"], state.get("preexisting_paths", [])),
        output_schema_path=schemas_dir / "plan.schema.json",
        output_path=plan_path,
        sandbox=state["sandbox"],
        model=state.get("model"),
    )

    for task in plan["tasks"]:
        task.setdefault("status", "pending")
        task.setdefault("retries", 0)

    plan_path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "plan": plan,
        "__trace__": {
            "artifacts": [
                str(plan_path),
                str(runtime_dir / "baseline_repo_state.json"),
            ],
            "task_count": len(plan["tasks"]),
        },
    }


@trace_node("dispatch")
def dispatch_node(state: WorkflowState) -> WorkflowState:
    plan = state["plan"]
    tasks = plan["tasks"]
    accepted_ids = {
        task["task_id"]
        for task in tasks
        if task["status"] == "accepted"
    }

    for task in tasks:
        if task["status"] not in {"pending", "ready"}:
            continue
        if all(dep in accepted_ids for dep in task.get("depends_on", [])):
            task["status"] = "ready"
            return {
                "plan": plan,
                "current_task_id": task["task_id"],
                "execution_result": None,
                "review_result": None,
                "observed_changed_files": None,
                "__trace__": {
                    "selected_task_id": task["task_id"],
                },
            }

    return {
        "plan": plan,
        "current_task_id": None,
        "observed_changed_files": None,
        "__trace__": {
            "selected_task_id": None,
        },
    }


def dispatch_router(state: WorkflowState) -> Literal["execute", "finalize"]:
    return "execute" if state.get("current_task_id") else "finalize"


@trace_node("execute")
def execute_node(state: WorkflowState) -> WorkflowState:
    repo_path = Path(state["repo_path"])
    runtime_dir = Path(state["runtime_dir"])
    schemas_dir = Path(state["schemas_dir"])
    task = _get_current_task(state)
    task["status"] = "running"

    dispatch_path = runtime_dir / "tasks" / f"{task['task_id']}.dispatch.json"
    dispatch_path.parent.mkdir(parents=True, exist_ok=True)
    dispatch_path.write_text(
        json.dumps(task, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    before_paths = set(_git_status_paths(repo_path))

    execution_result = run_codex_exec(
        repo_path=repo_path,
        prompt=build_execute_prompt(task, repo_path, state.get("preexisting_paths", [])),
        output_schema_path=schemas_dir / "execution.schema.json",
        output_path=runtime_dir / "tasks" / f"{task['task_id']}.result.json",
        sandbox=state["sandbox"],
        model=state.get("model"),
    )
    after_paths = set(_git_status_paths(repo_path))
    observed_changed_files = sorted(after_paths - before_paths)
    return {
        "plan": state["plan"],
        "execution_result": execution_result,
        "observed_changed_files": observed_changed_files,
        "__trace__": {
            "artifacts": [
                str(dispatch_path),
                str(runtime_dir / "tasks" / f"{task['task_id']}.result.json"),
            ],
            "task_id": task["task_id"],
            "observed_changed_files": observed_changed_files,
        },
    }


@trace_node("review")
def review_node(state: WorkflowState) -> WorkflowState:
    repo_path = Path(state["repo_path"])
    runtime_dir = Path(state["runtime_dir"])
    schemas_dir = Path(state["schemas_dir"])
    task = _get_current_task(state)
    execution_result = state["execution_result"]

    review_result = run_codex_exec(
        repo_path=repo_path,
        prompt=build_review_prompt(
            task,
            execution_result,
            repo_path,
            state.get("preexisting_paths", []),
            state.get("observed_changed_files") or [],
        ),
        output_schema_path=schemas_dir / "review.schema.json",
        output_path=runtime_dir / "tasks" / f"{task['task_id']}.review.json",
        sandbox=state["sandbox"],
        model=state.get("model"),
    )
    return {
        "plan": state["plan"],
        "review_result": review_result,
        "__trace__": {
            "artifacts": [
                str(runtime_dir / "tasks" / f"{task['task_id']}.review.json"),
            ],
            "task_id": task["task_id"],
            "observed_changed_files": state.get("observed_changed_files") or [],
        },
    }


@trace_node("update")
def update_plan_node(state: WorkflowState) -> WorkflowState:
    plan = state["plan"]
    task = _get_current_task(state)
    review_result = state["review_result"]
    max_retries = state["max_retries"]
    runtime_dir = Path(state["runtime_dir"])

    if review_result["approved"]:
        task["status"] = "accepted"
    else:
        task["retries"] = task.get("retries", 0) + 1
        task["status"] = "blocked" if task["retries"] > max_retries else "pending"

    (runtime_dir / "plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "plan": plan,
        "current_task_id": None,
        "observed_changed_files": None,
        "__trace__": {
            "artifacts": [str(runtime_dir / "plan.json")],
            "task_id": task["task_id"],
            "review_approved": review_result["approved"],
        },
    }


@trace_node("finalize")
def finalize_node(state: WorkflowState) -> WorkflowState:
    plan = state["plan"]
    statuses = {task["status"] for task in plan["tasks"]}

    if statuses == {"accepted"}:
        final_status = "done"
    elif "blocked" in statuses:
        final_status = "blocked"
    else:
        final_status = "incomplete"

    summary_path = Path(state["runtime_dir"]) / "summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "final_status": final_status,
                "tasks": [
                    {
                        "task_id": task["task_id"],
                        "status": task["status"],
                        "retries": task.get("retries", 0),
                    }
                    for task in plan["tasks"]
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "finished": True,
        "final_status": final_status,
        "__trace__": {
            "artifacts": [str(summary_path)],
            "final_status": final_status,
        },
    }


def _get_current_task(state: WorkflowState) -> dict[str, Any]:
    task_id = state.get("current_task_id")
    if not task_id:
        raise ValueError("current_task_id is not set")

    for task in state["plan"]["tasks"]:
        if task["task_id"] == task_id:
            return task
    raise KeyError(f"Task not found: {task_id}")


def _git_status_paths(repo_path: Path) -> list[str]:
    try:
        completed = subprocess.run(
            ["git", "status", "--short", "--untracked-files=all"],
            cwd=repo_path,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        return []

    if completed.returncode != 0:
        return []

    paths: list[str] = []
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        status_and_path = line[3:]
        if " -> " in status_and_path:
            status_and_path = status_and_path.split(" -> ", 1)[1]
        paths.append(status_and_path.strip())
    return sorted(set(paths))

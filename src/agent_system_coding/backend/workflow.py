from __future__ import annotations

import json
import operator
import subprocess
from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from .codex_cli import run_codex_exec
from .prompts import build_execute_prompt, build_plan_prompt, build_review_prompt
from .tracing import trace_node
from .writers import write_graph_mermaid, write_trace_report, write_trace_viewer_html


class WorkflowState(TypedDict, total=False):
    user_request: str
    repo_path: str
    runtime_dir: str
    schemas_dir: str
    model: str | None
    reasoning_effort: str
    sandbox: str
    max_retries: int
    preexisting_paths: list[str]
    plan: dict[str, Any]
    active_batch_id: str | None
    active_batch_task_ids: list[str]
    task_id: str | None
    execution_events: Annotated[list[dict[str, Any]], operator.add]
    review_events: Annotated[list[dict[str, Any]], operator.add]
    finished: bool
    final_status: str
    graph_mermaid_path: str


def run_workflow(
    *,
    user_request: str,
    repo_path: Path,
    runtime_dir: Path,
    schemas_dir: Path,
    sandbox: str,
    max_retries: int,
    model: str | None,
    reasoning_effort: str,
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
    graph.add_node("execute_task", execute_task_node)
    graph.add_node("dispatch_reviews", dispatch_reviews_node)
    graph.add_node("review_task", review_task_node)
    graph.add_node("update", update_plan_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "plan")
    graph.add_edge("plan", "dispatch")
    graph.add_conditional_edges(
        "dispatch",
        dispatch_router,
        {
            "execute_task": "execute_task",
            "finalize": "finalize",
        },
    )
    graph.add_edge("execute_task", "dispatch_reviews")
    graph.add_conditional_edges(
        "dispatch_reviews",
        dispatch_reviews_router,
        ["review_task"],
    )
    graph.add_edge("review_task", "update")
    graph.add_edge("update", "dispatch")
    graph.add_edge("finalize", END)

    app = graph.compile()
    graph_mermaid_path = write_graph_mermaid(runtime_dir, app.get_graph().draw_mermaid())
    return app.invoke(
        {
            "user_request": user_request,
            "repo_path": str(repo_path),
            "runtime_dir": str(runtime_dir),
            "schemas_dir": str(schemas_dir),
            "model": model,
            "reasoning_effort": reasoning_effort,
            "sandbox": sandbox,
            "max_retries": max_retries,
            "preexisting_paths": preexisting_paths,
            "execution_events": [],
            "review_events": [],
            "graph_mermaid_path": str(graph_mermaid_path),
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
        reasoning_effort=state["reasoning_effort"],
        transcript_path=runtime_dir / "agents" / "plan.codex.json",
        transcript_metadata={
            "agent": "planner",
            "node": "plan",
            "title": "Root Planner",
        },
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
                str(runtime_dir / "agents" / "plan.codex.json"),
                str(plan_path),
                str(runtime_dir / "baseline_repo_state.json"),
            ],
            "task_count": len(plan["tasks"]),
        },
    }


@trace_node("dispatch")
def dispatch_node(state: WorkflowState) -> WorkflowState:
    plan = state["plan"]
    ready_tasks = _select_parallel_batch(plan["tasks"])
    batch_id = uuid4().hex[:8] if ready_tasks else None

    if ready_tasks:
        for task in ready_tasks:
            task["status"] = "dispatched"

    return {
        "plan": plan,
        "active_batch_id": batch_id,
        "active_batch_task_ids": [task["task_id"] for task in ready_tasks],
        "__trace__": {
            "selected_task_ids": [task["task_id"] for task in ready_tasks],
            "batch_id": batch_id,
        },
    }


def dispatch_router(state: WorkflowState) -> list[Send] | Literal["finalize"]:
    batch_id = state.get("active_batch_id")
    task_ids = state.get("active_batch_task_ids") or []
    if not batch_id or not task_ids:
        return "finalize"

    return [
        Send(
            "execute_task",
            {
                "user_request": state["user_request"],
                "repo_path": state["repo_path"],
                "runtime_dir": state["runtime_dir"],
                "schemas_dir": state["schemas_dir"],
                "model": state.get("model"),
                "reasoning_effort": state["reasoning_effort"],
                "sandbox": state["sandbox"],
                "preexisting_paths": state.get("preexisting_paths", []),
                "plan": state["plan"],
                "active_batch_id": batch_id,
                "task_id": task_id,
                "active_batch_task_ids": task_ids,
            },
        )
        for task_id in task_ids
    ]


@trace_node("execute_task")
def execute_task_node(state: WorkflowState) -> WorkflowState:
    repo_path = Path(state["repo_path"])
    runtime_dir = Path(state["runtime_dir"])
    schemas_dir = Path(state["schemas_dir"])
    batch_id = state["active_batch_id"]
    task = _get_current_task(state["plan"], state["task_id"])

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
        reasoning_effort=state["reasoning_effort"],
        transcript_path=runtime_dir / "tasks" / f"{task['task_id']}.execute.codex.json",
        transcript_metadata={
            "agent": "executor",
            "node": "execute_task",
            "task_id": task["task_id"],
            "title": f"Executor {task['task_id']}",
        },
    )
    after_paths = set(_git_status_paths(repo_path))
    observed_changed_files = sorted(after_paths - before_paths)
    execution_event = {
        "batch_id": batch_id,
        "task_id": task["task_id"],
        "result": execution_result,
        "observed_changed_files": observed_changed_files,
    }

    return {
        "execution_events": [execution_event],
        "__trace__": {
            "artifacts": [
                str(dispatch_path),
                str(runtime_dir / "tasks" / f"{task['task_id']}.execute.codex.json"),
                str(runtime_dir / "tasks" / f"{task['task_id']}.result.json"),
            ],
            "task_id": task["task_id"],
            "batch_id": batch_id,
            "observed_changed_files": observed_changed_files,
        },
    }


@trace_node("dispatch_reviews")
def dispatch_reviews_node(state: WorkflowState) -> WorkflowState:
    batch_events = _execution_events_for_batch(state)
    return {
        "__trace__": {
            "batch_id": state.get("active_batch_id"),
            "task_ids": [event["task_id"] for event in batch_events],
        }
    }


def dispatch_reviews_router(state: WorkflowState) -> list[Send]:
    batch_id = state.get("active_batch_id")
    review_sends: list[Send] = []
    for event in _execution_events_for_batch(state):
        review_sends.append(
            Send(
                "review_task",
                {
                    "user_request": state["user_request"],
                    "repo_path": state["repo_path"],
                    "runtime_dir": state["runtime_dir"],
                    "schemas_dir": state["schemas_dir"],
                    "model": state.get("model"),
                    "reasoning_effort": state["reasoning_effort"],
                    "sandbox": state["sandbox"],
                    "preexisting_paths": state.get("preexisting_paths", []),
                    "plan": state["plan"],
                    "active_batch_id": batch_id,
                    "active_batch_task_ids": state.get("active_batch_task_ids", []),
                    "task_id": event["task_id"],
                    "execution_events": [event],
                },
            )
        )
    return review_sends


@trace_node("review_task")
def review_task_node(state: WorkflowState) -> WorkflowState:
    repo_path = Path(state["repo_path"])
    runtime_dir = Path(state["runtime_dir"])
    schemas_dir = Path(state["schemas_dir"])
    batch_id = state["active_batch_id"]
    execution_event = state["execution_events"][0]
    task = _get_current_task(state["plan"], execution_event["task_id"])

    review_result = run_codex_exec(
        repo_path=repo_path,
        prompt=build_review_prompt(
            task,
            execution_event["result"],
            repo_path,
            state.get("preexisting_paths", []),
            execution_event.get("observed_changed_files", []),
            _batch_allowed_paths(state["plan"], state.get("active_batch_task_ids", [])),
        ),
        output_schema_path=schemas_dir / "review.schema.json",
        output_path=runtime_dir / "tasks" / f"{task['task_id']}.review.json",
        sandbox=state["sandbox"],
        model=state.get("model"),
        reasoning_effort=state["reasoning_effort"],
        transcript_path=runtime_dir / "tasks" / f"{task['task_id']}.review.codex.json",
        transcript_metadata={
            "agent": "reviewer",
            "node": "review_task",
            "task_id": task["task_id"],
            "title": f"Reviewer {task['task_id']}",
        },
    )
    review_event = {
        "batch_id": batch_id,
        "task_id": task["task_id"],
        "review": review_result,
    }
    return {
        "review_events": [review_event],
        "__trace__": {
            "artifacts": [
                str(runtime_dir / "tasks" / f"{task['task_id']}.review.codex.json"),
                str(runtime_dir / "tasks" / f"{task['task_id']}.review.json"),
            ],
            "task_id": task["task_id"],
            "batch_id": batch_id,
        },
    }


@trace_node("update")
def update_plan_node(state: WorkflowState) -> WorkflowState:
    plan = state["plan"]
    batch_id = state.get("active_batch_id")
    max_retries = state["max_retries"]
    runtime_dir = Path(state["runtime_dir"])
    batch_reviews = {
        event["task_id"]: event["review"]
        for event in state.get("review_events", [])
        if event.get("batch_id") == batch_id
    }

    updated_task_ids: list[str] = []
    for task_id in state.get("active_batch_task_ids", []):
        task = _get_current_task(plan, task_id)
        review_result = batch_reviews.get(task_id)
        if not review_result:
            task["retries"] = task.get("retries", 0) + 1
            task["status"] = "blocked" if task["retries"] > max_retries else "pending"
            updated_task_ids.append(task_id)
            continue

        if review_result["approved"]:
            task["status"] = "accepted"
        else:
            task["retries"] = task.get("retries", 0) + 1
            task["status"] = "blocked" if task["retries"] > max_retries else "pending"
        updated_task_ids.append(task_id)

    (runtime_dir / "plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "plan": plan,
        "active_batch_id": None,
        "active_batch_task_ids": [],
        "__trace__": {
            "artifacts": [str(runtime_dir / "plan.json")],
            "batch_id": batch_id,
            "updated_task_ids": updated_task_ids,
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
    trace_report_path = write_trace_report(Path(state["runtime_dir"]))
    trace_viewer_path = write_trace_viewer_html(Path(state["runtime_dir"]))
    artifacts = [str(summary_path)]
    if trace_report_path:
        artifacts.append(str(trace_report_path))
    if trace_viewer_path:
        artifacts.append(str(trace_viewer_path))
    if state.get("graph_mermaid_path"):
        artifacts.append(state["graph_mermaid_path"])
    return {
        "finished": True,
        "final_status": final_status,
        "__trace__": {
            "artifacts": artifacts,
            "final_status": final_status,
        },
    }


def _execution_events_for_batch(state: WorkflowState) -> list[dict[str, Any]]:
    batch_id = state.get("active_batch_id")
    task_ids = set(state.get("active_batch_task_ids") or [])
    return [
        event
        for event in state.get("execution_events", [])
        if event.get("batch_id") == batch_id and event.get("task_id") in task_ids
    ]


def _get_current_task(plan: dict[str, Any], task_id: str | None) -> dict[str, Any]:
    if not task_id:
        raise ValueError("task_id is not set")

    for task in plan["tasks"]:
        if task["task_id"] == task_id:
            return task
    raise KeyError(f"Task not found: {task_id}")


def _select_parallel_batch(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    accepted_ids = {
        task["task_id"]
        for task in tasks
        if task["status"] == "accepted"
    }
    candidates = [
        task
        for task in tasks
        if task["status"] in {"pending", "ready"}
        and all(dep in accepted_ids for dep in task.get("depends_on", []))
    ]
    candidates.sort(key=lambda task: task["task_id"])

    selected: list[dict[str, Any]] = []
    selected_paths: list[str] = []
    for task in candidates:
        task_paths = task.get("allowed_paths", [])
        if any(_paths_conflict(path, existing) for path in task_paths for existing in selected_paths):
            continue
        selected.append(task)
        selected_paths.extend(task_paths)
    return selected


def _batch_allowed_paths(plan: dict[str, Any], task_ids: list[str]) -> list[str]:
    paths: list[str] = []
    for task_id in task_ids:
        paths.extend(_get_current_task(plan, task_id).get("allowed_paths", []))
    return sorted(set(paths))


def _paths_conflict(left: str, right: str) -> bool:
    left_norm = left.rstrip("/")
    right_norm = right.rstrip("/")
    return (
        left_norm == right_norm
        or left_norm.startswith(f"{right_norm}/")
        or right_norm.startswith(f"{left_norm}/")
    )


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

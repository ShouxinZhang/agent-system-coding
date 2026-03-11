---
name: workflow-trace-calculus
description: Use when you need to verify the local LangGraph + Codex CLI MVP leaves trace artifacts for every workflow node, or when you want a simple calculus smoke test that runs the full plan-execute-review loop and checks the trace files.
---

# Workflow Trace Calculus

Use this skill to validate two things at once:

1. the local workflow can run end to end
2. every node leaves machine-readable trace artifacts

## When To Use

Use this skill when:

- you changed the workflow graph
- you changed the Codex prompts or schemas
- you need a very small end-to-end smoke test
- you need to confirm `plan`, `dispatch`, `execute`, `review`, `update`, and `finalize` all left traces

## Primary Command

Run:

```bash
.venv/bin/python skills/workflow-trace-calculus/scripts/run_smoke.py
```

## Expected Outputs

The smoke test should produce:

- `runtime/calculus-smoke/demo-repo/docs/calculus-smoke-answer.md`
- `runtime/calculus-smoke/plan.json`
- `runtime/calculus-smoke/tasks/*.dispatch.json`
- `runtime/calculus-smoke/tasks/*.result.json`
- `runtime/calculus-smoke/tasks/*.review.json`
- `runtime/calculus-smoke/traces/events.jsonl`
- `runtime/calculus-smoke/traces/*.start.json`
- `runtime/calculus-smoke/traces/*.end.json`
- `runtime/calculus-smoke/summary.json`

## Pass Criteria

Treat the smoke test as passed only if:

- `summary.json` has `final_status = "done"`
- `runtime/calculus-smoke/demo-repo/docs/calculus-smoke-answer.md` exists
- the answer file contains the final derivative result `6`
- `events.jsonl` contains all six nodes:
  `plan`, `dispatch`, `execute`, `review`, `update`, `finalize`

## Failure Handling

If the run fails:

- inspect the latest `runtime/calculus-smoke/traces/*.error.json`
- inspect `runtime/calculus-smoke/traces/events.jsonl`
- inspect the task-level `*.result.json` and `*.review.json`
- fix the workflow or prompts first, then rerun the same smoke script

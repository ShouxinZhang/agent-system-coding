# agent-system-coding

基于 CodeX CLI + LangGraph 的 graph coding system 实验仓库。

## 当前状态

仓库里已经有一个最小可运行的 MVP 骨架：

- LangGraph 负责状态流转
- CodeX CLI 负责 `plan / execute / review`
- 运行产物落在 `runtime/`
- 每个 workflow 节点都会把 `start / end / error` trace 落在 `runtime/*/traces/`

代码入口：

- [src/agent_system_coding/cli.py](/home/wudizhe001/Documents/GitHub/agent-system-coding/src/agent_system_coding/cli.py)
- [src/agent_system_coding/workflow.py](/home/wudizhe001/Documents/GitHub/agent-system-coding/src/agent_system_coding/workflow.py)

## 快速开始

先准备环境：

```bash
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -e .
codex login
```

然后运行一个请求：

```bash
.venv/bin/agent-system-coding \
  --request "为当前项目生成一个最小计划，并逐步完成任务" \
  --repo . \
  --sandbox workspace-write
```

运行时会生成这些文件：

- `runtime/plan.json`
- `runtime/tasks/*.dispatch.json`
- `runtime/tasks/*.result.json`
- `runtime/tasks/*.review.json`
- `runtime/traces/events.jsonl`
- `runtime/summary.json`

## Smoke Skill

仓库里带了一个最小 smoke skill：

- [skills/workflow-trace-calculus/SKILL.md](/home/wudizhe001/Documents/GitHub/agent-system-coding/skills/workflow-trace-calculus/SKILL.md)

它会创建一个隔离 demo repo，然后用一道简单微积分题验证：

- workflow 的 `plan / dispatch / execute / review / update / finalize` 节点都完成
- 每个节点都有 trace
- 最终 answer 文件和 `summary.json` 都正确

详细方案见 [docs/plan/README.md](/home/wudizhe001/Documents/GitHub/agent-system-coding/docs/plan/README.md)。
最小范围说明见 [docs/plan/mvp.md](/home/wudizhe001/Documents/GitHub/agent-system-coding/docs/plan/mvp.md)。

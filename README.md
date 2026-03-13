# agent-system-coding

基于 CodeX CLI + LangGraph 的 graph coding system 实验仓库。

## 当前状态

仓库里已经有一个最小可运行的 MVP 骨架：

- LangGraph 负责状态流转
- CodeX CLI 负责 `plan / execute / review`
- v2 已支持同一批 ready tasks 的并行 `execute_task / review_task`
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

默认情况下，这个项目会显式把 CodeX CLI 的 `reasoning effort` 设为 `high`。
你也可以手动覆盖：

```bash
.venv/bin/agent-system-coding \
  --request "为当前项目生成一个最小计划，并逐步完成任务" \
  --repo . \
  --sandbox workspace-write \
  --reasoning-effort xhigh
```

运行时会生成这些文件：

- `runtime/plan.json`
- `runtime/tasks/*.dispatch.json`
- `runtime/tasks/*.result.json`
- `runtime/tasks/*.review.json`
- `runtime/graph.mmd`
- `runtime/traces/events.jsonl`
- `runtime/traces/latest-status.json`
- `runtime/trace-report.md`
- `runtime/summary.json`

## 本地 Dashboard

现在有一个本地 dashboard server，可以直接在前端提交 chat 指令，并实时看 workflow graph 里每个节点的状态。

启动：

```bash
.venv/bin/agent-system-coding-monitor --runtime-root runtime/live-runs --port 8765
```

然后打开：

```text
http://127.0.0.1:8765
```

你会看到三块内容：

- 左侧：输入 prompt，启动一条新的 workflow run
- 中间上半部分：固定布局的 LangGraph 节点图，节点会按 `idle / running / success / error` 实时变色
- 中间下半部分：agent console，会把 planner / executor / reviewer 的 prompt、结果和 artifact 内容按 thread 展示出来
- 右侧：当前 run 状态、task 列表、batch 列表、artifact 摘要、最近时间线

这个 dashboard 的默认演示 prompt 就是并行微积分题。
点击 `Launch Run` 后，后端会创建一个隔离 demo repo，并在后台启动一条真实 workflow run。

如果你已经有一个现成的 runtime，也可以预选它：

```bash
.venv/bin/agent-system-coding-monitor --runtime runtime/calculus-smoke --port 8765
```

这时页面会直接选中这次运行并展示它的状态。

## Smoke Skill

仓库里带了一个最小 smoke skill：

- [skills/workflow-trace-calculus/SKILL.md](/home/wudizhe001/Documents/GitHub/agent-system-coding/skills/workflow-trace-calculus/SKILL.md)

它会创建一个隔离 demo repo，然后用一组更复杂的并行微积分题验证：

- workflow 的 `plan / dispatch / execute_task / dispatch_reviews / review_task / update / finalize` 节点都完成
- 每个节点都有 trace
- 至少一批 subagents 并行执行
- 最终答案文件和 `summary.json` 都正确

直接运行：

```bash
.venv/bin/python skills/workflow-trace-calculus/scripts/run_smoke.py
```

详细方案见 [docs/plan/README.md](/home/wudizhe001/Documents/GitHub/agent-system-coding/docs/plan/README.md)。
最小范围说明见 [docs/plan/mvp.md](/home/wudizhe001/Documents/GitHub/agent-system-coding/docs/plan/mvp.md)。

## 实验记录

### calculus-smoke（2026-03-12）

**目标：** 验证 workflow 同时支持任务间的并行执行和串行依赖。

**实验设计：** 构造一个 3 任务计划，其中 task-1 与 task-2 无依赖关系（可并行），task-3 依赖前两者（串行等待）。

| 任务 | 目标 | 依赖 |
|------|------|------|
| task-1 | 用中文解答：求 f(x)=x³ 在 x=2 处的导数，答案 12 | 无 |
| task-2 | 用中文解答：求定积分 ∫[0,2] x dx，答案 2 | 无 |
| task-3 | 用中文汇总前两题结论（同时包含 12 和 2） | task-1, task-2 |

**并行执行（Batch 1）：**

task-1 和 task-2 在同一批次中由 `dispatch` 选中，`execute_task` 和 `review_task` 均两路并发启动：

```
10:12:27  dispatch    → 选中 [task-1, task-2]
10:12:27  execute_task start (task-1)
10:12:27  execute_task start (task-2)   ← 同时启动
10:12:57  execute_task end  (task-2)    ← task-2 先完成
10:13:01  execute_task end  (task-1)
10:13:01  review_task  start (task-1)
10:13:01  review_task  start (task-2)   ← review 同样并行
10:13:25  review_task  end  (task-1)
10:13:28  review_task  end  (task-2)
10:13:28  update       → task-1 accepted, task-2 accepted
```

**串行依赖（Batch 2）：**

task-3 在前两个任务均 `accepted` 后，才被下一轮 `dispatch` 选中执行：

```
10:13:28  dispatch    → 选中 [task-3]   ← 等 task-1/2 完成后才触发
10:13:28  execute_task start (task-3)
10:14:04  execute_task end  (task-3)
10:14:04  review_task  start (task-3)
10:14:26  review_task  end  (task-3)
10:14:26  update       → task-3 accepted
10:14:26  dispatch    → 无更多任务
10:14:26  finalize
```

**结果：** 全部 3 个任务均以 `accepted` 状态完成，产出文件：

- `demo-repo/docs/derivative-answer.md` — 导数解答（含答案 12）
- `demo-repo/docs/integral-answer.md` — 积分解答（含答案 2）
- `demo-repo/docs/final-summary.md` — 汇总结论（同时包含 12 和 2）

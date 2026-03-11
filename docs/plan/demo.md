# LangGraph Demo Flow

这张图描述当前仓库中已经实现的 LangGraph MVP 流程。

对应代码见：

- [src/agent_system_coding/workflow.py](/home/wudizhe001/Documents/GitHub/agent-system-coding/src/agent_system_coding/workflow.py)
- [src/agent_system_coding/tracing.py](/home/wudizhe001/Documents/GitHub/agent-system-coding/src/agent_system_coding/tracing.py)

## Mermaid 图

```mermaid
flowchart TD
    A([START]) --> B[plan]
    B --> C[dispatch]

    C -->|current_task_id exists| D[execute]
    C -->|no ready task| H[finalize]

    D --> E[review]
    E --> F[update]
    F --> C

    H --> I([END])
```

## 节点说明

- `plan`
  - 调用 CodeX CLI 生成 `plan.json`
  - 初始化任务状态
  - 写入 trace

- `dispatch`
  - 从 plan 中挑选当前可执行任务
  - 如果有 ready task，则设置 `current_task_id`
  - 如果没有可执行任务，则转到 `finalize`

- `execute`
  - 为当前任务写出 `*.dispatch.json`
  - 调用 CodeX CLI 执行任务
  - 写出 `*.result.json`
  - 记录本轮观测到的新增改动文件

- `review`
  - 调用 CodeX CLI 对当前任务做验收
  - 写出 `*.review.json`

- `update`
  - 根据 review 结果更新任务状态
  - 通过则标记为 `accepted`
  - 失败则按重试次数回到 `pending` 或标记 `blocked`
  - 回写 `plan.json`

- `finalize`
  - 汇总全部任务状态
  - 写出 `summary.json`
  - 给出最终 `done / blocked / incomplete`

## 状态回路

当前 demo 的核心回路是：

`plan -> dispatch -> execute -> review -> update -> dispatch`

只要还有任务可执行，这个回路就会继续。

当没有新的 ready task 时，流程进入：

`finalize -> END`

## 留痕文件

每个节点都会写 trace 到：

- `runtime/*/traces/events.jsonl`
- `runtime/*/traces/*.start.json`
- `runtime/*/traces/*.end.json`
- `runtime/*/traces/*.error.json`

这意味着每个环节是否执行、何时执行、执行后状态如何，都可以落盘追踪。

# API 接口契约

> **状态**: 设计中 (Draft)
> **版本**: v0.1.0
> **最后更新**: 2026-03-15
> **所有者**: 前后端共有

本文档是 `src/agent_system_coding` 前后端分离架构的**唯一接口真相源**。
前端和后端的重构文档均以本文档为依据进行开发。

---

## 1. 架构总览

```
┌─────────────────────────────────┐
│         Frontend (Vite)         │
│  TypeScript + shadcn/ui + TW    │
│                                 │
│  ┌──────┐ ┌──────┐ ┌─────────┐ │
│  │ DAG  │ │Tasks │ │ Context │ │
│  │ View │ │Panel │ │Inspector│ │
│  └──┬───┘ └──┬───┘ └────┬────┘ │
│     │        │         │        │
│     └────────┼─────────┘        │
│              │                  │
│         HTTP / WS               │
└──────────────┼──────────────────┘
               │
┌──────────────┼──────────────────┐
│         Backend (FastAPI)       │
│                                 │
│  ┌──────────┐  ┌─────────────┐  │
│  │ REST API │  │ WebSocket   │  │
│  │ /api/*   │  │ /ws/*       │  │
│  └────┬─────┘  └──────┬──────┘  │
│       │               │         │
│  ┌────┴───────────────┴──────┐  │
│  │     Workflow Engine       │  │
│  │  (LangGraph + Codex CLI)  │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
```

## 2. 通信协议

| 协议 | 用途 | 基础路径 |
|------|------|----------|
| HTTP REST | 工作流提交、状态查询、历史回溯 | `/api/v1/` |
| WebSocket | 运行时节点状态实时推送 | `/ws/v1/` |

### 2.1 通用约定

- **Content-Type**: `application/json`
- **编码**: UTF-8
- **时间格式**: ISO 8601 (`2026-03-15T02:00:00Z`)
- **错误响应格式**:

```json
{
  "error": {
    "code": "WORKFLOW_NOT_FOUND",
    "message": "Workflow run abc123 does not exist",
    "details": {}
  }
}
```

- **HTTP 状态码规范**:

| 状态码 | 用途 |
|--------|------|
| 200 | 成功返回数据 |
| 201 | 资源创建成功 |
| 400 | 请求参数校验失败 |
| 404 | 资源不存在 |
| 409 | 状态冲突（如重复提交） |
| 500 | 服务端内部错误 |

---

## 3. REST API 端点

### 3.1 `POST /api/v1/workflow/run` — 提交工作流

提交一次新的 Plan-Execute-Review 循环。

**请求体**:
```json
{
  "request": "string — 用户的自然语言需求",
  "repo_path": "string — 目标仓库路径（可选，默认 '.'）",
  "sandbox": "string — 沙箱模式：read-only | workspace-write | danger-full-access",
  "max_retries": "number — 最大重试次数（可选，默认 2）",
  "model": "string | null — Codex 模型覆盖（可选）",
  "reasoning_effort": "string — low | medium | high | xhigh（可选，默认 high）"
}
```

**响应体** (201):
```json
{
  "run_id": "string — 唯一运行标识",
  "status": "queued",
  "created_at": "string — ISO 8601"
}
```

**业务规则**:
- `run_id` 由后端生成，格式 `{date}-{uuid8}`
- 提交后工作流异步执行，前端通过 WebSocket 监听进度

---

### 3.2 `GET /api/v1/workflow/{run_id}/status` — 查询运行状态

**响应体** (200):
```json
{
  "run_id": "string",
  "status": "string — queued | running | done | blocked | incomplete",
  "created_at": "string",
  "finished_at": "string | null",
  "plan": {
    "goal": "string",
    "tasks": [
      {
        "task_id": "string",
        "title": "string",
        "status": "string — pending | dispatched | accepted | blocked",
        "retries": "number",
        "depends_on": ["string"],
        "allowed_paths": ["string"]
      }
    ]
  }
}
```

---

### 3.3 `GET /api/v1/workflow/{run_id}/graph` — 获取 DAG 图结构

前端用于渲染工作流 DAG 的结构化数据。

**响应体** (200):
```json
{
  "run_id": "string",
  "mermaid": "string — Mermaid 格式的图定义文本",
  "nodes": [
    {
      "id": "string — 节点标识（如 plan, dispatch, execute_task）",
      "label": "string — 显示名称",
      "type": "string — start | end | normal | conditional"
    }
  ],
  "edges": [
    {
      "from": "string — 起点节点 id",
      "to": "string — 终点节点 id",
      "label": "string | null — 条件标签",
      "conditional": "boolean"
    }
  ],
  "parallel_batches": [
    {
      "batch_id": "string — 批次标识",
      "node_ids": ["string — 该批次内并行执行的节点 id 列表"]
    }
  ]
}
```

**说明**: `parallel_batches` 用于前端渲染并行泳道，将同一批次的节点水平并排显示。

---

### 3.4 `GET /api/v1/workflow/{run_id}/traces` — 获取追踪事件

返回运行过程中所有 trace 事件的时间线。

**查询参数**:
| 参数 | 类型 | 描述 |
|------|------|------|
| `node` | string | 按节点名过滤（可选） |
| `phase` | string | 按阶段过滤：start / end / error（可选） |
| `limit` | number | 返回数量上限（可选，默认 100） |

**响应体** (200):
```json
{
  "run_id": "string",
  "events": [
    {
      "trace_id": "string",
      "timestamp": "string — ISO 8601",
      "node": "string — 节点名",
      "phase": "string — start | end | error",
      "state": {
        "user_request": "string | null",
        "current_task_id": "string | null",
        "final_status": "string | null",
        "tasks": [
          {
            "task_id": "string",
            "status": "string",
            "retries": "number"
          }
        ]
      },
      "payload": "object | null — 节点特定的附加数据"
    }
  ]
}
```

---

### 3.5 `GET /api/v1/workflow/{run_id}/node/{node_id}/context` — 节点上下文（记忆透明）

返回指定节点的完整 chat 上下文，包括输入状态、输出结果、发送的 prompt 和收到的 response。

**响应体** (200):
```json
{
  "run_id": "string",
  "node_id": "string",
  "node_name": "string — 节点显示名称",
  "input": {
    "state_snapshot": "object — 节点接收的 WorkflowState 快照（已脱敏摘要）"
  },
  "output": {
    "state_diff": "object — 节点返回的 state 变更字段"
  },
  "prompt": {
    "text": "string — 发送给 Codex CLI 的完整 prompt 文本",
    "schema_path": "string — 使用的 output schema 路径"
  },
  "response": {
    "result": "object — Codex CLI 返回的完整 JSON 结果",
    "exit_code": "number",
    "stdout_preview": "string | null — stdout 前 500 字"
  },
  "timing": {
    "started_at": "string — ISO 8601",
    "finished_at": "string — ISO 8601",
    "duration_ms": "number"
  }
}
```

**业务规则**:
- 数据来源于 `runtime_dir/traces/` 下的 trace 文件和 `runtime_dir/tasks/` 下的 dispatch/result/review 文件
- 对于无 Codex 调用的节点（如 dispatch, finalize），`prompt` 和 `response` 字段为 `null`
- `input.state_snapshot` 做脱敏处理，移除过长的文本字段（如完整 prompt），仅保留结构概览

---

### 3.6 `GET /api/v1/workflow/history` — 历史运行列表

**查询参数**:
| 参数 | 类型 | 描述 |
|------|------|------|
| `status` | string | 按状态过滤（可选） |
| `limit` | number | 返回数量（可选，默认 20） |
| `offset` | number | 偏移量（可选，默认 0） |

**响应体** (200):
```json
{
  "total": "number",
  "items": [
    {
      "run_id": "string",
      "status": "string",
      "request_preview": "string — 用户需求前 100 字",
      "task_count": "number",
      "created_at": "string",
      "finished_at": "string | null"
    }
  ]
}
```

---

## 4. WebSocket 端点

### 4.1 `WS /ws/v1/workflow/{run_id}` — 实时状态推送

前端连接后，后端在每个节点 phase 变更时主动推送。

**推送消息格式**:
```json
{
  "type": "string — node_start | node_end | node_error | workflow_complete",
  "timestamp": "string — ISO 8601",
  "data": {
    "trace_id": "string",
    "node": "string",
    "phase": "string",
    "state": { "...同 trace event 的 state 结构" },
    "payload": "object | null"
  }
}
```

**连接生命周期**:
1. 前端通过 `ws://host/ws/v1/workflow/{run_id}` 建立连接
2. 后端在工作流运行过程中持续推送事件
3. 工作流完成后推送 `workflow_complete`，随后服务端关闭连接
4. 前端可发送 `{ "type": "ping" }` 保活，后端回复 `{ "type": "pong" }`

---

## 5. 数据模型映射

本节说明接口数据结构与后端核心类型的对应关系，确保前端消费的数据与后端产生的数据语义一致。

| 接口字段 | 后端来源 | 说明 |
|---|---|---|
| `run_id` | 后端生成 | 新概念，当前代码无此字段 |
| `plan.tasks[]` | `WorkflowState["plan"]["tasks"]` | 直接映射 |
| `task.status` | `pending / dispatched / accepted / blocked` | 与 workflow.py 一致 |
| `task.depends_on` | `task["depends_on"]` | plan.schema.json 定义 |
| `task.allowed_paths` | `task["allowed_paths"]` | plan.schema.json 定义 |
| `trace event` | `tracing._write_trace_event()` 输出 | 直接映射 |
| `graph.mermaid` | `app.get_graph().draw_mermaid()` | LangGraph 生成 |
| `graph.nodes/edges` | 后端解析 mermaid 或 LangGraph 图 | 新增解析逻辑 |
| `graph.parallel_batches` | `_select_parallel_batch()` 调度结果 | 新增，运行时动态生成 |
| `node_context.input` | `traces/{trace_id}.start.json` 的 state | 映射 trace start 事件 |
| `node_context.output` | `traces/{trace_id}.end.json` 的 state diff | 映射 trace end 事件 |
| `node_context.prompt` | `tasks/{task_id}.dispatch.json` + prompts.py | 拼接还原 |
| `node_context.response` | `tasks/{task_id}.result.json` | 直接映射 |

---

## 6. 错误码枚举

| 错误码 | HTTP 状态码 | 描述 |
|--------|-------------|------|
| `VALIDATION_ERROR` | 400 | 请求参数校验失败 |
| `WORKFLOW_NOT_FOUND` | 404 | 指定的 run_id 不存在 |
| `WORKFLOW_ALREADY_RUNNING` | 409 | 同一请求正在执行 |
| `ENGINE_ERROR` | 500 | 工作流引擎内部错误 |
| `CODEX_CLI_ERROR` | 500 | Codex CLI 调用失败 |
| `WS_RUN_NOT_FOUND` | 4404 | WebSocket 连接时 run_id 无效 |

---

## 7. CORS 配置

后端需要配置 CORS 以允许前端 Vite 开发服务器访问：

```python
# 开发环境
origins = ["http://localhost:5173", "http://localhost:5174"]

# 生产环境
origins = ["部署域名"]
```

---

## 8. 版本策略

- API 路径以 `/v1/` 开头，未来大版本变更使用 `/v2/`
- 在同一版本内，新增字段采用**向后兼容**策略（新增可选字段，不删除已有字段）
- 破坏性变更必须升级版本号

---

## 9. 待确认事项

- [ ] 是否需要认证/鉴权？（当前为本地开发工具，暂不需要）
- [ ] 是否支持多个工作流并发运行？（初期建议单实例串行）
- [ ] graph.nodes/edges 的结构化数据是否由后端解析 mermaid 生成，还是直接从 LangGraph 对象提取？

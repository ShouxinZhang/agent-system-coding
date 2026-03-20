# API 契约定义

> 前后端重构的唯一耦合点。后端实现此契约，前端消费此契约。
> 两侧可完全并行开发，只要遵守本文件的接口定义。

---

## 一、REST 端点

### 1.1 `GET /api/runs`

列出所有运行记录。

**Response** `200 OK`
```jsonc
{
  "runs": [
    {
      "run_id": "run-20260312T201612-c1b197",
      "status": "running" | "done" | "failed" | "starting" | "unknown",
      "created_at": "2026-03-12T20:16:12+00:00",  // ISO-8601, 可选
      "prompt": "...",                              // 可选
      "runtime_dir": "/abs/path",                   // 可选，前端通常不用
      "finished_at": "...",                          // 可选
      "return_code": 0                               // 可选
    }
  ]
}
```

---

### 1.2 `POST /api/runs`

创建新运行。

**Request Body**
```json
{ "prompt": "string (可为空，空值使用默认 demo prompt)" }
```

**Response** `200 OK`
```json
{ "ok": true, "run_id": "run-...", "runtime_dir": "/abs/path" }
```

---

### 1.3 `GET /api/runs/{run_id}/snapshot`

获取运行的实时快照。核心数据接口。

**Response** `200 OK`
```jsonc
{
  "runtime_dir": "/abs/path",
  "run": {                             // Run 元数据
    "run_id": "string",
    "status": "string",
    "created_at": "string?",
    "prompt": "string?"
  },
  "events": [TraceEvent],              // 全量事件列表（JSONL 解析）
  "latest": TraceEvent | {},           // 最新事件
  "latest_state": {},                  // 最新事件的 state 字段
  "tasks": [Task],                     // 从 latest_state.tasks 提取
  "batches": [Batch],                  // 从事件流聚合
  "node_statuses": {                   // 节点 → 状态
    "plan": NodeStatus,
    "dispatch": NodeStatus,
    // ...
  },
  "node_details": {                    // 节点 → 详细信息
    "plan": NodeDetail,
    // ...
  },
  "artifacts": ["string"],             // 产物路径列表
  "conversations": [Conversation],     // Agent 对话记录
  "latest_conversation_id": "string?", // 最近活跃的对话 ID
  "process_log_path": "/abs/path",     // process.log 路径
  "graph_text": "string",              // Mermaid 文本
  "summary": Summary | null            // 结束后的汇总
}
```

**404** — 运行不存在

---

### 1.4 `GET /api/runs/{run_id}/artifact?path={relative_or_absolute}`

读取产物文件。

**Response** `200 OK`
```json
{ "path": "/resolved/path", "content": "file content as text" }
```

**403** — 路径在沙箱外  
**404** — 文件不存在

---

### 1.5 `GET /api/runs/{run_id}/log`

读取进程日志。

**Response** `200 OK` — `text/plain`

**404** — 日志不存在

---

## 二、WebSocket 端点（新增）

### 2.1 `ws /ws/runs/{run_id}/snapshot`

服务端以固定间隔（~1s）或事件驱动方式推送快照 JSON。

**消息格式**（Server→Client）：与 `GET /api/runs/{id}/snapshot` 响应体结构完全一致。

**客户端行为**：
- 连接成功后立即收到一次完整快照
- 之后每次快照变更时推送增量或全量（初版用全量，后续可优化为 JSON Patch）
- 断线后客户端自动指数退避重连

---

## 三、数据类型定义

### TraceEvent
```typescript
interface TraceEvent {
  trace_id: string;           // "20260312T202527387932Z-plan-7a32b50c"
  node: string;               // "plan" | "dispatch" | "execute_task" | ...
  phase: "start" | "end" | "error";
  timestamp: string;          // ISO-8601
  payload?: Record<string, unknown>;
  state?: Record<string, unknown>;
}
```

### Task
```typescript
interface Task {
  task_id: string;
  title: string;
  status: "pending" | "ready" | "in_progress" | "approved" | "blocked";
  depends_on: string[];
  allowed_paths: string[];
  retries?: number;
}
```

### Batch
```typescript
interface Batch {
  batch_id: string;
  task_ids: string[];
  nodes: string[];            // 经历过的节点名
}
```

### NodeStatus
```typescript
interface NodeStatus {
  status: "idle" | "running" | "success" | "error";
  latest_timestamp: string | null;
  open_traces: string[];
}
```

### NodeDetail
```typescript
interface NodeDetail {
  node: string;
  status: "idle" | "running" | "success" | "error";
  latest_phase: string | null;
  latest_timestamp: string | null;
  open_traces: string[];
  run_count: number;
  error_count: number;
  tasks: string[];
  batches: string[];
  recent_events: {
    timestamp: string;
    phase: string;
    task_id: string | null;
    batch_id: string | null;
    trace_id: string;
  }[];
}
```

### Conversation
```typescript
interface Conversation {
  id: string;                 // "user-request" | "plan:plan.codex" | "exec:task-1" | ...
  title: string;
  agent: "user" | "planner" | "executor" | "reviewer" | "node-agent";
  node: string;
  task_id: string | null;
  status: string;
  diagnostics?: string;
  messages: {
    role: "user" | "assistant" | "system";
    label: string;
    content: string;
  }[];
}
```

### Summary
```typescript
interface Summary {
  final_status: "done" | "blocked" | "incomplete";
  total_tasks: number;
  approved_tasks: number;
  // ...
}
```

### Run
```typescript
interface Run {
  run_id: string;
  status: string;
  created_at?: string;
  prompt?: string;
  runtime_dir?: string;
  finished_at?: string;
  return_code?: number;
  pid?: number;
}
```

---

## 四、CORS & 开发代理

- 开发态：前端 Vite dev server (`:5173`) 通过 `vite.config.ts` proxy 转发 `/api` 和 `/ws` 到后端 (`:8080`)
- 生产态：FastAPI 直接挂载前端 `dist/`，无跨域问题
- 后端 FastAPI 添加 CORS 中间件兜底，允许 `localhost:5173`

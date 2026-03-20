# 前端重构文档

> **状态**: 设计中 (Draft)
> **版本**: v0.1.0
> **最后更新**: 2026-03-15
> **接口契约**: [api-contract.md](./api-contract.md)
> **并行关系**: 与 [backend-refactor.md](./backend-refactor.md) Phase 1 并行开发

---

## 1. 业务目标

在 `src/agent_system_coding/frontend/` 下构建独立的前端应用，为 Agent 工作流系统提供可视化界面：

| 目标 | 描述 |
|------|------|
| DAG 可视化 | 正交箭头布局，清晰展示并行批次中多节点同时执行 |
| 任务状态监控 | 实时展示每个 task 的运行状态、重试次数、依赖关系 |
| 记忆透明 | 每个节点可展开查看完整 chat 上下文（Input / Output / Prompt / Response） |
| 工作流提交 | 提供表单界面提交新的工作流运行 |
| 运行历史 | 查看和管理历史工作流运行记录 |

---

## 2. 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Vite | ≥6.x | 构建工具 + 开发服务器 |
| TypeScript | ≥5.x | 类型安全 |
| React | ≥19.x | UI 框架 |
| shadcn/ui | latest | 组件库（基于 Radix UI） |
| Tailwind CSS | v4 | 原子化样式 |
| React Flow | ≥12.x | DAG 图渲染（可选，备选 dagre + 自绘） |
| TanStack Query | ≥5.x | 数据获取 + 缓存 |

---

## 3. 目录结构

```
src/agent_system_coding/
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.ts
    ├── tsconfig.json
    ├── tailwind.config.ts
    ├── components.json              # shadcn/ui 配置
    │
    ├── public/
    │   └── favicon.svg
    │
    └── src/
        ├── main.tsx                  # 应用入口
        ├── App.tsx                   # 路由 + 布局
        ├── index.css                 # Tailwind 基础样式 + 设计令牌
        │
        ├── api/                      # API 层（对接后端契约）
        │   ├── client.ts             # HTTP 客户端（fetch 封装）
        │   ├── websocket.ts          # WebSocket 客户端
        │   ├── types.ts              # 接口契约的 TypeScript 类型定义
        │   └── hooks.ts              # TanStack Query hooks
        │
        ├── components/               # UI 组件
        │   ├── ui/                   # shadcn/ui 组件（自动生成）
        │   │   ├── button.tsx
        │   │   ├── card.tsx
        │   │   ├── badge.tsx
        │   │   ├── input.tsx
        │   │   ├── select.tsx
        │   │   ├── table.tsx
        │   │   ├── toast.tsx
        │   │   └── ...
        │   │
        │   ├── dag-view.tsx              # DAG 图组件（正交箭头 + 并行泳道）
        │   ├── task-panel.tsx            # 任务状态面板
        │   ├── node-context-inspector.tsx # 节点上下文检查器（记忆透明）
        │   ├── trace-timeline.tsx        # Trace 时间线
        │   ├── workflow-form.tsx         # 工作流提交表单
        │   ├── run-history.tsx           # 运行历史列表
        │   └── layout/
        │       ├── header.tsx            # 顶部导航
        │       ├── sidebar.tsx           # 侧边栏
        │       └── main-layout.tsx       # 主布局
        │
        ├── pages/                    # 页面组件
        │   ├── dashboard.tsx         # 首页仪表盘
        │   ├── workflow-detail.tsx   # 工作流详情页
        │   └── new-workflow.tsx      # 新建工作流页
        │
        ├── hooks/                    # 自定义 hooks
        │   ├── use-workflow.ts       # 工作流状态管理
        │   └── use-websocket.ts      # WebSocket 连接管理
        │
        ├── lib/                      # 工具函数
        │   ├── utils.ts              # 通用工具（cn 函数等）
        │   ├── graph-parser.ts       # Mermaid/图结构解析
        │   └── constants.ts          # 常量定义
        │
        └── styles/
            └── globals.css           # 全局样式覆盖
```

---

## 4. 页面设计

### 4.1 首页仪表盘 (`/`)

> **预览图**: [dashboard_preview.png](./image/dashboard_preview.png)

- 顶部：系统标题 + 快速提交入口
- 中部：最近运行列表（卡片式）
- 底部：统计概览（成功/失败/运行中数量）

### 4.2 工作流详情页 (`/workflow/:runId`)

> **预览图**: [workflow_detail_preview.png](./image/workflow_detail_preview.png)

三面板布局：

| 区域 | 组件 | 数据来源 |
|------|------|----------|
| 左栏 (45%) | DAG 图视图 | `GET /api/v1/workflow/{run_id}/graph` |
| 右上 (55%, 40%h) | 任务状态面板 | `GET /api/v1/workflow/{run_id}/status` |
| 右下 (55%, 60%h) | **Node Context Inspector** | `GET /api/v1/workflow/{run_id}/node/{node_id}/context` |

#### DAG 可视化规范

- **正交箭头**: 所有连线只允许水平或垂直方向，拐角为 90 度直角
- **并行泳道**: 同一 batch 内的并行节点水平并排，左侧标注 Parallel Batch 虚线边框
- **循环回路**: update 到 dispatch 的回路通过右侧正交路径绘制
- **条件分支**: dispatch 到 finalize 用虚线箭头标记

#### 节点状态色彩编码

| 颜色 | 状态 | 视觉效果 |
|------|------|----------|
| 灰色 `hsl(0 0% 35%)` | pending | 静态 |
| 蓝色 `hsl(217 91% 60%)` | dispatched (运行中) | 发光边框脉动 |
| 绿色 `hsl(142 71% 45%)` | accepted | 静态 |
| 红色 `hsl(0 84% 60%)` | blocked | 静态 |

#### Node Context Inspector（记忆透明）

点击 DAG 中任意节点后，右下面板展示该节点的**完整 chat 上下文**：

| Tab | 内容 | 说明 |
|-----|------|------|
| **Input** | 节点接收的 WorkflowState 快照 | 可折叠的 JSON 树 |
| **Output** | 节点返回的 state 变更 | 可折叠的 JSON 树 |
| **Prompt** | 发送给 Codex CLI 的完整 prompt 文本 | 语法高亮的代码块 |
| **Response** | Codex CLI 返回的完整结果 | 语法高亮的 JSON |

面板顶部显示面包屑导航：节点名 > 当前 Tab

这使得每个 Agent 节点的决策过程完全透明——用户可以检视任意节点收到了什么输入、生成了什么 prompt、收到了什么回复、产出了什么输出。

### 4.3 新建工作流页 (`/workflow/new`)

> **预览图**: [new_workflow_preview.png](./image/new_workflow_preview.png)

表单字段（严格对齐接口契约 `POST /api/v1/workflow/run`）：

| 字段 | 组件 | 必填 |
|------|------|------|
| 用户需求 | Textarea | ✅ |
| 仓库路径 | Input（默认 `.`） | ❌ |
| 沙箱模式 | Select | ❌ |
| 最大重试次数 | Number Input | ❌ |
| 模型覆盖 | Input | ❌ |
| 推理力度 | Select | ❌ |

提交后跳转到工作流详情页。

---

## 5. 组件设计

### 5.1 `dag-view.tsx` — DAG 图组件

**输入**: `nodes[]`, `edges[]`, `parallelBatches[]`（来自 `GET /graph`）
**渲染**: 自绘 SVG（dagre 布局 + 正交路由）或 React Flow + custom edge
**布局规则**:
- 使用 dagre 的 `rankdir: 'TB'` 自上而下布局
- 边路由使用正交（orthogonal）模式：所有线段只有水平/垂直两种方向
- 同一 batch 的并行节点设置相同 rank，确保水平并排
- 并行批次区域用虚线边框框选，左侧标注 batch ID

**交互**:
- 节点可点击，选中后触发 `onNodeSelect(nodeId)` 联动 Node Context Inspector
- 节点颜色随 task status 动态变化
- 运行中节点边框添加蓝色脉动动画
- 条件边（conditional edges）用虚线标记

### 5.2 `task-panel.tsx` — 任务状态面板

**输入**: `tasks[]`（来自 `GET /status` + WebSocket 更新）
**渲染**: 数据表格
**列**: task_id, title, status (badge), retries, dependencies
**交互**:
- 行可点击，联动 DAG 节点高亮和 Node Context Inspector
- 允许展开查看 allowed_paths

### 5.3 `node-context-inspector.tsx` — 节点上下文检查器 (NEW)

**输入**: `nodeId`（来自 DAG 节点选中或 task 行点击）
**数据来源**: `GET /api/v1/workflow/{run_id}/node/{node_id}/context`
**渲染**: Tab 面板
**Tabs**:

| Tab | 数据 | 渲染方式 |
|-----|------|----------|
| Input | 节点接收的 state 快照 | 可折叠 JSON 树 |
| Output | 节点返回的 state diff | 可折叠 JSON 树，变更字段高亮 |
| Prompt | 发送给 Codex 的完整 prompt | 等宽字体代码块，支持搜索 |
| Response | Codex 返回的完整 JSON | 语法高亮 JSON，支持搜索 |

**面包屑**: 顶部显示 `{node_name} > {当前 tab}` 导航
**空状态**: 未选中节点时显示 Click a node to inspect its context

### 5.4 `trace-timeline.tsx` — Trace 时间线

**输入**: `events[]`（来自 `GET /traces` + WebSocket 实时追加）
**渲染**: 垂直时间线
**交互**:
- 可按 node 和 phase 过滤
- 点击事件可展开完整 payload
- 点击事件联动 DAG 节点高亮

### 5.5 `workflow-form.tsx` — 工作流提交表单

**输入**: 无
**输出**: 调用 `POST /api/v1/workflow/run`
**校验**: 前端校验 request 非空，其余字段有默认值
**Reasoning Effort**: 使用分段控制器（Segmented Control）而非下拉，四选一

---

## 6. API 对接层

### 6.1 TypeScript 类型定义 (`api/types.ts`)

严格对齐 `api-contract.md` 中的响应结构：

```typescript
// 与接口契约 §3.2 对应
interface WorkflowStatus {
  run_id: string;
  status: 'queued' | 'running' | 'done' | 'blocked' | 'incomplete';
  created_at: string;
  finished_at: string | null;
  plan: {
    goal: string;
    tasks: TaskInfo[];
  };
}

interface TaskInfo {
  task_id: string;
  title: string;
  status: 'pending' | 'dispatched' | 'accepted' | 'blocked';
  retries: number;
  depends_on: string[];
  allowed_paths: string[];
}

// 与接口契约 §3.3 对应
interface GraphData {
  run_id: string;
  mermaid: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

// 与接口契约 §4.1 对应
interface WebSocketMessage {
  type: 'node_start' | 'node_end' | 'node_error' | 'workflow_complete';
  timestamp: string;
  data: TraceEvent;
}
```

### 6.2 HTTP 客户端 (`api/client.ts`)

```typescript
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1';

export async function submitWorkflow(req: WorkflowRunRequest): Promise<WorkflowRunResponse>;
export async function getWorkflowStatus(runId: string): Promise<WorkflowStatus>;
export async function getWorkflowGraph(runId: string): Promise<GraphData>;
export async function getWorkflowTraces(runId: string, params?: TraceQueryParams): Promise<TraceResponse>;
export async function getWorkflowHistory(params?: HistoryQueryParams): Promise<HistoryResponse>;
```

### 6.3 WebSocket 客户端 (`api/websocket.ts`)

```typescript
const WS_BASE = import.meta.env.VITE_WS_BASE || 'ws://localhost:8000/ws/v1';

export function connectWorkflowWS(
  runId: string,
  onMessage: (msg: WebSocketMessage) => void,
  onClose?: () => void,
): { close: () => void };
```

---

## 7. 设计风格

### 7.1 色彩体系

| 语义 | 色值 | 用途 |
|------|------|------|
| 背景主色 | `hsl(0 0% 3%)` | 极暗背景 |
| 卡片背景 | `hsl(0 0% 8%)` | 卡片 / 面板 |
| 边框 | `hsl(0 0% 15%)` | 分割线 |
| 文字主色 | `hsl(0 0% 95%)` | 主体文字 |
| 文字次色 | `hsl(0 0% 55%)` | 次要信息 |
| 状态-运行中 | `hsl(217 91% 60%)` | 蓝色 - dispatched |
| 状态-成功 | `hsl(142 71% 45%)` | 绿色 - accepted |
| 状态-失败 | `hsl(0 84% 60%)` | 红色 - blocked |
| 状态-等待 | `hsl(0 0% 35%)` | 灰色 - pending |
| 强调色 | `hsl(262 83% 58%)` | 紫色 - 主操作按钮 / 高亮 |

### 7.2 设计原则

- **极简主义**: 黑白为主，颜色只用于状态语义
- **信息密度**: 开发者工具风格，追求高密度信息展示
- **微动效**: 节点状态变更时轻量动画过渡（200ms ease-out）
- **响应式**: 最小宽度 1024px（桌面开发工具定位）

---

## 8. 开发节奏（前后端统一）

### Phase 0: 接口契约对齐 ⬅️ 当前阶段

| 任务 | 所有者 | 产出 | 依赖 |
|------|--------|------|------|
| 定义 REST API 契约 | 前后端共有 | `api-contract.md` | 无 |
| 定义 WebSocket 消息格式 | 前后端共有 | `api-contract.md` §4 | 无 |
| 定义 TypeScript 类型 | 前端 | 类型定义文档 | 契约文档 |
| 定义 Pydantic 模型 | 后端 | 模型定义文档 | 契约文档 |
| 生成 UI 预览图 | 前端 | `docs/plan/image/` | 无 |

**Phase 0 退出条件**: 三篇文档审阅通过 + 预览图确认

---

### Phase 1: 并行开发

```
┌──────────────────────────────────────────────────┐
│                  Phase 1 (并行)                   │
│                                                  │
│  ┌─────────────────┐   ┌──────────────────────┐  │
│  │    后端任务       │   │     前端任务          │  │
│  │                 │   │                      │  │
│  │ 1. core/ 迁移   │   │ 1. Vite 脚手架初始化  │  │
│  │ 2. models/ 定义  │   │ 2. shadcn/ui 配置    │  │
│  │ 3. routes/ REST │   │ 3. 页面路由搭建       │  │
│  │ 4. services/    │   │ 4. api/ 层实现        │  │
│  │ 5. app.py 入口  │   │ 5. 组件开发           │  │
│  └─────────────────┘   └──────────────────────┘  │
│                                                  │
│  【对接点】前端使用 Mock 数据开发，后端独立运行     │
│  【同步机制】api/types.ts 与 models/ 保持一致      │
└──────────────────────────────────────────────────┘
```

**Phase 1 内部串行关系**:

后端:
```
core/ 迁移 → models/ → routes/ → services/ → app.py
(1)          (2)       (3)       (4)          (5)
```

前端:
```
Vite 初始化 → shadcn/ui → 路由 → api/ 层 → 组件
(1)           (2)        (3)     (4)        (5)
```

**Phase 1 退出条件**:
- 后端: `uvicorn backend.app:app` 启动成功，所有 REST 端点返回正确格式
- 前端: `npm run dev` 启动成功，所有页面可用 Mock 数据渲染

---

### Phase 2: 联调集成（串行）

| 任务 | 前提 | 产出 |
|------|------|------|
| 前端切换到真实 API | 后端 REST 就绪 | HTTP 通信验证 |
| WebSocket 联调 | 后端 WS 就绪 + event_bus 实现 | 实时推送验证 |
| 端到端测试 | 上述两项完成 | 完整工作流可运行 |
| 预览图更新 | UI 稳定 | 最终版预览图 |

**Phase 2 退出条件**:
- 前端能通过 REST API 提交工作流并获取结果
- WebSocket 能实时推送节点状态变更
- DAG 视图能正确渲染并随状态动态更新

---

## 9. Mock 数据策略（Phase 1 前端用）

前端在后端未就绪时使用本地 Mock 数据开发：

```
frontend/src/
└── mocks/
    ├── workflow-status.json     # 模拟 GET /status 响应
    ├── graph-data.json          # 模拟 GET /graph 响应
    ├── trace-events.json        # 模拟 GET /traces 响应
    └── history.json             # 模拟 GET /history 响应
```

通过环境变量控制是否使用 Mock：

```typescript
const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';
```

---

## 10. 退出条件

前端重构完成的验收标准：

- [ ] `npm run dev` 启动无报错
- [ ] 三个页面均可正常渲染
- [ ] API 客户端函数签名与 `api-contract.md` 完全对齐
- [ ] WebSocket 客户端能建立连接并接收消息
- [ ] DAG 视图正确渲染节点和边
- [ ] 任务面板正确显示状态和依赖关系
- [ ] Trace 时间线正确显示事件流
- [ ] 设计风格符合 §7 定义

---

## 11. UI 预览图

UI 预览图位于 `docs/plan/image/` 目录下（v2 版本）：

| 页面 | 预览图路径 | 描述 |
|------|-----------|------|
| 仪表盘 | `image/dashboard_preview.png` | 运行卡片网格 + 进度条 + 统计栏 |
| 工作流详情 | `image/workflow_detail_preview.png` | 正交 DAG（并行泳道）+ Tasks 表 + Node Context Inspector |
| 新建工作流 | `image/new_workflow_preview.png` | 表单 + Segmented Control + 下拉菜单 |

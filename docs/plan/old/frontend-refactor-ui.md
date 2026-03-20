# 前端重构计划

> 契约文件：[api-contract.md](api-contract.md)
> 后端重构计划：[backend-refactor.md](backend-refactor.md)

---

## 一、重构范围

### 1.1 被替代的旧文件

| 文件 | 行数 | 说明 |
|------|------|------|
| `frontend/dashboard/app.js` | ~500 行 | 全局函数式 JS，DOM 直接操作 |
| `frontend/dashboard/style.css` | ~400 行 | 手写 CSS，暗色主题变量 |
| `frontend/dashboard/index.html` | ~120 行 | 内嵌 SVG DAG + 模板变量 |
| `frontend/trace_viewer/app.js` | 3 行 | 预留文件 |
| `frontend/trace_viewer/style.css` | ~200 行 | trace-viewer 静态样式 |
| `frontend/trace_viewer/index.html` | ~80 行 | 模板占位符注入 |

> `trace_viewer/` 的静态 HTML 导出功能由 `writers.py` 自包含生成，**不受前端重构影响**。

### 1.2 新前端项目位置

```
src/frontend/          ← 独立 Node.js 项目
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.ts
├── components.json    ← shadcn/ui 配置
├── index.html         ← SPA 入口
├── public/
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── ...
```

构建产物：`npm run build` → `src/agent_system_coding/frontend/dist/`

---

## 二、技术栈

| 类别 | 选型 | 版本 |
|------|------|------|
| 语言 | TypeScript | ~5.x |
| 框架 | React | 19.x |
| 构建 | Vite | 6.x |
| 样式 | Tailwind CSS | v4 |
| 组件库 | shadcn/ui | latest |
| 路由 | React Router | v7 |
| 状态 | React hooks (useState/useReducer) | — |
| 通信 | fetch + WebSocket | 原生 |

---

## 三、目标目录结构

```
src/frontend/src/
├── main.tsx                          # ReactDOM 入口
├── App.tsx                           # Router 配置
│
├── api/                              # 🔌 后端通信层
│   ├── client.ts                     # fetchJson() 封装
│   ├── ws.ts                         # WebSocket 连接管理 + 重连
│   └── types.ts                      # TypeScript 类型（来自 api-contract.md）
│
├── hooks/                            # 🎣 自定义 hooks
│   ├── use-runs.ts                   # 运行列表查询
│   └── use-snapshot.ts               # WebSocket 实时快照
│
├── components/                       # 🧩 UI 组件
│   ├── ui/                           # shadcn/ui 基础组件
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── badge.tsx
│   │   ├── textarea.tsx
│   │   └── ...
│   │
│   ├── layout/                       # 布局组件
│   │   ├── shell.tsx                 # 三栏 grid 主布局
│   │   └── sidebar.tsx               # 左侧边栏
│   │
│   ├── workflow-graph/               # DAG 可视化
│   │   ├── graph.tsx                 # SVG 容器 + 边路径计算
│   │   └── graph-node.tsx            # 单节点组件
│   │
│   ├── console/                      # Agent 控制台
│   │   ├── thread-list.tsx           # 对话列表
│   │   ├── thread-view.tsx           # 对话详情
│   │   └── message-bubble.tsx        # 消息气泡
│   │
│   ├── run-list.tsx                  # 运行列表
│   ├── new-run-form.tsx              # 新建运行表单
│   ├── task-card.tsx                 # 任务卡片
│   ├── batch-card.tsx                # 批次卡片
│   ├── timeline.tsx                  # 事件时间线
│   ├── node-detail.tsx               # 节点详情面板
│   └── artifact-list.tsx             # 产物列表
│
├── pages/                            # 📄 页面
│   ├── dashboard.tsx                 # 主仪表板
│   └── trace-viewer.tsx              # Trace 查看器
│
└── lib/                              # 🔧 工具
    ├── utils.ts                      # cn() 等
    └── constants.ts                  # 节点 ID 列表、边定义等
```

---

## 四、执行步骤（含并行/串行标注）

### 🔗 串行层 S1：项目脚手架（必须先完成）

```
S1.1 创建 Vite + React + TS 项目
     npx create-vite src/frontend --template react-ts
     
S1.2 安装 Tailwind CSS v4
     npm install tailwindcss @tailwindcss/vite
     配置 vite.config.ts 加入 tailwindcss plugin
     src/index.css 加入 @import "tailwindcss"
     
S1.3 初始化 shadcn/ui
     npx shadcn@latest init
     配置 components.json（路径别名、暗色主题）
     
S1.4 配置 vite.config.ts 代理
     /api → http://localhost:8080
     /ws  → ws://localhost:8080
     
S1.5 配置构建输出路径
     build.outDir → "../../agent_system_coding/frontend/dist"
```

> S1.1→S1.2→S1.3 必须串行；S1.4 和 S1.5 可在 S1.1 后并行。

---

### 🔀 并行层 P1：基础模块（依赖 S1）

以下模块互不依赖，**全部可并行**：

```
P1.1 api/types.ts
     从 api-contract.md 翻译所有 TypeScript interface
     
P1.2 api/client.ts  
     fetchJson<T>(url, options?) 泛型封装
     处理 !response.ok → throw
     
P1.3 api/ws.ts
     WebSocketManager class
     - connect(url) / disconnect()
     - onMessage callback
     - 指数退避自动重连 (1s → 2s → 4s → ... → 30s cap)
     
P1.4 lib/constants.ts
     NODE_IDS = ["plan", "dispatch", "execute_task", ...]
     NODE_EDGES 定义（from, to, anchors, shape）
     从现有 app.js nodeIds / nodeIncomingEdges 迁移

P1.5 lib/utils.ts
     cn() — clsx + tailwind-merge
     escapeHtml() — 迁移自现有 app.js
```

---

### 🔀 并行层 P2：Hooks（依赖 P1.1 + P1.2/P1.3）

```
P2.1 hooks/use-runs.ts
     - useRuns() → { runs, loading, refresh, createRun }
     - 内部用 2s 轮询 GET /api/runs（run 列表变化低频，轮询足够）

P2.2 hooks/use-snapshot.ts
     - useSnapshot(runId) → { snapshot, connected }
     - WebSocket 连接 /ws/runs/{runId}/snapshot
     - fallback: 如 WS 连不上，降级为 1s 轮询 GET snapshot
```

> P2.1 和 P2.2 互不依赖，**可并行**。

---

### 🔀 并行层 P3：UI 组件（依赖 S1.3 shadcn init）

以下组件互不依赖，**全部可并行**：

```
P3.1 安装 shadcn/ui 基础组件
     npx shadcn@latest add button card badge textarea scroll-area

P3.2 layout/shell.tsx
     三栏 grid 布局（sidebar 300px | workspace 1fr | detail 360px）
     响应式断点保持与现有 CSS @media 一致

P3.3 layout/sidebar.tsx
     包含 NewRunForm + RunList

P3.4 run-list.tsx
     接收 runs[] + selectedRunId + onSelect 回调
     迁移自 renderRuns()

P3.5 new-run-form.tsx
     Textarea + Button，提交调用 createRun()
     迁移自 index.html #prompt-input + #start-run

P3.6 task-card.tsx
     显示 task_id / status / retries / executor & reviewer buttons
     迁移自 renderTasks()

P3.7 batch-card.tsx
     显示 batch_id / task chips / node 路径
     迁移自 renderBatches()

P3.8 timeline.tsx
     事件列表，支持按 node 过滤
     迁移自 renderTimeline()

P3.9 artifact-list.tsx
     文件按钮列表 + 点击加载 artifact 内容
     迁移自 renderArtifacts() + openArtifact()

P3.10 node-detail.tsx
      选中节点的详细信息（status/phase/runs/tasks/events）
      迁移自 renderNodeDetail()
```

---

### 🔀 并行层 P4：复合组件（依赖 P3 部分基础组件）

```
P4.1 workflow-graph/graph.tsx + graph-node.tsx
     依赖: P1.4 (constants), P3.1 (shadcn badge)
     - SVG 容器，动态计算边路径
     - 节点状态着色 (idle/running/success/error/selected)
     - 点击节点 → onSelectNode 回调
     迁移自: index.html SVG + updateGraphEdges() + renderNodeStatuses()
     
P4.2 console/thread-list.tsx + thread-view.tsx + message-bubble.tsx
     依赖: P1.1 (types)
     - ThreadList: 对话侧栏，选中高亮
     - ThreadView: meta + message 列表 + diagnostics
     - MessageBubble: role-based 样式 (user/assistant/system)
     迁移自: renderThreads() + renderThreadView()
```

> P4.1 和 P4.2 互不依赖，**可并行**。

---

### 🔗 串行层 S2：页面组装（依赖 P2 + P3 + P4）

```
S2.1 pages/dashboard.tsx
     组装所有组件:
     - Shell 布局
     - Sidebar: NewRunForm + RunList
     - Workspace: WorkflowGraph + Console
     - DetailPane: NodeDetail + Tasks + Batches + Timeline + Artifacts
     状态管理:
     - selectedRunId, selectedNodeId, selectedConversationId
     - pinnedNode, pinnedConversation, artifactView
     迁移自: boot() + refreshRuns() + refreshSnapshot() 主循环

S2.2 pages/trace-viewer.tsx
     - 独立页面，接收 runId URL 参数
     - 复用 useSnapshot hook
     - 简化版 tasks + batches + timeline 展示

S2.3 App.tsx + Router
     / → Dashboard
     /trace/:runId → TraceViewer
```

> S2.1 和 S2.2 互不依赖，**可并行**。S2.3 依赖 S2.1 + S2.2。

---

### 🔗 串行层 S3：收尾（依赖 S2）

```
S3.1 验证 npm run dev + 后端联调
S3.2 验证 npm run build 产物正确输出到 dist/
S3.3 删除旧 frontend/dashboard/ 和 frontend/trace_viewer/ 目录
     (保留 frontend/__init__.py 的 trace-viewer 模板加载供 writers.py 使用)
```

---

## 五、依赖关系 DAG

```
S1.1 → S1.2 → S1.3 ──────────────────────────────┐
S1.1 → S1.4 (并行)                                │
S1.1 → S1.5 (并行)                                │
                                                   ▼
              ┌── P1.1 (types.ts)                  
              ├── P1.2 (client.ts)                 
              ├── P1.3 (ws.ts)          ← 全部可并行
              ├── P1.4 (constants.ts)              
              └── P1.5 (utils.ts)                  
                      │                            
          ┌───────────┼───────────────┐            
          ▼           ▼               ▼            
      P2.1 (runs)  P2.2 (snapshot)   P3.1~P3.10 (UI 组件) ← 三路并行
          │           │               │
          │           │    ┌──────────┤
          │           │    ▼          ▼
          │           │  P4.1 (graph) P4.2 (console) ← 可并行
          │           │    │          │
          ▼           ▼    ▼          ▼
        S2.1 (dashboard) ←─┘  S2.2 (trace-viewer) ← 可并行
                │                │
                ▼                ▼
              S2.3 (App.tsx + Router)
                │
                ▼
              S3 (验证 + 清理)
```

---

## 六、设计风格迁移

### 6.1 色彩系统

现有 CSS 变量 → Tailwind 自定义颜色：

```css
/* src/frontend/src/index.css */
@import "tailwindcss";

@theme {
  --color-bg: #09111b;
  --color-panel: #101a28;
  --color-panel-2: #0b1420;
  --color-panel-3: #0f1a29;
  --color-ink: #edf4fb;
  --color-muted: #90a3b8;
  --color-line: #223246;
  --color-line-2: #30445a;
  --color-accent: #6fdcff;
  --color-ok: #5be28f;
  --color-warn: #f3c26f;
  --color-bad: #ff7c7c;
  --color-idle: #506273;
  --color-bubble-user: #10283a;
  --color-bubble-assistant: #152735;
  --color-bubble-system: #241a1a;
}
```

### 6.2 shadcn/ui 组件映射

| 现有 UI 元素 | → shadcn/ui |
|-------------|-------------|
| `.panel` 卡片 | `<Card>` 自定义 dark variant |
| `.badge` | `<Badge>` |
| `.primary-button` | `<Button>` |
| `textarea` | `<Textarea>` |
| `.chip` | `<Badge variant="outline">` |
| `.run-item` / `.thread-item` | `<Card>` + hover 样式 |
| `.graph-card` 区域 | 自定义 `<WorkflowGraph>` |
| `.bubble` 消息 | 自定义 `<MessageBubble>` |

### 6.3 字体

保持 IBM Plex Sans / IBM Plex Mono，通过 `@fontsource` 或 CDN 引入。

---

## 七、验收标准

- [ ] `npm run dev` 启动无报错，HMR 正常
- [ ] 仪表板三栏布局渲染正确，暗色主题与旧版视觉一致
- [ ] 可创建新运行（POST /api/runs）
- [ ] 运行列表实时刷新
- [ ] 选中运行后 WorkflowGraph 节点状态正确着色
- [ ] 点击节点显示详情
- [ ] Console 对话列表可浏览，气泡消息正确渲染
- [ ] WebSocket 实时推送快照，无明显延迟
- [ ] 断线自动重连
- [ ] `npm run build` 产物位于 `src/agent_system_coding/frontend/dist/`
- [ ] FastAPI 生产模式能直接服务 dist/ 下的 SPA

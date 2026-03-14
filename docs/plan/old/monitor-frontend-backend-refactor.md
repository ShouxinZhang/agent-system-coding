# Monitor Frontend/Backend Separation Refactor Plan

这份文档回答三个业务问题：

1. 为什么当前 monitor/dashboard 重构后容易出现“页面能开，但前端失效”的问题
2. Python workflow/backend 与前端静态资源应该如何拆开，才能降低后续维护成本
3. 新前端应该继续使用原生 JS 三件套，还是切到 TypeScript + 组件化方案

## 当前症状

当前 monitor 已经出现过一次典型问题：

- Python HTTP server 能正常返回 HTML
- 但静态资源命名与服务端映射未对齐
- 结果是 CSS/JS 未加载，页面退化成裸 HTML

这说明当前结构虽然能跑，但前后端交付链路仍然过于脆弱：

- 页面模板、资源名、路由名靠人工同步
- 前端没有独立构建与发布边界
- 前端资产和 Python 包装逻辑耦合在一起
- 重构时很容易出现“后端能起，前端失效”的半故障状态

## 当前结构

当前实现的核心关系可以概括为：

```text
+-------------------------------------------------------------+
| agent-system-coding                                         |
|                                                             |
|  +---------------------+      imports/calls_api            |
|  | Python Backend      |--------------------------------+   |
|  |                     |                                |   |
|  | workflow.py         |                                |   |
|  | tracing.py          |                                |   |
|  | snapshot.py         |                                |   |
|  | server/http_handler |                                |   |
|  +---------------------+                                |   |
|                                                         |   |
|  +---------------------+                                |   |
|  | Embedded Frontend   |<-------------------------------+   |
|  |                     |    static asset lookup by name     |
|  | frontend/dashboard/ |                                    |
|  |   index.html        |                                    |
|  |   style.css         |                                    |
|  |   app.js            |                                    |
|  +---------------------+                                    |
+-------------------------------------------------------------+
```

这个结构的优点是起步快，单仓可直接运行。

缺点也很直接：

- 后端既负责业务，又负责页面模板拼装和静态资源定位
- 前端没有独立工程边界，无法形成稳定构建产物
- 页面规模一旦继续增长，纯 JS 文件会快速变成难维护状态

## 目标结构

建议将 monitor 相关能力拆成三个明确边界：

```text
+--------------------------------------------------------------------------------+
| agent-system-coding                                                            |
|                                                                                |
|  +---------------------------+        HTTP/JSON API        +----------------+  |
|  | Python Workflow Backend   |<--------------------------->| Monitor Web UI |  |
|  |                           |                             |                |  |
|  | backend/workflow          |                             | frontend/      |  |
|  | backend/tracing           |                             | monitor-app/   |  |
|  | backend/snapshot          |                             | src/...        |  |
|  | backend/server/runtime    |                             |                |  |
|  +---------------------------+                             +----------------+  |
|                ^                                                         |     |
|                | owns runtime/traces                                     |     |
|                |                                                         | build|
|                |                                                         v     |
|  +---------------------------+                                 +---------------------------+
|  | Runtime Artifacts         |                                 | Built Static Assets       |
|  | runtime/*/summary.json    |                                 | frontend/monitor-app/dist |
|  | runtime/*/traces/*.json   |                                 | index.html, assets/*      |
|  +---------------------------+                                 +---------------------------+
|                                                                                |
+--------------------------------------------------------------------------------+
```

目标不是为了“技术更先进”，而是为了提升三个业务结果：

- 可维护性：前端变更不再牵动 Python 包装层
- 可交付性：前端有稳定 build 产物，发布边界清晰
- 可扩展性：后续增加节点详情、过滤、搜索、回放等能力时，复杂度不会继续堆在单个 JS 文件里

## 技术决策

### 结论

新 monitor 前端应采用：

`TypeScript + React + Vite + 轻量组件化`

不建议继续沿用原生 JS 三件套作为长期方案。

### 为什么不是继续原生 JS

如果 monitor 只是一页静态展示，原生 JS 足够。

但当前页面已经同时包含这些联动能力：

- run 列表
- workflow graph 状态高亮
- thread 切换
- artifact 预览
- timeline 展示
- run 启动与轮询刷新

这类界面已经进入“状态密集型控制台”的范畴。继续使用原生 JS 的问题是：

- 状态流散在多个 DOM 操作函数中
- 字段改名、接口变动缺少静态保护
- 模块复用和测试成本持续升高

### 为什么是 TypeScript + React + Vite

- TypeScript
  - 降低 API 字段变更带来的回归风险
  - 对 snapshot、run、artifact 这些结构化数据提供明确约束

- React
  - 适合管理控制台型界面的多区域联动
  - 可以把 graph、run list、console、details 拆成独立组件

- Vite
  - 本地开发和静态构建都足够轻
  - 对当前仓库规模来说，进入成本低于更重的全家桶

- 轻量组件化
  - 只抽取必要基础组件和布局片段
  - 避免过早引入重型设计系统，影响改动效率

## 重构原则

1. 先恢复可用性，再进行结构升级
2. 保持 runtime 数据格式稳定，避免同时改 UI 和底层 trace 语义
3. 前后端通过 HTTP/JSON 契约协作，不共享隐式模板约定
4. 分阶段迁移，任一阶段都应保持 monitor 可运行

## 分阶段计划

### Phase 0. 止血修复

目标：恢复当前 dashboard 的可用性，避免影响 workflow 验证。

动作：

- 对齐 HTML 引用的静态资源名与 Python 资源映射
- 明确 static 资源命名规范
- 为 monitor 启动链路补一个最小 smoke check

交付标准：

- 页面不再退化为裸 HTML
- CSS 与 JS 能稳定加载
- 新 run 可以被成功发起并刷新状态

### Phase 1. 抽离前后端契约

目标：让 monitor UI 不再依赖 Python 直接拼装页面逻辑。

动作：

- 盘点现有 API
  - `GET /api/runs`
  - `GET /api/runs/{run_id}/snapshot`
  - `GET /api/runs/{run_id}/artifact?path=...`
  - `GET /api/runs/{run_id}/log`
  - `POST /api/runs`
- 为 run、snapshot、artifact、timeline 明确 JSON 字段契约
- 将“页面模板渲染职责”与“运行时数据服务职责”分开

交付标准：

- API 字段有明确文档
- 前端可以只依赖 API 自举，不依赖 Python 拼接动态 HTML 内容

### Phase 2. 新建独立前端工程

目标：把 monitor 从嵌入式静态片段升级为独立 web app。

建议目录：

```text
frontend/
  monitor-app/
    package.json
    tsconfig.json
    vite.config.ts
    src/
      app/
      components/
      features/
      lib/
      styles/
```

建议组件拆分：

- `RunLauncher`
- `RunList`
- `WorkflowGraph`
- `ConversationPanel`
- `NodeDetailPanel`
- `TaskListPanel`
- `BatchListPanel`
- `ArtifactPanel`
- `TimelinePanel`

交付标准：

- `frontend/monitor-app` 可独立开发和构建
- 构建产物可被后端托管
- 核心页面能力与旧版持平

### Phase 3. 切换后端托管方式

目标：后端只托管构建产物，不再理解前端源文件组织。

动作：

- Python server 从“按文件名读取内嵌模板”切到“托管 dist 目录”
- 静态资源引用由构建系统生成
- 前端路由和资源版本由前端构建结果决定

交付标准：

- 后端不再维护 `index.html/style.css/app.js` 这类手工资源表
- 发布路径稳定
- 资源名不一致导致的故障不再发生

### Phase 4. 下线旧嵌入式前端

目标：彻底清理历史包袱。

动作：

- 删除 Python 包内旧 dashboard 源文件和兼容层
- 更新 README、运行说明和架构文档
- 补齐 smoke test 与使用文档

交付标准：

- 前端唯一来源变为 `frontend/monitor-app`
- 后端职责仅剩 workflow、runtime、API、静态托管

## 模块边界建议

### Python Backend

负责：

- workflow 编排
- runtime artifact 读写
- trace 聚合
- snapshot 生成
- HTTP API
- 静态构建产物托管

不负责：

- 页面结构拼接
- 前端组件状态管理
- 样式与交互细节

### Frontend Monitor App

负责：

- 页面布局与交互
- 轮询与数据刷新策略
- graph、console、artifact 等模块化展示
- 用户输入体验

不负责：

- runtime 文件直接读写
- workflow 调度逻辑
- trace 原始格式定义

## 风险与约束

### 风险 1

如果在拆前端的同时改 runtime 数据结构，问题定位会变得困难。

控制方式：

- UI 拆分阶段保持 runtime JSON 结构稳定

### 风险 2

如果一次性切换全部页面，迁移期会失去可用监控面板。

控制方式：

- 新旧 monitor 并行一段时间
- 先让新前端接同一套 API

### 风险 3

如果组件化过度，前端工程会变成“搭框架”而不是交付工具。

控制方式：

- 只抽取稳定复用的基础组件
- 业务块优先按功能分层，而不是按 UI 框架模板分层

## 近期落地建议

建议按下面顺序推进：

1. 修复当前 monitor 静态资源映射问题
2. 冻结 monitor API 契约
3. 新建 `frontend/monitor-app`，使用 TypeScript + React + Vite
4. 完成旧页面关键能力平移
5. 切换 Python server 到 `dist/` 托管模式
6. 下线旧嵌入式 dashboard

## 一句话结论

这次重构的核心，不是“把 JS 改成 TS”。

真正要解决的是：

`让 Python 负责系统运行，让前端负责界面交互，让两者只通过稳定契约协作。`

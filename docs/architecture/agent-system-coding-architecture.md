# `src/agent_system_coding` 架构说明

## 1. 业务目标

`src/agent_system_coding` 是这个仓库的运行内核，目标是把“接收需求、拆解任务、调用 Codex 执行、复核结果、沉淀运行痕迹、提供本地可视化观察”串成一条可复用的自动化交付链路。

从业务角度看，它解决的是三件事：

1. 把自然语言需求转成可执行的开发任务。
2. 把任务执行过程沉淀成可追踪的运行资产，而不是一次性对话。
3. 给本地操作者一个可观察、可复盘、可重放的运行面板。

## 2. 总体结构

当前包可以分成四层：

1. 入口层
   - `cli.py`
   - `monitor.py`
2. 编排与执行层
   - `backend/workflow.py`
   - `backend/codex_cli.py`
   - `backend/prompts.py`
3. 运行资产层
   - `backend/tracing.py`
   - `backend/writers.py`
   - `backend/snapshot.py`
   - `backend/demo_repo.py`
   - `backend/server/runtime.py`
4. 展示层
   - `backend/server/http_handler.py`
   - `frontend/dashboard/*`
   - `frontend/trace_viewer/*`

另外还有两个历史兼容入口：

- `visualization.py`
- `monitor.py`

它们更多承担“当前功能还能跑”的职责，不是新的主编排中心。

## 3. 核心链路

系统的主链路如下：

1. 用户通过 `cli.py` 或 `monitor.py` 发起请求。
2. `backend/workflow.py` 使用 LangGraph 组织完整流程。
3. `backend/prompts.py` 为不同节点生成计划、执行、复核提示词。
4. `backend/codex_cli.py` 负责真正调用 `codex exec`。
5. `backend/tracing.py`、`backend/writers.py`、`backend/snapshot.py` 持续写入运行痕迹、摘要和可视化资产。
6. `backend/server/runtime.py` 从运行目录读取状态并组织成前端可消费的数据。
7. `backend/server/http_handler.py` 提供本地 HTTP 接口。
8. `frontend/dashboard` 和 `frontend/trace_viewer` 把运行状态展示出来。

这条链路的业务价值是：系统不是只给出“答案”，而是给出一整套“计划、执行、复核、产物、轨迹”的运行证据。

## 4. 模块职责

### 4.1 入口层

[`cli.py`](/home/wudizhe001/Documents/GitHub/agent-system-coding/src/agent_system_coding/cli.py)

- 面向脚本化调用。
- 接收用户请求、仓库路径、运行目录、schema、sandbox、模型参数。
- 适合批处理、CI、脚本集成。

[`monitor.py`](/home/wudizhe001/Documents/GitHub/agent-system-coding/src/agent_system_coding/monitor.py)

- 面向本地交互观察。
- 启动 Dashboard 服务。
- 适合本地演示、调试和运行复盘。

### 4.2 编排与执行层

[`backend/workflow.py`](/home/wudizhe001/Documents/GitHub/agent-system-coding/src/agent_system_coding/backend/workflow.py)

- 是系统的业务中枢。
- 定义 `plan -> dispatch -> execute_task -> dispatch_reviews -> review_task -> update -> finalize` 的工作图。
- 决定并发批次、重试次数、任务状态流转和最终收口逻辑。

[`backend/codex_cli.py`](/home/wudizhe001/Documents/GitHub/agent-system-coding/src/agent_system_coding/backend/codex_cli.py)

- 是外部执行适配器。
- 把内部任务转换成 `codex exec` 命令。
- 负责写结构化输出和转录文件。

[`backend/prompts.py`](/home/wudizhe001/Documents/GitHub/agent-system-coding/src/agent_system_coding/backend/prompts.py)

- 负责把业务意图翻译成不同节点所需的提示词。
- 决定 planner、executor、reviewer 三类 agent 的输入边界。

### 4.3 运行资产层

[`backend/tracing.py`](/home/wudizhe001/Documents/GitHub/agent-system-coding/src/agent_system_coding/backend/tracing.py)

- 负责节点级 trace 留痕。
- 保证每个关键节点都有机器可读的开始/结束记录。

[`backend/writers.py`](/home/wudizhe001/Documents/GitHub/agent-system-coding/src/agent_system_coding/backend/writers.py)

- 负责把运行中间态写成文件资产。
- 包括图、报告、查看器页面等。

[`backend/snapshot.py`](/home/wudizhe001/Documents/GitHub/agent-system-coding/src/agent_system_coding/backend/snapshot.py)

- 负责从运行目录恢复状态快照。
- 为 Dashboard 和 Trace Viewer 提供可回放输入。

[`backend/demo_repo.py`](/home/wudizhe001/Documents/GitHub/agent-system-coding/src/agent_system_coding/backend/demo_repo.py)

- 负责生成演示用仓库和默认 prompt。
- 方便系统自测和 smoke test。

[`backend/server/runtime.py`](/home/wudizhe001/Documents/GitHub/agent-system-coding/src/agent_system_coding/backend/server/runtime.py)

- 是监控端的运行管理器。
- 负责创建 run、读取 run、拉取 artifact、读取日志。
- 把底层文件系统状态整理成前端需要的接口数据。

### 4.4 展示层

[`backend/server/http_handler.py`](/home/wudizhe001/Documents/GitHub/agent-system-coding/src/agent_system_coding/backend/server/http_handler.py)

- 是本地监控服务的 HTTP 边界。
- 暴露 run 列表、snapshot、artifact、log 等接口。
- 同时负责静态资源分发。

[`frontend/dashboard`](/home/wudizhe001/Documents/GitHub/agent-system-coding/src/agent_system_coding/frontend/dashboard)

- 面向操作者的主控台。
- 解决“当前有哪些 run、状态如何、从哪里继续看”的问题。

[`frontend/trace_viewer`](/home/wudizhe001/Documents/GitHub/agent-system-coding/src/agent_system_coding/frontend/trace_viewer)

- 面向深度排障和复盘。
- 解决“单个 run 的节点轨迹、任务批次、产物之间怎么关联”的问题。

## 5. 依赖关系

从主依赖方向看：

- `cli.py` 依赖 `backend/workflow.py`
- `monitor.py` 依赖 `backend/server/http_handler.py` 和 `backend/server/runtime.py`
- `backend/workflow.py` 依赖：
  - `backend/codex_cli.py`
  - `backend/prompts.py`
  - `backend/tracing.py`
  - `backend/writers.py`
- `backend/server/http_handler.py` 依赖：
  - `backend/server/runtime.py`
  - `frontend/__init__.py`
- `backend/server/runtime.py` 依赖：
  - `backend/demo_repo.py`
  - `backend/snapshot.py`
- `frontend/__init__.py` 依赖：
  - `backend/demo_repo.py`

这说明当前系统的中心依赖点主要有两个：

1. `backend/workflow.py`
2. `backend/server/runtime.py`

前者决定执行逻辑，后者决定监控视角下的数据组织。

## 6. 当前架构特点

优势：

- 主业务链路清晰，适合做自动化执行与复盘。
- LangGraph 编排与本地监控已经打通，不是黑盒调用。
- 运行资产按目录沉淀，利于追责、演示和回归验证。

风险：

- `workflow.py` 责任较重，既管流程图，也管任务状态和文件输出协同。
- `server/runtime.py` 同时承担运行创建、状态恢复、日志读取，聚合度偏高。
- `frontend/__init__.py` 依赖 `backend/demo_repo.py`，说明前后端边界仍有轻度耦合。
- `visualization.py` 仍在包根目录，说明旧可视化入口尚未完全收口到新结构。

## 7. 建议的 Draw.io 出图范围

如果用 `drawio-arch-diagram-cli` skill 画这块架构图，建议只画下面这些节点，先把业务协作关系讲清楚：

### 7.1 节点

- 用户 / 操作者
- CLI 入口
- Monitor 入口
- Workflow Orchestrator
- Codex CLI Adapter
- Prompt Builder
- Trace & Writers
- Snapshot / Runtime Store
- HTTP Handler
- Dashboard UI
- Trace Viewer UI
- Demo Repo / Target Repo

### 7.2 连线

- 用户 -> CLI 入口
- 用户 -> Monitor 入口
- CLI 入口 -> Workflow Orchestrator
- Monitor 入口 -> HTTP Handler
- Workflow Orchestrator -> Prompt Builder
- Workflow Orchestrator -> Codex CLI Adapter
- Workflow Orchestrator -> Trace & Writers
- Workflow Orchestrator -> Demo Repo / Target Repo
- Trace & Writers -> Snapshot / Runtime Store
- Snapshot / Runtime Store -> HTTP Handler
- HTTP Handler -> Dashboard UI
- HTTP Handler -> Trace Viewer UI

### 7.3 图类型建议

- 第一张图：系统上下文图
  - 目标：让人一眼看懂“谁发起、谁执行、谁存档、谁展示”
- 第二张图：后端执行依赖图
  - 目标：突出 `workflow.py` 与 `runtime.py` 两个中心模块

## 8. 结合当前 Draw.io Skill 的落地方式

建议按下面的仓库产物命名：

- 源文件：`docs/architecture/agent-system-coding-overview.drawio`
- 预览图：`docs/architecture/agent-system-coding-overview.drawio.svg`
- 文档引用：

```md
![agent_system_coding 架构总览](./agent-system-coding-overview.drawio.svg)
```

实际预览：

![agent_system_coding 架构总览](./agent-system-coding-overview.drawio.svg)

当前仓库里的 draw.io skill 已经支持这条链路：

- skill 文件：[`SKILL.md`](/home/wudizhe001/Documents/GitHub/agent-system-coding/.agents/skills/drawio-arch-diagram-cli/SKILL.md)
- CLI 包装脚本：[`drawio-wrapper`](/home/wudizhe001/Documents/GitHub/agent-system-coding/.agents/skills/drawio-arch-diagram-cli/scripts/drawio-wrapper)

在这台机器上的实测结论是：

- SVG 适合作为默认 Markdown 预览格式。
- PNG 可以导出，也能在浏览器里显示，但严格校验会出现 CRC 警告。

## 9. 下一步建议

如果继续推进，优先顺序建议是：

1. 先按本文件第 7 节画一张总览图。
2. 再单独画一张后端执行依赖图。
3. 最后把 `workflow.py` 和 `server/runtime.py` 的责任边界拆得更清楚。

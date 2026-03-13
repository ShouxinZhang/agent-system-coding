# Agent Cache: 前后端分离重构 Plan

> 缓存时间: 2026-03-14T00:37:11+08:00

## 已执行的重构

### 1. modular-arch 技能

新增 `.agents/skills/modular-arch/`，基于 SQLite 的模块依赖图管理工具：
- 3 张表：`modules`（注册）、`dependencies`（有向依赖边）、`interfaces`（接口契约）
- 8 个 CLI 子命令：register / depend / undepend / interface / show / graph / check / parallel
- 跨层违规规则：`backend→frontend` ❌、`infra→backend` ❌、任意→`shared` ✅

### 2. 前后端分离目录结构

```
src/agent_system_coding/
├── __init__.py
├── cli.py                      → backend.workflow
├── monitor.py                  → backend.server
├── visualization.py            → 兼容转发层
├── backend/
│   ├── workflow.py             (LangGraph 工作流引擎)
│   ├── codex_cli.py            (Codex CLI 调用)
│   ├── prompts.py              (Prompt 模板)
│   ├── tracing.py              (执行轨迹记录)
│   ├── snapshot.py             (数据采集，从 visualization 拆出)
│   ├── writers.py              (文件写入，从 visualization 拆出)
│   ├── demo_repo.py            (演示仓库初始化)
│   └── server/
│       ├── http_handler.py     (HTTP 路由)
│       └── runtime.py          (运行时管理)
└── frontend/
    ├── __init__.py             (资源定位器)
    ├── dashboard/
    │   ├── index.html
    │   ├── style.css
    │   └── app.js
    └── trace_viewer/
        ├── index.html          (从 Python f-string 剥离)
        ├── style.css
        └── app.js
```

### 3. 接口契约

前后端通过 **snapshot JSON** 解耦：
- 后端 `backend/snapshot.py` 产出 `load_runtime_snapshot(runtime_dir) -> dict`
- 前端 `frontend/trace_viewer/` 消费该 JSON 渲染 UI
- 静态导出：`writers.py` 将 JSON 注入 HTML 模板占位符
- Live 模式：JS 通过 `fetch('/api/runs/:id/snapshot')` 定时拉取

### 4. AGENTS.md 新增规则

- `workspace-docs` 技能管理节点说明（WHAT）
- `modular-arch` 技能管理模块依赖关系（HOW）

## 备份位置

旧文件备份在 `/tmp/agent-system-coding-backup/`

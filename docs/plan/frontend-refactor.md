# 监控仪表板重构计划 — 总览

> 日期：2026-03-14
> 状态：Draft

---

## 分文档索引

| 文档 | 职责 | 执行者 |
|------|------|--------|
| [api-contract.md](api-contract.md) | 前后端唯一耦合点：REST + WebSocket 接口契约 & TypeScript 类型定义 | 前后端共同遵守 |
| [backend-refactor.md](backend-refactor.md) | Python 后端重构：BaseHTTPRequestHandler → FastAPI + WebSocket | 后端 subagent |
| [frontend-refactor-ui.md](frontend-refactor-ui.md) | 前端重构：原生 JS/CSS → Vite + React + TS + Tailwind + shadcn/ui | 前端 subagent |

---

## 现状问题

| 问题 | 影响 |
|------|------|
| 原生 JS + 手写 CSS ~1000 行 | 无组件化，可维护性差 |
| BaseHTTPRequestHandler | 无异步、无中间件、路由靠字符串匹配 |
| 前后端耦合发布 | frontend/__init__.py 负责模板替换和静态文件服务 |
| 1s 轮询模式 | 浪费带宽，延迟高 |
| 零类型安全 | 前端 JS 无类型，API 契约隐式 |

## 目标技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python + FastAPI + uvicorn + WebSocket |
| 前端 | TypeScript + React + Vite + Tailwind v4 + shadcn/ui |
| 通信 | REST + WebSocket（替代轮询） |

## 不变的核心

workflow.py / codex_cli.py / prompts.py / tracing.py / snapshot.py / writers.py / demo_repo.py / cli.py — 全部保持不变。

## 并行执行策略

```
                api-contract.md (先制定)
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
   后端 subagent               前端 subagent
   (backend-refactor.md)       (frontend-refactor-ui.md)
          │                         │
          ▼                         ▼
   FastAPI + WS 就绪           Vite + React 就绪
          │                         │
          └────────────┬────────────┘
                       ▼
                  联调 + 验收
```

两个 subagent 可完全并行工作，唯一同步点是 `api-contract.md` 中的接口定义。各自文档内部也标注了哪些步骤可并行、哪些必须串行（见文档中的 DAG 图）。

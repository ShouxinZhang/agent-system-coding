---
name: session-log
description: '记录 Agent 会话日志。捕获用户原始 prompt、LLM 理解摘要和执行上下文摘要，用于追溯和复盘。'
---

# Session Log 会话日志管理

基于 **Markdown 文件 + SQLite** 双轨存储的 Agent 会话日志工具。

- 日志以 `.md` 文件写入 `docs/session-logs/`（人类可读、可 Git 追踪）。
- 写入 MD 的同时自动同步到 `docs/session_log.db`（程序化检索）。
- 手动编辑 MD 后可用 `sync` 命令重建 DB。

## When to use this skill?
1. **每次会话开始时**: 用 `start` 记录用户的原始 prompt 和 LLM 对需求的理解。
2. **会话结束时**: 用 `finish` 补充执行上下文摘要、涉及的文件和最终状态。
3. **复盘 / 追溯时**: 用 `show` 查看 MD 原文，`list`/`search` 从 DB 快速检索。
4. **手动编辑 MD 后**: 用 `sync` 将 MD 变更同步到 DB。

## Markdown 日志格式

每个 session 生成一个 `docs/session-logs/<session_id>.md`，结构如下：

```markdown
---
session_id: 20260314-a34418a4
status: completed
tags: refactor,modular
started_at: 2026-03-14T00:59:20
finished_at: 2026-03-14T01:05:30
---

# Session: 20260314-a34418a4

## Prompt

帮我把 visualization.py 拆分成模块化结构

## Understanding

用户希望将 visualization.py 按职责拆分为独立子模块

## Summary

创建了 chart_builder.py, layout_engine.py, theme_manager.py 三个模块

## Related Files

- `src/chart_builder.py`
- `src/layout_engine.py`
```

## How to use (Execution)

所有操作通过 [session_log.py](./scripts/session_log.py) 脚本完成。

### 1. 开始会话 (Start)
创建 MD 文件并同步到 DB，返回 session_id：
```bash
python3 .agents/skills/session-log/scripts/session_log.py start \
  --prompt "用户的原始输入" \
  --understanding "LLM 对 prompt 的简要理解" \
  --tags "refactor,modular"
```

### 2. 完成会话 (Finish)
更新 MD 文件的摘要和状态，同步到 DB：
```bash
python3 .agents/skills/session-log/scripts/session_log.py finish <session_id> \
  --summary "执行上下文摘要" \
  --files "src/a.py,src/b.py" \
  --status completed
```

### 3. 查看会话详情 (Show)
优先展示 MD 原文，无 MD 文件时回退到 DB：
```bash
python3 .agents/skills/session-log/scripts/session_log.py show <session_id>
```

### 4. 列出最近会话 (List)
```bash
python3 .agents/skills/session-log/scripts/session_log.py list --limit 10
```

### 5. 搜索会话 (Search)
按标签、状态、时间范围或关键词过滤：
```bash
python3 .agents/skills/session-log/scripts/session_log.py search \
  --tag "refactor" --status completed --since "2026-03-01"
```

### 6. 同步 MD → DB (Sync)
手动编辑 MD 文件后，重新解析并更新 DB：
```bash
python3 .agents/skills/session-log/scripts/session_log.py sync
```

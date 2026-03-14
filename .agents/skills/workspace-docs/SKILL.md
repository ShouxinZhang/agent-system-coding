---
name: workspace-docs
description: '管理和读取工作区目录文档。使用该技能可了解文件/目录用途、读取 agent 专用备注，或在创建/修改文件后更新文档。'
---

# Workspace Docs Management

这个技能提供了一个基于 SQLite 的工具，用于记录和查询项目中各文件与目录的用途，以及 agent 专用备注。

- 模板数据库位于 `workspace-docs/workspace_docs.db`。
- 实际运行时写入位于仓库根目录的 `docs/workspace_docs.db`。
- 不再生成 `WORKSPACE_MAP.md`，以避免维护一份重复的 Markdown 总览。

## When to use this skill?
1. **Exploring the project**: 当你不清楚某个文件的作用，或想在修改前了解注意事项时使用。
2. **After modifying/creating files**: 当你新建文件或对现有文件做了重要重构后，你 **MUST** 使用该技能更新文档。

## How to use (Execution)
所有操作都通过运行 [agent_docs.py](./scripts/agent_docs.py) 脚本完成。

## Documentation policy

这个技能管理的是“高价值仓库说明”，不是文件系统的全量镜像。

- `scan` 会遵守 `.gitignore`，默认跳过被忽略的路径。
- 对 `docs/session-logs/`、`docs/plan/image/`、`.agent_cache/`、`runtime/` 这类批量归档或运行时目录，仅维护目录级说明，不要求逐文件写描述。
- 对代码、配置、架构说明等关键文本文件，要求可在 DB 中快速 CRUD 到描述；重点覆盖 `src/`、`schemas/`、技能脚本与关键仓库入口文件。
- 图片、数据库、日志、缓存等低价值或生成型文件不进入文件级说明范围。

### 1. Query Documentation (Read)
想了解 `src/db.py` 的作用：
`python3 .agents/skills/workspace-docs/scripts/agent_docs.py get "src/db.py"`

### 2. Update/Add Documentation (Create/Update)
在创建或修改文件后，记录对应文档信息：
`python3 .agents/skills/workspace-docs/scripts/agent_docs.py set "src/new_file.py" -d "Short description" -n "Notes for the Agent"`

### 3. Deprecated Export Compatibility (Export)
`export` 命令仅保留兼容性，不再生成 Markdown 文件：
`python3 .agents/skills/workspace-docs/scripts/agent_docs.py export`

### 4. Scan Workspace (Scan)
扫描工作区中未文档化的文件，并将其加入数据库：
`python3 .agents/skills/workspace-docs/scripts/agent_docs.py scan`

### 5. Audit Managed Gaps (Audit)
找出按策略应有说明、但仍缺少有效描述的目录和文件：
`python3 .agents/skills/workspace-docs/scripts/agent_docs.py audit`

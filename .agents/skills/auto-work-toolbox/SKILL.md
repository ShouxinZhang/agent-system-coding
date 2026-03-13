---
name: auto-work-toolbox
description: '自动工作工具箱入口。用于按需加载架构设计、重构迁移、质量门禁和会话留痕能力；默认只读取本入口，再根据任务打开对应 references 或下游 skill。'
---

# Auto Work Toolbox 自动工作工具箱

这个技能是自动工作的导航层，不承载所有细节。

目标：
- 先判断任务属于哪类工作
- 只加载当前任务需要的说明
- 把具体动作委托给对应 skill

## 何时使用

1. 需要为一个开发任务决定先做哪些动作。
2. 需要在多个工程技能之间按需切换，而不是一次加载全部规则。
3. 需要统一“设计、实施、校验、留痕”的工作入口。

## 默认规则

先读本文件，不要默认展开整个工具箱。

然后按任务类型加载对应资料：
- 架构设计或模块边界调整：读 `references/routing.md` 中的架构段落，并使用 `modular-arch`
- 大规模重构或迁移：读 `references/routing.md` 中的重构段落，并使用 `refactor-migration`
- 代码修改完成后的质量校验：读 `references/routing.md` 中的质量段落，并使用 `python-quality-gate`
- 需要会话留痕或复盘：读 `references/routing.md` 中的日志段落，并使用 `session-log`

如果任务跨多个阶段，再读 `references/stage-playbook.md`，按阶段组合使用多个工具。

## 快速路由

可以用脚本快速得到建议路由：

```bash
python3 .agents/skills/auto-work-toolbox/scripts/route_task.py \
  --task "把订单模块重构为新架构并补质量校验"
```

这个脚本只负责给出建议，不替代判断。

## 约束

- 这是工具箱，不是大一统流程文档
- 不要一次性加载全部 references
- 不要复制下游 skill 的完整说明到这里
- 当下游 skill 已经能解决问题时，直接委托给下游 skill

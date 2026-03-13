# Stage Playbook

这个文件只在任务跨多个阶段时读取。

## 阶段 1：启动

- 如果需要留痕，先使用 `session-log` 记录任务背景
- 如果任务是重构，先确认是否需要冻结旧基线

## 阶段 2：设计

- 模块新增、依赖调整、接口设计，使用 `modular-arch`
- 大规模重构，先用 `refactor-migration` 定义 old/new/migration plan

## 阶段 3：实施

- 按设计结果修改代码
- 如果是重构，持续维护 `migration_plan.md`

## 阶段 4：校验

- Python 改动完成后，使用 `python-quality-gate`
- 涉及新模块或依赖变化时，再执行一次 `modular-arch` 的 `check`

## 阶段 5：收口

- 如果需要追溯，使用 `session-log` 记录最终摘要
- 如果是重构，确认迁移状态、退出条件和旧模块下线条件

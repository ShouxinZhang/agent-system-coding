# Graph Coding System 方案草案

最小可实现版本见 [mvp.md](/home/wudizhe001/Documents/GitHub/agent-system-coding/docs/plan/mvp.md)。

## 目标

这个系统的目标是把软件开发过程收敛成一个可编排、可审查、可回滚的状态机。

整体流程是：

`用户请求 -> 规划 -> 派发 -> 执行 -> 审查 -> 修复或通过 -> 下一任务 -> 全局验收`

## 精简算法

### 1. 根节点 Agent 生成 Plan

用户输入需求后，根节点 agent 先生成一个 DAG 形式的计划，而不是普通步骤列表。

每个任务至少包含这些字段：

- `task_id`：任务唯一标识
- `goal`：任务目标
- `depends_on`：依赖的前置任务
- `parallel_group`：可并行执行的分组
- `allowed_paths`：允许修改的文件范围
- `expected_outputs`：预期产物
- `acceptance_criteria`：验收标准
- `required_checks`：必须通过的检查
- `retry_budget`：最多可重试次数

Plan 只有在两种条件都满足时才算有效：

- 依赖关系清晰
- 并行任务之间不存在写入路径冲突

### 2. Dispatcher 生成规范化任务文档

Plan 生成后，dispatcher 为当前可执行任务生成标准化派遣文档。

派遣文档必须明确说明：

- subagent 具体要做什么
- 可以修改哪些文件
- 必须产出哪些结果
- 必须通过哪些测试或检查
- 最终按什么标准判定成功

### 3. Scheduler 调度可执行任务

scheduler 只挑选已经满足依赖的任务。

- 串行任务必须等待前置任务完成
- 并行任务只有在写入范围不重叠时才允许同时执行

### 4. Executor Subagents 执行任务

每个 executor subagent 一次只处理一个任务，并产出标准结果：

- 代码改动或 patch
- 任务执行报告
- 本地检查结果

executor 只负责执行，不负责宣布任务最终成功。

### 5. Review Agent 做门禁检查

review agent 用四层门禁判断任务是否真正完成：

1. `Artifact gate`
   检查要求的产物是否存在、是否可解析
2. `Scope gate`
   检查改动文件是否严格落在 `allowed_paths` 内
3. `Check gate`
   检查规定的测试、lint、type check 是否通过
4. `Review gate`
   检查任务是否满足 `acceptance_criteria`

只有四层门禁全部通过，任务才算 accepted。

### 6. 失败任务进入回路

如果 review 没通过，任务进入修复回路：

- 任务状态标记为 `review_failed`
- 把失败原因写回任务报告
- 如果还有 `retry_budget`，则重新执行
- 如果没有剩余重试次数，则交给根节点 agent 重规划或升级处理

这样可以避免无限循环，也能保证卡住的任务被显式处理。

### 7. 状态机定义

单个任务的主状态流转如下：

`pending -> ready -> running -> self_checked -> accepted`

如果审查失败，则进入：

`pending -> ready -> running -> self_checked -> review_failed -> rework -> running`

只有在以下条件全部满足时，整个系统才算完成：

- Plan 中所有任务都已 accepted
- 集成检查通过
- 最终验收条件通过

## 核心判定原则

subagent 是否“完成得好”，不能靠主观描述，而必须靠机器可验证的契约。

也就是说，任务成功必须同时依赖：

- 明确的任务输入契约
- 明确的可修改范围
- 明确的必过检查
- reviewer 按验收标准复核
- 失败后可重试、可重规划

而不能只靠 agent 自己声称“我已经完成了”。

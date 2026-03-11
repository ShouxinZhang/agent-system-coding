# Graph Coding System MVP

## 目标

这份文档只回答一个问题：

第一版最少做什么，才能让整个 graph coding system 真正跑起来。

MVP 不追求完整能力，只追求闭环：

`用户提需求 -> 生成计划 -> 执行一个或多个任务 -> review 验收 -> 全部完成`

## MVP 范围

第一版只做四个角色：

- `root_agent`：接收用户请求，生成 plan
- `dispatcher`：把 plan 中的 ready task 转成任务文档
- `executor`：执行具体编码任务
- `reviewer`：检查任务是否真的完成

第一版先不做这些能力：

- 动态技能生成
- 多层 reviewer
- 自动代码合并策略优化
- 复杂的人机协同审批
- 超长任务的跨轮次记忆优化

## MVP 的最小闭环

### Step 1. 用户输入需求

输入示例：

`为项目新增一个 /health HTTP 接口，并补充基础测试`

### Step 2. root_agent 生成 plan

第一版 plan 不需要太复杂，只要支持串行和并行即可。

最小字段如下：

- `task_id`
- `goal`
- `depends_on`
- `allowed_paths`
- `acceptance_criteria`
- `required_checks`
- `status`

示例：

```json
{
  "request": "为项目新增一个 /health HTTP 接口，并补充基础测试",
  "tasks": [
    {
      "task_id": "task_api_health",
      "goal": "实现 /health 接口并返回 200",
      "depends_on": [],
      "allowed_paths": ["src/", "server/"],
      "acceptance_criteria": [
        "存在 /health 路由",
        "返回状态码 200",
        "返回体包含 ok"
      ],
      "required_checks": ["npm test"],
      "status": "ready"
    },
    {
      "task_id": "task_test_health",
      "goal": "补充 /health 接口测试",
      "depends_on": ["task_api_health"],
      "allowed_paths": ["test/", "tests/"],
      "acceptance_criteria": [
        "存在 /health 测试",
        "测试覆盖成功响应"
      ],
      "required_checks": ["npm test"],
      "status": "pending"
    }
  ]
}
```

### Step 3. dispatcher 生成任务文档

dispatcher 只处理 `status=ready` 的任务，并生成一个任务派遣文档。

最小字段如下：

- `task_id`
- `goal`
- `input_context`
- `allowed_paths`
- `acceptance_criteria`
- `required_checks`

这个文档直接给 executor 使用，不需要再做复杂格式。

### Step 4. executor 执行任务

executor 收到任务文档后，完成编码，并输出三个结果：

- 改动后的代码
- 一个执行报告
- 一个本地检查结果

第一版不强制要求独立 workspace，但必须记录改动了哪些文件。

### Step 5. reviewer 做验收

reviewer 不重新定义需求，只按任务文档检查。

第一版只做三个检查：

1. 改动文件是否超出 `allowed_paths`
2. `required_checks` 是否通过
3. `acceptance_criteria` 是否满足

如果都通过，则该 task 状态改为 `accepted`。

如果没通过，则该 task 状态改为 `review_failed`，并记录失败原因。

### Step 6. scheduler 推进下一任务

当某个任务 accepted 后，scheduler 检查是否有依赖已满足的新任务可转为 `ready`。

如果有，就继续派发。

如果全部任务都 accepted，则整个任务完成。

## MVP 的最小状态机

第一版每个任务只需要这几个状态：

- `pending`
- `ready`
- `running`
- `review_failed`
- `accepted`

流转规则：

`pending -> ready -> running -> accepted`

或者：

`pending -> ready -> running -> review_failed -> ready -> running`

第一版先限制每个任务最多重试 2 次。超过后直接标记为 `blocked`，交给 root_agent 重规划。

## MVP 的最小文件结构

建议第一版直接固定落盘结构：

```text
runtime/
  plan.json
  tasks/
    task_api_health.dispatch.json
    task_api_health.result.json
    task_api_health.review.json
    task_test_health.dispatch.json
    task_test_health.result.json
    task_test_health.review.json
```

含义如下：

- `plan.json`：整个请求的任务计划
- `*.dispatch.json`：派遣给 executor 的任务说明
- `*.result.json`：executor 的执行结果
- `*.review.json`：reviewer 的验收结果

## MVP 的成功标准

如果第一版满足下面四点，就算成功：

1. 用户输入一个需求后，系统能生成 `plan.json`
2. 系统能按依赖顺序派发任务
3. executor 完成任务后，reviewer 能给出通过或拒绝
4. 全部任务通过后，系统能明确输出 `done`

## 第一版不要过度设计的地方

下面这些内容先不要做，否则很容易把 MVP 做成框架工程：

- 不要先做通用插件系统
- 不要先做复杂 DAG 可视化
- 不要先做太多 agent 角色
- 不要先做自动生成一堆 skills
- 不要先做分布式调度

先把单机、本地仓库、单个请求跑通，这才是第一版。

## 一句话定义

MVP 本质上就是一个能跑通的任务闭环：

`Plan -> Dispatch -> Execute -> Review -> Next -> Done`

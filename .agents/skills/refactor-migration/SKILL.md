---
name: refactor-migration
description: '用于大规模重构。冻结 old db 作为基线观察，使用 new db 持续建设新结构，并通过 migration_plan.md 管理旧模块到新模块的迁移设计、进度和退出条件。'
---

# Refactor Migration 大规模重构技能

这个技能用于处理“需要一边对照旧系统，一边建设新系统”的重构任务。

业务目标只有三个：
- 保留旧系统认知：冻结 `old db`，作为重构前基线
- 约束新系统建设：所有新结构只写入 `new db`
- 管住迁移过程：用 `migration_plan.md` 跟踪承接关系、状态和退出条件

## 何时使用

1. 需要对整体架构做大幅度重构，但不能丢失旧系统参考。
2. 需要同时维护“旧系统基线”和“新系统目标结构”。
3. 需要给业务方持续回答“哪些能力已经迁移，哪些还没有”。

## 核心规则

### 1. 双库分工

- `old db`: 只读基线，不再写入
- `new db`: 当前工作库，持续记录新结构
- `migration_plan.md`: 迁移映射与进度的唯一业务视图

不要把 `old db` 当作当前事实，也不要把 `new db` 当作历史档案。

### 2. 先设计迁移，再改代码

先明确旧模块如何承接到新模块，再开始大规模改动。
如果承接关系还不清晰，不要急着更新大批量结构文档。

### 3. 所有解释都从业务能力出发

描述重构时，优先说明：
- 哪个旧业务能力由哪个新模块承接
- 当前迁移状态是什么
- 完成迁移的退出条件是什么

不要只描述代码移动或目录调整。

## 标准流程

### 1. 重构前：冻结 old db

开始前先备份当前数据库到 `.agent_cache/.backup`，形成只读基线：

```bash
STAMP=$(date +%Y%m%d-%H%M%S)
BASE=".agent_cache/.backup/refactors/$STAMP"
mkdir -p "$BASE"
cp docs/workspace_docs.db "$BASE/workspace_docs.old.db"
cp docs/modular_arch.db "$BASE/modular_arch.old.db"
```

此后：
- `docs/workspace_docs.db` 继续作为 `new db`
- `docs/modular_arch.db` 继续作为 `new db`
- `.agent_cache/.backup/.../*.old.db` 只用于观察旧系统，不允许继续写入

### 2. 设计期：创建迁移计划

在与本次重构最接近的叶子目录下创建 `migration_plan.md`。

最小表结构如下：

```md
| Old Module | New Module | Business Capability | Status | Exit Criteria | Notes |
|------------|------------|---------------------|--------|---------------|-------|
| order      | order_v2   | 订单创建与查询      | doing  | 所有读写流量切换完成 | 查询已迁移，写入未迁移 |
| billing    | billing_v2 | 账单结算            | todo   | 对账链路通过回归验证 | 依赖新账户接口 |
| user       | user_v2    | 用户资料管理        | done   | 旧接口下线 | 已切流 |
```

规则：
- `Status` 只用 `todo` / `doing` / `done` / `blocked`
- `Business Capability` 必须是业务能力，不是技术动作
- `Exit Criteria` 必须可验证

### 3. 实施期：建设 new db

对新结构的所有正式记录，都写入当前工作库：

- 文件/目录职责：使用 `workspace-docs`
- 模块、依赖、接口：使用 `modular-arch`

示例：

```bash
python3 .agents/skills/workspace-docs/scripts/agent_docs.py set "src/order_v2" \
  -d "新订单域模块，承接订单创建与查询能力" \
  -n "对应 migration_plan.md 中的 order -> order_v2"
```

```bash
python3 .agents/skills/modular-arch/scripts/mod_arch.py register order_v2 \
  -p src/order_v2 -l backend -d "新订单域模块"
```

```bash
python3 .agents/skills/modular-arch/scripts/mod_arch.py interface order_v2 order_service \
  -s "createOrder(input) -> Order; getOrder(id) -> Order" \
  -d "订单核心业务接口"
```

### 4. 对照期：观察 old db

当你需要回答“旧系统原来是什么样”时，查看备份的 `old db`。

注意：
- `workspace-docs` 和 `modular-arch` 现有脚本默认读写 `docs/*.db`
- 因此 `old db` 的定位是“观察基线”，不是当前工具链的工作库
- 对旧基线的核对，以只读方式进行，不要把旧基线拷回当前工作库覆盖现状

### 5. 收口期：验证与下线

新结构收口时，至少执行：

```bash
python3 .agents/skills/modular-arch/scripts/mod_arch.py check
python3 .agents/skills/workspace-docs/scripts/agent_docs.py scan
```

然后检查：
- `migration_plan.md` 是否所有关键能力都具备明确状态
- `done` 项是否满足 `Exit Criteria`
- 旧模块是否已满足下线条件

## 决策准则

- 问“旧系统以前怎么做”时，查 `old db`
- 问“新系统现在应该长什么样”时，查 `new db`
- 问“迁移做到哪一步了”时，查 `migration_plan.md`

如果一个信息同时需要“结构事实”和“迁移状态”，优先以 `migration_plan.md` 为准，再回查 DB。

## 与其他技能的配合

- `workspace-docs`: 负责新文件和目录职责说明
- `modular-arch`: 负责新模块、依赖方向和接口契约

这个技能不替代它们，而是规定在大规模重构场景下，三者如何协同：
- `workspace-docs` 记录新结构职责
- `modular-arch` 记录新结构关系
- `refactor-migration` 记录旧到新的迁移方法和进度

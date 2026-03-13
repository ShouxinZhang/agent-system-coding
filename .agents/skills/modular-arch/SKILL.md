---
name: modular-arch
description: '管理模块间语义层级依赖关系。注册模块、声明依赖方向、定义接口契约，支持环检测、跨层违规检查和并行开发分组。'
---

# Modular Architecture 模块依赖关系管理

基于 SQLite 的模块依赖图管理工具，与 `workspace-docs`（节点说明）正交互补，专注于模块间的**关系图谱**。

- 模板数据库位于 `modular-arch/modular_arch.db`。
- 运行时数据库写入仓库根目录 `docs/modular_arch.db`。

## When to use this skill?
1. **设计阶段**: 注册新模块、声明依赖关系、定义接口契约，为前后端并行开发做准备。
2. **编码之前**: 使用 `check` 命令验证新增依赖是否会引入循环或跨层违规。
3. **重构之后**: 更新依赖关系和接口契约，保持依赖图与代码一致。

## How to use (Execution)

所有操作通过 [mod_arch.py](./scripts/mod_arch.py) 脚本完成。

### 1. 注册模块 (Register)
```bash
python3 .agents/skills/modular-arch/scripts/mod_arch.py register <name> \
  -p <relative_path> -l <layer> -d "描述"
# layer: frontend / backend / shared / infra
```

### 2. 添加依赖 (Depend)
```bash
python3 .agents/skills/modular-arch/scripts/mod_arch.py depend <from> <to> \
  -t <dep_type> -d "说明"
# dep_type: imports / calls_api / implements / extends
```

### 3. 移除依赖 (Undepend)
```bash
python3 .agents/skills/modular-arch/scripts/mod_arch.py undepend <from> <to>
```

### 4. 注册接口契约 (Interface)
```bash
python3 .agents/skills/modular-arch/scripts/mod_arch.py interface <module> <iface_name> \
  -s "签名" -d "说明"
```

### 5. 查看模块详情 (Show)
```bash
python3 .agents/skills/modular-arch/scripts/mod_arch.py show <name>
```

### 6. 输出依赖图 (Graph)
```bash
python3 .agents/skills/modular-arch/scripts/mod_arch.py graph
# 输出 Mermaid 格式的依赖图
```

### 7. 环检测 + 违规检查 (Check)
```bash
python3 .agents/skills/modular-arch/scripts/mod_arch.py check
```

### 8. 并行开发分组 (Parallel)
```bash
python3 .agents/skills/modular-arch/scripts/mod_arch.py parallel
```

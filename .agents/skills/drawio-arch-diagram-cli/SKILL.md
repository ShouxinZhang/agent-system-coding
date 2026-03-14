---
name: drawio-arch-diagram-cli
description: 使用 draw.io CLI 绘制项目架构依赖图，支持中英文标签，导出 SVG/PNG/PDF 预览，并将图片插入 Markdown 文档。
---

# Draw.io Architecture Diagram CLI

用于把项目模块、边界和依赖关系整理成可持续维护的架构图产物。

## When to use

在这些场景使用：

1. 需要绘制项目架构图、模块依赖图、分层关系图。
2. 需要把图文件保存到仓库，并在 Markdown 中可预览。
3. 需要导出图片后继续迭代优化布局，而不是一次性出图。

## Outputs

默认把图产物放在 `docs/architecture/`：

- 源文件：`docs/architecture/<name>.drawio`
- 预览图：`docs/architecture/<name>.drawio.svg` 或 `docs/architecture/<name>.drawio.png`
- Markdown：在目标 `.md` 中插入 `![说明](./architecture/<name>.drawio.svg)`

如果用户明确要求 PNG，则导出 PNG；否则优先导出 SVG，便于预览和后续检查。
在本仓库中，默认使用 `./.agents/skills/drawio-arch-diagram-cli/scripts/drawio-wrapper` 调用 draw.io CLI。

## Working rules

1. 先整理模块、层级、依赖方向、关键链路，再开始画图。
2. 文本语言跟随用户输入，可中文、英文或混合，不要强制翻译。
3. 节点命名保持短句，避免把长段说明塞进图里。
4. 布局优先表达依赖关系，不追求装饰性。
5. 导出图片后必须回看预览，必要时继续修改，最多迭代 3 到 5 轮。

## Diagram workflow

1. 先确定图类型：
   - 分层架构图：适合前后端、共享层、基础设施
   - 模块依赖图：适合展示包、服务、子系统之间的引用关系
   - 核心链路图：适合展示主业务流和关键调用路径
2. 生成 `.drawio` 源文件，文件名使用稳定短名。
3. 用 draw.io CLI 导出预览图。
4. 将预览图插入对应 Markdown。
5. 检查预览图是否满足验收规则，不满足就回改 `.drawio` 再导出。

## Export commands

先检查 CLI：

```bash
./.agents/skills/drawio-arch-diagram-cli/scripts/drawio-wrapper --version
```

导出 SVG：

```bash
./.agents/skills/drawio-arch-diagram-cli/scripts/drawio-wrapper -x -f svg -e -o docs/architecture/<name>.drawio.svg docs/architecture/<name>.drawio
```

导出 PNG：

```bash
./.agents/skills/drawio-arch-diagram-cli/scripts/drawio-wrapper -x -f png -e -b 10 -o docs/architecture/<name>.drawio.png docs/architecture/<name>.drawio
```

导出 PDF：

```bash
./.agents/skills/drawio-arch-diagram-cli/scripts/drawio-wrapper -x -f pdf -e -o docs/architecture/<name>.drawio.pdf docs/architecture/<name>.drawio
```

`-e` 会把图的 XML 一并嵌入导出结果，后续仍可用 draw.io 打开继续编辑。
当前仓库实测结果是：SVG 预览稳定，PNG 可被浏览器正常显示，但严格图片校验工具可能给出 CRC 警告，因此默认以 SVG 作为 Markdown 预览格式。

## Markdown embed

同目录 Markdown 引用示例：

```md
![项目架构依赖图](./architecture/system-overview.drawio.svg)
```

如果文档在其他目录，改为对应相对路径。

## Review checklist

导出预览后按以下标准复查：

- 节点没有明显重叠、遮挡、压线。
- 依赖箭头方向一致，主依赖链路一眼可读。
- 同层模块尽量对齐，留白正常。
- 中文不乱码，字号足够阅读。
- 核心模块突出，次要关系不过度抢眼。
- 图中只保留结构信息，详细解释写在 Markdown 正文。

如果有任一项不满足，继续调整布局、尺寸、连线锚点或文案，再重新导出。

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_plan_prompt(user_request: str, preexisting_paths: list[str]) -> str:
    preexisting_text = json.dumps(preexisting_paths, ensure_ascii=False, indent=2)
    return f"""
你是 root planner。你的任务是为当前仓库生成一个最小可执行计划。

要求：
1. 只输出符合 schema 的 JSON。
2. task 数量尽量少，优先 1 到 3 个任务。
3. 每个任务必须可执行、可审查。
4. allowed_paths 必须尽量小，不要写成整个仓库。
5. required_checks 只写必要命令。
6. 仓库可能已有历史脏文件，计划不要把这些历史脏文件误算成当前任务目标。
7. 如果用户明确给出了多个交付物，必须拆成多个 task。
8. 如果用户明确说明某些任务彼此独立或可并行，必须保留这种依赖关系，不要强行合并成单任务。

用户需求：
{user_request}

当前仓库在任务开始前已存在的脏路径：
{preexisting_text}
""".strip()


def build_execute_prompt(
    task: dict[str, Any],
    repo_path: Path,
    preexisting_paths: list[str],
) -> str:
    task_json = json.dumps(task, ensure_ascii=False, indent=2)
    preexisting_text = json.dumps(preexisting_paths, ensure_ascii=False, indent=2)
    return f"""
你是 executor。请在仓库中完成以下任务，只能修改 allowed_paths 允许的文件。

仓库路径：
{repo_path}

任务：
{task_json}

任务开始前已存在的历史脏路径：
{preexisting_text}

要求：
1. 直接在仓库中完成编码。
2. 运行必要的 required_checks。
3. 最终只输出符合 schema 的 JSON。
4. changed_files 必须列出你实际改动过的文件相对路径。
5. summary 用简洁中文描述你完成了什么。
6. 不要把历史脏文件算进 changed_files。
""".strip()


def build_review_prompt(
    task: dict[str, Any],
    execution_result: dict[str, Any],
    repo_path: Path,
    preexisting_paths: list[str],
    observed_changed_files: list[str],
    batch_allowed_paths: list[str],
) -> str:
    task_json = json.dumps(task, ensure_ascii=False, indent=2)
    result_json = json.dumps(execution_result, ensure_ascii=False, indent=2)
    preexisting_text = json.dumps(preexisting_paths, ensure_ascii=False, indent=2)
    observed_text = json.dumps(observed_changed_files, ensure_ascii=False, indent=2)
    batch_allowed_text = json.dumps(batch_allowed_paths, ensure_ascii=False, indent=2)
    return f"""
你是 reviewer。请基于任务定义和 executor 结果，对当前仓库进行验收。

仓库路径：
{repo_path}

任务：
{task_json}

executor 结果：
{result_json}

任务开始前已存在的历史脏路径：
{preexisting_text}

系统在本轮 execute 前后观测到的新增脏路径：
{observed_text}

当前并行 batch 允许写入的全部路径：
{batch_allowed_text}

验收要求：
1. Scope gate 只评估本轮任务新增的改动，不要因为历史脏文件直接判失败。
2. 并行 batch 中，`observed_changed_files` 可能包含同批其他任务的文件；这些文件只要仍在 `batch_allowed_paths` 内，就不能据此判失败。
3. 优先使用 `execution_result.changed_files` 判断当前任务自己的改动，再用 `observed_changed_files` 做辅助验证。
4. 如果目标文件是新建未跟踪文件，只要文件存在、内容符合要求、且在 `changed_files` 或 `observed_changed_files` 中出现，就可以视为本轮有效改动。
5. 检查 required_checks 是否已经通过，必要时可复跑。
6. 检查 acceptance_criteria 是否满足。
7. 只能输出符合 schema 的 JSON。
8. 若失败，issues 中必须写清楚失败原因。
""".strip()

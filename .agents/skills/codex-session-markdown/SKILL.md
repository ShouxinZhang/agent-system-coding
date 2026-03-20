---
name: codex-session-markdown
description: 当你需要按用户 prompt 片段从本机 Codex CLI JSONL 会话里定位最近一次相关会话，并导出为可读的 user/assistant Markdown 对话稿时使用。
---

# Codex Session Markdown

Use this skill to turn a Codex CLI local session into a readable Markdown transcript that can be inspected, archived, or handed to another agent.

## When To Use

Use this skill when:

- you need to recover a recent Codex conversation from `~/.codex/sessions`
- you only remember part of the user's prompt and want the newest matching session
- you need a clean `User` / `Assistant` transcript instead of raw JSONL
- you want to preserve a session inside the workspace instead of leaving it in home-directory session storage

## Primary Command

Run:

```bash
python3 .agents/skills/codex-session-markdown/scripts/export_codex_session.py --prompt "<prompt snippet>"
```

This command will:

1. build or refresh a workspace-local session index cache
2. ignore injected noise such as `AGENTS.md` instructions and `<environment_context>`
3. prefer sessions from the current workspace `cwd`
4. fall back to the newest session in the current workspace when prompt matching is weak
5. print search reasoning so another agent can see why the session was chosen
4. export a readable Markdown transcript into `.agent_cache/codex-session-markdown/`

## Search Rules

- Prefer a short but identifying prompt snippet from the user request.
- The script first tries exact normalized substring matching.
- If exact match fails, it falls back to keyword overlap scoring and picks the best candidate.
- Sessions from the current workspace get a preference bonus.
- If multiple sessions match at the same quality level, the newest one wins.
- If prompt matching is too weak, the script falls back to the newest session from the current workspace.
- If no good match exists, the script returns a hint that the prompt keywords may be too long or badly shaped and suggests shortening them.

## Output

Default output path pattern:

```text
.agent_cache/codex-session-markdown/<session-id>.md
```

The Markdown includes:

- session metadata
- `## User` blocks
- `## Assistant` blocks
- optional tool call and tool result sections

The skill also maintains an index cache at:

```text
.agent_cache/codex-session-markdown/session-index.json
```

## Useful Variants

Include tool activity:

```bash
python3 .agents/skills/codex-session-markdown/scripts/export_codex_session.py \
  --prompt "<prompt snippet>" \
  --include-tools
```

Write to a custom workspace path:

```bash
python3 .agents/skills/codex-session-markdown/scripts/export_codex_session.py \
  --prompt "<prompt snippet>" \
  --output runtime/session-review/latest.md
```

Inspect only the selected session without writing a file:

```bash
python3 .agents/skills/codex-session-markdown/scripts/export_codex_session.py \
  --prompt "<prompt snippet>" \
  --dry-run
```

Disable workspace-cwd fallback if you need strict prompt matching only:

```bash
python3 .agents/skills/codex-session-markdown/scripts/export_codex_session.py \
  --prompt "<prompt snippet>" \
  --no-cwd-fallback
```

## Notes

- This skill reads from `~/.codex/sessions`, but it only writes inside the current workspace.
- Search explanation is printed on every run so another agent can audit the decision path.
- The exported transcript is intentionally readable, not a byte-for-byte replay of every JSONL record.
- Hidden reasoning is not recoverable in full; the script only exports visible assistant text and optional reasoning summaries when requested.

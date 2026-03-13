"""Session Log CLI — Agent 会话日志管理工具。

记录每次 Agent 交互的完整生命周期：
  用户原始 prompt → LLM 理解摘要 → 执行上下文摘要。

日志以 Markdown 文件为主存储（人类可读），同时自动同步到 SQLite（程序检索）。
"""

import argparse
import re
import shutil
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
REPO_ROOT = SKILL_DIR.parent.parent.parent  # .agents/skills/session-log -> repo
DOCS_DIR = REPO_ROOT / "docs"
LOGS_DIR = DOCS_DIR / "session-logs"
TEMPLATE_DB = SKILL_DIR / "session_log.db"
RUNTIME_DB = DOCS_DIR / "session_log.db"

# ---------------------------------------------------------------------------
# Valid enum values
# ---------------------------------------------------------------------------
VALID_STATUSES = ("started", "completed", "failed", "cancelled")

# ---------------------------------------------------------------------------
# Markdown helpers
# ---------------------------------------------------------------------------

def _gen_session_id() -> str:
    """Generate a short, human-friendly session ID: date + 8-char UUID."""
    date_part = datetime.now().strftime("%Y%m%d")
    uuid_part = uuid.uuid4().hex[:8]
    return f"{date_part}-{uuid_part}"


def _now() -> str:
    return datetime.now().isoformat()


def _write_md(session_id: str, prompt: str, understanding: str,
              summary: str, status: str, tags: str,
              related_files: str, started_at: str,
              finished_at: str) -> Path:
    """Write (or overwrite) a session log Markdown file."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    md_path = LOGS_DIR / f"{session_id}.md"

    lines = [
        "---",
        f"session_id: {session_id}",
        f"status: {status}",
        f"tags: {tags}",
        f"started_at: {started_at}",
        f"finished_at: {finished_at}",
        "---",
        "",
        f"# Session: {session_id}",
        "",
        "## Prompt",
        "",
        prompt,
        "",
        "## Understanding",
        "",
        understanding or "(pending)",
        "",
        "## Summary",
        "",
        summary or "(pending)",
        "",
    ]

    if related_files:
        lines.append("## Related Files")
        lines.append("")
        for f in related_files.split(","):
            f = f.strip()
            if f:
                lines.append(f"- `{f}`")
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path


def _parse_md(md_path: Path) -> dict[str, str] | None:
    """Parse a session log Markdown file, returning a dict of fields."""
    text = md_path.read_text(encoding="utf-8")

    # Extract YAML frontmatter
    fm_match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not fm_match:
        return None

    fields: dict[str, str] = {}
    for line in fm_match.group(1).splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fields[key.strip()] = val.strip()

    # Extract sections
    body = text[fm_match.end():]
    sections = {}
    current_section = None
    current_lines: list[str] = []
    for line in body.splitlines():
        heading = re.match(r"^## (.+)$", line)
        if heading:
            if current_section is not None:
                sections[current_section] = "\n".join(current_lines).strip()
            current_section = heading.group(1).strip()
            current_lines = []
        elif current_section is not None:
            current_lines.append(line)
    if current_section is not None:
        sections[current_section] = "\n".join(current_lines).strip()

    # Merge
    prompt = sections.get("Prompt", "")
    understanding = sections.get("Understanding", "")
    if understanding == "(pending)":
        understanding = ""
    summary = sections.get("Summary", "")
    if summary == "(pending)":
        summary = ""

    # Parse Related Files section: lines starting with "- `...`"
    related = sections.get("Related Files", "")
    file_list = []
    for line in related.splitlines():
        m = re.match(r"^-\s+`(.+)`$", line.strip())
        if m:
            file_list.append(m.group(1))

    return {
        "session_id": fields.get("session_id", md_path.stem),
        "status": fields.get("status", "started"),
        "tags": fields.get("tags", ""),
        "started_at": fields.get("started_at", ""),
        "finished_at": fields.get("finished_at", ""),
        "prompt": prompt,
        "understanding": understanding,
        "summary": summary,
        "related_files": ",".join(file_list),
    }


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _ensure_db() -> None:
    """Copy template DB if runtime DB does not exist yet."""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    if RUNTIME_DB.exists():
        return
    if TEMPLATE_DB.exists():
        shutil.copy2(TEMPLATE_DB, RUNTIME_DB)
        return
    sqlite3.connect(RUNTIME_DB).close()


def _connect() -> sqlite3.Connection:
    _ensure_db()
    conn = sqlite3.connect(RUNTIME_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _init_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id   TEXT PRIMARY KEY,
            prompt       TEXT NOT NULL,
            understanding TEXT NOT NULL DEFAULT '',
            summary      TEXT NOT NULL DEFAULT '',
            status       TEXT NOT NULL DEFAULT 'started',
            tags         TEXT NOT NULL DEFAULT '',
            related_files TEXT NOT NULL DEFAULT '',
            started_at   TEXT NOT NULL,
            finished_at  TEXT
        );
    """)


def _upsert_to_db(data: dict[str, str]) -> None:
    """Insert or replace a session record in the DB."""
    with _connect() as conn:
        _init_tables(conn)
        conn.execute(
            """INSERT OR REPLACE INTO sessions
               (session_id, prompt, understanding, summary, status,
                tags, related_files, started_at, finished_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["session_id"], data["prompt"], data["understanding"],
                data["summary"], data["status"], data["tags"],
                data["related_files"], data["started_at"],
                data["finished_at"] or None,
            ),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------

def cmd_start(args: argparse.Namespace) -> None:
    session_id = _gen_session_id()
    started_at = _now()
    tags = args.tags or ""
    understanding = args.understanding or ""

    data = {
        "session_id": session_id,
        "prompt": args.prompt,
        "understanding": understanding,
        "summary": "",
        "status": "started",
        "tags": tags,
        "related_files": "",
        "started_at": started_at,
        "finished_at": "",
    }

    # 1. Write Markdown file
    md_path = _write_md(**data)

    # 2. Sync to DB
    _upsert_to_db(data)

    print(f"Session started: {session_id}")
    print(f"Log file: {md_path.relative_to(REPO_ROOT)}")


def cmd_finish(args: argparse.Namespace) -> None:
    status = args.status or "completed"
    if status not in VALID_STATUSES:
        print(f"Error: status must be one of {VALID_STATUSES}, got '{status}'")
        return

    md_path = LOGS_DIR / f"{args.session_id}.md"
    if not md_path.exists():
        print(f"Error: log file '{md_path}' not found.")
        return

    # 1. Parse existing MD
    data = _parse_md(md_path)
    if not data:
        print(f"Error: failed to parse '{md_path}'.")
        return

    # 2. Update fields
    data["status"] = status
    data["finished_at"] = _now()
    if args.summary:
        data["summary"] = args.summary
    if args.files:
        data["related_files"] = args.files

    # 3. Rewrite MD
    _write_md(**data)

    # 4. Sync to DB
    _upsert_to_db(data)

    print(f"Session finished: {args.session_id} (status={status})")


def cmd_show(args: argparse.Namespace) -> None:
    # Prefer reading from MD file for human-readable output
    md_path = LOGS_DIR / f"{args.session_id}.md"
    if md_path.exists():
        print(md_path.read_text(encoding="utf-8"))
    else:
        # Fallback to DB
        with _connect() as conn:
            _init_tables(conn)
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id=?", (args.session_id,)
            ).fetchone()
            if not row:
                print(f"Session '{args.session_id}' not found.")
                return
            print(f"Session:       {row['session_id']}")
            print(f"Status:        {row['status']}")
            print(f"Started:       {row['started_at']}")
            print(f"Finished:      {row['finished_at'] or '(in progress)'}")
            print(f"Tags:          {row['tags']}")
            print(f"Prompt:        {row['prompt']}")
            print(f"Understanding: {row['understanding']}")
            print(f"Summary:       {row['summary']}")
            print(f"Files:         {row['related_files']}")


def cmd_list(args: argparse.Namespace) -> None:
    limit = args.limit or 20
    with _connect() as conn:
        _init_tables(conn)
        rows = conn.execute(
            "SELECT session_id, status, tags, started_at, prompt FROM sessions "
            "ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()

    if not rows:
        print("No sessions found.")
        return

    print(f"{'Session ID':<22} {'Status':<12} {'Tags':<20} {'Started':<22} Prompt (truncated)")
    print("─" * 110)
    for r in rows:
        prompt_short = r["prompt"][:40].replace("\n", " ")
        if len(r["prompt"]) > 40:
            prompt_short += "..."
        tags = r["tags"] or "-"
        print(f"{r['session_id']:<22} {r['status']:<12} {tags:<20} {r['started_at']:<22} {prompt_short}")


def cmd_search(args: argparse.Namespace) -> None:
    conditions: list[str] = []
    params: list[str | int] = []

    if args.tag:
        conditions.append("tags LIKE ?")
        params.append(f"%{args.tag}%")
    if args.status:
        if args.status not in VALID_STATUSES:
            print(f"Error: status must be one of {VALID_STATUSES}, got '{args.status}'")
            return
        conditions.append("status = ?")
        params.append(args.status)
    if args.since:
        conditions.append("started_at >= ?")
        params.append(args.since)
    if args.keyword:
        conditions.append("(prompt LIKE ? OR understanding LIKE ? OR summary LIKE ?)")
        kw = f"%{args.keyword}%"
        params.extend([kw, kw, kw])

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    limit = args.limit or 20

    with _connect() as conn:
        _init_tables(conn)
        rows = conn.execute(
            f"SELECT session_id, status, tags, started_at, prompt FROM sessions "
            f"{where} ORDER BY started_at DESC LIMIT ?",
            [*params, limit],
        ).fetchall()

    if not rows:
        print("No matching sessions found.")
        return

    print(f"{'Session ID':<22} {'Status':<12} {'Tags':<20} {'Started':<22} Prompt (truncated)")
    print("─" * 110)
    for r in rows:
        prompt_short = r["prompt"][:40].replace("\n", " ")
        if len(r["prompt"]) > 40:
            prompt_short += "..."
        tags = r["tags"] or "-"
        print(f"{r['session_id']:<22} {r['status']:<12} {tags:<20} {r['started_at']:<22} {prompt_short}")


def cmd_sync(args: argparse.Namespace) -> None:
    """Rebuild DB from all Markdown files in the session-logs directory."""
    if not LOGS_DIR.exists():
        print("No session-logs directory found. Nothing to sync.")
        return

    md_files = sorted(LOGS_DIR.glob("*.md"))
    if not md_files:
        print("No .md files found in session-logs/. Nothing to sync.")
        return

    synced = 0
    skipped = 0
    for md_path in md_files:
        data = _parse_md(md_path)
        if data:
            _upsert_to_db(data)
            synced += 1
        else:
            print(f"  ⚠ Skipped (parse error): {md_path.name}")
            skipped += 1

    print(f"Sync complete: {synced} synced, {skipped} skipped.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Session Log CLI — Agent 会话日志管理"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # start
    p = sub.add_parser("start", help="开始新会话，记录 prompt 和 LLM 理解")
    p.add_argument("--prompt", required=True, help="用户的原始输入")
    p.add_argument("--understanding", help="LLM 对 prompt 的简要理解")
    p.add_argument("--tags", help="标签，逗号分隔 (如 refactor,bugfix)")

    # finish
    p = sub.add_parser("finish", help="完成会话，补充执行摘要")
    p.add_argument("session_id", help="会话 ID")
    p.add_argument("--summary", help="执行上下文摘要")
    p.add_argument("--files", help="涉及的文件，逗号分隔")
    p.add_argument("--status", help="状态: started/completed/failed/cancelled",
                   default="completed")

    # show
    p = sub.add_parser("show", help="查看会话详情 (优先展示 MD 文件)")
    p.add_argument("session_id", help="会话 ID")

    # list
    p = sub.add_parser("list", help="列出最近的会话")
    p.add_argument("--limit", type=int, default=20, help="最多显示条数 (默认 20)")

    # search
    p = sub.add_parser("search", help="搜索会话")
    p.add_argument("--tag", help="按标签过滤")
    p.add_argument("--status", help="按状态过滤")
    p.add_argument("--since", help="起始时间 (ISO 格式，如 2026-03-01)")
    p.add_argument("--keyword", help="关键词搜索 (搜索 prompt/understanding/summary)")
    p.add_argument("--limit", type=int, default=20, help="最多显示条数 (默认 20)")

    # sync
    sub.add_parser("sync", help="从 MD 文件重建 DB (手动编辑 MD 后使用)")

    args = parser.parse_args()
    {
        "start": cmd_start,
        "finish": cmd_finish,
        "show": cmd_show,
        "list": cmd_list,
        "search": cmd_search,
        "sync": cmd_sync,
    }[args.command](args)


if __name__ == "__main__":
    main()

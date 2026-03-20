#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable


SESSION_ROOT = Path.home() / ".codex" / "sessions"
DEFAULT_OUTPUT_DIR = Path(".agent_cache") / "codex-session-markdown"
DEFAULT_INDEX_PATH = DEFAULT_OUTPUT_DIR / "session-index.json"
STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "about",
    "please",
    "then",
    "have",
    "want",
    "need",
    "just",
    "一下",
    "一个",
    "一些",
    "这个",
    "那个",
    "可以",
    "然后",
    "就是",
    "现在",
    "我们",
    "你们",
    "是否",
    "如果",
    "以及",
    "进行",
    "当前",
    "最近",
    "一次",
    "对话",
    "会话",
    "导出",
    "整理",
    "转换",
    "生成",
}
NOISE_PREFIXES = (
    "<environment_context>",
    "# AGENTS.md instructions",
)
REQUEST_MARKER = "## My request for Codex:"


@dataclass
class TranscriptBlock:
    heading: str
    body: str


@dataclass
class SessionCandidate:
    path: Path
    session_id: str
    timestamp: datetime
    cwd: str | None
    search_text: str
    raw_score: float
    final_score: float
    match_mode: str
    overlap_keywords: list[str]
    cwd_matched: bool


@dataclass
class IndexStats:
    total_files: int = 0
    reused_entries: int = 0
    refreshed_entries: int = 0


@dataclass
class SessionIndexEntry:
    path: Path
    session_id: str
    timestamp: datetime
    cwd: str | None
    search_text: str
    mtime_ns: int
    size: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find a recent Codex CLI session by prompt snippet and export it as Markdown."
    )
    parser.add_argument("--prompt", required=True, help="Prompt snippet used to search user messages.")
    parser.add_argument(
        "--session-root",
        default=str(SESSION_ROOT),
        help="Codex session root directory. Defaults to ~/.codex/sessions.",
    )
    parser.add_argument(
        "--output",
        help="Workspace-local Markdown output path. Defaults to .agent_cache/codex-session-markdown/<session-id>.md",
    )
    parser.add_argument(
        "--include-tools",
        action="store_true",
        help="Include tool call and tool result sections in the Markdown export.",
    )
    parser.add_argument(
        "--include-reasoning",
        action="store_true",
        help="Include reasoning summaries when the session exposes them.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report the selected session without writing Markdown.",
    )
    parser.add_argument(
        "--cwd",
        default=str(Path.cwd()),
        help="Prefer sessions from this workspace path and use it for fallback. Defaults to current working directory.",
    )
    parser.add_argument(
        "--no-cwd-fallback",
        action="store_true",
        help="Disable fallback to the newest session from the preferred cwd when prompt matching is weak.",
    )
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def parse_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=UTC)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def extract_text_parts(content: Iterable[dict] | None, allowed_types: set[str]) -> str:
    parts: list[str] = []
    for item in content or []:
        if item.get("type") in allowed_types:
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
    return "\n\n".join(parts).strip()


def strip_noise(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    for prefix in NOISE_PREFIXES:
        if text.startswith(prefix):
            return ""
    if REQUEST_MARKER in text:
        before, after = text.split(REQUEST_MARKER, 1)
        kept = after.strip()
        if kept:
            return kept
        return before.strip()
    return text


def visible_user_text(payload: dict) -> str:
    return strip_noise(extract_text_parts(payload.get("content"), {"input_text", "text"}))


def visible_assistant_text(payload: dict) -> str:
    return extract_text_parts(payload.get("content"), {"output_text", "text"})


def normalize_text(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"https?://\S+", " ", lowered)
    lowered = re.sub(r"[^\w\u4e00-\u9fff]+", " ", lowered, flags=re.UNICODE)
    return re.sub(r"\s+", " ", lowered).strip()


def extract_keywords(text: str) -> list[str]:
    normalized = normalize_text(text)
    raw_tokens = normalized.split()
    keywords: list[str] = []
    for token in raw_tokens:
        if len(token) <= 1:
            continue
        if token in STOPWORDS:
            continue
        keywords.append(token)
    return keywords


def dedupe_preserve_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def score_match(query: str, search_text: str) -> tuple[float, str, list[str]]:
    normalized_query = normalize_text(query)
    normalized_search = normalize_text(search_text)
    if not normalized_query or not normalized_search:
        return 0.0, "no-match", []
    if normalized_query in normalized_search:
        return 1000.0 + len(normalized_query), "exact-substring", dedupe_preserve_order(extract_keywords(query))

    query_keywords = extract_keywords(query)
    search_keywords = set(extract_keywords(search_text))
    if not query_keywords:
        return 0.0, "no-match", []

    overlap = [token for token in query_keywords if token in search_keywords]
    if not overlap:
        return 0.0, "no-match", []

    coverage = len(overlap) / len(query_keywords)
    ordered_bonus = 0.0
    match_mode = "keyword-overlap"
    if len(overlap) >= 2:
        sequence = " ".join(overlap)
        if sequence in normalized_search:
            ordered_bonus = 0.2
            match_mode = "keyword-sequence"

    return coverage + ordered_bonus, match_mode, dedupe_preserve_order(overlap)


def session_metadata(rows: list[dict], path: Path) -> tuple[str, datetime, str | None]:
    session_id = path.stem
    timestamp = datetime.min
    cwd: str | None = None

    for row in rows:
        if row.get("type") == "session_meta":
            payload = row.get("payload", {})
            session_id = payload.get("id") or session_id
            timestamp = parse_timestamp(payload.get("timestamp") or row.get("timestamp"))
            cwd = payload.get("cwd")
            break

    if timestamp == datetime.min:
        for row in rows:
            timestamp = parse_timestamp(row.get("timestamp"))
            if timestamp != datetime.min:
                break

    if cwd is None:
        for row in rows:
            if row.get("type") == "turn_context":
                cwd = row.get("payload", {}).get("cwd")
                if cwd:
                    break

    return session_id, timestamp, cwd


def build_search_text(rows: list[dict]) -> str:
    user_parts: list[str] = []
    for row in rows:
        if row.get("type") != "response_item":
            continue
        payload = row.get("payload", {})
        if payload.get("type") != "message" or payload.get("role") != "user":
            continue
        text = visible_user_text(payload)
        if text:
            user_parts.append(text)
    return "\n".join(user_parts)


def iter_session_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    return sorted(root.rglob("*.jsonl"))


def index_cache_path() -> Path:
    return Path.cwd() / DEFAULT_INDEX_PATH


def load_index_cache(cache_path: Path) -> dict[str, dict]:
    if not cache_path.exists():
        return {}
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    entries = data.get("entries", {})
    if isinstance(entries, dict):
        return entries
    return {}


def write_index_cache(cache_path: Path, entries: dict[str, dict]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now(tz=UTC).isoformat(),
        "entries": entries,
    }
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def index_entry_to_json(entry: SessionIndexEntry) -> dict:
    return {
        "path": str(entry.path),
        "session_id": entry.session_id,
        "timestamp": entry.timestamp.isoformat(),
        "cwd": entry.cwd,
        "search_text": entry.search_text,
        "mtime_ns": entry.mtime_ns,
        "size": entry.size,
    }


def json_to_index_entry(path_key: str, payload: dict) -> SessionIndexEntry | None:
    try:
        return SessionIndexEntry(
            path=Path(payload.get("path") or path_key),
            session_id=payload["session_id"],
            timestamp=parse_timestamp(payload["timestamp"]),
            cwd=payload.get("cwd"),
            search_text=payload.get("search_text", ""),
            mtime_ns=int(payload["mtime_ns"]),
            size=int(payload["size"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def build_index_entry(path: Path, stat_result) -> SessionIndexEntry:
    rows = load_jsonl(path)
    session_id, timestamp, cwd = session_metadata(rows, path)
    return SessionIndexEntry(
        path=path,
        session_id=session_id,
        timestamp=timestamp,
        cwd=cwd,
        search_text=build_search_text(rows),
        mtime_ns=stat_result.st_mtime_ns,
        size=stat_result.st_size,
    )


def build_session_index(session_root: Path) -> tuple[list[SessionIndexEntry], IndexStats]:
    cache_path = index_cache_path()
    cached_payloads = load_index_cache(cache_path)
    fresh_payloads: dict[str, dict] = {}
    entries: list[SessionIndexEntry] = []
    stats = IndexStats()

    for path in iter_session_files(session_root):
        stats.total_files += 1
        stat_result = path.stat()
        path_key = str(path)
        cached_entry = json_to_index_entry(path_key, cached_payloads.get(path_key, {}))
        if (
            cached_entry
            and cached_entry.mtime_ns == stat_result.st_mtime_ns
            and cached_entry.size == stat_result.st_size
        ):
            entries.append(cached_entry)
            fresh_payloads[path_key] = cached_payloads[path_key]
            stats.reused_entries += 1
            continue

        entry = build_index_entry(path, stat_result)
        entries.append(entry)
        fresh_payloads[path_key] = index_entry_to_json(entry)
        stats.refreshed_entries += 1

    write_index_cache(cache_path, fresh_payloads)
    return entries, stats


def normalize_cwd(path: str | Path | None) -> str | None:
    if not path:
        return None
    return str(Path(path).expanduser().resolve())


def recency_bonus(timestamp: datetime) -> float:
    if timestamp == datetime.min.replace(tzinfo=UTC):
        return 0.0
    age_seconds = max(0.0, (datetime.now(tz=UTC) - timestamp).total_seconds())
    if age_seconds <= 3600:
        return 0.15
    if age_seconds <= 86400:
        return 0.10
    if age_seconds <= 604800:
        return 0.05
    return 0.0


def choose_session(
    entries: list[SessionIndexEntry],
    prompt: str,
    preferred_cwd: str | None,
) -> SessionCandidate | None:
    best: SessionCandidate | None = None
    normalized_preferred_cwd = normalize_cwd(preferred_cwd)
    for entry in entries:
        raw_score, match_mode, overlap_keywords = score_match(prompt, entry.search_text)
        if raw_score <= 0:
            continue
        cwd_matched = normalize_cwd(entry.cwd) == normalized_preferred_cwd if normalized_preferred_cwd else False
        final_score = raw_score + recency_bonus(entry.timestamp) + (0.25 if cwd_matched else 0.0)
        candidate = SessionCandidate(
            path=entry.path,
            session_id=entry.session_id,
            timestamp=entry.timestamp,
            cwd=entry.cwd,
            search_text=entry.search_text,
            raw_score=raw_score,
            final_score=final_score,
            match_mode=match_mode,
            overlap_keywords=overlap_keywords,
            cwd_matched=cwd_matched,
        )
        if best is None:
            best = candidate
            continue
        if abs(candidate.final_score - best.final_score) < 1e-9:
            if candidate.timestamp >= best.timestamp:
                best = candidate
            continue
        if candidate.final_score > best.final_score:
            best = candidate
    return best


def fallback_session(entries: list[SessionIndexEntry], preferred_cwd: str | None) -> SessionCandidate | None:
    normalized_preferred_cwd = normalize_cwd(preferred_cwd)
    candidates = entries
    if normalized_preferred_cwd:
        scoped = [entry for entry in entries if normalize_cwd(entry.cwd) == normalized_preferred_cwd]
        if scoped:
            candidates = scoped
    if not candidates:
        return None
    entry = max(candidates, key=lambda item: item.timestamp)
    return SessionCandidate(
        path=entry.path,
        session_id=entry.session_id,
        timestamp=entry.timestamp,
        cwd=entry.cwd,
        search_text=entry.search_text,
        raw_score=0.0,
        final_score=0.0,
        match_mode="cwd-recent-fallback" if normalized_preferred_cwd else "recent-fallback",
        overlap_keywords=[],
        cwd_matched=normalize_cwd(entry.cwd) == normalized_preferred_cwd if normalized_preferred_cwd else False,
    )


def reasoning_summary(payload: dict) -> str:
    summary = payload.get("summary")
    if isinstance(summary, list):
        parts: list[str] = []
        for item in summary:
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
        return "\n".join(parts).strip()
    if isinstance(summary, str):
        return summary.strip()
    return ""


def render_markdown(
    rows: list[dict],
    source_path: Path,
    session_id: str,
    timestamp: datetime,
    cwd: str | None,
    include_tools: bool,
    include_reasoning: bool,
) -> str:
    blocks: list[TranscriptBlock] = []
    for row in rows:
        if row.get("type") != "response_item":
            continue
        payload = row.get("payload", {})
        payload_type = payload.get("type")

        if payload_type == "message":
            role = payload.get("role")
            if role == "user":
                text = visible_user_text(payload)
                if text:
                    blocks.append(TranscriptBlock("User", text))
            elif role == "assistant":
                text = visible_assistant_text(payload)
                if text:
                    blocks.append(TranscriptBlock("Assistant", text))
        elif include_tools and payload_type == "function_call":
            name = payload.get("name", "tool")
            arguments = payload.get("arguments", "")
            blocks.append(
                TranscriptBlock(
                    f"Tool Call: {name}",
                    f"```json\n{arguments}\n```".strip(),
                )
            )
        elif include_tools and payload_type == "function_call_output":
            name = payload.get("name", "tool")
            output = payload.get("output", "")
            blocks.append(
                TranscriptBlock(
                    f"Tool Result: {name}",
                    f"```\n{output}\n```".strip(),
                )
            )
        elif include_reasoning and payload_type == "reasoning":
            summary = reasoning_summary(payload)
            if summary:
                blocks.append(TranscriptBlock("Reasoning Summary", summary))

    lines = [
        f"# Codex Session Transcript: {session_id}",
        "",
        f"- Source: `{source_path}`",
        f"- Session ID: `{session_id}`",
        f"- Timestamp: `{timestamp.isoformat()}`" if timestamp != datetime.min else "- Timestamp: unknown",
        f"- CWD: `{cwd}`" if cwd else "- CWD: unknown",
        "",
    ]
    for block in blocks:
        lines.append(f"## {block.heading}")
        lines.append("")
        lines.append(block.body)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def ensure_workspace_output(path: Path) -> Path:
    workspace_root = Path.cwd().resolve()
    output_path = path.resolve()
    try:
        output_path.relative_to(workspace_root)
    except ValueError as exc:
        raise SystemExit(f"Output path must stay inside the workspace: {workspace_root}") from exc
    return output_path


def default_output_path(session_id: str) -> Path:
    return Path.cwd() / DEFAULT_OUTPUT_DIR / f"{session_id}.md"


def print_search_explanation(
    prompt: str,
    preferred_cwd: str | None,
    candidate: SessionCandidate,
    stats: IndexStats,
) -> None:
    keywords = dedupe_preserve_order(extract_keywords(prompt))
    print(f"Index files scanned: {stats.total_files}")
    print(f"Index cache reused: {stats.reused_entries}")
    print(f"Index entries refreshed: {stats.refreshed_entries}")
    print(f"Prompt keywords: {', '.join(keywords) if keywords else '(none)'}")
    print(f"Preferred cwd: {preferred_cwd or '(none)'}")
    print(f"Match mode: {candidate.match_mode}")
    print(f"CWD matched: {'yes' if candidate.cwd_matched else 'no'}")
    if candidate.overlap_keywords:
        print(f"Matched keywords: {', '.join(candidate.overlap_keywords)}")
    print(f"Raw score: {candidate.raw_score:.3f}")
    print(f"Final score: {candidate.final_score:.3f}")


def main() -> int:
    args = parse_args()
    session_root = Path(args.session_root).expanduser()
    preferred_cwd = normalize_cwd(args.cwd)
    entries, stats = build_session_index(session_root)
    candidate = choose_session(entries, args.prompt, preferred_cwd)
    if (candidate is None or candidate.raw_score < 0.35) and not args.no_cwd_fallback:
        candidate = fallback_session(entries, preferred_cwd)
    if candidate is None:
        print(
            "说明prompt可能格式错误，缩短一下prompt关键词；尽量保留最能区分该对话的 2 到 6 个词。",
            file=sys.stderr,
        )
        return 1

    print(f"Matched session: {candidate.session_id}")
    print(f"Session file: {candidate.path}")
    print_search_explanation(args.prompt, preferred_cwd, candidate, stats)

    if args.dry_run:
        return 0

    rows = load_jsonl(candidate.path)
    markdown = render_markdown(
        rows=rows,
        source_path=candidate.path,
        session_id=candidate.session_id,
        timestamp=candidate.timestamp,
        cwd=candidate.cwd,
        include_tools=args.include_tools,
        include_reasoning=args.include_reasoning,
    )

    output_path = Path(args.output) if args.output else default_output_path(candidate.session_id)
    output_path = ensure_workspace_output(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")

    print(f"Markdown written to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import argparse
import os
import sqlite3
import subprocess
import shutil
from datetime import datetime
from pathlib import Path

# Define paths
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
REPO_ROOT = SKILL_DIR.parent.parent.parent  # .agents/skills/workspace-docs -> repo root
MODULE_ROOT = REPO_ROOT
DOCS_DIR = REPO_ROOT / "docs"
TEMPLATE_DB_PATH = SKILL_DIR / "workspace_docs.db"
DB_PATH = DOCS_DIR / "workspace_docs.db"
PENDING_DESCRIPTION = "待补充描述 (Pending description)"
DIRECTORY_ONLY_PREFIXES = (
    ".agent_cache/",
    "docs/plan/image/",
    "docs/session-logs/",
    "runtime/",
)
EXCLUDED_PREFIXES = (
    ".backup/",
    ".tools/",
    "docs/ref_code/",
)
REQUIRED_DIRECTORY_PATHS = {
    ".agent_cache",
    ".agents",
    ".agents/skills",
    "docs",
    "docs/plan",
    "docs/session-logs",
    "schemas",
    "src",
    "src/agent_system_coding",
}
IGNORED_DIR_NAMES = {
    ".git",
    ".idea",
    ".mypy_cache",
    ".nox",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    ".vscode",
    "__pycache__",
    "env",
    "node_modules",
    "venv",
}
IGNORED_SUFFIXES = {
    ".db",
    ".jpeg",
    ".jpg",
    ".log",
    ".pdf",
    ".png",
    ".pyc",
    ".svg",
}
DOCUMENTED_EXACT_PATHS = {
    ".gitattributes",
    ".gitignore",
    "AGENTS.md",
    "README.md",
    "check_errors.sh",
    "package-lock.json",
    "package.json",
    "pyproject.toml",
}
DOCUMENTED_EXTENSIONS = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".toml",
}


def ensure_runtime_storage():
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        return
    if TEMPLATE_DB_PATH.exists():
        shutil.copy2(TEMPLATE_DB_PATH, DB_PATH)
        return
    sqlite3.connect(DB_PATH).close()

def get_db():
    ensure_runtime_storage()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS workspace_nodes (
                path TEXT PRIMARY KEY,
                type TEXT,
                description TEXT,
                agent_notes TEXT,
                last_updated TEXT
            )
        ''')
        conn.commit()


def _insert_placeholder_node(conn, path: str, node_type: str) -> bool:
    cursor = conn.execute('SELECT 1 FROM workspace_nodes WHERE path = ?', (path,))
    if cursor.fetchone():
        return False

    now = datetime.now().isoformat()
    conn.execute('''
        INSERT INTO workspace_nodes (path, type, description, agent_notes, last_updated)
        VALUES (?, ?, ?, ?, ?)
    ''', (path, node_type, PENDING_DESCRIPTION, "", now))
    return True


def _ensure_ancestor_directories(conn, rel_path: str) -> int:
    added_count = 0
    parts = Path(rel_path).parts
    for depth in range(1, len(parts)):
        ancestor = Path(*parts[:depth]).as_posix()
        added_count += int(_insert_placeholder_node(conn, ancestor, 'directory'))
    return added_count


def _iter_scan_entries(module_root: Path):
    ignore_dirs = {'venv', 'env', 'node_modules'}

    for root, dirs, files in os.walk(module_root):
        dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('.') and not d.startswith('__')]

        root_path = Path(root)
        rel_root = root_path.relative_to(module_root)
        if rel_root != Path('.'):
            yield rel_root.as_posix(), 'directory'

        for name in files:
            if name.endswith('.pyc') or name == '.DS_Store' or name.endswith('.db'):
                continue

            full_path = root_path / name
            rel_path = full_path.relative_to(module_root).as_posix()
            yield rel_path, 'file'


def _matches_prefix(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in prefixes)


def _should_ignore_path(rel_path: str) -> bool:
    if _matches_prefix(rel_path, EXCLUDED_PREFIXES):
        return True
    path = Path(rel_path)
    if any(part in IGNORED_DIR_NAMES for part in path.parts):
        return True
    return path.suffix.lower() in IGNORED_SUFFIXES or path.name == ".DS_Store"


def _is_directory_only_path(rel_path: str) -> bool:
    return _matches_prefix(rel_path, DIRECTORY_ONLY_PREFIXES)


def _should_document_file(rel_path: str) -> bool:
    if _should_ignore_path(rel_path) or _is_directory_only_path(rel_path):
        return False

    if rel_path in DOCUMENTED_EXACT_PATHS:
        return True

    path = Path(rel_path)
    if path.suffix.lower() not in DOCUMENTED_EXTENSIONS:
        return False

    if ".egg-info" in path.parts:
        return False

    return True


def _iter_git_tracked_and_visible_files(module_root: Path):
    try:
        result = subprocess.run(
            ["git", "-C", str(module_root), "ls-files", "--cached", "--others", "--exclude-standard"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        for rel_path, node_type in _iter_scan_entries(module_root):
            if node_type == "file" and not _should_ignore_path(rel_path):
                yield rel_path
        return

    for line in result.stdout.splitlines():
        rel_path = line.strip()
        if not rel_path or _should_ignore_path(rel_path):
            continue
        yield rel_path


def _iter_managed_directories(module_root: Path):
    directories = set()
    for rel_path in _iter_git_tracked_and_visible_files(module_root):
        directories.update(
            Path(*Path(rel_path).parts[:depth]).as_posix()
            for depth in range(1, len(Path(rel_path).parts))
        )
    for rel_dir in sorted(directories):
        yield rel_dir


def _iter_managed_files(module_root: Path):
    for rel_path in _iter_git_tracked_and_visible_files(module_root):
        if _should_document_file(rel_path):
            yield rel_path


def _load_workspace_row_map(conn):
    return {
        row["path"]: row
        for row in conn.execute(
            "SELECT path, type, description, agent_notes, last_updated FROM workspace_nodes"
        )
    }


def _is_missing_description(row) -> bool:
    if row is None:
        return True
    description = (row["description"] or "").strip()
    return description in {"", PENDING_DESCRIPTION}


def _collect_audit_issues(conn, module_root: Path):
    rows = _load_workspace_row_map(conn)

    directory_issues = []
    for rel_dir in sorted(
        rel_dir
        for rel_dir in _iter_managed_directories(module_root)
        if rel_dir in REQUIRED_DIRECTORY_PATHS
    ):
        row = rows.get(rel_dir)
        if _is_missing_description(row):
            directory_issues.append(rel_dir)

    file_issues = []
    for rel_path in _iter_managed_files(module_root):
        row = rows.get(rel_path)
        if _is_missing_description(row):
            file_issues.append(rel_path)

    return directory_issues, file_issues

def cmd_set(args):
    path = args.path
    full_path = MODULE_ROOT / path
    node_type = 'directory' if full_path.is_dir() else 'file'
    now = datetime.now().isoformat()
    
    with get_db() as conn:
        # Check if exists to preserve old data if not provided
        cursor = conn.execute('SELECT description, agent_notes FROM workspace_nodes WHERE path = ?', (path,))
        row = cursor.fetchone()
        
        desc = args.desc if args.desc is not None else (row['description'] if row else "")
        notes = args.notes if args.notes is not None else (row['agent_notes'] if row else "")
        
        conn.execute('''
            INSERT OR REPLACE INTO workspace_nodes (path, type, description, agent_notes, last_updated)
            VALUES (?, ?, ?, ?, ?)
        ''', (path, node_type, desc, notes, now))
        conn.commit()
    print(f"Successfully updated documentation for '{path}'.")

def cmd_get(args):
    with get_db() as conn:
        cursor = conn.execute('SELECT * FROM workspace_nodes WHERE path = ?', (args.path,))
        row = cursor.fetchone()
        if row:
            print(f"--- {row['path']} ({row['type']}) ---")
            print(f"Description: {row['description']}")
            print(f"Agent Notes: {row['agent_notes']}")
            print(f"Last Updated: {row['last_updated']}")
        else:
            print(f"No documentation found for '{args.path}'.")

def cmd_delete(args):
    with get_db() as conn:
        conn.execute('DELETE FROM workspace_nodes WHERE path = ?', (args.path,))
        conn.commit()
    print(f"Successfully deleted documentation for '{args.path}'.")

def cmd_scan(args):
    added_count = 0

    with get_db() as conn:
        for rel_dir in _iter_managed_directories(MODULE_ROOT):
            added_count += _ensure_ancestor_directories(conn, rel_dir)
            added_count += int(_insert_placeholder_node(conn, rel_dir, "directory"))

        for rel_path in _iter_managed_files(MODULE_ROOT):
            added_count += _ensure_ancestor_directories(conn, rel_path)
            added_count += int(_insert_placeholder_node(conn, rel_path, "file"))
        conn.commit()
    print(
        "Scan complete. Added "
        f"{added_count} managed nodes with .gitignore-aware and directory-only rules."
    )


def cmd_audit(args):
    with get_db() as conn:
        directory_issues, file_issues = _collect_audit_issues(conn, MODULE_ROOT)

    print(f"Directory issues: {len(directory_issues)}")
    for rel_dir in directory_issues:
        print(f"DIR  {rel_dir}")

    print(f"File issues: {len(file_issues)}")
    for rel_path in file_issues:
        print(f"FILE {rel_path}")

def cmd_export(args):
    init_db()
    print(
        "Export is deprecated. Workspace documentation is stored in "
        f"{DB_PATH} and no WORKSPACE_MAP.md will be generated."
    )

def main():
    init_db()
    parser = argparse.ArgumentParser(description="Workspace Documentation Manager for Agents")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Set command
    parser_set = subparsers.add_parser("set", help="Set or update documentation for a path")
    parser_set.add_argument("path", help="Relative path to the file or directory")
    parser_set.add_argument("-d", "--desc", help="Short description of the file/directory")
    parser_set.add_argument("-n", "--notes", help="Specific notes or rules for the AI Agent")
    
    # Get command
    parser_get = subparsers.add_parser("get", help="Get documentation for a path")
    parser_get.add_argument("path", help="Relative path to the file or directory")
    
    # Delete command
    parser_delete = subparsers.add_parser("delete", help="Delete documentation for a path")
    parser_delete.add_argument("path", help="Relative path to the file or directory")
    
    # Scan command
    subparsers.add_parser("scan", help="Scan workspace for undocumented files")

    # Audit command
    subparsers.add_parser(
        "audit",
        help="Report managed directories/files that are missing meaningful descriptions",
    )
    
    # Export command
    subparsers.add_parser("export", help="Deprecated compatibility command; no markdown file is generated")
    
    args = parser.parse_args()
    
    if args.command == "set":
        cmd_set(args)
    elif args.command == "get":
        cmd_get(args)
    elif args.command == "delete":
        cmd_delete(args)
    elif args.command == "scan":
        cmd_scan(args)
    elif args.command == "audit":
        cmd_audit(args)
    elif args.command == "export":
        cmd_export(args)

if __name__ == "__main__":
    main()

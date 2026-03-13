"""Modular Architecture CLI — 模块依赖关系管理工具。

提供模块注册、依赖声明、接口契约、依赖图可视化、
环检测 / 跨层违规检查以及并行开发分组功能。
"""

import argparse
import shutil
import sqlite3
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
REPO_ROOT = SKILL_DIR.parent.parent.parent  # .agents/skills/modular-arch -> repo
DOCS_DIR = REPO_ROOT / "docs"
TEMPLATE_DB = SKILL_DIR / "modular_arch.db"
RUNTIME_DB = DOCS_DIR / "modular_arch.db"

# ---------------------------------------------------------------------------
# Valid enum values
# ---------------------------------------------------------------------------
VALID_LAYERS = ("frontend", "backend", "shared", "infra")
VALID_DEP_TYPES = ("imports", "calls_api", "implements", "extends")

# Cross-layer rules: (from_layer, to_layer, dep_type | None) -> forbidden?
# dep_type=None means all types are forbidden for that layer pair.
# dep_type=specific means only that type is forbidden.
# Note: backend→frontend via calls_api is ALLOWED (serving templates).
FORBIDDEN_EDGES: set[tuple[str, str, str | None]] = {
    ("backend", "frontend", "imports"),    # backend must not import frontend code
    ("infra", "frontend", None),           # infra must not depend on frontend at all
    ("infra", "backend", None),            # infra must not depend on backend at all
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
        CREATE TABLE IF NOT EXISTS modules (
            name        TEXT PRIMARY KEY,
            path        TEXT NOT NULL,
            layer       TEXT NOT NULL,
            description TEXT,
            updated_at  TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS dependencies (
            from_module TEXT NOT NULL REFERENCES modules(name),
            to_module   TEXT NOT NULL REFERENCES modules(name),
            dep_type    TEXT NOT NULL,
            description TEXT,
            updated_at  TEXT NOT NULL,
            PRIMARY KEY (from_module, to_module, dep_type)
        );
        CREATE TABLE IF NOT EXISTS interfaces (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            module_name TEXT NOT NULL REFERENCES modules(name),
            iface_name  TEXT NOT NULL,
            signature   TEXT,
            description TEXT,
            updated_at  TEXT NOT NULL,
            UNIQUE(module_name, iface_name)
        );
    """)


def _now() -> str:
    return datetime.now().isoformat()

# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------

def cmd_register(args: argparse.Namespace) -> None:
    layer = args.layer
    if layer not in VALID_LAYERS:
        print(f"Error: layer must be one of {VALID_LAYERS}, got '{layer}'")
        return
    with _connect() as conn:
        _init_tables(conn)
        conn.execute(
            """INSERT OR REPLACE INTO modules (name, path, layer, description, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (args.name, args.path, layer, args.desc or "", _now()),
        )
        conn.commit()
    print(f"Module '{args.name}' registered (layer={layer}).")


def cmd_depend(args: argparse.Namespace) -> None:
    dep_type = args.type
    if dep_type not in VALID_DEP_TYPES:
        print(f"Error: dep_type must be one of {VALID_DEP_TYPES}, got '{dep_type}'")
        return
    with _connect() as conn:
        _init_tables(conn)
        # Verify both modules exist
        for mod in (args.from_mod, args.to_mod):
            row = conn.execute("SELECT 1 FROM modules WHERE name=?", (mod,)).fetchone()
            if not row:
                print(f"Error: module '{mod}' not registered. Use 'register' first.")
                return
        conn.execute(
            """INSERT OR REPLACE INTO dependencies
               (from_module, to_module, dep_type, description, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (args.from_mod, args.to_mod, dep_type, args.desc or "", _now()),
        )
        conn.commit()
    print(f"Dependency added: {args.from_mod} --[{dep_type}]--> {args.to_mod}")


def cmd_undepend(args: argparse.Namespace) -> None:
    with _connect() as conn:
        _init_tables(conn)
        cur = conn.execute(
            "DELETE FROM dependencies WHERE from_module=? AND to_module=?",
            (args.from_mod, args.to_mod),
        )
        conn.commit()
    if cur.rowcount:
        print(f"Removed all dependencies: {args.from_mod} --> {args.to_mod}")
    else:
        print(f"No dependency found: {args.from_mod} --> {args.to_mod}")


def cmd_interface(args: argparse.Namespace) -> None:
    with _connect() as conn:
        _init_tables(conn)
        row = conn.execute("SELECT 1 FROM modules WHERE name=?", (args.module,)).fetchone()
        if not row:
            print(f"Error: module '{args.module}' not registered.")
            return
        conn.execute(
            """INSERT OR REPLACE INTO interfaces
               (module_name, iface_name, signature, description, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (args.module, args.iface_name, args.sig or "", args.desc or "", _now()),
        )
        conn.commit()
    print(f"Interface '{args.iface_name}' registered on module '{args.module}'.")


def cmd_show(args: argparse.Namespace) -> None:
    with _connect() as conn:
        _init_tables(conn)
        mod = conn.execute("SELECT * FROM modules WHERE name=?", (args.name,)).fetchone()
        if not mod:
            print(f"Module '{args.name}' not found.")
            return

        print(f"=== Module: {mod['name']} ===")
        print(f"  Path:        {mod['path']}")
        print(f"  Layer:       {mod['layer']}")
        print(f"  Description: {mod['description']}")
        print(f"  Updated:     {mod['updated_at']}")

        # Outgoing deps
        out_deps = conn.execute(
            "SELECT to_module, dep_type, description FROM dependencies WHERE from_module=?",
            (args.name,),
        ).fetchall()
        if out_deps:
            print("  Depends on:")
            for d in out_deps:
                print(f"    --> {d['to_module']} [{d['dep_type']}] {d['description']}")

        # Incoming deps
        in_deps = conn.execute(
            "SELECT from_module, dep_type, description FROM dependencies WHERE to_module=?",
            (args.name,),
        ).fetchall()
        if in_deps:
            print("  Depended on by:")
            for d in in_deps:
                print(f"    <-- {d['from_module']} [{d['dep_type']}] {d['description']}")

        # Interfaces
        ifaces = conn.execute(
            "SELECT iface_name, signature, description FROM interfaces WHERE module_name=?",
            (args.name,),
        ).fetchall()
        if ifaces:
            print("  Interfaces:")
            for i in ifaces:
                sig = f" | {i['signature']}" if i["signature"] else ""
                print(f"    • {i['iface_name']}{sig}  {i['description']}")


def cmd_graph(args: argparse.Namespace) -> None:
    with _connect() as conn:
        _init_tables(conn)
        modules = conn.execute("SELECT name, layer FROM modules").fetchall()
        deps = conn.execute(
            "SELECT from_module, to_module, dep_type FROM dependencies"
        ).fetchall()

    if not modules:
        print("No modules registered yet.")
        return

    # Group by layer
    layers: dict[str, list[str]] = defaultdict(list)
    for m in modules:
        layers[m["layer"]].append(m["name"])

    lines = ["graph LR"]
    for layer, members in layers.items():
        lines.append(f"  subgraph {layer}")
        for name in members:
            lines.append(f"    {name}")
        lines.append("  end")
    for d in deps:
        label = d["dep_type"]
        lines.append(f"  {d['from_module']} -->|{label}| {d['to_module']}")

    print("```mermaid")
    print("\n".join(lines))
    print("```")


def _build_adj(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """Build adjacency list from dependencies table."""
    adj: dict[str, list[str]] = defaultdict(list)
    deps = conn.execute("SELECT from_module, to_module FROM dependencies").fetchall()
    for d in deps:
        adj[d["from_module"]].append(d["to_module"])
    return adj


def _find_cycles(adj: dict[str, list[str]], nodes: list[str]) -> list[list[str]]:
    """Detect all cycles using DFS."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in nodes}
    path: list[str] = []
    cycles: list[list[str]] = []

    def dfs(u: str) -> None:
        color[u] = GRAY
        path.append(u)
        for v in adj.get(u, []):
            if v not in color:
                continue
            if color[v] == GRAY:
                idx = path.index(v)
                cycles.append(path[idx:] + [v])
            elif color[v] == WHITE:
                dfs(v)
        path.pop()
        color[u] = BLACK

    for n in nodes:
        if color[n] == WHITE:
            dfs(n)
    return cycles


def cmd_check(args: argparse.Namespace) -> None:
    with _connect() as conn:
        _init_tables(conn)
        modules = {
            r["name"]: r["layer"]
            for r in conn.execute("SELECT name, layer FROM modules").fetchall()
        }
        deps = conn.execute(
            "SELECT from_module, to_module, dep_type FROM dependencies"
        ).fetchall()
        adj = _build_adj(conn)

    if not modules:
        print("No modules registered yet.")
        return

    issues: list[str] = []

    # 1. Cycle detection
    cycles = _find_cycles(adj, list(modules.keys()))
    for cyc in cycles:
        issues.append(f"[CYCLE] {' -> '.join(cyc)}")

    # 2. Cross-layer violations
    for d in deps:
        f_layer = modules.get(d["from_module"])
        t_layer = modules.get(d["to_module"])
        if not f_layer or not t_layer:
            continue
        # Check if this specific (layer, layer, type) is forbidden,
        # or if (layer, layer, None) is forbidden (meaning all types).
        is_forbidden = (
            (f_layer, t_layer, d["dep_type"]) in FORBIDDEN_EDGES
            or (f_layer, t_layer, None) in FORBIDDEN_EDGES
        )
        if is_forbidden:
            issues.append(
                f"[LAYER VIOLATION] {d['from_module']}({f_layer}) "
                f"--[{d['dep_type']}]--> {d['to_module']}({t_layer})"
            )

    if issues:
        print(f"Found {len(issues)} issue(s):")
        for iss in issues:
            print(f"  ✗ {iss}")
    else:
        print("All checks passed. No cycles or layer violations detected.")


def cmd_parallel(args: argparse.Namespace) -> None:
    with _connect() as conn:
        _init_tables(conn)
        modules = {
            r["name"]: r["layer"]
            for r in conn.execute("SELECT name, layer FROM modules").fetchall()
        }
        deps = conn.execute(
            "SELECT from_module, to_module FROM dependencies"
        ).fetchall()
        iface_modules = {
            r["module_name"]
            for r in conn.execute(
                "SELECT DISTINCT module_name FROM interfaces"
            ).fetchall()
        }

    if not modules:
        print("No modules registered yet.")
        return

    # Find cross-layer dependency pairs
    pairs_aligned: list[tuple[str, str]] = []
    pairs_unaligned: list[tuple[str, str, str]] = []  # (from, to, missing_side)

    for d in deps:
        fl = modules.get(d["from_module"])
        tl = modules.get(d["to_module"])
        if fl and tl and fl != tl:
            from_has = d["from_module"] in iface_modules
            to_has = d["to_module"] in iface_modules
            if from_has and to_has:
                pairs_aligned.append((d["from_module"], d["to_module"]))
            else:
                missing = []
                if not from_has:
                    missing.append(d["from_module"])
                if not to_has:
                    missing.append(d["to_module"])
                pairs_unaligned.append(
                    (d["from_module"], d["to_module"], ", ".join(missing))
                )

    # Independent modules (no cross-layer deps)
    involved = {d["from_module"] for d in deps} | {d["to_module"] for d in deps}
    independent = [m for m in modules if m not in involved]

    print("=== Parallel Development Groups ===\n")

    if pairs_aligned:
        print("✅ Contract Aligned (can develop in parallel):")
        for f, t in pairs_aligned:
            print(f"   {f} ({modules[f]}) <--> {t} ({modules[t]})")

    if pairs_unaligned:
        print("\n⚠️  Contract Pending (align interfaces first):")
        for f, t, miss in pairs_unaligned:
            print(f"   {f} ({modules[f]}) <--> {t} ({modules[t]})  [missing: {miss}]")

    if independent:
        print("\n🟢 Independent (no cross-layer deps, freely parallelisable):")
        for m in independent:
            print(f"   {m} ({modules[m]})")

    if not pairs_aligned and not pairs_unaligned and not independent:
        print("No cross-layer dependencies found.")

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Modular Architecture CLI — 模块依赖关系管理"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # register
    p = sub.add_parser("register", help="注册/更新模块")
    p.add_argument("name", help="模块唯一名称")
    p.add_argument("-p", "--path", required=True, help="模块相对路径")
    p.add_argument("-l", "--layer", required=True, help="架构层级: frontend/backend/shared/infra")
    p.add_argument("-d", "--desc", help="模块描述")

    # depend
    p = sub.add_parser("depend", help="添加依赖关系")
    p.add_argument("from_mod", help="依赖方（主动方）")
    p.add_argument("to_mod", help="被依赖方")
    p.add_argument("-t", "--type", required=True, help="依赖类型: imports/calls_api/implements/extends")
    p.add_argument("-d", "--desc", help="依赖说明")

    # undepend
    p = sub.add_parser("undepend", help="移除依赖关系")
    p.add_argument("from_mod", help="依赖方")
    p.add_argument("to_mod", help="被依赖方")

    # interface
    p = sub.add_parser("interface", help="注册接口契约")
    p.add_argument("module", help="模块名")
    p.add_argument("iface_name", help="接口名")
    p.add_argument("-s", "--sig", help="函数签名或 API schema")
    p.add_argument("-d", "--desc", help="接口描述")

    # show
    p = sub.add_parser("show", help="查看模块详情")
    p.add_argument("name", help="模块名称")

    # graph
    sub.add_parser("graph", help="输出 Mermaid 依赖图")

    # check
    sub.add_parser("check", help="环检测 + 跨层违规检查")

    # parallel
    sub.add_parser("parallel", help="并行开发分组分析")

    args = parser.parse_args()
    {
        "register": cmd_register,
        "depend": cmd_depend,
        "undepend": cmd_undepend,
        "interface": cmd_interface,
        "show": cmd_show,
        "graph": cmd_graph,
        "check": cmd_check,
        "parallel": cmd_parallel,
    }[args.command](args)


if __name__ == "__main__":
    main()

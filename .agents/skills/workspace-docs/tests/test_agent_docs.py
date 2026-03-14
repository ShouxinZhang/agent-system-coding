import importlib.util
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path


def _load_agent_docs_module():
    script_path = (
        Path(__file__).resolve().parents[1] / "scripts" / "agent_docs.py"
    )
    spec = importlib.util.spec_from_file_location("workspace_agent_docs", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


agent_docs = _load_agent_docs_module()


class AgentDocsPolicyTests(unittest.TestCase):
    def _create_conn(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE workspace_nodes (
                path TEXT PRIMARY KEY,
                type TEXT,
                description TEXT,
                agent_notes TEXT,
                last_updated TEXT
            )
            """
        )
        return conn

    def _init_git_repo(self, root: Path):
        subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
        (root / ".gitignore").write_text(".vscode/\n.venv/\n", encoding="utf-8")

    def test_should_document_file_respects_directory_only_and_key_files(self):
        self.assertTrue(agent_docs._should_document_file("src/app.py"))
        self.assertTrue(agent_docs._should_document_file("README.md"))
        self.assertFalse(
            agent_docs._should_document_file("docs/session-logs/20260314-abc.md")
        )
        self.assertFalse(
            agent_docs._should_document_file("docs/plan/image/demo/diagram.png")
        )
        self.assertFalse(agent_docs._should_document_file(".venv/bin/python"))

    def test_git_visible_files_follow_gitignore_rules(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._init_git_repo(root)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
            (root / ".vscode").mkdir()
            (root / ".vscode" / "settings.json").write_text("{}", encoding="utf-8")
            (root / "docs" / "session-logs").mkdir(parents=True)
            (root / "docs" / "session-logs" / "run.md").write_text(
                "# log\n", encoding="utf-8"
            )

            files = sorted(agent_docs._iter_git_tracked_and_visible_files(root))

        self.assertIn(".gitignore", files)
        self.assertIn("src/app.py", files)
        self.assertIn("docs/session-logs/run.md", files)
        self.assertNotIn(".vscode/settings.json", files)

    def test_audit_focuses_on_managed_code_files_not_session_logs(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._init_git_repo(root)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
            (root / "docs" / "session-logs").mkdir(parents=True)
            (root / "docs" / "session-logs" / "run.md").write_text(
                "# log\n", encoding="utf-8"
            )

            conn = self._create_conn()
            conn.execute(
                """
                INSERT INTO workspace_nodes (path, type, description, agent_notes, last_updated)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("docs/session-logs", "directory", "session logs", "", "2026-03-14T00:00:00"),
            )
            conn.commit()

            directory_issues, file_issues = agent_docs._collect_audit_issues(conn, root)

        self.assertIn("src", directory_issues)
        self.assertIn("src/app.py", file_issues)
        self.assertNotIn("docs/session-logs/run.md", file_issues)


if __name__ == "__main__":
    unittest.main()

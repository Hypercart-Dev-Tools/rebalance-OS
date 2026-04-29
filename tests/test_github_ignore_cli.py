"""CLI tests for the GitHub ingest ignore list."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from typer.testing import CliRunner

from rebalance.cli import app
from rebalance.ingest import audit as audit_module
from rebalance.ingest import config as config_module
from rebalance.ingest.config import get_github_ignored_repos
from rebalance.ingest.db import db_connection, ensure_github_schema, ensure_semantic_schema


class GitHubIgnoreCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

        self._orig_config_path = config_module.CONFIG_PATH
        config_module.CONFIG_PATH = Path(self._tmp.name) / "rbos.config"

        self._orig_audit_path = audit_module.AUDIT_LOG_PATH
        audit_module.AUDIT_LOG_PATH = Path(self._tmp.name) / "logs" / "agent-audit.json"

    def tearDown(self) -> None:
        config_module.CONFIG_PATH = self._orig_config_path
        audit_module.AUDIT_LOG_PATH = self._orig_audit_path

    def test_add_and_list_ignored_repo(self) -> None:
        result = self.runner.invoke(app, ["config", "add-github-ignored-repo", "DLT-HUB/dlt"])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(get_github_ignored_repos(), ["dlt-hub/dlt"])

        listed = self.runner.invoke(app, ["config", "list-github-ignored-repos"])
        self.assertEqual(listed.exit_code, 0)
        self.assertIn("dlt-hub/dlt", listed.stdout)

    def test_add_with_dry_run_reports_counts_without_deleting(self) -> None:
        db_path = Path(self._tmp.name) / "rebalance.db"
        with db_connection(db_path) as conn:
            ensure_github_schema(conn)
            ensure_semantic_schema(conn)
            conn.execute(
                """
                INSERT INTO github_documents
                    (repo_full_name, source_type, source_number, doc_type, source_key,
                     title, body, content_hash, embedded_hash, updated_at, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "dlt-hub/dlt",
                    "issue",
                    1,
                    "item_body",
                    "dlt-hub/dlt:issue:1:item",
                    "Test",
                    "Body",
                    "hash",
                    None,
                    "2026-04-28T00:00:00Z",
                    "2026-04-28T00:00:00Z",
                ),
            )
            conn.execute(
                """
                INSERT INTO semantic_documents
                    (source_type, source_table, source_pk, doc_kind, title, body, content_hash,
                     embedded_hash, embedded_model_version, embedded_at, metadata_json,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "github",
                    "github_documents",
                    "dlt-hub/dlt:issue:1:item",
                    "item_body",
                    "Test",
                    "Body",
                    "hash",
                    None,
                    None,
                    None,
                    "{}",
                    "2026-04-28T00:00:00Z",
                    "2026-04-28T00:00:00Z",
                ),
            )
            conn.commit()

        result = self.runner.invoke(
            app,
            [
                "config",
                "add-github-ignored-repo",
                "dlt-hub/dlt",
                "--dry-run",
                "--database",
                str(db_path),
            ],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("would purge", result.stdout)

        with db_connection(db_path, ensure_github_schema) as conn:
            doc_count = conn.execute("SELECT COUNT(*) FROM github_documents").fetchone()[0]
            semantic_count = conn.execute("SELECT COUNT(*) FROM semantic_documents").fetchone()[0]
        self.assertEqual(doc_count, 1)
        self.assertEqual(semantic_count, 1)

    def test_add_with_purge_requires_confirm(self) -> None:
        db_path = Path(self._tmp.name) / "rebalance.db"
        result = self.runner.invoke(
            app,
            [
                "config",
                "add-github-ignored-repo",
                "dlt-hub/dlt",
                "--purge",
                "--database",
                str(db_path),
            ],
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("--confirm", result.stdout)

    def test_add_with_purge_and_confirm_deletes_rows_and_writes_audit_log(self) -> None:
        db_path = Path(self._tmp.name) / "rebalance.db"
        with db_connection(db_path) as conn:
            ensure_github_schema(conn)
            ensure_semantic_schema(conn)
            conn.execute(
                "INSERT INTO github_activity (login, repo_full_name, scan_date, commits, pushes, prs_opened, prs_merged, issues_opened, issue_comments, reviews, last_active_at, scanned_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("tester", "dlt-hub/dlt", "2026-04-28", 1, 1, 0, 0, 0, 0, 0, "2026-04-28T00:00:00Z", "2026-04-28T00:00:00Z"),
            )
            conn.execute(
                """
                INSERT INTO github_documents
                    (repo_full_name, source_type, source_number, doc_type, source_key,
                     title, body, content_hash, embedded_hash, updated_at, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "dlt-hub/dlt",
                    "issue",
                    1,
                    "item_body",
                    "dlt-hub/dlt:issue:1:item",
                    "Test",
                    "Body",
                    "hash",
                    None,
                    "2026-04-28T00:00:00Z",
                    "2026-04-28T00:00:00Z",
                ),
            )
            conn.execute(
                """
                INSERT INTO semantic_documents
                    (source_type, source_table, source_pk, doc_kind, title, body, content_hash,
                     embedded_hash, embedded_model_version, embedded_at, metadata_json,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "github",
                    "github_documents",
                    "dlt-hub/dlt:issue:1:item",
                    "item_body",
                    "Test",
                    "Body",
                    "hash",
                    None,
                    None,
                    None,
                    "{}",
                    "2026-04-28T00:00:00Z",
                    "2026-04-28T00:00:00Z",
                ),
            )
            conn.commit()

        result = self.runner.invoke(
            app,
            [
                "config",
                "add-github-ignored-repo",
                "dlt-hub/dlt",
                "--purge",
                "--confirm",
                "--database",
                str(db_path),
            ],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Purged", result.stdout)

        with db_connection(db_path, ensure_github_schema) as conn:
            activity_count = conn.execute("SELECT COUNT(*) FROM github_activity").fetchone()[0]
            doc_count = conn.execute("SELECT COUNT(*) FROM github_documents").fetchone()[0]
            semantic_count = conn.execute("SELECT COUNT(*) FROM semantic_documents").fetchone()[0]
        self.assertEqual(activity_count, 0)
        self.assertEqual(doc_count, 0)
        self.assertEqual(semantic_count, 0)

        audit_entries = json.loads(audit_module.AUDIT_LOG_PATH.read_text(encoding="utf-8"))
        self.assertEqual(audit_entries[-1]["action"], "github_repo_purge")
        self.assertEqual(audit_entries[-1]["target"], "dlt-hub/dlt")
        self.assertEqual(audit_entries[-1]["dry_run"], False)

    def test_explicit_github_sync_rejects_ignored_repo(self) -> None:
        self.runner.invoke(app, ["config", "add-github-ignored-repo", "dlt-hub/dlt"])
        result = self.runner.invoke(
            app,
            ["github-sync-artifacts", "--repo", "dlt-hub/dlt"],
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("GitHub repo is ignored", result.stdout)

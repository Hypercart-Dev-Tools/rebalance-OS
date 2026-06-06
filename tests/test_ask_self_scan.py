"""Tests for the ask_self device-local index collector (spike)."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from rebalance.ingest.ask_self_scan import (
    derive_repo_full_name,
    iter_repo_harnesses,
    sync_ask_self_indexes,
    summarize_ask_self_indexes,
)


def _make_ask_self_repo(
    root: Path,
    name: str,
    *,
    remote_url: str | None = "https://github.com/Acme/widget.git",
    head_sha: str = "abc123",
    total_chunks: int = 42,
    build_index: bool = True,
    github_owner: str | None = "Acme",
    github_repo: str | None = "widget",
) -> Path:
    """Create a fake ask_self repo under *root*; return its repo root."""
    repo = root / name
    (repo / "ask_self" / "index").mkdir(parents=True, exist_ok=True)

    harness: dict = {
        "repo_label": name,
        "repo_kind": "python-repo",
        "db_path": "ask_self/index/idx.sqlite",
    }
    if github_owner and github_repo:
        harness["github"] = {"owner": github_owner, "repo": github_repo}
    (repo / "ask_self" / "ask_self_harness.json").write_text(
        json.dumps(harness), encoding="utf-8"
    )

    if build_index:
        idx = repo / "ask_self" / "index" / "idx.sqlite"
        conn = sqlite3.connect(str(idx))
        conn.execute("DROP TABLE IF EXISTS repo_metadata")
        conn.execute(
            """
            CREATE TABLE repo_metadata (
                slug TEXT, repo_label TEXT, repo_kind TEXT, branch TEXT,
                head_sha TEXT, last_commit_at TEXT, remote_url TEXT,
                file_count INTEGER, loc_total INTEGER, repo_size_bytes INTEGER,
                ingested_at TEXT, embed_model TEXT, embed_dim INTEGER,
                total_chunks INTEGER, harness_config_path TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO repo_metadata VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                name.lower(), name, "python-repo", "main", head_sha,
                "2026-06-01T00:00:00Z", remote_url, 100, 5000, 999,
                "2026-06-01T03:00:00Z", "Qwen/Qwen3-Embedding-0.6B", 1024,
                total_chunks, str(repo / "ask_self" / "ask_self_harness.json"),
            ),
        )
        conn.commit()
        conn.close()
    return repo


class DeriveRepoFullNameTests(unittest.TestCase):
    def test_https(self) -> None:
        self.assertEqual(
            derive_repo_full_name("https://github.com/Owner/Repo.git"), "Owner/Repo"
        )

    def test_https_no_suffix(self) -> None:
        self.assertEqual(
            derive_repo_full_name("https://github.com/Owner/Repo"), "Owner/Repo"
        )

    def test_ssh_scp_form(self) -> None:
        self.assertEqual(
            derive_repo_full_name("git@github.com:Owner/Repo.git"), "Owner/Repo"
        )

    def test_preserves_casing(self) -> None:
        self.assertEqual(
            derive_repo_full_name("https://github.com/Hypercart-Dev-Tools/rebalance-OS.git"),
            "Hypercart-Dev-Tools/rebalance-OS",
        )

    def test_none_and_garbage(self) -> None:
        self.assertIsNone(derive_repo_full_name(None))
        self.assertIsNone(derive_repo_full_name(""))
        self.assertIsNone(derive_repo_full_name("not-a-url"))


class ScannerTests(unittest.TestCase):
    def test_finds_harness_and_dedupes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_ask_self_repo(root, "alpha")
            _make_ask_self_repo(root / "nested", "beta", build_index=False)
            # Noise that must be pruned, not descended into.
            (root / "node_modules" / "junk").mkdir(parents=True)

            found = dict(iter_repo_harnesses([root]))
            found_names = sorted(p.name for p in found)
            self.assertEqual(found_names, ["alpha", "beta"])
            # Overlapping roots should not double-yield.
            twice = list(iter_repo_harnesses([root, root / "nested"]))
            self.assertEqual(len({rp for rp, _ in twice}), 2)


class SyncTests(unittest.TestCase):
    def _db(self, tmp: Path) -> Path:
        # A bare file is enough; sync_ask_self_indexes runs migrations itself.
        db = tmp / "rebalance.db"
        sqlite3.connect(str(db)).close()
        return db

    def test_sync_upserts_and_bridges_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repos"
            root.mkdir()
            _make_ask_self_repo(root, "widget")
            db = self._db(Path(tmp))

            result = sync_ask_self_indexes(db, roots=[root], device_id="testdev")
            self.assertEqual(result.found, 1)
            self.assertEqual(result.inserted, 1)

            rows = summarize_ask_self_indexes(db)["indexes"]
            self.assertEqual(len(rows), 1)
            row = rows[0]
            # remote_url (https://github.com/Acme/widget.git) -> owner/repo bridge
            self.assertEqual(row["repo_full_name"], "Acme/widget")
            self.assertTrue(row["index_built"])
            self.assertEqual(row["total_chunks"], 42)
            self.assertEqual(row["device_id"], "testdev")

    def test_resync_is_unchanged_then_updated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repos"
            root.mkdir()
            _make_ask_self_repo(root, "widget", head_sha="sha1")
            db = self._db(Path(tmp))

            sync_ask_self_indexes(db, roots=[root], device_id="testdev")
            again = sync_ask_self_indexes(db, roots=[root], device_id="testdev")
            self.assertEqual(again.unchanged, 1)
            self.assertEqual(again.updated, 0)

            # Re-ingest moved the head SHA -> the row is "updated", not duplicated.
            _make_ask_self_repo(root, "widget", head_sha="sha2", total_chunks=99)
            third = sync_ask_self_indexes(db, roots=[root], device_id="testdev")
            self.assertEqual(third.updated, 1)
            self.assertEqual(third.inserted, 0)
            rows = summarize_ask_self_indexes(db)["indexes"]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["head_sha"], "sha2")

    def test_harness_without_index_is_recorded_unbuilt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repos"
            root.mkdir()
            _make_ask_self_repo(
                root, "skeleton", build_index=False,
                github_owner="Acme", github_repo="skeleton",
            )
            db = self._db(Path(tmp))

            sync_ask_self_indexes(db, roots=[root], device_id="testdev")
            row = summarize_ask_self_indexes(db)["indexes"][0]
            self.assertFalse(row["index_built"])
            # Falls back to harness github.owner/repo when no index/remote exists.
            self.assertEqual(row["repo_full_name"], "Acme/skeleton")

    def test_watched_join(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repos"
            root.mkdir()
            _make_ask_self_repo(root, "widget")  # remote -> Acme/widget
            db = self._db(Path(tmp))

            # Make Acme/widget "watched" via the pushed-repos discovery source.
            now = datetime.now(timezone.utc).isoformat()
            conn = sqlite3.connect(str(db))
            from rebalance.ingest.db import run_migrations
            run_migrations(conn)
            conn.execute(
                "INSERT INTO github_pushed_repos "
                "(repo_full_name, pushed_at, first_seen_at, last_seen_at) VALUES (?,?,?,?)",
                ("Acme/widget", now, now, now),
            )
            conn.commit()
            conn.close()

            sync_ask_self_indexes(db, roots=[root], device_id="testdev")
            out = summarize_ask_self_indexes(db)
            self.assertTrue(out["indexes"][0]["watched"])
            self.assertEqual(out["summary"]["watched"], 1)
            self.assertEqual(out["summary"]["built"], 1)
            self.assertEqual(out["summary"]["devices"], ["testdev"])


if __name__ == "__main__":
    unittest.main()

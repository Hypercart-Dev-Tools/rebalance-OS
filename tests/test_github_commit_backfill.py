"""Regression coverage for GH-169 Phase 1 — local-git commit backfill.

Each test here maps to a QA gate in
PROJECT/2-WORKING/GH-169-COMMIT-HISTORY-COVERAGE.md. The synthetic-repo fixture
builds a real git repo rather than mocking git, because the defects this phase
fixes (merge commits invisible to --name-only, multi-line messages split by a
naive parser) only appear against real git output.
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from rebalance.ingest.db import db_connection, ensure_github_schema, ensure_schema
from rebalance.ingest.db import github as gh
from rebalance.ingest.github_commit_backfill import (
    backfill_commits,
    resolve_clone,
    _parse_log,
)

REPO = "Hypercart-Dev-Tools/rebalance-OS"

# The real commit that started GH-169: a multi-line body carrying the origin
# repo, an @-pinned upstream SHA, and slashes -- everything a naive parser eats.
CLIO_MESSAGE = """feat: bring CLIO into rebalance-OS as its canonical home

Pull the latest CLIO skill (append+cursor exporter for cross-device
accumulation, atomic same-fs writes, shrink-cursor recovery) from
Claude-AI-Tools-Ventura-County/CLIO-Claude-Prompts@ef96a44, plus
README/LICENSE, into utils/CLIO/.
"""


def _git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *args], capture_output=True, text=True
    )
    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


def _write(path: Path, rel: str, body: str = "x") -> None:
    target = path / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body)


class _Fixture:
    """A real git repo with a direct commit, a merge commit, and a PR-style commit."""

    def __init__(self, root: Path):
        self.path = root / "clone"
        self.path.mkdir()
        _git(self.path, "init", "-q", "-b", "development")
        _git(self.path, "config", "user.email", "t@example.com")
        _git(self.path, "config", "user.name", "Tester")

        _write(self.path, "README.md", "base")
        _git(self.path, "add", "-A")
        _git(self.path, "commit", "-q", "-m", "chore: base")
        self.base_sha = _git(self.path, "rev-parse", "HEAD")

        # The CLIO-shaped direct commit: multi-line message, 3 files, one dir.
        _write(self.path, "utils/CLIO/INSTALL.md", "install")
        _write(self.path, "utils/CLIO/README.md", "readme")
        _write(self.path, "utils/CLIO/LICENSE", "license")
        _git(self.path, "add", "-A")
        _git(self.path, "commit", "-q", "-m", CLIO_MESSAGE)
        self.clio_sha = _git(self.path, "rev-parse", "HEAD")

        # A branch merged back with a real merge commit.
        _git(self.path, "checkout", "-q", "-b", "feature")
        _write(self.path, "feature.txt", "feat")
        _git(self.path, "add", "-A")
        _git(self.path, "commit", "-q", "-m", "feat: add feature")
        self.feature_sha = _git(self.path, "rev-parse", "HEAD")
        _git(self.path, "checkout", "-q", "development")
        _git(self.path, "merge", "-q", "--no-ff", "feature", "-m", "Merge pull request #1")
        self.merge_sha = _git(self.path, "rev-parse", "HEAD")

        # A real clone always has remote-tracking refs, and the walk is scoped
        # to `--remotes=origin` precisely so it does not depend on which branch
        # happens to be checked out. Mirror that here rather than testing a
        # shape no clone actually has.
        self.publish("development")

    def publish(self, *branches: str) -> None:
        """Point origin/<branch> at the local branch, as a fetch would."""
        for branch in branches:
            _git(self.path, "update-ref", f"refs/remotes/origin/{branch}", branch)


class GitCommitBackfillTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.db = root / "test.db"
        with db_connection(self.db, ensure_schema):
            pass
        with db_connection(self.db, ensure_github_schema):
            pass
        self.fx = _Fixture(root)

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, **kw):
        return backfill_commits(
            self.db, REPO, clone_path=self.fx.path, fetch=False, **kw
        )

    def _rows(self):
        with db_connection(self.db, ensure_github_schema) as conn:
            return {
                r["sha"]: r for r in conn.execute(
                    "SELECT * FROM github_direct_commits WHERE repo_full_name = ?", (REPO,)
                )
            }

    # -- QA gate: the gap closes, and cfeafe4-shaped commits carry their paths --

    def test_backfill_captures_direct_commit_with_full_message_and_paths(self):
        result = self._run()
        self.assertEqual(result.state, "ok")
        rows = self._rows()
        self.assertIn(self.fx.clio_sha, rows)

        row = rows[self.fx.clio_sha]
        # The whole multi-line body must survive, not just the subject -- the
        # provenance (origin repo + upstream SHA) lives in the body.
        self.assertIn("bring CLIO into rebalance-OS as its canonical home", row["message"])
        self.assertIn("CLIO-Claude-Prompts@ef96a44", row["message"])
        self.assertIn("utils/CLIO/", row["message"])
        self.assertEqual(row["path_coverage"], "complete")
        self.assertEqual(row["source"], "git_backfill")

        with db_connection(self.db, ensure_github_schema) as conn:
            paths = sorted(
                r[0] for r in conn.execute(
                    "SELECT path FROM github_direct_commit_files "
                    "WHERE repo_full_name = ? AND sha = ?",
                    (REPO, self.fx.clio_sha),
                )
            )
        self.assertEqual(
            paths,
            ["utils/CLIO/INSTALL.md", "utils/CLIO/LICENSE", "utils/CLIO/README.md"],
        )

    # -- QA gate: merge commits captured (missed by BOTH pre-existing paths) --

    def test_merge_commits_are_captured_with_their_paths(self):
        result = self._run()
        self.assertGreaterEqual(result.merge_commits, 1)
        rows = self._rows()
        self.assertIn(self.fx.merge_sha, rows)
        with db_connection(self.db, ensure_github_schema) as conn:
            paths = [
                r[0] for r in conn.execute(
                    "SELECT path FROM github_direct_commit_files "
                    "WHERE repo_full_name = ? AND sha = ?",
                    (REPO, self.fx.merge_sha),
                )
            ]
        # Without `-m --first-parent` git prints nothing for a merge; that
        # silence is how merge commits went uncollected.
        self.assertIn("feature.txt", paths)

    # -- QA gate: PR commits are not duplicated --

    def test_pr_commits_are_not_duplicated(self):
        with db_connection(self.db, ensure_github_schema) as conn:
            conn.execute(
                "INSERT INTO github_commits "
                "(repo_full_name, item_type, item_number, sha, author_login, message, "
                " committed_at, html_url, fetched_at) "
                "VALUES (?, 'pull_request', 1, ?, 'noelsaw1', 'feat: add feature', "
                "'2026-07-18T00:00:00Z', '', '2026-07-19T00:00:00Z')",
                (REPO, self.fx.feature_sha),
            )
            conn.commit()

        self._run()
        self.assertNotIn(self.fx.feature_sha, self._rows())

    # -- QA gate: idempotency proven, not assumed --

    def test_rerun_is_a_no_op(self):
        first = self._run()
        self.assertGreater(first.commits_inserted, 0)

        second = self._run()
        self.assertEqual(second.commits_inserted, 0)
        self.assertEqual(second.commits_updated, 0)
        self.assertEqual(second.commits_skipped_existing, second.commits_seen)

    # -- QA gate: zero API calls --

    def test_backfill_makes_no_api_calls(self):
        self.assertEqual(self._run().api_calls_used, 0)

    # -- QA gate: no-clone repos REPORT, never silently skip --

    def test_missing_clone_is_reported_as_uncoverable_not_skipped(self):
        result = backfill_commits(
            self.db, "Some-Org/never-cloned", roots=[], fetch=False
        )
        self.assertEqual(result.state, "uncoverable")
        self.assertIn("no local clone", result.reason)

        with db_connection(self.db, ensure_github_schema) as conn:
            row = conn.execute(
                "SELECT state, reason FROM github_repo_coverage WHERE repo_full_name = ?",
                ("Some-Org/never-cloned",),
            ).fetchone()
        # The durable row is the point: an uncoverable repo must be visible to
        # the Phase 3 check, not absent from it.
        self.assertIsNotNone(row)
        self.assertEqual(row["state"], "uncoverable")

    def test_resolve_clone_returns_none_when_no_roots_configured(self):
        self.assertIsNone(resolve_clone("Some-Org/never-cloned", roots=[]))

    # -- QA gate: a failed fetch warns rather than reporting clean coverage --

    def test_failed_fetch_warns_instead_of_claiming_coverage(self):
        result = backfill_commits(self.db, REPO, clone_path=self.fx.path, fetch=True)
        # The fixture has no origin remote, so the fetch must fail.
        self.assertFalse(result.fetched)
        self.assertTrue(any("stale" in w for w in result.warnings))

    # -- QA gate: conflict policy -- enrichment must never downgrade --

    def test_later_unavailable_write_cannot_downgrade_complete_row(self):
        self._run()
        before = self._rows()[self.fx.clio_sha]
        self.assertEqual(before["path_coverage"], "complete")

        # Simulate the cap-starved API path writing `unavailable` afterwards.
        with db_connection(self.db, ensure_github_schema) as conn:
            gh.upsert_direct_commit(
                conn,
                (REPO, self.fx.clio_sha, "push-999", "refs/heads/development",
                 "noelsaw1", "Tester", "clobbered", "2026-07-18T00:00:00Z", "",
                 "unavailable", "2026-07-19T00:00:00Z", "2026-07-19T00:00:00Z"),
                source="events",
            )
            conn.commit()

        after = self._rows()[self.fx.clio_sha]
        self.assertEqual(after["path_coverage"], "complete")
        self.assertEqual(after["source"], "git_backfill")

    def test_unavailable_row_is_upgraded_to_complete(self):
        with db_connection(self.db, ensure_github_schema) as conn:
            gh.upsert_direct_commit(
                conn,
                (REPO, self.fx.clio_sha, "push-1", "refs/heads/development",
                 "noelsaw1", "Tester", "stub", "2026-07-18T00:00:00Z", "",
                 "unavailable", "2026-07-19T00:00:00Z", "2026-07-19T00:00:00Z"),
                source="events",
            )
            conn.commit()

        result = self._run()
        self.assertEqual(result.commits_updated, 1)
        row = self._rows()[self.fx.clio_sha]
        self.assertEqual(row["path_coverage"], "complete")
        self.assertEqual(row["source"], "git_backfill")

    # -- parser: multi-line bodies must not be split into separate commits --

    def test_parse_log_keeps_multiline_bodies_intact(self):
        from rebalance.ingest.github_commit_backfill import _FIELD_SEP, _RECORD_SEP

        raw = (
            _FIELD_SEP.join(["sha1", "A", "a@x", "2026-07-17T20:06:18-07:00", CLIO_MESSAGE])
            + _RECORD_SEP
            + _FIELD_SEP.join(["sha2", "B", "b@x", "2026-07-16T10:00:00-07:00", "chore: two"])
            + _RECORD_SEP
        )
        parsed = _parse_log(raw)
        self.assertEqual([c["sha"] for c in parsed], ["sha1", "sha2"])
        self.assertIn("CLIO-Claude-Prompts@ef96a44", parsed[0]["message"])

    # -- scope: the default-branch assumption does not survive real repos --

    def test_default_scope_covers_branches_outside_the_default_branch(self):
        """A commit on an unmerged branch must still be captured.

        Found by running the backfill against the real clone: `origin/HEAD`
        there points at `main`, while the actual trunk is `development` -- so a
        default-branch walk enumerated the wrong branch and missed the measured
        gap completely. Walking all remote branches removes the assumption.
        """
        _git(self.fx.path, "checkout", "-q", "-b", "never-merged")
        _write(self.fx.path, "orphan.txt", "orphan")
        _git(self.fx.path, "add", "-A")
        _git(self.fx.path, "commit", "-q", "-m", "docs: only on an unmerged branch")
        orphan_sha = _git(self.fx.path, "rev-parse", "HEAD")
        _git(self.fx.path, "checkout", "-q", "development")

        self.fx.publish("development", "never-merged")

        self._run()
        self.assertIn(orphan_sha, self._rows())

    def test_explicit_branch_scopes_the_walk(self):
        self.fx.publish("development", "feature")
        result = self._run(branch="development")
        self.assertEqual(result.default_branch, "development")
        self.assertIn(self.fx.clio_sha, self._rows())

    # -- cap is reported, never a silent truncation --

    def test_cap_is_reported_not_silent(self):
        result = self._run(cap=1)
        self.assertTrue(result.capped)
        self.assertEqual(result.commits_seen, 1)
        self.assertTrue(any("capped" in w for w in result.warnings))


if __name__ == "__main__":
    unittest.main()

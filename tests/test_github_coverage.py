"""Regression coverage for GH-169 Phase 3 — completeness as a measurable property.

The gates here encode the two review findings that reframed this phase:
a stale clone must never report a confident 0 (agy r1 Blocker), and a row that
exists but carries no file data is a gap, not coverage (agy r2 Nit).
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from rebalance.ingest.db import db_connection, ensure_github_schema
from rebalance.ingest.github_commit_backfill import backfill_commits
from rebalance.ingest.github_coverage import (
    check_repo_coverage,
    coverage_health,
    CoverageReport,
    RepoCoverage,
)
from rebalance.ingest.github_direct_commits import sync_direct_commit_documents

REPO = "Hypercart-Dev-Tools/rebalance-OS"


def _git(path: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {r.stderr}")
    return r.stdout.strip()


class CoverageCheckTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.db = root / "t.db"
        with db_connection(self.db, ensure_github_schema):
            pass

        self.clone = root / "clone"
        self.clone.mkdir()
        _git(self.clone, "init", "-q", "-b", "development")
        _git(self.clone, "config", "user.email", "t@example.com")
        _git(self.clone, "config", "user.name", "T")
        for i in range(3):
            (self.clone / f"f{i}.txt").write_text(str(i))
            _git(self.clone, "add", "-A")
            _git(self.clone, "commit", "-q", "-m", f"chore: commit {i}")
        _git(self.clone, "update-ref", "refs/remotes/origin/development", "development")
        # A real clone has fetched at some point; FETCH_HEAD's mtime is the
        # network-free staleness signal, and its ABSENCE is correctly treated as
        # stale. Mirror a freshly-fetched clone rather than testing a shape no
        # working clone has.
        (self.clone / ".git" / "FETCH_HEAD").write_text("")

    def tearDown(self):
        self._tmp.cleanup()

    def _check(self, **kw):
        return check_repo_coverage(
            self.db, REPO, clone_path=self.clone, check_remote=False, **kw
        )

    def _backfill(self):
        return backfill_commits(self.db, REPO, clone_path=self.clone, fetch=False)

    # -- the headline: a real gap is reported --

    def test_uncollected_commits_report_a_collection_gap(self):
        c = self._check()
        self.assertEqual(c.collection_gap, 3)

    def test_after_backfill_and_projection_everything_reads_zero(self):
        self._backfill()
        sync_direct_commit_documents(self.db)
        c = self._check()
        self.assertEqual(c.collection_gap, 0)
        self.assertEqual(c.projection_gap, 0)
        self.assertEqual(c.orphan_count, 0)
        self.assertEqual(c.incomplete, 0)
        self.assertTrue(c.is_clean)

    # -- agy r2 Nit: presence of a row is NOT coverage --

    def test_row_without_file_data_counts_as_a_gap_not_as_covered(self):
        self._backfill()
        with db_connection(self.db, ensure_github_schema) as conn:
            sha = conn.execute(
                "SELECT sha FROM github_direct_commits WHERE repo_full_name = ? LIMIT 1",
                (REPO,),
            ).fetchone()[0]
            conn.execute(
                "UPDATE github_direct_commits SET path_coverage = 'unavailable' "
                "WHERE repo_full_name = ? AND sha = ?",
                (REPO, sha),
            )
            conn.commit()

        c = self._check()
        # The row is PRESENT. A presence-only check would score it covered and
        # report 0 -- the last route back into the #155/#157/#169 loop.
        self.assertEqual(c.incomplete, 1)
        self.assertEqual(c.collection_gap, 1)
        self.assertFalse(c.is_clean)

    # -- RC5: projection is measured independently of collection --

    def test_projection_gap_is_measured_separately_from_collection(self):
        self._backfill()
        sync_direct_commit_documents(self.db)
        with db_connection(self.db, ensure_github_schema) as conn:
            conn.execute(
                "DELETE FROM github_documents WHERE repo_full_name = ? "
                "AND doc_type = 'direct_commit'", (REPO,)
            )
            conn.commit()

        c = self._check()
        # Collection is intact; only the corpus was emptied. Exactly the
        # sync_direct_commit_documents() destroy-then-rebuild failure mode.
        self.assertEqual(c.collection_gap, 0)
        self.assertEqual(c.projection_gap, 3)
        self.assertFalse(c.is_clean)

    # -- a phantom must not cancel a real gap --

    def test_orphans_and_collection_gap_are_never_netted(self):
        self._backfill()
        with db_connection(self.db, ensure_github_schema) as conn:
            # One captured SHA that is not on the remote (force-push residue)...
            conn.execute(
                "UPDATE github_direct_commits SET sha = ? "
                "WHERE repo_full_name = ? AND sha = "
                "(SELECT sha FROM github_direct_commits WHERE repo_full_name = ? LIMIT 1)",
                ("d" * 40, REPO, REPO),
            )
            conn.commit()

        c = self._check()
        # ...produces BOTH a phantom and a real gap. A single netted number
        # would report zero here.
        self.assertEqual(c.orphan_count, 1)
        self.assertEqual(c.collection_gap, 1)

    # -- agy r1 Blocker: a stale clone must never report a confident 0 --

    def test_never_fetched_clone_reports_stale_not_zero(self):
        """The anti-self-agreement invariant, enforced without the network."""
        (self.clone / ".git" / "FETCH_HEAD").unlink()
        c = self._check()
        self.assertEqual(c.state, "stale")
        self.assertEqual(c.collection_gap, 0)  # not measured -- and not claimed as clean
        self.assertFalse(c.is_clean)

    def test_stale_clone_reports_stale_not_zero(self):
        c = check_repo_coverage(
            self.db, REPO, clone_path=self.clone, check_remote=True,
        )
        # The fixture cannot contain a real github.com tip, so this exercises
        # the anchor: unreachable or not-contained must never read as "ok, 0".
        self.assertIn(c.state, ("stale", "uncoverable"))
        self.assertNotEqual(c.state, "ok")
        self.assertTrue(c.reason)

    # -- uncoverable repos are reported, never silent --

    def test_missing_clone_is_uncoverable(self):
        c = check_repo_coverage(self.db, "Some-Org/nope", roots=[], check_remote=False)
        self.assertEqual(c.state, "uncoverable")
        self.assertFalse(c.is_clean)

    # -- health verdict --

    def test_health_is_ok_only_when_everything_is_clean(self):
        self._backfill()
        sync_direct_commit_documents(self.db)
        report = CoverageReport(repos=[self._check()], checked_at="now")
        self.assertEqual(coverage_health(report)["status"], "ok")

    def test_health_degrades_on_a_stale_clone(self):
        stale = RepoCoverage(repo=REPO, state="stale", reason="behind remote")
        report = CoverageReport(repos=[stale], checked_at="now")
        self.assertEqual(coverage_health(report)["status"], "degraded")

    def test_health_warns_rather_than_going_silent_on_uncoverable(self):
        unc = RepoCoverage(repo=REPO, state="uncoverable", reason="no clone")
        report = CoverageReport(repos=[unc], checked_at="now")
        verdict = coverage_health(report)
        self.assertEqual(verdict["status"], "warn")
        self.assertIn("uncoverable", verdict["reason"])

    def test_health_degrades_on_a_large_gap(self):
        big = RepoCoverage(repo=REPO, state="ok", collection_gap=182)
        report = CoverageReport(repos=[big], checked_at="now")
        self.assertEqual(coverage_health(report)["status"], "degraded")


if __name__ == "__main__":
    unittest.main()

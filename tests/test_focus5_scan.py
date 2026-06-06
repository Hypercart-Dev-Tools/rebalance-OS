"""Tests for the Focus 5 device-local collector (rebalance.ingest.focus5_scan).

Split by what each layer needs:
  - ranking + status parsing are PURE — unit-tested with hand-built inputs so
    the dirty-first vs my_work vs any_touch behavior (and mode switching) is
    proven without touching git or the disk.
  - discovery / probe / sync / summarize need real git, so they run against
    throwaway temp repos.
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from unittest import mock

from rebalance.ingest.focus5_scan import (
    RepoSignals,
    _parse_status,
    get_roster_meta,
    iter_git_repos,
    live_health,
    probe_repo_signals,
    rank_repos,
    recent_activity,
    resolve_ranking_strategy,
    summarize_focus5,
    sync_focus5,
    vscode_url,
)

NOW = 1_700_000_000  # fixed "now" epoch for deterministic recency math
HOUR = 3600
DAY = 86400


def _sig(name: str, **over) -> RepoSignals:
    """Build a RepoSignals with sensible clean-repo defaults; override per test."""
    base = dict(
        device_id="dev", local_path=f"/repos/{name}", repo_name=name,
        repo_full_name=None, branch="main", upstream=None, has_upstream=False,
        ahead=0, behind=0, modified_count=0, untracked_count=0, is_dirty=False,
        last_commit_at=None, last_commit_ts=None, my_last_commit_ts=None,
        head_reflog_ts=None, index_mtime_ts=None, remote_url=None,
        probed_at="2026-06-05T00:00:00Z",
    )
    base.update(over)
    return RepoSignals(**base)


# ---------------------------------------------------------------------------
# Pure: status parsing
# ---------------------------------------------------------------------------

class ParseStatusTests(unittest.TestCase):
    def test_clean_with_upstream(self) -> None:
        out = (
            "# branch.oid abc\n# branch.head main\n"
            "# branch.upstream origin/main\n# branch.ab +0 -0\n"
        )
        h = _parse_status(out)
        self.assertEqual(h["branch"], "main")
        self.assertTrue(h["has_upstream"])
        self.assertEqual((h["ahead"], h["behind"]), (0, 0))
        self.assertFalse(h["is_dirty"])

    def test_dirty_counts_modified_and_untracked(self) -> None:
        out = (
            "# branch.head main\n"
            "1 .M N... 100644 100644 100644 aaa bbb file_a\n"
            "2 R. N... 100644 100644 100644 ccc ddd R100 new old\n"
            "? untracked.txt\n? another.txt\n"
        )
        h = _parse_status(out)
        self.assertEqual(h["modified_count"], 2)   # the "1 " and "2 " lines
        self.assertEqual(h["untracked_count"], 2)  # the two "? " lines
        self.assertTrue(h["is_dirty"])

    def test_ahead_behind(self) -> None:
        out = "# branch.head main\n# branch.upstream origin/main\n# branch.ab +3 -7\n"
        h = _parse_status(out)
        self.assertEqual((h["ahead"], h["behind"]), (3, 7))

    def test_detached_and_no_upstream(self) -> None:
        h = _parse_status("# branch.head (detached)\n")
        self.assertIsNone(h["branch"])
        self.assertFalse(h["has_upstream"])

    def test_empty_output_is_safe_default(self) -> None:
        h = _parse_status("")  # git failure path → all defaults
        self.assertFalse(h["is_dirty"])
        self.assertIsNone(h["branch"])


# ---------------------------------------------------------------------------
# Pure: ranking strategies + the swappable seam
# ---------------------------------------------------------------------------

class RankingTests(unittest.TestCase):
    def test_dirty_first_forces_wip_above_newer_clean(self) -> None:
        # A clean repo I committed to 1h ago vs my dirty repo last committed 5d ago.
        clean = _sig("clean", my_last_commit_ts=NOW - HOUR)
        dirty = _sig("dirty", is_dirty=True, modified_count=3,
                     my_last_commit_ts=NOW - 5 * DAY)
        ranked = rank_repos([clean, dirty], mode="dirty_first", now_ts=NOW)
        self.assertEqual([r.signals.repo_name for r in ranked], ["dirty", "clean"])
        self.assertIn("modified", ranked[0].reason)

    def test_my_work_excludes_never_committed_clean_clone(self) -> None:
        # Dormant third-party clone: someone else's recent commit, none of mine,
        # clean tree. The spike's failure case — must NOT be eligible.
        clone = _sig("vendor_clone", last_commit_ts=NOW - HOUR, my_last_commit_ts=None)
        mine = _sig("mine", my_last_commit_ts=NOW - 2 * DAY)
        ranked = rank_repos([clone, mine], mode="my_work", now_ts=NOW)
        self.assertEqual([r.signals.repo_name for r in ranked], ["mine"])

    def test_any_touch_includes_everything(self) -> None:
        clone = _sig("vendor_clone", index_mtime_ts=NOW, my_last_commit_ts=None)
        mine = _sig("mine", my_last_commit_ts=NOW - 2 * DAY)
        ranked = rank_repos([clone, mine], mode="any_touch", now_ts=NOW)
        names = {r.signals.repo_name for r in ranked}
        self.assertEqual(names, {"vendor_clone", "mine"})
        # index-mtime activity dominates under the (noisy) any_touch mode.
        self.assertEqual(ranked[0].signals.repo_name, "vendor_clone")

    def test_mode_switch_reranks_same_signals(self) -> None:
        # Same inputs, different mode → different roster. Proves the seam.
        signals = [
            _sig("vendor_clone", index_mtime_ts=NOW, last_commit_ts=NOW - HOUR),
            _sig("wip", is_dirty=True, my_last_commit_ts=NOW - 3 * DAY),
        ]
        top_dirty = rank_repos(signals, mode="dirty_first", now_ts=NOW)[0]
        top_touch = rank_repos(signals, mode="any_touch", now_ts=NOW)[0]
        self.assertEqual(top_dirty.signals.repo_name, "wip")
        self.assertEqual(top_touch.signals.repo_name, "vendor_clone")

    def test_unknown_mode_raises_with_valid_set(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            resolve_ranking_strategy("bogus")
        self.assertIn("dirty_first", str(ctx.exception))

    def test_limit_caps_roster(self) -> None:
        sigs = [_sig(f"r{i}", is_dirty=True, my_last_commit_ts=NOW - i * HOUR)
                for i in range(8)]
        self.assertEqual(len(rank_repos(sigs, mode="dirty_first", now_ts=NOW, limit=5)), 5)


# ---------------------------------------------------------------------------
# Real git helpers
# ---------------------------------------------------------------------------

def _run(cwd: Path, *args: str, env: dict | None = None) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True, env=env)


def _make_git_repo(
    root: Path, name: str, *, user_email: str = "me@example.com",
    author_email: str | None = None, commit: bool = True,
    dirty: bool = False, untracked: bool = False,
) -> Path:
    """Create a real git repo under *root*. author_email defaults to user_email."""
    repo = root / name
    repo.mkdir(parents=True)
    _run(repo, "git", "init", "-q", "-b", "main")
    _run(repo, "git", "config", "user.email", user_email)
    _run(repo, "git", "config", "user.name", "Test User")
    if commit:
        (repo / "file.txt").write_text("hello", encoding="utf-8")
        _run(repo, "git", "add", ".")
        ae = author_email or user_email
        env = {
            **os.environ,
            "GIT_AUTHOR_EMAIL": ae, "GIT_AUTHOR_NAME": "Author",
            "GIT_COMMITTER_EMAIL": user_email, "GIT_COMMITTER_NAME": "Committer",
        }
        _run(repo, "git", "commit", "-q", "-m", "init", env=env)
    if dirty:
        (repo / "file.txt").write_text("changed", encoding="utf-8")
    if untracked:
        (repo / "untracked.txt").write_text("new", encoding="utf-8")
    return repo


def _db(tmp: Path) -> Path:
    db = tmp / "rebalance.db"
    sqlite3.connect(str(db)).close()
    return db


# ---------------------------------------------------------------------------
# Real git: discovery
# ---------------------------------------------------------------------------

class DiscoveryTests(unittest.TestCase):
    def test_finds_repos_prunes_noise_and_stops_at_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_git_repo(root, "alpha")
            _make_git_repo(root / "nested", "beta")
            # Noise that must be pruned, not descended into.
            (root / "node_modules" / "junk").mkdir(parents=True)
            # A repo checked out *inside* alpha's tree must NOT be yielded
            # separately (we stop at the first repo boundary).
            _make_git_repo(root / "alpha", "vendored")

            found = sorted(p.name for p in iter_git_repos([root]))
            self.assertEqual(found, ["alpha", "beta"])

    def test_overlapping_roots_dedupe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_git_repo(root / "nested", "beta")
            twice = list(iter_git_repos([root, root / "nested"]))
            self.assertEqual(len({p for p in twice}), 1)


# ---------------------------------------------------------------------------
# Real git: probe signals
# ---------------------------------------------------------------------------

class ProbeTests(unittest.TestCase):
    def test_probe_reads_dirty_and_my_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_git_repo(Path(tmp), "wip", dirty=True, untracked=True)
            s = probe_repo_signals(repo, device_id="dev", probed_at="t")
            self.assertEqual(s.branch, "main")
            self.assertTrue(s.is_dirty)
            self.assertEqual(s.modified_count, 1)
            self.assertEqual(s.untracked_count, 1)
            self.assertIsNotNone(s.my_last_commit_ts)  # I authored the commit
            self.assertIsNotNone(s.last_commit_ts)

    def test_probe_distinguishes_foreign_author(self) -> None:
        # Commit authored by someone else → my_last_commit_ts stays None, so the
        # repo is only eligible when dirty. This is the identity-matching guard.
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_git_repo(
                Path(tmp), "clone", user_email="me@example.com",
                author_email="someoneelse@upstream.com",
            )
            s = probe_repo_signals(repo, device_id="dev", probed_at="t")
            self.assertIsNotNone(s.last_commit_ts)     # a commit exists
            self.assertIsNone(s.my_last_commit_ts)     # but not authored by me

    def test_probe_on_non_repo_is_safe(self) -> None:
        # A `.git` that isn't a real repo (git failure path): no crash, defaults.
        with tempfile.TemporaryDirectory() as tmp:
            bogus = Path(tmp) / "broken"
            (bogus / ".git").mkdir(parents=True)
            s = probe_repo_signals(bogus, device_id="dev", probed_at="t")
            self.assertFalse(s.is_dirty)
            self.assertIsNone(s.branch)
            self.assertIsNone(s.my_last_commit_ts)


# ---------------------------------------------------------------------------
# Real git: sync + summarize (the read contract)
# ---------------------------------------------------------------------------

class SyncSummarizeTests(unittest.TestCase):
    def test_sync_ranks_persists_and_surfaces_off_roster(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repos"
            root.mkdir()
            _make_git_repo(root, "wip", dirty=True)      # at-risk → roster
            _make_git_repo(root, "also_dirty", untracked=True)  # at-risk, off-roster (limit=1)
            db = _db(Path(tmp))

            result = sync_focus5(
                db, roots=[root], device_id="dev", mode="dirty_first", limit=1,
            )
            self.assertEqual(result.discovered, 2)
            self.assertEqual(result.roster_size, 1)
            self.assertEqual(result.ranking_mode, "dirty_first")

            out = summarize_focus5(db, device_id="dev")
            # Both repos are dirty (tier-1); which one wins the single slot depends
            # on commit recency, so assert the partition invariant rather than a
            # specific winner: exactly one rostered, the other warned, no overlap.
            self.assertEqual(len(out["roster"]), 1)
            self.assertTrue(out["roster"][0]["is_dirty"])
            self.assertIsNone(out["roster"][0]["newest_pr"])  # no corpus row
            rostered = {c["repo_name"] for c in out["roster"]}
            warned = {w["repo_name"] for w in out["off_roster_warnings"]}
            self.assertEqual(rostered | warned, {"wip", "also_dirty"})  # both surfaced
            self.assertEqual(rostered & warned, set())                  # never double-counted
            self.assertEqual(out["summary"]["discovered"], 2)

    def test_resync_replaces_roster_without_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repos"
            root.mkdir()
            _make_git_repo(root, "wip", dirty=True)
            db = _db(Path(tmp))
            sync_focus5(db, roots=[root], device_id="dev", mode="dirty_first")
            sync_focus5(db, roots=[root], device_id="dev", mode="dirty_first")
            out = summarize_focus5(db, device_id="dev")
            self.assertEqual(len(out["roster"]), 1)  # not duplicated on re-sync

    def test_newest_pr_enrichment_joins_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repos"
            root.mkdir()
            repo = _make_git_repo(root, "widget", dirty=True)
            _run(repo, "git", "remote", "add", "origin",
                 "https://github.com/Acme/widget.git")
            db = _db(Path(tmp))
            sync_focus5(db, roots=[root], device_id="dev", mode="dirty_first")

            # Seed a PR in the GitHub corpus for Acme/widget.
            conn = sqlite3.connect(str(db))
            conn.row_factory = sqlite3.Row
            from rebalance.ingest.db import run_migrations
            run_migrations(conn)
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "INSERT INTO github_items "
                "(repo_full_name, item_type, number, title, state, html_url, fetched_at) "
                "VALUES (?,?,?,?,?,?,?)",
                ("Acme/widget", "pull_request", 42, "Add thing", "open",
                 "https://github.com/Acme/widget/pull/42", now),
            )
            conn.commit()
            conn.close()

            out = summarize_focus5(db, device_id="dev")
            pr = out["roster"][0]["newest_pr"]
            self.assertIsNotNone(pr)
            self.assertEqual(pr["number"], 42)
            self.assertEqual(pr["title"], "Add thing")

    def test_summarize_empty_db_is_safe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = _db(Path(tmp))
            out = summarize_focus5(db, device_id="dev")
            self.assertEqual(out["roster"], [])
            self.assertEqual(out["summary"]["discovered"], 0)

    def test_card_carries_activity_and_vscode_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repos"
            root.mkdir()
            repo = _make_git_repo(root, "wip", dirty=True)
            db = _db(Path(tmp))
            sync_focus5(db, roots=[root], device_id="dev", mode="dirty_first")

            card = summarize_focus5(db, device_id="dev")["roster"][0]
            # iter_git_repos stores the resolved path (macOS /var -> /private/var).
            self.assertEqual(card["vscode_url"], vscode_url(str(repo.resolve())))
            self.assertTrue(card["vscode_url"].startswith("vscode://file"))
            # The seeded repo has exactly one "init" commit.
            self.assertEqual(len(card["recent_activity"]), 1)
            self.assertEqual(card["recent_activity"][0]["subject"], "init")

    def test_with_activity_false_skips_git_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repos"
            root.mkdir()
            _make_git_repo(root, "wip", dirty=True)
            db = _db(Path(tmp))
            sync_focus5(db, roots=[root], device_id="dev", mode="dirty_first")
            card = summarize_focus5(db, device_id="dev", with_activity=False)["roster"][0]
            self.assertEqual(card["recent_activity"], [])

    def test_live_health_overlay_reflects_post_sync_changes(self) -> None:
        # Sync clean, then dirty the tree. The persisted snapshot says clean, but
        # the live overlay must report the *current* dirty state + a fresh stamp.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repos"
            root.mkdir()
            repo = _make_git_repo(root, "wip")  # committed, clean
            db = _db(Path(tmp))
            sync_focus5(db, roots=[root], device_id="dev", mode="dirty_first")

            snap = summarize_focus5(db, device_id="dev", with_live_health=False)["roster"][0]
            self.assertFalse(snap["is_dirty"])  # snapshot was clean

            (repo / "file.txt").write_text("changed now", encoding="utf-8")
            live = summarize_focus5(db, device_id="dev", with_live_health=True)["roster"][0]
            self.assertTrue(live["is_dirty"])            # overlay sees the new edit
            self.assertTrue(live["health_available"])
            self.assertIsNotNone(live["health_probed_at"])


class ReadHelperTests(unittest.TestCase):
    def test_recent_activity_orders_newest_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_git_repo(Path(tmp), "r")  # commit "init"
            (repo / "f2.txt").write_text("two", encoding="utf-8")
            _run(repo, "git", "add", ".")
            env = {
                **os.environ,
                "GIT_AUTHOR_EMAIL": "me@example.com", "GIT_AUTHOR_NAME": "A",
                "GIT_COMMITTER_EMAIL": "me@example.com", "GIT_COMMITTER_NAME": "A",
            }
            _run(repo, "git", "commit", "-q", "-m", "second", env=env)
            items = recent_activity(str(repo), limit=3)
            self.assertEqual([i["subject"] for i in items], ["second", "init"])

    def test_recent_activity_on_missing_repo_is_empty(self) -> None:
        self.assertEqual(recent_activity("/no/such/repo"), [])

    def test_vscode_url_encodes_spaces(self) -> None:
        self.assertEqual(
            vscode_url("/Users/me/My Repos/app"),
            "vscode://file/Users/me/My%20Repos/app",
        )

    def test_live_health_reads_current_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_git_repo(Path(tmp), "r", dirty=True, untracked=True)
            h = live_health(str(repo))
            self.assertTrue(h["health_available"])
            self.assertTrue(h["is_dirty"])
            self.assertEqual(h["branch"], "main")
            self.assertIsNotNone(h["health_probed_at"])

    def test_live_health_missing_repo_is_unavailable(self) -> None:
        h = live_health("/no/such/repo")
        self.assertFalse(h["health_available"])
        self.assertIsNotNone(h["health_probed_at"])  # still stamped


class RosterMetaTests(unittest.TestCase):
    def test_empty_db_meta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            meta = get_roster_meta(_db(Path(tmp)), device_id="dev")
            self.assertEqual(meta["roster_size"], 0)
            self.assertIsNone(meta["computed_at"])

    def test_meta_after_sync(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repos"
            root.mkdir()
            _make_git_repo(root, "wip", dirty=True)
            db = _db(Path(tmp))
            sync_focus5(db, roots=[root], device_id="dev", mode="dirty_first")
            meta = get_roster_meta(db, device_id="dev")
            self.assertEqual(meta["roster_size"], 1)
            self.assertEqual(meta["ranking_mode"], "dirty_first")
            self.assertIsNotNone(meta["computed_at"])


class WebRouteTests(unittest.TestCase):
    def test_focus5_route_renders_seeded_roster(self) -> None:
        # End-to-end: seed a roster, point REBALANCE_DB at it, hit the route.
        # Pre-seeding keeps the route's lazy bootstrap from scanning the machine.
        from rebalance.ingest.sync_snapshot import get_device_id
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repos"
            root.mkdir()
            _make_git_repo(root, "widget", dirty=True)
            db = _db(Path(tmp))
            sync_focus5(db, roots=[root], device_id=get_device_id(), mode="dirty_first")

            os.environ["REBALANCE_DB"] = str(db)
            try:
                from fastapi.testclient import TestClient
                from rebalance.web import app
                resp = TestClient(app).get("/focus-5")
            finally:
                os.environ.pop("REBALANCE_DB", None)

            self.assertEqual(resp.status_code, 200)
            self.assertIn("widget", resp.text)
            self.assertIn("Focus 5", resp.text)
            self.assertIn("vscode://file", resp.text)
            self.assertIn("f5-grid", resp.text)

    def _seed(self, tmp: Path):
        """Seed a fresh single-repo roster; return (db, device_id)."""
        from rebalance.ingest.sync_snapshot import get_device_id
        root = tmp / "repos"
        root.mkdir()
        _make_git_repo(root, "widget", dirty=True)
        db = _db(tmp)
        dev = get_device_id()
        sync_focus5(db, roots=[root], device_id=dev, mode="dirty_first")
        return db, dev

    def _get(self, db: Path, url: str = "/focus-5", **kw):
        from fastapi.testclient import TestClient
        from rebalance.web import app
        os.environ["REBALANCE_DB"] = str(db)
        try:
            return TestClient(app).get(url, **kw)
        finally:
            os.environ.pop("REBALANCE_DB", None)

    def test_manual_refresh_recomputes_then_redirects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = self._seed(Path(tmp))
            # Patch the recompute so the forced refresh doesn't scan the machine.
            with mock.patch("rebalance.ingest.focus5_scan.sync_focus5") as m:
                resp = self._get(db, "/focus-5?refresh=1", follow_redirects=False)
            self.assertEqual(resp.status_code, 303)          # post/redirect/get
            self.assertEqual(resp.headers["location"], "/focus-5")
            self.assertTrue(m.called)                        # recompute fired

    def test_fresh_roster_skips_recompute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = self._seed(Path(tmp))  # computed_at = just now
            with mock.patch("rebalance.ingest.focus5_scan.sync_focus5") as m:
                resp = self._get(db)
            self.assertEqual(resp.status_code, 200)
            self.assertFalse(m.called)                       # within TTL → no scan

    def test_stale_roster_triggers_recompute_on_visit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db, dev = self._seed(Path(tmp))
            # Age the snapshot past the 24h TTL.
            old = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
            conn = sqlite3.connect(str(db))
            conn.execute("UPDATE focus5_roster SET computed_at=? WHERE device_id=?", (old, dev))
            conn.commit(); conn.close()
            with mock.patch("rebalance.ingest.focus5_scan.sync_focus5") as m:
                resp = self._get(db)
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(m.called)                        # TTL expired → recompute


if __name__ == "__main__":
    unittest.main()

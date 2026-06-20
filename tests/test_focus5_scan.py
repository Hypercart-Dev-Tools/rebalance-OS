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
    _SIGNAL_COLUMNS,
    _parse_status,
    _signal_row,
    focus5_repo_identity,
    get_roster_meta,
    iter_git_repos,
    live_health,
    probe_repo_signals,
    rank_repos,
    recent_activity,
    rerank_focus5_from_cache,
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

    def test_recent_activity_ranks_authored_recency_without_dirty_pin(self) -> None:
        # The headline view. A clean repo I committed to 1h ago must outrank a
        # dirty repo I last authored 5d ago — the exact inversion dirty_first
        # makes. No dirty pinning here.
        clean_recent = _sig("clean_recent", my_last_commit_ts=NOW - HOUR)
        dirty_old = _sig("dirty_old", is_dirty=True, modified_count=4,
                         my_last_commit_ts=NOW - 5 * DAY)
        ranked = rank_repos([dirty_old, clean_recent], mode="recent_activity", now_ts=NOW)
        self.assertEqual([r.signals.repo_name for r in ranked],
                         ["clean_recent", "dirty_old"])
        self.assertIn("your commit", ranked[0].reason)

    def test_recent_activity_excludes_dirty_only_no_authored_repo(self) -> None:
        # A repo with leftover WIP but NO operator-authored commit (e.g. a clone
        # I dirtied but never committed to) must NOT appear in recent_activity —
        # admitting it would reintroduce the "junk buries my real work" bug. It
        # still surfaces under dirty_first (the Dirty Five safety view).
        dirty_only = _sig("dirty_only", is_dirty=True, modified_count=2,
                          my_last_commit_ts=None)
        mine = _sig("mine", my_last_commit_ts=NOW - 2 * DAY)
        recent = rank_repos([dirty_only, mine], mode="recent_activity", now_ts=NOW)
        self.assertEqual([r.signals.repo_name for r in recent], ["mine"])
        dirty = {r.signals.repo_name for r in
                 rank_repos([dirty_only, mine], mode="dirty_first", now_ts=NOW)}
        self.assertIn("dirty_only", dirty)  # but Dirty Five still carries it

    def test_recent_activity_orders_among_clean_authored_repos(self) -> None:
        older = _sig("older", my_last_commit_ts=NOW - 3 * DAY)
        newer = _sig("newer", my_last_commit_ts=NOW - HOUR)
        ranked = rank_repos([older, newer], mode="recent_activity", now_ts=NOW)
        self.assertEqual([r.signals.repo_name for r in ranked], ["newer", "older"])

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

    def test_hidden_repos_are_filtered_and_promote_next(self) -> None:
        # 6 dirty repos but a roster of 5: the hidden one must drop out and the
        # 6th must be promoted into the freed slot.
        sigs = [_sig(f"r{i}", is_dirty=True, my_last_commit_ts=NOW - i * HOUR,
                     repo_full_name=f"Org/r{i}") for i in range(6)]
        full = rank_repos(sigs, mode="dirty_first", now_ts=NOW, limit=5)
        self.assertEqual([r.signals.repo_name for r in full], ["r0", "r1", "r2", "r3", "r4"])
        hidden = rank_repos(sigs, mode="dirty_first", now_ts=NOW, limit=5,
                            hidden=["Org/r1"])
        names = [r.signals.repo_name for r in hidden]
        self.assertNotIn("r1", names)
        self.assertIn("r5", names)          # 6th candidate promoted into the slot
        self.assertEqual(len(names), 5)

    def test_hidden_identity_falls_back_to_local_path(self) -> None:
        # A local-only repo (no remote) is hidden by its device-local path.
        local = _sig("local", is_dirty=True, local_path="/repos/local")
        other = _sig("other", is_dirty=True)
        ranked = rank_repos([local, other], mode="dirty_first", now_ts=NOW,
                            hidden=["/repos/local"])
        self.assertEqual([r.signals.repo_name for r in ranked], ["other"])


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

    def test_root_that_is_itself_a_repo_is_discovered(self) -> None:
        # Phase 4: rebalance-OS is a scan root that is ITSELF a repo (.git at the
        # top level). Passing the repo dir as a root must yield it (and stop there).
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_git_repo(Path(tmp), "self_repo")
            found = list(iter_git_repos([repo]))
            self.assertEqual([p.name for p in found], ["self_repo"])


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


class CollectorObservabilityTests(unittest.TestCase):
    def test_sync_result_reports_timing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repos"
            root.mkdir()
            _make_git_repo(root, "wip", dirty=True)
            db = _db(Path(tmp))
            res = sync_focus5(db, roots=[root], device_id="dev", mode="dirty_first")
            self.assertGreater(res.elapsed_seconds, 0.0)
            self.assertEqual(res.failed_repos, 0)
            self.assertIn("elapsed_seconds", res.as_dict())  # surfaced to refresh_index

    def test_sync_logs_timing_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repos"
            root.mkdir()
            _make_git_repo(root, "wip", dirty=True)
            db = _db(Path(tmp))
            with self.assertLogs("rebalance.ingest.focus5_scan", level="INFO") as cm:
                sync_focus5(db, roots=[root], device_id="dev", mode="dirty_first")
            self.assertTrue(any("focus5 sync:" in line for line in cm.output))

    def test_failed_git_probe_is_logged_and_counted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repos"
            root.mkdir()
            _make_git_repo(root, "ok", dirty=True)
            # A bogus repo: a `.git` dir that isn't a real git repo → status fails.
            (root / "broken" / ".git").mkdir(parents=True)
            db = _db(Path(tmp))
            with self.assertLogs("rebalance.ingest.focus5_scan", level="WARNING") as cm:
                res = sync_focus5(db, roots=[root], device_id="dev", mode="dirty_first")
            self.assertEqual(res.discovered, 2)
            self.assertEqual(res.failed_repos, 1)
            self.assertTrue(any("git status failed" in line for line in cm.output))


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

    def test_dirty_view_renders_transiently_without_resync(self) -> None:
        # /focus-5?view=dirty re-ranks the cached signals under dirty_first; a
        # fresh roster means no ~30s scan, and the persisted roster is untouched.
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = self._seed(Path(tmp))  # computed_at = just now
            with mock.patch("rebalance.ingest.focus5_scan.sync_focus5") as m:
                resp = self._get(db, "/focus-5?view=dirty")
            self.assertEqual(resp.status_code, 200)
            self.assertIn("Dirty Five", resp.text)
            self.assertIn("widget", resp.text)
            self.assertFalse(m.called)                       # transient re-rank, no scan

    def test_fresh_roster_skips_recompute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = self._seed(Path(tmp))  # computed_at = just now
            with mock.patch("rebalance.ingest.focus5_scan.sync_focus5") as m:
                resp = self._get(db)
            self.assertEqual(resp.status_code, 200)
            self.assertFalse(m.called)                       # within TTL → no scan

    def test_stale_roster_serves_cached_without_blocking_scan(self) -> None:
        # sync_focus5() is a ~30s synchronous git scan; a stale page load must NOT
        # run it inline (that made the page look broken). Serve the cached roster
        # instantly with the "⚠ stale" badge; recompute only on explicit Refresh.
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
            self.assertFalse(m.called)                       # stale → no inline scan
            self.assertIn("⚠ stale", resp.text)             # but the staleness is surfaced


# ---------------------------------------------------------------------------
# Hide → ignore → re-rank
# ---------------------------------------------------------------------------

def _seed_signals(db: Path, sigs: list[RepoSignals]) -> None:
    """Insert raw signals into the focus5_repo_signals cache (no git probe)."""
    from rebalance.ingest.db import db_connection, run_migrations
    with db_connection(db) as conn:
        run_migrations(conn)
        ph = ", ".join("?" for _ in _SIGNAL_COLUMNS)
        conn.executemany(
            f"INSERT INTO focus5_repo_signals ({', '.join(_SIGNAL_COLUMNS)}) VALUES ({ph})",
            [_signal_row(s) for s in sigs],
        )
        conn.commit()


class _ConfigIsolated(unittest.TestCase):
    """Base that points the config file at a throwaway temp path."""

    def setUp(self) -> None:
        import rebalance.ingest.config as config_module
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._cfg_mod = config_module
        self._orig_cfg = config_module.CONFIG_PATH
        config_module.CONFIG_PATH = Path(self._tmp.name) / "rbos.config"
        self.addCleanup(setattr, config_module, "CONFIG_PATH", self._orig_cfg)
        self.db = Path(self._tmp.name) / "rebalance.db"


class Focus5HiddenConfigTests(_ConfigIsolated):
    def test_add_remove_dedupe_list_and_is_hidden(self) -> None:
        from rebalance.ingest.config import (
            add_focus5_hidden_repo, get_focus5_hidden_repos,
            is_focus5_repo_hidden, remove_focus5_hidden_repo,
        )
        self.assertEqual(get_focus5_hidden_repos(), [])
        self.assertTrue(add_focus5_hidden_repo("Org/a"))
        self.assertFalse(add_focus5_hidden_repo("Org/a"))      # idempotent
        self.assertTrue(add_focus5_hidden_repo("  /repos/b  "))  # trims
        self.assertTrue(is_focus5_repo_hidden("Org/a"))
        self.assertFalse(is_focus5_repo_hidden("Org/z"))
        self.assertEqual(get_focus5_hidden_repos(), ["Org/a", "/repos/b"])
        self.assertTrue(remove_focus5_hidden_repo("Org/a"))
        self.assertFalse(remove_focus5_hidden_repo("Org/a"))
        self.assertEqual(get_focus5_hidden_repos(), ["/repos/b"])


class Focus5ScanRootsConfigTests(_ConfigIsolated):
    def test_add_seeds_from_effective_then_appends_and_is_idempotent(self) -> None:
        from rebalance.ingest.config import (
            add_focus5_scan_root, get_focus5_scan_roots, remove_focus5_scan_root,
        )
        default = get_focus5_scan_roots()  # effective default (repo_scan_roots)
        self.assertTrue(add_focus5_scan_root("/tmp/extra-root"))
        roots = get_focus5_scan_roots()
        self.assertIn("/tmp/extra-root", roots)
        for d in default:
            self.assertIn(d, roots)        # existing scope preserved, not dropped
        self.assertFalse(add_focus5_scan_root("/tmp/extra-root"))  # idempotent
        self.assertTrue(remove_focus5_scan_root("/tmp/extra-root"))
        self.assertNotIn("/tmp/extra-root", get_focus5_scan_roots())

    def test_add_expands_user_home(self) -> None:
        from rebalance.ingest.config import add_focus5_scan_root, get_focus5_scan_roots
        add_focus5_scan_root("~/some-dev-dir")
        self.assertTrue(
            any(r.endswith("/some-dev-dir") and "~" not in r
                for r in get_focus5_scan_roots())
        )

    def test_empty_path_rejected(self) -> None:
        from rebalance.ingest.config import add_focus5_scan_root
        with self.assertRaises(ValueError):
            add_focus5_scan_root("   ")


class Focus5RankingModeDefaultTests(_ConfigIsolated):
    def test_unset_defaults_to_recent_activity(self) -> None:
        from rebalance.ingest.config import get_focus5_ranking_mode
        # Fresh config (no focus5_ranking_mode key) → the headline view.
        self.assertEqual(get_focus5_ranking_mode(), "recent_activity")

    def test_explicit_mode_still_wins(self) -> None:
        from rebalance.ingest.config import (
            get_focus5_ranking_mode, set_focus5_ranking_mode,
        )
        set_focus5_ranking_mode("dirty_first")
        self.assertEqual(get_focus5_ranking_mode(), "dirty_first")

    def test_default_matches_module_constant(self) -> None:
        # The getter's unset default and DEFAULT_RANKING_MODE must not drift.
        from rebalance.ingest.config import get_focus5_ranking_mode
        from rebalance.ingest.focus5_scan import DEFAULT_RANKING_MODE
        self.assertEqual(get_focus5_ranking_mode(), DEFAULT_RANKING_MODE)


class Focus5RerankHideTests(_ConfigIsolated):
    def _dirty(self, name: str) -> RepoSignals:
        # Dirty AND authored, so it's eligible under every mode (recent_activity
        # — the default rerank_focus5_from_cache uses — as well as dirty_first).
        return _sig(name, device_id="dev", is_dirty=True, modified_count=1,
                    my_last_commit_ts=NOW - HOUR,
                    local_path=f"/repos/{name}", repo_full_name=f"Org/{name}")

    def test_hide_rerank_drops_repo_then_unhide_restores(self) -> None:
        _seed_signals(self.db, [self._dirty(n) for n in ("a", "b", "c")])
        # Initial re-rank from cache: all three eligible.
        self.assertEqual(rerank_focus5_from_cache(self.db, device_id="dev",
                                                  mode="dirty_first"), 3)
        # Hide one and re-rank: it drops out, board refills with the rest.
        from rebalance.ingest.config import (
            add_focus5_hidden_repo, remove_focus5_hidden_repo,
        )
        add_focus5_hidden_repo("Org/b")
        self.assertEqual(rerank_focus5_from_cache(self.db, device_id="dev",
                                                  mode="dirty_first"), 2)
        out = summarize_focus5(self.db, device_id="dev",
                               with_activity=False, with_live_health=False)
        self.assertEqual({c["repo_name"] for c in out["roster"]}, {"a", "c"})
        # And it must NOT resurface in the off-roster "needs attention" strip —
        # hiding a dirty repo should silence it, not relocate it to the nag list.
        self.assertNotIn("b", {w["repo_name"] for w in out["off_roster_warnings"]})
        # Un-hide restores it on the next re-rank (reversible — not a one-way door).
        remove_focus5_hidden_repo("Org/b")
        self.assertEqual(rerank_focus5_from_cache(self.db, device_id="dev",
                                                  mode="dirty_first"), 3)

    def test_web_helper_hides_and_reranks_from_cache(self) -> None:
        import rebalance.web as web
        _seed_signals(self.db, [self._dirty(n) for n in ("a", "b", "c")])
        with mock.patch("rebalance.ingest.focus5_scan.get_device_id", return_value="dev"), \
             mock.patch("rebalance.paths.resolve_database_path", return_value=self.db):
            res = web.focus5_set_hidden("Org/b", hidden=True)
            self.assertEqual(res, {"ok": True, "changed": True,
                                   "reranked": True, "roster_size": 2})
            out = summarize_focus5(self.db, device_id="dev",
                                   with_activity=False, with_live_health=False)
            self.assertNotIn("b", {c["repo_name"] for c in out["roster"]})
        from rebalance.ingest.config import get_focus5_hidden_repos
        self.assertIn("Org/b", get_focus5_hidden_repos())

    def test_web_helper_rejects_empty_identity(self) -> None:
        import rebalance.web as web
        self.assertEqual(web.focus5_set_hidden("  ", hidden=True),
                         {"ok": False, "error": "empty repo identity"})


class Focus5TransientViewTests(_ConfigIsolated):
    """Dirty Five re-ranks the cached signals under dirty_first WITHOUT disturbing
    the persisted recent_activity roster (relay r2 persistence model)."""

    def _seed_two(self) -> None:
        # clean_recent wins recent_activity (newest authored); dirty_old wins
        # dirty_first (at-risk). So the two modes produce inverted rosters.
        clean_recent = _sig("clean_recent", device_id="dev", my_last_commit_ts=NOW,
                            local_path="/repos/clean_recent", repo_full_name="Org/clean_recent")
        dirty_old = _sig("dirty_old", device_id="dev", is_dirty=True, modified_count=2,
                        my_last_commit_ts=NOW - 5 * DAY,
                        local_path="/repos/dirty_old", repo_full_name="Org/dirty_old")
        _seed_signals(self.db, [clean_recent, dirty_old])

    def test_transient_view_does_not_mutate_persisted_roster(self) -> None:
        self._seed_two()
        # Persist the default recent_activity roster.
        rerank_focus5_from_cache(self.db, device_id="dev", mode="recent_activity")
        default = summarize_focus5(self.db, device_id="dev",
                                   with_activity=False, with_live_health=False)
        self.assertEqual([c["repo_name"] for c in default["roster"]],
                         ["clean_recent", "dirty_old"])
        self.assertEqual(default["ranking_mode"], "recent_activity")

        # Transient Dirty Five view: dirty_first ordering, same signal cache.
        dirty = summarize_focus5(self.db, device_id="dev", mode="dirty_first",
                                 with_activity=False, with_live_health=False)
        self.assertEqual(dirty["roster"][0]["repo_name"], "dirty_old")
        self.assertEqual(dirty["ranking_mode"], "dirty_first")

        # The persisted roster is UNTOUCHED — re-read still recent_activity order.
        again = summarize_focus5(self.db, device_id="dev",
                                 with_activity=False, with_live_health=False)
        self.assertEqual([c["repo_name"] for c in again["roster"]],
                         ["clean_recent", "dirty_old"])
        self.assertEqual(again["ranking_mode"], "recent_activity")

    def test_transient_view_carries_signal_freshness(self) -> None:
        self._seed_two()
        out = summarize_focus5(self.db, device_id="dev", mode="dirty_first",
                               with_activity=False, with_live_health=False)
        # computed_at reflects the cached signals' probed_at (the last sync).
        self.assertEqual(out["computed_at"], "2026-06-05T00:00:00Z")


class Focus5IdentityTests(unittest.TestCase):
    def test_identity_prefers_full_name_then_path(self) -> None:
        self.assertEqual(focus5_repo_identity(_sig("x", repo_full_name="Org/x")), "Org/x")
        self.assertEqual(
            focus5_repo_identity(_sig("y", repo_full_name=None, local_path="/repos/y")),
            "/repos/y",
        )


if __name__ == "__main__":
    unittest.main()

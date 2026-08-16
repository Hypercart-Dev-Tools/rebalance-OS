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
    _classify_reflog_op,
    _parse_status,
    _probe_head_reflog_commit,
    _signal_row,
    basis_badge,
    explain_recency,
    focus5_repo_identity,
    get_roster_meta,
    iter_git_repos,
    live_health,
    off_roster_reason,
    pick_newest_dirty_off_roster,
    probe_repo_signals,
    rank_repos,
    recent_activity,
    rerank_focus5_from_cache,
    resolve_ranking_strategy,
    resolve_recency,
    summarize_focus5,
    sync_focus5,
    vscode_url,
)

NOW = 1_700_000_000  # fixed "now" epoch for deterministic recency math
HOUR = 3600
DAY = 86400


def _sig(name: str, **over) -> RepoSignals:
    """Build a RepoSignals with sensible clean-repo defaults; override per test.

    When ``my_local_commit_ts``/``recency_basis`` aren't given explicitly, they
    are resolved from the raw inputs exactly as :func:`probe_repo_signals` does
    (with no reflog, so ``reflog_available=True`` — a foreign-only clone resolves
    to ``none``, not ``any_commit``). A test wanting the ``local_reflog`` basis
    sets both fields explicitly (e.g. the sleuth/EOS oracle).
    """
    base = dict(
        device_id="dev", local_path=f"/repos/{name}", repo_name=name,
        repo_full_name=None, branch="main", upstream=None, has_upstream=False,
        ahead=0, behind=0, modified_count=0, untracked_count=0, is_dirty=False,
        last_commit_at=None, last_commit_ts=None, my_last_commit_ts=None,
        my_local_commit_ts=None, recency_basis="none",
        head_reflog_ts=None, index_mtime_ts=None, remote_url=None,
        probed_at="2026-06-05T00:00:00Z",
    )
    base.update(over)
    if "my_local_commit_ts" not in over and "recency_basis" not in over:
        ts, basis = resolve_recency(
            reflog_commit_ts=None, reflog_available=True,
            author_email_ts=base["my_last_commit_ts"], any_commit_ts=base["last_commit_ts"],
        )
        base["my_local_commit_ts"], base["recency_basis"] = ts, basis
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
# GH-81: reflog op classification (the semantic accept/reject op set)
# ---------------------------------------------------------------------------

class ReflogOpClassificationTests(unittest.TestCase):
    """The one place that decides 'is this reflog op a local commit?' — proven
    against the accept/reject op families + unrecognized-op handling."""

    def test_accept_ops_create_or_rewrite_a_local_commit(self) -> None:
        for subject in (
            "commit: add feature",
            "commit (amend): reword",
            "commit (initial): first",
            "cherry-pick: port fix",
            "revert: undo bad change",
            "rebase (pick): replay",
            "rebase (finish): returning to refs/heads/main",
            "rebase -i (pick): squash",
            "merge feature: Merge made by the 'ort' strategy.",
        ):
            self.assertIs(_classify_reflog_op(subject), True, subject)

    def test_reject_ops_move_head_to_foreign_or_navigation(self) -> None:
        for subject in (
            "pull: Fast-forward",
            "pull origin main: Fast-forward",
            "merge origin/main: Fast-forward",
            "fetch origin: storing head",
            "clone: from https://github.com/x/y.git",
            "checkout: moving from main to feature",
            "reset: moving to HEAD~1",
            "branch: Created from HEAD",
        ):
            self.assertIs(_classify_reflog_op(subject), False, subject)

    def test_unrecognized_op_is_none_so_caller_rejects_and_logs(self) -> None:
        # A future/unknown git phrasing must NOT be silently counted as my commit.
        self.assertIsNone(_classify_reflog_op("teleport: beam HEAD aboard"))


# ---------------------------------------------------------------------------
# GH-81: the recency fallback ladder (local_reflog → author_email → any_commit)
# ---------------------------------------------------------------------------

class ResolveRecencyTests(unittest.TestCase):
    def test_local_reflog_wins_when_present(self) -> None:
        ts, basis = resolve_recency(
            reflog_commit_ts=NOW, reflog_available=True,
            author_email_ts=NOW - DAY, any_commit_ts=NOW - 2 * DAY,
        )
        self.assertEqual((ts, basis), (NOW, "local_reflog"))

    def test_falls_to_author_email_when_no_reflog_commit(self) -> None:
        ts, basis = resolve_recency(
            reflog_commit_ts=None, reflog_available=True,
            author_email_ts=NOW - DAY, any_commit_ts=NOW,
        )
        self.assertEqual((ts, basis), (NOW - DAY, "author_email"))

    def test_any_commit_only_when_reflog_unavailable(self) -> None:
        # Reflog disabled + no author-email match → the last-resort rung fires.
        ts, basis = resolve_recency(
            reflog_commit_ts=None, reflog_available=False,
            author_email_ts=None, any_commit_ts=NOW - 3 * DAY,
        )
        self.assertEqual((ts, basis), (NOW - 3 * DAY, "any_commit"))

    def test_available_reflog_without_commit_does_NOT_surface_foreign_clone(self) -> None:
        # The GH-81 refinement: a readable reflog with no local-commit op is a
        # DEFINITIVE 'I never committed here' — a foreign-only clone stays
        # ineligible (none), it must NOT fall through to any_commit.
        ts, basis = resolve_recency(
            reflog_commit_ts=None, reflog_available=True,
            author_email_ts=None, any_commit_ts=NOW,  # foreign commit present
        )
        self.assertEqual((ts, basis), (None, "none"))


# ---------------------------------------------------------------------------
# GH-81 Phase 2: operator-facing explain UX (pure)
# ---------------------------------------------------------------------------

class ExplainRecencyTests(unittest.TestCase):
    def test_on_roster_local_reflog_just_shows_recency(self) -> None:
        # Above the cutoff (on the board), normal basis → no cutoff/fallback noise.
        s = explain_recency("local_reflog", NOW - HOUR, rank_cutoff_ts=NOW - 2 * HOUR, now_ts=NOW)
        self.assertEqual(s, "your local commit 1h ago")

    def test_off_roster_eligible_shows_below_cutoff(self) -> None:
        # The original GH-81 forensics question answered in one line.
        s = explain_recency("local_reflog", NOW - 3 * DAY, rank_cutoff_ts=NOW - 16 * HOUR, now_ts=NOW)
        self.assertIn("your local commit 3d ago", s)
        self.assertIn("below the #5 cutoff (16h ago)", s)

    def test_ineligible_none_basis(self) -> None:
        s = explain_recency("none", None, rank_cutoff_ts=NOW - HOUR, now_ts=NOW)
        self.assertEqual(s, "no local commit here — not eligible for Focus 5")

    def test_fallback_basis_is_explained(self) -> None:
        ae = explain_recency("author_email", NOW - HOUR, rank_cutoff_ts=None, now_ts=NOW)
        self.assertIn("ranked by author email", ae)
        ac = explain_recency("any_commit", NOW - HOUR, rank_cutoff_ts=None, now_ts=NOW)
        self.assertIn("ranked by latest commit", ac)

    def test_no_cutoff_note_when_cutoff_unknown(self) -> None:
        s = explain_recency("local_reflog", NOW - 3 * DAY, rank_cutoff_ts=None, now_ts=NOW)
        self.assertNotIn("cutoff", s)


class BasisBadgeTests(unittest.TestCase):
    def test_fallback_bases_get_a_badge(self) -> None:
        self.assertEqual(basis_badge("author_email"), "via author email")
        self.assertEqual(basis_badge("any_commit"), "via latest commit")

    def test_normal_and_ineligible_bases_have_no_badge(self) -> None:
        self.assertEqual(basis_badge("local_reflog"), "")
        self.assertEqual(basis_badge("none"), "")
        self.assertEqual(basis_badge(None), "")


# ---------------------------------------------------------------------------
# GH-105: single "BTW, this went dirty" banner (pure)
# ---------------------------------------------------------------------------

def _off_roster_row(
    name: str, *, is_dirty: bool = True, ahead: int = 0,
    my_local_commit_ts: int | None = NOW, modified_count: int = 1,
    untracked_count: int = 0,
) -> dict:
    return {
        "repo_name": name, "local_path": f"/repos/{name}",
        "repo_full_name": f"me/{name}", "branch": "development",
        "ahead": ahead, "modified_count": modified_count,
        "untracked_count": untracked_count, "is_dirty": is_dirty,
        "probed_at": "2026-07-03T00:00:00Z",
        "my_local_commit_ts": my_local_commit_ts, "recency_basis": "local_reflog",
    }


class PickNewestDirtyOffRosterTests(unittest.TestCase):
    def test_empty_off_roster_yields_no_banner(self) -> None:
        self.assertIsNone(pick_newest_dirty_off_roster([]))

    def test_no_dirty_repos_yields_no_banner(self) -> None:
        # ahead-only (unpushed, not dirty) must NOT trigger the banner — this is
        # specifically "you left uncommitted work", not "you forgot to push".
        rows = [_off_roster_row("clean-but-unpushed", is_dirty=False, ahead=2)]
        self.assertIsNone(pick_newest_dirty_off_roster(rows))

    def test_dirty_with_no_local_commit_is_excluded(self) -> None:
        # A dirty-only repo the operator never committed to has nothing to rank
        # "most recently touched" by — must not win over a repo with a real
        # my_local_commit_ts, and alone yields no banner at all.
        rows = [_off_roster_row("never-committed", my_local_commit_ts=None)]
        self.assertIsNone(pick_newest_dirty_off_roster(rows))

    def test_picks_the_most_recently_committed_dirty_repo(self) -> None:
        rows = [
            _off_roster_row("stale-dirty", my_local_commit_ts=NOW - 30 * DAY),
            _off_roster_row("fresh-dirty", my_local_commit_ts=NOW - HOUR),
            _off_roster_row("mid-dirty", my_local_commit_ts=NOW - DAY),
        ]
        winner = pick_newest_dirty_off_roster(rows)
        self.assertEqual(winner["repo_name"], "fresh-dirty")

    def test_dirty_beats_never_committed_and_unpushed_only(self) -> None:
        rows = [
            _off_roster_row("clean-but-unpushed", is_dirty=False, ahead=3),
            _off_roster_row("never-committed", my_local_commit_ts=None),
            _off_roster_row("the-real-answer", my_local_commit_ts=NOW - HOUR),
        ]
        winner = pick_newest_dirty_off_roster(rows)
        self.assertEqual(winner["repo_name"], "the-real-answer")

    def test_tie_break_is_deterministic(self) -> None:
        rows = [
            _off_roster_row("bbb", my_local_commit_ts=NOW - HOUR),
            _off_roster_row("aaa", my_local_commit_ts=NOW - HOUR),
        ]
        self.assertEqual(pick_newest_dirty_off_roster(rows)["repo_name"], "bbb")


class OffRosterReasonTests(unittest.TestCase):
    def test_dirty_repo_reason(self) -> None:
        # If the repo is dirty, the reason must be "uncommitted changes"
        # even if it has ahead commits as well.
        w = _sig("wip", is_dirty=True, ahead=3)
        self.assertEqual(off_roster_reason(w), "uncommitted changes")

        wd = {"is_dirty": True, "ahead": 3}
        self.assertEqual(off_roster_reason(wd), "uncommitted changes")

    def test_ahead_repo_reason(self) -> None:
        # If the repo is not dirty but has ahead commits, it shows "N ahead of origin"
        w = _sig("clean-ahead", is_dirty=False, ahead=3)
        self.assertEqual(off_roster_reason(w), "3 ahead of origin")

        wd = {"is_dirty": False, "ahead": 5}
        self.assertEqual(off_roster_reason(wd), "5 ahead of origin")

    def test_fallback_reason(self) -> None:
        # If not dirty and not ahead, returns fallback "needs attention"
        w = _sig("clean-no-ahead", is_dirty=False, ahead=0)
        self.assertEqual(off_roster_reason(w), "needs attention")

        wd = {"is_dirty": False, "ahead": 0}
        self.assertEqual(off_roster_reason(wd), "needs attention")


# ---------------------------------------------------------------------------
# Real git helpers
# ---------------------------------------------------------------------------

def _run(cwd: Path, *args: str, env: dict | None = None) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True, env=env)


def _make_git_repo(
    root: Path, name: str, *, user_email: str = "me@example.com",
    author_email: str | None = None, commit: bool = True,
    dirty: bool = False, untracked: bool = False, disable_reflog: bool = False,
) -> Path:
    """Create a real git repo under *root*. author_email defaults to user_email.

    ``disable_reflog`` sets ``core.logAllRefUpdates=false`` BEFORE any commit, so
    no HEAD reflog is ever written (the GH-81 reflog-unavailable fixture).
    """
    repo = root / name
    repo.mkdir(parents=True)
    _run(repo, "git", "init", "-q", "-b", "main")
    _run(repo, "git", "config", "user.email", user_email)
    _run(repo, "git", "config", "user.name", "Test User")
    if disable_reflog:
        _run(repo, "git", "config", "core.logAllRefUpdates", "false")
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
            self.assertIsNone(s.my_local_commit_ts)
            self.assertEqual(s.recency_basis, "none")


# ---------------------------------------------------------------------------
# GH-81: real-git reflog vector + the fallback ladder rungs
# ---------------------------------------------------------------------------

class ReflogVectorProbeTests(unittest.TestCase):
    def test_local_commit_basis_is_reflog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_git_repo(Path(tmp), "mine")
            s = probe_repo_signals(repo, device_id="dev", probed_at="t")
            self.assertEqual(s.recency_basis, "local_reflog")
            self.assertIsNotNone(s.my_local_commit_ts)
            ts, available = _probe_head_reflog_commit(repo)
            self.assertTrue(available)
            self.assertEqual(ts, s.my_local_commit_ts)

    def test_foreign_authored_local_commit_is_eligible_via_reflog(self) -> None:
        # THE GH-81 FIX: I committed locally, but under an author email that does
        # NOT match this repo's user.email (CLI identity vs web-merge noreply). The
        # old author-email gate (my_last_commit_ts) misses it → silent drop. The
        # reflog catches the local `commit` op, so the repo is still eligible.
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_git_repo(
                Path(tmp), "sleuth", user_email="bot@noreply.github",
                author_email="noel@neochro.me",
            )
            s = probe_repo_signals(repo, device_id="dev", probed_at="t")
            self.assertIsNone(s.my_last_commit_ts)        # old gate would drop it
            self.assertEqual(s.recency_basis, "local_reflog")
            self.assertIsNotNone(s.my_local_commit_ts)    # new vector keeps it

    def test_reflog_disabled_falls_back_to_author_email(self) -> None:
        # core.logAllRefUpdates=false → no HEAD reflog. We must NOT regress below
        # today: fall back to the author-email match.
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_git_repo(Path(tmp), "noreflog", disable_reflog=True)
            ts, available = _probe_head_reflog_commit(repo)
            self.assertFalse(available)                   # reflog unavailable
            self.assertIsNone(ts)
            s = probe_repo_signals(repo, device_id="dev", probed_at="t")
            self.assertEqual(s.recency_basis, "author_email")
            self.assertEqual(s.my_local_commit_ts, s.my_last_commit_ts)

    def test_reflog_disabled_foreign_author_falls_back_to_any_commit(self) -> None:
        # Reflog off AND no author-email match → the last-resort any_commit rung.
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_git_repo(
                Path(tmp), "vendor", user_email="bot@noreply.github",
                author_email="upstream@x.com", disable_reflog=True,
            )
            s = probe_repo_signals(repo, device_id="dev", probed_at="t")
            self.assertIsNone(s.my_last_commit_ts)
            self.assertEqual(s.recency_basis, "any_commit")
            self.assertEqual(s.my_local_commit_ts, s.last_commit_ts)

    def test_empty_repo_basis_is_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_git_repo(Path(tmp), "empty", commit=False)
            s = probe_repo_signals(repo, device_id="dev", probed_at="t")
            self.assertIsNone(s.my_local_commit_ts)
            self.assertEqual(s.recency_basis, "none")


class Focus5RankOracleTests(unittest.TestCase):
    """Regression oracle for GH-81: local hands-on work outranks web-merge-only."""

    def test_oracle_pure_local_reflog_outranks_email_fallback(self) -> None:
        # sleuth: recent LOCAL commit (reflog), but its author-email match is an
        # OLD merge (3d). eos: no local commit — only a stale author-email match.
        # OLD ranking (my_last_commit_ts) → eos wins (the bug). NEW ranking
        # (my_local_commit_ts) → sleuth wins (fixed).
        sleuth = _sig("sleuth", my_last_commit_ts=NOW - 3 * DAY,
                      my_local_commit_ts=NOW - 15 * HOUR, recency_basis="local_reflog")
        eos = _sig("eos", my_last_commit_ts=NOW - 2 * DAY,
                   my_local_commit_ts=NOW - 2 * DAY, recency_basis="author_email")
        new = [r.signals.repo_name for r in
               rank_repos([eos, sleuth], mode="recent_activity", now_ts=NOW)]
        self.assertEqual(new, ["sleuth", "eos"])
        # Document the bug the fix inverts: ranking on the old email vector alone.
        old = sorted([sleuth, eos], key=lambda s: s.my_last_commit_ts, reverse=True)
        self.assertEqual([s.repo_name for s in old], ["eos", "sleuth"])

    def test_oracle_real_git_webmerge_only_repo_drops_off_roster(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repos"
            root.mkdir()
            # sleuth: a local commit authored under a non-user.email identity.
            _make_git_repo(root, "sleuth", user_email="bot@noreply.github",
                           author_email="noel@neochro.me")
            # eos: receives its commit from a foreign repo via fetch+checkout — NO
            # local-commit op in its reflog (the web-merge-only analog). The
            # upstream lives OUTSIDE the scan root so it isn't itself rostered.
            upstream = _make_git_repo(Path(tmp) / "_up", "upstream",
                                      user_email="other@up.com")
            eos = root / "eos"
            eos.mkdir()
            _run(eos, "git", "init", "-q", "-b", "main")
            _run(eos, "git", "config", "user.email", "bot@noreply.github")
            _run(eos, "git", "config", "user.name", "Bot")
            _run(eos, "git", "remote", "add", "origin", str(upstream))
            _run(eos, "git", "fetch", "-q", "origin")
            _run(eos, "git", "checkout", "-q", "-B", "main", "origin/main")

            db = _db(Path(tmp))
            sync_focus5(db, roots=[root], device_id="dev", mode="recent_activity")
            out = summarize_focus5(db, device_id="dev",
                                   with_activity=False, with_live_health=False)
            cards = {c["repo_name"]: c for c in out["roster"]}
            self.assertIn("sleuth", cards)            # local work surfaces
            self.assertNotIn("eos", cards)            # web-merge-only does not
            # And the fix is via the reflog, not the email gate (which is blind here).
            self.assertEqual(cards["sleuth"]["recency_basis"], "local_reflog")
            self.assertIsNone(cards["sleuth"]["my_last_commit_ts"])


class Focus5LegacyRowBackfillTests(unittest.TestCase):
    """Codex r2 [Should]: a pre-0007 row has NULL GH-81 recency; rerank-from-cache
    (fired on every hide click) must NOT blank the board before the first resync.
    Migration 0008 backfills NULL rows to the old author-email behavior."""

    def test_migration_0008_backfills_and_rerank_keeps_roster(self) -> None:
        from rebalance.ingest.db import db_connection, run_migrations
        from rebalance.ingest.db.migrate import discover_migrations
        from rebalance.ingest.db.schema import (
            ensure_baseline_schema, ensure_schema_version_table,
        )
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "rebalance.db"
            with db_connection(db) as conn:
                ensure_baseline_schema(conn)
                ensure_schema_version_table(conn)
                conn.execute("INSERT OR IGNORE INTO schema_version (version, applied_at) "
                             "VALUES (1, 't')")
                # Apply real migrations THROUGH 0007 (adds the NULL columns) but not 0008.
                for ver, path in discover_migrations():
                    if ver > 7:
                        break
                    conn.executescript(path.read_text(encoding="utf-8"))
                    conn.execute("INSERT OR IGNORE INTO schema_version (version, applied_at) "
                                 "VALUES (?, 't')", (ver,))
                # Seed a legacy row: authored commit, but NULL GH-81 recency — exactly
                # a pre-0007 row after 0007 adds the columns.
                conn.execute(
                    "INSERT INTO focus5_repo_signals "
                    "(device_id, local_path, repo_name, has_upstream, ahead, behind, "
                    " modified_count, untracked_count, is_dirty, my_last_commit_ts, "
                    " my_local_commit_ts, recency_basis, probed_at) "
                    "VALUES ('dev','/r/legacy','legacy',0,0,0,0,0,0,?,NULL,NULL,'t')",
                    (NOW - HOUR,),
                )
                conn.commit()
                # run_migrations now applies 0008 → backfills the NULL row.
                run_migrations(conn)
                row = conn.execute(
                    "SELECT my_local_commit_ts, recency_basis FROM focus5_repo_signals "
                    "WHERE local_path='/r/legacy'"
                ).fetchone()
                self.assertEqual(row["my_local_commit_ts"], NOW - HOUR)
                self.assertEqual(row["recency_basis"], "author_email")
            # The hide/rerank path (recent_activity) keeps the repo — board not blanked.
            self.assertEqual(
                rerank_focus5_from_cache(db, device_id="dev", mode="recent_activity"), 1
            )


class Focus5WorktreeTopologyTests(unittest.TestCase):
    """Codex r2 [Nit]: discovery handles `.git` as a file (linked worktree), but no
    reflog fixture exercised it. Pin that the vector resolves for a worktree."""

    def test_linked_worktree_git_file_resolves_reflog_basis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            main = _make_git_repo(Path(tmp), "main_repo")  # one commit on main
            wt = Path(tmp) / "wt"
            _run(main, "git", "worktree", "add", "-q", str(wt), "-b", "feature")
            (wt / "w.txt").write_text("x", encoding="utf-8")
            _run(wt, "git", "add", ".")
            env = {
                **os.environ,
                "GIT_AUTHOR_EMAIL": "me@example.com", "GIT_AUTHOR_NAME": "A",
                "GIT_COMMITTER_EMAIL": "me@example.com", "GIT_COMMITTER_NAME": "A",
            }
            _run(wt, "git", "commit", "-q", "-m", "wt commit", env=env)
            self.assertTrue((wt / ".git").is_file())  # linked worktree → .git is a FILE
            ts, available = _probe_head_reflog_commit(wt)
            self.assertTrue(available)
            self.assertIsNotNone(ts)
            s = probe_repo_signals(wt, device_id="dev", probed_at="t")
            self.assertEqual(s.recency_basis, "local_reflog")
            self.assertIsNotNone(s.my_local_commit_ts)


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

    def test_roster_drops_repo_removed_from_disk_without_resync(self) -> None:
        # GH-109: the Mac app's refresh is a read-only summarize (no disk rescan).
        # A checkout/worktree deleted from disk must vanish from the roster anyway,
        # not linger from its stale cached row until the next full sync.
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repos"
            root.mkdir()
            _make_git_repo(root, "keep", dirty=True)
            _make_git_repo(root, "gone", dirty=True)
            db = _db(Path(tmp))
            sync_focus5(db, roots=[root], device_id="dev", mode="dirty_first", limit=2)
            before = {c["repo_name"] for c in summarize_focus5(db, device_id="dev")["roster"]}
            self.assertEqual(before, {"keep", "gone"})  # both rostered at limit=2

            shutil.rmtree(root / "gone")  # as `git worktree remove` / rm -rf would

            out = summarize_focus5(db, device_id="dev")  # read-only, NO resync
            self.assertEqual({c["repo_name"] for c in out["roster"]}, {"keep"})
            self.assertNotIn(
                "gone", {w["repo_name"] for w in out["off_roster_warnings"]})

    def test_off_roster_drops_repo_removed_from_disk_without_resync(self) -> None:
        # GH-109, off-roster path: a deleted repo sitting in the attention strip must
        # also drop on a read-only refresh (and must not get promoted into the roster).
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repos"
            root.mkdir()
            _make_git_repo(root, "a", dirty=True)
            _make_git_repo(root, "b", dirty=True)
            db = _db(Path(tmp))
            sync_focus5(db, roots=[root], device_id="dev", mode="dirty_first", limit=1)
            off = summarize_focus5(db, device_id="dev")["off_roster_warnings"]
            self.assertEqual(len(off), 1)  # one rostered, one off-roster at limit=1
            gone_name, gone_path = off[0]["repo_name"], off[0]["local_path"]

            shutil.rmtree(gone_path)  # delete the off-roster repo from disk

            out = summarize_focus5(db, device_id="dev")  # read-only, NO resync
            self.assertNotIn(
                gone_name, {w["repo_name"] for w in out["off_roster_warnings"]})
            self.assertNotIn(
                gone_name, {c["repo_name"] for c in out["roster"]})  # not promoted

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

    # --- /api/focus5/open — focus-if-open exec endpoint (VSCODE Phase 2) ---

    def _post_open(self, db: Path, payload: dict, **kw):
        from fastapi.testclient import TestClient
        from rebalance.web import app
        os.environ["REBALANCE_DB"] = str(db)
        try:
            return TestClient(app).post("/api/focus5/open", json=payload, **kw)
        finally:
            os.environ.pop("REBALANCE_DB", None)

    def test_open_allowlist_resolves_known_and_rejects_unknown(self) -> None:
        # The resolver runs the REAL summarize over the seeded temp repo (no mocks):
        # a known id maps to a server-owned local_path; an unknown id is absent.
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = self._seed(Path(tmp))
            from rebalance import web
            os.environ["REBALANCE_DB"] = str(db)
            try:
                allow = web._focus5_open_allowlist(db)
            finally:
                os.environ.pop("REBALANCE_DB", None)
            self.assertTrue(allow, "seeded roster should resolve at least one repo")
            _identity, local_path = next(iter(allow.items()))
            self.assertTrue(os.path.isdir(local_path))     # a real, server-owned path
            self.assertNotIn("no/such-repo", allow)        # unknown id not in allowlist

    def test_open_known_repo_runs_code_with_server_path(self) -> None:
        # Known id → the launcher runs `code <server_path>` as a direct argv (no
        # shell). Allowlist mocked so no git/subprocess from the resolver collides.
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = self._seed(Path(tmp))
            fake = mock.Mock(returncode=0)
            with mock.patch("rebalance.web._request_is_local", return_value=True), \
                 mock.patch("rebalance.web._focus5_open_allowlist",
                            return_value={"demo/repo": "/repos/demo"}), \
                 mock.patch("rebalance.web._resolve_code_binary", return_value="/usr/bin/code"), \
                 mock.patch("subprocess.run", return_value=fake) as run:
                resp = self._post_open(db, {"repo": "demo/repo"})
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.json()["ok"])
            run.assert_called_once()
            self.assertEqual(run.call_args.args[0], ["/usr/bin/code", "/repos/demo"])

    def test_open_unknown_repo_is_404_and_runs_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = self._seed(Path(tmp))
            with mock.patch("rebalance.web._request_is_local", return_value=True), \
                 mock.patch("rebalance.web._focus5_open_allowlist",
                            return_value={"demo/repo": "/repos/demo"}), \
                 mock.patch("rebalance.web._resolve_code_binary", return_value="/usr/bin/code"), \
                 mock.patch("subprocess.run") as run:
                resp = self._post_open(db, {"repo": "no/such-repo"})
            self.assertEqual(resp.status_code, 404)
            run.assert_not_called()

    def test_open_missing_code_binary_is_409(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = self._seed(Path(tmp))
            with mock.patch("rebalance.web._request_is_local", return_value=True), \
                 mock.patch("rebalance.web._focus5_open_allowlist",
                            return_value={"demo/repo": "/repos/demo"}), \
                 mock.patch("rebalance.web._resolve_code_binary", return_value=None):
                resp = self._post_open(db, {"repo": "demo/repo"})
            self.assertEqual(resp.status_code, 409)   # client falls back to vscode://

    def test_open_non_local_request_is_403_and_runs_nothing(self) -> None:
        # Integration: with the real guard in place, a TestClient POST (non-loopback
        # client host) is refused before anything runs.
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = self._seed(Path(tmp))
            with mock.patch("subprocess.run") as run:
                resp = self._post_open(db, {"repo": "anything"})
            self.assertEqual(resp.status_code, 403)
            run.assert_not_called()

    def test_request_is_local_guard(self) -> None:
        # Unit-test the two-layer gate over a fake request (agy QA r1 Finding 1).
        from types import SimpleNamespace
        from rebalance.web import _request_is_local

        def req(host: str | None, origin: str | None = None):
            client = SimpleNamespace(host=host) if host is not None else None
            headers = {"origin": origin} if origin else {}
            return SimpleNamespace(client=client, headers=headers)

        # loopback client, no Origin (curl-style) → allowed
        self.assertTrue(_request_is_local(req("127.0.0.1")))
        self.assertTrue(_request_is_local(req("::1")))
        # loopback client + same-origin → allowed
        self.assertTrue(_request_is_local(req("127.0.0.1", "http://127.0.0.1:8787")))
        self.assertTrue(_request_is_local(req("localhost", "http://localhost:8787")))
        # loopback client + cross-origin → refused (CSRF guard)
        self.assertFalse(_request_is_local(req("127.0.0.1", "http://evil.example")))
        # non-loopback client → refused even with no Origin (the LAN/curl gap)
        self.assertFalse(_request_is_local(req("192.168.1.50")))
        self.assertFalse(_request_is_local(req("192.168.1.50", "http://127.0.0.1")))
        # missing client → refused
        self.assertFalse(_request_is_local(req(None)))

    def test_resolve_code_binary_rejects_directory(self) -> None:
        # agy QA r1 Finding 2: a VSCODE_BIN pointing at a dir (X_OK true for dirs)
        # must NOT be returned as the launcher.
        from rebalance.web import _resolve_code_binary
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"VSCODE_BIN": d}), \
                 mock.patch("rebalance.web._VSCODE_CODE_CANDIDATES", ()), \
                 mock.patch("shutil.which", return_value=None):
                self.assertIsNone(_resolve_code_binary())

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
            conn.commit()
            conn.close()
            with mock.patch("rebalance.ingest.focus5_scan.sync_focus5") as m:
                resp = self._get(db)
            self.assertEqual(resp.status_code, 200)
            self.assertFalse(m.called)                       # stale → no inline scan
            self.assertIn("⚠ stale", resp.text)             # but the staleness is surfaced

    # --- /focus-5.json — the read-only JSON contract the macOS app consumes ---

    def _roster_rows(self, db: Path):
        conn = sqlite3.connect(str(db))
        try:
            return conn.execute(
                "SELECT device_id, local_path, position, rank_reason, "
                "ranking_mode, computed_at FROM focus5_roster ORDER BY position"
            ).fetchall()
        finally:
            conn.close()

    def test_focus5_json_returns_contract_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = self._seed(Path(tmp))
            resp = self._get(db, "/focus-5.json")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.headers["content-type"], "application/json")
            data = resp.json()
            self.assertEqual(
                set(data),
                {"roster", "off_roster_warnings", "dirty_banner", "computed_at",
                 "ranking_mode", "summary"},
            )
            self.assertLessEqual(len(data["roster"]), 5)
            self.assertEqual(
                set(data["summary"]),
                {"discovered", "roster_size", "off_roster_attention", "rank_cutoff_ts"},
            )
            card = data["roster"][0]
            for key in ("position", "repo_name", "local_path", "vscode_url",
                        "branch", "is_dirty", "newest_pr", "recent_activity",
                        "health_available", "my_local_commit_ts", "recency_basis"):
                self.assertIn(key, card)
            self.assertTrue(card["vscode_url"].startswith("vscode://file"))

    def test_focus5_json_is_read_only_no_scan_no_write(self) -> None:
        # The macOS client polls this on a timer; it must never trigger the ~30s
        # device git scan and must never rewrite the persisted roster.
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = self._seed(Path(tmp))
            before = self._roster_rows(db)
            with mock.patch("rebalance.ingest.focus5_scan.sync_focus5") as m:
                resp = self._get(db, "/focus-5.json")
            self.assertEqual(resp.status_code, 200)
            self.assertFalse(m.called)                       # GET never scans
            self.assertEqual(self._roster_rows(db), before)  # GET never writes

    def test_focus5_json_dirty_view_reranks_without_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = self._seed(Path(tmp))
            before = self._roster_rows(db)
            with mock.patch("rebalance.ingest.focus5_scan.sync_focus5") as m:
                resp = self._get(db, "/focus-5.json?view=dirty")
            self.assertEqual(resp.status_code, 200)
            self.assertFalse(m.called)
            self.assertEqual(resp.json()["ranking_mode"], "dirty_first")
            self.assertEqual(self._roster_rows(db), before)  # transient re-rank only

    def test_focus5_json_missing_db_returns_empty_contract(self) -> None:
        # Brand-new machine (no DB): same shape, empty roster — not a 404/500.
        from fastapi.testclient import TestClient
        from rebalance.paths import DatabaseNotFoundError
        from rebalance.web import app
        with mock.patch("rebalance.paths.resolve_database_path",
                        side_effect=DatabaseNotFoundError([])):
            resp = TestClient(app).get("/focus-5.json")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(
            set(data),
            {"roster", "off_roster_warnings", "dirty_banner", "computed_at",
             "ranking_mode", "summary"},
        )
        self.assertEqual(data["roster"], [])
        self.assertEqual(data["summary"]["roster_size"], 0)


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
        out = summarize_focus5(self.db, device_id="dev", drop_missing_paths=False,
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
            out = summarize_focus5(self.db, device_id="dev", drop_missing_paths=False,
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
        default = summarize_focus5(self.db, device_id="dev", drop_missing_paths=False,
                                   with_activity=False, with_live_health=False)
        self.assertEqual([c["repo_name"] for c in default["roster"]],
                         ["clean_recent", "dirty_old"])
        self.assertEqual(default["ranking_mode"], "recent_activity")

        # Transient Dirty Five view: dirty_first ordering, same signal cache.
        dirty = summarize_focus5(self.db, device_id="dev", drop_missing_paths=False, mode="dirty_first",
                                 with_activity=False, with_live_health=False)
        self.assertEqual(dirty["roster"][0]["repo_name"], "dirty_old")
        self.assertEqual(dirty["ranking_mode"], "dirty_first")

        # The persisted roster is UNTOUCHED — re-read still recent_activity order.
        again = summarize_focus5(self.db, device_id="dev", drop_missing_paths=False,
                                 with_activity=False, with_live_health=False)
        self.assertEqual([c["repo_name"] for c in again["roster"]],
                         ["clean_recent", "dirty_old"])
        self.assertEqual(again["ranking_mode"], "recent_activity")

    def test_transient_view_carries_signal_freshness(self) -> None:
        self._seed_two()
        out = summarize_focus5(self.db, device_id="dev", drop_missing_paths=False, mode="dirty_first",
                               with_activity=False, with_live_health=False)
        # computed_at reflects the cached signals' probed_at (the last sync).
        self.assertEqual(out["computed_at"], "2026-06-05T00:00:00Z")


class DirtyBannerIntegrationTests(_ConfigIsolated):
    """GH-105: summarize_focus5() surfaces the single newest dirty off-roster
    repo end-to-end, via the same seeded-cache + rerank path as the transient
    Dirty Five tests above (deterministic — no real git commit timing)."""

    def _seed(self) -> None:
        clean_active = _sig("clean_active", device_id="dev", my_last_commit_ts=NOW,
                            local_path="/repos/clean_active", repo_full_name="Org/clean_active")
        dirty_leftover = _sig("dirty_leftover", device_id="dev", is_dirty=True,
                              modified_count=3, my_last_commit_ts=NOW - 5 * DAY,
                              local_path="/repos/dirty_leftover",
                              repo_full_name="Org/dirty_leftover")
        _seed_signals(self.db, [clean_active, dirty_leftover])

    def test_dirty_banner_surfaces_the_repo_pushed_off_the_roster(self) -> None:
        self._seed()
        rerank_focus5_from_cache(self.db, device_id="dev", mode="recent_activity", limit=1)
        out = summarize_focus5(self.db, device_id="dev", drop_missing_paths=False,
                               with_activity=False, with_live_health=False)
        self.assertEqual([c["repo_name"] for c in out["roster"]], ["clean_active"])
        self.assertIsNotNone(out["dirty_banner"])
        self.assertEqual(out["dirty_banner"]["repo_name"], "dirty_leftover")

    def test_dirty_banner_absent_when_off_roster_is_all_clean(self) -> None:
        older_clean = _sig("older_clean", device_id="dev", my_last_commit_ts=NOW - DAY,
                           local_path="/repos/older_clean", repo_full_name="Org/older_clean")
        newer_clean = _sig("newer_clean", device_id="dev", my_last_commit_ts=NOW,
                           local_path="/repos/newer_clean", repo_full_name="Org/newer_clean")
        _seed_signals(self.db, [older_clean, newer_clean])
        rerank_focus5_from_cache(self.db, device_id="dev", mode="recent_activity", limit=1)
        out = summarize_focus5(self.db, device_id="dev", drop_missing_paths=False,
                               with_activity=False, with_live_health=False)
        self.assertIsNone(out["dirty_banner"])

    def test_dirty_banner_is_none_on_transient_dirty_five_rerank(self) -> None:
        # Dirty Five already shows every dirty repo as a full card — the banner
        # would be redundant there, so it must be suppressed (mode is not None).
        self._seed()
        rerank_focus5_from_cache(self.db, device_id="dev", mode="recent_activity", limit=1)
        out = summarize_focus5(self.db, device_id="dev", drop_missing_paths=False, mode="dirty_first",
                               with_activity=False, with_live_health=False)
        self.assertIsNone(out["dirty_banner"])


class Focus5IdentityTests(unittest.TestCase):
    def test_identity_prefers_full_name_then_path(self) -> None:
        self.assertEqual(focus5_repo_identity(_sig("x", repo_full_name="Org/x")), "Org/x")
        self.assertEqual(
            focus5_repo_identity(_sig("y", repo_full_name=None, local_path="/repos/y")),
            "/repos/y",
        )


if __name__ == "__main__":
    unittest.main()

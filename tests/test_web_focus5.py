"""Tests for the Focus 5 web view renderer (rebalance.web._focus5_body).

These are pure: they feed _focus5_body a hand-built summarize_focus5()-shaped
dict and assert the rendered HTML, with no DB or git. The full stack (collector
-> route) is covered by the TestClient case in test_focus5_scan.py.
"""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from rebalance.web import _focus5_body, _rel_time, _roster_stale


def _now_iso(**delta) -> str:
    return (datetime.now(timezone.utc) - timedelta(**delta)).isoformat()


def _card(**over) -> dict:
    base = dict(
        position=1, repo_name="rebalance-OS",
        local_path="/Users/me/dev/rebalance-OS",
        vscode_url="vscode://file/Users/me/dev/rebalance-OS",
        rank_reason="5 modified, 7 untracked",
        is_dirty=True, modified_count=5, untracked_count=7,
        branch="development", has_upstream=True, ahead=2, behind=0,
        remote_url="https://github.com/Org/rebalance-OS.git",
        repo_full_name="Org/rebalance-OS",
        newest_pr=None, recent_activity=[],
        health_available=True, health_probed_at=_now_iso(minutes=0),
    )
    base.update(over)
    return base


def _data(roster, **over) -> dict:
    d = dict(
        roster=roster, off_roster_warnings=[],
        computed_at=_now_iso(hours=1), ranking_mode="dirty_first",
        summary={"discovered": 21, "roster_size": len(roster),
                 "off_roster_attention": len(over.get("off_roster_warnings", []))},
    )
    d.update(over)
    return d


class FocusBodyTests(unittest.TestCase):
    def test_empty_roster_shows_guidance(self) -> None:
        body = _focus5_body(_data([]))
        self.assertIn("No active repos found", body)
        self.assertNotIn("f5-grid", body)

    def test_renders_card_with_vscode_link_and_health(self) -> None:
        body = _focus5_body(_data([_card()]))
        self.assertIn("f5-grid", body)
        self.assertIn("rebalance-OS", body)
        self.assertIn("vscode://file/Users/me/dev/rebalance-OS", body)  # Open in VS Code
        self.assertIn("5 modified", body)
        self.assertIn("development", body)         # branch
        self.assertIn("↑2 ↓0", body)               # ahead/behind drift
        self.assertIn("dirty_first", body)         # roster meta
        self.assertIn("#1", body)                  # position

    def test_renders_newest_pr_link(self) -> None:
        card = _card(newest_pr={
            "number": 54, "title": "Focus 5 Phase 1", "state": "open",
            "html_url": "https://github.com/Org/rebalance-OS/pull/54",
            "is_draft": False, "is_merged": False,
        })
        body = _focus5_body(_data([card]))
        self.assertIn("#54", body)
        self.assertIn("Focus 5 Phase 1", body)
        self.assertIn("/pull/54", body)

    def test_pr_fallback_states_are_explicit(self) -> None:
        synced = _focus5_body(_data([_card(newest_pr=None, repo_full_name="Org/x")]))
        self.assertIn("no open PR synced yet", synced)
        nongh = _focus5_body(_data([_card(repo_full_name=None, remote_url="git@gitlab.com:x/y.git")]))
        self.assertIn("non-GitHub remote", nongh)
        local = _focus5_body(_data([_card(repo_full_name=None, remote_url=None)]))
        self.assertIn("no remote configured", local)

    def test_renders_recent_activity(self) -> None:
        card = _card(recent_activity=[
            {"sha": "abc1234", "subject": "feat: add thing",
             "committed_at": "2026-06-05T00:00:00+00:00", "author_email": "me@x"},
        ])
        body = _focus5_body(_data([card]))
        self.assertIn("feat: add thing", body)
        self.assertIn("abc1234", body)

    def test_html_is_escaped(self) -> None:
        # A hostile PR title / commit subject must not inject markup.
        card = _card(
            newest_pr={"number": 1, "title": "<script>x</script>", "state": "open",
                       "html_url": "https://h/pull/1", "is_draft": False, "is_merged": False},
            recent_activity=[{"sha": "d", "subject": "<b>boom</b>",
                              "committed_at": "2026-06-05T00:00:00+00:00", "author_email": "m"}],
        )
        body = _focus5_body(_data([card]))
        self.assertNotIn("<script>x</script>", body)
        self.assertIn("&lt;script&gt;", body)
        self.assertNotIn("<b>boom</b>", body)

    def test_clean_repo_shows_clean_health(self) -> None:
        card = _card(is_dirty=False, modified_count=0, untracked_count=0,
                     rank_reason="your commit 1h ago", ahead=0)
        body = _focus5_body(_data([card]))
        self.assertIn("clean", body)
        self.assertIn("your commit 1h ago", body)

    def test_has_refresh_button_and_live_marker(self) -> None:
        body = _focus5_body(_data([_card()]))
        self.assertIn("/focus-5?refresh=1", body)          # manual refresh control
        self.assertIn("tree health checked live", body)    # freshness marker

    def test_fresh_roster_not_flagged_stale(self) -> None:
        body = _focus5_body(_data([_card()], computed_at=_now_iso(hours=2)))
        self.assertNotIn("⚠ stale", body)

    def test_old_roster_flagged_stale(self) -> None:
        body = _focus5_body(_data([_card()], computed_at=_now_iso(days=2)))
        self.assertIn("⚠ stale", body)

    def test_warning_strip_lists_off_roster_repos(self) -> None:
        warns = [
            {"repo_name": "side-proj", "local_path": "/x/side-proj", "repo_full_name": None,
             "branch": "main", "ahead": 3, "modified_count": 0, "untracked_count": 0,
             "is_dirty": False, "probed_at": _now_iso(hours=1)},
            {"repo_name": "scratch", "local_path": "/x/scratch", "repo_full_name": None,
             "branch": "main", "ahead": 0, "modified_count": 2, "untracked_count": 1,
             "is_dirty": True, "probed_at": _now_iso(hours=1)},
        ]
        body = _focus5_body(_data([_card()], off_roster_warnings=warns))
        self.assertIn("f5-warn", body)
        self.assertIn("side-proj", body)
        self.assertIn("3 unpushed", body)
        self.assertIn("scratch", body)
        self.assertIn("2 modified", body)

    def test_no_warning_strip_when_all_clear(self) -> None:
        body = _focus5_body(_data([_card()]))  # no off-roster warnings
        self.assertNotIn("f5-warn", body)

    def test_unavailable_health_renders_safely(self) -> None:
        card = _card(health_available=False)
        body = _focus5_body(_data([card]))
        self.assertIn("unavailable", body)


class ViewToggleTests(unittest.TestCase):
    """The Focus 5 / Dirty Five segmented toggle, shared by both views."""

    def test_default_view_is_focus5_and_shows_both_tabs(self) -> None:
        body = _focus5_body(_data([_card()]))
        self.assertIn("🎯 Focus 5", body)
        self.assertIn("f5-views", body)             # toggle present
        self.assertIn("🧹 Dirty Five", body)        # the other tab is linked
        self.assertIn("?view=dirty", body)          # link to the dirty view

    def test_dirty_view_is_titled_and_keeps_view_on_refresh(self) -> None:
        body = _focus5_body(_data([_card()], ranking_mode="dirty_first"), view="dirty")
        self.assertIn("🧹 Dirty Five", body)
        self.assertIn("f5-view active", body)       # a tab is marked active
        self.assertIn("refresh=1&amp;view=dirty", body)  # refresh stays on Dirty Five

    def test_dirty_empty_state_differs_from_default(self) -> None:
        body = _focus5_body(_data([]), view="dirty")
        self.assertIn("Nothing at risk", body)
        self.assertNotIn("No active repos found", body)
        self.assertIn("f5-views", body)             # toggle still shown when empty


class RosterStaleTests(unittest.TestCase):
    def test_missing_is_stale(self) -> None:
        self.assertTrue(_roster_stale(None))
        self.assertTrue(_roster_stale("not-a-date"))

    def test_recent_is_fresh(self) -> None:
        self.assertFalse(_roster_stale(_now_iso(hours=1)))

    def test_old_is_stale(self) -> None:
        self.assertTrue(_roster_stale(_now_iso(days=2)))


class RelTimeTests(unittest.TestCase):
    def test_handles_none_and_garbage(self) -> None:
        self.assertEqual(_rel_time(None), "")
        self.assertEqual(_rel_time("not-a-date"), "")

    def test_formats_z_suffix(self) -> None:
        # Should parse a trailing-Z timestamp without raising.
        self.assertIsInstance(_rel_time("2026-06-05T00:00:00Z"), str)


class HideButtonTests(unittest.TestCase):
    def test_card_renders_hide_button_with_full_name_identity(self) -> None:
        body = _focus5_body(_data([_card()]))
        self.assertIn("class='f5-hide'", body)
        self.assertIn('data-f5-hide="Org/rebalance-OS"', body)  # repo_full_name wins
        self.assertIn("/api/focus5/hide", body)                 # POST target in JS

    def test_hide_identity_falls_back_to_local_path(self) -> None:
        body = _focus5_body(_data([_card(
            repo_full_name=None, remote_url=None,
            local_path="/Users/me/dev/local-only",
        )]))
        self.assertIn('data-f5-hide="/Users/me/dev/local-only"', body)

    def test_empty_roster_has_no_hide_assets(self) -> None:
        body = _focus5_body(_data([]))
        self.assertNotIn("f5-hide", body)


class OpenButtonTests(unittest.TestCase):
    def test_card_has_open_button_pointing_at_vscode_url(self) -> None:
        body = _focus5_body(_data([_card()]))
        self.assertIn("rb-btn", body)                  # shared "Button ↗" helper
        self.assertIn("rb-btn-arrow", body)            # the ↗ affordance
        self.assertIn("vscode://file/Users/me/dev/rebalance-OS", body)

    def test_open_and_hide_share_the_action_cluster(self) -> None:
        body = _focus5_body(_data([_card()]))
        self.assertIn("f5-actions", body)              # top-right cluster
        self.assertIn("rb-btn", body)                  # Open ↗
        self.assertIn("f5-hide", body)                 # ✕ still present


class RouteScanTriggerTests(unittest.TestCase):
    """focus5_page must NOT run the ~30s synchronous sync_focus5 git scan on a
    stale page load — only on an explicit Refresh or a never-built roster."""

    def _load(self, *, refresh: bool, roster_size: int, computed_at):
        from unittest.mock import patch
        from rebalance import web

        meta = {"roster_size": roster_size, "computed_at": computed_at}
        with patch("rebalance.paths.resolve_database_path", return_value="db"), \
             patch("rebalance.ingest.focus5_scan.get_roster_meta", return_value=meta), \
             patch("rebalance.ingest.focus5_scan.summarize_focus5", return_value={"roster": []}), \
             patch("rebalance.ingest.focus5_scan.sync_focus5") as scan, \
             patch("rebalance.web._focus5_body", return_value=""), \
             patch("rebalance.web._page", return_value="OK"):
            web.focus5_page(refresh=refresh)
        return scan

    def test_stale_roster_does_not_trigger_blocking_scan(self) -> None:
        scan = self._load(refresh=False, roster_size=5, computed_at=_now_iso(days=2))
        scan.assert_not_called()

    def test_never_built_roster_triggers_first_scan(self) -> None:
        scan = self._load(refresh=False, roster_size=0, computed_at=None)
        scan.assert_called_once()

    def test_explicit_refresh_triggers_scan(self) -> None:
        from unittest.mock import patch
        from rebalance import web

        meta = {"roster_size": 5, "computed_at": _now_iso(days=2)}
        with patch("rebalance.paths.resolve_database_path", return_value="db"), \
             patch("rebalance.ingest.focus5_scan.get_roster_meta", return_value=meta), \
             patch("rebalance.ingest.focus5_scan.sync_focus5") as scan, \
             patch("rebalance.ingest.focus5_scan.summarize_focus5", return_value={"roster": []}):
            web.focus5_page(refresh=True)  # returns a redirect before render
        scan.assert_called_once()


if __name__ == "__main__":
    unittest.main()

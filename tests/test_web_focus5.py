"""Tests for the Focus 5 web view renderer (rebalance.web._focus5_body).

These are pure: they feed _focus5_body a hand-built summarize_focus5()-shaped
dict and assert the rendered HTML, with no DB or git. The full stack (collector
-> route) is covered by the TestClient case in test_focus5_scan.py.
"""
from __future__ import annotations

import unittest

from rebalance.web import _focus5_body, _rel_time


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
    )
    base.update(over)
    return base


def _data(roster, **over) -> dict:
    d = dict(
        roster=roster, off_roster_warnings=[],
        computed_at="2026-06-05T00:00:00+00:00", ranking_mode="dirty_first",
        summary={"discovered": 21, "roster_size": len(roster), "off_roster_attention": 0},
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


class RelTimeTests(unittest.TestCase):
    def test_handles_none_and_garbage(self) -> None:
        self.assertEqual(_rel_time(None), "")
        self.assertEqual(_rel_time("not-a-date"), "")

    def test_formats_z_suffix(self) -> None:
        # Should parse a trailing-Z timestamp without raising.
        self.assertIsInstance(_rel_time("2026-06-05T00:00:00Z"), str)


if __name__ == "__main__":
    unittest.main()

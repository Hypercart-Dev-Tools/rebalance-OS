"""Tests for the Focus 5 web view renderer (rebalance.web._focus5_body).

These are pure: they feed _focus5_body a hand-built summarize_focus5()-shaped
dict and assert the rendered HTML, with no DB or git. The full stack (collector
-> route) is covered by the TestClient case in test_focus5_scan.py.
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

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
        recency_basis="local_reflog", my_local_commit_ts=None,
    )
    base.update(over)
    return base


def _data(roster, *, cutoff=None, **over) -> dict:
    d = dict(
        roster=roster, off_roster_warnings=[],
        computed_at=_now_iso(hours=1), ranking_mode="dirty_first",
        summary={"discovered": 21, "roster_size": len(roster),
                 "off_roster_attention": len(over.get("off_roster_warnings", [])),
                 "rank_cutoff_ts": cutoff},
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
            {"repo_name": "other-proj", "local_path": "/x/other-proj", "repo_full_name": None,
             "branch": "main", "ahead": 0, "modified_count": 0, "untracked_count": 0,
             "is_dirty": False, "probed_at": _now_iso(hours=1)},
        ]
        body = _focus5_body(_data([_card()], off_roster_warnings=warns))
        self.assertIn("f5-warn", body)
        self.assertIn("side-proj", body)
        self.assertIn("3 ahead of origin", body)
        self.assertIn("scratch", body)
        self.assertIn("uncommitted changes", body)
        self.assertIn("other-proj", body)
        self.assertIn("needs attention", body)

    def test_no_warning_strip_when_all_clear(self) -> None:
        body = _focus5_body(_data([_card()]))  # no off-roster warnings
        self.assertNotIn("f5-warn", body)

    # --- GH-81 Phase 2: explain UX on the off-roster strip + card basis badge ---

    def test_off_roster_strip_explains_recency_vs_cutoff(self) -> None:
        # The original GH-81 forensics question, answered inline: a dirty repo whose
        # last LOCAL commit is below the #5 cutoff shows exactly why it's off-roster.
        now = int(datetime.now(timezone.utc).timestamp())
        warns = [{
            "repo_name": "sleuth-app", "local_path": "/x/sleuth-app",
            "repo_full_name": None, "branch": "main", "ahead": 0,
            "modified_count": 1, "untracked_count": 0, "is_dirty": True,
            "probed_at": _now_iso(hours=1),
            "recency_basis": "local_reflog", "my_local_commit_ts": now - 3 * 86400,
        }]
        body = _focus5_body(_data([_card()], off_roster_warnings=warns,
                                  ranking_mode="recent_activity",
                                  cutoff=now - 16 * 3600))  # #5 cutoff = 16h ago
        self.assertIn("sleuth-app", body)
        self.assertIn("your local commit 3d ago", body)
        self.assertIn("below the #5 cutoff", body)

    def test_off_roster_strip_shows_fallback_basis(self) -> None:
        now = int(datetime.now(timezone.utc).timestamp())
        warns = [{
            "repo_name": "no-reflog-clone", "local_path": "/x/no-reflog-clone",
            "repo_full_name": None, "branch": "main", "ahead": 1,
            "modified_count": 0, "untracked_count": 0, "is_dirty": False,
            "probed_at": _now_iso(hours=1),
            "recency_basis": "author_email", "my_local_commit_ts": now - 2 * 3600,
        }]
        body = _focus5_body(_data([_card()], off_roster_warnings=warns,
                                  ranking_mode="recent_activity", cutoff=now))
        self.assertIn("ranked by author email", body)  # the fallback is shown, not silent

    def test_dirty_view_suppresses_focus5_explain_copy(self) -> None:
        # Codex r2: the explain copy ("below the #5 cutoff", "Focus 5") is
        # recent_activity-specific — the Dirty Five board must NOT render it.
        now = int(datetime.now(timezone.utc).timestamp())
        warns = [{
            "repo_name": "side-proj", "local_path": "/x/side-proj",
            "repo_full_name": None, "branch": "main", "ahead": 0,
            "modified_count": 1, "untracked_count": 0, "is_dirty": True,
            "probed_at": _now_iso(hours=1),
            "recency_basis": "local_reflog", "my_local_commit_ts": now - 3 * 86400,
        }]
        body = _focus5_body(_data([_card()], off_roster_warnings=warns,
                                  ranking_mode="dirty_first", cutoff=None),
                            view="dirty")
        self.assertIn("side-proj", body)            # repo still listed…
        self.assertNotIn("below the #5 cutoff", body)  # …but no Focus-5 cutoff copy
        self.assertNotIn("not eligible for Focus 5", body)

    def test_roster_card_shows_fallback_basis_badge(self) -> None:
        # A rostered repo that ranked by a fallback basis must surface it on-card.
        body = _focus5_body(_data([_card(recency_basis="author_email")]))
        self.assertIn("f5-basis", body)
        self.assertIn("via author email", body)

    def test_roster_card_no_badge_on_normal_reflog_basis(self) -> None:
        body = _focus5_body(_data([_card(recency_basis="local_reflog")]))
        self.assertNotIn("f5-basis", body)

    def test_unavailable_health_renders_safely(self) -> None:
        card = _card(health_available=False)
        body = _focus5_body(_data([card]))
        self.assertIn("unavailable", body)

    # --- GH-105: the single "BTW, this went dirty" banner ---

    def test_dirty_banner_renders_repo_and_detail(self) -> None:
        now = int(datetime.now(timezone.utc).timestamp())
        banner = {
            "repo_name": "sleuth-app", "local_path": "/x/sleuth-app",
            "repo_full_name": "me/sleuth-app", "branch": "development",
            "ahead": 0, "modified_count": 4, "untracked_count": 0,
            "is_dirty": True, "probed_at": _now_iso(hours=1),
            "my_local_commit_ts": now - 2 * 3600, "recency_basis": "local_reflog",
        }
        body = _focus5_body(_data([_card()], dirty_banner=banner))
        self.assertIn("f5-dirty-banner", body)
        self.assertIn("sleuth-app", body)
        self.assertIn("4 modified", body)
        self.assertIn("2h ago", body)

    def test_no_dirty_banner_when_absent(self) -> None:
        body = _focus5_body(_data([_card()]))  # no dirty_banner key at all
        self.assertNotIn("f5-dirty-banner", body)

    def test_no_dirty_banner_when_none(self) -> None:
        body = _focus5_body(_data([_card()], dirty_banner=None))
        self.assertNotIn("f5-dirty-banner", body)

    def test_dirty_banner_escapes_repo_name(self) -> None:
        now = int(datetime.now(timezone.utc).timestamp())
        banner = {
            "repo_name": "<script>x</script>", "local_path": "/x/evil",
            "repo_full_name": None, "branch": "main", "ahead": 0,
            "modified_count": 1, "untracked_count": 0, "is_dirty": True,
            "probed_at": _now_iso(hours=1),
            "my_local_commit_ts": now - 3600, "recency_basis": "local_reflog",
        }
        body = _focus5_body(_data([_card()], dirty_banner=banner))
        self.assertNotIn("<script>x</script>", body)
        self.assertIn("&lt;script&gt;", body)


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


class Focus5NoteRouteTests(unittest.TestCase):
    """GET /focus-5/note — the read-only vault `focus5.md` projection.

    Always returns the same {exists, content, path} shape at HTTP 200; the vault
    path is resolved via config.get_vault_path (patched here so no real vault is
    touched). The route reads only — these never write a file.
    """

    def _get(self):
        from fastapi.testclient import TestClient
        from rebalance.web import app
        return TestClient(app).get("/focus-5/note")

    def test_serves_note_content_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "focus5.md").write_text("# Today\n- ship the note\n", encoding="utf-8")
            with mock.patch("rebalance.ingest.config.get_vault_path", return_value=tmp):
                resp = self._get()
            self.assertEqual(resp.status_code, 200)
            body = resp.json()
            self.assertTrue(body["exists"])
            self.assertIn("ship the note", body["content"])
            self.assertTrue(body["path"].endswith("focus5.md"))

    def test_missing_note_returns_exists_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:  # vault dir exists, no focus5.md
            with mock.patch("rebalance.ingest.config.get_vault_path", return_value=tmp):
                resp = self._get()
            self.assertEqual(resp.status_code, 200)
            body = resp.json()
            self.assertFalse(body["exists"])
            self.assertEqual(body["content"], "")
            self.assertIsNone(body["path"])

    def test_no_vault_configured_returns_exists_false(self) -> None:
        with mock.patch("rebalance.ingest.config.get_vault_path", return_value=None):
            resp = self._get()
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body["exists"])
        self.assertEqual(body["content"], "")

    def test_oversized_note_is_capped(self) -> None:
        from rebalance.web import FOCUS5_NOTE_MAX_CHARS
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "focus5.md").write_text("x" * (FOCUS5_NOTE_MAX_CHARS + 5000), encoding="utf-8")
            with mock.patch("rebalance.ingest.config.get_vault_path", return_value=tmp):
                resp = self._get()
            self.assertEqual(len(resp.json()["content"]), FOCUS5_NOTE_MAX_CHARS)

    def test_directory_named_focus5_md_is_not_a_note(self) -> None:
        # A focus5.md *directory* must degrade to exists:false, not crash on read.
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "focus5.md").mkdir()
            with mock.patch("rebalance.ingest.config.get_vault_path", return_value=tmp):
                resp = self._get()
            self.assertEqual(resp.status_code, 200)
            self.assertFalse(resp.json()["exists"])


class Focus5GoalsRouteTests(unittest.TestCase):
    def _get(self):
        from fastapi.testclient import TestClient
        from rebalance.web import app
        return TestClient(app).get("/focus-5/goals")

    def _post_complete(self, payload: dict[str, object]):
        from fastapi.testclient import TestClient
        from rebalance.web import app
        return TestClient(app).post("/api/focus5/goals/complete", json=payload)

    def test_serves_top_open_goals_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "0. Goals.md").write_text(
                "\n".join(f"- [ ] Open item {i}" for i in range(1, 11)),
                encoding="utf-8",
            )
            with mock.patch("rebalance.ingest.config.get_vault_path", return_value=tmp):
                resp = self._get()
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["exists"])
        self.assertEqual(body["total_open"], 10)
        self.assertEqual(len(body["items"]), 8)
        self.assertEqual(body["items"][0]["title"], "Open item 1")
        self.assertEqual(body["items"][-1]["title"], "Open item 8")

    def test_missing_goals_returns_exists_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("rebalance.ingest.config.get_vault_path", return_value=tmp):
                resp = self._get()
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["exists"])
        self.assertEqual(resp.json()["items"], [])
        self.assertEqual(resp.json()["reason"], "file_missing")
        self.assertTrue(resp.json()["path"].endswith("0. Goals.md"))

    def test_no_vault_configured_returns_reason(self) -> None:
        with mock.patch("rebalance.ingest.config.get_vault_path", return_value=None):
            resp = self._get()
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body["exists"])
        self.assertEqual(body["reason"], "vault_not_configured")
        self.assertIn("vault_path", body["message"])

    def test_complete_marks_exact_line_then_returns_refreshed_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            goals = Path(tmp) / "0. Goals.md"
            goals.write_text(
                "\n".join(
                    [
                        "- [ ] Duplicate",
                        "- [ ] Unique",
                        "- [ ] Duplicate",
                    ]
                ),
                encoding="utf-8",
            )
            with mock.patch("rebalance.ingest.config.get_vault_path", return_value=tmp), \
                 mock.patch("rebalance.web._request_is_local", return_value=True):
                resp = self._post_complete({"title": "Duplicate", "line_index": 2})
            self.assertEqual(resp.status_code, 200)
            body = resp.json()
            self.assertTrue(body["ok"])
            self.assertEqual(body["total_open"], 2)
            self.assertEqual([item["title"] for item in body["items"]], ["Duplicate", "Unique"])
            self.assertEqual(
                goals.read_text(encoding="utf-8").splitlines(),
                ["- [ ] Duplicate", "- [ ] Unique", "- [x] Duplicate"],
            )

    def test_complete_rejects_non_local_requests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "0. Goals.md").write_text("- [ ] One\n", encoding="utf-8")
            with mock.patch("rebalance.ingest.config.get_vault_path", return_value=tmp), \
                 mock.patch("rebalance.web._request_is_local", return_value=False):
                resp = self._post_complete({"title": "One", "line_index": 0})
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(resp.json()["ok"])


if __name__ == "__main__":
    unittest.main()

"""3-Eyes fleet-health tile on /focus-5.json (GH-195).

The synthetic 6th roster card must be additive, gated, defensive, and cached. These
are pure unit tests over the web.py helpers — no DB, no launchctl, no FastAPI stack.
"""
from __future__ import annotations

import unittest
from unittest import mock

from rebalance import web

# A required-field checklist mirrored from macOS/Apps/Focus5Float/CONTRACT.md — the
# non-optional RepoCard fields the Swift client will fail to decode if any is absent.
REQUIRED = [
    "position", "repo_name", "local_path", "vscode_url", "rank_reason", "ranking_mode",
    "computed_at", "ahead", "behind", "modified_count", "untracked_count", "is_dirty",
    "health_available", "recent_activity",
]

FAILING_REPORT = {
    "ok": 24, "failing": 2, "not_loaded": 1,
    "rows": [
        {"label": "com.x.ga-pull", "health": "FAIL(exit 1)"},
        {"label": "com.x.pulse", "health": "FAIL(exit 1)"},
        {"label": "com.x.ok", "health": "ok"},
    ],
}
OK_REPORT = {"ok": 25, "failing": 0, "not_loaded": 0, "rows": []}


def _reset_cache():
    web._te_health_cache["at"] = -1e9
    web._te_health_cache["card"] = None


class BuildCardTests(unittest.TestCase):
    def test_failing_report_flags_dirty_and_titles_failing(self):
        card = web._build_three_eyes_card(FAILING_REPORT)
        self.assertTrue(card["is_dirty"])                 # red StatusDot
        self.assertIn("FAILING", card["repo_name"])
        self.assertIn("2", card["repo_name"])
        self.assertEqual(card["modified_count"], 2)        # failing count
        self.assertEqual(card["untracked_count"], 1)       # not-loaded count
        self.assertIn("com.x.ga-pull", card["rank_reason"])
        self.assertEqual(card["ranking_mode"], "three_eyes_health")

    def test_all_ok_report_is_clean(self):
        card = web._build_three_eyes_card(OK_REPORT)
        self.assertFalse(card["is_dirty"])
        self.assertIn("all jobs OK", card["repo_name"])

    def test_card_has_every_required_repocard_field(self):
        card = web._build_three_eyes_card(FAILING_REPORT)
        missing = [k for k in REQUIRED if k not in card]
        self.assertEqual(missing, [], f"missing required RepoCard fields: {missing}")

    def test_commit_timestamps_are_null_so_subtitle_shows_reason(self):
        # commitLine (Swift) falls back to rank_reason only when these are null.
        card = web._build_three_eyes_card(FAILING_REPORT)
        for k in ("last_commit_at", "last_commit_ts", "my_last_commit_ts"):
            self.assertIsNone(card[k])


class CardGatingTests(unittest.TestCase):
    def setUp(self):
        _reset_cache()
        self.addCleanup(_reset_cache)

    def test_none_when_three_eyes_inert(self):
        with mock.patch.object(web, "_three_eyes_health_scan", return_value=None):
            self.assertIsNone(web._three_eyes_health_card(6))

    def test_none_and_no_raise_when_scan_errors(self):
        with mock.patch.object(web, "_three_eyes_health_scan",
                               side_effect=RuntimeError("launchctl blew up")):
            self.assertIsNone(web._three_eyes_health_card(6))  # swallowed, roster intact

    def test_position_is_restamped(self):
        with mock.patch.object(web, "_three_eyes_health_scan", return_value=FAILING_REPORT):
            self.assertEqual(web._three_eyes_health_card(6)["position"], 6)

    def test_scan_is_cached_within_ttl(self):
        with mock.patch.object(web, "_three_eyes_health_scan",
                               return_value=FAILING_REPORT) as m:
            web._three_eyes_health_card(6)
            web._three_eyes_health_card(7)   # within TTL → no second scan
            self.assertEqual(m.call_count, 1)


if __name__ == "__main__":
    unittest.main()

"""Tests for the GH-124 repo-pie 'New repo added' top-item annotation."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import pulse_web  # noqa: E402


class RepoPieAutoPromoteBadgeTests(unittest.TestCase):
    def test_no_recent_promotion_renders_no_badge(self) -> None:
        html = pulse_web.render_repo_pie(
            [{"repo_full_name": "Acme/widget", "events": 5}], days=7, recent_promotion=None
        )
        self.assertNotIn("repo-pie-new-badge", html)

    def test_recent_promotion_renders_badge_with_project_name(self) -> None:
        html = pulse_web.render_repo_pie(
            [{"repo_full_name": "Acme/widget", "events": 5}],
            days=7,
            recent_promotion={"repo": "Acme/widget", "project_name": "widget", "promoted_at": "2026-07-10T00:00:00+00:00"},
        )
        self.assertIn("repo-pie-new-badge", html)
        self.assertIn("New repo added: widget", html)

    def test_recent_promotion_renders_on_empty_rows_too(self) -> None:
        html = pulse_web.render_repo_pie(
            [],
            days=7,
            recent_promotion={"repo": "Acme/widget", "project_name": "widget", "promoted_at": "2026-07-10T00:00:00+00:00"},
        )
        self.assertIn("New repo added: widget", html)


if __name__ == "__main__":
    unittest.main()

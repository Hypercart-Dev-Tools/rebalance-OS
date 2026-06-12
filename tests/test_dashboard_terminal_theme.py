"""Terminal theme guardrails for the live Rich dashboard."""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from rebalance.ingest import config as config_module
from rebalance.ingest.config import set_github_ignored_repos, set_pulse_config
from rebalance.ingest.db import db_connection, ensure_calendar_schema, ensure_github_schema
from rebalance.ingest.sleuth_reminders import ensure_sleuth_schema


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_PATH = ROOT / "scripts" / "dashboard.py"


def _load_dashboard(*, inverse: bool, database_path: Path | None = None):
    module_name = f"_dashboard_theme_{uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, DASHBOARD_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load dashboard module")

    env = {"PULSE_INVERSE": "1" if inverse else "0"}
    if database_path is not None:
        env["REBALANCE_DB"] = str(database_path)

    with patch.dict(os.environ, env):
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module


def _relative_luminance(hex_color: str) -> float:
    raw = hex_color.lstrip("#")
    channels = [int(raw[i : i + 2], 16) / 255 for i in (0, 2, 4)]

    def linear(channel: float) -> float:
        if channel <= 0.03928:
            return channel / 12.92
        return ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = [linear(channel) for channel in channels]
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _contrast_ratio(foreground: str, background: str) -> float:
    fg = _relative_luminance(foreground)
    bg = _relative_luminance(background)
    lighter, darker = max(fg, bg), min(fg, bg)
    return (lighter + 0.05) / (darker + 0.05)


class DashboardTerminalThemeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_config_path = config_module.CONFIG_PATH

    def tearDown(self) -> None:
        config_module.CONFIG_PATH = self._orig_config_path

    def test_inverse_theme_uses_explicit_light_palette_not_ansi_reverse(self) -> None:
        dashboard = _load_dashboard(inverse=True)

        panel_style = dashboard._panel_style()

        self.assertNotIn("reverse", panel_style["style"])
        self.assertNotIn("reverse", panel_style["border_style"])
        self.assertIn(dashboard.PALETTE["bg"], panel_style["style"])
        self.assertEqual(dashboard.PALETTE, dashboard.LIGHT_PALETTE)

    def test_dashboard_text_colors_clear_wcag_contrast_in_both_modes(self) -> None:
        for inverse in (False, True):
            dashboard = _load_dashboard(inverse=inverse)
            bg = dashboard.PALETTE["bg"]

            for color_key in ("fg", "fg_muted", "fg_dim", "accent", "ok", "info", "warn", "danger"):
                with self.subTest(inverse=inverse, color=color_key):
                    ratio = _contrast_ratio(dashboard.PALETTE[color_key], bg)
                    self.assertGreaterEqual(ratio, 4.5)

    def test_recent_github_feed_hides_ignored_repos_already_in_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "rebalance.db"
            config_module.CONFIG_PATH = root / "rbos.config"
            set_github_ignored_repos(["QuantumSorcerer02/design.md"])

            with db_connection(db_path) as conn:
                ensure_github_schema(conn)
                conn.execute(
                    """
                    INSERT INTO github_items
                        (repo_full_name, item_type, number, title, state, author_login,
                         assignees_json, labels_json, html_url, created_at, updated_at, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "QuantumSorcerer02/design.md",
                        "issue",
                        70,
                        "Ignored issue",
                        "open",
                        "QuantumSorcerer02",
                        "[]",
                        "[]",
                        "https://example.test/ignored",
                        "2026-05-04T17:00:00Z",
                        "2026-05-04T17:00:00Z",
                        "2026-05-04T17:00:00Z",
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO github_items
                        (repo_full_name, item_type, number, title, state, author_login,
                         assignees_json, labels_json, html_url, created_at, updated_at, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "kissplugins/KISS-woo-order-monitoring-alerts",
                        "issue",
                        27,
                        "Visible issue",
                        "open",
                        "noelsaw1",
                        "[\"noelsaw1\"]",
                        "[]",
                        "https://example.test/visible",
                        "2026-05-04T16:00:00Z",
                        "2026-05-04T16:00:00Z",
                        "2026-05-04T16:00:00Z",
                    ),
                )
                conn.commit()

            dashboard = _load_dashboard(inverse=False, database_path=db_path)
            rows = dashboard.fetch_recent_github(limit=10)

        self.assertEqual([row["repo_full_name"] for row in rows], ["kissplugins/KISS-woo-order-monitoring-alerts"])

    def test_calendar_upcoming_uses_absolute_time_for_offset_rows(self) -> None:
        now = datetime(2026, 5, 14, 15, 25, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "rebalance.db"
            config_module.CONFIG_PATH = root / "rbos.config"

            with db_connection(db_path, ensure_calendar_schema) as conn:
                conn.executemany(
                    """
                    INSERT INTO calendar_events
                        (id, summary, start_time, end_time, location, attendees_json,
                         calendar_id, status, description, fetched_at)
                    VALUES (?, ?, ?, ?, '', '[]', 'primary', 'confirmed', '', ?)
                    """,
                    [
                        (
                            "past-morning",
                            "Past local morning",
                            "2026-05-14T08:00:00-07:00",
                            "2026-05-14T08:30:00-07:00",
                            now.isoformat(),
                        ),
                        (
                            "next-morning",
                            "Next local morning",
                            "2026-05-14T09:00:00-07:00",
                            "2026-05-14T09:30:00-07:00",
                            now.isoformat(),
                        ),
                        (
                            "end-of-day",
                            "End of day",
                            "2026-05-14T17:00:00-07:00",
                            "2026-05-14T17:30:00-07:00",
                            now.isoformat(),
                        ),
                        (
                            "tomorrow-morning",
                            "Tomorrow morning",
                            "2026-05-15T08:30:00-07:00",
                            "2026-05-15T09:00:00-07:00",
                            now.isoformat(),
                        ),
                    ],
                )
                conn.commit()

            dashboard = _load_dashboard(inverse=False, database_path=db_path)
            rows = dashboard.fetch_calendar_upcoming(now, limit=3)

        self.assertEqual(
            [row["summary"] for row in rows],
            ["Next local morning", "End of day", "Tomorrow morning"],
        )

    def test_dashboard_refresh_skips_semantic_embedding(self) -> None:
        dashboard = _load_dashboard(inverse=False)
        result = {
            "elapsed_seconds": 1.2,
            "results": [
                {
                    "scope": "github",
                    "artifact_sync": [
                        {"repo": "example/repo", "elapsed_seconds": 1.0},
                    ],
                    "semantic": {"skipped": True},
                }
            ],
            "errors": [],
        }

        with (
            patch.object(dashboard, "refresh_index", return_value=result) as refresh,
            patch.object(dashboard, "_write_refresh_profile"),
        ):
            dashboard._do_refresh()

        refresh.assert_called_once_with(dashboard.DB_PATH, scope=["github"])
        snapshot = dashboard.REFRESH.snapshot()
        self.assertEqual(snapshot["status"], "ok")
        self.assertEqual(snapshot["last_profile"]["slowest_repo"], "example/repo")

    def test_sleuth_panel_includes_reminders_assigned_by_me(self) -> None:
        from datetime import datetime, timedelta, timezone

        # Use relative timestamps so the test stays valid as wall-clock time
        # advances: fetch_sleuth_due filters out reminders whose
        # should_post_on is more than 2 days in the past. Hardcoded dates
        # would silently rot.
        now = datetime.now(timezone.utc)
        created_iso = (now - timedelta(hours=1)).isoformat()
        seen_iso = now.isoformat()
        ordered_post_times = {
            "to-me": (now + timedelta(hours=1)).isoformat(),
            "by-me": (now + timedelta(hours=2)).isoformat(),
            "not-mine": (now + timedelta(hours=3)).isoformat(),
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "rebalance.db"
            config_module.CONFIG_PATH = root / "rbos.config"
            set_pulse_config(slack_user_id="U032TCHJ8")

            with db_connection(db_path, ensure_sleuth_schema) as conn:
                for reminder_id, assignee_id, sender_id, message in [
                    ("to-me", "U032TCHJ8", "U999", "Assigned to me"),
                    ("by-me", "U08BHQEAX", "U032TCHJ8", "Assigned by me"),
                    ("not-mine", "U08BHQEAX", "U999", "Not mine"),
                ]:
                    conn.execute(
                        """
                        INSERT INTO sleuth_reminders (
                            reminder_id, workspace_name, state, is_active,
                            created_on, should_post_on, reminder_message_text,
                            ignore_snooze, assignee_id, original_sender_id,
                            target_channel_id, original_channel_id, original_channel_name,
                            original_message_id, original_thread_ts, github_urls_json,
                            first_seen_at, last_seen_at, last_synced_at
                        ) VALUES (?, 'neochrome-dev', 'scheduled', 1,
                            ?, ?, ?, 0, ?, ?, 'C1', 'C2', 'eng',
                            '123.456', NULL, '[]', ?, ?, ?
                        )
                        """,
                        (
                            reminder_id,
                            created_iso,
                            ordered_post_times[reminder_id],
                            message,
                            assignee_id,
                            sender_id,
                            seen_iso,
                            seen_iso,
                            seen_iso,
                        ),
                    )
                conn.commit()

            dashboard = _load_dashboard(inverse=False, database_path=db_path)
            rows = dashboard.fetch_sleuth_due(limit=10)

        self.assertEqual([row["reminder_id"] for row in rows], ["to-me", "by-me"])
        self.assertEqual(rows[0]["sleuth_role"], "assigned_to_me")
        self.assertEqual(rows[1]["sleuth_role"], "assigned_by_me")


if __name__ == "__main__":
    unittest.main()

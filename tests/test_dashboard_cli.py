"""CLI tests for dashboard rendering and optional Gemini synthesis."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from rebalance.cli import app
from rebalance.ingest.calendar_config import CalendarConfig
from rebalance.ingest.db import db_connection, ensure_calendar_schema, ensure_github_schema, ensure_project_schema


def _calendar_config() -> CalendarConfig:
    return CalendarConfig(
        calendar_id="primary",
        exclude_titles=[],
        aggregator_skip_words=[],
        timezone="America/Los_Angeles",
        projects=[],
        hours_format="decimal",
    )


def _seed_dashboard_db(database_path: Path) -> None:
    with db_connection(database_path) as conn:
        ensure_project_schema(conn)
        ensure_github_schema(conn)
        ensure_calendar_schema(conn)
        conn.execute(
            """
            INSERT INTO project_registry
                (name, status, summary, value_level, priority_tier, risk_level,
                 repos_json, tags_json, custom_fields_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Binoid",
                "active",
                "High-priority storefront and SEO work.",
                None,
                1,
                "medium",
                json.dumps(["BinoidCBD/universal-child-theme-oct-2024"]),
                json.dumps(["source:github"]),
                json.dumps({}),
            ),
        )
        conn.execute(
            """
            INSERT INTO github_activity
                (login, repo_full_name, scan_date, commits, pushes, prs_opened, prs_merged,
                 issues_opened, issue_comments, reviews, last_active_at, scanned_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "tester",
                "BinoidCBD/universal-child-theme-oct-2024",
                "2999-04-28",
                7,
                3,
                2,
                1,
                0,
                0,
                0,
                "2999-04-28T16:00:00Z",
                "2999-04-28T16:05:00Z",
            ),
        )
        conn.executemany(
            """
            INSERT INTO calendar_events
                (id, summary, start_time, end_time, location, attendees_json,
                 calendar_id, status, description, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "evt-1",
                    "Binoid sprint review",
                    "2026-04-28T10:00:00-07:00",
                    "2026-04-28T11:30:00-07:00",
                    "",
                    "[]",
                    "primary",
                    "confirmed",
                    "",
                    "2026-04-28T18:00:00Z",
                ),
                (
                    "evt-2",
                    "Mystery sync",
                    "2026-04-27T13:00:00-07:00",
                    "2026-04-27T13:30:00-07:00",
                    "",
                    "[]",
                    "primary",
                    "confirmed",
                    "",
                    "2026-04-28T18:00:00Z",
                ),
            ],
        )
        conn.commit()


class DashboardRenderCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_dashboard_render_writes_vault_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "rebalance.db"
            vault_path = root / "vault"
            vault_path.mkdir()
            changelog_path = root / "CHANGELOG.md"
            goals_path = root / "4X4.md"
            _seed_dashboard_db(db_path)
            changelog_path.write_text(
                "\n".join(
                    [
                        "# Changelog",
                        "",
                        "## [0.21.0] - 2026-04-28",
                        "",
                        "### Added",
                        "",
                        "- Added inferred project registry.",
                    ]
                ),
                encoding="utf-8",
            )
            goals_path.write_text(
                "\n".join(
                    [
                        "PROJECT OVERVIEW",
                        "demo",
                        "",
                        "B. CURRENT WEEK GOALS",
                        "1. [ ] Generate the first dashboard note.",
                        "",
                        "C. LAST WEEKS ACCOMPLISHMENTS",
                    ]
                ),
                encoding="utf-8",
            )

            with (
                patch("rebalance.ingest.calendar_config.CalendarConfig.load", return_value=_calendar_config()),
                patch("rebalance.ingest.dashboard.load_review_decisions", return_value={}),
            ):
                result = self.runner.invoke(
                    app,
                    [
                        "dashboard-render",
                        "--database",
                        str(db_path),
                        "--vault",
                        str(vault_path),
                        "--date",
                        "2026-04-28",
                        "--changelog-path",
                        str(changelog_path),
                        "--goals-path",
                        str(goals_path),
                    ],
                )

            self.assertEqual(result.exit_code, 0)
            note_path = vault_path / "Dashboards" / "rebalanceOS Dashboard.md"
            self.assertTrue(note_path.exists())
            note_text = note_path.read_text(encoding="utf-8")
            self.assertIn("# rebalanceOS Dashboard", note_text)
            self.assertIn("Added inferred project registry.", note_text)
            self.assertIn("Generate the first dashboard note.", note_text)
            self.assertIn("### Binoid", note_text)
            self.assertIn("Mystery sync", note_text)
            self.assertIn("Dashboard written to", result.output)

    def test_dashboard_render_with_gemini_summary_and_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "rebalance.db"
            output_path = root / "dashboard.md"
            changelog_path = root / "CHANGELOG.md"
            goals_path = root / "4X4.md"
            _seed_dashboard_db(db_path)
            changelog_path.write_text("# Changelog\n", encoding="utf-8")
            goals_path.write_text("B. CURRENT WEEK GOALS\n1. [ ] Keep momentum.\nC. LAST WEEKS ACCOMPLISHMENTS\n", encoding="utf-8")

            with (
                patch("rebalance.ingest.calendar_config.CalendarConfig.load", return_value=_calendar_config()),
                patch("rebalance.ingest.dashboard.load_review_decisions", return_value={}),
                patch("rebalance.ingest.dashboard.get_gemini_api_key", return_value="test-key"),
                patch("rebalance.ingest.dashboard.synthesize_dashboard_narrative", return_value="Short operator summary.") as mock_synth,
            ):
                result = self.runner.invoke(
                    app,
                    [
                        "dashboard-render",
                        "--database",
                        str(db_path),
                        "--output",
                        str(output_path),
                        "--date",
                        "2026-04-28",
                        "--changelog-path",
                        str(changelog_path),
                        "--goals-path",
                        str(goals_path),
                        "--gemini-synthesis",
                        "--cleanup",
                    ],
                )

            self.assertEqual(result.exit_code, 0)
            note_text = output_path.read_text(encoding="utf-8")
            self.assertIn("Short operator summary.", note_text)
            self.assertTrue(mock_synth.called)
            self.assertEqual(mock_synth.call_args.kwargs["cleanup"], True)


if __name__ == "__main__":
    unittest.main()

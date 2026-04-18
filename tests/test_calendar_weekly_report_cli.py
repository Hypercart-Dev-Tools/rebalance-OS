"""Tests for weekly report write-back into the vault."""

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from rebalance.cli import app
from rebalance.ingest.calendar_config import CalendarConfig
from rebalance.ingest.embedder import EmbedResult
from rebalance.ingest.note_ingester import IngestResult


def _insert_events(database_path: Path, events: list[tuple], calendar_id: str = "primary") -> None:
    from rebalance.ingest.calendar import ensure_calendar_schema
    from rebalance.ingest.db import get_connection

    conn = get_connection(database_path)
    ensure_calendar_schema(conn)
    conn.executemany(
        """
        INSERT INTO calendar_events
        (id, summary, start_time, end_time, location, attendees_json,
         calendar_id, status, description, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (eid, summary, start, end, "", "[]", calendar_id, "confirmed", "", "2026-04-07T10:00:00+00:00")
            for eid, summary, start, end in events
        ],
    )
    conn.commit()
    conn.close()


WEEK_EVENTS = [
    ("w1", "Binoid - SEO", "2026-03-30T17:00:00+00:00", "2026-03-30T19:00:00+00:00"),
    ("w2", "CR - CC", "2026-03-31T17:00:00+00:00", "2026-03-31T18:30:00+00:00"),
]


class CalendarWeeklyReportCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_write_week_note_reingests_and_embeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "cal.db"
            vault_path = Path(tmpdir) / "vault"
            vault_path.mkdir()
            _insert_events(db_path, WEEK_EVENTS)
            resolved_db_path = db_path.resolve()
            resolved_vault_path = vault_path.resolve()

            config = CalendarConfig(
                calendar_id="primary",
                exclude_titles=[],
                aggregator_skip_words=[],
                timezone="America/Los_Angeles",
                projects=[],
                hours_format="decimal",
            )

            with (
                patch("rebalance.ingest.calendar_config.CalendarConfig.load", return_value=config),
                patch(
                    "rebalance.ingest.note_ingester.ingest_vault",
                    return_value=IngestResult(1, 1, 0, 0, 0, 2, 2, 0, 0.12),
                ) as mock_ingest,
                patch(
                    "rebalance.ingest.embedder.embed_chunks",
                    return_value=EmbedResult(2, 1, 1, "fake-model", 1024, 0.08),
                ) as mock_embed,
            ):
                result = self.runner.invoke(
                    app,
                    [
                        "calendar-weekly-report",
                        "--database",
                        str(db_path),
                        "--date",
                        str(date(2026, 3, 31)),
                        "--vault",
                        str(vault_path),
                        "--write-week-note",
                    ],
                )
                self.assertEqual(result.exit_code, 0)
                note_path = resolved_vault_path / "Weekly Notes" / "week-of-2026-03-29.md"
                self.assertTrue(note_path.exists())
                note_text = note_path.read_text(encoding="utf-8")
                self.assertIn("## End of Week Summary", note_text)
                self.assertIn("type: weekly-review", note_text)
                mock_ingest.assert_called_once_with(vault_path=resolved_vault_path, database_path=resolved_db_path)
                mock_embed.assert_called_once_with(database_path=resolved_db_path)
                self.assertIn("Week note written to", result.output)
                self.assertIn("Vault ingest complete", result.output)
                self.assertIn("Embed complete", result.output)

    def test_write_week_note_requires_vault(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "cal.db"
            _insert_events(db_path, [])
            result = self.runner.invoke(
                app,
                [
                    "calendar-weekly-report",
                    "--database",
                    str(db_path),
                    "--write-week-note",
                ],
            )

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("--vault or REBALANCE_VAULT is required", result.output)

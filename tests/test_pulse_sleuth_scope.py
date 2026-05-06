"""Tests for Sleuth reminder scope in pulse rendering."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from rebalance.ingest.db import db_connection, ensure_github_schema, ensure_schema
from rebalance.ingest.pulse import _query_day_activity
from rebalance.ingest.sleuth_reminders import ensure_sleuth_schema


def _ensure_pulse_query_schemas(conn: object) -> None:
    ensure_schema(conn)
    ensure_github_schema(conn)
    ensure_sleuth_schema(conn)


def _insert_reminder(
    conn: object,
    *,
    reminder_id: str,
    assignee_id: str,
    original_sender_id: str,
    message: str,
) -> None:
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
            '123.456', NULL, ?, ?, ?, ?
        )
        """,
        (
            reminder_id,
            "2026-05-05T17:00:00+00:00",
            "2026-05-05T20:00:00+00:00",
            message,
            assignee_id,
            original_sender_id,
            json.dumps([]),
            "2026-05-05T18:00:00+00:00",
            "2026-05-05T18:00:00+00:00",
            "2026-05-05T18:00:00+00:00",
        ),
    )


class PulseSleuthScopeTests(unittest.TestCase):
    def test_includes_reminders_assigned_to_me_and_assigned_by_me(self) -> None:
        slack_user_id = "U032TCHJ8"
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            with db_connection(db_path, _ensure_pulse_query_schemas) as conn:
                _insert_reminder(
                    conn,
                    reminder_id="assigned-to-me",
                    assignee_id=slack_user_id,
                    original_sender_id="U999",
                    message="Follow up assigned to me",
                )
                _insert_reminder(
                    conn,
                    reminder_id="assigned-by-me",
                    assignee_id="U08BHQEAX",
                    original_sender_id=slack_user_id,
                    message="Follow up assigned by me",
                )
                _insert_reminder(
                    conn,
                    reminder_id="not-mine",
                    assignee_id="U08BHQEAX",
                    original_sender_id="U999",
                    message="Someone else's reminder",
                )
                conn.commit()

                activity = _query_day_activity(
                    conn,
                    label="today",
                    start=datetime(2026, 5, 5, tzinfo=timezone.utc),
                    end=datetime(2026, 5, 6, tzinfo=timezone.utc),
                    github_login="noelsaw1",
                    slack_user_id=slack_user_id,
                )

        reminders = {row["reminder_id"]: row for row in activity.sleuth_activity}
        self.assertEqual(set(reminders), {"assigned-to-me", "assigned-by-me"})
        self.assertEqual(reminders["assigned-to-me"]["sleuth_role"], "assigned_to_me")
        self.assertEqual(reminders["assigned-by-me"]["sleuth_role"], "assigned_by_me")


if __name__ == "__main__":
    unittest.main()

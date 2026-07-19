"""Regression coverage for declarative collector content-health checks."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import rebalance.doctor as doctor
from rebalance.doctor import OK, WARN, _COLLECTOR_FRESHNESS, _check_collector_freshness
from rebalance.ingest.db import db_connection, ensure_email_schema


def _collector(name: str) -> dict:
    return next(spec for spec in _COLLECTOR_FRESHNESS if spec["name"] == name)


class CollectorHealthPredicateTests(unittest.TestCase):
    def test_husk_email_rows_degrade_an_otherwise_fresh_collector(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "rebalance.db"
            with db_connection(db_path, ensure_email_schema) as conn:
                conn.executemany(
                    """
                    INSERT INTO email_messages
                    (message_id, snippet, synced_at) VALUES (?, 'metadata only', datetime('now'))
                    """,
                    [(f"husk-{n}",) for n in range(4)],
                )
                conn.commit()

            check = _check_collector_freshness(db_path, **_collector("email data"))

        self.assertEqual(check.status, WARN)
        self.assertIn("degraded", check.detail)
        self.assertIn("100%", check.detail)
        self.assertIn("sender or subject", check.detail)

    def test_successful_quiet_gmail_filter_stays_ok_and_names_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "rebalance.db"
            with db_connection(db_path, ensure_email_schema) as conn:
                conn.execute(
                    """
                    INSERT INTO email_messages
                    (message_id, from_address, subject, received_at, synced_at)
                    VALUES ('old-but-retained', 'person@example.test', 'Important thread',
                            datetime('now', '-31 days'), datetime('now'))
                    """
                )
                conn.commit()

            with patch(
                "rebalance.doctor._active_gmail_filter",
                return_value="Gmail filter: in:inbox is:starred is:important",
            ):
                spec = {**_collector("email data"), "quiet_filter": doctor._active_gmail_filter}
                check = _check_collector_freshness(db_path, **spec)

        self.assertEqual(check.status, OK)
        self.assertIn("no rows matched", check.detail)
        self.assertIn("in:inbox is:starred is:important", check.detail)

    def test_empty_collector_is_not_claimed_healthy_without_run_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "rebalance.db"
            with db_connection(db_path, ensure_email_schema):
                pass

            check = _check_collector_freshness(db_path, **_collector("email data"))

        self.assertEqual(check.status, WARN)
        self.assertIn("no email data ingested", check.detail)

    def test_source_without_predicate_keeps_legacy_freshness_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "rebalance.db"
            with db_connection(db_path) as conn:
                conn.execute("CREATE TABLE plain_rows (seen_at TEXT NOT NULL)")
                conn.execute("INSERT INTO plain_rows VALUES (datetime('now'))")
                conn.commit()

            check = _check_collector_freshness(
                db_path,
                name="plain data",
                table="plain_rows",
                ts_col="seen_at",
                warn_days=7,
                empty_hint="seed data",
                stale_hint="refresh data",
            )

        self.assertEqual(check.status, OK)
        self.assertIn("1 rows", check.detail)

    def test_second_collector_declares_its_predicate_without_check_logic(self) -> None:
        github = _collector("github data")
        email = _collector("email data")

        self.assertEqual(github["quality_predicate"], "title IS NOT NULL AND TRIM(title) != ''")
        self.assertIn("from_address", email["quality_predicate"])
        self.assertEqual(github["quality_table"], "github_items")


if __name__ == "__main__":
    unittest.main()

"""Regression coverage for GH-169 Phase 2 — attempt accounting.

The defect: `update_push_event()` charged an attempt unconditionally, while
`pending_push_events()` filters `attempt_count < MAX_EVENT_ATTEMPTS`. An event
deferred purely because a run hit its own per-refresh cap therefore burned an
attempt, and after three cap-losses was evicted permanently -- never fetched,
never reported. On the live DB that was 20 events, every one for "compare cap
reached", i.e. not a single genuine failure among them.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rebalance.ingest.db import db_connection, ensure_github_schema
from rebalance.ingest.db import github as gh
from rebalance.ingest.github_direct_commits import (
    MAX_EVENT_ATTEMPTS,
    classify_legacy_deferrals,
    recover_budget_evicted_events,
)

REPO = "Hypercart-Dev-Tools/rebalance-OS"


class PushEventAccountingTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db = Path(self._tmp.name) / "t.db"
        with db_connection(self.db, ensure_github_schema) as conn:
            for i in range(4):
                gh.insert_push_event(conn, (
                    f"e{i}", REPO, "refs/heads/development", "a" * 40, "b" * 40,
                    f"2026-07-1{i}T00:00:00Z", "2026-07-19T00:00:00Z",
                ))
            conn.commit()

    def tearDown(self):
        self._tmp.cleanup()

    def _attempts(self, event_id: str) -> int:
        with db_connection(self.db, ensure_github_schema) as conn:
            return conn.execute(
                "SELECT attempt_count FROM github_push_events WHERE event_id = ?",
                (event_id,),
            ).fetchone()[0]

    def _pending_ids(self) -> list[str]:
        with db_connection(self.db, ensure_github_schema) as conn:
            return [
                r["event_id"]
                for r in gh.pending_push_events(conn, 100, MAX_EVENT_ATTEMPTS)
            ]

    # -- the core invariant --

    def test_budget_deferral_does_not_charge_an_attempt(self):
        with db_connection(self.db, ensure_github_schema) as conn:
            for _ in range(5):
                gh.update_push_event(
                    conn, "e0", state="deferred", now="2026-07-19T00:00:00Z",
                    reason="compare cap reached", deferral_kind="budget",
                )
            conn.commit()
        self.assertEqual(self._attempts("e0"), 0)

    def test_budget_deferred_event_stays_eligible_after_many_runs(self):
        """The regression gate: losing the cap lottery must never evict."""
        with db_connection(self.db, ensure_github_schema) as conn:
            for _ in range(MAX_EVENT_ATTEMPTS + 3):
                gh.update_push_event(
                    conn, "e0", state="deferred", now="2026-07-19T00:00:00Z",
                    reason="compare cap reached", deferral_kind="budget",
                )
            conn.commit()
        self.assertIn("e0", self._pending_ids())

    # -- and the other direction: real failures must still stop --

    def test_genuine_failure_still_costs_an_attempt_and_stops_retrying(self):
        with db_connection(self.db, ensure_github_schema) as conn:
            for _ in range(MAX_EVENT_ATTEMPTS):
                gh.update_push_event(
                    conn, "e1", state="deferred", now="2026-07-19T00:00:00Z",
                    reason="compare HTTP 500", deferral_kind="failure",
                )
            conn.commit()
        self.assertEqual(self._attempts("e1"), MAX_EVENT_ATTEMPTS)
        # Must NOT become an infinite retry loop.
        self.assertNotIn("e1", self._pending_ids())

    def test_unclassified_deferral_defaults_to_charging_an_attempt(self):
        """Absent a kind, charge -- the conservative direction."""
        with db_connection(self.db, ensure_github_schema) as conn:
            gh.update_push_event(
                conn, "e2", state="deferred", now="2026-07-19T00:00:00Z",
                reason="something new",
            )
            conn.commit()
        self.assertEqual(self._attempts("e2"), 1)

    # -- migration: text is a one-time seed, never a control path --

    def test_legacy_rows_are_classified_from_reason_text_once(self):
        with db_connection(self.db, ensure_github_schema) as conn:
            conn.execute(
                "UPDATE github_push_events SET state='deferred', attempt_count=3, "
                "failure_reason='compare cap reached', deferral_kind=NULL "
                "WHERE event_id='e0'"
            )
            conn.execute(
                "UPDATE github_push_events SET state='deferred', attempt_count=3, "
                "failure_reason='compare HTTP 404', deferral_kind=NULL "
                "WHERE event_id='e1'"
            )
            conn.commit()

        self.assertEqual(classify_legacy_deferrals(self.db), 2)
        with db_connection(self.db, ensure_github_schema) as conn:
            kinds = {
                r[0]: r[1] for r in conn.execute(
                    "SELECT event_id, deferral_kind FROM github_push_events"
                )
            }
        self.assertEqual(kinds["e0"], "budget")
        self.assertEqual(kinds["e1"], "failure")

    # -- recovery: preview by default, snapshot before mutating --

    def _strand(self):
        with db_connection(self.db, ensure_github_schema) as conn:
            conn.execute(
                "UPDATE github_push_events SET state='deferred', attempt_count=3, "
                "failure_reason='compare cap reached', deferral_kind=NULL "
                "WHERE event_id IN ('e0','e1')"
            )
            conn.execute(
                "UPDATE github_push_events SET state='deferred', attempt_count=3, "
                "failure_reason='compare HTTP 404', deferral_kind=NULL "
                "WHERE event_id='e2'"
            )
            conn.commit()

    def test_recovery_previews_without_mutating(self):
        self._strand()
        result = recover_budget_evicted_events(self.db)
        self.assertEqual(result["eligible"], 2)
        self.assertFalse(result["applied"])
        # Preview must not resurrect anything.
        self.assertEqual(self._attempts("e0"), 3)
        self.assertNotIn("e0", self._pending_ids())

    def test_recovery_applies_and_writes_a_pre_image_snapshot(self):
        self._strand()
        snap = Path(self._tmp.name) / "snap.json"
        result = recover_budget_evicted_events(self.db, apply=True, snapshot_path=snap)

        self.assertTrue(result["applied"])
        self.assertEqual(result["eligible"], 2)
        self.assertIn("e0", self._pending_ids())
        self.assertEqual(self._attempts("e0"), 0)

        # A genuine failure must NOT be resurrected by the recovery.
        self.assertNotIn("e2", self._pending_ids())

        pre_image = json.loads(snap.read_text())
        self.assertEqual({r["event_id"] for r in pre_image}, {"e0", "e1"})
        self.assertTrue(all(r["attempt_count"] == 3 for r in pre_image))

    def test_recovery_is_idempotent(self):
        self._strand()
        recover_budget_evicted_events(self.db, apply=True)
        second = recover_budget_evicted_events(self.db, apply=True)
        self.assertEqual(second["eligible"], 0)


if __name__ == "__main__":
    unittest.main()

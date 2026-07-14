"""HiQS pipeline (GH-125) — the six-source unified ranked pipeline.

These are the executable acceptance proofs for the HiQS consolidation:

  Phase 1 — all six sources reach the ranker:
    * an ``email_messages`` row in the day window becomes a ``source == "email"``
      candidate,
    * an EMPTY ``figma_comments`` table yields zero figma candidates and does not
      raise, while a present unresolved comment DOES surface,
    * every ranked action carries ``source`` and non-empty ``evidence`` (Attested).

  Phase 3 — Principle 3 is discharged (a source is added by registering a
    collector, NOT by editing the dispatch chain): a FAKE collector with a
    ``candidates=`` provider reaches the ranked output with ZERO edits to
    next_actions.py / querier.py. This is the single most important artifact here.

Everything runs against a seeded temporary SQLite DB — no network, no model.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from rebalance.ingest.db import db_connection, run_migrations
from rebalance.ingest.next_actions import rank_next_actions

# A fixed instant; local tz is Etc/UTC in the sandbox, so this is inside the
# local day [2026-07-14T00:00Z, 2026-07-15T00:00Z).
NOW = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
IN_WINDOW = NOW.isoformat()


def _fresh_db(tmpdir: str) -> Path:
    db = Path(tmpdir) / "rebalance.db"
    with db_connection(db) as conn:
        run_migrations(conn)
        conn.commit()
    return db


def _seed_email(
    db: Path,
    *,
    subject: str,
    received_at: str = IN_WINDOW,
    message_id: str = "m1",
    from_address: str = "boss@acme.test",
    from_name: str = "The Boss",
) -> None:
    with db_connection(db) as conn:
        conn.execute(
            "INSERT INTO email_messages "
            "(message_id, thread_id, from_address, from_name, subject, snippet, "
            " received_at, labels_json, synced_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                message_id, "t1", from_address, from_name, subject,
                "please review the deploy checklist", received_at, "[]", IN_WINDOW,
            ),
        )
        conn.commit()


def _seed_figma(db: Path, *, resolved: bool, message: str = "tighten the header") -> None:
    with db_connection(db) as conn:
        conn.execute(
            "INSERT INTO figma_comments "
            "(comment_key, file_key, comment_id, parent_id, message, user_id, "
            " user_handle, created_at, resolved_at, order_id, client_meta_json, "
            " reactions_json, raw_json, synced_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "c1", "FILEKEY", "cid1", None, message, "u1", "designer",
                IN_WINDOW, (IN_WINDOW if resolved else None), 1.0, None, None,
                "{}", IN_WINDOW,
            ),
        )
        conn.commit()


class Phase1BundleTests(unittest.TestCase):
    """Phase 1 — email + figma reach the deterministic ranker floor."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._db = _fresh_db(self._tmp.name)

    def _rank(self):
        # blend_team=False + synthesize=False → the deterministic candidate floor,
        # no teammate calendar read, no LLM/network.
        return rank_next_actions(
            self._db, blend_team=False, synthesize=False, now=NOW
        )

    def test_email_row_becomes_email_candidate(self) -> None:
        """Acceptance #2: an email_messages row in the window → source=='email'."""
        _seed_email(self._db, subject="Deploy checklist")
        result = self._rank()
        email = [a for a in result.ranked if a.source == "email"]
        self.assertEqual(len(email), 1, msg=f"ranked={[a.as_dict() for a in result.ranked]}")
        self.assertEqual(email[0].title, "Deploy checklist")
        self.assertTrue(email[0].evidence, "email candidate must carry evidence")

    def test_contentless_email_shell_is_never_ranked(self) -> None:
        """Signal quality: a row with NO sender and NO subject earns no rank.

        Found by running the branch against the real DB (2026-07-14): 119 of 124
        `email_messages` rows are shells — a message_id and labels, but no headers.
        They are currently invisible only because their `received_at` is also empty.
        The day an ingest fix populates the timestamp but not the headers, every one
        of them would land at tier 1 — ABOVE open GitHub items — as "(no subject)
        from unknown sender". This pins the guard so that cannot happen silently.
        """
        _seed_email(
            self._db, subject="", from_address="", from_name="", message_id="shell",
        )
        _seed_email(self._db, subject="Real mail", message_id="real")
        result = self._rank()
        email = [a for a in result.ranked if a.source == "email"]
        self.assertEqual(
            [a.title for a in email], ["Real mail"],
            msg=f"contentless shell must not be ranked; got {[a.as_dict() for a in email]}",
        )

    def test_empty_figma_yields_no_candidates_and_does_not_raise(self) -> None:
        """Acceptance #3: an EMPTY figma_comments table → zero figma candidates."""
        _seed_email(self._db, subject="unrelated")  # ensure ranking runs
        result = self._rank()  # must not raise
        figma = [a for a in result.ranked if a.source == "figma"]
        self.assertEqual(figma, [])

    def test_present_unresolved_figma_comment_surfaces(self) -> None:
        """The dormant arm is correct: a present UNRESOLVED comment DOES surface."""
        _seed_figma(self._db, resolved=False)
        result = self._rank()
        figma = [a for a in result.ranked if a.source == "figma"]
        self.assertEqual(len(figma), 1)
        self.assertTrue(figma[0].evidence)

    def test_resolved_figma_comment_is_excluded(self) -> None:
        """resolved_at IS NULL filter: a resolved comment must NOT surface."""
        _seed_figma(self._db, resolved=True)
        result = self._rank()
        self.assertEqual([a for a in result.ranked if a.source == "figma"], [])

    def test_every_ranked_action_is_attested(self) -> None:
        """Acceptance #4: every ranked action carries source + non-empty evidence."""
        _seed_email(self._db, subject="Deploy checklist")
        _seed_figma(self._db, resolved=False)
        result = self._rank()
        self.assertTrue(result.ranked, "expected at least one candidate")
        for a in result.ranked:
            self.assertTrue(a.source, msg=f"missing source: {a.as_dict()}")
            self.assertTrue(
                [e for e in a.evidence if e],
                msg=f"missing/empty evidence: {a.as_dict()}",
            )


class Phase3RegistryWalkTests(unittest.TestCase):
    """Phase 3 — Principle 3 is discharged (THE keystone proof).

    A source reaches the ranked verdict by REGISTERING a collector with a
    ``candidates=`` provider — with ZERO edits to next_actions.py / querier.py.
    This test registers a brand-new fake collector at runtime and asserts its
    rows appear in the ranked output. The only "edit" is a register_collector
    call; the ranker walks the registry, so it needs no per-source dispatch.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._db = _fresh_db(self._tmp.name)

    def test_fake_collector_candidates_reach_ranked_output(self) -> None:
        from rebalance.ingest.index_ops import COLLECTORS, Collector, register_collector

        def _fake_provider(bundle):
            # Ignores the bundle entirely — a truly external source whose data is
            # NOT one of the six built-in bundle fields. Proves the walk is
            # source-agnostic: any registered provider's rows are ranked.
            return [{
                "rank_key": (3, IN_WINDOW),
                "title": "FAKE EXTERNAL SIGNAL",
                "source": "faketest",
                "evidence": ["fake://evidence/42"],
                "why": "registered via candidates= provider, no ranker edit",
            }]

        register_collector(
            Collector(
                "faketest",
                refresh=lambda db_path, **opts: {"scope": "faketest"},
                candidates=_fake_provider,
                included_in_all=False,
            )
        )
        self.addCleanup(lambda: COLLECTORS.pop("faketest", None))

        result = rank_next_actions(
            self._db, blend_team=False, synthesize=False, now=NOW
        )
        fake = [a for a in result.ranked if a.source == "faketest"]
        self.assertEqual(len(fake), 1, msg=f"ranked={[a.as_dict() for a in result.ranked]}")
        self.assertEqual(fake[0].title, "FAKE EXTERNAL SIGNAL")
        self.assertEqual(fake[0].evidence, ["fake://evidence/42"])

    def test_removing_the_collector_removes_its_candidates(self) -> None:
        """Symmetry: unregister → the source no longer reaches the ranked output."""
        from rebalance.ingest.index_ops import COLLECTORS, Collector, register_collector

        register_collector(
            Collector(
                "faketest2",
                refresh=lambda db_path, **opts: {"scope": "faketest2"},
                candidates=lambda bundle: [{
                    "rank_key": (3, IN_WINDOW), "title": "X", "source": "faketest2",
                    "evidence": ["e"], "why": "w",
                }],
                included_in_all=False,
            )
        )
        COLLECTORS.pop("faketest2", None)  # immediately unregister
        result = rank_next_actions(
            self._db, blend_team=False, synthesize=False, now=NOW
        )
        self.assertEqual([a for a in result.ranked if a.source == "faketest2"], [])


if __name__ == "__main__":
    unittest.main()

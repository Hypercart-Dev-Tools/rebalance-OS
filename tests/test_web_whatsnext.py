"""Tests for the What's Next web view renderer (rebalance.web._whatsnext_body).

Pure: feed _whatsnext_body a hand-built RankedNextActions.as_dict()-shaped dict
and assert the rendered HTML, with no DB or server. The full handler/route is
control-flow only and exercised at the surface level in test_web_surface.py.
"""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from rebalance.web import _whatsnext_body, whatsnext_page


def _now_iso(**delta) -> str:
    return (datetime.now(timezone.utc) - timedelta(**delta)).isoformat()


def _action(**over) -> dict:
    base = dict(
        rank=1,
        title="Push the calendar fix branch",
        person=None,
        source="github",
        project="Org/rebalance-OS",
        evidence=["https://github.com/Org/rebalance-OS/pull/54"],
        why="open PR you authored, awaiting push",
    )
    base.update(over)
    return base


def _data(ranked, **over) -> dict:
    d = dict(
        ranked=ranked,
        synthesis="",
        model_used="gemini-3.5-flash",
        blended=True,
        weights_used={},
        note="",
        elapsed_seconds=1.2,
        computed_at=_now_iso(hours=1),
    )
    d.update(over)
    return d


class WhatsNextBodyTests(unittest.TestCase):
    def test_empty_shows_guidance(self) -> None:
        body = _whatsnext_body(_data([]))
        self.assertIn("Nothing ranked yet", body)
        self.assertNotIn("wn-list", body)

    def test_empty_surfaces_note(self) -> None:
        body = _whatsnext_body(_data([], note="synthesis failed: boom"))
        self.assertIn("synthesis failed: boom", body)

    def test_renders_operator_and_teammate_items(self) -> None:
        ranked = [
            _action(rank=1, person=None, title="Operator task"),
            _action(rank=2, person="Matt", source="calendar",
                    title="Teammate review block", project=None,
                    evidence=["Matt 14:00 (30m)"], why="cross-person signal"),
        ]
        body = _whatsnext_body(_data(ranked))
        self.assertIn("wn-list", body)
        self.assertIn("#1", body)
        self.assertIn("#2", body)
        self.assertIn("Operator task", body)
        self.assertIn("Teammate review block", body)
        # Operator vs teammate attribution badges.
        self.assertIn("You", body)            # operator badge
        self.assertIn("Matt", body)           # teammate label
        # Evidence + why render.
        self.assertIn("cross-person signal", body)
        self.assertIn("Matt 14:00 (30m)", body)

    def test_freshness_and_blended_indicator(self) -> None:
        body = _whatsnext_body(_data([_action()]))
        self.assertIn("last computed", body)
        self.assertIn("team-blended", body)
        self.assertIn("gemini-3.5-flash", body)
        self.assertIn("/whats-next?refresh=1", body)  # refresh control

    def test_operator_only_indicator(self) -> None:
        body = _whatsnext_body(_data([_action()], blended=False, model_used=""))
        self.assertIn("operator-only", body)
        self.assertIn("deterministic order", body)

    def test_automation_tag_renders_only_when_flagged(self) -> None:
        on = _whatsnext_body(_data([_action(automation=True, title="Fix the deploy")]))
        self.assertIn("automation", on)
        off = _whatsnext_body(_data([_action(automation=False, title="Sync with Matt")]))
        self.assertNotIn("automation", off)

    def test_hostile_person_and_title_are_escaped(self) -> None:
        # Person labels are local-display-only but still untrusted: a hostile
        # teammate label / title / evidence must not inject markup.
        ranked = [
            _action(
                rank=1,
                person="<script>alert(1)</script>",
                title="<img src=x onerror=boom>",
                project="<b>proj</b>",
                evidence=["<script>ev</script>"],
                why="<i>why</i>",
            ),
        ]
        body = _whatsnext_body(_data(ranked))
        self.assertNotIn("<script>alert(1)</script>", body)
        self.assertNotIn("<img src=x onerror=boom>", body)
        self.assertNotIn("<script>ev</script>", body)
        self.assertNotIn("<i>why</i>", body)
        self.assertIn("&lt;script&gt;", body)
        self.assertIn("&lt;img", body)

    def test_missing_optional_fields_render_safely(self) -> None:
        # No project, no evidence, empty why must not raise or leak None.
        body = _whatsnext_body(_data([
            _action(project=None, evidence=[], why=""),
        ]))
        self.assertIn("wn-item", body)
        self.assertNotIn("None", body)


class WhatsNextRoutePersistsTests(unittest.TestCase):
    """FIX 4 (C3): when the route computes LIVE (no precompute), it ALWAYS persists
    the result — even a degraded one — so subsequent normal loads read the cache
    instead of recomputing live Gemini on every hit."""

    def test_live_compute_persists_even_when_no_precompute(self) -> None:
        from rebalance.ingest.next_actions import RankedNextActions

        live = RankedNextActions(note="freshly computed", blended=False)
        with patch(
            "rebalance.paths.resolve_database_path", return_value=Path("/tmp/x.db")
        ), patch(
            "rebalance.ingest.next_actions.get_ranked_meta",
            return_value={"row_count": 0},  # no precompute yet
        ), patch(
            "rebalance.ingest.next_actions.rank_next_actions", return_value=live
        ) as mock_rank, patch(
            "rebalance.ingest.next_actions.persist_ranked_next_actions"
        ) as mock_persist, patch(
            "rebalance.ingest.next_actions.load_ranked_next_actions", return_value=live
        ):
            # refresh=False (a NORMAL first hit with an empty cache).
            whatsnext_page(refresh=False)

        mock_rank.assert_called_once()
        # The live result was persisted so the next normal load hits the cache.
        mock_persist.assert_called_once()
        persisted = mock_persist.call_args.args[1]
        self.assertIs(persisted, live)

    def test_persist_failure_is_swallowed_not_500(self) -> None:
        from rebalance.ingest.next_actions import RankedNextActions

        live = RankedNextActions(note="x")
        with patch(
            "rebalance.paths.resolve_database_path", return_value=Path("/tmp/x.db")
        ), patch(
            "rebalance.ingest.next_actions.get_ranked_meta",
            return_value={"row_count": 0},
        ), patch(
            "rebalance.ingest.next_actions.rank_next_actions", return_value=live
        ), patch(
            "rebalance.ingest.next_actions.persist_ranked_next_actions",
            side_effect=RuntimeError("disk full"),
        ), patch(
            "rebalance.ingest.next_actions.load_ranked_next_actions", return_value=None
        ):
            # Must not raise — the swallowed-compute path degrades cleanly.
            resp = whatsnext_page(refresh=False)
        self.assertIsNotNone(resp)


if __name__ == "__main__":
    unittest.main()

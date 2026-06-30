"""GH-94: priority_tier wired into 'what to do next' as a soft down-weight.

Covers the prompt tag + calibration lever (synthesis path) and the deterministic
fallback demotion (the stable sort), both keyed off the one shared predicate.
"""

from __future__ import annotations

import unittest

from rebalance.ingest.next_actions import (
    RankedAction,
    _DEPRIORITIZE_TIER,
    _is_low_priority,
    build_rank_prompt,
    load_signal_weights,
)


def _action(title: str, project: str | None) -> RankedAction:
    return RankedAction(
        rank=0, title=title, person="operator", source="github",
        project=project, evidence=[], why="",
    )


class PriorityDownweightTests(unittest.TestCase):
    def test_is_low_priority_threshold(self) -> None:
        pri = {"a/low": 5, "a/edge": _DEPRIORITIZE_TIER, "a/high": 1}
        self.assertTrue(_is_low_priority("a/low", pri))
        self.assertTrue(_is_low_priority("a/edge", pri))   # >= threshold
        self.assertFalse(_is_low_priority("a/high", pri))
        self.assertFalse(_is_low_priority("a/unknown", pri))  # absent -> not low
        self.assertFalse(_is_low_priority(None, pri))

    def test_prompt_tags_low_priority_only(self) -> None:
        cands = [_action("ship feature", "a/high"), _action("weekly sync", "a/low")]
        prompt = build_rank_prompt(
            operator_candidates=cands,
            teammate_delta=[],
            weights=load_signal_weights(),
            temporal_context=None,
            blended=False,
            priority_by_project={"a/high": 1, "a/low": 5},
        )
        # The low-priority line carries the tag; the high-priority line does not.
        self.assertIn("[priority:low] weekly sync", prompt)
        self.assertNotIn("[priority:low] ship feature", prompt)
        self.assertIn("PRIORITY DOWN-WEIGHT", prompt)

    def test_prompt_no_priority_metadata_is_inert(self) -> None:
        prompt = build_rank_prompt(
            operator_candidates=[_action("ship feature", "a/high")],
            teammate_delta=[],
            weights=load_signal_weights(),
            temporal_context=None,
            blended=False,
            priority_by_project=None,
        )
        self.assertNotIn("[priority:low]", prompt)
        self.assertNotIn("PRIORITY DOWN-WEIGHT", prompt)

    def test_fallback_demotion_sinks_low_priority_stably(self) -> None:
        # Same stable-sort key rank_next_actions applies to operator_actions.
        pri = {"a/low": 5}
        actions = [
            _action("high-1", "a/high"),
            _action("low-1", "a/low"),
            _action("high-2", "b/other"),
        ]
        actions.sort(key=lambda a: 1 if _is_low_priority(a.project, pri) else 0)
        titles = [a.title for a in actions]
        # Low sinks to the bottom; the two non-low keep their original order.
        self.assertEqual(titles, ["high-1", "high-2", "low-1"])


if __name__ == "__main__":
    unittest.main()

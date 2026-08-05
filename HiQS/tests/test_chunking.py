"""Tests for the shared chunk cap (§6.3).

The cap exists because the truncation gate it serves had never been executed. These tests
cover the splitter's own behaviour; the gate over the real corpus lives in
``judge_pairwise.truncation_gate`` and runs before any scoring.
"""

from __future__ import annotations

import pytest

from hiqs.chunking import MAX_CHUNK_CHARS, split_oversized


def test_a_body_within_the_cap_is_returned_untouched():
    body = "A short note.\n\nWith two paragraphs."
    # The common case is p50 511 characters, well under the cap. Capping must not perturb it,
    # or every existing chunk id churns for nothing.
    assert split_oversized(body) == [body]


def test_every_part_of_a_split_body_respects_the_cap():
    body = "\n\n".join(f"Paragraph {n} " + "word " * 40 for n in range(20))
    parts = split_oversized(body, cap=600)
    assert len(parts) > 1
    assert all(len(part) <= 600 for part in parts)


def test_splitting_prefers_paragraph_boundaries_over_cutting_mid_sentence():
    body = "\n\n".join(["alpha " * 50, "bravo " * 50, "charlie " * 50])
    parts = split_oversized(body, cap=400)
    # Each part should be whole paragraphs, so no part mixes a fragment of two topics.
    for part in parts:
        assert part.startswith(("alpha", "bravo", "charlie"))


def test_a_single_line_longer_than_the_cap_is_still_bounded():
    """A minified blob or table row has no structural boundary left — it must still be cut."""
    body = "x" * 5000
    parts = split_oversized(body, cap=600)
    assert all(len(part) <= 600 for part in parts)
    assert "".join(parts) == body  # nothing is dropped


def test_no_content_is_lost_across_a_split():
    body = "\n\n".join(f"line {n} with some real words in it" for n in range(200))
    parts = split_oversized(body, cap=600)
    rejoined = "".join(part.replace("\n", "").replace(" ", "") for part in parts)
    assert rejoined == body.replace("\n", "").replace(" ", "")


def test_an_oversized_whitespace_body_still_yields_a_document():
    """Dropping a document silently is the failure mode this project exists to kill (§8)."""
    parts = split_oversized(" " * 5000, cap=600)
    assert parts and all(len(part) <= 600 for part in parts)


def test_a_nonsensical_cap_is_rejected_rather_than_producing_empty_chunks():
    with pytest.raises(ValueError, match="at least 1"):
        split_oversized("anything at all that exceeds it", cap=0)


def test_the_shipped_cap_is_the_calibrated_value():
    """600 was measured, not guessed: it is the largest cap clearing the 95% gate.

    Pinned so a later "let's allow bigger chunks" edit has to confront the gate rather than
    quietly dropping the corpus back under it.
    """
    assert MAX_CHUNK_CHARS == 600

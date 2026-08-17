"""Tests for the blind pairwise judging path (§6.3, amended)."""

from __future__ import annotations

import json

import pytest

from hiqs.db import db_connection
from judge_pairwise import (
    blind_order,
    disagreements,
    load_queries,
    truncation_gate,
    vector_leg_ready,
    win_rate,
)


class _Tokenizer:
    def encode(self, text, add_special_tokens=True):
        return text.split()


class _Embedder:
    tokenizer = _Tokenizer()
    max_seq_length = 5


def _corpus(tmp_path, bodies):
    connection = db_connection(tmp_path / "hiqs.db")
    for index, body in enumerate(bodies):
        connection.execute(
            "INSERT INTO docs (source, id, title, body, url, ts, project, author) "
            "VALUES ('vault', ?, '', ?, '', '', '', '')",
            (f"d{index}", body),
        )
    connection.commit()
    return connection


def _write(tmp_path, committed, sidecar):
    c = tmp_path / "eval_queries.json"
    s = tmp_path / "sidecar.json"
    c.write_text(json.dumps(committed), encoding="utf-8")
    s.write_text(json.dumps(sidecar), encoding="utf-8")
    return c, s


def test_time_window_probes_are_excluded_from_scoring(tmp_path):
    c, s = _write(
        tmp_path,
        [
            {"id": "q-1", "shape": "jargon", "scoreable": True},
            {"id": "q-2", "shape": "time-window", "scoreable": False},
        ],
        {"q-1": {"query": "where is the registry"}, "q-2": {"query": "what did I do yesterday"}},
    )
    assert [q["id"] for q in load_queries(c, s)] == ["q-1"]


def test_a_missing_sidecar_entry_fails_loudly_rather_than_scoring_a_subset(tmp_path):
    c, s = _write(
        tmp_path,
        [{"id": "q-1", "shape": "jargon", "scoreable": True}],
        {},
    )
    with pytest.raises(ValueError, match="unknown query text"):
        load_queries(c, s)


def test_an_unfinished_sheet_does_not_count_blanks_as_ties():
    """Counting blanks as ties would push `judged` past the threshold and invent a result."""
    from judge_pairwise import parse_sheet

    sheet = "## q-1\n\n`VERDICT: A`\n\n## q-2\n\n`VERDICT:`\n\n## q-3\n\n`VERDICT: tie`\n"
    assert parse_sheet(sheet) == {"q-1": "a", "q-3": "tie"}


def test_an_unreadable_verdict_is_refused_rather_than_guessed():
    from judge_pairwise import parse_sheet

    with pytest.raises(ValueError, match="unreadable verdict"):
        parse_sheet("## q-1\n\n`VERDICT: maybe the second one`\n")


def test_tally_unblinds_slots_back_to_the_models():
    from judge_pairwise import MINILM, QWEN, blind_order, tally

    # Whichever model sits in slot A for this query is the one an "a" verdict credits.
    first, _second = blind_order("q-1", MINILM, QWEN)
    result = tally({"q-1": "a"})
    assert result[first] == 1


def test_the_eval_excludes_units_that_merely_echo_the_query(monkeypatch):
    """20 of 22 queries returned the operator's own prompt log at rank 1, for both models."""
    from hiqs.plugins import Doc
    import judge_pairwise

    hits = [
        Doc(source="vault", id=f"d{n}", title="t", body="b", unit=unit)
        for n, unit in enumerate(["0. Claude Prompts.md"] * 3 + ["real-work.md"] * 5)
    ]
    monkeypatch.setattr(judge_pairwise, "search", lambda *a, **k: hits)

    sets = judge_pairwise.result_sets(None, [{"id": "q-1", "query": "anything"}], "m")

    # The echo chunks are gone and the set is still full length, not silently truncated.
    assert sets["q-1"] == ["d3", "d4", "d5", "d6", "d7"]


def test_the_exclusion_can_be_turned_off_for_a_real_use_ranking(monkeypatch):
    from hiqs.plugins import Doc
    import judge_pairwise

    hits = [Doc(source="vault", id="d0", title="t", body="b", unit="0. Claude Prompts.md")]
    monkeypatch.setattr(judge_pairwise, "search", lambda *a, **k: hits)

    sets = judge_pairwise.result_sets(
        None, [{"id": "q-1", "query": "x"}], "m", excluded_units=frozenset()
    )
    assert sets["q-1"] == ["d0"]


def test_disagreements_are_full_set_comparisons_not_top_hit_only():
    a = {"q-1": ["d1", "d2"], "q-2": ["d3", "d4"], "q-3": ["d5"]}
    b = {"q-1": ["d1", "d2"], "q-2": ["d3", "d9"], "q-3": ["d6"]}
    # q-2 shares a top hit but differs below it — a real disagreement the top-hit-only
    # comparison in eval_retrieval.py would miss.
    assert disagreements(a, b) == ["q-2", "q-3"]


def test_blind_order_is_deterministic_and_not_always_the_same_slot():
    ids = [f"q-{n}" for n in range(20)]
    orders = [blind_order(i, "mini", "qwen") for i in ids]
    assert orders == [blind_order(i, "mini", "qwen") for i in ids]  # stable across runs
    assert len({o[0] for o in orders}) == 2  # both models take slot A somewhere


def test_an_indecisive_result_reports_unknown_rather_than_the_leader():
    result = win_rate({"q-1": "mini", "q-2": "qwen", "q-3": "mini"}, "mini", "qwen")
    assert result["winner"] == "unknown"
    assert result["decisive"] is False
    assert "cannot separate" in result["note"]


def test_a_clear_margin_names_a_winner():
    judgments = {f"q-{n}": "qwen" for n in range(7)}
    judgments.update({f"q-{n}": "mini" for n in range(7, 10)})
    result = win_rate(judgments, "mini", "qwen")
    assert result["winner"] == "qwen"
    assert result["decisive"] is True


def test_a_model_with_no_vectors_is_not_ready_to_be_compared(tmp_path):
    """Without this, search() degrades both models to FTS and reports them indistinguishable."""
    connection = _corpus(tmp_path, ["a b c"] * 3)
    try:
        result = vector_leg_ready(connection, "Qwen/Qwen3-Embedding-0.6B")
        assert result["ready"] is False
        assert result["coverage"] == 0.0
    finally:
        connection.close()


def test_partial_vector_coverage_is_not_ready_either(tmp_path):
    connection = _corpus(tmp_path, ["a b c"] * 3)
    try:
        connection.execute(
            "INSERT INTO docs_vec (doc_id, model, dim, vec) VALUES ('d0', 'm', 1, X'00')"
        )
        connection.commit()
        result = vector_leg_ready(connection, "m")
        assert result["ready"] is False
        assert result["vectors"] == 1 and result["docs"] == 3
    finally:
        connection.close()


def test_the_truncation_gate_fails_a_corpus_the_model_cannot_read(tmp_path):
    connection = _corpus(tmp_path, ["a b c"] * 5 + ["w " * 40] * 5)
    try:
        result = truncation_gate(connection, _Embedder())
        assert result["passed"] is False
        assert result["rate"] == 0.5
    finally:
        connection.close()


def test_the_truncation_gate_passes_a_corpus_within_the_window(tmp_path):
    connection = _corpus(tmp_path, ["a b c"] * 20)
    try:
        assert truncation_gate(connection, _Embedder())["passed"] is True
    finally:
        connection.close()


def test_an_unmeasurable_gate_is_an_error_not_a_pass(tmp_path):
    """A gate that cannot run must never report the same thing as a gate that passed."""
    connection = _corpus(tmp_path, ["a b c"])
    try:
        with pytest.raises(TypeError, match="truncation gate"):
            truncation_gate(connection, object())
    finally:
        connection.close()


def test_an_empty_corpus_does_not_vacuously_pass_the_gate(tmp_path):
    connection = _corpus(tmp_path, [])
    try:
        with pytest.raises(ValueError, match="empty corpus"):
            truncation_gate(connection, _Embedder())
    finally:
        connection.close()


def test_ties_count_toward_volume_but_never_toward_a_win():
    judgments = {f"q-{n}": "tie" for n in range(10)}
    result = win_rate(judgments, "mini", "qwen")
    assert result["ties"] == 10
    assert result["winner"] == "unknown"

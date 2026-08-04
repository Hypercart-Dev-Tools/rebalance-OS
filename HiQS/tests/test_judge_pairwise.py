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

"""Blind pairwise judging — the Checkpoint A decision path (§6.3, amended 2026-08-03).

Why this exists separately from ``eval_retrieval.py``: that runner scores against a
pre-authored answer key. The operator's objection retired it — *"if I knew the answers I
wouldn't be building the system"* — and the objection is right, because a hand-written key is
only tractable for questions you can already answer, which selects exactly the queries that do
not need the system.

Checkpoint A decides *which of two models is better*. That is a relative question, so it does
not need an absolute metric. This module runs both models over the same frozen queries, shows
the operator the ones where they disagree **with the models unlabelled**, and decides on
pairwise preference. Recognising a better answer from two side by side is a categorically
easier task than recalling one from memory, and it is the only one honestly available here.

Kept deliberately small and separate: ``eval_retrieval.py`` is already 3x its budgeted size and
this is a different question, not more of the same one.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hiqs.db import db_connection  # noqa: E402
from hiqs.search import search  # noqa: E402

TOP_N = 5
TRUNCATION_GATE_MINIMUM = 0.95


def truncation_gate(connection, embedder: Any) -> dict[str, Any]:
    """Refuse to score a corpus the shipped model cannot actually read (§6.3).

    §6.3 requires that ≥95% of chunks fit the shipped model's context, and this check existed
    only as a sentence in the plan until the corpus was measured at 64.0%. Below the gate the
    comparison is not merely weak, it is invalid: MiniLM truncates at 256 word-pieces while
    Qwen3-Embedding-0.6B truncates at 32768, so the two models are not being shown the same
    input and any winner is an artefact of who got to read more.

    Returns the measurement rather than raising, so the caller reports a number; ``passed`` is
    the thing to branch on and it is deliberately not a soft warning.
    """
    tokenizer = getattr(embedder, "tokenizer", None)
    limit = getattr(embedder, "max_seq_length", None)
    if tokenizer is None or not limit:
        raise TypeError(
            f"Cannot run the truncation gate against {type(embedder).__name__}: no tokenizer "
            "or max_seq_length. An unmeasurable gate must not be reported as a passing one."
        )

    rows = connection.execute("SELECT title, body FROM docs").fetchall()
    if not rows:
        raise ValueError("Refusing to gate an empty corpus: nothing has been indexed.")

    lengths = sorted(
        len(tokenizer.encode(f"{title}\n{body}" if title else body, add_special_tokens=True))
        for title, body in rows
    )
    fitting = sum(1 for length in lengths if length <= limit)
    rate = fitting / len(lengths)
    return {
        "chunks": len(lengths),
        "fitting": fitting,
        "rate": rate,
        "limit": limit,
        "max_tokens": lengths[-1],
        "passed": rate >= TRUNCATION_GATE_MINIMUM,
    }


def load_queries(committed: str | Path, sidecar: str | Path) -> list[dict[str, Any]]:
    """Return scoreable queries with their text, joined across the §19.2 public/private split."""
    committed_rows = json.loads(Path(committed).read_text(encoding="utf-8"))
    sidecar_rows = json.loads(Path(sidecar).read_text(encoding="utf-8"))

    queries = []
    for row in committed_rows:
        if not row.get("scoreable", True):
            continue  # time-window probes: no retrieval model can answer them (§6.4 Q1)
        entry = sidecar_rows.get(row["id"])
        if entry is None:
            raise ValueError(
                f"unknown query text for {row['id']}: sidecar missing. "
                "Refusing to score a subset silently (§19.2)."
            )
        text = entry["query"] if isinstance(entry, dict) else entry
        queries.append({**row, "query": text})
    return queries


def result_sets(
    connection,
    queries: list[dict[str, Any]],
    model: str,
    embedder: Any | None = None,
) -> dict[str, list[str]]:
    """Top-N document ids per query for one model."""
    return {
        q["id"]: [
            doc.id
            for doc in search(
                q["query"],
                limit=TOP_N,
                connection=connection,
                model_name=model,
                embedder=embedder,
            )
        ]
        for q in queries
    }


def disagreements(a: dict[str, list[str]], b: dict[str, list[str]]) -> list[str]:
    """Query ids where the two models' ranked sets differ at all."""
    return sorted(q for q in a if a.get(q) != b.get(q))


def blind_order(query_id: str, model_a: str, model_b: str) -> tuple[str, str]:
    """Assign models to slots A/B deterministically but unpredictably.

    Deterministic so a re-run shows the same layout and a judgment stays meaningful;
    keyed on the query id so the operator cannot learn "left is always the challenger"
    and start voting for a model instead of for an answer.
    """
    digest = hashlib.sha256(query_id.encode("utf-8")).digest()[0]
    return (model_a, model_b) if digest % 2 == 0 else (model_b, model_a)


def win_rate(judgments: dict[str, str], model_a: str, model_b: str) -> dict[str, Any]:
    """Tally blind judgments into a decision. Ties are not wins (§6.3: ties go to the incumbent)."""
    a_wins = sum(1 for v in judgments.values() if v == model_a)
    b_wins = sum(1 for v in judgments.values() if v == model_b)
    ties = sum(1 for v in judgments.values() if v == "tie")
    judged = a_wins + b_wins + ties

    # Below this, the disagreement set cannot separate two models and saying so is the
    # honest result — not picking whichever is nominally ahead (§8: unknown is a real state).
    decisive = judged >= 8 and abs(a_wins - b_wins) >= 3
    return {
        "judged": judged,
        model_a: a_wins,
        model_b: b_wins,
        "ties": ties,
        "winner": (model_a if a_wins > b_wins else model_b) if decisive else "unknown",
        "decisive": decisive,
        "note": "" if decisive else (
            f"{judged} judgments with a margin of {abs(a_wins - b_wins)} cannot separate these "
            "models. Report unknown and widen the query set rather than picking the leader."
        ),
    }

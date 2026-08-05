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


def vector_leg_ready(connection, model: str) -> dict[str, Any]:
    """Confirm a model's vectors actually cover the corpus before comparing it to anything.

    ``search()`` catches any failure in the vector leg and degrades to FTS-only with a warn
    event (§6.2). That is right for a user query and fatal for this comparison: with no Qwen3
    vectors both models fall back to the same BM25 ranking, produce zero disagreements, and
    the run reports "the models are indistinguishable" when what actually happened is that
    neither model was consulted. Checkpoint A would have been decided by FTS against itself.
    """
    total = connection.execute("SELECT count(*) FROM docs").fetchone()[0]
    vectors = connection.execute(
        "SELECT count(*) FROM docs_vec WHERE model = ?", (model,)
    ).fetchone()[0]
    return {
        "model": model,
        "docs": total,
        "vectors": vectors,
        "coverage": (vectors / total) if total else 0.0,
        "ready": bool(total) and vectors == total,
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


# Eval-only exclusion. `0. Claude Prompts.md` is a verbatim log of the operator's own prompts
# and is 1,572 of 6,053 corpus chunks (26%). The eval queries were mined from it, so the query
# text appears in the corpus verbatim and 20 of 22 queries returned a prompt-log chunk at rank
# 1 — for BOTH models. Scoring that measures whether a model can find a copy of the question,
# which is not retrieval quality; it is the §6.5 corpus/question mismatch made concrete.
#
# The filter is deliberately eval-only: the note stays indexed, so real-use behaviour is
# unchanged and the corpus-composition question stays open. Both models are filtered
# identically, so neither is advantaged. Widen the retrieval before filtering, or the
# exclusion silently returns short result sets and shrinks what is being compared.
EVAL_EXCLUDED_UNITS = frozenset({"0. Claude Prompts.md"})
_OVERFETCH = 6


def result_sets(
    connection,
    queries: list[dict[str, Any]],
    model: str,
    embedder: Any | None = None,
    excluded_units: frozenset[str] = EVAL_EXCLUDED_UNITS,
) -> dict[str, list[str]]:
    """Top-N document ids per query for one model, minus units the eval cannot learn from."""
    sets: dict[str, list[str]] = {}
    for q in queries:
        hits = search(
            q["query"],
            limit=TOP_N * _OVERFETCH if excluded_units else TOP_N,
            connection=connection,
            model_name=model,
            embedder=embedder,
        )
        kept = [doc.id for doc in hits if doc.unit not in excluded_units]
        sets[q["id"]] = kept[:TOP_N]
    return sets


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


MINILM = "all-MiniLM-L6-v2"
QWEN = "Qwen/Qwen3-Embedding-0.6B"


def _render(connection, query_id: str, ids: list[str]) -> str:
    """Render one model's ranked set as titles the operator can actually judge."""
    lines = []
    for rank, doc_id in enumerate(ids, 1):
        row = connection.execute(
            "SELECT source, title, substr(body, 1, 220) FROM docs WHERE id = ?", (doc_id,)
        ).fetchone()
        if row is None:
            lines.append(f"{rank}. [MISSING ROW {doc_id}]")
            continue
        source, title, snippet = row
        snippet = " ".join(snippet.split())
        lines.append(f"{rank}. **[{source}] {title or '(untitled)'}**\n   {snippet}…")
    return "\n".join(lines) or "_(no results)_"


def parse_sheet(text: str) -> dict[str, str]:
    """Read `VERDICT: A|B|tie` lines back off the judged sheet, keyed by query id.

    Unjudged verdicts are skipped rather than defaulted. A blank line is "not judged", never a
    tie: silently counting blanks as ties would inflate `judged` past the decisiveness
    threshold and manufacture a result out of an unfinished sheet.
    """
    verdicts: dict[str, str] = {}
    query_id = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            query_id = stripped[3:].strip()
        elif stripped.startswith("`VERDICT:") or stripped.startswith("VERDICT:"):
            raw = stripped.split("VERDICT:", 1)[1].strip().strip("`").strip().lower()
            if not raw or query_id is None:
                continue
            if raw not in {"a", "b", "tie"}:
                raise ValueError(
                    f"{query_id}: unreadable verdict {raw!r}. Expected A, B, or tie — "
                    "refusing to guess what was meant."
                )
            verdicts[query_id] = raw
    return verdicts


def tally(verdicts: dict[str, str], model_a: str = MINILM, model_b: str = QWEN) -> dict[str, Any]:
    """Un-blind slot verdicts into model judgments and decide (§6.3)."""
    judgments: dict[str, str] = {}
    for query_id, slot in verdicts.items():
        if slot == "tie":
            judgments[query_id] = "tie"
            continue
        first, second = blind_order(query_id, model_a, model_b)
        judgments[query_id] = first if slot == "a" else second
    return win_rate(judgments, model_a, model_b)


def main() -> int:
    """Emit the blind A/B sheet for Checkpoint A, refusing to run on an invalid comparison."""
    from sentence_transformers import SentenceTransformer

    here = Path(__file__).resolve().parent

    if "--tally" in sys.argv:
        sheet = here / "checkpoint_a_pairs.md"
        verdicts = parse_sheet(sheet.read_text(encoding="utf-8"))
        result = tally(verdicts)
        print(f"judged {result['judged']} of 22")
        print(f"  {MINILM:32} {result[MINILM]}")
        print(f"  {QWEN:32} {result[QWEN]}")
        print(f"  ties{'':29} {result['ties']}")
        print(f"\nwinner: {result['winner']}   decisive: {result['decisive']}")
        if result["note"]:
            print(result["note"])
        return 0

    connection = db_connection()
    try:
        shipped = SentenceTransformer(f"sentence-transformers/{MINILM}", local_files_only=True)
        gate = truncation_gate(connection, shipped)
        print(
            f"§6.3 truncation gate: {gate['fitting']}/{gate['chunks']} = {gate['rate']:.1%} "
            f"(max {gate['max_tokens']} of {gate['limit']} word-pieces) — "
            f"{'PASS' if gate['passed'] else 'FAIL'}"
        )
        if not gate["passed"]:
            print("Refusing to score: the models are not being shown the same input.")
            return 1

        for model in (MINILM, QWEN):
            leg = vector_leg_ready(connection, model)
            print(f"vector leg {model:32} {leg['vectors']}/{leg['docs']} = {leg['coverage']:.1%}")
            if not leg["ready"]:
                # search() would silently fall back to FTS for this model and the run would
                # report the two as indistinguishable. That is a lie, not a result.
                print(f"Refusing to score: {model} has no usable vector leg.")
                return 1

        queries = load_queries(here / "eval_queries.json", here / "eval_queries_sidecar.json")
        embedders = {
            MINILM: shipped,
            QWEN: SentenceTransformer(QWEN, local_files_only=True),
        }
        sets = {
            model: result_sets(connection, queries, model, embedder=embedders[model])
            for model in (MINILM, QWEN)
        }
        differing = disagreements(sets[MINILM], sets[QWEN])
        print(f"\nqueries scored: {len(queries)}   disagreements: {len(differing)}")

        text = {q["id"]: q["query"] for q in queries}
        out = [
            "# Checkpoint A — blind pairwise judging",
            "",
            f"{len(differing)} of {len(queries)} queries where the two models disagree. The models",
            "are unlabelled and their slots are shuffled per query. For each, write **A**, **B**,",
            "or **tie** on the verdict line. Judge the results, not the layout.",
            "",
        ]
        for query_id in differing:
            first, second = blind_order(query_id, MINILM, QWEN)
            out += [
                "---",
                "",
                f"## {query_id}",
                "",
                f"> {text[query_id]}",
                "",
                "**A**",
                "",
                _render(connection, query_id, sets[first][query_id]),
                "",
                "**B**",
                "",
                _render(connection, query_id, sets[second][query_id]),
                "",
                "`VERDICT:`",
                "",
            ]
        # Gitignored: these sheets carry real query text and vault titles (§19.2).
        sheet = here / "checkpoint_a_pairs.md"
        sheet.write_text("\n".join(out), encoding="utf-8")
        print(f"wrote {sheet}")
        return 0
    finally:
        connection.close()


if __name__ == "__main__":  # pragma: no cover - operator entry point
    raise SystemExit(main())

"""Offline retrieval evaluation runner for HiQS (§6.3, §19.2).

Reports recall@10 and MRR@10 per leg (FTS-only, vector-only, fused) per model.
Emits paired disagreement set, captures costs (embed_ms, index_mb, peak_rss_mb),
and logs 'eval.completed' events to the observability spine.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import sqlite3
import sys
import time
from typing import Any
from unittest.mock import patch

from hiqs.db import db_connection
from hiqs.docs_index import get_embed_text
from hiqs.plugins import Doc
from hiqs.search import _fts_search, _vec_search, cap_per_document, rrf_fuse


def _utc_now() -> str:
    """Return an ISO-8601 UTC timestamp with a stable 'Z' suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def get_peak_rss_mb() -> float:
    """Return peak RSS memory usage in MB."""
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return usage / (1024.0 * 1024.0)
    return usage / 1024.0


def get_git_sha(git_sha_override: str | None = None) -> str:
    """Retrieve git SHA from parameter, GIT_SHA env var, or default to 'unknown' without subprocess calls."""
    if git_sha_override and git_sha_override.strip():
        return git_sha_override.strip()
    env_sha = os.environ.get("GIT_SHA")
    if env_sha and env_sha.strip():
        return env_sha.strip()
    return "unknown"


def compute_queryset_sha(committed_path: str | Path, sidecar_path: str | Path) -> str:
    """Compute SHA256 spanning both the committed query set and local sidecar files (§19.2)."""
    c_path = Path(committed_path)
    s_path = Path(sidecar_path)

    if not c_path.exists():
        raise FileNotFoundError(
            f"Missing query set file '{committed_path}' per §6.3 protocol."
        )
    if not s_path.exists():
        raise FileNotFoundError(
            f"Sidecar missing: unknown query set sidecar at '{sidecar_path}' (§19.2)."
        )

    c_bytes = c_path.read_bytes()
    s_bytes = s_path.read_bytes()
    return hashlib.sha256(c_bytes + s_bytes).hexdigest()


def load_query_set(
    committed_path: str | Path, sidecar_path: str | Path
) -> tuple[list[dict[str, Any]], str]:
    """Load queries from committed JSON and local sidecar, validating §6.3/§19.2 split."""
    queryset_sha = compute_queryset_sha(committed_path, sidecar_path)

    with open(committed_path, "r", encoding="utf-8") as f:
        committed_data = json.load(f)

    with open(sidecar_path, "r", encoding="utf-8") as f:
        sidecar_data = json.load(f)

    sidecar_map: dict[str, Any] = {}
    if isinstance(sidecar_data, dict):
        sidecar_map = sidecar_data
    elif isinstance(sidecar_data, list):
        for item in sidecar_data:
            if isinstance(item, dict) and "id" in item:
                sidecar_map[item["id"]] = item

    queries: list[dict[str, Any]] = []
    for item in committed_data:
        q_id = item.get("id")
        if not q_id or q_id not in sidecar_map:
            raise ValueError(
                f"Sidecar missing text for query id '{q_id}': unknown query text (§19.2)."
            )

        sc_entry = sidecar_map[q_id]
        if isinstance(sc_entry, str):
            text = sc_entry
        elif isinstance(sc_entry, dict):
            text = sc_entry.get("query", sc_entry.get("text", ""))
        else:
            text = ""

        if not text.strip():
            raise ValueError(
                f"Empty text for query id '{q_id}': unknown query text (§19.2)."
            )

        # Canonical §19.2 fields: doc_id and shape
        raw_doc_ids = item.get(
            "doc_id",
            item.get(
                "target_doc_ids", item.get("doc_ids", item.get("target_doc_id", []))
            ),
        )
        if isinstance(raw_doc_ids, str):
            target_doc_ids = [raw_doc_ids] if raw_doc_ids.strip() else []
        elif isinstance(raw_doc_ids, list):
            target_doc_ids = [str(d) for d in raw_doc_ids if str(d).strip()]
        else:
            target_doc_ids = []

        if not target_doc_ids:
            raise ValueError(
                f"Query item '{q_id}' missing canonical target doc_id (§19.2)."
            )

        raw_shape = item.get(
            "shape", item.get("shape_tags", item.get("tags", []))
        )
        if isinstance(raw_shape, str):
            shape_tags = [raw_shape] if raw_shape.strip() else []
        elif isinstance(raw_shape, list):
            shape_tags = [str(s) for s in raw_shape if str(s).strip()]
        else:
            shape_tags = []

        if not shape_tags:
            raise ValueError(
                f"Query item '{q_id}' missing canonical shape tag (§19.2)."
            )

        queries.append(
            {
                "id": q_id,
                "query": text,
                "target_doc_ids": target_doc_ids,
                "shape_tags": shape_tags,
            }
        )

    return queries, queryset_sha


def score_single_query(
    target_doc_ids: list[str], hits: list[Doc]
) -> tuple[float, float]:
    """Score recall@10 and MRR@10 for a single query."""
    top10 = hits[:10]
    matched_ranks: list[int] = []
    found_targets: set[str] = set()

    for rank, doc in enumerate(top10, start=1):
        doc_keys = {doc.id}
        if doc.unit:
            doc_keys.add(doc.unit)

        for target in target_doc_ids:
            if target in doc_keys or target == doc.id:
                found_targets.add(target)
                matched_ranks.append(rank)

    if not target_doc_ids:
        return 0.0, 0.0

    recall = len(found_targets) / len(set(target_doc_ids))
    mrr = (1.0 / matched_ranks[0]) if matched_ranks else 0.0
    return recall, mrr


def get_offline_embedder(model_name: str) -> Any:
    """Load embedder with strict local_files_only=True semantics to prevent network downloads (§6.3)."""
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer(model_name, local_files_only=True)
    except Exception as err:
        raise RuntimeError(
            f"Offline model '{model_name}' is unavailable locally: {err}. No network downloads allowed during evaluation (§6.3)."
        )


def evaluate_retrieval(
    connection: sqlite3.Connection,
    queries: list[dict[str, Any]],
    model_name: str = "all-MiniLM-L6-v2",
    embedder: Any | None = None,
) -> dict[str, Any]:
    """Evaluate retrieval queries across FTS-only, vector-only, and fused legs without side-effects."""
    if embedder is None:
        embedder = get_offline_embedder(model_name)

    fts_recalls, fts_mrrs = [], []
    vec_recalls, vec_mrrs = [], []
    fused_recalls, fused_mrrs = [], []

    fts_top_hits: dict[str, str] = {}
    vec_top_hits: dict[str, str] = {}
    fused_top_hits: dict[str, str] = {}

    for q in queries:
        q_id = q["id"]
        q_text = q["query"]
        targets = q["target_doc_ids"]

        # FTS-only leg
        fts_hits = _fts_search(connection, q_text, limit=10)
        rec, mrr = score_single_query(targets, fts_hits)
        fts_recalls.append(rec)
        fts_mrrs.append(mrr)
        if fts_hits:
            fts_top_hits[q_id] = fts_hits[0].id

        # Vector-only leg (raise loud failure on encoder or missing vector error)
        try:
            vec_hits = _vec_search(connection, q_text, model_name, embedder, limit=10)
        except Exception as err:
            raise RuntimeError(
                f"Vector search failed for model '{model_name}': {err}. Cannot record valid evaluation metrics (§6.3)."
            ) from err

        rec, mrr = score_single_query(targets, vec_hits)
        vec_recalls.append(rec)
        vec_mrrs.append(mrr)
        if vec_hits:
            vec_top_hits[q_id] = vec_hits[0].id

        # Fused leg (executed directly on connection without calling search() to avoid writing search telemetry to default DB)
        fts_hits_50 = _fts_search(connection, q_text, limit=50)
        try:
            vec_hits_50 = _vec_search(connection, q_text, model_name, embedder, limit=50)
        except Exception as err:
            raise RuntimeError(
                f"Vector search failed for model '{model_name}': {err}. Cannot record valid evaluation metrics (§6.3)."
            ) from err

        fused = rrf_fuse(fts_hits_50, vec_hits_50, k=60)
        fused_hits = cap_per_document(fused, max_chunks=2)[:10]

        rec, mrr = score_single_query(targets, fused_hits)
        fused_recalls.append(rec)
        fused_mrrs.append(mrr)
        if fused_hits:
            fused_top_hits[q_id] = fused_hits[0].id

    n = len(queries)
    def mean(arr):
        return sum(arr) / n if n > 0 else 0.0

    return {
        "model": model_name,
        "n_queries": n,
        "fused": {"recall_at_10": mean(fused_recalls), "mrr_at_10": mean(fused_mrrs)},
        "fts_only": {"recall_at_10": mean(fts_recalls), "mrr_at_10": mean(fts_mrrs)},
        "vector_only": {"recall_at_10": mean(vec_recalls), "mrr_at_10": mean(vec_mrrs)},
        "top_hits": {
            "fused": fused_top_hits,
            "fts_only": fts_top_hits,
            "vector_only": vec_top_hits,
        },
    }


def compute_paired_disagreement_set(
    eval_res1_or_list: dict[str, Any] | list[dict[str, Any]],
    eval_res2: dict[str, Any] | None = None,
    leg: str = "fused",
) -> list[dict[str, Any]]:
    """Emit every query where any two models return a different top hit."""
    if isinstance(eval_res1_or_list, list):
        results = eval_res1_or_list
    elif isinstance(eval_res1_or_list, dict):
        if eval_res2 is None:
            return []
        results = [eval_res1_or_list, eval_res2]
    else:
        return []

    disagreements: list[dict[str, Any]] = []
    n = len(results)
    for i in range(n):
        for j in range(i + 1, n):
            r1 = results[i]
            r2 = results[j]
            m1_name = r1.get("model", f"model_{i+1}")
            m2_name = r2.get("model", f"model_{j+1}")
            m1_hits = r1.get("top_hits", {}).get(leg, {})
            m2_hits = r2.get("top_hits", {}).get(leg, {})

            all_qids = sorted(set(m1_hits.keys()) | set(m2_hits.keys()))
            for q_id in all_qids:
                h1 = m1_hits.get(q_id, "None")
                h2 = m2_hits.get(q_id, "None")
                if h1 != h2:
                    disagreements.append(
                        {
                            "query_id": q_id,
                            "model1": m1_name,
                            "model1_top_hit": h1,
                            "model2": m2_name,
                            "model2_top_hit": h2,
                        }
                    )
    return disagreements


def capture_costs(
    connection: sqlite3.Connection,
    model_name: str,
    embedder: Any | None = None,
) -> dict[str, float]:
    """Capture runtime cost metrics per model by timing full corpus re-embedding."""
    if embedder is None:
        embedder = get_offline_embedder(model_name)

    rows = connection.execute("SELECT title, body FROM docs").fetchall()
    texts: list[str] = [get_embed_text(r[0] or "", r[1] or "") for r in rows]

    t0 = time.perf_counter()
    if texts:
        if hasattr(embedder, "encode"):
            embedder.encode(texts)
        elif callable(embedder):
            embedder(texts)
        else:
            raise RuntimeError(
                f"Embedder for model '{model_name}' is invalid or missing encode method (§6.3)."
            )
    t1 = time.perf_counter()
    embed_ms = (t1 - t0) * 1000.0

    index_mb = 0.0
    try:
        page_count_row = connection.execute("PRAGMA page_count").fetchone()
        page_size_row = connection.execute("PRAGMA page_size").fetchone()
        if page_count_row and page_size_row:
            index_mb = (page_count_row[0] * page_size_row[0]) / (1024.0 * 1024.0)
    except Exception:
        index_mb = 0.0

    peak_rss_mb = get_peak_rss_mb()

    return {
        "embed_ms": float(round(embed_ms, 2)),
        "index_mb": float(round(index_mb, 2)),
        "peak_rss_mb": float(round(peak_rss_mb, 2)),
        "n_corpus_items": float(len(texts)),
    }


def evaluate_gates(
    fused_recall_at_10: float,
    fts_recall_at_10: float,
    challenger_scores: dict[str, float] | None = None,
    incumbent_scores: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Evaluate falsifiable quality gates (floor, vector justification, §3.2 selection rule)."""
    floor_passed = fused_recall_at_10 >= 0.60
    vector_justified = (fused_recall_at_10 - fts_recall_at_10) >= 0.10

    winner = "incumbent"
    if challenger_scores and incumbent_scores:
        c_rec = challenger_scores.get("recall_at_10", 0.0)
        c_mrr = challenger_scores.get("mrr_at_10", 0.0)
        i_rec = incumbent_scores.get("recall_at_10", 0.0)
        i_mrr = incumbent_scores.get("mrr_at_10", 0.0)

        rec_diff = c_rec - i_rec
        mrr_diff = c_mrr - i_mrr

        # §3.2 Selection Rule:
        # Precondition: floor_passed must be True.
        # Primary metric: recall@10. Incumbent ships unless challenger leads by >= 0.08.
        # Tiebreak: MRR@10, used only when recall@10 falls inside the ±0.08 band. Challenger takes tiebreak win at >= 0.05 MRR@10.
        # Split decisions go to incumbent: if one metric favours challenger and the other favours incumbent, incumbent ships.
        # Ties go to incumbent.

        if not floor_passed:
            winner = "incumbent"
        elif rec_diff >= 0.08:
            if mrr_diff < 0:
                winner = "incumbent"  # split decision
            else:
                winner = "challenger"
        elif -0.08 < rec_diff < 0.08:
            if rec_diff >= 0 and mrr_diff >= 0.05:
                winner = "challenger"
            else:
                winner = "incumbent"
        else:
            winner = "incumbent"

    return {
        "floor_passed": floor_passed,
        "vector_justified": vector_justified,
        "winner": winner,
    }


def _log_eval_completed(connection: sqlite3.Connection, payload: dict[str, Any]) -> None:
    """Route completion event through hiqs.events.log_event while targeting connection."""
    import hiqs.events

    class _NonClosingConn:
        def __init__(self, conn: sqlite3.Connection):
            self._conn = conn
        def execute(self, *args, **kwargs):
            return self._conn.execute(*args, **kwargs)
        def commit(self):
            return self._conn.commit()
        def close(self):
            pass

    with patch("hiqs.events.db_connection", return_value=_NonClosingConn(connection)):
        hiqs.events.log_event("eval.completed", "search", "ok", payload)


def run_eval_and_log(
    connection: sqlite3.Connection,
    committed_path: str | Path,
    sidecar_path: str | Path,
    model_name: str | list[str] = "all-MiniLM-L6-v2",
    embedder: Any | None = None,
    embedders: dict[str, Any] | None = None,
    git_sha_override: str | None = None,
) -> dict[str, Any]:
    """Run retrieval evaluation and write 'eval.completed' events to SQLite events table."""
    queries, queryset_sha = load_query_set(committed_path, sidecar_path)

    if isinstance(model_name, list):
        models = model_name
    elif isinstance(model_name, str):
        models = [m.strip() for m in model_name.split(",") if m.strip()]
    else:
        models = ["all-MiniLM-L6-v2"]

    eval_results: list[dict[str, Any]] = []
    costs_list: list[dict[str, float]] = []

    for m in models:
        m_embedder = None
        if embedders and m in embedders:
            m_embedder = embedders[m]
        elif embedder is not None and len(models) == 1:
            m_embedder = embedder
        else:
            m_embedder = get_offline_embedder(m)

        res = evaluate_retrieval(
            connection, queries, model_name=m, embedder=m_embedder
        )
        costs = capture_costs(connection, m, embedder=m_embedder)

        eval_results.append(res)
        costs_list.append(costs)

        fused_recall = res["fused"]["recall_at_10"]
        fused_mrr = res["fused"]["mrr_at_10"]
        git_sha = get_git_sha(git_sha_override)

        payload_single = {
            "model": m,
            "recall_at_10": float(round(fused_recall, 4)),
            "mrr_at_10": float(round(fused_mrr, 4)),
            "n_queries": len(queries),
            "queryset_sha": queryset_sha,
            "embed_ms": float(round(costs["embed_ms"], 2)),
            "index_mb": float(round(costs["index_mb"], 2)),
            "peak_rss_mb": float(round(costs["peak_rss_mb"], 2)),
            "git_sha": git_sha,
            "legs": res,
        }

        _log_eval_completed(connection, payload_single)

    disagreements = compute_paired_disagreement_set(eval_results, leg="fused")

    # Selection & Gate evaluation across models
    winning_idx = 0
    if len(eval_results) >= 2:
        for challenger_idx in range(1, len(eval_results)):
            gate_eval = evaluate_gates(
                fused_recall_at_10=eval_results[winning_idx]["fused"]["recall_at_10"],
                fts_recall_at_10=eval_results[winning_idx]["fts_only"]["recall_at_10"],
                challenger_scores=eval_results[challenger_idx]["fused"],
                incumbent_scores=eval_results[winning_idx]["fused"],
            )
            if gate_eval["winner"] == "challenger":
                winning_idx = challenger_idx

    winning_res = eval_results[winning_idx]
    winning_costs = costs_list[winning_idx]

    final_gates = evaluate_gates(
        fused_recall_at_10=winning_res["fused"]["recall_at_10"],
        fts_recall_at_10=winning_res["fts_only"]["recall_at_10"],
        challenger_scores=winning_res["fused"] if winning_idx != 0 else None,
        incumbent_scores=eval_results[0]["fused"] if winning_idx != 0 else None,
    )
    if winning_idx != 0:
        final_gates["winner"] = winning_res["model"]
    else:
        final_gates["winner"] = "incumbent"

    git_sha = get_git_sha(git_sha_override)

    return {
        "model": winning_res["model"],
        "recall_at_10": float(round(winning_res["fused"]["recall_at_10"], 4)),
        "mrr_at_10": float(round(winning_res["fused"]["mrr_at_10"], 4)),
        "n_queries": len(queries),
        "queryset_sha": queryset_sha,
        "embed_ms": float(round(winning_costs["embed_ms"], 2)),
        "index_mb": float(round(winning_costs["index_mb"], 2)),
        "peak_rss_mb": float(round(winning_costs["peak_rss_mb"], 2)),
        "git_sha": git_sha,
        "legs": {
            "fused": winning_res["fused"],
            "fts_only": winning_res["fts_only"],
            "vector_only": winning_res["vector_only"],
        },
        "paired_disagreements": disagreements,
        "gates": final_gates,
        "eval_results": eval_results,
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for running retrieval evaluation."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run HiQS retrieval evaluation (§6.3, §19.2)."
    )
    parser.add_argument(
        "--db", default=None, help="Path to SQLite database file."
    )
    parser.add_argument(
        "--queries",
        default="HiQS/tests/eval_queries.json",
        help="Path to committed query set JSON.",
    )
    parser.add_argument(
        "--sidecar",
        default="HiQS/tests/eval_queries_sidecar.json",
        help="Path to local query set sidecar JSON.",
    )
    parser.add_argument(
        "--model",
        "--models",
        nargs="+",
        default=["all-MiniLM-L6-v2"],
        help="Embedding model name(s) to evaluate.",
    )

    args = parser.parse_args(argv)

    try:
        conn = db_connection(args.db) if args.db else db_connection()
        try:
            payload = run_eval_and_log(
                conn,
                committed_path=args.queries,
                sidecar_path=args.sidecar,
                model_name=args.model,
            )
            print(json.dumps(payload, indent=2))
            return 0
        finally:
            conn.close()
    except FileNotFoundError as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1
    except ValueError as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1
    except Exception as err:
        print(f"UNEXPECTED ERROR: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

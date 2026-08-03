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
import subprocess
import sys
import time
from typing import Any

from hiqs.db import db_connection
from hiqs.docs_index import get_default_embedder
from hiqs.plugins import Doc
from hiqs.search import _fts_search, _vec_search, search


def _utc_now() -> str:
    """Return an ISO-8601 UTC timestamp with a stable 'Z' suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def get_peak_rss_mb() -> float:
    """Return peak RSS memory usage in MB."""
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return usage / (1024.0 * 1024.0)
    return usage / 1024.0


def get_git_sha() -> str:
    """Retrieve current git SHA without mutating git repo."""
    env_sha = os.environ.get("GIT_SHA")
    if env_sha:
        return env_sha
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
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

        target_doc_ids = item.get("target_doc_ids", item.get("doc_ids", []))
        shape_tags = item.get("shape_tags", item.get("tags", []))

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


def evaluate_retrieval(
    connection: sqlite3.Connection,
    queries: list[dict[str, Any]],
    model_name: str = "all-MiniLM-L6-v2",
    embedder: Any | None = None,
) -> dict[str, Any]:
    """Evaluate retrieval queries across FTS-only, vector-only, and fused legs."""
    if embedder is None:
        try:
            embedder = get_default_embedder(model_name)
        except Exception:
            embedder = None

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

        # Vector-only leg
        vec_hits: list[Doc] = []
        if embedder is not None:
            try:
                vec_hits = _vec_search(connection, q_text, model_name, embedder, limit=10)
            except Exception:
                vec_hits = []
        rec, mrr = score_single_query(targets, vec_hits)
        vec_recalls.append(rec)
        vec_mrrs.append(mrr)
        if vec_hits:
            vec_top_hits[q_id] = vec_hits[0].id

        # Fused leg
        fused_hits = search(
            q_text,
            limit=10,
            connection=connection,
            model_name=model_name,
            embedder=embedder,
        )
        rec, mrr = score_single_query(targets, fused_hits)
        fused_recalls.append(rec)
        fused_mrrs.append(mrr)
        if fused_hits:
            fused_top_hits[q_id] = fused_hits[0].id

    n = len(queries)
    mean = lambda arr: sum(arr) / n if n > 0 else 0.0

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
    eval_res1: dict[str, Any],
    eval_res2: dict[str, Any],
    leg: str = "fused",
) -> list[dict[str, Any]]:
    """Emit every query where two models/evaluations return a different top hit."""
    m1_name = eval_res1.get("model", "model1")
    m2_name = eval_res2.get("model", "model2")
    m1_hits = eval_res1.get("top_hits", {}).get(leg, {})
    m2_hits = eval_res2.get("top_hits", {}).get(leg, {})

    all_qids = sorted(set(m1_hits.keys()) | set(m2_hits.keys()))
    disagreements = []

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
    sample_texts: list[str] | None = None,
) -> dict[str, float]:
    """Capture runtime cost metrics per model (embed_ms, index_mb, peak_rss_mb)."""
    texts = sample_texts or ["sample text for cost capture timing"]
    t0 = time.perf_counter()
    if embedder is not None and hasattr(embedder, "encode"):
        embedder.encode(texts)
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

        # Candidate wins ONLY IF floor passes AND recall & MRR are >= incumbent AND at least one >.
        # Ties and splits go to incumbent.
        if (
            floor_passed
            and c_rec >= i_rec
            and c_mrr >= i_mrr
            and (c_rec > i_rec or c_mrr > i_mrr)
        ):
            winner = "challenger"
        else:
            winner = "incumbent"

    return {
        "floor_passed": floor_passed,
        "vector_justified": vector_justified,
        "winner": winner,
    }


def run_eval_and_log(
    connection: sqlite3.Connection,
    committed_path: str | Path,
    sidecar_path: str | Path,
    model_name: str = "all-MiniLM-L6-v2",
    embedder: Any | None = None,
) -> dict[str, Any]:
    """Run retrieval evaluation and write the 'eval.completed' event to SQLite events table."""
    queries, queryset_sha = load_query_set(committed_path, sidecar_path)
    eval_res = evaluate_retrieval(
        connection, queries, model_name=model_name, embedder=embedder
    )

    fused_recall = eval_res["fused"]["recall_at_10"]
    fused_mrr = eval_res["fused"]["mrr_at_10"]

    costs = capture_costs(connection, model_name, embedder)
    git_sha = get_git_sha()

    payload = {
        "model": model_name,
        "recall_at_10": float(round(fused_recall, 4)),
        "mrr_at_10": float(round(fused_mrr, 4)),
        "n_queries": len(queries),
        "queryset_sha": queryset_sha,
        "embed_ms": float(round(costs["embed_ms"], 2)),
        "index_mb": float(round(costs["index_mb"], 2)),
        "peak_rss_mb": float(round(costs["peak_rss_mb"], 2)),
        "git_sha": git_sha,
        "legs": {
            "fused": eval_res["fused"],
            "fts_only": eval_res["fts_only"],
            "vector_only": eval_res["vector_only"],
        },
    }

    # Ensure events table exists and insert event directly into the target database connection
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            rowid INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            kind TEXT NOT NULL,
            source TEXT NOT NULL,
            status TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "INSERT INTO events(ts, kind, source, status, payload_json) VALUES (?, ?, ?, ?, ?)",
        (_utc_now(), "eval.completed", "search", "ok", json.dumps(payload, sort_keys=True)),
    )
    connection.commit()

    return payload


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
        "--model", default="all-MiniLM-L6-v2", help="Embedding model name to evaluate."
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

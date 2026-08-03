"""Hybrid retrieval path for HiQS (FTS5 + numpy cosine vector search + RRF).

This module implements the canonical search seam defined in HIQS-PROJECT.md §6.1.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3
from typing import Any, Callable

import numpy as np

from hiqs.db import db_connection
from hiqs.docs_index import deserialize_vector, get_default_embedder
from hiqs.plugins import Doc

RERANKER: Callable[[str, list[Doc]], list[Doc]] | None = None


def cap_per_document(hits: list[Doc], max_chunks: int = 2) -> list[Doc]:
    """Limit the number of chunks from the same source document to max_chunks."""
    counts: dict[str, int] = {}
    capped: list[Doc] = []
    for doc in hits:
        doc_key = doc.unit if doc.unit else (doc.id.rsplit(":", 1)[0] if ":" in doc.id else doc.id)
        current = counts.get(doc_key, 0)
        if current < max_chunks:
            counts[doc_key] = current + 1
            capped.append(doc)
    return capped


def rrf_fuse(fts_hits: list[Doc], vec_hits: list[Doc], k: int = 60) -> list[Doc]:
    """Fuse FTS5 and vector search results using Reciprocal Rank Fusion."""
    scores: dict[str, float] = {}
    doc_map: dict[str, Doc] = {}

    for rank, doc in enumerate(fts_hits, start=1):
        scores[doc.id] = scores.get(doc.id, 0.0) + 1.0 / (k + rank)
        doc_map[doc.id] = doc

    for rank, doc in enumerate(vec_hits, start=1):
        scores[doc.id] = scores.get(doc.id, 0.0) + 1.0 / (k + rank)
        doc_map[doc.id] = doc

    sorted_ids = sorted(scores.keys(), key=lambda doc_id: scores[doc_id], reverse=True)
    return [doc_map[doc_id] for doc_id in sorted_ids]


def _fts_search(connection: sqlite3.Connection, query: str, limit: int = 50) -> list[Doc]:
    """Execute FTS5 BM25 search over docs_fts."""
    sql = """
        SELECT d.source, d.id, d.title, d.body, d.url, d.ts, d.project, d.author, COALESCE(u.unit, '') AS unit
        FROM docs_fts f
        JOIN docs d ON d.rowid = f.rowid
        LEFT JOIN doc_units u ON d.id = u.doc_id
        WHERE docs_fts MATCH ?
        ORDER BY bm25(docs_fts)
        LIMIT ?
    """
    rows = []
    try:
        rows = connection.execute(sql, (query, limit)).fetchall()
    except sqlite3.OperationalError:
        clean = query.replace('"', '""')
        formatted = f'"{clean}"'
        try:
            rows = connection.execute(sql, (formatted, limit)).fetchall()
        except sqlite3.OperationalError:
            tokens = [f'"{t.replace(chr(34), chr(34)+chr(34))}"' for t in query.split() if t]
            if tokens:
                try:
                    rows = connection.execute(sql, (" ".join(tokens), limit)).fetchall()
                except sqlite3.OperationalError:
                    rows = []
            else:
                rows = []

    return [
        Doc(
            source=r[0],
            id=r[1],
            title=r[2],
            body=r[3],
            url=r[4],
            ts=r[5],
            project=r[6],
            author=r[7],
            unit=r[8],
        )
        for r in rows
    ]


def _vec_search(
    connection: sqlite3.Connection,
    query: str,
    model_name: str,
    embedder: Any,
    limit: int = 50,
) -> list[Doc]:
    """Execute numpy cosine vector search filtered BY model_name."""
    raw_vecs = getattr(embedder, "encode")([query])
    if raw_vecs is None or len(raw_vecs) == 0:
        return []
    query_vec = np.array(raw_vecs[0], dtype=np.float32)

    sql = """
        SELECT v.doc_id, v.dim, v.vec, d.source, d.title, d.body, d.url, d.ts, d.project, d.author, COALESCE(u.unit, '') AS unit
        FROM docs_vec v
        JOIN docs d ON v.doc_id = d.id
        LEFT JOIN doc_units u ON d.id = u.doc_id
        WHERE v.model = ?
    """
    rows = connection.execute(sql, (model_name,)).fetchall()
    if not rows:
        return []

    doc_ids = []
    doc_objs = []
    vec_list = []

    for r in rows:
        doc_id = r[0]
        dim = r[1]
        blob = r[2]
        doc = Doc(
            source=r[3],
            id=doc_id,
            title=r[4],
            body=r[5],
            url=r[6],
            ts=r[7],
            project=r[8],
            author=r[9],
            unit=r[10],
        )
        vec = deserialize_vector(blob)
        if len(vec) != dim:
            raise ValueError(f"Vector dim mismatch for doc '{doc_id}': expected {dim}, got {len(vec)}")
        doc_ids.append(doc_id)
        doc_objs.append(doc)
        vec_list.append(vec)

    V = np.array(vec_list, dtype=np.float32)

    q_norm = query_vec / (np.linalg.norm(query_vec) + 1e-9)
    V_norm = V / (np.linalg.norm(V, axis=1, keepdims=True) + 1e-9)
    sims = V_norm @ q_norm

    top_indices = np.argsort(-sims)[:limit]
    return [doc_objs[idx] for idx in top_indices]


def _log_search_event(
    connection: sqlite3.Connection, kind: str, status_str: str, payload: dict[str, Any]
) -> None:
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    with connection:
        connection.execute(
            "INSERT INTO events(ts, kind, source, status, payload_json) VALUES (?, ?, ?, ?, ?)",
            (ts, kind, "search", status_str, payload_json),
        )


def search(
    query: str,
    limit: int = 10,
    *,
    connection: sqlite3.Connection | None = None,
    model_name: str = "all-MiniLM-L6-v2",
    embedder: Any | None = None,
) -> list[Doc]:
    """Execute hybrid retrieval (FTS5 + vector search + RRF fusion + document cap)."""
    if not query.strip():
        return []

    owns_connection = False
    if connection is None:
        connection = db_connection()
        owns_connection = True

    try:
        fts_hits = _fts_search(connection, query, limit=50)

        vec_hits: list[Doc] = []
        try:
            if embedder is None:
                embedder = get_default_embedder(model_name)
            vec_hits = _vec_search(connection, query, model_name, embedder, limit=50)
            _log_search_event(connection, "search.ready", "ok", {"mode": "hybrid", "model": model_name})
        except Exception as err:
            _log_search_event(
                connection,
                "search.degraded",
                "warn",
                {"mode": "fts_only", "model": model_name, "reason": str(err)},
            )

        fused = rrf_fuse(fts_hits, vec_hits, k=60)
        capped = cap_per_document(fused, max_chunks=2)

        rerank_fn = RERANKER if RERANKER is not None else (lambda q, hits: hits)
        result = rerank_fn(query, capped)[:limit]
        return result
    finally:
        if owns_connection:
            connection.close()

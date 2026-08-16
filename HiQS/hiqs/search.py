"""Hybrid retrieval path for HiQS (FTS5 + numpy cosine vector search + RRF).

This module implements the canonical search seam defined in HIQS-PROJECT.md §6.1.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any, Callable

import numpy as np

from hiqs.db import db_connection
from hiqs.docs_index import deserialize_vector, get_default_embedder
from hiqs.events import log_event
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


_FTS_OPERATORS = ("AND", "OR", "NOT", "NEAR")
_FTS_TOKEN = re.compile(r"[A-Za-z0-9_]+(?:[-'][A-Za-z0-9_]+)*")


def _fts_expression(query: str) -> str:
    """Build an FTS5 MATCH expression that ORs the query's terms, ranked by bm25.

    FTS5's implicit operator is AND, so passing a question through verbatim demands that one
    chunk contain *every* word. Measured on the real corpus, that returned 35 hits across 22
    queries and **all 35 were the operator's own prompt log** — the only text holding a
    question verbatim is the record of it being asked. Remove that log and the lexical leg
    returned nothing at all, so "hybrid" search was running on the vector leg alone.

        "Where is the earlier generated ADR doc stored?"
            AND (before) ->     1 matching chunk
            OR  (after)  -> 4,760 matching chunks, bm25-ranked

    OR alone would be too loose if every match counted equally, but bm25 is what does the
    ranking: rare terms ("ADR") dominate common ones ("is", "the"), so recall widens without
    the top of the list going to whatever mentions "the" most.
    """
    if any(f" {op} " in query for op in _FTS_OPERATORS) or '"' in query:
        # The caller wrote FTS5 syntax on purpose. Honour it rather than rewriting it.
        return query
    tokens = _FTS_TOKEN.findall(query)
    return " OR ".join(f'"{token}"' for token in tokens)


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
    expression = _fts_expression(query)
    if expression:
        try:
            rows = connection.execute(sql, (expression, limit)).fetchall()
        except sqlite3.OperationalError:
            # Caller-supplied FTS5 syntax that does not parse. Fall back to its bare terms
            # rather than returning nothing, since an empty lexical leg is invisible in a
            # fused result and reads as "no lexical match" instead of "malformed query".
            tokens = _FTS_TOKEN.findall(query)
            if tokens:
                try:
                    rows = connection.execute(
                        sql, (" OR ".join(f'"{t}"' for t in tokens), limit)
                    ).fetchall()
                except sqlite3.OperationalError:
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
    raw_vecs = embedder.encode([query])
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


def search(
    query: str,
    limit: int = 10,
    *,
    connection: sqlite3.Connection | None = None,
    model_name: str = "all-MiniLM-L6-v2",
    embedder: Any | None = None,
    affinity: bool = True,
    affinity_edges: frozenset[str] | None = None,
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
            log_event("search.ready", "search", "ok", {"mode": "hybrid", "model": model_name})
        except Exception as err:
            log_event(
                "search.degraded",
                "search",
                "warn",
                {"mode": "fts_only", "model": model_name, "reason": str(err)},
            )

        fused = rrf_fuse(fts_hits, vec_hits, k=60)
        capped = cap_per_document(fused, max_chunks=2)

        rerank_fn = RERANKER if RERANKER is not None else (lambda q, hits: hits)
        direct_hits = rerank_fn(query, capped)[:limit]
        if not affinity:
            return direct_hits

        # Widen only after fusion, the document cap, and any ranking hook so
        # sibling documents can never reorder or displace direct retrieval.
        from hiqs.affinity import append_affinity_hits

        return append_affinity_hits(
            connection, query, direct_hits, limit, enabled_edges=affinity_edges
        )
    finally:
        if owns_connection:
            connection.close()

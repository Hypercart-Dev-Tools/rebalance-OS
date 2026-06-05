"""chat_with_data — scoped, citations-first retrieval over rebalance's corpus.

Phase 0 of PROJECT/2-WORKING/CHAT-WITH-DATA.md. This is the retrieval core the
dashboard "Ask" search mode and (later) an MCP tool call into.

Today it searches the native unified semantic index (vault / github / email).
``scope`` is accepted now so the surface is stable; ``code`` federation via
ask_self is added in the spike phase behind an availability gate. Synthesis is
intentionally off by default — return grounded citations, fast and debuggable.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

# Reserved scope vocabulary. "work" = the ingested work artifacts; "code" =
# source tree + GitHub artifacts (code federation lands in the spike); "all" = both.
SCOPES = ("all", "work", "code")


def _citation_from_semantic(row: dict[str, Any]) -> dict[str, Any]:
    """Map a semantic_index result row to the stable citation contract."""
    meta = row.get("metadata") or {}
    path = meta.get("path") or meta.get("url") or row.get("source_pk") or ""
    return {
        "source": row.get("source_type") or "work",
        "title": row.get("title") or "",
        "path": path,
        "preview": (row.get("body_preview") or "")[:280],
        "score": row.get("similarity_score"),
        "kind": row.get("doc_kind") or "",
    }


def _default_work_query(database_path: Path, query: str, top_k: int) -> list[dict[str, Any]]:
    from rebalance.ingest.semantic_index import query as _q
    return _q(database_path, query, top_k=top_k)


def chat_with_data(
    database_path: Path,
    query: str,
    *,
    scope: str = "all",
    top_k: int = 8,
    skip_synthesis: bool = True,
    work_query_fn: Callable[[Path, str, int], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Retrieve citations for *query* across the requested *scope*.

    Returns a JSON-able dict:
        {query, scope, citations: [{source,title,path,preview,score,kind}],
         used_sources: [...], elapsed_ms, answer}

    ``answer`` is always None while ``skip_synthesis`` is True (Phase 0).
    *work_query_fn* is an injection point for tests so they need no embed model.
    """
    start = time.monotonic()
    scope = (scope or "all").strip().lower()
    if scope not in SCOPES:
        scope = "all"
    text = (query or "").strip()
    if not text:
        return {
            "query": text, "scope": scope, "citations": [],
            "used_sources": [], "elapsed_ms": 0, "answer": None,
        }

    citations: list[dict[str, Any]] = []
    used: list[str] = []

    # Native work corpus. Searched for work/all now; also the only code-adjacent
    # source until the ask_self federation / native code corpus lands.
    if scope in ("all", "work", "code"):
        qfn = work_query_fn or _default_work_query
        rows = qfn(database_path, text, top_k)
        citations.extend(_citation_from_semantic(r) for r in rows)
        used.append("semantic_index")

    # Stable, deterministic ordering: score desc, then source/title for ties.
    citations.sort(
        key=lambda c: (-(c.get("score") or 0.0), c.get("source") or "", c.get("title") or "")
    )
    citations = citations[:top_k]

    return {
        "query": text,
        "scope": scope,
        "citations": citations,
        "used_sources": used,
        "elapsed_ms": int((time.monotonic() - start) * 1000),
        "answer": None,
    }

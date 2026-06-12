"""chat_with_data — scoped, citations-first retrieval over rebalance's corpus.

Phase 0 of PROJECT/2-WORKING/CHAT-WITH-DATA.md. This is the retrieval core the
dashboard "Ask" search mode and (later) an MCP tool call into.

Today it searches the native unified semantic index (vault / github / email).
``scope`` is accepted now so the surface is stable; ``code`` federation via
ask_self is added in the spike phase behind an availability gate. Synthesis is
intentionally off by default — return grounded citations, fast and debuggable.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

# Reserved scope vocabulary. "work" = the ingested work artifacts; "code" =
# source tree + docs via the federated ask_self index; "all" = both.
SCOPES = ("all", "work", "code")

from rebalance.paths import resolve_project_root
from rebalance.ingest.semantic_index import (  # noqa: E402
    WORK_SOURCES,
    scope_to_sources as _semantic_sources_for_scope,
)
_REPO_ROOT = resolve_project_root(Path(__file__))
ASK_SELF_TIMEOUT_SECONDS = 60


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


def _default_semantic_query(
    database_path: Path, query: str, top_k: int, sources: list[str]
) -> list[dict[str, Any]]:
    from rebalance.ingest.semantic_index import query as _q
    return _q(database_path, query, top_k=top_k, source_filter=sources)


# ---------------------------------------------------------------------------
# ask_self federation (code/docs corpus)
# ---------------------------------------------------------------------------

def ask_self_available() -> bool:
    """True if ask_self federation can run: a configured install + the wrapper."""
    from rebalance.ingest.config import get_ask_self_path
    root = get_ask_self_path()
    wrapper = _REPO_ROOT / "scripts" / "ask-self-query.sh"
    return bool(root) and Path(root).is_dir() and wrapper.exists()


def _query_ask_self(query: str, top_k: int) -> list[dict[str, Any]]:
    """Federate the ask_self code/doc index → citation dicts. Never raises.

    Runs the repo's ask-self-query.sh wrapper with the rebalance venv as the
    interpreter (ASK_SELF_PYTHON) — ask-self's own venv lacks mlx-embeddings,
    so the rebalance venv is required for the local Qwen-MLX provider.
    """
    from rebalance.ingest.config import get_ask_self_path
    root = get_ask_self_path()
    wrapper = _REPO_ROOT / "scripts" / "ask-self-query.sh"
    if not root or not wrapper.exists():
        return []
    env = {**os.environ, "ASK_SELF_PATH": root, "ASK_SELF_PYTHON": sys.executable}
    try:
        proc = subprocess.run(
            ["bash", str(wrapper), query, "--retrieval-only", "--json"],
            capture_output=True, text=True, env=env,
            timeout=ASK_SELF_TIMEOUT_SECONDS, cwd=str(_REPO_ROOT),
        )
        if proc.returncode != 0:
            return []
        data = json.loads(proc.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, dict) or not data.get("ok"):
        return []

    cites: list[dict[str, Any]] = []
    for hit in (data.get("retrieved_hits") or [])[:top_k]:
        if not isinstance(hit, dict):
            continue
        dist = hit.get("distance")
        score = round(1.0 - dist, 4) if isinstance(dist, (int, float)) else hit.get("score")
        cites.append({
            "source": "code",
            "title": hit.get("path") or "",
            "path": hit.get("path") or "",
            "preview": (hit.get("content") or "")[:280],
            "score": score,
            "kind": hit.get("source") or "code",
        })
    return cites


def _rrf_merge(lists: list[list[dict[str, Any]]], top_k: int, k: int = 60) -> list[dict[str, Any]]:
    """Reciprocal-rank fusion — rank-based, so the two systems' score scales
    don't have to be comparable. Dedupe by (source, path|title)."""
    def key(c: dict[str, Any]) -> tuple[str, str]:
        return (c.get("source") or "", (c.get("path") or c.get("title") or "").lower())

    scores: dict[tuple[str, str], float] = {}
    best: dict[tuple[str, str], dict[str, Any]] = {}
    for lst in lists:
        for rank, c in enumerate(lst):
            ck = key(c)
            scores[ck] = scores.get(ck, 0.0) + 1.0 / (k + rank + 1)
            best.setdefault(ck, c)
    ranked = sorted(best.values(), key=lambda c: -scores[key(c)])
    return ranked[:top_k]


def chat_with_data(
    database_path: Path,
    query: str,
    *,
    scope: str = "all",
    top_k: int = 8,
    skip_synthesis: bool = True,
    work_query_fn: Callable[[Path, str, int, list[str]], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Retrieve citations for *query* across the requested *scope*.

    Scope selects native semantic_index sources — ``work`` (vault/github/email),
    ``code`` (the indexed source tree), ``all`` (both) — and adds the federated
    ask_self code/doc index for ``code``/``all`` when available.

    Returns a JSON-able dict:
        {query, scope, citations: [{source,title,path,preview,score,kind}],
         used_sources: [...], elapsed_ms, answer}

    ``answer`` is always None while ``skip_synthesis`` is True (Phase 0).
    *work_query_fn(db, query, top_k, sources)* is an injection point for tests.
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

    used: list[str] = []
    result_lists: list[list[dict[str, Any]]] = []

    # Native semantic index — scope picks the source_types (work / code / both).
    qfn = work_query_fn or _default_semantic_query
    sources = _semantic_sources_for_scope(scope)
    native = [_citation_from_semantic(r) for r in qfn(database_path, text, top_k, sources)]
    if native:
        result_lists.append(native)
        used.append("semantic_index")

    # Federated code/docs corpus via ask_self: code + all (gated on availability).
    if scope in ("all", "code") and ask_self_available():
        code = _query_ask_self(text, top_k)
        if code:
            result_lists.append(code)
            used.append("ask_self")

    if len(result_lists) > 1:
        citations = _rrf_merge(result_lists, top_k)  # fuse across systems
    elif result_lists:
        citations = result_lists[0][:top_k]
    else:
        citations = []

    return {
        "query": text,
        "scope": scope,
        "citations": citations,
        "used_sources": used,
        "elapsed_ms": int((time.monotonic() - start) * 1000),
        "answer": None,
    }

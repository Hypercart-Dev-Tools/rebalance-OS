"""Unified semantic document index across vault and GitHub sources."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from rebalance.ingest.config import get_github_ignored_repos, normalize_github_repo_name
from rebalance.ingest.db import (
    db_connection,
    ensure_github_schema,
    ensure_schema,
    ensure_semantic_schema,
)
from rebalance.ingest.db import semantic as sem
from rebalance.ingest.embedder import (
    DEFAULT_MODEL as DEFAULT_EMBED_MODEL,
    EMBEDDING_DIM,
    _embed_batch,
    _load_model,
    _vec_to_bytes,
)

EmbedTexts = Callable[[list[str], str], list[list[float]]]


@dataclass
class SemanticBackfillResult:
    source_types: tuple[str, ...]
    total_documents: int
    inserted_count: int
    updated_count: int
    unchanged_count: int
    deleted_count: int
    elapsed_seconds: float


@dataclass
class SemanticEmbedResult:
    total_docs: int
    embedded_docs: int
    skipped_unchanged: int
    model_name: str
    embedding_dim: int
    elapsed_seconds: float


def _default_embed_texts(texts: list[str], model_name: str) -> list[list[float]]:
    model, tokenizer = _load_model(model_name)
    return _embed_batch(model, tokenizer, texts)


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _normalize_sources(source_types: Iterable[str] | None) -> tuple[str, ...]:
    if source_types is None:
        return ("vault", "github", "email")
    normalized = []
    for value in source_types:
        item = value.strip().lower()
        if not item:
            continue
        if item == "all":
            return ("vault", "github", "email")
        if item not in {"vault", "github", "calendar", "sleuth", "email"}:
            raise ValueError(f"Unsupported source type: {value}")
        if item not in normalized:
            normalized.append(item)
    return tuple(normalized)


def upsert_document(
    conn: Any,
    *,
    source_type: str,
    source_table: str,
    source_pk: str,
    doc_kind: str,
    title: str,
    body: str,
    metadata: dict[str, Any] | None,
    created_at: str,
    updated_at: str,
) -> tuple[int, str]:
    """Insert or update one semantic document row.

    Returns ``(doc_id, state)`` where state is one of ``inserted``, ``updated``,
    or ``unchanged``.
    """
    metadata_json = _json_dumps(metadata or {})
    content_hash = _content_hash(body)
    existing = sem.find_semantic_document(conn, source_type, source_pk)

    if existing is None:
        doc_id = sem.insert_semantic_document(
            conn,
            source_type=source_type,
            source_table=source_table,
            source_pk=source_pk,
            doc_kind=doc_kind,
            title=title,
            body=body,
            content_hash=content_hash,
            metadata_json=metadata_json,
            created_at=created_at,
            updated_at=updated_at,
        )
        return doc_id, "inserted"

    has_changed = any(
        [
            existing["source_table"] != source_table,
            existing["doc_kind"] != doc_kind,
            (existing["title"] or "") != title,
            existing["body"] != body,
            existing["content_hash"] != content_hash,
            (existing["metadata_json"] or "{}") != metadata_json,
            (existing["updated_at"] or "") != updated_at,
        ]
    )
    if not has_changed:
        return int(existing["id"]), "unchanged"

    sem.update_semantic_document(
        conn,
        int(existing["id"]),
        source_table=source_table,
        doc_kind=doc_kind,
        title=title,
        body=body,
        content_hash=content_hash,
        metadata_json=metadata_json,
        updated_at=updated_at,
    )
    return int(existing["id"]), "updated"


def _delete_missing_docs(
    conn: Any,
    *,
    source_type: str,
    seen_source_pks: set[str],
    source_pk_prefix: str = "",
) -> int:
    rows = sem.semantic_documents_for_source(
        conn, source_type, source_pk_prefix=source_pk_prefix
    )

    to_delete = [int(row["id"]) for row in rows if row["source_pk"] not in seen_source_pks]
    if not to_delete:
        return 0

    sem.delete_semantic_documents(conn, to_delete)
    return len(to_delete)


def sync_vault_documents(conn: Any) -> dict[str, int]:
    """Backfill semantic documents from the current ``chunks`` table."""
    ensure_semantic_schema(conn)
    rows = sem.vault_chunks_for_semantic(conn)

    inserted = updated = unchanged = 0
    seen_source_pks: set[str] = set()
    for row in rows:
        source_pk = str(row["id"])
        seen_source_pks.add(source_pk)
        _, state = upsert_document(
            conn,
            source_type="vault",
            source_table="chunks",
            source_pk=source_pk,
            doc_kind="chunk",
            title=row["title"] or row["rel_path"],
            body=row["body"],
            metadata={
                "file_id": row["file_id"],
                "file_path": row["rel_path"],
                "heading": row["heading"] or "",
                "heading_level": row["heading_level"],
                "chunk_index": row["chunk_index"],
                "char_count": row["char_count"],
                "tags": json.loads(row["tags_json"]) if row["tags_json"] else [],
            },
            created_at=row["ingested_at"],
            updated_at=row["last_modified"] or row["ingested_at"],
        )
        if state == "inserted":
            inserted += 1
        elif state == "updated":
            updated += 1
        else:
            unchanged += 1

    deleted = _delete_missing_docs(conn, source_type="vault", seen_source_pks=seen_source_pks)
    return {
        "total": len(rows),
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "deleted": deleted,
    }


def sync_github_documents(conn: Any, *, repo_full_name: str = "") -> dict[str, int]:
    """Backfill semantic documents from ``github_documents``."""
    ensure_semantic_schema(conn)
    ignored_repos = set(get_github_ignored_repos())
    normalized_repo = normalize_github_repo_name(repo_full_name) if repo_full_name.strip() else ""
    if normalized_repo and normalized_repo in ignored_repos:
        return {"total": 0, "inserted": 0, "updated": 0, "unchanged": 0, "deleted": 0}

    rows = sem.github_documents_for_semantic(
        conn, normalized_repo=normalized_repo, ignored_repos=ignored_repos
    )

    inserted = updated = unchanged = 0
    seen_source_pks: set[str] = set()
    for row in rows:
        source_pk = row["source_key"]
        seen_source_pks.add(source_pk)
        _, state = upsert_document(
            conn,
            source_type="github",
            source_table="github_documents",
            source_pk=source_pk,
            doc_kind=row["doc_type"],
            title=row["title"] or "",
            body=row["body"],
            metadata={
                "repo_full_name": row["repo_full_name"],
                "item_type": row["github_source_type"],
                "source_number": row["source_number"],
                "state": row["state"] or "",
                "milestone_title": row["milestone_title"] or "",
                "labels": json.loads(row["labels_json"]) if row["labels_json"] else [],
                "review_decision": row["review_decision"] or "",
                "check_status": row["check_status"] or "",
                "html_url": row["html_url"] or "",
            },
            created_at=row["fetched_at"],
            updated_at=row["updated_at"] or row["fetched_at"],
        )
        if state == "inserted":
            inserted += 1
        elif state == "updated":
            updated += 1
        else:
            unchanged += 1

    explicit_prefix = f"{repo_full_name.strip()}:" if repo_full_name.strip() else ""
    deleted = _delete_missing_docs(
        conn,
        source_type="github",
        seen_source_pks=seen_source_pks,
        source_pk_prefix=explicit_prefix,
    )
    return {
        "total": len(rows),
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "deleted": deleted,
    }


def sync_email_documents(conn: Any) -> dict[str, int]:
    """Backfill semantic documents from ``email_messages``.

    Body is ``subject + "\\n" + snippet`` per the Phase 1 plan — full MIME
    body extraction is deferred to Phase 2. Newest-100 rolling fetches
    don't delete older rows, so we don't reconcile against ``seen``: an
    email row that drops out of the fetch window stays in the index.
    """
    ensure_semantic_schema(conn)
    rows = sem.email_messages_for_semantic(conn)

    inserted = updated = unchanged = 0
    for row in rows:
        subject = row["subject"] or ""
        snippet = row["snippet"] or ""
        body = f"{subject}\n{snippet}".strip()
        if not body:
            continue

        title = subject or (row["from_address"] or "(no subject)")
        received_at = row["received_at"] or row["synced_at"]

        _, state = upsert_document(
            conn,
            source_type="email",
            source_table="email_messages",
            source_pk=row["message_id"],
            doc_kind="message",
            title=title,
            body=body,
            metadata={
                "thread_id": row["thread_id"] or "",
                "from_address": row["from_address"] or "",
                "from_name": row["from_name"] or "",
                "labels": json.loads(row["labels_json"]) if row["labels_json"] else [],
                "received_at": received_at,
            },
            created_at=received_at,
            updated_at=row["synced_at"],
        )
        if state == "inserted":
            inserted += 1
        elif state == "updated":
            updated += 1
        else:
            unchanged += 1

    return {
        "total": len(rows),
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "deleted": 0,
    }


def backfill_semantic_documents(
    database_path: Path,
    *,
    source_types: Iterable[str] | None = None,
    repo_full_name: str = "",
) -> SemanticBackfillResult:
    """Populate ``semantic_documents`` from existing source tables."""
    start = time.monotonic()
    selected_sources = _normalize_sources(source_types)
    inserted = updated = unchanged = deleted = total = 0

    with db_connection(database_path) as conn:
        ensure_semantic_schema(conn)
        if "vault" in selected_sources:
            ensure_schema(conn)
            result = sync_vault_documents(conn)
            inserted += result["inserted"]
            updated += result["updated"]
            unchanged += result["unchanged"]
            deleted += result["deleted"]
            total += result["total"]
        if "github" in selected_sources:
            ensure_github_schema(conn)
            result = sync_github_documents(conn, repo_full_name=repo_full_name)
            inserted += result["inserted"]
            updated += result["updated"]
            unchanged += result["unchanged"]
            deleted += result["deleted"]
            total += result["total"]
        if "email" in selected_sources:
            from rebalance.ingest.db import ensure_email_schema
            ensure_email_schema(conn)
            result = sync_email_documents(conn)
            inserted += result["inserted"]
            updated += result["updated"]
            unchanged += result["unchanged"]
            deleted += result["deleted"]
            total += result["total"]
        conn.commit()

    return SemanticBackfillResult(
        source_types=selected_sources,
        total_documents=total,
        inserted_count=inserted,
        updated_count=updated,
        unchanged_count=unchanged,
        deleted_count=deleted,
        elapsed_seconds=round(time.monotonic() - start, 2),
    )


def embed_pending(
    database_path: Path,
    *,
    model_name: str = DEFAULT_EMBED_MODEL,
    batch_size: int = 32,
    min_chars: int = 1,
    force_reembed: bool = False,
    source_types: Iterable[str] | None = None,
    embed_texts: EmbedTexts | None = None,
) -> SemanticEmbedResult:
    """Embed pending semantic document rows via the shared local embedder."""
    start = time.monotonic()
    embed_fn = embed_texts or _default_embed_texts
    selected_sources = _normalize_sources(source_types)
    current_model_version = f"{model_name}|{EMBEDDING_DIM}"

    with db_connection(database_path, ensure_semantic_schema) as conn:
        if force_reembed:
            if set(selected_sources) == {"vault", "github", "email"} and len(selected_sources) == 3:
                sem.clear_semantic_embeddings(conn)
                sem.reset_semantic_embedded_state(conn)
            else:
                row_ids = sem.semantic_doc_ids_for_sources(conn, selected_sources)
                sem.delete_semantic_embeddings_for_docs(conn, row_ids)
                sem.reset_semantic_embedded_state(conn, selected_sources)
            conn.commit()

        rows = sem.semantic_documents_pending_embed(
            conn, selected_sources, min_chars, current_model_version
        )
        total_docs = sem.count_embeddable_semantic_documents(
            conn, selected_sources, min_chars
        )

        if not rows:
            return SemanticEmbedResult(
                total_docs=total_docs,
                embedded_docs=0,
                skipped_unchanged=total_docs,
                model_name=model_name,
                embedding_dim=EMBEDDING_DIM,
                elapsed_seconds=round(time.monotonic() - start, 2),
            )

        embedded = 0
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            texts = [row["body"][:4000] for row in batch]
            vectors = embed_fn(texts, model_name)
            now_iso = datetime.now(timezone.utc).isoformat()
            for row, vec in zip(batch, vectors):
                sem.delete_semantic_embedding(conn, row["id"])
                sem.insert_semantic_embedding(conn, row["id"], _vec_to_bytes(vec))
                sem.mark_semantic_document_embedded(
                    conn, row["id"], current_model_version, now_iso
                )
                embedded += 1
            conn.commit()

        now_iso = datetime.now(timezone.utc).isoformat()
        for key, value in [
            ("model_name", model_name),
            ("embedding_dim", str(EMBEDDING_DIM)),
            ("embedder_version", current_model_version),
            ("last_embed_at", now_iso),
        ]:
            sem.set_semantic_embedding_meta(conn, key, value)
        conn.commit()

    return SemanticEmbedResult(
        total_docs=total_docs,
        embedded_docs=embedded,
        skipped_unchanged=total_docs - embedded,
        model_name=model_name,
        embedding_dim=EMBEDDING_DIM,
        elapsed_seconds=round(time.monotonic() - start, 2),
    )


def _rrf_fuse(
    result_lists: list[list[Any]], top_k: int, *, k: int = 60
) -> list[Any]:
    """Reciprocal-rank fusion of ranked row lists, keyed on ``doc_id``.

    Rank-based, so the vector (distance) and lexical (bm25) scales never have to
    be compared. Dedupe by doc_id; when a doc is in both lists, keep the row that
    carries a ``distance`` (the vector hit) so a similarity score can be shown.
    """
    scores: dict[Any, float] = {}
    rowmap: dict[Any, Any] = {}
    for rows in result_lists:
        for rank, row in enumerate(rows):
            doc_id = row["doc_id"]
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
            if doc_id not in rowmap or row["distance"] is not None:
                rowmap[doc_id] = row
    ordered = sorted(scores, key=lambda d: -scores[d])
    return [rowmap[d] for d in ordered[:top_k]]


def query(
    database_path: Path,
    query_text: str,
    *,
    top_k: int = 10,
    model_name: str = DEFAULT_EMBED_MODEL,
    source_filter: Iterable[str] | None = None,
    updated_after: str | None = None,
    repo: str | None = None,
    embed_texts: EmbedTexts | None = None,
    hybrid: bool = True,
) -> list[dict[str, Any]]:
    """Semantic search across the unified semantic index.

    Args:
        updated_after: ISO-8601 string (e.g. ``"2026-05-01"``); exclude docs
                       updated before this date/time.
        repo: Restrict github results to one repo (``owner/name``).
        hybrid: Fuse the vector (ANN) ranking with an FTS5 lexical ranking via
                RRF — better recall on exact identifiers/paths/config keys. Set
                False for pure ANN (also the automatic fallback when FTS5 is
                unavailable or the query has no lexical terms).
    """
    selected_sources = _normalize_sources(source_filter)
    embed_fn = embed_texts or _default_embed_texts
    query_vec = _vec_to_bytes(embed_fn([query_text], model_name)[0])
    # Fetch a deeper pool per retriever so RRF has material to fuse.
    pool = max(top_k * 4, 24) if hybrid else top_k

    with db_connection(database_path, ensure_semantic_schema) as conn:
        vec_rows = sem.search_semantic_documents(
            conn, query_vec, pool, selected_sources,
            updated_after=updated_after, repo=repo,
        )
        fts_rows = (
            sem.search_semantic_documents_fts(
                conn, query_text, pool, selected_sources,
                updated_after=updated_after, repo=repo,
            )
            if hybrid else []
        )

    rows = _rrf_fuse([vec_rows, fts_rows], top_k) if fts_rows else vec_rows[:top_k]

    results: list[dict[str, Any]] = []
    for row in rows:
        metadata = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
        distance = row["distance"]
        results.append(
            {
                "doc_id": row["doc_id"],
                "source_type": row["source_type"],
                "source_table": row["source_table"],
                "source_pk": row["source_pk"],
                "doc_kind": row["doc_kind"],
                "title": row["title"] or "",
                "body_preview": row["body_preview"],
                "metadata": metadata,
                "updated_at": row["updated_at"],
                "similarity_score": round(1.0 - distance, 4) if distance is not None else None,
            }
        )
    return results

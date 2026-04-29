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
        return ("vault", "github")
    normalized = []
    for value in source_types:
        item = value.strip().lower()
        if not item:
            continue
        if item == "all":
            return ("vault", "github")
        if item not in {"vault", "github", "calendar", "sleuth"}:
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
    existing = conn.execute(
        """
        SELECT id, source_table, doc_kind, title, body, content_hash, metadata_json, updated_at
        FROM semantic_documents
        WHERE source_type = ? AND source_pk = ?
        """,
        (source_type, source_pk),
    ).fetchone()

    if existing is None:
        conn.execute(
            """
            INSERT INTO semantic_documents
                (source_type, source_table, source_pk, doc_kind, title, body, content_hash,
                 embedded_hash, embedded_model_version, embedded_at, metadata_json,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?, ?)
            """,
            (
                source_type,
                source_table,
                source_pk,
                doc_kind,
                title,
                body,
                content_hash,
                metadata_json,
                created_at,
                updated_at,
            ),
        )
        return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0]), "inserted"

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

    conn.execute(
        """
        UPDATE semantic_documents
        SET source_table = ?,
            doc_kind = ?,
            title = ?,
            body = ?,
            content_hash = ?,
            metadata_json = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            source_table,
            doc_kind,
            title,
            body,
            content_hash,
            metadata_json,
            updated_at,
            existing["id"],
        ),
    )
    return int(existing["id"]), "updated"


def _delete_missing_docs(
    conn: Any,
    *,
    source_type: str,
    seen_source_pks: set[str],
    source_pk_prefix: str = "",
) -> int:
    if source_pk_prefix:
        rows = conn.execute(
            """
            SELECT id, source_pk
            FROM semantic_documents
            WHERE source_type = ? AND SUBSTR(source_pk, 1, ?) = ?
            """,
            (source_type, len(source_pk_prefix), source_pk_prefix),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id, source_pk
            FROM semantic_documents
            WHERE source_type = ?
            """,
            (source_type,),
        ).fetchall()

    to_delete = [int(row["id"]) for row in rows if row["source_pk"] not in seen_source_pks]
    if not to_delete:
        return 0

    conn.executemany("DELETE FROM semantic_embeddings WHERE rowid = ?", [(doc_id,) for doc_id in to_delete])
    conn.executemany("DELETE FROM semantic_documents WHERE id = ?", [(doc_id,) for doc_id in to_delete])
    return len(to_delete)


def sync_vault_documents(conn: Any) -> dict[str, int]:
    """Backfill semantic documents from the current ``chunks`` table."""
    ensure_semantic_schema(conn)
    rows = conn.execute(
        """
        SELECT
            c.id,
            c.file_id,
            c.chunk_index,
            c.heading,
            c.heading_level,
            c.body,
            c.char_count,
            c.content_hash,
            vf.rel_path,
            vf.title,
            vf.tags_json,
            vf.ingested_at,
            vf.last_modified
        FROM chunks c
        JOIN vault_files vf ON vf.id = c.file_id
        ORDER BY c.id
        """
    ).fetchall()

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

    params: tuple[Any, ...]
    where_sql = ""
    if normalized_repo:
        where_sql = "WHERE LOWER(gd.repo_full_name) = ?"
        params = (normalized_repo,)
    else:
        ignored_placeholders = ", ".join("?" for _ in ignored_repos)
        if ignored_placeholders:
            where_sql = f"WHERE LOWER(gd.repo_full_name) NOT IN ({ignored_placeholders})"
            params = tuple(sorted(ignored_repos))
        else:
            params = ()

    rows = conn.execute(
        f"""
        SELECT
            gd.id,
            gd.repo_full_name,
            gd.source_type AS github_source_type,
            gd.source_number,
            gd.doc_type,
            gd.source_key,
            gd.title,
            gd.body,
            gd.content_hash,
            gd.updated_at,
            gd.fetched_at,
            gi.state,
            gi.milestone_title,
            gi.labels_json,
            gi.review_decision,
            gi.check_status,
            gi.html_url
        FROM github_documents gd
        LEFT JOIN github_items gi
          ON gi.repo_full_name = gd.repo_full_name
         AND gi.item_type = gd.source_type
         AND gi.number = gd.source_number
        {where_sql}
        ORDER BY gd.id
        """,
        params,
    ).fetchall()

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
            if set(selected_sources) == {"vault", "github"} and len(selected_sources) == 2:
                conn.execute("DELETE FROM semantic_embeddings")
                conn.execute(
                    """
                    UPDATE semantic_documents
                    SET embedded_hash = NULL,
                        embedded_model_version = NULL,
                        embedded_at = NULL
                    """
                )
            else:
                placeholders = ", ".join("?" for _ in selected_sources)
                row_ids = [
                    int(row["id"])
                    for row in conn.execute(
                        f"""
                        SELECT id
                        FROM semantic_documents
                        WHERE source_type IN ({placeholders})
                        """,
                        selected_sources,
                    ).fetchall()
                ]
                conn.executemany("DELETE FROM semantic_embeddings WHERE rowid = ?", [(row_id,) for row_id in row_ids])
                conn.execute(
                    f"""
                    UPDATE semantic_documents
                    SET embedded_hash = NULL,
                        embedded_model_version = NULL,
                        embedded_at = NULL
                    WHERE source_type IN ({placeholders})
                    """,
                    selected_sources,
                )
            conn.commit()

        placeholders = ", ".join("?" for _ in selected_sources)
        params: list[Any] = [*selected_sources, min_chars, current_model_version]
        rows = conn.execute(
            f"""
            SELECT id, body, content_hash
            FROM semantic_documents
            WHERE source_type IN ({placeholders})
              AND LENGTH(body) >= ?
              AND (
                    embedded_hash IS NULL
                 OR embedded_hash != content_hash
                 OR embedded_model_version IS NULL
                 OR embedded_model_version != ?
              )
            ORDER BY id
            """,
            params,
        ).fetchall()
        total_docs = conn.execute(
            f"""
            SELECT COUNT(*)
            FROM semantic_documents
            WHERE source_type IN ({placeholders}) AND LENGTH(body) >= ?
            """,
            [*selected_sources, min_chars],
        ).fetchone()[0]

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
                conn.execute("DELETE FROM semantic_embeddings WHERE rowid = ?", (row["id"],))
                conn.execute(
                    "INSERT INTO semantic_embeddings (rowid, embedding) VALUES (?, ?)",
                    (row["id"], _vec_to_bytes(vec)),
                )
                conn.execute(
                    """
                    UPDATE semantic_documents
                    SET embedded_hash = content_hash,
                        embedded_model_version = ?,
                        embedded_at = ?
                    WHERE id = ?
                    """,
                    (current_model_version, now_iso, row["id"]),
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
            conn.execute(
                "INSERT OR REPLACE INTO semantic_embedding_meta (key, value) VALUES (?, ?)",
                (key, value),
            )
        conn.commit()

    return SemanticEmbedResult(
        total_docs=total_docs,
        embedded_docs=embedded,
        skipped_unchanged=total_docs - embedded,
        model_name=model_name,
        embedding_dim=EMBEDDING_DIM,
        elapsed_seconds=round(time.monotonic() - start, 2),
    )


def query(
    database_path: Path,
    query_text: str,
    *,
    top_k: int = 10,
    model_name: str = DEFAULT_EMBED_MODEL,
    source_filter: Iterable[str] | None = None,
    embed_texts: EmbedTexts | None = None,
) -> list[dict[str, Any]]:
    """Semantic search across the unified semantic index."""
    selected_sources = _normalize_sources(source_filter)
    embed_fn = embed_texts or _default_embed_texts
    query_vec = _vec_to_bytes(embed_fn([query_text], model_name)[0])

    with db_connection(database_path, ensure_semantic_schema) as conn:
        placeholders = ", ".join("?" for _ in selected_sources)
        rows = conn.execute(
            f"""
            SELECT
                se.rowid AS doc_id,
                se.distance,
                sd.source_type,
                sd.source_table,
                sd.source_pk,
                sd.doc_kind,
                sd.title,
                SUBSTR(sd.body, 1, 400) AS body_preview,
                sd.metadata_json,
                sd.updated_at
            FROM semantic_embeddings se
            JOIN semantic_documents sd ON sd.id = se.rowid
            WHERE se.embedding MATCH ? AND se.k = ?
              AND sd.source_type IN ({placeholders})
            ORDER BY se.distance
            """,
            [query_vec, top_k, *selected_sources],
        ).fetchall()

    results: list[dict[str, Any]] = []
    for row in rows:
        metadata = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
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
                "similarity_score": round(1.0 - row["distance"], 4),
            }
        )
    return results

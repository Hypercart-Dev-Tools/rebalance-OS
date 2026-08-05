"""Typed query helpers for the unified semantic index tables.

Keeps raw SQL out of ``semantic_index.py``: the document corpus
(``semantic_documents``), its vector index (``semantic_embeddings``), and the
source-table reads that feed the backfill. This module owns the column layout.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Sequence


# ---------------------------------------------------------------------------
# Document upsert
# ---------------------------------------------------------------------------


def find_semantic_document(
    conn: sqlite3.Connection, source_type: str, source_pk: str
) -> sqlite3.Row | None:
    """Return the existing ``semantic_documents`` row for a source key, or None."""
    return conn.execute(
        """
        SELECT id, source_table, doc_kind, title, body, content_hash, metadata_json, updated_at
        FROM semantic_documents
        WHERE source_type = ? AND source_pk = ?
        """,
        (source_type, source_pk),
    ).fetchone()


def insert_semantic_document(
    conn: sqlite3.Connection,
    *,
    source_type: str,
    source_table: str,
    source_pk: str,
    doc_kind: str,
    title: str,
    body: str,
    content_hash: str,
    metadata_json: str,
    created_at: str,
    updated_at: str,
) -> int:
    """Insert one ``semantic_documents`` row (embedding columns start NULL).

    Returns the new row id.
    """
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
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def update_semantic_document(
    conn: sqlite3.Connection,
    doc_id: int,
    *,
    source_table: str,
    doc_kind: str,
    title: str,
    body: str,
    content_hash: str,
    metadata_json: str,
    updated_at: str,
) -> None:
    """Update the content columns of one ``semantic_documents`` row."""
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
            doc_id,
        ),
    )


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------


def semantic_documents_for_source(
    conn: sqlite3.Connection, source_type: str, source_pk_prefix: str = ""
) -> list[sqlite3.Row]:
    """Rows (id, source_pk) for one source type, optionally prefix-scoped.

    *source_pk_prefix* restricts to rows whose ``source_pk`` begins with it —
    used to reconcile a single GitHub repo without touching other repos' rows.
    """
    if source_pk_prefix:
        return conn.execute(
            """
            SELECT id, source_pk
            FROM semantic_documents
            WHERE source_type = ? AND SUBSTR(source_pk, 1, ?) = ?
            """,
            (source_type, len(source_pk_prefix), source_pk_prefix),
        ).fetchall()
    return conn.execute(
        """
        SELECT id, source_pk
        FROM semantic_documents
        WHERE source_type = ?
        """,
        (source_type,),
    ).fetchall()


def delete_semantic_documents(
    conn: sqlite3.Connection, doc_ids: list[int]
) -> None:
    """Delete ``semantic_embeddings`` + ``semantic_documents`` rows for *doc_ids*."""
    try:
        conn.executemany(
            "DELETE FROM semantic_embeddings WHERE rowid = ?",
            [(doc_id,) for doc_id in doc_ids],
        )
    except sqlite3.OperationalError:
        pass  # vec0 unavailable (FTS-only / no sqlite-vec) — no embeddings to clear
    conn.executemany(
        "DELETE FROM semantic_documents WHERE id = ?",
        [(doc_id,) for doc_id in doc_ids],
    )


# ---------------------------------------------------------------------------
# Source-table reads (backfill inputs)
# ---------------------------------------------------------------------------


def vault_chunks_for_semantic(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Every vault chunk joined to its file — the input for the vault backfill."""
    return conn.execute(
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


def github_documents_for_semantic(
    conn: sqlite3.Connection,
    *,
    normalized_repo: str = "",
    ignored_repos: Sequence[str] = (),
) -> list[sqlite3.Row]:
    """GitHub documents joined to their item — the input for the GitHub backfill.

    With *normalized_repo* set, restricts to that one repo. Otherwise excludes
    every repo in *ignored_repos* (case-insensitive).
    """
    if normalized_repo:
        where_sql = "WHERE LOWER(gd.repo_full_name) = ?"
        params: tuple[str, ...] = (normalized_repo,)
    else:
        ignored_placeholders = ", ".join("?" for _ in ignored_repos)
        if ignored_placeholders:
            where_sql = f"WHERE LOWER(gd.repo_full_name) NOT IN ({ignored_placeholders})"
            params = tuple(sorted(ignored_repos))
        else:
            where_sql = ""
            params = ()

    return conn.execute(
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


def email_messages_for_semantic(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Every email message, newest first — the input for the email backfill."""
    return conn.execute(
        """
        SELECT message_id, thread_id, from_address, from_name, subject,
               snippet, received_at, labels_json, synced_at
        FROM email_messages
        ORDER BY received_at DESC
        """
    ).fetchall()


def figma_comments_for_semantic(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Every Figma comment, newest first — the input for the Figma backfill."""
    return conn.execute(
        """
        SELECT comment_key, file_key, comment_id, parent_id, message,
               user_id, user_handle, created_at, resolved_at, order_id,
               client_meta_json, reactions_json, synced_at
        FROM figma_comments
        ORDER BY created_at DESC
        """
    ).fetchall()


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------


def clear_semantic_embeddings(conn: sqlite3.Connection) -> None:
    """Drop every row from ``semantic_embeddings``."""
    conn.execute("DELETE FROM semantic_embeddings")


def reset_semantic_embedded_state(
    conn: sqlite3.Connection, source_types: Sequence[str] | None = None
) -> None:
    """Null out the embedding bookkeeping columns on ``semantic_documents``.

    Pass *source_types* to restrict the reset; omit it to reset every row.
    """
    if source_types is None:
        conn.execute(
            """
            UPDATE semantic_documents
            SET embedded_hash = NULL,
                embedded_model_version = NULL,
                embedded_at = NULL
            """
        )
        return
    placeholders = ", ".join("?" for _ in source_types)
    conn.execute(
        f"""
        UPDATE semantic_documents
        SET embedded_hash = NULL,
            embedded_model_version = NULL,
            embedded_at = NULL
        WHERE source_type IN ({placeholders})
        """,
        list(source_types),
    )


def semantic_doc_ids_for_sources(
    conn: sqlite3.Connection, source_types: Sequence[str]
) -> list[int]:
    """Ids of ``semantic_documents`` rows for the given source types."""
    placeholders = ", ".join("?" for _ in source_types)
    return [
        int(row["id"])
        for row in conn.execute(
            f"""
            SELECT id
            FROM semantic_documents
            WHERE source_type IN ({placeholders})
            """,
            list(source_types),
        ).fetchall()
    ]


def delete_semantic_embeddings_for_docs(
    conn: sqlite3.Connection, doc_ids: list[int]
) -> None:
    """Delete ``semantic_embeddings`` rows for the given document ids."""
    conn.executemany(
        "DELETE FROM semantic_embeddings WHERE rowid = ?",
        [(doc_id,) for doc_id in doc_ids],
    )


def semantic_documents_pending_embed(
    conn: sqlite3.Connection,
    source_types: Sequence[str],
    min_chars: int,
    model_version: str,
) -> list[sqlite3.Row]:
    """Rows (id, body, content_hash) for documents needing (re-)embedding.

    A document qualifies when its body is at least *min_chars* long and its
    embedding is missing or stale relative to ``content_hash`` / *model_version*.
    """
    placeholders = ", ".join("?" for _ in source_types)
    return conn.execute(
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
        [*source_types, min_chars, model_version],
    ).fetchall()


def count_embeddable_semantic_documents(
    conn: sqlite3.Connection, source_types: Sequence[str], min_chars: int
) -> int:
    """Count documents of the given source types whose body is long enough."""
    placeholders = ", ".join("?" for _ in source_types)
    return conn.execute(
        f"""
        SELECT COUNT(*)
        FROM semantic_documents
        WHERE source_type IN ({placeholders}) AND LENGTH(body) >= ?
        """,
        [*source_types, min_chars],
    ).fetchone()[0]


def delete_semantic_embedding(conn: sqlite3.Connection, doc_id: int) -> None:
    """Delete a single ``semantic_embeddings`` row by its rowid."""
    conn.execute("DELETE FROM semantic_embeddings WHERE rowid = ?", (doc_id,))


def insert_semantic_embedding(
    conn: sqlite3.Connection, doc_id: int, embedding: bytes
) -> None:
    """Insert one ``semantic_embeddings`` vector row."""
    conn.execute(
        "INSERT INTO semantic_embeddings (rowid, embedding) VALUES (?, ?)",
        (doc_id, embedding),
    )


def mark_semantic_document_embedded(
    conn: sqlite3.Connection, doc_id: int, model_version: str, embedded_at: str
) -> None:
    """Mark a document fresh: copy ``content_hash`` and stamp model/version/time."""
    conn.execute(
        """
        UPDATE semantic_documents
        SET embedded_hash = content_hash,
            embedded_model_version = ?,
            embedded_at = ?
        WHERE id = ?
        """,
        (model_version, embedded_at, doc_id),
    )


def set_semantic_embedding_meta(
    conn: sqlite3.Connection, key: str, value: str
) -> None:
    """Insert-or-replace one ``semantic_embedding_meta`` key/value row."""
    conn.execute(
        "INSERT OR REPLACE INTO semantic_embedding_meta (key, value) VALUES (?, ?)",
        (key, value),
    )


def count_orphaned_embeddings(conn: sqlite3.Connection) -> tuple[int, int]:
    """Count orphaned semantic_embeddings and estimate their wasted bytes.

    Returns (orphan_count, estimated_wasted_bytes).
    """
    try:
        count = conn.execute(
            """
            SELECT COUNT(*) FROM semantic_embeddings e
            WHERE NOT EXISTS (SELECT 1 FROM semantic_documents d WHERE d.id = e.rowid)
            """
        ).fetchone()[0]
        wasted = 0
        if count > 0:
            row = conn.execute(
                """
                SELECT LENGTH(embedding) FROM semantic_embeddings e
                WHERE NOT EXISTS (SELECT 1 FROM semantic_documents d WHERE d.id = e.rowid)
                LIMIT 1
                """
            ).fetchone()
            if row and row[0]:
                wasted = count * row[0]
        return count, wasted
    except sqlite3.OperationalError:
        return 0, 0


def count_unembedded_documents(
    conn: sqlite3.Connection,
    source_types: Sequence[str] | None,
    min_chars: int,
    model_version: str,
) -> int:
    """Count semantic_documents needing (re-)embedding."""
    if source_types is None:
        return conn.execute(
            """
            SELECT COUNT(*)
            FROM semantic_documents
            WHERE LENGTH(body) >= ?
              AND (
                    embedded_hash IS NULL
                 OR embedded_hash != content_hash
                 OR embedded_model_version IS NULL
                 OR embedded_model_version != ?
              )
            """,
            [min_chars, model_version],
        ).fetchone()[0]

    placeholders = ", ".join("?" for _ in source_types)
    return conn.execute(
        f"""
        SELECT COUNT(*)
        FROM semantic_documents
        WHERE source_type IN ({placeholders})
          AND LENGTH(body) >= ?
          AND (
                embedded_hash IS NULL
             OR embedded_hash != content_hash
             OR embedded_model_version IS NULL
             OR embedded_model_version != ?
          )
        """,
        [*source_types, min_chars, model_version],
    ).fetchone()[0]


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------


def search_semantic_documents(
    conn: sqlite3.Connection,
    query_vec: bytes,
    top_k: int,
    source_types: Sequence[str],
    *,
    updated_after: str | None = None,
    repo: str | None = None,
) -> list[sqlite3.Row]:
    """Vector search over ``semantic_embeddings``, nearest first.

    Args:
        source_types: Restrict to these source families (e.g. ["vault", "github"]).
        updated_after: ISO-8601 timestamp string; exclude docs updated before this.
        repo: Filter to a specific GitHub repo (``owner/name``); only applies to
              github-sourced documents whose metadata_json contains repo_full_name.
    """
    placeholders = ", ".join("?" for _ in source_types)
    params: list = [query_vec, top_k, *source_types]

    extra_clauses = []
    if updated_after:
        extra_clauses.append("AND sd.updated_at >= ?")
        params.append(updated_after)
    if repo:
        extra_clauses.append(
            "AND (sd.source_type != 'github' OR "
            "LOWER(JSON_EXTRACT(sd.metadata_json, '$.repo_full_name')) = LOWER(?))"
        )
        params.append(repo)

    extra_sql = "\n          ".join(extra_clauses)
    return conn.execute(
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
          {extra_sql}
        ORDER BY se.distance
        """,
        params,
    ).fetchall()


def _fts_match_query(query_text: str) -> str:
    """Turn a natural-language query into a safe FTS5 MATCH expression.

    Alphanumeric tokens (len ≥ 2), each double-quoted to neutralize FTS5 operator
    syntax, OR-ed for recall. Underscores are split (matching FTS5's unicode61
    tokenizer), so ``auth_log`` in the query becomes ``"auth" OR "log"`` and
    matches the same tokens the content was indexed under.
    """
    tokens = re.findall(r"[A-Za-z0-9]{2,}", query_text or "")
    if not tokens:
        return ""
    # de-dupe while preserving order, cap to keep the MATCH expression bounded
    seen: dict[str, None] = {}
    for t in tokens:
        seen.setdefault(t.lower(), None)
    return " OR ".join(f'"{t}"' for t in list(seen)[:24])


def search_semantic_documents_fts(
    conn: sqlite3.Connection,
    query_text: str,
    top_k: int,
    source_types: Sequence[str],
    *,
    updated_after: str | None = None,
    repo: str | None = None,
) -> list[sqlite3.Row]:
    """Lexical (FTS5) search over title+body, best (lowest bm25) first.

    Same column shape as :func:`search_semantic_documents` so the two can be
    fused uniformly — ``distance`` is NULL here; ``fts_rank`` carries the bm25
    score. Returns ``[]`` if the query has no usable terms or FTS5 is missing.
    """
    match = _fts_match_query(query_text)
    if not match:
        return []

    placeholders = ", ".join("?" for _ in source_types)
    params: list = [match, *source_types]

    extra_clauses = []
    if updated_after:
        extra_clauses.append("AND sd.updated_at >= ?")
        params.append(updated_after)
    if repo:
        extra_clauses.append(
            "AND (sd.source_type != 'github' OR "
            "LOWER(JSON_EXTRACT(sd.metadata_json, '$.repo_full_name')) = LOWER(?))"
        )
        params.append(repo)
    params.append(top_k)
    extra_sql = "\n          ".join(extra_clauses)

    try:
        return conn.execute(
            f"""
            SELECT
                sd.id AS doc_id,
                NULL AS distance,
                sd.source_type,
                sd.source_table,
                sd.source_pk,
                sd.doc_kind,
                sd.title,
                SUBSTR(sd.body, 1, 400) AS body_preview,
                sd.metadata_json,
                sd.updated_at,
                bm25(semantic_documents_fts) AS fts_rank
            FROM semantic_documents_fts
            JOIN semantic_documents sd ON sd.id = semantic_documents_fts.rowid
            WHERE semantic_documents_fts MATCH ?
              AND sd.source_type IN ({placeholders})
              {extra_sql}
            ORDER BY fts_rank
            LIMIT ?
            """,
            params,
        ).fetchall()
    except sqlite3.DatabaseError:
        return []  # FTS5 unavailable or malformed match → ANN-only upstream

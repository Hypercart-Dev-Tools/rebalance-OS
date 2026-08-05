"""Typed query helpers for the ``github_*`` tables.

These keep raw SQL out of the CLI and ingest modules — callers work with
plain Python values and let this module own the column layout. Upsert
helpers take the value tuple in the documented column order (``github_items``
takes a column-keyed dict, bound by name, since it has 35 columns).
"""

from __future__ import annotations

import sqlite3
from typing import Any


# ---------------------------------------------------------------------------
# Activity queries
# ---------------------------------------------------------------------------


def top_active_repos(
    conn: sqlite3.Connection, top_n: int, since_days: int = 7
) -> list[str]:
    """Repo full-names ranked by recent activity score, highest first.

    Score sums ``commits + prs_opened + prs_merged + issues_opened +
    issue_comments + reviews`` over the trailing *since_days* window
    (``github_activity.scan_date``). Repos with a zero score are excluded.
    """
    rows = conn.execute(
        """
        SELECT repo_full_name,
               SUM(commits) + SUM(prs_opened) + SUM(prs_merged) +
               SUM(issues_opened) + SUM(issue_comments) + SUM(reviews) AS score
        FROM github_activity
        WHERE scan_date >= date('now', ?)
        GROUP BY repo_full_name
        HAVING score > 0
        ORDER BY score DESC
        LIMIT ?
        """,
        (f"-{since_days} days", top_n),
    ).fetchall()
    return [r[0] for r in rows]


def repo_last_active(
    conn: sqlite3.Connection, repos: list[str] | None = None
) -> dict[str, str]:
    """Map of ``repo_full_name`` -> latest ``last_active_at`` (raw ISO string).

    Pass *repos* to restrict to a subset; omit it for every repo. Repos with
    no non-null ``last_active_at`` are omitted. Timestamp parsing is left to
    the caller — this helper only touches the database.
    """
    if repos is not None:
        if not repos:
            return {}
        placeholders = ",".join("?" * len(repos))
        rows = conn.execute(
            f"SELECT repo_full_name, MAX(last_active_at) FROM github_activity "
            f"WHERE repo_full_name IN ({placeholders}) "
            f"AND last_active_at IS NOT NULL "
            f"GROUP BY repo_full_name",
            list(repos),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT repo_full_name, MAX(last_active_at) FROM github_activity "
            "WHERE last_active_at IS NOT NULL GROUP BY repo_full_name"
        ).fetchall()
    return {r[0]: r[1] for r in rows}


def repo_meta_names(conn: sqlite3.Connection) -> set[str]:
    """Set of ``repo_full_name`` values present in ``github_repo_meta``.

    This is the canonical "fully synced" watched set — a repo only gets a
    ``github_repo_meta`` row after a complete artifact sync.
    """
    return {r[0] for r in conn.execute("SELECT repo_full_name FROM github_repo_meta")}


# ---------------------------------------------------------------------------
# Artifact upserts — one helper per github_* table; this module owns the
# column layout so ingest code never embeds INSERT SQL.
# ---------------------------------------------------------------------------


def upsert_repo_meta(conn: sqlite3.Connection, values: tuple) -> None:
    """Insert-or-replace one ``github_repo_meta`` row.

    *values*: repo_full_name, default_branch, pushed_at, updated_at,
    open_issues_count, has_issues, has_projects, fetched_at.
    """
    conn.execute(
        """
        INSERT OR REPLACE INTO github_repo_meta
            (repo_full_name, default_branch, pushed_at, updated_at, open_issues_count,
             has_issues, has_projects, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        values,
    )


def upsert_branch(conn: sqlite3.Connection, values: tuple) -> None:
    """Insert-or-replace one ``github_branches`` row.

    *values*: repo_full_name, name, head_sha, is_protected, is_default, fetched_at.
    """
    conn.execute(
        """
        INSERT OR REPLACE INTO github_branches
            (repo_full_name, name, head_sha, is_protected, is_default, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        values,
    )


def upsert_label(conn: sqlite3.Connection, values: tuple) -> None:
    """Insert-or-replace one ``github_labels`` row.

    *values*: repo_full_name, name, color, description, is_default.
    """
    conn.execute(
        """
        INSERT OR REPLACE INTO github_labels
            (repo_full_name, name, color, description, is_default)
        VALUES (?, ?, ?, ?, ?)
        """,
        values,
    )


def upsert_milestone(conn: sqlite3.Connection, values: tuple) -> None:
    """Insert-or-replace one ``github_milestones`` row.

    *values*: repo_full_name, number, title, description, state, open_issues,
    closed_issues, due_on, created_at, updated_at, closed_at, html_url.
    """
    conn.execute(
        """
        INSERT OR REPLACE INTO github_milestones
            (repo_full_name, number, title, description, state, open_issues,
             closed_issues, due_on, created_at, updated_at, closed_at, html_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        values,
    )


def upsert_release(conn: sqlite3.Connection, values: tuple) -> None:
    """Insert-or-replace one ``github_releases`` row.

    *values*: repo_full_name, github_id, tag_name, name, target_commitish,
    is_draft, is_prerelease, body, created_at, published_at, html_url.
    """
    conn.execute(
        """
        INSERT OR REPLACE INTO github_releases
            (repo_full_name, github_id, tag_name, name, target_commitish, is_draft,
             is_prerelease, body, created_at, published_at, html_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        values,
    )


def upsert_item(conn: sqlite3.Connection, record: dict[str, Any]) -> None:
    """Insert-or-replace one ``github_items`` row from a column-keyed dict.

    Bound by name — *record* must carry every github_items column as a key.
    Extra keys are ignored by sqlite3. Named binding (rather than positional)
    removes any dependence on dict iteration order.
    """
    conn.execute(
        """
        INSERT OR REPLACE INTO github_items
            (repo_full_name, item_type, number, node_id, github_id, title, body, state,
             state_reason, author_login, assignees_json, labels_json, milestone_number,
             milestone_title, is_draft, is_merged, base_ref, head_ref, head_sha,
             mergeable_state, review_decision, check_status, requested_reviewers_json,
             comments_count, review_comments_count, commits_count, additions, deletions,
             changed_files, html_url, created_at, updated_at, closed_at, merged_at, fetched_at)
        VALUES (:repo_full_name, :item_type, :number, :node_id, :github_id, :title, :body,
                :state, :state_reason, :author_login, :assignees_json, :labels_json,
                :milestone_number, :milestone_title, :is_draft, :is_merged, :base_ref,
                :head_ref, :head_sha, :mergeable_state, :review_decision, :check_status,
                :requested_reviewers_json, :comments_count, :review_comments_count,
                :commits_count, :additions, :deletions, :changed_files, :html_url,
                :created_at, :updated_at, :closed_at, :merged_at, :fetched_at)
        """,
        record,
    )


def upsert_comment(conn: sqlite3.Connection, values: tuple) -> None:
    """Insert-or-replace one ``github_comments`` row.

    *values*: repo_full_name, item_type, item_number, comment_type,
    github_comment_id, author_login, author_association, body, review_state,
    in_reply_to_id, html_url, created_at, updated_at, fetched_at.
    """
    conn.execute(
        """
        INSERT OR REPLACE INTO github_comments
            (repo_full_name, item_type, item_number, comment_type, github_comment_id,
             author_login, author_association, body, review_state, in_reply_to_id,
             html_url, created_at, updated_at, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        values,
    )


def upsert_link(conn: sqlite3.Connection, values: tuple) -> None:
    """Insert-or-replace one ``github_links`` row.

    *values*: repo_full_name, source_type, source_number, target_type,
    target_number, link_kind.
    """
    conn.execute(
        """
        INSERT OR REPLACE INTO github_links
            (repo_full_name, source_type, source_number, target_type, target_number, link_kind)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        values,
    )


def upsert_commit(conn: sqlite3.Connection, values: tuple) -> None:
    """Insert-or-replace one ``github_commits`` row.

    *values*: repo_full_name, item_type, item_number, sha, author_login,
    message, committed_at, html_url, fetched_at.
    """
    conn.execute(
        """
        INSERT OR REPLACE INTO github_commits
            (repo_full_name, item_type, item_number, sha, author_login,
             message, committed_at, html_url, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        values,
    )


def insert_push_event(conn: sqlite3.Connection, values: tuple) -> bool:
    """Insert one direct-push receipt; return whether it was newly observed."""
    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO github_push_events
            (event_id, repo_full_name, ref, before_sha, head_sha, observed_at,
             state, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
        """,
        values,
    )
    return cursor.rowcount == 1


def pending_push_events(
    conn: sqlite3.Connection, limit: int, max_attempts: int
) -> list[sqlite3.Row]:
    """Oldest direct-push receipts still requiring bounded enrichment."""
    return conn.execute(
        """
        SELECT event_id, repo_full_name, ref, before_sha, head_sha, observed_at,
               state, attempt_count
        FROM github_push_events
        WHERE state IN ('pending', 'deferred') AND attempt_count < ?
        ORDER BY observed_at ASC, event_id ASC
        LIMIT ?
        """,
        (max_attempts, limit),
    ).fetchall()


def update_push_event(
    conn: sqlite3.Connection,
    event_id: str,
    *,
    state: str,
    now: str,
    reason: str = "",
    deferral_kind: str | None = None,
) -> None:
    """Advance a receipt state without hiding its prior observation.

    ``attempt_count`` counts ATTEMPTS, not visits (GH-169). A deferral with
    ``deferral_kind='budget'`` means the run exhausted its own per-refresh cap
    before reaching this event — nothing was tried, so nothing is charged.

    The previous unconditional ``attempt_count + 1`` charged those too, and
    ``pending_push_events()`` filters ``attempt_count < MAX_EVENT_ATTEMPTS``.
    An event that merely lost the cap lottery three times was therefore evicted
    permanently, never fetched, and never reported as lost — 20 real events on
    the live DB, every one of them for "compare cap reached". Genuine failures
    still cost an attempt, so a non-retryable error still stops retrying.
    """
    charge = 0 if deferral_kind == "budget" else 1
    conn.execute(
        """
        UPDATE github_push_events
        SET state = ?, attempt_count = attempt_count + ?, last_attempt_at = ?,
            resolved_at = CASE WHEN ? IN ('enriched', 'ignored', 'head_only', 'failed')
                               THEN ? ELSE resolved_at END,
            failure_reason = ?,
            deferral_kind = ?
        WHERE event_id = ?
        """,
        (state, charge, now, state, now, reason[:500] or None, deferral_kind, event_id),
    )


def upsert_direct_commit(
    conn: sqlite3.Connection, values: tuple, *, source: str = "events"
) -> None:
    """Insert-or-replace a direct commit while retaining its event provenance.

    ``path_coverage`` is RATCHETED, never assigned (GH-169): it may only move
    ``unavailable -> complete``. The previous unconditional
    ``path_coverage=excluded.path_coverage`` meant a later cap-starved API pass
    — which writes ``unavailable`` when it runs out of detail budget — could
    silently *downgrade* a row that already had a full file list, turning
    collected data back into a gap. That is what makes backfill-then-enrich
    ordering safe: whichever path runs second cannot destroy the other's work.
    """
    conn.execute(
        """
        INSERT INTO github_direct_commits
            (repo_full_name, sha, event_id, ref, author_login, author_name,
             message, committed_at, html_url, path_coverage, discovered_at,
             fetched_at, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(repo_full_name, sha) DO UPDATE SET
            event_id=excluded.event_id, ref=excluded.ref,
            author_login=excluded.author_login, author_name=excluded.author_name,
            message=excluded.message, committed_at=excluded.committed_at,
            html_url=excluded.html_url,
            path_coverage=CASE
                WHEN github_direct_commits.path_coverage = 'complete' THEN 'complete'
                ELSE excluded.path_coverage
            END,
            source=CASE
                WHEN github_direct_commits.path_coverage = 'complete'
                     THEN github_direct_commits.source
                ELSE excluded.source
            END,
            fetched_at=excluded.fetched_at
        """,
        (*values, source),
    )


def replace_direct_commit_files(
    conn: sqlite3.Connection, repo_full_name: str, sha: str, files: list[dict[str, object]]
) -> None:
    """Replace the exact file list for one direct commit atomically."""
    conn.execute(
        "DELETE FROM github_direct_commit_files WHERE repo_full_name = ? AND sha = ?",
        (repo_full_name, sha),
    )
    conn.executemany(
        """
        INSERT INTO github_direct_commit_files
            (repo_full_name, sha, path, status, additions, deletions, changes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                repo_full_name, sha, str(row.get("filename") or ""),
                str(row.get("status") or ""), row.get("additions"),
                row.get("deletions"), row.get("changes"),
            )
            for row in files
            if row.get("filename")
        ],
    )


def upsert_check_run(conn: sqlite3.Connection, values: tuple) -> None:
    """Insert-or-replace one ``github_check_runs`` row.

    *values*: repo_full_name, item_type, item_number, head_sha, name, status,
    conclusion, details_url, started_at, completed_at, fetched_at.
    """
    conn.execute(
        """
        INSERT OR REPLACE INTO github_check_runs
            (repo_full_name, item_type, item_number, head_sha, name, status,
             conclusion, details_url, started_at, completed_at, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        values,
    )


def delete_repo_table(
    conn: sqlite3.Connection, table: str, repo_full_name: str
) -> None:
    """Delete every row of *table* for an exact ``repo_full_name`` match.

    Used to clear branches/labels/milestones/releases before a fresh sync.
    *table* must be a trusted constant — it is interpolated, not bound.
    """
    conn.execute(f"DELETE FROM {table} WHERE repo_full_name = ?", (repo_full_name,))


# ---------------------------------------------------------------------------
# Document corpus
# ---------------------------------------------------------------------------


def insert_github_document(
    conn: sqlite3.Connection,
    *,
    repo_full_name: str,
    source_type: str,
    source_number: int,
    doc_type: str,
    source_key: str,
    title: str,
    body: str,
    content_hash: str,
    updated_at: str,
    fetched_at: str,
) -> int:
    """Insert one ``github_documents`` row (``embedded_hash`` starts NULL).

    Returns the new row id. Content hashing is the caller's job — pass the
    precomputed *content_hash*.
    """
    conn.execute(
        """
        INSERT INTO github_documents
            (repo_full_name, source_type, source_number, doc_type, source_key,
             title, body, content_hash, embedded_hash, updated_at, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
        """,
        (
            repo_full_name,
            source_type,
            source_number,
            doc_type,
            source_key,
            title,
            body,
            content_hash,
            updated_at,
            fetched_at,
        ),
    )
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def upsert_github_document(
    conn: sqlite3.Connection,
    *,
    repo_full_name: str,
    source_type: str,
    source_number: int,
    doc_type: str,
    source_key: str,
    title: str,
    body: str,
    content_hash: str,
    updated_at: str,
    fetched_at: str,
) -> int:
    """Insert or update a ``github_documents`` row, preserving ``embedded_hash`` if unchanged.

    Returns the new or existing row id.
    """
    cursor = conn.execute(
        """
        INSERT INTO github_documents
            (repo_full_name, source_type, source_number, doc_type, source_key,
             title, body, content_hash, embedded_hash, updated_at, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
        ON CONFLICT(source_key) DO UPDATE SET
            repo_full_name=excluded.repo_full_name,
            source_type=excluded.source_type,
            source_number=excluded.source_number,
            doc_type=excluded.doc_type,
            title=excluded.title,
            body=excluded.body,
            embedded_hash=NULL,
            content_hash=excluded.content_hash,
            updated_at=excluded.updated_at,
            fetched_at=excluded.fetched_at
        WHERE github_documents.content_hash != excluded.content_hash
        RETURNING id
        """,
        (
            repo_full_name,
            source_type,
            source_number,
            doc_type,
            source_key,
            title,
            body,
            content_hash,
            updated_at,
            fetched_at,
        ),
    )
    row = cursor.fetchone()
    if row is not None:
        return int(row[0])
    return int(conn.execute(
        "SELECT id FROM github_documents WHERE source_key = ?",
        (source_key,)
    ).fetchone()[0])


def delete_item_children(
    conn: sqlite3.Connection,
    repo_full_name: str,
    item_type: str,
    item_number: int,
) -> None:
    """Delete one item's derived rows (documents, embeddings, comments,
    commits, check runs, links) before the item is re-synced."""
    doc_ids = [
        row["id"]
        for row in conn.execute(
            """
            SELECT id
            FROM github_documents
            WHERE repo_full_name = ? AND source_type = ? AND source_number = ?
            """,
            (repo_full_name, item_type, item_number),
        ).fetchall()
    ]
    if doc_ids:
        conn.executemany(
            "DELETE FROM github_embeddings WHERE doc_id = ?",
            [(doc_id,) for doc_id in doc_ids],
        )
    conn.execute(
        """
        DELETE FROM github_documents
        WHERE repo_full_name = ? AND source_type = ? AND source_number = ?
        """,
        (repo_full_name, item_type, item_number),
    )
    conn.execute(
        """
        DELETE FROM github_comments
        WHERE repo_full_name = ? AND item_type = ? AND item_number = ?
        """,
        (repo_full_name, item_type, item_number),
    )
    conn.execute(
        """
        DELETE FROM github_commits
        WHERE repo_full_name = ? AND item_type = ? AND item_number = ?
        """,
        (repo_full_name, item_type, item_number),
    )
    conn.execute(
        """
        DELETE FROM github_check_runs
        WHERE repo_full_name = ? AND item_type = ? AND item_number = ?
        """,
        (repo_full_name, item_type, item_number),
    )
    conn.execute(
        """
        DELETE FROM github_links
        WHERE repo_full_name = ? AND source_type = ? AND source_number = ?
        """,
        (repo_full_name, item_type, item_number),
    )


def search_github_documents(
    conn: sqlite3.Connection,
    query_vec: bytes,
    top_k: int,
    repo_full_name: str = "",
) -> list[sqlite3.Row]:
    """Vector search over ``github_embeddings``, nearest first.

    Returns raw rows joined to ``github_documents`` and (left) ``github_items``.
    Pass *repo_full_name* to restrict results to a single repo.
    """
    repo = repo_full_name.strip()
    base = """
        SELECT
            ge.doc_id,
            ge.distance,
            gd.repo_full_name,
            gd.source_type,
            gd.source_number,
            gd.doc_type,
            gd.title,
            SUBSTR(gd.body, 1, 400) AS body_preview,
            gi.state,
            gi.milestone_title,
            gi.labels_json,
            gi.review_decision,
            gi.check_status,
            gi.html_url
        FROM github_embeddings ge
        JOIN github_documents gd ON gd.id = ge.doc_id
        LEFT JOIN github_items gi
          ON gi.repo_full_name = gd.repo_full_name
         AND gi.item_type = gd.source_type
         AND gi.number = gd.source_number
        WHERE ge.embedding MATCH ? AND ge.k = ?{repo_clause}
        ORDER BY ge.distance
    """
    if repo:
        sql = base.format(repo_clause=" AND gd.repo_full_name = ?")
        return conn.execute(sql, (query_vec, top_k, repo)).fetchall()
    sql = base.format(repo_clause="")
    return conn.execute(sql, (query_vec, top_k)).fetchall()


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------


def clear_github_embeddings(conn: sqlite3.Connection) -> None:
    """Drop every row from ``github_embeddings`` (used by force-reembed)."""
    conn.execute("DELETE FROM github_embeddings")


def reset_github_embedded_hashes(conn: sqlite3.Connection) -> None:
    """Null out every ``github_documents.embedded_hash`` (used by force-reembed)."""
    conn.execute("UPDATE github_documents SET embedded_hash = NULL")


def github_documents_pending_embed(
    conn: sqlite3.Connection, min_chars: int
) -> list[sqlite3.Row]:
    """Rows (id, body, content_hash) for documents needing (re-)embedding.

    A document qualifies when its body is at least *min_chars* long and its
    ``embedded_hash`` is missing or stale relative to ``content_hash``.
    """
    return conn.execute(
        """
        SELECT id, body, content_hash
        FROM github_documents
        WHERE LENGTH(body) >= ?
          AND (embedded_hash IS NULL OR embedded_hash != content_hash)
        ORDER BY id
        """,
        (min_chars,),
    ).fetchall()


def count_embeddable_github_documents(
    conn: sqlite3.Connection, min_chars: int
) -> int:
    """Count documents whose body is at least *min_chars* long."""
    return conn.execute(
        "SELECT COUNT(*) FROM github_documents WHERE LENGTH(body) >= ?",
        (min_chars,),
    ).fetchone()[0]


def upsert_github_embedding(
    conn: sqlite3.Connection, doc_id: int, embedding: bytes
) -> None:
    """Insert-or-replace one ``github_embeddings`` vector row."""
    conn.execute("DELETE FROM github_embeddings WHERE doc_id = ?", (doc_id,))
    conn.execute(
        "INSERT INTO github_embeddings (doc_id, embedding) VALUES (?, ?)",
        (doc_id, embedding),
    )


def mark_github_document_embedded(conn: sqlite3.Connection, doc_id: int) -> None:
    """Mark a document fresh by copying ``content_hash`` into ``embedded_hash``."""
    conn.execute(
        "UPDATE github_documents SET embedded_hash = content_hash WHERE id = ?",
        (doc_id,),
    )


def set_github_embedding_meta(
    conn: sqlite3.Connection, key: str, value: str
) -> None:
    """Insert-or-replace one ``github_embedding_meta`` key/value row."""
    conn.execute(
        "INSERT OR REPLACE INTO github_embedding_meta (key, value) VALUES (?, ?)",
        (key, value),
    )


def count_orphaned_embeddings(conn: sqlite3.Connection) -> tuple[int, int]:
    """Count orphaned github_embeddings and estimate their wasted bytes.

    Returns (orphan_count, estimated_wasted_bytes).
    """
    count = conn.execute(
        """
        SELECT COUNT(*) FROM github_embeddings e
        WHERE NOT EXISTS (SELECT 1 FROM github_documents d WHERE d.id = e.doc_id)
        """
    ).fetchone()[0]
    wasted = 0
    if count > 0:
        row = conn.execute(
            """
            SELECT LENGTH(embedding) FROM github_embeddings e
            WHERE NOT EXISTS (SELECT 1 FROM github_documents d WHERE d.id = e.doc_id)
            LIMIT 1
            """
        ).fetchone()
        if row and row[0]:
            wasted = count * row[0]
    return count, wasted


def count_unembedded_documents(conn: sqlite3.Connection, min_chars: int) -> int:
    """Count github_documents needing (re-)embedding."""
    return conn.execute(
        """
        SELECT COUNT(*)
        FROM github_documents
        WHERE LENGTH(body) >= ?
          AND (embedded_hash IS NULL OR embedded_hash != content_hash)
        """,
        (min_chars,),
    ).fetchone()[0]


def table_byte_size(conn: sqlite3.Connection, table_name: str) -> int:
    """Return the total byte size of a table using dbstat."""
    try:
        return conn.execute(
            "SELECT SUM(pgsize) FROM dbstat WHERE name LIKE ?", (f"{table_name}%",)
        ).fetchone()[0] or 0
    except sqlite3.OperationalError:
        return 0


# ---------------------------------------------------------------------------
# Per-repo purge
# ---------------------------------------------------------------------------


def count_repo_rows(
    conn: sqlite3.Connection, table: str, repo_name_lower: str
) -> int:
    """Count rows of *table* for a case-insensitive ``repo_full_name`` match.

    *table* must be a trusted constant — it is interpolated, not bound.
    """
    return conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE LOWER(repo_full_name) = ?",
        (repo_name_lower,),
    ).fetchone()[0]


def delete_repo_rows(
    conn: sqlite3.Connection, table: str, repo_name_lower: str
) -> None:
    """Delete rows of *table* for a case-insensitive ``repo_full_name`` match.

    *table* must be a trusted constant — it is interpolated, not bound.
    """
    conn.execute(
        f"DELETE FROM {table} WHERE LOWER(repo_full_name) = ?",
        (repo_name_lower,),
    )


def github_document_ids(
    conn: sqlite3.Connection, repo_name_lower: str
) -> list[int]:
    """Ids of ``github_documents`` for a case-insensitive repo match."""
    return [
        int(row["id"])
        for row in conn.execute(
            "SELECT id FROM github_documents WHERE LOWER(repo_full_name) = ?",
            (repo_name_lower,),
        ).fetchall()
    ]


def semantic_doc_ids_for_github_repo(
    conn: sqlite3.Connection, repo_name_lower: str
) -> list[int]:
    """Ids of ``semantic_documents`` projected from one GitHub repo's docs."""
    return [
        int(row["id"])
        for row in conn.execute(
            """
            SELECT sd.id
            FROM semantic_documents sd
            JOIN github_documents gd ON gd.source_key = sd.source_pk
            WHERE sd.source_type = 'github'
              AND LOWER(gd.repo_full_name) = ?
            """,
            (repo_name_lower,),
        ).fetchall()
    ]


def count_ids_in(
    conn: sqlite3.Connection, table: str, id_column: str, ids: list[int]
) -> int:
    """Count rows of *table* whose *id_column* is in *ids* (0 for an empty list).

    *table* and *id_column* must be trusted constants — interpolated, not bound.
    """
    if not ids:
        return 0
    placeholders = ", ".join("?" for _ in ids)
    return conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE {id_column} IN ({placeholders})",
        list(ids),
    ).fetchone()[0]


def delete_github_embeddings_for_docs(
    conn: sqlite3.Connection, doc_ids: list[int]
) -> None:
    """Delete ``github_embeddings`` rows for the given document ids."""
    conn.executemany(
        "DELETE FROM github_embeddings WHERE doc_id = ?",
        [(doc_id,) for doc_id in doc_ids],
    )


def delete_github_documents(conn: sqlite3.Connection, doc_ids: list[int]) -> None:
    """Delete vectors and then documents for the given document ids."""
    if not doc_ids:
        return
    delete_github_embeddings_for_docs(conn, doc_ids)
    for i in range(0, len(doc_ids), 900):
        chunk = doc_ids[i:i + 900]
        conn.executemany(
            "DELETE FROM github_documents WHERE id = ?",
            [(doc_id,) for doc_id in chunk],
        )

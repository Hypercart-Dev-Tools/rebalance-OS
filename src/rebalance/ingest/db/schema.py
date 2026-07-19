"""All CREATE TABLE statements for rebalance, grouped by source.

Keeping every DDL statement in one module means the full DB shape is visible
in one place; individual modules call the appropriate ``ensure_*_schema()``
function (or use the ``db_connection`` context manager) rather than carrying
their own DDL.
"""

from __future__ import annotations

import sqlite3


# ---------------------------------------------------------------------------
# Vault schemas (notes, chunks, keywords, links, embeddings)
# ---------------------------------------------------------------------------


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create all vault ingestion and embedding tables if they don't exist."""

    conn.execute("""
        CREATE TABLE IF NOT EXISTS vault_files (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            rel_path        TEXT    NOT NULL UNIQUE,
            title           TEXT,
            content_hash    TEXT    NOT NULL,
            frontmatter_json TEXT,
            tags_json       TEXT,
            ingested_at     TEXT    NOT NULL,
            file_size_bytes INTEGER NOT NULL DEFAULT 0,
            last_modified   TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id         INTEGER NOT NULL REFERENCES vault_files(id) ON DELETE CASCADE,
            chunk_index     INTEGER NOT NULL,
            heading         TEXT,
            heading_level   INTEGER,
            body            TEXT    NOT NULL,
            char_count      INTEGER NOT NULL DEFAULT 0,
            content_hash    TEXT    NOT NULL,
            UNIQUE(file_id, chunk_index)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS keywords (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            chunk_id        INTEGER NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
            keyword         TEXT    NOT NULL,
            tf_idf_score    REAL    NOT NULL DEFAULT 0.0,
            UNIQUE(chunk_id, keyword)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_keywords_keyword ON keywords(keyword)")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS links (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file_id  INTEGER NOT NULL REFERENCES vault_files(id) ON DELETE CASCADE,
            target_title    TEXT    NOT NULL,
            link_type       TEXT    NOT NULL DEFAULT 'wikilink',
            context_chunk_id INTEGER REFERENCES chunks(id) ON DELETE SET NULL,
            UNIQUE(source_file_id, target_title, link_type)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_links_target ON links(target_title)")

    try:
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS embeddings USING vec0(
                chunk_id INTEGER PRIMARY KEY,
                embedding float[1024]
            )
        """)
    except sqlite3.DatabaseError:
        pass

    conn.execute("""
        CREATE TABLE IF NOT EXISTS embedding_meta (
            key     TEXT PRIMARY KEY,
            value   TEXT NOT NULL
        )
    """)

    conn.commit()


# ---------------------------------------------------------------------------
# Unified semantic index schema
# ---------------------------------------------------------------------------


def ensure_semantic_schema(conn: sqlite3.Connection) -> None:
    """Create derived cross-source semantic index tables if they don't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS semantic_documents (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type             TEXT    NOT NULL,
            source_table            TEXT    NOT NULL,
            source_pk               TEXT    NOT NULL,
            doc_kind                TEXT    NOT NULL,
            title                   TEXT,
            body                    TEXT    NOT NULL,
            content_hash            TEXT    NOT NULL,
            embedded_hash           TEXT,
            embedded_model_version  TEXT,
            embedded_at             TEXT,
            metadata_json           TEXT,
            created_at              TEXT    NOT NULL,
            updated_at              TEXT    NOT NULL,
            UNIQUE(source_type, source_pk)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_semantic_docs_source "
        "ON semantic_documents(source_type, updated_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_semantic_docs_source_table "
        "ON semantic_documents(source_type, source_table)"
    )
    try:
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS semantic_embeddings USING vec0(
                embedding float[1024]
            )
        """)
    except sqlite3.DatabaseError:
        pass

    conn.execute("""
        CREATE TABLE IF NOT EXISTS semantic_embedding_meta (
            key     TEXT PRIMARY KEY,
            value   TEXT NOT NULL
        )
    """)

    # Phase 1 hybrid retrieval: an FTS5 lexical index over title+body, beside the
    # vec0 ANN index. A standalone FTS5 table (keeps its own copy of title+body —
    # robust, vs the external-content variant whose backfill proved flaky here),
    # kept in sync with semantic_documents by triggers and joined back on
    # ``rowid = semantic_documents.id``. Fused with the vector ranking via RRF in
    # semantic_index.query(). Degrades to ANN-only if FTS5 is unavailable.
    #
    # Lives in ensure (not a numbered migration) by design — it is a self-healing
    # derived index and the read path (query()) opens the DB without migrations.
    # This is the documented virtual-index exception; see db/migrations/README.md.
    # Bump FTS_VERSION to force a clean drop+rebuild of the FTS table on every DB
    # (e.g. if its definition changes). Guards against a stale/incompatible FTS
    # table that an older code path may have left with rows but an empty index.
    FTS_VERSION = "1"
    try:
        _row = conn.execute(
            "SELECT value FROM semantic_embedding_meta WHERE key='fts_version'"
        ).fetchone()
        if (_row[0] if _row else None) != FTS_VERSION:
            conn.execute("DROP TABLE IF EXISTS semantic_documents_fts")
            for _t in ("ai", "ad", "au"):
                conn.execute(f"DROP TRIGGER IF EXISTS semantic_documents_fts_{_t}")
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS semantic_documents_fts USING fts5(title, body)"
        )
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS semantic_documents_fts_ai
            AFTER INSERT ON semantic_documents BEGIN
                INSERT INTO semantic_documents_fts(rowid, title, body)
                VALUES (new.id, new.title, new.body);
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS semantic_documents_fts_ad
            AFTER DELETE ON semantic_documents BEGIN
                DELETE FROM semantic_documents_fts WHERE rowid = old.id;
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS semantic_documents_fts_au
            AFTER UPDATE ON semantic_documents BEGIN
                DELETE FROM semantic_documents_fts WHERE rowid = old.id;
                INSERT INTO semantic_documents_fts(rowid, title, body)
                VALUES (new.id, new.title, new.body);
            END
        """)
        # One-time backfill for DBs that already had documents before the FTS
        # table existed (triggers only catch writes from here on).
        fts_n = conn.execute("SELECT count(*) FROM semantic_documents_fts").fetchone()[0]
        doc_n = conn.execute("SELECT count(*) FROM semantic_documents").fetchone()[0]
        if fts_n == 0 and doc_n > 0:
            conn.execute(
                "INSERT INTO semantic_documents_fts(rowid, title, body) "
                "SELECT id, title, body FROM semantic_documents"
            )
        conn.execute(
            "INSERT OR REPLACE INTO semantic_embedding_meta(key, value) VALUES('fts_version', ?)",
            (FTS_VERSION,),
        )
    except sqlite3.DatabaseError:
        pass  # FTS5 not compiled in — hybrid retrieval falls back to ANN-only

    conn.commit()


# ---------------------------------------------------------------------------
# Calendar schema
# ---------------------------------------------------------------------------


def ensure_calendar_schema(conn: sqlite3.Connection) -> None:
    """Create calendar_events table if it doesn't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS calendar_events (
            id              TEXT PRIMARY KEY,
            summary         TEXT,
            start_time      TEXT NOT NULL,
            end_time        TEXT,
            location        TEXT,
            attendees_json  TEXT,
            calendar_id     TEXT NOT NULL DEFAULT 'primary',
            status          TEXT,
            description     TEXT,
            fetched_at      TEXT NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_calendar_start ON calendar_events(start_time)"
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Email schema
# ---------------------------------------------------------------------------


def ensure_email_schema(conn: sqlite3.Connection) -> None:
    """Create email_messages table if it doesn't exist.

    Phase 1 stores metadata + Gmail-provided snippet only — no MIME body
    parsing. ``message_id`` is Gmail's globally unique id; ``INSERT OR
    REPLACE`` keyed on this PK gives upsert behavior across runs.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS email_messages (
            message_id      TEXT PRIMARY KEY,
            thread_id       TEXT,
            from_address    TEXT,
            from_name       TEXT,
            subject         TEXT,
            snippet         TEXT,
            received_at     TEXT,
            labels_json     TEXT,
            synced_at       TEXT NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_email_received ON email_messages(received_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_email_thread ON email_messages(thread_id)"
    )
    conn.commit()


# ---------------------------------------------------------------------------
# GitHub activity schema
# ---------------------------------------------------------------------------


def _ensure_github_activity_schema(conn: sqlite3.Connection) -> None:
    """Daily per-repo/login activity rollups (powers ``github_balance``)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS github_activity (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            login           TEXT    NOT NULL,
            repo_full_name  TEXT    NOT NULL,
            scan_date       TEXT    NOT NULL,
            commits         INTEGER NOT NULL DEFAULT 0,
            pushes          INTEGER NOT NULL DEFAULT 0,
            prs_opened      INTEGER NOT NULL DEFAULT 0,
            prs_merged      INTEGER NOT NULL DEFAULT 0,
            issues_opened   INTEGER NOT NULL DEFAULT 0,
            issue_comments  INTEGER NOT NULL DEFAULT 0,
            reviews         INTEGER NOT NULL DEFAULT 0,
            last_active_at  TEXT,
            scanned_at      TEXT    NOT NULL,
            UNIQUE(login, repo_full_name, scan_date) ON CONFLICT REPLACE
        )
    """)


def _ensure_github_repo_schema(conn: sqlite3.Connection) -> None:
    """Repo-level metadata: labels, repo meta, push-discovery cache, branches."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS github_labels (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_full_name  TEXT    NOT NULL,
            name            TEXT    NOT NULL,
            color           TEXT,
            description     TEXT,
            is_default      INTEGER NOT NULL DEFAULT 0,
            UNIQUE(repo_full_name, name) ON CONFLICT REPLACE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS github_repo_meta (
            repo_full_name      TEXT PRIMARY KEY,
            default_branch      TEXT,
            pushed_at           TEXT,
            updated_at          TEXT,
            open_issues_count   INTEGER NOT NULL DEFAULT 0,
            has_issues          INTEGER NOT NULL DEFAULT 0,
            has_projects        INTEGER NOT NULL DEFAULT 0,
            fetched_at          TEXT NOT NULL
        )
    """)

    # Auto-discovery cache: every repo the PAT has seen via /user/repos?sort=pushed.
    # Independent of github_repo_meta (which only gets a row after a full artifact
    # sync). Lets get_watched_repos() pick up pushes that the events feed missed —
    # collaborator pushes on private org repos, non-default-branch pushes, events
    # dropped by the 300-event pagination cap, etc.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS github_pushed_repos (
            repo_full_name  TEXT PRIMARY KEY,
            pushed_at       TEXT NOT NULL,
            private         INTEGER NOT NULL DEFAULT 0,
            fork            INTEGER NOT NULL DEFAULT 0,
            archived        INTEGER NOT NULL DEFAULT 0,
            disabled        INTEGER NOT NULL DEFAULT 0,
            first_seen_at   TEXT NOT NULL,
            last_seen_at    TEXT NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_github_pushed_repos_pushed "
        "ON github_pushed_repos(pushed_at DESC)"
    )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS github_branches (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_full_name      TEXT    NOT NULL,
            name                TEXT    NOT NULL,
            head_sha            TEXT,
            is_protected        INTEGER NOT NULL DEFAULT 0,
            is_default          INTEGER NOT NULL DEFAULT 0,
            fetched_at          TEXT    NOT NULL,
            UNIQUE(repo_full_name, name) ON CONFLICT REPLACE
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_github_branches_repo "
        "ON github_branches(repo_full_name)"
    )


def _ensure_github_artifact_schema(conn: sqlite3.Connection) -> None:
    """Issue/PR corpus: milestones, releases, items, comments, commits, checks, links."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS github_milestones (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_full_name  TEXT    NOT NULL,
            number          INTEGER NOT NULL,
            title           TEXT    NOT NULL,
            description     TEXT,
            state           TEXT,
            open_issues     INTEGER NOT NULL DEFAULT 0,
            closed_issues   INTEGER NOT NULL DEFAULT 0,
            due_on          TEXT,
            created_at      TEXT,
            updated_at      TEXT,
            closed_at       TEXT,
            html_url        TEXT,
            UNIQUE(repo_full_name, number) ON CONFLICT REPLACE
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_github_milestones_repo_state "
        "ON github_milestones(repo_full_name, state)"
    )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS github_releases (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_full_name  TEXT    NOT NULL,
            github_id       INTEGER,
            tag_name        TEXT    NOT NULL,
            name            TEXT,
            target_commitish TEXT,
            is_draft        INTEGER NOT NULL DEFAULT 0,
            is_prerelease   INTEGER NOT NULL DEFAULT 0,
            body            TEXT,
            created_at      TEXT,
            published_at    TEXT,
            html_url        TEXT,
            UNIQUE(repo_full_name, tag_name) ON CONFLICT REPLACE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS github_items (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_full_name      TEXT    NOT NULL,
            item_type           TEXT    NOT NULL,
            number              INTEGER NOT NULL,
            node_id             TEXT,
            github_id           INTEGER,
            title               TEXT    NOT NULL,
            body                TEXT,
            state               TEXT,
            state_reason        TEXT,
            author_login        TEXT,
            assignees_json      TEXT,
            labels_json         TEXT,
            milestone_number    INTEGER,
            milestone_title     TEXT,
            is_draft            INTEGER NOT NULL DEFAULT 0,
            is_merged           INTEGER NOT NULL DEFAULT 0,
            base_ref            TEXT,
            head_ref            TEXT,
            head_sha            TEXT,
            mergeable_state     TEXT,
            review_decision     TEXT,
            check_status        TEXT,
            requested_reviewers_json TEXT,
            comments_count      INTEGER NOT NULL DEFAULT 0,
            review_comments_count INTEGER NOT NULL DEFAULT 0,
            commits_count       INTEGER NOT NULL DEFAULT 0,
            additions           INTEGER NOT NULL DEFAULT 0,
            deletions           INTEGER NOT NULL DEFAULT 0,
            changed_files       INTEGER NOT NULL DEFAULT 0,
            html_url            TEXT,
            created_at          TEXT,
            updated_at          TEXT,
            closed_at           TEXT,
            merged_at           TEXT,
            fetched_at          TEXT    NOT NULL,
            UNIQUE(repo_full_name, item_type, number) ON CONFLICT REPLACE
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_github_items_repo_updated "
        "ON github_items(repo_full_name, updated_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_github_items_milestone "
        "ON github_items(repo_full_name, milestone_title)"
    )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS github_comments (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_full_name      TEXT    NOT NULL,
            item_type           TEXT    NOT NULL,
            item_number         INTEGER NOT NULL,
            comment_type        TEXT    NOT NULL,
            github_comment_id   INTEGER NOT NULL,
            author_login        TEXT,
            author_association  TEXT,
            body                TEXT,
            review_state        TEXT,
            in_reply_to_id      INTEGER,
            html_url            TEXT,
            created_at          TEXT,
            updated_at          TEXT,
            fetched_at          TEXT    NOT NULL,
            UNIQUE(repo_full_name, comment_type, github_comment_id) ON CONFLICT REPLACE
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_github_comments_item "
        "ON github_comments(repo_full_name, item_type, item_number)"
    )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS github_commits (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_full_name      TEXT    NOT NULL,
            item_type           TEXT    NOT NULL,
            item_number         INTEGER NOT NULL,
            sha                 TEXT    NOT NULL,
            author_login        TEXT,
            message             TEXT,
            committed_at        TEXT,
            html_url            TEXT,
            fetched_at          TEXT    NOT NULL,
            UNIQUE(repo_full_name, item_type, item_number, sha) ON CONFLICT REPLACE
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_github_commits_item "
        "ON github_commits(repo_full_name, item_type, item_number)"
    )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS github_check_runs (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_full_name      TEXT    NOT NULL,
            item_type           TEXT    NOT NULL,
            item_number         INTEGER NOT NULL,
            head_sha            TEXT,
            name                TEXT    NOT NULL,
            status              TEXT,
            conclusion          TEXT,
            details_url         TEXT,
            started_at          TEXT,
            completed_at        TEXT,
            fetched_at          TEXT    NOT NULL,
            UNIQUE(repo_full_name, item_type, item_number, head_sha, name) ON CONFLICT REPLACE
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_github_checks_item "
        "ON github_check_runs(repo_full_name, item_type, item_number)"
    )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS github_links (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_full_name      TEXT    NOT NULL,
            source_type         TEXT    NOT NULL,
            source_number       INTEGER NOT NULL,
            target_type         TEXT    NOT NULL,
            target_number       INTEGER NOT NULL,
            link_kind           TEXT    NOT NULL,
            UNIQUE(
                repo_full_name,
                source_type,
                source_number,
                target_type,
                target_number,
                link_kind
            ) ON CONFLICT REPLACE
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_github_links_source "
        "ON github_links(repo_full_name, source_type, source_number)"
    )


def _ensure_github_knowledge_schema(conn: sqlite3.Connection) -> None:
    """Embeddable GitHub documents + their vector index."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS github_documents (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_full_name      TEXT    NOT NULL,
            source_type         TEXT    NOT NULL,
            source_number       INTEGER NOT NULL,
            doc_type            TEXT    NOT NULL,
            source_key          TEXT    NOT NULL,
            title               TEXT,
            body                TEXT    NOT NULL,
            content_hash        TEXT    NOT NULL,
            embedded_hash       TEXT,
            updated_at          TEXT,
            fetched_at          TEXT    NOT NULL,
            UNIQUE(source_key) ON CONFLICT REPLACE
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_github_documents_source "
        "ON github_documents(repo_full_name, source_type, source_number)"
    )

    try:
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS github_embeddings USING vec0(
                doc_id INTEGER PRIMARY KEY,
                embedding float[1024]
            )
        """)
    except sqlite3.DatabaseError:
        pass

    conn.execute("""
        CREATE TABLE IF NOT EXISTS github_embedding_meta (
            key     TEXT PRIMARY KEY,
            value   TEXT NOT NULL
        )
    """)


def _add_column_if_missing(
    conn: sqlite3.Connection, table: str, column: str, decl: str
) -> bool:
    """Additive migration for an existing table; True when the column was added.

    SQLite has no ``ADD COLUMN IF NOT EXISTS``, and ``CREATE TABLE IF NOT
    EXISTS`` silently skips an existing table with an older shape — so a new
    column on a table that already exists on a live DB needs this. Additive
    only: never drops or rewrites, so it is safe to re-run and safe to roll
    back by ignoring the column.
    """
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column in existing:
        return False
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
    return True


def _ensure_github_direct_commit_schema(conn: sqlite3.Connection) -> None:
    """Durable receipts and file-level facts for direct branch pushes (GH-155)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS github_push_events (
            event_id        TEXT PRIMARY KEY,
            repo_full_name  TEXT NOT NULL,
            ref             TEXT NOT NULL,
            before_sha      TEXT,
            head_sha        TEXT,
            observed_at     TEXT,
            state           TEXT NOT NULL,
            attempt_count   INTEGER NOT NULL DEFAULT 0,
            last_attempt_at TEXT,
            resolved_at     TEXT,
            failure_reason  TEXT,
            fetched_at      TEXT NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_github_push_events_pending "
        "ON github_push_events(state, observed_at)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS github_direct_commits (
            repo_full_name  TEXT NOT NULL,
            sha             TEXT NOT NULL,
            event_id        TEXT NOT NULL,
            ref             TEXT,
            author_login    TEXT,
            author_name     TEXT,
            message         TEXT,
            committed_at    TEXT,
            html_url        TEXT,
            path_coverage   TEXT NOT NULL DEFAULT 'unavailable',
            discovered_at   TEXT NOT NULL,
            fetched_at      TEXT NOT NULL,
            PRIMARY KEY (repo_full_name, sha)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_github_direct_commits_time "
        "ON github_direct_commits(committed_at DESC)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS github_direct_commit_files (
            repo_full_name  TEXT NOT NULL,
            sha             TEXT NOT NULL,
            path            TEXT NOT NULL,
            status          TEXT,
            additions       INTEGER,
            deletions       INTEGER,
            changes         INTEGER,
            PRIMARY KEY (repo_full_name, sha, path)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_github_direct_commit_files_path "
        "ON github_direct_commit_files(repo_full_name, path)"
    )
    # GH-169: provenance is a separate axis from data completeness. `path_coverage`
    # answers "do we have the file list?"; `source` answers "who collected it?".
    # Conflating them would force the completeness check to special-case a
    # coverage value that means "complete, but from git" — the kind of overloaded
    # column that made `failure_reason` unusable as a control signal (see Phase 2).
    _add_column_if_missing(
        conn, "github_direct_commits", "source", "TEXT NOT NULL DEFAULT 'events'"
    )
    # GH-169 Phase 2: why an event was deferred is a CONTROL signal, so it needs
    # a column of its own. It previously lived only inside `failure_reason`, a
    # human-readable log string — and reading control flow out of prose is how
    # 20 events were evicted for "compare cap reached", which is not a failure
    # at all. 'budget' = the run ran out of its own quota (must not cost an
    # attempt); 'failure' = the fetch genuinely failed (must cost one).
    _add_column_if_missing(
        conn, "github_push_events", "deferral_kind", "TEXT"
    )
    # GH-169 Phase 1: a watched repo we cannot enumerate locally is a REPORTED
    # state, not an omission. Silence is the failure shape this whole issue is
    # about, so an uncoverable repo gets a durable row with a reason.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS github_repo_coverage (
            repo_full_name  TEXT PRIMARY KEY,
            state           TEXT NOT NULL,
            reason          TEXT,
            local_path      TEXT,
            default_branch  TEXT,
            local_tip       TEXT,
            remote_tip      TEXT,
            last_fetched_at TEXT,
            checked_at      TEXT NOT NULL
        )
    """)


def ensure_github_schema(conn: sqlite3.Connection) -> None:
    """Create GitHub activity and local knowledge tables if they don't exist.

    Decomposed into per-table-group helpers for readability; the public
    contract is unchanged — every group is created, then committed once.
    """
    _ensure_github_activity_schema(conn)
    _ensure_github_repo_schema(conn)
    _ensure_github_artifact_schema(conn)
    _ensure_github_knowledge_schema(conn)
    _ensure_github_direct_commit_schema(conn)
    conn.commit()


# ---------------------------------------------------------------------------
# Project registry schema
# ---------------------------------------------------------------------------


def ensure_project_schema(conn: sqlite3.Connection) -> None:
    """Create project_registry table if it doesn't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS project_registry (
            name TEXT PRIMARY KEY,
            status TEXT,
            summary TEXT,
            value_level TEXT,
            priority_tier INTEGER,
            risk_level TEXT,
            repos_json TEXT,
            tags_json TEXT,
            custom_fields_json TEXT
        )
    """)
    conn.commit()


# ---------------------------------------------------------------------------
# Schema versioning
# ---------------------------------------------------------------------------

# The baseline schema — everything the ensure_*_schema functions above create.
# A database that has run those functions is, by definition, at this version.
# Schema changes from here on are forward-only migration files in db/migrations/
# (applied by db/migrate.py). This number never changes and the ensure_*_schema
# functions stay frozen at the baseline — see db/migrations/README.md.
#
# Exception: idempotent self-healing virtual indexes (the vec0 embedding tables
# and the semantic_documents_fts FTS5 index) are created in ensure_*_schema, not
# migrations — they are rebuildable derived indexes that must self-heal and cover
# read paths that don't run migrations. See the README "Exception" section.
BASELINE_SCHEMA_VERSION = 1


def ensure_baseline_schema(conn: sqlite3.Connection) -> None:
    """Create every baseline (version 1) table if it doesn't exist.

    Runs all six ``ensure_*_schema`` functions — the full version-1 shape.
    Idempotent; safe to call on an already-populated database. The migration
    runner calls this first so that migrations always have their tables.
    """
    ensure_schema(conn)
    ensure_semantic_schema(conn)
    ensure_calendar_schema(conn)
    ensure_email_schema(conn)
    ensure_github_schema(conn)
    ensure_project_schema(conn)


def ensure_schema_version_table(conn: sqlite3.Connection) -> None:
    """Create the ``schema_version`` ledger if it doesn't exist.

    One row per applied version; the current version is ``MAX(version)``.
    An empty table means no version has been recorded yet.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version    INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    conn.commit()

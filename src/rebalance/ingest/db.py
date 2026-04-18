"""
Shared database layer for rebalance — connection factory, schema creation,
sqlite-vec extension loading, and context managers.

All CREATE TABLE statements live here so the full DB shape is visible in
one place.  Individual modules call the appropriate ensure_*_schema()
function (or use the db_connection context manager) rather than carrying
their own DDL.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Generator

try:
    import sqlite_vec
except Exception:  # pragma: no cover - import guard for environments without sqlite-vec
    sqlite_vec = None


# ---------------------------------------------------------------------------
# Connection factory
# ---------------------------------------------------------------------------


def get_connection(database_path: Path) -> sqlite3.Connection:
    """Open a SQLite connection with WAL mode, foreign keys, and sqlite-vec loaded.

    Note: sqlite-vec may not load on all Python builds (e.g., system Python without
    extension support). The connection will still work for basic queries.
    """
    database_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(database_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # Try to load sqlite-vec, but gracefully fall back if unavailable
    try:
        if sqlite_vec is not None and hasattr(conn, 'enable_load_extension'):
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
    except (AttributeError, Exception):
        # sqlite-vec not available on this Python build; continue without it
        pass

    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db_connection(
    database_path: Path,
    ensure_fn: Callable[[sqlite3.Connection], None] | None = None,
) -> Generator[sqlite3.Connection, None, None]:
    """Context-managed database connection with optional schema setup.

    Usage::

        with db_connection(db_path, ensure_schema) as conn:
            rows = conn.execute("SELECT ...").fetchall()

    The connection is always closed on exit — even if the caller raises.
    Pass *ensure_fn* to guarantee a specific set of tables exists (e.g.
    ``ensure_schema``, ``ensure_calendar_schema``).  Omit it when you only
    need a bare connection.
    """
    conn = get_connection(database_path)
    if ensure_fn is not None:
        ensure_fn(conn)
    try:
        yield conn
    finally:
        conn.close()


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
# GitHub activity schema
# ---------------------------------------------------------------------------


def ensure_github_schema(conn: sqlite3.Connection) -> None:
    """Create GitHub activity and local knowledge tables if they don't exist."""
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

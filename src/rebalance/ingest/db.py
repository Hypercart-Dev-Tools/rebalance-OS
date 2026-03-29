"""
Shared database layer for rebalance — connection factory, schema creation,
and sqlite-vec extension loading.

All table creation for vault ingestion and embeddings lives here.
Does NOT touch project_registry or github_activity — those have their own
writers in registry.py and github_scan.py.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import sqlite_vec


def get_connection(database_path: Path) -> sqlite3.Connection:
    """Open a SQLite connection with WAL mode, foreign keys, and sqlite-vec loaded."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(database_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.row_factory = sqlite3.Row
    return conn


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

    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS embeddings USING vec0(
            chunk_id INTEGER PRIMARY KEY,
            embedding float[1024]
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS embedding_meta (
            key     TEXT PRIMARY KEY,
            value   TEXT NOT NULL
        )
    """)

    conn.commit()

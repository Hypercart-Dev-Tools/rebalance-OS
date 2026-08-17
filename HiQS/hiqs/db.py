"""SQLite connection and schema setup for HiQS.

This module is deliberately the narrow persistence base: it owns connection
configuration and the initial schema, but no query or reconciliation policy.
"""

from __future__ import annotations

import os
from pathlib import Path
import platform
import sqlite3


def default_db_path() -> Path:
    """Return HiQS's platform-appropriate application-data database path."""
    system = platform.system()
    if system == "Darwin":
        data_root = Path.home() / "Library" / "Application Support"
    elif system == "Windows":
        data_root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        data_root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return data_root / "hiqs" / "hiqs.db"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS vault_files(
  path TEXT PRIMARY KEY,
  content_hash TEXT NOT NULL,
  mtime TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS github_activity(
  login TEXT NOT NULL,
  repo TEXT NOT NULL,
  day TEXT NOT NULL,
  counts_json TEXT NOT NULL,
  PRIMARY KEY (login, repo, day));

CREATE TABLE IF NOT EXISTS github_items(
  repo TEXT NOT NULL,
  type TEXT NOT NULL,
  number INTEGER NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  state TEXT NOT NULL,
  url TEXT NOT NULL,
  author TEXT NOT NULL,
  assignee TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  activity_at TEXT NOT NULL,
  PRIMARY KEY (repo, type, number));

CREATE TABLE IF NOT EXISTS calendar_events(
  id TEXT PRIMARY KEY,
  summary TEXT NOT NULL,
  start TEXT NOT NULL,
  end TEXT NOT NULL,
  project TEXT NOT NULL,
  organizer TEXT NOT NULL,
  attendees_json TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS docs(
  source TEXT NOT NULL,
  id TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  url TEXT NOT NULL,
  ts TEXT NOT NULL,
  project TEXT NOT NULL,
  author TEXT NOT NULL,
  PRIMARY KEY (source, id));

CREATE TABLE IF NOT EXISTS doc_github_refs(
  doc_source TEXT NOT NULL,
  doc_id TEXT NOT NULL,
  repo TEXT NOT NULL,
  type TEXT NOT NULL,
  number INTEGER NOT NULL,
  PRIMARY KEY (doc_source, doc_id, repo, type, number),
  FOREIGN KEY (doc_source, doc_id) REFERENCES docs(source, id) ON DELETE CASCADE,
  FOREIGN KEY (repo, type, number) REFERENCES github_items(repo, type, number) ON DELETE CASCADE);

CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
  title, body,
  content='docs', content_rowid='rowid');

CREATE TRIGGER IF NOT EXISTS docs_ai AFTER INSERT ON docs BEGIN
  INSERT INTO docs_fts(rowid, title, body) VALUES (new.rowid, new.title, new.body);
END;

CREATE TRIGGER IF NOT EXISTS docs_ad AFTER DELETE ON docs BEGIN
  INSERT INTO docs_fts(docs_fts, rowid, title, body)
  VALUES ('delete', old.rowid, old.title, old.body);
END;

CREATE TRIGGER IF NOT EXISTS docs_au AFTER UPDATE ON docs BEGIN
  INSERT INTO docs_fts(docs_fts, rowid, title, body)
  VALUES ('delete', old.rowid, old.title, old.body);
  INSERT INTO docs_fts(rowid, title, body) VALUES (new.rowid, new.title, new.body);
END;

CREATE TABLE IF NOT EXISTS docs_vec(
  doc_id TEXT NOT NULL,
  model  TEXT NOT NULL,          -- e.g. 'all-MiniLM-L6-v2'
  dim    INTEGER NOT NULL,       -- 384 | 1024 — models of different width coexist
  vec    BLOB NOT NULL,
  PRIMARY KEY (doc_id, model));

CREATE TABLE IF NOT EXISTS projects(
  name TEXT PRIMARY KEY,
  aliases_json TEXT NOT NULL,
  repos_json TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS project_affinity(
  project_a TEXT NOT NULL,
  project_b TEXT NOT NULL,
  edge TEXT NOT NULL,
  weight REAL NOT NULL,
  PRIMARY KEY (project_a, project_b, edge),
  CHECK (project_a < project_b),
  CHECK (edge IN ('same_org', 'name_token')),
  CHECK (weight > 0));

CREATE TABLE IF NOT EXISTS events(
  ts TEXT,
  kind TEXT,
  source TEXT,
  status TEXT CHECK(status IN ('ok', 'warn', 'error', 'unknown')),
  payload_json TEXT);
"""


def db_connection(path: str | Path | None = None) -> sqlite3.Connection:
    """Open a configured HiQS database and ensure its idempotent schema exists."""
    db_path = default_db_path() if path is None else Path(path)
    if str(db_path) != ":memory:":
        db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    connection.executescript(_SCHEMA)
    return connection

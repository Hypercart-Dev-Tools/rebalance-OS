import sqlite3
import struct

import pytest

from hiqs.db import db_connection


def test_connection_configures_required_pragmas_and_full_schema(tmp_path):
    connection = db_connection(tmp_path / "hiqs.db")
    try:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 30000

        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert {
            "vault_files",
            "github_activity",
            "github_items",
            "calendar_events",
            "docs",
            "doc_github_refs",
            "docs_vec",
            "projects",
            "project_affinity",
            "events",
        } <= tables
        assert "docs_fts" in tables
    finally:
        connection.close()


def test_project_affinity_enforces_one_canonical_row_per_edge(tmp_path):
    connection = db_connection(tmp_path / "hiqs.db")
    try:
        connection.execute(
            "INSERT INTO project_affinity VALUES (?, ?, ?, ?)", ("alpha", "beta", "same_org", 1.0)
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO project_affinity VALUES (?, ?, ?, ?)", ("beta", "alpha", "same_org", 1.0)
            )
    finally:
        connection.close()


def test_schema_creation_is_idempotent_and_fts_tracks_docs(tmp_path):
    path = tmp_path / "hiqs.db"
    first_connection = db_connection(path)
    first_connection.close()
    connection = db_connection(path)
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'trigger' AND name = 'docs_ai'"
        ).fetchone()[0] == 1
        connection.execute(
            "INSERT INTO docs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("vault", "note-1", "A title", "searchable body", "", "2026-08-03T12:00:00Z", "", ""),
        )
        assert connection.execute(
            "SELECT rowid FROM docs_fts WHERE docs_fts MATCH 'searchable'"
        ).fetchone() is not None
    finally:
        connection.close()


def test_vectors_for_multiple_models_share_a_document_id(tmp_path):
    connection = db_connection(tmp_path / "hiqs.db")
    try:
        vectors = (
            ("all-MiniLM-L6-v2", 384),
            ("Qwen3-Embedding-0.6B", 1024),
        )
        connection.executemany(
            "INSERT INTO docs_vec(doc_id, model, dim, vec) VALUES (?, ?, ?, ?)",
            [
                ("vault:note-1", model, dimension, struct.pack(f"<{dimension}f", *([0.0] * dimension)))
                for model, dimension in vectors
            ],
        )
        rows = connection.execute(
            "SELECT model, dim, length(vec) FROM docs_vec WHERE doc_id = ? ORDER BY dim",
            ("vault:note-1",),
        ).fetchall()
        assert rows == [
            ("all-MiniLM-L6-v2", 384, 384 * 4),
            ("Qwen3-Embedding-0.6B", 1024, 1024 * 4),
        ]
    finally:
        connection.close()


def test_docs_vec_rejects_duplicate_model_for_same_document(tmp_path):
    connection = db_connection(tmp_path / "hiqs.db")
    try:
        values = ("vault:note-1", "all-MiniLM-L6-v2", 384, b"vector")
        connection.execute("INSERT INTO docs_vec VALUES (?, ?, ?, ?)", values)
        try:
            connection.execute("INSERT INTO docs_vec VALUES (?, ?, ?, ?)", values)
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("docs_vec must key vectors by document and model")
    finally:
        connection.close()

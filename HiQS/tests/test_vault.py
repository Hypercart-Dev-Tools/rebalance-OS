"""Tests for the Obsidian vault source plugin."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3

import pytest

from hiqs.db import db_connection
from hiqs.sources.vault import SOURCE, is_generated_file


def test_is_generated_file_exclusions():
    """Assert generated and hidden system files are excluded by construction (L5)."""
    assert is_generated_file(".git/config")
    assert is_generated_file("vault/.obsidian/workspace.json")
    assert is_generated_file(".trash/deleted_note.md")
    assert is_generated_file("notes/auto_summary.gen.md")
    assert is_generated_file("notes/.DS_Store")
    assert is_generated_file("notes/temp.tmp")
    assert is_generated_file("node_modules/package/README.md")

    assert not is_generated_file("notes/project_plan.md")
    assert not is_generated_file("daily/2026-08-03.md")


def test_vault_fetch_idempotence_and_counts(tmp_path):
    """Two consecutive runs over an unchanged tree: zero inserts, zero updates."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    (vault_dir / "note1.md").write_text("# Note One\n\nContent of note 1.", encoding="utf-8")
    (vault_dir / "note2.md").write_text("# Note Two\n\nContent of note 2.", encoding="utf-8")
    (vault_dir / "ignored.tmp").write_text("Temp file", encoding="utf-8")

    db_path = tmp_path / "hiqs.db"
    connection = db_connection(db_path)

    try:
        # Run 1: initial ingest
        report1 = SOURCE.fetch(connection, {"vault_path": str(vault_dir)})
        assert report1.counts["inserted"] == 2
        assert report1.counts["updated"] == 0
        assert report1.counts["unchanged"] == 0
        assert report1.counts["skipped"] == 1
        assert report1.counts["rejected"] == 0
        assert report1.counts["pruned"] == 0
        assert report1.errors == []

        # Run 2: second run over unchanged tree
        report2 = SOURCE.fetch(connection, {"vault_path": str(vault_dir)})
        assert report2.counts["inserted"] == 0
        assert report2.counts["updated"] == 0
        assert report2.counts["unchanged"] == 2
        assert report2.counts["skipped"] == 1
        assert report2.counts["rejected"] == 0
        assert report2.counts["pruned"] == 0
        assert report2.errors == []

        docs_list = list(SOURCE.docs(connection, {"vault_path": str(vault_dir)}))
        assert len(docs_list) == 2
    finally:
        connection.close()


def test_vault_docs_chunking_and_id_shape(tmp_path):
    """Assert chunking by heading emits file-scoped IDs and author=''."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    note_path = vault_dir / "architecture.md"
    note_path.write_text(
        "---\ntitle: System Architecture\n---\n"
        "Preamble text here.\n\n"
        "# Section One\n\n"
        "Body of section 1.\n\n"
        "## Subsection A\n\n"
        "Body of subsection A.\n",
        encoding="utf-8",
    )

    db_path = tmp_path / "hiqs.db"
    connection = db_connection(db_path)

    try:
        SOURCE.fetch(connection, {"vault_path": str(vault_dir)})
        docs = list(SOURCE.docs(connection, {"vault_path": str(vault_dir)}))

        assert len(docs) == 3

        # Every Doc must have source="vault" and author=""
        for doc in docs:
            assert doc.source == "vault"
            assert doc.author == ""
            assert doc.id.startswith("vault:architecture.md:")

        # Verify title formatting
        titles = [doc.title for doc in docs]
        assert "System Architecture" in titles
        assert "System Architecture - Section One" in titles
        assert "System Architecture - Subsection A" in titles
    finally:
        connection.close()


def test_vault_heading_rename_and_deletion_chunk_ids(tmp_path):
    """Renaming or deleting a heading updates chunk IDs emitted by docs()."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    note_path = vault_dir / "topic.md"
    note_path.write_text(
        "# Heading Original\n\nContent original.\n\n# Heading To Delete\n\nContent to delete.",
        encoding="utf-8",
    )

    db_path = tmp_path / "hiqs.db"
    connection = db_connection(db_path)

    try:
        SOURCE.fetch(connection, {"vault_path": str(vault_dir)})
        docs_run1 = list(SOURCE.docs(connection, {"vault_path": str(vault_dir)}))
        ids_run1 = {doc.id for doc in docs_run1}
        assert len(ids_run1) == 2

        # Rename Heading Original and Delete Heading To Delete
        note_path.write_text(
            "# Heading Renamed\n\nContent original.",
            encoding="utf-8",
        )

        SOURCE.fetch(connection, {"vault_path": str(vault_dir)})
        docs_run2 = list(SOURCE.docs(connection, {"vault_path": str(vault_dir)}))
        ids_run2 = {doc.id for doc in docs_run2}
        assert len(ids_run2) == 1

        # Old IDs must no longer be present
        assert ids_run1.isdisjoint(ids_run2)

        # Hash of "Heading Renamed" with body
        expected_key = "Heading Renamed:# Heading Renamed\n\nContent original."
        expected_hash = hashlib.sha256(expected_key.encode("utf-8")).hexdigest()[:12]
        assert f"vault:topic.md:{expected_hash}" in ids_run2
    finally:
        connection.close()


def test_vault_duplicate_headings_stable_identity(tmp_path):
    """Deleting the first of two equal headings does not cause the second to inherit the deleted heading's ID or change its own ID."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    note_path = vault_dir / "dup.md"
    note_path.write_text(
        "## Setup\n\nFirst setup block.\n\n## Setup\n\nSecond setup block.",
        encoding="utf-8",
    )

    db_path = tmp_path / "hiqs.db"
    connection = db_connection(db_path)

    try:
        SOURCE.fetch(connection, {"vault_path": str(vault_dir)})
        docs_run1 = list(SOURCE.docs(connection, {"vault_path": str(vault_dir)}))
        assert len(docs_run1) == 2

        doc1, doc2 = docs_run1[0], docs_run1[1]
        assert doc1.id != doc2.id
        id1_initial, id2_initial = doc1.id, doc2.id

        # Delete the first "## Setup" block
        note_path.write_text(
            "## Setup\n\nSecond setup block.",
            encoding="utf-8",
        )

        SOURCE.fetch(connection, {"vault_path": str(vault_dir)})
        docs_run2 = list(SOURCE.docs(connection, {"vault_path": str(vault_dir)}))
        assert len(docs_run2) == 1

        remaining_doc = docs_run2[0]
        # The remaining doc's ID must NOT be id1_initial, and MUST match its prior id2_initial
        assert remaining_doc.id != id1_initial
        assert remaining_doc.id == id2_initial
        assert remaining_doc.body == "## Setup\n\nSecond setup block."
    finally:
        connection.close()


def test_vault_docs_unfetched_drift_or_failure_retains_projected_rows(tmp_path, monkeypatch):
    """docs() raises RuntimeError on missing/unreadable/drifted tracked files so project_docs retains prior rows."""
    from unittest.mock import MagicMock
    from hiqs.docs_index import project_docs

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    note_path = vault_dir / "note.md"
    note_path.write_text("# Note Title\n\nInitial note content.", encoding="utf-8")

    db_path = tmp_path / "hiqs.db"
    connection = db_connection(db_path)

    try:
        mock_embedder = MagicMock()
        mock_embedder.encode.return_value = [[0.1] * 384]

        # Step 1: Initial fetch and projection
        SOURCE.fetch(connection, {"vault_path": str(vault_dir)})
        report1 = project_docs(
            connection,
            sources=[SOURCE],
            embedder=mock_embedder,
        )
        assert report1.counts["inserted"] == 1
        rows_before = connection.execute("SELECT id, title, body FROM docs WHERE source = 'vault'").fetchall()
        assert len(rows_before) == 1

        # Step 2: Content drift without running fetch()
        note_path.write_text("# Note Title\n\nDrifted content on disk.", encoding="utf-8")

        # project_docs should record error and NOT prune the existing row in docs
        report_drift = project_docs(
            connection,
            sources=[SOURCE],
            embedder=mock_embedder,
        )
        assert len(report_drift.errors) == 1
        assert "content drifted without fetch" in report_drift.errors[0]

        rows_after_drift = connection.execute("SELECT id, title, body FROM docs WHERE source = 'vault'").fetchall()
        assert rows_after_drift == rows_before

        # Step 3: Unreadable file / failed read without fetch()
        orig_read_bytes = Path.read_bytes

        def mock_read_bytes(path_obj):
            if path_obj.name == "note.md":
                raise PermissionError("Permission denied")
            return orig_read_bytes(path_obj)

        monkeypatch.setattr(Path, "read_bytes", mock_read_bytes)

        report_read_err = project_docs(
            connection,
            sources=[SOURCE],
            embedder=mock_embedder,
        )
        assert len(report_read_err.errors) == 1
        assert "Failed to read tracked file" in report_read_err.errors[0]

        rows_after_err = connection.execute("SELECT id, title, body FROM docs WHERE source = 'vault'").fetchall()
        assert rows_after_err == rows_before
    finally:
        connection.close()


def test_ensure_schema_canonical(tmp_path):
    """Assert _ensure_schema creates vault_files with canonical schema (path, content_hash, mtime)."""
    from hiqs.sources.vault import _ensure_schema

    db_path = tmp_path / "canonical.db"
    conn = sqlite3.connect(db_path)
    try:
        _ensure_schema(conn)

        cols = {r[1]: r[2] for r in conn.execute("PRAGMA table_info(vault_files)").fetchall()}
        assert set(cols.keys()) == {"path", "content_hash", "mtime"}

        # Ensure vault_chunks table is NOT created
        chunk_table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='vault_chunks'"
        ).fetchone()
        assert chunk_table is None
    finally:
        conn.close()


def test_vault_unreadable_file_handling(tmp_path, monkeypatch):
    """Unreadable files append to errors and keep existing DB state without advancing watermark (L15, L19)."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    good_path = vault_dir / "good.md"
    bad_path = vault_dir / "bad.md"
    good_path.write_text("# Good Note\nGood content.", encoding="utf-8")
    bad_path.write_text("# Bad Note\nBad content.", encoding="utf-8")

    db_path = tmp_path / "hiqs.db"
    connection = db_connection(db_path)

    try:
        # Step 1: Initial successful fetch of both files
        report1 = SOURCE.fetch(connection, {"vault_path": str(vault_dir)})
        assert report1.counts["inserted"] == 2
        assert report1.errors == []

        row_bad_before = connection.execute(
            "SELECT content_hash, mtime FROM vault_files WHERE path = 'bad.md'"
        ).fetchone()

        # Step 2: Make bad.md unreadable
        orig_read_bytes = Path.read_bytes

        def mock_read_bytes(path_obj):
            if path_obj.name == "bad.md":
                raise PermissionError("Permission denied: bad.md")
            return orig_read_bytes(path_obj)

        bad_path.write_text("# Bad Note Updated\nNew content.", encoding="utf-8")
        monkeypatch.setattr(Path, "read_bytes", mock_read_bytes)

        report2 = SOURCE.fetch(connection, {"vault_path": str(vault_dir)})
        assert report2.counts["rejected"] == 1
        assert len(report2.errors) == 1
        assert "bad.md" in report2.errors[0]

        # Existing row for bad.md in vault_files must remain untouched (from initial fetch)
        row_bad_after = connection.execute(
            "SELECT content_hash, mtime FROM vault_files WHERE path = 'bad.md'"
        ).fetchone()
        assert row_bad_before == row_bad_after
    finally:
        connection.close()


def test_vault_path_resolution_from_config(tmp_path):
    """Vault path must come from config, not a hardcoded location (L11). Supports dicts and objects."""
    vault_dir = tmp_path / "my_custom_vault"
    vault_dir.mkdir()
    (vault_dir / "test.md").write_text("# Custom Path\nContent.", encoding="utf-8")

    db_path = tmp_path / "hiqs.db"
    connection = db_connection(db_path)

    try:
        # Dict with vault_path
        report = SOURCE.fetch(connection, {"vault_path": str(vault_dir)})
        assert report.counts["inserted"] == 1
        assert report.errors == []

        docs = list(SOURCE.docs(connection, {"vault_path": str(vault_dir)}))
        assert len(docs) == 1
        assert docs[0].title == "test - Custom Path"

        # Object with vault_path attribute
        class ConfigObj:
            vault_path = str(vault_dir)

        report_obj = SOURCE.fetch(connection, ConfigObj())
        assert report_obj.counts["unchanged"] == 1
    finally:
        connection.close()


def test_vault_hidden_vault_path_ingestion(tmp_path):
    """A vault whose root path is hidden (e.g. /path/.my_vault) ingests valid notes."""
    hidden_vault = tmp_path / ".my_hidden_vault"
    hidden_vault.mkdir()

    (hidden_vault / "secret.md").write_text("# Secret Note\nSecret content.", encoding="utf-8")

    db_path = tmp_path / "hiqs.db"
    connection = db_connection(db_path)

    try:
        report = SOURCE.fetch(connection, {"vault_path": str(hidden_vault)})
        assert report.counts["inserted"] == 1
        assert report.counts["skipped"] == 0
        assert report.errors == []

        docs = list(SOURCE.docs(connection, {"vault_path": str(hidden_vault)}))
        assert len(docs) == 1
        assert docs[0].title == "secret - Secret Note"
    finally:
        connection.close()


def test_vault_walk_onerror_populates_errors(tmp_path, monkeypatch):
    """Directory listing errors during os.walk populate SyncReport.errors via onerror callback."""
    import os

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    (vault_dir / "note.md").write_text("# Note\nContent", encoding="utf-8")

    db_path = tmp_path / "hiqs.db"
    connection = db_connection(db_path)

    try:
        orig_walk = os.walk

        def mock_walk(top, topdown=True, onerror=None, followlinks=False):
            if onerror:
                onerror(PermissionError("Permission denied reading directory"))
            return orig_walk(top, topdown=topdown, onerror=onerror, followlinks=followlinks)

        monkeypatch.setattr(os, "walk", mock_walk)

        report = SOURCE.fetch(connection, {"vault_path": str(vault_dir)})
        assert len(report.errors) == 1
        assert "Directory walk error: Permission denied reading directory" in report.errors[0]
    finally:
        connection.close()


def test_vault_source_entry_point_discovery(monkeypatch):
    """Verify VAULT_SOURCE can be loaded via hiqs.sources entry point group."""
    from hiqs.plugins import discover_sources

    class VaultEntryPoint:
        def load(self):
            return SOURCE

    monkeypatch.setattr(
        "hiqs.plugins.metadata.entry_points",
        lambda *, group: (VaultEntryPoint(),) if group == "hiqs.sources" else (),
    )
    sources = discover_sources()
    assert any(s.name == "vault" for s in sources)





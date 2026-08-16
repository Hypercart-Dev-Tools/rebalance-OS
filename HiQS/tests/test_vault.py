"""Tests for the Obsidian vault source plugin."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3


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

    monkeypatch.setattr("hiqs.config.load_config", lambda: {"vault_path": str(vault_dir)})

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


def test_vault_docs_process_restart_resolves_config_without_global_state(tmp_path, monkeypatch):
    """Fetches to a file-backed DB, clears/reloads module state, then projects via project_docs() without passing config and succeeds."""
    import importlib
    import sys
    from unittest.mock import MagicMock
    from hiqs.docs_index import project_docs

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    note_path = vault_dir / "restart.md"
    note_path.write_text("# Restart Note\nContent for restart test.", encoding="utf-8")

    db_path = tmp_path / "hiqs.db"
    connection = db_connection(db_path)

    try:
        monkeypatch.setattr("hiqs.config.load_config", lambda: {"vault_path": str(vault_dir)})

        # Step 1: Initial fetch
        SOURCE.fetch(connection, {"vault_path": str(vault_dir)})

        # Step 2: Clear/reload module state to simulate process restart
        sys.modules.pop("hiqs.sources.vault", None)
        vault_module = importlib.import_module("hiqs.sources.vault")

        mock_embedder = MagicMock()
        mock_embedder.encode.return_value = [[0.1] * 384]

        # Step 3: project_docs calls source.docs(connection) with no config argument
        report = project_docs(
            connection,
            sources=[vault_module.SOURCE],
            embedder=mock_embedder,
        )
        assert report.errors == []
        assert report.counts["inserted"] == 1

        rows = connection.execute("SELECT id, title, body FROM docs WHERE source = 'vault'").fetchall()
        assert len(rows) == 1
        assert "Restart Note" in rows[0][1]
    finally:
        connection.close()


def test_vault_mtime_utc_iso8601_format(tmp_path):
    """mtime in vault_files must be stored in canonical UTC ISO-8601 format ending with Z."""
    import re

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    (vault_dir / "time_check.md").write_text("# Timestamp Check\nContent", encoding="utf-8")

    db_path = tmp_path / "hiqs.db"
    connection = db_connection(db_path)

    try:
        SOURCE.fetch(connection, {"vault_path": str(vault_dir)})
        row = connection.execute("SELECT mtime FROM vault_files WHERE path = 'time_check.md'").fetchone()
        assert row is not None
        mtime_str = row[0]
        # Assert UTC ISO-8601 timestamp ending in 'Z'
        assert mtime_str.endswith("Z")
        assert "T" in mtime_str
        assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$", mtime_str) is not None
    finally:
        connection.close()


def test_deleting_vault_note_removes_from_search_and_errored_walk_retains(tmp_path, monkeypatch):
    """Deleting a vault note removes its rows on a clean fetch, but retains rows when walk errors."""
    from unittest.mock import MagicMock
    from hiqs.docs_index import project_docs

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    monkeypatch.setattr("hiqs.config.load_config", lambda: {"vault_path": str(vault_dir)})

    file1 = vault_dir / "note1.md"
    file1.write_text("# Note 1\nContent 1", encoding="utf-8")

    file2 = vault_dir / "note2.md"
    file2.write_text("# Note 2\nContent 2", encoding="utf-8")

    db_path = tmp_path / "hiqs.db"
    conn = db_connection(db_path)

    try:
        mock_embedder = MagicMock()
        mock_embedder.encode.side_effect = lambda texts: [[0.1] * 384 for _ in texts]

        # Initial sync of both notes
        rep1 = SOURCE.fetch(conn, {"vault_path": str(vault_dir)})
        project_docs(conn, sources=[SOURCE], embedder=mock_embedder, reports={"vault": rep1})
        assert conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0] == 2

        # Step 1: Delete note1.md and perform clean fetch
        file1.unlink()
        rep_clean = SOURCE.fetch(conn, {"vault_path": str(vault_dir)})
        assert rep_clean.errors == []
        assert "note1.md" in rep_clean.units_ok

        project_docs(conn, sources=[SOURCE], embedder=mock_embedder, reports={"vault": rep_clean})
        # note1.md rows MUST BE GONE, note2.md rows REMAIN
        remaining = [r[0] for r in conn.execute("SELECT id FROM docs").fetchall()]
        assert len(remaining) == 1
        assert remaining[0].startswith("vault:note2.md:")

        # Step 2: Delete note2.md, but trigger walk error during fetch
        file2.unlink()

        def mock_walk(top, topdown=True, onerror=None, followlinks=False):
            if onerror:
                onerror(PermissionError("Simulated walk error"))
            return [(str(top), [], [])]

        monkeypatch.setattr("os.walk", mock_walk)

        rep_error = SOURCE.fetch(conn, {"vault_path": str(vault_dir)})
        assert len(rep_error.errors) > 0
        # Because walk errored, note2.md is NOT in units_ok
        assert "note2.md" not in rep_error.units_ok

        project_docs(conn, sources=[SOURCE], embedder=mock_embedder, reports={"vault": rep_error})
        # note2.md rows MUST SURVIVE!
        remaining_after_err = [r[0] for r in conn.execute("SELECT id FROM docs").fetchall()]
        assert len(remaining_after_err) == 1
        assert remaining_after_err[0].startswith("vault:note2.md:")
    finally:
        conn.close()







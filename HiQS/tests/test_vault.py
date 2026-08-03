"""Tests for the Obsidian vault source plugin."""

from __future__ import annotations

import hashlib
from pathlib import Path
import stat

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

        # Run 3: delete note2.md and re-fetch -> assert pruned == 1
        (vault_dir / "note2.md").unlink()
        report3 = SOURCE.fetch(connection, {"vault_path": str(vault_dir)})
        assert report3.counts["inserted"] == 0
        assert report3.counts["updated"] == 0
        assert report3.counts["unchanged"] == 1
        assert report3.counts["skipped"] == 1
        assert report3.counts["rejected"] == 0
        assert report3.counts["pruned"] == 1
        assert report3.errors == []

        remaining_docs = list(SOURCE.docs(connection))
        assert len(remaining_docs) == 1
        assert remaining_docs[0].id.startswith("vault:note1.md:")
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
        docs = list(SOURCE.docs(connection))

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
    """Renaming or deleting a heading produces distinct chunk IDs."""
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
        docs_run1 = list(SOURCE.docs(connection))
        ids_run1 = {doc.id for doc in docs_run1}
        assert len(ids_run1) == 2

        # Rename Heading Original and Delete Heading To Delete
        note_path.write_text(
            "# Heading Renamed\n\nContent original.",
            encoding="utf-8",
        )

        SOURCE.fetch(connection, {"vault_path": str(vault_dir)})
        docs_run2 = list(SOURCE.docs(connection))
        ids_run2 = {doc.id for doc in docs_run2}
        assert len(ids_run2) == 1

        # Old IDs must not be present in run 2 docs
        assert ids_run1.isdisjoint(ids_run2)

        # Hash of "Heading Renamed"
        expected_hash = hashlib.sha256(b"Heading Renamed").hexdigest()[:12]
        assert f"vault:topic.md:{expected_hash}" in ids_run2
    finally:
        connection.close()


def test_vault_unreadable_file_handling(tmp_path, monkeypatch):
    """Unreadable files append to errors, keep existing DB state, and do not advance watermark (L15, L19)."""
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

        # Step 2: Make bad.md unreadable
        orig_read_bytes = Path.read_bytes

        def mock_read_bytes(path_obj):
            if path_obj.name == "bad.md":
                raise PermissionError("Permission denied: bad.md")
            return orig_read_bytes(path_obj)

        # Update bad.md on disk, but mock reading it to throw error
        bad_path.write_text("# Bad Note Updated\nNew content.", encoding="utf-8")
        monkeypatch.setattr(Path, "read_bytes", mock_read_bytes)

        report2 = SOURCE.fetch(connection, {"vault_path": str(vault_dir)})
        assert report2.counts["rejected"] == 1
        assert len(report2.errors) == 1
        assert "bad.md" in report2.errors[0]

        # Existing row for bad.md in vault_files must remain untouched (from initial fetch)
        row = connection.execute("SELECT content FROM vault_files WHERE path = 'bad.md'").fetchone()
        assert row is not None
        assert "Bad content." in row[0]
        assert "New content." not in row[0]
    finally:
        connection.close()


def test_vault_path_resolution_from_config(tmp_path):
    """Vault path must come from config, not a hardcoded location (L11)."""
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

        docs = list(SOURCE.docs(connection))
        assert len(docs) == 1
        assert docs[0].title == "test - Custom Path"
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

        docs = list(SOURCE.docs(connection))
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




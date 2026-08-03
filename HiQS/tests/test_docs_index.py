"""Tests for hiqs.docs_index module."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hiqs import docs_index
from hiqs.db import db_connection
from hiqs.docs_index import deserialize_vector, get_doc_vector, project_docs, serialize_vector
from hiqs.plugins import Doc, Source, SyncReport


def _sql_writers(table: str) -> set[tuple[str, str]]:
    """Helper to analyze SQL statements writing to a table across all hiqs package modules using AST."""
    import hiqs

    writers = set()
    pkg_path = Path(hiqs.__file__).parent

    for py_file in pkg_path.rglob("*.py"):
        if py_file.name == "db.py":
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except Exception:
            continue

        rel_path = py_file.relative_to(pkg_path.parent).as_posix()
        for function in (node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)):
            for call in (node for node in ast.walk(function) if isinstance(node, ast.Call)):
                for argument in call.args:
                    if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                        val = argument.value.upper()
                        if f"INSERT INTO {table}".upper() in val or f"UPDATE {table} SET".upper() in val:
                            writers.add((rel_path, function.name))
    return writers


class MockSource:

    def __init__(self, name: str, docs_list: list[Doc]):
        self.name = name
        self._docs = docs_list

    def fetch(self, conn, config):
        return SyncReport(counts={"inserted": len(self._docs)})

    def docs(self, conn):
        return self._docs


def test_docs_has_exactly_one_writer():
    """Assert docs table has exactly one writer across all hiqs modules: project_docs."""
    writers = _sql_writers("docs")
    writer_funcs = {func_name for _, func_name in writers}
    assert writer_funcs == {"project_docs"}


def test_delta_behaviour_zero_embed_calls_on_unchanged_content(tmp_path):
    """Assert unchanged content re-runs with zero embed calls."""
    conn = db_connection(tmp_path / "hiqs.db")

    doc1 = Doc(
        source="mock",
        id="mock:1",
        title="Test Title",
        body="Test Body",
    )
    source = MockSource("mock", [doc1])

    mock_embedder = MagicMock(return_value=[[0.1] * 384])

    report1 = project_docs(conn, sources=[source], embedder=mock_embedder)
    assert report1.counts["inserted"] == 1
    assert mock_embedder.call_count == 1

    # Second run with unchanged content
    mock_embedder.reset_mock()
    report2 = project_docs(conn, sources=[source], embedder=mock_embedder)
    assert report2.counts["unchanged"] == 1
    assert mock_embedder.call_count == 0

    conn.close()


def test_metadata_update_makes_zero_embed_calls(tmp_path):
    """Assert a metadata-only update updates the docs table but calls embed zero times."""
    conn = db_connection(tmp_path / "hiqs.db")

    doc1 = Doc(
        source="mock",
        id="mock:1",
        title="Stable Title",
        body="Stable Body",
        url="http://v1.com",
    )
    source1 = MockSource("mock", [doc1])
    mock_embedder = MagicMock(return_value=[[0.1] * 384])

    report1 = project_docs(conn, sources=[source1], embedder=mock_embedder)
    assert report1.counts["inserted"] == 1
    assert mock_embedder.call_count == 1

    # Update metadata (url) but keep title and body identical
    doc2 = Doc(
        source="mock",
        id="mock:1",
        title="Stable Title",
        body="Stable Body",
        url="http://v2.com",
    )
    source2 = MockSource("mock", [doc2])
    mock_embedder.reset_mock()

    report2 = project_docs(conn, sources=[source2], embedder=mock_embedder)
    assert report2.counts["updated"] == 1
    assert mock_embedder.call_count == 0

    # Verify url was updated in docs table
    url = conn.execute("SELECT url FROM docs WHERE id = ?", ("mock:1",)).fetchone()[0]
    assert url == "http://v2.com"

    conn.close()


def test_atomic_vector_update_rollback_on_encoder_exception(tmp_path):
    """Assert encoder failure leaves DB state untouched so retry succeeds."""
    conn = db_connection(tmp_path / "hiqs.db")

    doc1 = Doc(source="mock", id="mock:1", title="V1 Title", body="V1 Body")
    source1 = MockSource("mock", [doc1])
    mock_embedder = MagicMock(return_value=[[0.1] * 384])

    project_docs(conn, sources=[source1], embedder=mock_embedder)

    # Now update doc content to V2, but embedder raises exception
    doc2 = Doc(source="mock", id="mock:1", title="V2 Title", body="V2 Body")
    source2 = MockSource("mock", [doc2])

    failing_embedder = MagicMock(side_effect=RuntimeError("GPU OOM"))

    with pytest.raises(RuntimeError, match="GPU OOM"):
        project_docs(conn, sources=[source2], embedder=failing_embedder)

    # DB must still have V1 Title, not V2 Title!
    title = conn.execute("SELECT title FROM docs WHERE id = ?", ("mock:1",)).fetchone()[0]
    assert title == "V1 Title"

    # Retry with working embedder succeed and updates to V2
    retry_embedder = MagicMock(return_value=[[0.2] * 384])
    report_retry = project_docs(conn, sources=[source2], embedder=retry_embedder)
    assert report_retry.counts["updated"] == 1

    title_after = conn.execute("SELECT title FROM docs WHERE id = ?", ("mock:1",)).fetchone()[0]
    assert title_after == "V2 Title"

    conn.close()


def test_source_identity_mismatch_raises_error(tmp_path):
    """Assert mismatched doc.source and source.name raises ValueError."""
    conn = db_connection(tmp_path / "hiqs.db")

    doc1 = Doc(source="wrong_source", id="mock:1", title="Title", body="Body")
    source = MockSource("expected_source", [doc1])
    mock_embedder = MagicMock(return_value=[[0.1] * 384])

    with pytest.raises(ValueError, match="Doc source 'wrong_source' does not match Source name 'expected_source'"):
        project_docs(conn, sources=[source], embedder=mock_embedder)

    conn.close()


def test_both_models_resident_and_vectors_coexist(tmp_path):
    """Assert two embedding models can coexist in docs_vec with different dims and vectors."""
    conn = db_connection(tmp_path / "hiqs.db")

    doc1 = Doc(
        source="mock",
        id="mock:1",
        title="Coexist Doc",
        body="Coexist Body",
    )
    source = MockSource("mock", [doc1])

    vec_minilm = [0.1] * 384
    vec_qwen = [0.5] * 1024

    mock_minilm = MagicMock(return_value=[vec_minilm])
    mock_qwen = MagicMock(return_value=[vec_qwen])

    # Embed under all-MiniLM-L6-v2
    project_docs(conn, sources=[source], model_name="all-MiniLM-L6-v2", embedder=mock_minilm)

    # Embed under Qwen3-Embedding-0.6B
    project_docs(conn, sources=[source], model_name="Qwen3-Embedding-0.6B", embedder=mock_qwen)

    # Both model rows must exist in docs_vec
    rows = conn.execute(
        "SELECT model, dim FROM docs_vec WHERE doc_id = ? ORDER BY model", ("mock:1",)
    ).fetchall()
    assert len(rows) == 2
    assert rows == [("Qwen3-Embedding-0.6B", 1024), ("all-MiniLM-L6-v2", 384)]

    # Reading one model does not return the other's vector
    res_minilm = get_doc_vector(conn, "mock:1", model_name="all-MiniLM-L6-v2")
    assert res_minilm is not None
    assert res_minilm[0] == 384
    assert pytest.approx(res_minilm[1]) == vec_minilm

    res_qwen = get_doc_vector(conn, "mock:1", model_name="Qwen3-Embedding-0.6B")
    assert res_qwen is not None
    assert res_qwen[0] == 1024
    assert pytest.approx(res_qwen[1]) == vec_qwen

    conn.close()


def test_reconciliation_removes_docs_vec_rows_for_pruned_chunks(tmp_path):
    """Assert within-unit reconciliation removes both docs and docs_vec rows for pruned chunks."""
    conn = db_connection(tmp_path / "hiqs.db")

    doc1 = Doc(source="mock", id="mock:chunk1", title="Doc 1", body="Body 1")
    doc2 = Doc(source="mock", id="mock:chunk2", title="Doc 2", body="Body 2")
    source = MockSource("mock", [doc1, doc2])

    mock_embedder = MagicMock(return_value=[[0.1] * 384, [0.2] * 384])

    project_docs(conn, sources=[source], embedder=mock_embedder)

    assert conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM docs_vec").fetchone()[0] == 2

    # Update source: doc2 pruned
    source_pruned = MockSource("mock", [doc1])
    project_docs(conn, sources=[source_pruned], embedder=mock_embedder)

    # doc2 pruned from docs and docs_vec
    doc_ids = [r[0] for r in conn.execute("SELECT id FROM docs").fetchall()]
    vec_doc_ids = [r[0] for r in conn.execute("SELECT doc_id FROM docs_vec").fetchall()]

    assert doc_ids == ["mock:chunk1"]
    assert vec_doc_ids == ["mock:chunk1"]

    conn.close()


def test_embed_ms_and_peak_rss_mb_recorded_in_meta(tmp_path):
    """Assert SyncReport.meta records embed_ms and peak_rss_mb."""
    conn = db_connection(tmp_path / "hiqs.db")

    doc1 = Doc(source="mock", id="mock:1", title="Title", body="Body")
    source = MockSource("mock", [doc1])
    mock_embedder = MagicMock(return_value=[[0.1] * 384])

    report = project_docs(conn, sources=[source], embedder=mock_embedder)

    assert "embed_ms" in report.meta
    assert isinstance(report.meta["embed_ms"], (int, float))
    assert report.meta["embed_ms"] >= 0

    assert "peak_rss_mb" in report.meta
    assert isinstance(report.meta["peak_rss_mb"], (int, float))
    assert report.meta["peak_rss_mb"] > 0

    conn.close()


def test_vector_serialization_roundtrip():
    """Test vector float array serialization and deserialization."""
    vec = [0.12345, -0.67890, 1.0, 0.0]
    dim, blob = serialize_vector(vec)
    assert dim == 4
    recovered = deserialize_vector(blob)
    assert pytest.approx(recovered) == vec

"""Tests for hiqs.docs_index module."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
import re
from unittest.mock import MagicMock

import pytest

from hiqs import docs_index
from hiqs.db import db_connection
from hiqs.docs_index import (
    deserialize_vector,
    get_doc_vector,
    get_linked_github_items,
    project_docs,
    serialize_vector,
)
from hiqs.plugins import Doc, Source, SyncReport


def _sql_writers(table: str) -> set[tuple[str, str]]:
    """Helper to analyze SQL statements writing to a table across all hiqs package modules using AST."""
    import hiqs

    writers = set()
    pkg_path = Path(hiqs.__file__).parent
    pattern = re.compile(
        rf"\b(INSERT\s+(?:OR\s+\w+\s+)?INTO|UPDATE|DELETE\s+FROM|REPLACE\s+INTO)\s+[\"`']?{table}[\"`']?\b",
        re.IGNORECASE,
    )

    for py_file in pkg_path.rglob("*.py"):
        if py_file.name == "db.py":
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except Exception:
            continue

        rel_path = py_file.relative_to(pkg_path.parent).as_posix()
        for function in (
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ):
            for call in (node for node in ast.walk(function) if isinstance(node, ast.Call)):
                call_args = call.args + [kw.value for kw in call.keywords]
                for argument in call_args:
                    if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                        if pattern.search(argument.value):
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
    """Assert docs table has exactly one writer across all hiqs modules: (hiqs/docs_index.py, project_docs)."""
    writers = _sql_writers("docs")
    assert writers == {("hiqs/docs_index.py", "project_docs")}


def _insert_github_item(conn, repo: str, item_type: str, number: int, title: str = "Linked item"):
    conn.execute(
        "INSERT INTO github_items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (repo, item_type, number, title, "", "open", f"https://github.com/{repo}/issues/{number}", "author", "", "2026-08-03", "2026-08-03"),
    )


def test_projection_records_only_resolved_literal_github_references(tmp_path):
    conn = db_connection(tmp_path / "hiqs.db")
    try:
        _insert_github_item(conn, "acme/widgets", "issue", 123, "Issue")
        _insert_github_item(conn, "acme/widgets", "pull_request", 42, "Pull request")
        _insert_github_item(conn, "other/service", "issue", 7, "Other issue")
        doc = Doc(
            source="vault",
            id="vault:decision",
            title="Decision",
            body="See #123, https://github.com/acme/widgets/pull/42, and other/service#7.",
            project="acme/widgets",
            unit="decision.md",
        )
        embedder = MagicMock()
        embedder.encode.return_value = [[0.1] * 3]

        project_docs(
            conn,
            sources=[MockSource("vault", [doc])],
            embedder=embedder,
            reports={"vault": SyncReport(counts={}, units_ok=("decision.md",))},
        )

        assert get_linked_github_items(conn, doc.id) == [
            ("acme/widgets", "issue", 123, "Issue", "https://github.com/acme/widgets/issues/123"),
            ("acme/widgets", "pull_request", 42, "Pull request", "https://github.com/acme/widgets/issues/42"),
            ("other/service", "issue", 7, "Other issue", "https://github.com/other/service/issues/7"),
        ]
    finally:
        conn.close()


def test_projection_drops_unresolved_and_false_positive_github_references(tmp_path):
    conn = db_connection(tmp_path / "hiqs.db")
    try:
        _insert_github_item(conn, "acme/widgets", "issue", 1)
        _insert_github_item(conn, "acme/widgets", "issue", 2)
        _insert_github_item(conn, "acme/widgets", "issue", 123)
        doc = Doc(
            source="vault",
            id="vault:false-positives",
            title="Decision",
            body=(
                "```python\n#123\n```\n"
                "Read https://example.test/newsletter#123. issue #1 of the newsletter. "
                "The actual item is #2, while #999 and https://github.com/acme/widgets/issues/888 are unresolved."
            ),
            project="acme/widgets",
            unit="decision.md",
        )
        no_context = Doc(source="vault", id="vault:no-context", title="No context", body="#2", unit="other.md")
        embedder = MagicMock()
        embedder.encode.return_value = [[0.1] * 3, [0.2] * 3]

        project_docs(
            conn,
            sources=[MockSource("vault", [doc, no_context])],
            embedder=embedder,
            reports={"vault": SyncReport(counts={}, units_ok=("decision.md", "other.md"))},
        )

        assert get_linked_github_items(conn, doc.id) == [
            ("acme/widgets", "issue", 2, "Linked item", "https://github.com/acme/widgets/issues/2")
        ]
        assert get_linked_github_items(conn, no_context.id) == []
    finally:
        conn.close()


def test_unchanged_projection_does_not_write_github_reference_edges(tmp_path):
    conn = db_connection(tmp_path / "hiqs.db")
    try:
        _insert_github_item(conn, "acme/widgets", "issue", 123)
        doc = Doc(source="vault", id="vault:decision", title="Decision", body="See #123", project="acme/widgets", unit="decision.md")
        source = MockSource("vault", [doc])
        report = SyncReport(counts={}, units_ok=("decision.md",))
        embedder = MagicMock()
        embedder.encode.return_value = [[0.1] * 3]
        project_docs(conn, sources=[source], embedder=embedder, reports={"vault": report})

        statements = []
        conn.set_trace_callback(statements.append)
        project_docs(conn, sources=[source], embedder=embedder, reports={"vault": report})
        conn.set_trace_callback(None)

        assert not any(
            statement.upper().startswith(("INSERT INTO DOC_GITHUB_REFS", "UPDATE DOC_GITHUB_REFS"))
            for statement in statements
        )
    finally:
        conn.close()


def test_failed_document_fetch_retains_existing_github_reference_edges(tmp_path):
    conn = db_connection(tmp_path / "hiqs.db")
    try:
        _insert_github_item(conn, "acme/widgets", "issue", 123)
        doc = Doc(source="vault", id="vault:decision", title="Decision", body="See #123", project="acme/widgets", unit="decision.md")
        embedder = MagicMock()
        embedder.encode.return_value = [[0.1] * 3]
        project_docs(
            conn,
            sources=[MockSource("vault", [doc])],
            embedder=embedder,
            reports={"vault": SyncReport(counts={}, units_ok=("decision.md",))},
        )

        def failed_docs(_connection):
            raise OSError("vault file could not be read")

        result = project_docs(
            conn,
            sources=[Source(name="vault", fetch=lambda *_args: SyncReport(counts={}), docs=failed_docs)],
            embedder=embedder,
            reports={"vault": SyncReport(counts={}, units_ok=("decision.md",))},
        )

        assert result.errors == ["Error fetching docs for source 'vault': vault file could not be read"]
        assert get_linked_github_items(conn, doc.id)[0][:3] == ("acme/widgets", "issue", 123)
    finally:
        conn.close()


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

    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = [[0.1] * 384]

    report1 = project_docs(conn, sources=[source], embedder=mock_embedder)
    assert report1.counts["inserted"] == 1
    assert mock_embedder.encode.call_count == 1

    # Second run with unchanged content
    mock_embedder.encode.reset_mock()
    report2 = project_docs(conn, sources=[source], embedder=mock_embedder)
    assert report2.counts["unchanged"] == 1
    assert mock_embedder.encode.call_count == 0

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
    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = [[0.1] * 384]

    report1 = project_docs(conn, sources=[source1], embedder=mock_embedder)
    assert report1.counts["inserted"] == 1
    assert mock_embedder.encode.call_count == 1

    # Update metadata (url) but keep title and body identical
    doc2 = Doc(
        source="mock",
        id="mock:1",
        title="Stable Title",
        body="Stable Body",
        url="http://v2.com",
    )
    source2 = MockSource("mock", [doc2])
    mock_embedder.encode.reset_mock()

    report2 = project_docs(conn, sources=[source2], embedder=mock_embedder)
    assert report2.counts["updated"] == 1
    assert mock_embedder.encode.call_count == 0

    # Verify url was updated in docs table
    url = conn.execute("SELECT url FROM docs WHERE id = ?", ("mock:1",)).fetchone()[0]
    assert url == "http://v2.com"

    conn.close()


def test_atomic_vector_update_rollback_on_encoder_exception(tmp_path):
    """Assert encoder failure leaves DB state untouched so retry succeeds."""
    conn = db_connection(tmp_path / "hiqs.db")

    doc1 = Doc(source="mock", id="mock:1", title="V1 Title", body="V1 Body")
    source1 = MockSource("mock", [doc1])
    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = [[0.1] * 384]

    project_docs(conn, sources=[source1], embedder=mock_embedder)

    # Now update doc content to V2, but embedder raises exception
    doc2 = Doc(source="mock", id="mock:1", title="V2 Title", body="V2 Body")
    source2 = MockSource("mock", [doc2])

    failing_embedder = MagicMock()
    failing_embedder.encode.side_effect = RuntimeError("GPU OOM")

    with pytest.raises(RuntimeError, match="GPU OOM"):
        project_docs(conn, sources=[source2], embedder=failing_embedder)

    # DB must still have V1 Title, not V2 Title!
    title = conn.execute("SELECT title FROM docs WHERE id = ?", ("mock:1",)).fetchone()[0]
    assert title == "V1 Title"

    # Retry with working embedder succeed and updates to V2
    retry_embedder = MagicMock()
    retry_embedder.encode.return_value = [[0.2] * 384]
    report_retry = project_docs(conn, sources=[source2], embedder=retry_embedder)
    assert report_retry.counts["updated"] == 1

    title_after = conn.execute("SELECT title FROM docs WHERE id = ?", ("mock:1",)).fetchone()[0]
    assert title_after == "V2 Title"

    conn.close()


def test_embedder_without_encode_method_raises_type_error(tmp_path):
    """Assert embedder lacking .encode() method raises TypeError."""
    conn = db_connection(tmp_path / "hiqs.db")
    doc1 = Doc(source="mock", id="mock:1", title="Title", body="Body")
    source = MockSource("mock", [doc1])

    plain_callable = lambda texts: [[0.1] * 384]

    with pytest.raises(TypeError, match="Embedder must have an encode method"):
        project_docs(conn, sources=[source], embedder=plain_callable)

    conn.close()


def test_malformed_encoder_result_raises_and_rolls_back(tmp_path):
    """Assert returning fewer vectors than requested raises ValueError and leaves DB empty."""
    conn = db_connection(tmp_path / "hiqs.db")

    doc1 = Doc(source="mock", id="mock:1", title="Title 1", body="Body 1")
    doc2 = Doc(source="mock", id="mock:2", title="Title 2", body="Body 2")
    source = MockSource("mock", [doc1, doc2])

    short_embedder = MagicMock()
    short_embedder.encode.return_value = [[0.1] * 384]  # 1 vector for 2 docs

    with pytest.raises(ValueError, match="Encoder returned 1 vectors, expected 2"):
        project_docs(conn, sources=[source], embedder=short_embedder)

    assert conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM docs_vec").fetchone()[0] == 0

    conn.close()


def test_cross_source_duplicate_doc_id_raises_error(tmp_path):
    """Assert duplicate doc IDs across sources raise ValueError to protect docs_vec."""
    conn = db_connection(tmp_path / "hiqs.db")

    doc1 = Doc(source="src1", id="shared:1", title="Title 1", body="Body 1")
    doc2 = Doc(source="src2", id="shared:1", title="Title 2", body="Body 2")
    s1 = MockSource("src1", [doc1])
    s2 = MockSource("src2", [doc2])

    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = [[0.1] * 384]

    with pytest.raises(ValueError, match="Duplicate doc ID 'shared:1' found across sources"):
        project_docs(conn, sources=[s1, s2], embedder=mock_embedder)

    # Also test existing DB collision
    project_docs(conn, sources=[s1], embedder=mock_embedder)

    doc2_colliding = Doc(source="src2", id="shared:1", title="Title 2", body="Body 2")
    s2_colliding = MockSource("src2", [doc2_colliding])

    with pytest.raises(ValueError, match="Doc ID 'shared:1' from source 'src2' collides with existing doc"):
        project_docs(conn, sources=[s2_colliding], embedder=mock_embedder)

    conn.close()


def test_source_identity_mismatch_raises_error(tmp_path):
    """Assert mismatched doc.source and source.name raises ValueError."""
    conn = db_connection(tmp_path / "hiqs.db")

    doc1 = Doc(source="wrong_source", id="mock:1", title="Title", body="Body")
    source = MockSource("expected_source", [doc1])
    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = [[0.1] * 384]

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

    mock_minilm = MagicMock()
    mock_minilm.encode.return_value = [vec_minilm]
    mock_qwen = MagicMock()
    mock_qwen.encode.return_value = [vec_qwen]

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

    doc1 = Doc(source="mock", id="mock:chunk1", title="Doc 1", body="Body 1", unit="mock:chunk1")
    doc2 = Doc(source="mock", id="mock:chunk2", title="Doc 2", body="Body 2", unit="mock:chunk2")
    source = MockSource("mock", [doc1, doc2])

    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = [[0.1] * 384, [0.2] * 384]

    rep1 = SyncReport(counts={}, units_ok=("mock:chunk1", "mock:chunk2"))
    project_docs(conn, sources=[source], embedder=mock_embedder, reports={"mock": rep1})

    assert conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM docs_vec").fetchone()[0] == 2

    # Update source: doc2 pruned
    source_pruned = MockSource("mock", [doc1])
    rep2 = SyncReport(counts={}, units_ok=("mock:chunk1", "mock:chunk2"))
    project_docs(conn, sources=[source_pruned], embedder=mock_embedder, reports={"mock": rep2})

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
    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = [[0.1] * 384]

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


def test_sql_writers_detects_async_function():
    """Assert _sql_writers AST scan catches async def functions writing to target table."""
    code = """
async def async_writer():
    cursor.execute("INSERT INTO docs (id) VALUES ('1')")
"""
    tree = ast.parse(code)
    pattern = re.compile(r"\bINSERT\s+INTO\s+docs\b", re.IGNORECASE)
    writers = set()
    for function in (
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ):
        for call in (node for node in ast.walk(function) if isinstance(node, ast.Call)):
            call_args = call.args + [kw.value for kw in call.keywords]
            for argument in call_args:
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    if pattern.search(argument.value):
                        writers.add(function.name)
    assert writers == {"async_writer"}


def test_preexisting_corrupt_db_duplicate_doc_id_raises_and_preserves(tmp_path):
    """Assert existing database containing duplicate doc ID across sources raises and preserves DB rows."""
    conn = db_connection(tmp_path / "hiqs.db")

    conn.execute(
        "INSERT INTO docs (source, id, title, body, url, ts, project, author) VALUES ('srcA', 'corrupt:1', 'T1', 'B1', '', '', '', '')"
    )
    conn.execute(
        "INSERT INTO docs (source, id, title, body, url, ts, project, author) VALUES ('srcB', 'corrupt:1', 'T2', 'B2', '', '', '', '')"
    )
    conn.commit()

    doc1 = Doc(source="srcA", id="corrupt:1", title="T1", body="B1")
    s1 = MockSource("srcA", [doc1])

    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = [[0.1] * 384]

    with pytest.raises(
        ValueError, match="Existing database contains duplicate doc ID 'corrupt:1' across multiple sources"
    ):
        project_docs(conn, sources=[s1], embedder=mock_embedder)

    rows = conn.execute("SELECT source, id FROM docs WHERE id = 'corrupt:1' ORDER BY source").fetchall()
    assert len(rows) == 2
    assert rows == [("srcA", "corrupt:1"), ("srcB", "corrupt:1")]

    conn.close()


def test_embed_ms_times_only_encode_and_reports_zero_when_no_encode(tmp_path, monkeypatch):
    """Assert embed_ms measures only encode() duration and returns 0 when no encoding runs."""
    conn = db_connection(tmp_path / "hiqs.db")

    doc1 = Doc(source="mock", id="mock:1", title="Title", body="Body")
    source = MockSource("mock", [doc1])

    clock = [100.0]

    def mock_perf_counter():
        return clock[0]

    monkeypatch.setattr("time.perf_counter", mock_perf_counter)

    def mock_encode(texts):
        clock[0] += 0.075  # 75 ms spent inside encode
        return [[0.1] * 384]

    mock_embedder = MagicMock()
    mock_embedder.encode.side_effect = mock_encode

    clock[0] += 5.0  # Simulate time spent outside encode

    report1 = project_docs(conn, sources=[source], embedder=mock_embedder)
    assert report1.meta["embed_ms"] == 75.0

    mock_embedder.encode.reset_mock()
    report2 = project_docs(conn, sources=[source], embedder=mock_embedder)
    assert report2.meta["embed_ms"] == 0.0

    conn.close()


def test_within_unit_reconciliation_retains_unfetched_sibling_units_and_vectors(tmp_path):
    """Assert within-unit reconciliation retains unfetched sibling units and vectors while pruning stale chunks in fetched units."""
    conn = db_connection(tmp_path / "hiqs.db")

    # Initial state: vault source with unit "one.md" (2 chunks) and unit "two.md" (1 chunk)
    doc_u1_c1 = Doc(source="vault", id="vault:one.md:h1", title="U1 C1", body="Body 1", unit="one.md")
    doc_u1_c2 = Doc(source="vault", id="vault:one.md:h2", title="U1 C2", body="Body 2", unit="one.md")
    doc_u2_c1 = Doc(source="vault", id="vault:two.md:h1", title="U2 C1", body="Body 3", unit="two.md")

    source_init = MockSource("vault", [doc_u1_c1, doc_u1_c2, doc_u2_c1])
    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = [[0.1] * 384, [0.2] * 384, [0.3] * 384]

    report_init = SyncReport(counts={}, units_ok=("one.md", "two.md"))
    report_res = project_docs(conn, sources=[source_init], embedder=mock_embedder, reports={"vault": report_init})
    assert report_res.counts["inserted"] == 3

    assert conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0] == 3
    assert conn.execute("SELECT COUNT(*) FROM docs_vec").fetchone()[0] == 3

    # Next sync: unit "two.md" was not fetched (e.g. read error), and unit "one.md" now only has chunk 1 (h2 stale)
    source_partial = MockSource("vault", [doc_u1_c1])
    mock_embedder.encode.reset_mock()

    report_partial_sync = SyncReport(counts={}, units_ok=("one.md",))
    report_partial = project_docs(conn, sources=[source_partial], embedder=mock_embedder, reports={"vault": report_partial_sync})

    # Pruned must be 1 (vault:one.md:h2 pruned), NOT 2 (vault:two.md:h1 retained)
    assert report_partial.counts["pruned"] == 1

    remaining_docs = [r[0] for r in conn.execute("SELECT id FROM docs ORDER BY id").fetchall()]
    assert remaining_docs == ["vault:one.md:h1", "vault:two.md:h1"]

    remaining_vecs = [r[0] for r in conn.execute("SELECT doc_id FROM docs_vec ORDER BY doc_id").fetchall()]
    assert remaining_vecs == ["vault:one.md:h1", "vault:two.md:h1"]

    conn.close()


def test_content_hash_helpers_and_delta_embedding(tmp_path):
    """Test compute_content_hash helper and verify metadata-only updates perform zero embed calls."""
    from hiqs.docs_index import compute_content_hash, get_embed_text

    text = get_embed_text("My Title", "My Body")
    assert text == "My Title\nMy Body"
    assert get_embed_text("", "Only Body") == "Only Body"

    h1 = compute_content_hash("My Title", "My Body")
    h2 = compute_content_hash("My Title", "My Body")
    assert h1 == h2

    conn = db_connection(tmp_path / "hiqs.db")
    doc = Doc(source="mock", id="mock:1", title="Title", body="Body", author="Alice")
    source = MockSource("mock", [doc])

    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = [[0.1] * 384]

    project_docs(conn, sources=[source], embedder=mock_embedder)
    assert mock_embedder.encode.call_count == 1

    # Update metadata (author) with identical title and body
    doc_updated = Doc(source="mock", id="mock:1", title="Title", body="Body", author="Bob")
    source_updated = MockSource("mock", [doc_updated])

    mock_embedder.encode.reset_mock()
    report = project_docs(conn, sources=[source_updated], embedder=mock_embedder)

    assert report.counts["updated"] == 1
    assert mock_embedder.encode.call_count == 0

    conn.close()


class MockSourceWithUnits:

    def __init__(self, name: str, docs_list: list[Doc], unit_names: list[str]):
        self.name = name
        self._docs = docs_list
        self._units = unit_names

    def fetch(self, conn, config):
        return SyncReport(counts={"inserted": len(self._docs)}, units_ok=self._units)

    def docs(self, conn):
        return self._docs

    def units(self, conn):
        return self._units


def test_explicit_successful_empty_unit_deletes_docs_and_vectors(tmp_path):
    """Assert a multi-chunk unit explicitly attested as successful but emitting zero docs is pruned along with its docs_vec rows, while unfetched siblings are retained."""
    conn = db_connection(tmp_path / "hiqs.db")

    # Initial state: unit "one.md" with 2 chunks, sibling unit "two.md" with 1 chunk
    doc_u1_c1 = Doc(source="vault", id="vault:one.md:chunk1", title="U1 C1", body="Body 1", unit="one.md")
    doc_u1_c2 = Doc(source="vault", id="vault:one.md:chunk2", title="U1 C2", body="Body 2", unit="one.md")
    doc_u2_c1 = Doc(source="vault", id="vault:two.md:chunk1", title="U2 C1", body="Body 3", unit="two.md")

    source_init = MockSource("vault", [doc_u1_c1, doc_u1_c2, doc_u2_c1])
    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = [[0.1] * 384, [0.2] * 384, [0.3] * 384]

    report_init = SyncReport(counts={}, units_ok=("one.md", "two.md"))
    report_res = project_docs(conn, sources=[source_init], embedder=mock_embedder, reports={"vault": report_init})
    assert report_res.counts["inserted"] == 3
    assert conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0] == 3
    assert conn.execute("SELECT COUNT(*) FROM docs_vec").fetchone()[0] == 3

    # Sync 2: unit "one.md" was successfully fetched but yields 0 chunks (empty content).
    # "one.md" is in successful units attestation. Sibling unit "two.md" was not fetched (absent from units attestation).
    source_empty_u1 = MockSource("vault", [])
    mock_embedder.encode.reset_mock()

    report_empty = SyncReport(counts={}, units_ok=("one.md",))
    report_sync2 = project_docs(conn, sources=[source_empty_u1], embedder=mock_embedder, reports={"vault": report_empty})

    # 2 chunks from "one.md" pruned, 0 from "two.md"
    assert report_sync2.counts["pruned"] == 2

    remaining_docs = [r[0] for r in conn.execute("SELECT id FROM docs ORDER BY id").fetchall()]
    assert remaining_docs == ["vault:two.md:chunk1"]

    remaining_vecs = [r[0] for r in conn.execute("SELECT doc_id FROM docs_vec ORDER BY doc_id").fetchall()]
    assert remaining_vecs == ["vault:two.md:chunk1"]

    conn.close()


def test_document_content_change_invalidates_all_model_vectors_until_reencoded(tmp_path):
    """Assert changing document payload invalidates all resident model vectors until re-encoded."""
    conn = db_connection(tmp_path / "hiqs.db")

    doc_v1 = Doc(source="mock", id="mock:1", title="Title 1", body="Body 1")
    source_v1 = MockSource("mock", [doc_v1])

    embedder_m1 = MagicMock()
    embedder_m1.encode.return_value = [[0.1] * 384]

    embedder_m2 = MagicMock()
    embedder_m2.encode.return_value = [[0.9] * 1024]

    # Embed under model 1 and model 2 for v1 content
    project_docs(conn, sources=[source_v1], model_name="model1", embedder=embedder_m1)
    project_docs(conn, sources=[source_v1], model_name="model2", embedder=embedder_m2)

    assert get_doc_vector(conn, "mock:1", "model1") is not None
    assert get_doc_vector(conn, "mock:1", "model2") is not None

    # Change content payload to v2
    doc_v2 = Doc(source="mock", id="mock:1", title="Title 1", body="Body 2 updated")
    source_v2 = MockSource("mock", [doc_v2])

    embedder_m1.encode.return_value = [[0.2] * 384]
    project_docs(conn, sources=[source_v2], model_name="model1", embedder=embedder_m1)

    # Model 1 has updated vector for v2
    vec1_v2 = get_doc_vector(conn, "mock:1", "model1")
    assert vec1_v2 is not None
    assert pytest.approx(vec1_v2[1]) == [0.2] * 384

    # Model 2 vector for old v1 content MUST BE INVALIDATED and return None
    assert get_doc_vector(conn, "mock:1", "model2") is None

    # Re-running project_docs under model 2 re-encodes new v2 payload
    embedder_m2.encode.return_value = [[0.8] * 1024]
    project_docs(conn, sources=[source_v2], model_name="model2", embedder=embedder_m2)

    vec2_v2 = get_doc_vector(conn, "mock:1", "model2")
    assert vec2_v2 is not None
    assert pytest.approx(vec2_v2[1]) == [0.8] * 1024

    conn.close()


def test_vault_source_successful_empty_unit_pruning_integration(tmp_path, monkeypatch):
    """Assert real vault source auto-reconciles empty fetched units when passed in reports."""
    from hiqs.sources import vault
    from hiqs.sources.vault import fetch as vault_fetch, SOURCE as VAULT_SOURCE

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    file1 = vault_dir / "note1.md"
    file1.write_text("# Heading 1\nContent 1\n# Heading 2\nContent 2")

    file2 = vault_dir / "note2.md"
    file2.write_text("# Heading A\nContent A")

    monkeypatch.setattr(vault, "_resolve_vault_path", lambda cfg=None: vault_dir)

    conn = db_connection(tmp_path / "hiqs.db")
    config = {"vault_path": vault_dir}

    # Initial sync
    report1 = vault_fetch(conn, config)
    mock_embedder = MagicMock()
    mock_embedder.encode.side_effect = lambda texts: [[0.1] * 384 for _ in texts]
    project_docs(
        conn,
        sources=[VAULT_SOURCE],
        embedder=mock_embedder,
        reports={"vault": report1},
    )

    assert conn.execute("SELECT COUNT(*) FROM docs WHERE id LIKE 'vault:note1.md:%'").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM docs WHERE id LIKE 'vault:note2.md:%'").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM docs_vec").fetchone()[0] == 3

    # Now make note1.md empty (0 chunks), while note2.md stays unchanged
    file1.write_text("")
    report2 = vault_fetch(conn, config)
    project_docs(
        conn,
        sources=[VAULT_SOURCE],
        embedder=mock_embedder,
        reports={"vault": report2},
    )

    # note1.md chunks and vectors must be pruned! note2.md stays.
    assert conn.execute("SELECT COUNT(*) FROM docs WHERE id LIKE 'vault:note1.md:%'").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM docs WHERE id LIKE 'vault:note2.md:%'").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM docs_vec").fetchone()[0] == 1

    conn.close()


def test_retained_raw_row_after_failed_partial_fetch_is_not_pruned(tmp_path):
    """Assert a unit whose raw row is retained in DB after a failed/partial fetch is NOT pruned when absent from successful units attestation."""
    conn = db_connection(tmp_path / "hiqs.db")

    # Seed vault_files raw tracking table with historical rows
    conn.execute(
        "CREATE TABLE IF NOT EXISTS vault_files(path TEXT PRIMARY KEY, content_hash TEXT NOT NULL, mtime TEXT NOT NULL)"
    )
    conn.execute("INSERT INTO vault_files VALUES ('u1.md', 'hash1', 'mtime1')")
    conn.execute("INSERT INTO vault_files VALUES ('u2_failed.md', 'hash2', 'mtime2')")
    conn.commit()

    doc_u1 = Doc(source="vault", id="vault:u1.md:chunk1", title="U1", body="Body 1", unit="u1.md")
    doc_u2 = Doc(source="vault", id="vault:u2_failed.md:chunk1", title="U2", body="Body 2", unit="u2_failed.md")

    source_init = MockSource("vault", [doc_u1, doc_u2])
    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = [[0.1] * 384, [0.2] * 384]

    # Initial projection
    rep_init = SyncReport(counts={}, units_ok=("u1.md", "u2_failed.md"))
    project_docs(conn, sources=[source_init], embedder=mock_embedder, reports={"vault": rep_init})
    assert conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM docs_vec").fetchone()[0] == 2

    # Second sync: u2_failed.md fetch failed (so u2_failed.md is NOT in units_ok).
    # u1.md fetch succeeded.
    source_sync2 = MockSource("vault", [doc_u1])
    mock_embedder.encode.reset_mock()

    rep_sync2 = SyncReport(counts={}, units_ok=("u1.md",))
    report_sync2 = project_docs(
        conn,
        sources=[source_sync2],
        embedder=mock_embedder,
        reports={"vault": rep_sync2},
    )

    # u2_failed.md must NOT be pruned despite vault_files raw table entry existing!
    assert report_sync2.counts["pruned"] == 0
    remaining_docs = [r[0] for r in conn.execute("SELECT id FROM docs ORDER BY id").fetchall()]
    assert remaining_docs == ["vault:u1.md:chunk1", "vault:u2_failed.md:chunk1"]

    remaining_vecs = [r[0] for r in conn.execute("SELECT doc_id FROM docs_vec ORDER BY doc_id").fetchall()]
    assert remaining_vecs == ["vault:u1.md:chunk1", "vault:u2_failed.md:chunk1"]

    conn.close()


def test_source_with_no_attestation_prunes_nothing(tmp_path):
    """Assert a source with no attestation (default units_ok=()) prunes nothing."""
    conn = db_connection(tmp_path / "hiqs.db")
    doc1 = Doc(source="fake", id="alpha:one", title="Title 1", body="Body 1", unit="alpha")
    source = MockSource("fake", [doc1])
    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = [[0.1] * 384]

    # Initial run without reports -> prunes nothing
    rep1 = project_docs(conn, sources=[source], embedder=mock_embedder)
    assert rep1.counts["inserted"] == 1

    # Run 2: empty docs returned, but no attestation (reports is None or units_ok=())
    empty_source = MockSource("fake", [])
    rep2 = project_docs(conn, sources=[empty_source], embedder=mock_embedder)
    assert rep2.counts["pruned"] == 0
    assert conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0] == 1
    conn.close()


def test_doc_unit_membership_and_colon_in_id(tmp_path):
    """Assert unit membership comes from Doc.unit (sole authority), get_doc_unit & _matches_unit are gone, and opaque colon IDs decouple from unit derivation."""
    assert not hasattr(docs_index, "get_doc_unit")
    assert not hasattr(docs_index, "_matches_unit")

    conn = db_connection(tmp_path / "hiqs.db")
    # Opaque ID that does NOT begin with its unit name
    doc1 = Doc(source="custom", id="opaque_hash_9999", title="T1", body="B1", unit="sub/dir:file.md")
    source = MockSource("custom", [doc1])
    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = [[0.1] * 384]

    report_sync1 = SyncReport(counts={}, units_ok=("sub/dir:file.md",))
    project_docs(conn, sources=[source], embedder=mock_embedder, reports={"custom": report_sync1})
    assert conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM docs_vec").fetchone()[0] == 1

    # Now empty source for sub/dir:file.md unit
    source_empty = MockSource("custom", [])
    report_sync2 = SyncReport(counts={}, units_ok=("sub/dir:file.md",))
    rep2 = project_docs(conn, sources=[source_empty], embedder=mock_embedder, reports={"custom": report_sync2})
    assert rep2.counts["pruned"] == 1
    assert conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM docs_vec").fetchone()[0] == 0

    conn.close()


def test_doc_with_empty_unit_is_not_pruned_when_id_is_attested(tmp_path):
    """Assert a Doc with empty unit is not pruned merely because an attested unit matches its ID, and becomes reconcilable once a real non-empty unit is supplied."""
    conn = db_connection(tmp_path / "hiqs.db")

    doc1 = Doc(source="custom", id="alpha", title="T1", body="B1", unit="")
    source1 = MockSource("custom", [doc1])
    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = [[0.1] * 384]

    report1 = SyncReport(counts={}, units_ok=("alpha",))
    project_docs(conn, sources=[source1], embedder=mock_embedder, reports={"custom": report1})
    assert conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0] == 1

    # Sync empty source with unit "alpha" attested: MUST NOT prune "alpha" because its unit was empty
    source_empty = MockSource("custom", [])
    report2 = SyncReport(counts={}, units_ok=("alpha",))
    rep2 = project_docs(conn, sources=[source_empty], embedder=mock_embedder, reports={"custom": report2})
    assert rep2.counts["pruned"] == 0
    assert conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0] == 1

    # Update doc with non-empty unit="alpha"
    doc2 = Doc(source="custom", id="alpha", title="T1", body="B1", unit="alpha")
    source2 = MockSource("custom", [doc2])
    report3 = SyncReport(counts={}, units_ok=("alpha",))
    project_docs(conn, sources=[source2], embedder=mock_embedder, reports={"custom": report3})
    assert conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0] == 1

    # Now sync empty source with unit "alpha" attested: MUST prune "alpha"
    rep4 = project_docs(conn, sources=[source_empty], embedder=mock_embedder, reports={"custom": report2})
    assert rep4.counts["pruned"] == 1
    assert conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0] == 0

    conn.close()


def test_encoding_is_batched_so_memory_cannot_grow_with_corpus_size():
    """BOUNDED (§18.3). One unbounded .encode() over 1,833 chunks hit 14.32 GiB on 2026-08-03."""
    from hiqs.docs_index import _encode_texts

    seen_batch_sizes = []

    class RecordingEmbedder:
        def encode(self, texts, **kwargs):
            seen_batch_sizes.append(len(texts))
            return [[float(len(t)), 0.0] for t in texts]

    texts = [f"chunk {n}" for n in range(150)]
    vectors = _encode_texts(RecordingEmbedder(), texts, batch_size=64)

    assert len(vectors) == 150               # nothing dropped by batching
    assert seen_batch_sizes == [64, 64, 22]  # bounded, and the remainder is not lost
    assert max(seen_batch_sizes) <= 64


def test_a_batch_size_below_one_is_rejected_rather_than_looping_forever():
    from hiqs.docs_index import _encode_texts

    class Embedder:
        def encode(self, texts, **kwargs):
            return [[0.0] for _ in texts]

    with pytest.raises(ValueError, match="at least 1"):
        _encode_texts(Embedder(), ["a", "b"], batch_size=0)

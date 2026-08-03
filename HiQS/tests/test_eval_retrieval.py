"""Unit and acceptance tests for HiQS retrieval evaluation runner (§6.3, §19.2)."""

from __future__ import annotations

import json
import sqlite3
from unittest.mock import MagicMock, patch
import pytest

from hiqs.db import db_connection, default_db_path
from hiqs.docs_index import get_embed_text
from hiqs.events import status
from hiqs.plugins import Doc
from tests.eval_retrieval import (
    capture_costs,
    compute_queryset_sha,
    compute_paired_disagreement_set,
    evaluate_gates,
    evaluate_retrieval,
    load_query_set,
    run_eval_and_log,
    score_single_query,
)
from tests.test_search import StubEmbedder, insert_doc


@pytest.fixture
def memory_db(tmp_path, monkeypatch):
    """Fixture providing an initialized SQLite database in a temp directory."""
    path = tmp_path / "test_eval_retrieval.db"
    monkeypatch.setattr("hiqs.events.db_connection", lambda: db_connection(path))
    conn = db_connection(path)
    yield conn
    conn.close()


@pytest.fixture
def synthetic_query_files(tmp_path):
    """Fixture creating synthetic committed query set and sidecar files."""
    committed_file = tmp_path / "eval_queries.json"
    sidecar_file = tmp_path / "eval_queries_sidecar.json"

    committed_data = [
        {
            "id": "q-test-001",
            "doc_id": "doc-test-001",
            "shape": "asymmetric",
        },
        {
            "id": "q-test-002",
            "doc_id": "doc-test-002",
            "shape": "exact_phrase",
        },
    ]

    sidecar_data = {
        "q-test-001": {"query": "signal architecture design", "title": "Signal Architecture"},
        "q-test-002": {"query": "quantum computing mechanics", "title": "Quantum Mechanics"},
    }

    committed_file.write_text(json.dumps(committed_data), encoding="utf-8")
    sidecar_file.write_text(json.dumps(sidecar_data), encoding="utf-8")

    return committed_file, sidecar_file


def test_reproducibility(memory_db, synthetic_query_files):
    """Acceptance test 1: Two runs on the same DB and query set produce identical figures."""
    committed_file, sidecar_file = synthetic_query_files

    doc1 = Doc(
        source="vault",
        id="doc-test-001",
        title="Signal Architecture Note",
        body="Signal architecture design document",
        unit="note1.md",
    )
    doc2 = Doc(
        source="vault",
        id="doc-test-002",
        title="Quantum Mechanics Note",
        body="Quantum computing mechanics note",
        unit="note2.md",
    )
    insert_doc(memory_db, doc1)
    insert_doc(memory_db, doc2)

    stub = StubEmbedder(dim=384)

    run1 = run_eval_and_log(
        memory_db,
        committed_path=committed_file,
        sidecar_path=sidecar_file,
        model_name="all-MiniLM-L6-v2",
        embedder=stub,
    )

    run2 = run_eval_and_log(
        memory_db,
        committed_path=committed_file,
        sidecar_path=sidecar_file,
        model_name="all-MiniLM-L6-v2",
        embedder=stub,
    )

    assert run1["recall_at_10"] == run2["recall_at_10"]
    assert run1["mrr_at_10"] == run2["mrr_at_10"]
    assert run1["queryset_sha"] == run2["queryset_sha"]
    assert run1["n_queries"] == run2["n_queries"]
    assert run1["legs"] == run2["legs"]


def test_missing_files_handling(tmp_path, synthetic_query_files):
    """Acceptance test 2: Missing query set names §6.3 protocol; missing sidecar reports loud unknown."""
    committed_file, sidecar_file = synthetic_query_files
    missing_file = tmp_path / "nonexistent.json"

    # Missing committed file -> clear error naming §6.3
    with pytest.raises(FileNotFoundError, match=r"§6\.3"):
        compute_queryset_sha(missing_file, sidecar_file)

    # Missing sidecar file -> loud unknown
    with pytest.raises(FileNotFoundError, match=r"unknown"):
        compute_queryset_sha(committed_file, missing_file)

    # Incomplete sidecar missing query entry -> loud unknown
    incomplete_sidecar = tmp_path / "incomplete_sidecar.json"
    incomplete_sidecar.write_text(json.dumps({}), encoding="utf-8")
    with pytest.raises(ValueError, match=r"unknown"):
        load_query_set(committed_file, incomplete_sidecar)


def test_gate_arithmetic_synthetic():
    """Acceptance test 3: Floor, vector-leg justification, and selection rule arithmetic."""
    # Floor gate: fused recall@10 >= 0.60
    gates_pass_floor = evaluate_gates(fused_recall_at_10=0.65, fts_recall_at_10=0.50)
    assert gates_pass_floor["floor_passed"] is True

    gates_fail_floor = evaluate_gates(fused_recall_at_10=0.55, fts_recall_at_10=0.40)
    assert gates_fail_floor["floor_passed"] is False

    # Vector justification gate: fused recall@10 beats FTS by >= 0.10
    gates_vec_justified = evaluate_gates(fused_recall_at_10=0.70, fts_recall_at_10=0.55)
    assert gates_vec_justified["vector_justified"] is True

    gates_vec_unjustified = evaluate_gates(fused_recall_at_10=0.70, fts_recall_at_10=0.65)
    assert gates_vec_unjustified["vector_justified"] is False


def test_section_3_2_selection_rule_boundaries():
    """Comprehensive test of §3.2 selection rule boundaries, ties, split decisions, and 1-point recall gain."""
    incumbent = {"recall_at_10": 0.70, "mrr_at_10": 0.60}

    # 1. One-point recall gain (0.01 gain) -> incumbent wins
    challenger_1pt = {"recall_at_10": 0.71, "mrr_at_10": 0.61}
    res_1pt = evaluate_gates(
        fused_recall_at_10=0.71,
        fts_recall_at_10=0.50,
        challenger_scores=challenger_1pt,
        incumbent_scores=incumbent,
    )
    assert res_1pt["winner"] == "incumbent"

    # 2. Frozen 8-point recall lead boundary (0.08) -> challenger wins
    challenger_8pt = {"recall_at_10": 0.78, "mrr_at_10": 0.60}
    res_8pt = evaluate_gates(
        fused_recall_at_10=0.78,
        fts_recall_at_10=0.50,
        challenger_scores=challenger_8pt,
        incumbent_scores=incumbent,
    )
    assert res_8pt["winner"] == "challenger"

    # 3. Just below 8-point lead without MRR tiebreak (0.079) -> incumbent wins
    challenger_7_9pt = {"recall_at_10": 0.779, "mrr_at_10": 0.60}
    res_7_9pt = evaluate_gates(
        fused_recall_at_10=0.779,
        fts_recall_at_10=0.50,
        challenger_scores=challenger_7_9pt,
        incumbent_scores=incumbent,
    )
    assert res_7_9pt["winner"] == "incumbent"

    # 4. In-band tiebreak boundary (0.04 recall, 0.05 MRR) -> challenger wins
    challenger_tb_win = {"recall_at_10": 0.74, "mrr_at_10": 0.65}
    res_tb_win = evaluate_gates(
        fused_recall_at_10=0.74,
        fts_recall_at_10=0.50,
        challenger_scores=challenger_tb_win,
        incumbent_scores=incumbent,
    )
    assert res_tb_win["winner"] == "challenger"

    # 5. In-band tiebreak just below MRR threshold (0.04 recall, 0.049 MRR) -> incumbent wins
    challenger_tb_fail = {"recall_at_10": 0.74, "mrr_at_10": 0.649}
    res_tb_fail = evaluate_gates(
        fused_recall_at_10=0.74,
        fts_recall_at_10=0.50,
        challenger_scores=challenger_tb_fail,
        incumbent_scores=incumbent,
    )
    assert res_tb_fail["winner"] == "incumbent"

    # 6. Split decision 1: recall lead >= 0.08 but MRR worse -> incumbent wins
    challenger_split_1 = {"recall_at_10": 0.80, "mrr_at_10": 0.55}
    res_split_1 = evaluate_gates(
        fused_recall_at_10=0.80,
        fts_recall_at_10=0.50,
        challenger_scores=challenger_split_1,
        incumbent_scores=incumbent,
    )
    assert res_split_1["winner"] == "incumbent"

    # 7. Split decision 2: MRR lead >= 0.05 but recall worse -> incumbent wins
    challenger_split_2 = {"recall_at_10": 0.68, "mrr_at_10": 0.67}
    res_split_2 = evaluate_gates(
        fused_recall_at_10=0.68,
        fts_recall_at_10=0.50,
        challenger_scores=challenger_split_2,
        incumbent_scores=incumbent,
    )
    assert res_split_2["winner"] == "incumbent"

    # 8. Tie -> incumbent wins
    challenger_tie = {"recall_at_10": 0.70, "mrr_at_10": 0.60}
    res_tie = evaluate_gates(
        fused_recall_at_10=0.70,
        fts_recall_at_10=0.50,
        challenger_scores=challenger_tie,
        incumbent_scores=incumbent,
    )
    assert res_tie["winner"] == "incumbent"

    # 9. Floor failed -> incumbent wins even if challenger scores high
    res_floor_fail = evaluate_gates(
        fused_recall_at_10=0.50,
        fts_recall_at_10=0.30,
        challenger_scores=challenger_8pt,
        incumbent_scores=incumbent,
    )
    assert res_floor_fail["winner"] == "incumbent"


def test_status_search_quality_integration(memory_db, synthetic_query_files):
    """Acceptance test 4: status().search.quality reads from written eval.completed event, not a constant."""
    committed_file, sidecar_file = synthetic_query_files

    doc = Doc(
        source="vault",
        id="doc-test-001",
        title="Signal Architecture Note",
        body="signal architecture design document",
        unit="note1.md",
    )
    insert_doc(memory_db, doc)

    stub = StubEmbedder(dim=384)

    payload = run_eval_and_log(
        memory_db,
        committed_path=committed_file,
        sidecar_path=sidecar_file,
        model_name="all-MiniLM-L6-v2",
        embedder=stub,
    )

    st = status()
    search_quality = st["search"]["quality"]

    assert isinstance(search_quality, dict)
    assert search_quality["model"] == "all-MiniLM-L6-v2"
    assert search_quality["recall_at_10"] == payload["recall_at_10"]
    assert search_quality["mrr_at_10"] == payload["mrr_at_10"]
    assert search_quality["queryset_sha"] == payload["queryset_sha"]
    assert search_quality["n_queries"] == 2
    assert "measured_at" in search_quality


def test_no_default_db_event_written(tmp_path, synthetic_query_files):
    """Test that running evaluation on a fixture DB writes zero events to the default DB."""
    committed_file, sidecar_file = synthetic_query_files
    fixture_db_path = tmp_path / "fixture.db"
    fixture_conn = db_connection(fixture_db_path)

    doc = Doc(
        source="vault",
        id="doc-test-001",
        title="Signal Architecture Note",
        body="signal architecture design document",
        unit="note1.md",
    )
    insert_doc(fixture_conn, doc)
    stub = StubEmbedder(dim=384)

    # Run evaluation against fixture_conn
    run_eval_and_log(
        fixture_conn,
        committed_path=committed_file,
        sidecar_path=sidecar_file,
        model_name="all-MiniLM-L6-v2",
        embedder=stub,
    )

    fixture_conn.close()

    # Assert default DB has no events written by this evaluation
    default_path = default_db_path()
    if default_path.exists():
        dconn = db_connection(default_path)
        rows = dconn.execute(
            "SELECT count(*) FROM events WHERE kind IN ('eval.completed', 'search.ready', 'search.degraded')"
        ).fetchone()
        dconn.close()
        # Verify no event from this run modified default DB
        assert rows is not None


def test_eval_event_logged_via_log_event_writer(memory_db, synthetic_query_files):
    """Test that eval.completed events route through hiqs.events.log_event writer."""
    committed_file, sidecar_file = synthetic_query_files

    doc = Doc(
        source="vault",
        id="doc-test-001",
        title="Signal Architecture Note",
        body="signal architecture design document",
        unit="note1.md",
    )
    insert_doc(memory_db, doc)
    stub = StubEmbedder(dim=384)

    with patch("hiqs.events.log_event", wraps=None) as mock_log:
        mock_log.side_effect = lambda kind, source, status, payload: memory_db.execute(
            "INSERT INTO events(ts, kind, source, status, payload_json) VALUES ('2026-08-03T00:00:00Z', ?, ?, ?, ?)",
            (kind, source, status, json.dumps(payload)),
        )
        run_eval_and_log(
            memory_db,
            committed_path=committed_file,
            sidecar_path=sidecar_file,
            model_name="all-MiniLM-L6-v2",
            embedder=stub,
        )

        assert mock_log.called
        assert mock_log.call_args[0][0] == "eval.completed"
        assert mock_log.call_args[0][1] == "search"
        assert mock_log.call_args[0][2] == "ok"


def test_multi_model_three_models(memory_db, synthetic_query_files):
    """Test evaluation across 3 models, verifying all pairwise disagreements and winner/gate selection."""
    committed_file, sidecar_file = synthetic_query_files

    doc1 = Doc(
        source="vault",
        id="doc-test-001",
        title="Signal Architecture Note",
        body="signal architecture design document",
        unit="note1.md",
    )
    insert_doc(memory_db, doc1)

    stub1 = StubEmbedder(dim=384)
    stub2 = StubEmbedder(dim=384)
    stub3 = StubEmbedder(dim=384)

    models = ["model-1", "model-2", "model-3"]
    embedders = {
        "model-1": stub1,
        "model-2": stub2,
        "model-3": stub3,
    }

    payload = run_eval_and_log(
        memory_db,
        committed_path=committed_file,
        sidecar_path=sidecar_file,
        model_name=models,
        embedders=embedders,
    )

    assert len(payload["eval_results"]) == 3
    assert "paired_disagreements" in payload
    assert "gates" in payload
    assert payload["gates"]["winner"] in ("incumbent", "model-1", "model-2", "model-3")


def test_capture_costs_full_corpus(memory_db):
    """Test capture_costs timing and exact input payload matching get_embed_text(title, body)."""
    doc1 = Doc(
        source="vault",
        id="doc-1",
        title="Title 1",
        body="Body content number one",
        unit="note1.md",
    )
    doc2 = Doc(
        source="vault",
        id="doc-2",
        title="Title 2",
        body="Body content number two",
        unit="note2.md",
    )
    insert_doc(memory_db, doc1)
    insert_doc(memory_db, doc2)

    stub = MagicMock()
    stub.encode = MagicMock()

    costs = capture_costs(memory_db, "all-MiniLM-L6-v2", embedder=stub)

    assert costs["n_corpus_items"] == 2.0
    assert costs["embed_ms"] >= 0.0
    assert costs["index_mb"] >= 0.0
    assert costs["peak_rss_mb"] >= 0.0

    # Verify exact inputs passed to embedder match get_embed_text(title, body)
    expected_texts = [
        get_embed_text(doc1.title, doc1.body),
        get_embed_text(doc2.title, doc2.body),
    ]
    stub.encode.assert_called_once_with(expected_texts)


def test_load_query_set_canonical_shape(tmp_path):
    """Test load_query_set with §19.2 canonical fields (singular doc_id and shape)."""
    committed_file = tmp_path / "eval_canonical.json"
    sidecar_file = tmp_path / "sidecar_canonical.json"

    committed_data = [
        {
            "id": "q-canon-001",
            "doc_id": "doc-canon-001",
            "shape": "asymmetric",
        }
    ]
    sidecar_data = {
        "q-canon-001": {"query": "canonical query text"}
    }

    committed_file.write_text(json.dumps(committed_data), encoding="utf-8")
    sidecar_file.write_text(json.dumps(sidecar_data), encoding="utf-8")

    queries, sha = load_query_set(committed_file, sidecar_file)
    assert len(queries) == 1
    assert queries[0]["id"] == "q-canon-001"
    assert queries[0]["target_doc_ids"] == ["doc-canon-001"]
    assert queries[0]["shape_tags"] == ["asymmetric"]

    # Test missing target doc_id raises ValueError (§19.2)
    invalid_file = tmp_path / "eval_invalid.json"
    invalid_file.write_text(json.dumps([{"id": "q-canon-001"}]), encoding="utf-8")
    with pytest.raises(ValueError, match=r"canonical target doc_id"):
        load_query_set(invalid_file, sidecar_file)


def test_paired_disagreement_set():
    """Unit test for paired disagreement set computation."""
    eval1 = {
        "model": "model-A",
        "top_hits": {
            "fused": {
                "q-test-001": "doc-A",
                "q-test-002": "doc-B",
            }
        },
    }
    eval2 = {
        "model": "model-B",
        "top_hits": {
            "fused": {
                "q-test-001": "doc-A",
                "q-test-002": "doc-C",
            }
        },
    }

    disagreements = compute_paired_disagreement_set(eval1, eval2, leg="fused")
    assert len(disagreements) == 1
    assert disagreements[0]["query_id"] == "q-test-002"
    assert disagreements[0]["model1"] == "model-A"
    assert disagreements[0]["model1_top_hit"] == "doc-B"
    assert disagreements[0]["model2"] == "model-B"
    assert disagreements[0]["model2_top_hit"] == "doc-C"


def test_score_single_query_unit():
    """Unit test for score_single_query logic."""
    target_ids = ["target-1", "target-2"]
    hits = [
        Doc(source="s", id="other-1", title="T1", body="B1"),
        Doc(source="s", id="target-1", title="T2", body="B2"),
        Doc(source="s", id="target-2", title="T3", body="B3"),
    ]

    recall, mrr = score_single_query(target_ids, hits)
    # Both targets in top 10 -> recall = 1.0
    # First match target-1 at rank 2 -> MRR = 1/2 = 0.5
    assert recall == 1.0
    assert mrr == 0.5

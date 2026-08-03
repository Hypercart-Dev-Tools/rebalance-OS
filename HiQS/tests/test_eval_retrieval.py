"""Unit and acceptance tests for HiQS retrieval evaluation runner (§6.3, §19.2)."""

from __future__ import annotations

import json
import sqlite3
import pytest

from hiqs.db import db_connection
from hiqs.events import status
from hiqs.plugins import Doc
from tests.eval_retrieval import (
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
            "target_doc_ids": ["doc-test-001"],
            "shape_tags": ["asymmetric"],
        },
        {
            "id": "q-test-002",
            "target_doc_ids": ["doc-test-002"],
            "shape_tags": ["exact_phrase"],
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

    # Selection rule (§3.2): ties and split decisions go to incumbent
    incumbent = {"recall_at_10": 0.70, "mrr_at_10": 0.60}

    # Clear challenger win
    challenger_win = {"recall_at_10": 0.80, "mrr_at_10": 0.70}
    res_win = evaluate_gates(
        fused_recall_at_10=0.80,
        fts_recall_at_10=0.60,
        challenger_scores=challenger_win,
        incumbent_scores=incumbent,
    )
    assert res_win["winner"] == "challenger"

    # Tie -> incumbent wins
    challenger_tie = {"recall_at_10": 0.70, "mrr_at_10": 0.60}
    res_tie = evaluate_gates(
        fused_recall_at_10=0.70,
        fts_recall_at_10=0.50,
        challenger_scores=challenger_tie,
        incumbent_scores=incumbent,
    )
    assert res_tie["winner"] == "incumbent"

    # Split decision (higher recall, lower MRR) -> incumbent wins
    challenger_split = {"recall_at_10": 0.75, "mrr_at_10": 0.55}
    res_split = evaluate_gates(
        fused_recall_at_10=0.75,
        fts_recall_at_10=0.50,
        challenger_scores=challenger_split,
        incumbent_scores=incumbent,
    )
    assert res_split["winner"] == "incumbent"

    # Floor failed -> incumbent wins even if challenger metrics higher
    res_floor_fail = evaluate_gates(
        fused_recall_at_10=0.50,
        fts_recall_at_10=0.30,
        challenger_scores=challenger_win,
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

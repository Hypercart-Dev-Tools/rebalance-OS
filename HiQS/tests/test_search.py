"""Unit and acceptance tests for HiQS hybrid retrieval path (search.py)."""

from __future__ import annotations

import sqlite3
from typing import Any

import numpy as np
import pytest

from hiqs.db import db_connection
from hiqs.docs_index import deserialize_vector, serialize_vector
from hiqs.events import status
from hiqs.plugins import Doc
from hiqs.search import cap_per_document, rrf_fuse, search


class StubEmbedder:
    """Offline stub embedder producing deterministic normalized vectors."""

    def __init__(self, dim: int = 384, mappings: dict[str, list[float]] | None = None):
        self.dim = dim
        self.mappings = mappings or {}

    def encode(self, texts: list[str]) -> list[list[float]]:
        results = []
        for text in texts:
            if text in self.mappings:
                vec = self.mappings[text]
            else:
                # Deterministic pseudo-random vector based on text hash
                seed = sum(ord(c) for c in text) % 1000
                rng = np.random.default_rng(seed)
                vec = rng.normal(size=self.dim).astype(np.float32)
                vec = (vec / np.linalg.norm(vec)).tolist()
            results.append(vec)
        return results


@pytest.fixture
def memory_db(tmp_path, monkeypatch):
    """Fixture providing an initialized SQLite database in a temp directory."""
    path = tmp_path / "test_search.db"
    monkeypatch.setattr("hiqs.events.db_connection", lambda: db_connection(path))
    conn = db_connection(path)
    yield conn
    conn.close()


def insert_doc(conn: sqlite3.Connection, doc: Doc, model_vecs: dict[str, list[float]] | None = None):
    """Helper to insert a doc and optional model vectors into DB."""
    with conn:
        conn.execute("CREATE TABLE IF NOT EXISTS doc_units (doc_id TEXT PRIMARY KEY, unit TEXT NOT NULL)")
        conn.execute(
            "INSERT INTO docs (source, id, title, body, url, ts, project, author) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (doc.source, doc.id, doc.title, doc.body, doc.url, doc.ts, doc.project, doc.author),
        )
        if doc.unit:
            conn.execute(
                "INSERT INTO doc_units (doc_id, unit) VALUES (?, ?)",
                (doc.id, doc.unit),
            )
        if model_vecs:
            for model_name, vec in model_vecs.items():
                dim, blob = serialize_vector(vec)
                conn.execute(
                    "INSERT INTO docs_vec (doc_id, model, dim, vec) VALUES (?, ?, ?, ?)",
                    (doc.id, model_name, dim, blob),
                )


def test_model_filter_with_coexisting_vectors(memory_db):
    """Acceptance test 1: With 384-dim and 1024-dim vectors both resident, search returns correct results and does not raise.

    Removing the WHERE model = <active> filter must make the test fail.
    """
    v384 = [1.0] + [0.0] * 383
    v1024 = [1.0] + [0.0] * 1023

    doc1 = Doc(source="vault", id="doc1", title="MiniLM Doc", body="Content for doc 1", unit="doc1.md")
    doc2 = Doc(source="vault", id="doc2", title="Qwen Doc", body="Content for doc 2", unit="doc2.md")

    # doc1 has both 384-dim (MiniLM) and 1024-dim (Qwen3) vectors
    # doc2 has 1024-dim vector
    insert_doc(memory_db, doc1, {"all-MiniLM-L6-v2": v384, "Qwen3-Embedding-0.6B": v1024})
    insert_doc(memory_db, doc2, {"Qwen3-Embedding-0.6B": v1024})

    stub384 = StubEmbedder(dim=384, mappings={"test": v384})

    # Search with model filter active MUST succeed
    hits = search("test", limit=10, connection=memory_db, model_name="all-MiniLM-L6-v2", embedder=stub384)
    assert len(hits) > 0
    assert hits[0].id == "doc1"

    # Demonstrate that removing model filter causes failure on inhomogeneous shapes
    raw_unfiltered_rows = memory_db.execute("SELECT doc_id, dim, vec FROM docs_vec").fetchall()

    vec_list = [serialize_vector(deserialize_vector(r[2]))[1] for r in raw_unfiltered_rows]
    # Check that extracting vectors without model filter yields different dimensions
    dims = [r[1] for r in raw_unfiltered_rows]
    assert 384 in dims and 1024 in dims

    # Attempting to stack inhomogeneous vectors into numpy matrix without filter raises ValueError
    deserialized_list = [deserialize_vector(r[2]) for r in raw_unfiltered_rows]
    with pytest.raises(ValueError):
        np.array(deserialized_list, dtype=np.float32)


def test_per_document_cap(memory_db):
    """Acceptance test 2: A query matching five headings of one note returns at most 2 of its chunks in top-10,

    and other relevant notes are not starved.
    """
    # Insert 5 chunks of Note A
    for i in range(1, 6):
        doc = Doc(
            source="vault",
            id=f"vault:noteA.md:h{i}",
            title=f"Note A Section {i}",
            body="Rebalance OS signal architecture heading search",
            unit="noteA.md",
        )
        insert_doc(memory_db, doc)

    # Insert 3 chunks of Note B
    for i in range(1, 4):
        doc = Doc(
            source="vault",
            id=f"vault:noteB.md:h{i}",
            title=f"Note B Section {i}",
            body="Rebalance OS signal architecture alternative heading",
            unit="noteB.md",
        )
        insert_doc(memory_db, doc)

    stub = StubEmbedder(dim=384)
    hits = search("signal architecture", limit=10, connection=memory_db, embedder=stub)

    # Count hits per document unit
    note_a_hits = [h for h in hits if h.unit == "noteA.md"]
    note_b_hits = [h for h in hits if h.unit == "noteB.md"]

    assert len(note_a_hits) <= 2
    assert len(note_b_hits) >= 1
    assert len(hits) > len(note_a_hits)  # Note B is not starved!


def test_degrade_rungs(memory_db, monkeypatch):
    """Acceptance test 3: Force model unavailable and assert status.search.mode reports fts_only

    and search.degraded event is written. Force probe unreadable and assert unknown.
    """
    doc = Doc(
        source="vault",
        id="doc_fts",
        title="FTS Fallback Test",
        body="Exact match topic for degrade testing",
        unit="doc_fts.md",
    )
    insert_doc(memory_db, doc)

    class FailingEmbedder:
        def encode(self, texts: list[str]):
            raise RuntimeError("Model weight loading failed")

    # Run search with failing embedder
    hits = search("degrade testing", connection=memory_db, embedder=FailingEmbedder())

    # Search falls back to FTS5 and returns hit
    assert len(hits) == 1
    assert hits[0].id == "doc_fts"

    # Verify search.degraded event was written to events table
    event_row = memory_db.execute(
        "SELECT kind, status, payload_json FROM events WHERE kind = 'search.degraded' ORDER BY rowid DESC LIMIT 1"
    ).fetchone()

    assert event_row is not None
    assert event_row[0] == "search.degraded"
    assert event_row[1] == "warn"

    # Verify status.search.mode reports fts_only when using this DB
    st = status()
    assert st["search"]["mode"] == "fts_only"

    # Force probe unreadable
    def unreadable_db():
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr("hiqs.events.db_connection", unreadable_db)

    unreadable_st = status()
    assert unreadable_st["search"]["mode"] == "unknown"


def test_exact_phrase_vs_paraphrase(memory_db):
    """Acceptance test 4: Exact-phrase queries resolve through FTS leg; paraphrases resolve through vector leg."""
    doc_fts = Doc(
        source="vault",
        id="doc_exact",
        title="Quantum Mechanics Note",
        body="Contains verbatim exact keyphrase quantum computing mechanics here.",
        unit="doc_exact.md",
    )

    doc_vec = Doc(
        source="vault",
        id="doc_para",
        title="Physics Computation Note",
        body="Discusses subatomic particle calculation methods.",
        unit="doc_para.md",
    )

    vec_query = [0.9, 0.1] + [0.0] * 382
    vec_para = [0.85, 0.15] + [0.0] * 382
    vec_exact = [0.0, 1.0] + [0.0] * 382

    insert_doc(memory_db, doc_fts, {"all-MiniLM-L6-v2": vec_exact})
    insert_doc(memory_db, doc_vec, {"all-MiniLM-L6-v2": vec_para})

    stub = StubEmbedder(dim=384, mappings={"subatomic calculation": vec_query})

    # Exact phrase matching
    exact_hits = search('"quantum computing mechanics"', connection=memory_db, embedder=stub)
    assert len(exact_hits) > 0
    assert exact_hits[0].id == "doc_exact"

    # Paraphrase matching via vector leg
    para_hits = search("subatomic calculation", connection=memory_db, embedder=stub)
    assert len(para_hits) > 0
    assert para_hits[0].id == "doc_para"


def test_cap_per_document_unit():
    """Unit test for cap_per_document function."""
    hits = [
        Doc(source="vault", id="vault:n1:h1", title="T1", body="B1", unit="n1.md"),
        Doc(source="vault", id="vault:n1:h2", title="T2", body="B2", unit="n1.md"),
        Doc(source="vault", id="vault:n1:h3", title="T3", body="B3", unit="n1.md"),
        Doc(source="vault", id="vault:n2:h1", title="T4", body="B4", unit="n2.md"),
    ]
    capped = cap_per_document(hits, max_chunks=2)
    assert len(capped) == 3
    assert [d.id for d in capped] == ["vault:n1:h1", "vault:n1:h2", "vault:n2:h1"]


def test_rrf_fuse_unit():
    """Unit test for reciprocal rank fusion."""
    doc1 = Doc(source="s", id="d1", title="T1", body="B1")
    doc2 = Doc(source="s", id="d2", title="T2", body="B2")
    doc3 = Doc(source="s", id="d3", title="T3", body="B3")

    fts_list = [doc1, doc2]
    vec_list = [doc2, doc3]

    fused = rrf_fuse(fts_list, vec_list, k=60)
    # doc2 is in both (rank 2 in FTS, rank 1 in vec) -> score = 1/62 + 1/61
    # doc1 is rank 1 in FTS -> score = 1/61
    # doc3 is rank 2 in vec -> score = 1/62
    # So doc2 should be rank 1 in fused output
    assert fused[0].id == "d2"


def test_precise_search_is_byte_identical_with_affinity_on_or_off(memory_db):
    doc = Doc(source="vault", id="precise:1", title="Exact maintenance ticket", body="repair", unit="precise.md")
    insert_doc(memory_db, doc)
    stub = StubEmbedder(dim=384)
    enabled = search("exact maintenance ticket", connection=memory_db, embedder=stub, affinity=True)
    disabled = search("exact maintenance ticket", connection=memory_db, embedder=stub, affinity=False)
    assert enabled == disabled


def test_a_question_matches_on_its_distinctive_terms_not_all_of_them(memory_db):
    """FTS5's implicit operator is AND, so a question demanded every word in one chunk.

    Measured on the real corpus that returned 35 hits across 22 queries and all 35 were the
    operator's own prompt log — the only text containing a question verbatim is the record of
    it being asked. With the log excluded the lexical leg returned nothing, so hybrid search
    was silently running on the vector leg alone.
    """
    from hiqs.search import _fts_search

    doc = Doc(source="vault", id="d1", title="Architecture decision record storage",
              body="ADR documents live under docs/adr.", unit="n1.md")
    insert_doc(memory_db, doc)

    hits = _fts_search(memory_db, "Where is the earlier generated ADR doc stored?")

    # Not one word of "where/earlier/generated" appears in the note, and it must still match.
    assert [h.id for h in hits] == ["d1"]


def test_explicit_fts_syntax_is_honoured_not_rewritten(memory_db):
    from hiqs.search import _fts_expression

    assert _fts_expression('"exact phrase here"') == '"exact phrase here"'
    assert _fts_expression("alpha AND bravo") == "alpha AND bravo"


def test_a_plain_question_becomes_an_or_expression():
    from hiqs.search import _fts_expression

    assert _fts_expression("Where is the ADR?") == '"Where" OR "is" OR "the" OR "ADR"'


def test_hyphenated_and_versioned_terms_survive_tokenisation():
    """GH-172 and ask-self are how the operator actually refers to things (§6.3 jargon)."""
    from hiqs.search import _fts_expression

    assert _fts_expression("status of GH-172") == '"status" OR "of" OR "GH-172"'

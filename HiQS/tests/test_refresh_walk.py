"""Tests for §5's one refresh walk — the seam nothing owned until now.

Every part of this path was built and tested in isolation across three marathons, and the
suite was green at 133 tests while the system had never ingested a single real file. These
tests exist so that cannot be true again.
"""

from __future__ import annotations

import pytest

from hiqs import events
from hiqs.__main__ import refresh
from hiqs.db import db_connection
from hiqs.plugins import Doc, Source, SyncReport


class StubEmbedder:
    """Deterministic offline encoder. Tests never touch the network (§6.3).

    Load-bearing: docs_index.get_default_embedder() calls SentenceTransformer(model_name)
    with no local_files_only, so an unstubbed projection DOWNLOADS a model. That is how the
    first run of this file hung.
    """

    def encode(self, texts, **kwargs):
        return [[float(len(t) % 7), 1.0, 0.0] for t in texts]


def _ok_source(name, docs_out, *, unit="u1"):
    return Source(
        name=name,
        fetch=lambda conn, cfg: SyncReport(counts={"inserted": len(docs_out)}, units_ok=(unit,)),
        docs=lambda conn: docs_out,
    )


def _doc(source, ident, title, unit="u1"):
    return Doc(source=source, id=ident, title=title, body=f"{title} body", unit=unit)


@pytest.fixture
def wired(tmp_path, monkeypatch):
    path = tmp_path / "hiqs.db"
    monkeypatch.setattr(events, "db_connection", lambda: db_connection(path))
    return db_connection(path)


def test_a_walk_turns_configuration_into_a_searchable_corpus(wired, monkeypatch):
    source = _ok_source("alpha", [_doc("alpha", "alpha:1", "Release checklist")])
    monkeypatch.setattr("hiqs.__main__.discover_sources", lambda: [source])

    summary = refresh(connection=wired, config={}, embedder=StubEmbedder())

    assert summary["sources"]["alpha"] == {"inserted": 1}
    assert summary["errors"] == {}
    rows = wired.execute("SELECT id, title FROM docs").fetchall()
    assert rows == [("alpha:1", "Release checklist")]


def test_one_failing_source_does_not_abort_the_walk(wired, monkeypatch):
    def explode(conn, cfg):
        raise RuntimeError("network gone")

    bad = Source(name="bad", fetch=explode, docs=lambda conn: [])
    good = _ok_source("good", [_doc("good", "good:1", "Survived")])
    monkeypatch.setattr("hiqs.__main__.discover_sources", lambda: [bad, good])

    summary = refresh(connection=wired, config={}, embedder=StubEmbedder())

    assert "RuntimeError: network gone" in summary["errors"]["bad"]
    assert summary["sources"]["good"] == {"inserted": 1}  # plugin rule 5: the walk continued
    assert wired.execute("SELECT id FROM docs").fetchall() == [("good:1",)]


def test_a_source_that_raised_is_kept_out_of_the_projection(wired, monkeypatch):
    """A failed fetch has no units_ok, and absent attestation must never authorise pruning."""
    survivor = _doc("flaky", "flaky:1", "Existing row")
    ok = _ok_source("flaky", [survivor])
    monkeypatch.setattr("hiqs.__main__.discover_sources", lambda: [ok])
    refresh(connection=wired, config={}, embedder=StubEmbedder())
    assert wired.execute("SELECT count(*) FROM docs").fetchone()[0] == 1

    def explode(conn, cfg):
        raise TimeoutError("source timed out")

    monkeypatch.setattr(
        "hiqs.__main__.discover_sources",
        lambda: [Source(name="flaky", fetch=explode, docs=lambda conn: [])],
    )
    summary = refresh(connection=wired, config={}, embedder=StubEmbedder())

    assert "TimeoutError" in summary["errors"]["flaky"]
    # The row survives: a source that could not fetch cannot cause a deletion.
    assert wired.execute("SELECT id FROM docs").fetchall() == [("flaky:1",)]


def test_a_failed_walk_is_reported_not_swallowed(wired, monkeypatch):
    monkeypatch.setattr(
        "hiqs.__main__.discover_sources",
        lambda: [Source(name="bad", fetch=lambda c, f: (_ for _ in ()).throw(OSError("disk")), docs=None)],
    )
    refresh(connection=wired, config={}, embedder=StubEmbedder())

    kinds = [row[0] for row in wired.execute("SELECT kind FROM events ORDER BY rowid").fetchall()]
    assert "sync.failed" in kinds
    statuses = [r[0] for r in wired.execute("SELECT status FROM events WHERE kind='sync.failed'").fetchall()]
    assert statuses == ["error"]


def test_a_source_that_reports_errors_without_raising_is_still_a_failed_walk(wired, monkeypatch):
    """Observed live: all seven GitHub repos failed, and refresh printed errors:{} and exited 0.

    github's fetch catches per-repo failures and returns them in SyncReport.errors rather than
    raising, so the exception handler above never saw them. A scheduled job reading the exit
    code could not tell that run from a clean one.
    """
    partial = Source(
        name="github",
        fetch=lambda conn, cfg: SyncReport(counts={}, errors=["repo a: 403", "repo b: 403"]),
        docs=lambda conn: [],
    )
    monkeypatch.setattr("hiqs.__main__.discover_sources", lambda: [partial])

    summary = refresh(connection=wired, config={}, embedder=StubEmbedder())

    assert summary["errors"] == {}  # nothing raised
    assert summary["source_errors"] == {"github": ["repo a: 403", "repo b: 403"]}


def test_naming_a_source_that_does_not_exist_is_loud(wired, monkeypatch):
    monkeypatch.setattr("hiqs.__main__.discover_sources", lambda: [_ok_source("alpha", [])])

    summary = refresh(["alpha", "typo"], connection=wired, config={}, embedder=StubEmbedder())

    # Silently refreshing nothing and reporting success is the exact failure this project
    # exists to kill, so a misnamed source is named rather than ignored.
    assert summary["unknown_sources"] == ["typo"]


def test_selecting_one_source_leaves_the_others_untouched(wired, monkeypatch):
    a = _ok_source("alpha", [_doc("alpha", "alpha:1", "A")])
    b = _ok_source("beta", [_doc("beta", "beta:1", "B")])
    monkeypatch.setattr("hiqs.__main__.discover_sources", lambda: [a, b])
    refresh(connection=wired, config={}, embedder=StubEmbedder())
    assert wired.execute("SELECT count(*) FROM docs").fetchone()[0] == 2

    summary = refresh(["alpha"], connection=wired, config={}, embedder=StubEmbedder())
    assert set(summary["sources"]) == {"alpha"}
    # beta was never fetched this run, so its rows must survive untouched.
    assert wired.execute("SELECT count(*) FROM docs WHERE source='beta'").fetchone()[0] == 1

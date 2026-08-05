"""Integration tests for GitHub documents in the unified search index."""

from __future__ import annotations

from unittest.mock import MagicMock

from hiqs.db import db_connection
from hiqs.docs_index import project_docs
from hiqs.plugins import Doc, Source, SyncReport
from hiqs.search import search
from hiqs.sources import github


def _insert_item(
    connection, repo: str, item_type: str, number: int, title: str, body: str, state: str,
    activity_at: str, *, updated_at: str = "2026-08-03T12:00:00Z",
):
    connection.execute(
        "INSERT INTO github_items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            repo, item_type, number, title, body, state,
            f"https://github.com/{repo}/issues/{number}", "octocat", "",
            updated_at, activity_at,
        ),
    )


def _embedder():
    embedder = MagicMock()
    embedder.encode.side_effect = lambda texts: [[0.1, 0.2, 0.3] for _ in texts]
    return embedder


def test_github_docs_index_closed_items_with_vault_and_are_idempotent(tmp_path, monkeypatch):
    """Closed GitHub work is searchable beside vault docs without re-embedding unchanged rows."""
    connection = db_connection(tmp_path / "hiqs.db")
    try:
        monkeypatch.setattr("hiqs.search.log_event", lambda *_args: None)
        _insert_item(
            connection, "acme/widgets", "issue", 7, "Closed retrieval decision",
            "Archaeology says this retrieval work is finished.", "closed", "2026-08-01T09:00:00Z",
            updated_at="2026-08-03T12:00:00Z",
        )
        _insert_item(
            connection, "acme/widgets", "pull_request", 8, "Open indexing PR",
            "Makes GitHub items searchable.", "open", "2026-08-02T09:00:00Z",
        )
        vault_doc = Doc(
            source="vault", id="vault:retrieval", title="Vault retrieval context",
            body="Retrieval notes from the vault.", unit="retrieval.md",
        )
        vault = Source(name="vault", fetch=lambda *_args: SyncReport(counts={}), docs=lambda _conn: [vault_doc])
        embedder = _embedder()

        github_docs = list(github.docs(connection))
        closed = next(doc for doc in github_docs if doc.id == "github:acme/widgets#7")
        assert closed == Doc(
            source="github", id="github:acme/widgets#7", title="Closed retrieval decision",
            body="Archaeology says this retrieval work is finished.",
            url="https://github.com/acme/widgets/issues/7", ts="2026-08-01T09:00:00Z",
            project="acme/widgets", author="octocat", unit="acme/widgets",
        )

        reports = {
            "github": SyncReport(counts={}, units_ok=("acme/widgets",)),
            "vault": SyncReport(counts={}, units_ok=("retrieval.md",)),
        }
        first = project_docs(connection, sources=[github.SOURCE, vault], embedder=embedder, reports=reports)
        assert first.counts["inserted"] == 3
        assert connection.execute("SELECT COUNT(*) FROM docs").fetchone()[0] == 3

        hits = search("retrieval", connection=connection, embedder=embedder)
        assert {hit.id for hit in hits} >= {"github:acme/widgets#7", "vault:retrieval"}

        embedder.encode.reset_mock()
        second = project_docs(connection, sources=[github.SOURCE, vault], embedder=embedder, reports=reports)
        assert second.counts["inserted"] == second.counts["updated"] == 0
        assert second.counts["unchanged"] == 3
        assert embedder.encode.call_count == 0
    finally:
        connection.close()


def test_github_reconciliation_only_prunes_attested_repositories(tmp_path):
    """A failed repo is retained while a successfully scanned sibling reconciles normally."""
    connection = db_connection(tmp_path / "hiqs.db")
    try:
        _insert_item(connection, "acme/good", "issue", 1, "Good old item", "stale", "open", "2026-08-01T00:00:00Z")
        _insert_item(connection, "acme/failed", "issue", 2, "Failed old item", "stale", "open", "2026-08-01T00:00:00Z")
        embedder = _embedder()
        initial_report = SyncReport(counts={}, units_ok=("acme/good", "acme/failed"))
        project_docs(connection, sources=[github.SOURCE], embedder=embedder, reports={"github": initial_report})

        # No documents are returned this projection. Only the successful repo is attested,
        # so its old document may reconcile; the failed sibling must remain untouched.
        connection.execute("DELETE FROM github_items")
        connection.commit()
        result = project_docs(
            connection,
            sources=[github.SOURCE],
            embedder=embedder,
            reports={"github": SyncReport(counts={}, units_ok=("acme/good",))},
        )

        assert result.counts["pruned"] == 1
        assert connection.execute("SELECT id FROM docs ORDER BY id").fetchall() == [
            ("github:acme/failed#2",)
        ]
    finally:
        connection.close()

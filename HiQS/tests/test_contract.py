"""Seam-level source contract tests — the L23 guard against future source drift."""

from __future__ import annotations

import ast
import inspect

import pytest

from hiqs import events
from hiqs.db import db_connection
from hiqs.plugins import discover_sources

from fake_source import NETWORK_TIMEOUT_SECONDS, SOURCE


class FakeEntryPoint:
    """A distribution entry point without installing a package in the test env."""

    def load(self):
        return SOURCE


def _fetched_unit(*, timeout):
    assert timeout == NETWORK_TIMEOUT_SECONDS
    return {"unit": "alpha", "records": [("one", "Fake title", "Fake body")]}


def _sql_writers(module, table: str) -> set[str]:
    tree = ast.parse(inspect.getsource(module))
    writers = set()
    for function in (
        node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ):
        for call in (node for node in ast.walk(function) if isinstance(node, ast.Call)):
            for argument in call.args + [keyword.value for keyword in call.keywords]:
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    if f"INSERT INTO {table}".upper() in argument.value.upper():
                        writers.add(function.name)
    return writers


def test_fake_source_is_discovered_only_through_the_entry_point(monkeypatch):
    monkeypatch.setattr("hiqs.plugins.metadata.entry_points", lambda *, group: (FakeEntryPoint(),))

    assert discover_sources() == [SOURCE]


def test_fake_source_reaches_docs_and_status_without_a_core_edit(tmp_path, monkeypatch):
    path = tmp_path / "hiqs.db"
    connection = db_connection(path)
    watermark = {}
    try:
        report = SOURCE.fetch(connection, {"fetch_unit": _fetched_unit, "watermark": watermark})
        assert report.counts == {"inserted": 1, "pruned": 0}
        assert [document.id for document in SOURCE.docs(connection)] == ["alpha:one"]
    finally:
        connection.close()

    monkeypatch.setattr(events, "db_connection", lambda: db_connection(path))
    events.log_event("sync.completed", "fake", "ok", {"counts": report.counts})
    assert events.status()["sources"]["fake"]["status"] == "ok"
    assert watermark == {"last_completed_unit": "alpha"}


def test_candidate_attestation_is_total_for_the_fake_source(tmp_path):
    connection = db_connection(tmp_path / "hiqs.db")
    try:
        SOURCE.fetch(connection, {"fetch_unit": _fetched_unit, "watermark": {}})
        candidates = list(SOURCE.candidates(connection, {}))
    finally:
        connection.close()

    assert candidates
    assert all(candidate.source and candidate.evidence and candidate.why for candidate in candidates)


def test_fake_fetch_advances_its_watermark_only_after_a_completed_fetch(tmp_path):
    connection = db_connection(tmp_path / "hiqs.db")
    watermark = {"last_completed_unit": "previous"}

    def failed_fetch(*, timeout):
        assert timeout == NETWORK_TIMEOUT_SECONDS
        raise TimeoutError("source timed out")

    try:
        with pytest.raises(TimeoutError):
            SOURCE.fetch(connection, {"fetch_unit": failed_fetch, "watermark": watermark})
        assert watermark == {"last_completed_unit": "previous"}

        SOURCE.fetch(connection, {"fetch_unit": _fetched_unit, "watermark": watermark})
        assert watermark == {"last_completed_unit": "alpha"}
    finally:
        connection.close()


def test_fake_reconciliation_is_limited_to_the_successfully_fetched_unit(tmp_path):
    connection = db_connection(tmp_path / "hiqs.db")
    try:
        connection.execute(
            "CREATE TABLE fake_source_records(unit TEXT, id TEXT, title TEXT, body TEXT, PRIMARY KEY(unit, id))"
        )
        connection.executemany(
            "INSERT INTO fake_source_records VALUES (?, ?, ?, ?)",
            [("alpha", "obsolete", "Old", "Old body"), ("beta", "keep", "Keep", "Keep body")],
        )
        report = SOURCE.fetch(connection, {"fetch_unit": _fetched_unit, "watermark": {}})
        rows = connection.execute(
            "SELECT unit, id FROM fake_source_records ORDER BY unit, id"
        ).fetchall()
    finally:
        connection.close()

    assert report.counts["pruned"] == 1
    assert rows == [("alpha", "one"), ("beta", "keep")]


def test_every_network_boundary_in_the_fake_fetch_receives_an_explicit_timeout(tmp_path):
    observed_timeouts = []

    def timeout_recording_fetch(*, timeout):
        observed_timeouts.append(timeout)
        return {"unit": "alpha", "records": []}

    connection = db_connection(tmp_path / "hiqs.db")
    try:
        SOURCE.fetch(connection, {"fetch_unit": timeout_recording_fetch, "watermark": {}})
    finally:
        connection.close()

    assert observed_timeouts == [NETWORK_TIMEOUT_SECONDS]


def test_log_event_is_the_only_events_table_writer():
    assert _sql_writers(events, "events") == {"log_event"}


def test_projection_is_the_only_docs_table_writer():
    from hiqs import docs_index

    assert _sql_writers(docs_index, "docs") == {"project_docs"}


def test_projection_is_the_only_github_reference_edge_writer():
    from hiqs import docs_index

    assert _sql_writers(docs_index, "doc_github_refs") == {"project_docs"}


@pytest.mark.xfail(strict=True, reason="M3 owns ranking; this protects the fake-source path until then.")
def test_fake_candidates_reach_the_single_ranking_seam(tmp_path):
    from hiqs.ranking import rank

    connection = db_connection(tmp_path / "hiqs.db")
    try:
        SOURCE.fetch(connection, {"fetch_unit": _fetched_unit, "watermark": {}})
        assert rank(list(SOURCE.candidates(connection, {})))
    finally:
        connection.close()

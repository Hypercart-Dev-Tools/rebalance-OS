"""Tests for local, attested sibling-project affinity edges."""

from __future__ import annotations

import inspect
import json
import pathlib

import pytest

from hiqs import affinity
from hiqs.affinity import AffinityDoc, append_affinity_hits, rebuild_project_affinity
from hiqs.db import db_connection
from hiqs.plugins import Doc


def _project(connection, name: str, aliases: list[str], repos: list[str]) -> None:
    connection.execute(
        "INSERT INTO projects(name, aliases_json, repos_json) VALUES (?, ?, ?)",
        (name, json.dumps(aliases), json.dumps(repos)),
    )


def _item(connection, repo: str, number: int, title: str) -> None:
    connection.execute(
        "INSERT INTO github_items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (repo, "issue", number, title, "", "open", "", "author", "", "2026-08-03", "2026-08-03"),
    )


def _doc(connection, ident: str, project: str, title: str) -> None:
    connection.execute(
        "INSERT INTO docs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("github", ident, title, "work item", "", "2026-08-03", project, "author"),
    )


def test_same_org_edges_are_canonical_and_work_without_name_tokens(tmp_path):
    connection = db_connection(tmp_path / "hiqs.db")
    try:
        _project(connection, "North", ["north work"], ["orbit/north"])
        _project(connection, "South", ["south work"], ["orbit/south"])
        _item(connection, "orbit/north", 1, "Release work")
        _item(connection, "orbit/south", 2, "Release work")
        assert rebuild_project_affinity(connection, include_name_tokens=False) == 1
        assert connection.execute("SELECT project_a, project_b, edge FROM project_affinity").fetchall() == [
            ("North", "South", "same_org")
        ]
    finally:
        connection.close()


def test_name_token_edges_ignore_generic_and_short_tokens(tmp_path):
    connection = db_connection(tmp_path / "hiqs.db")
    try:
        _project(connection, "Atlas Billing", [], ["one/atlas-a"])
        _project(connection, "Atlas Mobile", [], ["two/atlas-b"])
        _project(connection, "API Web", [], ["three/api-web"])
        _project(connection, "Web Dev", [], ["four/web-dev"])
        assert rebuild_project_affinity(connection) == 1
        assert connection.execute("SELECT project_a, project_b, edge FROM project_affinity").fetchall() == [
            ("Atlas Billing", "Atlas Mobile", "name_token")
        ]
    finally:
        connection.close()


def test_widening_appends_attested_siblings_without_changing_direct_hits(tmp_path):
    connection = db_connection(tmp_path / "hiqs.db")
    try:
        _project(connection, "North", ["orbit program"], ["orbit/north"])
        _project(connection, "South", ["south work"], ["orbit/south"])
        _item(connection, "orbit/north", 1, "Release checklist")
        _item(connection, "orbit/south", 2, "Release checklist")
        _doc(connection, "north:1", "North", "North direct work")
        _doc(connection, "south:1", "South", "South sibling work")
        rebuild_project_affinity(connection, include_name_tokens=False)
        direct = [Doc(source="github", id="north:1", title="North direct work", body="work item", project="North")]

        widened = append_affinity_hits(connection, "orbit program release", direct, limit=5)
        assert widened[0] == direct[0]
        assert isinstance(widened[1], AffinityDoc)
        assert widened[1].id == "south:1"
        assert widened[1].affinity_edge == "same_org"
        assert append_affinity_hits(
            connection, "orbit program release", direct, limit=5, enabled_edges=frozenset()
        ) == direct
        assert append_affinity_hits(connection, "unrelated exact request", direct, limit=5) == direct
    finally:
        connection.close()


def test_issue_title_edge_is_query_time_only(tmp_path):
    connection = db_connection(tmp_path / "hiqs.db")
    try:
        _project(connection, "One", ["one program"], ["one/repo"])
        _project(connection, "Two", ["two program"], ["two/repo"])
        _item(connection, "one/repo", 1, "Invoice migration")
        _item(connection, "two/repo", 2, "Invoice follow-up")
        _doc(connection, "two:1", "Two", "Two work")
        rebuild_project_affinity(connection, include_name_tokens=False)
        direct = [Doc(source="github", id="one:1", title="One work", body="", project="One")]
        widened = append_affinity_hits(connection, "one program invoice", direct, limit=5)
        assert widened[1].affinity_edge == "issue_title"
        assert connection.execute("SELECT edge FROM project_affinity").fetchall() == []
    finally:
        connection.close()


def test_affinity_module_has_no_operator_specific_literals():
    """Guard §19.2 without becoming the leak it guards.

    The first version of this test asserted one client name inline — which put that
    name in a file destined for a public repo, and pinned the check to a single
    string. The forbidden list therefore lives in a gitignored sidecar, the same
    split §19.2 already mandates for the eval sets. Absent sidecar reports a loud
    skip, never a silent pass: the blocking full-history scan at Phase 6 is the
    backstop, not this test.
    """
    sidecar = pathlib.Path(__file__).with_name("private_names.txt")
    if not sidecar.exists():
        pytest.skip(
            f"UNKNOWN, not pass: {sidecar.name} absent, so no name check ran. "
            "Create it (one lowercase name per line, gitignored) to enforce locally; "
            "the Phase 6 pre-extraction history scan remains the blocking gate."
        )

    forbidden = [
        line.strip().casefold()
        for line in sidecar.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert forbidden, f"{sidecar.name} exists but lists no names — an empty guard is not a guard"

    source = inspect.getsource(affinity).casefold()
    assert [name for name in forbidden if name in source] == []

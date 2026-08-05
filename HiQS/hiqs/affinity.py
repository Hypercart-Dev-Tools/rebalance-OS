"""Derive sibling-project edges and append their documents after direct hits."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
import sqlite3

from hiqs.plugins import Doc


_TOKEN_RE = re.compile(r"[a-z][a-z0-9]*")
_STOP_TOKENS = frozenset(
    {
        "and", "app", "api", "code", "dev", "docs", "for", "from", "main",
        "our", "project", "repo", "service", "test", "tests", "the", "tool",
        "tools", "web", "with", "www",
    }
)
_EDGE_WEIGHTS = {"same_org": 1.0, "name_token": 0.5}


@dataclass(frozen=True)
class AffinityDoc(Doc):
    """A sibling document with the persisted or query-time edge that admitted it."""

    affinity_edge: str = ""


def _strings(value: str) -> tuple[str, ...]:
    """Decode a JSON string list without trusting registry data blindly."""
    try:
        decoded = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return ()
    if not isinstance(decoded, list):
        return ()
    return tuple(item.strip() for item in decoded if isinstance(item, str) and item.strip())


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in _TOKEN_RE.findall(value.casefold())
        if len(token) >= 3 and not token.isdigit() and token not in _STOP_TOKENS
    }


def _project_rows(connection: sqlite3.Connection) -> dict[str, tuple[set[str], set[str]]]:
    """Return each project as (registered repos, significant name tokens)."""
    projects: dict[str, tuple[set[str], set[str]]] = {}
    for name, aliases_json, repos_json in connection.execute(
        "SELECT name, aliases_json, repos_json FROM projects"
    ):
        aliases = _strings(aliases_json)
        repos = {repo.casefold() for repo in _strings(repos_json)}
        projects[name] = (repos, _tokens(" ".join((name, *aliases))))
    return projects


def _canonical_pair(project_a: str, project_b: str) -> tuple[str, str]:
    return (project_a, project_b) if project_a < project_b else (project_b, project_a)


def rebuild_project_affinity(connection: sqlite3.Connection, *, include_name_tokens: bool = True) -> int:
    """Replace persisted same-org and optional shared-name affinity edges from local rows."""
    projects = _project_rows(connection)
    edges: dict[tuple[str, str, str], float] = {}

    owners_by_repo = {
        repo.casefold(): repo.partition("/")[0].casefold()
        for (repo,) in connection.execute("SELECT DISTINCT repo FROM github_items")
        if "/" in repo
    }
    project_owners = {
        name: {owners_by_repo[repo] for repo in repos if repo in owners_by_repo}
        for name, (repos, _tokens_for_project) in projects.items()
    }
    names = sorted(projects)
    for index, project_a in enumerate(names):
        repos_a, tokens_a = projects[project_a]
        for project_b in names[index + 1 :]:
            repos_b, tokens_b = projects[project_b]
            if project_owners[project_a] & project_owners[project_b]:
                edges[(*_canonical_pair(project_a, project_b), "same_org")] = _EDGE_WEIGHTS["same_org"]
            if include_name_tokens and tokens_a & tokens_b:
                edges[(*_canonical_pair(project_a, project_b), "name_token")] = _EDGE_WEIGHTS["name_token"]

    with connection:
        connection.execute("DELETE FROM project_affinity")
        connection.executemany(
            "INSERT INTO project_affinity(project_a, project_b, edge, weight) VALUES (?, ?, ?, ?)",
            [(*key, weight) for key, weight in sorted(edges.items())],
        )
    return len(edges)


def _query_projects(connection: sqlite3.Connection, query: str) -> set[str]:
    """Find projects explicitly named by a meaningful registry name or alias in a query."""
    query_tokens = _tokens(query)
    matched: set[str] = set()
    for name, aliases_json in connection.execute("SELECT name, aliases_json FROM projects"):
        labels = (name, *_strings(aliases_json))
        if any((label_tokens := _tokens(label)) and label_tokens <= query_tokens for label in labels):
            matched.add(name)
    return matched


def _issue_title_edges(
    connection: sqlite3.Connection, query: str, projects: dict[str, tuple[set[str], set[str]]]
) -> set[tuple[str, str]]:
    """Compute query-time sibling pairs whose issue titles share a query term."""
    terms = _tokens(query)
    if not terms:
        return set()
    repos_by_project = {name: repos for name, (repos, _tokens_for_project) in projects.items()}
    matching_projects: set[str] = set()
    for repo, title in connection.execute("SELECT repo, title FROM github_items"):
        if terms & _tokens(title):
            repo_key = repo.casefold()
            matching_projects.update(name for name, repos in repos_by_project.items() if repo_key in repos)
    names = sorted(matching_projects)
    return {_canonical_pair(project_a, project_b) for index, project_a in enumerate(names) for project_b in names[index + 1 :]}


def _sibling_edges(
    connection: sqlite3.Connection,
    query: str,
    direct_projects: set[str],
    enabled_edges: frozenset[str] | None,
) -> dict[str, str]:
    """Return each sibling's strongest attested edge, without changing direct-project order."""
    selected: dict[str, tuple[float, str]] = {}
    for project_a, project_b, edge, weight in connection.execute(
        "SELECT project_a, project_b, edge, weight FROM project_affinity"
    ):
        if enabled_edges is not None and edge not in enabled_edges:
            continue
        for direct, sibling in ((project_a, project_b), (project_b, project_a)):
            if direct in direct_projects:
                candidate = (float(weight), edge)
                if candidate > selected.get(sibling, (-1.0, "")):
                    selected[sibling] = candidate

    if enabled_edges is None or "issue_title" in enabled_edges:
        issue_pairs = _issue_title_edges(connection, query, _project_rows(connection))
        for project_a, project_b in issue_pairs:
            for direct, sibling in ((project_a, project_b), (project_b, project_a)):
                if direct in direct_projects and (sibling not in selected or selected[sibling][0] < _EDGE_WEIGHTS["name_token"]):
                    selected[sibling] = (_EDGE_WEIGHTS["name_token"], "issue_title")
    return {project: edge for project, (_weight, edge) in selected.items()}


def append_affinity_hits(
    connection: sqlite3.Connection,
    query: str,
    direct_hits: list[Doc],
    limit: int,
    *,
    enabled_edges: frozenset[str] | None = None,
) -> list[Doc]:
    """Append sibling-project docs below direct hits, never displacing or reordering them."""
    if len(direct_hits) >= limit:
        return direct_hits[:limit]
    direct_projects = _query_projects(connection, query)
    if not direct_projects:
        return direct_hits[:limit]

    sibling_edges = _sibling_edges(connection, query, direct_projects, enabled_edges)
    if not sibling_edges:
        return direct_hits[:limit]
    direct_ids = {doc.id for doc in direct_hits}
    widened = list(direct_hits)
    for sibling, edge in sorted(sibling_edges.items()):
        rows = connection.execute(
            """
            SELECT source, id, title, body, url, ts, project, author
            FROM docs WHERE project = ? ORDER BY ts DESC, id
            """,
            (sibling,),
        ).fetchall()
        for row in rows:
            if row[1] in direct_ids:
                continue
            widened.append(AffinityDoc(*row, affinity_edge=edge))
            direct_ids.add(row[1])
            if len(widened) == limit:
                return widened
    return widened

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class Project(BaseModel):
    name: str
    status: str = "active"
    summary: str = ""
    repos: list[str] = Field(default_factory=list)
    # When true, every repo under ``repos`` is an EXTERNAL repo to monitor for
    # everyone's activity (commits/PRs), not the operator's own work. Watched
    # externals enter the watched set and get a whole-repo github_activity rollup
    # (see rebalance.ingest.github_watch). A dedicated "Watched — …" project with
    # external: true is the intended container.
    external: bool = False
    # Where this project entered the system (lifecycle contract, Phase 5):
    # "remote-activity" (GitHub activity discovery), "vault-note" (vault title
    # discovery), "inferred" (activity inference); "local-scan" is reserved for
    # the Phase 6 git-pulse promotion. "" = legacy/operator-entered rows.
    provenance: str = ""
    obsidian_folder: str | None = None
    tags: list[str] = Field(default_factory=list)
    value_level: str | None = None
    priority_tier: int | None = None
    risk_level: str | None = None
    custom_fields: dict[str, Any] = Field(default_factory=dict)
    computed: dict[str, Any] = Field(default_factory=dict)
    last_activity_at: str | None = None  # ISO 8601; used for activity-based filtering


class Registry(BaseModel):
    active_projects: list[Project] = Field(default_factory=list)
    # Activity-based potential project segmentation
    most_likely_active_projects: list[Project] = Field(default_factory=list)  # Activity in last 14 days
    semi_active_projects: list[Project] = Field(default_factory=list)  # Activity 15-30 days ago
    dormant_projects: list[Project] = Field(default_factory=list)  # Activity 31+ days ago
    # Legacy fallback for projects without detectable activity
    potential_projects: list[Project] = Field(default_factory=list)
    archived_projects: list[Project] = Field(default_factory=list)


YAML_BLOCK_PATTERN = re.compile(r"```ya?ml\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _default_registry_markdown() -> str:
    payload = Registry().model_dump(mode="json")
    yaml_content = yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)
    return f"""# Project Registry

Canonical project list for rebalance ingest and scoring.

Sections:
- `active_projects`: currently tracked and scored
- `most_likely_active_projects`: GitHub activity last 14 days
- `semi_active_projects`: GitHub activity 15-30 days ago
- `dormant_projects`: GitHub activity 31+ days ago
- `potential_projects`: candidates with no activity signals (vault-only discoveries)
- `archived_projects`: historical records

```yaml
{yaml_content}```
"""


def _extract_yaml_block(markdown: str) -> dict[str, Any]:
    match = YAML_BLOCK_PATTERN.search(markdown)
    if not match:
        return Registry().model_dump(mode="json")
    block = match.group(1).strip()
    parsed = yaml.safe_load(block) or {}
    if not isinstance(parsed, dict):
        return Registry().model_dump(mode="json")
    return parsed


def read_registry(registry_path: Path) -> Registry:
    """Pure read: parse the registry file, or return an empty Registry when
    it doesn't exist. Never touches the filesystem — the right call for
    read-only paths (discovery) where creating the registry file would lie
    to the setup-status contract (`registry_exists` flipping done before any
    confirmation)."""
    if not registry_path.exists():
        return Registry()
    raw = registry_path.read_text(encoding="utf-8")
    parsed = _extract_yaml_block(raw)
    return Registry.model_validate(parsed)


def load_registry(registry_path: Path) -> Registry:
    """Read the registry, creating the default file first when missing.

    Write-path variant: only confirmation-gated flows should call this —
    read-only paths use :func:`read_registry`."""
    if not registry_path.exists():
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(_default_registry_markdown(), encoding="utf-8")
    return read_registry(registry_path)


def save_registry(registry_path: Path, registry: Registry) -> None:
    payload = registry.model_dump(mode="json")
    yaml_content = yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)
    content = f"""# Project Registry

Canonical project list for rebalance ingest and scoring.

Sections:
- `active_projects`: currently tracked and scored
- `most_likely_active_projects`: GitHub activity last 14 days
- `semi_active_projects`: GitHub activity 15-30 days ago
- `dormant_projects`: GitHub activity 31+ days ago
- `potential_projects`: candidates with no activity signals (vault-only discoveries)
- `archived_projects`: historical records

```yaml
{yaml_content}```
"""
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(content, encoding="utf-8")


def _registry_to_projection(registry: Registry) -> dict[str, Any]:
    projects = []
    for project in registry.active_projects:
        # Persist the typed ``external`` flag inside custom_fields_json so it
        # round-trips through the project_registry table without a schema column
        # (get_projects already decodes custom_fields, and read paths that open
        # via ensure_project_schema without running migrations keep working).
        custom_fields = dict(project.custom_fields)
        if project.external:
            custom_fields["external"] = True
        # Same pattern as ``external``: provenance rides in custom_fields_json
        # so it round-trips through the fixed project_registry columns.
        if project.provenance:
            custom_fields["provenance"] = project.provenance
        projects.append(
            {
                "name": project.name,
                "summary": project.summary,
                "status": project.status,
                "value_level": project.value_level,
                "priority_tier": project.priority_tier,
                "risk_level": project.risk_level,
                "repos": project.repos,
                "obsidian_folder": project.obsidian_folder,
                "tags": project.tags,
                "custom_fields": custom_fields,
            }
        )
    return {"projects": projects}


def write_projection(projects_yaml_path: Path, projection: dict[str, Any]) -> None:
    projects_yaml_path.parent.mkdir(parents=True, exist_ok=True)
    projects_yaml_path.write_text(yaml.safe_dump(projection, sort_keys=False, allow_unicode=False), encoding="utf-8")


def sync_db(database_path: Path, projection: dict[str, Any]) -> int:
    from rebalance.ingest.db import db_connection, ensure_project_schema

    rows = projection.get("projects", [])
    with db_connection(database_path, ensure_project_schema) as conn:
        for project in rows:
            conn.execute(
                """
                INSERT INTO project_registry (
                    name, status, summary, value_level, priority_tier, risk_level,
                    repos_json, tags_json, custom_fields_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    status=excluded.status,
                    summary=excluded.summary,
                    value_level=excluded.value_level,
                    priority_tier=excluded.priority_tier,
                    risk_level=excluded.risk_level,
                    repos_json=excluded.repos_json,
                    tags_json=excluded.tags_json,
                    custom_fields_json=excluded.custom_fields_json
                """,
                (
                    project.get("name"),
                    project.get("status"),
                    project.get("summary", ""),
                    project.get("value_level"),
                    project.get("priority_tier"),
                    project.get("risk_level"),
                    json.dumps(project.get("repos", [])),
                    json.dumps(project.get("tags", [])),
                    json.dumps(project.get("custom_fields", {})),
                ),
            )
        conn.commit()
    return len(rows)


def _push_from_projection(registry: Registry, projects_yaml_path: Path) -> Registry:
    if not projects_yaml_path.exists():
        return registry
    raw = yaml.safe_load(projects_yaml_path.read_text(encoding="utf-8")) or {}
    projects = raw.get("projects", []) if isinstance(raw, dict) else []

    transformed: list[Project] = []
    for item in projects:
        if not isinstance(item, dict):
            continue
        custom_fields = dict(item.get("custom_fields", {}) or {})
        external = bool(item.get("external") or custom_fields.pop("external", False))
        # Like external: provenance rides custom_fields in the projection and
        # must be lifted back to the typed field on push, or the round-trip
        # desyncs the model from its custom_fields copy.
        provenance = str(item.get("provenance") or custom_fields.pop("provenance", "") or "")
        transformed.append(
            Project(
                name=str(item.get("name", "")).strip(),
                status=str(item.get("status", "active")),
                summary=str(item.get("summary", "")),
                repos=list(item.get("repos", []) or []),
                external=external,
                provenance=provenance,
                obsidian_folder=item.get("obsidian_folder"),
                tags=list(item.get("tags", []) or []),
                value_level=item.get("value_level"),
                priority_tier=item.get("priority_tier"),
                risk_level=item.get("risk_level"),
                custom_fields=custom_fields,
            )
        )

    registry.active_projects = transformed
    return registry


def sync_registry(mode: str, registry_path: Path, projects_yaml_path: Path, database_path: Path) -> str:
    normalized_mode = mode.strip().lower()
    if normalized_mode not in {"pull", "push", "check"}:
        raise ValueError("mode must be one of: pull, push, check")

    registry = load_registry(registry_path)

    if normalized_mode == "push":
        updated_registry = _push_from_projection(registry=registry, projects_yaml_path=projects_yaml_path)
        save_registry(registry_path=registry_path, registry=updated_registry)
        return f"Sync push complete: registry updated from {projects_yaml_path}"

    projection = _registry_to_projection(registry)
    projection_text = yaml.safe_dump(projection, sort_keys=False, allow_unicode=False)

    if normalized_mode == "check":
        existing = projects_yaml_path.read_text(encoding="utf-8") if projects_yaml_path.exists() else ""
        status = "in-sync" if existing.strip() == projection_text.strip() else "out-of-sync"
        return (
            f"Sync check: {status}; active_projects={len(registry.active_projects)}; "
            f"potential_projects={len(registry.potential_projects)}"
        )

    write_projection(projects_yaml_path=projects_yaml_path, projection=projection)
    upserted = sync_db(database_path=database_path, projection=projection)
    return (
        f"Sync pull complete: wrote {projects_yaml_path}, upserted {upserted} rows into "
        f"{database_path}"
    )


# ---------------------------------------------------------------------------
# Centralized project DB reader — single source of truth
# ---------------------------------------------------------------------------


def get_projects(
    database_path: Path,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch projects from the project_registry table.

    Returns a list of dicts with ``repos`` (list), ``tags`` (list), and
    ``custom_fields`` (dict) already decoded from their ``*_json`` columns.

    This is the **canonical** way to read projects from SQLite.  All callers
    (MCP server, querier, project classifier, etc.) should use this instead
    of writing their own SQL + JSON-parsing logic.
    """
    if not database_path.exists():
        return []

    from rebalance.ingest.db import db_connection, ensure_project_schema

    with db_connection(database_path, ensure_project_schema) as conn:
        query = (
            "SELECT name, status, summary, value_level, priority_tier, "
            "risk_level, repos_json, tags_json, custom_fields_json "
            "FROM project_registry"
        )
        params: tuple[Any, ...] = ()
        if status:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY name ASC"

        rows = conn.execute(query, params).fetchall()

    result: list[dict[str, Any]] = []
    for row in rows:
        d = dict(row)
        # Decode *_json columns into native Python types
        for json_col, target_key, default in (
            ("repos_json", "repos", []),
            ("tags_json", "tags", []),
            ("custom_fields_json", "custom_fields", {}),
        ):
            raw = d.pop(json_col, None)
            try:
                d[target_key] = json.loads(raw) if raw else default
            except (json.JSONDecodeError, ValueError):
                d[target_key] = default
        # Lift provenance back to the top level so DB reads match the
        # candidate/Project shape (it is persisted inside custom_fields).
        d["provenance"] = (d["custom_fields"] or {}).get("provenance", "")
        result.append(d)
    return result


def effective_client(custom_fields: dict[str, Any] | None) -> str | None:
    """Resolve a project's client curated-first.

    Curated config ``client`` (operator-set priority rule) always wins; the
    machine-inferred ``client_inferred`` (owner-as-client) is the fallback;
    neither present → None (the ``(unassigned)`` bucket on read).
    """
    cf = custom_fields or {}
    return cf.get("client") or cf.get("client_inferred") or None


def get_clients(database_path: Path) -> dict[str, list[str]]:
    """Group project names by effective client. Derived view, not stored state.

    The "discrete client buckets" the next-action synthesis groups by. No
    ``client_registry`` table exists — clients are an attribute of a project
    (``custom_fields.client`` curated, ``client_inferred`` machine-owned).
    """
    from collections import defaultdict

    buckets: dict[str, list[str]] = defaultdict(list)
    for project in get_projects(database_path):
        client = effective_client(project.get("custom_fields")) or "(unassigned)"
        buckets[client].append(project["name"])
    return dict(buckets)


def get_external_repos(database_path: Path) -> list[str]:
    """Return the external/watched repos declared in the project registry.

    These are repos from any project flagged ``external: true`` (persisted in
    ``custom_fields_json``) — monitored for everyone's activity, regardless of
    project status. Normalized to ``owner/name`` and de-duplicated. This is the
    source consumed by ``get_watched_repos`` and the watched-repo rollup.
    """
    from rebalance.ingest.config import normalize_github_repo_name

    repos: list[str] = []
    for project in get_projects(database_path):
        custom_fields = project.get("custom_fields") or {}
        if not custom_fields.get("external"):
            continue
        for repo in project.get("repos") or []:
            try:
                normalized = normalize_github_repo_name(repo)
            except ValueError:
                continue
            if normalized not in repos:
                repos.append(normalized)
    return repos

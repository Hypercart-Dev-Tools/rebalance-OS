from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class Project(BaseModel):
    name: str
    status: str = "active"
    summary: str = ""
    repos: list[str] = Field(default_factory=list)
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


def load_registry(registry_path: Path) -> Registry:
    if not registry_path.exists():
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(_default_registry_markdown(), encoding="utf-8")
    raw = registry_path.read_text(encoding="utf-8")
    parsed = _extract_yaml_block(raw)
    return Registry.model_validate(parsed)


def save_registry(registry_path: Path, registry: Registry) -> None:
    payload = registry.model_dump(mode="json")
    yaml_content = yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)
    content = f"""# Project Registry

Canonical project list for rebalance ingest and scoring.

Sections:
- `active_projects`: currently tracked and scored
- `potential_projects`: candidates discovered by preflight
- `archived_projects`: historical records

```yaml
{yaml_content}```
"""
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(content, encoding="utf-8")


def _registry_to_projection(registry: Registry) -> dict[str, Any]:
    projects = []
    for project in registry.active_projects:
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
                "custom_fields": project.custom_fields,
            }
        )
    return {"projects": projects}


def write_projection(projects_yaml_path: Path, projection: dict[str, Any]) -> None:
    projects_yaml_path.parent.mkdir(parents=True, exist_ok=True)
    projects_yaml_path.write_text(yaml.safe_dump(projection, sort_keys=False, allow_unicode=False), encoding="utf-8")


def sync_db(database_path: Path, projection: dict[str, Any]) -> int:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS project_registry (
                name TEXT PRIMARY KEY,
                status TEXT,
                summary TEXT,
                value_level TEXT,
                priority_tier INTEGER,
                risk_level TEXT,
                repos_json TEXT,
                tags_json TEXT,
                custom_fields_json TEXT
            )
            """
        )
        rows = projection.get("projects", [])
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
                    yaml.safe_dump(project.get("repos", []), sort_keys=False),
                    yaml.safe_dump(project.get("tags", []), sort_keys=False),
                    yaml.safe_dump(project.get("custom_fields", {}), sort_keys=False),
                ),
            )
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def _push_from_projection(registry: Registry, projects_yaml_path: Path) -> Registry:
    if not projects_yaml_path.exists():
        return registry
    raw = yaml.safe_load(projects_yaml_path.read_text(encoding="utf-8")) or {}
    projects = raw.get("projects", []) if isinstance(raw, dict) else []

    transformed: list[Project] = []
    for item in projects:
        if not isinstance(item, dict):
            continue
        transformed.append(
            Project(
                name=str(item.get("name", "")).strip(),
                status=str(item.get("status", "active")),
                summary=str(item.get("summary", "")),
                repos=list(item.get("repos", []) or []),
                obsidian_folder=item.get("obsidian_folder"),
                tags=list(item.get("tags", []) or []),
                value_level=item.get("value_level"),
                priority_tier=item.get("priority_tier"),
                risk_level=item.get("risk_level"),
                custom_fields=dict(item.get("custom_fields", {}) or {}),
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

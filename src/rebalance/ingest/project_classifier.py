from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rebalance.ingest.calendar_config import CalendarConfig
from rebalance.ingest.db import db_connection


ALIAS_KEYS = {"aliases", "calendar_aliases", "calendar_keywords", "keywords"}
NESTED_ALIAS_KEYS = {"calendar", "calendar_report", "calendar_reports"}


@dataclass(frozen=True)
class ProjectMatcher:
    name: str
    aliases: tuple[str, ...]


def _normalize_text(text: str) -> str:
    """Normalize free-form text for project alias matching."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.casefold()).split())


def _camel_case_parts(text: str) -> list[str]:
    """Split CamelCase and mixed-case names into readable word parts."""
    return re.findall(r"[A-Z]+(?=[A-Z][a-z]|\b)|[A-Z]?[a-z]+|\d+", text)


def _iter_alias_values(value: Any) -> list[str]:
    """Flatten alias-like config values from custom_fields."""
    if isinstance(value, str):
        cleaned = value.strip()
        return [cleaned] if cleaned else []
    if isinstance(value, list):
        flattened: list[str] = []
        for item in value:
            flattened.extend(_iter_alias_values(item))
        return flattened
    return []


def _extract_custom_aliases(custom_fields: dict[str, Any]) -> list[str]:
    """Extract project aliases from flexible custom_fields shapes."""
    aliases: list[str] = []
    for key, value in custom_fields.items():
        if key in ALIAS_KEYS:
            aliases.extend(_iter_alias_values(value))
        elif key in NESTED_ALIAS_KEYS and isinstance(value, dict):
            for nested_key, nested_value in value.items():
                if nested_key in ALIAS_KEYS:
                    aliases.extend(_iter_alias_values(nested_value))
    return aliases


def _build_aliases(
    *,
    name: str,
    repos: list[str],
    tags: list[str],
    custom_fields: dict[str, Any],
) -> tuple[str, ...]:
    """Build normalized aliases for a canonical project name."""
    aliases: set[str] = set()

    def add_alias(raw: str) -> None:
        normalized = _normalize_text(raw)
        if normalized:
            aliases.add(normalized)

    add_alias(name)

    camel_parts = _camel_case_parts(name)
    if len(camel_parts) > 1:
        add_alias(" ".join(camel_parts))
        acronym = "".join(part[0] for part in camel_parts if part)
        add_alias(acronym)

    for repo in repos:
        add_alias(repo)
        add_alias(repo.replace("-", " "))

    for tag in tags:
        cleaned = tag.strip().lstrip("#")
        if cleaned.startswith("project-"):
            cleaned = cleaned[len("project-"):]
        add_alias(cleaned)
        add_alias(cleaned.replace("-", " "))

    for alias in _extract_custom_aliases(custom_fields):
        add_alias(alias)

    return tuple(
        sorted(
            aliases,
            key=lambda alias: (len(alias.split()), len(alias)),
            reverse=True,
        )
    )


def _build_matchers_from_config(config: CalendarConfig | None) -> list[ProjectMatcher]:
    """Build canonical project matchers from calendar config fallback projects."""
    if config is None:
        return []

    matchers: list[ProjectMatcher] = []
    for project in config.projects:
        aliases = _build_aliases(
            name=project.name,
            repos=[],
            tags=[],
            custom_fields={"calendar_aliases": project.aliases},
        )
        if aliases:
            matchers.append(ProjectMatcher(name=project.name, aliases=aliases))
    return matchers


def load_project_matchers(
    database_path: Path,
    config: CalendarConfig | None = None,
) -> list[ProjectMatcher]:
    """Load canonical project matchers from project_registry, or config fallback."""
    with db_connection(database_path) as conn:
        table_exists = conn.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = 'project_registry'
            """
        ).fetchone()
        if not table_exists:
            return _build_matchers_from_config(config)

        rows = conn.execute(
            """
            SELECT name, repos_json, tags_json, custom_fields_json
            FROM project_registry
            WHERE COALESCE(status, 'active') != 'archived'
            ORDER BY LENGTH(name) DESC, name ASC
            """
        ).fetchall()

    if not rows:
        return _build_matchers_from_config(config)

    matchers: list[ProjectMatcher] = []
    for row in rows:
        repos = json.loads(row["repos_json"]) if row["repos_json"] else []
        tags = json.loads(row["tags_json"]) if row["tags_json"] else []
        custom_fields = json.loads(row["custom_fields_json"]) if row["custom_fields_json"] else {}
        aliases = _build_aliases(
            name=row["name"] or "",
            repos=list(repos or []),
            tags=list(tags or []),
            custom_fields=dict(custom_fields or {}),
        )
        if aliases:
            matchers.append(ProjectMatcher(name=row["name"], aliases=aliases))

    return matchers


def classify_event_project(summary: str, matchers: list[ProjectMatcher]) -> str | None:
    """Return the canonical project name for an event summary, if matched."""
    normalized_summary = _normalize_text(summary)
    if not normalized_summary:
        return None

    padded_summary = f" {normalized_summary} "
    best_match: tuple[int, int, str] | None = None
    best_project: str | None = None

    for matcher in matchers:
        for alias in matcher.aliases:
            padded_alias = f" {alias} "
            if padded_alias not in padded_summary:
                continue

            score = (len(alias.split()), len(alias), alias)
            if best_match is None or score > best_match:
                best_match = score
                best_project = matcher.name

    return best_project


def annotate_events_with_projects(
    events: list[dict[str, Any]],
    matchers: list[ProjectMatcher],
) -> list[dict[str, Any]]:
    """Attach canonical project names to event dicts when the registry matches."""
    if not matchers:
        return events

    annotated: list[dict[str, Any]] = []
    for event in events:
        project_name = classify_event_project(event.get("summary", ""), matchers)
        if project_name:
            annotated.append({**event, "project_name": project_name})
        else:
            annotated.append(event)
    return annotated

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from rebalance.ingest.calendar_config import CalendarConfig, filter_events
from rebalance.ingest.calendar_helpers import event_duration_minutes, parse_calendar_dt
from rebalance.ingest.config import get_github_ignored_repos
from rebalance.ingest.db import (
    db_connection,
    ensure_calendar_schema,
    ensure_github_schema,
    ensure_project_schema,
)
from rebalance.ingest.registry import sync_db

_GENERIC_ALIAS_TOKENS = {
    "app",
    "dev",
    "git",
    "github",
    "loop",
    "oct",
    "os",
    "plugin",
    "repo",
    "team",
    "theme",
    "tool",
    "toolkit",
    "tools",
    "universal",
}
_CALENDAR_NOISE_SUBSTRINGS = (
    "blocked off",
    "morning exercise",
    "end of day check in",
    "team call",
)
_CALENDAR_NOISE_EXACT = {
    "15 minute meeting",
    "matt noel jose",
    "verizon store",
}
_CALENDAR_SUFFIX_WORDS = {"weekly", "meetings", "meeting", "website", "deployment", "day", "daily"}


@dataclass
class InferenceSummary:
    inferred_count: int
    github_backed_count: int
    calendar_only_count: int
    updated_count: int
    deleted_stale_inferred_count: int
    project_names: list[str]


@dataclass
class _ProjectSeed:
    key: str
    display_name: str
    repos: set[str]
    github_score: int = 0
    github_last_active_at: str | None = None
    github_bands: set[str] | None = None
    github_signals: int = 0
    calendar_event_count: int = 0
    calendar_total_minutes: int = 0
    calendar_last_event_at: str | None = None
    calendar_labels: Counter[str] | None = None
    aliases: set[str] | None = None

    def __post_init__(self) -> None:
        if self.github_bands is None:
            self.github_bands = set()
        if self.calendar_labels is None:
            self.calendar_labels = Counter()
        if self.aliases is None:
            self.aliases = set()


def _normalize_text(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.casefold()).split())


def _split_tokens(text: str) -> list[str]:
    parts = re.findall(r"[A-Z]+(?=[A-Z][a-z]|\b)|[A-Z]?[a-z]+|\d+", text.replace(".", " "))
    return [part.casefold() for part in parts if part]


def _repo_slug_to_title(slug: str) -> str:
    pieces = [piece for piece in re.split(r"[-_.]+", slug.strip()) if piece and piece.casefold() != "md"]
    rendered: list[str] = []
    for piece in pieces:
        if piece.isupper():
            rendered.append(piece)
        elif piece.lower() in {"os", "ai", "wp", "db", "ui", "llm"}:
            rendered.append(piece.upper())
        else:
            rendered.append(piece.capitalize())
    return " ".join(rendered) or slug


def _owner_brand_aliases(owner: str) -> list[str]:
    aliases: list[str] = []
    token_groups = _split_tokens(owner)
    if token_groups:
        joined = " ".join(token_groups)
        if joined:
            aliases.append(joined)
        if token_groups[0] not in _GENERIC_ALIAS_TOKENS:
            aliases.append(token_groups[0])
    cleaned = re.sub(r"(team|dev|tools|labs|hq|inc|llc|studio|group)$", "", owner, flags=re.IGNORECASE)
    if cleaned and cleaned.casefold() != owner.casefold():
        cleaned_norm = _normalize_text(cleaned)
        if cleaned_norm:
            aliases.append(cleaned_norm)
    return [alias for alias in aliases if alias]


def _build_repo_aliases(repo_full_name: str) -> set[str]:
    owner, _, slug = repo_full_name.partition("/")
    aliases: set[str] = set()
    for raw in [repo_full_name, repo_full_name.replace("-", " "), slug, slug.replace("-", " "), owner]:
        normalized = _normalize_text(raw)
        if normalized:
            aliases.add(normalized)
    for alias in _owner_brand_aliases(owner):
        aliases.add(alias)
    for token in _split_tokens(slug):
        if len(token) >= 3 and token not in _GENERIC_ALIAS_TOKENS and not token.isdigit():
            aliases.add(token)
    return aliases


def _choose_display_name(repo_full_name: str) -> str:
    owner, _, slug = repo_full_name.partition("/")
    slug_tokens = [token for token in _split_tokens(slug) if token]
    generic_count = sum(1 for token in slug_tokens if token in _GENERIC_ALIAS_TOKENS or token.isdigit())
    if slug_tokens and generic_count / len(slug_tokens) > 0.6:
        owner_aliases = _owner_brand_aliases(owner)
        if owner_aliases:
            return _repo_slug_to_title(owner_aliases[-1].replace(" ", "-"))
    return _repo_slug_to_title(slug)


def _owner_group_key(owner: str) -> str | None:
    cleaned = owner.strip()
    if re.search(r"(team|cbd)$", cleaned, flags=re.IGNORECASE):
        aliases = _owner_brand_aliases(cleaned)
        if aliases:
            return aliases[-1]
    return None


def _latest_github_rows(database_path: Path) -> list[dict[str, Any]]:
    ignored = set(get_github_ignored_repos())
    with db_connection(database_path, ensure_github_schema) as conn:
        rows = conn.execute(
            """
            SELECT ga.repo_full_name,
                   ga.commits,
                   ga.pushes,
                   ga.prs_opened,
                   ga.prs_merged,
                   ga.issues_opened,
                   ga.issue_comments,
                   ga.reviews,
                   ga.last_active_at,
                   ga.scanned_at
            FROM github_activity ga
            JOIN (
                SELECT repo_full_name, MAX(scanned_at) AS max_scanned_at
                FROM github_activity
                GROUP BY repo_full_name
            ) latest
              ON latest.repo_full_name = ga.repo_full_name
             AND latest.max_scanned_at = ga.scanned_at
            ORDER BY ga.last_active_at DESC, ga.repo_full_name ASC
            """
        ).fetchall()

    result: list[dict[str, Any]] = []
    for row in rows:
        repo_full_name = row["repo_full_name"]
        if repo_full_name.casefold() in ignored:
            continue
        result.append(dict(row))
    return result


def _load_calendar_events(
    database_path: Path,
    *,
    config: CalendarConfig,
    days_back: int,
    days_forward: int,
) -> list[dict[str, Any]]:
    today = datetime.now(timezone.utc).date()
    min_date = (today - timedelta(days=days_back)).isoformat()
    max_date = (today + timedelta(days=days_forward)).isoformat()
    with db_connection(database_path, ensure_calendar_schema) as conn:
        rows = conn.execute(
            """
            SELECT summary, start_time, end_time
            FROM calendar_events
            WHERE calendar_id = ?
              AND DATE(start_time) BETWEEN ? AND ?
            ORDER BY start_time ASC
            """,
            (config.calendar_id, min_date, max_date),
        ).fetchall()

    events = [
        {
            "summary": row["summary"] or "",
            "start_time": row["start_time"] or "",
            "end_time": row["end_time"] or "",
        }
        for row in rows
    ]
    return filter_events(events, config.exclude_titles)


def _extract_calendar_label(summary: str) -> str | None:
    stripped = summary.strip()
    normalized = _normalize_text(stripped)
    if not normalized:
        return None
    if normalized in _CALENDAR_NOISE_EXACT:
        return None
    if any(token in normalized for token in _CALENDAR_NOISE_SUBSTRINGS):
        return None

    if " - " in stripped:
        prefix = stripped.split(" - ", 1)[0].strip()
        if prefix:
            return prefix

    words = stripped.split()
    if len(words) >= 2 and words[1].casefold().strip(":") in _CALENDAR_SUFFIX_WORDS:
        return words[0].strip(":-")
    if len(words) >= 3 and words[2].casefold().strip(":") in _CALENDAR_SUFFIX_WORDS:
        return " ".join(words[:2]).strip(":-")

    return None


def _best_alias_match(summary: str, seeds: dict[str, _ProjectSeed]) -> str | None:
    normalized = f" {_normalize_text(summary)} "
    best_seed: str | None = None
    best_score = (-1, -1)
    for seed in seeds.values():
        for alias in seed.aliases or set():
            if not alias:
                continue
            padded_alias = f" {alias} "
            if padded_alias not in normalized:
                continue
            score = (len(alias.split()), len(alias))
            if score > best_score:
                best_score = score
                best_seed = seed.key
    return best_seed


def _parse_event_time(raw: str) -> datetime | None:
    try:
        dt = parse_calendar_dt(raw)
    except Exception:
        return None
    if dt.tzinfo is None:
        return None
    return dt.astimezone(timezone.utc)


def _merge_calendar_signal(seed: _ProjectSeed, *, summary: str, start_time: str, end_time: str, label: str | None) -> None:
    seed.calendar_event_count += 1
    seed.calendar_total_minutes += event_duration_minutes(start_time, end_time)
    if label:
        seed.calendar_labels[label] += 1
        normalized_label = _normalize_text(label)
        if normalized_label:
            seed.aliases.add(normalized_label)
    start_dt = _parse_event_time(start_time)
    if start_dt:
        start_iso = start_dt.isoformat()
        if not seed.calendar_last_event_at or start_iso > seed.calendar_last_event_at:
            seed.calendar_last_event_at = start_iso
    normalized_summary = _normalize_text(summary)
    if normalized_summary:
        seed.aliases.add(normalized_summary)


def _build_seeds_from_github(database_path: Path) -> dict[str, _ProjectSeed]:
    seeds: dict[str, _ProjectSeed] = {}
    for row in _latest_github_rows(database_path):
        repo_full_name = row["repo_full_name"]
        owner, _, _slug = repo_full_name.partition("/")
        score = (
            row["commits"]
            + row["pushes"]
            + row["prs_opened"]
            + row["prs_merged"]
            + row["issues_opened"]
            + row["issue_comments"]
            + row["reviews"]
        )
        if score <= 0:
            continue
        grouped_key = _owner_group_key(owner)
        seed_key = f"owner:{grouped_key}" if grouped_key else repo_full_name.casefold()
        seed = seeds.get(seed_key)
        if seed is None:
            seed = _ProjectSeed(
                key=seed_key,
                display_name=_repo_slug_to_title(grouped_key.replace(" ", "-")) if grouped_key else _choose_display_name(repo_full_name),
                repos=set(),
                github_score=0,
                github_last_active_at=None,
                github_signals=0,
            )
            seeds[seed.key] = seed

        seed.repos.add(repo_full_name)
        seed.github_score += score
        seed.github_signals += 1
        if row["last_active_at"] and (
            not seed.github_last_active_at or row["last_active_at"] > seed.github_last_active_at
        ):
            seed.github_last_active_at = row["last_active_at"]
        seed.aliases.update(_build_repo_aliases(repo_full_name))
        if grouped_key:
            seed.aliases.add(grouped_key)
    return seeds


def _apply_calendar_signal(
    database_path: Path,
    *,
    seeds: dict[str, _ProjectSeed],
    config: CalendarConfig,
    days_back: int,
    days_forward: int,
) -> None:
    events = _load_calendar_events(
        database_path,
        config=config,
        days_back=days_back,
        days_forward=days_forward,
    )
    for event in events:
        summary = event["summary"]
        label = _extract_calendar_label(summary)
        matched_key = _best_alias_match(summary, seeds)
        if matched_key:
            _merge_calendar_signal(
                seeds[matched_key],
                summary=summary,
                start_time=event["start_time"],
                end_time=event["end_time"],
                label=label,
            )
            continue

        if not label:
            continue
        normalized_label = _normalize_text(label)
        if not normalized_label or normalized_label in _CALENDAR_NOISE_EXACT:
            continue

        key = f"calendar:{normalized_label}"
        seed = seeds.get(key)
        if seed is None:
            seed = _ProjectSeed(
                key=key,
                display_name=label.strip(),
                repos=set(),
            )
            seed.aliases.add(normalized_label)
            seeds[key] = seed
        _merge_calendar_signal(
            seed,
            summary=summary,
            start_time=event["start_time"],
            end_time=event["end_time"],
            label=label,
        )


def _choose_seed_name(seed: _ProjectSeed) -> str:
    normalized_display = _normalize_text(seed.display_name)
    if normalized_display:
        for label in seed.calendar_labels or Counter():
            normalized_label = _normalize_text(label)
            if f" {normalized_display} " in f" {normalized_label} ":
                return seed.display_name
    if seed.calendar_labels:
        return seed.calendar_labels.most_common(1)[0][0]
    return seed.display_name


def _seed_status(seed: _ProjectSeed) -> str:
    latest = seed.calendar_last_event_at or seed.github_last_active_at
    if not latest:
        return "potential"
    try:
        latest_dt = parse_calendar_dt(latest).astimezone(timezone.utc)
    except Exception:
        return "potential"
    age_days = (datetime.now(timezone.utc) - latest_dt).days
    if age_days <= 30:
        return "active"
    if age_days <= 90:
        return "semi_active"
    return "dormant"


def _seed_summary(seed: _ProjectSeed) -> str:
    parts: list[str] = []
    if seed.repos:
        repo_count = len(seed.repos)
        parts.append(
            f"GitHub inferred from {repo_count} repo{'s' if repo_count != 1 else ''}"
        )
        if seed.github_score:
            parts[-1] += f" with score {seed.github_score}"
    if seed.calendar_event_count:
        hours = seed.calendar_total_minutes / 60.0
        parts.append(
            f"calendar inferred from {seed.calendar_event_count} event{'s' if seed.calendar_event_count != 1 else ''} ({hours:.1f}h)"
        )
    latest = seed.calendar_last_event_at or seed.github_last_active_at
    if latest:
        parts.append(f"last signal {latest[:10]}")
    return "; ".join(parts)


def _seed_to_project_row(seed: _ProjectSeed) -> dict[str, Any]:
    name = _choose_seed_name(seed)
    aliases = sorted(
        {
            alias
            for alias in seed.aliases or set()
            if alias
            and alias != _normalize_text(name)
            and len(alias) >= 2
        }
    )
    calendar_aliases = sorted(label for label in (seed.calendar_labels or Counter()).keys() if label != name)
    tags = ["inferred"]
    if seed.repos:
        tags.append("source:github")
    if seed.calendar_event_count:
        tags.append("source:calendar")
    status = _seed_status(seed)
    if status != "potential":
        tags.append(f"status:{status}")

    return {
        "name": name,
        "status": status,
        "summary": _seed_summary(seed),
        "value_level": None,
        "priority_tier": None,
        "risk_level": None,
        "repos": sorted(seed.repos),
        "tags": tags,
        "custom_fields": {
            "aliases": aliases,
            "calendar_aliases": calendar_aliases,
            "inference": {
                "generated_by": "activity_inference_v1",
                "github_repo_count": len(seed.repos),
                "github_activity_score": seed.github_score,
                "github_last_active_at": seed.github_last_active_at,
                "calendar_event_count": seed.calendar_event_count,
                "calendar_total_minutes": seed.calendar_total_minutes,
                "calendar_last_event_at": seed.calendar_last_event_at,
            },
        },
    }


def _delete_stale_inferred_rows(database_path: Path, project_names: set[str]) -> int:
    with db_connection(database_path, ensure_project_schema) as conn:
        rows = conn.execute(
            "SELECT name, custom_fields_json FROM project_registry"
        ).fetchall()
        stale_names: list[str] = []
        for row in rows:
            try:
                custom_fields = json.loads(row["custom_fields_json"]) if row["custom_fields_json"] else {}
            except json.JSONDecodeError:
                custom_fields = {}
            generated_by = ((custom_fields or {}).get("inference") or {}).get("generated_by")
            if generated_by == "activity_inference_v1" and row["name"] not in project_names:
                stale_names.append(row["name"])

        if stale_names:
            conn.executemany("DELETE FROM project_registry WHERE name = ?", [(name,) for name in stale_names])
            conn.commit()
        return len(stale_names)


def infer_project_registry(
    database_path: Path,
    *,
    calendar_config: CalendarConfig | None = None,
    calendar_days_back: int = 90,
    calendar_days_forward: int = 14,
) -> tuple[list[dict[str, Any]], InferenceSummary]:
    config = calendar_config or CalendarConfig.load()
    seeds = _build_seeds_from_github(database_path)
    _apply_calendar_signal(
        database_path,
        seeds=seeds,
        config=config,
        days_back=calendar_days_back,
        days_forward=calendar_days_forward,
    )

    projects = [
        _seed_to_project_row(seed)
        for seed in seeds.values()
        if seed.repos or seed.calendar_event_count >= 2
    ]
    projects.sort(key=lambda item: (item["status"] != "active", item["name"].casefold()))

    summary = InferenceSummary(
        inferred_count=len(projects),
        github_backed_count=sum(1 for item in projects if item["repos"]),
        calendar_only_count=sum(1 for item in projects if not item["repos"]),
        updated_count=0,
        deleted_stale_inferred_count=0,
        project_names=[item["name"] for item in projects],
    )
    return projects, summary


def sync_inferred_project_registry(
    database_path: Path,
    *,
    calendar_config: CalendarConfig | None = None,
    calendar_days_back: int = 90,
    calendar_days_forward: int = 14,
) -> InferenceSummary:
    projects, summary = infer_project_registry(
        database_path,
        calendar_config=calendar_config,
        calendar_days_back=calendar_days_back,
        calendar_days_forward=calendar_days_forward,
    )
    updated_count = sync_db(database_path, {"projects": projects})
    deleted_count = _delete_stale_inferred_rows(database_path, set(summary.project_names))
    return InferenceSummary(
        inferred_count=summary.inferred_count,
        github_backed_count=summary.github_backed_count,
        calendar_only_count=summary.calendar_only_count,
        updated_count=updated_count,
        deleted_stale_inferred_count=deleted_count,
        project_names=summary.project_names,
    )

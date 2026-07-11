from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from rebalance.ingest.calendar_config import (
    OPERATOR_CALENDAR_ID,
    CalendarConfig,
    filter_events,
)
from rebalance.ingest.calendar_helpers import event_duration_minutes, parse_calendar_dt
from rebalance.ingest.config import get_github_ignored_repos
from rebalance.ingest.db import (
    db_connection,
    ensure_calendar_schema,
    ensure_github_schema,
    ensure_project_schema,
)
from rebalance.ingest.project_classifier import normalize_match_text
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
_CLIENT_GAPFILL_UNCERTAIN = {"", "n/a", "na", "none", "null", "unclear", "unknown", "unsure", "?"}


# Provenance marker for rows this module owns. Inference may create, update,
# and delete ONLY rows carrying this marker (lifecycle contract:
# write_semantics="machine_owned") — curated registry rows always win.
INFERENCE_GENERATED_BY = "activity_inference_v1"

# GH-124: a second machine-owned marker for commit-threshold auto-promotion
# (sync_commit_threshold_promotions below). Kept distinct from
# INFERENCE_GENERATED_BY so a promoted row's provenance is self-describing,
# but recognized by _is_inference_owned alongside it — both markers share the
# same machine_owned contract (curated rows never touched, safe to recreate).
COMMIT_THRESHOLD_GENERATED_BY = "commit_threshold_v1"
_MACHINE_OWNED_MARKERS = {INFERENCE_GENERATED_BY, COMMIT_THRESHOLD_GENERATED_BY}


def _generated_by(custom_fields_json: str | None) -> str | None:
    try:
        custom_fields = json.loads(custom_fields_json) if custom_fields_json else {}
    except json.JSONDecodeError:
        custom_fields = {}
    return ((custom_fields or {}).get("inference") or {}).get("generated_by")


def _is_inference_owned(custom_fields_json: str | None) -> bool:
    return _generated_by(custom_fields_json) in _MACHINE_OWNED_MARKERS


@dataclass
class InferenceSummary:
    inferred_count: int
    github_backed_count: int
    calendar_only_count: int
    updated_count: int
    deleted_stale_inferred_count: int
    project_names: list[str]
    skipped_curated_count: int = 0
    skipped_curated_names: list[str] = field(default_factory=list)


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


# Phase 5: one normalizer across classifier/inference/priority — the
# canonical implementation lives in project_classifier.
_normalize_text = normalize_match_text


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
            # Operator rows are canonically stored as 'primary' (see
            # OPERATOR_CALENDAR_ID); config.calendar_id would miss them.
            (OPERATOR_CALENDAR_ID, min_date, max_date),
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


def _infer_client(seed: _ProjectSeed) -> str | None:
    """Owner-as-client: the GitHub owner/org IS the client for the common case.

    Deterministic, no API key. Calendar-only seeds have no repo owner → None
    (the Gemini gap-fill in Phase 2 fills those). When a seed spans several owners
    (grouped brand), the dominant owner wins.

    # ponytail: owner-as-client is the free spine. Upgrade to Gemini gap-fill only
    # for the None cases (personal/calendar-only), never the whole field.
    """
    owners = Counter(repo.partition("/")[0] for repo in seed.repos if "/" in repo)
    if not owners:
        return None
    return owners.most_common(1)[0][0]


def _project_activity_snippets(seed: _ProjectSeed) -> list[str]:
    snippets: list[str] = []
    repos = sorted(seed.repos)
    if repos:
        snippets.append(f"Repos: {', '.join(repos[:2])}")
        github_bits: list[str] = []
        if seed.github_last_active_at:
            github_bits.append(f"last GitHub activity {seed.github_last_active_at[:10]}")
        if seed.github_score:
            github_bits.append(f"github activity score {seed.github_score}")
        if github_bits:
            snippets.append("; ".join(github_bits))
    if seed.calendar_event_count:
        calendar_bits = [f"{seed.calendar_event_count} calendar event(s)"]
        top_label = (seed.calendar_labels or Counter()).most_common(1)
        if top_label:
            calendar_bits.append(f"top calendar label {top_label[0][0]!r}")
        if seed.calendar_last_event_at:
            calendar_bits.append(f"last calendar event {seed.calendar_last_event_at[:10]}")
        snippets.append("; ".join(calendar_bits))
    return snippets


def _build_client_gapfill_prompt(candidates: list[tuple[_ProjectSeed, dict[str, Any]]]) -> str:
    lines = [
        "Infer the client/customer for each project from the evidence below.",
        "Return STRICT JSON only: {\"Project Name\": \"Client Name\" | null}.",
        "Rules:",
        "- Use only explicit evidence from the project name, repos, or activity snippets.",
        "- If the project looks internal, personal, open-source, or the client is not evident, return null.",
        "- Do not guess or explain.",
        "",
        "Projects:",
    ]
    for index, (seed, project) in enumerate(candidates, 1):
        lines.append(f"{index}. project={project['name']}")
        repos = sorted(seed.repos)
        lines.append(f"   repos={repos if repos else []}")
        snippets = _project_activity_snippets(seed)
        if snippets:
            for snippet in snippets:
                lines.append(f"   signal={snippet}")
        else:
            lines.append("   signal=no recent activity snippets")
    return "\n".join(lines)


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _normalize_gapfill_client(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text.casefold() in _CLIENT_GAPFILL_UNCERTAIN:
        return None
    return text or None


def _parse_client_gapfill_response(
    raw_text: str,
    *,
    project_names: set[str],
) -> dict[str, str | None]:
    try:
        payload = json.loads(_strip_json_fence(raw_text))
    except json.JSONDecodeError:
        return {}

    if not isinstance(payload, dict):
        return {}

    expected_by_key = {_normalize_text(name): name for name in project_names}
    parsed: dict[str, str | None] = {}
    for raw_name, raw_client in payload.items():
        if not isinstance(raw_name, str):
            continue
        project_name = expected_by_key.get(_normalize_text(raw_name))
        if not project_name:
            continue
        parsed[project_name] = _normalize_gapfill_client(raw_client)
    return parsed


def _gapfill_missing_clients(candidates: list[tuple[_ProjectSeed, dict[str, Any]]]) -> None:
    if not candidates:
        return

    from rebalance.ingest.config import get_gemini_api_key
    from rebalance.ingest.querier import (
        DEFAULT_GEMINI_MODEL,
        _synthesize_with_fallback,
    )

    if not get_gemini_api_key():
        return

    prompt = _build_client_gapfill_prompt(candidates)
    try:
        synthesis, model_used = _synthesize_with_fallback(
            prompt,
            max_tokens=1024,
            thinking_budget=0,
        )
    except Exception:
        return
    if model_used != DEFAULT_GEMINI_MODEL:
        return

    inferred = _parse_client_gapfill_response(
        synthesis,
        project_names={project["name"] for _, project in candidates},
    )
    for _seed, project in candidates:
        client = inferred.get(project["name"])
        if client:
            project["custom_fields"]["client_inferred"] = client


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
            "client_inferred": _infer_client(seed),
            "provenance": "inferred",
            "inference": {
                "generated_by": INFERENCE_GENERATED_BY,
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
    """Delete rows this specific pass (activity/calendar inference) owns and no
    longer generates.

    Bug found in cross-model QA (GH-124): scoping this to _is_inference_owned()
    (any machine_owned marker) instead of INFERENCE_GENERATED_BY specifically
    would delete GH-124 auto-promoted rows on every inference sync, since
    project_names here only ever contains this pass's own generated names —
    an auto-promoted row is never "stale" from this pass's perspective, it's
    simply not this pass's row to judge.
    """
    with db_connection(database_path, ensure_project_schema) as conn:
        rows = conn.execute(
            "SELECT name, custom_fields_json FROM project_registry"
        ).fetchall()
        stale_names: list[str] = [
            row["name"]
            for row in rows
            if _generated_by(row["custom_fields_json"]) == INFERENCE_GENERATED_BY
            and row["name"] not in project_names
        ]

        if stale_names:
            conn.executemany("DELETE FROM project_registry WHERE name = ?", [(name,) for name in stale_names])
            conn.commit()
        return len(stale_names)


def _partition_writable_rows(
    database_path: Path, projects: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Split inferred rows into writable vs. curated-name collisions.

    A name already present in project_registry WITHOUT the inference marker is
    operator-curated state — inference must not touch it (the registry upsert
    is keyed by name, so writing would clobber the curated row wholesale).
    """
    with db_connection(database_path, ensure_project_schema) as conn:
        rows = conn.execute(
            "SELECT name, custom_fields_json FROM project_registry"
        ).fetchall()
    curated_names = {
        row["name"] for row in rows if not _is_inference_owned(row["custom_fields_json"])
    }
    writable = [p for p in projects if p["name"] not in curated_names]
    skipped = sorted(p["name"] for p in projects if p["name"] in curated_names)
    return writable, skipped


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

    projects: list[dict[str, Any]] = []
    gapfill_candidates: list[tuple[_ProjectSeed, dict[str, Any]]] = []
    for seed in seeds.values():
        if not seed.repos and seed.calendar_event_count < 2:
            continue
        project = _seed_to_project_row(seed)
        projects.append(project)
        if project["custom_fields"].get("client_inferred") is None:
            gapfill_candidates.append((seed, project))
    _gapfill_missing_clients(gapfill_candidates)
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
    # machine_owned contract: write only rows inference owns. Curated rows
    # sharing a name are skipped (reported in the summary), never clobbered.
    writable, skipped_curated = _partition_writable_rows(database_path, projects)
    updated_count = sync_db(database_path, {"projects": writable})
    deleted_count = _delete_stale_inferred_rows(database_path, set(summary.project_names))
    return InferenceSummary(
        inferred_count=summary.inferred_count,
        github_backed_count=summary.github_backed_count,
        calendar_only_count=summary.calendar_only_count,
        updated_count=updated_count,
        deleted_stale_inferred_count=deleted_count,
        project_names=summary.project_names,
        skipped_curated_count=len(skipped_curated),
        skipped_curated_names=skipped_curated,
    )


# ---------------------------------------------------------------------------
# GH-124: commit-threshold auto-promotion
# ---------------------------------------------------------------------------


def _count_operator_commits(conn: Any, repo_full_name: str, github_login: str) -> int:
    """Count the operator's (or a known cloud-agent bot's) commits to
    ``repo_full_name``, combining two signals that each cover a gap the other
    has:

    - ``github_activity.commits`` (summed across every ``scan_date`` row for
      ``login=github_login``) — sourced from GitHub's PushEvent feed, so it
      covers direct-to-branch pushes with no PR. It is inherently
      operator-scoped (the events feed is `/users/{login}/events`), so it can
      never see a bot's commits.
    - ``github_commits`` (distinct SHA, ``author_login`` matched via
      ``pulse._author_filter_sql``) — populated only from PR commit listings,
      so it misses direct pushes, but it is the only table carrying a
      per-commit author, which is what lets a known cloud-agent bot count.

    Found and fixed in cross-model QA (GH-124): the original PR-commits-only
    version silently undercounted (often to zero) any repo the operator
    pushes to directly without opening a PR — the common case.

    Each ``scan_date`` row is preserved across rescans (only *today's* row is
    overwritten — see the "GitHub activity — window refetch" sync semantics
    in ARCHITECTURE.md), so summing across all of them is a genuine cumulative
    count since Rebalance started watching the repo, not a rolling window.
    """
    from rebalance.ingest.pulse import CLOUD_AGENT_AUTHORS, _author_filter_sql

    activity_row = conn.execute(
        "SELECT COALESCE(SUM(commits), 0) AS n FROM github_activity "
        "WHERE repo_full_name = ? AND login = ?",
        (repo_full_name, github_login),
    ).fetchone()
    operator_push_count = int(activity_row["n"] or 0) if activity_row else 0

    bot_placeholders = ", ".join("?" for _ in CLOUD_AGENT_AUTHORS)
    bot_row = conn.execute(
        f"""
        SELECT COUNT(DISTINCT sha) AS n
        FROM github_commits
        WHERE repo_full_name = ? AND author_login IN ({bot_placeholders})
        """,
        (repo_full_name, *CLOUD_AGENT_AUTHORS),
    ).fetchone()
    bot_commit_count = int(bot_row["n"] or 0) if bot_row else 0

    return operator_push_count + bot_commit_count


def _promoted_row_name(repo_full_name: str, *, taken_names: set[str]) -> str:
    """Derive a display name for an auto-promoted row, disambiguated against
    every name already in use (existing registry rows in this DB, plus any
    other repo already promoted in this same run).

    Found in cross-model QA (GH-124): a bare repo-slug name (``owner/widget``
    -> ``widget``) collides silently when two different repos share a slug —
    ``sync_db`` upserts by name, so the second promotion would overwrite the
    first's ``repos_json``. Falls back to an ``Owner Widget`` form on
    collision; reuses ``_choose_display_name`` for the base form so an
    auto-promoted name matches the same formatting standard inference uses
    (title-cased, not a raw lowercase slug).
    """
    base = _choose_display_name(repo_full_name)
    if base not in taken_names:
        return base
    owner = repo_full_name.split("/", 1)[0]
    disambiguated = f"{_repo_slug_to_title(owner)} {base}"
    if disambiguated not in taken_names:
        return disambiguated
    # Extremely unlikely third collision: fall back to the exact repo slug.
    return repo_full_name


def _repo_to_promoted_row(
    repo_full_name: str, *, commit_count: int, threshold: int, taken_names: set[str]
) -> dict[str, Any]:
    """Build a machine-owned project_registry row for one auto-promoted repo.

    Shape mirrors ``_seed_to_project_row`` (same table, same optional fields
    left ``None`` for the operator to fill in later) but with a distinct
    provenance marker so an auto-promoted row is self-describing.
    """
    name = _promoted_row_name(repo_full_name, taken_names=taken_names)
    return {
        "name": name,
        "status": "active",
        "summary": f"Auto-promoted after {commit_count} operator commit(s) to {repo_full_name}.",
        "value_level": None,
        "priority_tier": None,
        "risk_level": None,
        "repos": [repo_full_name],
        "tags": ["auto-promoted", "source:github"],
        "custom_fields": {
            "provenance": "auto_promoted",
            "inference": {
                "generated_by": COMMIT_THRESHOLD_GENERATED_BY,
                "repo_full_name": repo_full_name,
                "commit_count": commit_count,
                "threshold": threshold,
                "promoted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            },
        },
    }


@dataclass
class AutoPromoteSummary:
    """Result of one ``sync_commit_threshold_promotions`` pass."""

    enabled: bool
    threshold: int
    candidates_evaluated: int = 0
    promoted: list[dict[str, Any]] = field(default_factory=list)
    skipped_curated_names: list[str] = field(default_factory=list)

    @property
    def promoted_count(self) -> int:
        return len(self.promoted)


def sync_commit_threshold_promotions(database_path: Path) -> AutoPromoteSummary:
    """GH-124: auto-promote a watched repo into ``project_registry`` once the
    operator has authored enough commits to it.

    Candidate pool = ``get_watched_repos()["auto_discovered"]`` — repos with
    GitHub activity/push signal that are not already in ANY active project's
    ``repos`` (curated or machine-owned), and ``github_ignored_repos`` already
    excluded upstream by ``get_watched_repos``. A candidate promotes once its
    operator-authored commit count (see ``_count_operator_commits``) reaches
    ``auto_promote_commit_threshold``. A fork or starred-only repo with zero
    operator commits never reaches the threshold, so no separate fork
    detection is needed — the commit count IS the filter.

    Writes only via the existing machine_owned partition/write path
    (``_partition_writable_rows`` / ``sync_db``) — a curated row sharing the
    derived name is skipped, never clobbered, exactly like
    ``sync_inferred_project_registry``.
    """
    from rebalance.ingest.config import get_auto_promote_config, get_pulse_config
    from rebalance.ingest.index_ops import get_watched_repos

    auto_promote_config = get_auto_promote_config()
    threshold = auto_promote_config["auto_promote_commit_threshold"]
    if not auto_promote_config["auto_promote_enabled"]:
        return AutoPromoteSummary(enabled=False, threshold=threshold)

    github_login = get_pulse_config().get("github_login")
    if not github_login:
        # No identity to match commits against — nothing is promotable.
        return AutoPromoteSummary(enabled=True, threshold=threshold)

    candidates = get_watched_repos(database_path)["auto_discovered"]

    with db_connection(database_path, ensure_project_schema) as conn:
        taken_names = {
            row["name"] for row in conn.execute("SELECT name FROM project_registry").fetchall()
        }

    promoted_rows: list[dict[str, Any]] = []
    with db_connection(database_path, ensure_github_schema) as conn:
        for repo_full_name in candidates:
            commit_count = _count_operator_commits(conn, repo_full_name, github_login)
            if commit_count >= threshold:
                row = _repo_to_promoted_row(
                    repo_full_name, commit_count=commit_count, threshold=threshold,
                    taken_names=taken_names,
                )
                taken_names.add(row["name"])
                promoted_rows.append(row)

    writable, skipped_curated = _partition_writable_rows(database_path, promoted_rows)
    if writable:
        sync_db(database_path, {"projects": writable})
        from rebalance.ingest.auth_log import log_project_auto_promoted

        for row in writable:
            inference = row["custom_fields"]["inference"]
            log_project_auto_promoted(
                inference["repo_full_name"],
                project_name=row["name"],
                commit_count=inference["commit_count"],
                threshold=inference["threshold"],
            )

    return AutoPromoteSummary(
        enabled=True,
        threshold=threshold,
        candidates_evaluated=len(candidates),
        promoted=writable,
        skipped_curated_names=skipped_curated,
    )

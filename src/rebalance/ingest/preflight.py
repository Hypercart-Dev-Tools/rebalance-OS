from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

import questionary

from rebalance.ingest.registry import (
    Project,
    Registry,
    load_registry,
    save_registry,
    sync_registry,
)
from rebalance.ingest.github_scan import (
    BAND_A_DAYS,
    BAND_B_DAYS,
    BAND_C_DAYS,
    discover_repos_from_activity,
)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class DiscoveryResult:
    """Returned by discover_candidates — read-only, no writes."""

    most_likely_active_projects: list[dict[str, Any]] = field(default_factory=list)
    semi_active_projects: list[dict[str, Any]] = field(default_factory=list)
    dormant_projects: list[dict[str, Any]] = field(default_factory=list)
    potential_projects: list[dict[str, Any]] = field(default_factory=list)
    scanned_files: int = 0
    github_error: str | None = None


@dataclass
class ConfirmResult:
    """Returned by confirm_and_write — registry written + sync attempted."""

    registry_path: str
    project_count: int
    sync_ok: bool


@dataclass
class PreflightResult:
    """Returned by run_preflight (CLI wrapper)."""

    scanned_files: int
    new_candidates: int
    curated_candidates: int


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _derive_title_from_note(note_path: Path) -> str:
    stem = note_path.stem.replace("_", " ").replace("-", " ").strip()
    if not stem:
        return "Untitled Project"
    return " ".join(word.capitalize() for word in stem.split())


def _scan_titles(vault_path: Path, registry_path: Path) -> tuple[list[str], int]:
    titles: list[str] = []
    scanned = 0
    for note_path in vault_path.rglob("*.md"):
        if note_path.resolve() == registry_path.resolve():
            continue
        scanned += 1
        titles.append(_derive_title_from_note(note_path))
    return titles, scanned


def _existing_names(registry: Registry) -> set[str]:
    names: set[str] = set()
    for group in (
        registry.active_projects,
        registry.potential_projects,
        registry.most_likely_active_projects,
        registry.semi_active_projects,
        registry.dormant_projects,
        registry.archived_projects,
    ):
        for project in group:
            names.add(project.name.strip().casefold())
    return names


def _calculate_days_since_activity(last_activity_at: str | None) -> int:
    """
    Calculate days since last activity date (ISO 8601).
    Return 999 if no activity date provided (safe for comparison).
    """
    if not last_activity_at:
        return 999
    try:
        from rebalance.ingest.calendar_helpers import parse_calendar_dt
        activity_dt = parse_calendar_dt(last_activity_at)
        now = datetime.now(timezone.utc)
        if activity_dt.tzinfo is None:
            activity_dt = activity_dt.replace(tzinfo=timezone.utc)
        delta = now - activity_dt
        return delta.days
    except (ValueError, TypeError):
        return 999


def _segment_project(project_dict: dict[str, Any]) -> str:
    """Return the registry section name for a candidate based on activity recency."""
    days_since = _calculate_days_since_activity(project_dict.get("last_activity_at"))
    if days_since <= BAND_B_DAYS:
        return "most_likely_active_projects"
    elif days_since <= BAND_C_DAYS:
        return "semi_active_projects"
    elif days_since < 999:
        return "dormant_projects"
    else:
        return "potential_projects"


def _classify_repo_bands(bands: list[str]) -> str:
    """
    Classify a GitHub repo candidate into a registry segment based on which
    time bands have activity.

    Band definitions (see BAND_*_DAYS in github_scan.py):
      A = last {BAND_A_DAYS} days
      B = {BAND_A_DAYS+1}-{BAND_B_DAYS} days ago
      C = {BAND_B_DAYS+1}-{BAND_C_DAYS} days ago

    Rules (in priority order):
      A+B (with or without C) → most_likely_active  (consistent recent activity)
      A only                  → most_likely_active  (hot sprint)
      A+C (no B)              → semi_active         (gap in the middle)
      B+C or B only           → semi_active         (cooling off, nothing recent)
      C only                  → dormant
      none                    → potential
    """
    s = set(bands)
    has_a = "A" in s
    has_b = "B" in s
    has_c = "C" in s

    if has_a and has_b:
        return "most_likely_active_projects"
    if has_a and not has_b:
        return "semi_active_projects" if has_c else "most_likely_active_projects"
    if has_b:
        return "semi_active_projects"
    if has_c:
        return "dormant_projects"
    return "potential_projects"


def _prompt_project_details(project: Project, non_interactive: bool) -> Project:
    if non_interactive:
        if not project.summary:
            project.summary = "Add a 2-3 sentence summary during next interactive preflight review."
        return project

    summary = questionary.text(
        f"2-3 sentence summary for '{project.name}':",
        default=project.summary or "",
    ).ask()
    if summary:
        project.summary = summary.strip()

    priority = questionary.text("priority_tier (1-5)", default="3").ask() or "3"
    value_score = questionary.text("value_score (1-10)", default="5").ask() or "5"
    risk_score = questionary.text("risk_score (1-10)", default="5").ask() or "5"
    weekly_target = questionary.text("weekly_hours_target", default="5").ask() or "5"
    confidence = questionary.text("confidence_score (1-10)", default="5").ask() or "5"

    strategic_reason = questionary.text("strategic_reason", default="").ask() or ""
    failure_mode = questionary.text("failure_mode", default="").ask() or ""
    momentum_state = questionary.select("momentum_state", choices=["cold", "warm", "hot"]).ask() or "warm"
    stakeholder_context = questionary.text("stakeholder_context", default="").ask() or ""
    notes_quality = questionary.select("notes_quality", choices=["low", "medium", "high"]).ask() or "medium"

    project.custom_fields = {
        "quantitative": {
            "priority_tier": int(priority),
            "value_score": int(value_score),
            "risk_score": int(risk_score),
            "weekly_hours_target": int(weekly_target),
            "confidence_score": int(confidence),
        },
        "qualitative": {
            "strategic_reason": strategic_reason,
            "failure_mode": failure_mode,
            "momentum_state": momentum_state,
            "stakeholder_context": stakeholder_context,
            "notes_quality": notes_quality,
        },
    }

    return project


# ---------------------------------------------------------------------------
# Public API — pure discovery (read-only)
# ---------------------------------------------------------------------------


def discover_candidates(
    vault_path: Path,
    registry_path: Path,
    github_token: str | None = None,
    github_days: int = 30,
) -> DiscoveryResult:
    """
    Discover project candidates from vault titles and GitHub activity.

    Read-only: does not write to registry, DB, or filesystem.
    Returns candidates segmented by activity recency.
    """
    registry = load_registry(registry_path)
    existing = _existing_names(registry)

    titles, scanned = _scan_titles(vault_path=vault_path, registry_path=registry_path)

    discovered: list[Project] = []
    for title in titles:
        key = title.casefold()
        if key in existing:
            continue
        discovered.append(Project(name=title, status="potential"))
        existing.add(key)

    github_error: str | None = None
    if github_token:
        try:
            repo_candidates = discover_repos_from_activity(token=github_token, days=github_days)
            for repo_cand in repo_candidates:
                key = repo_cand.repo_full_name.casefold()
                if key not in existing:
                    discovered.append(
                        Project(
                            name=repo_cand.repo_full_name,
                            status="potential",
                            summary=(
                                f"Recent activity: {repo_cand.commit_count} commits, "
                                f"{repo_cand.activity_score} total events (last {github_days} days). "
                                f"Active bands: {', '.join(repo_cand.bands) or 'none'}."
                            ),
                            repos=[repo_cand.repo_full_name],
                            last_activity_at=repo_cand.last_active_at,
                            tags=repo_cand.bands,  # store bands as tags for downstream use
                        )
                    )
                    existing.add(key)
        except Exception as e:
            github_error = str(e)

    # Segment candidates — GitHub repos use band-based classification, vault-only use recency.
    # GitHub repos have band letters (A/B/C) stored in their tags field.
    result = DiscoveryResult(scanned_files=scanned, github_error=github_error)
    for project in discovered:
        d = project.model_dump(mode="json")
        bands: list[str] = [t for t in (d.get("tags") or []) if t in ("A", "B", "C")]
        if bands:
            segment = _classify_repo_bands(bands)
        else:
            segment = _segment_project(d)
        getattr(result, segment).append(d)

    return result


# ---------------------------------------------------------------------------
# Public API — confirm and write (side effects)
# ---------------------------------------------------------------------------


def confirm_and_write(
    projects: list[dict[str, Any]],
    vault_path: Path,
    registry_path: Path,
    projects_yaml_path: Path,
    database_path: Path,
) -> ConfirmResult:
    """
    Write confirmed projects to the canonical registry and run pull sync.

    Creates standard vault directories (Projects/, Daily Notes/) if missing.
    """
    registry = load_registry(registry_path)

    for proj_dict in projects:
        project = Project.model_validate(proj_dict)
        # Respect explicit status field: active → active_projects (scored/tracked).
        # Otherwise fall back to activity-based segmentation.
        explicit_status = (proj_dict.get("status") or "").strip().lower()
        if explicit_status == "active":
            registry.active_projects.append(project)
        else:
            segment = _segment_project(proj_dict)
            getattr(registry, segment).append(project)

    save_registry(registry_path=registry_path, registry=registry)

    # Create standard vault dirs
    (vault_path / "Projects").mkdir(parents=True, exist_ok=True)
    (vault_path / "Daily Notes").mkdir(parents=True, exist_ok=True)

    # Run pull sync to materialize projections
    try:
        sync_registry(
            mode="pull",
            registry_path=registry_path,
            projects_yaml_path=projects_yaml_path,
            database_path=database_path,
        )
        sync_ok = True
    except Exception:
        sync_ok = False

    return ConfirmResult(
        registry_path=str(registry_path),
        project_count=len(projects),
        sync_ok=sync_ok,
    )


# ---------------------------------------------------------------------------
# CLI wrapper — discover → interactive prompts → write registry
# ---------------------------------------------------------------------------


def run_preflight(
    vault_path: Path,
    registry_path: Path,
    non_interactive: bool = False,
    github_token: str | None = None,
    github_days: int = 30,
) -> PreflightResult:
    """
    CLI-oriented preflight: discover candidates, prompt user, write registry.

    Does NOT run sync — the user runs `rebalance ingest sync --mode pull` separately.
    For MCP-driven onboarding, use discover_candidates + confirm_and_write instead.
    """
    discovery = discover_candidates(
        vault_path=vault_path,
        registry_path=registry_path,
        github_token=github_token,
        github_days=github_days,
    )

    if discovery.github_error and not non_interactive:
        questionary.print(f"⚠ GitHub scan failed: {discovery.github_error}")

    # Flatten all segments for interactive selection
    all_candidates = (
        discovery.most_likely_active_projects
        + discovery.semi_active_projects
        + discovery.dormant_projects
        + discovery.potential_projects
    )
    total_new = len(all_candidates)

    if not all_candidates:
        return PreflightResult(scanned_files=discovery.scanned_files, new_candidates=0, curated_candidates=0)

    # Interactive keep/remove
    if not non_interactive:
        selected_names = questionary.checkbox(
            "Review candidates: select the projects to keep",
            choices=[c["name"] for c in all_candidates],
        ).ask() or []
        selected = {name.casefold() for name in selected_names}
        all_candidates = [c for c in all_candidates if c["name"].casefold() in selected]

    # Prompt for details per candidate
    curated: list[dict[str, Any]] = []
    for candidate_dict in all_candidates:
        project = Project.model_validate(candidate_dict)
        project = _prompt_project_details(project=project, non_interactive=non_interactive)
        curated.append(project.model_dump(mode="json"))

    # Write to registry (no sync — CLI user runs sync separately)
    if curated:
        registry = load_registry(registry_path)
        for proj_dict in curated:
            project = Project.model_validate(proj_dict)
            segment = _segment_project(proj_dict)
            getattr(registry, segment).append(project)
        save_registry(registry_path=registry_path, registry=registry)

    return PreflightResult(
        scanned_files=discovery.scanned_files,
        new_candidates=total_new,
        curated_candidates=len(curated),
    )

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import questionary

from rebalance.ingest.registry import Project, Registry, load_registry, save_registry
from rebalance.ingest.github_scan import discover_repos_from_activity


@dataclass
class PreflightResult:
    scanned_files: int
    new_candidates: int
    curated_candidates: int


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
    for group in (registry.active_projects, registry.potential_projects, registry.archived_projects):
        for project in group:
            names.add(project.name.strip().casefold())
    return names


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


def run_preflight(
    vault_path: Path,
    registry_path: Path,
    non_interactive: bool = False,
    github_token: str | None = None,
    github_days: int = 14,
) -> PreflightResult:
    """
    Discover project candidates from vault titles and/or GitHub activity.

    Args:
        vault_path:       Path to Obsidian vault.
        registry_path:    Path to project registry Markdown file.
        non_interactive:  Skip prompts; apply defaults.
        github_token:     Optional GitHub PAT for discovering repos from recent activity.
        github_days:      How many days back to scan GitHub activity (max ~14).

    Returns:
        PreflightResult with stats.
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

    # Optionally scan GitHub for recent repos
    if github_token:
        try:
            repo_candidates = discover_repos_from_activity(token=github_token, days=github_days)
            for repo_cand in repo_candidates:
                key = repo_cand.repo_full_name.casefold()
                if key not in existing:
                    project = Project(
                        name=repo_cand.repo_full_name,
                        status="potential",
                        summary=f"Recent activity: {repo_cand.commit_count} commits, {repo_cand.activity_score} total events (last {github_days} days).",
                        repos=[repo_cand.repo_full_name],
                    )
                    discovered.append(project)
                    existing.add(key)
        except Exception as e:
            # If GitHub scan fails, still proceed with vault titles
            if not non_interactive:
                questionary.print(f"⚠ GitHub scan failed: {e}")
            pass

    if not discovered:
        save_registry(registry_path, registry)
        return PreflightResult(scanned_files=scanned, new_candidates=0, curated_candidates=0)

    candidates = discovered
    if not non_interactive:
        selected_names = questionary.checkbox(
            "Review candidates: select the projects to keep",
            choices=[item.name for item in candidates],
        ).ask() or []
        selected = {name.casefold() for name in selected_names}
        candidates = [item for item in candidates if item.name.casefold() in selected]

    curated: list[Project] = []
    for project in candidates:
        curated.append(_prompt_project_details(project=project, non_interactive=non_interactive))

    registry.potential_projects.extend(curated)
    save_registry(registry_path=registry_path, registry=registry)

    return PreflightResult(
        scanned_files=scanned,
        new_candidates=len(discovered),
        curated_candidates=len(curated),
    )

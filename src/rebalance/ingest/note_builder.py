"""Obsidian dashboard synthesis for rebalance OS."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from rebalance.ingest.calendar_config import (
    OPERATOR_CALENDAR_ID,
    CalendarConfig,
    filter_events,
    load_review_decisions,
)
from rebalance.ingest.calendar_helpers import event_duration_minutes
from rebalance.ingest.config import get_gemini_api_key
from rebalance.ingest.db import db_connection, ensure_calendar_schema
from rebalance.tz_utils import format_local, local_tz
from rebalance.ingest.project_priority import apply_project_priorities
from rebalance.ingest.project_classifier import annotate_events_with_projects, load_project_matchers
from rebalance.ingest.registry import get_projects


REPO_ROOT = Path(__file__).parent.parent.parent.parent
DEFAULT_CHANGELOG_PATH = REPO_ROOT / "CHANGELOG.md"
DEFAULT_4X4_PATH = REPO_ROOT / "4X4.md"


def get_all_repo_activity_by_org(
    database_path: Path,
    since_days: int = 14,
) -> dict[str, list[dict[str, Any]]]:
    """
    Return all github_activity rows grouped by GitHub org, with no project_registry filter.

    Every repo that had any activity in the window appears regardless of whether it is
    registered in Obsidian. Repos within each org are sorted by last_active_at DESC.
    """
    if not database_path.exists():
        return {}

    from rebalance.ingest.config import get_github_ignored_repos
    from rebalance.ingest.db import db_connection, ensure_github_schema

    since_date = (datetime.now(timezone.utc) - timedelta(days=since_days)).strftime("%Y-%m-%d")

    ignored = get_github_ignored_repos()
    params: list[Any] = [since_date]
    ignored_clause = ""
    if ignored:
        placeholders = ",".join("?" * len(ignored))
        ignored_clause = f"AND LOWER(repo_full_name) NOT IN ({placeholders})"
        params.extend(ignored)

    with db_connection(database_path, ensure_github_schema) as conn:
        rows = conn.execute(
            f"""
            SELECT repo_full_name,
                   SUM(commits)        AS commits,
                   SUM(prs_opened)     AS prs_opened,
                   SUM(prs_merged)     AS prs_merged,
                   SUM(issues_opened)  AS issues_opened,
                   MAX(last_active_at) AS last_active_at
            FROM github_activity
            WHERE scan_date >= ?
            {ignored_clause}
            GROUP BY repo_full_name
            """,
            tuple(params),
        ).fetchall()

    by_org: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        repo = row["repo_full_name"]
        org = repo.split("/")[0] if "/" in repo else repo
        by_org.setdefault(org, []).append({
            "repo_full_name": repo,
            "commits": int(row["commits"] or 0),
            "prs_opened": int(row["prs_opened"] or 0),
            "prs_merged": int(row["prs_merged"] or 0),
            "issues_opened": int(row["issues_opened"] or 0),
            "last_active_at": row["last_active_at"],
        })

    for org_repos in by_org.values():
        org_repos.sort(key=lambda r: r["last_active_at"] or "", reverse=True)

    return by_org


@dataclass
class DashboardProjectRow:
    name: str
    summary: str
    priority_tier: int | None
    priority_score: int = 0
    client: str = ""
    value_level: str | None = None
    value_score: int | None = None
    risk_level: str | None = None


@dataclass
class DashboardPayload:
    target_date: date
    since_days: int
    generated_at: str
    highlights: list[str]
    current_goals: list[str]
    projects: list[DashboardProjectRow]
    needs_review: list[str]
    source_window: dict[str, str]
    operator_summary: str
    org_activity: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


def read_recent_changelog_highlights(path: Path, *, max_versions: int = 2, max_bullets: int = 8) -> list[str]:
    """Return recent changelog bullets from the newest version sections."""
    if not path.exists():
        return []

    lines = path.read_text(encoding="utf-8").splitlines()
    bullets: list[str] = []
    versions_seen = 0

    for line in lines:
        if line.startswith("## ["):
            versions_seen += 1
            if versions_seen > max_versions:
                break
            continue
        if versions_seen == 0:
            continue
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        bullets.append(stripped[2:].strip())
        if len(bullets) >= max_bullets:
            break

    return bullets


def read_current_goals(path: Path, *, limit: int = 4) -> list[str]:
    """Return the current-week goals from the 4X4 document."""
    if not path.exists():
        return []

    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    goals: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped == "B. CURRENT WEEK GOALS":
            in_section = True
            continue
        if in_section and stripped.startswith("C. "):
            break
        if not in_section:
            continue
        if not stripped or not stripped[0].isdigit():
            continue
        _, _, goal = stripped.partition(".")
        cleaned = goal.strip().replace("[ ]", "").strip()
        if cleaned:
            goals.append(cleaned)
        if len(goals) >= limit:
            break

    return goals


def _load_recent_calendar_activity(
    database_path: Path,
    *,
    target_date: date,
    since_days: int,
    config: CalendarConfig,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Aggregate recent calendar events into project-aligned stats."""
    start_date = target_date - timedelta(days=since_days - 1)
    with db_connection(database_path, ensure_calendar_schema) as conn:
        rows = conn.execute(
            """
            SELECT summary, start_time, end_time
            FROM calendar_events
            WHERE calendar_id = ?
              AND DATE(start_time) >= ?
              AND DATE(start_time) <= ?
            ORDER BY start_time DESC
            """,
            # Operator rows are canonically stored as 'primary' (see
            # OPERATOR_CALENDAR_ID); config.calendar_id would miss them.
            (OPERATOR_CALENDAR_ID, start_date.isoformat(), target_date.isoformat()),
        ).fetchall()

    events = [
        {
            "summary": row["summary"] or "",
            "start_time": row["start_time"] or "",
            "end_time": row["end_time"] or "",
        }
        for row in rows
    ]
    filtered = filter_events(events, config.exclude_titles)
    matchers = load_project_matchers(database_path, config=config)
    annotated = annotate_events_with_projects(filtered, matchers)
    review_decisions = load_review_decisions()

    project_stats: dict[str, dict[str, Any]] = {}
    needs_review: list[str] = []

    for event in annotated:
        decision = review_decisions.get(event["summary"].strip().lower())
        if decision == "exclude":
            continue

        project_name = event.get("project_name")
        if decision and decision.startswith("project:"):
            project_name = decision.split(":", 1)[1].strip()

        minutes = event_duration_minutes(event["start_time"], event["end_time"])
        if project_name:
            stats = project_stats.setdefault(
                project_name,
                {"event_count": 0, "total_minutes": 0, "sample_titles": []},
            )
            stats["event_count"] += 1
            stats["total_minutes"] += minutes
            title = event["summary"].strip()
            if title and title not in stats["sample_titles"] and len(stats["sample_titles"]) < 3:
                stats["sample_titles"].append(title)
            continue

        start_day = event["start_time"][:10] if event["start_time"] else ""
        label = f"{start_day} — {event['summary']}".strip(" —")
        if label not in needs_review:
            needs_review.append(label)

    return project_stats, needs_review[:10]


def build_dashboard_payload(
    database_path: Path,
    *,
    target_date: date,
    since_days: int,
    config: CalendarConfig | None = None,
    changelog_path: Path = DEFAULT_CHANGELOG_PATH,
    goals_path: Path = DEFAULT_4X4_PATH,
) -> DashboardPayload:
    """Build the structured payload that drives the dashboard markdown."""
    config = config or CalendarConfig.load()
    projects = apply_project_priorities(get_projects(database_path, status="active"))
    org_activity = get_all_repo_activity_by_org(database_path, since_days=since_days)
    calendar_stats, needs_review = _load_recent_calendar_activity(
        database_path,
        target_date=target_date,
        since_days=since_days,
        config=config,
    )

    project_rows: list[DashboardProjectRow] = []
    for project in projects:
        name = project["name"]
        custom_fields = project.get("custom_fields") or {}
        display_name = str(custom_fields.get("priority_display_name") or name)
        client = str(custom_fields.get("client") or "")
        value_score = custom_fields.get("value_score")
        project_rows.append(
            DashboardProjectRow(
                name=display_name,
                summary=project.get("summary") or "",
                priority_tier=project.get("priority_tier"),
                priority_score=int(project.get("priority_score") or 0),
                client=client,
                value_level=project.get("value_level"),
                value_score=value_score if isinstance(value_score, int) else None,
                risk_level=project.get("risk_level"),
            )
        )

    project_rows.sort(
        key=lambda row: (
            -row.priority_score,
            row.priority_tier if row.priority_tier is not None else 99,
            row.name.lower(),
        )
    )

    total_repos = sum(len(repos) for repos in org_activity.values())
    operator_summary = (
        f"{len(project_rows)} active project(s); {total_repos} repo(s) with activity across "
        f"{len(org_activity)} org(s) in the last {since_days} days; "
        f"{len(needs_review)} unattributed calendar item(s) waiting for review."
    )

    return DashboardPayload(
        target_date=target_date,
        since_days=since_days,
        generated_at=datetime.now(timezone.utc).isoformat(),
        highlights=read_recent_changelog_highlights(changelog_path),
        current_goals=read_current_goals(goals_path),
        projects=project_rows,
        needs_review=needs_review,
        source_window={
            "calendar_since": (target_date - timedelta(days=since_days - 1)).isoformat(),
            "calendar_until": target_date.isoformat(),
            "changelog_path": str(changelog_path),
            "goals_path": str(goals_path),
        },
        operator_summary=operator_summary,
        org_activity=org_activity,
    )




def synthesize_dashboard_narrative(
    payload: DashboardPayload,
    *,
    api_key: str,
    model: str,
    cleanup: bool = False,
) -> str:
    """Generate a concise operator summary via the Gemini REST API."""
    project_lines = [
        f"- {project.name} (tier {project.priority_tier or 'n/a'}): {project.summary or '(no summary)'}"
        for project in payload.projects[:8]
    ]
    prompt_parts = [
        "Write a concise operator summary for a personal work dashboard.",
        "Preserve the facts exactly. Do not invent projects, risks, or actions.",
        "Return markdown only. No heading. Use one short paragraph plus up to three bullets.",
        "Tone: direct, pragmatic, low-drama.",
    ]
    if cleanup:
        prompt_parts.append("Tighten wording aggressively and remove redundancy.")
    prompt_parts.extend(
        [
            "",
            f"Target date: {payload.target_date.isoformat()}",
            f"Window: last {payload.since_days} days",
            f"Recent highlights: {' | '.join(payload.highlights[:6]) or '(none)'}",
            f"Current goals: {' | '.join(payload.current_goals[:4]) or '(none)'}",
            f"Needs review count: {len(payload.needs_review)}",
            "Project signals:",
            *project_lines,
        ]
    )
    body = {
        "contents": [{"parts": [{"text": "\n".join(prompt_parts)}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 320,
        },
    }
    request = urllib.request.Request(
        url=f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload_json = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # pragma: no cover - network path
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini request failed with HTTP {exc.code}: {error_body}") from exc
    except urllib.error.URLError as exc:  # pragma: no cover - network path
        raise RuntimeError(f"Gemini request failed: {exc.reason}") from exc

    candidates = payload_json.get("candidates") or []
    if not candidates:
        raise RuntimeError(f"Gemini response did not contain candidates: {payload_json}")
    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    text = "\n".join(part.get("text", "").strip() for part in parts if part.get("text")).strip()
    if not text:
        raise RuntimeError(f"Gemini response did not contain text: {payload_json}")
    return text


def render_dashboard_markdown(
    payload: DashboardPayload,
    *,
    synthesized_summary: str = "",
) -> str:
    """Render the dashboard markdown note."""
    generated_at = _format_generated_at(payload.generated_at)
    lines = [
        "---",
        "type: dashboard",
        f"generated_at: {payload.generated_at}",
        f"target_date: {payload.target_date.isoformat()}",
        f"window_days: {payload.since_days}",
        "generated_by: rebalance",
        "tags:",
        "  - dashboard",
        "  - autogenerated",
        "---",
        "",
        "# rebalanceOS Dashboard",
        f"_Last generated: {generated_at}_",
        "",
        "## Table of Contents",
        "- [Now](#now)",
        "- [Recent Highlights](#recent-highlights)",
        "- [Current Focus](#current-focus)",
        "- [Project Rebalance](#project-rebalance)",
        "- [Recent GitHub Activity](#recent-github-activity)",
        "- [Needs Review](#needs-review)",
        "- [Source Window](#source-window)",
        "",
        "## Now",
        f"- {payload.operator_summary}",
    ]

    if synthesized_summary:
        lines.extend(["", synthesized_summary.strip()])

    lines.extend(["", "## Recent Highlights"])
    if payload.highlights:
        lines.extend([f"- {item}" for item in payload.highlights])
    else:
        lines.append("- No recent changelog highlights found.")

    lines.extend(["", "## Current Focus"])
    if payload.current_goals:
        lines.extend([f"- {item}" for item in payload.current_goals])
    else:
        lines.append("- No current-week goals found in 4X4.")

    lines.extend(["", "## Project Rebalance"])
    if not payload.projects:
        lines.append("- No active projects found in the local registry.")
    else:
        for project in payload.projects:
            tier = project.priority_tier if project.priority_tier is not None else "n/a"
            value_str = project.value_level or "n/a"
            if project.value_score is not None:
                value_str += f" ({project.value_score}/10)"
            lines.extend(
                [
                    "",
                    f"### {project.name}",
                    f"- Priority tier: {tier}",
                    f"- Client: {project.client or 'n/a'}",
                    f"- Value: {value_str}",
                    f"- Risk: {project.risk_level or 'n/a'}",
                ]
            )
            if project.summary:
                lines.append(f"- Summary: {project.summary}")

    lines.extend(["", "## Recent GitHub Activity"])
    if payload.org_activity:
        for org, repos in sorted(payload.org_activity.items()):
            lines.append(f"\n### {org}")
            for repo in repos:
                commits = repo["commits"]
                last_active = (repo["last_active_at"] or "")[:10]
                prs = repo["prs_merged"]
                parts = [f"{commits} commit(s)"]
                if prs:
                    parts.append(f"{prs} PR(s) merged")
                if last_active:
                    parts.append(f"last active {last_active}")
                lines.append(f"- {repo['repo_full_name']} — {' · '.join(parts)}")
    else:
        lines.append(f"- No GitHub activity in the last {payload.since_days} days.")

    lines.extend(["", "## Needs Review"])
    if payload.needs_review:
        lines.extend([f"- {item}" for item in payload.needs_review])
    else:
        lines.append("- No unattributed or low-confidence calendar items in the current window.")

    lines.extend(
        [
            "",
            "## Source Window",
            f"- Calendar window: {payload.source_window['calendar_since']} to {payload.source_window['calendar_until']}",
            f"- Changelog source: {payload.source_window['changelog_path']}",
            f"- 4X4 source: {payload.source_window['goals_path']}",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _format_generated_at(value: str) -> str:
    """Format an ISO timestamp for the visible dashboard freshness marker."""
    return format_local(value, "%Y-%m-%d %H:%M:%S %Z", tz=local_tz()) or value


def build_dashboard_note_content(
    database_path: Path,
    *,
    target_date: date,
    since_days: int,
    config: CalendarConfig | None = None,
    changelog_path: Path = DEFAULT_CHANGELOG_PATH,
    goals_path: Path = DEFAULT_4X4_PATH,
    gemini_synthesis: bool = False,
    gemini_model: str = "gemini-3.5-flash",
    cleanup: bool = False,
) -> str:
    """Build the final dashboard markdown, optionally with Gemini summary."""
    payload = build_dashboard_payload(
        database_path,
        target_date=target_date,
        since_days=since_days,
        config=config,
        changelog_path=changelog_path,
        goals_path=goals_path,
    )

    synthesized_summary = ""
    if gemini_synthesis:
        api_key = get_gemini_api_key()
        if not api_key:
            raise RuntimeError("Gemini synthesis requested but GEMINI_API_KEY / GOOGLE_API_KEY is not set.")
        synthesized_summary = synthesize_dashboard_narrative(
            payload,
            api_key=api_key,
            model=gemini_model,
            cleanup=cleanup,
        )

    return render_dashboard_markdown(payload, synthesized_summary=synthesized_summary)


def write_dashboard_note(output_path: Path, markdown: str) -> Path:
    """Write the generated dashboard note to disk."""
    resolved = output_path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(markdown, encoding="utf-8")
    return resolved

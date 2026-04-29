"""Obsidian dashboard synthesis for rebalance OS."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from rebalance.ingest.calendar_config import CalendarConfig, filter_events, load_review_decisions
from rebalance.ingest.calendar_helpers import event_duration_minutes
from rebalance.ingest.db import db_connection, ensure_calendar_schema
from rebalance.ingest.github_scan import get_github_balance
from rebalance.ingest.project_classifier import annotate_events_with_projects, load_project_matchers
from rebalance.ingest.registry import get_projects


REPO_ROOT = Path(__file__).parent.parent.parent.parent
DEFAULT_CHANGELOG_PATH = REPO_ROOT / "CHANGELOG.md"
DEFAULT_4X4_PATH = REPO_ROOT / "4X4.md"
@dataclass
class DashboardProjectRow:
    name: str
    summary: str
    priority_tier: int | None
    verdict: str
    confidence: str
    evidence: list[str] = field(default_factory=list)
    next_move: str = ""
    source_counts: dict[str, int] = field(default_factory=dict)
    activity_score: int = 0


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
            (config.calendar_id, start_date.isoformat(), target_date.isoformat()),
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


def _determine_verdict(
    *,
    priority_tier: int | None,
    calendar_minutes: int,
    github_stats: dict[str, Any],
) -> tuple[str, str, str, int]:
    """Return verdict, confidence, next move, and activity score."""
    commits = int(github_stats.get("total_commits") or 0)
    prs_opened = int(github_stats.get("prs_opened") or 0)
    repos_touched = len(github_stats.get("repos_touched") or [])
    calendar_hours = calendar_minutes / 60
    source_count = int(calendar_minutes > 0) + int(repos_touched > 0)
    tier = priority_tier or 99

    if tier <= 2 and calendar_minutes == 0 and repos_touched == 0:
        return (
            "Needs attention",
            "medium",
            "Schedule one concrete work block or define the next deliverable this week.",
            0,
        )
    if calendar_hours >= 6 or commits >= 8 or prs_opened >= 2:
        return (
            "Heavy focus",
            "high" if source_count == 2 else "medium",
            "Protect momentum, but confirm this level of attention still matches current priorities.",
            4,
        )
    if calendar_hours >= 2 or commits >= 2 or repos_touched > 0:
        return (
            "Active",
            "high" if source_count == 2 else "medium",
            "Keep the thread moving and capture the next explicit step before context decays.",
            3,
        )
    if tier <= 2:
        return (
            "Quiet",
            "low",
            "Decide whether this is intentionally parked or needs a small restart move.",
            1,
        )
    return (
        "Quiet",
        "low",
        "Leave parked unless another signal raises its priority this week.",
        0,
    )


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
    projects = get_projects(database_path, status="active")
    repo_map = {project["name"]: list(project.get("repos") or []) for project in projects}
    github_rows = {
        row["project_name"]: row
        for row in get_github_balance(database_path, repo_map, since_days=since_days)
    }
    calendar_stats, needs_review = _load_recent_calendar_activity(
        database_path,
        target_date=target_date,
        since_days=since_days,
        config=config,
    )

    project_rows: list[DashboardProjectRow] = []
    for project in projects:
        name = project["name"]
        github_stats = github_rows.get(
            name,
            {
                "total_commits": 0,
                "prs_opened": 0,
                "prs_merged": 0,
                "issues_opened": 0,
                "repos_touched": [],
                "repos_linked": project.get("repos") or [],
            },
        )
        calendar_row = calendar_stats.get(
            name,
            {"event_count": 0, "total_minutes": 0, "sample_titles": []},
        )
        verdict, confidence, next_move, activity_score = _determine_verdict(
            priority_tier=project.get("priority_tier"),
            calendar_minutes=int(calendar_row["total_minutes"]),
            github_stats=github_stats,
        )
        evidence = [
            (
                f"Calendar: {calendar_row['total_minutes'] / 60:.2f}h across "
                f"{calendar_row['event_count']} event(s) in the last {since_days} days."
            ),
            (
                f"GitHub: {int(github_stats.get('total_commits') or 0)} commits, "
                f"{int(github_stats.get('prs_opened') or 0)} PR(s) opened, "
                f"{int(github_stats.get('prs_merged') or 0)} PR(s) merged across "
                f"{len(github_stats.get('repos_touched') or [])} touched repo(s)."
            ),
        ]
        if calendar_row["sample_titles"]:
            evidence.append("Recent calendar titles: " + "; ".join(calendar_row["sample_titles"]))
        if project.get("summary"):
            evidence.append(f"Registry summary: {project['summary']}")

        project_rows.append(
            DashboardProjectRow(
                name=name,
                summary=project.get("summary") or "",
                priority_tier=project.get("priority_tier"),
                verdict=verdict,
                confidence=confidence,
                evidence=evidence,
                next_move=next_move,
                source_counts={
                    "calendar_events": int(calendar_row["event_count"]),
                    "repos_linked": len(project.get("repos") or []),
                    "repos_touched": len(github_stats.get("repos_touched") or []),
                },
                activity_score=activity_score,
            )
        )

    project_rows.sort(
        key=lambda row: (
            row.priority_tier if row.priority_tier is not None else 99,
            -row.activity_score,
            row.name.lower(),
        )
    )

    needs_attention = sum(1 for row in project_rows if row.verdict == "Needs attention")
    heavy_focus = sum(1 for row in project_rows if row.verdict == "Heavy focus")
    operator_summary = (
        f"{len(project_rows)} active project(s); {heavy_focus} in heavy focus, "
        f"{needs_attention} needing attention, and {len(needs_review)} unattributed item(s) "
        f"still waiting for review."
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
    )


def get_gemini_api_key() -> str | None:
    """Resolve Gemini API key from environment."""
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def synthesize_dashboard_narrative(
    payload: DashboardPayload,
    *,
    api_key: str,
    model: str,
    cleanup: bool = False,
) -> str:
    """Generate a concise operator summary via the Gemini REST API."""
    project_lines = [
        f"- {project.name}: {project.verdict}; confidence={project.confidence}; next={project.next_move}"
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
        "",
        "## Table of Contents",
        "- [Now](#now)",
        "- [Recent Highlights](#recent-highlights)",
        "- [Current Focus](#current-focus)",
        "- [Project Rebalance](#project-rebalance)",
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
            lines.extend(
                [
                    "",
                    f"### {project.name}",
                    f"- Verdict: {project.verdict}",
                    f"- Confidence: {project.confidence}",
                    f"- Priority tier: {tier}",
                    f"- Source counts: calendar_events={project.source_counts.get('calendar_events', 0)}, "
                    f"repos_linked={project.source_counts.get('repos_linked', 0)}, "
                    f"repos_touched={project.source_counts.get('repos_touched', 0)}",
                    "- Evidence:",
                ]
            )
            lines.extend([f"  - {item}" for item in project.evidence])
            lines.append(f"- Next move: {project.next_move}")

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


def build_dashboard_note_content(
    database_path: Path,
    *,
    target_date: date,
    since_days: int,
    config: CalendarConfig | None = None,
    changelog_path: Path = DEFAULT_CHANGELOG_PATH,
    goals_path: Path = DEFAULT_4X4_PATH,
    gemini_synthesis: bool = False,
    gemini_model: str = "gemini-2.5-flash",
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

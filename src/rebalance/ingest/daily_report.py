"""
Daily calendar report generator — creates markdown report with daily totals and project aggregator.

Excludes events by keyword, groups similar tasks, and generates stats.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from rebalance.ingest.calendar_config import (
    CalendarConfig,
    filter_events,
    load_review_decisions,
)
from rebalance.ingest.calendar_helpers import (
    calendar_connection,
    event_duration_minutes,
    parse_calendar_dt,
)
from rebalance.ingest.project_classifier import (
    ProjectMatcher,
    annotate_events_with_projects,
    load_project_matchers,
)

DEFAULT_AGGREGATOR_SKIP_WORDS = frozenset(
    {
        "and",
        "can",
        "change",
        "check",
        "confirm",
        "daily",
        "download",
        "drive",
        "earlier",
        "fix",
        "for",
        "get",
        "if",
        "later",
        "make",
        "move",
        "new",
        "off",
        "post",
        "prepare",
        "recap",
        "set",
        "setup",
        "slack",
        "start",
        "submit",
        "take",
        "test",
        "testing",
        "the",
        "to",
        "update",
        "valid",
        "weekly",
        "wind",
        "with",
    }
)


@dataclass
class ProjectGroup:
    """Group of similar event names with combined stats."""
    keyword: str
    count: int
    total_minutes: int
    events: list[str]  # Original event summaries
    
    @property
    def total_hours(self) -> float:
        return self.total_minutes / 60.0


def _normalize_word_tokens(text: str) -> list[str]:
    """Split text into normalized word tokens for report grouping."""
    return [
        word
        for word in re.findall(r"\b[a-z0-9]+\b", text.lower())
        if len(word) > 1 and not word.isdigit()
    ]


def _build_aggregator_skip_words(
    extra_skip_words: list[str] | None = None,
) -> set[str]:
    """Combine built-in low-signal words with config aggregator_skip_words.

    Does NOT tokenize exclude_titles — those are full event titles used for
    filtering, not grouping labels. Mixing them leaks words like "post" from
    "Post Daily Timesheet" into the aggregator where they'd suppress
    legitimate project keywords.
    """
    skip_words = set(DEFAULT_AGGREGATOR_SKIP_WORDS)
    for word in extra_skip_words or []:
        skip_words.update(_normalize_word_tokens(word))
    return skip_words


def extract_keywords(
    text: str,
    top_n: int = 5,
    *,
    skip_words: set[str] | None = None,
) -> list[str]:
    """Extract top N most common words from event name."""
    words = [
        word
        for word in _normalize_word_tokens(text)
        if word not in (skip_words or set())
    ]

    counter = Counter(words)
    return [word for word, _ in counter.most_common(top_n)]


def group_similar_events(
    events: list[dict[str, Any]],
    *,
    aggregator_skip_words: list[str] | None = None,
) -> dict[str, ProjectGroup]:
    """Group events by most common keywords (case-insensitive substring matching)."""
    groups: dict[str, ProjectGroup] = {}
    skip_words = _build_aggregator_skip_words(aggregator_skip_words)
    fallback_skip_words = set(DEFAULT_AGGREGATOR_SKIP_WORDS)

    for event in events:
        project_name = (event.get("project_name") or "").strip()
        summary = event.get("summary", "")
        start_str = event.get("start_time", "")
        end_str = event.get("end_time", "")

        minutes = event_duration_minutes(start_str, end_str)

        # Canonical project matches from the registry win over heuristic grouping.
        if project_name:
            group_key = project_name
        else:
            keywords = extract_keywords(summary, skip_words=skip_words)

            # Prefer configured skip words first, then fall back to built-in skip
            # words so config can steer grouping without forcing raw-title labels
            # back in.
            if keywords:
                group_key = keywords[0].title()
            else:
                relaxed_keywords = extract_keywords(summary, skip_words=fallback_skip_words)
                group_key = (
                    relaxed_keywords[0].title()
                    if relaxed_keywords
                    else (summary.strip()[:20] or "(untagged)")
                )

        if group_key not in groups:
            groups[group_key] = ProjectGroup(
                keyword=group_key,
                count=0,
                total_minutes=0,
                events=[],
            )

        groups[group_key].count += 1
        groups[group_key].total_minutes += minutes
        groups[group_key].events.append(summary)

    return groups


@dataclass
class DayData:
    """Structured data for a single day (used by both daily and weekly reports)."""
    target_date: date
    filtered_events: list[dict[str, Any]]
    total_minutes: int
    groups: dict[str, ProjectGroup]
    needs_review: list[dict[str, Any]] = field(default_factory=list)


def _format_duration(minutes: int, hours_format: str = "decimal") -> str:
    """Format minutes into human-readable duration string.

    hours_format:
        "decimal" — e.g. "4.50h", "0.58h"  (default)
        "hm"      — e.g. "4h 30m", "35m"
    """
    if hours_format == "hm":
        hours = int(minutes / 60)
        mins = minutes % 60
        if hours > 0:
            return f"{hours}h {mins}m" if mins > 0 else f"{hours}h"
        return f"{mins}m"
    # decimal
    return f"{minutes / 60:.2f}h"


def get_day_data(
    database_path: Path,
    target_date: date,
    config: CalendarConfig,
    project_matchers: list[ProjectMatcher] | None = None,
) -> DayData:
    """Fetch and filter events for a single day. Returns structured data for reuse."""
    with calendar_connection(database_path) as conn:
        date_str = target_date.isoformat()
        rows = conn.execute(
            """SELECT summary, start_time, end_time
               FROM calendar_events
               WHERE DATE(start_time) = ?
                 AND calendar_id = ?
               ORDER BY start_time ASC""",
            (date_str, config.calendar_id),
        ).fetchall()

    events = [
        {
            "summary": row["summary"],
            "start_time": row["start_time"],
            "end_time": row["end_time"],
        }
        for row in rows
    ]

    filtered_events = filter_events(events, config.exclude_titles)
    filtered_events = annotate_events_with_projects(filtered_events, project_matchers or [])

    # Apply persisted review decisions
    review_decisions = load_review_decisions()
    kept: list[dict[str, Any]] = []
    needs_review: list[dict[str, Any]] = []
    for event in filtered_events:
        summary_key = event.get("summary", "").strip().lower()
        decision = review_decisions.get(summary_key)
        if decision == "exclude":
            continue
        elif decision and decision.startswith("project:"):
            event = {**event, "project_name": decision.split(":", 1)[1]}
            kept.append(event)
        else:
            kept.append(event)
            # Flag events with no project match and no prior decision
            if not event.get("project_name") and decision != "include":
                needs_review.append(event)

    total_minutes = sum(
        event_duration_minutes(e.get("start_time", ""), e.get("end_time", ""))
        for e in kept
    )

    groups = group_similar_events(
        kept,
        aggregator_skip_words=config.aggregator_skip_words,
    )

    return DayData(
        target_date=target_date,
        filtered_events=kept,
        total_minutes=total_minutes,
        groups=groups,
        needs_review=needs_review,
    )


def _pluralize_events(count: int) -> str:
    return "1 event" if count == 1 else f"{count} events"


def _event_local_time(event: dict[str, Any], config: CalendarConfig) -> str:
    """Format an event's start time in the configured local timezone."""
    try:
        start_dt = parse_calendar_dt(event["start_time"])
        local_time = start_dt.astimezone(ZoneInfo(config.timezone))
        return local_time.strftime("%I:%M %p").lstrip("0")
    except Exception:
        return "—"


def format_daily_markdown(day: DayData, config: CalendarConfig) -> str:
    """Render a DayData into markdown. Pure formatting — no DB access."""
    fmt = config.hours_format
    day_name = day.target_date.strftime("%A")
    md = f"## {day_name}, {day.target_date.strftime('%B %d, %Y')}\n\n"

    md += f"**Total:** {_pluralize_events(len(day.filtered_events))}, {_format_duration(day.total_minutes, fmt)}\n\n"

    if day.filtered_events:
        md += "### Events\n\n"
        for event in day.filtered_events:
            md += f"- {_event_local_time(event, config)} — {event['summary']}\n"
        md += "\n"

    sorted_groups = sorted(day.groups.items(), key=lambda x: x[1].total_minutes, reverse=True)
    if day.groups:
        md += "### Project Aggregator\n\n"
        for group_key, group in sorted_groups:
            md += f"- **{group_key}**: {_pluralize_events(group.count)}, {_format_duration(group.total_minutes, fmt)}\n"
        md += "\n"

    if day.needs_review:
        md += "### Needs Review\n\n"
        md += "Events not matched to a project. Use `review_timesheet` to classify.\n\n"
        for event in day.needs_review:
            md += f"- {_event_local_time(event, config)} — {event['summary']}\n"
        md += "\n"

    return md


def generate_daily_report(
    database_path: Path,
    target_date: date,
    config: CalendarConfig,
) -> str:
    """Generate markdown report for a single day (convenience wrapper)."""
    day = get_day_data(
        database_path,
        target_date,
        config,
        project_matchers=load_project_matchers(database_path, config=config),
    )
    return format_daily_markdown(day, config)

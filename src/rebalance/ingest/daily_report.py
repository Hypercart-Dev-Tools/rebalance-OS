"""
Daily calendar report generator — creates markdown report with daily totals and project aggregator.

Excludes events by keyword, groups similar tasks, and generates stats.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from rebalance.ingest.calendar import ensure_calendar_schema
from rebalance.ingest.calendar_config import CalendarConfig, filter_events
from rebalance.ingest.db import get_connection
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


def _build_aggregator_skip_words(exclude_keywords: list[str] | None = None) -> set[str]:
    """Combine built-in low-signal words with configured exclude keywords."""
    skip_words = set(DEFAULT_AGGREGATOR_SKIP_WORDS)
    for keyword in exclude_keywords or []:
        skip_words.update(_normalize_word_tokens(keyword))
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
    exclude_keywords: list[str] | None = None,
) -> dict[str, ProjectGroup]:
    """Group events by most common keywords (case-insensitive substring matching)."""
    groups: dict[str, ProjectGroup] = {}
    skip_words = _build_aggregator_skip_words(exclude_keywords)
    fallback_skip_words = set(DEFAULT_AGGREGATOR_SKIP_WORDS)

    for event in events:
        project_name = (event.get("project_name") or "").strip()
        summary = event.get("summary", "")
        start_str = event.get("start_time", "")
        end_str = event.get("end_time", "")

        # Calculate duration
        try:
            start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00')) if end_str else start_dt
            minutes = int((end_dt - start_dt).total_seconds() / 60)
        except Exception:
            minutes = 0

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
    conn = get_connection(database_path)
    ensure_calendar_schema(conn)

    date_str = target_date.isoformat()
    rows = conn.execute(
        """SELECT summary, start_time, end_time
           FROM calendar_events
           WHERE DATE(start_time) = ?
             AND calendar_id = ?
           ORDER BY start_time ASC""",
        (date_str, config.calendar_id),
    ).fetchall()
    conn.close()

    events = [
        {
            "summary": row["summary"],
            "start_time": row["start_time"],
            "end_time": row["end_time"],
        }
        for row in rows
    ]

    filtered_events = filter_events(events, config.exclude_keywords)
    filtered_events = annotate_events_with_projects(filtered_events, project_matchers or [])

    total_minutes = sum(
        int((datetime.fromisoformat(e["end_time"].replace('Z', '+00:00')) -
             datetime.fromisoformat(e["start_time"].replace('Z', '+00:00'))
            ).total_seconds() / 60)
        for e in filtered_events
        if e.get("end_time")
    )

    groups = group_similar_events(filtered_events, config.exclude_keywords)

    return DayData(
        target_date=target_date,
        filtered_events=filtered_events,
        total_minutes=total_minutes,
        groups=groups,
    )


def format_daily_markdown(day: DayData, config: CalendarConfig) -> str:
    """Render a DayData into markdown. Pure formatting — no DB access."""
    fmt = config.hours_format
    day_name = day.target_date.strftime("%A")
    md = f"## {day_name}, {day.target_date.strftime('%B %d, %Y')}\n\n"

    md += f"**Total:** {len(day.filtered_events)} events, {_format_duration(day.total_minutes, fmt)}\n\n"

    if day.filtered_events:
        md += "### Events\n\n"
        for event in day.filtered_events:
            try:
                start_dt = datetime.fromisoformat(event["start_time"].replace('Z', '+00:00'))
                tz = ZoneInfo(config.timezone)
                local_time = start_dt.astimezone(tz)
                time_str = local_time.strftime("%I:%M %p").lstrip('0')
            except Exception:
                time_str = "—"
            md += f"- {time_str} — {event['summary']}\n"
        md += "\n"

    sorted_groups = sorted(day.groups.items(), key=lambda x: x[1].total_minutes, reverse=True)
    if day.groups:
        md += "### Project Aggregator\n\n"
        for group_key, group in sorted_groups:
            md += f"- **{group_key}**: {group.count} events, {_format_duration(group.total_minutes, fmt)}\n"
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

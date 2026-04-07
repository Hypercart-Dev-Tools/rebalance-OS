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

from rebalance.ingest.calendar import get_daily_totals, ensure_calendar_schema
from rebalance.ingest.calendar_config import CalendarConfig, filter_events
from rebalance.ingest.db import get_connection


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


def extract_keywords(text: str, top_n: int = 5) -> list[str]:
    """Extract top N most common words from event name."""
    # Remove common words and split
    words = re.findall(r'\b[a-z]+\b', text.lower())
    # Filter out very short words
    words = [w for w in words if len(w) > 2]
    
    counter = Counter(words)
    return [word for word, _ in counter.most_common(top_n)]


def group_similar_events(
    events: list[dict[str, Any]],
) -> dict[str, ProjectGroup]:
    """Group events by most common keywords (case-insensitive substring matching)."""
    groups: dict[str, ProjectGroup] = {}
    
    for event in events:
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
        
        # Extract top keywords
        keywords = extract_keywords(summary)
        
        # Group by first keyword (or use full summary if no keywords)
        group_key = keywords[0] if keywords else summary[:20]
        
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


def _format_duration(minutes: int) -> str:
    """Format minutes into human-readable duration string."""
    hours = int(minutes / 60)
    mins = minutes % 60
    if hours > 0:
        return f"{hours}h {mins}m" if mins > 0 else f"{hours}h"
    return f"{mins}m"


def get_day_data(
    database_path: Path,
    target_date: date,
    config: CalendarConfig,
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

    total_minutes = sum(
        int((datetime.fromisoformat(e["end_time"].replace('Z', '+00:00')) -
             datetime.fromisoformat(e["start_time"].replace('Z', '+00:00'))
            ).total_seconds() / 60)
        for e in filtered_events
        if e.get("end_time")
    )

    groups = group_similar_events(filtered_events)

    return DayData(
        target_date=target_date,
        filtered_events=filtered_events,
        total_minutes=total_minutes,
        groups=groups,
    )


def format_daily_markdown(day: DayData, config: CalendarConfig) -> str:
    """Render a DayData into markdown. Pure formatting — no DB access."""
    day_name = day.target_date.strftime("%A")
    md = f"## {day_name}, {day.target_date.strftime('%B %d, %Y')}\n\n"

    md += f"**Total:** {len(day.filtered_events)} events, {_format_duration(day.total_minutes)}\n\n"

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
            md += f"- **{group_key.title()}**: {group.count} events, {_format_duration(group.total_minutes)}\n"
        md += "\n"

    return md


def generate_daily_report(
    database_path: Path,
    target_date: date,
    config: CalendarConfig,
) -> str:
    """Generate markdown report for a single day (convenience wrapper)."""
    day = get_day_data(database_path, target_date, config)
    return format_daily_markdown(day, config)

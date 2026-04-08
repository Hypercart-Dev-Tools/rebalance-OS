"""
Weekly calendar report generator — combines daily reports into Sun-Sat markdown format.

Collects structured data from each day, renders daily sections, then builds a
proper weekly summary with totals and a cross-week project aggregator.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from rebalance.ingest.daily_report import (
    DayData,
    _format_duration,
    format_daily_markdown,
    get_day_data,
    group_similar_events,
)
from rebalance.ingest.calendar_config import CalendarConfig
from rebalance.ingest.project_classifier import load_project_matchers


def get_week_start(target_date: date) -> date:
    """Get Sunday of the week containing target_date."""
    days_since_sunday = (target_date.weekday() + 1) % 7
    return target_date - timedelta(days=days_since_sunday)


def generate_weekly_report(
    database_path: Path,
    target_date: date | None = None,
    config: CalendarConfig | None = None,
) -> str:
    """Generate markdown weekly report (Sun-Sat) with full summary."""
    if target_date is None:
        target_date = date.today()
    if config is None:
        config = CalendarConfig.load()

    week_start = get_week_start(target_date)
    week_end = week_start + timedelta(days=6)
    project_matchers = load_project_matchers(database_path, config=config)

    # ── Collect structured data for every day ──
    days: list[DayData] = []
    for offset in range(7):
        day_date = week_start + timedelta(days=offset)
        days.append(get_day_data(database_path, day_date, config, project_matchers=project_matchers))

    # ── Header ──
    md = f"# Weekly Calendar Report\n\n"
    md += (
        f"**Week of {week_start.strftime('%B %d')} – "
        f"{week_end.strftime('%B %d, %Y')}**  \n"
        f"Timezone: {config.timezone}\n\n"
    )

    # ── Daily sections ──
    for day in days:
        md += format_daily_markdown(day, config)
        md += "---\n\n"

    # ── Weekly Summary ──
    total_events = sum(len(d.filtered_events) for d in days)
    total_minutes = sum(d.total_minutes for d in days)
    working_days = [d for d in days if len(d.filtered_events) > 0]
    num_working_days = len(working_days)

    md += "## Weekly Summary\n\n"

    # Per-day table
    fmt = config.hours_format
    md += "| Day | Events | Hours |\n"
    md += "|-----|-------:|------:|\n"
    for day in days:
        day_label = day.target_date.strftime("%a %m/%d")
        evt_count = len(day.filtered_events)
        hours_str = _format_duration(day.total_minutes, fmt)
        md += f"| {day_label} | {evt_count} | {hours_str} |\n"
    md += f"| **Total** | **{total_events}** | **{_format_duration(total_minutes, fmt)}** |\n\n"

    if num_working_days > 0:
        avg_events = total_events / num_working_days
        avg_minutes = total_minutes / num_working_days
        md += (
            f"Working days: {num_working_days}  \n"
            f"Avg events/day: {avg_events:.1f}  \n"
            f"Avg hours/day: {_format_duration(int(avg_minutes), fmt)}\n\n"
        )

    # ── Weekly Project Aggregator ──
    # Pool all filtered events across the week, then re-group
    all_events: list[dict] = []
    for day in days:
        all_events.extend(day.filtered_events)

    if all_events:
        weekly_groups = group_similar_events(
            all_events,
            aggregator_skip_words=config.aggregator_skip_words,
        )
        sorted_groups = sorted(
            weekly_groups.items(),
            key=lambda x: x[1].total_minutes,
            reverse=True,
        )

        md += "## Weekly Project Aggregator\n\n"
        md += "| Project | Events | Hours |\n"
        md += "|---------|-------:|------:|\n"
        for group_key, group in sorted_groups:
            md += (
                f"| {group_key} | {group.count} | "
                f"{_format_duration(group.total_minutes, fmt)} |\n"
            )
        md += "\n"

    return md

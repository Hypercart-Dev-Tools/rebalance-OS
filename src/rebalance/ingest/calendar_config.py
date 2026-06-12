"""
Calendar configuration — per-user settings for event filtering, calendar selection, and timezone.

Config file: temp/calendar_config.json (gitignored, repo root)
Schema:
  {
    "calendar_id": "primary",
    "team_calendars": [
      {"person": "matthew", "calendar_id": "matthew@group.calendar.google.com"}
    ],
    "exclude_titles": ["Check Slack", "Post Daily Timesheet"],
    "aggregator_skip_words": ["wrap", "setup", "test"],
    "timezone": "",
    "hours_format": "decimal",
    "projects": [
      {
        "name": "CreditRegistry",
        "aliases": ["CR", "Credit Registry", "CR CC"]
      }
    ]
  }

Field notes:
  - ``calendar_id``: the operator's own Google Calendar ID. "primary" is the
    Google alias for the authenticated user's default calendar and is the
    canonical stored value. index_ops always syncs the operator's calendar
    as "primary" regardless of this field; change it only for direct CLI usage
    (``calendar-sync``) if your primary has a non-standard ID.
  - ``team_calendars``: list of teammate calendars to ingest. Each entry must
    have ``person`` (short label used in the ``person`` DB column, e.g. "matthew")
    and ``calendar_id`` (the Google Calendar ID, e.g. a group calendar address).
    Teammate rows are stored with ``calendar_id != 'primary'`` and are NEVER
    exported to the pulse repo (P2 privacy default-deny).
  - ``timezone`` accepts any IANA name (e.g. "America/Los_Angeles"). If omitted
    or left as an empty string, the device's local timezone is used (resolved
    via REBALANCE_TZ env var, then /etc/localtime, then UTC fallback).
  - ``hours_format``: "decimal" = 1.75h  |  "hm" = 1h 45m

Legacy field "exclude_keywords" is accepted for backwards compatibility and
mapped to exclude_titles.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rebalance.tz_utils import local_tz

# __file__ = src/rebalance/ingest/calendar_config.py
# .parent (ingest) .parent (rebalance) .parent (src) .parent (repo root)
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "temp" / "calendar_config.json"
REVIEW_DECISIONS_PATH = Path(__file__).parent.parent.parent.parent / "temp" / "review_decisions.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "calendar_id": "primary",
    "team_calendars": [],
    "exclude_titles": [
        "Lunch",
        "Break",
        "Admin",
    ],
    "aggregator_skip_words": [],
    "timezone": "",  # empty → resolved to device local timezone at load time
    "projects": [],
    "hours_format": "decimal",
}


@dataclass
class TeamCalendarEntry:
    """A single teammate's calendar to ingest alongside the operator's own."""
    person: str      # short label stored in the DB ``person`` column (e.g. "matthew")
    calendar_id: str # Google Calendar ID (e.g. "matthew@group.calendar.google.com")


@dataclass
class CalendarProject:
    """Canonical project label and optional calendar aliases."""
    name: str
    aliases: list[str]


@dataclass
class CalendarConfig:
    """Validated calendar configuration."""
    calendar_id: str
    exclude_titles: list[str]
    aggregator_skip_words: list[str]
    timezone: str
    projects: list[CalendarProject]
    hours_format: str  # "decimal" (default) or "hm"
    team_calendars: list[TeamCalendarEntry] = field(default_factory=list)

    @property
    def exclude_keywords(self) -> list[str]:
        """Backwards-compatible alias — returns exclude_titles."""
        return self.exclude_titles

    @staticmethod
    def _load_team_calendars(raw: Any) -> list[TeamCalendarEntry]:
        if not isinstance(raw, list):
            return []
        entries: list[TeamCalendarEntry] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            person = str(item.get("person", "")).strip()
            cal_id = str(item.get("calendar_id", "")).strip()
            if person and cal_id:
                entries.append(TeamCalendarEntry(person=person, calendar_id=cal_id))
        return entries

    @staticmethod
    def _load_projects(raw_projects: Any) -> list[CalendarProject]:
        """Normalize project definitions from config JSON."""
        if not isinstance(raw_projects, list):
            return []

        projects: list[CalendarProject] = []
        for item in raw_projects:
            if not isinstance(item, dict):
                continue

            name = str(item.get("name", "")).strip()
            if not name:
                continue

            aliases_raw = item.get("aliases", [])
            aliases = [
                str(alias).strip()
                for alias in aliases_raw
                if str(alias).strip()
            ] if isinstance(aliases_raw, list) else []

            projects.append(CalendarProject(name=name, aliases=aliases))

        return projects

    @classmethod
    def load(cls, config_path: Path | None = None) -> CalendarConfig:
        """Load config from file, or return defaults if file doesn't exist.

        Backwards compatibility: if the file uses ``exclude_keywords`` (legacy)
        instead of ``exclude_titles``, the value is migrated automatically.
        """
        path = config_path or DEFAULT_CONFIG_PATH

        if path.exists():
            with open(path, "r") as f:
                data = json.load(f)
        else:
            data = dict(DEFAULT_CONFIG)

        hours_fmt = data.get("hours_format", DEFAULT_CONFIG["hours_format"])
        if hours_fmt not in ("decimal", "hm"):
            hours_fmt = "decimal"

        # Legacy migration: exclude_keywords → exclude_titles
        if "exclude_titles" in data:
            exclude_titles = data["exclude_titles"]
        elif "exclude_keywords" in data:
            exclude_titles = data["exclude_keywords"]
        else:
            exclude_titles = DEFAULT_CONFIG["exclude_titles"]

        aggregator_skip_words = data.get(
            "aggregator_skip_words",
            DEFAULT_CONFIG["aggregator_skip_words"],
        )

        return cls(
            calendar_id=data.get("calendar_id", DEFAULT_CONFIG["calendar_id"]),
            team_calendars=cls._load_team_calendars(data.get("team_calendars", [])),
            exclude_titles=exclude_titles,
            aggregator_skip_words=aggregator_skip_words,
            timezone=data.get("timezone") or local_tz().key,
            projects=cls._load_projects(data.get("projects", DEFAULT_CONFIG["projects"])),
            hours_format=hours_fmt,
        )

    def save(self, config_path: Path | None = None) -> None:
        """Save config to file."""
        path = config_path or DEFAULT_CONFIG_PATH
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            json.dump(
                {
                    "calendar_id": self.calendar_id,
                    "team_calendars": [
                        {"person": tc.person, "calendar_id": tc.calendar_id}
                        for tc in self.team_calendars
                    ],
                    "exclude_titles": self.exclude_titles,
                    "aggregator_skip_words": self.aggregator_skip_words,
                    "timezone": self.timezone,
                    "hours_format": self.hours_format,
                    "projects": [
                        {
                            "name": project.name,
                            "aliases": project.aliases,
                        }
                        for project in self.projects
                    ],
                },
                f,
                indent=2,
            )

        print(f"✓ Config saved to {path}")


def should_exclude_event(event_summary: str, exclude_titles: list[str]) -> bool:
    """Check if event summary matches any exclude title (case-insensitive).

    Uses case-insensitive full-title matching, not substring matching, so
    "wrap" in exclude_titles won't catch "Wrap up Countdown Timer".
    """
    summary_lower = event_summary.strip().lower()
    for title in exclude_titles:
        if title.strip().lower() == summary_lower:
            return True
    return False


def filter_events(
    events: list[dict[str, Any]],
    exclude_titles: list[str],
) -> list[dict[str, Any]]:
    """Filter out events whose title exactly matches an exclude entry."""
    return [
        event for event in events
        if not should_exclude_event(event.get("summary", ""), exclude_titles)
    ]


# ── Review decisions persistence ─────────────────────────────────────────────

VALID_DECISION_PREFIXES = ("include", "exclude", "project:")


class InvalidDecisionError(ValueError):
    """Raised when a review decision string doesn't match an accepted format."""


def load_review_decisions(path: Path | None = None) -> dict[str, str]:
    """Load prior review decisions from temp/review_decisions.json.

    Returns {normalized_summary: decision} where decision is one of:
    "include", "exclude", or "project:<name>".
    """
    p = path or REVIEW_DECISIONS_PATH
    if not p.exists():
        return {}
    with open(p, "r") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def save_review_decision(summary: str, decision: str, path: Path | None = None) -> None:
    """Validate and persist a review decision.

    Raises :class:`InvalidDecisionError` if *decision* is not one of
    ``"include"``, ``"exclude"``, or ``"project:<Name>"``.
    """
    if not any(decision.startswith(p) for p in VALID_DECISION_PREFIXES):
        raise InvalidDecisionError(
            f"Invalid decision '{decision}'. Must be 'include', 'exclude', or 'project:<Name>'."
        )
    p = path or REVIEW_DECISIONS_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    decisions = load_review_decisions(p)
    decisions[summary.strip().lower()] = decision
    with open(p, "w") as f:
        json.dump(decisions, f, indent=2)

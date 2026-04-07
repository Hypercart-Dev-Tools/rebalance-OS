"""
Calendar configuration — per-user settings for event filtering, calendar selection, and timezone.

Config file: temp/calendar_config.json (gitignored, repo root)
Schema:
  {
    "calendar_id": "primary",
    "exclude_keywords": ["Lunch", "Break", "Admin"],
    "timezone": "America/New_York",
    "projects": [
      {
        "name": "CreditRegistry",
        "aliases": ["CR", "Credit Registry", "CR CC"]
      }
    ]
  }
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# __file__ = src/rebalance/ingest/calendar_config.py
# .parent (ingest) .parent (rebalance) .parent (src) .parent (repo root)
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "temp" / "calendar_config.json"

DEFAULT_CONFIG = {
    "calendar_id": "primary",
    "exclude_keywords": [
        "Lunch",
        "Break",
        "Admin",
    ],
    "timezone": "America/New_York",
    "projects": [],
}


@dataclass
class CalendarProject:
    """Canonical project label and optional calendar aliases."""
    name: str
    aliases: list[str]


@dataclass
class CalendarConfig:
    """Validated calendar configuration."""
    calendar_id: str
    exclude_keywords: list[str]
    timezone: str
    projects: list[CalendarProject]

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
        """Load config from file, or return defaults if file doesn't exist."""
        path = config_path or DEFAULT_CONFIG_PATH
        
        if path.exists():
            with open(path, "r") as f:
                data = json.load(f)
        else:
            data = DEFAULT_CONFIG
        
        return cls(
            calendar_id=data.get("calendar_id", DEFAULT_CONFIG["calendar_id"]),
            exclude_keywords=data.get("exclude_keywords", DEFAULT_CONFIG["exclude_keywords"]),
            timezone=data.get("timezone", DEFAULT_CONFIG["timezone"]),
            projects=cls._load_projects(data.get("projects", DEFAULT_CONFIG["projects"])),
        )
    
    def save(self, config_path: Path | None = None) -> None:
        """Save config to file."""
        path = config_path or DEFAULT_CONFIG_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w") as f:
            json.dump(
                {
                    "calendar_id": self.calendar_id,
                    "exclude_keywords": self.exclude_keywords,
                    "timezone": self.timezone,
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


def should_exclude_event(event_summary: str, exclude_keywords: list[str]) -> bool:
    """Check if event summary contains any exclude keywords (case-insensitive)."""
    summary_lower = event_summary.lower()
    for keyword in exclude_keywords:
        if keyword.lower() in summary_lower:
            return True
    return False


def filter_events(
    events: list[dict[str, Any]],
    exclude_keywords: list[str],
) -> list[dict[str, Any]]:
    """Filter out events with excluded keywords."""
    return [
        event for event in events
        if not should_exclude_event(event.get("summary", ""), exclude_keywords)
    ]

"""Shared utilities for git-pulse personal and team pipelines."""

from __future__ import annotations

import calendar
import re
import shlex
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, TypeVar


CONV_PREFIX_RE = re.compile(
    r"^(feat|fix|chore|docs|refactor|test|style|perf|build|ci|revert)(?:\([^)]*\))?!?:\s*",
    re.IGNORECASE,
)


GROUP_ORDER = [
    "feat",
    "fix",
    "refactor",
    "perf",
    "docs",
    "test",
    "chore",
    "build",
    "ci",
    "style",
    "revert",
    "other",
]


class HasLocalDay(Protocol):
    local_day: str


RowT = TypeVar("RowT", bound=HasLocalDay)


def current_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def markdown_cell(value: str) -> str:
    return value.replace("|", "\\|")


def classify_subject(subject: str) -> str:
    match = CONV_PREFIX_RE.match(subject)
    return match.group(1).lower() if match else "other"


def load_sync_repo_dir(config_file: Path, config_dir: Path) -> Path | None:
    if not config_file.is_file():
        return None

    shell_script = (
        "set -euo pipefail\n"
        f"CONFIG_DIR={shlex.quote(str(config_dir))}\n"
        f"source {shlex.quote(str(config_file))}\n"
        'printf "%s" "${sync_repo_dir:-$CONFIG_DIR/repo}"\n'
    )
    result = subprocess.run(
        ["/bin/bash", "-lc", shell_script],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip())


def split_rows_by_month(
    rows: list[RowT],
) -> list[tuple[int, int, list[RowT]]]:
    buckets: dict[tuple[int, int], list[RowT]] = defaultdict(list)
    for row in rows:
        parts = row.local_day.split("-")
        if len(parts) != 3:
            continue
        try:
            year = int(parts[0])
            month = int(parts[1])
        except ValueError:
            continue
        buckets[(year, month)].append(row)
    return [(y, m, buckets[(y, m)]) for (y, m) in sorted(buckets)]


def month_auto_filename(
    year: int, month: int, month_rows: list[HasLocalDay]
) -> str:
    days = sorted(
        {
            int(row.local_day[8:10])
            for row in month_rows
            if len(row.local_day) >= 10
        }
    )
    month_end_day = calendar.monthrange(year, month)[1]
    is_full_month = bool(days) and days[0] == 1 and days[-1] == month_end_day
    if is_full_month:
        abbr = calendar.month_abbr[month].upper()
        return f"{year:04d}-{month:02d}-{abbr}.md"
    last_covered_day = days[-1] if days else 1
    return f"{year:04d}-{month:02d}-{last_covered_day:02d}-PARTIAL.md"

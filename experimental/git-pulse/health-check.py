#!/usr/bin/env python3
"""Check git-pulse collector health across machines.

Reads the sync repo's git log for each `pulse-<device_id>.md` file and
computes time-since-last-push per machine. Flags machines whose collectors
haven't fired recently. Exit codes:

  0  — all machines within the warn window
  1  — one or more STALE (between warn and alert)
  2  — one or more ALERT (past alert window) or NO PUSHES at all
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pulse_common import load_sync_repo_dir


@dataclass
class DeviceStatus:
    device_id: str
    device_name: str
    pulse_file: str
    pulse_path: Path
    last_scan_utc: datetime | None
    last_pulse_push_utc: datetime | None
    latest_activity_utc: datetime | None
    pulse_exists: bool
    metadata_exists: bool
    notes: list[str] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check git-pulse collector health across machines."
    )
    parser.add_argument(
        "--warn-hours",
        type=float,
        default=3.0,
        help="Warn if last push older than N hours (default: 3).",
    )
    parser.add_argument(
        "--alert-hours",
        type=float,
        default=24.0,
        help="Alert if last push older than N hours (default: 24).",
    )
    parser.add_argument(
        "--sync-repo-dir",
        metavar="PATH",
        default=None,
        help="Override sync repo directory. Defaults to sync_repo_dir from git-pulse config.",
    )
    return parser.parse_args()


def yaml_value(path: Path, key: str) -> str:
    prefix = f"{key}: "
    for raw_line in path.read_text().splitlines():
        if not raw_line.startswith(prefix):
            continue
        value = raw_line[len(prefix):].strip()
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        return value.replace('\\"', '"').replace("\\\\", "\\")
    return ""


def parse_utc(value: str) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(normalized).astimezone(timezone.utc)
    except ValueError:
        return None


def git_last_commit_utc(repo_dir: Path, path_in_repo: str) -> datetime | None:
    result = subprocess.run(
        ["git", "-C", str(repo_dir), "log", "-1", "--format=%cI", "--", path_in_repo],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    stamp = result.stdout.strip()
    if not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp).astimezone(timezone.utc)
    except ValueError:
        return None


def pulse_latest_activity_utc(path: Path) -> datetime | None:
    if not path.is_file():
        return None

    latest: datetime | None = None
    for raw_line in path.read_text().splitlines():
        parts = raw_line.split("\t")
        if len(parts) != 6 or not parts[0].isdigit():
            continue
        parsed = parse_utc(parts[1])
        if parsed is not None:
            latest = parsed
    return latest


def display_age_hours(moment: datetime, now: datetime) -> str:
    hours = max((now - moment).total_seconds() / 3600, 0.0)
    if hours >= 24:
        return f"{hours / 24:.1f}d"
    return f"{hours:.1f}h"


def classify(
    last_scan: datetime | None,
    now: datetime,
    warn_hours: float,
    alert_hours: float,
) -> tuple[int, str]:
    """Return (priority, label). Lower priority sorts first (worst first)."""
    if last_scan is None:
        return 0, "NO PUSHES"
    hours = (now - last_scan).total_seconds() / 3600
    if hours > alert_hours:
        return 1, f"ALERT ({hours:.0f}h)"
    if hours > warn_hours:
        return 2, f"STALE ({hours:.1f}h)"
    return 3, f"ALIVE ({hours:.1f}h)"


def collect_statuses(sync_repo_dir: Path, now: datetime) -> list[DeviceStatus]:
    statuses: list[DeviceStatus] = []
    devices_dir = sync_repo_dir / "devices"

    metadata_pulse_files: set[str] = set()
    if devices_dir.is_dir():
        for yaml_path in sorted(devices_dir.glob("*.yaml")):
            device_id = yaml_value(yaml_path, "device_id")
            if not device_id:
                continue
            device_name = yaml_value(yaml_path, "device_name") or device_id
            pulse_file = (
                yaml_value(yaml_path, "pulse_file") or f"pulse-{device_id}.md"
            )
            pulse_path = sync_repo_dir / pulse_file
            metadata_pulse_files.add(pulse_file)
            last_scan_utc = parse_utc(yaml_value(yaml_path, "last_scan_utc"))
            statuses.append(
                DeviceStatus(
                    device_id=device_id,
                    device_name=device_name,
                    pulse_file=pulse_file,
                    pulse_path=pulse_path,
                    last_scan_utc=last_scan_utc,
                    last_pulse_push_utc=git_last_commit_utc(sync_repo_dir, pulse_file),
                    latest_activity_utc=pulse_latest_activity_utc(pulse_path),
                    pulse_exists=pulse_path.is_file(),
                    metadata_exists=True,
                )
            )

    # Orphan pulse files (on disk / in git but no matching YAML)
    for pulse_path in sorted(sync_repo_dir.glob("pulse-*.md")):
        if pulse_path.name in metadata_pulse_files:
            continue
        device_id = pulse_path.stem.removeprefix("pulse-")
        statuses.append(
            DeviceStatus(
                device_id=device_id,
                device_name=device_id,
                pulse_file=pulse_path.name,
                pulse_path=pulse_path,
                last_scan_utc=git_last_commit_utc(sync_repo_dir, pulse_path.name),
                last_pulse_push_utc=git_last_commit_utc(sync_repo_dir, pulse_path.name),
                latest_activity_utc=pulse_latest_activity_utc(pulse_path),
                pulse_exists=True,
                metadata_exists=False,
            )
        )

    for s in statuses:
        if not s.metadata_exists:
            s.notes.append("no metadata YAML")
        if not s.pulse_exists:
            s.notes.append(f"{s.pulse_file} missing on disk")
            continue
        if s.last_scan_utc is None:
            s.last_scan_utc = s.last_pulse_push_utc
            s.notes.append("heartbeat unavailable; using pulse-file pushes")
        if s.last_pulse_push_utc and s.last_scan_utc and s.last_scan_utc > s.last_pulse_push_utc:
            s.notes.append(
                f"last pulse update {display_age_hours(s.last_pulse_push_utc, now)} ago"
            )
        if s.latest_activity_utc:
            s.notes.append(
                f"last local commit {display_age_hours(s.latest_activity_utc, now)} ago"
            )

    return statuses


def render(
    statuses: list[DeviceStatus],
    now: datetime,
    warn_hours: float,
    alert_hours: float,
    sync_repo_dir: Path,
) -> tuple[str, int]:
    if not statuses:
        return (f"no devices found under {sync_repo_dir}\n", 2)

    scored = [(classify(s.last_scan_utc, now, warn_hours, alert_hours), s) for s in statuses]
    scored.sort(key=lambda pair: (pair[0][0], pair[1].device_name.lower()))

    worst_priority = min(priority for (priority, _label), _s in scored)
    exit_code = 2 if worst_priority <= 1 else (1 if worst_priority == 2 else 0)

    lines = [
        f"Git Pulse health check — sync_repo_dir: {sync_repo_dir}",
        f"Now: {now.strftime('%Y-%m-%dT%H:%M:%SZ')} · warn > {warn_hours}h · alert > {alert_hours}h",
        "",
        f"{'Device':<36}  {'Status':<18}  {'Last scan (UTC)':<22}  Notes",
        f"{'-'*36}  {'-'*18}  {'-'*22}  {'-'*30}",
    ]
    for (_, label), s in scored:
        last = (
            s.last_scan_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
            if s.last_scan_utc
            else "(never)"
        )
        note = "; ".join(s.notes) if s.notes else ""
        name = s.device_name if len(s.device_name) <= 36 else s.device_name[:33] + "..."
        lines.append(f"{name:<36}  {label:<18}  {last:<22}  {note}")
    lines.append("")
    return ("\n".join(lines), exit_code)


def main() -> int:
    args = parse_args()

    if args.sync_repo_dir:
        sync_repo_dir = Path(args.sync_repo_dir).expanduser()
    else:
        config_dir = Path(
            os.environ.get("GIT_PULSE_CONFIG_DIR")
            or os.environ.get("GIT_HISTORY_CONFIG_DIR")
            or Path.home() / ".config" / "git-pulse"
        )
        resolved = load_sync_repo_dir(config_dir / "config.sh", config_dir)
        if resolved is None:
            print(
                "No --sync-repo-dir and no git-pulse config at "
                f"{config_dir / 'config.sh'}",
                file=sys.stderr,
            )
            return 2
        sync_repo_dir = resolved

    if not (sync_repo_dir / ".git").is_dir():
        print(f"Not a git repo: {sync_repo_dir}", file=sys.stderr)
        return 2

    now = datetime.now(timezone.utc)
    statuses = collect_statuses(sync_repo_dir, now)
    output, exit_code = render(
        statuses, now, args.warn_hours, args.alert_hours, sync_repo_dir
    )
    sys.stdout.write(output)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

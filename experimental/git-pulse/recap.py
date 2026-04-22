#!/usr/bin/env python3
"""Synthesize git-pulse TSV reports into an agent-fillable executive recap."""

from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


HEADER = [
    "local_day",
    "local_time",
    "utc_time",
    "device_id",
    "device_name",
    "repo",
    "branch",
    "short_sha",
    "subject",
]


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


SKILL_PATH = Path(__file__).resolve().parent / "EXEC-SUMMARY.md"


AGENT_INSTRUCTIONS = f"""\
<!--
AGENT INSTRUCTIONS — remove this entire block after editing.

Before filling the TLDR / FOCUS / OBSERVATIONS placeholders below, read the
authoritative rulebook (applies to any agent — Claude Code, Codex, Copilot,
Gemini, etc.):

  Absolute:       {SKILL_PATH}
  Repo-relative:  experimental/git-pulse/EXEC-SUMMARY.md  (from rebalance-OS root)
  Claude Code:    registered skill `git-pulse-exec-recap` (see .claude/skills/)

Three placeholder types to replace (including the HTML comment delimiters):

  <!-- TLDR: ... -->          1-2 sentences at the top.
  <!-- FOCUS: ... -->         2-3 sentences per repo.
  <!-- OBSERVATIONS: ... -->  3-5 bullets.

Do not modify the Appendix section. Strip this AGENT INSTRUCTIONS block once
the three placeholder types have been filled in.
-->"""


@dataclass(frozen=True)
class PulseRow:
    local_day: str
    local_time: str
    utc_time: str
    device_id: str
    device_name: str
    repo: str
    branch: str
    short_sha: str
    subject: str

    @property
    def dedupe_key(self) -> tuple[str, str, str, str, str, str]:
        return (
            self.device_id,
            self.utc_time,
            self.repo,
            self.branch,
            self.short_sha,
            self.subject,
        )


@dataclass(frozen=True)
class DeviceMetadata:
    device_id: str
    device_name: str
    pulse_file: str
    pulse_path: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Combine one or more raw git-pulse TSV reports into an agent-fillable "
            "executive-style Markdown recap."
        )
    )
    parser.add_argument(
        "--input",
        action="append",
        default=[],
        metavar="PATH",
        help="Raw git-pulse TSV report to include. Repeat to combine multiple reports.",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        help="Optional output path for the rendered Markdown recap.",
    )
    parser.add_argument(
        "--recent-limit",
        type=int,
        default=15,
        help="Rows to show in the Appendix Recent Activity table. Default: 15.",
    )
    parser.add_argument(
        "--per-group-limit",
        type=int,
        default=5,
        help="Max commits shown per theme (feat/fix/etc.) per repo. 0 disables the cap. Default: 5.",
    )
    parser.add_argument(
        "--no-agent-instructions",
        action="store_true",
        help="Omit the top-of-file agent instructions block.",
    )
    return parser.parse_args()


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
        'set -euo pipefail\n'
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


def discover_input_files(input_args: list[str], sync_repo_dir: Path | None) -> list[Path]:
    if input_args:
        return [Path(value).expanduser() for value in input_args]

    if sync_repo_dir is None:
        raise SystemExit("No --input files were provided and ~/.config/git-pulse/config.sh was not found.")

    reports_dir = sync_repo_dir / "reports"
    files = sorted(path for path in reports_dir.glob("*.tsv") if path.is_file())
    if not files:
        raise SystemExit(f"No TSV reports found under {reports_dir}")
    return files


def parse_report(path: Path) -> tuple[list[PulseRow], int]:
    rows: list[PulseRow] = []
    malformed = 0

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip("\n")
        if not line:
            continue
        if line == "\t".join(HEADER):
            continue

        parts = line.split("\t")
        if len(parts) != len(HEADER):
            malformed += 1
            continue

        rows.append(PulseRow(*parts))

    return rows, malformed


def dedupe_rows(rows: list[PulseRow]) -> tuple[list[PulseRow], int]:
    ordered: list[PulseRow] = []
    seen: set[tuple[str, str, str, str, str, str]] = set()
    duplicates = 0

    for row in rows:
        if row.dedupe_key in seen:
            duplicates += 1
            continue
        seen.add(row.dedupe_key)
        ordered.append(row)

    ordered.sort(
        key=lambda row: (
            row.utc_time,
            row.local_day,
            row.local_time,
            row.device_id,
            row.repo,
            row.short_sha,
        )
    )
    return ordered, duplicates


def yaml_value(path: Path, key: str) -> str:
    prefix = f"{key}: "
    for raw_line in path.read_text().splitlines():
        if not raw_line.startswith(prefix):
            continue
        value = raw_line[len(prefix) :].strip()
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        return value.replace('\\"', '"').replace("\\\\", "\\")
    return ""


def load_metadata(sync_repo_dir: Path | None) -> list[DeviceMetadata]:
    if sync_repo_dir is None:
        return []

    devices_dir = sync_repo_dir / "devices"
    if not devices_dir.is_dir():
        return []

    metadata: list[DeviceMetadata] = []
    for path in sorted(devices_dir.glob("*.yaml")):
        device_id = yaml_value(path, "device_id")
        if not device_id:
            continue
        device_name = yaml_value(path, "device_name") or device_id
        pulse_file = yaml_value(path, "pulse_file") or f"pulse-{device_id}.md"
        metadata.append(
            DeviceMetadata(
                device_id=device_id,
                device_name=device_name,
                pulse_file=pulse_file,
                pulse_path=sync_repo_dir / pulse_file,
            )
        )
    return metadata


def build_repo_section(
    repo_name: str,
    entries: list[PulseRow],
    *,
    per_group_limit: int,
) -> list[str]:
    machine_counts: dict[str, int] = defaultdict(int)
    for row in entries:
        machine_counts[row.device_name] += 1
    machines_sorted = sorted(machine_counts.items(), key=lambda item: (-item[1], item[0]))
    machines_str = ", ".join(
        f"{markdown_cell(name)} ({count})" for name, count in machines_sorted
    )

    branches = sorted({row.branch for row in entries})
    branches_str = ", ".join(f"`{b}`" for b in branches)

    active_days = sorted({row.local_day for row in entries})
    first_day = active_days[0]
    last_day = active_days[-1]
    day_range = first_day if first_day == last_day else f"{first_day} to {last_day}"

    groups: dict[str, list[PulseRow]] = defaultdict(list)
    for row in entries:
        groups[classify_subject(row.subject)].append(row)
    for group_rows in groups.values():
        group_rows.sort(
            key=lambda r: (r.local_day, r.local_time, r.short_sha),
            reverse=True,
        )

    machine_count = len(machine_counts)
    machine_word = "machine" if machine_count == 1 else "machines"
    lines = [
        f"### `{repo_name}` — {len(entries)} commits · {machine_count} {machine_word} · {day_range}",
        "",
        f"- **Machines:** {machines_str}",
        f"- **Branches:** {branches_str}",
        f"- **Active days:** {len(active_days)}",
        "",
        (
            "<!-- FOCUS: Write 2-3 sentences describing this repo's work during the "
            "window. Cover themes, notable milestones, and any cross-machine "
            "coordination. Base the summary on the Commit themes below. -->"
        ),
        "",
        "**Commit themes:**",
    ]
    for key in GROUP_ORDER:
        group_rows = groups.get(key)
        if not group_rows:
            continue
        lines.append(f"- **{key} ({len(group_rows)}):**")
        displayed = (
            group_rows[:per_group_limit] if per_group_limit > 0 else group_rows
        )
        for row in displayed:
            lines.append(
                f"  - {row.local_day} · `{row.short_sha}` · {markdown_cell(row.subject)}"
            )
        remaining = len(group_rows) - len(displayed)
        if remaining > 0:
            lines.append(f"  - _…and {remaining} more_")
    lines.append("")
    return lines


def build_appendix(
    args: argparse.Namespace,
    input_files: list[Path],
    rows: list[PulseRow],
    *,
    raw_rows: int,
    duplicates: int,
    malformed: int,
    detached_count: int,
    device_rows: dict[str, list[PulseRow]],
    repo_rows: dict[str, list[PulseRow]],
    day_rows: dict[str, list[PulseRow]],
    metadata: list[DeviceMetadata],
) -> list[str]:
    lines: list[str] = ["### Source Reports"]
    for path in input_files:
        lines.append(f"- `{path}`")

    lines.extend(["", "### Coverage"])
    lines.append("| Device | Device ID | Commits | First Seen | Last Seen | Status |")
    lines.append("|---|---|---:|---|---|---|")

    metadata_by_device = {item.device_id: item for item in metadata}
    all_device_ids = set(metadata_by_device) | set(device_rows)
    for device_id in sorted(
        all_device_ids,
        key=lambda value: (
            metadata_by_device.get(
                value, DeviceMetadata(value, value, "", Path("."))
            ).device_name.lower(),
            value,
        ),
    ):
        metadata_row = metadata_by_device.get(device_id)
        recapped_rows = device_rows.get(device_id, [])
        device_name = (
            metadata_row.device_name
            if metadata_row
            else (recapped_rows[0].device_name if recapped_rows else device_id)
        )
        first_seen = (
            f"{recapped_rows[0].local_day} {recapped_rows[0].local_time}"
            if recapped_rows
            else "n/a"
        )
        last_seen = (
            f"{recapped_rows[-1].local_day} {recapped_rows[-1].local_time}"
            if recapped_rows
            else "n/a"
        )

        status_parts: list[str] = []
        if recapped_rows:
            status_parts.append("in recap")
        else:
            status_parts.append("no rows in supplied reports")
        if metadata_row is None:
            status_parts.append("no metadata file")
        elif not metadata_row.pulse_path.is_file():
            status_parts.append(f"missing `{metadata_row.pulse_file}`")

        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(device_name),
                    f"`{device_id}`",
                    str(len(recapped_rows)),
                    markdown_cell(first_seen),
                    markdown_cell(last_seen),
                    markdown_cell("; ".join(status_parts)),
                ]
            )
            + " |"
        )

    lines.extend(["", "### Machines Table"])
    lines.append(
        "| Device | Device ID | Commits | Repos | Branches | Active Days | Latest Subject |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---|")
    for device_id, entries in sorted(
        device_rows.items(),
        key=lambda item: (-len(item[1]), item[1][0].device_name.lower(), item[0]),
    ):
        latest_subject = entries[-1].subject
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(entries[0].device_name),
                    f"`{device_id}`",
                    str(len(entries)),
                    str(len({row.repo for row in entries})),
                    str(len({row.branch for row in entries})),
                    str(len({row.local_day for row in entries})),
                    markdown_cell(latest_subject),
                ]
            )
            + " |"
        )

    lines.extend(["", "### Repos Table"])
    lines.append(
        "| Repo | Commits | Machines | Branches | Latest Activity | Latest Subject |"
    )
    lines.append("|---|---:|---:|---:|---|---|")
    for repo_name, entries in sorted(
        repo_rows.items(),
        key=lambda item: (-len(item[1]), item[0].lower()),
    ):
        latest = entries[-1]
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{repo_name}`",
                    str(len(entries)),
                    str(len({row.device_id for row in entries})),
                    str(len({row.branch for row in entries})),
                    markdown_cell(f"{latest.local_day} {latest.local_time}"),
                    markdown_cell(latest.subject),
                ]
            )
            + " |"
        )

    lines.extend(["", "### Cross-Machine Repos"])
    lines.append("| Repo | Commits | Machines | Device Names | Latest Activity |")
    lines.append("|---|---:|---:|---|---|")
    cross_machine_rows = [
        (repo_name, entries)
        for repo_name, entries in repo_rows.items()
        if len({row.device_id for row in entries}) > 1
    ]
    if cross_machine_rows:
        for repo_name, entries in sorted(
            cross_machine_rows,
            key=lambda item: (-len(item[1]), item[0].lower()),
        ):
            latest = entries[-1]
            device_names = ", ".join(sorted({row.device_name for row in entries}))
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{repo_name}`",
                        str(len(entries)),
                        str(len({row.device_id for row in entries})),
                        markdown_cell(device_names),
                        markdown_cell(f"{latest.local_day} {latest.local_time}"),
                    ]
                )
                + " |"
            )
    else:
        lines.append("| none | 0 | 0 | n/a | n/a |")

    lines.extend(["", "### Daily Activity"])
    lines.append("| Local Day | Commits | Machines | Repos | Latest Activity |")
    lines.append("|---|---:|---:|---:|---|")
    for local_day, entries in sorted(
        day_rows.items(), key=lambda item: item[0], reverse=True
    ):
        latest = entries[-1]
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{local_day}`",
                    str(len(entries)),
                    str(len({row.device_id for row in entries})),
                    str(len({row.repo for row in entries})),
                    markdown_cell(
                        f"{latest.local_time} · {latest.device_name} · {latest.repo}"
                    ),
                ]
            )
            + " |"
        )

    lines.extend(["", "### Recent Activity"])
    lines.append(
        "| Local Day | Local Time | UTC Time | Device | Repo | Branch | Short SHA | Subject |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")
    for row in reversed(
        rows[-args.recent_limit :] if args.recent_limit > 0 else []
    ):
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row.local_day}`",
                    markdown_cell(row.local_time),
                    f"`{row.utc_time}`",
                    markdown_cell(row.device_name),
                    f"`{row.repo}`",
                    f"`{row.branch}`",
                    f"`{row.short_sha}`",
                    markdown_cell(row.subject),
                ]
            )
            + " |"
        )

    lines.extend(["", "### Exceptions"])
    lines.append(f"- Raw rows: {raw_rows}")
    lines.append(f"- Unique rows: {len(rows)}")
    lines.append(f"- Overlapping rows removed: {duplicates}")
    lines.append(f"- Malformed rows skipped: {malformed}")
    lines.append(f"- Detached branch commits: {detached_count}")

    coverage_only = [
        item.device_name for item in metadata if item.device_id not in device_rows
    ]
    if coverage_only:
        lines.append(
            "- Metadata devices with no rows in the supplied reports: "
            + ", ".join(f"`{name}`" for name in coverage_only)
        )

    missing_pulse = [
        item.device_name for item in metadata if not item.pulse_path.is_file()
    ]
    if missing_pulse:
        lines.append(
            "- Metadata devices whose pulse file is missing: "
            + ", ".join(f"`{name}`" for name in missing_pulse)
        )

    return lines


def build_lines(
    args: argparse.Namespace,
    input_files: list[Path],
    rows: list[PulseRow],
    *,
    raw_rows: int,
    duplicates: int,
    malformed: int,
    metadata: list[DeviceMetadata],
) -> list[str]:
    coverage_start = rows[0].local_day if rows else "n/a"
    coverage_end = rows[-1].local_day if rows else "n/a"

    device_rows: dict[str, list[PulseRow]] = defaultdict(list)
    repo_rows: dict[str, list[PulseRow]] = defaultdict(list)
    day_rows: dict[str, list[PulseRow]] = defaultdict(list)
    for row in rows:
        device_rows[row.device_id].append(row)
        repo_rows[row.repo].append(row)
        day_rows[row.local_day].append(row)

    busiest_day = max(
        day_rows.items(), key=lambda item: (len(item[1]), item[0]), default=(None, [])
    )
    most_active_device = max(
        device_rows.items(),
        key=lambda item: (len(item[1]), item[0]),
        default=(None, []),
    )
    most_active_repo = max(
        repo_rows.items(),
        key=lambda item: (len(item[1]), item[0]),
        default=(None, []),
    )
    detached_count = sum(1 for row in rows if row.branch == "(detached)")

    lines: list[str] = ["# Git Pulse Executive Recap", ""]

    if not args.no_agent_instructions:
        lines.extend([AGENT_INSTRUCTIONS, ""])

    lines.extend(
        [
            "## Summary",
            f"- Generated at: `{current_utc_iso()}`",
            f"- Window: `{coverage_start}` to `{coverage_end}` ({len(day_rows)} active days)",
            f"- Commits: {len(rows)} across {len(repo_rows)} repos from {len(device_rows)} machines",
        ]
    )
    if busiest_day[0]:
        lines.append(
            f"- Busiest day: `{busiest_day[0]}` ({len(busiest_day[1])} commits)"
        )
    if most_active_repo[0]:
        lines.append(
            f"- Most active repo: `{most_active_repo[0]}` "
            f"({len(most_active_repo[1])} commits)"
        )
    if most_active_device[0]:
        lines.append(
            f"- Most active machine: `{most_active_device[1][0].device_name}` "
            f"({len(most_active_device[1])} commits)"
        )
    lines.extend(
        [
            "",
            (
                "<!-- TLDR: Write 1-2 sentences summarizing the window at an executive "
                "level — scale of work, where it concentrated, and any standout "
                "pattern. Base on the Summary stats above and the By Repo sections "
                "below. -->"
            ),
            "",
        ]
    )

    lines.extend(["## By Repo", ""])
    if not repo_rows:
        lines.extend(["_No commits in the supplied reports._", ""])
    for repo_name, entries in sorted(
        repo_rows.items(), key=lambda item: (-len(item[1]), item[0].lower())
    ):
        lines.extend(
            build_repo_section(
                repo_name, entries, per_group_limit=args.per_group_limit
            )
        )

    lines.extend(
        [
            "## Observations",
            "",
            (
                "<!-- OBSERVATIONS: 3-5 bullets on notable patterns, gaps, or "
                "anomalies. Use the Appendix tables to spot signals like quiet days, "
                "cross-machine coordination, missing device metadata, or commits on "
                "non-default branches. -->"
            ),
            "",
        ]
    )

    lines.extend(["## Appendix", ""])
    lines.extend(
        build_appendix(
            args,
            input_files,
            rows,
            raw_rows=raw_rows,
            duplicates=duplicates,
            malformed=malformed,
            detached_count=detached_count,
            device_rows=device_rows,
            repo_rows=repo_rows,
            day_rows=day_rows,
            metadata=metadata,
        )
    )

    return lines


def main() -> int:
    args = parse_args()
    if args.recent_limit < 0:
        raise SystemExit("--recent-limit must be 0 or greater.")
    if args.per_group_limit < 0:
        raise SystemExit("--per-group-limit must be 0 or greater.")

    config_dir = Path(
        os.environ.get("GIT_PULSE_CONFIG_DIR")
        or os.environ.get("GIT_HISTORY_CONFIG_DIR")
        or Path.home() / ".config" / "git-pulse"
    )
    config_file = config_dir / "config.sh"
    sync_repo_dir = load_sync_repo_dir(config_file, config_dir)
    input_files = discover_input_files(args.input, sync_repo_dir)

    raw_rows = 0
    malformed = 0
    collected: list[PulseRow] = []
    for path in input_files:
        if not path.is_file():
            raise SystemExit(f"Input report not found: {path}")
        rows, malformed_rows = parse_report(path)
        collected.extend(rows)
        raw_rows += len(rows)
        malformed += malformed_rows

    deduped_rows, duplicates = dedupe_rows(collected)
    metadata = load_metadata(sync_repo_dir)
    lines = build_lines(
        args,
        input_files,
        deduped_rows,
        raw_rows=raw_rows,
        duplicates=duplicates,
        malformed=malformed,
        metadata=metadata,
    )
    rendered = "\n".join(lines) + "\n"

    if args.output:
        output_path = Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered)

    sys.stdout.write(rendered)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

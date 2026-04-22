#!/usr/bin/env python3
"""Synthesize team-pulse TSVs into an agent-fillable executive recap per month."""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from pulse_common import (
    GROUP_ORDER,
    classify_subject,
    current_utc_iso,
    load_sync_repo_dir,
    markdown_cell,
    month_auto_filename,
    split_rows_by_month,
)


HEADER = [
    "local_day",
    "local_time",
    "utc_time",
    "author_login",
    "author_name",
    "repo",
    "branch",
    "short_sha",
    "subject",
    "kind",
    "pr_number",
]


SKILL_PATH = Path(__file__).resolve().parent / "TEAM-EXEC-SUMMARY.md"


AGENT_INSTRUCTIONS = f"""\
<!--
AGENT INSTRUCTIONS — remove this entire block after editing.

Before filling the TLDR / FOCUS / OBSERVATIONS placeholders below, read the
authoritative rulebook (applies to any agent — Claude Code, Codex, Copilot,
Gemini, etc.):

  Absolute:       {SKILL_PATH}
  Repo-relative:  experimental/git-pulse/TEAM-EXEC-SUMMARY.md  (from rebalance-OS root)
  Claude Code:    registered skill `git-pulse-team-recap` (see .claude/skills/)

Three placeholder types to replace (including the HTML comment delimiters):

  <!-- TLDR: ... -->          1-2 sentences at the top.
  <!-- FOCUS: ... -->         2-3 sentences per contributor.
  <!-- OBSERVATIONS: ... -->  3-5 bullets.

Do not modify the Appendix section. Strip this AGENT INSTRUCTIONS block once
the three placeholder types have been filled in.
-->"""


@dataclass(frozen=True)
class TeamRow:
    local_day: str
    local_time: str
    utc_time: str
    author_login: str
    author_name: str
    repo: str
    branch: str
    short_sha: str
    subject: str
    kind: str
    pr_number: str

    @property
    def dedupe_key(self) -> tuple[str, ...]:
        return (
            self.author_login,
            self.utc_time,
            self.repo,
            self.kind,
            self.short_sha,
            self.pr_number,
            self.subject,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Combine one or more team-pulse TSV reports into agent-fillable "
            "executive-style Markdown recaps, split per month."
        )
    )
    parser.add_argument(
        "--input",
        action="append",
        default=[],
        metavar="PATH",
        help="Team-pulse TSV to include. Repeat to combine multiple.",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        help="Write a single combined recap to PATH (skips month splitting).",
    )
    parser.add_argument(
        "--recent-limit",
        type=int,
        default=15,
        help="Rows in the Appendix Recent Activity table. Default: 15.",
    )
    parser.add_argument(
        "--per-group-limit",
        type=int,
        default=5,
        help=(
            "Max items shown per theme/PR list per repo block. "
            "0 disables the cap. Default: 5."
        ),
    )
    parser.add_argument(
        "--no-agent-instructions",
        action="store_true",
        help="Omit the top-of-file agent instructions block.",
    )
    return parser.parse_args()


def discover_input_files(
    input_args: list[str], sync_repo_dir: Path | None
) -> list[Path]:
    if input_args:
        return [Path(value).expanduser() for value in input_args]

    if sync_repo_dir is None:
        raise SystemExit(
            "No --input files were provided and ~/.config/git-pulse/config.sh was not found."
        )

    pulses_dir = sync_repo_dir / "team-pulses"
    files = sorted(path for path in pulses_dir.glob("*.tsv") if path.is_file())
    if not files:
        raise SystemExit(f"No team-pulse TSVs found under {pulses_dir}")
    return files


def parse_report(path: Path) -> tuple[list[TeamRow], int]:
    rows: list[TeamRow] = []
    malformed = 0
    for raw_line in path.read_text().splitlines():
        line = raw_line.rstrip("\n")
        if not line:
            continue
        if line == "\t".join(HEADER):
            continue
        parts = line.split("\t")
        if len(parts) != len(HEADER):
            malformed += 1
            continue
        rows.append(TeamRow(*parts))
    return rows, malformed


def dedupe_rows(rows: list[TeamRow]) -> tuple[list[TeamRow], int]:
    seen: set[tuple[str, ...]] = set()
    ordered: list[TeamRow] = []
    duplicates = 0
    for row in rows:
        if row.dedupe_key in seen:
            duplicates += 1
            continue
        seen.add(row.dedupe_key)
        ordered.append(row)
    ordered.sort(
        key=lambda r: (
            r.utc_time,
            r.author_login,
            r.repo,
            r.kind,
            r.short_sha,
            r.pr_number,
        )
    )
    return ordered, duplicates


def _render_commits_by_theme(
    commits: list[TeamRow], per_group_limit: int
) -> list[str]:
    groups: dict[str, list[TeamRow]] = defaultdict(list)
    for c in commits:
        groups[classify_subject(c.subject)].append(c)
    for group_rows in groups.values():
        group_rows.sort(
            key=lambda r: (r.local_day, r.local_time, r.short_sha),
            reverse=True,
        )
    lines: list[str] = []
    for key in GROUP_ORDER:
        group_rows = groups.get(key)
        if not group_rows:
            continue
        lines.append(f"  - **{key} ({len(group_rows)}):**")
        displayed = (
            group_rows[:per_group_limit]
            if per_group_limit > 0
            else group_rows
        )
        for row in displayed:
            lines.append(
                f"    - {row.local_day} · `{row.short_sha}` · {markdown_cell(row.subject)}"
            )
        remaining = len(group_rows) - len(displayed)
        if remaining > 0:
            lines.append(f"    - _…and {remaining} more_")
    return lines


def _render_prs(prs: list[TeamRow], per_group_limit: int) -> list[str]:
    prs_sorted = sorted(
        prs,
        key=lambda r: (r.local_day, r.local_time, r.pr_number),
        reverse=True,
    )
    lines: list[str] = [f"  - **PRs ({len(prs_sorted)}):**"]
    displayed = (
        prs_sorted[:per_group_limit] if per_group_limit > 0 else prs_sorted
    )
    for row in displayed:
        number = f"#{row.pr_number}" if row.pr_number else "#?"
        lines.append(
            f"    - {row.local_day} · {number} · {markdown_cell(row.subject)}"
        )
    remaining = len(prs_sorted) - len(displayed)
    if remaining > 0:
        lines.append(f"    - _…and {remaining} more_")
    return lines


def build_contributor_section(
    login: str,
    entries: list[TeamRow],
    *,
    per_group_limit: int,
) -> list[str]:
    names = sorted(
        {row.author_name for row in entries if row.author_name and row.author_name != login}
    )
    display_name = names[0] if names else ""

    commits = [r for r in entries if r.kind == "commit"]
    prs = [r for r in entries if r.kind == "pr"]

    repo_buckets: dict[str, list[TeamRow]] = defaultdict(list)
    for row in entries:
        repo_buckets[row.repo].append(row)

    days = sorted({r.local_day for r in entries})
    first_day, last_day = days[0], days[-1]
    day_range = first_day if first_day == last_day else f"{first_day} to {last_day}"

    repos_sorted = sorted(
        repo_buckets.items(),
        key=lambda kv: (-len(kv[1]), kv[0].lower()),
    )
    repos_str = ", ".join(
        f"{markdown_cell(repo)} ({len(rs)})" for repo, rs in repos_sorted
    )

    header = f"### @{login}"
    if display_name:
        header += f" ({markdown_cell(display_name)})"
    header_bits = [f"{len(commits)} commits"]
    if prs:
        header_bits.append(f"{len(prs)} PRs")
    header_bits.append(
        f"{len(repo_buckets)} repo{'s' if len(repo_buckets) != 1 else ''}"
    )
    header_bits.append(day_range)
    header += " — " + " · ".join(header_bits)

    lines = [
        header,
        "",
        f"- **Repos:** {repos_str}",
        f"- **Active days:** {len(days)}",
        "",
        (
            "<!-- FOCUS: Write 2-3 sentences describing this contributor's "
            "work during the window. Name themes and tempo shifts. Do not "
            "list individual commits, PR numbers, or SHAs. -->"
        ),
        "",
        "**Activity by repo:**",
    ]

    for repo, repo_entries in repos_sorted:
        repo_commits = [r for r in repo_entries if r.kind == "commit"]
        repo_prs = [r for r in repo_entries if r.kind == "pr"]
        bits: list[str] = []
        if repo_commits:
            bits.append(f"{len(repo_commits)} commits")
        if repo_prs:
            bits.append(f"{len(repo_prs)} PRs")
        lines.append(f"- **`{repo}`** — {', '.join(bits)}")

        lines.extend(_render_commits_by_theme(repo_commits, per_group_limit))
        if repo_prs:
            lines.extend(_render_prs(repo_prs, per_group_limit))

    lines.append("")
    return lines


def build_appendix(
    args: argparse.Namespace,
    input_files: list[Path],
    rows: list[TeamRow],
    *,
    raw_rows: int,
    duplicates: int,
    malformed: int,
    contributor_rows: dict[str, list[TeamRow]],
    repo_rows: dict[str, list[TeamRow]],
    day_rows: dict[str, list[TeamRow]],
) -> list[str]:
    lines: list[str] = ["### Source TSVs"]
    for path in input_files:
        lines.append(f"- `{path}`")

    lines.extend(["", "### Contributors Table"])
    lines.append(
        "| Login | Name | Commits | PRs | Repos | Active Days | Latest Subject |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---|")
    for login, entries in sorted(
        contributor_rows.items(),
        key=lambda kv: (-len(kv[1]), kv[0].lower()),
    ):
        names = sorted(
            {r.author_name for r in entries if r.author_name and r.author_name != login}
        )
        name = names[0] if names else ""
        commit_count = sum(1 for r in entries if r.kind == "commit")
        pr_count = sum(1 for r in entries if r.kind == "pr")
        repo_count = len({r.repo for r in entries})
        day_count = len({r.local_day for r in entries})
        latest = entries[-1]
        latest_subject = latest.subject
        if latest.kind == "pr" and latest.pr_number:
            latest_subject = f"#{latest.pr_number} {latest_subject}"
        lines.append(
            "| "
            + " | ".join(
                [
                    f"@{login}",
                    markdown_cell(name),
                    str(commit_count),
                    str(pr_count),
                    str(repo_count),
                    str(day_count),
                    markdown_cell(latest_subject),
                ]
            )
            + " |"
        )

    lines.extend(["", "### Repos Table"])
    lines.append(
        "| Repo | Commits | PRs | Contributors | Latest Activity | Latest Subject |"
    )
    lines.append("|---|---:|---:|---:|---|---|")
    for repo, entries in sorted(
        repo_rows.items(),
        key=lambda kv: (-len(kv[1]), kv[0].lower()),
    ):
        commit_count = sum(1 for r in entries if r.kind == "commit")
        pr_count = sum(1 for r in entries if r.kind == "pr")
        contributors = len({r.author_login for r in entries})
        latest = entries[-1]
        latest_subject = latest.subject
        if latest.kind == "pr" and latest.pr_number:
            latest_subject = f"#{latest.pr_number} {latest_subject}"
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{repo}`",
                    str(commit_count),
                    str(pr_count),
                    str(contributors),
                    markdown_cell(f"{latest.local_day} {latest.local_time}"),
                    markdown_cell(latest_subject),
                ]
            )
            + " |"
        )

    lines.extend(["", "### Daily Activity"])
    lines.append("| Local Day | Commits | PRs | Contributors | Repos |")
    lines.append("|---|---:|---:|---:|---:|")
    for day, entries in sorted(
        day_rows.items(), key=lambda kv: kv[0], reverse=True
    ):
        commit_count = sum(1 for r in entries if r.kind == "commit")
        pr_count = sum(1 for r in entries if r.kind == "pr")
        contributors = len({r.author_login for r in entries})
        repos = len({r.repo for r in entries})
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{day}`",
                    str(commit_count),
                    str(pr_count),
                    str(contributors),
                    str(repos),
                ]
            )
            + " |"
        )

    lines.extend(["", "### Recent Activity"])
    lines.append(
        "| Local Day | Local Time | Author | Repo | Kind | Ref | Subject |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for row in reversed(
        rows[-args.recent_limit :] if args.recent_limit > 0 else []
    ):
        ref = f"`{row.short_sha}`" if row.kind == "commit" else (
            f"#{row.pr_number}" if row.pr_number else ""
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row.local_day}`",
                    markdown_cell(row.local_time),
                    f"@{row.author_login}",
                    f"`{row.repo}`",
                    row.kind,
                    ref,
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

    return lines


def build_lines(
    args: argparse.Namespace,
    input_files: list[Path],
    rows: list[TeamRow],
    *,
    raw_rows: int,
    duplicates: int,
    malformed: int,
) -> list[str]:
    coverage_start = rows[0].local_day if rows else "n/a"
    coverage_end = rows[-1].local_day if rows else "n/a"

    contributor_rows: dict[str, list[TeamRow]] = defaultdict(list)
    repo_rows: dict[str, list[TeamRow]] = defaultdict(list)
    day_rows: dict[str, list[TeamRow]] = defaultdict(list)
    for row in rows:
        contributor_rows[row.author_login].append(row)
        repo_rows[row.repo].append(row)
        day_rows[row.local_day].append(row)

    total_commits = sum(1 for r in rows if r.kind == "commit")
    total_prs = sum(1 for r in rows if r.kind == "pr")

    busiest_day = max(
        day_rows.items(), key=lambda kv: (len(kv[1]), kv[0]), default=(None, [])
    )
    most_active_contributor = max(
        contributor_rows.items(),
        key=lambda kv: (len(kv[1]), kv[0]),
        default=(None, []),
    )
    most_active_repo = max(
        repo_rows.items(),
        key=lambda kv: (len(kv[1]), kv[0]),
        default=(None, []),
    )

    lines: list[str] = ["# Git Pulse Team Recap", ""]

    if not args.no_agent_instructions:
        lines.extend([AGENT_INSTRUCTIONS, ""])

    repos_covered = (
        " | ".join(sorted(repo_rows.keys())) if repo_rows else "_(none)_"
    )
    contributors_list = (
        ", ".join(f"@{login}" for login in sorted(contributor_rows.keys()))
        if contributor_rows
        else "_(none)_"
    )
    lines.extend(
        [
            "## Summary",
            f"- Generated at: `{current_utc_iso()}`",
            f"- Window: `{coverage_start}` to `{coverage_end}` ({len(day_rows)} active days)",
            f"- Repos covered: {repos_covered}",
            f"- Contributors: {len(contributor_rows)} — {contributors_list}",
            f"- Commits: {total_commits} · PRs: {total_prs}",
        ]
    )
    if busiest_day[0]:
        day_commits = sum(1 for r in busiest_day[1] if r.kind == "commit")
        day_prs = sum(1 for r in busiest_day[1] if r.kind == "pr")
        lines.append(
            f"- Busiest day: `{busiest_day[0]}` "
            f"({day_commits} commits, {day_prs} PRs)"
        )
    if most_active_contributor[0]:
        lines.append(
            f"- Most active contributor: `@{most_active_contributor[0]}` "
            f"({len(most_active_contributor[1])} events)"
        )
    if most_active_repo[0]:
        lines.append(
            f"- Most active repo: `{most_active_repo[0]}` "
            f"({len(most_active_repo[1])} events)"
        )

    lines.extend(
        [
            "",
            (
                "<!-- TLDR: Write 1-2 sentences summarizing the team's work "
                "during the window — overall shape, where energy concentrated "
                "(which people and/or repos), and any standout pattern. -->"
            ),
            "",
        ]
    )

    lines.extend(["## By Contributor", ""])
    if not contributor_rows:
        lines.extend(["_No activity in the supplied reports._", ""])
    for login, entries in sorted(
        contributor_rows.items(),
        key=lambda kv: (-len(kv[1]), kv[0].lower()),
    ):
        lines.extend(
            build_contributor_section(
                login, entries, per_group_limit=args.per_group_limit
            )
        )

    lines.extend(
        [
            "## Observations",
            "",
            (
                "<!-- OBSERVATIONS: 3-5 bullets on notable team patterns — "
                "bus factor, handoff flow, direct-push vs. PR cadence, silent "
                "repos, new contributors. Each bullet should name a pattern "
                "and hint at the question it raises. -->"
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
            contributor_rows=contributor_rows,
            repo_rows=repo_rows,
            day_rows=day_rows,
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
    collected: list[TeamRow] = []
    for path in input_files:
        if not path.is_file():
            raise SystemExit(f"Input TSV not found: {path}")
        rows, malformed_rows = parse_report(path)
        collected.extend(rows)
        raw_rows += len(rows)
        malformed += malformed_rows

    deduped_rows, duplicates = dedupe_rows(collected)

    if args.output:
        lines = build_lines(
            args,
            input_files,
            deduped_rows,
            raw_rows=raw_rows,
            duplicates=duplicates,
            malformed=malformed,
        )
        rendered = "\n".join(lines) + "\n"
        output_path = Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered)
        sys.stdout.write(rendered)
        return 0

    if not deduped_rows:
        sys.stdout.write(
            "No activity in the supplied reports; nothing to write.\n"
        )
        return 0

    if sync_repo_dir is None:
        raise SystemExit(
            "Auto-naming requires either --output or a configured "
            "sync_repo_dir (~/.config/git-pulse/config.sh)."
        )

    output_dir = sync_repo_dir / "team-reports"
    output_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for year, month, month_rows in split_rows_by_month(deduped_rows):
        month_lines = build_lines(
            args,
            input_files,
            month_rows,
            raw_rows=len(month_rows),
            duplicates=0,
            malformed=0,
        )
        rendered = "\n".join(month_lines) + "\n"
        filename = month_auto_filename(year, month, month_rows)
        out_path = output_dir / filename
        out_path.write_text(rendered)
        written.append(out_path)

    for path in written:
        sys.stdout.write(f"wrote: {path}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

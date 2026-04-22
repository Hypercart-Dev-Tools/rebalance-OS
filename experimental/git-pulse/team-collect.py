#!/usr/bin/env python3
"""Fetch commits and PRs for remote GitHub repos into a team-pulse TSV.

Captures everyone's activity on each target repo within a time window.
Default branch commits + all PRs (any state) are captured; filter at
render time via team-recap.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from urllib import error, parse, request

from pulse_common import load_sync_repo_dir


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

    def to_tsv(self) -> str:
        return "\t".join(getattr(self, col) for col in HEADER)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch commits and PRs from remote GitHub repos into a git-pulse "
            "team TSV. Requires a GitHub PAT via --token, GITHUB_TOKEN, or "
            "GH_TOKEN (repo:read for public, repo for private)."
        )
    )
    parser.add_argument(
        "--repo",
        action="append",
        default=[],
        required=True,
        metavar="OWNER/NAME",
        help="Target repo in owner/name form. Repeatable.",
    )
    parser.add_argument(
        "--since",
        metavar="YYYY-MM-DD",
        default=None,
        help="Earliest date to fetch (UTC). Default: 30 days ago.",
    )
    parser.add_argument(
        "--token",
        metavar="PAT",
        default=None,
        help="GitHub PAT. Falls back to GITHUB_TOKEN / GH_TOKEN env var.",
    )
    parser.add_argument(
        "--output-dir",
        metavar="PATH",
        default=None,
        help="Output directory for TSVs. Default: {sync_repo_dir}/team-pulses.",
    )
    parser.add_argument(
        "--branch",
        action="append",
        default=[],
        metavar="BRANCH",
        help=(
            "Extra branch(es) to fetch commits from. Default branch is always "
            "included. Repeatable."
        ),
    )
    return parser.parse_args()


def resolve_token(cli_token: str | None) -> str:
    token = cli_token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit(
            "No GitHub token provided. Pass --token or set GITHUB_TOKEN / GH_TOKEN."
        )
    return token


def resolve_since(since_arg: str | None) -> datetime:
    if since_arg:
        try:
            dt = datetime.strptime(since_arg, "%Y-%m-%d")
        except ValueError:
            raise SystemExit(
                f"Invalid --since value (expected YYYY-MM-DD): {since_arg}"
            )
        return dt.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - timedelta(days=30)


def resolve_output_dir(output_dir_arg: str | None) -> Path:
    if output_dir_arg:
        return Path(output_dir_arg).expanduser()
    config_dir = Path(
        os.environ.get("GIT_PULSE_CONFIG_DIR")
        or os.environ.get("GIT_HISTORY_CONFIG_DIR")
        or Path.home() / ".config" / "git-pulse"
    )
    sync_repo_dir = load_sync_repo_dir(config_dir / "config.sh", config_dir)
    if sync_repo_dir is None:
        raise SystemExit(
            "No --output-dir given and no git-pulse sync_repo_dir configured "
            "(~/.config/git-pulse/config.sh)."
        )
    return sync_repo_dir / "team-pulses"


def sanitize_tsv(value: str) -> str:
    return value.replace("\t", " ").replace("\n", " ").replace("\r", " ")


def parse_github_iso(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )


def utc_to_local(utc_iso: str) -> tuple[str, str]:
    local = parse_github_iso(utc_iso).astimezone()
    return local.strftime("%Y-%m-%d"), local.strftime("%H:%M %Z")


def parse_link_next(link_header: str) -> str | None:
    for part in link_header.split(","):
        segments = [s.strip() for s in part.split(";")]
        if len(segments) < 2:
            continue
        url_part, rel_part = segments[0], segments[1]
        if rel_part != 'rel="next"':
            continue
        if url_part.startswith("<") and url_part.endswith(">"):
            return url_part[1:-1]
    return None


def gh_get(url: str, token: str) -> tuple[object, dict[str, str]]:
    req = request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "git-pulse-team-collect",
        },
    )
    try:
        with request.urlopen(req) as resp:
            body = resp.read()
            headers = {k: v for k, v in resp.headers.items()}
    except error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise SystemExit(
            f"GitHub API error {exc.code} for {url}: {detail[:300]}"
        )
    return json.loads(body), headers


def paginate(
    url: str,
    token: str,
    stop_predicate: Callable[[dict], bool] | None = None,
) -> list[dict]:
    collected: list[dict] = []
    next_url: str | None = url
    while next_url:
        page, headers = gh_get(next_url, token)
        if not isinstance(page, list):
            break
        for item in page:
            if stop_predicate and stop_predicate(item):
                return collected
            collected.append(item)
        next_url = parse_link_next(
            headers.get("Link") or headers.get("link") or ""
        )
    return collected


def fetch_commits(
    owner: str,
    repo: str,
    since: datetime,
    extra_branches: list[str],
    token: str,
) -> list[TeamRow]:
    rows: list[TeamRow] = []
    seen_shas: set[str] = set()
    since_iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")
    branches = list(dict.fromkeys(["HEAD", *extra_branches]))

    for branch in branches:
        params = {"since": since_iso, "per_page": "100"}
        if branch != "HEAD":
            params["sha"] = branch
        url = (
            f"https://api.github.com/repos/{owner}/{repo}/commits?"
            + parse.urlencode(params)
        )
        items = paginate(url, token)
        branch_label = "(default)" if branch == "HEAD" else branch
        for item in items:
            sha = item.get("sha", "")
            if not sha or sha in seen_shas:
                continue
            seen_shas.add(sha)
            commit = item.get("commit") or {}
            author_info = commit.get("author") or {}
            utc_iso = author_info.get("date") or (
                commit.get("committer") or {}
            ).get("date") or ""
            if not utc_iso:
                continue
            local_day, local_time = utc_to_local(utc_iso)
            author_user = item.get("author") or {}
            author_login = author_user.get("login") or "(unknown)"
            author_name = author_info.get("name") or author_login
            subject = (commit.get("message") or "").split("\n", 1)[0]
            rows.append(
                TeamRow(
                    local_day=local_day,
                    local_time=local_time,
                    utc_time=utc_iso,
                    author_login=author_login,
                    author_name=sanitize_tsv(author_name),
                    repo=f"{owner}/{repo}",
                    branch=branch_label,
                    short_sha=sha[:7],
                    subject=sanitize_tsv(subject),
                    kind="commit",
                    pr_number="",
                )
            )
    return rows


def fetch_prs(
    owner: str, repo: str, since: datetime, token: str
) -> list[TeamRow]:
    rows: list[TeamRow] = []
    url = (
        f"https://api.github.com/repos/{owner}/{repo}/pulls"
        "?state=all&sort=updated&direction=desc&per_page=100"
    )

    def stop(item: dict) -> bool:
        updated_iso = item.get("updated_at", "")
        if not updated_iso:
            return False
        return parse_github_iso(updated_iso) < since

    items = paginate(url, token, stop_predicate=stop)
    for item in items:
        created_iso = item.get("created_at") or ""
        if not created_iso:
            continue
        if parse_github_iso(created_iso) < since:
            continue
        local_day, local_time = utc_to_local(created_iso)
        user = item.get("user") or {}
        author_login = user.get("login") or "(unknown)"
        number = str(item.get("number") or "")
        subject = item.get("title") or ""
        head = item.get("head") or {}
        branch = head.get("ref") or ""
        rows.append(
            TeamRow(
                local_day=local_day,
                local_time=local_time,
                utc_time=created_iso,
                author_login=author_login,
                author_name=author_login,
                repo=f"{owner}/{repo}",
                branch=branch,
                short_sha="",
                subject=sanitize_tsv(subject),
                kind="pr",
                pr_number=number,
            )
        )
    return rows


def write_tsv(path: Path, rows: list[TeamRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sorted_rows = sorted(rows, key=lambda r: r.utc_time)
    lines = ["\t".join(HEADER)]
    lines.extend(row.to_tsv() for row in sorted_rows)
    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    args = parse_args()
    token = resolve_token(args.token)
    since = resolve_since(args.since)
    output_dir = resolve_output_dir(args.output_dir)

    exit_code = 0
    for repo_arg in args.repo:
        if "/" not in repo_arg:
            print(
                f"skipping {repo_arg}: expected owner/name form",
                file=sys.stderr,
            )
            exit_code = 1
            continue
        owner, repo = repo_arg.split("/", 1)
        print(
            f"fetching {owner}/{repo} since {since.strftime('%Y-%m-%d')}...",
            file=sys.stderr,
        )
        commits = fetch_commits(owner, repo, since, args.branch, token)
        prs = fetch_prs(owner, repo, since, token)
        output_path = output_dir / f"{owner}-{repo}.tsv"
        write_tsv(output_path, commits + prs)
        print(
            f"wrote: {output_path} ({len(commits)} commits, {len(prs)} PRs)",
            file=sys.stderr,
        )

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

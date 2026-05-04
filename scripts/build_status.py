#!/usr/bin/env python3
"""
Build the activity-status JSON consumed by the GitHub Pages dashboard.

Designed to run inside ``.github/workflows/update-status.yml`` — one process,
no SQLite, no FastAPI. Pulls fresh data from the GitHub REST API and writes a
single ``status.json`` to the path passed via ``--out``.

Output shape (frozen — frontend depends on it):

    {
      "generated_at": ISO-8601 UTC,
      "window_days":  int,
      "watched_repos": [...],
      "rate_limit":   {"remaining": int, "limit": int, "reset_at": str},
      "rows": [
        {
          "when":       ISO-8601,
          "repo":       "owner/name",
          "branch":     "claude/abc" | null,
          "kind":       "commit" | "pr_opened" | "pr_merged" | "pr_closed"
                        | "workflow_run" | "local_session",
          "title":      str,
          "actor":      str | null,
          "source_tag": "claude-cloud" | "codex-cloud" | "lovable"
                        | "local-vscode" | "human",
          "links":      {"commit": url|null, "pr": url|null, "run": url|null},
          "ci":         {"status", "conclusion", "url", "name", "color"} | null
        }
      ]
    }

Usage:
    GH_TOKEN=ghp_… python scripts/build_status.py --out /tmp/status.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from rebalance.ingest.agent_tags import classify  # noqa: E402

GITHUB_API = "https://api.github.com"
DEFAULT_WINDOW_DAYS = 7
EVENT_DISCOVERY_DAYS = 14
DEFAULT_PER_REPO_LIMIT = 30
USER_AGENT = "rebalance-os-status/0.1"


# ---------------------------------------------------------------------------
# HTTP helper with rate-limit handling
# ---------------------------------------------------------------------------


class GitHubClient:
    def __init__(self, token: str) -> None:
        self.token = token
        self.rate_limit: dict[str, Any] = {"remaining": None, "limit": None, "reset_at": None}

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": USER_AGENT,
        }

    def get(self, url: str) -> tuple[int, Any]:
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                self._record_limits(resp.headers)
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            self._record_limits(exc.headers)
            return exc.code, None
        except urllib.error.URLError as exc:
            print(f"[warn] network error fetching {url}: {exc}", file=sys.stderr)
            return 0, None

    def _record_limits(self, headers: Any) -> None:
        if headers is None:
            return
        try:
            remaining = headers.get("X-RateLimit-Remaining")
            limit = headers.get("X-RateLimit-Limit")
            reset = headers.get("X-RateLimit-Reset")
            if remaining is not None:
                self.rate_limit["remaining"] = int(remaining)
            if limit is not None:
                self.rate_limit["limit"] = int(limit)
            if reset is not None:
                self.rate_limit["reset_at"] = datetime.fromtimestamp(
                    int(reset), tz=timezone.utc
                ).isoformat()
        except (ValueError, TypeError):
            pass


# ---------------------------------------------------------------------------
# Repo discovery
# ---------------------------------------------------------------------------


def discover_repos_from_events(client: GitHubClient, days: int) -> list[str]:
    """Mirror ``github_scan.discover_repos_from_activity`` — events feed."""
    status, data = client.get(f"{GITHUB_API}/user")
    if status != 200 or not isinstance(data, dict):
        return []
    login = data.get("login")
    if not login:
        return []

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    repos: set[str] = set()
    for page in range(1, 4):
        url = f"{GITHUB_API}/users/{login}/events?per_page=100&page={page}"
        status, events = client.get(url)
        if status != 200 or not isinstance(events, list):
            break
        reached_cutoff = False
        for ev in events:
            day = (ev.get("created_at") or "")[:10]
            if day < cutoff:
                reached_cutoff = True
                break
            repo = (ev.get("repo") or {}).get("name")
            if isinstance(repo, str) and "/" in repo:
                repos.add(repo)
        if reached_cutoff or len(events) < 100:
            break
    return sorted(repos)


def read_registry_repos(repo_root: Path) -> list[str]:
    """
    Read repos from ``Projects/00-project-registry.md`` if checked into the
    repo. Falls back to an env var ``REBALANCE_WATCH_REPOS`` (comma-sep).

    The registry file lives in the user's vault and is not checked in by
    default, so most CI runs will rely on the env var or pure event discovery.
    """
    env_list = os.environ.get("REBALANCE_WATCH_REPOS", "").strip()
    if env_list:
        return [r.strip() for r in env_list.split(",") if r.strip() and "/" in r]

    candidate = repo_root / "Projects" / "00-project-registry.md"
    if not candidate.exists():
        return []
    repos: set[str] = set()
    for line in candidate.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if "/" in stripped and len(stripped.split()) <= 2:
            for tok in stripped.replace(",", " ").split():
                if tok.count("/") == 1 and not tok.startswith(("http", "/", "#", "-")):
                    repos.add(tok)
    return sorted(repos)


# ---------------------------------------------------------------------------
# Per-repo fetchers
# ---------------------------------------------------------------------------


def _iso_cutoff(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_commits(client: GitHubClient, repo: str, since: str, limit: int) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"since": since, "per_page": limit})
    status, data = client.get(f"{GITHUB_API}/repos/{repo}/commits?{params}")
    if status != 200 or not isinstance(data, list):
        return []
    return data


def fetch_pulls(client: GitHubClient, repo: str, limit: int) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode(
        {"state": "all", "sort": "updated", "direction": "desc", "per_page": limit}
    )
    status, data = client.get(f"{GITHUB_API}/repos/{repo}/pulls?{params}")
    if status != 200 or not isinstance(data, list):
        return []
    return data


def fetch_workflow_runs(
    client: GitHubClient, repo: str, since: str, limit: int
) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode(
        {"per_page": limit, "created": f">={since}"}
    )
    status, data = client.get(f"{GITHUB_API}/repos/{repo}/actions/runs?{params}")
    if status != 200 or not isinstance(data, dict):
        return []
    runs = data.get("workflow_runs") or []
    return runs if isinstance(runs, list) else []


# ---------------------------------------------------------------------------
# Local pulse files (optional)
# ---------------------------------------------------------------------------


def read_device_pulses(mirror_path: Path, since: datetime) -> list[dict[str, Any]]:
    if not mirror_path or not mirror_path.exists():
        return []
    cutoff_epoch = int(since.timestamp())
    rows: list[dict[str, Any]] = []
    for pulse_file in sorted(mirror_path.glob("pulse-*.md")):
        device = pulse_file.stem.removeprefix("pulse-")
        try:
            text = pulse_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for raw in text.splitlines():
            line = raw.rstrip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 6:
                continue
            try:
                epoch = int(parts[0])
            except ValueError:
                continue
            if epoch < cutoff_epoch:
                continue
            rows.append(
                {
                    "when": parts[1],
                    "device": device,
                    "repo": parts[2],
                    "branch": parts[3],
                    "sha": parts[4],
                    "subject": parts[5],
                }
            )
    return rows


# ---------------------------------------------------------------------------
# CI-color helper
# ---------------------------------------------------------------------------


def _ci_color(status: str | None, conclusion: str | None) -> str:
    c = (conclusion or "").lower()
    s = (status or "").lower()
    if c == "success":
        return "green"
    if c in {"failure", "timed_out", "cancelled", "startup_failure", "action_required", "stale"}:
        return "red"
    if s in {"in_progress", "queued", "pending", "waiting"}:
        return "yellow"
    return "grey"


def _commit_title(message: str | None) -> str:
    if not message:
        return ""
    return message.split("\n", 1)[0].strip()[:200]


# ---------------------------------------------------------------------------
# Row builders
# ---------------------------------------------------------------------------


def _index_runs_by_sha(runs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Return the most recent run per head_sha (runs are usually newest-first)."""
    by_sha: dict[str, dict[str, Any]] = {}
    for run in runs:
        sha = run.get("head_sha")
        if not isinstance(sha, str):
            continue
        existing = by_sha.get(sha)
        if existing is None or (run.get("created_at") or "") > (existing.get("created_at") or ""):
            by_sha[sha] = run
    return by_sha


def build_rows(
    repo: str,
    commits: list[dict[str, Any]],
    pulls: list[dict[str, Any]],
    runs: list[dict[str, Any]],
    pr_window_iso: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    runs_by_sha = _index_runs_by_sha(runs)

    for c in commits:
        commit_block = c.get("commit") or {}
        author_block = c.get("author") or {}
        committer_block = c.get("committer") or {}
        message = commit_block.get("message") or ""
        sha = c.get("sha") or ""
        when = (commit_block.get("author") or {}).get("date") or (
            (commit_block.get("committer") or {}).get("date") or ""
        )
        run = runs_by_sha.get(sha)
        ci = None
        branch = run.get("head_branch") if run else None
        if run is not None:
            ci = {
                "status": run.get("status"),
                "conclusion": run.get("conclusion"),
                "url": run.get("html_url"),
                "name": run.get("name"),
                "color": _ci_color(run.get("status"), run.get("conclusion")),
            }
        rows.append(
            {
                "when": when,
                "repo": repo,
                "branch": branch,
                "kind": "commit",
                "title": _commit_title(message) or sha[:7],
                "actor": author_block.get("login") or (commit_block.get("author") or {}).get("name"),
                "source_tag": classify(
                    branch=branch,
                    author_login=author_block.get("login"),
                    committer_login=committer_block.get("login"),
                    commit_message=message,
                ),
                "links": {
                    "commit": c.get("html_url"),
                    "pr": None,
                    "run": ci["url"] if ci else None,
                },
                "ci": ci,
            }
        )

    for p in pulls:
        if (p.get("updated_at") or "") < pr_window_iso:
            continue
        head = p.get("head") or {}
        author = (p.get("user") or {}).get("login")
        branch = head.get("ref")
        if p.get("merged_at"):
            kind, when = "pr_merged", p["merged_at"]
        elif p.get("state") == "closed":
            kind, when = "pr_closed", p.get("updated_at") or p.get("created_at") or ""
        else:
            kind, when = "pr_opened", p.get("created_at") or p.get("updated_at") or ""
        rows.append(
            {
                "when": when,
                "repo": repo,
                "branch": branch,
                "kind": kind,
                "title": f"#{p.get('number')} {p.get('title') or ''}".strip(),
                "actor": author,
                "source_tag": classify(branch=branch, author_login=author),
                "links": {
                    "commit": None,
                    "pr": p.get("html_url"),
                    "run": None,
                },
                "ci": None,
            }
        )

    for run in runs:
        actor = (run.get("actor") or {}).get("login") or (
            (run.get("triggering_actor") or {}).get("login")
        )
        ci = {
            "status": run.get("status"),
            "conclusion": run.get("conclusion"),
            "url": run.get("html_url"),
            "name": run.get("name"),
            "color": _ci_color(run.get("status"), run.get("conclusion")),
        }
        rows.append(
            {
                "when": run.get("created_at") or "",
                "repo": repo,
                "branch": run.get("head_branch"),
                "kind": "workflow_run",
                "title": f"{run.get('name') or 'workflow'} · {run.get('event') or ''}".strip(" ·"),
                "actor": actor,
                "source_tag": classify(branch=run.get("head_branch"), author_login=actor),
                "links": {"commit": None, "pr": None, "run": run.get("html_url")},
                "ci": ci,
            }
        )

    return rows


def build_local_session_rows(pulses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for p in pulses:
        rows.append(
            {
                "when": p["when"],
                "repo": p["repo"],
                "branch": p.get("branch"),
                "kind": "local_session",
                "title": p.get("subject") or "",
                "actor": p.get("device"),
                "source_tag": "local-vscode",
                "links": {"commit": None, "pr": None, "run": None},
                "ci": None,
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build status.json for GH Pages dashboard")
    parser.add_argument("--out", required=True, type=Path, help="Path to write status.json")
    parser.add_argument(
        "--window-days",
        type=int,
        default=DEFAULT_WINDOW_DAYS,
        help="Days of history to include for PRs/workflow runs (default: 7)",
    )
    parser.add_argument(
        "--per-repo",
        type=int,
        default=DEFAULT_PER_REPO_LIMIT,
        help="Max items to fetch per endpoint per repo (default: 30)",
    )
    parser.add_argument(
        "--pulse-mirror",
        type=Path,
        default=None,
        help="Path to a checkout of the device-pulse repo (optional)",
    )
    args = parser.parse_args(argv)

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("error: GH_TOKEN (or GITHUB_TOKEN) is required", file=sys.stderr)
        return 2

    started = time.monotonic()
    client = GitHubClient(token)

    repos = set(read_registry_repos(REPO_ROOT))
    repos.update(discover_repos_from_events(client, EVENT_DISCOVERY_DAYS))
    watched = sorted(r.lower() for r in repos)

    cutoff = _iso_cutoff(args.window_days)
    rows: list[dict[str, Any]] = []
    for repo in watched:
        commits = fetch_commits(client, repo, cutoff, args.per_repo)
        pulls = fetch_pulls(client, repo, args.per_repo)
        runs = fetch_workflow_runs(client, repo, cutoff, args.per_repo)
        rows.extend(build_rows(repo, commits, pulls, runs, cutoff))

    if args.pulse_mirror:
        pulses = read_device_pulses(
            args.pulse_mirror, datetime.now(timezone.utc) - timedelta(days=args.window_days)
        )
        rows.extend(build_local_session_rows(pulses))

    rows.sort(key=lambda r: r.get("when") or "", reverse=True)
    rows = rows[:500]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
            "+00:00", "Z"
        ),
        "window_days": args.window_days,
        "watched_repos": watched,
        "rate_limit": client.rate_limit,
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "rows": rows,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"wrote {len(rows)} rows across {len(watched)} repos to {args.out} "
        f"(elapsed {payload['elapsed_seconds']}s, rate-limit "
        f"{client.rate_limit.get('remaining')}/{client.rate_limit.get('limit')})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

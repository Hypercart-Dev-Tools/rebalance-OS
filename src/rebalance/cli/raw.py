"""`rebalance raw` — calibration probe: recent GitHub events vs local pipeline state.

Extracted from the cli monolith (Phase 5). Registers the `raw` command on the
shared Typer `app` and keeps its `_raw_*` helpers alongside it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from rebalance.cli._core import app
from rebalance.ingest.config import get_github_ignored_repos
from rebalance.lib.time_ops import format_local, parse_utc_iso
from rebalance.paths import DatabaseNotFoundError, DBOption, resolve_database_path


# ---------------------------------------------------------------------------
# Raw activity probe (calibration tool)
# ---------------------------------------------------------------------------

def _raw_summarize_event(event: dict[str, Any]) -> str:
    """One-line summary of a GitHub user-event dict."""
    kind = event.get("type") or ""
    p = event.get("payload") or {}
    if kind == "PushEvent":
        n = len(p.get("commits") or [])
        ref = (p.get("ref") or "").split("/")[-1]
        return f"{n} commit{'s' if n != 1 else ''} → {ref}" if ref else f"{n} commit{'s' if n != 1 else ''}"
    if kind == "PullRequestEvent":
        pr = p.get("pull_request") or {}
        return f"#{pr.get('number','?')} {p.get('action','')} — {(pr.get('title') or '').strip()[:160]}"
    if kind == "IssuesEvent":
        issue = p.get("issue") or {}
        return f"#{issue.get('number','?')} {p.get('action','')} — {(issue.get('title') or '').strip()[:160]}"
    if kind == "IssueCommentEvent":
        issue = p.get("issue") or {}
        return f"comment on #{issue.get('number','?')}"
    if kind == "PullRequestReviewEvent":
        pr = p.get("pull_request") or {}
        return f"review on #{pr.get('number','?')}"
    if kind == "PullRequestReviewCommentEvent":
        pr = p.get("pull_request") or {}
        return f"review comment on #{pr.get('number','?')}"
    if kind == "CreateEvent":
        return f"create {p.get('ref_type','')} {p.get('ref','') or ''}".strip()
    if kind == "DeleteEvent":
        return f"delete {p.get('ref_type','')} {p.get('ref','') or ''}".strip()
    if kind == "ReleaseEvent":
        rel = p.get("release") or {}
        return f"release {rel.get('tag_name','')}"
    if kind == "WatchEvent":
        return "starred"
    if kind == "ForkEvent":
        return "forked"
    return ""


def _raw_get_top_active_repos(db_path: Path, top_n: int) -> list[str]:
    """Top N watched repos by 7-day activity score (commits + PRs + issues + comments + reviews)."""
    from rebalance.ingest.db import db_connection, top_active_repos
    with db_connection(db_path) as conn:
        return top_active_repos(conn, top_n)


def _raw_fetch_repo_events(repo: str, token: str, per_page: int = 30) -> list[dict[str, Any]]:
    """Fetch the most recent events for a single repo. Returns [] on any failure."""
    from rebalance.ingest.github_scan import GITHUB_API, _get
    try:
        status, data = _get(f"{GITHUB_API}/repos/{repo}/events?per_page={per_page}", token)
    except Exception:
        return []
    if status != 200 or not isinstance(data, list):
        return []
    return data


def _raw_gather_team_activity(
    login: str, token: str, db_path: Path, minutes: int, top_n: int
) -> dict[str, Any]:
    """Per-repo events for the top N most-active watched repos, filtered to the last
    N minutes and excluding the current user (those are already in the user-activity
    section).
    """
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    top_repos = _raw_get_top_active_repos(db_path, top_n)

    last_active_map: dict[str, datetime] = {}
    if top_repos:
        from rebalance.ingest.db import db_connection, repo_last_active
        with db_connection(db_path) as conn:
            last_active_raw = repo_last_active(conn, top_repos)
        for repo, ts in last_active_raw.items():
            parsed_ts = parse_utc_iso(ts)
            if parsed_ts:
                last_active_map[repo] = parsed_ts

    items: list[dict[str, Any]] = []
    counts = {"captured": 0, "pending": 0}

    for repo in top_repos:
        for event in _raw_fetch_repo_events(repo, token):
            event_time = parse_utc_iso(event.get("created_at"))
            if not event_time:
                continue
            if event_time < cutoff:
                continue
            actor = (event.get("actor") or {}).get("login") or ""
            if actor == login:
                continue  # already covered in user-activity section

            la = last_active_map.get(repo)
            status = "captured" if (la and la >= event_time) else "pending"
            counts[status] += 1

            items.append({
                "time": event_time.isoformat(timespec="seconds"),
                "type": event.get("type") or "",
                "repo": repo,
                "actor": f"@{actor}" if actor else "",
                "summary": _raw_summarize_event(event),
                "status": status,
                "last_active_at": la.isoformat(timespec="seconds") if la else None,
            })

    items.sort(key=lambda x: x["time"], reverse=True)

    return {
        "top_repos_checked": top_repos,
        "events": items,
        "summary": {"total": len(items), **counts},
    }


def _raw_gather_unwatched_active_repos(
    token: str, db_path: Path, fresh_threshold_days: int = 7, per_page: int = 30
) -> dict[str, Any]:
    """Find accessible-but-unwatched repos with recent pushes.

    Surfaces freshly-created or low-event repos that the events feed can
    miss (collaborator pushes on private org repos, pushes dropped by the
    300-event pagination cap, eventual-consistency gaps). Hits
    /user/repos?sort=pushed&direction=desc&per_page=N and compares against
    the canonical watched set (get_watched_repos) and the ignored list.

    Cost: 1 GH API request per probe.
    """
    from datetime import datetime, timedelta, timezone

    from rebalance.ingest.github_scan import fetch_pushed_repos
    from rebalance.ingest.index_ops import get_watched_repos

    result: dict[str, Any] = {
        "checked_count": 0,
        "fresh_threshold_days": fresh_threshold_days,
        "repos": [],
    }
    try:
        records = fetch_pushed_repos(token, per_page=per_page)
    except Exception as exc:
        result["error"] = f"fetch failed: {exc}"
        return result

    result["checked_count"] = len(records)

    watched = set(get_watched_repos(db_path)["watched"])
    # Lowercased for case-insensitive ignore-match — see get_watched_repos
    # for the same pattern (config stores lowercase, GitHub returns original casing).
    ignored_lower = {r.lower() for r in get_github_ignored_repos()}

    cutoff = datetime.now(timezone.utc) - timedelta(days=fresh_threshold_days)
    repos: list[dict[str, Any]] = []
    for rec in records:
        if rec.repo_full_name in watched or rec.repo_full_name.lower() in ignored_lower:
            continue
        if rec.archived or rec.disabled:
            continue
        pushed = parse_utc_iso(rec.pushed_at)
        if not pushed or pushed < cutoff:
            continue
        repos.append({
            "full_name": rec.repo_full_name,
            "pushed_at": pushed.isoformat(timespec="seconds"),
            "private": rec.private,
            "fork": rec.fork,
        })

    result["repos"] = repos
    return result


def _raw_gather_snapshot(login: str, token: str, db_path: Path, minutes: int, top_n: int) -> dict[str, Any]:
    """Fetch recent GH events and classify each against local pipeline state."""
    from datetime import datetime, timedelta, timezone

    from rebalance.ingest.github_scan import _fetch_events

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)

    # 1 API request: events API caps recent activity at ~30 days; we just need the latest page.
    events = _fetch_events(login, token, days=1)

    recent = []
    for e in events:
        t = parse_utc_iso(e.get("created_at"))
        if not t:
            continue
        if t >= cutoff:
            recent.append((t, e))
    recent.sort(key=lambda x: x[0], reverse=True)

    from rebalance.ingest.db import db_connection, repo_last_active, repo_meta_names
    with db_connection(db_path) as conn:
        watched = repo_meta_names(conn)
        last_active_raw = repo_last_active(conn)
    last_active_map: dict[str, datetime] = {}
    for repo, ts in last_active_raw.items():
        parsed_ts = parse_utc_iso(ts)
        if parsed_ts:
            last_active_map[repo] = parsed_ts

    items: list[dict[str, Any]] = []
    counts = {"captured": 0, "pending": 0, "unwatched": 0}
    unwatched_repos: set[str] = set()

    for event_time, event in recent:
        repo = (event.get("repo") or {}).get("name") or ""
        if repo and repo not in watched:
            status = "unwatched"
            la_iso: str | None = None
            unwatched_repos.add(repo)
        else:
            la = last_active_map.get(repo)
            la_iso = la.isoformat(timespec="seconds") if la else None
            status = "captured" if (la and la >= event_time) else "pending"
        counts[status] += 1
        items.append({
            "time": event_time.isoformat(timespec="seconds"),
            "type": event.get("type") or "",
            "repo": repo,
            "summary": _raw_summarize_event(event),
            "status": status,
            "last_active_at": la_iso,
        })

    team_activity = _raw_gather_team_activity(login, token, db_path, minutes, top_n)
    unwatched_active_repos = _raw_gather_unwatched_active_repos(token, db_path)

    return {
        "raw_version": 1,
        "scanned_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "login": login,
        "window_minutes": minutes,
        "events": items,
        "summary": {
            "total": len(items),
            **counts,
            "unwatched_repos": sorted(unwatched_repos),
        },
        "team_activity": team_activity,
        "unwatched_active_repos": unwatched_active_repos,
    }


def _raw_render_text(snapshot: dict[str, Any]) -> None:
    """Render snapshot as a Rich table for terminal use."""
    from datetime import datetime
    from rich.console import Console
    from rich.table import Table

    console = Console()
    sm = snapshot["summary"]
    console.print(
        f"[bold]raw activity · last {snapshot['window_minutes']} min · "
        f"@{snapshot['login']} · {snapshot['scanned_at']}[/bold]"
    )
    console.print(
        f"[dim]{sm['total']} event(s) · "
        f"[green]✓ {sm['captured']} captured[/green] · "
        f"[yellow]⏳ {sm['pending']} pending[/yellow] · "
        f"[red]✗ {sm['unwatched']} unwatched[/red][/dim]"
    )

    if not snapshot["events"]:
        console.print("[dim](no events in window)[/dim]")
        return

    table = Table(show_header=True, header_style="bold", expand=True)
    table.add_column("time", style="dim", no_wrap=True)
    table.add_column("status", justify="center", no_wrap=True, width=6)
    table.add_column("type", overflow="fold", ratio=1, max_width=30)
    table.add_column("repo", overflow="fold", ratio=2)
    table.add_column("summary", overflow="fold", ratio=2)

    glyphs = {"captured": ("✓", "green"), "pending": ("⏳", "yellow"), "unwatched": ("✗", "red")}
    for ev in snapshot["events"]:
        glyph, color = glyphs.get(ev["status"], ("?", "white"))
        local_time = format_local(ev["time"], "%H:%M:%S")
        table.add_row(local_time, f"[{color}]{glyph}[/{color}]", ev["type"], ev["repo"], ev["summary"])
    console.print(table)

    if sm["unwatched_repos"]:
        console.print()
        console.print("[red]Unwatched repos with recent activity (likely missing from pipeline):[/red]")
        for r in sm["unwatched_repos"]:
            console.print(f"  - {r}")

    team = snapshot.get("team_activity") or {}
    top_repos = team.get("top_repos_checked") or []
    if top_repos:
        ts = team["summary"]
        console.print()
        console.print(
            f"[bold]team activity · top {len(top_repos)} most-active watched repos · "
            f"{ts['total']} event(s) · "
            f"[green]✓ {ts['captured']} captured[/green] · "
            f"[yellow]⏳ {ts['pending']} pending[/yellow][/bold]"
        )
        if not team["events"]:
            console.print("[dim](no team events from these repos in window)[/dim]")
        else:
            team_table = Table(show_header=True, header_style="bold", expand=True)
            team_table.add_column("time", style="dim", no_wrap=True)
            team_table.add_column("status", justify="center", no_wrap=True, width=6)
            team_table.add_column("type", overflow="fold", ratio=1, max_width=30)
            team_table.add_column("repo", overflow="fold", ratio=2)
            team_table.add_column("actor", style="dim", no_wrap=True)
            team_table.add_column("summary", overflow="fold", ratio=2)
            for ev in team["events"]:
                glyph, color = glyphs.get(ev["status"], ("?", "white"))
                local_time = format_local(ev["time"], "%H:%M:%S")
                team_table.add_row(
                    local_time,
                    f"[{color}]{glyph}[/{color}]",
                    ev["type"],
                    ev["repo"],
                    ev["actor"],
                    ev["summary"],
                )
            console.print(team_table)
        console.print(f"[dim]Repos checked: {', '.join(top_repos)}[/dim]")

    unwatched = snapshot.get("unwatched_active_repos") or {}
    if unwatched.get("error"):
        console.print()
        console.print(f"[yellow]Unwatched-repos check skipped: {unwatched['error']}[/yellow]")
    elif unwatched.get("repos"):
        from datetime import datetime, timezone
        console.print()
        console.print(
            f"[red]Unwatched repos with recent pushes "
            f"(last {unwatched['fresh_threshold_days']}d, not in github_repo_meta or ignored list):[/red]"
        )
        now_utc = datetime.now(timezone.utc)
        for r in unwatched["repos"]:
            pushed = parse_utc_iso(r["pushed_at"])
            if not pushed:
                continue
            delta = now_utc - pushed
            if delta.days > 0:
                ago = f"{delta.days}d ago"
            elif delta.seconds >= 3600:
                ago = f"{delta.seconds // 3600}h ago"
            else:
                ago = f"{max(1, delta.seconds // 60)}m ago"
            flags = []
            if r.get("private"):
                flags.append("private")
            if r.get("fork"):
                flags.append("fork")
            flag_str = f"  [dim]({', '.join(flags)})[/dim]" if flags else ""
            console.print(f"  - {r['full_name']}  [dim]pushed {ago}[/dim]{flag_str}")
    elif unwatched.get("checked_count"):
        console.print()
        console.print(
            f"[dim]All {unwatched['checked_count']} most-recently-pushed accessible repos "
            f"are watched or ignored.[/dim]"
        )


@app.command("raw")
def raw(
    minutes: int = typer.Option(30, "--minutes", "-m", help="Look back this many minutes (default 30)."),
    watch: int | None = typer.Option(
        None, "--watch", "-w",
        help="Re-run every N seconds until Ctrl-C. Floor 30s recommended (GH events API has ~30s eventual consistency).",
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON instead of a Rich table."),
    top_n: int = typer.Option(
        10, "--top",
        help="How many of the most-active watched repos to scan for team activity (cost: 1 GH API request per repo per probe).",
    ),
    database: Path | None = DBOption(),
) -> None:
    """Calibration view: GitHub events from the last N minutes vs local pipeline state.

    Three sections:
      - Your activity (from /users/{login}/events) classified as
            ✓ captured   — pipeline caught up (last_active_at >= event_time)
            ⏳ pending    — repo is watched but the next sync hasn't run yet
            ✗ unwatched  — repo is NOT in github_repo_meta; silently missing
      - Team activity from the top N most-active watched repos (per-repo events,
        excluding the current user) — surfaces teammate activity the
        user-events feed alone can't see, classified as captured / pending.
      - Unwatched repos with recent pushes (from /user/repos?sort=pushed) —
        independent of the events feed, so freshly-created or low-event repos
        you haven't yet added to the watch list don't slip past. Honors the
        configured ignored-repos list and skips archived/disabled repos.

    Costs 1 + N + 1 GitHub API requests per invocation (default N=10).
    Default --watch cadence: 60s is comfortable; 30s is the practical floor;
    faster gives diminishing returns due to GH events API ~30s eventual
    consistency.
    """
    import json as _json
    import time

    from rebalance.ingest.config import get_github_token
    from rebalance.ingest.github_scan import GitHubApiError, _get_login

    token = get_github_token()
    if not token:
        typer.echo("[error] no GitHub token configured. Run: rebalance config set-github-token")
        raise typer.Exit(2)

    try:
        login = _get_login(token)
    except GitHubApiError as exc:
        typer.echo(f"[error] cannot resolve GH login: {exc}")
        raise typer.Exit(2)

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc

    if watch is not None and watch < 30:
        typer.echo(f"[warn] --watch {watch}s is below the recommended 30s floor; rate-limit fine but events API won't refresh faster.")

    while True:
        snapshot = _raw_gather_snapshot(login, token, db_path, minutes, top_n)
        if json_output:
            print(_json.dumps(snapshot, indent=2))
        else:
            _raw_render_text(snapshot)
        if watch is None:
            break
        try:
            time.sleep(watch)
        except KeyboardInterrupt:
            break

import json
import pickle
from datetime import date as date_cls, datetime, time as time_cls, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import typer

from rebalance.ingest.preflight import run_preflight
from rebalance.ingest.registry import sync_registry
from rebalance.ingest.config import (
    add_github_related_repo,
    add_github_ignored_repo,
    clear_github_token,
    get_github_related_repos,
    get_github_token,
    get_github_token_with_source,
    get_github_ignored_repos,
    get_project_priority_rules,
    set_github_token,
    set_project_priority_rule,
    get_vault_path,
    set_vault_path,
    get_config_path,
    normalize_github_repo_name,
    remove_github_related_repo,
    remove_github_ignored_repo,
    remove_project_priority_rule,
)
from rebalance.ingest.audit import append_audit_entry
from rebalance.paths import (
    DatabaseNotFoundError,
    DBOption,
    canonical_database_path,
    resolve_database_path,
    resolve_secret_path,
)

app = typer.Typer(help="rebalance CLI")
ingest_app = typer.Typer(help="Ingest and project registry workflows")
config_app = typer.Typer(help="Configuration and secrets management")
app.add_typer(ingest_app, name="ingest")
app.add_typer(config_app, name="config")


# Resolved once so all paths in the CLI process agree on where the project
# lives — cli.py is at src/rebalance/cli.py, so .parent.parent.parent is the
# repo root regardless of cwd.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _launch_dashboard() -> None:
    """Replace the current CLI process with the live dashboard.

    Used by both the no-arg invocation (``rebalance``) and the explicit
    ``rebalance dashboard`` subcommand. We ``execv`` the dashboard
    script so the user sees a clean process with no nested Python
    overhead and so the dashboard's own termios / Rich Live cleanup
    runs at exit.
    """
    import os
    import sys

    dashboard_path = _PROJECT_ROOT / "scripts" / "dashboard.py"
    if not dashboard_path.exists():
        typer.echo(f"dashboard script not found: {dashboard_path}", err=True)
        raise typer.Exit(1)

    # Default REBALANCE_DB to the canonical app-data location so `rebalance`
    # works from any cwd and agrees with the MCP server / launchd jobs. (Do
    # not point this at the repo root — that reintroduces the DB-path split.)
    os.environ.setdefault("REBALANCE_DB", str(canonical_database_path()))
    os.execv(sys.executable, [sys.executable, str(dashboard_path)])


@app.callback(invoke_without_command=True)
def _root(ctx: typer.Context) -> None:
    """rebalance — local-first workday operating system.

    Invoked with no subcommand: launches the live activity dashboard
    (Rich Live, 4-pane). Subcommands continue to work as before; see
    ``rebalance --help`` for the full surface.
    """
    if ctx.invoked_subcommand is None:
        _launch_dashboard()


@app.command("dashboard")
def dashboard_cmd() -> None:
    """Launch the live activity dashboard (Rich Live, 4-pane).

    Same as running ``rebalance`` with no arguments — exposed
    explicitly so it shows up in ``--help``.
    """
    _launch_dashboard()


@app.command("doctor")
def doctor_cmd(database: Path | None = DBOption()) -> None:
    """Health check — database, token, schema, projects, GitHub data, scheduled jobs.

    Read-only. Surfaces the class of problem a test suite cannot: which database
    is actually in use, whether the GitHub token is reachable by launchd jobs,
    schema version, registered projects, data freshness, and job exit status.
    """
    from rich.console import Console

    from rebalance.doctor import FAIL, OK, WARN, run_doctor

    console = Console()
    report = run_doctor(database)
    label = {
        OK: "[green] OK [/green]",
        WARN: "[yellow]WARN[/yellow]",
        FAIL: "[red]FAIL[/red]",
    }
    console.print("\n[bold]rebalance doctor[/bold]\n")
    for c in report.checks:
        console.print(f"  {label[c.status]}  [bold]{c.name}[/bold] — {c.detail}")
        if c.hint and c.status != OK:
            console.print(f"         [dim]{c.hint}[/dim]")
    console.print()
    if report.failed:
        console.print("[red]Health check found failures.[/red]")
        raise typer.Exit(1)
    if report.warned:
        console.print("[yellow]Health check passed with warnings.[/yellow]")
    else:
        console.print("[green]All checks passed.[/green]")


@app.command("onboard")
def onboard_cmd(
    vault_path: str = typer.Option(
        "", "--vault-path", help="Obsidian vault path (default: the configured one)."
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y",
        help="Register every discovered active project without prompting.",
    ),
    skip_refresh: bool = typer.Option(
        False, "--skip-refresh", help="Skip the initial data refresh."
    ),
    database: Path | None = DBOption(),
) -> None:
    """Guided onboarding: persist the GitHub token, discover & register projects, refresh.

    One command for the sequence that was previously only an agent-driven MCP
    flow — so it doesn't fall between the cracks. Idempotent: safe to re-run.
    """
    from dataclasses import asdict, is_dataclass

    from rebalance.ingest.config import (
        get_github_token_with_source,
        get_vault_path,
        set_github_token,
    )
    from rebalance.ingest.index_ops import refresh_index
    from rebalance.ingest.preflight import confirm_and_write, discover_candidates

    # 1. Vault path.
    vault = (vault_path or "").strip() or (get_vault_path() or "")
    if not vault:
        typer.echo("No vault path configured. Run: rebalance config set-vault-path <path>", err=True)
        raise typer.Exit(1)
    vp = Path(vault).expanduser().resolve()
    if not vp.exists():
        typer.echo(f"Vault path does not exist: {vp}", err=True)
        raise typer.Exit(1)

    # 2. Token — persist into config if it only resolves via gh/env, so the
    #    launchd sync jobs (which run with a minimal environment) can reach it.
    token, source = get_github_token_with_source()
    if not token:
        typer.echo(
            "No GitHub token configured. Run: rebalance config set-github-token", err=True
        )
        raise typer.Exit(1)
    if source != "config":
        set_github_token(token)
        typer.echo(f"Persisted GitHub token to config (was reachable only via '{source}').")
    else:
        typer.echo("GitHub token already stored in config.")

    # 3. Discover candidates.
    registry_path = vp / "Projects" / "00-project-registry.md"
    typer.echo("Discovering project candidates from vault + GitHub activity...")
    discovery = discover_candidates(
        vault_path=vp, registry_path=registry_path, github_token=token
    )
    if getattr(discovery, "github_error", None):
        typer.echo(f"  ! GitHub discovery error: {discovery.github_error}", err=True)

    candidates = [
        c
        for bucket in (
            discovery.most_likely_active_projects,
            discovery.semi_active_projects,
            discovery.dormant_projects,
        )
        for c in bucket
    ]
    if not candidates:
        typer.echo("No GitHub-active project candidates found — nothing to register.")
        raise typer.Exit(0)

    def _as_dict(c: Any) -> dict[str, Any]:
        return asdict(c) if is_dataclass(c) else dict(c)

    # 4. Select which to register.
    if yes:
        chosen = candidates
    else:
        import questionary

        active_names = {_as_dict(c)["name"] for c in discovery.most_likely_active_projects}
        picked = questionary.checkbox(
            "Select projects to register (space to toggle, enter to confirm):",
            choices=[
                questionary.Choice(
                    _as_dict(c)["name"], checked=_as_dict(c)["name"] in active_names
                )
                for c in candidates
            ],
        ).ask()
        if picked is None:
            typer.echo("Cancelled.")
            raise typer.Exit(1)
        chosen = [c for c in candidates if _as_dict(c)["name"] in set(picked)]
    if not chosen:
        typer.echo("No projects selected — nothing to register.")
        raise typer.Exit(0)

    # 5. Register.
    projects = [
        {
            "name": d["name"],
            "status": "active",
            "summary": d.get("summary", ""),
            "repos": d.get("repos", []),
            "priority_tier": d.get("priority_tier") or 3,
            "tags": d.get("tags", []),
        }
        for d in (_as_dict(c) for c in chosen)
    ]
    try:
        db = database or resolve_database_path()
    except DatabaseNotFoundError:
        db = canonical_database_path()
    result = confirm_and_write(
        projects=projects,
        vault_path=vp,
        registry_path=registry_path,
        projects_yaml_path=vp / "projects.yaml",
        database_path=db,
    )
    typer.echo(
        f"Registered {result.project_count} project(s) -> {result.registry_path}"
    )

    # 6. Initial refresh.
    if skip_refresh:
        typer.echo("Skipped initial refresh (--skip-refresh). Run `rebalance refresh` later.")
    else:
        typer.echo("Running initial data refresh (this can take a few minutes)...")
        refresh = refresh_index(db, scope=["all"])
        errors = refresh.get("errors", [])
        if errors:
            typer.echo(f"  Refresh finished with {len(errors)} error(s):", err=True)
            for e in errors:
                typer.echo(f"    - {e.get('scope')}: {e.get('error')}", err=True)
        else:
            typer.echo("Initial refresh complete.")

    typer.echo("\nOnboarding done. Run `rebalance doctor` to verify the install.")


@app.command("refresh")
def refresh_cmd(
    publish: bool = typer.Option(
        True,
        "--publish/--no-publish",
        help="Render the markdown pulse and push to the configured private repo "
             "(gated on content change). Use --no-publish to skip the remote push.",
    ),
    pulse_web: bool = typer.Option(
        True,
        "--pulse-web/--no-pulse-web",
        help="Regenerate the local web/pulse.html mirror.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON instead of a status table."),
    database: Path | None = typer.Option(
        None,
        "--database",
        "-d",
        help="Override the resolved REBALANCE_DB path for this run.",
    ),
) -> None:
    """Run the full refresh pipeline that the four launchd jobs collectively do.

    Steps, each independently guarded so one failure does not abort the rest:

    1. ``refresh_index(scope=["all"])`` — vault, github (incl. pushed-repo
       auto-discovery), calendar, sleuth, unified semantic index.
    2. Regenerate ``web/pulse.html`` from the now-fresh DB (atomic
       tmp+replace; same renderer the 30-min launchd job uses).
    3. Render the markdown pulse and push it to your private pulse repo,
       gated on content change. Skip with ``--no-publish``.
    """
    import json as _json
    import time as _time

    from rebalance.ingest.index_ops import refresh_index

    db_path = resolve_database_path(database)
    started = _time.monotonic()

    summary: dict[str, Any] = {
        "database": str(db_path),
        "steps": [],
    }

    # ---- Step 1: refresh_index(all) ----
    step_started = _time.monotonic()
    try:
        index_result = refresh_index(db_path, scope=["all"])
        step_record = {
            "name": "refresh_index",
            "ok": not bool(index_result.get("errors")),
            "elapsed_seconds": round(_time.monotonic() - step_started, 2),
            "errors": index_result.get("errors") or [],
            "result": index_result,
        }
    except Exception as exc:
        step_record = {
            "name": "refresh_index",
            "ok": False,
            "elapsed_seconds": round(_time.monotonic() - step_started, 2),
            "errors": [f"{type(exc).__name__}: {exc}"],
            "result": None,
        }
    summary["steps"].append(step_record)

    # ---- Step 2: web/pulse.html ----
    if pulse_web:
        step_started = _time.monotonic()
        try:
            from rebalance.ingest.config import get_vault_path
            # pulse_web.py lives in scripts/, not in the package. Import via path.
            import importlib.util as _importlib_util
            pulse_web_path = _PROJECT_ROOT / "scripts" / "pulse_web.py"
            spec = _importlib_util.spec_from_file_location("rebalance_pulse_web", pulse_web_path)
            assert spec and spec.loader, f"could not load {pulse_web_path}"
            mod = _importlib_util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            vault_path = get_vault_path()
            goals_path = (Path(vault_path) / "0. Goals.md") if vault_path else None
            out_path = _PROJECT_ROOT / "web" / "pulse.html"
            if goals_path and goals_path.exists():
                mod.write_page(out_path, goals_path=goals_path, vault_path=Path(vault_path) if vault_path else None, refresh_seconds=30)
                step_record = {
                    "name": "pulse_web",
                    "ok": True,
                    "elapsed_seconds": round(_time.monotonic() - step_started, 2),
                    "output_path": str(out_path),
                }
            else:
                step_record = {
                    "name": "pulse_web",
                    "ok": False,
                    "elapsed_seconds": round(_time.monotonic() - step_started, 2),
                    "errors": [f"goals file not found: {goals_path}"] if goals_path else ["vault_path not configured"],
                }
        except Exception as exc:
            step_record = {
                "name": "pulse_web",
                "ok": False,
                "elapsed_seconds": round(_time.monotonic() - step_started, 2),
                "errors": [f"{type(exc).__name__}: {exc}"],
            }
        summary["steps"].append(step_record)
    else:
        summary["steps"].append({"name": "pulse_web", "ok": True, "skipped": True})

    # ---- Step 3: publish_pulse (markdown → private repo) ----
    if publish:
        step_started = _time.monotonic()
        try:
            from rebalance.ingest.pulse import publish_pulse as _publish_pulse
            publish_result = _publish_pulse(db_path, dry_run=False, push=True)
            step_record = {
                "name": "publish_pulse",
                "ok": bool(publish_result.get("ok", True)) and not publish_result.get("error"),
                "elapsed_seconds": round(_time.monotonic() - step_started, 2),
                "result": publish_result,
            }
            if publish_result.get("error"):
                step_record["errors"] = [publish_result["error"]]
        except Exception as exc:
            step_record = {
                "name": "publish_pulse",
                "ok": False,
                "elapsed_seconds": round(_time.monotonic() - step_started, 2),
                "errors": [f"{type(exc).__name__}: {exc}"],
            }
        summary["steps"].append(step_record)
    else:
        summary["steps"].append({"name": "publish_pulse", "ok": True, "skipped": True})

    summary["total_elapsed_seconds"] = round(_time.monotonic() - started, 2)
    summary["ok"] = all(s.get("ok", False) for s in summary["steps"])

    if json_output:
        typer.echo(_json.dumps(summary, indent=2, default=str))
        raise typer.Exit(0 if summary["ok"] else 1)

    # Human-readable rendering
    from rich.console import Console
    from rich.table import Table

    console = Console()
    console.print(
        f"[bold]rebalance refresh[/bold] · db=[dim]{db_path}[/dim] · "
        f"{summary['total_elapsed_seconds']}s total"
    )
    table = Table(show_header=True, header_style="bold")
    table.add_column("step", no_wrap=True)
    table.add_column("status", no_wrap=True, justify="center", width=8)
    table.add_column("elapsed", no_wrap=True, justify="right")
    table.add_column("notes", overflow="fold")
    for step in summary["steps"]:
        name = step["name"]
        if step.get("skipped"):
            table.add_row(name, "[dim]skip[/dim]", "-", "[dim]disabled by flag[/dim]")
            continue
        ok = step.get("ok")
        status = "[green]✓[/green]" if ok else "[red]✗[/red]"
        elapsed = f"{step.get('elapsed_seconds', 0):.2f}s"
        notes_parts: list[str] = []
        if step.get("errors"):
            notes_parts.append("[red]" + "; ".join(str(e) for e in step["errors"]) + "[/red]")
        result = step.get("result") or {}
        if name == "refresh_index" and isinstance(result, dict):
            scope_results = result.get("results") or []
            scope_names = sorted(
                {(r.get("scope") or "?") for r in scope_results if isinstance(r, dict)}
            )
            scope_summary = ", ".join(scope_names) if scope_names else "(no scopes)"
            notes_parts.append(f"scopes: {scope_summary}")
        if name == "pulse_web" and step.get("output_path"):
            notes_parts.append(step["output_path"])
        if name == "publish_pulse" and isinstance(result, dict):
            git = result.get("git") or {}
            if git.get("committed"):
                notes_parts.append(f"committed{' + pushed' if git.get('pushed') else ''}")
            elif git.get("unchanged"):
                notes_parts.append("no content change → no commit")
        table.add_row(name, status, elapsed, " · ".join(notes_parts) if notes_parts else "")
    console.print(table)
    raise typer.Exit(0 if summary["ok"] else 1)


@app.command("profile-sync")
def profile_sync_cmd(
    log: Path = typer.Option(
        None,
        "--log",
        help="Specific daily_sync log file to parse. Defaults to the most recent one in temp/logs/.",
    ),
    top: int = typer.Option(0, "--top", help="If >0, show only the slowest N repos."),
) -> None:
    """Show per-repo timings from the most recent GitHub sync.

    Parses the JSON dumped by ``scripts/daily_sync.sh`` so you can see
    which repos dominate the run and where the sync budget goes. Pass
    ``--log`` for a specific log file or ``--top 5`` to see only the
    biggest offenders.
    """
    from rebalance.ingest.profile_sync import render_profile_sync

    exit_code = render_profile_sync(
        project_root=_PROJECT_ROOT,
        log_override=log,
        top_n=top if top > 0 else None,
    )
    if exit_code:
        raise typer.Exit(exit_code)

CALENDAR_EVENT_LOG_PATH = Path("temp/logs/calendar-event-create.jsonl")

# Secret env files resolve via rebalance.paths.resolve_secret_path which honors
# REBALANCE_SECRETS_DIR, ~/.config/rebalance-os/config.json (set via
# `rebalance config set-secrets-dir`), and ~/secrets as the legacy default.
# TODO: support sleuth-web-api-production.env once a prod Sleuth deployment
# exists — likely via a --env name|production|development flag.

# Module-level paths for operator env files. Resolved at import time so tests
# can patch `rebalance.cli.GOOGLE_CALENDAR_ENV_PATH` / `rebalance.cli.SLEUTH_ENV_PATH`
# to redirect subsequent reads without monkey-patching the resolver itself.
GOOGLE_CALENDAR_ENV_PATH = resolve_secret_path("google-calendar.env")
SLEUTH_ENV_PATH = resolve_secret_path("sleuth-web-api-development.env")


def _load_google_calendar_env() -> dict[str, str]:
    """Load shared Google Calendar env metadata from the operator-owned file."""
    # Read the module-level binding at call time so test patches take effect.
    path = GOOGLE_CALENDAR_ENV_PATH
    if not path.exists():
        raise typer.BadParameter(f"Google Calendar env file not found: {path}")

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _load_sleuth_env(which: str = "production") -> dict[str, str]:
    """Load Sleuth Web API connection details from the operator-owned env file.

    Looks up `sleuth-web-api-{which}.env` (default: production). Falls back to
    the development env file if the requested one doesn't exist — keeps the
    older dev-only setup working until production is configured.
    """
    primary = resolve_secret_path(f"sleuth-web-api-{which}.env")
    fallback = resolve_secret_path("sleuth-web-api-development.env")
    if primary.exists():
        path = primary
    elif fallback.exists():
        path = fallback
    else:
        raise typer.BadParameter(
            f"Sleuth env file not found: tried {primary} then {fallback}"
        )

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()

    required = ("SLEUTH_WEB_API_BASE_URL", "SLEUTH_WEB_API_TOKEN", "SLEUTH_WORKSPACE_NAME")
    missing = [k for k in required if not values.get(k)]
    if missing:
        raise typer.BadParameter(
            f"Sleuth env file missing required keys: {', '.join(missing)} "
            f"(expected in {path})"
        )
    return values


def _load_calendar_credentials_from_env(env_data: dict[str, str]) -> object:
    """Load the pickled Google OAuth credentials referenced by the shared env file."""
    token_path_str = env_data.get("GOOGLE_CALENDAR_TOKEN_PATH", "").strip()
    if not token_path_str:
        raise typer.BadParameter(
            f"GOOGLE_CALENDAR_TOKEN_PATH is missing in {GOOGLE_CALENDAR_ENV_PATH}"
        )

    token_path = Path(token_path_str).expanduser()
    if not token_path.exists():
        raise typer.BadParameter(f"Google Calendar token not found: {token_path}")

    with open(token_path, "rb") as token_file:
        return pickle.load(token_file)


def _require_calendar_write_scope(env_data: dict[str, str]) -> object:
    """Validate that the current token already includes the required write scope."""
    creds = _load_calendar_credentials_from_env(env_data)
    required_scope = env_data.get("GOOGLE_CALENDAR_REQUIRED_WRITE_SCOPE", "").strip()
    current_scopes = set(getattr(creds, "scopes", []) or [])

    if required_scope and required_scope not in current_scopes:
        reauth_command = env_data.get("GOOGLE_CALENDAR_REAUTH_COMMAND", "").strip()
        message = [
            "Google Calendar token is missing the required write scope.",
            f"Required: {required_scope}",
            f"Current: {sorted(current_scopes)}",
        ]
        if reauth_command:
            message.append(f"Reauthorize with: {reauth_command}")
        raise typer.BadParameter("\n".join(message))

    return creds


def _resolve_calendar_event_window(
    *,
    date_str: str,
    start_time: str,
    end_time: str,
    timezone_name: str,
) -> tuple[str, str, str]:
    """Resolve either an all-day date or explicit start/end datetimes."""
    if date_str and (start_time or end_time):
        raise typer.BadParameter("Use either --date or --start/--end, not both.")

    if date_str:
        target_date = date_cls.fromisoformat(date_str)
        tz = ZoneInfo(timezone_name)
        start_dt = datetime.combine(target_date, time_cls.min, tzinfo=tz)
        end_dt = datetime.combine(target_date + timedelta(days=1), time_cls.min, tzinfo=tz)
        return start_dt.isoformat(), end_dt.isoformat(), timezone_name

    if bool(start_time) != bool(end_time):
        raise typer.BadParameter("--start and --end must be provided together.")
    if not start_time or not end_time:
        raise typer.BadParameter("Provide either --date or both --start and --end.")

    try:
        start_dt = datetime.fromisoformat(start_time)
        end_dt = datetime.fromisoformat(end_time)
    except ValueError as exc:
        raise typer.BadParameter(f"Invalid datetime: {exc}") from exc

    if start_dt.tzinfo is None or end_dt.tzinfo is None:
        raise typer.BadParameter("--start and --end must include timezone offsets.")
    if end_dt <= start_dt:
        raise typer.BadParameter("--end must be after --start.")

    return start_dt.isoformat(), end_dt.isoformat(), timezone_name


def _build_calendar_event_payload(
    *,
    title: str,
    start_iso: str,
    end_iso: str,
    description: str,
    location: str,
    attendees: list[str],
    calendar_id: str,
    timezone_name: str,
) -> dict[str, object]:
    """Build the normalized payload for create_calendar_event."""
    return {
        "calendar_id": calendar_id,
        "summary": title.strip(),
        "start_time": start_iso,
        "end_time": end_iso,
        "timezone_name": timezone_name,
        "description": description,
        "location": location,
        "attendees": [email.strip() for email in attendees if email.strip()],
    }


def _find_logged_dedupe_hit(dedupe_key: str) -> dict[str, object] | None:
    """Return the most recent logged record for a dedupe key, if present."""
    if not dedupe_key or not CALENDAR_EVENT_LOG_PATH.exists():
        return None

    for raw_line in reversed(CALENDAR_EVENT_LOG_PATH.read_text(encoding="utf-8").splitlines()):
        line = raw_line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("dedupe_key") == dedupe_key:
            return record
    return None


def _append_calendar_event_log(record: dict[str, object]) -> None:
    """Append one structured calendar-create record to the local JSONL log."""
    CALENDAR_EVENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CALENDAR_EVENT_LOG_PATH, "a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(record, ensure_ascii=False) + "\n")


def _resolve_github_repos(database_path: Path, repos: list[str]) -> list[str]:
    """Use explicit --repo values or fall back to active project registry repos."""
    ignored = set(get_github_ignored_repos())
    normalized = [repo.strip() for repo in repos if repo.strip()]
    if normalized:
        explicit = [normalize_github_repo_name(repo) for repo in normalized]
        ignored_explicit = [repo for repo in explicit if repo in ignored]
        if ignored_explicit:
            typer.echo(f"GitHub repo is ignored: {', '.join(ignored_explicit)}")
            raise typer.Exit(code=2)
        return sorted(set(normalized))

    from rebalance.ingest.registry import get_projects

    discovered: list[str] = []
    if database_path.exists():
        for project in get_projects(database_path, status="active"):
            discovered.extend(project.get("repos") or [])

    unique = sorted(
        {
            repo.strip()
            for repo in discovered
            if repo and repo.strip() and normalize_github_repo_name(repo) not in ignored
        }
    )
    if unique:
        return unique

    raise typer.BadParameter(
        "No eligible GitHub repos provided. Pass --repo owner/name or sync the project registry first."
    )


def _format_purge_counts(row_counts: dict[str, int]) -> str:
    parts = [f"{name}={count}" for name, count in row_counts.items() if count]
    return ", ".join(parts) if parts else "no matching rows"


def _normalize_semantic_sources_option(values: list[str]) -> list[str]:
    """Normalize repeatable --source flags for unified semantic commands."""
    normalized = [value.strip().lower() for value in values if value.strip()]
    if not normalized or "all" in normalized:
        return ["vault", "github"]
    allowed = {"vault", "github", "calendar", "sleuth"}
    invalid = [value for value in normalized if value not in allowed]
    if invalid:
        raise typer.BadParameter(
            f"Unsupported --source value(s): {', '.join(sorted(set(invalid)))}. "
            "Use vault, github, calendar, sleuth, or all."
        )
    deduped: list[str] = []
    for value in normalized:
        if value not in deduped:
            deduped.append(value)
    return deduped


def _find_existing_calendar_event(payload: dict[str, object]) -> dict[str, str] | None:
    """Search for an existing event with the same title and same start date."""
    from rebalance.ingest.calendar import CALENDAR_WRITE_SCOPE, _build_service

    summary = str(payload["summary"])
    start_iso = str(payload["start_time"])
    end_iso = str(payload["end_time"])
    target_date = start_iso[:10]

    service = _build_service(required_scopes=[CALENDAR_WRITE_SCOPE])
    result = (
        service.events()
        .list(
            calendarId=str(payload["calendar_id"]),
            q=summary,
            timeMin=start_iso,
            timeMax=end_iso,
            singleEvents=True,
            orderBy="startTime",
            maxResults=25,
        )
        .execute()
    )

    for event in result.get("items", []):
        event_summary = event.get("summary", "")
        event_start = event.get("start", {}).get("dateTime", event.get("start", {}).get("date", ""))
        if event_summary == summary and event_start[:10] == target_date:
            return {
                "event_id": event.get("id", ""),
                "html_link": event.get("htmlLink", ""),
                "summary": event_summary,
                "start_time": event_start,
            }
    return None


def _emit_calendar_create_result(output_format: str, data: dict[str, object]) -> None:
    """Emit calendar-create result in plain text or JSON."""
    if output_format == "json":
        typer.echo(json.dumps(data, ensure_ascii=False))
        return

    status = str(data.get("status", ""))
    if status == "created":
        typer.echo(f"Created event: {data.get('event_id', '')}")
        typer.echo(f"Link: {data.get('html_link', '')}")
    elif status == "idempotency_hit":
        typer.echo(f"Idempotency hit for dedupe key: {data.get('dedupe_key', '')}")
        if data.get("event_id"):
            typer.echo(f"Existing event: {data['event_id']}")
        if data.get("html_link"):
            typer.echo(f"Link: {data['html_link']}")
    elif status in {"skipped_existing", "blocked_duplicate"}:
        typer.echo(f"Matching event already exists: {data.get('event_id', '')}")
        if data.get("html_link"):
            typer.echo(f"Link: {data['html_link']}")


@ingest_app.command("preflight")
def ingest_preflight(
    vault: Path = typer.Option(..., exists=True, file_okay=False, dir_okay=True, help="Path to Obsidian vault"),
    registry: Path = typer.Option(
        Path("Projects/00-project-registry.md"),
        help="Registry file path (relative to vault unless absolute)",
    ),
    non_interactive: bool = typer.Option(False, help="Skip prompts and apply defaults"),
    include_github: bool = typer.Option(False, help="Scan GitHub activity for repo discovery"),
    github_days: int = typer.Option(14, help="Days back to scan GitHub (max ~14)"),
) -> None:
    """Discover potential projects from vault page titles and optional GitHub activity."""
    registry_path = registry if registry.is_absolute() else vault / registry

    github_token = None
    if include_github:
        github_token = get_github_token()
        if not github_token:
            typer.echo(
                f"⚠ GitHub PAT not configured. Set it with:\n"
                f"  rebalance config set-github-token <PAT>"
            )
            raise typer.Exit(code=1)

    result = run_preflight(
        vault_path=vault,
        registry_path=registry_path,
        non_interactive=non_interactive,
        github_token=github_token,
        github_days=github_days,
    )
    typer.echo(
        f"Preflight complete: scanned={result.scanned_files}, "
        f"new_candidates={result.new_candidates}, curated={result.curated_candidates}"
    )


@ingest_app.command("sync")
def ingest_sync(
    mode: str = typer.Option("pull", help="Sync mode: pull | push | check"),
    vault: Path = typer.Option(..., exists=True, file_okay=False, dir_okay=True, help="Path to Obsidian vault"),
    registry: Path = typer.Option(
        Path("Projects/00-project-registry.md"),
        help="Registry file path (relative to vault unless absolute)",
    ),
    projects_yaml: Path = typer.Option(Path("projects.yaml"), help="Projection YAML output path"),
    database: Path = typer.Option(Path("rebalance.db"), help="SQLite database output path"),
) -> None:
    """Sync canonical Markdown registry with projections and database."""
    registry_path = registry if registry.is_absolute() else vault / registry
    projects_path = projects_yaml if projects_yaml.is_absolute() else vault / projects_yaml
    database_path = database if database.is_absolute() else vault / database

    summary = sync_registry(mode=mode, registry_path=registry_path, projects_yaml_path=projects_path, database_path=database_path)
    typer.echo(summary)


@ingest_app.command("infer-project-registry")
def ingest_infer_project_registry(
    database: Path | None = DBOption(),
    calendar_days_back: int = typer.Option(90, help="How many calendar days back to use for inference"),
    calendar_days_forward: int = typer.Option(14, help="How many calendar days forward to include for meeting signals"),
    dry_run: bool = typer.Option(False, help="Preview inferred project rows without writing to project_registry"),
) -> None:
    """Infer project_registry rows from the current GitHub and Calendar activity in SQLite."""
    from rebalance.ingest.calendar_config import CalendarConfig
    from rebalance.ingest.project_inference import infer_project_registry, sync_inferred_project_registry

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    config = CalendarConfig.load()

    if dry_run:
        projects, summary = infer_project_registry(
            db_path,
            calendar_config=config,
            calendar_days_back=calendar_days_back,
            calendar_days_forward=calendar_days_forward,
        )
        typer.echo(
            f"Dry run: inferred={summary.inferred_count}, github_backed={summary.github_backed_count}, "
            f"calendar_only={summary.calendar_only_count}"
        )
        for project in projects:
            repo_count = len(project["repos"])
            typer.echo(
                f"  {project['name']} [{project['status']}] repos={repo_count} "
                f"tags={','.join(project['tags'])}"
            )
        return

    summary = sync_inferred_project_registry(
        db_path,
        calendar_config=config,
        calendar_days_back=calendar_days_back,
        calendar_days_forward=calendar_days_forward,
    )
    typer.echo(
        f"Inferred project registry: inferred={summary.inferred_count}, updated={summary.updated_count}, "
        f"github_backed={summary.github_backed_count}, calendar_only={summary.calendar_only_count}, "
        f"deleted_stale={summary.deleted_stale_inferred_count}"
    )
    for name in summary.project_names:
        typer.echo(f"  {name}")


@app.command("github-scan")
def github_scan(
    token: str = typer.Option(..., envvar="GITHUB_TOKEN", help="GitHub Personal Access Token"),
    days: int = typer.Option(30, help="Number of days to look back (supports 30-day A/B/C band classification)"),
    database: Path | None = DBOption(),
) -> None:
    """Fetch GitHub activity and persist to database for use by github_balance MCP tool."""
    from rebalance.ingest.github_scan import (
        filter_ignored_repo_activity,
        scan_github,
        upsert_github_activity,
    )

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    typer.echo(f"Scanning GitHub activity for last {days} days...")
    result = scan_github(token=token, days=days)
    skipped_repos = filter_ignored_repo_activity(result, get_github_ignored_repos())
    upsert_github_activity(db_path, result)
    typer.echo(
        f"Done: login={result.login}, events={result.total_events}, "
        f"repos={len(result.repo_activity)}, skipped={len(skipped_repos)}, stored to {db_path}"
    )


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
            try:
                last_active_map[repo] = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except (AttributeError, ValueError):
                continue

    items: list[dict[str, Any]] = []
    counts = {"captured": 0, "pending": 0}

    for repo in top_repos:
        for event in _raw_fetch_repo_events(repo, token):
            try:
                event_time = datetime.fromisoformat((event.get("created_at") or "").replace("Z", "+00:00"))
            except ValueError:
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
        try:
            pushed = datetime.fromisoformat(rec.pushed_at.replace("Z", "+00:00"))
        except ValueError:
            continue
        if pushed < cutoff:
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
        try:
            t = datetime.fromisoformat((e.get("created_at") or "").replace("Z", "+00:00"))
        except ValueError:
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
        try:
            last_active_map[repo] = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (AttributeError, ValueError):
            continue

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
        local_time = datetime.fromisoformat(ev["time"]).astimezone().strftime("%H:%M:%S")
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
                local_time = datetime.fromisoformat(ev["time"]).astimezone().strftime("%H:%M:%S")
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
            pushed = datetime.fromisoformat(r["pushed_at"])
            delta = now_utc - pushed
            if delta.days > 0:
                ago = f"{delta.days}d ago"
            elif delta.seconds >= 3600:
                ago = f"{delta.seconds // 3600}h ago"
            else:
                ago = f"{max(1, delta.seconds // 60)}m ago"
            flags = []
            if r.get("private"): flags.append("private")
            if r.get("fork"): flags.append("fork")
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


@app.command("github-sync-artifacts")
def github_sync_artifacts(
    repos: list[str] = typer.Option(
        [],
        "--repo",
        help="GitHub repo in owner/name form. Repeat the flag to sync multiple repos.",
    ),
    token: str = typer.Option("", envvar="GITHUB_TOKEN", help="GitHub Personal Access Token"),
    days: int = typer.Option(90, help="Lookback window for changed issues and PRs"),
    database: Path | None = DBOption(),
) -> None:
    """Sync detailed GitHub issues, PRs, comments, reviews, checks, and releases."""
    from rebalance.ingest.github_knowledge import sync_github_repo

    # When the caller pins explicit --repo values, validate them against the
    # ignored list BEFORE resolving the DB. Catches "you told me to sync an
    # ignored repo" with the right error, instead of letting a missing DB
    # mask the misuse.
    normalized_explicit = [r.strip() for r in (repos or []) if r.strip()]
    if normalized_explicit:
        explicit_normalized = [normalize_github_repo_name(r) for r in normalized_explicit]
        ignored = set(get_github_ignored_repos())
        ignored_explicit = [r for r in explicit_normalized if r in ignored]
        if ignored_explicit:
            typer.echo(f"GitHub repo is ignored: {', '.join(ignored_explicit)}")
            raise typer.Exit(code=2)

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    target_repos = _resolve_github_repos(db_path, repos or [])
    resolved_token = token.strip() or (get_github_token() or "")
    if not resolved_token:
        raise typer.BadParameter(
            "GitHub token not configured. Use --token, GITHUB_TOKEN, or `rebalance config set-github-token`."
        )

    for repo in target_repos:
        typer.echo(f"Syncing GitHub artifacts for {repo} ({days} days)...")
        result = sync_github_repo(
            database_path=db_path,
            repo_full_name=repo,
            token=resolved_token,
            since_days=days,
        )
        typer.echo(
            f"  synced branches={result.branches_synced}, issues={result.issues_synced}, prs={result.prs_synced}, "
            f"comments={result.comments_synced}, commits={result.commits_synced}, "
            f"checks={result.checks_synced}, docs={result.docs_built} "
            f"({result.elapsed_seconds}s)"
        )


@app.command("github-embed")
def github_embed(
    database: Path | None = DBOption(),
    model: str = typer.Option("Qwen/Qwen3-Embedding-0.6B", help="HuggingFace model name"),
    batch_size: int = typer.Option(32, help="Batch size for embedding"),
    min_chars: int = typer.Option(40, help="Minimum document length to embed"),
    force: bool = typer.Option(False, help="Force re-embed all GitHub documents"),
) -> None:
    """Generate embeddings for the local GitHub artifact corpus."""
    from rebalance.ingest.github_knowledge import embed_github_documents

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    typer.echo(f"Embedding GitHub documents with {model} (batch_size={batch_size})...")
    result = embed_github_documents(
        database_path=db_path,
        model_name=model,
        batch_size=batch_size,
        min_chars=min_chars,
        force_reembed=force,
    )
    typer.echo(
        f"GitHub embed complete: embedded={result.embedded_docs}, "
        f"skipped={result.skipped_unchanged}, total_docs={result.total_docs}, "
        f"model={result.model_name}, dim={result.embedding_dim} "
        f"({result.elapsed_seconds}s)"
    )


@ingest_app.command("notes")
def ingest_notes(
    vault: Path = typer.Option(..., exists=True, file_okay=False, dir_okay=True, help="Path to Obsidian vault"),
    database: Path | None = DBOption(),
    exclude: list[str] = typer.Option(
        [".obsidian/*", ".trash/*", "node_modules/*", ".git/*", ".venv/*", "*/.venv/*"],
        help="Glob patterns to exclude",
    ),
    dry_run: bool = typer.Option(False, help="Show what would be ingested without writing"),
) -> None:
    """Ingest Obsidian vault notes into SQLite (parse, chunk, extract keywords/links)."""
    from rebalance.ingest.note_ingester import ingest_vault

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    result = ingest_vault(
        vault_path=vault,
        database_path=db_path,
        exclude_patterns=exclude,
        dry_run=dry_run,
    )
    typer.echo(
        f"Ingest {'(dry-run) ' if dry_run else ''}complete: "
        f"total={result.total_files}, new={result.new_files}, "
        f"updated={result.updated_files}, unchanged={result.unchanged_files}, "
        f"deleted={result.deleted_files}, chunks={result.total_chunks}, "
        f"keywords={result.total_keywords}, links={result.total_links} "
        f"({result.elapsed_seconds}s)"
    )


@ingest_app.command("embed")
def ingest_embed(
    database: Path | None = DBOption(),
    model: str = typer.Option("Qwen/Qwen3-Embedding-0.6B", help="HuggingFace model name"),
    batch_size: int = typer.Option(32, help="Batch size for embedding (lower = less memory)"),
    force: bool = typer.Option(False, help="Force re-embed all chunks (use after model change)"),
) -> None:
    """Generate embeddings for ingested chunks via mlx-embeddings."""
    from rebalance.ingest.embedder import embed_chunks

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    typer.echo(f"Embedding chunks with {model} (batch_size={batch_size})...")
    result = embed_chunks(
        database_path=db_path,
        model_name=model,
        batch_size=batch_size,
        force_reembed=force,
    )
    typer.echo(
        f"Embed complete: embedded={result.embedded_chunks}, "
        f"skipped={result.skipped_unchanged}, total_chunks={result.total_chunks}, "
        f"model={result.model_name}, dim={result.embedding_dim} "
        f"({result.elapsed_seconds}s)"
    )


@app.command("query")
def query_cmd(
    text: str = typer.Argument(..., help="Natural language query"),
    database: Path | None = DBOption(),
    top_k: int = typer.Option(10, help="Number of results to return"),
    model: str = typer.Option("Qwen/Qwen3-Embedding-0.6B", help="Embedding model for query"),
) -> None:
    """Semantic search over vault notes."""
    from rebalance.ingest.embedder import query_similar

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    results = query_similar(database_path=db_path, query_text=text, model_name=model, top_k=top_k)
    if not results:
        typer.echo("No results found. Run `rebalance ingest notes` and `rebalance ingest embed` first.")
        return
    for i, r in enumerate(results, 1):
        heading = f" > {r['heading']}" if r["heading"] else ""
        typer.echo(f"{i}. [{r['similarity_score']:.3f}] {r['title']}{heading}")
        typer.echo(f"   {r['file_path']}")
        typer.echo(f"   {r['body_preview'][:120]}...")
        typer.echo()


@app.command("github-query")
def github_query_cmd(
    text: str = typer.Argument(..., help="Natural language query"),
    database: Path | None = DBOption(),
    repo: str = typer.Option("", help="Optional owner/name repo filter"),
    top_k: int = typer.Option(8, help="Number of results to return"),
    model: str = typer.Option("Qwen/Qwen3-Embedding-0.6B", help="Embedding model for query"),
) -> None:
    """Semantic search over the local GitHub issue/PR/comment corpus."""
    from rebalance.ingest.github_knowledge import query_github_documents

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    results = query_github_documents(
        database_path=db_path,
        query_text=text,
        repo_full_name=repo,
        top_k=top_k,
        model_name=model,
    )
    if not results:
        typer.echo(
            "No GitHub results found. Run `rebalance github-sync-artifacts` and "
            "`rebalance github-embed` first."
        )
        return
    for i, result in enumerate(results, 1):
        labels = f" [{', '.join(result['labels'])}]" if result["labels"] else ""
        milestone = f" milestone={result['milestone_title']}" if result["milestone_title"] else ""
        state = f" state={result['state']}" if result["state"] else ""
        typer.echo(
            f"{i}. [{result['similarity_score']:.3f}] {result['repo_full_name']} "
            f"{result['source_type']} #{result['source_number']} {result['doc_type']}{labels}{state}{milestone}"
        )
        typer.echo(f"   {result['title']}")
        if result["html_url"]:
            typer.echo(f"   {result['html_url']}")
        typer.echo(f"   {result['body_preview'][:180]}...")
        typer.echo()


@app.command("semantic-backfill")
def semantic_backfill_cmd(
    source: list[str] = typer.Option(
        ["all"],
        "--source",
        help="Source family to backfill. Repeat for multiple values.",
    ),
    repo: str = typer.Option(
        "",
        "--repo",
        help="Optional owner/name filter when backfilling GitHub semantic documents.",
    ),
    database: Path | None = DBOption(),
) -> None:
    """Populate the unified semantic document layer from existing source tables."""
    from rebalance.ingest.semantic_index import backfill_semantic_documents

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    sources = _normalize_semantic_sources_option(source)
    typer.echo(f"Backfilling semantic documents for {', '.join(sources)}...")
    result = backfill_semantic_documents(
        database_path=db_path,
        source_types=sources,
        repo_full_name=repo,
    )
    typer.echo(
        f"Semantic backfill complete: inserted={result.inserted_count}, "
        f"updated={result.updated_count}, unchanged={result.unchanged_count}, "
        f"deleted={result.deleted_count}, total_scanned={result.total_documents} "
        f"({result.elapsed_seconds}s)"
    )


@app.command("semantic-embed")
def semantic_embed_cmd(
    source: list[str] = typer.Option(
        ["all"],
        "--source",
        help="Source family to embed. Repeat for multiple values.",
    ),
    database: Path | None = DBOption(),
    model: str = typer.Option("Qwen/Qwen3-Embedding-0.6B", help="HuggingFace model name"),
    batch_size: int = typer.Option(32, help="Batch size for embedding"),
    min_chars: int = typer.Option(1, help="Minimum document length to embed"),
    force: bool = typer.Option(False, help="Force re-embed matching semantic documents"),
) -> None:
    """Generate embeddings for the unified semantic document layer."""
    from rebalance.ingest.semantic_index import embed_pending

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    sources = _normalize_semantic_sources_option(source)
    typer.echo(
        f"Embedding semantic documents for {', '.join(sources)} with {model} "
        f"(batch_size={batch_size})..."
    )
    result = embed_pending(
        database_path=db_path,
        source_types=sources,
        model_name=model,
        batch_size=batch_size,
        min_chars=min_chars,
        force_reembed=force,
    )
    typer.echo(
        f"Semantic embed complete: embedded={result.embedded_docs}, "
        f"skipped={result.skipped_unchanged}, total_docs={result.total_docs}, "
        f"model={result.model_name}, dim={result.embedding_dim} "
        f"({result.elapsed_seconds}s)"
    )


@app.command("semantic-query")
def semantic_query_cmd(
    text: str = typer.Argument(..., help="Natural language query"),
    source: list[str] = typer.Option(
        ["all"],
        "--source",
        help="Source family to search. Repeat for multiple values.",
    ),
    database: Path | None = DBOption(),
    top_k: int = typer.Option(10, help="Number of results to return"),
    model: str = typer.Option("Qwen/Qwen3-Embedding-0.6B", help="Embedding model for query"),
) -> None:
    """Semantic search over the unified semantic index."""
    from rebalance.ingest.semantic_index import query

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    sources = _normalize_semantic_sources_option(source)
    results = query(
        database_path=db_path,
        query_text=text,
        top_k=top_k,
        model_name=model,
        source_filter=sources,
    )
    if not results:
        typer.echo(
            "No semantic results found. Run `rebalance semantic-backfill` and "
            "`rebalance semantic-embed` first."
        )
        return
    for i, result in enumerate(results, 1):
        metadata = result["metadata"]
        heading = f" > {metadata.get('heading')}" if metadata.get("heading") else ""
        repo_label = f" {metadata.get('repo_full_name')}" if metadata.get("repo_full_name") else ""
        html_url = metadata.get("html_url") or ""
        typer.echo(
            f"{i}. [{result['similarity_score']:.3f}] {result['source_type']}:{result['doc_kind']}{repo_label}"
        )
        typer.echo(f"   {result['title']}{heading}")
        if metadata.get("file_path"):
            typer.echo(f"   {metadata['file_path']}")
        if html_url:
            typer.echo(f"   {html_url}")
        typer.echo(f"   {result['body_preview'][:180]}...")
        typer.echo()


@app.command("github-release-readiness")
def github_release_readiness_cmd(
    repo: str = typer.Option(..., "--repo", help="Repo in owner/name form"),
    milestone: str = typer.Option("", "--milestone", help="Optional milestone title"),
    database: Path | None = DBOption(),
    output_format: str = typer.Option("text", "--output", help="Output format: text or json"),
) -> None:
    """Infer current release/readiness state from the local GitHub corpus."""
    from rebalance.ingest.github_readiness import infer_github_release_readiness

    normalized_output = output_format.strip().lower()
    if normalized_output not in {"text", "json"}:
        raise typer.BadParameter("--output must be 'text' or 'json'.")

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    result = infer_github_release_readiness(
        database_path=db_path,
        repo_full_name=repo.strip(),
        milestone_title=milestone.strip(),
    )
    data = result.as_dict()
    if normalized_output == "json":
        typer.echo(json.dumps(data, ensure_ascii=False))
        return

    typer.echo(f"Repo:       {result.repo_full_name}")
    typer.echo(f"Milestone:  {result.milestone_title or '(none)'}")
    if result.milestone_due_on:
        typer.echo(f"Due:        {result.milestone_due_on[:10]}")
    typer.echo(f"Status:     {result.status}")
    typer.echo(f"Confidence: {result.confidence:.2f}")
    typer.echo(f"\n{result.summary}")

    if result.blockers:
        typer.echo("\nBlockers:")
        for blocker in result.blockers:
            typer.echo(f"  - {blocker}")

    if result.evidence:
        typer.echo("\nEvidence:")
        for line in result.evidence[:12]:
            typer.echo(f"  - {line}")

    if result.issue_states:
        typer.echo("\nIssue States:")
        for item in result.issue_states[:12]:
            prs = f" prs={','.join(str(n) for n in item.linked_pr_numbers)}" if item.linked_pr_numbers else ""
            typer.echo(f"  - #{item.issue_number} {item.classification}{prs} — {item.title}")


@app.command("github-close-candidates")
def github_close_candidates_cmd(
    repo: str = typer.Option(..., "--repo", help="Repo in owner/name form"),
    database: Path | None = DBOption(),
    output_format: str = typer.Option("text", "--output", help="Output format: text or json"),
) -> None:
    """Suggest open issues that likely map to merged PRs and may be ready to close."""
    from rebalance.ingest.github_reconciliation import infer_issue_pr_close_candidates

    normalized_output = output_format.strip().lower()
    if normalized_output not in {"text", "json"}:
        raise typer.BadParameter("--output must be 'text' or 'json'.")

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    report = infer_issue_pr_close_candidates(
        database_path=db_path,
        repo_full_name=repo.strip(),
    )
    data = report.as_dict()
    if normalized_output == "json":
        typer.echo(json.dumps(data, ensure_ascii=False))
        return

    typer.echo(f"Repo: {report.repo_full_name}")
    typer.echo(report.summary)
    typer.echo(
        "Counts: "
        f"open_issues={report.counts.get('open_issues_considered', 0)}, "
        f"merged_prs={report.counts.get('merged_prs_considered', 0)}, "
        f"high={report.counts.get('high_confidence', 0)}, "
        f"medium={report.counts.get('medium_confidence', 0)}, "
        f"explicit_auto_close={report.counts.get('explicit_auto_close', 0)}"
    )

    if report.high_confidence:
        typer.echo("\nHigh Confidence")
        for item in report.high_confidence[:15]:
            typer.echo(
                f"  - Issue #{item.issue_number} -> PR #{item.pr_number} "
                f"[{item.recommendation}, {item.confidence:.2f}] {item.issue_title}"
            )
            for line in item.evidence[:3]:
                typer.echo(f"      {line}")

    if report.medium_confidence:
        typer.echo("\nMedium Confidence")
        for item in report.medium_confidence[:15]:
            typer.echo(
                f"  - Issue #{item.issue_number} -> PR #{item.pr_number} "
                f"[{item.recommendation}, {item.confidence:.2f}] {item.issue_title}"
            )
            for line in item.evidence[:3]:
                typer.echo(f"      {line}")


@app.command("search")
def search_cmd(
    keyword: str = typer.Argument(..., help="Keyword to search"),
    database: Path | None = DBOption(),
    limit: int = typer.Option(20, help="Max results"),
) -> None:
    """Full-text keyword search over vault files and chunks."""
    from rebalance.ingest.note_ingester import search_by_keyword

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    results = search_by_keyword(database_path=db_path, keyword=keyword, limit=limit)
    if not results:
        typer.echo(f"No results for '{keyword}'. Run `rebalance ingest notes` first.")
        return
    for i, r in enumerate(results, 1):
        heading = f" > {r['heading']}" if r["heading"] else ""
        typer.echo(f"{i}. [{r['keyword_score']:.3f}] {r['title']}{heading}")
        typer.echo(f"   {r['file_path']}")
        typer.echo()


@app.command("ask")
def ask_cmd(
    text: str = typer.Argument(..., help="Natural language question"),
    database: Path | None = DBOption(),
    days: int = typer.Option(7, help="Activity window in days"),
    no_llm: bool = typer.Option(False, help="Skip local LLM synthesis, return raw context only"),
    chat_model: str = typer.Option("Qwen/Qwen3-0.6B", help="Chat model for synthesis"),
) -> None:
    """Ask a natural language question across all data sources."""
    from rebalance.ingest.querier import ask as querier_ask

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    typer.echo(f"Gathering context...")
    result = querier_ask(
        query=text,
        database_path=db_path,
        chat_model=chat_model,
        since_days=days,
        skip_synthesis=no_llm,
    )

    if result.temporal_context:
        today = result.temporal_context.get("today", {})
        tomorrow = result.temporal_context.get("tomorrow", {})
        typer.echo(f"\n--- Schedule ---")
        typer.echo(f"  Today:    {today.get('day_name', '')} — {today.get('day_type', '')}")
        typer.echo(f"  Tomorrow: {tomorrow.get('day_name', '')} — {tomorrow.get('day_type', '')}")

    if result.synthesis:
        typer.echo(f"\n--- Synthesis ({result.model_used}, {result.elapsed_seconds}s) ---\n")
        typer.echo(result.synthesis)
    else:
        typer.echo(f"\n--- Raw context ({result.elapsed_seconds}s) ---\n")

    if result.github_context:
        typer.echo("\n--- GitHub Activity ---")
        for g in result.github_context:
            if g.get("is_idle"):
                typer.echo(f"  {g['project_name']:25s}  IDLE")
            else:
                typer.echo(f"  {g['project_name']:25s}  {g['total_commits']:3d} commits  {g['prs_opened']} PRs  {g['issues_opened']} issues")

    if result.github_semantic_context:
        typer.echo("\n--- Relevant GitHub Artifacts ---")
        for item in result.github_semantic_context[:8]:
            typer.echo(
                f"  {item['repo_full_name']} {item['source_type']} #{item['source_number']} "
                f"[{item['similarity_score']:.3f}] {item['title']}"
            )

    if result.calendar_context:
        upcoming = result.calendar_context.get("upcoming", [])
        if upcoming:
            typer.echo("\n--- Upcoming Calendar ---")
            for e in upcoming[:10]:
                t = e["start_time"][:16].replace("T", " ")
                loc = f"  @ {e['location']}" if e.get("location") else ""
                typer.echo(f"  {t}  {e['summary']}{loc}")

    if result.vault_activity:
        typer.echo("\n--- Recent Vault Notes ---")
        for v in result.vault_activity[:10]:
            typer.echo(f"  {v['last_modified'][:10]}  {v['title']}")


@app.command("calendar-sync")
def calendar_sync_cmd(
    database: Path | None = DBOption(),
    calendar_id: str = typer.Option("", help="Calendar ID or email (default: from config, then 'primary')"),
    days_back: int = typer.Option(30, help="Days back to fetch (use 365 for initial backfill)"),
    days_forward: int = typer.Option(7, help="Days forward to fetch"),
) -> None:
    """Sync Google Calendar events to SQLite for historical queries."""
    from rebalance.ingest.calendar import sync_calendar
    from rebalance.ingest.calendar_config import CalendarConfig

    if not calendar_id:
        config = CalendarConfig.load()
        calendar_id = config.calendar_id

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    typer.echo(f"Syncing calendar '{calendar_id}' ({days_back} days back, {days_forward} days forward)...")
    result = sync_calendar(
        database_path=db_path,
        calendar_id=calendar_id,
        days_back=days_back,
        days_forward=days_forward,
    )
    typer.echo(
        f"Calendar sync complete: fetched={result.events_fetched}, "
        f"stored={result.events_stored}, window={result.window_start}..{result.window_end} "
        f"({result.elapsed_seconds}s)"
    )


@app.command("calendar-create-event")
def calendar_create_event_cmd(
    title: str = typer.Option(..., "--title", help="Event title"),
    date_str: str = typer.Option("", "--date", help="All-day event date (YYYY-MM-DD)"),
    start_time: str = typer.Option("", "--start", help="Start datetime with timezone offset"),
    end_time: str = typer.Option("", "--end", help="End datetime with timezone offset"),
    description: str = typer.Option("", "--description", help="Event description"),
    location: str = typer.Option("", "--location", help="Event location"),
    attendees: list[str] = typer.Option(None, "--attendee", help="Attendee email; repeat the flag to add more"),
    calendar_id: str = typer.Option("primary", "--calendar-id", help="Calendar ID (defaults to primary)"),
    timezone_name: str = typer.Option("America/Los_Angeles", "--timezone", help="IANA timezone for --date payloads"),
    dedupe_key: str = typer.Option("", "--dedupe-key", help="Optional idempotency key checked against the local create-event log"),
    skip_if_exists: bool = typer.Option(False, "--skip-if-exists", help="Return success instead of erroring when a matching event already exists"),
    output_format: str = typer.Option("text", "--output", help="Output format: text or json"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the normalized payload without creating the event"),
) -> None:
    """Create a Google Calendar event from the CLI without needing an MCP host."""
    from rebalance.ingest.calendar import create_calendar_event

    normalized_output_format = output_format.strip().lower()
    if normalized_output_format not in {"text", "json"}:
        raise typer.BadParameter("--output must be 'text' or 'json'.")

    env_data = _load_google_calendar_env()
    _require_calendar_write_scope(env_data)

    start_iso, end_iso, resolved_timezone = _resolve_calendar_event_window(
        date_str=date_str,
        start_time=start_time,
        end_time=end_time,
        timezone_name=timezone_name,
    )

    payload = _build_calendar_event_payload(
        title=title,
        start_iso=start_iso,
        end_iso=end_iso,
        description=description,
        location=location,
        attendees=attendees or [],
        calendar_id=calendar_id,
        timezone_name=resolved_timezone,
    )
    request_id = uuid4().hex
    base_log_record = {
        "timestamp": datetime.now(ZoneInfo("UTC")).isoformat(),
        "request_id": request_id,
        "dedupe_key": dedupe_key.strip(),
        "calendar_id": payload["calendar_id"],
        "summary": payload["summary"],
        "start_time": payload["start_time"],
        "start_date": str(payload["start_time"])[:10],
    }

    if dry_run:
        typer.echo(json.dumps(payload, indent=2))
        return

    normalized_dedupe_key = dedupe_key.strip()
    if normalized_dedupe_key:
        logged_hit = _find_logged_dedupe_hit(normalized_dedupe_key)
        if logged_hit and logged_hit.get("action") in {"created", "skipped_existing", "blocked_duplicate"}:
            emit_data = {
                **base_log_record,
                "status": "idempotency_hit",
                "event_id": logged_hit.get("event_id", ""),
                "html_link": logged_hit.get("html_link", ""),
            }
            _append_calendar_event_log({**emit_data, "action": "idempotency_hit"})
            _emit_calendar_create_result(normalized_output_format, emit_data)
            return

    existing_event = _find_existing_calendar_event(payload)
    if existing_event:
        emit_data = {
            **base_log_record,
            "status": "skipped_existing" if skip_if_exists else "blocked_duplicate",
            "event_id": existing_event["event_id"],
            "html_link": existing_event["html_link"],
        }
        _append_calendar_event_log({**emit_data, "action": emit_data["status"]})
        _emit_calendar_create_result(normalized_output_format, emit_data)
        if not skip_if_exists:
            raise typer.Exit(code=1)
        return

    result = create_calendar_event(
        calendar_id=str(payload["calendar_id"]),
        summary=str(payload["summary"]),
        start_time=str(payload["start_time"]),
        end_time=str(payload["end_time"]),
        timezone_name=str(payload["timezone_name"]),
        description=str(payload["description"]),
        location=str(payload["location"]),
        attendees=list(payload["attendees"]),
    )
    emit_data = {
        **base_log_record,
        "status": "created",
        "event_id": result.event_id,
        "html_link": result.html_link,
    }
    _append_calendar_event_log({**emit_data, "action": "created"})
    _emit_calendar_create_result(normalized_output_format, emit_data)


@app.command("calendar-daily-totals")
def calendar_daily_totals_cmd(
    database: Path | None = DBOption(),
    days_back: int = typer.Option(30, help="Days back to show"),
    days_forward: int = typer.Option(0, help="Days forward to show"),
) -> None:
    """Show combined daily event totals (count + duration) for calendar events.

    Applies the same calendar_id, exclude_titles, and hours_format settings
    as the daily and weekly report commands.
    """
    from datetime import date, timedelta
    from rebalance.ingest.calendar_config import CalendarConfig
    from rebalance.ingest.daily_report import _format_duration, get_day_data
    from rebalance.ingest.project_classifier import load_project_matchers

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    config = CalendarConfig.load()
    fmt = config.hours_format
    matchers = load_project_matchers(db_path, config=config)

    today = date.today()
    start = today - timedelta(days=days_back)
    end = today + timedelta(days=days_forward)

    days = []
    current = start
    while current <= end:
        day = get_day_data(db_path, current, config, project_matchers=matchers)
        if day.filtered_events:
            days.append(day)
        current += timedelta(days=1)

    if not days:
        typer.echo("No events found.")
        return

    typer.echo(f"\n📅 Daily Event Totals (last {days_back} days):\n")
    for day in days:
        day_name = day.target_date.strftime("%A")
        count = len(day.filtered_events)
        duration = _format_duration(day.total_minutes, fmt)
        typer.echo(f"  {day.target_date.isoformat()} ({day_name}): {count} events, {duration}")

    total_events = sum(len(d.filtered_events) for d in days)
    total_minutes = sum(d.total_minutes for d in days)
    avg_events_per_day = total_events / len(days) if days else 0
    avg_hours = _format_duration(int(total_minutes / len(days)), fmt) if days else _format_duration(0, fmt)

    typer.echo(f"\n📊 Summary:")
    typer.echo(f"  Days analyzed: {len(days)}")
    typer.echo(f"  Total events: {total_events}")
    typer.echo(f"  Total hours: {_format_duration(total_minutes, fmt)}")
    typer.echo(f"  Avg events/day: {avg_events_per_day:.1f}")
    typer.echo(f"  Avg hours/day: {avg_hours}\n")


@app.command("calendar-snap-edges")
def calendar_snap_edges_cmd(
    date_str: str = typer.Option(None, "--date", help="Start date (YYYY-MM-DD, default: today)"),
    days: int = typer.Option(1, "--days", help="Number of consecutive days to process (1-7)"),
    calendar_id: str = typer.Option("", "--calendar-id", help="Calendar ID (default: from config)"),
    timezone_name: str = typer.Option("", "--timezone", help="IANA timezone (default: from config)"),
    apply: bool = typer.Option(False, "--apply", help="Actually patch Google Calendar (default: dry-run)"),
    output_format: str = typer.Option("text", "--output", "-o", help="Output format: text or json"),
) -> None:
    """Detect and fix slightly overlapping calendar events.

    Trims Event 1's end to 1 minute before Event 2's start so adjacent
    events have clean edges.  Skips all-day events and clusters of 3+
    overlapping events (manual resolution required).

    Dry-run by default — re-run with --apply to patch Google Calendar.
    """
    from rebalance.ingest.calendar_config import CalendarConfig
    from rebalance.ingest.calendar_snap import snap_edges

    normalized_output = output_format.strip().lower()
    if normalized_output not in {"text", "json"}:
        raise typer.BadParameter("--output must be 'text' or 'json'.")

    if not 1 <= days <= 7:
        raise typer.BadParameter("--days must be between 1 and 7.")

    env_data = _load_google_calendar_env()
    if apply:
        _require_calendar_write_scope(env_data)

    config = CalendarConfig.load()
    resolved_calendar_id = calendar_id.strip() or config.calendar_id
    resolved_timezone = timezone_name.strip() or config.timezone

    if date_str:
        start_date = date_cls.fromisoformat(date_str)
    else:
        # Use the calendar timezone for "today", not the machine's local date
        start_date = datetime.now(ZoneInfo(resolved_timezone)).date()

    result = snap_edges(
        calendar_id=resolved_calendar_id,
        start_date=start_date,
        num_days=days,
        timezone_name=resolved_timezone,
        apply=apply,
    )

    if normalized_output == "json":
        import dataclasses
        typer.echo(json.dumps(dataclasses.asdict(result), ensure_ascii=False, indent=2))
        return

    # Text output
    mode_label = "APPLIED" if result.applied else "DRY RUN"
    typer.echo(f"\n--- Calendar Edge Snap ({mode_label}) ---\n")

    for day in result.days:
        typer.echo(f"  {day.date}  ({day.total_events_examined} events examined, {day.skipped_allday} all-day skipped)")

        if not day.snapped and not day.skipped_clusters:
            typer.echo("    No overlaps detected.\n")
            continue

        for pair in day.snapped:
            action = "Snapped" if result.applied else "Would snap"
            typer.echo(
                f"    {action}: \"{pair.event1_summary}\" end {pair.event1_original_end} -> {pair.event1_new_end}"
                f"  (overlapped \"{pair.event2_summary}\" by {pair.overlap_minutes}m)"
            )

        for cluster in day.skipped_clusters:
            names = ", ".join(f'"{s}"' for s in cluster.event_summaries)
            typer.echo(f"    Skipped cluster: {names} — {cluster.reason}")

        typer.echo()

    typer.echo(f"  Total snapped: {result.total_snapped}")
    typer.echo(f"  Total skipped clusters: {result.total_skipped_clusters}")
    typer.echo(f"  Elapsed: {result.elapsed_seconds}s\n")

    if not result.applied:
        typer.echo("  Dry run — no changes applied. Re-run with --apply to patch Google Calendar.\n")


@app.command("calendar-daily-report")
def calendar_daily_report_cmd(
    database: Path | None = DBOption(),
    date_str: str = typer.Option(None, "--date", help="Date to report on (YYYY-MM-DD, default: today)"),
    output: Path = typer.Option(None, "--output", "-o", help="Write report to a markdown file instead of stdout"),
) -> None:
    """Generate daily calendar report with project aggregator (exclude keywords configured in temp/calendar_config.json)."""
    from datetime import date
    from rebalance.ingest.daily_report import generate_daily_report
    from rebalance.ingest.calendar_config import CalendarConfig

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    config = CalendarConfig.load()

    if date_str:
        target_date = date.fromisoformat(date_str)
    else:
        target_date = date.today()

    report = generate_daily_report(db_path, target_date, config)

    if output:
        out_path = output.expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        typer.echo(f"Report written to {out_path}")
    else:
        typer.echo(report)


@app.command("calendar-weekly-report")
def calendar_weekly_report_cmd(
    database: Path | None = DBOption(),
    date_str: str = typer.Option(None, "--date", help="Date in target week (YYYY-MM-DD, default: today)"),
    output: Path = typer.Option(None, "--output", "-o", help="Write report to a markdown file instead of stdout"),
    vault: Path = typer.Option(None, "--vault", envvar="REBALANCE_VAULT", help="Obsidian vault path for weekly note write-back"),
    write_week_note: bool = typer.Option(False, "--write-week-note", help="Write week-of-YYYY-MM-DD.md into the vault under Weekly Notes/"),
    reingest_note: bool = typer.Option(True, "--reingest-note/--no-reingest-note", help="When writing a week note, re-ingest and embed it into the local knowledge store"),
) -> None:
    """Generate weekly calendar report (Sun-Sat) with daily summaries and project aggregator."""
    from datetime import date
    from rebalance.ingest.weekly_report import generate_weekly_report, write_weekly_note
    from rebalance.ingest.calendar_config import CalendarConfig

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    config = CalendarConfig.load()

    if date_str:
        target_date = date.fromisoformat(date_str)
    else:
        target_date = date.today()

    report = generate_weekly_report(db_path, target_date, config)
    wrote_artifact = False

    if output:
        out_path = output.expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        typer.echo(f"Report written to {out_path}")
        wrote_artifact = True

    if write_week_note:
        if vault is None:
            raise typer.BadParameter("--vault or REBALANCE_VAULT is required with --write-week-note.")
        vault_path = vault.expanduser().resolve()
        if not vault_path.exists() or not vault_path.is_dir():
            raise typer.BadParameter(f"Vault path does not exist or is not a directory: {vault_path}")

        note_path = write_weekly_note(vault_path, report, target_date=target_date, config=config)
        typer.echo(f"Week note written to {note_path}")
        wrote_artifact = True

        if reingest_note:
            from rebalance.ingest.note_ingester import ingest_vault
            from rebalance.ingest.embedder import embed_chunks

            ingest_result = ingest_vault(vault_path=vault_path, database_path=db_path)
            typer.echo(
                "Vault ingest complete: "
                f"new={ingest_result.new_files}, updated={ingest_result.updated_files}, "
                f"unchanged={ingest_result.unchanged_files}, deleted={ingest_result.deleted_files} "
                f"({ingest_result.elapsed_seconds}s)"
            )
            embed_result = embed_chunks(database_path=db_path)
            typer.echo(
                "Embed complete: "
                f"embedded={embed_result.embedded_chunks}, skipped={embed_result.skipped_unchanged}, "
                f"total_chunks={embed_result.total_chunks} ({embed_result.elapsed_seconds}s)"
            )

    if not wrote_artifact:
        typer.echo(report)


@app.command("dashboard-render")
def dashboard_render_cmd(
    database: Path | None = DBOption(),
    date_str: str = typer.Option(None, "--date", help="Date anchoring the dashboard window (YYYY-MM-DD, default: today)"),
    since_days: int = typer.Option(14, "--since-days", min=1, help="Lookback window for recent signals"),
    vault: Path = typer.Option(None, "--vault", envvar="REBALANCE_VAULT", help="Obsidian vault path for dashboard note write-back"),
    note_path: str = typer.Option("Dashboards/rebalanceOS Dashboard.md", "--note-path", help="Vault-relative dashboard note path"),
    output: Path = typer.Option(None, "--output", "-o", help="Write dashboard markdown to an explicit path"),
    gemini_synthesis: bool = typer.Option(False, "--gemini-synthesis", help="Add a Gemini-written operator summary"),
    cleanup: bool = typer.Option(False, "--cleanup", help="Tighten the Gemini-written summary to reduce redundancy"),
    gemini_model: str = typer.Option("gemini-2.5-flash", "--gemini-model", help="Gemini model for optional synthesis"),
    reingest_note: bool = typer.Option(False, "--reingest-note/--no-reingest-note", help="When writing into the vault, re-ingest and embed the updated note"),
    changelog_path: Path = typer.Option(Path("CHANGELOG.md"), "--changelog-path", help="Path to the changelog source"),
    goals_path: Path = typer.Option(Path("4X4.md"), "--goals-path", help="Path to the 4X4 source"),
) -> None:
    """Generate the Obsidian dashboard note from recent local signals."""
    from datetime import date
    from rebalance.ingest.dashboard import build_dashboard_note_content, write_dashboard_note
    from rebalance.ingest.calendar_config import CalendarConfig

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    config = CalendarConfig.load()

    if date_str:
        target_date = date.fromisoformat(date_str)
    else:
        target_date = date.today()

    resolved_output: Path | None = output.expanduser().resolve() if output else None
    resolved_vault: Path | None = None
    if vault is not None:
        resolved_vault = vault.expanduser().resolve()
    elif not resolved_output:
        configured_vault = get_vault_path()
        if configured_vault:
            resolved_vault = Path(configured_vault).expanduser().resolve()

    if resolved_output is None:
        if resolved_vault is None:
            raise typer.BadParameter("--vault, REBALANCE_VAULT, configured vault path, or --output is required.")
        if not resolved_vault.exists() or not resolved_vault.is_dir():
            raise typer.BadParameter(f"Vault path does not exist or is not a directory: {resolved_vault}")
        resolved_output = (resolved_vault / note_path).resolve()

    if reingest_note and resolved_vault is None:
        raise typer.BadParameter("--reingest-note requires a vault path.")

    try:
        markdown = build_dashboard_note_content(
            db_path,
            target_date=target_date,
            since_days=since_days,
            config=config,
            changelog_path=changelog_path.expanduser().resolve(),
            goals_path=goals_path.expanduser().resolve(),
            gemini_synthesis=gemini_synthesis,
            gemini_model=gemini_model,
            cleanup=cleanup,
        )
    except RuntimeError as exc:
        raise typer.BadParameter(str(exc)) from exc

    note_file = write_dashboard_note(resolved_output, markdown)
    typer.echo(f"Dashboard written to {note_file}")

    if reingest_note:
        from rebalance.ingest.note_ingester import ingest_vault
        from rebalance.ingest.embedder import embed_chunks

        ingest_result = ingest_vault(vault_path=resolved_vault, database_path=db_path)
        typer.echo(
            "Vault ingest complete: "
            f"new={ingest_result.new_files}, updated={ingest_result.updated_files}, "
            f"unchanged={ingest_result.unchanged_files}, deleted={ingest_result.deleted_files} "
            f"({ingest_result.elapsed_seconds}s)"
        )
        embed_result = embed_chunks(database_path=db_path)
        typer.echo(
            "Embed complete: "
            f"embedded={embed_result.embedded_chunks}, skipped={embed_result.skipped_unchanged}, "
            f"total_chunks={embed_result.total_chunks} ({embed_result.elapsed_seconds}s)"
        )


@app.command("sleuth-sync")
def sleuth_sync_cmd(
    active_only: bool = typer.Option(
        False,
        "--active-only/--all",
        help="Only fetch currently active reminders (default: all)",
    ),
    database: Path | None = DBOption("--database-path"),
    json_output: bool = typer.Option(False, "--json", help="Emit full sync result as JSON"),
) -> None:
    """Pull Slack reminders from the Sleuth Web API and upsert them into SQLite."""
    from rebalance.ingest.sleuth_reminders import sync_sleuth_reminders

    env_data = _load_sleuth_env()
    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    result = sync_sleuth_reminders(
        base_url=env_data["SLEUTH_WEB_API_BASE_URL"],
        token=env_data["SLEUTH_WEB_API_TOKEN"],
        workspace_name=env_data["SLEUTH_WORKSPACE_NAME"],
        database_path=db_path,
        active_only=active_only,
    )

    if json_output:
        typer.echo(json.dumps(result.as_dict(), ensure_ascii=False))
        return

    typer.echo(
        f"Sleuth sync: workspace={result.workspace_name}, "
        f"returned={result.returned_reminder_count}/{result.total_reminder_count}, "
        f"inserted={result.inserted_count}, updated={result.updated_count}, "
        f"unchanged={result.unchanged_count}"
    )


@app.command("version")
def version() -> None:
    """Print rebalance CLI version."""
    from rebalance import __version__

    typer.echo(__version__)


@config_app.command("add-github-ignored-repo")
def config_add_github_ignored_repo(
    repo: str = typer.Argument(..., help="GitHub repo in owner/name form"),
    purge: bool = typer.Option(False, help="Purge existing local GitHub rows for this repo"),
    dry_run: bool = typer.Option(False, help="Preview purge counts without deleting"),
    confirm: bool = typer.Option(False, help="Confirm destructive purge execution"),
    database: Path | None = DBOption(help="SQLite database path for purge operations (resolves via layered chain)"),
) -> None:
    """Add one repo to the local GitHub ingest ignore list, with optional purge."""
    from rebalance.ingest.github_knowledge import purge_github_repo_data

    normalized_repo = normalize_github_repo_name(repo)
    added = add_github_ignored_repo(normalized_repo)
    if added:
        typer.echo(f"✓ Added ignored GitHub repo: {normalized_repo}")
    else:
        typer.echo(f"✓ GitHub repo already ignored: {normalized_repo}")

    if not purge and not dry_run:
        return

    # Validate destructive-flag combination before touching the DB so missing
    # databases don't mask user-facing argument errors.
    if purge and not dry_run and not confirm:
        typer.echo("Use --confirm with --purge to execute the destructive delete.")
        raise typer.Exit(code=2)

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    if dry_run:
        purge_result = purge_github_repo_data(db_path, normalized_repo, dry_run=True)
        append_audit_entry(
            "github_repo_purge",
            normalized_repo,
            dry_run=True,
            confirmed=False,
            database_path=str(db_path),
            row_counts=purge_result.row_counts,
            total_rows=purge_result.total_rows,
            deleted_rows=purge_result.deleted_rows,
        )
        typer.echo(
            f"Dry run: {normalized_repo} would purge {purge_result.total_rows} rows "
            f"({_format_purge_counts(purge_result.row_counts)})"
        )
        return

    purge_result = purge_github_repo_data(db_path, normalized_repo, dry_run=False)
    append_audit_entry(
        "github_repo_purge",
        normalized_repo,
        dry_run=False,
        confirmed=True,
        database_path=str(db_path),
        row_counts=purge_result.row_counts,
        total_rows=purge_result.total_rows,
        deleted_rows=purge_result.deleted_rows,
    )
    typer.echo(
        f"Purged {purge_result.deleted_rows} rows for {normalized_repo} "
        f"({_format_purge_counts(purge_result.row_counts)})"
    )


@config_app.command("remove-github-ignored-repo")
def config_remove_github_ignored_repo(
    repo: str = typer.Argument(..., help="GitHub repo in owner/name form"),
) -> None:
    """Remove one repo from the local GitHub ingest ignore list."""
    normalized_repo = normalize_github_repo_name(repo)
    removed = remove_github_ignored_repo(normalized_repo)
    if removed:
        typer.echo(f"✓ Removed ignored GitHub repo: {normalized_repo}")
    else:
        typer.echo(f"✓ GitHub repo was not ignored: {normalized_repo}")


@config_app.command("list-github-ignored-repos")
def config_list_github_ignored_repos() -> None:
    """List the operator-local GitHub repos excluded from ingest."""
    repos = get_github_ignored_repos()
    if not repos:
        typer.echo("No ignored GitHub repos configured.")
        return
    for repo in repos:
        typer.echo(repo)


@config_app.command("add-github-related-repo")
def config_add_github_related_repo(
    repo: str = typer.Argument(..., help="Central tracker repo in owner/name form"),
    related_repo: str = typer.Argument(..., help="Related implementation repo in owner/name form"),
) -> None:
    """Add an affiliate implementation repo for a central GitHub tracker repo."""
    normalized_repo = normalize_github_repo_name(repo)
    normalized_related = normalize_github_repo_name(related_repo)
    added = add_github_related_repo(normalized_repo, normalized_related)
    if added:
        typer.echo(f"✓ Added related GitHub repo for {normalized_repo}: {normalized_related}")
    else:
        typer.echo(f"✓ Related GitHub repo already configured for {normalized_repo}: {normalized_related}")


@config_app.command("remove-github-related-repo")
def config_remove_github_related_repo(
    repo: str = typer.Argument(..., help="Central tracker repo in owner/name form"),
    related_repo: str = typer.Argument(..., help="Related implementation repo in owner/name form"),
) -> None:
    """Remove an affiliate implementation repo from a central tracker repo."""
    normalized_repo = normalize_github_repo_name(repo)
    normalized_related = normalize_github_repo_name(related_repo)
    removed = remove_github_related_repo(normalized_repo, normalized_related)
    if removed:
        typer.echo(f"✓ Removed related GitHub repo for {normalized_repo}: {normalized_related}")
    else:
        typer.echo(f"✓ Related GitHub repo was not configured for {normalized_repo}: {normalized_related}")


@config_app.command("list-github-related-repos")
def config_list_github_related_repos(
    repo: str = typer.Argument(..., help="Central tracker repo in owner/name form"),
) -> None:
    """List affiliate implementation repos for a central GitHub tracker repo."""
    normalized_repo = normalize_github_repo_name(repo)
    repos = get_github_related_repos(normalized_repo)
    if not repos:
        typer.echo(f"No related GitHub repos configured for {normalized_repo}.")
        return
    for related_repo in repos:
        typer.echo(related_repo)


@config_app.command("set-project-priority")
def config_set_project_priority(
    name: str = typer.Argument(..., help="Canonical project name"),
    alias: list[str] = typer.Option([], "--alias", help="Project/client alias. Repeat for multiple aliases."),
    client: str = typer.Option("", "--client", help="Client or account label"),
    priority_tier: int | None = typer.Option(None, "--priority-tier", min=1, max=5, help="Priority tier: 1 is highest, 5 is lowest"),
    value_score: int | None = typer.Option(None, "--value-score", min=1, max=10, help="Value score: 10 is highest"),
    value_level: str = typer.Option("", "--value-level", help="Value level, e.g. strategic or revenue-generating"),
    risk_level: str = typer.Option("", "--risk-level", help="Risk level, e.g. high, medium, low"),
) -> None:
    """Set local project/client priority metadata used by dashboards."""
    try:
        rule = set_project_priority_rule(
            name=name,
            aliases=alias,
            client=client,
            priority_tier=priority_tier,
            value_score=value_score,
            value_level=value_level,
            risk_level=risk_level,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"✓ Set project priority: {rule['name']}")


@config_app.command("remove-project-priority")
def config_remove_project_priority(
    name: str = typer.Argument(..., help="Canonical project name"),
) -> None:
    """Remove local project/client priority metadata by project name."""
    removed = remove_project_priority_rule(name)
    if removed:
        typer.echo(f"✓ Removed project priority: {name}")
    else:
        typer.echo(f"✓ Project priority was not configured: {name}")


@config_app.command("list-project-priorities")
def config_list_project_priorities() -> None:
    """List local project/client priority metadata."""
    rules = get_project_priority_rules()
    if not rules:
        typer.echo("No project priorities configured.")
        return
    for rule in rules:
        pieces = [
            rule["name"],
            f"tier={rule.get('priority_tier', 'n/a')}",
            f"value={rule.get('value_score', 'n/a')}",
        ]
        if rule.get("client"):
            pieces.append(f"client={rule['client']}")
        if rule.get("aliases"):
            pieces.append(f"aliases={', '.join(rule['aliases'])}")
        typer.echo(" | ".join(pieces))


@config_app.command("set-github-token")
def config_set_github_token(
    token: str = typer.Argument(..., help="GitHub Personal Access Token (ghp_...)"),
) -> None:
    """Store GitHub PAT in local config (temp/rbos.config, gitignored)."""
    set_github_token(token)
    typer.echo(f"✓ GitHub token stored in {get_config_path()}")
    typer.echo("  Keep this file secret and never commit it.")


@config_app.command("get-github-token")
def config_get_github_token() -> None:
    """Check if GitHub token is available (config first, gh CLI fallback)."""
    token, source = get_github_token_with_source()
    if token:
        masked = token[:10] + "..." + token[-4:] if len(token) > 14 else "***"
        label = {"config": "stored PAT", "gh-cli": "via `gh auth token`"}.get(source, source or "unknown")
        typer.echo(f"✓ GitHub token available: {masked}  (source: {label})")
    else:
        typer.echo("✗ No GitHub token available. Either:")
        typer.echo("  rebalance config set-github-token <PAT>")
        typer.echo("  — or —")
        typer.echo("  gh auth login   (then it'll be picked up automatically)")


@config_app.command("clear-github-token")
def config_clear_github_token() -> None:
    """Remove stored PAT so the gh CLI fallback takes over (`gh auth token`)."""
    clear_github_token()
    typer.echo("✓ Stored PAT cleared. `get-github-token` will now fall back to gh CLI.")


@config_app.command("set-vault")
def config_set_vault(
    path: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True, help="Absolute path to the Obsidian vault root"),
) -> None:
    """Store Obsidian vault path in local config (temp/rbos.config). Canonical source for all ingest/sync workflows."""
    resolved = str(path.expanduser().resolve())
    set_vault_path(resolved)
    typer.echo(f"✓ Vault path stored in {get_config_path()}")
    typer.echo(f"  vault_path = {resolved}")


@config_app.command("get-vault")
def config_get_vault() -> None:
    """Show the configured Obsidian vault path."""
    path = get_vault_path()
    if path:
        typer.echo(f"✓ Vault path: {path}")
    else:
        typer.echo("✗ Vault path not configured. Set it with:")
        typer.echo("  rebalance config set-vault <absolute-path>")


@config_app.command("show-config-path")
def config_show_config_path() -> None:
    """Show where configuration is stored."""
    path = get_config_path()
    typer.echo(f"Config file: {path}")
    typer.echo(f"Gitignored:  {path.parent.name}/ is in .gitignore")


@config_app.command("set-default-database")
def config_set_default_database(
    path: Path = typer.Argument(..., help="Absolute path to rebalance.db"),
) -> None:
    """Set the user-level default database path.

    Writes ``database_path`` to ~/.config/rebalance-os/config.json so any
    `rebalance` command run from any directory on this machine resolves to
    the right database without needing REBALANCE_DB in the shell rc.

    Resolution order (highest priority first):
      1. --database flag
      2. REBALANCE_DB env var
      3. Walk-up from cwd for a project marker (.git / pyproject.toml)
      4. This user-level default
    """
    from rebalance.paths import set_user_config_value

    abs_path = path.expanduser().resolve()
    if not abs_path.exists():
        typer.echo(f"[error] {abs_path} does not exist; refusing to write default")
        raise typer.Exit(2)
    config_file = set_user_config_value("database_path", str(abs_path))
    typer.echo(f"[+] wrote database_path={abs_path}")
    typer.echo(f"    to {config_file}")


@config_app.command("set-secrets-dir")
def config_set_secrets_dir(
    path: Path = typer.Argument(..., help="Absolute path to secrets directory"),
) -> None:
    """Set the user-level secrets directory.

    Writes ``secrets_dir`` to ~/.config/rebalance-os/config.json. Used when
    resolving env files like google-calendar.env, sleuth-web-api-development.env,
    etc.

    Resolution order:
      1. REBALANCE_SECRETS_DIR env var
      2. This user-level default
      3. ~/secrets (legacy fallback)
    """
    from rebalance.paths import set_user_config_value

    abs_path = path.expanduser().resolve()
    if not abs_path.exists():
        typer.echo(f"[error] {abs_path} does not exist; refusing to write default")
        raise typer.Exit(2)
    if not abs_path.is_dir():
        typer.echo(f"[error] {abs_path} is not a directory")
        raise typer.Exit(2)
    config_file = set_user_config_value("secrets_dir", str(abs_path))
    typer.echo(f"[+] wrote secrets_dir={abs_path}")
    typer.echo(f"    to {config_file}")


@config_app.command("show-defaults")
def config_show_defaults() -> None:
    """Show the layered path-resolution state (debug helper).

    Prints what every layer of the resolver currently sees, so you can tell
    *why* a particular DB or secret path is being used.
    """
    from rebalance.paths import get_user_config_summary

    summary = get_user_config_summary()
    for k, v in summary.items():
        typer.echo(f"  {k}: {v}")

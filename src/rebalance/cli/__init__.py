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
    get_anthropic_api_key,
    get_gemini_api_key,
    get_github_related_repos,
    get_github_token,
    get_github_token_with_source,
    get_github_ignored_repos,
    get_project_priority_rules,
    get_sleuth_credentials,
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

from rebalance.cli._core import app, ingest_app, config_app, _PROJECT_ROOT

# Extracted per-domain command modules — importing each registers its commands
# on the shared `app` from `_core` (Phase 5 decomposition, in progress).
from rebalance.cli import raw as _raw  # noqa: F401,E402
from rebalance.cli import semantic as _semantic  # noqa: F401,E402
from rebalance.cli import config_cmds as _config_cmds  # noqa: F401,E402
from rebalance.cli import calendar as _calendar  # noqa: F401,E402
from rebalance.cli import github as _github  # noqa: F401,E402
from rebalance.cli import query as _query  # noqa: F401,E402
from rebalance.cli import ingest_cmds as _ingest_cmds  # noqa: F401,E402
from rebalance.cli import dashboard as _dashboard  # noqa: F401,E402
from rebalance.cli import sleuth as _sleuth  # noqa: F401,E402
from rebalance.cli import serve as _serve  # noqa: F401,E402

# Re-exported for ingest.index_ops, which imports `from rebalance.cli import _load_sleuth_env`.
from rebalance.cli.sleuth import _load_sleuth_env  # noqa: F401,E402


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
    Also surfaces the last auth failure per integration (from the unified auth
    log) and a diagnostics index pointing at every other observability surface —
    making this the single entry point into the project's diagnostics.
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


@app.command("version")
def version() -> None:
    """Print rebalance CLI version."""
    from rebalance import __version__

    typer.echo(__version__)



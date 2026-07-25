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
from rebalance.cli import onboard as _onboard  # noqa: F401,E402
from rebalance.cli import reset as _reset  # noqa: F401,E402
from rebalance.cli import profile_sync as _profile_sync  # noqa: F401,E402
from rebalance.cli import refresh as _refresh  # noqa: F401,E402
from rebalance.cli import apple_reminders as _apple_reminders  # noqa: F401,E402

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
    from rebalance.ingest.index_ops import get_index_status

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

    try:
        status = get_index_status(resolve_database_path(database))
    except DatabaseNotFoundError:
        status = {}

    degraded = {
        name: health.get("reason", "degraded")
        for name, health in status.get("freshness", {}).get("signal_health", {}).items()
        if health.get("status") == "degraded"
    }
    if degraded:
        detail = "; ".join(f"{name}: {reason}" for name, reason in degraded.items())
        console.print(f"  {label[WARN]}  [bold]signal health[/bold] — {detail}")
    console.print()
    if report.failed:
        console.print("[red]Health check found failures.[/red]")
        raise typer.Exit(1)
    if report.warned:
        console.print("[yellow]Health check passed with warnings.[/yellow]")
    else:
        console.print("[green]All checks passed.[/green]")


@app.command("version")
def version() -> None:
    """Print rebalance CLI version."""
    from rebalance import __version__

    typer.echo(__version__)


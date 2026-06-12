"""`rebalance sleuth-sync` — pull Slack reminders from the Sleuth Web API.

Extracted from the cli monolith (Phase 5). Registers on the shared Typer `app`.
`_load_sleuth_env` is the CLI's `typer.BadParameter` wrapper over
`config.get_sleuth_credentials`. The shared sync path is
`ingest.sleuth_reminders.sync_sleuth`, which this command, the MCP tool, and the
`sleuth` collector all call (COLLECTOR-PATH-AND-PORTABILITY-AUDIT Phase 2).
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from rebalance.cli._core import app
from rebalance.paths import DatabaseNotFoundError, DBOption, resolve_database_path


def _load_sleuth_env(which: str = "production") -> dict[str, str]:
    """Thin CLI wrapper — converts config.get_sleuth_credentials() errors to typer.BadParameter."""
    from rebalance.ingest.config import get_sleuth_credentials
    try:
        return get_sleuth_credentials(which)
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc


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
    from rebalance.ingest.sleuth_reminders import sync_sleuth

    _load_sleuth_env()  # validate creds → typer.BadParameter before touching the DB
    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    result = sync_sleuth(db_path, active_only=active_only)

    if json_output:
        typer.echo(json.dumps(result.as_dict(), ensure_ascii=False))
        return

    typer.echo(
        f"Sleuth sync: workspace={result.workspace_name}, "
        f"returned={result.returned_reminder_count}/{result.total_reminder_count}, "
        f"inserted={result.inserted_count}, updated={result.updated_count}, "
        f"unchanged={result.unchanged_count}"
    )

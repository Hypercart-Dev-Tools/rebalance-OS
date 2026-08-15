"""`rebalance dashboard-render` — generate the Obsidian dashboard note.

Extracted from the cli monolith (Phase 5). Registers on the shared Typer `app`.
(The live `dashboard` command + its `_launch_dashboard` helper stay in the
package root alongside the no-arg callback that shares them.)
"""

from __future__ import annotations

from pathlib import Path

import typer

from rebalance.cli._core import app
from rebalance.ingest.config import get_vault_path
from rebalance.paths import DatabaseNotFoundError, DBOption, resolve_database_path


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
    gemini_model: str = typer.Option("gemini-3.5-flash", "--gemini-model", help="Gemini model for optional synthesis"),
    reingest_note: bool = typer.Option(False, "--reingest-note/--no-reingest-note", help="When writing into the vault, re-ingest and embed the updated note"),
    changelog_path: Path = typer.Option(Path("CHANGELOG.md"), "--changelog-path", help="Path to the changelog source"),
    goals_path: Path = typer.Option(Path("4X4.md"), "--goals-path", help="Path to the 4X4 source"),
) -> None:
    """Generate the Obsidian dashboard note from recent local signals."""
    from datetime import date
    from rebalance.ingest.note_builder import build_dashboard_note_content, write_dashboard_note
    from rebalance.ingest.calendar_config import CalendarConfig
    from rebalance.lib.time_ops import parse_date

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    config = CalendarConfig.load()

    if date_str:
        target_date = parse_date(date_str) or date.today()
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
        from rebalance.ingest.note_ingester import ingest_notes_command
        from rebalance.ingest.embedder import embed_vault_chunks

        ingest_result = ingest_notes_command(vault_path=resolved_vault, database_path=db_path)
        typer.echo(
            "Vault ingest complete: "
            f"new={ingest_result.new_files}, updated={ingest_result.updated_files}, "
            f"unchanged={ingest_result.unchanged_files}, deleted={ingest_result.deleted_files} "
            f"({ingest_result.elapsed_seconds}s)"
        )
        embed_result = embed_vault_chunks(database_path=db_path)
        typer.echo(
            "Embed complete: "
            f"embedded={embed_result.embedded_chunks}, skipped={embed_result.skipped_unchanged}, "
            f"total_chunks={embed_result.total_chunks} ({embed_result.elapsed_seconds}s)"
        )

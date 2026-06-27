"""`rebalance apple-reminders *` commands — Apple Reminders write-back (Phase 5.1).

Safe by default: every mutation runs in PLAN (dry-run) mode and prints what it
*would* do unless ``--apply`` is passed. Writes are delegated to the signed
helper bundle (the single writer to Apple Reminders); ``delete`` additionally
requires ``--yes``. See APPLE-REMINDERS-UNIFIED-PLAN Phase 5.1.

Deliberately NOT exposed as an MCP tool in v1: write-through-MCP would let an
agent mutate or delete the operator's reminders. The CLI keeps a human in the
loop (and the dry-run default). MCP exposure, if ever wanted, registers the same
`apply_reminder_writes` orchestrator the same way the read tools do.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import typer

from rebalance.cli._core import app
from rebalance.ingest.apple_reminders_write import (
    AppleRemindersWriteError,
    WriteOp,
    apply_reminder_writes,
    build_request,
    ensure_apple_reminders_write_schema,
)
from rebalance.paths import DatabaseNotFoundError, DBOption, resolve_database_path

apple_reminders_app = typer.Typer(
    help="Apple Reminders write-back (create/update/complete/delete). "
    "Dry-run by default; pass --apply to execute."
)
app.add_typer(apple_reminders_app, name="apple-reminders")


def _resolve_db(database: Path | None) -> Path:
    try:
        return resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc


def _run(db_path: Path, op: WriteOp, *, apply: bool, confirm: bool = False) -> None:
    """Build a one-op request, run it through the orchestrator, print the result."""
    mode = "apply" if apply else "plan"
    request = build_request([op], mode=mode, confirm_destructive=confirm)
    try:
        result = apply_reminder_writes(db_path, request)
    except AppleRemindersWriteError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from exc
    typer.echo(json.dumps(result.as_dict(), indent=2))
    if not result.ok:
        raise typer.Exit(1)


@apple_reminders_app.command("create")
def create_cmd(
    title: str = typer.Option(..., "--title", help="Reminder title."),
    notes: str = typer.Option("", "--notes", help="Reminder notes."),
    due: str = typer.Option("", "--due", help="Due datetime (ISO 8601)."),
    list_name: str | None = typer.Option(
        None, "--list", help="Target list (defaults to the configured ingest list)."
    ),
    apply: bool = typer.Option(False, "--apply", help="Execute (default: dry-run)."),
    database: Path | None = DBOption(),
) -> None:
    """Create a reminder in the configured ingest list."""
    db_path = _resolve_db(database)
    if not list_name:
        from rebalance.ingest.config import get_apple_reminders_list_name
        list_name = get_apple_reminders_list_name()
    fields: dict[str, object] = {"title": title}
    if notes:
        fields["notes"] = notes
    if due:
        fields["due_at"] = due
    op = WriteOp(op="create", client_token=uuid4().hex, list_name=list_name, fields=fields)
    _run(db_path, op, apply=apply)


@apple_reminders_app.command("update")
def update_cmd(
    reminder_id: str = typer.Argument(..., help="Reminder id (ZCKIDENTIFIER)."),
    title: str | None = typer.Option(None, "--title", help="New title."),
    notes: str | None = typer.Option(None, "--notes", help="New notes."),
    due: str | None = typer.Option(None, "--due", help="New due datetime (ISO 8601)."),
    apply: bool = typer.Option(False, "--apply", help="Execute (default: dry-run)."),
    database: Path | None = DBOption(),
) -> None:
    """Update fields on an existing reminder."""
    db_path = _resolve_db(database)
    fields: dict[str, object] = {}
    if title is not None:
        fields["title"] = title
    if notes is not None:
        fields["notes"] = notes
    if due is not None:
        fields["due_at"] = due
    if not fields:
        typer.echo("error: update needs at least one of --title/--notes/--due", err=True)
        raise typer.Exit(2)
    op = WriteOp(op="update", reminder_id=reminder_id, fields=fields)
    _run(db_path, op, apply=apply)


@apple_reminders_app.command("complete")
def complete_cmd(
    reminder_id: str = typer.Argument(..., help="Reminder id (ZCKIDENTIFIER)."),
    apply: bool = typer.Option(False, "--apply", help="Execute (default: dry-run)."),
    database: Path | None = DBOption(),
) -> None:
    """Mark an existing reminder completed."""
    db_path = _resolve_db(database)
    op = WriteOp(op="complete", reminder_id=reminder_id)
    _run(db_path, op, apply=apply)


@apple_reminders_app.command("delete")
def delete_cmd(
    reminder_id: str = typer.Argument(..., help="Reminder id (ZCKIDENTIFIER)."),
    apply: bool = typer.Option(False, "--apply", help="Execute (default: dry-run)."),
    yes: bool = typer.Option(
        False, "--yes", help="Confirm the destructive delete (required with --apply)."
    ),
    database: Path | None = DBOption(),
) -> None:
    """Delete an existing reminder (destructive — needs --apply and --yes)."""
    db_path = _resolve_db(database)
    op = WriteOp(op="delete", reminder_id=reminder_id)
    _run(db_path, op, apply=apply, confirm=yes)


@apple_reminders_app.command("audit")
def audit_cmd(
    limit: int = typer.Option(20, "--limit", help="Max rows to show."),
    database: Path | None = DBOption(),
) -> None:
    """Show recent Apple Reminders write-audit rows (forensic trail)."""
    from rebalance.ingest.db import db_connection

    db_path = _resolve_db(database)
    with db_connection(db_path, ensure_apple_reminders_write_schema) as conn:
        rows = conn.execute(
            "SELECT created_at, request_id, op, reminder_id, mode, state, op_status, "
            "detail FROM apple_reminders_write_audit ORDER BY created_at DESC, "
            "op_index ASC LIMIT ?",
            (limit,),
        ).fetchall()
    out = [
        {
            "created_at": r[0], "request_id": r[1], "op": r[2], "reminder_id": r[3],
            "mode": r[4], "state": r[5], "op_status": r[6], "detail": r[7],
        }
        for r in rows
    ]
    typer.echo(json.dumps(out, indent=2))

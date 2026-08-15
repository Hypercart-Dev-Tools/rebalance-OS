"""`rebalance calendar-*` commands — Google Calendar sync, create, reports, snap.

Extracted from the cli monolith (Phase 5). Registers on the shared Typer `app`.

Tests patch the module-level `GOOGLE_CALENDAR_ENV_PATH`, `CALENDAR_EVENT_LOG_PATH`,
and `_find_existing_calendar_event` here (i.e. `rebalance.cli.calendar.*`) — they
moved with the code from `rebalance.cli.*`.
"""

from __future__ import annotations

import json
import pickle
from datetime import date as date_cls, datetime, time as time_cls, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import typer

from rebalance.cli._core import app
from rebalance.paths import (
    DatabaseNotFoundError,
    DBOption,
    resolve_database_path,
    resolve_secret_path,
)

from rebalance.lib.time_ops import parse_date, parse_iso

CALENDAR_EVENT_LOG_PATH = Path("temp/logs/calendar-event-create.jsonl")

# Module-level path for the operator-owned Google Calendar env file. Resolved at
# import time so tests can patch `rebalance.cli.calendar.GOOGLE_CALENDAR_ENV_PATH`
# to redirect subsequent reads without monkey-patching the resolver itself.
GOOGLE_CALENDAR_ENV_PATH = resolve_secret_path("google-calendar.env")


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
        target_date = parse_date(date_str)
        if target_date is None:
            raise typer.BadParameter(f"Invalid date: {date_str}")
        tz = ZoneInfo(timezone_name)
        start_dt = datetime.combine(target_date, time_cls.min, tzinfo=tz)
        end_dt = datetime.combine(target_date + timedelta(days=1), time_cls.min, tzinfo=tz)
        return start_dt.isoformat(), end_dt.isoformat(), timezone_name

    if bool(start_time) != bool(end_time):
        raise typer.BadParameter("--start and --end must be provided together.")
    if not start_time or not end_time:
        raise typer.BadParameter("Provide either --date or both --start and --end.")

    start_dt = parse_iso(start_time, force_utc=False)
    end_dt = parse_iso(end_time, force_utc=False)
    if start_dt is None or end_dt is None:
        raise typer.BadParameter("Invalid datetime format for --start or --end.")

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


@app.command("calendar-sync")
def calendar_sync_cmd(
    database: Path | None = DBOption(),
    calendar_id: str = typer.Option(
        "",
        help=(
            "Calendar ID or email to sync. Omit to sync your own calendar "
            "(stored as 'primary'); an explicit value is synced verbatim under "
            "that id."
        ),
    ),
    days_back: int = typer.Option(30, help="Days back to fetch (use 365 for initial backfill)"),
    days_forward: int = typer.Option(7, help="Days forward to fetch"),
) -> None:
    """Sync Google Calendar events to SQLite for historical queries."""
    from rebalance.ingest.calendar import refresh_calendar_source

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc

    target = f"calendar '{calendar_id}'" if calendar_id else "your own calendar (primary)"
    typer.echo(f"Syncing {target} ({days_back} days back, {days_forward} days forward)...")
    # Pass the raw override (empty => operator's own calendar): refresh_calendar_source
    # resolves config + canonicalises only the operator default, never an explicit id.
    result = refresh_calendar_source(
        database_path=db_path,
        calendar_id=calendar_id,
        days_back=days_back,
        days_forward=days_forward,
    )
    typer.echo(
        f"Calendar sync complete: calendar='{result.calendar_id}', "
        f"fetched={result.events_fetched}, stored={result.events_stored}, "
        f"window={result.window_start}..{result.window_end} ({result.elapsed_seconds}s)"
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
    output_format: str = typer.Option("text", "--output", "-o", help="Output format: text or json"),
) -> None:
    """Report slightly overlapping calendar events and a clean boundary.

    Read-only: this never modifies your calendar. The calendar is the system of
    record for time tracking, so overlaps are surfaced for you to fix directly.
    Skips all-day events and clusters of 3+ overlapping events (manual
    resolution required).

    The suggested boundary is gapless by default (snap_gap_minutes=0 in
    calendar config). A positive snap_gap_minutes understates tracked time and
    prints a warning.
    """
    from rebalance.ingest.calendar_config import CalendarConfig
    from rebalance.ingest.calendar_snap import snap_edges

    normalized_output = output_format.strip().lower()
    if normalized_output not in {"text", "json"}:
        raise typer.BadParameter("--output must be 'text' or 'json'.")

    if not 1 <= days <= 7:
        raise typer.BadParameter("--days must be between 1 and 7.")

    config = CalendarConfig.load()
    resolved_calendar_id = calendar_id.strip() or config.calendar_id
    resolved_timezone = timezone_name.strip() or config.timezone

    if date_str:
        start_date = parse_date(date_str) or datetime.now(ZoneInfo(resolved_timezone)).date()
    else:
        # Use the calendar timezone for "today", not the machine's local date
        start_date = datetime.now(ZoneInfo(resolved_timezone)).date()

    result = snap_edges(
        calendar_id=resolved_calendar_id,
        start_date=start_date,
        num_days=days,
        timezone_name=resolved_timezone,
        gap_minutes=config.snap_gap_minutes,
    )

    if normalized_output == "json":
        import dataclasses
        typer.echo(json.dumps(dataclasses.asdict(result), ensure_ascii=False, indent=2))
        return

    # Text output
    typer.echo("\n--- Calendar Edge Overlaps (report only) ---\n")

    if result.warning:
        typer.echo(f"  ⚠️  {result.warning}\n")

    for day in result.days:
        typer.echo(f"  {day.date}  ({day.total_events_examined} events examined, {day.skipped_allday} all-day skipped)")

        if not day.snapped and not day.skipped_clusters:
            typer.echo("    No overlaps detected.\n")
            continue

        for pair in day.snapped:
            typer.echo(
                f"    Suggested: \"{pair.event1_summary}\" end {pair.event1_original_end} -> {pair.event1_new_end}"
                f"  (overlapped \"{pair.event2_summary}\" by {pair.overlap_minutes}m)"
            )

        for cluster in day.skipped_clusters:
            names = ", ".join(f'"{s}"' for s in cluster.event_summaries)
            typer.echo(f"    Skipped cluster: {names} — {cluster.reason}")

        typer.echo()

    typer.echo(f"  Total overlaps: {result.total_snapped}")
    typer.echo(f"  Total skipped clusters: {result.total_skipped_clusters}")
    typer.echo(f"  Elapsed: {result.elapsed_seconds}s\n")
    typer.echo("  Report only — your calendar was not modified. Resolve overlaps in the calendar directly.\n")


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
        target_date = parse_date(date_str) or date.today()
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
        target_date = parse_date(date_str) or date.today()
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
            from rebalance.ingest.note_ingester import ingest_notes_command
            from rebalance.ingest.embedder import embed_vault_chunks

            ingest_result = ingest_notes_command(vault_path=vault_path, database_path=db_path)
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

    if not wrote_artifact:
        typer.echo(report)

import json
import pickle
from datetime import date as date_cls, datetime, time as time_cls, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import typer

from rebalance.ingest.preflight import run_preflight
from rebalance.ingest.registry import sync_registry
from rebalance.ingest.config import get_github_token, set_github_token, get_config_path

app = typer.Typer(help="rebalance CLI")
ingest_app = typer.Typer(help="Ingest and project registry workflows")
config_app = typer.Typer(help="Configuration and secrets management")
app.add_typer(ingest_app, name="ingest")
app.add_typer(config_app, name="config")

GOOGLE_CALENDAR_ENV_PATH = Path("/Users/noelsaw/secrets/google-calendar.env")
CALENDAR_EVENT_LOG_PATH = Path("logs/calendar-event-create.jsonl")


def _load_google_calendar_env() -> dict[str, str]:
    """Load shared Google Calendar env metadata from the operator-owned file."""
    if not GOOGLE_CALENDAR_ENV_PATH.exists():
        raise typer.BadParameter(
            f"Google Calendar env file not found: {GOOGLE_CALENDAR_ENV_PATH}"
        )

    values: dict[str, str] = {}
    for raw_line in GOOGLE_CALENDAR_ENV_PATH.read_text(encoding="utf-8").splitlines():
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


@app.command("github-scan")
def github_scan(
    token: str = typer.Option(..., envvar="GITHUB_TOKEN", help="GitHub Personal Access Token"),
    days: int = typer.Option(30, help="Number of days to look back (supports 30-day A/B/C band classification)"),
    database: Path = typer.Option(
        Path("rebalance.db"), envvar="REBALANCE_DB", help="SQLite database path"
    ),
) -> None:
    """Fetch GitHub activity and persist to database for use by github_balance MCP tool."""
    from rebalance.ingest.github_scan import scan_github, upsert_github_activity

    db_path = database.expanduser().resolve()
    typer.echo(f"Scanning GitHub activity for last {days} days...")
    result = scan_github(token=token, days=days)
    upsert_github_activity(db_path, result)
    typer.echo(
        f"Done: login={result.login}, events={result.total_events}, "
        f"repos={len(result.repo_activity)}, stored to {db_path}"
    )


@ingest_app.command("notes")
def ingest_notes(
    vault: Path = typer.Option(..., exists=True, file_okay=False, dir_okay=True, help="Path to Obsidian vault"),
    database: Path = typer.Option(Path("rebalance.db"), envvar="REBALANCE_DB", help="SQLite database path"),
    exclude: list[str] = typer.Option(
        [".obsidian/*", ".trash/*", "node_modules/*", ".git/*", ".venv/*", "*/.venv/*"],
        help="Glob patterns to exclude",
    ),
    dry_run: bool = typer.Option(False, help="Show what would be ingested without writing"),
) -> None:
    """Ingest Obsidian vault notes into SQLite (parse, chunk, extract keywords/links)."""
    from rebalance.ingest.note_ingester import ingest_vault

    db_path = database.expanduser().resolve()
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
    database: Path = typer.Option(Path("rebalance.db"), envvar="REBALANCE_DB", help="SQLite database path"),
    model: str = typer.Option("Qwen/Qwen3-Embedding-0.6B", help="HuggingFace model name"),
    batch_size: int = typer.Option(32, help="Batch size for embedding (lower = less memory)"),
    force: bool = typer.Option(False, help="Force re-embed all chunks (use after model change)"),
) -> None:
    """Generate embeddings for ingested chunks via mlx-embeddings."""
    from rebalance.ingest.embedder import embed_chunks

    db_path = database.expanduser().resolve()
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
    database: Path = typer.Option(Path("rebalance.db"), envvar="REBALANCE_DB", help="SQLite database path"),
    top_k: int = typer.Option(10, help="Number of results to return"),
    model: str = typer.Option("Qwen/Qwen3-Embedding-0.6B", help="Embedding model for query"),
) -> None:
    """Semantic search over vault notes."""
    from rebalance.ingest.embedder import query_similar

    db_path = database.expanduser().resolve()
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


@app.command("search")
def search_cmd(
    keyword: str = typer.Argument(..., help="Keyword to search"),
    database: Path = typer.Option(Path("rebalance.db"), envvar="REBALANCE_DB", help="SQLite database path"),
    limit: int = typer.Option(20, help="Max results"),
) -> None:
    """Full-text keyword search over vault files and chunks."""
    from rebalance.ingest.note_ingester import search_by_keyword

    db_path = database.expanduser().resolve()
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
    database: Path = typer.Option(Path("rebalance.db"), envvar="REBALANCE_DB", help="SQLite database path"),
    days: int = typer.Option(7, help="Activity window in days"),
    no_llm: bool = typer.Option(False, help="Skip local LLM synthesis, return raw context only"),
    chat_model: str = typer.Option("Qwen/Qwen3-0.6B", help="Chat model for synthesis"),
) -> None:
    """Ask a natural language question across all data sources."""
    from rebalance.ingest.querier import ask as querier_ask

    db_path = database.expanduser().resolve()
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
    database: Path = typer.Option(Path("rebalance.db"), envvar="REBALANCE_DB", help="SQLite database path"),
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

    db_path = database.expanduser().resolve()
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
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the normalized payload without creating the event"),
) -> None:
    """Create a Google Calendar event from the CLI without needing an MCP host."""
    from rebalance.ingest.calendar import create_calendar_event

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
            _append_calendar_event_log(
                {
                    **base_log_record,
                    "action": "idempotency_hit",
                    "event_id": logged_hit.get("event_id", ""),
                    "html_link": logged_hit.get("html_link", ""),
                }
            )
            typer.echo(f"Idempotency hit for dedupe key: {normalized_dedupe_key}")
            if logged_hit.get("event_id"):
                typer.echo(f"Existing event: {logged_hit['event_id']}")
            if logged_hit.get("html_link"):
                typer.echo(f"Link: {logged_hit['html_link']}")
            return

    existing_event = _find_existing_calendar_event(payload)
    if existing_event:
        log_record = {
            **base_log_record,
            "action": "skipped_existing" if skip_if_exists else "blocked_duplicate",
            "event_id": existing_event["event_id"],
            "html_link": existing_event["html_link"],
        }
        _append_calendar_event_log(log_record)
        typer.echo(f"Matching event already exists: {existing_event['event_id']}")
        if existing_event["html_link"]:
            typer.echo(f"Link: {existing_event['html_link']}")
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
    _append_calendar_event_log(
        {
            **base_log_record,
            "action": "created",
            "event_id": result.event_id,
            "html_link": result.html_link,
        }
    )
    typer.echo(f"Created event: {result.event_id}")
    typer.echo(f"Link: {result.html_link}")


@app.command("calendar-daily-totals")
def calendar_daily_totals_cmd(
    database: Path = typer.Option(Path("rebalance.db"), envvar="REBALANCE_DB", help="SQLite database path"),
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

    db_path = database.expanduser().resolve()
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


@app.command("calendar-daily-report")
def calendar_daily_report_cmd(
    database: Path = typer.Option(Path("rebalance.db"), envvar="REBALANCE_DB", help="SQLite database path"),
    date_str: str = typer.Option(None, "--date", help="Date to report on (YYYY-MM-DD, default: today)"),
    output: Path = typer.Option(None, "--output", "-o", help="Write report to a markdown file instead of stdout"),
) -> None:
    """Generate daily calendar report with project aggregator (exclude keywords configured in temp/calendar_config.json)."""
    from datetime import date
    from rebalance.ingest.daily_report import generate_daily_report
    from rebalance.ingest.calendar_config import CalendarConfig

    db_path = database.expanduser().resolve()
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
    database: Path = typer.Option(Path("rebalance.db"), envvar="REBALANCE_DB", help="SQLite database path"),
    date_str: str = typer.Option(None, "--date", help="Date in target week (YYYY-MM-DD, default: today)"),
    output: Path = typer.Option(None, "--output", "-o", help="Write report to a markdown file instead of stdout"),
) -> None:
    """Generate weekly calendar report (Sun-Sat) with daily summaries and project aggregator."""
    from datetime import date
    from rebalance.ingest.weekly_report import generate_weekly_report
    from rebalance.ingest.calendar_config import CalendarConfig

    db_path = database.expanduser().resolve()
    config = CalendarConfig.load()

    if date_str:
        target_date = date.fromisoformat(date_str)
    else:
        target_date = date.today()

    report = generate_weekly_report(db_path, target_date, config)

    if output:
        out_path = output.expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        typer.echo(f"Report written to {out_path}")
    else:
        typer.echo(report)


@app.command("version")
def version() -> None:
    """Print rebalance CLI version."""
    from rebalance import __version__

    typer.echo(__version__)


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
    """Check if GitHub PAT is configured (returns masked result for security)."""
    token = get_github_token()
    if token:
        masked = token[:10] + "..." + token[-4:] if len(token) > 14 else "***"
        typer.echo(f"✓ GitHub token is configured: {masked}")
    else:
        typer.echo("✗ GitHub token not configured. Set it with:")
        typer.echo("  rebalance config set-github-token <PAT>")


@config_app.command("show-config-path")
def config_show_config_path() -> None:
    """Show where configuration is stored."""
    path = get_config_path()
    typer.echo(f"Config file: {path}")
    typer.echo(f"Gitignored:  {path.parent.name}/ is in .gitignore")

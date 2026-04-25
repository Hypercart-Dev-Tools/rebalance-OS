import json
import pickle
from datetime import date as date_cls, datetime, time as time_cls, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import typer

from rebalance.ingest.preflight import run_preflight
from rebalance.ingest.registry import sync_registry
from rebalance.ingest.config import (
    get_github_token,
    get_github_token_with_source,
    set_github_token,
    clear_github_token,
    get_vault_path,
    set_vault_path,
    get_config_path,
)

app = typer.Typer(help="rebalance CLI")
ingest_app = typer.Typer(help="Ingest and project registry workflows")
config_app = typer.Typer(help="Configuration and secrets management")
app.add_typer(ingest_app, name="ingest")
app.add_typer(config_app, name="config")

GOOGLE_CALENDAR_ENV_PATH = Path("/Users/noelsaw/secrets/google-calendar.env")
CALENDAR_EVENT_LOG_PATH = Path("temp/logs/calendar-event-create.jsonl")

# TODO: support ~/secrets/sleuth-web-api-production.env once a prod Sleuth
# deployment exists — likely via a --env name|production|development flag.
SLEUTH_ENV_PATH = Path("/Users/noelsaw/secrets/sleuth-web-api-development.env")


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


def _load_sleuth_env() -> dict[str, str]:
    """Load Sleuth Web API connection details from the operator-owned env file."""
    if not SLEUTH_ENV_PATH.exists():
        raise typer.BadParameter(f"Sleuth env file not found: {SLEUTH_ENV_PATH}")

    values: dict[str, str] = {}
    for raw_line in SLEUTH_ENV_PATH.read_text(encoding="utf-8").splitlines():
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
            f"(expected in {SLEUTH_ENV_PATH})"
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
    normalized = [repo.strip() for repo in repos if repo.strip()]
    if normalized:
        return sorted(set(normalized))

    from rebalance.ingest.registry import get_projects

    discovered: list[str] = []
    if database_path.exists():
        for project in get_projects(database_path, status="active"):
            discovered.extend(project.get("repos") or [])

    unique = sorted({repo.strip() for repo in discovered if repo and repo.strip()})
    if unique:
        return unique

    raise typer.BadParameter(
        "No GitHub repos provided. Pass --repo owner/name or sync the project registry first."
    )


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


@app.command("github-sync-artifacts")
def github_sync_artifacts(
    repos: list[str] = typer.Option(
        [],
        "--repo",
        help="GitHub repo in owner/name form. Repeat the flag to sync multiple repos.",
    ),
    token: str = typer.Option("", envvar="GITHUB_TOKEN", help="GitHub Personal Access Token"),
    days: int = typer.Option(90, help="Lookback window for changed issues and PRs"),
    database: Path = typer.Option(
        Path("rebalance.db"), envvar="REBALANCE_DB", help="SQLite database path"
    ),
) -> None:
    """Sync detailed GitHub issues, PRs, comments, reviews, checks, and releases."""
    from rebalance.ingest.github_knowledge import sync_github_repo

    db_path = database.expanduser().resolve()
    resolved_token = token.strip() or (get_github_token() or "")
    if not resolved_token:
        raise typer.BadParameter(
            "GitHub token not configured. Use --token, GITHUB_TOKEN, or `rebalance config set-github-token`."
        )

    target_repos = _resolve_github_repos(db_path, repos or [])
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
    database: Path = typer.Option(
        Path("rebalance.db"), envvar="REBALANCE_DB", help="SQLite database path"
    ),
    model: str = typer.Option("Qwen/Qwen3-Embedding-0.6B", help="HuggingFace model name"),
    batch_size: int = typer.Option(32, help="Batch size for embedding"),
    min_chars: int = typer.Option(40, help="Minimum document length to embed"),
    force: bool = typer.Option(False, help="Force re-embed all GitHub documents"),
) -> None:
    """Generate embeddings for the local GitHub artifact corpus."""
    from rebalance.ingest.github_knowledge import embed_github_documents

    db_path = database.expanduser().resolve()
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


@app.command("github-query")
def github_query_cmd(
    text: str = typer.Argument(..., help="Natural language query"),
    database: Path = typer.Option(
        Path("rebalance.db"), envvar="REBALANCE_DB", help="SQLite database path"
    ),
    repo: str = typer.Option("", help="Optional owner/name repo filter"),
    top_k: int = typer.Option(8, help="Number of results to return"),
    model: str = typer.Option("Qwen/Qwen3-Embedding-0.6B", help="Embedding model for query"),
) -> None:
    """Semantic search over the local GitHub issue/PR/comment corpus."""
    from rebalance.ingest.github_knowledge import query_github_documents

    db_path = database.expanduser().resolve()
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
    database: Path = typer.Option(
        Path("rebalance.db"), envvar="REBALANCE_DB", help="SQLite database path"
    ),
) -> None:
    """Populate the unified semantic document layer from existing source tables."""
    from rebalance.ingest.semantic_index import backfill_semantic_documents

    db_path = database.expanduser().resolve()
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
    database: Path = typer.Option(
        Path("rebalance.db"), envvar="REBALANCE_DB", help="SQLite database path"
    ),
    model: str = typer.Option("Qwen/Qwen3-Embedding-0.6B", help="HuggingFace model name"),
    batch_size: int = typer.Option(32, help="Batch size for embedding"),
    min_chars: int = typer.Option(1, help="Minimum document length to embed"),
    force: bool = typer.Option(False, help="Force re-embed matching semantic documents"),
) -> None:
    """Generate embeddings for the unified semantic document layer."""
    from rebalance.ingest.semantic_index import embed_pending

    db_path = database.expanduser().resolve()
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
    database: Path = typer.Option(
        Path("rebalance.db"), envvar="REBALANCE_DB", help="SQLite database path"
    ),
    top_k: int = typer.Option(10, help="Number of results to return"),
    model: str = typer.Option("Qwen/Qwen3-Embedding-0.6B", help="Embedding model for query"),
) -> None:
    """Semantic search over the unified semantic index."""
    from rebalance.ingest.semantic_index import query

    db_path = database.expanduser().resolve()
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
    database: Path = typer.Option(
        Path("rebalance.db"), envvar="REBALANCE_DB", help="SQLite database path"
    ),
    output_format: str = typer.Option("text", "--output", help="Output format: text or json"),
) -> None:
    """Infer current release/readiness state from the local GitHub corpus."""
    from rebalance.ingest.github_readiness import infer_github_release_readiness

    normalized_output = output_format.strip().lower()
    if normalized_output not in {"text", "json"}:
        raise typer.BadParameter("--output must be 'text' or 'json'.")

    db_path = database.expanduser().resolve()
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
    database: Path = typer.Option(
        Path("rebalance.db"), envvar="REBALANCE_DB", help="SQLite database path"
    ),
    output_format: str = typer.Option("text", "--output", help="Output format: text or json"),
) -> None:
    """Suggest open issues that likely map to merged PRs and may be ready to close."""
    from rebalance.ingest.github_reconciliation import infer_issue_pr_close_candidates

    normalized_output = output_format.strip().lower()
    if normalized_output not in {"text", "json"}:
        raise typer.BadParameter("--output must be 'text' or 'json'.")

    db_path = database.expanduser().resolve()
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
    vault: Path = typer.Option(None, "--vault", envvar="REBALANCE_VAULT", help="Obsidian vault path for weekly note write-back"),
    write_week_note: bool = typer.Option(False, "--write-week-note", help="Write week-of-YYYY-MM-DD.md into the vault under Weekly Notes/"),
    reingest_note: bool = typer.Option(True, "--reingest-note/--no-reingest-note", help="When writing a week note, re-ingest and embed it into the local knowledge store"),
) -> None:
    """Generate weekly calendar report (Sun-Sat) with daily summaries and project aggregator."""
    from datetime import date
    from rebalance.ingest.weekly_report import generate_weekly_report, write_weekly_note
    from rebalance.ingest.calendar_config import CalendarConfig

    db_path = database.expanduser().resolve()
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


@app.command("sleuth-sync")
def sleuth_sync_cmd(
    active_only: bool = typer.Option(
        False,
        "--active-only/--all",
        help="Only fetch currently active reminders (default: all)",
    ),
    database: Path = typer.Option(
        Path("rebalance.db"),
        "--database-path",
        envvar="REBALANCE_DB",
        help="SQLite database path",
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit full sync result as JSON"),
) -> None:
    """Pull Slack reminders from the Sleuth Web API and upsert them into SQLite."""
    from rebalance.ingest.sleuth_reminders import sync_sleuth_reminders

    env_data = _load_sleuth_env()
    db_path = database.expanduser().resolve()
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

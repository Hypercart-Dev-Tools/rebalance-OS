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

# Secret env files resolve via rebalance.paths.resolve_secret_path which honors
# REBALANCE_SECRETS_DIR, ~/.config/rebalance-os/config.json (set via
# `rebalance config set-secrets-dir`), and ~/secrets as the legacy default.
# TODO: support sleuth-web-api-production.env once a prod Sleuth deployment
# exists — likely via a --env name|production|development flag.
#
# Resolved at import time so tests can patch `rebalance.cli.SLEUTH_ENV_PATH` to
# redirect subsequent reads. (GOOGLE_CALENDAR_ENV_PATH / CALENDAR_EVENT_LOG_PATH
# moved to rebalance.cli.calendar.)
SLEUTH_ENV_PATH = resolve_secret_path("sleuth-web-api-development.env")


def _load_sleuth_env(which: str = "production") -> dict[str, str]:
    """Thin CLI wrapper — converts config.get_sleuth_credentials() errors to typer.BadParameter."""
    from rebalance.ingest.config import get_sleuth_credentials
    try:
        return get_sleuth_credentials(which)
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc


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
    from rebalance.ingest.note_builder import build_dashboard_note_content, write_dashboard_note
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


@app.command("serve")
def serve_cmd(
    port: int = typer.Option(8787, "--port", "-p", help="Port to listen on"),
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address"),
) -> None:
    """Start the local web dashboard (auth log, future dashboards).

    Opens http://localhost:<port>/auth-log in your browser automatically.
    Requires: pip install 'rebalance-os[server]'
    """
    try:
        import uvicorn
    except ImportError:
        typer.echo("uvicorn not installed. Run: pip install 'rebalance-os[server]'")
        raise typer.Exit(1)

    import webbrowser
    import threading

    url = f"http://{host}:{port}"
    typer.echo(f"Starting rebalance web server at {url}")
    typer.echo(f"  Auth log: {url}/auth-log")
    threading.Timer(0.8, lambda: webbrowser.open(f"{url}/auth-log")).start()

    from rebalance.web import app as web_app
    uvicorn.run(web_app, host=host, port=port, log_level="warning")


@app.command("version")
def version() -> None:
    """Print rebalance CLI version."""
    from rebalance import __version__

    typer.echo(__version__)



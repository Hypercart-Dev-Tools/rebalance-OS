"""`rebalance ingest *` subcommands — preflight, sync, infer, notes, embed.

Extracted from the cli monolith (Phase 5). Registers on the shared `ingest_app`
sub-Typer from `_core`.
"""

from __future__ import annotations

from pathlib import Path

import typer

from rebalance.cli._core import ingest_app
from rebalance.ingest.config import get_github_token
from rebalance.ingest.preflight import run_preflight
from rebalance.ingest.registry import sync_registry
from rebalance.paths import DatabaseNotFoundError, DBOption, resolve_database_path


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
                "⚠ GitHub PAT not configured. Set it with:\n"
                "  rebalance config set-github-token <PAT>"
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
        f"deleted_stale={summary.deleted_stale_inferred_count}, "
        f"skipped_curated={summary.skipped_curated_count}"
    )
    if summary.skipped_curated_names:
        typer.echo(
            "  Skipped (curated rows own these names; inference never overwrites them): "
            + ", ".join(summary.skipped_curated_names)
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
    from rebalance.ingest.note_ingester import ingest_notes_command

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    result = ingest_notes_command(
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
    from rebalance.ingest.embedder import embed_vault_chunks

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    typer.echo(f"Embedding chunks with {model} (batch_size={batch_size})...")
    result = embed_vault_chunks(
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

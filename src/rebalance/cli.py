from pathlib import Path

import typer

from rebalance.ingest.preflight import run_preflight
from rebalance.ingest.registry import sync_registry
from rebalance.ingest.config import get_github_token, set_github_token, get_config_path

app = typer.Typer(help="rebalance CLI")
ingest_app = typer.Typer(help="Ingest and project registry workflows")
config_app = typer.Typer(help="Configuration and secrets management")
app.add_typer(ingest_app, name="ingest")
app.add_typer(config_app, name="config")


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
    days: int = typer.Option(14, help="Number of days to look back (max ~14 due to GitHub API limits)"),
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

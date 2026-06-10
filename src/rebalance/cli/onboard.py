"""`rebalance onboard` — guided setup: token, project discovery, initial refresh.

Extracted from the cli monolith (Phase 5). Registers on the shared Typer `app`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from rebalance.cli._core import app
from rebalance.paths import (
    DatabaseNotFoundError,
    DBOption,
    canonical_database_path,
    resolve_database_path,
)


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
        refresh = refresh_index(db)  # default recipe: raw sources + code/semantic/sync
        errors = refresh.get("errors", [])
        if errors:
            typer.echo(f"  Refresh finished with {len(errors)} error(s):", err=True)
            for e in errors:
                typer.echo(f"    - {e.get('scope')}: {e.get('error')}", err=True)
        else:
            typer.echo("Initial refresh complete.")

    typer.echo("\nOnboarding done. Run `rebalance doctor` to verify the install.")

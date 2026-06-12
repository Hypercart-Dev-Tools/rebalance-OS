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


# Status glyphs — same vocabulary the /welcome skill renders; the CLI is the
# no-LLM parity client of the lifecycle contract.
_STATUS_GLYPHS = {
    "done": "[x]",
    "now": " ->",
    "next": "( )",
    "blocked": " !!",
    "skipped": "(s)",
}


def _render_setup_status(database: Path | None) -> None:
    """Render the setup stage map (where am I / what's next) from one
    evaluate_setup call — the contract is the source of truth, never this
    renderer."""
    from rebalance.ingest.config import get_vault_path
    from rebalance.ingest.lifecycle import evaluate_setup

    vault = (get_vault_path() or "").strip()
    try:
        db = database or resolve_database_path()
    except DatabaseNotFoundError:
        db = canonical_database_path()

    report = evaluate_setup(
        vault_path=Path(vault).expanduser() if vault else None,
        database_path=db,
    )
    typer.echo(
        f"rebalance setup — complete: {report['setup_complete']}"
        + (f" · current step: {report['now']}" if report["now"] else "")
    )
    for stage in report["stages"]:
        optional = " (optional)" if stage["optional"] else ""
        skipped_note = " — skipped; re-enterable" if stage["status"] == "skipped" else ""
        typer.echo(
            f"  {_STATUS_GLYPHS[stage['status']]} {stage['title']}{optional}"
            f" — {stage['detail']}{skipped_note}"
        )
        if stage["status"] in ("now", "blocked"):
            typer.echo(f"      fix: {stage['remediation']}")


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
    status: bool = typer.Option(
        False, "--status",
        help="Render the setup stage map (where am I / what's next) and exit.",
    ),
    database: Path | None = DBOption(),
) -> None:
    """Guided onboarding: persist the GitHub token, discover & register projects, refresh.

    One command for the sequence that was previously only an agent-driven MCP
    flow — so it doesn't fall between the cracks. Idempotent: safe to re-run.
    `--status` renders the same lifecycle stage map the /welcome agent and
    onboarding_status MCP tool serve.
    """
    from dataclasses import asdict, is_dataclass

    from rebalance.ingest.config import (
        get_github_token_with_source,
        get_vault_path,
        set_github_token,
    )
    from rebalance.ingest.index_ops import refresh_index
    from rebalance.ingest.preflight import confirm_and_write, discover_candidates

    if status:
        _render_setup_status(database)
        return

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

    # 7. Optional stages + graduation — CLI parity with the /welcome flow.
    #    Interactive only: --yes must never launch OAuth browser flows or
    #    install launchd jobs silently.
    if not yes:
        _offer_optional_stages(db)
    else:
        typer.echo(
            "\nOptional next steps (skipped under --yes): Calendar/Gmail OAuth "
            "(scripts/setup_*_oauth.py), scheduler fleet (scripts/install_scheduler.sh), "
            "first pulse (scripts/pulse_web_sync.sh)."
        )

    typer.echo("\nOnboarding done. Run `rebalance onboard --status` for the stage map"
               " and `rebalance doctor` to verify the install.")


def _offer_optional_stages(database: Path | None) -> None:
    """Offer each incomplete optional stage from the lifecycle contract.

    Stage list, executors, and skip persistence all come from the contract —
    this function only renders prompts and dispatches `cli:`/`script:`
    executors (the same hints the /welcome agent uses).
    """
    import shlex
    import subprocess
    import sys

    import questionary

    from rebalance.ingest.config import get_vault_path, set_onboarding_stage_skipped
    from rebalance.ingest.lifecycle import evaluate_setup
    from rebalance.paths import find_project_root

    vault = (get_vault_path() or "").strip()
    report = evaluate_setup(
        vault_path=Path(vault).expanduser() if vault else None,
        database_path=database,
    )
    repo_root = find_project_root(Path(__file__).resolve())
    offered = [
        s for s in report["stages"]
        if s["optional"] and s["status"] in ("next", "blocked", "skipped")
    ]
    if not offered:
        return

    if repo_root is None:
        # Installed outside a checkout (e.g. pipx): the script/installer
        # executors have nowhere to run. Point at the remediation instead of
        # crashing in an arbitrary cwd (review finding).
        typer.echo("\nOptional steps (run from a rebalance-OS checkout):")
        for stage in offered:
            typer.echo(f"  - {stage['title']}: {stage['remediation']}")
        return

    venv_python = repo_root / ".venv" / "bin" / "python"
    python_bin = str(venv_python) if venv_python.exists() else sys.executable

    typer.echo("\nOptional steps:")
    for stage in offered:
        if stage["status"] == "blocked":
            typer.echo(f"  - {stage['title']}: blocked ({stage['detail']}) — skipping offer.")
            continue
        run_it = questionary.confirm(
            f"{stage['title']} — set up now?", default=False
        ).ask()
        if run_it is None:
            # Ctrl+C / EOF: abort the offers without persisting anything —
            # an interrupt is not a skip decision (review finding).
            typer.echo("  Cancelled — no skip state recorded.")
            return
        if not run_it:
            set_onboarding_stage_skipped(stage["id"])
            typer.echo(f"  Skipped {stage['title']} — re-enterable via `rebalance onboard` or /welcome.")
            continue
        set_onboarding_stage_skipped(stage["id"], False)
        kind, _, target = stage["executor"].partition(":")
        if kind == "script":
            cmd = [python_bin, str(repo_root / target)]
        elif kind == "cli" and target.startswith("bash "):
            cmd = shlex.split(target)
        else:
            typer.echo(f"  Run manually: {stage['remediation']}")
            continue
        typer.echo(f"  Running: {' '.join(cmd)}")
        proc = subprocess.run(cmd, cwd=repo_root)
        if proc.returncode != 0:
            typer.echo(f"  ! {stage['title']} exited {proc.returncode} — fix: {stage['remediation']}", err=True)

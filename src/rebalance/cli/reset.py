"""`rebalance reset` — return the machine to a pre-onboarding state (Phase 6).

Dry-run by default: prints exactly what would be removed. `--force` executes.
The vault is NEVER touched — notes, the registry markdown, and projects.yaml
are operator content. Keyring entries are enumerated but only deleted with an
explicit `--include-keyring`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import typer

from rebalance.cli._core import app
from rebalance.paths import (
    DatabaseNotFoundError,
    DBOption,
    canonical_database_path,
    resolve_database_path,
    resolve_oauth_token_path,
)

# Secrets stored under the rebalance-os keyring service. Enumerated (and only
# ever deleted) by name — there is no portable "list all" keyring API.
KEYRING_KEYS = (
    "github_token",
    "figma_token",
    "calendar_oauth_token",
    "gmail_oauth_token",
    "sleuth_web_api",
)

OAUTH_FILE_SERVICES = ("calendar", "gmail")

LAUNCHD_PREFIX = "com.rebalance-os."


def _installed_plists() -> list[Path]:
    agents = Path.home() / "Library" / "LaunchAgents"
    return sorted(agents.glob(f"{LAUNCHD_PREFIX}*.plist"))


@app.command("reset")
def reset_cmd(
    force: bool = typer.Option(
        False, "--force",
        help="Actually execute. Without it, this is a dry-run plan.",
    ),
    include_keyring: bool = typer.Option(
        False, "--include-keyring",
        help="Also delete the enumerated keyring secrets (default: list only).",
    ),
    database: Path | None = DBOption(),
) -> None:
    """Return the machine to a pre-onboarding state. Vault content is never touched.

    Unloads and removes the launchd fleet, deletes the operator config
    (temp/rbos.config) and the SQLite knowledge base (+ -wal/-shm sidecars),
    and enumerates keyring secrets. Re-run setup afterward with /welcome or
    `rebalance onboard`.
    """
    from rebalance.ingest.config import _keyring_delete, _keyring_get, get_config_path

    plists = _installed_plists()
    config_path = get_config_path()
    try:
        db_path: Path | None = database or resolve_database_path()
    except DatabaseNotFoundError:
        # Half-reset recovery (review finding): a prior reset may have removed
        # the config that pointed at the DB — still sweep the canonical
        # location so the files aren't orphaned on re-run.
        candidate = canonical_database_path()
        db_path = candidate if candidate.exists() else None
    db_files = (
        [p for p in (db_path, *(db_path.with_name(db_path.name + s) for s in ("-wal", "-shm")))
         if p and p.exists()]
        if db_path else []
    )
    oauth_files = [
        p for p in (resolve_oauth_token_path(s) for s in OAUTH_FILE_SERVICES) if p.exists()
    ]
    keyring_present = [k for k in KEYRING_KEYS if _keyring_get(k)]

    mode = "RESET" if force else "DRY-RUN (pass --force to execute)"
    typer.echo(f"rebalance reset — {mode}")
    typer.echo(f"  launchd jobs to unload+remove: {len(plists)}")
    for p in plists:
        typer.echo(f"    - {p.name}")
    typer.echo(f"  operator config: {config_path}{'' if config_path.exists() else ' (absent)'}")
    typer.echo(f"  knowledge base: {db_path or '(none resolved)'} ({len(db_files)} file(s))")
    typer.echo(f"  OAuth token files: {len(oauth_files)}")
    for p in oauth_files:
        typer.echo(f"    - {p}")
    typer.echo(
        "  keyring secrets present: " + (", ".join(keyring_present) or "none")
        + ("" if include_keyring else "  [kept — pass --include-keyring to delete]")
    )
    typer.echo("  vault: untouched (registry markdown and projects.yaml stay where they are)")
    typer.echo("  note: com.user.* utility agents (git-pulse, stickies) have their own installers and are not touched")

    if not force:
        return

    for plist in plists:
        subprocess.run(["launchctl", "unload", str(plist)], capture_output=True)
        plist.unlink(missing_ok=True)
        typer.echo(f"  removed {plist.name}")
    if config_path.exists():
        config_path.unlink()
        typer.echo(f"  removed {config_path}")
    for f in db_files:
        f.unlink(missing_ok=True)
        typer.echo(f"  removed {f}")
    for f in oauth_files:
        f.unlink(missing_ok=True)
        typer.echo(f"  removed {f}")
    if include_keyring:
        for key in keyring_present:
            ok = _keyring_delete(key)
            typer.echo(f"  keyring {key}: {'deleted' if ok else 'NOT deleted'}")

    typer.echo("\nReset complete. Start over with /welcome or `rebalance onboard`.")

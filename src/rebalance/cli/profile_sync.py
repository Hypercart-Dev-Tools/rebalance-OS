"""`rebalance profile-sync` — per-repo timings from the most recent GitHub sync.

Extracted from the cli monolith (Phase 5). Registers on the shared Typer `app`.
"""

from __future__ import annotations

from pathlib import Path

import typer

from rebalance.cli._core import app, _PROJECT_ROOT


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

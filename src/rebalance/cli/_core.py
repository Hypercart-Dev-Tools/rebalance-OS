"""Shared Typer apps and process-wide constants for the rebalance CLI package.

Defining the app instances here — rather than in ``__init__`` — lets the
per-domain command modules (``refresh``, ``github``, ``calendar``, …) import
them and register their commands without a circular dependency on the package
root. ``__init__`` then imports every command module so the full CLI is wired.
"""

from __future__ import annotations

from pathlib import Path

import typer

from rebalance.paths import resolve_project_root

app = typer.Typer(help="rebalance CLI")
ingest_app = typer.Typer(help="Ingest and project registry workflows")
config_app = typer.Typer(help="Configuration and secrets management")
app.add_typer(ingest_app, name="ingest")
app.add_typer(config_app, name="config")


# Resolved once so all paths in the CLI process agree on where the project
# lives. Uses the walk-up resolver so layout changes (e.g., deeper nesting)
# don't silently return a wrong directory the way parents[3] would.
_PROJECT_ROOT = resolve_project_root(Path(__file__))

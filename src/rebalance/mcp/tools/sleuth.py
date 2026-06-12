from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP, database_path: Path) -> None:
    @mcp.tool()
    def sleuth_sync_reminders(active_only: bool = False) -> dict[str, Any]:
        """
        Pull Slack reminders from the Sleuth Web API and upsert them into SQLite.

        Credentials are loaded from ~/secrets/sleuth-web-api-development.env
        (operator-owned, mode 600). Set active_only=True to fetch only the
        currently active reminders; default pulls all states so completed
        reminders get their terminal state mirrored.
        """
        from rebalance.ingest.sleuth_reminders import sync_sleuth

        return sync_sleuth(database_path, active_only=active_only).as_dict()

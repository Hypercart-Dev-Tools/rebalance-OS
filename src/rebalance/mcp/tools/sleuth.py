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
        from rebalance.ingest.config import get_sleuth_credentials
        from rebalance.ingest.sleuth_reminders import sync_sleuth_reminders

        env_data = get_sleuth_credentials()
        result = sync_sleuth_reminders(
            base_url=env_data["SLEUTH_WEB_API_BASE_URL"],
            token=env_data["SLEUTH_WEB_API_TOKEN"],
            workspace_name=env_data["SLEUTH_WORKSPACE_NAME"],
            database_path=database_path,
            active_only=active_only,
        )
        return result.as_dict()

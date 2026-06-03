from __future__ import annotations

import logging
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from rebalance.mcp.tools import calendar, hygiene, index, onboarding, projects, retrieval, sleuth

logger = logging.getLogger(__name__)


def create_server(database_path: Path) -> FastMCP:
    mcp = FastMCP("rebalance")
    projects.register(mcp, database_path)
    onboarding.register(mcp, database_path)
    retrieval.register(mcp, database_path)
    calendar.register(mcp, database_path)
    index.register(mcp, database_path)
    hygiene.register(mcp, database_path)
    sleuth.register(mcp, database_path)
    return mcp


def main() -> None:
    from rebalance.paths import DatabaseNotFoundError, canonical_database_path, resolve_database_path

    try:
        database_path = resolve_database_path()
    except DatabaseNotFoundError:
        # First run: no database exists yet. Create the canonical path so
        # MCP-driven onboarding can proceed — the onboarding tools need
        # the server to be running before any data exists.
        database_path = canonical_database_path()
        database_path.parent.mkdir(parents=True, exist_ok=True)
        import sqlite3
        sqlite3.connect(database_path).close()
        logger.info("Created empty database at %s", database_path)
    server = create_server(database_path=database_path)
    server.run()


if __name__ == "__main__":
    main()

"""GH-93 MCP probe tools: peek_source (raw rows) + get_next_actions (persisted ranking).

Drives the tools through the real FastMCP server (create_server) so the registration,
allowlist guard, limit clamp, and None-safety are all exercised end to end.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from rebalance.ingest.db import db_connection, ensure_github_schema
from rebalance.mcp.server import create_server


def _call(server, name: str, args: dict) -> dict:
    """Invoke an MCP tool and decode its JSON content block to a dict."""
    content, _ = asyncio.run(server.call_tool(name, args))
    return json.loads(content[0].text)


class McpProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.db = Path(self._tmp.name) / "rebalance.db"

    def _seed_github_row(self) -> None:
        with db_connection(self.db) as conn:
            ensure_github_schema(conn)
            conn.execute(
                "INSERT INTO github_activity (login, repo_full_name, scan_date, commits, "
                "pushes, prs_opened, prs_merged, issues_opened, issue_comments, reviews, "
                "last_active_at, scanned_at) VALUES "
                "('me','a/b','2026-06-01',1,0,0,0,0,0,0,'2026-06-01T00:00:00Z','2026-06-01T00:00:00Z')"
            )
            conn.commit()

    def test_peek_source_returns_rows_for_known_source(self) -> None:
        self._seed_github_row()
        server = create_server(self.db)
        out = _call(server, "peek_source", {"source": "github_activity", "limit": 5})
        self.assertEqual(out["source"], "github_activity")
        self.assertEqual(out["count"], 1)
        self.assertEqual(out["rows"][0]["repo_full_name"], "a/b")

    def test_peek_source_rejects_unknown_source(self) -> None:
        server = create_server(self.db)
        out = _call(server, "peek_source", {"source": "secrets; DROP TABLE x"})
        self.assertIn("error", out)
        self.assertIn("github_activity", out["valid_sources"])
        self.assertNotIn("rows", out)

    def test_peek_source_clamps_limit(self) -> None:
        self._seed_github_row()
        server = create_server(self.db)
        # 9999 must not raise and must clamp (only 1 row exists, so count==1).
        out = _call(server, "peek_source", {"source": "github_activity", "limit": 9999})
        self.assertEqual(out["count"], 1)

    def test_get_next_actions_none_safe_on_fresh_db(self) -> None:
        server = create_server(self.db)
        out = _call(server, "get_next_actions", {})
        self.assertEqual(out["ranked"], [])
        self.assertIn("note", out)


if __name__ == "__main__":
    unittest.main()

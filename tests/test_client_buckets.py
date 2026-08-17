"""Phase 1 client auto-discovery: owner-as-client inference + derived buckets.

Contract under test (PROJECT/2-WORKING/CLIENT-AUTO-DISCOVERY.md):
  - curated ``client`` beats machine ``client_inferred``
  - ``get_clients`` groups project names by effective client
  - a project with neither client lands in the ``(unassigned)`` bucket
  - ``_infer_client`` returns the dominant repo owner, None for calendar-only seeds
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rebalance.ingest.project_inference import _ProjectSeed, _infer_client
from rebalance.ingest.registry import effective_client, get_clients, sync_db


class ClientBucketTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.db_path = Path(self._tmp.name) / "rebalance.db"

    def test_effective_client_curated_beats_inferred(self) -> None:
        self.assertEqual(
            effective_client({"client": "Acme", "client_inferred": "anthropics"}),
            "Acme",
        )
        self.assertEqual(effective_client({"client_inferred": "anthropics"}), "anthropics")
        self.assertIsNone(effective_client({}))
        self.assertIsNone(effective_client(None))

    def test_get_clients_groups_by_effective_client(self) -> None:
        sync_db(
            self.db_path,
            {
                "projects": [
                    {"name": "Curated Win", "custom_fields": {"client": "Acme", "client_inferred": "anthropics"}},
                    {"name": "Inferred Only", "custom_fields": {"client_inferred": "anthropics"}},
                    {"name": "No Client", "custom_fields": {}},
                ]
            },
        )
        buckets = get_clients(self.db_path)
        self.assertEqual(buckets["Acme"], ["Curated Win"])
        self.assertEqual(buckets["anthropics"], ["Inferred Only"])
        self.assertEqual(buckets["(unassigned)"], ["No Client"])

    def test_infer_client_owner_as_client(self) -> None:
        github_seed = _ProjectSeed(
            key="anthropics/claude-code",
            display_name="Claude Code",
            repos={"anthropics/claude-code", "anthropics/claude-cli"},
        )
        self.assertEqual(_infer_client(github_seed), "anthropics")

        calendar_only = _ProjectSeed(key="calendar:ltvera", display_name="LTVera", repos=set())
        self.assertIsNone(_infer_client(calendar_only))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import pulse_server  # noqa: E402


class ExtractFigmaKeyTests(unittest.TestCase):
    def test_accepts_raw_key(self) -> None:
        self.assertEqual(
            pulse_server._extract_figma_file_key("VoQWc0fhO020JoxOyqeE1P"),
            "VoQWc0fhO020JoxOyqeE1P",
        )

    def test_extracts_key_from_design_url(self) -> None:
        self.assertEqual(
            pulse_server._extract_figma_file_key(
                "https://www.figma.com/design/VoQWc0fhO020JoxOyqeE1P/Norman-s-Nursery?t=x"
            ),
            "VoQWc0fhO020JoxOyqeE1P",
        )

    def test_rejects_non_figma_url(self) -> None:
        self.assertIsNone(
            pulse_server._extract_figma_file_key("https://example.com/design/VoQWc0fhO020JoxOyqeE1P")
        )


class AddFigmaProjectApiTests(unittest.TestCase):
    def test_adds_new_key_and_returns_sync_counts(self) -> None:
        # Patch the names the handler actually binds (module-level imports in
        # pulse_server) — never with create=True, which silently masked an
        # API drift here for months and let the test mutate the operator's
        # real config (failed 409 locally, wrote real config in CI).
        client = TestClient(pulse_server.app)

        with patch.object(pulse_server, "_run_pulse_render") as run_render, \
             patch.object(pulse_server, "add_figma_file_key", return_value=True) as add_key, \
             patch.object(pulse_server, "get_figma_file_keys", return_value=["VoQWc0fhO020JoxOyqeE1P"]), \
             patch.object(pulse_server, "resolve_database_path", return_value=Path("/tmp/rebalance.db")), \
             patch.object(pulse_server, "refresh_index", return_value={
                 "results": [{
                     "scope": "figma",
                     "comments_fetched": 12,
                     "comments_inserted": 12,
                     "comments_updated": 0,
                     "errors": [],
                 }],
                 "errors": [],
             }):
            run_render.return_value.returncode = 0
            run_render.return_value.stderr = ""
            res = client.post("/api/figma/projects", json={"project": "VoQWc0fhO020JoxOyqeE1P"})

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["file_key"], "VoQWc0fhO020JoxOyqeE1P")
        self.assertTrue(data["sync_ok"])
        self.assertEqual(data["comments_fetched"], 12)
        add_key.assert_called_once_with("VoQWc0fhO020JoxOyqeE1P")

    def test_invalid_input_returns_400(self) -> None:
        client = TestClient(pulse_server.app)
        res = client.post("/api/figma/projects", json={"project": "not-a-figma-link"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("figma file key", res.json()["detail"].lower())


if __name__ == "__main__":
    unittest.main()

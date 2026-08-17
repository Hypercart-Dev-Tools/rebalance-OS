from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "generate_capabilities_index.py"
MANIFEST_PATH = ROOT / "capabilities" / "manifest.yaml"
INDEX_PATH = ROOT / "capabilities" / "INDEX.md"

sys.path.insert(0, str(ROOT / "scripts"))
import generate_capabilities_index as generator  # noqa: E402


class CapabilitiesManifestTests(unittest.TestCase):
    def test_manifest_schema_matches_scoped_contract(self) -> None:
        entries = generator.load_manifest(MANIFEST_PATH)
        self.assertEqual([entry["id"] for entry in entries], ["relay-xyz", "xyz", "consult"])
        for entry in entries:
            self.assertEqual(set(entry), set(generator.REQUIRED_FIELDS))
            self.assertIsInstance(entry["owner"], str)
            self.assertTrue(entry["owner"])
            for field in generator.REQUIRED_FIELDS[2:]:
                self.assertIsInstance(entry[field], list)
                for item in entry[field]:
                    self.assertIsInstance(item, str)
                    self.assertTrue(item)

    def test_checked_in_index_matches_manifest(self) -> None:
        entries = generator.load_manifest(MANIFEST_PATH)
        expected = generator.render_index(entries, MANIFEST_PATH)
        actual = INDEX_PATH.read_text()
        self.assertEqual(actual, expected)

    def test_generator_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "INDEX.md"
            command = [
                sys.executable,
                str(SCRIPT_PATH),
                "--manifest",
                str(MANIFEST_PATH),
                "--output",
                str(output_path),
            ]

            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, msg=first.stderr)
            first_bytes = output_path.read_bytes()

            second = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(second.returncode, 0, msg=second.stderr)
            second_bytes = output_path.read_bytes()

            self.assertEqual(first_bytes, second_bytes)

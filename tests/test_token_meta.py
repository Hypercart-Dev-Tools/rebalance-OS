"""Tests for the per-token sidecar metadata (ingest/token_meta.py)."""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from rebalance.ingest import token_meta


class TokenMetaTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        path = Path(self._tmp.name) / "token_meta.json"
        p = patch.object(token_meta, "_meta_path", return_value=path)
        p.start()
        self.addCleanup(p.stop)

    def test_fingerprint_is_stable_and_not_the_raw_token(self) -> None:
        fp = token_meta.fingerprint("ghp_secret_value")
        self.assertEqual(fp, token_meta.fingerprint("ghp_secret_value"))
        self.assertNotIn("secret", fp)
        self.assertEqual(len(fp), 12)

    def test_first_added_preserved_across_resets(self) -> None:
        r1 = token_meta.record_token_set("github", "ghp_aaa", kind="classic PAT", source="manual")
        first = r1["first_added_at"]
        # Re-set the SAME token (e.g. gh-fallback re-persist) → first_added unchanged.
        r2 = token_meta.record_token_set("github", "ghp_aaa", kind="classic PAT", source="gh-fallback")
        self.assertEqual(r2["first_added_at"], first)
        self.assertEqual(r2["set_count"], 2)
        self.assertEqual(token_meta.current_token_meta("github")["first_added_at"], first)

    def test_new_token_value_starts_fresh_record(self) -> None:
        r1 = token_meta.record_token_set("github", "ghp_aaa", kind="classic PAT")
        r2 = token_meta.record_token_set("github", "ghp_bbb", kind="classic PAT")
        self.assertNotEqual(r1["fingerprint"], r2["fingerprint"])
        self.assertEqual(r2["set_count"], 1)
        # current points at the newest token.
        self.assertEqual(token_meta.current_token_meta("github")["fingerprint"], r2["fingerprint"])

    def test_current_is_none_when_empty(self) -> None:
        self.assertIsNone(token_meta.current_token_meta("github"))

    def test_age_text(self) -> None:
        now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
        six_days = (now - timedelta(days=6)).isoformat()
        two_hours = (now - timedelta(hours=2)).isoformat()
        self.assertEqual(token_meta.age_text(six_days, now=now), "6d")
        self.assertEqual(token_meta.age_text(two_hours, now=now), "2.0h")
        self.assertEqual(token_meta.age_text(None, now=now), "")


if __name__ == "__main__":
    unittest.main()

"""Tests for the first-class git-pulse collector-health read (ingest/pulse_health).

Covers the ported classify() thresholds (ALIVE/STALE/ALERT/DEGRADED/NO PUSHES),
flat-YAML device parsing, sync-repo resolution via rebalance's pulse_target_path,
and graceful empties when git-pulse is not configured.
"""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from rebalance.ingest import pulse_health
from rebalance.ingest.pulse_health import (
    CollectorHealth,
    classify,
    read_collector_health,
    resolve_sync_repo_dir,
)

NOW = datetime(2026, 6, 3, 0, 0, 0, tzinfo=timezone.utc)


def _h(last_scan, **kw):
    return CollectorHealth(
        device_id="d", device_name="Device", last_scan_utc=last_scan, **kw
    )


class ClassifyTests(unittest.TestCase):
    def test_alive_within_warn_window(self) -> None:
        h = classify(_h(NOW - timedelta(hours=1)), NOW)
        self.assertEqual(h.state, "ALIVE")
        self.assertEqual(h.priority, 3)
        self.assertTrue(h.healthy)

    def test_stale_between_warn_and_alert(self) -> None:
        h = classify(_h(NOW - timedelta(hours=5)), NOW)
        self.assertEqual(h.state, "STALE")
        self.assertEqual(h.priority, 2)

    def test_alert_past_alert_window(self) -> None:
        h = classify(_h(NOW - timedelta(hours=30)), NOW)
        self.assertEqual(h.state, "ALERT")
        self.assertEqual(h.priority, 1)

    def test_degraded_on_scan_failures_regardless_of_age(self) -> None:
        h = classify(_h(NOW - timedelta(minutes=10), repo_scan_failures=3), NOW)
        self.assertEqual(h.state, "DEGRADED")
        self.assertEqual(h.priority, 1)

    def test_degraded_on_scan_status(self) -> None:
        h = classify(_h(NOW - timedelta(minutes=10), scan_status="degraded"), NOW)
        self.assertEqual(h.state, "DEGRADED")

    def test_no_pushes_when_never_scanned(self) -> None:
        h = classify(_h(None), NOW)
        self.assertEqual(h.state, "NO PUSHES")
        self.assertEqual(h.priority, 0)
        self.assertIsNone(h.age_hours)


class ReadCollectorHealthTests(unittest.TestCase):
    def _write_device(self, devices_dir: Path, name: str, **fields) -> None:
        lines = [f'{k}: "{v}"' for k, v in fields.items()]
        (devices_dir / f"{name}.yaml").write_text("\n".join(lines) + "\n")

    def test_reads_and_sorts_worst_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            devices = repo / "devices"
            devices.mkdir()
            self._write_device(
                devices, "alive-dev",
                device_id="alive", device_name="Alive Box",
                last_scan_utc=(NOW - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
                scan_status="ok", repo_scan_failures="0",
            )
            self._write_device(
                devices, "broken-dev",
                device_id="broken", device_name="Broken Box",
                last_scan_utc=(NOW - timedelta(minutes=20)).isoformat().replace("+00:00", "Z"),
                scan_status="degraded", repo_scan_failures="4",
                scan_failure_examples="repo-a,repo-b",
            )
            out = read_collector_health(sync_repo_dir=repo, now=NOW)
        self.assertEqual([h.device_name for h in out], ["Broken Box", "Alive Box"])
        self.assertEqual(out[0].state, "DEGRADED")
        self.assertEqual(out[0].repo_scan_failures, 4)
        self.assertEqual(out[0].scan_failure_examples, "repo-a,repo-b")
        self.assertEqual(out[1].state, "ALIVE")

    def test_empty_when_no_devices_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(read_collector_health(sync_repo_dir=Path(tmp), now=NOW), [])

    def test_empty_when_unresolvable(self) -> None:
        with patch.object(pulse_health, "resolve_sync_repo_dir", return_value=None):
            self.assertEqual(read_collector_health(now=NOW), [])


class ResolveSyncRepoDirTests(unittest.TestCase):
    def test_prefers_pulse_target_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "devices").mkdir()
            with patch(
                "rebalance.ingest.config.get_pulse_config",
                return_value={"pulse_target_path": str(repo)},
            ):
                self.assertEqual(resolve_sync_repo_dir(), repo)

    def test_none_when_target_has_no_devices_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "rebalance.ingest.config.get_pulse_config",
                return_value={"pulse_target_path": tmp},
            ), patch.dict("os.environ", {"GIT_PULSE_CONFIG_DIR": tmp}, clear=False):
                # pulse_target_path has no devices/, and the bogus config dir has
                # no config.sh/repo → unresolvable.
                self.assertIsNone(resolve_sync_repo_dir())


if __name__ == "__main__":
    unittest.main()

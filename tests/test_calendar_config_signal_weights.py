"""SignalWeights: seeded defaults, temp-config override, and the per-person
additivity gate (Matt-first decision)."""

import json
import tempfile
import unittest
from pathlib import Path

from rebalance.ingest.calendar_config import (
    SignalWeights,
    load_signal_weights,
    team_persons_passing_additivity,
)


class TestSignalWeightsDefaults(unittest.TestCase):
    def test_load_defaults_when_file_missing(self) -> None:
        weights = load_signal_weights(Path("/nonexistent/path/config.json"))
        self.assertIsInstance(weights, SignalWeights)
        # The one load-bearing lever defaults ON.
        self.assertTrue(weights.owner_bias_correction)
        # The additivity threshold is present and seeded.
        self.assertEqual(weights.min_team_events, 12)

    def test_seeded_per_person_and_per_source(self) -> None:
        weights = load_signal_weights(Path("/nonexistent/path/config.json"))
        # Matt rich → full trust; Jose/Jinhui sparse → halved.
        self.assertEqual(weights.per_person["matthew"], 1.0)
        self.assertEqual(weights.per_person["jose"], 0.5)
        self.assertEqual(weights.per_person["jinhui"], 0.5)
        # Structured sources full; vault/email discounted.
        self.assertEqual(weights.per_source["calendar"], 1.0)
        self.assertEqual(weights.per_source["github"], 1.0)
        self.assertEqual(weights.per_source["sleuth"], 1.0)
        self.assertEqual(weights.per_source["vault"], 0.7)
        self.assertEqual(weights.per_source["email"], 0.8)


class TestAdditivityGate(unittest.TestCase):
    def test_matt_passes_jose_jinhui_fail(self) -> None:
        counts = {"matthew": 239, "jose": 3, "jinhui": 7}
        self.assertEqual(
            team_persons_passing_additivity(counts, 12),
            ["matthew"],
        )

    def test_roster_order_preserved(self) -> None:
        counts = {"jose": 50, "matthew": 240, "jinhui": 30}
        self.assertEqual(
            team_persons_passing_additivity(counts, 12),
            ["jose", "matthew", "jinhui"],
        )

    def test_empty_counts_gives_empty(self) -> None:
        self.assertEqual(team_persons_passing_additivity({}, 12), [])

    def test_boundary_is_inclusive(self) -> None:
        counts = {"matthew": 12, "jose": 11}
        self.assertEqual(
            team_persons_passing_additivity(counts, 12),
            ["matthew"],
        )


class TestSignalWeightsOverride(unittest.TestCase):
    def _weights_with(self, block: dict) -> SignalWeights:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump({"signal_weights": block}, f)
            path = Path(f.name)
        try:
            return load_signal_weights(path)
        finally:
            path.unlink(missing_ok=True)

    def test_override_scalar_and_bool(self) -> None:
        weights = self._weights_with(
            {"min_team_events": 30, "owner_bias_correction": False}
        )
        self.assertEqual(weights.min_team_events, 30)
        self.assertFalse(weights.owner_bias_correction)

    def test_override_per_person_merges_with_seed(self) -> None:
        weights = self._weights_with({"per_person": {"jose": 0.9}})
        # Overridden key takes the new value...
        self.assertEqual(weights.per_person["jose"], 0.9)
        # ...while un-overridden seed keys survive.
        self.assertEqual(weights.per_person["matthew"], 1.0)

    def test_absent_block_gives_defaults(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump({}, f)
            path = Path(f.name)
        try:
            weights = load_signal_weights(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertTrue(weights.owner_bias_correction)
        self.assertEqual(weights.min_team_events, 12)

    def test_malformed_override_falls_back(self) -> None:
        weights = self._weights_with({"min_team_events": "not-a-number"})
        self.assertEqual(weights.min_team_events, 12)


if __name__ == "__main__":
    unittest.main()

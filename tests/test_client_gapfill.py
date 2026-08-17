from __future__ import annotations

import unittest
from unittest.mock import patch

from rebalance.ingest.project_inference import (
    _ProjectSeed,
    _build_client_gapfill_prompt,
    _gapfill_missing_clients,
)
from rebalance.ingest.querier import DEFAULT_CHAT_MODEL, DEFAULT_GEMINI_MODEL


class ClientGapfillTests(unittest.TestCase):
    def test_gapfill_skips_without_gemini_key(self) -> None:
        seed = _ProjectSeed(key="calendar:ltvera", display_name="LTVera", repos=set())
        project = {"name": "LTVera", "custom_fields": {"client_inferred": None}}

        with patch("rebalance.ingest.config.get_gemini_api_key", return_value=""), patch(
            "rebalance.ingest.querier._synthesize_with_fallback"
        ) as synth:
            _gapfill_missing_clients([(seed, project)])

        synth.assert_not_called()
        self.assertIsNone(project["custom_fields"]["client_inferred"])

    def test_gapfill_uses_one_batched_gemini_call(self) -> None:
        seed_one = _ProjectSeed(
            key="calendar:acme",
            display_name="Acme Website",
            repos={"acme-client/website"},
            github_score=7,
            github_last_active_at="2026-06-29T12:00:00+00:00",
        )
        seed_two = _ProjectSeed(
            key="calendar:ops",
            display_name="Internal Ops",
            repos=set(),
            calendar_event_count=3,
            calendar_last_event_at="2026-06-28T09:00:00+00:00",
        )
        seed_two.calendar_labels["Internal Ops"] += 3
        project_one = {"name": "Acme Website", "custom_fields": {"client_inferred": None}}
        project_two = {"name": "Internal Ops", "custom_fields": {"client_inferred": None}}

        with patch("rebalance.ingest.config.get_gemini_api_key", return_value="k"), patch(
            "rebalance.ingest.querier._synthesize_with_fallback",
            return_value=(
                '{"Acme Website": "Acme Corp", "Internal Ops": null}',
                DEFAULT_GEMINI_MODEL,
            ),
        ) as synth:
            _gapfill_missing_clients([(seed_one, project_one), (seed_two, project_two)])

        synth.assert_called_once()
        prompt = synth.call_args.args[0]
        self.assertIn("project=Acme Website", prompt)
        self.assertIn("project=Internal Ops", prompt)
        self.assertEqual(project_one["custom_fields"]["client_inferred"], "Acme Corp")
        self.assertIsNone(project_two["custom_fields"]["client_inferred"])

    def test_gapfill_ignores_non_gemini_fallback_result(self) -> None:
        seed = _ProjectSeed(key="calendar:ltvera", display_name="LTVera", repos=set())
        project = {"name": "LTVera", "custom_fields": {"client_inferred": None}}

        with patch("rebalance.ingest.config.get_gemini_api_key", return_value="k"), patch(
            "rebalance.ingest.querier._synthesize_with_fallback",
            return_value=('{"LTVera": "LTVera"}', f"{DEFAULT_CHAT_MODEL} (gemini-fallback)"),
        ):
            _gapfill_missing_clients([(seed, project)])

        self.assertIsNone(project["custom_fields"]["client_inferred"])

    def test_gapfill_invalid_json_fails_soft(self) -> None:
        seed = _ProjectSeed(key="calendar:ltvera", display_name="LTVera", repos=set())
        project = {"name": "LTVera", "custom_fields": {"client_inferred": None}}

        with patch("rebalance.ingest.config.get_gemini_api_key", return_value="k"), patch(
            "rebalance.ingest.querier._synthesize_with_fallback",
            return_value=("not json", DEFAULT_GEMINI_MODEL),
        ):
            _gapfill_missing_clients([(seed, project)])

        self.assertIsNone(project["custom_fields"]["client_inferred"])

    def test_gapfill_prompt_includes_recent_signals(self) -> None:
        seed = _ProjectSeed(
            key="owner:acme",
            display_name="Acme Website",
            repos={"acme/website"},
            github_score=5,
            github_last_active_at="2026-06-29T12:00:00+00:00",
            calendar_event_count=2,
            calendar_last_event_at="2026-06-30T12:00:00+00:00",
        )
        seed.calendar_labels["Acme client review"] += 2
        project = {"name": "Acme Website", "custom_fields": {"client_inferred": None}}

        prompt = _build_client_gapfill_prompt([(seed, project)])

        self.assertIn("repos=['acme/website']", prompt)
        self.assertIn("last GitHub activity 2026-06-29", prompt)
        self.assertIn("top calendar label 'Acme client review'", prompt)


if __name__ == "__main__":
    unittest.main()

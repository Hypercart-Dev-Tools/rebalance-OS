"""Contract tests for the Phase 5 lifecycle module (ingest/lifecycle.py).

Locks the two machine-readable maps the Phase 6 welcome agent will consume:
the project-lifecycle ownership table (owners exist, write semantics use the
fixed vocabulary) and the setup-stage status machine (done/now/next/blocked
assignment, blocked propagation, exactly one ``now``).
"""

import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rebalance.ingest import lifecycle
from rebalance.ingest.lifecycle import (
    PROJECT_LIFECYCLE,
    SETUP_STAGES,
    SETUP_STATUS_VALUES,
    WRITE_SEMANTICS_VALUES,
    evaluate_setup,
)

CONFIG = "rebalance.ingest.config"


class ProjectLifecycleMapTests(unittest.TestCase):
    def test_stage_ids_unique_and_ordered(self):
        ids = [s.id for s in PROJECT_LIFECYCLE]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(
            ids,
            ["discovery", "review", "confirmation", "persistence", "inference", "prioritization"],
        )

    def test_write_semantics_use_fixed_vocabulary(self):
        for stage in PROJECT_LIFECYCLE:
            self.assertIn(stage.write_semantics, WRITE_SEMANTICS_VALUES, stage.id)

    def test_discovery_and_review_are_read_only(self):
        semantics = {s.id: s.write_semantics for s in PROJECT_LIFECYCLE}
        self.assertEqual(semantics["discovery"], "read_only")
        self.assertEqual(semantics["review"], "read_only")
        self.assertEqual(semantics["confirmation"], "confirmation_gated")
        self.assertEqual(semantics["inference"], "machine_owned")
        self.assertEqual(semantics["prioritization"], "read_time_overlay")

    def test_owner_functions_exist(self):
        for stage in PROJECT_LIFECYCLE:
            if ":" not in stage.owner:
                continue  # human/agent-owned stages have no code owner
            module_name, func_name = stage.owner.split(":")
            module = importlib.import_module(module_name)
            self.assertTrue(
                callable(getattr(module, func_name, None)),
                f"{stage.id}: owner {stage.owner} does not resolve",
            )


class SetupStageMapTests(unittest.TestCase):
    def test_stage_ids_unique_and_requires_resolve(self):
        ids = {s.id for s in SETUP_STAGES}
        self.assertEqual(len(ids), len(SETUP_STAGES))
        order = [s.id for s in SETUP_STAGES]
        for stage in SETUP_STAGES:
            for dep in stage.requires:
                self.assertIn(dep, ids, f"{stage.id} requires unknown stage {dep}")
                self.assertLess(
                    order.index(dep), order.index(stage.id),
                    f"{stage.id}: prerequisite {dep} must come earlier in the map",
                )

    def test_every_stage_has_remediation(self):
        for stage in SETUP_STAGES:
            self.assertTrue(stage.remediation.strip(), stage.id)

    def test_optional_stages_are_auth_and_graduation(self):
        optional = {s.id for s in SETUP_STAGES if s.optional}
        self.assertEqual(
            optional,
            {"calendar_auth", "gmail_auth", "schedulers_installed", "first_pulse"},
        )


class _EvaluateHarness(unittest.TestCase):
    """Shared sandbox driver for the status machine (mocked config)."""

    def _evaluate(self, *, config=True, vault_ok=True, token=True,
                  calendar=False, gmail=False, vault_dir=None, db=None,
                  skipped=()):
        vault = vault_dir
        with patch(f"{CONFIG}.get_config_path") as config_path, \
             patch(f"{CONFIG}.get_vault_path") as vault_path, \
             patch(f"{CONFIG}.get_github_token") as gh_token, \
             patch(f"{CONFIG}.get_calendar_oauth_token_json") as cal_tok, \
             patch(f"{CONFIG}.get_gmail_oauth_token_json") as gm_tok, \
             patch(f"{CONFIG}.get_onboarding_skipped_stages") as skip_list, \
             patch("rebalance.ingest.lifecycle._launch_agents_dir") as agents_dir, \
             patch("rebalance.ingest.lifecycle._pulse_html_path") as pulse_html, \
             patch("rebalance.paths.resolve_oauth_token_path") as oauth_path:
            sandbox = Path(vault or tempfile.gettempdir())
            oauth_path.side_effect = lambda svc: sandbox / f"oauth-{svc}.json"
            agents_dir.return_value = sandbox / "LaunchAgents"
            pulse_html.return_value = sandbox / "web" / "pulse.html"
            fake_cfg = Path(vault or tempfile.gettempdir()) / "rbos.config"
            if config:
                fake_cfg.parent.mkdir(parents=True, exist_ok=True)
                fake_cfg.write_text("{}")
            config_path.return_value = fake_cfg
            vault_path.return_value = str(vault) if (vault_ok and vault) else ""
            gh_token.return_value = "tok" if token else None
            cal_tok.return_value = '{"token": "x"}' if calendar else None
            gm_tok.return_value = '{"token": "x"}' if gmail else None
            skip_list.return_value = list(skipped)
            return evaluate_setup(
                vault_path=Path(vault) if vault else None,
                database_path=db,
            )

    def _status(self, report, stage_id):
        return next(s for s in report["stages"] if s["id"] == stage_id)["status"]


class EvaluateSetupTests(_EvaluateHarness):
    def test_missing_pat_blocks_downstream_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self._evaluate(token=False, vault_dir=tmp)
            self.assertEqual(self._status(report, "github_token_set"), "now")
            self.assertEqual(self._status(report, "registry_exists"), "blocked")
            self.assertEqual(self._status(report, "projection_exists"), "blocked")
            self.assertEqual(self._status(report, "db_synced"), "blocked")

    def test_exactly_one_now_until_required_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self._evaluate(token=False, vault_dir=tmp)
            now_count = sum(1 for s in report["stages"] if s["status"] == "now")
            self.assertEqual(now_count, 1)
            self.assertEqual(report["now"], "github_token_set")

    def test_optional_stages_are_next_not_now(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self._evaluate(vault_dir=tmp)
            self.assertEqual(self._status(report, "calendar_auth"), "next")
            self.assertEqual(self._status(report, "gmail_auth"), "next")
            # The required pipeline continues past the optional stages.
            self.assertEqual(report["now"], "registry_exists")

    def test_all_required_done_reports_setup_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            (vault / "Projects").mkdir(parents=True)
            (vault / "Projects" / "00-project-registry.md").write_text("# r")
            (vault / "projects.yaml").write_text("projects: []")
            db = Path(tmp) / "rebalance.db"
            with patch("rebalance.ingest.registry.get_projects", return_value=[{"name": "p"}]):
                db.write_text("")  # existence is all the check needs pre-read
                report = self._evaluate(vault_dir=str(vault), db=db)
        self.assertTrue(report["setup_complete"])
        self.assertIsNone(report["now"])
        self.assertEqual(report["required_remaining"], [])
        # Optional, un-done stages remain visible as next — never silently dropped.
        self.assertEqual(self._status(report, "calendar_auth"), "next")

    def test_statuses_use_fixed_vocabulary_and_pure_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = self._evaluate(token=False, vault_dir=tmp)
            second = self._evaluate(token=False, vault_dir=tmp)
        for stage in first["stages"]:
            self.assertIn(stage["status"], SETUP_STATUS_VALUES)
        self.assertEqual(first, second)  # re-polling is stable and safe

    def test_contract_version_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self._evaluate(vault_dir=tmp)
        self.assertEqual(report["contract_version"], lifecycle.CONTRACT_VERSION)


class ContractV2Tests(_EvaluateHarness):
    """Phase 6 slice 1: skipped status, executor hints, keyring seam."""

    def test_skipped_optional_stage_reports_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self._evaluate(vault_dir=tmp, skipped=["calendar_auth"])
        self.assertEqual(self._status(report, "calendar_auth"), "skipped")
        self.assertEqual(self._status(report, "gmail_auth"), "next")

    def test_blocked_beats_skipped(self):
        # Review finding: a skip marker must never mask unmet prerequisites —
        # clients execute `skipped` stages without re-checking deps.
        with tempfile.TemporaryDirectory() as tmp:
            report = self._evaluate(
                config=False, vault_dir=tmp, skipped=["calendar_auth"]
            )
        self.assertEqual(self._status(report, "calendar_auth"), "blocked")

    def test_oauth_file_fallback_counts_as_authenticated(self):
        # Review finding: runtime collectors read a token FILE — a file-only
        # machine has working auth and must not show the stage incomplete.
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "oauth-calendar.json").write_text("{}")
            report = self._evaluate(vault_dir=tmp, calendar=False)
        stage = next(s for s in report["stages"] if s["id"] == "calendar_auth")
        self.assertEqual(stage["status"], "done")
        self.assertIn("file", stage["detail"])

    def test_hermetic_mode_ignores_oauth_token_files(self):
        import os

        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "oauth-calendar.json").write_text("{}")
            with patch.dict(os.environ, {"REBALANCE_HERMETIC": "1"}):
                report = self._evaluate(vault_dir=tmp, calendar=False)
        self.assertEqual(self._status(report, "calendar_auth"), "next")

    def test_completing_a_stage_wins_over_stale_skip_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self._evaluate(
                vault_dir=tmp, calendar=True, skipped=["calendar_auth"]
            )
        self.assertEqual(self._status(report, "calendar_auth"), "done")

    def test_skip_state_is_persisted_and_reversible(self):
        from rebalance.ingest import config as config_module
        from rebalance.ingest.config import (
            get_onboarding_skipped_stages,
            set_onboarding_stage_skipped,
        )

        with tempfile.TemporaryDirectory() as tmp:
            orig = config_module.CONFIG_PATH
            config_module.CONFIG_PATH = Path(tmp) / "rbos.config"
            try:
                self.assertEqual(get_onboarding_skipped_stages(), [])
                self.assertEqual(set_onboarding_stage_skipped("calendar_auth"), ["calendar_auth"])
                self.assertEqual(set_onboarding_stage_skipped("calendar_auth"), ["calendar_auth"])  # idempotent
                self.assertEqual(get_onboarding_skipped_stages(), ["calendar_auth"])
                self.assertEqual(set_onboarding_stage_skipped("calendar_auth", False), [])
            finally:
                config_module.CONFIG_PATH = orig

    def test_every_stage_has_a_valid_executor(self):
        from rebalance.ingest.lifecycle import EXECUTOR_KINDS

        for stage in SETUP_STAGES:
            kind, sep, target = stage.executor.partition(":")
            self.assertTrue(sep and target, f"{stage.id}: executor missing")
            self.assertIn(kind, EXECUTOR_KINDS, f"{stage.id}: unknown executor kind")

    def test_executor_surfaces_in_evaluate_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self._evaluate(vault_dir=tmp)
        by_id = {s["id"]: s for s in report["stages"]}
        self.assertEqual(by_id["github_token_set"]["executor"], "mcp:setup_github_token")

    def test_keyring_seam_disables_all_keyring_io(self):
        import os

        from rebalance.ingest import config as config_module

        with patch.dict(os.environ, {"REBALANCE_NO_KEYRING": "1"}):
            self.assertIsNone(config_module._keyring_get("github_token"))
            self.assertFalse(config_module._keyring_set("k", "v"))
            self.assertFalse(config_module._keyring_delete("k"))


class WriteSemanticsEnforcementTests(unittest.TestCase):
    """Gemini review finding: write semantics were asserted as strings only.
    Behavioral lock: a read_time_overlay stage must not persist anything."""

    def test_prioritization_overlay_never_writes_the_db(self):
        import json as _json
        import sqlite3

        from rebalance.ingest.db import db_connection, ensure_project_schema
        from rebalance.ingest.project_priority import apply_project_priorities
        from rebalance.ingest.registry import get_projects

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "rebalance.db"
            with db_connection(db, ensure_project_schema) as conn:
                conn.execute(
                    "INSERT INTO project_registry (name, status, summary, value_level,"
                    " priority_tier, risk_level, repos_json, tags_json, custom_fields_json)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ("P", "active", "s", None, 3, None, "[]", "[]", _json.dumps({})),
                )
                conn.commit()

            before = sqlite3.connect(db).execute(
                "SELECT * FROM project_registry"
            ).fetchall()
            overlaid = apply_project_priorities(get_projects(db))
            self.assertTrue(overlaid)  # overlay produced output...
            after = sqlite3.connect(db).execute(
                "SELECT * FROM project_registry"
            ).fetchall()
            self.assertEqual(before, after)  # ...and persisted nothing

    def test_project_lifecycle_map_is_runtime_consumable(self):
        from rebalance.ingest.lifecycle import project_lifecycle_map

        rows = project_lifecycle_map()
        self.assertEqual(len(rows), len(PROJECT_LIFECYCLE))
        import json as _json

        _json.dumps(rows)  # MCP-serializable
        by_id = {r["id"]: r for r in rows}
        self.assertEqual(by_id["confirmation"]["write_semantics"], "confirmation_gated")


if __name__ == "__main__":
    unittest.main()

"""End-to-end onboarding contract tests (Phase 5).

Covers the full promote path the welcome agent will drive —
discover_candidates → confirm_and_write → get_projects (the function layer
under the run_preflight / confirm_projects / list_projects MCP tools) — plus
the setup-status contract flipping to done as the artifacts land. Hermetic:
sandbox vault + SQLite, remote GitHub discovery faked, no network.
"""

import tempfile
import unittest
import unittest.mock
from pathlib import Path
from unittest.mock import patch

from rebalance.ingest import config as config_module
from rebalance.ingest.github_scan import RepoCandidate
from rebalance.ingest.lifecycle import evaluate_setup
from rebalance.ingest.preflight import confirm_and_write, discover_candidates
from rebalance.ingest.registry import get_projects

CONFIG = "rebalance.ingest.config"


class OnboardingEndToEndTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.vault = root / "vault"
        (self.vault / "Projects").mkdir(parents=True)
        (self.vault / "Acme Site Redesign.md").write_text("# Acme Site Redesign\n")
        self.registry_path = self.vault / "Projects" / "00-project-registry.md"
        self.projects_yaml = self.vault / "projects.yaml"
        self.db = root / "rebalance.db"
        self._orig_config = config_module.CONFIG_PATH
        config_module.CONFIG_PATH = root / "rbos.config"
        self.addCleanup(setattr, config_module, "CONFIG_PATH", self._orig_config)

    def _discover(self):
        fake_repo = RepoCandidate(
            repo_full_name="acme/site-redesign",
            last_active_at="2026-06-10T12:00:00Z",
            activity_score=12,
            commit_count=5,
            bands=["A"],
        )
        with patch(
            "rebalance.ingest.preflight.discover_repos_from_activity",
            return_value=[fake_repo],
        ):
            return discover_candidates(
                vault_path=self.vault,
                registry_path=self.registry_path,
                github_token="fake-token",
            )

    def _all_candidates(self, discovery) -> list[dict]:
        return (
            discovery.most_likely_active_projects
            + discovery.semi_active_projects
            + discovery.dormant_projects
            + discovery.potential_projects
        )

    def test_discovery_is_read_only_and_carries_provenance(self):
        discovery = self._discover()
        candidates = self._all_candidates(discovery)
        by_provenance = {c["provenance"]: c for c in candidates}

        self.assertIn("vault-note", by_provenance)
        self.assertIn("remote-activity", by_provenance)
        self.assertEqual(by_provenance["remote-activity"]["name"], "acme/site-redesign")
        self.assertEqual(by_provenance["vault-note"]["name"], "Acme Site Redesign")

        # read_only contract: discovery persisted nothing.
        self.assertFalse(self.registry_path.exists())
        self.assertFalse(self.projects_yaml.exists())
        self.assertFalse(self.db.exists())

        # Re-running discovery is always safe and stable.
        second = self._discover()
        self.assertEqual(
            sorted(c["name"] for c in candidates),
            sorted(c["name"] for c in self._all_candidates(second)),
        )

    def test_promote_path_discover_confirm_list(self):
        discovery = self._discover()
        curated = []
        for cand in self._all_candidates(discovery):
            cand = dict(cand)
            cand["status"] = "active"  # operator promotes both candidates
            curated.append(cand)

        result = confirm_and_write(
            projects=curated,
            vault_path=self.vault,
            registry_path=self.registry_path,
            projects_yaml_path=self.projects_yaml,
            database_path=self.db,
        )
        self.assertTrue(result.sync_ok)
        self.assertTrue(self.registry_path.exists())
        self.assertTrue(self.projects_yaml.exists())

        rows = get_projects(self.db, status="active")
        by_name = {row["name"]: row for row in rows}
        self.assertIn("acme/site-redesign", by_name)
        self.assertIn("Acme Site Redesign", by_name)

        # Provenance survives the full promote path into the DB read shape.
        self.assertEqual(by_name["acme/site-redesign"]["provenance"], "remote-activity")
        self.assertEqual(by_name["Acme Site Redesign"]["provenance"], "vault-note")

        # What the operator confirmed is what list_projects returns.
        self.assertEqual(by_name["acme/site-redesign"]["status"], "active")

    def test_setup_status_flips_done_after_promote(self):
        def status_report():
            sandbox = Path(self._tmp.name)
            with patch(f"{CONFIG}.get_config_path", return_value=config_module.CONFIG_PATH), \
                 patch(f"{CONFIG}.get_vault_path", return_value=str(self.vault)), \
                 patch(f"{CONFIG}.get_github_token", return_value="fake-token"), \
                 patch(f"{CONFIG}.get_calendar_oauth_token_json", return_value=None), \
                 patch(f"{CONFIG}.get_gmail_oauth_token_json", return_value=None), \
                 patch("rebalance.ingest.lifecycle._launch_agents_dir", return_value=sandbox / "LaunchAgents"), \
                 patch("rebalance.ingest.lifecycle._pulse_html_path", return_value=sandbox / "web" / "pulse.html"), \
                 patch("rebalance.paths.resolve_oauth_token_path", side_effect=lambda svc: sandbox / f"oauth-{svc}.json"):
                Path(config_module.CONFIG_PATH).write_text("{}")
                return evaluate_setup(vault_path=self.vault, database_path=self.db)

        before = status_report()
        self.assertEqual(before["now"], "registry_exists")
        self.assertFalse(before["setup_complete"])

        discovery = self._discover()
        curated = [dict(c, status="active") for c in self._all_candidates(discovery)]
        confirm_and_write(
            projects=curated,
            vault_path=self.vault,
            registry_path=self.registry_path,
            projects_yaml_path=self.projects_yaml,
            database_path=self.db,
        )

        after = status_report()
        by_id = {s["id"]: s for s in after["stages"]}
        self.assertEqual(by_id["registry_exists"]["status"], "done")
        self.assertEqual(by_id["projection_exists"]["status"], "done")
        self.assertEqual(by_id["db_synced"]["status"], "done")
        self.assertTrue(after["setup_complete"])
        # Optional auth stages remain offered, never blocking completion.
        self.assertEqual(by_id["calendar_auth"]["status"], "next")
        self.assertEqual(by_id["gmail_auth"]["status"], "next")


class ProvenancePushRoundTripTests(unittest.TestCase):
    """Gemini review finding (High): push sync dropped Project.provenance.

    Locks the full pull -> push -> pull cycle: provenance must survive every
    direction, with the typed field and its custom_fields copy in sync.
    """

    def test_provenance_survives_push_sync(self):
        from rebalance.ingest.registry import (
            Project,
            Registry,
            read_registry,
            save_registry,
            sync_registry,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path = root / "Projects" / "00-project-registry.md"
            projects_yaml = root / "projects.yaml"
            db = root / "rebalance.db"

            registry = Registry(
                active_projects=[
                    Project(name="acme/site", provenance="remote-activity", repos=["acme/site"])
                ]
            )
            save_registry(registry_path, registry)
            sync_registry("pull", registry_path, projects_yaml, db)  # md -> yaml + db
            sync_registry("push", registry_path, projects_yaml, db)  # yaml -> md

            after = read_registry(registry_path)
            self.assertEqual(after.active_projects[0].provenance, "remote-activity")
            # The custom_fields copy must not desync from the typed field.
            self.assertEqual(
                after.active_projects[0].custom_fields.get("provenance", "remote-activity"),
                "remote-activity",
            )


if __name__ == "__main__":
    unittest.main()


class OptionalOfferInterruptTests(unittest.TestCase):
    """Review finding: Ctrl+C during an offer must not persist a skip."""

    def test_interrupt_records_no_skip_state(self):
        from rebalance.cli import onboard as onboard_module

        fake_report = {
            "stages": [{
                "id": "calendar_auth", "title": "Google Calendar",
                "optional": True, "status": "next",
                "detail": "no token", "remediation": "run the script",
                "executor": "script:scripts/setup_calendar_oauth.py",
                "requires": [], "complete": False,
            }],
            "now": None, "setup_complete": True,
            "required_remaining": [], "contract_version": 2,
        }
        confirm = unittest.mock.MagicMock()
        confirm.return_value.ask.return_value = None  # Ctrl+C / EOF
        with patch("rebalance.ingest.lifecycle.evaluate_setup", return_value=fake_report), \
             patch(f"{CONFIG}.get_vault_path", return_value=""), \
             patch(f"{CONFIG}.set_onboarding_stage_skipped") as set_skip, \
             patch("questionary.confirm", confirm):
            onboard_module._offer_optional_stages(None)
        set_skip.assert_not_called()

"""Hermetic welcome-agent walkthrough (Phase 6 close).

Drives the FULL journey — fresh machine → config → vault → PAT → skip
Calendar / set up Gmail → discover → promote → graduation — the way the
/welcome agent does, but with real artifacts instead of mocked checks:
config values are written through the actual config module (the
REBALANCE_NO_KEYRING seam routes secrets to the sandbox rbos.config), the
registry/projection/DB come from real confirm_and_write, and the skip state
round-trips through set_onboarding_stage_skipped. Only machine-global
locations (keyring, LaunchAgents, web/) and the GitHub network call are
sandboxed. Time-to-first-pulse (wall clock for the whole journey) is
reported in the test output.
"""

import os
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from rebalance.ingest import config as config_module
from rebalance.ingest.github_scan import RepoCandidate
from rebalance.ingest.lifecycle import evaluate_setup
from rebalance.ingest.preflight import confirm_and_write, discover_candidates


class WelcomeWalkthroughTest(unittest.TestCase):
    def test_clone_to_first_pulse(self):
        started = time.monotonic()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault = root / "vault"
            db = root / "rebalance.db"
            agents_dir = root / "LaunchAgents"
            pulse_html = root / "web" / "pulse.html"

            # Full hermetic mode: keyring AND gh-CLI fallbacks off — the
            # walkthrough caught the gh CLI leaking the operator's real
            # token into a "fresh" sandbox (same bug class as the keyring).
            env = {"REBALANCE_HERMETIC": "1"}
            orig_config = config_module.CONFIG_PATH
            config_module.CONFIG_PATH = root / "temp" / "rbos.config"

            def status():
                with patch("rebalance.ingest.lifecycle._launch_agents_dir", return_value=agents_dir), \
                     patch("rebalance.ingest.lifecycle._pulse_html_path", return_value=pulse_html):
                    return evaluate_setup(vault_path=vault, database_path=db)

            def stage(report, sid):
                return next(s for s in report["stages"] if s["id"] == sid)

            try:
                with patch.dict(os.environ, env):
                    # 0. Fresh machine: nothing exists.
                    report = status()
                    self.assertEqual(report["now"], "config_exists")
                    self.assertEqual(stage(report, "registry_exists")["status"], "blocked")

                    # 1-2. Vault: real config write (creates the config file too).
                    vault.mkdir(parents=True)
                    (vault / "Side Quest.md").write_text("# Side Quest\n")
                    config_module.set_vault_path(str(vault))
                    report = status()
                    self.assertEqual(report["now"], "github_token_set")

                    # 3. PAT: keyring disabled by the seam, so the secret lands
                    # in the sandbox config file — never the OS keyring.
                    config_module.set_github_token("ghp_sandbox")
                    self.assertIsNone(config_module._keyring_get("github_token"))
                    report = status()
                    self.assertEqual(report["now"], "registry_exists")

                    # 4-5. Optional auth: skip Calendar (persisted), leave Gmail offered.
                    config_module.set_onboarding_stage_skipped("calendar_auth")
                    report = status()
                    self.assertEqual(stage(report, "calendar_auth")["status"], "skipped")
                    self.assertEqual(stage(report, "gmail_auth")["status"], "next")

                    # 6-7. Discover (remote mocked, local off) and promote.
                    fake = RepoCandidate(
                        repo_full_name="acme/side-quest",
                        last_active_at="2026-06-10T12:00:00Z",
                        activity_score=9, commit_count=4, bands=["A"],
                    )
                    registry_path = vault / "Projects" / "00-project-registry.md"
                    with patch("rebalance.ingest.preflight.discover_repos_from_activity",
                               return_value=[fake]):
                        discovery = discover_candidates(
                            vault_path=vault, registry_path=registry_path,
                            github_token="ghp_sandbox",
                        )
                    curated = [
                        dict(c, status="active")
                        for c in discovery.most_likely_active_projects
                        + discovery.potential_projects
                    ]
                    confirm_and_write(
                        projects=curated, vault_path=vault,
                        registry_path=registry_path,
                        projects_yaml_path=vault / "projects.yaml",
                        database_path=db,
                    )
                    report = status()
                    self.assertTrue(report["setup_complete"])  # graduation is optional
                    self.assertEqual(stage(report, "schedulers_installed")["status"], "next")

                    # 8-9. Graduation: the executors' observable artifacts.
                    agents_dir.mkdir(parents=True)
                    (agents_dir / "com.rebalance-os.daily-sync.plist").write_text("<plist/>")
                    pulse_html.parent.mkdir(parents=True)
                    pulse_html.write_text("<html>pulse</html>")
                    report = status()
                    self.assertEqual(stage(report, "schedulers_installed")["status"], "done")
                    self.assertEqual(stage(report, "first_pulse")["status"], "done")
                    done = [s["id"] for s in report["stages"] if s["status"] == "done"]
                    # All 8 of the 10 stages — only skipped Calendar and
                    # still-offered Gmail remain undone.
                    self.assertEqual(len(done), 8)
            finally:
                config_module.CONFIG_PATH = orig_config

        elapsed = time.monotonic() - started
        print(f"\n[walkthrough] clone -> first pulse (hermetic): {elapsed:.2f}s")


if __name__ == "__main__":
    unittest.main()

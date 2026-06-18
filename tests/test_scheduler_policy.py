"""Scheduler policy conformance tests (Phase 4).

SCHEDULER.md is the policy table for the launchd fleet; these tests enforce
its machine-checkable columns against the actual artifacts in ``scripts/``:

- every plist template renders cleanly (no leftover ``{{...}}``), parses, and
  carries the right label, cadence, RunAtLoad/KeepAlive, and program paths
- every wrapper script uses the shared runtime (``lib/scheduler_common.sh``)
  and encodes its policy scope / entry call verbatim
- every installer uses the shared install flow (``lib/install_common.sh``)
- SCHEDULER.md documents every job with its cadence-defining tokens

Everything runs hermetically: templates are rendered with dummy paths and
parsed with ``plistlib`` — no ``launchctl``, no live LaunchAgents, no network.
"""

import plistlib
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
SCHEDULER_MD = REPO / "SCHEDULER.md"

FAKE_ROOT = "/policy-test/repo"
FAKE_PYTHON = "/policy-test/venv/bin/python"
FAKE_HOME = "/policy-test/home"

WORKDAY_HOURS = list(range(6, 24))  # 06:00 through 23:xx


def _hourly(minute):
    return [{"Hour": h, "Minute": minute} for h in WORKDAY_HOURS]


# Mirror of the SCHEDULER.md job table. Keys are the label suffix
# (com.rebalance-os.<key>). Fields:
#   calendar      expected StartCalendarInterval entries (None = no schedule)
#   run_at_load / keep_alive   expected boolean plist keys (absent key = False)
#   wrapper       repo-relative wrapper script, or None for python-direct jobs
#   wrapper_must_contain       policy-bearing lines the wrapper must keep
#   args_must_contain          tokens required in rendered ProgramArguments
#   args_must_not_contain      tokens that must NOT appear (cost guards)
#   retention     log retention days passed to rb_job_init
#   doc_tokens    strings SCHEDULER.md must contain for this job
POLICY = {
    "daily-sync": {
        "calendar": [{"Hour": 6, "Minute": 30}],
        "run_at_load": True,
        "keep_alive": False,
        "wrapper": "scripts/daily_sync.sh",
        "wrapper_must_contain": [
            'rb_job_init "daily-sync" 30',
            "result = refresh_index(db_path)",
        ],
        "doc_tokens": ["daily 06:30", "refresh_index(db_path)"],
    },
    "vault-sync": {
        "calendar": _hourly(15),
        "run_at_load": False,
        "keep_alive": False,
        "wrapper": "scripts/vault_sync.sh",
        "wrapper_must_contain": [
            'rb_job_init "vault-sync" 14',
            'scope=["vault", "semantic"]',
        ],
        "doc_tokens": ["hourly at :15", '["vault", "semantic"]'],
    },
    "github-sync": {
        "calendar": _hourly(45),
        "run_at_load": False,
        "keep_alive": False,
        "wrapper": "scripts/github_sync.sh",
        "wrapper_must_contain": [
            'rb_job_init "github-sync" 14',
            'scope=["github"]',
        ],
        "doc_tokens": ["hourly at :45", '["github"]'],
    },
    "pulse-sync": {
        "calendar": _hourly(0),
        "run_at_load": False,
        "keep_alive": False,
        "wrapper": "scripts/pulse_sync.sh",
        "wrapper_must_contain": [
            'rb_job_init "pulse-sync" 14',
            "publish_pulse(db_path, dry_run=False, push=push)",
        ],
        "doc_tokens": ["hourly at :00", "publish_pulse(db_path"],
    },
    "pulse-web-sync": {
        "calendar": [
            {"Hour": h, "Minute": m} for h in WORKDAY_HOURS for m in (0, 30)
        ],
        "run_at_load": False,
        "keep_alive": False,
        "wrapper": "scripts/pulse_web_sync.sh",
        "wrapper_must_contain": [
            'rb_job_init "pulse-web-sync" 14',
            "scripts/pulse_web.py",
        ],
        "doc_tokens": ["every 30 min", "pulse_web.py"],
    },
    "pulse-server": {
        "calendar": None,
        "run_at_load": True,
        "keep_alive": True,
        "wrapper": "scripts/pulse_server.sh",
        "wrapper_must_contain": [
            'rb_job_mark_started "pulse-server"',
            "scripts/pulse_server.py",
        ],
        "doc_tokens": ["RunAtLoad + KeepAlive", "pulse_server.py"],
    },
    "pulse-warning-watch": {
        "calendar": [{"Minute": m} for m in (0, 15, 30, 45)],
        "run_at_load": True,
        "keep_alive": False,
        "wrapper": None,
        "args_must_contain": [
            "scripts/pulse_warning_watch.py",
            "--url",
            "http://127.0.0.1:8767/",
        ],
        "doc_tokens": ["every 15 min", "pulse_warning_watch.py"],
    },
    "health-check": {
        "calendar": [{"Minute": 0}],
        "run_at_load": False,
        "keep_alive": False,
        "wrapper": None,
        "args_must_contain": ["scripts/health_issue_reporter.py", "--close"],
        # The hourly run is the cheap FAIL-only tier — LLM flags live only in
        # the 3x-daily triage job.
        "args_must_not_contain": ["--llm-triage"],
        "doc_tokens": ["hourly at :00", "--close"],
    },
    "health-check-triage": {
        "calendar": [
            {"Hour": 8, "Minute": 0},
            {"Hour": 14, "Minute": 0},
            {"Hour": 20, "Minute": 0},
        ],
        "run_at_load": False,
        "keep_alive": False,
        "wrapper": None,
        "args_must_contain": [
            "scripts/health_issue_reporter.py",
            "--llm-triage",
            "--llm-daily-limit",
        ],
        "doc_tokens": ["08:00, 14:00, 20:00", "--llm-triage"],
    },
    "obsidian-rollover": {
        "calendar": [{"Hour": 0, "Minute": 0}],
        # Loading must never fire the rollover — it would wipe Today's Notes.
        "run_at_load": False,
        "keep_alive": False,
        "wrapper": "utilities/obsidian_rollover.sh",
        "wrapper_must_contain": ["obsidian_daily_rollover.py"],
        "doc_tokens": ["daily 00:00", "obsidian_rollover.sh"],
    },
}

INSTALLERS = {
    "daily-sync": "install_scheduler.sh",
    "vault-sync": "install_vault_scheduler.sh",
    "github-sync": "install_github_scheduler.sh",
    "pulse-sync": "install_pulse_scheduler.sh",
    "pulse-web-sync": "install_pulse_web_scheduler.sh",
    "pulse-server": "install_pulse_server_scheduler.sh",
    "pulse-warning-watch": "install_pulse_warning_watch_scheduler.sh",
    "health-check": "install_health_check_scheduler.sh",
    "health-check-triage": "install_health_check_triage_scheduler.sh",
    "obsidian-rollover": "install_obsidian_rollover_scheduler.sh",
}


def _label(job):
    return f"com.rebalance-os.{job}"


def _render(job):
    """Render a template the way install_common.sh does, with dummy paths."""
    text = (SCRIPTS / f"{_label(job)}.plist.template").read_text()
    return (
        text.replace("{{REBALANCE_DIR}}", FAKE_ROOT)
        .replace("{{PYTHON}}", FAKE_PYTHON)
        .replace("{{HOME}}", FAKE_HOME)
    )


def _parse(job):
    return plistlib.loads(_render(job).encode())


def _intervals(plist):
    """Normalize StartCalendarInterval (dict or array) to a list of dicts."""
    raw = plist.get("StartCalendarInterval")
    if raw is None:
        return None
    return [raw] if isinstance(raw, dict) else list(raw)


class TestPlistTemplates(unittest.TestCase):
    def test_every_policy_job_has_a_template(self):
        for job in POLICY:
            self.assertTrue(
                (SCRIPTS / f"{_label(job)}.plist.template").is_file(),
                f"missing template for {job}",
            )

    def test_no_unrendered_placeholders(self):
        for job in POLICY:
            self.assertNotIn("{{", _render(job), f"{job}: unrendered {{{{...}}}}")

    def test_labels_match_filenames(self):
        for job in POLICY:
            self.assertEqual(_parse(job)["Label"], _label(job))

    def test_cadence_matches_policy(self):
        for job, spec in POLICY.items():
            got = _intervals(_parse(job))
            self.assertEqual(
                got, spec["calendar"],
                f"{job}: StartCalendarInterval diverged from SCHEDULER.md policy",
            )

    def test_run_at_load_and_keep_alive(self):
        for job, spec in POLICY.items():
            plist = _parse(job)
            self.assertEqual(
                bool(plist.get("RunAtLoad", False)), spec["run_at_load"],
                f"{job}: RunAtLoad",
            )
            self.assertEqual(
                bool(plist.get("KeepAlive", False)), spec["keep_alive"],
                f"{job}: KeepAlive",
            )

    def test_program_arguments_reference_real_files(self):
        for job in POLICY:
            for arg in _parse(job)["ProgramArguments"]:
                if not arg.startswith(FAKE_ROOT + "/"):
                    continue
                rel = arg[len(FAKE_ROOT) + 1:]
                # Only executables must exist in the repo. Runtime artifacts
                # (temp/ logs, state files) are created on first run and are
                # gitignored — asserting them broke CI on clean checkouts.
                if not rel.endswith((".py", ".sh")):
                    continue
                self.assertTrue(
                    (REPO / rel).is_file(),
                    f"{job}: ProgramArguments references missing file {rel}",
                )

    def test_python_direct_jobs_carry_policy_args(self):
        for job, spec in POLICY.items():
            args = " ".join(_parse(job)["ProgramArguments"])
            for token in spec.get("args_must_contain", []):
                self.assertIn(token, args, f"{job}: missing arg {token!r}")
            for token in spec.get("args_must_not_contain", []):
                self.assertNotIn(token, args, f"{job}: forbidden arg {token!r}")

    def test_no_secrets_in_templates(self):
        for job in POLICY:
            text = (SCRIPTS / f"{_label(job)}.plist.template").read_text()
            for line in text.splitlines():
                if "sk-ant-" in line and "YOUR-KEY" not in line and "..." not in line:
                    self.fail(f"{job}: template appears to contain a real API key")


class TestWrapperScripts(unittest.TestCase):
    def _wrapper_jobs(self):
        return {j: s for j, s in POLICY.items() if s["wrapper"]}

    def test_wrappers_exist_and_pass_bash_syntax(self):
        shell = list((SCRIPTS / "lib").glob("*.sh"))
        shell += [REPO / s["wrapper"] for s in self._wrapper_jobs().values()]
        shell += [SCRIPTS / name for name in INSTALLERS.values()]
        for path in shell:
            self.assertTrue(path.is_file(), f"missing {path}")
            proc = subprocess.run(
                ["bash", "-n", str(path)], capture_output=True, text=True
            )
            self.assertEqual(proc.returncode, 0, f"{path}: {proc.stderr}")

    def test_scheduled_wrappers_use_shared_runtime(self):
        # scripts/-resident wrappers must source the shared lib; the
        # utilities/ rollover wrapper predates it and is exec-only by design.
        for job, spec in self._wrapper_jobs().items():
            if not spec["wrapper"].startswith("scripts/"):
                continue
            text = (REPO / spec["wrapper"]).read_text()
            self.assertIn(
                "lib/scheduler_common.sh", text,
                f"{job}: wrapper does not source scheduler_common.sh",
            )

    def test_wrappers_encode_policy_entry_calls(self):
        for job, spec in self._wrapper_jobs().items():
            text = (REPO / spec["wrapper"]).read_text()
            for token in spec.get("wrapper_must_contain", []):
                self.assertIn(token, text, f"{job}: wrapper lost {token!r}")

    def test_wrappers_never_call_launchctl(self):
        # Job runtime must stay hermetic — install/uninstall is installer
        # territory.
        for job, spec in self._wrapper_jobs().items():
            text = (REPO / spec["wrapper"]).read_text()
            self.assertNotIn("launchctl", text, f"{job}: wrapper calls launchctl")


class TestSchedulerCommonRuntime(unittest.TestCase):
    """Run the shared runtime in a throwaway tree — no venv, no real repo."""

    def _make_tree(self, tmp, body):
        import shutil

        repo = Path(tmp) / "repo"
        (repo / "scripts" / "lib").mkdir(parents=True)
        shutil.copy(
            SCRIPTS / "lib" / "scheduler_common.sh",
            repo / "scripts" / "lib" / "scheduler_common.sh",
        )
        wrapper = repo / "scripts" / "job.sh"
        wrapper.write_text(
            "#!/bin/bash\nset -euo pipefail\n"
            'source "$(cd "$(dirname "$0")" && pwd)/lib/scheduler_common.sh"\n'
            + body
        )
        wrapper.chmod(0o755)
        return repo, wrapper

    def test_init_creates_dated_log_and_preserves_exit_zero(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            repo, wrapper = self._make_tree(
                tmp, 'rb_job_init "fake-job" 14\nlog "hello"\nrb_trim_logs\n'
            )
            proc = subprocess.run([str(wrapper)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            logs = list((repo / "temp" / "logs").glob("fake_job_*.log"))
            self.assertEqual(len(logs), 1)
            self.assertIn("hello", logs[0].read_text())

    def test_failure_exit_code_survives_lifecycle_trap(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            _, wrapper = self._make_tree(
                tmp, 'rb_job_init "fake-job" 14\nexit 3\n'
            )
            proc = subprocess.run([str(wrapper)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 3)


class TestInstallers(unittest.TestCase):
    def test_every_job_has_an_installer_using_shared_flow(self):
        for job, name in INSTALLERS.items():
            path = SCRIPTS / name
            self.assertTrue(path.is_file(), f"{job}: missing installer {name}")
            text = path.read_text()
            self.assertIn(
                "lib/install_common.sh", text,
                f"{job}: installer does not source install_common.sh",
            )
            self.assertIn(
                f'rb_install_launchd_job "{_label(job)}"', text,
                f"{job}: installer does not install label {_label(job)}",
            )

    def test_installers_have_no_inline_render_or_racy_unload(self):
        for job, name in INSTALLERS.items():
            text = (SCRIPTS / name).read_text()
            self.assertNotIn(
                's/{{', text, f"{job}: inline sed render belongs in install_common.sh"
            )
            self.assertNotIn(
                "if launchctl list", text,
                f"{job}: racy grep-conditional unload; install_common always unloads",
            )


class TestSchedulerDoc(unittest.TestCase):
    def test_policy_doc_exists_and_documents_every_job(self):
        self.assertTrue(SCHEDULER_MD.is_file(), "SCHEDULER.md missing")
        doc = SCHEDULER_MD.read_text()
        for job, spec in POLICY.items():
            self.assertIn(f"`{job}`", doc, f"SCHEDULER.md missing job {job}")
            for token in spec["doc_tokens"]:
                self.assertIn(
                    token, doc, f"SCHEDULER.md: job {job} missing token {token!r}"
                )


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Thin Phase 6 spike: drive the Phase 5 lifecycle contract like the welcome
agent would — no skill, no UX polish. Disposable by design.

Two scenarios:

1. ``--real``  render "where am I" for THIS machine from one evaluate_setup
   call (what /welcome would print at the top of every turn).
2. default     fresh-machine sandbox walkthrough: complete the journey one
   stage at a time and assert the contract holds at every boundary
   (blocked propagation, exactly-one-now, optional stages stay offered).

Exit 0 = contract validated. Findings feed the Phase 5 close notes.
"""

from __future__ import annotations

import sys
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import _bootstrap  # noqa: F401

from rebalance.ingest.lifecycle import evaluate_setup

CONFIG = "rebalance.ingest.config"
GLYPHS = {"done": "[x]", "now": "->", "next": "( )", "blocked": "!!", "skipped": "(s)"}


def render(report: dict) -> None:
    print(f"  setup_complete={report['setup_complete']}  now={report['now']}")
    for stage in report["stages"]:
        opt = " (optional)" if stage["optional"] else ""
        line = f"  {GLYPHS[stage['status']]:>3} {stage['title']}{opt} — {stage['detail']}"
        print(line)
        if stage["status"] in ("now", "blocked"):
            print(f"      remediation: {stage['remediation']}")


def real_machine() -> int:
    from rebalance.ingest.config import get_vault_path
    from rebalance.paths import resolve_database_path

    vault = get_vault_path()
    db = resolve_database_path()
    report = evaluate_setup(
        vault_path=Path(vault).expanduser() if vault else None,
        database_path=db,
    )
    print("Where am I (this machine):")
    render(report)
    return 0


def sandbox_walkthrough() -> int:
    failures: list[str] = []

    def expect(cond: bool, label: str) -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {label}")
        if not cond:
            failures.append(label)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        vault = root / "vault"
        cfg = root / "rbos.config"
        db = root / "rebalance.db"
        state = {"config": False, "vault": False, "token": False}

        def fake_config_path() -> Path:
            return cfg

        def evaluate() -> dict:
            with ExitStack() as stack:
                stack.enter_context(patch(f"{CONFIG}.get_config_path", fake_config_path))
                stack.enter_context(patch(
                    f"{CONFIG}.get_vault_path",
                    lambda: str(vault) if state["vault"] else "",
                ))
                stack.enter_context(patch(
                    f"{CONFIG}.get_github_token",
                    lambda: "tok" if state["token"] else None,
                ))
                stack.enter_context(patch(f"{CONFIG}.get_calendar_oauth_token_json", lambda: None))
                stack.enter_context(patch(f"{CONFIG}.get_gmail_oauth_token_json", lambda: None))
                stack.enter_context(patch(f"{CONFIG}.get_onboarding_skipped_stages", lambda: list(state.get("skipped", []))))
                stack.enter_context(patch("rebalance.ingest.lifecycle._launch_agents_dir", lambda: root / "LaunchAgents"))
                stack.enter_context(patch("rebalance.ingest.lifecycle._pulse_html_path", lambda: root / "web" / "pulse.html"))
                stack.enter_context(patch("rebalance.paths.resolve_oauth_token_path", lambda svc: root / f"oauth-{svc}.json"))
                return evaluate_setup(vault_path=vault, database_path=db)

        def status(report: dict, stage_id: str) -> str:
            return next(s for s in report["stages"] if s["id"] == stage_id)["status"]

        print("Stage 0 — fresh machine:")
        report = evaluate()
        render(report)
        expect(report["now"] == "config_exists", "fresh machine: now=config_exists")
        expect(status(report, "vault_path_set") == "blocked", "vault blocked behind config")
        expect(status(report, "registry_exists") == "blocked", "registry blocked at start")
        expect(sum(1 for s in report["stages"] if s["status"] == "now") == 1, "exactly one now")

        print("\nStage 1 — config written:")
        cfg.write_text("{}")
        state["config"] = True
        report = evaluate()
        expect(report["now"] == "vault_path_set", "now advances to vault_path_set")
        expect(status(report, "calendar_auth") == "next", "optional calendar offered (next), not now")

        print("\nStage 2 — vault configured:")
        (vault / "Projects").mkdir(parents=True)
        state["vault"] = True
        report = evaluate()
        expect(report["now"] == "github_token_set", "now advances to github_token_set")
        expect(status(report, "registry_exists") == "blocked", "registry still blocked without PAT")

        print("\nStage 3 — PAT stored:")
        state["token"] = True
        report = evaluate()
        expect(report["now"] == "registry_exists", "now advances to registry_exists (promote step)")

        print("\nStage 4 — projects promoted (registry + projection + db):")
        (vault / "Projects" / "00-project-registry.md").write_text("# registry")
        (vault / "projects.yaml").write_text("projects: []")
        db.write_text("")
        with patch("rebalance.ingest.registry.get_projects", return_value=[{"name": "p"}]):
            report = evaluate()
        render(report)
        expect(report["setup_complete"], "required journey complete")
        expect(report["now"] is None, "no current step once required stages done")
        expect(status(report, "calendar_auth") == "next", "skipped optional stages remain visible")

    print()
    if failures:
        print(f"SPIKE FAILED: {len(failures)} contract violation(s)")
        return 1
    print("SPIKE PASSED: status contract holds at every stage boundary.")
    return 0


if __name__ == "__main__":
    sys.exit(real_machine() if "--real" in sys.argv else sandbox_walkthrough())

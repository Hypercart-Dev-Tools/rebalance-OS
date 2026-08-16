#!/usr/bin/env python3
"""Obsidian daily notes rollover.

Every night at midnight this:
  1. Reads "0. Today's Notes.md"
  2. Prepends its content to the top of "0. Yesterday.md" under a dated header
     (newest entry on top — a rolling log of every day)
  3. Blanks "0. Today's Notes.md" so each morning starts clean

It also AUTO-CREATES "0. Today's Notes.md" if it has gone missing — but with two
safety guards so it never churns out conflict copies:

  * Vault sentinel  — only create when the real vault is actually present (a known
    file, "0. Now.md", must exist). Prevents writing into a wrong/unmounted path.
  * Circuit breaker — auto-creates are recorded in a state file; if the file gets
    recreated more than MAX_CREATES_PER_DAY times in 24h, the breaker TRIPS and
    refuses to recreate, logging a warning instead. This stops a sync-loop
    (file keeps vanishing → script keeps recreating) from spewing duplicates.

Stdlib only — no third-party deps, so it runs under any python3.

Usage:
  obsidian_daily_rollover.py            # do the rollover (the nightly job)
  obsidian_daily_rollover.py --setup    # create the two files if missing, reset breaker
  obsidian_daily_rollover.py --dry-run  # print what would happen, change nothing
  obsidian_daily_rollover.py --status   # show breaker state, then exit
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Structured job event logging — optional; fails silently if rebalance isn't
# importable (e.g. when run under the system python3 fallback, not the venv).
try:
    from rebalance.ingest.auth_log import log_job_completed, log_job_failed, log_job_started as _ljs
    _JOB_LOG = True
except ImportError:
    _JOB_LOG = False

def _log_job(event: str, elapsed: float | None = None, exit_code: int | None = None) -> None:
    if not _JOB_LOG:
        return
    if event == "started":
        _ljs("obsidian-rollover")
    elif event == "completed":
        log_job_completed("obsidian-rollover", elapsed)
    elif event == "failed":
        log_job_failed("obsidian-rollover", exit_code or 1, elapsed)

# --- Configuration -----------------------------------------------------------
# Operator-specific. Set OBSIDIAN_VAULT to your own vault; the former hardcoded
# default named one operator's home directory and could not work anywhere else.
VAULT = Path(os.environ.get("OBSIDIAN_VAULT", str(Path.home() / "Documents" / "Obsidian Vault")))
TODAY_FILE = VAULT / "0. Today's Notes.md"
YESTERDAY_FILE = VAULT / "0. Yesterday.md"

# Sentinels: files that live in the real vault. If NONE are present we assume the
# vault isn't mounted/synced yet and refuse to create anything. Matching on any one
# of several stable anchor files (not a single name) keeps the guard working even
# when notes get reorganized/renamed — the failure mode that silently stalled the
# rollover when the old lone sentinel "0. Now.md" was removed.
VAULT_SENTINELS = [
    VAULT / "0. Now.md",
    VAULT / "0. Goals.md",
    VAULT / "0. Incoming.md",
    VAULT / "0. Yesterday.md",
]

# Circuit breaker: auto-create events are recorded here (kept out of git in temp/).
STATE_FILE = Path(__file__).resolve().parent.parent / "temp" / "obsidian-rollover-state.json"
# Trip the breaker if Today's Notes is auto-created more than this many times in 24h.
MAX_CREATES_PER_DAY = 3

# Header line that always stays at the very top of the Yesterday log.
YESTERDAY_TITLE = "# Yesterday"
# Starter content for a freshly-blanked Today's Notes (kept minimal on purpose).
TODAY_TEMPLATE = ""
# -----------------------------------------------------------------------------


def log(msg: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] {msg}", flush=True)


# --- Circuit-breaker state ---------------------------------------------------
def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            log(f"WARN: state file unreadable, starting fresh: {STATE_FILE}")
    return {}


def _save_state(state: dict) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError as exc:
        log(f"WARN: could not write state file: {exc}")


def _recent_creates(state: dict, within_hours: int = 24) -> list[str]:
    cutoff = datetime.now() - timedelta(hours=within_hours)
    recent = []
    for s in state.get("today_creates", []):
        try:
            if datetime.fromisoformat(s) >= cutoff:
                recent.append(s)
        except ValueError:
            continue
    return recent


def _record_create(state: dict) -> None:
    # Keep a 48h trailing window so the file doesn't grow forever.
    kept = _recent_creates(state, within_hours=48)
    kept.append(datetime.now().isoformat())
    state["today_creates"] = kept
    _save_state(state)


def _reset_breaker() -> None:
    state = _load_state()
    state["today_creates"] = []
    _save_state(state)


# --- Vault / file guards -----------------------------------------------------
def vault_ready() -> bool:
    """True only when the real vault is present (at least one sentinel exists)."""
    return VAULT.is_dir() and any(s.exists() for s in VAULT_SENTINELS)


def ensure_today_file() -> bool:
    """Auto-create Today's Notes if missing, guarded by the circuit breaker.

    Returns True if the file exists afterwards, False if we declined to create it.
    """
    if TODAY_FILE.exists():
        return True

    state = _load_state()
    recent = _recent_creates(state)
    if len(recent) >= MAX_CREATES_PER_DAY:
        log(
            f"CIRCUIT BREAKER TRIPPED: {TODAY_FILE.name} has been auto-created "
            f"{len(recent)}x in 24h — something keeps removing it (sync loop or "
            f"wrong path). NOT recreating. Investigate, then run with --setup to "
            f"reset the breaker."
        )
        return False

    TODAY_FILE.write_text(TODAY_TEMPLATE, encoding="utf-8")
    _record_create(state)
    log(f"auto-created {TODAY_FILE.name} (create #{len(recent) + 1} of "
        f"{MAX_CREATES_PER_DAY} allowed in 24h)")
    return True


def ensure_yesterday_file() -> None:
    if not YESTERDAY_FILE.exists():
        YESTERDAY_FILE.write_text(YESTERDAY_TITLE + "\n", encoding="utf-8")
        log(f"created {YESTERDAY_FILE.name}")


# --- Rollover ----------------------------------------------------------------
def build_entry(content: str, entry_date) -> str:
    header = entry_date.strftime("## %Y-%m-%d (%A)")
    return f"{header}\n\n{content.strip()}\n\n---\n\n"


def prepend_to_yesterday(entry: str) -> None:
    """Insert a new entry directly under the Yesterday title (newest first)."""
    existing = YESTERDAY_FILE.read_text(encoding="utf-8") if YESTERDAY_FILE.exists() else ""
    lines = existing.splitlines(keepends=True)
    if lines and lines[0].lstrip().startswith(YESTERDAY_TITLE):
        title = lines[0]
        body = "".join(lines[1:]).lstrip("\n")
        new = f"{title.rstrip()}\n\n{entry}{body}"
    else:
        new = f"{YESTERDAY_TITLE}\n\n{entry}{existing.lstrip()}"
    YESTERDAY_FILE.write_text(new, encoding="utf-8")


def rollover(dry_run: bool = False) -> int:
    if not vault_ready():
        names = ", ".join(f"'{s.name}'" for s in VAULT_SENTINELS)
        log(f"vault not ready (no sentinel found; looked for {names}) — "
            f"skipping safely. Nothing created or changed.")
        return 0

    if not ensure_today_file():
        return 0  # breaker tripped; nothing to roll

    ensure_yesterday_file()

    today_content = TODAY_FILE.read_text(encoding="utf-8")
    if not today_content.strip():
        log("Today's Notes is empty — nothing to roll over. Leaving files as-is.")
        return 0

    # The job fires at 00:00 of the new day, so the notes belong to *yesterday*.
    entry_date = datetime.now() - timedelta(days=1)
    entry = build_entry(today_content, entry_date)

    if dry_run:
        log("DRY RUN — would prepend this entry to Yesterday:")
        print("-" * 60)
        print(entry, end="")
        print("-" * 60)
        log("DRY RUN — would then blank Today's Notes. No changes made.")
        return 0

    prepend_to_yesterday(entry)
    TODAY_FILE.write_text(TODAY_TEMPLATE, encoding="utf-8")
    log(
        f"rolled {len(today_content.strip())} chars into {YESTERDAY_FILE.name} "
        f"under {entry_date:%Y-%m-%d}; blanked {TODAY_FILE.name}"
    )
    return 0


def show_status() -> int:
    state = _load_state()
    recent = _recent_creates(state)
    present = [s.name for s in VAULT_SENTINELS if s.exists()]
    log(f"vault ready: {vault_ready()} (sentinels present: {present or 'none'})")
    log(f"Today's Notes exists: {TODAY_FILE.exists()}")
    log(f"auto-creates in last 24h: {len(recent)} / {MAX_CREATES_PER_DAY}")
    if len(recent) >= MAX_CREATES_PER_DAY:
        log("breaker state: TRIPPED — run --setup to reset")
    else:
        log("breaker state: ok")
    return 0


def main(argv: list[str]) -> int:
    import time
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setup", action="store_true",
                        help="create the two files if missing, reset the breaker")
    parser.add_argument("--dry-run", action="store_true",
                        help="show what would happen without changing anything")
    parser.add_argument("--status", action="store_true",
                        help="show circuit-breaker state, then exit")
    args = parser.parse_args(argv)

    if args.status:
        return show_status()

    if not VAULT.exists():
        log(f"ERROR: vault not found at {VAULT}")
        return 1

    if args.setup:
        if not vault_ready():
            names = ", ".join(f"'{s.name}'" for s in VAULT_SENTINELS)
            log(f"vault not ready (no sentinel found; looked for {names}) — "
                f"refusing to create files. Mount/sync the vault first.")
            return 1
        _reset_breaker()
        ensure_today_file()
        ensure_yesterday_file()
        log("setup complete (circuit breaker reset).")
        return 0

    _log_job("started")
    _t0 = time.monotonic()
    code = rollover(dry_run=args.dry_run)
    elapsed = time.monotonic() - _t0
    if code == 0:
        _log_job("completed", elapsed=elapsed)
    else:
        _log_job("failed", elapsed=elapsed, exit_code=code)
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

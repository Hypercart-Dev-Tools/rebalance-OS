#!/usr/bin/env python3
"""Obsidian daily activity sync — the 6 PM launchd consumer (GH-112).

Synthesizes a Gemini daily-activity summary from the structured pulse snapshot
and lands it in an idempotent, sentinel-bracketed block at the BOTTOM of the
Obsidian vault's "0. Today's Notes.md", preserving any manual notes above it.

Design contract (PROJECT/2-WORKING/MARATHON-2026-07-04.md + GH-112 doc):
  * Input signal  — collect_pulse_snapshot() STRUCTURED output (never rendered md).
  * Synthesis     — Gemini only (_synthesize_gemini, thinking_budget=0,
                    max_tokens=2048). Gemini unavailable/fails -> SKIP + log,
                    write NOTHING. The Qwen fallback must never touch the vault.
  * Vault target  — derived from obsidian_daily_rollover.TODAY_FILE (never hardcoded).
  * Block markers — <!-- AI Daily Summary Start/End -->, replaced in-place on rerun.
  * Late-run rule — a post-midnight launchd catch-up (local hour < 18, after the
                    00:00 rollover moved Today->Yesterday) SKIPS entirely.

Requires the rebalance venv (imports rebalance.*). Run via the bash wrapper
utils/obsidian_daily_sync.sh so launchd inherits Full Disk Access.

Usage:
  obsidian_daily_sync.py            # do the sync (the 6 PM job)
  obsidian_daily_sync.py --dry-run  # print the block that would be written; no write
  obsidian_daily_sync.py --status   # show vault/block state, then exit
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

# utils/ is not a package — add it so we reuse the rollover module's vault config
# (TODAY_FILE / vault_ready) rather than hardcoding the vault path a second time.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from obsidian_daily_rollover import TODAY_FILE, vault_ready  # noqa: E402

MARKER_START = "<!-- AI Daily Summary Start -->"
MARKER_END = "<!-- AI Daily Summary End -->"
BLOCK_HEADING = "## 🤖 AI Daily Summary"

# The 6 PM job's valid window is same-day 18:00 -> 23:59. A launchd catch-up that
# wakes the Mac after midnight fires in the small hours (local hour 0-17); by then
# the 00:00 rollover has moved Today -> Yesterday, so appending would pollute the
# fresh day. Below this floor, skip.
RUN_HOUR_FLOOR = 18

# Structured job-event logging — optional; silent if rebalance isn't importable.
try:
    from rebalance.ingest.auth_log import (
        log_job_completed,
        log_job_failed,
        log_job_started as _ljs,
    )
    _JOB_LOG = True
except ImportError:
    _JOB_LOG = False

JOB_NAME = "obsidian-daily-sync"


def _log_job(event: str, elapsed: float | None = None, exit_code: int | None = None) -> None:
    if not _JOB_LOG:
        return
    if event == "started":
        _ljs(JOB_NAME)
    elif event == "completed":
        log_job_completed(JOB_NAME, elapsed)
    elif event == "failed":
        log_job_failed(JOB_NAME, exit_code or 1, elapsed)


def log(msg: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] {msg}", flush=True)


# --- Pure block logic (unit-tested, no I/O) ----------------------------------
def _format_time(dt: datetime) -> str:
    """12-hour clock like '6:00 PM' (no leading zero) for the reminder line."""
    return dt.strftime("%I:%M %p").lstrip("0")


def build_block(summary: str, generated_at: datetime) -> str:
    """The exact sentinel-bracketed block written to the vault.

    A subtle italic reminder line under the heading flags the block as machine-
    written and stamps *when* — the actual run time (~6 PM for the scheduled job,
    or later if launchd caught up on wake). ``generated_at`` is passed in (not
    read from the clock here) so the block stays byte-stable across reruns.
    """
    stamp = f"*Auto-generated at {_format_time(generated_at)}.*"
    return f"{MARKER_START}\n{BLOCK_HEADING}\n{stamp}\n\n{summary.strip()}\n{MARKER_END}\n"


def upsert_block(content: str, summary: str, generated_at: datetime) -> str:
    """Replace an existing sentinel block in-place, else append one at the bottom.

    Idempotent: rerunning always yields exactly ONE block with the markers intact
    and every byte of surrounding human markdown untouched. Uses first-start /
    last-end so an accidental duplicate pair collapses back to a single block.
    """
    block = build_block(summary, generated_at)
    if MARKER_START in content and MARKER_END in content:
        before = content.split(MARKER_START, 1)[0]
        # Strip leading blank lines the old block left behind so trailing newlines
        # don't accumulate one-per-run (breaks the byte-stable fixed point). The
        # block already ends in "\n"; re-separate only if real content follows it.
        tail = content.rsplit(MARKER_END, 1)[1].lstrip("\n")
        return before + block + (f"\n{tail}" if tail else "")
    # Append at the bottom, separated from manual notes by exactly one blank line.
    body = content if content.endswith("\n") else content + "\n"
    if not body.endswith("\n\n"):
        body += "\n"
    return body + block


def is_late_run(now: datetime) -> bool:
    """True if this fired as a post-midnight launchd catch-up (past the rollover)."""
    return now.hour < RUN_HOUR_FLOOR


# --- Signal + synthesis (I/O; lazy imports so tests can monkeypatch) ---------
PROMPT_TEMPLATE = """You are an AI assistant summarizing the daily activity of a software engineer.
Based on the following structured snapshot of today's activity, write a concise daily summary.
Keep it casual but informative. Group by project or theme where possible. Do NOT hallucinate data.
If activity is sparse, say so briefly rather than padding.

Activity data:
{data}
"""


def collect_today_activity() -> dict:
    """Today's structured pulse activity as a plain dict (never rendered markdown)."""
    import os
    from dataclasses import asdict

    from rebalance.ingest.pulse import collect_pulse_snapshot
    from rebalance.ingest.config import get_pulse_config, get_github_token

    default_db = Path(os.environ["HOME"]) / "Library/Application Support/rebalance-os/rebalance.db"
    db_path = Path(os.environ.get("REBALANCE_DB", default_db))
    config = get_pulse_config()
    snapshot = collect_pulse_snapshot(
        database_path=db_path,
        github_login=config["github_login"],
        slack_user_id=config.get("slack_user_id"),
        timezone_name=config.get("pulse_timezone", "UTC"),
        github_token=get_github_token(),
    )
    return asdict(snapshot.today)


def synthesize(activity: dict) -> str | None:
    """Gemini-only synthesis. Returns text, or None if Gemini is unavailable/fails.

    NO Qwen fallback — a fallback-quality summary must never reach the vault, so
    both "no key" and "call failed" return None and the caller writes nothing.
    """
    from rebalance.ingest.config import get_gemini_api_key
    from rebalance.ingest.querier import _synthesize_gemini

    key = get_gemini_api_key()
    if not key:
        log("SKIP: no Gemini API key available — refusing to write a fallback summary.")
        return None
    prompt = PROMPT_TEMPLATE.format(data=json.dumps(activity, indent=2, default=str))
    try:
        return _synthesize_gemini(prompt, api_key=key, thinking_budget=0, max_tokens=2048)
    except Exception as e:  # noqa: BLE001 — any failure means skip, never fall back
        log(f"SKIP: Gemini synthesis failed ({e}) — no fallback written to vault.")
        return None


# --- Orchestration -----------------------------------------------------------
def run(dry_run: bool = False, now: datetime | None = None, force: bool = False) -> int:
    now = now or datetime.now()

    if not force and is_late_run(now):
        log(f"SKIP: late catch-up run at {now:%H:%M} (< {RUN_HOUR_FLOOR:02d}:00) — the 00:00 "
            f"rollover has already moved Today->Yesterday. Writing nothing.")
        return 0

    if not vault_ready():
        log("SKIP: vault not ready (no sentinel found) — writing nothing.")
        return 0

    if not TODAY_FILE.exists():
        log(f"SKIP: {TODAY_FILE.name} missing — the rollover owns file creation. Writing nothing.")
        return 0

    activity = collect_today_activity()
    summary = synthesize(activity)
    if summary is None:
        return 0  # skip reason already logged; clean no-op

    content = TODAY_FILE.read_text(encoding="utf-8")
    new_content = upsert_block(content, summary, now)

    if dry_run:
        log("DRY RUN — would write this block to the bottom of Today's Notes:")
        print("-" * 60)
        print(build_block(summary, now), end="")
        print("-" * 60)
        return 0

    if new_content != content:
        TODAY_FILE.write_text(new_content, encoding="utf-8")
        log(f"wrote AI daily summary block ({len(summary)} chars) to {TODAY_FILE.name}")
    else:
        log("summary block unchanged — no write needed.")
    return 0


def show_status() -> int:
    now = datetime.now()
    log(f"vault ready: {vault_ready()}")
    log(f"Today's Notes exists: {TODAY_FILE.exists()}")
    if TODAY_FILE.exists():
        content = TODAY_FILE.read_text(encoding="utf-8")
        present = MARKER_START in content and MARKER_END in content
        log(f"AI summary block present: {present}")
    log(f"would run now ({now:%H:%M}): {not is_late_run(now)} (hour floor {RUN_HOUR_FLOOR:02d}:00)")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="print the block that would be written; change nothing")
    parser.add_argument("--force", action="store_true",
                        help="bypass the 6 PM floor guard for manual runs (uses real current time)")
    parser.add_argument("--status", action="store_true",
                        help="show vault/block state, then exit")
    args = parser.parse_args(argv)

    if args.status:
        return show_status()

    _log_job("started")
    t0 = time.monotonic()
    try:
        code = run(dry_run=args.dry_run, force=args.force)
    except Exception as e:  # noqa: BLE001
        elapsed = time.monotonic() - t0
        log(f"ERROR: {e}")
        _log_job("failed", elapsed=elapsed, exit_code=1)
        return 1
    elapsed = time.monotonic() - t0
    _log_job("completed" if code == 0 else "failed", elapsed=elapsed, exit_code=code)
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

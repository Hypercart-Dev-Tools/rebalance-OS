#!/usr/bin/env python3
"""Git Pulse daily synthesis — the GH-114 exporter.

Shells out to `experimental/git-pulse/view.sh --today` to collect multi-device
git activity, synthesizes a daily summary via Gemini, and lands it in an idempotent,
sentinel-bracketed block at the BOTTOM of the Obsidian vault's "0. Today's Notes.md".

Appends AFTER the GH-112 AI Daily Summary block if both exist.

Optional second destination (git_pulse_clio_enabled, see rebalance.ingest.config
.get_pulse_config): the SAME synthesized summary is ALSO upserted into a growing,
git-committed log file inside pulse_target_path (default
"<pulse_target_path>/CLIO/git-pulse-daily-log.md"). Unlike the Obsidian write,
this is decoupled from vault_ready() — it works for users running Git Pulse Sync
without an Obsidian vault configured at all. Each day gets its own date-scoped
sentinel block so reruns upsert only today's entry; prior days accumulate below.

Usage:
  git_pulse_daily_synthesis.py            # do the sync
  git_pulse_daily_synthesis.py --dry-run  # print the block(s) that would be written
  git_pulse_daily_synthesis.py --status   # show vault/CLIO/block state, then exit
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import os
from datetime import datetime
from pathlib import Path

# Reuse the rollover module's vault config
sys.path.insert(0, str(Path(__file__).resolve().parent))
from obsidian_daily_rollover import TODAY_FILE, vault_ready  # noqa: E402

MARKER_START = "<!-- Git Pulse Daily Summary Start -->"
MARKER_END = "<!-- Git Pulse Daily Summary End -->"
BLOCK_HEADING = "## 📊 Git Pulse Daily Summary"

# The zero-row fallback synthesize() returns. Named so the no-clobber guard
# below can recognize "the summary about to be written is itself a fallback"
# without string-literal duplication.
FALLBACK_SUMMARY = "No git activity found today."

# CLIO log: one block per calendar day, so the markers are date-scoped — this is
# what lets today's rerun replace only today's block while every prior day's
# block in the same growing file stays untouched.
CLIO_BLOCK_HEADING = "Git Pulse Daily Summary"

RUN_HOUR_FLOOR = 18

try:
    from rebalance.ingest.auth_log import (
        log_job_completed,
        log_job_failed,
        log_job_started as _ljs,
    )
    _JOB_LOG = True
except ImportError:
    _JOB_LOG = False

JOB_NAME = "git-pulse-daily-synthesis"


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


# --- Pure block logic ----------------------------------
def _format_time(dt: datetime) -> str:
    return dt.strftime("%I:%M %p").lstrip("0")


def build_block(summary: str, generated_at: datetime) -> str:
    stamp = f"*Auto-generated at {_format_time(generated_at)}.*"
    return f"{MARKER_START}\n{BLOCK_HEADING}\n{stamp}\n\n{summary.strip()}\n{MARKER_END}\n"


def upsert_block(content: str, summary: str, generated_at: datetime) -> str:
    block = build_block(summary, generated_at)
    if MARKER_START in content and MARKER_END in content:
        before = content.split(MARKER_START, 1)[0]
        tail = content.rsplit(MARKER_END, 1)[1].lstrip("\n")
        return before + block + (f"\n{tail}" if tail else "")
    
    body = content if content.endswith("\n") else content + "\n"
    if not body.endswith("\n\n"):
        body += "\n"
    return body + block


def is_late_run(now: datetime) -> bool:
    return now.hour < RUN_HOUR_FLOOR


# --- CLIO block logic (growing multi-day log, date-scoped markers) -----------
def _clio_markers(date_str: str) -> tuple[str, str]:
    return (
        f"<!-- Git Pulse Daily Summary {date_str} Start -->",
        f"<!-- Git Pulse Daily Summary {date_str} End -->",
    )


def build_clio_block(summary: str, generated_at: datetime) -> str:
    """The dated, sentinel-bracketed block appended to the CLIO log file."""
    date_str = generated_at.strftime("%Y-%m-%d")
    start, end = _clio_markers(date_str)
    stamp = f"*Auto-generated at {_format_time(generated_at)}.*"
    heading = f"## {date_str} — {CLIO_BLOCK_HEADING}"
    return f"{start}\n{heading}\n{stamp}\n\n{summary.strip()}\n{end}\n"


def upsert_clio_block(content: str, summary: str, generated_at: datetime) -> str:
    """Upsert *today's* dated block into a growing multi-day log.

    Idempotent per day: rerunning the same day replaces only that day's block.
    Every other day's block already in the file is left byte-for-byte intact,
    so the file accumulates one block per day instead of being overwritten.
    """
    date_str = generated_at.strftime("%Y-%m-%d")
    start, end = _clio_markers(date_str)
    block = build_clio_block(summary, generated_at)

    if start in content and end in content:
        before = content.split(start, 1)[0]
        tail = content.split(end, 1)[1].lstrip("\n")
        return before + block + (f"\n{tail}" if tail else "")

    if not content:
        return block
    body = content if content.endswith("\n") else content + "\n"
    if not body.endswith("\n\n"):
        body += "\n"
    return body + block


# --- No-clobber guard (GH-129 follow-up #3) -----------------------------
# A later, transient zero-row rerun on the same day must not overwrite an
# earlier successful run's real summary with the empty-activity fallback.
# A first-write-of-the-day (no block yet, or a block that's already the
# fallback) is unaffected — the guard only fires for "real content already
# there -> don't overwrite with empty."
def _extract_block_text(content: str, start_marker: str, end_marker: str) -> str | None:
    """Return the text between start/end markers in content, or None if either
    marker is absent (i.e. no block exists yet at this location)."""
    if start_marker not in content or end_marker not in content:
        return None
    return content.split(start_marker, 1)[1].split(end_marker, 1)[0]


def _would_clobber_real_summary(existing_block_text: str | None, new_summary: str) -> bool:
    """True only when writing new_summary would replace an earlier real summary
    with the zero-row fallback: new_summary IS the fallback, a block already
    exists, and that existing block is non-empty and is not itself the
    fallback."""
    if new_summary != FALLBACK_SUMMARY:
        return False
    if existing_block_text is None:
        return False
    stripped = existing_block_text.strip()
    if not stripped:
        return False
    if FALLBACK_SUMMARY in stripped:
        return False
    return True


# --- Signal + synthesis ---------------------------------
PROMPT_TEMPLATE = """You are an AI assistant summarizing the git commit activity of a software engineer for the day.
Based on the following structured snapshot of today's git pulse activity, write a concise daily summary.
Keep it casual but informative. Group by repository or theme where possible. Do NOT hallucinate data.
If activity is sparse, say so briefly rather than padding.

Activity data:
{data}
"""

def collect_today_activity(dry_run: bool = False, force: bool = False) -> tuple[str | None, int]:
    """Shells out to view.sh --today and returns the TSV stdout string and exit code."""
    repo_root = Path(__file__).resolve().parent.parent
    view_script = repo_root / "experimental" / "git-pulse" / "view.sh"
    
    if not view_script.exists():
        log(f"SKIP: view.sh not found at {view_script}")
        return None, 1
        
    cmd = [str(view_script), "--today"]
    
    try:
        env = os.environ.copy()
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
        if result.returncode != 0:
            log(f"SKIP: view.sh failed with exit code {result.returncode}. Is config missing?")
            if result.stderr:
                log(f"view.sh stderr: {result.stderr.strip()}")
            return None, result.returncode
        return result.stdout.strip(), 0
    except Exception as e:
        log(f"SKIP: failed to execute view.sh: {e}")
        return None, 1


def synthesize(activity_tsv: str) -> str | None:
    from rebalance.ingest.config import get_gemini_api_key
    from rebalance.ingest.querier import _synthesize_gemini
    
    lines = activity_tsv.splitlines()
    if len(lines) <= 1:
        # Zero-row case (only headers or empty)
        return FALLBACK_SUMMARY
        
    key = get_gemini_api_key()
    if not key:
        log("SKIP: no Gemini API key available — refusing to write a fallback summary.")
        return None
        
    prompt = PROMPT_TEMPLATE.format(data=activity_tsv)
    try:
        return _synthesize_gemini(prompt, api_key=key, thinking_budget=0, max_tokens=2048)
    except Exception as e:
        log(f"SKIP: Gemini synthesis failed ({e}) — no fallback written to vault.")
        return None


# --- CLIO sync (optional second destination, decoupled from the vault) ------
def sync_to_clio(summary: str, now: datetime, dry_run: bool = False) -> dict:
    """Upsert today's block into pulse_target_path/<subdir>/<filename>, commit+push.

    Opt-in via git_pulse_clio_enabled (see rebalance.ingest.config.get_pulse_config).
    Does NOT depend on vault_ready() — this is the path for users running Git Pulse
    Sync without an Obsidian vault configured at all. Reuses pulse.py's
    _commit_and_push_if_changed so this gets the same write/commit/push + push-repair
    behavior as the primary live-pulse.md writer, rather than a second implementation.
    """
    from rebalance.ingest.config import get_pulse_config
    from rebalance.ingest.pulse import _commit_and_push_if_changed

    cfg = get_pulse_config()
    if not cfg.get("git_pulse_clio_enabled"):
        return {"enabled": False}

    target_path = cfg.get("pulse_target_path")
    if not target_path:
        log("SKIP CLIO: git_pulse_clio_enabled is set but pulse_target_path is not configured.")
        return {"enabled": True, "ok": False, "reason": "pulse_target_path not configured"}

    target_repo = Path(target_path).expanduser().resolve()
    if not (target_repo / ".git").exists():
        log(f"SKIP CLIO: pulse_target_path is not a git repo: {target_repo}")
        return {"enabled": True, "ok": False, "reason": f"not a git repo: {target_repo}"}

    subdir = cfg.get("git_pulse_clio_subdir") or "CLIO"
    filename = cfg.get("git_pulse_clio_filename") or "git-pulse-daily-log.md"
    file_rel = f"{subdir}/{filename}"

    target_file = target_repo / file_rel
    existing = target_file.read_text(encoding="utf-8") if target_file.exists() else ""

    clio_start, clio_end = _clio_markers(now.strftime("%Y-%m-%d"))
    existing_clio_block = _extract_block_text(existing, clio_start, clio_end)
    if _would_clobber_real_summary(existing_clio_block, summary):
        log(f"SKIP: zero-row rerun would clobber an existing non-empty summary ({file_rel})")
        return {"enabled": True, "ok": True, "skipped": "would_clobber"}

    new_content = upsert_clio_block(existing, summary, now)

    if dry_run:
        log(f"DRY RUN — would upsert CLIO block into {file_rel}:")
        print("-" * 60)
        print(build_clio_block(summary, now), end="")
        print("-" * 60)
        return {"enabled": True, "ok": True, "dry_run": True, "file_rel": file_rel}

    result = _commit_and_push_if_changed(
        target_repo=target_repo,
        file_rel=file_rel,
        new_content=new_content,
        push=True,
        commit_message=f"git-pulse: {now:%Y-%m-%d} daily summary",
    )
    log(f"CLIO sync ({file_rel}): {result}")
    return {"enabled": True, "ok": True, "file_rel": file_rel, **result}


# --- Orchestration -----------------------------------------------------------
def run(dry_run: bool = False, now: datetime | None = None, force: bool = False) -> int:
    now = now or datetime.now()

    if not force and is_late_run(now):
        log(f"SKIP: late catch-up run at {now:%H:%M} (< {RUN_HOUR_FLOOR:02d}:00) — the 00:00 "
            f"rollover has already moved Today->Yesterday. Writing nothing.")
        return 0

    # vault_ready() gates ONLY the Obsidian write below — collecting/synthesizing
    # activity, and the optional CLIO write, both work without an Obsidian vault.
    vault_write_ready = vault_ready() and TODAY_FILE.exists()
    if not vault_ready():
        log("Obsidian vault not ready (no sentinel found) — skipping the vault write.")
    elif not TODAY_FILE.exists():
        log(f"{TODAY_FILE.name} missing — the rollover owns file creation. Skipping the vault write.")

    from rebalance.ingest.config import get_pulse_config
    clio_enabled = bool(get_pulse_config().get("git_pulse_clio_enabled"))

    if not vault_write_ready and not clio_enabled:
        log("SKIP: no destination available (vault not ready, CLIO not enabled). Writing nothing.")
        return 0

    activity_tsv, exit_code = collect_today_activity(dry_run, force)
    if exit_code != 0 or activity_tsv is None:
        return 0  # skip reason already logged; clean no-op

    summary = synthesize(activity_tsv)
    if summary is None:
        return 0

    if clio_enabled:
        sync_to_clio(summary, now, dry_run=dry_run)

    if not vault_write_ready:
        return 0

    content = TODAY_FILE.read_text(encoding="utf-8")
    existing_block = _extract_block_text(content, MARKER_START, MARKER_END)
    if _would_clobber_real_summary(existing_block, summary):
        log("SKIP: zero-row rerun would clobber an existing non-empty summary")
        return 0

    new_content = upsert_block(content, summary, now)

    if dry_run:
        log("DRY RUN — would write this block to the bottom of Today's Notes:")
        print("-" * 60)
        print(build_block(summary, now), end="")
        print("-" * 60)
        return 0

    if new_content != content:
        TODAY_FILE.write_text(new_content, encoding="utf-8")
        log(f"wrote Git Pulse daily summary block ({len(summary)} chars) to {TODAY_FILE.name}")
    else:
        log("summary block unchanged — no write needed.")
    return 0


def show_status() -> int:
    from rebalance.ingest.config import get_pulse_config

    now = datetime.now()
    log(f"vault ready: {vault_ready()}")
    log(f"Today's Notes exists: {TODAY_FILE.exists()}")
    if TODAY_FILE.exists():
        content = TODAY_FILE.read_text(encoding="utf-8")
        present = MARKER_START in content and MARKER_END in content
        log(f"Git Pulse summary block present: {present}")

    cfg = get_pulse_config()
    clio_enabled = bool(cfg.get("git_pulse_clio_enabled"))
    log(f"CLIO export enabled: {clio_enabled}")
    if clio_enabled:
        target_path = cfg.get("pulse_target_path")
        subdir = cfg.get("git_pulse_clio_subdir") or "CLIO"
        filename = cfg.get("git_pulse_clio_filename") or "git-pulse-daily-log.md"
        if target_path:
            clio_file = Path(target_path).expanduser().resolve() / subdir / filename
            log(f"CLIO target: {clio_file} (exists: {clio_file.exists()})")
        else:
            log("CLIO target: pulse_target_path not configured — CLIO write would SKIP")

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
    except Exception as e:
        elapsed = time.monotonic() - t0
        log(f"ERROR: {e}")
        _log_job("failed", elapsed=elapsed, exit_code=1)
        return 1
    elapsed = time.monotonic() - t0
    _log_job("completed" if code == 0 else "failed", elapsed=elapsed, exit_code=code)
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

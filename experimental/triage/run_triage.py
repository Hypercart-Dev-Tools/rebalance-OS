#!/usr/bin/env python3
"""One-command triage: sync, analyze, and optionally publish — all in one step.

This wraps the multi-step process (github-sync, sleuth-sync, spike.py) into
a single command. It does NOT modify spike.py or any existing process.

Examples:
    # Preview to stdout (no side effects)
    ./run_triage.py --repo BinoidCBD/universal-child-theme-oct-2024

    # Sync fresh data, then preview
    ./run_triage.py --repo X --sync

    # Sync + publish as a GitHub issue
    ./run_triage.py --repo X --sync --publish

    # Skip sleuth sync (no credentials), resolve ambiguities interactively
    ./run_triage.py --repo X --sync --no-sleuth --ambiguity ask-operator

    # Use existing DB data, publish with a custom title
    ./run_triage.py --repo X --publish --title "Weekly triage 2026-05-01"
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SPIKE = Path(__file__).resolve().parent / "spike.py"
DEFAULT_DB = Path(os.environ.get("REBALANCE_DB", REPO_ROOT / "rebalance.db"))


def _run(cmd: list[str], label: str, check: bool = True) -> subprocess.CompletedProcess:
    print(f"\n{'─' * 60}", file=sys.stderr)
    print(f"  {label}", file=sys.stderr)
    print(f"  $ {' '.join(cmd)}", file=sys.stderr)
    print(f"{'─' * 60}", file=sys.stderr)
    result = subprocess.run(cmd, text=True)
    if check and result.returncode != 0:
        print(f"\n✗ {label} failed (exit {result.returncode})", file=sys.stderr)
        sys.exit(result.returncode)
    return result


def _run_quiet(cmd: list[str], label: str) -> subprocess.CompletedProcess:
    """Run a command, capture output, print summary only."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        last_line = (result.stderr or result.stdout or "").strip().rsplit("\n", 1)[-1]
        print(f"  ✓ {label}: {last_line}", file=sys.stderr)
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="One-command triage: sync → analyze → publish",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--repo", required=True,
                   help="GitHub repo (owner/name)")
    p.add_argument("--db", type=Path, default=DEFAULT_DB,
                   help=f"SQLite database path (default: {DEFAULT_DB})")

    sync_group = p.add_argument_group("data sync")
    sync_group.add_argument("--sync", action="store_true",
                            help="sync GitHub + Sleuth data before triage")
    sync_group.add_argument("--no-sleuth", action="store_true",
                            help="skip Sleuth sync (use when credentials aren't configured)")
    sync_group.add_argument("--days", type=int, default=90,
                            help="lookback window for GitHub sync (default: 90)")

    triage_group = p.add_argument_group("triage options")
    triage_group.add_argument("--ambiguity", choices=["auto", "queue", "ask-operator"],
                              default="queue",
                              help="how to handle review cases (default: queue)")
    triage_group.add_argument("--decisions", type=Path, default=None,
                              help="JSONL of pre-made decisions from a previous run")
    triage_group.add_argument("--duplicate-threshold", type=float, default=0.7,
                              help="jaccard cutoff for duplicate detection (0..1)")

    publish_group = p.add_argument_group("publishing")
    publish_group.add_argument("--publish", action="store_true",
                               help="post the triage report as a GitHub issue")
    publish_group.add_argument("--title", default=None,
                               help="custom issue title (default: auto-generated)")
    publish_group.add_argument("--dry-run", action="store_true",
                               help="show what would be posted without posting")

    args = p.parse_args(argv)

    print(f"Triage: {args.repo}", file=sys.stderr)
    print(f"DB: {args.db}", file=sys.stderr)

    # ── Step 1: Sync ──────────────────────────────────────────────────────
    if args.sync:
        _run(
            ["rebalance", "github-sync-artifacts",
             "--repo", args.repo,
             "--days", str(args.days),
             "--database", str(args.db)],
            label=f"Syncing GitHub artifacts ({args.days}d lookback)",
        )

        if not args.no_sleuth:
            result = _run_quiet(
                ["rebalance", "sleuth-sync",
                 "--database-path", str(args.db)],
                label="Sleuth sync",
            )
            if result.returncode != 0:
                print("  ⚠ Sleuth sync skipped (credentials not configured)",
                      file=sys.stderr)
    else:
        if not args.db.exists():
            print(f"✗ No database at {args.db}. Run with --sync first.",
                  file=sys.stderr)
            return 1
        print("  (using existing DB data — add --sync for fresh data)",
              file=sys.stderr)

    # ── Step 2: Run triage ────────────────────────────────────────────────
    spike_cmd = [
        sys.executable, str(SPIKE),
        "--repo", args.repo,
        "--db", str(args.db),
        "--ambiguity", args.ambiguity,
        "--duplicate-threshold", str(args.duplicate_threshold),
    ]
    if args.decisions:
        spike_cmd.extend(["--decisions", str(args.decisions)])
    if args.publish and not args.dry_run:
        spike_cmd.append("--post-issue")
    if args.publish and args.dry_run:
        spike_cmd.extend(["--post-issue", "--dry-run"])
    if args.title:
        spike_cmd.extend(["--issue-title", args.title])

    _run(spike_cmd, label="Running triage analysis")

    # ── Done ──────────────────────────────────────────────────────────────
    if args.publish and not args.dry_run:
        print("\n✓ Triage published to GitHub.", file=sys.stderr)
    elif args.publish and args.dry_run:
        print("\n✓ Dry run complete (nothing posted).", file=sys.stderr)
    else:
        print("\n✓ Triage complete. Add --publish to post as a GitHub issue.",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

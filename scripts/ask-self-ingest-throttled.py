#!/usr/bin/env python3
"""Throttled wrapper around ask-self ingest to stay under Gemini per-minute limits.

The upstream ask_self_ingest module exposes only a `--concurrency` knob, which
controls in-flight parallelism but not requests-per-minute. This wrapper
monkey-patches `embed_one` with a token-bucket-style rate limiter so the actual
request rate is bounded regardless of concurrency, then hands off to the
unmodified ingest pipeline.

Usage:
    scripts/ask-self-ingest-throttled.py [--rpm 60] [-- <ask_self_ingest args>]
    ASK_SELF_RPM=30 scripts/ask-self-ingest-throttled.py

Required env (from temp/ask-self-rag.env or shell):
    GOOGLE_API_KEY     Gemini API key
    SLEUTH_RAG_GITHUB_PAT or GITHUB_TOKEN     for PR ingestion (optional)
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ASK_SELF_PATH = Path(os.environ.get("ASK_SELF_PATH", "/Users/noelsaw/Documents/GH Repos/ask-self"))
HARNESS_CONFIG = REPO_ROOT / "ask_self" / "ask_self_harness.json"
ENV_FILE = REPO_ROOT / "temp" / "ask-self-rag.env"


def _load_env_file(path: Path) -> None:
    """Load KEY=VALUE pairs from a .env file into the process env (shell wins)."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _install_rpm_limiter(rpm: int) -> None:
    """Monkey-patch ask_self_ingest.embed_one to enforce a global RPM cap."""
    import ask_self_ingest  # noqa: WPS433  (intentional after sys.path tweak)

    if rpm <= 0:
        print(f"[throttle] ASK_SELF_RPM={rpm} → no throttle", file=sys.stderr)
        return

    min_interval = 60.0 / rpm
    lock = threading.Lock()
    last_call = [0.0]
    counter = [0]
    original = ask_self_ingest.embed_one

    def throttled_embed_one(*args, **kwargs):  # type: ignore[no-untyped-def]
        with lock:
            now = time.monotonic()
            wait = (last_call[0] + min_interval) - now
            if wait > 0:
                time.sleep(wait)
            last_call[0] = time.monotonic()
            counter[0] += 1
            n = counter[0]
        if n % 25 == 0:
            print(f"[throttle] {n} embeddings sent (cap {rpm}/min)", file=sys.stderr)
        return original(*args, **kwargs)

    ask_self_ingest.embed_one = throttled_embed_one
    print(f"[throttle] cap = {rpm} RPM (min interval {min_interval:.2f}s between requests)",
          file=sys.stderr)


def main() -> int:
    p = argparse.ArgumentParser(
        description="Throttled wrapper for ask-self ingest",
        epilog="Args after `--` are passed through to ask_self_ingest.main()",
    )
    p.add_argument(
        "--rpm",
        type=int,
        default=int(os.environ.get("ASK_SELF_RPM", "60")),
        help="Embedding requests per minute cap (default 60, env: ASK_SELF_RPM)",
    )
    p.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="In-flight parallel embed workers (default 4; the RPM cap is the real ceiling)",
    )
    args, passthrough = p.parse_known_args()

    _load_env_file(ENV_FILE)
    if not os.environ.get("GOOGLE_API_KEY"):
        print(f"ERROR: GOOGLE_API_KEY not set (looked in shell + {ENV_FILE})", file=sys.stderr)
        return 2

    if not ASK_SELF_PATH.is_dir():
        print(f"ERROR: ask-self repo not found at {ASK_SELF_PATH}", file=sys.stderr)
        return 2
    sys.path.insert(0, str(ASK_SELF_PATH))

    _install_rpm_limiter(args.rpm)

    import ask_self_ingest

    forwarded = [
        "--repo-root", str(REPO_ROOT),
        "--harness-config", str(HARNESS_CONFIG),
        "--concurrency", str(args.concurrency),
    ] + [a for a in passthrough if a != "--"]

    print(f"[ingest] forwarding to ask_self_ingest.main with: {' '.join(forwarded)}",
          file=sys.stderr)
    return ask_self_ingest.main(forwarded)


if __name__ == "__main__":
    raise SystemExit(main())

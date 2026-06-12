#!/usr/bin/env python3
"""Phase-0 eval harness for chat_with_data — recall@k + latency.

Measures whether a correct source shows up in the top-k citations for a fixed
set of real questions, and how long it takes. Run two ways to compare:

  work-only:   .venv/bin/python scripts/chat_eval.py --scope work
  federated:   ASK_SELF_PATH="/path/to/ask-self" .venv/bin/python scripts/chat_eval.py --scope all

See PROJECT/2-WORKING/CHAT-WITH-DATA.md (Phase 0).
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

import _bootstrap  # noqa: E402, F401  — puts src/ on sys.path

from rebalance.chat import ask_self_available, chat_with_data  # noqa: E402
from rebalance.paths import resolve_database_path  # noqa: E402

# (question, expected-source substrings). A question counts as recalled if any
# expected substring appears in a top-k citation's path or title.
QUESTIONS: list[tuple[str, list[str]]] = [
    ("which module logs auth failures", ["auth_log"]),
    ("how does refresh flow into the semantic index", ["index_ops", "semantic_index", "architecture"]),
    ("where is the pulse dashboard html generated", ["pulse_web"]),
    ("what code serves the authorization log web page", ["web.py", "pulse_server"]),
    ("how are sleuth reminders ingested", ["sleuth_reminders"]),
    ("where is the gmail oauth token loaded", ["gmail"]),
    ("what computes the collector health verdict", ["health"]),
    ("how does doctor check the collectors", ["doctor"]),
    ("what is the keyring credential model", ["config", "upgrade"]),
    ("how is the calendar oauth token stored", ["calendar", "config"]),
]


def _recalled(cites: list[dict], expect: list[str]) -> bool:
    blob = " ".join(
        ((c.get("path") or "") + " " + (c.get("title") or "")).lower() for c in cites
    )
    return any(e.lower() in blob for e in expect)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", default="work", choices=["work", "code", "all"])
    ap.add_argument("--top-k", type=int, default=8)
    args = ap.parse_args()

    db = resolve_database_path()
    print(f"scope={args.scope}  top_k={args.top_k}  ask_self_available={ask_self_available()}\n")
    print(f"| # | question | hit | ms | used | top source |")
    print(f"|---|---|:--:|--:|---|---|")

    hits = 0
    latencies: list[int] = []
    used_union: set[str] = set()
    for i, (q, exp) in enumerate(QUESTIONS, 1):
        r = chat_with_data(db, q, scope=args.scope, top_k=args.top_k)
        cites = r["citations"]
        ok = _recalled(cites, exp)
        hits += int(ok)
        latencies.append(r["elapsed_ms"])
        used_union.update(r["used_sources"])
        top = (cites[0].get("path") or cites[0].get("title") or "—")[:38] if cites else "—"
        print(f"| {i} | {q[:44]} | {'✅' if ok else '❌'} | {r['elapsed_ms']} | {','.join(r['used_sources']) or '—'} | {top} |")

    med = int(statistics.median(latencies))
    p95 = int(statistics.quantiles(latencies, n=100)[94]) if len(latencies) >= 100 else int(max(latencies))
    print(f"\n**recall@{args.top_k} = {hits}/{len(QUESTIONS)}**  ·  latency median={med}ms p95≈{p95}ms  ·  used={','.join(sorted(used_union)) or '—'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

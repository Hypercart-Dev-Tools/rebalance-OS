# Marathon Phase hiqs-m3-p1
STATUS: Approved
NEXT: codex

<!-- marathon-drive: task=MARATHON-HIQS-M3-P1-TURN builder=codex reviewer=agy round-cap=7 -->

## Phase Brief

---
title: "M3 p1 — github.py: activity scan and item sync"
status: "Brief authored; phase not yet run"
created: 2026-08-03
updated: 2026-08-03
owner: noel
gh_issue: TBA
roadmap_exempt: true
doc_type: project
goal: >
  Marathon phase brief (harness input, not a tracked effort). Builds one module of the HiQS
  v1.0 core against the contract in PROJECT/2-WORKING/HIQS-PROJECT.md, which stays canonical.
---
# M3 p1 — github.py: activity scan + item sync

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-08-03 and preflighted — `marathon.sh --dry-run` resolves this phase in execution order. **Not yet run.** | Runs after **operator checkpoint A** (the Phase 1 eval). Fire M3 with `--builder codex`. |

**Canonical spec:** `HIQS-PROJECT.md` §5 (rules 2/3/5/7/8), §9 (`github_items` columns), §11
(~250 LOC, stdlib `urllib`), L18, L19, L20, L4.

## Build

`HiQS/hiqs/sources/github.py` — `fetch` using **stdlib `urllib`** (§11: no `requests`), writing
`github_activity` and `github_items`. Pattern: window refetch + upsert (§5 rule 2, pattern 2).

Project **both** timestamps, which §9 separates deliberately:
- `updated_at` — the source's own field. The correct **sync watermark**.
- `activity_at` — the last event that actually *happened* (commit, comment, review, state change).
  **The only one the ranker may read.** L20: `updated_at` is bumped by label and assignee edits
  that indicate no real movement.

Also project `author` and `assignee`.

## Acceptance

- Two consecutive runs over an unchanged window: zero inserts, zero updates. Never auto-delete
  across units (§5 rule 2).
- **Explicit timeout on every network call** (rule 7, L18). A test asserts no `urlopen` without one
  — a stalled request must fail its own source, not hold the SQLite writer while every other job
  piles up behind it.
- **Watermark on success only** (rule 8, L19): simulate a mid-window failure and assert the
  watermark does not advance, the error lands in `events` + `SyncReport.errors`, and the walk
  continues (rule 5). The next run re-covers the window, which upsert-only makes free.
- **Quality, not count (L4):** rows that cannot attest are *rejected* at the write boundary and
  counted as rejected. A run storing 100 contentless shells must not report healthy. This is the
  incumbent's three-week email starvation, and it is the reason this bullet exists.
- `api_calls` and `peak_rss_mb` in `SyncReport.meta`; the Phase 2 gate's ceilings are **<=100 calls
  and <=500 MB** per refresh, breach is a `warn` naming the figure.
- Token resolves only through `config.secret()`; no token, path, or username hardcoded, and none in
  any event payload.
- Network fully stubbed in tests.

## Do not

- Do not use `requests` or any HTTP library outside stdlib.
- Do not let the ranker-facing timestamp be `updated_at`. That single substitution violates L20 on
  day one and is invisible until the ranking is quietly wrong.


---

▶ TAKE YOUR TURN (codex — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): HiQS/hiqs/sources/github.py,HiQS/tests/test_github.py,HiQS/pyproject.toml
2. Append a build block to this relay file: `### Round N · Builder · codex` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick claim MARATHON-HIQS-M3-P1-TURN --agent codex --paths "phases/hiqs-m3-github--hiqs-m3-p1/RELAY.md,HiQS/hiqs/sources/github.py,HiQS/tests/test_github.py,HiQS/pyproject.toml"
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick ping MARATHON-HIQS-M3-P1-TURN --agent codex
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M3-P1-TURN --agent codex --to agy
4. Edit ONLY these paths: phases/hiqs-m3-github--hiqs-m3-p1/RELAY.md and HiQS/hiqs/sources/github.py,HiQS/tests/test_github.py,HiQS/pyproject.toml. Do NOT run git. Do NOT touch any other file — the harness commits for you.
5. HAND OFF EXPLICITLY (GH-268): after releasing the token, end your turn by naming who acts next —
   "handing off to agy — agy, take your turn." A turn that ends without that line
   leaves a human guessing whether the relay is waiting on them or has stalled. Do this EVERY round,
   not just the first.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: HiQS/hiqs/sources/github.py,HiQS/tests/test_github.py,HiQS/pyproject.toml. REVIEW THE WHOLE FILE, NOT JUST THE DIFF (GH-268): a beta test had this loop reach 'Approved' in two rounds while an independent audit of the same branch found 20 issues (1 critical, 4 high) — every one of them in the pre-existing code the change sat on, which nobody had read. Pre-existing defects in a file you are touching are IN SCOPE; say so explicitly if you find none. DECLARE IT: your review block MUST contain a literal 'swept file: yes' or 'swept file: no' line — without it a reviewer that skipped the sweep is indistinguishable in the transcript from one that did it and found nothing, which is exactly how those 20 issues stayed invisible.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M3-P1-TURN --agent agy --to codex
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick done MARATHON-HIQS-M3-P1-TURN --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/hiqs-m3-github--hiqs-m3-p1/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
5. HAND OFF EXPLICITLY (GH-268): end your turn by naming who acts next — "handing off to codex —
   codex, take your turn" when requesting changes, or "relay closed, no further turn needed" when
   approving. The beta report singled this out: the Reviewer turn did not tell the user to go back to the
   Producer, so the relay looked stalled when it was simply waiting. Do this EVERY round.

### Round 1 · Builder · codex

Implemented the GitHub source and its entry point. `github.py` uses only stdlib `urllib` with an explicit timeout on every request; it window-refetches user activity and repo issues/events, upserts without deletion, rejects unattestable shells, and distinguishes source `updated_at` from event-derived `activity_at`. The global mutable watermark moves only after an error-free run, while failures are logged through the core event seam and do not stop later repos. Reports include `api_calls` and platform-safe `peak_rss_mb`, with a budget-breach warning.

Added focused network-stubbed tests for idempotence, label-only metadata changes, rejected shells, timeout coverage, and a mid-walk failure that preserves the watermark while continuing. Verified with `pytest tests/test_github.py -q` (3 passed).

### Round 1 · Reviewer · agy

**Verdict:** Approved

swept file: yes
Fully swept `HiQS/hiqs/sources/github.py`, `HiQS/tests/test_github.py`, and `HiQS/pyproject.toml`. No pre-existing or new defects found.

Key findings:
1. `github.py` adheres strictly to stdlib `urllib` and enforces `NETWORK_TIMEOUT_SECONDS = 15` on all network requests.
2. Watermarking accurately uses `updated_at` while `activity_at` isolates real movement (comments, state changes, commits) from metadata-only updates. Watermark advances only when the sync run is error-free.
3. Contentless item shells are properly rejected and tracked in `counts["rejected"]`.
4. Observability and resource limits (`api_calls` and `peak_rss_mb`) are logged and checked against Phase 2 ceilings.
5. `pyproject.toml` correctly registers the `github` entry point under `[project.entry-points."hiqs.sources"]`.
6. Verified with `python3 -m pytest HiQS/tests/test_github.py -q` (3 passed).

relay closed, no further turn needed

# Marathon Phase coll-p2-144-fanout
STATUS: Open
NEXT: codex

<!-- marathon-drive: task=MARATHON-COLL-P2-144-FANOUT-TURN builder=codex reviewer=agy round-cap=5 -->

## Phase Brief

# Phase 2 — request attribution, then reduce the per-PR fan-out

Part of **GH-144**. Issue: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/144
Wave 1, runs concurrently with p1 and p3. **Artifact: `src/rebalance/ingest/_http.py`.**

## The problem (measured, by Codex under #140)

One `github-sync` run costs **~2,292 requests**, against a 5,000/hr PAT ceiling, at 18
scheduled runs/day:

| Component | Requests |
|---|---|
| 60 repos × 7 (metadata, branches, labels, milestones, releases, issues, pulls) | 420 |
| 423 issues × 1 (issue-comments list) | 423 |
| **241 PRs × 6** (detail, issue comments, reviews, review comments, commits, check-runs) | **1,446** |
| discovery (`/user`, pushed repos, 1–3 event pages) | 3–5 |

The per-PR fan-out is **63% of the run** and grows unbounded with PR count. 2,292 is a
*floor* — every paginator runs until a short page.

## ⛔ Hard invariants

- **Measure before optimizing.** Ship step 1 (attribution) and read its output before changing
  any fetch behavior. An unmeasured optimization is an unverifiable claim — Principle 9.
- **No data regression.** The goal is fewer requests for the *same collected data*. If a
  sub-resource is dropped, prove nothing downstream reads it; do not assume.
- **Record the reset epoch with every header sample.** Start/end `x-ratelimit-used` is NOT a
  valid per-job delta when a run crosses an hourly reset (the observed one did) or when
  another device shares the PAT. Codex flagged this explicitly.
- **Do not touch `_get_login()`'s 403 handling** — it was just fixed in `5fc670d` and its
  logging is the instrument that will classify tomorrow's `daily-sync` failure.
- **Off-box spend is out of scope.** The PAT is shared across ≥3 machines (#138) and rate-limit
  headers cannot distinguish clients. Proving it needs a per-device PAT. Do not attempt it here.
- **Do not change the retry/backoff logic** in `_retry_after_seconds()` / `_is_rate_limit()`.
  It is correct and load-bearing.

## Task

### Step 1 — attribution at the chokepoint (do this first)

`GitHubClient._request()` (`_http.py:137`) is the single point **every** GitHub call in the
codebase passes through. Add a run-id/job label and a local counter; emit endpoint-path
counts, attempt counts, and rate-limit headers at job completion.

This must capture paginated calls and retries, which per-call-site instrumentation would miss.

### Step 2 — reduce the per-PR fan-out

Only after step 1 gives a before number. Options to weigh — none is pre-decided:

- Fetch only sub-resources actually consumed downstream. Some of the six may be collected and
  never read; the attribution data from step 1 plus a read-path grep will show which.
- Condition expensive calls on PR recency or state instead of fetching all six for every PR
  every run.
- Consider GraphQL for the PR detail bundle — it can collapse several REST calls into one.

State the reasoning for whichever path you take in the relay. A 63% cost centre deserves an
argued choice, not a silent one.

### Not in this phase

Cadence (18 runs/day) and the dashboard's `PULSE_AUTO_MIN=10` full refresh are **operator
decisions**, not code changes. Surface a recommendation with numbers; do not change schedules.

## Watch for

- `_get()` in `github_scan.py:108` constructs a **new client per call** — its own docstring
  says *"new code should use a long-lived GitHubClient instead."* That defeats connection
  reuse and would fragment any per-client counter state. Decide deliberately whether the
  counter lives on the instance or in a module-level/run-scoped registry, and say why.
- The 15 pre-existing full-suite failures are unrelated debt. Do not attempt to fix them.

## Acceptance

- [ ] Per-job request counts are measurable on-box, broken down by endpoint path.
- [ ] Each header sample records the reset epoch alongside `x-ratelimit-used`.
- [ ] A **before/after request count** for one `github-sync` run demonstrates the reduction.
- [ ] Nothing `github-sync` collected before is missing after — stated explicitly, with the
      read-path evidence for any sub-resource dropped.
- [ ] Retry/backoff behavior unchanged; `_get_login()` untouched.
- [ ] Gate: `.venv/bin/python -m pytest tests/ -k "github_scan or github_client or http" -q`
      green (27 tests at time of writing).
- [ ] A recommendation on cadence + `PULSE_AUTO_MIN`, with numbers, left for the operator.

---

▶ TAKE YOUR TURN (codex — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): src/rebalance/ingest/_http.py
2. Append a build block to this relay file: `### Round N · Builder · codex` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick claim MARATHON-COLL-P2-144-FANOUT-TURN --agent codex --paths "phases/marathon-2026-07-18-collectors--coll-p2-144-fanout/RELAY.md,src/rebalance/ingest/_http.py"
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick ping MARATHON-COLL-P2-144-FANOUT-TURN --agent codex
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-COLL-P2-144-FANOUT-TURN --agent codex --to agy
4. Edit ONLY these paths: phases/marathon-2026-07-18-collectors--coll-p2-144-fanout/RELAY.md and src/rebalance/ingest/_http.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: src/rebalance/ingest/_http.py.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-COLL-P2-144-FANOUT-TURN --agent agy --to codex
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick done MARATHON-COLL-P2-144-FANOUT-TURN --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/marathon-2026-07-18-collectors--coll-p2-144-fanout/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.

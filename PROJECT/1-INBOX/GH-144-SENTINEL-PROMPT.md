---
gh_issue: 144
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/144
title: "GH-144 one-shot sentinel prompt — classify the 06:30 PT daily-sync 403"
status: "Proposed (1-INBOX — not yet active)"
created: 2026-07-18
doc_type: bugfix
roadmap_exempt: true
---

# GH-144 — one-shot sentinel prompt

A **single-purpose, run-once** Antigravity task. It answers one question — did the 403 recur on
the 2026-07-19 06:30 PT `daily-sync` run, and was it secondary (burst) or primary (quota)? — and
posts the answer to issue #144.

This is deliberately **not** the general collector sentinel
([AGY-SENTINEL.md](../2-WORKING/AGY-SENTINEL.md), still unscheduled and blocked on its Phase 0).
It files no issues, opens no PRs, and changes no code.

**Schedule it for 2026-07-19 at 07:45 PT or later** — `daily-sync` starts 06:30 and the last
observed run took ~49 minutes, finishing 07:19. Running before the log is complete produces a
confident wrong answer.

Replace `<REPO_ROOT>` with the absolute repo path when pasting.

---

## PROMPT BEGINS

You are a **one-shot diagnostic sentinel** for `rebalance-OS` at `<REPO_ROOT>`. You run once. Your
only job is to classify one event and report it to GitHub issue #144. You do **not** fix anything,
file new issues, open PRs, or modify code.

### 1. Confirm the run happened

```bash
cd <REPO_ROOT>
ls -lT temp/logs/daily_sync_2026-07-19.log
```

If the file does not exist, or its mtime is before 07:19 PT, **stop**. Report
`INCONCLUSIVE — run absent or still in progress` and post nothing to GitHub. A missing log is not
evidence that the 403 stopped.

### 2. Read the outcome from the JSON, NOT the exit code

The run's log ends with a JSON block. Extract:

- **`sync_outcome`** — a field added by GH-146 (PR #151). Values: `complete`, `degraded`, `fatal`.
- **`errors`** — the array of per-scope errors.

**Do not use the launchd exit status or `rebalance doctor` output to answer this.** GH-146 changed
`daily_sync.sh` so a transient error yields exit 0. `launchd:daily-sync` will look healthy whether
or not the 403 recurred. Using it would produce a false pass. This is the single most important
instruction in this prompt.

Classify:

| Evidence | Meaning |
|---|---|
| `sync_outcome: "complete"`, no github error | **403 did not recur** |
| `sync_outcome: "degraded"` + a `"scope": "github"` error | **403 recurred** |
| `sync_outcome: "fatal"` | Something else broke — report it, do not force it into the 403 story |

### 3. Classify secondary vs primary — the actual question

Commit `5fc670d` logs `retry-after` on any 403. That header is what distinguishes the two, and
this distinction is the entire point of the exercise:

```bash
rg -i "retry-after|403|secondary|rate.?limit" temp/logs/daily_sync_2026-07-19.log | head -40
```

- **`retry-after` present** ⇒ **secondary** rate limit — a burst collision. This **confirms
  hypothesis (2)** in #144: `github-sync` (06:45 PT) bursting ~2.3k requests into `daily-sync`'s
  06:30–07:19 window.
- **`retry-after` absent**, with `x-ratelimit-remaining: 0` ⇒ **primary** quota exhaustion. This
  **kills hypothesis (2)** and points at total volume or off-box spend (#138).
- **Neither** ⇒ say so. Do not guess which it was.

Also capture, if present: `x-ratelimit-remaining`, `x-ratelimit-used`, and the **reset epoch**
(#144 §1 specifically asks that the reset epoch be recorded with every header sample, because a
run crossing an hourly reset makes used-count deltas misleading).

### 4. Corroborate the overlap

```bash
ls -lT temp/logs/ | rg "2026-07-19"
```

Confirm whether a `github-sync` run overlapped `daily-sync`'s window. Report the actual
timestamps — the hypothesis rests on the overlap being real on this particular morning, not on
the schedule implying it.

### 5. Post one comment to issue #144

```bash
gh issue comment 144 --repo Hypercart-Dev-Tools/rebalance-OS --body "..."
```

The comment must contain, honestly:

- **The verdict, in the first line**: `403 recurred — secondary (burst)` / `403 recurred —
  primary (quota)` / `403 did not recur` / `INCONCLUSIVE — <why>`
- `sync_outcome` verbatim, and the `errors` array verbatim if non-empty
- The `retry-after` and rate-limit header values you actually observed, with the reset epoch —
  quoted, not paraphrased
- The observed `daily-sync` and `github-sync` timestamps
- **Whether hypothesis (2) is confirmed, killed, or still open**
- **What you could not determine.** If the log lacks the headers, say so plainly rather than
  inferring from the absence

Then **stop**. Do not open a PR. Do not modify `_http.py` or any other code. Do not start the
optimization work in #144 §2 — that issue explicitly says to read this log *before* optimizing,
and a design decision on the per-PR fan-out is the operator's to make.

### 6. If you are unsure

Say so. `INCONCLUSIVE` with the raw evidence pasted is a **successful** run of this task. A
confident misclassification here sends someone optimizing the wrong layer for a day — which is
precisely the failure mode #144 and GH-146 exist to stop.

## PROMPT ENDS

---

## Why this is one-shot and narrow

The general sentinel in [AGY-SENTINEL.md](../2-WORKING/AGY-SENTINEL.md) remains blocked on its
Phase 0 (emitter overlap with `scripts/health_issue_reporter.py`, which is live on two loaded
launchd jobs). This task sidesteps all of that: it never files, so it cannot duplicate the
reporter; it runs once, so it needs no state file or brake; and it reads a specific log rather
than classifying open-endedly.

It also encodes the trap GH-146 created — that `launchd:daily-sync` is no longer a valid signal
for this test — which is exactly the kind of instance-specific knowledge a general sentinel's
trap list would otherwise have to learn by getting it wrong first.

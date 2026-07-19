---
gh_issue: 169
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/169
title: Commit history coverage — backfill direct + merge commits, and stop the collector evicting its own work
status: "Active (2-WORKING)"
owner: Noel
created: 2026-07-19
updated: 2026-07-19
doc_type: project
branch: worktree-temp-cognee-litmus-test
goal: >
  Make git commit history a complete, self-healing signal source. Close the measured 182-commit
  (19.4%) gap on `development` — including the CLIO import commit `cfeafe4` — by enumerating
  history from the local clone rather than the Events API, and repair the attempt-accounting
  defect that is currently evicting 20 push events that never actually failed. Completeness must
  become a property the system can prove and re-derive, not a side effect of a 300-event API window.
related:
  - PROJECT/1-INBOX/GH-155-DIRECT-COMMIT-SIGNALS.md
  - PROJECT/2-WORKING/GH-146-HEALTH-SIGNAL-ACCURACY.md
  - PROJECT/2-WORKING/SIGNAL-HEALTH-NUANCE.md
  - PROJECT/1-INBOX/GH-156-CRITICAL-CLIO-PROJECTION-RECONCILIATION.md
non_goals:
  - Ingesting archived third-party repos (deferred from the original #169 framing — the destination
    repo's own commit already carries the provenance).
  - Changing the embedding model or re-embedding the existing corpus.
  - Re-architecting the Events-API path from #157; it stays as an accelerator.
effort: 3
complexity: 3
risk: 2
phases: 4
---

# GH-169 — Commit history coverage

## Status

| What was just completed | What's next |
|---|---|
| RCA complete. Four compounding causes identified and each one confirmed against live data, not inferred: 300-event API ceiling, actor-scoped discovery, per-run caps starving the queue, and an attempt-accounting defect that has already permanently evicted 20 push events which never failed. Gap measured at **182 of 938 commits (19.4%)** on `development` since 2026-05-01. | Phase 1 — build the local-git backfill, verify `cfeafe4` becomes queryable and the gap goes to 0. Doc is out for an agy relay review before code is written. |

## Table of contents

- [Why this exists](#why-this-exists)
- [Root cause analysis](#root-cause-analysis)
- [Phase 1 — Local-git commit backfill](#phase-1--local-git-commit-backfill)
- [Phase 2 — Repair attempt accounting](#phase-2--repair-attempt-accounting)
- [Phase 3 — Completeness as a measurable property](#phase-3--completeness-as-a-measurable-property)
- [Phase 4 — Verification against the original symptom](#phase-4--verification-against-the-original-symptom)
- [Anti-goals](#anti-goals)

## Why this exists

The operator could not answer "where does CLIO live, and where did it come from?" from the HiQS
signal, and resorted to manual digging. The answer existed the whole time, in one commit:

```
cfeafe4f564cf8f8fa5b161bad80642ae8752d16   2026-07-17T20:06:18-07:00

feat: bring CLIO into rebalance-OS as its canonical home

Pull the latest CLIO skill (append+cursor exporter for cross-device
accumulation, atomic same-fs writes, shrink-cursor recovery) from
Claude-AI-Tools-Ventura-County/CLIO-Claude-Prompts@ef96a44, plus
README/LICENSE, into utils/CLIO/.
```

That single document names the origin repo, the exact upstream SHA, the destination path, and the
intent. It was never indexed. This is the third consecutive issue in this area (#155 → #157 → #169),
which is the "one more thing" pattern this doc is explicitly chartered to end — hence Phase 3, which
exists so the *next* gap is detected by the system rather than by an operator noticing a bad answer.

## Root cause analysis

Why a gap persists **after** #157 shipped. All four verified against the live DB on 2026-07-19.

### RC1 — Discovery is capped at 300 events / ~90 days

`capture_direct_commits()` never enumerates git history. It only filters a list of `events` handed in
from `github_scan` (`src/rebalance/ingest/github_direct_commits.py:82`, `:99`). GitHub's user-events
endpoint returns at most 300 events and retains roughly 90 days. The 2026-07-19 refresh reported
`events: 300` — the ceiling, exactly. Anything older is undiscoverable by construction, and no amount
of re-running helps. `cfeafe4` is outside that window.

### RC2 — Discovery is actor-scoped

The scan reads the authenticated user's event feed (`login: noelsaw1`). Commits pushed under a
different account, a different device identity, or by CI never enter the candidate set at all.

### RC3 — Per-run caps starve the queue

`MAX_PUSH_COMPARES_PER_REFRESH = 5` and `MAX_COMMIT_DETAILS_PER_REFRESH = 20`
(`github_direct_commits.py:17-18`). The observed refresh enriched 5 events and deferred 20. There are
**137 push events still pending at attempt 0** with a drain rate of ~5 per run.

### RC4 — Cap-deferrals burn retry attempts (the actual data-loss defect)

`update_push_event()` in `src/rebalance/ingest/db/github.py` increments unconditionally:

```sql
SET state = ?, attempt_count = attempt_count + 1, ...
```

while `pending_push_events()` selects only `WHERE state IN ('pending','deferred') AND attempt_count < ?`
against `MAX_EVENT_ATTEMPTS = 3`.

A deferral for `"compare cap reached"` (`github_direct_commits.py:161`, and `:139`) is **not a
failure** — it means the run exhausted its own budget before reaching this event. It costs an attempt
anyway. Lose that lottery three times and the event is permanently excluded from the pending query.
It will never be fetched, and nothing reports it as lost.

Live state confirming this:

| state | attempt_count | n | dominant reason |
|---|---|---|---|
| deferred | 1 | 5 | compare cap reached |
| deferred | 2 | 5 | compare cap reached |
| **deferred** | **3** | **21** | **compare cap reached (20 of 21)** |
| enriched | 1–3 | 29 | — |
| pending | 0 | 137 | — |

**20 push events have been permanently dropped without a single real failure.**

The module docstring states: *"A transient failure remains a durable deferred receipt, so no work is
silently treated as absent."* The implementation does not honour that guarantee. Worse, the
`events_deferred` counter reports these as ordinary deferrals, so the refresh output looks healthy
while data is being discarded — the same class of defect as GH-146, where a working system reported
as broken; here a lossy system reports as working.

### Why the two fixes are different

RC1/RC2 are **coverage** problems — the collector cannot see far enough back, or wide enough.
RC3/RC4 are **durability** problems — of what it does see, it discards some. Backfill alone would
close today's gap and let it regrow. The attempt fix alone would not recover `cfeafe4`, which is
outside the event window entirely. Both are required, which is why this doc has both.

## Phase 1 — Local-git commit backfill

**Decision (operator, 2026-07-19):** read from the **local clone**, not the API. Every one of the 182
missing SHAs is already on disk. This costs zero API calls, is not rate-limited, and therefore does
not reproduce the pressure that motivated the caps in RC3 — which is precisely what makes a
full-history backfill affordable instead of a 90-day compromise.

- [ ] Add `backfill_commits(database_path, repo, *, since, cap)` in a new
      `src/rebalance/ingest/github_commit_backfill.py`.
- [ ] Enumerate via `git log` on the resolved default branch: SHA, author, author-email, authored
      date, full message, and changed paths (`--name-only`).
- [ ] Dedupe against **both** `github_commits` (PR commits) and `github_direct_commits` before
      insert; key on `(repo_full_name, sha)`.
- [ ] Capture **merge commits explicitly** — they are missed by both existing paths and are the
      "when did X land on development" record.
- [ ] Persist into `github_direct_commits` / `github_direct_commit_files` with a new
      `path_coverage` value distinguishing git-sourced rows from API-sourced ones.
- [ ] Project through the existing `sync_direct_commit_documents()` so no retrieval-side change is
      needed.
- [ ] Resolve the clone path from existing config rather than a new hardcoded constant; skip cleanly
      with a logged reason when no clone is present.

### QA gate — Phase 1

- [ ] Backfilling `development` since 2026-05-01 reduces the measured 182-commit gap to **0**.
- [ ] `cfeafe4` is present in `github_direct_commits` with its full message and all 3 `utils/CLIO/` paths.
- [ ] Merge commits are captured and do **not** duplicate their PR-commit counterparts.
- [ ] Re-running the backfill is a no-op (0 inserted, 0 updated) — idempotency proven, not assumed.
- [ ] Zero GitHub API calls made by this path, asserted in test.
- [ ] Runs cleanly against a repo with no local clone (skips, logs, does not raise).
- [ ] `rebalance doctor` clean.

## Phase 2 — Repair attempt accounting

- [ ] Separate **budget exhaustion** from **attempt failure**. A cap-deferral must not increment
      `attempt_count`; introduce a distinct state (e.g. `queued`) or an explicit
      `increment_attempt: bool` on `update_push_event()`.
- [ ] Recover the 21 currently-stuck events: reset those whose `failure_reason` indicates a cap
      deferral rather than a genuine fetch failure.
- [ ] Distinguish the two in `DirectCommitCaptureResult` — `events_deferred` must not conflate
      "over budget" with "failed", since that conflation is what made this invisible.
- [ ] Make the module docstring's durability claim true, or amend the docstring. It currently
      asserts a guarantee the code does not provide.

### QA gate — Phase 2

- [ ] A regression test proves an event deferred purely by cap is still eligible after 3+ runs.
- [ ] The 21 stuck events return to eligibility; the 20 cap-only ones enrich on subsequent runs.
- [ ] Genuine failures (non-retryable HTTP) still exhaust attempts and stop retrying — the fix must
      not turn real failures into an infinite retry loop.
- [ ] Refresh output reports over-budget and failed counts separately.

## Phase 3 — Completeness as a measurable property

This phase is why the doc exists in the form it does. #155 and #157 each fixed a real thing and each
left a gap that only surfaced when an operator asked a question and got a bad answer. Completeness
must be continuously derivable.

- [ ] Add a coverage check comparing local `git log` SHAs against captured SHAs, reporting the
      absolute gap per repo.
- [ ] Surface it in `index_status` freshness (alongside `github_documents_missing_from_semantic`)
      and in `rebalance doctor`.
- [ ] Degrade health status when the gap exceeds a defined threshold.

### QA gate — Phase 3

- [ ] With commits deliberately withheld, the check reports the correct non-zero gap.
- [ ] After backfill, it reports 0 and health is `ok`.
- [ ] The check is cheap enough to run on every `doctor` invocation (local git only, no API).
- [ ] Consistent with the #167 precedent for reporting corpus drift.

## Phase 4 — Verification against the original symptom

The plan is only done when the question that started it is answerable.

- [ ] Re-run `semantic_query("where does CLIO live and where did it come from")`.
- [ ] `cfeafe4` returns in the top results, carrying both the origin repo and `utils/CLIO/`.
- [ ] Spot-check 3 further missing commits from the measured 182 for correct message and paths.
- [ ] Record the before/after retrieval comparison in this doc (per PDDA: discovery findings are
      written back here before the gate passes).

### QA gate — Phase 4

- [ ] The originating operator question is answered from the signal alone, with no manual digging.
- [ ] Full suite: zero regressions against the `development` baseline.
- [ ] `rebalance doctor` and `pdda` both clean.
- [ ] Findings written back into this doc.

## Anti-goals

- **Not** ingesting archived third-party repos. Deferred from the original #169 framing after the
  RCA showed the destination repo's own commit already carries the provenance — the origin repo did
  not need ingesting at all.
- **Not** removing the Events-API path. It stays as a low-latency accelerator; git history becomes
  the correctness backstop.
- **Not** raising the per-run caps as the fix. Caps are a legitimate rate-limit defence; the defect
  is that hitting one is accounted as a failure.
- **Not** a full re-embed of the corpus.

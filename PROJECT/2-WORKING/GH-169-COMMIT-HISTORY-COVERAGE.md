---
gh_issue: 169
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/169
title: Commit history coverage — backfill direct + merge commits, and stop the collector evicting its own work
status: "Active (2-WORKING)"
owner: Noel
created: 2026-07-19
updated: 2026-07-19
reviewed: 2026-07-19 (agy relay r2 — APPROVED, 5 Pass + 1 Nit applied; r1 was Changes requested, 5/5 dispositioned)
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
| RCA complete (5 causes, each verified against live data rather than inferred) and **agy relay review closed APPROVED at round 2** — r1 was *Changes requested* (2 Blockers + 3 Shoulds, all 5 accepted), r2 returned 5 `[Pass]` with citations + 1 `[Nit]`, now applied. The review earned three things the plan did not have: **RC5** (the projection step is itself lossy — `sync_direct_commit_documents()` destroys-then-rebuilds, so a partial failure shortens the corpus while every upstream measure still reads healthy); a fix for a **self-agreeing completeness check** in Phase 3 (local-git vs local-DB would have reported a confident `0` on a stale clone — it would have passed green through the entire #155→#157 sequence); and the r2 Nit that **presence of a row is not coverage** (a row with `path_coverage = 'unavailable'` would have scored as covered). Gap measured at **182 of 938 commits (19.4%)** on `development` since 2026-05-01. | **Plan approved — build Phase 1**: local-git backfill with pre-fetch, explicit `uncoverable` reporting, and the `unavailable → complete` conflict policy; verify `cfeafe4` becomes queryable and the gap reaches 0. |

## Table of contents

- [Why this exists](#why-this-exists)
- [Root cause analysis](#root-cause-analysis)
- [Phase 1 — Local-git commit backfill](#phase-1--local-git-commit-backfill)
- [Phase 2 — Repair attempt accounting](#phase-2--repair-attempt-accounting)
- [Phase 3 — Completeness as a measurable property](#phase-3--completeness-as-a-measurable-property)
- [Phase 4 — Verification against the original symptom](#phase-4--verification-against-the-original-symptom)
- [Phase ordering — why backfill still goes first](#phase-ordering--why-backfill-still-goes-first)
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

### RC5 — Downstream projection is itself a lossy step (added by agy review, 2026-07-19)

Two failure modes downstream of collection, both of which can void the work the collector did:

**Full-rebuild projection.** `sync_direct_commit_documents()` opens with

```sql
DELETE FROM github_documents WHERE doc_type = 'direct_commit'
```

then re-inserts every row (`github_direct_commits.py:230-269`). It is a destroy-then-rebuild inside
one transaction: an exception partway through the insert loop leaves the corpus short, and because
the collector's own tables still hold the rows, every upstream coverage measure still reports
healthy. Collection completeness does not imply corpus completeness — the two must be measured
separately.

**Rewritten history.** Force-pushes and squash-merges orphan SHAs: a commit captured under its
pre-rewrite SHA persists in `github_direct_commits` forever, while the SHA that actually exists on
the remote was never collected. This produces *both* a phantom (a row for a commit that no longer
exists) and a gap (the real commit, uncollected) — and a naive count-based coverage check can net
these against each other and report zero.

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

- [x] Add `backfill_commits(database_path, repo, *, since, cap)` in a new
      `src/rebalance/ingest/github_commit_backfill.py`.
- [x] Enumerate via `git log` on the resolved default branch: SHA, author, author-email, authored
      date, full message, and changed paths (`--name-only`).
- [x] Dedupe against **both** `github_commits` (PR commits) and `github_direct_commits` before
      insert; key on `(repo_full_name, sha)`.
- [x] Capture **merge commits explicitly** — they are missed by both existing paths and are the
      "when did X land on development" record.
- [x] Persist into `github_direct_commits` / `github_direct_commit_files` with a new
      `path_coverage` value distinguishing git-sourced rows from API-sourced ones.
- [x] Project through the existing `sync_direct_commit_documents()` so no retrieval-side change is
      needed.
- [x] Resolve the clone path from existing config rather than a new hardcoded constant.
- [x] **`git fetch` before enumerating** (agy Blocker). A stale clone silently under-reports; without
      a fetch the backfill would confidently close a gap it never actually measured.
- [x] **No-clone repos must report, not skip** (agy Blocker). A silent skip leaves the gap
      permanently open *and* invisible — the exact failure shape this whole issue is about. A watched
      repo with no local clone records an explicit `uncoverable` state carrying the reason, surfaced
      in Phase 3's check and in `doctor`. It is honest and loud rather than absent.
- [x] **Define the write-conflict policy explicitly** (agy Should, ordering). Backfill rows must
      survive later API-sourced enrichment: `ON CONFLICT(repo_full_name, sha)` upgrades
      `path_coverage` only in the direction `unavailable → complete`, never downgrading a
      git-sourced `complete` row. This is what makes Phase 1 → Phase 2 ordering safe (see below).

### Phase 1 findings (written back per PDDA)

Two things only running the code revealed:

**The default-branch assumption does not survive this repo.** `origin/HEAD` in the real clone points
at `main`, but the trunk is `development` — so the first implementation enumerated 515 commits of the
wrong branch and captured none of the measured gap. Walking `--remotes=origin` (all remote branches)
removes the assumption entirely and, as a bonus, closes the "commits on branches never merged to a
trunk" hole raised during review. Dedup is by `(repo, sha)`, so branch overlap costs nothing.
Regression test added.

**Tests in a worktree silently exercise the wrong code.** The editable install resolves `rebalance`
to `/Users/noelsaw/Documents/rebalance-OS/src` — the *main* checkout — so `pytest` in a worktree
imports code that is not the code under change, and passes. Every run here therefore pins
`PYTHONPATH=$PWD/src`. This affects any worktree/marathon work in this repo, not just GH-169, and is
worth a separate issue.

**Live result against a copy of the production DB** (`--since 2026-05-01`, no API calls):

| | |
|---|---|
| commits enumerated | 977 |
| inserted | 211 |
| already covered (skipped) | 765 |
| merge commits captured | 38 |
| files recorded | 1442 |
| **GitHub API calls** | **0** |
| `cfeafe4` | **captured** — full 6-line message, all 3 `utils/CLIO/` paths, `source=git_backfill` |

### QA gate — Phase 1

- [x] Backfilling `development` since 2026-05-01 reduces the measured 182-commit gap to **0**.
- [x] `cfeafe4` is present in `github_direct_commits` with its full message and all 3 `utils/CLIO/` paths.
- [x] Merge commits are captured and do **not** duplicate their PR-commit counterparts.
- [x] Re-running the backfill is a no-op (0 inserted, 0 updated) — idempotency proven, not assumed.
- [x] Zero GitHub API calls made by this path, asserted in test.
- [x] A repo with **no local clone** yields an `uncoverable` record with a reason — not a silent skip,
      and not an exception.
- [x] A **stale clone** is fetched before enumeration; a test proves a deliberately-behind clone does
      not report a false 0 gap.
- [x] Conflict policy proven: an API-sourced enrichment arriving after a git-sourced row does **not**
      downgrade its `path_coverage`.
- [x] `rebalance doctor` clean.

## Phase 2 — Repair attempt accounting

- [x] Separate **budget exhaustion** from **attempt failure**. A cap-deferral must not increment
      `attempt_count`; introduce a distinct state (e.g. `queued`) or an explicit
      `increment_attempt: bool` on `update_push_event()`.
- [x] Recover the 21 currently-stuck events. **Not by matching `failure_reason` text** (agy Should —
      brittle, and the string is a human-readable log line that has already changed once). Instead
      persist the distinction structurally: add a `deferral_kind` column (`budget` | `failure`) set at
      write time, migrate existing rows once using the current text as a best-effort seed, and key the
      reset on the column thereafter.
- [x] Ship the recovery as a **preview-then-apply** step against the live DB: a `SELECT` reporting the
      exact rows to be reset (count + event ids), gated behind an explicit apply flag. Default is
      preview.
- [x] Rollback story: the migration is additive (new column, no drops); the reset only lowers
      `attempt_count` and flips `state` back to `pending`, so re-running collection is the rollback.
      Snapshot the affected `(event_id, state, attempt_count)` triples to a file before applying.
- [x] Distinguish the two in `DirectCommitCaptureResult` — `events_deferred` must not conflate
      "over budget" with "failed", since that conflation is what made this invisible.
- [x] Make the module docstring's durability claim true, or amend the docstring. It currently
      asserts a guarantee the code does not provide.

### Phase 2 findings (written back per PDDA)

Verified against a copy of the production DB:

| | before | after |
|---|---|---|
| permanently stuck (`attempts >= 3`, never enriched) | **21** | **1** |
| legacy rows classified by the one-time text seed | — | 41 |
| recovered | — | **20** |

The single remaining stuck event is the genuine transient-fetch failure, correctly left stuck — the
recovery deliberately does not resurrect real failures, only budget evictions. Recovery ran preview
first (no mutation), then applied with a pre-image snapshot.

One deliberate behaviour change to an existing GH-155 test: it asserted
`events_deferred == 1` for a cap deferral. That conflation is the defect, so the assertion now reads
`events_over_budget == 1`, `events_deferred == 0`, and additionally checks `attempt_count == 0` —
the receipt is only "durable" if it kept its eligibility.

### QA gate — Phase 2

- [x] A regression test proves an event deferred purely by cap is still eligible after 3+ runs.
- [x] The 21 stuck events return to eligibility; the 20 cap-only ones enrich on subsequent runs.
- [x] Genuine failures (non-retryable HTTP) still exhaust attempts and stop retrying — the fix must
      not turn real failures into an infinite retry loop.
- [x] Refresh output reports over-budget and failed counts separately.

## Phase 3 — Completeness as a measurable property

This phase is why the doc exists in the form it does. #155 and #157 each fixed a real thing and each
left a gap that only surfaced when an operator asked a question and got a bad answer. Completeness
must be continuously derivable.

**agy raised a Blocker here that reframes the phase.** A check comparing local `git log` to the local
DB only proves *the backfill ran*. If the clone is stale, both sides are equally behind the remote and
the check reports a confident **0** while the real gap is wide open. A completeness check that can
silently agree with itself is precisely the "one more thing" generator this phase exists to remove —
it would have passed green through the entire #155→#157 sequence.

The check must therefore be **anchored to the remote**, and must report three distinct quantities
rather than one number:

- [ ] **Remote anchor.** Resolve the remote default-branch tip via `git ls-remote` (one cheap call,
      no clone required) and record clone freshness as `local_tip == remote_tip` plus last-fetch age.
      A check run against a clone behind the remote reports `stale`, never `0`.
- [ ] **Three separate gaps, never netted** (closes the RC5 phantom/gap cancellation):
      1. `collection_gap` — SHAs on the remote default branch absent from `github_direct_commits` +
         `github_commits`. **Presence of a row is not coverage** (agy r2 Nit): a row whose
         `path_coverage` is `unavailable` is a captured commit with no file data, and a
         presence-only check would score it as covered and report a false zero. The gap is therefore
         computed against rows with `path_coverage = 'complete'`, and `incomplete_count` is reported
         alongside so a partially-enriched corpus is visible rather than rounded away.
      2. `projection_gap` — captured commits absent from `github_documents` (catches the
         `sync_direct_commit_documents()` full-rebuild failure mode).
      3. `orphan_count` — captured SHAs no longer reachable on the remote (force-push / squash
         residue).
- [ ] **Uncoverable repos are a reported state**, not an omission: watched repos with no clone appear
      in the check with `uncoverable` and a reason.
- [ ] Surface all of it in `index_status` freshness (alongside `github_documents_missing_from_semantic`)
      and in `rebalance doctor`.
- [ ] Degrade health when any gap exceeds threshold, when a clone is stale, or when a repo is
      uncoverable.

### QA gate — Phase 3

- [ ] With commits deliberately withheld, the check reports the correct non-zero `collection_gap`.
- [ ] **A deliberately stale clone reports `stale` rather than `0`** — the blocker's regression test.
- [ ] Deleting rows from `github_documents` while leaving `github_direct_commits` intact produces a
      non-zero `projection_gap` (proves the two are measured independently).
- [ ] A phantom SHA plus an equal-sized real gap reports **both**, not a net zero.
- [ ] **A row present but with `path_coverage = 'unavailable'` counts as a gap, not as covered**
      (agy r2 Nit regression test — presence is not coverage).
- [ ] After backfill on a fresh clone, all three report 0 and health is `ok`.
- [ ] Cheap enough for every `doctor` run: local git plus one `git ls-remote` per repo, no REST API.
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

## Phase ordering — why backfill still goes first

agy flagged (Should) that running Phase 1 before Phase 2 risks the 21 un-stuck events re-processing
and overwriting the `path_coverage` metadata the backfill just wrote, and offered two remedies: swap
the phases, or define an explicit conflict policy.

**Taking the second.** The operator chose backfill-first deliberately, and the reason survives the
review: Phase 1 is what makes `cfeafe4` findable — the originating symptom — and it is verifiable on
its own the day it lands. Phase 2 cannot deliver that at all, because `cfeafe4` is outside the
300-event window no amount of attempt-accounting repair can reach.

The interference agy identified is real but is a write-conflict question, not an ordering question,
and it is fully addressed by the `ON CONFLICT` rule now specified in Phase 1: `path_coverage` may only
move `unavailable → complete`, so a later API-sourced enrichment can never downgrade a git-sourced
row. Both orderings need that rule; only one ordering also fixes the symptom first.

Recorded here rather than silently resolved, because it modifies a reviewer finding rather than
implementing it as written.

## Anti-goals

- **Not** ingesting archived third-party repos. Deferred from the original #169 framing after the
  RCA showed the destination repo's own commit already carries the provenance — the origin repo did
  not need ingesting at all.
- **Not** removing the Events-API path. It stays as a low-latency accelerator; git history becomes
  the correctness backstop.
- **Not** raising the per-run caps as the fix. Caps are a legitimate rate-limit defence; the defect
  is that hitting one is accounted as a failure.
- **Not** a full re-embed of the corpus.

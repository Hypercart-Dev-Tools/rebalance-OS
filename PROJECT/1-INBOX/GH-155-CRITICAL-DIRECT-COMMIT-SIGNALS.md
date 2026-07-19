---
gh_issue: 155
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/155
title: "[CRITICAL] HiQS loses direct GitHub commits and file-level change signals"
status: triage
doc_type: pdda-spec
priority: P0
effort: 3
complexity: 3
risk: 3
phases: 4
created: 2026-07-18
---

# GH-155 — Critical direct-commit signal loss

## TOC

- Decision and impact
- Evidence and root cause
- PDDA contract
- Proposed data model and collection algorithm
- Rate, failure, and duplication policy
- Phased delivery
- Test and rollout plan
- Acceptance checklist

## Decision and impact

Treat this as a P0 collection-correctness defect. HiQS must preserve enough
identity and file evidence to distinguish meaningful direct pushes from a raw
commit count. Without that, work can be collected but cannot be retrieved,
explained, or ranked accurately.

## Evidence and root cause

On 2026-07-17 20:06 PT, direct commit `cfeafe4` added `utils/CLIO/` to this
repository. The GitHub activity row retained only aggregate activity (`5`
commits / `5` pushes); the detailed commit table has no record for that SHA.

The pipeline has two incompatible partial views:

1. `github_scan` turns the authenticated user Events API stream into counts in
   `github_activity`; it retains neither push commit identity nor changed paths.
2. `github_knowledge` persists commits discovered through PR endpoints. Direct
   commits not attached to a PR are consequently absent from
   `github_commits`, `github_documents`, the recent-activity stream, and HiQS.

## PDDA contract

### Problem

Historical collection promises are broken for direct branch pushes: the system
knows that something happened but cannot answer what changed or why it matters.

### Decision

Extend the existing GitHub raw-source pipeline with a bounded direct-commit
collection path. The GitHub source remains the sole writer for its raw table;
semantic projection remains the sole writer of `semantic_documents`.

### Design constraints

- Reuse the already-fetched authenticated Events response for discovery. Do not
  add a per-repository commit poll to the hourly refresh.
- A production `PushEvent` may contain `before` and `head` but no `commits`
  list. Treat event payload commit lists as an optimisation, never as the
  identity contract.
- Restrict enrichment to branch pushes in the resolved watched-repository set.
  Tags, deleted branches, ignored repositories, and unauthorised events are
  recorded as non-actionable observations, not silently treated as commits.
- Keep a durable event receipt as well as one canonical direct-commit row keyed
  by `(repo_full_name, sha)`; a commit table alone cannot explain a failed,
  deleted, or force-pushed event.
- Store SHA, message, author/time, provenance, and exact changed paths with a
  completeness indicator. Never assign a push-level file list to each commit.
- De-duplicate PR and direct evidence by `(repo_full_name, sha)` at every
  consumer. Retain both raw provenance records so later PR discovery does not
  erase the historical direct-push fact.
- Enforce a per-run API budget and expose deferred/truncated coverage in the
  refresh result and operator diagnostics.

## Proposed data model and collection algorithm

### New source-owned tables

`github_push_events` is the durable receipt/cursor table, keyed by GitHub event
ID. It holds `repo_full_name`, `ref`, `before_sha`, `head_sha`, `observed_at`,
`state`, `attempt_count`, `last_attempt_at`, `resolved_at`, and a bounded
`failure_reason`. States are: `pending`, `enriched`, `deferred`, `head_only`,
`ignored`, and `failed`. This makes an API failure, a range that exceeds the
budget, and a branch deletion visible rather than indistinguishable from "no
work."

`github_direct_commits` is the canonical raw work record, keyed by
`(repo_full_name, sha)`. It holds the originating event ID, ref, commit
message, GitHub author login/name, commit timestamp, URL, discovery timestamp,
and `path_coverage` (`complete`, `truncated`, or `unavailable`).

`github_direct_commit_files` is keyed by `(repo_full_name, sha, path)` and
holds the changed path plus status/additions/deletions/changes when GitHub
supplies them. A relational path table makes `utils/CLIO/` queryable without
parsing JSON and avoids duplicating a push-wide file list across several SHAs.

The GitHub raw source is the only writer for these three tables and for its
`github_documents` rows. The semantic projection remains the only writer for
`semantic_documents`.

### Collection sequence

1. Fetch the existing authenticated Events pages once; write normal
   `github_activity` counters exactly as today.
2. Resolve the watched-repository set before enrichment. Insert newly observed
   watched-repo `PushEvent`s into `github_push_events` idempotently. This step
   costs no additional GitHub request.
3. Process pending/deferred events oldest first, only for `refs/heads/*`.
   For a normal `before`/`head` range, call
   `GET /repos/{owner}/{repo}/compare/{before}...{head}` once. Its commit list
   establishes the SHAs even when the event payload omitted `commits`.
4. If the compare range is within the configured limit, upsert its direct
   commits. For each previously unseen direct SHA, call
   `GET /repos/{owner}/{repo}/commits/{sha}` to capture that commit's own file
   list. This is essential: the compare endpoint's `files` collection describes
   the whole range, not a particular commit.
5. A deleted branch is `ignored`. A force-push, missing base, or oversized
   range is not silently dropped: capture the reachable `head` with one commit
   request where possible, mark it `head_only`/`truncated`, and retain the
   event's explicit reason for follow-up.
6. After the normal PR-artifact refresh, reconcile by SHA. A direct row that
   also exists in `github_commits` remains raw evidence but is excluded from
   direct-commit documents, pulse rows, recent activity, and HiQS candidates.
   If the PR arrives later, reconciliation removes the formerly-direct document
   and consumer result on the next refresh.
7. Materialise non-overlapping direct commits as `github_documents` with a
   stable source key such as `repo:direct_commit:<sha>`. The existing semantic
   projection then indexes that document. The document body includes subject,
   SHA, ref, timestamp, and a capped path list with coverage status.

## Rate, failure, and duplication policy

### Explicit budget

Start with two configuration values:

- `github_direct_push_compare_cap = 5` per refresh;
- `github_direct_commit_detail_cap = 20` per refresh.

The worst additional cost is therefore 25 REST calls in a run that contains
new work; the typical cost is zero because event receipts and commit upserts
are idempotent. Deferred events remain queued for a later run rather than
being forgotten. The refresh result must report `events_seen`, `events_new`,
`events_enriched`, `events_deferred`, `commits_captured`, `head_only`, and
`api_calls_used`.

This cap is deliberately separate from GH-140's broader GitHub-refresh rate
problem. It prevents the fix for this correctness defect from introducing an
unbounded new call pattern; it does not make the current full artifact sync
cheap.

### Coverage and recovery

- GitHub's Events API has delivery latency and bounded history. The contract is
  *eventual capture after event visibility*, not real-time capture. The receipt
  counts make a delayed/missed observation diagnosable.
- A compare result beyond the supported bounded range is marked `truncated`;
  no whole-history fallback runs automatically. An explicit operator backfill
  can be designed later if needed.
- Retry only transient API/network errors with bounded attempts and backoff.
  Authentication/permission errors surface in the source error envelope; they
  do not create empty successful rows.
- Reconciliation uses a set-based SQL anti-join, not one query per commit. It
  must run before documents and display rows are selected.

### Consumer contract

The GitHub `OperatorBundle` gains `gh_direct_commits`; `github_candidates()`
emits one candidate only for a recent, non-PR-overlapping direct commit. Its
evidence contains the commit URL/SHA and affected paths, and its `why` text
states that it is an unreviewed direct branch push. `pulse._query_day_activity`
and `dashboard.fetch_recent_github()` use the same anti-joined direct rows, so
HiQS, the Obsidian-facing pulse, and the dashboard cannot disagree about
whether the signal exists.

## Phased delivery

### Phase 0 — technical spike (1–2 hours)

- [ ] Replay a fixture shaped like the real `cfeafe4` PushEvent: `before` and
  `head` present, no `payload.commits` list. Confirm compare resolves the SHA.
- [ ] Fetch `cfeafe4` through the commit endpoint and prove its three exact
  paths (`utils/CLIO/INSTALL.md`, `LICENSE`, `README.md`) can be persisted.
- [ ] Record measured request counts for normal, empty, force-push, and
  oversized ranges; validate the 5/20 cap against GH-140's rate budget.
- [ ] Validate the set-based PR-overlap query and the document deletion path
  when a previously direct SHA subsequently appears on a PR.
- [ ] Stop and revise if GitHub cannot return per-commit files within the cap,
  or if projection cannot remove an overlapping direct document safely.

### Phase 1 — durable raw capture

- [ ] Add migrations, typed DB helpers, and indexes for event receipts, direct
  commits, and direct-commit paths.
- [ ] Add the bounded event-to-compare-to-commit-detail collector behind the
  existing GitHub refresh orchestrator; dry-run reports the plan without API
  detail calls or writes.
- [ ] Persist provenance, retry/defer state, and coverage/truncation diagnostics
  in the GitHub source result.

### Phase 2 — projection and consumption

- [ ] Build/delete direct-commit `github_documents` through the GitHub source;
  project them only through the existing semantic stage.
- [ ] Extend the GitHub bundle/candidate provider, pulse query, and dashboard
  union with one shared non-overlap query contract.
- [ ] Add operator-visible evidence: repo, SHA, changed paths, coverage state,
  and reason for relevance.

### Phase 3 — guarded rollout

- [ ] Ship disabled-by-default or with the conservative 5/20 caps, run a
  single targeted refresh, and inspect structured counters plus rate headers.
- [ ] Backfill only the incident's bounded window (for example, the event range
  containing `cfeafe4`) through an explicit operator command—not by a silent
  whole-history scan.
- [ ] Enable for watched repositories after the regression tests and observed
  rate cost pass; document the coverage limitation in the operator runbook.

## Test and rollout plan

| Layer | Required proof |
| --- | --- |
| Raw capture | Fixture with no payload commits resolves `cfeafe4` via compare and stores exactly three CLIO paths. |
| Idempotency | A repeat run makes no compare/detail call for an enriched event and creates no duplicate rows. |
| Boundaries | Deleted ref, force-push, compare over cap, 401/403, 429, 504, malformed response, and pagination leave explicit states/counters. |
| De-duplication | A SHA also present in `github_commits` remains in raw provenance but yields one consumer-visible commit and no direct document. |
| Projection | Direct document is indexed by semantic projection; later PR overlap deletes that semantic document. |
| End to end | `utils/CLIO/` returns from the file-aware query, appears in the activity feed, and has HiQS evidence after refresh. |

Use versioned JSON fixtures for Events, compare, and commit-detail endpoints;
assert API-call counts as well as rows. Add one integration test that starts
from an empty SQLite DB and one migration test against a DB containing current
GitHub tables.

## Acceptance checklist

- [ ] A cfeafe4-equivalent direct commit makes `utils/CLIO/` discoverable.
- [ ] SHA, message, timestamp, and changed paths survive an unchanged rerun.
- [ ] A matching PR commit leaves raw provenance intact but produces neither a
  duplicate visible signal nor a second semantic document/HiQS candidate.
- [ ] Cap/pagination, delayed events, and API failures are tested with fixtures
  and leave an operator-visible coverage state.
- [ ] The result appears in the recent-activity and HiQS evidence contracts.

## Out of scope

- Whole-history repository backfill without an explicit operator request.
- Changing GitHub scheduler cadence or token allocation (tracked separately).

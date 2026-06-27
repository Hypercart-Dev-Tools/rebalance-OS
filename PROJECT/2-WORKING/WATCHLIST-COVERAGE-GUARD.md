---
title: "Watch-list coverage guard — canonical snapshot + silent-reduction alarm"
status: "complete (ponytail-trimmed) — ready to move to 3-COMPLETED"
doc_type: bugfix
owner: noel@neochro.me
created: 2026-06-26
updated: 2026-06-26
branch: development
goal: >
  Persist the canonical watched-repos set on every GitHub sync, diff it against the
  prior snapshot, and surface any *reduction* in monitored repos to the web app's
  auth-log screen — so a repo can never silently fall off the roster the way
  BinoidCBD/LTVera-Pandas appeared to.
priority: P2
related:
  - PROJECT/3-COMPLETED/FOCUS-5-RANKING-BUG-AND-REMEDIATION.md
  - PROJECT/2-WORKING/GH-81-FOCUS5-RANK-VECTOR.md
non_goals:
  - "Does not change how the watched set is *computed* (the union in get_watched_repos)."
  - "Does not add a new web screen or a new launchd job — reuses /auth-log and github-sync."
rollout_rule: >
  Each phase leaves the system runnable (`pytest tests/` green, `rebalance doctor` clean);
  the change is an additive snapshot table + a pure diff function + one new log event —
  reversible, no destructive migration, no change to the computed watch set.
---

## Status

| What was just completed | What's next |
|---|---|
| **COMPLETE (2026-06-26).** Phase 1 shipped + ponytail-trimmed + Phase 2 collapsed to one line. Migration `0009_watched_repos_snapshot.sql` + isolated `watchlist_guard.py` (`classify_removal` pure helper + `snapshot_and_detect` single writer) at the end of `_refresh_github` (clean-sync only) + `log_watched_repos_reduced` helper + a one-line `_EVENT_BADGE` entry so the event shows a ⚠ warn chip on `/auth-log`. All 4 agy `[Should]` baked in. **ponytail pass** cut the monotonic-id machinery + its test (prod-impossible same-second double-sync) and inlined the `set - set` wrapper (`diff_watched_set` + 4 stdlib-testing tests deleted); Phase 2's "phase" framing collapsed since `/auth-log` already renders any event. **11 guard tests; suite green; `doctor` clean.** Live-DB proof: 59 watched, 24 durable-intent — LTVera-Pandas (`project`) now alarms on a silent drop. | **Move doc to `3-COMPLETED`** and merge PR #82. |

## Table of Contents

- [Problem](#problem)
- [Decision (why snapshot-and-diff, not a watch-set rewrite)](#decision-why-snapshot-and-diff-not-a-watch-set-rewrite)
- [Non-Goals](#non-goals)
- [Phase 1 — Canonical snapshot + silent-reduction detection](#phase-1--canonical-snapshot--silent-reduction-detection)
- [Phase 2 — Operator surface (collapsed into Phase 1)](#phase-2--operator-surface-on-the-web-log-screen-collapsed-into-phase-1--ponytail)
- [Open Questions](#open-questions)

## Problem

The watched-repos set — `get_watched_repos()`
([src/rebalance/ingest/index_ops.py:511](../../src/rebalance/ingest/index_ops.py#L511)) — is a
**dynamically recomputed union** of four sources minus an ignore list:

```
watched = (project_repos ∪ activity_repos ∪ pushed_repos ∪ external_repos) − github_ignored_repos
```

Two of those sources are **rolling time windows**: `_activity_repos()` keys on
`scan_date >= date('now','-{since_days} days')` (default 14d,
[index_ops.py:424](../../src/rebalance/ingest/index_ops.py#L424)) and `_pushed_repos()` keys on
`pushed_at >= cutoff` ([index_ops.py:460](../../src/rebalance/ingest/index_ops.py#L460)). A repo
held *only* by a window drops off the roster the instant the window slides past its last
push/activity — and because the set is **never persisted**, the drop leaves **no trace**: no
log line, no diff, nothing to diagnose after the fact.

Verified 2026-06-26: `BinoidCBD/LTVera-Pandas` was reported "fell out", but `diagnose_repo`
returns `watched_and_fresh` (in the active registry **and** both windows, not ignored). It is
monitored *now* — the perceived drop already self-healed. The exact trigger is **unrecoverable**
precisely because nothing recorded the prior set. That unrecoverability is the bug: a coverage
reduction must never be silent.

## Decision (why snapshot-and-diff, not a watch-set rewrite)

The union logic is correct and intentional (windows keep auto-discovered repos from
accumulating forever). The gap is **observability**, not computation. So the fix is the
minimal additive layer that already has three precedents in this repo:

1. **Persist a canonical snapshot** of the resolved watched set on every github sync — the
   same snapshot-to-DB pattern as `focus5_repo_signals`
   ([src/rebalance/ingest/focus5_scan.py](../../src/rebalance/ingest/focus5_scan.py)), written by a
   **single writer** in the path that already calls `get_watched_repos()`.
2. **Diff against the prior snapshot** with a pure function — same isolate-the-logic stance
   as the focus5 `resolve_recency` / `rank_recent_activity` pure functions.
3. **Emit reductions to the existing log surface** — `auth_log.log_event(...)`
   ([src/rebalance/ingest/auth_log.py:129](../../src/rebalance/ingest/auth_log.py#L129)), already
   rendered by the `/auth-log` web screen
   ([src/rebalance/web.py:909](../../src/rebalance/web.py#L909)) and already used by the launchd
   `log_job_*` helpers — so no new screen and no new event plumbing.
4. **Run unattended for free** by piggybacking the hourly `com.rebalance-os.github-sync`
   job (the same lever focus5's roster refresh used — commit `53286a3`), so **no new launchd
   job**.

Reversible (additive table + pure function + one event), no destructive migration, no change
to the computed watch set.

## Non-Goals

- The watch-set **computation** (`get_watched_repos` union + ignore list) is untouched.
- **No new web screen** — reuse `/auth-log`. **No new launchd job** — piggyback `github-sync`.
- Not a generic "alert on any change" — *additions* are expected churn; only *reductions* of
  durable-intent monitoring are surfaced (see [Open Questions](#open-questions)).
- Not retroactive — the first snapshot is a baseline; diffing starts on the second sync.

---

## Phase 1 — Canonical snapshot + silent-reduction detection

> Persist the resolved watched set each github sync, diff it against the previous snapshot,
> and record any concerning reduction — data layer only.

- [x] **Additive migration `0009_watched_repos_snapshot.sql`** (next free number — `0008` is
      the latest, [src/rebalance/ingest/db/migrations/](../../src/rebalance/ingest/db/migrations/)).
      A `watched_repos_snapshot` table keyed by `(snapshot_ts, repo)` with the resolving
      `bucket`(s) (`project`/`activity`/`pushed`/`external`) recorded per repo, so a later
      reduction can name *what kind* of coverage was lost. `CREATE TABLE IF NOT EXISTS`,
      NULL-tolerant — idempotent per the migrations README.
- [x] **Pure `diff_watched_set(prev: set, curr: set) -> {added, removed}`** in
      `index_ops.py` (or a small `watchlist_guard.py` sibling) — no I/O, fully unit-testable.
- [x] **Single writer** hooked into the github sync path where `get_watched_repos()` already
      runs (`_refresh_github`, [index_ops.py:571](../../src/rebalance/ingest/index_ops.py#L571),
      reached via `_github_adapter` / `refresh_index(scope=["github"])`). It: (a) reads the
      latest prior snapshot, (b) writes the new snapshot, (c) diffs, (d) classifies removals.
- [x] **Pin a canonical window (agy r1 [Should]).** `refresh_index` defaults `since_days=30`
      ([index_ops.py:1040](../../src/rebalance/ingest/index_ops.py#L1040)) but the watched-set
      windows default to `14` ([index_ops.py:424](../../src/rebalance/ingest/index_ops.py#L424),
      [:460](../../src/rebalance/ingest/index_ops.py#L460)). If the snapshot reflected the
      *caller's* `since_days`, a 30-day sync vs a 14-day sync would diff against each other and
      manufacture **phantom** reductions/additions. The writer therefore calls
      `get_watched_repos(db, since_days=14)` with a **fixed canonical window**, independent of
      the triggering sync's window.
- [x] **Run only on a clean sync (agy r1 [Should]).** A github sync that raises partway could
      leave a *truncated* set and record a **false** reduction. The snapshot+diff runs at the
      **end of `_refresh_github`** ([index_ops.py:571](../../src/rebalance/ingest/index_ops.py#L571)),
      only when the adapter completed without raising — never in a `finally`/error path.
- [x] **Classify removals** so the alarm is signal, not noise: a removed repo whose last-known
      bucket set includes `project`/`external` (durable monitoring *intent*) → **concerning**
      (`warn`); one held only by `activity`/`pushed` (rolling window) → **expected churn**
      (`info`). Multi-bucket membership resolves by "warn if `project` **or** `external` is in
      the last-known bucket set" (agy r1 confirmed this resolves the ambiguity). See Open
      Question 1.
- [x] **Exclude intentional ignores (agy r1 [Should]).** A repo the operator just added to
      `github_ignored_repos` ([config.py:870](../../src/rebalance/ingest/config.py#L870)) leaves
      the watched set and would look like a reduction. The differ filters removed repos through
      `get_github_ignored_repos()` and **suppresses** the alert for any now-ignored repo (an
      intentional opt-out is not a coverage loss).
- [x] **Prune the snapshot table (agy r1 [Should] — resolves Open Q2).** At the end of the
      writer, `DELETE FROM watched_repos_snapshot WHERE snapshot_ts < <now − 30d>` so the table
      keeps ~30 days of diffable history without unbounded growth.
- [x] **Emit via the existing surface** — on a concerning reduction call
      `auth_log.log_event("github", "watched_repos_reduced", {...})` with per-repo
      `{repo, last_bucket, ...}`; add a typed helper
      `log_watched_repos_reduced(...)` next to the `log_job_*` helpers
      ([auth_log.py:282](../../src/rebalance/ingest/auth_log.py#L282)) so the vocabulary lives
      in one place (DRY).
- [x] **Baseline-safe:** first-ever run (no prior snapshot) writes the baseline and emits
      **no** reduction event — diffing begins on the second sync.

### QA Checklist — Phase 1

- [x] **DRY:** one snapshot writer (single source of the persisted set), one pure differ; the
      bucket→severity vocabulary defined once.
- [x] **SOLID:** snapshot + diff isolated from the union computation; `get_watched_repos`
      unchanged; route/render layers untouched.
- [x] **Diagnosable:** every snapshot records the resolving bucket per repo, so a reduction
      answers "*what kind* of coverage was lost" — the exact fact missing for LTVera-Pandas.
- [x] **Blast:** additive table + pure function + one event = reversible; no destructive
      migration; the computed watch set is byte-for-byte unchanged.
- [x] **Proof:** unit tests for `diff_watched_set` (add-only, remove-only, no-op, first-run
      baseline) + an integration test (snapshot→slide→removal emits exactly one event;
      re-add emits none); `pytest tests/` green; `rebalance doctor` clean.
- [x] **Single write path:** the snapshot table is written only by the github-sync writer —
      no second writer.
- [x] **UTC:** `snapshot_ts` is a UTC epoch; display formats at the edge (matches focus5).

---

## Phase 2 — Operator surface on the web log screen *(collapsed into Phase 1 — ponytail)*

> Originally a separate phase; the ponytail pass collapsed it to **one line**.
> `/auth-log` already renders any event via `_EVENT_BADGE.get(event, ("neutral", event))`
> ([src/rebalance/web.py:200](../../src/rebalance/web.py#L200)), so `watched_repos_reduced`
> surfaced on the screen the moment Phase 1 emitted it — no Phase 2 code was required for it
> to be visible.

- [x] **Badge the event** — added one `_EVENT_BADGE` entry
      ([src/rebalance/web.py:44](../../src/rebalance/web.py#L44)):
      `"watched_repos_reduced": ("warn", "⚠ watched repos reduced")`, upgrading the fallback
      neutral chip to a red warn chip. The event is only emitted on a *concerning* drop, so a
      single warn variant is correct (no per-row info/warn split needed).
- [x] **Render test** — `test_watched_repos_reduced_renders_warn_badge`
      ([tests/test_web_auth_log.py](../../tests/test_web_auth_log.py)) seeds the event and
      asserts the `⚠ watched repos reduced` warn badge **and** the dropped repo
      (`BinoidCBD/LTVera-Pandas`) render on `GET /auth-log`.

---

## Open Questions

1. ~~**Reduction severity threshold.**~~ **RESOLVED (shipped):** the event fires only when a
   removed repo's last-known bucket set includes `project`/`external`; `activity`/`pushed`-only
   churn is recorded as `info_churn` context and does not alarm. Revisit only if the signal
   proves noisy.
2. ~~**Snapshot retention.**~~ **RESOLVED (agy r1):** prune to a rolling 30-day window
   (`DELETE ... WHERE snapshot_ts < now−30d`) at the end of the writer — folded into Phase 1.
3. **Should a re-add also surface?** A repo that drops then returns is arguably worth an
   `info` "recovered" line. Default OFF for v1 (reductions are the ask); trivial to add later.
4. ~~**Ignore-list & caller-variable window.**~~ **RESOLVED (agy r1):** the differ filters
   removed repos through `get_github_ignored_repos()` (intentional opt-out ≠ reduction), and
   the writer pins a fixed `since_days=14` canonical window so a 30-day sync can't manufacture
   phantom diffs — both folded into Phase 1.

## Review history

- **Diagnosis (2026-06-26)** — `diagnose_repo BinoidCBD/LTVera-Pandas` → `watched_and_fresh`
  (in active registry + both windows, not ignored); `list_watched_repos` confirms membership
  across `project_repos`, `activity_repos`, `pushed_repos`. Root cause = no persisted history
  of the watched set ⇒ reductions are silent and unrecoverable. Plan scaffolded against the
  focus5 snapshot table, the `auth_log`/`auth-log` event surface, and the `github-sync`
  piggyback — no new patterns invented.
- **agy relay r1 (2026-06-26) — PLAN QA, Verdict: FAIL → all findings integrated.** Thread:
  [relay-system/2026-06-26/watchlist-guard-qa.md](../../relay-system/2026-06-26/watchlist-guard-qa.md).
  Two `[Pass]` (severity classification sound; `/auth-log` reuse correct, no extra render code).
  Four `[Should]`, all folded into Phase 1: (1) **caller-variable `since_days`** — pin a fixed
  `since_days=14` window so a 30-day sync can't manufacture phantom diffs; (2) **partial-sync
  guard** — run snapshot+diff only on a clean `_refresh_github` completion; (3) **ignore-list
  interaction** — suppress alerts for repos just added to `github_ignored_repos`; (4) **table
  pruning** — 30-day retention `DELETE` (resolved Open Q2).
- **Phase 1 implementation (2026-06-26)** — shipped: migration
  `0009_watched_repos_snapshot.sql`; new isolated module
  [src/rebalance/ingest/watchlist_guard.py](../../src/rebalance/ingest/watchlist_guard.py)
  (`diff_watched_set` + `classify_removal` pure helpers; `snapshot_and_detect` single writer);
  `log_watched_repos_reduced` typed helper in `auth_log.py`; and the clean-sync-only hook at the
  end of `_refresh_github`. Tests: `tests/test_watchlist_guard.py` (16 — pure diff/classify
  matrices + baseline / project-removal-warns / window-churn-quiet / ignore-suppressed / re-add /
  pruning / monotonic-ts). **`pytest tests/` 1137 passed; `doctor` clean.** Live-DB baseline:
  59 watched, bucket spread `pushed 18 · activity,pushed 15 · project 11 · activity,project,pushed
  10 · …` → 24 durable-intent repos now alarm on a drop. One deviation recorded inline: an
  *empty* watched set writes zero rows and so isn't anchored by `MAX(snapshot_ts)` — out of scope
  (monitoring-is-off is a bigger alarm) and **safe-loud** (next run re-alarms, never silent).
- **Ponytail pass (2026-06-26)** — de-overengineering review of the whole effort. Cuts: (1)
  the monotonic snapshot-id bump + its dedicated test — defended a same-second double-sync that
  a minutes-long github sync makes prod-impossible (`INSERT OR REPLACE` covers it); (2) inlined
  `diff_watched_set` (a one-line `set - set` wrapper, used once) and deleted its 4 unit tests
  (testing stdlib; the integration tests exercise the diff); (3) collapsed **Phase 2** from a
  phase-with-QA-gates to a single `_EVENT_BADGE` line, since `/auth-log` already renders any
  event via the `.get(event, ("neutral", …))` fallback. Kept (defended as load-bearing): the
  bucket CSV (diagnostic payload), `classify_removal` (the warn/info signal), the canonical
  `since_days=14` pin, clean-sync guard, ignore-suppression, pruning, baseline-safe.

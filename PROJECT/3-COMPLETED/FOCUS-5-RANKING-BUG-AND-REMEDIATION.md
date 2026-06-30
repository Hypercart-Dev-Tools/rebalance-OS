---
title: "Focus 5 surfaces the wrong repos — root-cause trace + remediation"
doc_type: bug-trace + remediation-plan
status: COMPLETE (2026-06-24) — Phases 1/2/4 verified live; Phase 3 activated (com.rebalance-os.github-sync installed + loaded + fired on the :45 schedule, focus5 recompute OK, 0 failed repos)
method: /debug-mantra (reproduce → fail path → falsify → cross-reference)
owner: noel@neochro.me
created: 2026-06-19
updated: 2026-06-24
goal: "Identify and resolve why the Focus 5 dashboard page surfaces incorrect or stale repositories rather than the most recently active ones."
related:
  - PROJECT/2-WORKING/FOCUS-5.md  (original spike/design)
  - src/rebalance/ingest/focus5_scan.py  (ranking + scan)
  - src/rebalance/web.py  (focus5_page route)
---

# Focus 5 surfaces the wrong repos

## Status

| What was just completed | What's next |
|---|---|
| **Phase 3 activated (2026-06-24)** — `com.rebalance-os.github-sync` installed + loaded (`launchctl list` shows it) and fired on the `:45` schedule; the focus5 recompute completed (`failed_repos: 0`), so the roster now refreshes hourly without manual intervention. Phases 1/2/4 were already verified live (2026-06-19). | **Complete — moved to `3-COMPLETED`.** No remaining project work; the hourly recompute runs autonomously. |

**Implementation log (2026-06-19).** Landed on `fix/focus5-no-blocking-scan`,
one commit per phase, 139 tests green:
- **Phase 1** — `rank_recent_activity` strategy + registered; `get_focus5_ranking_mode()`
  unset default flipped to `recent_activity` (in lockstep with `DEFAULT_RANKING_MODE`).
- **Phase 2** — `/focus-5` defaults to recent_activity; `?view=dirty` renders a
  **transient** Dirty Five (re-rank from cache via `summarize_focus5(mode=...)`,
  never rewrites `focus5_roster`); shared `_build_roster_card`; segmented toggle.
- **Phase 4** — Focus-5-only scan-root config (`set/add/remove_focus5_scan_root`)
  + `rebalance config {add,remove,list}-focus5-scan-root`; `rebalance-OS` added to
  the live (gitignored) `temp/rbos.config`; self-repo-root discovery pinned by test.
- **Phase 3** — folded `focus5` into the hourly `github-sync` scope (operator's
  choice over a standalone job); SCHEDULER.md + policy test updated. **Activated
  2026-06-24:** `bash scripts/install_github_scheduler.sh` installed + loaded
  `com.rebalance-os.github-sync`; it fired on the `:45` schedule and the focus5
  recompute completed (0 failed repos), so `refresh_index(scope=["github","focus5"])`
  now runs hourly.
- **Live verification** — `sync_focus5()` on the real DB: discovered 86 repos,
  roster = rebalance-OS (2m), xyz-3-agents-swarm (8h), giant-brains (9h),
  hypercart-plugin-mkiii (12h), wp-code-check (1d). `eve` (dirty-only, no authored
  commit) is **absent** from Focus 5 and present in Dirty Five — contract holds.

## Symptom (as reported)

The Focus 5 page shows 5 repos none of which were touched in the last 8h. The
repos actually being worked on (frequent commits + pushes in the last ~12h) —
`xyz-3-agents-swarm`, `rebalanceOS`, `giant-brains-claude-skills`,
`hypercart-plugin-mkiii` — do **not** appear. The page instead shows
`sleuth-app`, `eve`, `ask-self`, `sharelist-sync-stream`, `9arm-skills`.

## Debug-mantra ledger (evidence)

All runs are **read-only**; the decisive ones re-rank the *already-stored*
signals (no re-probe) via `rerank`-equivalent logic.

| # | Experiment | Result | Rules in / out |
|---|---|---|---|
| 1 | Read scan-root config | `repo_scan_roots = focus5_scan_roots = ['~/Documents/GitHub-Repos']`; mode `dirty_first` | scope = one root |
| 2 | `ls -ld` the root | `GitHub-Repos` is a **symlink → `GH Repos`** | path mismatch **ruled out** |
| 3 | Roster table | 5 dirty repos, `computed_at = 2026-06-19T06:12:45Z` (≈11h before the screenshot) | roster is a **stale snapshot** |
| 4 | Are the active repos discovered? | `giant-brains-claude-skills`, `hypercart-plugin-mkiii`, `xyz-3-agents-swarm` **all present**, all `is_dirty=0`, and the **most-recently-committed** rows in the set | discovery **ruled out** as the cause |
| 5 | `rank_dirty_first` sort_key | `(1 if at_risk else 0, _recency)` → **every dirty/unpushed repo sorts above every clean repo** | primary mechanism |
| 6 | Re-rank stored signals under `my_work` | Also surfaces dirty repos — `rank_my_work` sets `recency = max(my_last_commit_ts, now if is_dirty)`, so **dirty repos pin to "now"** | `my_work` is **not** the fix |
| 7 | Re-rank by pure `_recency` (no dirty pin) | TOP 5 = **hypercart-plugin-mkiii, wp-code-check, xyz-3-agents-swarm, giant-brains-claude-skills**, facebook-for-woocommerce | the desired view needs a **new mode** |
| 8 | Look for `rebalance-OS` in signals | Only `rebalanceos-webapp` present; `~/Documents/rebalance-OS` is **outside** the scan root | secondary discovery gap |

## Root cause — three distinct issues

### Issue A (PRIMARY) — no ranking mode surfaces "my most recent active repos"

All three existing modes bury clean-but-recently-committed repos:

- `dirty_first` (default): `sort_key = (at_risk, recency)` — **all** dirty/unpushed
  repos rank above **all** clean repos, regardless of how recently you committed.
- `my_work`: `recency = max(my_last_commit_ts, now_ts if is_dirty)` — a dirty repo
  is **pinned to "now"**, so dirty repos float to the top here too.
- `any_touch`: ranks on `index_mtime_ts` etc. — the rejected Phase-0 default that
  surfaces dormant clone/fetch activity.

A **commit-often / push-often** workflow keeps active repos **clean**
(`is_dirty=0`, nothing unpushed). Under every mode, clean repos lose to any repo
with leftover uncommitted/untracked files — so the genuinely active work is
invisible and stale repos with forgotten WIP fill the roster. Ledger #7 used
`_recency` as a quick *exploratory* rerank to demonstrate the **shape** of the
fix (recency-first, no dirty pin) — it surfaced the right repos, but `_recency`
is **not** the implementation contract: it falls back to
`head_reflog_ts`/`last_commit_ts` (`focus5_scan.py:142-149`) and would admit
foreign-push/clone activity. The actual fix ranks on **`my_last_commit_ts`**
(operator-*authored* recency) — see the contract below and Phase 1.

### Issue B (CONTRIBUTING) — the roster is a frozen snapshot

`computed_at` is stamped by `sync_focus5()` when it writes `focus5_roster`. The
shown value (`06:12:45Z`) was produced by a manual `?refresh=1` during this
debugging session — nothing has recomputed it since, because:

- Focus 5 is **opt-in** (`included_in_all=False` in `index_ops.py`) → it is **not
  in any scheduled sync** (daily/vault/github), so no unattended job refreshes it.
- The recent fix (`fix/focus5-no-blocking-scan`, merged PR #72) **removed the
  on-view stale recompute** to stop the 36s page hang — correct for latency, but
  it means the only remaining refresh path is the manual **↻ Refresh** button.

Net: the roster freezes until someone clicks Refresh. Even the *correct* ranking
mode would display stale repos. The two issues compound: **stale + wrong-mode**.

### Issue C (SECONDARY) — `rebalance-OS` is outside the scan root

`rebalance-OS` lives at `~/Documents/rebalance-OS`, not under the
single scan root `~/Documents/GH Repos`. It is never discovered, so
it cannot appear in Focus 5 under any mode. (One of the four named active repos.)

## What Focus 5 is *supposed* to surface (product decision)

Per operator intent: **Focus 5 = my 5 most recently active repos** (what I'm
working on right now), ranked by operator-authored commit recency — clean,
freshly-pushed repos included. The current "dirty-first" behavior is a *separate*
safety lens. Adopt the operator's framing:

- **Focus 5** (default, headline view): most recent operator activity ranked by
  **`my_last_commit_ts`** (operator-*authored* commit recency). Answers "what am
  I working on?"
- **Dirty Five** (secondary safety view): the existing `dirty_first` behavior —
  repos with at-risk uncommitted/unpushed work. Answers "what might I lose?"

**Authored-commit contract (relay r2 decision).** "Recency" here means
`my_last_commit_ts` specifically — **not** the `_recency()` helper, which falls
back to `head_reflog_ts`/`last_commit_ts` and would let a foreign-push or
clone/checkout masquerade as my activity. A **dirty repo with no operator commit
must NOT outrank a clean repo with a recent operator commit** — that would
reintroduce the bug under a new name. Such dirty-only/no-authored repos are
**excluded** from Focus 5 and carried by Dirty Five + the off-roster "needs
attention" strip.

## Remediation plan

### Phase 1 — Add a recency ranking mode (the real fix)

- [x] Add `rank_recent_activity(s, now)` to `focus5_scan.py`:
      `sort_key = (s.my_last_commit_ts or 0,)` — rank on **authored** recency, NOT
      `_recency()` (which would admit foreign-push/clone activity). **No dirty
      pinning.** Eligibility = `s.my_last_commit_ts is not None` (authored a commit
      here) — this **excludes** dirty-only/no-authored repos from Focus 5 (they
      remain in Dirty Five + the off-roster strip). reason = `"your commit {ago}"`.
      *(Fixes relay r2 [Blocker] #1 — `_recency`/`_eligible_as_my_work` contradicted the product contract.)*
- [x] Register in `RANKING_STRATEGIES` as `"recent_activity"`
- [x] **Flip the runtime default in `config.py::get_focus5_ranking_mode()`** —
      getter now returns `recent_activity` on unset; explicit `focus5_ranking_mode`
      still wins; `DEFAULT_RANKING_MODE` constant pointed at the same value with a
      lockstep comment. *(Fixes relay r2 [Blocker] #2.)*
- [x] Unit tests: clean-recent-authored repo outranks an older clean-authored repo;
      a dirty/no-authored repo is **absent** from `recent_activity` (and present in
      `dirty_first`)

**QA — Phase 1**
- [x] Re-ranking the current stored signals under `recent_activity` yields
      hypercart-plugin-mkiii / xyz-3-agents-swarm / giant-brains in the top 5
      *(verified live: all three present, plus rebalance-OS #1 and wp-code-check #5)*
- [x] Dirty-only/no-authored repo (`eve`, `my_last_commit_ts=None`) does
      **not** appear in `recent_activity`, but still appears in `dirty_first`
      *(verified live: `eve` is Dirty Five #5, absent from Focus 5)*
- [x] Default resolution: unset config → `get_focus5_ranking_mode()` returns
      `recent_activity`; explicit `focus5_ranking_mode=dirty_first` config still wins
- [x] Ordering is deterministic — `rank_repos()` already sorts score-desc then
      `local_path`, so equal-recency ties are stable
- [x] `dirty_first` + `my_work` unchanged (no regressions — existing tests green)
- [x] Pure function preserved (no I/O / clock inside the strategy)

### Phase 2 — Two views in the web UI

- [x] Default `/focus-5` → `recent_activity` mode, titled **Focus 5**
- [x] Add **Dirty Five** as a second view — a mode toggle on the same page
      (`?view=dirty`) → `dirty_first` mode
- [x] **Persistence model (relay r2 [Should]):** the second view is a **transient
      mode param** — `summarize_focus5(mode="dirty_first")` re-ranks the cached
      `focus5_repo_signals` **in memory** and renders without writing
      `focus5_roster`. (Implemented as a read-side rerank rather than
      `rerank_focus5_from_cache`, which persists — so the default roster is provably
      untouched.) Verified live: after Dirty Five, the persisted roster mode is
      still `recent_activity` and the top repo is still rebalance-OS.
- [x] Reuse the existing `_focus5_body` renderer for both (only mode + title +
      toggle differ); keep the "⚠ stale" badge and ↻ Refresh on both

**QA — Phase 2**
- [x] Switching views does **not** call `sync_focus5()` / does not rescan the whole
      device — it reranks from cached `focus5_repo_signals`. (Per-card *live tree
      health* is still re-probed on render by design — `with_live_health=True` — that
      is expected, not a regression.) *(Fixes relay r2 [Blocker] #3.)* Route test
      `test_dirty_view_renders_transiently_without_resync` asserts no `sync_focus5`.
- [x] After visiting **Dirty Five**, reloading `/focus-5` still defaults to
      `recent_activity` (transient param did not mutate the persisted roster)
- [x] Off-roster "needs attention" strip still reflects dirty/unpushed repos

### Phase 3 — Freshness (so the roster stops rotting)

**Decision (2026-06-19): scheduled refresh (option a).** Background-on-view (b)
was rejected to avoid thread/race complexity in the web process.

- [x] Add `focus5` to a launchd cadence — **piggybacked on hourly `github-sync`**
      (operator's choice over a standalone job): `github_sync.sh` scope is now
      `["github", "focus5"]`. Non-blocking page from PR #72 preserved.
- [x] Cadence vs ~30s scan cost decided — hourly (git-only, no network); wired
      through `SCHEDULER.md` policy table + freshness-model note + the
      `test_scheduler_policy.py` mirror. No new wrapper/plist/installer (piggyback).
- [x] The page never blocks on the scan — this job is the background writer; the
      route still serves the cached roster instantly (PR #72 behavior untouched).

**QA — Phase 3**
- [~] After a normal day, the roster `computed_at` is < cadence old without anyone
      clicking Refresh — **will hold once `github-sync` is installed** (`bash
      scripts/install_github_scheduler.sh`); no rebalance launchd jobs are loaded
      on this box right now, so the unattended recompute isn't firing yet.
- [x] Page load stays fast even when a scheduled scan is mid-flight — the route
      reads the persisted roster; it never awaits a scan (PR #72).

### Phase 4 — Discovery scope (`rebalance-OS`)

- [x] Add `~/Documents/rebalance-OS` to `focus5_scan_roots`. Added
      `set/add/remove_focus5_scan_root` setters + `rebalance config
      {add,remove,list}-focus5-scan-root` CLI, then registered the root in the live
      (gitignored) `temp/rbos.config`. The `add` seeds from the effective roots so
      the existing `GitHub-Repos` scope is preserved, not replaced. *(Fixes relay r2
      [Should].)*
- [x] Verify discovery handles a scan root that is itself a repo (`.git` at root) —
      `iter_git_repos` yields the root and stops at its boundary; pinned by
      `test_root_that_is_itself_a_repo_is_discovered`.
- [x] Confirm `rebalance-OS` appears under `recent_activity` — verified live: it is
      **#1** ("your commit 2m ago").

**QA — Phase 4**
- [x] `refresh_index(scope=["focus5"], dry_run=True)` lists `rebalance-OS` among
      `scan_roots` (and confirms `ranking_mode=recent_activity`).
- [x] No accidental broadening — only the one explicit root was added; the roster
      is still the top-5 active repos (the extra root only adds rebalance-OS itself).
- [x] `rebalance-OS` shows with correct branch/ahead-behind enrichment (Dirty Five
      shows it "4 unpushed commit(s)"); PR enrichment is corpus-dependent as designed.

## Notes

- The merged non-blocking fix (PR #72) is correct and stays — Phase 3 is its
  freshness companion, not a revert.
- Issues A and C are independent: fixing the mode (A) still won't show
  `rebalance-OS` until the scan scope (C) includes it.

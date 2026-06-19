---
title: "Focus 5 surfaces the wrong repos — root-cause trace + remediation"
doc_type: bug-trace + remediation-plan
status: diagnosed (2026-06-19) · remediation NOT started
method: /debug-mantra (reproduce → fail path → falsify → cross-reference)
owner: noel@neochro.me
related:
  - PROJECT/2-WORKING/FOCUS-5.md  (original spike/design)
  - src/rebalance/ingest/focus5_scan.py  (ranking + scan)
  - src/rebalance/web.py  (focus5_page route)
---

# Focus 5 surfaces the wrong repos

| Most recently completed | What's next |
|---|---|
| **Diagnosis complete** (2026-06-19) — root cause proven by re-ranking stored signals; 3 distinct issues isolated | **Phase 1 — add a recency ranking mode** (the real fix), pending approval |

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
| 1 | Read scan-root config | `repo_scan_roots = focus5_scan_roots = ['/Users/noelsaw/Documents/GitHub-Repos']`; mode `dirty_first` | scope = one root |
| 2 | `ls -ld` the root | `GitHub-Repos` is a **symlink → `GH Repos`** | path mismatch **ruled out** |
| 3 | Roster table | 5 dirty repos, `computed_at = 2026-06-19T06:12:45Z` (≈11h before the screenshot) | roster is a **stale snapshot** |
| 4 | Are the active repos discovered? | `giant-brains-claude-skills`, `hypercart-plugin-mkiii`, `xyz-3-agents-swarm` **all present**, all `is_dirty=0`, and the **most-recently-committed** rows in the set | discovery **ruled out** as the cause |
| 5 | `rank_dirty_first` sort_key | `(1 if at_risk else 0, _recency)` → **every dirty/unpushed repo sorts above every clean repo** | primary mechanism |
| 6 | Re-rank stored signals under `my_work` | Also surfaces dirty repos — `rank_my_work` sets `recency = max(my_last_commit_ts, now if is_dirty)`, so **dirty repos pin to "now"** | `my_work` is **not** the fix |
| 7 | Re-rank by pure `_recency` (no dirty pin) | TOP 5 = **hypercart-plugin-mkiii, wp-code-check, xyz-3-agents-swarm, giant-brains-claude-skills**, facebook-for-woocommerce | the desired view needs a **new mode** |
| 8 | Look for `rebalance-OS` in signals | Only `rebalanceos-webapp` present; `/Users/noelsaw/Documents/rebalance-OS` is **outside** the scan root | secondary discovery gap |

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
invisible and stale repos with forgotten WIP fill the roster. Ranking by pure
operator-commit recency (`_recency`, no dirty pin) surfaces exactly the right
repos (ledger #7).

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

`rebalance-OS` lives at `/Users/noelsaw/Documents/rebalance-OS`, not under the
single scan root `/Users/noelsaw/Documents/GH Repos`. It is never discovered, so
it cannot appear in Focus 5 under any mode. (One of the four named active repos.)

## What Focus 5 is *supposed* to surface (product decision)

Per operator intent: **Focus 5 = my 5 most recently active repos** (what I'm
working on right now), ranked by operator-authored commit recency — clean,
freshly-pushed repos included. The current "dirty-first" behavior is a *separate*
safety lens. Adopt the operator's framing:

- **Focus 5** (default, headline view): most recent operator activity by commit
  recency. Answers "what am I working on?"
- **Dirty Five** (secondary safety view): the existing `dirty_first` behavior —
  repos with at-risk uncommitted/unpushed work. Answers "what might I lose?"

## Remediation plan

### Phase 1 — Add a recency ranking mode (the real fix)

- [ ] Add `rank_recent_activity(s, now)` to `focus5_scan.py`:
      `sort_key = (_recency(s),)`, **no dirty pinning**; eligibility =
      `_eligible_as_my_work(s)`; reason = `"your commit {ago}"` (or
      `"uncommitted changes"` when dirty but use the honest `_recency`, not `now`)
- [ ] Register in `RANKING_STRATEGIES` as `"recent_activity"`
- [ ] Set `DEFAULT_RANKING_MODE = "recent_activity"` (and/or set the operator's
      `focus5_ranking_mode` config) so the headline view is recency by default
- [ ] Unit tests: clean-but-recent repo outranks an older dirty repo; dirty repo
      with no commits still eligible via `_recency` fallback

**QA — Phase 1**
- [ ] Re-ranking the current stored signals under `recent_activity` yields
      hypercart-plugin-mkiii / xyz-3-agents-swarm / giant-brains in the top 5
- [ ] `dirty_first` + `my_work` unchanged (no regressions to existing modes)
- [ ] Pure function preserved (no I/O / clock inside the strategy)

### Phase 2 — Two views in the web UI

- [ ] Default `/focus-5` → `recent_activity` mode, titled **Focus 5**
- [ ] Add **Dirty Five** as a second view (separate nav item or a mode toggle on
      the same page) → `dirty_first` mode
- [ ] Reuse the existing `_focus5_body` renderer for both (only the mode + title
      differ); keep the "⚠ stale" badge and ↻ Refresh on both

**QA — Phase 2**
- [ ] Both views render; switching does not re-probe (re-rank from cache)
- [ ] Off-roster "needs attention" strip still reflects dirty/unpushed repos

### Phase 3 — Freshness (so the roster stops rotting)

**Decision (2026-06-19): scheduled refresh (option a).** Background-on-view (b)
was rejected to avoid thread/race complexity in the web process.

- [ ] Add `focus5` to a launchd cadence (e.g. hourly, or piggybacked on an
      existing sync) so the roster recomputes unattended; keep the non-blocking
      page from PR #72
- [ ] Decide cadence vs the ~36s scan cost (hourly is fine; it only re-probes
      git, no network) and wire it through `SCHEDULER.md` policy + a wrapper
      script if a standalone job
- [ ] The page must never block on the scan (preserve PR #72's behavior)

**QA — Phase 3**
- [ ] After a normal day, the roster `computed_at` is < the chosen cadence old
      without anyone clicking Refresh
- [ ] Page load stays fast even when a scheduled/background scan is mid-flight

### Phase 4 — Discovery scope (`rebalance-OS`)

- [ ] Add `rebalance-OS` to the scan set — simplest: `rebalance config` add
      `/Users/noelsaw/Documents/rebalance-OS` (a root that is itself a repo) to
      `focus5_scan_roots` (verify discovery handles a root that is a repo)
- [ ] Confirm `rebalance-OS` then appears under `recent_activity` (it has very
      recent operator commits)

**QA — Phase 4**
- [ ] No accidental broadening that pulls in dozens of unrelated repos
- [ ] `rebalance-OS` shows with correct branch/ahead-behind/PR enrichment

## Notes

- The merged non-blocking fix (PR #72) is correct and stays — Phase 3 is its
  freshness companion, not a revert.
- Issues A and C are independent: fixing the mode (A) still won't show
  `rebalance-OS` until the scan scope (C) includes it.

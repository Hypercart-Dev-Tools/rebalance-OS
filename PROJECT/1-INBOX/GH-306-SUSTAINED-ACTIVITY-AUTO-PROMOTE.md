---
gh_issue: 306
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/306
title: "GH-306 sustained-activity auto-promotion"
status: "Moved to HiQS-Suite/rebalanceOS#1 — this repo is retiring (see #291); no longer live here"
created: 2026-08-16
updated: 2026-08-16
owner: noel
doc_type: feature
goal: >
  Replace the commit-only auto-promote threshold with a multi-signal, sustained-activity
  threshold (5+ qualifying actions, proven across two real wall-clock observations) so a
  repo joins permanent low-maintenance watch status on real engagement — not a single
  burst, and never from merely forking/cloning with no activity.
effort: 3
complexity: 3
risk: 3
phases: 3
ratings_provisional: true
roadmap_exempt: false
---

# GH-306 — Sustained-Activity Auto-Promotion

> **Moved to `HiQS-Suite/rebalanceOS#1`** / `PROJECT/1-INBOX/GH-1-SUSTAINED-ACTIVITY-AUTO-PROMOTE.md`
> in the new repo — this repo is being retired (see #291). This copy is kept only as a historical
> record; do not pick up work from here.

## Status

| What was just completed | What's next |
|---|---|
| Consult (Codex + agy, relay-xyz `consult.sh`) on the v1.0 draft — full transcripts at `relay-system/2026-08-16/gh306-consult-085839/`. Both advisors independently converged: proposed design has a verified Blocker (burst-guard is a no-op) and a verified regression (drops cloud-agent commit credit). Plan revised below; ratings bumped 2/2/2 → 3/3/3 per both advisors' independent convergence. | Re-triage (clear `ratings_provisional` on the revised design), then Phase 0 spike below before implementation |

## Why

Rebalance already auto-promotes repos into permanent `project_registry` membership via
`sync_commit_threshold_promotions()` ([`project_inference.py:911`](../../src/rebalance/ingest/project_inference.py#L911)),
gated by `auto_promote_enabled` / `auto_promote_commit_threshold` (default 3,
[`config.py:968`](../../src/rebalance/ingest/config.py#L968)). It runs on every `refresh_index()`
call — no dedicated cron needed. This is the mechanism to extend, not replace wholesale (PDDA
Phase 0 rule: don't build a redundant solution when extending an existing one is viable).

**Confirmed gaps** (see [Phase 0](#phase-0--prior-art-review) for citations):

1. **Commit-only.** The function counts distinct-SHA operator commits only. `github_activity`
   already has `prs_opened`, `prs_merged`, `issues_opened`, `issue_comments`, `reviews` columns —
   collected today, summed today by `_activity_repos()` for a *different* purpose (the 14-day
   watched-set union) — but never read by the promotion path.
2. **No burst guard.** 3 commits pushed in one sitting promotes identically to 3 commits spread
   across a month. "Sustained" isn't checked.
3. **Fork/clone-only already correctly excluded.** `test_fork_with_zero_operator_commits_never_promotes`
   ([`test_auto_promote.py:126`](../../tests/test_auto_promote.py#L126)) confirms a fork with zero
   operator-authored GitHub events never promotes today — this generalizes for free under the new
   multi-signal tally, since a bare fork still produces zero `github_activity` rows.

## Non-goals (v1.0)

Explicitly deferred — not designed or built in this pass:

- **Demotion / cooldown** for promoted repos that later go quiet. Today's promotion is monotonic
  (no un-promote code exists anywhere); this proposal keeps that posture rather than reversing it.
  A quiet-repo demotion policy is a separate, larger design (what counts as "quiet"? does it ever
  un-collect history?) that deserves its own doc.
- **New visibility surface.** `log_project_auto_promoted()` already writes into the auth log and
  renders on the dashboard as a notice (`"project_auto_promoted": ("ok", "✓ project auto-added")`,
  [`web.py:226`](../../src/rebalance/web.py#L226)). Reused as-is — no new UI/notification work.
- **Watched-set window reconciliation.** `get_watched_repos()`'s 14-day `activity`/`pushed` buckets
  and the permanent `project_registry` promotion are independent today and stay independent.
- **Events-API collection blind spot** (the ~300-event/90-day GitHub API cap). A data-collection
  concern, not a promotion-logic concern.
- **Retroactive re-evaluation** of already-promoted repos against the new threshold. Existing
  `project_registry` rows are untouched — promotion has always been monotonic/one-way.
- **Type-diversity requirement** (e.g. "must include at least one non-commit action"). v1.0 treats
  all six action types as equal-weight; a repo could still promote on 5 commits alone, as long as
  they span ≥2 days. Revisit only if the burst guard proves insufficient in practice.

## Table of contents

- [Phase 0 — Prior art review](#phase-0--prior-art-review)
- [Consult findings (2026-08-16)](#consult-findings-2026-08-16)
- [Phase 1 — Multi-signal tally + burst guard (revised)](#phase-1--multi-signal-tally--burst-guard-revised)
- [Phase 2 — Config, migration, tests](#phase-2--config-migration-tests)

## Phase 0 — Prior art review

**Existing layer:** `sync_commit_threshold_promotions()` + `_count_operator_commits()`
(`project_inference.py:793,911`), called from `refresh_index()`
([`index_ops.py:1160`](../../src/rebalance/ingest/index_ops.py#L1160)), gated by
`get_auto_promote_config()` (`config.py:968`). Writes only to the SQLite `project_registry` table
via `sync_db()` upsert ([`registry.py:165`](../../src/rebalance/ingest/registry.py#L165)) — never
to `Projects/00-project-registry.md`.

**Why extend, not replace:** the trigger point (piggyback on `refresh_index()`, zero new cron), the
write path (`project_registry` upsert), the ignore-list override (`github_ignored_repos` always
wins, enforced upstream in `get_watched_repos()`), and the "no GitHub login → no-op" guard are all
correct and reusable. Only the **counting logic** (`_count_operator_commits`) and the **threshold
semantics** change. This keeps the diff small: one new tally function, one new day-spread check,
one config key, no new tables, no new collector.

**Data already available, no new collection needed:** `github_activity` rows are per
`(repo_full_name, scan_date, login)` with columns `commits, pushes, prs_opened, prs_merged,
issues_opened, issue_comments, reviews` — the same set `_activity_repos()`
([`index_ops.py:870`](../../src/rebalance/ingest/index_ops.py#L870)) already sums to decide 14-day
"watched" membership. This proposal reads the same table for a different (all-time, gated) purpose.

## Consult findings (2026-08-16)

Ran via relay-xyz's `consult.sh` (Codex + agy, parallel, isolated worktree, advisory-only) against
the original v1.0 draft below. Both raised distinct issues; both were verified directly against
source before being folded in (not taken on trust). Full transcripts:
`relay-system/2026-08-16/gh306-consult-085839/{gh306-consult.codex.md,gh306-consult.agy.md}`.

**[Blocker, Codex — verified] `COUNT(DISTINCT scan_date)` does not measure activity spread; it's a
no-op burst guard.** `_fetch_events()` ([`github_scan.py:209`](../../src/rebalance/ingest/github_scan.py#L209))
pulls a rolling 30-day event window on **every** scan call. `_summarize_by_repo()`
([`github_scan.py:256`](../../src/rebalance/ingest/github_scan.py#L256)) sums the *entire* fetched
window into one `RepoActivity` with no per-event-day bucketing at all. `upsert_github_activity()`
([`github_scan.py:498`](../../src/rebalance/ingest/github_scan.py#L498)) then writes that whole-window
sum into **today's** row (`scan_date = scanned_at[:10]`). Net effect: a single burst of 5 actions on
Monday reappears in the 30-day window on every subsequent day's scan, so it gets re-summed into
Tuesday's row, Wednesday's row, etc., for weeks. `COUNT(DISTINCT scan_date) >= 2` therefore becomes
true the day after *any* burst, from pure rescanning — exactly the "5 things in one sitting" case
the whole proposal exists to block. Confirmed directly against the code above; the original design
would have shipped a non-functional burst guard while looking tested.

**[Blocker, agy — verified] Drops cloud-agent commit credit, regresses GH-124.**
`_count_operator_commits()` ([`project_inference.py:793`](../../src/rebalance/ingest/project_inference.py#L793))
deliberately combines `github_activity.commits` (operator, via the events feed) **with**
`github_commits` rows authored by `CLOUD_AGENT_AUTHORS` (bot/PR-commit-only signal) — its own
docstring cites this as a prior cross-model-QA fix (GH-124). The original Phase 1 draft here read
only `github_activity`, silently dropping bot-commit credit and failing
`test_cloud_agent_commits_count_toward_threshold` ([`test_auto_promote.py:139`](../../tests/test_auto_promote.py#L139)).

**[Should, Codex — verified] Provenance/notice payload is commit-typed, not generic.**
`_repo_to_promoted_row()` hardcodes `generated_by: COMMIT_THRESHOLD_GENERATED_BY` and
`commit_count` into `project_registry.custom_fields` ([`project_inference.py:864-890`](../../src/rebalance/ingest/project_inference.py#L864));
`log_project_auto_promoted()` takes `commit_count` as a named kwarg
([`auth_log.py:329`](../../src/rebalance/ingest/auth_log.py#L329)). `COMMIT_THRESHOLD_GENERATED_BY`
is also one of exactly two entries in `_MACHINE_OWNED_MARKERS`
([`project_inference.py:69-70`](../../src/rebalance/ingest/project_inference.py#L69)), which gates
whether a row is recognized as machine-owned — a new marker must be **added** to that set, not swap
out the old one, or existing promoted rows stop being recognized as machine-owned.

**[Should, Codex — verified] "Existing dashboard notice" is actually the `/auth-log` System Log
page**, not the main dashboard: `web.py:226` only supplies the badge label; it renders at
`auth_log_page()` ([`web.py:1668`](../../src/rebalance/web.py#L1668)), a separate page. The claim
that no new visibility work is needed still holds — just correcting where it surfaces.

**Both advisors independently converged** on: keep the 5-action / (revised) 2-observation
threshold numbers, omit `pushes` from the sum (already implied by `commits`), don't add a
type-diversity requirement, and bump ratings to **effort 3 / complexity 3 / risk 3** (from the
original 2/2/2) — the burst-guard fix requires new persisted state, not just a wider SQL SELECT.

## Phase 1 — Multi-signal tally + burst guard (revised)

The distinct-day mechanism is dropped entirely (see Blocker above) and replaced with a
**two-observation, wall-clock-time gate** — no per-event-date storage needed, one small new table:

- [ ] New table `auto_promote_watch (repo_full_name TEXT PRIMARY KEY, first_seen_over_threshold_at
      TEXT NOT NULL, action_count_at_first_seen INTEGER NOT NULL)`.
- [ ] New function `_count_operator_actions(db, repo, login) -> int`, combining both signals like
      `_count_operator_commits` does today:
      `SELECT SUM(commits + prs_opened + prs_merged + issues_opened + issue_comments + reviews)
      FROM github_activity WHERE repo_full_name = ? AND login = ?` (operator, all-time cumulative,
      same as today) **plus** `COUNT(DISTINCT sha) FROM github_commits WHERE repo_full_name = ? AND
      author_login IN (CLOUD_AGENT_AUTHORS)` (bot commits, unchanged from today).
- [ ] Promotion predicate, evaluated each `refresh_index()` run:
      - If `action_count < auto_promote_action_threshold` (default 5): no-op, clear any stale
        `auto_promote_watch` row for this repo (activity can still dip below before promoting).
      - If `action_count >= threshold` and no `auto_promote_watch` row exists yet: insert one
        (`first_seen_over_threshold_at = now`, records the count) — **do not promote yet**.
      - If a row exists and `now - first_seen_over_threshold_at >= 20h`: promote. The 20h floor
        (not a full 24h) tolerates the daily collector's natural run-time drift while still
        guaranteeing two genuinely separate days' worth of operator behavior — a single sitting,
        however long, cannot satisfy it since it requires two separate `refresh_index()` calls.
      - If a row exists but `< 20h` has elapsed: no-op, wait for the next refresh.
- [ ] Everything else downstream unchanged: `sync_db()` upsert, `auto_promote_enabled` /
      ignored-repo gating, "no GitHub login → no-op", monotonic (no demotion).

**QA gate:** unit tests below green; `rebalance doctor` clean; no change to any currently-promoted
row (verify via a snapshot diff of `project_registry` before/after on a repo with existing fixture
data).

## Phase 2 — Config, migration, tests

- [ ] Rename `auto_promote_commit_threshold` → `auto_promote_action_threshold` (default `5`) in
      `get_auto_promote_config()` (`config.py:968`). New key wins if both are set; a deprecated-key
      log line fires when only the old key is present — this is a **migration compatibility
      fallback**, not semantic preservation (a user-configured "3 commits" becomes "3 mixed
      actions," a real behavior change, not an equivalent re-expression — call this out to the
      operator once via the deprecation log rather than silently reinterpreting their old value).
- [ ] Add `activity_threshold_v1` to `_MACHINE_OWNED_MARKERS`
      (`project_inference.py:70`) **alongside**, not replacing, `commit_threshold_v1` — existing
      promoted rows must stay recognized as machine-owned.
- [ ] Update `_repo_to_promoted_row()` (`project_inference.py:864`) to accept/write generic
      `action_count` instead of `commit_count` in `custom_fields.inference`, and
      `generated_by: "activity_threshold_v1"` for newly-promoted rows.
- [ ] Update `log_project_auto_promoted()` (`auth_log.py:329`) kwarg from `commit_count` to
      `action_count` (grepped: no other reader depends on this field's name outside
      `project_inference.py`/`auth_log.py`/`test_auto_promote.py`).
- [ ] Update `sync_commit_threshold_promotions()` → rename to `sync_activity_threshold_promotions()`
      (the old name becomes misleading); update its one call site (`index_ops.py:1160`) and its
      docstring's "Writes only via the existing machine_owned partition/write path" framing.
- [ ] New/updated tests in `tests/test_auto_promote.py` (extend, don't replace — keep passing:
      `test_fork_with_zero_operator_commits_never_promotes`,
      `test_ignored_repo_never_promotes`, `test_curated_row_never_touched`,
      `test_idempotent_rerun_does_not_duplicate`, `test_disabled_is_a_no_op`,
      `test_no_github_login_configured_is_a_no_op`,
      `test_cloud_agent_commits_count_toward_threshold` — must still pass unmodified):
      - `test_promotes_on_mixed_signal_types` — 2 issues + 2 comments + 1 PR review (no commits at
        all) crosses threshold, then promotes after the 20h gate clears on a second refresh.
      - `test_single_sitting_does_not_promote_immediately` — 5+ actions observed on one
        `refresh_index()` call inserts an `auto_promote_watch` row but does **not** promote yet.
      - `test_promotes_after_20h_second_observation` — same repo, a second `refresh_index()` call
        ≥20h later with the count still ≥ threshold promotes.
      - `test_second_observation_before_20h_does_not_promote` — second call at +2h does not promote.
      - `test_count_dropping_below_threshold_clears_watch_row` — count dips below threshold between
        two observations; the `auto_promote_watch` row is cleared, no promotion on eventual re-cross.
      - `test_below_action_threshold_never_creates_watch_row` — 4 actions total never inserts into
        `auto_promote_watch`.
      - `test_legacy_commit_threshold_key_still_read` — old config key honored (with deprecation
        log) if new key absent.
      - `test_existing_commit_threshold_v1_rows_still_recognized_machine_owned` — a row promoted
        under the old marker is still treated as machine-owned after this change.
- [ ] `rebalance doctor` + `pytest tests/test_auto_promote.py -v` green before marking done.

**QA gate:** full `pytest tests/` green (not just the one file — this touches a shared call site
in `refresh_index()`); `utils/pdda/pdda.sh frontmatter` clean on this doc once promoted to
`2-WORKING`.

## Lessons Learned (For Future Agents)

_(fill in before moving to `PROJECT/3-COMPLETED`)_

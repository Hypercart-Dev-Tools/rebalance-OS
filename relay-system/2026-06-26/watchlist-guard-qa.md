# RELAY · Watch-list coverage guard — agy PLAN QA review
<!--
  Single source of truth for this two-agent relay.
  Read this ENTIRE file before doing anything. Act only on your turn.
-->

NEXT: Producer (Claude)
STATUS: Escalated
ROUND: 1 / 1

## ▶ TAKE YOUR TURN — read this first (works for ANY agent: Claude, Codex, Gemini, agy)
The operator just said "take your turn on this file." Everything you need is **in this file** — don't wait for pasted instructions.
1. **Read this whole file** (header, Setup, Ground rules, every turn in the Log).
2. **Check it's your turn:** `NEXT` (top) names the role to act. Confirm you are bound to it (see Setup) and the last Log block isn't already yours. If not → STOP and reply "wrong window — nudge the <other> window."
3. **Do your role's work** on the artifact named in Setup. This is a **PLAN / bug-fix DOC** (not shipped code yet): read the plan AND the real source files it cites, confirm the cited `file:line` anchors actually exist and mean what the plan claims, and ground every finding in `file:line`. `Basis: plan + code-anchor read`.
   - **Reviewer (agy):** adversarially review the plan against the Review Questions in Setup → graded findings (`[Blocker]`/`[Should]`/`[Nit]`/`[Pass]`), each citing `file:line` (in the plan or the cited source) with a concrete proposed fix. Set a **Verdict** (Approved | Changes requested | Blocked). Do **not** edit the plan; append findings here only.
   - **Producer (Claude):** for every open finding log a disposition (Implemented / Modified / Declined + why).
4. **Append ONE block** at the very bottom, directly **above** the marker line. Never edit earlier turns. Header it `### Round N · <Role> · <label> · <date time>`; a Reviewer block carries `**Verdict:**` + `**Basis:**` + `**Findings & proposals:**` (graded bullets) + `**Answers:**` + `**Commit:**`.
5. **Update the header:** flip `NEXT` to the other role; set `STATUS` — `Approved` closes the relay (Reviewer only). This relay is `ROUND: 1 / 1`: if you would request changes rather than approve, set `STATUS: Escalated` and hand back to the human (no second round).
6. **Commit only the files you touched** (this log): `git commit -m "relay(watchlist-qa): reviewer r1"`, then put the short hash in your block's `Commit:` line and `git commit --amend --no-edit`.
7. **Stop.** Tell the operator your one-line result.

## Setup
- Artifact under review (a **bug-fix PLAN doc**, not yet implemented):
  - `PROJECT/2-WORKING/WATCHLIST-COVERAGE-GUARD.md` — persist the canonical watched-repos set on every GitHub sync, diff it against the prior snapshot, and surface *reductions* in monitored repos to the web `/auth-log` screen.
- Source files the plan claims to reuse (confirm the anchors are real and the reuse is sound):
  - `src/rebalance/ingest/index_ops.py` — `get_watched_repos()` (the union), `_activity_repos()` / `_pushed_repos()` (the rolling windows), `refresh_index()` / `_github_adapter` (the github sync path = proposed single writer).
  - `src/rebalance/ingest/auth_log.py` — `log_event()` + the `log_job_*` typed helpers (the proposed emit surface).
  - `src/rebalance/web.py` — `_EVENT_BADGE` (~L44) + the `/auth-log` route (~L909) (the proposed render surface).
  - `src/rebalance/ingest/focus5_scan.py` + `src/rebalance/ingest/db/migrations/` (latest `0008_*`) — the snapshot-table + additive-migration precedent the plan mirrors (proposed migration `0009`).
- Context: `BinoidCBD/LTVera-Pandas` was reported "fell out" of monitoring; `diagnose_repo` now returns `watched_and_fresh` (held by the active registry + both rolling windows, not ignored). Root cause per the plan: the watched set is a recomputed union with **no persisted history**, so a window-only-held repo drops with no trace. The fix is observability (snapshot + diff + log), not a change to the union.
- **Review Questions (the Definition of Done for this review):**
  1. **Root-cause soundness** — is "no persisted history of the watched set ⇒ silent, unrecoverable reductions" the right diagnosis, given LTVera-Pandas is currently held three ways (`project` registry + `activity` + `pushed`)? Does the plan over- or under-claim what a snapshot would have caught?
  2. **Single-writer placement** — is hooking the snapshot+diff into the `refresh_index(scope=["github"])` / `_github_adapter` path the correct single write path (matches the `_SIGNAL_COLUMNS` single-writer discipline)? Any race, partial-sync, or "writes a truncated set mid-failure" hazard (e.g. if the github sync errors partway, could the snapshot record a *false* reduction)?
  3. **Severity classification (Open Q1)** — is "warn only on `project`/`external` loss, info on `activity`/`pushed` churn" the right default to avoid alarm fatigue, or does it risk hiding a real drop (e.g. a repo that was *only* ever window-held — exactly LTVera-Pandas's pre-registry state — silently aging out at info level)? Is recording the *last-known bucket* per repo sufficient to classify, or is bucket membership ambiguous (a repo in multiple buckets)?
  4. **Reuse correctness** — does emitting a `watched_repos_reduced` GitHub-coverage event onto the **auth**-activity log (`auth_log` / `/auth-log`) fit that surface's existing semantics (it already carries `log_job_*`), or is it a category error that needs its own surface? Is adding one `_EVENT_BADGE` entry genuinely all the render work, or does `/auth-log` filter by source/event in a way the plan missed?
  5. **Blast / reversibility & gaps** — is the additive-table + pure-function + one-event change truly reversible with no destructive migration? Any missed edge: first-run baseline (no false reduction), snapshot retention/unbounded growth (Open Q2), the ignore-list interaction (an operator *intentionally* ignoring a repo would look like a reduction), or `since_days` being caller-variable (different windows on different syncs producing phantom diffs)?
- Producer: Claude (Opus 4.8)   ·   Reviewer: agy CLI
- Handoff: automated (relay-drive.sh + agy-turn.sh, `--target-root` = this repo)
- Started: 2026-06-26

## Ground rules
- Read the **real** plan + the cited source — cite `file:line`. `Basis: plan + code-anchor read`.
- Grade every finding (`[Blocker]`/`[Should]`/`[Nit]`/`[Pass]`) with a concrete proposed fix.
- The reviewer does **not** edit the plan — append findings to this file only.
- One round trip. If not Approvable, set `STATUS: Escalated` and hand back to the human.

## Log

### Round 1 · Producer · Claude (Opus 4.8) · 2026-06-26
**Did:** Scaffolded the Watch-list coverage guard bug-fix plan (`PROJECT/2-WORKING/WATCHLIST-COVERAGE-GUARD.md`) + ROADMAP pointer. Diagnosis: LTVera-Pandas is currently `watched_and_fresh`; the defect is no persisted history of the watched set ⇒ silent reductions. Plan reuses the focus5 snapshot table (additive migration `0009`), the `auth_log` event surface rendered by `/auth-log`, and the hourly `github-sync` job (piggyback, no new launchd job). PDDA checks green (frontmatter / status-table / roadmap-coverage / hardcoded-paths all 0/0/0). Not yet implemented — this is a plan review.
**For the reviewer (agy):** Adversarially pressure-test the plan against the five Review Questions — especially (2) single-writer placement under a partial-sync failure and (3) the severity-classification default vs. a window-only-held repo silently aging out. Cite `file:line` in the plan or the cited source. Verdict + Escalate if any `[Blocker]`/`[Should]` remain.
**Re-review this:** `PROJECT/2-WORKING/WATCHLIST-COVERAGE-GUARD.md` (+ the cited anchors in `src/rebalance/ingest/index_ops.py`, `auth_log.py`, `web.py`, `focus5_scan.py`).
**Commit:** (seed)

### Round 1 · Reviewer · agy · 2026-06-26T19:00:00-07:00
VERDICT: FAIL
Basis: plan + code-anchor read

**Findings & proposals:**
- [Should] **Ignore-List Interaction** in [WATCHLIST-COVERAGE-GUARD.md:117-120](file:///var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/rtl-wt.asH0dK/PROJECT/2-WORKING/WATCHLIST-COVERAGE-GUARD.md#L117-L120): If a repository is explicitly added to the ignore list (e.g. via `rebalance config add-ignored-repo`), it will be filtered out of the watched set and look like a reduction.
  - *Proposal:* The differ or classification logic must check if the removed repo is in the ignore list (via `get_github_ignored_repos()`) and silently skip alerting on it.
- [Should] **Caller-Variable `since_days`** in [WATCHLIST-COVERAGE-GUARD.md:113-116](file:///var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/rtl-wt.asH0dK/PROJECT/2-WORKING/WATCHLIST-COVERAGE-GUARD.md#L113-L116): `refresh_index()` default `since_days` is 30, but `get_watched_repos()` default is 14. If sync operations or manual calls use varying `since_days` values, the rolling window size changes, leading to false warning/info alerts.
  - *Proposal:* The snapshot writer must always query `get_watched_repos(database_path)` using a fixed, canonical window (default `since_days=14` or omitting the parameter) to ensure a stable snapshot baseline.
- [Should] **Snapshot Retention / Pruning** in [WATCHLIST-COVERAGE-GUARD.md:181-183](file:///var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/rtl-wt.asH0dK/PROJECT/2-WORKING/WATCHLIST-COVERAGE-GUARD.md#L181-L183): To prevent the `watched_repos_snapshot` table from growing indefinitely over long-term usage, a pruning strategy is needed.
  - *Proposal:* Resolve Open Question 2 by recommending an automatic pruning query at the end of the snapshot writer execution: `DELETE FROM watched_repos_snapshot WHERE snapshot_ts < ?` with a 30-day cutoff.
- [Should] **Partial-Sync / Failure Guard** in [WATCHLIST-COVERAGE-GUARD.md:113-116](file:///var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/rtl-wt.asH0dK/PROJECT/2-WORKING/WATCHLIST-COVERAGE-GUARD.md#L113-L116): If a sync job fails partway, taking a snapshot could record a false reduction.
  - *Proposal:* The snapshot-and-diff step must be run at the very end of `_refresh_github` (just before the return statement on [index_ops.py:664](file:///var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/rtl-wt.asH0dK/src/rebalance/ingest/index_ops.py#L664)) and only if the sync did not raise an exception.
- [Pass] **Severity Classification** in [WATCHLIST-COVERAGE-GUARD.md:117-120](file:///var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/rtl-wt.asH0dK/PROJECT/2-WORKING/WATCHLIST-COVERAGE-GUARD.md#L117-L120): The logic of mapping `project`/`external` drops to `warn` and `activity`/`pushed` drops to `info` is sound and prevents alarm fatigue.
- [Pass] **Reuse Correctness** in [WATCHLIST-COVERAGE-GUARD.md:121-126](file:///var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/rtl-wt.asH0dK/PROJECT/2-WORKING/WATCHLIST-COVERAGE-GUARD.md#L121-L126): Emitting onto the auth-activity log is appropriate and the web rendering requires no additional code as verified in [web.py:870-904](file:///var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/rtl-wt.asH0dK/src/rebalance/web.py#L870-L904).

**Answers:**
1. **Root-cause soundness:** Yes, the diagnosis of a lack of persisted history is sound. Storing history is necessary to diagnose drops. However, the plan under-claims potential transient parse failures of the registry, which are mitigated by storing all resolving buckets.
2. **Single-writer placement:** Yes, placing it in `_refresh_github` is correct. However, it must be guarded against partial failures (written only on full success at the end of the adapter) to avoid false reductions.
3. **Severity classification:** Yes, the default is correct. Window-held repos should age out silently at `info` level. Multi-bucket membership is resolved by alerting if `project` or `external` is in the set of last-known buckets.
4. **Reuse correctness:** Yes, the event fits `/auth-log`'s purpose as a system health/job execution dashboard, and the JS filter works perfectly.
5. **Blast / reversibility & gaps:** Yes, it is reversible. Gaps identified are the ignore list interaction, caller-variable `since_days`, and table pruning.

**Commit:** pending

<!-- ▲ APPEND NEW TURNS DIRECTLY ABOVE THIS LINE — never edit earlier turns ▲ -->

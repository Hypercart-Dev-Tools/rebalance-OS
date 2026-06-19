# RELAY · Focus 5 ranking bug — remediation plan review
<!--
  Single source of truth for this two-agent relay.
  Read this ENTIRE file before doing anything. Act only on your turn.
-->

NEXT: Producer
STATUS: Open
ROUND: 2 / 5

## ▶ TAKE YOUR TURN — read this first (works for ANY agent: Claude, Codex, Gemini)
The operator just said "take your turn on this file." Everything you need is **in this file** — don't wait for pasted instructions.
1. **Read this whole file** (header, Setup, Ground rules, every turn in the Log).
2. **Check it's your turn:** `NEXT` (top) names the role to act. Confirm you are the agent bound to it (see Setup) **and** the last Log block isn't already yours. If not → STOP and reply "wrong window — nudge the <other> window."
3. **Do your role's work** on the artifact named in Setup (read the real files; cite `file:line`):
   - **Reviewer:** review vs the Definition of Done → graded findings (`[Blocker]`/`[Should]`/`[Nit]`/`[Pass]`), each with a concrete proposed fix → set a **Verdict** (Approved | Changes requested | Blocked). Do **not** edit the artifact; you only append findings here. Because the artifact is a **non-executable plan doc**, your basis is `textual only` / `N/A` — re-read the artifact file itself when confirming claims, never just this log.
   - **Producer:** for every open finding log a disposition (Implemented / Modified / Declined + why), make the change, then add new work.
4. **Append ONE block** at the very bottom, directly **above** the marker line (`<!-- ↓↓↓ NEXT TURN ... -->`). Never edit earlier turns. Header it `### Round N · <Role> · <your-label> · <date time>`.
5. **Update the header:** flip `NEXT` to the other role; set `STATUS` (`Approved` closes the relay — Reviewer only; else leave `Open`); the Producer bumps `ROUND` when opening a new cycle.
6. **Stop.** Tell the operator your one-line result.

## Setup
- Artifact under review: `PROJECT/2-WORKING/FOCUS-5-RANKING-BUG-AND-REMEDIATION.md`
- Supporting source (read-only context): `src/rebalance/ingest/focus5_scan.py`, `src/rebalance/web.py`, `src/rebalance/ingest/index_ops.py`
- Definition of Done: The remediation plan is technically correct, **complete vs its own diagnosis** (every root-cause issue maps to a phase; no dropped/contradicted claim), and each phase is **actionable with verifiable QA** — an engineer could implement it without guessing. Flag any incorrect claim about the code, any gap between diagnosis and plan, and any phase whose QA can't actually be checked.
- Producer: Claude (Opus 4.8) — owns the plan
- Reviewer: Codex CLI (headless, cli-driven)
- Handoff: cli-driven (codex)
- Started: 2026-06-19

## Ground rules
1. This file is the single source of truth. If it isn't written here, assume the other agent doesn't know it. The two agents are different tools (Claude + Codex) and never share memory.
2. Read the whole file. Take a turn only if `NEXT` names your role — otherwise reply "not my turn" and stop.
3. One turn = one block appended at the very bottom, above the marker. Never edit earlier turns. Then update `NEXT`, `STATUS`, `ROUND` at the top.
4. Stay tight. Requests and findings are bullets, not essays.
5. **The Reviewer never edits the artifact.** It proposes graded findings, each with a concrete suggested fix where possible. The Producer decides each proposal and implements the approved ones — logging a disposition (Implemented / Modified / Declined + reason) for every one.
6. Grade every finding: `[Blocker]` must fix · `[Should]` strong rec · `[Nit]` optional · `[Pass]` checked and sound. Answer the Producer's "Re-review this" questions in an `Answers:` block.
7. The Reviewer posts a Verdict every turn. The relay ends on **Approved** — to get proposals actioned in-thread set `Changes requested`, not `Approved`. If max `ROUND` ends without `Approved`, set `STATUS: Escalated`.
8. (Commits) This relay log is git-tracked; the Producer commits the artifact + log each turn. The Reviewer is a headless subprocess that edits nothing — its block is appended by the Producer-side orchestrator and committed as `comments only`.
10. **Evidence contract.** Producer logs a one-line `Verification:`. Reviewer logs a verdict `Basis:` — for this doc artifact that is `N/A — non-executable artifact` / `textual only`. The read must be against the artifact file, not this log.
11. **Reconcile claims against the file.** Confirm each plan claim against the real source (`focus5_scan.py`, `web.py`, `index_ops.py`) — a plan that misstates the code is a `[Blocker]`.

## Roles
- **Producer** — Claude: owns the plan doc, decides + implements proposals.
- **Reviewer** — Codex: reviews vs the DoD, proposes graded findings, sets a verdict. Never edits the artifact.

---
## Log

### Round 1 · Producer · Claude · 2026-06-19
**Did:** Wrote the remediation plan `PROJECT/2-WORKING/FOCUS-5-RANKING-BUG-AND-REMEDIATION.md`. It documents a /debug-mantra trace (8-run ledger) and isolates three root-cause issues:
- **A (primary):** no ranking mode surfaces "most recent active repos" — `dirty_first` sorts `(at_risk, recency)` and `my_work` pins dirty repos to `now`, both burying clean-but-recently-committed repos. Proven by re-ranking the stored signals: pure `_recency` surfaces the operator's actual active repos.
- **B (contributing):** the roster is a frozen snapshot — Focus 5 is opt-in (not scheduled) and PR #72 removed on-view recompute, so it only refreshes on manual ↻ Refresh.
- **C (secondary):** `rebalance-OS` is outside the single scan root (`/Documents/GH Repos`), so it's never discovered.

Plan: Phase 1 add `rank_recent_activity` (default), Phase 2 two views (Focus 5 = recency, Dirty Five = dirty_first), Phase 3 scheduled refresh (decided), Phase 4 add rebalance-OS to scan roots. Each phase has a QA checklist.

**Review this:**
- Are the code claims accurate? Specifically `rank_dirty_first` sort_key `(at_risk, recency)` and `rank_my_work` pinning dirty→now (`focus5_scan.py` ~lines 157–182), and `_recency` excluding `index_mtime_ts` (~142–149).
- Is the proposed `rank_recent_activity` (sort_key `(_recency(s),)`, eligibility `_eligible_as_my_work`) correct, and does making it the **default** have any downside vs the documented "don't lose WIP" intent of dirty_first?
- Completeness: does every diagnosed issue (A/B/C) map to a phase with checkable QA? Any dropped consideration (e.g. tie-breaking when recency ties, repos with no operator commits, the off-roster "needs attention" strip semantics under the new default)?
- Any missing root cause the diagnosis didn't consider?

**Verification:** N/A — non-executable artifact (plan doc). Code claims were derived from reading the cited source + re-ranking stored signals during the trace.
**Open questions:** Should `rank_recent_activity` still surface a purely-dirty repo with no operator commits, and if so where should it rank vs a clean recently-committed repo?
**Commit:** 402d43a

### Round 2 · Reviewer · Codex · 2026-06-19
**Verdict:** Changes requested

**Basis:** textual only

**Findings & proposals:**
- [Blocker] The plan equates `_recency` with “operator-authored commit recency,” but the code does not. `_recency()` falls back from `my_last_commit_ts` to `head_reflog_ts` and then `last_commit_ts`, and `_eligible_as_my_work()` also admits dirty repos with no authored commit. As written, Phase 1 can still rank a dirty repo with no operator commit above a clean repo with a recent operator commit, which contradicts the stated product contract. Evidence: `focus5_scan.py:142-154`, `:157-182`, artifact `:100-108`.
  Proposed fix: use `my_last_commit_ts` as the primary eligibility/ranking signal for `recent_activity`; dirty-only/no-authored repos should be excluded from Focus 5 (left to Dirty Five) or explicitly demoted below all authored-commit repos. Add QA covering “dirty/no-authored vs clean/recent-authored.”

- [Blocker] The Phase 1 default-switch step is incomplete. Runtime selection does not read `DEFAULT_RANKING_MODE`; the collector reads `get_focus5_ranking_mode()`, which hardcodes `"dirty_first"` when config is unset. Changing `DEFAULT_RANKING_MODE` alone is inert. Evidence: `index_ops.py:1401-1421`, `config.py:652-669`, `focus5_scan.py:129`, artifact `:104-106`.
  Proposed fix: change the default returned by `get_focus5_ranking_mode()` in `config.py`, decide how existing config values behave, and remove/wire the dead constant. QA both: unset→`recent_activity`; explicit `dirty_first` still wins.

- [Blocker] Phase 2 QA says “switching does not re-probe (re-rank from cache),” but the read path always re-probes the top-5 cards’ live tree health on render. A view switch avoids a full-device scan, not all re-probing. Evidence: `focus5_scan.py:724-743`, `:767-778`, `web.py:548-549`, artifact `:124-126`.
  Proposed fix: reword QA to “switching does not call `sync_focus5()`/does not rescan all repos; it reranks from cached `focus5_repo_signals`.”

- [Should] Phase 2 is underspecified on persistence. `focus5_roster` stores one roster + one `ranking_mode` per device, so Dirty Five needs an explicit choice: transient mode param, rerank-and-persist per switch, or a second persisted roster. Evidence: `focus5_scan.py:523-527`, `:598-603`, `:681-693`, `:753-756`, artifact `:118-126`.
  Proposed fix: choose one model and QA it, especially “after visiting Dirty Five, reloading `/focus-5` still defaults to recent_activity.”

- [Should] Phase 4 names a `rebalance config` path that does not exist. There are getters/setters for `focus5_scan_roots` but no CLI command. Evidence: `config.py:635-649`, `cli/config_cmds.py:159-193`, artifact `:148-150`.
  Proposed fix: specify direct config-file mutation / a new CLI command, or phrase as “persist `focus5_scan_roots` in `temp/rbos.config`” and QA with `refresh_index(scope=["focus5"], dry_run=True)`.

- [Pass] Core claims about existing ranking are accurate: `rank_dirty_first` = `(at_risk, _recency)`, `rank_my_work` pins dirty→`now_ts`. Evidence: `focus5_scan.py:157-182`.
- [Pass] Stale-snapshot diagnosis + Phase 3 mapping sound: `focus5` is `included_in_all=False`; route rescans only on `?refresh=1`/empty. Evidence: `index_ops.py:1436`, `web.py:533-549`.
- [Pass] Off-roster “needs attention” strip stays compatible with recency-first Focus 5 (built from cached `is_dirty=1 OR ahead>0` not on roster). Evidence: `focus5_scan.py:790-803`, `web.py:351-376`.

**Answers:**
- Open question: no — a purely-dirty repo with no operator-authored commit should NOT outrank a clean repo with a recent operator commit in default Focus 5. Recommend excluding dirty-only/no-authored from `recent_activity` entirely (Dirty Five / off-roster carry them); softer option = demote below all repos with `my_last_commit_ts`.
- No 4th root cause beyond A/B/C. The main correction is A’s implementation not yet matching A’s product definition.
- Tie-breaking is already deterministic: `rank_repos()` sorts by score desc then `local_path`. Evidence: `focus5_scan.py:245-246`. Mention in QA rather than treat as unresolved.

**Commit:** none (comments only)

<!-- ↓↓↓  NEXT TURN GOES ABOVE THIS LINE — keep this marker last  ↓↓↓ -->

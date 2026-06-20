# RELAY · Focus 5 ranking-bug remediation — QA (correctness + minimal-code / ponytail)
<!--
  Single source of truth for this two-agent relay.
  Read this ENTIRE file before doing anything. Act only on your turn.
-->

NEXT: Producer
STATUS: Approved
ROUND: 2 / 3

## ▶ TAKE YOUR TURN — read this first (works for ANY agent: Claude, Codex, agy/Antigravity)
The operator just said "take your turn on this file." Everything you need is **in this file** — don't wait for pasted instructions.
1. **Read this whole file** (header, Setup, Ground rules, every turn in the Log).
2. **Check it's your turn:** `NEXT` (top) names the role to act. Confirm you are the agent bound to it (see Setup) **and** the last Log block isn't already yours. If not → STOP and reply "wrong window — nudge the <other> window."
3. **Do your role's work** on the artifact named in Setup. ⚠ Your process CWD is the *tooling* repo, NOT the repo under review — so use the **ABSOLUTE** paths listed in Setup. The primary artifact is the unified diff at
   `/Users/noelsaw/Documents/rebalance-OS/relay-system/2026-06-20/focus5-remediation-qa.diff`
   (read it directly); the six changed source files are listed by absolute path in Setup for deeper context.
   - **Reviewer:** review the diff against the Definition of Done → graded findings (`[Blocker]`/`[Should]`/`[Nit]`/`[Pass]`), each with a concrete proposed fix → set a **Verdict** (Approved | Changes requested | Blocked). Do **not** edit the source files; you only append findings here.
4. **Append ONE block** at the very bottom, directly **above** the marker line (`<!-- ↓↓↓ NEXT TURN ... -->`). Never edit earlier turns. Header it `### Round N · <Role> · <your-label> · <date time>`; a Reviewer block carries `**Verdict:**` + `**Basis:**` + `**Findings & proposals:**` (graded bullets) + `**Commit:**`.
5. **Update the header:** flip `NEXT` to the other role; set `STATUS` (`Approved` closes the relay — Reviewer only; else leave `Open`).
6. **Token handoff:** use `./bin/tick` for the `RELAY-TURN` token (claim/ping, then `release --to claude-a`, or `done` + set `STATUS: Approved` when approving). Do **NOT** run git — the harness commits this file for you.
7. **Stop.** Tell the operator your one-line result (e.g. "Changes requested, 1 Blocker — Producer's turn").

## Setup
- **Artifact under review:** the Focus 5 remediation diff (6 production files), primary copy embedded as a sibling `.diff`:
  - `/Users/noelsaw/Documents/rebalance-OS/relay-system/2026-06-20/focus5-remediation-qa.diff`  ← **read this first**
  - `/Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/focus5_scan.py`
  - `/Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/config.py`
  - `/Users/noelsaw/Documents/rebalance-OS/src/rebalance/web.py`
  - `/Users/noelsaw/Documents/rebalance-OS/src/rebalance/cli/config_cmds.py`
  - `/Users/noelsaw/Documents/rebalance-OS/scripts/github_sync.sh`
  - `/Users/noelsaw/Documents/rebalance-OS/scripts/pulse_server.py`
- **Definition of Done:** the remediation is **correct** AND **minimal** — it fixes the Focus 5 ranking bug (and the two contributing issues) with the *least code that actually works*. No code beyond what the fix needs.
- **Primary lens — `/ponytail` (least-code / YAGNI).** Judge every added line against:
  1. **Does this code need to exist at all?** Flag any abstraction, parameter, helper, or branch the fix doesn't require.
  2. **Stdlib / existing-helper first.** Flag anything hand-rolled that an existing function in the same module/repo already does.
  3. **One line before fifty.** Flag verbose constructs where a shorter equivalent reads as clearly.
  4. **Smallest change that satisfies the finding.** Flag wholesale rewrites where a narrow edit would do.
  5. **No speculative generality.** Flag params/modes/config knobs added "for later" with no current caller.
  Call out over-engineering, bloat, dead abstractions, and needless indirection explicitly — that is the headline criterion, ranked alongside correctness.
- **Also check (correctness):** the new `recent_activity` strategy + default flip; the transient Dirty Five view that must NOT overwrite the persisted roster; the scan-root config + CLI; the github-sync piggyback. Pure-function ranking (no I/O/clock in a strategy). HTML escaping in the web layer.
- **Out of scope:** test files and docs (SCHEDULER.md) — review the *production* diff only. The design was already plan-reviewed (Codex r1–r6); this pass is implementation QA, ponytail-first.
- Producer: claude-a (Claude Opus)   ·   Reviewer: agy (Antigravity CLI, via xyz relay-automation/agy-turn.sh)
- Handoff: cli-driven (agy)   <!-- xyz relay-automation: agy-turn.sh drives the Reviewer turn headless -->
- Started: 2026-06-20

## Ground rules
1. This file is the single source of truth. If it isn't written here, assume the other agent doesn't know it. The two agents are different tools (Claude and agy) and never share memory.
2. Read the whole file. Take a turn only if `NEXT` names your role — otherwise reply "not my turn" and stop.
3. One turn = one block appended at the very bottom, above the marker. Never edit earlier turns. Then update `NEXT`/`STATUS` at the top.
4. Stay tight. Findings are bullets, not essays.
5. **The Reviewer never edits the source files.** It proposes graded findings, each with a concrete suggested fix where possible. The Producer (the author), with the operator, decides each proposal and implements the approved ones.
6. Grade every finding: `[Blocker]` must fix · `[Should]` strong rec · `[Nit]` optional · `[Pass]` checked and sound. A ponytail/minimal-code violation is a legitimate `[Should]` (or `[Blocker]` if it adds real risk/maintenance burden).
7. The Reviewer posts a Verdict every turn. The relay ends on **Approved** — to get proposals actioned in-thread set `Changes requested`, not `Approved`.
8. Token handoff via `./bin/tick`; the harness commits this file (Reviewer runs no git).
10. **Evidence contract.** The Reviewer logs a verdict `Basis:` — `behaviorally proven` (ran/observed) or `textual only` (read, not run). This is a read of a diff, so `textual only` is expected and honest.

## Roles
- **Producer (claude-a)** — author of the change: built it, requests review, decides and implements proposals.
- **Reviewer (agy)** — reviews the diff against the DoD (ponytail-first + correctness), proposes graded findings, sets a verdict. Never edits the source.

---
## Log

### Round 1 · Producer · claude-a · 2026-06-20
**Did:** Implemented the approved 4-phase Focus 5 remediation (plan: `PROJECT/2-WORKING/FOCUS-5-RANKING-BUG-AND-REMEDIATION.md`). In the production diff under review:
- **Phase 1** — new `rank_recent_activity` strategy in `focus5_scan.py` (`sort_key = (my_last_commit_ts or 0,)`, eligibility = authored a commit here, no dirty pinning); registered `"recent_activity"`; flipped `get_focus5_ranking_mode()`'s unset default to it (+ the `DEFAULT_RANKING_MODE` constant, in lockstep).
- **Phase 2** — `summarize_focus5(mode=...)` re-ranks the cached signals **in memory** for the transient Dirty Five view (never writes `focus5_roster`); shared `_build_roster_card` + `_persisted_roster_bases`/`_transient_roster_bases`; `_focus5_body(view=...)` + a segmented toggle; route `view` param; pulse-server route forwards `view`.
- **Phase 4** — `set/add/remove_focus5_scan_root` in `config.py` + `rebalance config {add,remove,list}-focus5-scan-root` CLI.
- **Phase 3** — `github_sync.sh` scope `["github"]` → `["github","focus5"]` (piggyback; no new launchd job).

**Review this (ponytail-first):** Be aggressive on minimal-code. Specific suspects I want challenged:
- `_build_roster_card` + `_persisted_roster_bases` + `_transient_roster_bases` — is the 3-function split justified, or is it indirection a smaller inline branch would beat?
- `add_focus5_scan_root` / `remove_focus5_scan_root` seeding from the effective roots — necessary, or over-built vs a plain setter?
- `_f5_view_toggle` + `_F5_VIEWS` — least-code for a 2-item toggle?
- The `mode`/`view` params threaded through `summarize_focus5` / `_focus5_body` / both routes — any param added without a real caller?
- Anything hand-rolled that an existing helper already does. Any dead branch, any speculative knob.
Plus correctness: transient view must not mutate the persisted roster; `recent_activity` excludes dirty-only/no-authored repos; strategies stay pure (no I/O/clock); HTML stays escaped.

**Verification:** ran `pytest tests/test_focus5_scan.py tests/test_web_focus5.py tests/test_web_surface.py tests/test_web_components.py tests/test_scheduler_policy.py tests/test_index_ops.py` → 139 passed. Live: `sync_focus5()` on the real DB surfaced rebalance-OS/xyz-3-agents-swarm/giant-brains/hypercart-plugin-mkiii/wp-code-check; `eve` (dirty-only) absent from Focus 5, present in Dirty Five; persisted roster stayed `recent_activity` after a transient Dirty Five render. `rebalance doctor` passed (2 unrelated pre-existing warns).

**Open questions:** Is any of the Phase-2 helper split (`_build_roster_card` / `_*_roster_bases`) net-negative on the ponytail lens — i.e. would a single function with one `if mode` branch be strictly simpler with no readability loss?

**Commit:** (harness commits this turn)

### Round 1 · Reviewer · agy · 2026-06-20
**Verdict:** Changes requested
**Basis:** textual only
**Findings & proposals:**
- [Blocker] `remove_focus5_scan_root` bug: removing the last default scan root from config resets the configuration and brings all defaults back.
  * *Proposed Fix:* Update `get_focus5_scan_roots` in `src/rebalance/ingest/config.py` to return defaults only if the config key is `None`, and modify `set_focus5_scan_roots` to avoid popping the config key when empty (allowing `[]` as an explicit setting).
- [Should] Ponytail/YAGNI redundant functions in `focus5_scan.py`: `_persisted_roster_bases` and `_transient_roster_bases` are single-caller helpers adding needless indirection.
  * *Proposed Fix:* Inline these database queries and re-ranking logic directly into the branches of `summarize_focus5()`.
- [Should] Ponytail/YAGNI view toggle in `web.py`: `_F5_VIEWS` and `_f5_view_toggle()` are single-caller helpers.
  * *Proposed Fix:* Inline the segmented toggle HTML generation inside `_focus5_body()`.
- [Nit] Redundant path expansions in `config_cmds.py`: CLI commands `config_add_focus5_scan_root` and `config_remove_focus5_scan_root` repeat `Path.expanduser()` logic already encapsulated inside core functions.
  * *Proposed Fix:* Pass the path directly or have core functions return the expanded path.
- [Pass] Correctness: Purity of `recent_activity` strategy and exclusion logic verified; transient views correctly avoid database mutations; HTML variables properly escaped.

**Commit:** (harness commits this turn)

### Round 2 · Producer · claude-a · 2026-06-20
**Decisions on proposals:** (verified each finding against the repo before deciding)
- [Should] inline `_persisted_roster_bases` + `_transient_roster_bases` — **Implemented** → deleted both single-caller helpers; folded the persisted-query / in-memory-rerank branches directly into `summarize_focus5()` (`src/rebalance/ingest/focus5_scan.py` ~860-895), and tightened the transient base-build from a 6-line append loop to one dict-comprehension (`{**asdict(r.signals), ...}`). `_build_roster_card` stays (genuinely shared by both branches). · Proof: `pytest` 119 passed.
- [Should] inline `_F5_VIEWS` + `_f5_view_toggle()` — **Implemented** → removed the module constant + single-caller function; the 2-tab toggle is now an inline `tabs` literal + join inside `_focus5_body()` (`src/rebalance/web.py` ~473-483). · Proof: `pytest` 119 passed (ViewToggleTests still green).
- [Blocker] `remove_focus5_scan_root` / `get_focus5_scan_roots` empty-reset — **Declined (contested)** → On the last-root removal the override clears and discovery falls back to the default root. That is the *intended* idiom: `get_focus5_scan_roots` deliberately mirrors `get_repo_scan_roots`'s "unset/empty → shared default" fallback, and an explicitly-empty scan set would make Focus 5 discover **nothing** (a useless state). agy's fix (distinguish `None` from `[]`, store `[]`) adds code to enable that no-value state — net **anti-ponytail**, against this relay's headline criterion. No data loss, fully recoverable. Flagged to the operator for override; if they want the distinction it's a ~4-line change.
- [Nit] CLI repeats `Path.expanduser()` — **Declined** → the CLI's one-line local expand is purely for the confirmation echo (good UX: shows the resolved absolute path). agy's fix (core returns the expanded path) complicates the `bool` return contract for a 1-line save — net more code. Left as-is.
**Did:** Applied the two ponytail reductions only; no behavior change (pure refactor). Net: −3 functions, −1 module constant, less indirection.
**Verification:** ran `pytest tests/test_focus5_scan.py tests/test_web_focus5.py tests/test_web_surface.py tests/test_web_components.py` → **119 passed**. Reconciled each `Implemented` against the file: the two helpers are gone (grep clean) and `summarize_focus5`/`_focus5_body` carry the inlined logic.
**Re-review this:** (1) confirm the two inlinings are behavior-preserving and genuinely lower the line/indirection count; (2) confirm `[Pass]` correctness still holds post-refactor (transient view still never writes `focus5_roster`); (3) your call on the contested `[Blocker]` — accept the decline, or hold that empty-roots SHOULD be storable.
**Commit:** 73d7a90

### Round 2 · Reviewer · agy · 2026-06-20
**Verdict:** Approved
**Basis:** textual only
**Findings & proposals:**
- [Pass] Refactoring: confirmed successful inlining of both `_persisted_roster_bases`/`_transient_roster_bases` and `_F5_VIEWS`/`_f5_view_toggle()`. Redundancy and indirection are resolved, preserving behavior while lowering complexity.
- [Pass] Contested blocker resolved: accepted the decline on `remove_focus5_scan_root` fallback. Returning the default list when empty matches the fallback model of `get_repo_scan_roots`, and a zero-root state is useless for Focus 5.
- [Pass] Contested nit resolved: CLI `Path.expanduser()` echo design is accepted.
- [Pass] Correctness: verified transient views still avoid database mutations and HTML remains properly escaped.

**Commit:** (harness commits this turn)

<!-- ↓↓↓  NEXT TURN GOES ABOVE THIS LINE — keep this marker last  ↓↓↓ -->

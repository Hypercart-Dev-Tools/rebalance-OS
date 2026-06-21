# RELAY · Auth Storage Hardening — Re-Scope Review (is it safe? is it worth doing?)
<!--
  Single source of truth for this two-agent relay.
  Read this ENTIRE file before doing anything. Act only on your turn.
-->

NEXT: Producer
STATUS: Open
ROUND: 1 / 3

## Setup
- Artifact under review: PROJECT/2-WORKING/AUTH-AND-API-KEY-STORAGE-HARDENING.md (revised: active Phases 0–3 + a new "Deferred Work" section)
- Definition of Done: The re-scope is **SAFE** (active Phases 0–3 still reach the core end state — no live secrets under the repo root, `0600`/`0700` enforced, JSON not pickle — and nothing pushed to Deferred Work is secretly load-bearing for that end state or for an unattended/launchd failure mode) **and WORTH DOING** (the active work delivers real risk/durability reduction proportional to its cost; the deferrals are genuinely YAGNI for a single-operator ~3-Mac tool, not a silent drop that will bite later).
- Producer: Claude (Opus 4.8)   ·   Reviewer: agy CLI (agy 1.0.10) — **hung past its `--print-timeout 4m`, killed; fell back to Codex CLI 0.139.0**
- Handoff: cli-driven (agy → codex fallback)
- Started: 2026-06-20

## Ground rules
1. This file is the single source of truth. The two agents never share memory.
2. Take a turn only if `NEXT` names your role.
3. One turn = one block appended at the bottom. Never edit earlier turns.
4. Reviewer never edits the artifact — it proposes graded findings ([Blocker]/[Should]/[Nit]/[Pass]) and sets a Verdict (Approved | Changes requested | Blocked).
5. For this non-executable plan doc, the Reviewer's basis is textual; the key safety check is reading the artifact itself, not just this thread.

---
## Log

### Round 1 · Producer · Claude · 2026-06-20 08:30 PDT
**Did:** Re-scoped the hardening plan after a ponytail pass. Context: rebalance-OS is a single-operator tool on ~3 personal Macs; the public-repo commit-leak path is already closed (`temp/` is gitignored, the config file untracked); `ANTHROPIC_API_KEY` is already env-only (`config.py:1254`). The revision keeps **Phases 0–3 active** (the `secret_store` keystone — already shipped + 11 tests; move GitHub/Figma/Sleuth fallbacks out of the repo tree; pickle→JSON OAuth) and pushes the rest into a new **Deferred Work** section: per-integration descriptors + six-field resolver wiring, Phase 4 (API-key unification), and the migration-report + staged decommission ceremony. Each deferral carries a revisit trigger. The decommission *outcome* (stop reading/writing `temp/rbos.config`) was folded into Phase 2 as a single-pass migration so the active plan still finishes the job.
**Review this — answer two questions against the DoD:**
1. **Is it SAFE?** Re-read the revised artifact. Is any item moved to Deferred Work actually load-bearing for the core end state (no live secrets under repo root, `0600`/`0700`, JSON not pickle) or for an unattended/launchd failure mode? Specifically: does deferring the per-integration resolver wiring, Phase 4, and the decommission *ceremony* leave any path where a live secret still persists in the repo tree, where unattended jobs break, or where a refresh-token can be lost? Flag any silent drop disguised as a defer.
2. **Is it WORTH DOING?** Is the active Phases 0–3 scope proportional — real risk/durability reduction for the cost — given a single-operator deployment with the commit-leak already closed? Or is even the active scope over- or under-built (e.g. should pickle→JSON stay, should Phase 2's repo-tree move stay, is anything still YAGNI that should also be deferred, or did the re-scope cut something that genuinely matters)?
**Verification:** N/A — non-executable artifact (planning/spec doc).
**Open questions:** Is "single-pass migration (move + stop-reading in one phase)" safe for a single operator, or does collapsing the additive-first gate create a real risk of locking out an unattended job mid-migration?

_Note: agy hung past its 4-minute print-timeout with no output and was killed; Codex 0.139.0 took the Reviewer turn as fallback (read-only sandbox)._

### Round 1 · Reviewer · Codex · 2026-06-20 09:10 PDT
**Verdict:** Changes requested
**Basis:** textual (read the revised plan; non-executable artifact)
**Q1 — Is it safe?:** Mostly yes: deferring the per-integration descriptor layer, Phase 4, and the migration-report/staged-decommission ceremony does not by itself undermine the core end state. Active Phases 0–3 still cover the load-bearing outcomes: no live secrets under the repo root, enforced `0600`/`0700`, and JSON instead of pickle for Google OAuth fallback. The one silent-drop risk is in `Phase 2 - Remove Repo-Local Secret Persistence`: the "single-pass migration" wording is only safe if cutover is per-machine and happens after verification on that machine. As written, it can be read as one release that both introduces migration and stops runtime reads from `temp/rbos.config`; that would violate the additive-first hard gate stated in `Target State` and `Cross-Phase Risks` and could lock out a launchd job on any Mac not yet migrated. The deferred ceremony can stay deferred, but the plan needs an explicit rule that legacy reads are removed only after that machine has written the new secret, proven interactive and unattended resolution, and then deleted the old key.
**Q2 — Is it worth doing?:** Yes, with that sequencing tightened. For a single-operator, ~3-Mac tool, the active scope is proportional: repo-root plaintext plus the observed `0644`/`0755` posture is still a real local exposure and copy/archive risk even if the public commit-leak path is already closed, and Phase 3's pickle→JSON work is the clearest unattended durability improvement in the document. The re-scope correctly defers fleet-style uniformity machinery. I would not pull Phase 4 or full resolver unification back into active. The only remaining YAGNI risk is letting descriptor/registry work creep back into Phase 1 under the guise of doctor cleanup; the active plan should stay focused on storage, permissions, migration, and OAuth format conversion.
**Findings & proposals:**
- [Should] `Phase 2 - Remove Repo-Local Secret Persistence` leaves rollout sequencing ambiguous and therefore weakens the additive-first gate from `Target State` / `Cross-Phase Risks` — Proposed fix: state explicitly that legacy reads remain available until a given machine's migration command has written the new secret, verified interactive and launchd-safe reads on that machine, and only then deletes old keys and disables legacy reads there; reject any release-wide cutover before per-machine verification.
- [Should] `Definition of Done` and `Deferred Work` blur whether doctor's `optional+unconfigured` vs `configured+broken/insecure` distinction is active or deferred — Proposed fix: keep that distinction unambiguously active in Phase 1 and reserve the defer strictly for the full six-field resolver contract / descriptor registry.
- [Nit] `Phase 0 - Durability Spike` still includes "Decide the canonical secret root" even though the header and Phase 1 status already say the root was settled inline — Proposed fix: mark that item complete or rewrite it as a validation checkpoint so the plan does not look less mature than it is.
- [Pass] The re-scope kept the right load-bearing work active: repo-local secret removal and pickle retirement stayed in scope, while fleet ceremony and API-key unification moved to Deferred Work — Proposed fix: none.
**Answers:**
- single-pass migration safe? → Safe only if it is a per-machine, verify-then-cutover transaction; unsafe if it means shipping code that stops reading `temp/rbos.config` before that machine has been migrated and unattended reads have been proven.
**Commit:** none (comments only)

<!-- ↓↓↓  NEXT TURN GOES ABOVE THIS LINE — keep this marker last  ↓↓↓ -->

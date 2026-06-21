# RELAY · Auth Storage Hardening — Re-Scope Review (is it safe? is it worth doing?)
<!--
  Single source of truth for this two-agent relay.
  Read this ENTIRE file before doing anything. Act only on your turn.
-->

NEXT: Reviewer
STATUS: Open
ROUND: 1 / 3

## Setup
- Artifact under review: PROJECT/2-WORKING/AUTH-AND-API-KEY-STORAGE-HARDENING.md (revised: active Phases 0–3 + a new "Deferred Work" section)
- Definition of Done: The re-scope is **SAFE** (active Phases 0–3 still reach the core end state — no live secrets under the repo root, `0600`/`0700` enforced, JSON not pickle — and nothing pushed to Deferred Work is secretly load-bearing for that end state or for an unattended/launchd failure mode) **and WORTH DOING** (the active work delivers real risk/durability reduction proportional to its cost; the deferrals are genuinely YAGNI for a single-operator ~3-Mac tool, not a silent drop that will bite later).
- Producer: Claude (Opus 4.8)   ·   Reviewer: agy CLI (agy 1.0.10)
- Handoff: cli-driven (agy)
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

<!-- ↓↓↓  NEXT TURN GOES ABOVE THIS LINE — keep this marker last  ↓↓↓ -->

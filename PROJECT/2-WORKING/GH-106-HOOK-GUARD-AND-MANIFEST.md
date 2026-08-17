---
title: "Adopt gsd-core patterns: hook guard + PDDA conventions + skills inventory + capabilities manifest"
owner: Noel
gh_issue: 106
source: "https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/106"
status: "Active (2-WORKING) — Phase 1 (6-item quick-win batch) complete 2026-07-03. Phase 2 rebalance-side three-bundle capabilities-manifest slice implemented 2026-07-05; relay review pending."
created: 2026-07-03
updated: 2026-07-05
doc_type: project
goal: >
  Build the follow-on adoptions from the closed GSD Core pattern review (GH-103): a batch of 6
  low-risk, easily-reversible process/tooling changes (Phase 1, complete), plus a deferred narrow
  capabilities-style manifest across Rebalance + XYZ skill surfaces (Phase 2).
related:
  - PROJECT/3-COMPLETED/GH-103-GSD-CORE-PATTERN-REVIEW.md
effort: 2
complexity: 2
risk: 1
phases: 2
---

## Status

| What was just completed | What's next |
|---|---|
| **Phase 2 slice implemented 2026-07-05** — added rebalance-side `capabilities/manifest.yaml` for exactly 3 XYZ-owned bundles (`relay-xyz`, `xyz`, `consult`), plus deterministic generator `scripts/generate_capabilities_index.py`, checked-in `capabilities/INDEX.md`, and a focused regression test. Scope stays pinned to by-reference facts already documented in this repo; no live `xyz-3-agents-swarm` scan, no edits there, no dynamic loader/trust engine. | **Relay review / ship the bounded slice.** If a fuller cross-repo capabilities system is ever wanted later, treat it as new scope rather than expanding this lane implicitly. |

## Goal

Build the follow-on items from the GSD Core pattern review
([GH-103](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/103), closed): a batch of 6
low-risk, easily-reversible process/tooling adoptions, plus (deferred) a narrow ownership manifest
across Rebalance + XYZ skill surfaces.

Provenance: [GH-103-GSD-CORE-PATTERN-REVIEW.md](../3-COMPLETED/GH-103-GSD-CORE-PATTERN-REVIEW.md),
Phase 1–3 Findings. All items were graded via cross-model consult (Codex + agy); the
capabilities-manifest scope is deliberately narrowed to the version that survived a real YAGNI
objection one advisor raised.

## Discuss (before Phase 1 execution)

- **Why batch 6 items into one pass instead of an XYZ marathon:** all 6 scored low-medium risk with
  trivial-to-easy reversibility (no schema migration, no dependency add, no one-way door). Marathon
  is strictly serial regardless (confirmed against the vendored planner during GH-103), so batching
  saves nothing there; worse, two items (#1 verify-gate, #4 loop-naming) both edit
  `PROJECT/PDDA.md`, and marathon explicitly defers cross-phase context injection — running them as
  separate phases risked duplicate/conflicting edits with no phase aware of the other's change. A
  direct, single-session batch avoids that entirely.
- **Correction found mid-build:** gsd-core's own `gsd-read-guard.js` (the source for the original
  "read-before-edit advisory hook" first step) explicitly detects and **skips itself on Claude
  Code** — its own comment states "Claude Code natively enforces read-before-edit — skip the
  advisory." Porting it here verbatim would have been a permanent no-op. Substituted Codex's
  original alternative framing instead: an advisory nudge against bypassing the collector registry
  via inline-Python `rebalance.ingest` calls — a real, non-redundant gap.
- **Scope note (concurrent-edit awareness):** another agent was independently updating XYZ tooling
  in this repo during this batch. None of the 6 items touch `.xyz/` (gitignored, out of this repo's
  git-tracked surface anyway), so there was no file or commit collision; the new
  `SKILLS-INVENTORY.md` references XYZ paths by name/concept rather than exact line numbers for
  exactly this reason.

## Scope

**Phase 1 — Quick-win batch, all low-medium risk / trivial-to-easy reversibility (target: mostly
Rebalance, 3 shared with XYZ). COMPLETE 2026-07-03:**

1. **Verify-before-done gate** — `PROJECT/PDDA.md` → "Named phase-loop steps: Discuss & Verification
   summary." A `Verification summary` convention required before a phase's QA gate can pass.
2. **Hook guard (corrected scope)** — `utils/pdda/pdda-leaf-ingest-guard.py`, an advisory (never
   blocking) `PreToolUse` hook wired in `.claude/settings.json`, firing only on inline-Python
   `rebalance.ingest` calls that bypass `register_collector`/`refresh_index`. The originally-scoped
   read-before-edit port was dropped as a no-op on Claude Code (see Discuss above); hardening this
   guard to a hard block is deliberately deferred to a future pass once proven false-positive-free.
3. **Subagent/consult hand-back contract** — `PROJECT/PDDA.md` → "Subagent & consult hand-back
   contract." Required return shape for future `consult`/subagent prompts authored from this repo.
4. **5-step loop naming** — same `PROJECT/PDDA.md` section as #1: a named `Discuss` step before
   planning, alongside the `Verification summary` before close. (This very doc's Discuss section
   above is the convention's first real use.)
5. **Skill/agent/command/hook composition inventory** — `SKILLS-INVENTORY.md` (repo root),
   "Orchestrated flows" table: traces `welcome`, `ask_self`/`reingest`, the new leaf-ingest guard,
   and the two XYZ relay/consult flows end-to-end (skill → runtime surface → hook → owner).
6. **Skills-help / discoverability index** — same `SKILLS-INVENTORY.md`, "Skills & commands index"
   + "Cross-repo surfaces" tables. Hand-maintained, not a generation script (kept at the "S" effort
   the review scored it — no automation infrastructure added for a 5-skill/2-command catalog).

**Phase 2 — Narrow capabilities-style manifest (rebalance-side, scope-pinned slice). IMPLEMENTED
2026-07-05:**
- `capabilities/manifest.yaml` now records a static bundle manifest (`id`, `owner`, `skills`,
  `commands`, `hooks`, `executables`, `requires`) for exactly 3 bundles: `relay-xyz`, `xyz`,
  `consult`.
- `scripts/generate_capabilities_index.py` renders the checked-in, read-only
  `capabilities/INDEX.md` from that manifest.
- The manifest documents the XYZ surfaces **by reference only** (names / known paths already cited in
  this repo's docs). It does **not** scan `xyz-3-agents-swarm`, edit that repo, or claim to be a
  full cross-repo capabilities system.
- Explicitly **not** gsd-core's dynamic overlay/trust engine (39-file system) — still just a static
  manifest + generated index.

## Non-goals

- Do not build gsd-core's dynamic capability-overlay/trust engine — static manifest only (this is
  the YAGNI line one advisor drew; respect it).
- Do not widen into a general skill/command architecture rewrite.
- Do not couple this into GH-102 (XYZ⇄Rebalance integration) scope — separate effort, separate issue.
- Do not vendor gsd-core code; pattern reuse only (MIT, ideas free, no attribution needed for
  non-verbatim reuse).
- Do not harden the leaf-ingest guard to a hard block in this pass — advisory only until proven
  false-positive-free (stated in Phase 1 item #2 above).

## Verification summary (Phase 1)

- `rebalance doctor` — clean (warnings present are pre-existing/unrelated: Figma token, two stale
  pulse collectors).
- `pytest tests/` — 1264 passed, 10 skipped (pre-existing skips), 0 failed.
- `utils/pdda/pdda.sh run` — clean for every file this phase touched (the one remaining ERROR in the
  run output is pre-existing on the unrelated `GH-102` doc).
- `CHANGELOG.md` — `0.52.0` entry added (was 1 day stale per the PDDA changelog check; now current).
- Manual litmus on the new hook: fired correctly and non-blockingly on a live matching Bash command
  during this session (real hook invocation, not just a piped-stdin unit test), and stayed silent on
  a non-matching command.
- Unmet: none for Phase 1's stated acceptance.

## Acceptance

- Phase 1: ✅ done — see Verification summary above.
- Phase 2: ✅ the rebalance-side, scope-pinned slice is done — `capabilities/manifest.yaml` exists
  for the 3 named bundles (`relay-xyz`, `xyz`, `consult`), `capabilities/INDEX.md` is generated
  from it, and no dynamic loader/trust logic was added. This is intentionally **not** a broader
  cross-repo capabilities system.

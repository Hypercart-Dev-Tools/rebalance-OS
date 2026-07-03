---
title: "GSD Core pattern review — harvest reusable patterns for XYZ & Rebalance"
owner: Noel
gh_issue: 103
source: "gsd-core (open-gsd/gsd-core, MIT, npm @opengsd/gsd-core) — external repo, operator-local checkout, not part of this repo"
status: "Complete (3-COMPLETED) — satisfies GH-103's acceptance criteria. All 4 phases run 2026-07-03 via consult (Codex + agy). Top-3 adopt calls: verify-before-done gate, hook catalog guard, capabilities/ narrow manifest — captured as follow-on GH issue, not executed here. Retroactive note: this doc predates linking gh_issue: 103 (the issue existed before this doc was authored but wasn't checked at capture time); doc renamed GH-103- prefix added post hoc, no content changed."
created: 2026-07-03
updated: 2026-07-03
branch: gh-102-xyz-rebalance-integration
doc_type: review
goal: >
  Review the MIT-licensed gsd-core framework and extract the patterns worth reusing across two
  targets — XYZ (the vendored .xyz/ agent-swarm harness in this repo) and Rebalance itself —
  focused on two pattern families: (1) phase-loop & context engineering, (2) skill/command/hook/
  agent architecture. Output is an adopt/adapt/skip call per pattern, each paired with a gap-analysis
  of what Reb/XYZ already have.
non_goals: >
  Not a wholesale port of gsd-core. Not adopting its testing/quality-gate stack (stryker/eslint-rules)
  or its cross-runtime installer/versioning — both explicitly out of scope for this review. Not
  copying code verbatim (MIT attribution would apply if we ever did). Not a comparative teardown /
  research report — the lens is "what do we steal and how", grounded in what already exists here.
related:
  - https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/103 (this review's originating issue)
  - PROJECT/2-WORKING/GH-102-XYZ-REBALANCE-INTEGRATION.md
  - .xyz/ (vendored XYZ harness)
effort: 2
complexity: 2
risk: 1
phases: 4
license_note: >
  gsd-core is MIT-licensed. Reusing *patterns/ideas* needs no attribution; if any file or substantial
  text/code is copied verbatim, retain the MIT LICENSE + copyright notice at the copy site.
---

## Status

| What was just completed | What's next |
|---|---|
| **Review complete 2026-07-03 — all 4 phases run via `consult`** (Codex + agy in parallel), not Claude subagents, per operator request. Phase 0 grounded both pattern families and found the `capabilities/` overlay layer as the starkest gap (one disagreement adjudicated: agy fabricated 3 out-of-bounds citations against the gitignored `.xyz/`, caught by direct measurement). Phase 1 (Family A) graded 5 patterns: ADOPT a verify-before-done record, ADAPT loop-naming + subagent hand-back, SKIP 2 (`STATE.md`-equivalent, XYZ parallel waves — one disagreement adjudicated toward SKIP per XYZ's own no-shared-file design). Phase 2 (Family B) graded 5 patterns: the consequential disagreement was the `capabilities/` layer itself — Codex's narrow static-manifest ADAPT vs. agy's YAGNI-grounded SKIP — **adjudicated ADAPT scoped exactly to the minimal manifest**, plus ADOPT a hook guard, ADAPT a skills-help index, SKIP-punt installer/versioning to GH-102. **Phase 3 synthesized all 10 calls into a ranked table + Top-3: (1) verify-before-done gate, (2) hook catalog guard — both ROI 3.0, Reb-only; (3) `capabilities/` narrow manifest — promoted ahead of a 4-way ROI tie on strategic signal (both Phase-0 advisors independently flagged it), override stated explicitly, not silent.** XYZ has zero unique adopt items — its only actionable rows are shared with Rebalance. Full ranked table, SKIP ledger, and next-action recommendations in the Phase 3 Findings block. | **Operator decision on next actions** (this review only recommends): (1) verify-before-done gate → direct `PDDA.md` convention edit; (2) hook guard → GH issue or `1-INBOX` capture (touches `.claude/settings.json`); (3) `capabilities/` manifest → park in `ROADMAP.md` with its own scoped capture doc. Review doc itself needs no further phases — promoted to `3-COMPLETED`. |

---

## Table of contents

- [Thesis & shape](#thesis--shape)
- [Review invariants](#review-invariants)
- [Two review targets](#two-review-targets)
- [Two in-scope pattern families (+ what's excluded)](#two-in-scope-pattern-families)
- [Grading rubric (adopt / adapt / skip)](#grading-rubric)
- [Execution plan — XYZ marathon serialization](#execution-plan--xyz-marathon-serialization)
- [Phase 0 — Inventory & counterpart map](#phase-0--inventory--counterpart-map) _(discovery)_
- [Phase 1 — Family A: phase-loop & context engineering](#phase-1--family-a-phase-loop--context-engineering)
- [Phase 2 — Family B: skill/command/hook/agent architecture](#phase-2--family-b-skillcommandhookagent-architecture)
- [Phase 3 — Synthesis: ranked adopt-list, split by target](#phase-3--synthesis-ranked-adopt-list-split-by-target)
- [Anti-goals](#anti-goals)
- [Provenance & verification](#provenance--verification)

---

## Thesis & shape

> **Thesis:** gsd-core and our stack solve the *same* problem — keeping AI agents disciplined and
> honest as context fills — with independently-evolved machinery. gsd-core is further along on two
> axes we care about: an explicit **five-step phase loop** (Discuss → Plan → Execute → Verify →
> Ship) with fresh-context subagents, and a **large, cross-runtime-portable skill/command/hook**
> catalog. We already have analogues (PDDA phases, `phase-qa`, `snapshot`, the relay/swarm harness,
> the `.claude` skill ecosystem). The review's job is to find where gsd's version is *better shaped*
> than ours and produce a graded, cheap-first adopt list — not to port a framework.

**Method:** for each pattern, answer four questions — (1) what gsd-core does (grounded in
`file:line`), (2) what XYZ / Rebalance already have for it, (3) the **gap**, (4) an **adopt / adapt /
skip** call with an effort estimate and the target it applies to. The plan *is* the deliverable: the
Findings blocks below are filled as the review runs.

---

## Review invariants

These hold across every phase; a finding that violates one is wrong, not merely weak.

1. **Grounded, not vibed.** Every claim about gsd-core cites a `file:line` or an example artifact;
   every "we already have this" cites the counterpart here. Ungrounded claims are marked UNVERIFIED.
2. **Gap-analysis before adopt.** No adopt call is made without first stating what already exists —
   the ROI is the *delta*, not the feature in isolation.
3. **Cheapest-that-works.** Prefer adapting an existing surface (a PDDA phase, a `.claude` skill, an
   XYZ shim) over standing up a gsd-shaped subsystem. "Adopt the idea, not the plumbing."
4. **Target-aware.** Each pattern is tagged for **XYZ**, **Rebalance**, or **both** — the two have
   different owners, languages (XYZ = shell/relay shims; Reb = Python), and install surfaces.
5. **License-clean.** Patterns are free to reuse; verbatim copies retain gsd-core's MIT notice.
6. **ROI-gated (per operator standing pref).** Skip deep dives on patterns with obviously low payoff;
   this is a scoped harvest, not an exhaustive teardown.

---

## Two review targets

| Target | Where | Language/shape | What "reuse" means here |
|---|---|---|---|
| **XYZ** | vendored [.xyz/](../../.xyz) — `skills/`, `relay-automation/`, `src/`, `bin/` | shell + relay shims, skill markdown | Improve the swarm/relay harness & its skill ergonomics |
| **Rebalance** | this repo — `src/rebalance/`, `.claude/`, PDDA (`utils/pdda/`), `PROJECT/` | Python + `.claude` skills/hooks + PDDA docs | Improve the phase discipline, doc lifecycle, and skill/agent structure |

---

## Two in-scope pattern families

**In scope (operator-selected):**

- **Family A — Phase-loop & context engineering.** gsd's Discuss→Plan→Execute→Verify→Ship loop;
  fresh-context subagents for heavy work; persistent cross-session artifacts (`STATE.md`,
  `CONTEXT.md`). Counterparts here: PDDA 1-INBOX→2-WORKING→3-DONE lifecycle, `phase-qa`, `snapshot`,
  `relay`/`xyz` swarm, the collector/ingest pipeline.
- **Family B — Skill/command/hook/agent architecture.** How gsd structures 70 skills / 34 agents /
  70 commands / 22 hooks / 39 capabilities and keeps them portable across runtimes. Counterparts
  here: `~/.claude/skills/*`, the vendored `.xyz/skills/*`, project hooks, MCP tools.

**Deliberately excluded (this review):** testing/quality gates (stryker mutation, eslint-rules,
TESTING-STANDARDS, coderabbit) and install/versioning/release-channel (cross-runtime installer,
VERSIONING, changesets). *Note:* the install/versioning family overlaps GH-102 seam #2 — if a
compelling pattern surfaces incidentally, log it as a one-line pointer for GH-102, do not review it
here.

---

## Grading rubric

Each reviewed pattern gets exactly one call:

- **ADOPT** — clear gap, cheap to add, high payoff. Names the target + a concrete first step.
- **ADAPT** — good idea, but our shape differs; take the concept, not the implementation. Names what
  to change.
- **SKIP** — already covered here, or payoff doesn't justify cost, or out of scope. States which.

Every call carries: **target** (XYZ / Reb / both), **effort** (S/M/L), **payoff** (1-3), and a
one-line **why**.

---

## Execution plan — XYZ marathon serialization

**Tooling gap found:** the operator asked to run XYZ's `swarm-preflight` step to generate this plan.
`utils/swarm-preflight.sh` (readiness packet: `run-candidate.json` / `lane-plan.json` / `packet.md` /
`marathon-invocation.txt`) is referenced by [.xyz/test/swarm-preflight.sh](../../.xyz/test/swarm-preflight.sh)
but is **not part of this repo's vendored `.xyz/` copy** (`find .xyz -iname '*preflight*'` returns only
the test file — the vendor only shipped `bin/`, `relay-automation/`, `skills/`, `src/`, `test/`). That
readiness-gate step could not literally be run. What **is** vendored and *was* run: the multi-phase
planner itself — [bin/marathon-yaml](../../.xyz/bin/marathon-yaml) (schema validate + topological
`depends_on` resolve, the same primitive `marathon.sh`/`swarm-preflight` build on) — against a
hand-authored `MARATHON.yaml` for this review's four phases.

**The plan** (`gsd-core-pattern-review`):

```yaml
name: gsd-core-pattern-review
phases:
  - id: p0
    name: Inventory and counterpart map
    reviewer: codex
    brief: PROJECT/1-INBOX/GSD-CORE-PATTERN-REVIEW.md
    artifact: PROJECT/1-INBOX/GSD-CORE-PATTERN-REVIEW.md
    max_review_rounds: 2

  - id: p1
    name: Family A grading - phase-loop and context engineering
    reviewer: codex
    brief: PROJECT/1-INBOX/GSD-CORE-PATTERN-REVIEW.md
    artifact: PROJECT/1-INBOX/GSD-CORE-PATTERN-REVIEW.md
    depends_on: p0
    max_review_rounds: 2

  - id: p2
    name: Family B grading - skill/command/hook/agent architecture
    reviewer: gemini
    brief: PROJECT/1-INBOX/GSD-CORE-PATTERN-REVIEW.md
    artifact: PROJECT/1-INBOX/GSD-CORE-PATTERN-REVIEW.md
    depends_on: p0
    max_review_rounds: 2

  - id: p3
    name: Synthesis - ranked adopt-list split by target
    reviewer: codex
    brief: PROJECT/1-INBOX/GSD-CORE-PATTERN-REVIEW.md
    artifact: PROJECT/1-INBOX/GSD-CORE-PATTERN-REVIEW.md
    depends_on: p2
    max_review_rounds: 2
```

**Resolved serial order** (real output, `node .xyz/bin/marathon-yaml <plan> --format tsv`; parsed and
validated clean — no duplicate ids, no unknown `depends_on`, no cycle):

| # | id | reviewer | round-cap | depends_on | phase |
|---|----|----------|-----------|------------|-------|
| 1 | p0 | codex  | 5 | — | Inventory and counterpart map |
| 2 | p1 | codex  | 5 | p0 | Family A grading |
| 3 | p2 | gemini | 5 | p0 | Family B grading |
| 4 | p3 | codex  | 5 | p2 | Synthesis |

**Parallelism/concurrency analysis (honest, tool-grounded):**

- **`marathon.sh` itself is strictly serial.** Its own header states cross-phase concurrency is
  "deliberately deferred" — it runs each resolved phase through `marathon-drive.sh` one at a time,
  advances only on approval, and halts on first failure. There is no flag or mode that fans phases out
  concurrently, so the resolver above always emits one linear order even when phases don't depend on
  each other.
- **`p1` and `p2` ARE structurally independent** — both list `depends_on: p0` only, not each other.
  The resolver places `p2` right after `p1` purely because it preserves authoring order among
  equally-ready nodes (confirmed by reading `resolveOrder` in
  [src/marathon-yaml.js](../../.xyz/src/marathon-yaml.js)), not because of a real ordering constraint.
  This is genuine parallel-eligible work: Family A and Family B are independent gsd-core reading tracks.
- **XYZ's actual concurrency primitive (`xyz` skill / `tick` lanes) doesn't fit this case.** It requires
  non-overlapping, path-scoped lanes — but `p1` and `p2` both write into the **same** shared doc (this
  file), just different `Findings` sections. Two agents editing one file concurrently is exactly what
  the lane model is built to prevent, not enable.
- **Practical concurrency lever for this review:** run Phase 1 and Phase 2 as two parallel research
  subagents (native Agent-tool fan-out, no XYZ tick/relay machinery needed — this is single-operator
  research, not multi-CLI construction) into two independent scratch findings, then merge both into
  this doc's `Findings` blocks before Phase 3. This gets the real wall-clock win the DAG allows without
  fighting the same-file constraint.
- **Live `marathon.sh` execution deliberately not fired.** Actually running `marathon.sh --plan …`
  would acquire the repo's global `.relay-driver.lock`, spin up real headless codex/gemini relay turns
  with git commits per phase, and require each phase's `brief`/`artifact` to be real non-overlapping
  files — all disproportionate machinery for a single-operator read/decide review. The plan above is
  validated and ready if a future phase (e.g. code lands from an ADOPT call) warrants a real cross-model
  gate; this review's four phases run under normal PDDA discipline instead (per-phase QA checklist,
  doc-only `git status`).

---

## Phase 0 — Inventory & counterpart map

*(discovery — findings MUST be written back before the QA gate passes; no code written)*

**Goal:** produce the grounded inventory both review phases build on — for the two in-scope families
only — and map each gsd pattern to its existing counterpart (or "none") here.

**Observable checklist:**

- [x] **Family A inventory.** Read gsd-core's phase-loop docs & skills — at minimum
      `docs/explanation/the-phase-loop.md`, `docs/explanation/context-engineering.md`,
      `docs/ARCHITECTURE.md`, and the driving skills (`skills/gsd-discuss-phase/`,
      `gsd-plan-phase`/`gsd-execute-phase`/`gsd-audit-*`/`gsd-complete-milestone`). Record the loop's
      real artifacts (`STATE.md`, `CONTEXT.md`, phase files) with paths + example shape.
- [x] **Family B inventory.** Characterize how `skills/`, `agents/`, `commands/`, `hooks/`,
      `capabilities/` relate (what's the unit of reuse, how do they compose, how does the installer
      make them cross-runtime). Record the directory contract + one worked example (one skill traced
      through to its agent/command/hook).
- [x] **Counterpart map.** For each notable gsd pattern, name the existing here-counterpart:
      PDDA lifecycle, `phase-qa`, `snapshot`, `relay`/`relay-xyz`/`xyz`, `.claude/skills`, project
      hooks, MCP tools, the `.xyz/` vendored skills — or "none".
- [x] **License note confirmed.** Re-confirm gsd-core LICENSE = MIT; record the one-line reuse rule.
- [x] **Excluded-family spillover log.** If any install/versioning pattern jumps out (GH-102 seam #2
      relevance), capture it as a single pointer line — do not review it here.

**Exit criteria:** the two-family inventory is grounded (`file:line` / example per pattern), the
counterpart map is complete (every gsd pattern → here-analogue or "none"), and this doc is ready to
`git mv` to `2-WORKING`.

#### Phase 0 — Findings

**Method.** Ran via `consult` (per the operator's request to use Codex + agy as the agents), not a
Claude subagent: `.xyz/relay-automation/consult.sh --models codex,agy` fanned the same Phase-0
question to both in parallel, `CONSULT_ROOT` = this repo, question referenced gsd-core by its
operator-local absolute checkout path (not repo-portable, omitted here — see `source:` in this
doc's frontmatter) and this repo/global skills by relative/absolute path. Both answered
(`2 answered, 0 failed`). Transcripts:
[relay-system/2026-07-03/gsd-phase0-122028/](../../relay-system/2026-07-03/gsd-phase0-122028/)
(`gsd-phase0.codex.md`, `gsd-phase0.agy.md`).

**Disagree (adjudicated first, per consult discipline — don't average away the delta).**

- **Whether the vendored `.xyz/` was actually visible to either advisor.** `.xyz/` is gitignored
  here (`.gitignore:71`, `git ls-files .xyz` = 0 tracked files) — `consult.sh`'s throwaway worktree
  only copies tracked + untracked-**not-ignored** files, so `.xyz/` should have been invisible to
  both. **Codex** (runs `-s read-only`) correctly reported it absent — saw only `.xyz-pin`, marked
  every local-`.xyz/` claim UNVERIFIED, and substituted citations from the canonical
  `xyz-3-agents-swarm` source repo instead (the repo `.xyz/` is vendored from). I spot-checked those
  substitute citations directly — **accurate and in-bounds**
  (`xyz-3-agents-swarm/src/marathon-yaml.js` is 149 lines; Codex's cited `98-146` fits;
  `skills/xyz/SKILL.md:22-34,38-49` content matches verbatim). **agy** (no OS sandbox — the consult
  skill's own caveat: "can still reach the network / the host outside the worktree") read `.xyz/`
  via the real absolute path anyway, bypassing the intended isolation. Its frontmatter citation
  (`​.xyz/skills/xyz/SKILL.md:4-11`) checks out verbatim — but three other `.xyz/`-local citations
  are **fabricated, out-of-bounds line ranges**, confirmed by direct measurement: agy cited
  `.xyz/src/project.js:589-631` (real file is **335 lines** — the range doesn't exist);
  `.xyz/relay-automation/hooks/relay-xyz-guard.sh:1-4495` (real file is **113 lines**);
  `utils/pdda/pdda-edit-doc-hook.sh:1-2444` (real file is **55 lines**). **Adjudication: REFUTED** —
  agy's "Parallel Execution Waves" and "Modular Hook System" counterpart-map citations for `.xyz/`
  are not grounded reads; they're replaced below with Codex's (verified) canonical-repo citations.
  Its underlying architectural claim (XYZ uses `tick`'s shared event log + path-scoped lanes) is
  independently correct — only the specific line-range citations were fabricated, not the concept.
- **Process finding (worth remembering for future consults):** a gitignored vendored directory
  referenced by *relative* path in a consult question is a silent trap — a sandboxed advisor (Codex)
  honestly loses it and says so; an unsandboxed advisor (agy) may still reach it via the real absolute
  path on disk, but that reach isn't guaranteed reliable (it fabricated ranges for the larger files
  here). Future consults over a gitignored tree should reference it by **absolute path explicitly**
  in the prompt (as this one did for gsd-core, where both models cited it correctly) rather than
  relying on the worktree copy.
- **Minor, not a real disagreement:** agy's own answer internally wavers between "no Rebalance
  counterpart" and "ad-hoc `ask_self`/Agent-tool counterpart" for fresh-context subagents. Resolved
  in the Agree section below in the more precise direction both models actually support.

**Agree (cross-model convergence — higher confidence).**

*Family A — phase-loop & context engineering (gsd-core):*
- The loop is explicit and command-driven: Discuss → (UI design) → Plan → Execute → Verify → Ship
  [`gsd-core/docs/explanation/the-phase-loop.md:11-15,23-59`].
- Persisted through `.planning/`: `STATE.md` is compact living memory (read every workflow start,
  written after significant actions: `active_phase`, `next_action`, progress counters); per-phase
  artifacts are `CONTEXT.md` (sealed decision record — fixed `<domain>/<decisions>/<canonical_refs>/
  <code_context>/<specifics>/<deferred>` blocks), `RESEARCH.md`, `PLAN.md`, `SUMMARY.md`,
  `VERIFICATION.md`, `UAT.md` [`gsd-core/docs/reference/state-md.md:9-76`; `context-md.md:21-92`;
  `planning-artifacts.md:9-189`].
- Fresh-context subagents are the explicit anti-context-rot mechanism: the orchestrator stays thin;
  researcher/planner/executor/verifier agents start clean and read only what they need
  [`gsd-core/docs/explanation/context-engineering.md:26-66`; `multi-agent-orchestration.md:21-55`].
- Execution is wave-based: plans declare dependencies/waves, Wave 1 runs in parallel worktrees,
  later waves wait, executors write `SUMMARY.md` + atomic commits
  [`gsd-core/docs/explanation/multi-agent-orchestration.md:88-136`; `plan-md.md:27-76,218-240`].
- "Done" is verifier-gated, not completion-gated: a verifier checks `must_haves`/coverage/goal
  alignment and emits routable `VERIFICATION.md` statuses
  [`gsd-core/docs/explanation/the-phase-loop.md:51-59`; `planning-artifacts.md:182-189`].

*Family B — skill/command/hook/agent architecture (gsd-core):*
- Composition traced concretely through `execute-phase`: skill entrypoint
  [`gsd-core/skills/gsd-execute-phase/SKILL.md:1-66`] → command surface
  [`commands/gsd/execute-phase.md:1-66`] → workflow orchestrator (init, checkpoints, worktree
  branch gates) [`gsd-core/workflows/execute-phase.md`] → `gsd-executor` agent (owns the
  plan-execution contract, task commits, deviations) [`agents/gsd-executor.md:14-160`] → runtime
  hooks (compaction/stop/file-change monitors) [`hooks/hooks.json:11-68`].
- The `capabilities/` layer is a **real declarative abstraction, not cosmetic naming**: runtime
  capabilities (`capabilities/claude/`, `capabilities/codex/`) define install roots, artifact
  layout, hook surfaces, command styles per runtime; feature capabilities (e.g. `research`,
  `nyquist`) inject loop steps/config keys/agents/artifacts; an overlay model composes all of it
  into one validated registry with fail-closed trust rules for executable surfaces
  [`gsd-core/docs/explanation/capability-overlay-model.md:18-151`; `capability-trust-model.md:16-254`;
  `capabilities/nyquist/capability.json:1-51`].

*Counterpart map (Rebalance / XYZ) — agreed, corrected per the Disagree adjudication above:*

| gsd-core pattern | Counterpart here | Gap |
|---|---|---|
| 5-step loop | PDDA's `1-INBOX→2-WORKING→3-DONE` lifecycle + per-phase QA checklists (this doc is an instance) [`PROJECT/PDDA.md:30-66`] | Doc/checklist-driven, not command/agent-driven — no `/gsd:discuss-phase`-style entrypoint |
| `STATE.md` | `ROADMAP.md` (pointer ledger) + active `PROJECT/**` docs as canonical state; session-level → `snapshot` skill [`ROADMAP.md:9-23`; `giant-brains-claude-skills/repo-health/snapshot/SKILL.md:14-60`] | No single compact living-memory file; state is spread across the ledger + per-project docs |
| `CONTEXT.md` | PDDA's "write findings back into the originating doc" convention + this doc's own Findings/QA blocks [`PROJECT/PDDA.md:162-175`] | No standalone sealed decision artifact with fixed structured fields |
| Fresh-context subagents | `consult` (parallel advisory fan-out, this very Phase 0 run) + ad-hoc Agent-tool subagents; no formal context-budget/hand-back contract | Different shape — advisory fan-out and general subagent use, not a phase-loop researcher/planner/executor/verifier cast |
| Parallel execution waves | XYZ's `tick`-based non-overlapping path-scoped lanes [`xyz-3-agents-swarm/skills/xyz/SKILL.md:22-49`] + marathon `depends_on` DAG resolution [`xyz-3-agents-swarm/src/marathon-yaml.js:98-146`] | Lane/claim model (path-scoped, agent-symmetric), not centrally-orchestrated dependency-waved worktrees; this review's own execution-plan section already found the DAG-vs-lane mismatch when phases share one file |
| Verify-before-done gate | `phase-qa` skill + PDDA QA/doc-readiness gates [`giant-brains-claude-skills/02-plan/phase-qa/SKILL.md:16-26,193-242`; `PROJECT/PDDA.md:439-470`] | Human/LLM-checklist-driven, not an automated verifier *agent* producing a routable report |
| **`capabilities/` overlay layer** | **None** — flat `.claude/skills/` + `.claude/commands/` (project) and `.xyz/skills/` (vendored) with no composed registry/overlay abstraction between authoring surface and runtime projection | **The starkest gap both models independently converged on** — no equivalent trust/fail-closed layer, no per-runtime capability projection |

**License + spillover (agreed):**
- MIT reconfirmed: `gsd-core/LICENSE:1` = "MIT License" (Copyright (c) 2026 Open GSD). Patterns/ideas
  free to reuse; a verbatim copy keeps the notice.
- **Spillover (logged only, not reviewed here):** gsd-core's "author once, transform per runtime"
  installer/capability model [`gsd-core/docs/how-to/install-on-your-runtime.md:9-13`;
  `capabilities/claude/capability.json`; `capabilities/codex/capability.json`] — both advisors
  independently flagged this as directly relevant to
  [GH-102](../2-WORKING/GH-102-XYZ-REBALANCE-INTEGRATION.md) seam #2 (harness release channel). Not
  pursued here per this review's excluded-family scope; pointer only.

**Reconciled call.** Phase 0 exit criteria are met: both families are grounded inventory (not
vibed), the counterpart map is complete (one row corrected per the Disagree adjudication above), the
license is reconfirmed, and the one spillover item is logged as a pointer, not chased. The
`capabilities/` overlay gap is the single highest-signal lead for Phase 2 — both independent models
converged on it unprompted. Ready to `git mv` to `2-WORKING` and proceed to Phase 1/Phase 2.

### Phase 0 — QA checklist
- [x] **Discovery written back.** Inventory + counterpart map recorded above, each grounded, with an
      explicit Disagree/Agree/Reconciled-call structure (consult idiom) — three fabricated agy
      citations caught and REFUTED by direct measurement, corrected before landing in the table.
- [x] **No code changed.** `git status` before this promotion showed only `ROADMAP.md` + this doc.
- [x] **Scope honored.** Only the two in-scope families inventoried; the installer/capability
      spillover appears only as a one-line GH-102 pointer, not reviewed here.
- [x] **Doc hygiene.** `utils/pdda/pdda.sh run` clean for both edited files (the one pre-existing
      ERROR in the run output is on the unrelated `GH-102` doc, out of scope here).

---

## Phase 1 — Family A: phase-loop & context engineering

*(depends on Phase 0 inventory)*

Review gsd's phase loop and context-engineering machinery against our PDDA + `phase-qa` + `snapshot`
+ swarm reality, and grade each pattern.

**Candidate patterns to grade (extend from Phase 0 inventory):**

- [x] **Explicit 5-step loop** (Discuss→Plan→Execute→Verify→Ship) vs. PDDA's INBOX→WORKING→DONE +
      per-phase QA. Gap: do we have an explicit *Discuss* (decisions-before-plan) and *Verify*
      (walk-what-was-built) step, or are they implicit? → graded ADAPT, see Findings.
- [x] **Fresh-context subagents for heavy work** vs. our Agent/Explore subagents + XYZ tick lanes.
      Gap: does gsd have a discipline (context budget, hand-back contract) we lack? → graded ADAPT.
- [x] **Persistent cross-session artifacts** (`STATE.md`, `CONTEXT.md`) vs. `snapshot.md`, PDDA docs,
      `.claude` memory. Gap: is there a durable *project state* file our snapshot doesn't cover? → graded SKIP.
- [x] **Parallel execution waves** vs. XYZ concurrent lanes / relay. Gap: wave orchestration &
      collision rules — does gsd add anything over XYZ's claim/heartbeat model? → graded SKIP (disagreement adjudicated).
- [x] **Verify-before-done gate** (diagnose & fix before declaring done) vs. `doctor`+`pytest`+`pdda`
      + `loose-ends`/`phase-qa`. Gap: any verify-loop shape worth borrowing? → graded ADOPT.

#### Phase 1 — Findings (per-pattern grading)

**Method.** Ran via `consult` (Codex + agy in parallel), same pattern as Phase 0. Transcripts:
[relay-system/2026-07-03/gsd-phase1-124159/](../../relay-system/2026-07-03/gsd-phase1-124159/).
Both advisors well-grounded this time — spot-checked citations against real files across both
transcripts (`PROJECT/PDDA.md`, `ROADMAP.md`, `ROUTER.md`, `phase-qa/SKILL.md`, `snapshot/SKILL.md`,
this doc, and several gsd-core files); no fabrications found (unlike Phase 0's `.xyz/`-local trap —
neither advisor referenced the gitignored local `.xyz/` this time, both correctly used
`xyz-3-agents-swarm` canonical citations instead).

1. **Explicit 5-step loop** — **AGREE: ADAPT** · target `Reb` · effort `S` · payoff `2`.
   Gap: gsd makes Discuss/Verify named, artifact-producing steps
   [`gsd-core/docs/explanation/the-phase-loop.md:23-30,51-59`]; PDDA has lifecycle buckets + QA
   gates + end-of-task `doctor`/`pytest`/`pdda` rails, but no explicit decisions-before-plan or
   goal-backward verify step [`PROJECT/PDDA.md:30-65`; `ROUTER.md:17-27`]. Why: the seam is real,
   but the cheap move is naming the steps inside PDDA, not porting gsd's command stack. First step:
   require a short `Discuss` subsection before execution phases and a `Verification` subsection
   before phase close in phased PDDA docs.

2. **Fresh-context subagents for heavy work** — **converged call, target reconciled: ADAPT** ·
   target `both` · effort `S` · payoff `2`. Codex said target `both`; agy said `Reb` only —
   reconciled toward `both` since `consult` itself (the XYZ-side mechanism) is as much a candidate
   for a stronger hand-back contract as Rebalance's ad-hoc subagents are. Gap: gsd budgets
   orchestrator-vs-subagent context and requires artifact hand-back
   [`gsd-core/docs/explanation/context-engineering.md:26-42,57-66`;
   `multi-agent-orchestration.md:21-27,88-119`]; here the counterpart is `consult` + ad-hoc
   subagents with no formal context-budget or hand-back contract [this doc's Phase 0 Findings].
   First step: add a tiny required return shape to `consult` and subagent prompts — what changed,
   evidence, open questions, next action.

3. **Persistent cross-session artifacts** (`STATE.md`/`CONTEXT.md`) — **AGREE: SKIP** · target
   `both` · effort `S` · payoff `1` (Codex additionally scored the hypothetical build effort `L` —
   same SKIP conclusion, just estimating the road not taken). Gap: none functionally — Rebalance's
   `ROADMAP.md` (pointer ledger) + active `PROJECT/**` docs already serve as canonical state, and
   `snapshot` covers session-level recovery [`ROADMAP.md:9-23`; `PROJECT/PDDA.md:39-41,162-175`;
   `giant-brains-claude-skills/repo-health/snapshot/SKILL.md:14-30`]. Why: a new `STATE.md` would
   duplicate ROADMAP + project-doc state and violate the repo's one-canonical-place discipline; the
   distributed pointer-led model also suits Rebalance's multi-track-at-once reality better than
   gsd's single-milestone model.

4. **Parallel execution waves** — **DISAGREE, adjudicated: SKIP** · target `XYZ` · effort `M` ·
   payoff `1`. Codex called SKIP; agy called ADAPT (payoff `2`, proposing a split-and-merge wrapper
   so XYZ lanes could coordinate edits to one shared file). **Adjudication: side with SKIP.** XYZ's
   own `SKILL.md` explicitly scopes shared-file work OUT by design — "NOT for work that touches
   shared files" and "no shared mutable files" are listed as *preconditions* for using `xyz` at all
   [`xyz-3-agents-swarm/skills/xyz/SKILL.md` — cf. Phase 0 Findings]. Building a split/merge wrapper
   works around that boundary rather than respecting it; central wave orchestration doesn't fix the
   actual constraint here, which is overlapping write surfaces, not missing wave semantics. **Parked
   idea (not dropped):** agy's split/merge concept is worth remembering if a genuine
   shared-file-concurrency need shows up somewhere that isn't fighting XYZ's design intent.

5. **Verify-before-done gate** — **converged call, reconciled: ADOPT** · target `Reb` · effort `S`
   · payoff `3`. Codex called ADOPT (payoff 3); agy called ADAPT (payoff 2) — same substance
   (a structured, automated verification record), different label; reconciled toward ADOPT on
   Codex's sharper diagnosis. Gap: gsd's verifier agent writes `VERIFICATION.md` from goal-backward
   checks over plans/context/code [`gsd-core/docs/explanation/the-phase-loop.md:51-59`;
   `docs/reference/planning-artifacts.md:182-188`; `agents/gsd-verifier.md:15-38`]; Rebalance has
   `doctor`/`pytest`/PDDA/`phase-qa`/`loose-ends`, but those are command/checklist sweeps, not a
   routable phase-close verdict [`ROUTER.md:25-26`; `giant-brains-claude-skills/02-plan/phase-qa/
   SKILL.md:16-25,207-214`; `05-close/loose-ends/SKILL.md:13-22,43-45`]. Why: this is the cleanest
   high-ROI gap — it closes the "green commands, but no phase-goal verdict" hole. First step
   (merging both advisors' proposals): add a PDDA-owned `Verification summary` block for completed
   phases, populated from actual `doctor`/`pytest`/`pdda` results plus unmet acceptance items —
   optionally packaged as a `.claude` skill (agy's framing) rather than a manual PDDA convention
   (Codex's framing); make its absence a phase-close failure.

**Reconciled call for Phase 1:** do #5 first (highest payoff, cleanest gap), then #1, then the light
#2 hand-back contract; #3 and #4 are confirmed SKIPs.

### Phase 1 — QA checklist
- [x] **Every pattern grounded on both sides** (gsd `file:line` + here-counterpart or "none") — spot-checked, no fabrications this phase.
- [x] **Gap stated before every call** — no adopt without the delta.
- [x] **Each call is target-tagged** (XYZ / Reb / both) with effort + payoff.
- [x] **Cheapest-that-works** preferred; the one real disagreement (#4) was adjudicated toward SKIP
      specifically because the ADAPT alternative would have worked around, not adopted, an existing
      design boundary.

---

## Phase 2 — Family B: skill/command/hook/agent architecture

*(depends on Phase 0 inventory)*

Review how gsd structures and *ports* its skill/command/hook/agent/capability catalog, against our
`.claude` ecosystem + the vendored `.xyz/skills`.

**Candidate patterns to grade (extend from Phase 0 inventory):**

- [x] **Skill ↔ agent ↔ command ↔ hook composition** — gsd's unit-of-reuse boundaries vs. our flat
      `.claude/skills` + MCP tools + project hooks. Gap: does gsd's layering reduce duplication or
      improve discoverability? → graded ADAPT (disagreement adjudicated), see Findings.
- [x] **`capabilities/` layer** (39 files) — is there a "capability" abstraction between skill and
      runtime we lack? → graded ADAPT, narrowly scoped (disagreement adjudicated — the consequential call).
- [x] **Cross-runtime portability via installer** — the source-of-truth-then-transform model
      (author once, install per runtime). Gap: relevant to XYZ's vendored-vs-machine-local install
      split (GH-102 Phase 0). → graded SKIP, punted to GH-102.
- [x] **Hook catalog** (22 hooks) vs. our project hooks — any hook pattern (guardrails, context
      protection, gate enforcement) worth borrowing for Reb/XYZ? → graded ADOPT-worthy, two complementary first steps.
- [x] **Skill authoring conventions** (frontmatter/trigger discipline, naming, help/index) vs. our
      SKILL.md conventions + the `.xyz/skills` set. Gap: authoring ergonomics. → graded ADAPT.

#### Phase 2 — Findings (per-pattern grading)

**Method.** Ran via `consult` (Codex + agy in parallel), same pattern as Phase 0/1. Transcripts:
[relay-system/2026-07-03/gsd-phase2-124548/](../../relay-system/2026-07-03/gsd-phase2-124548/).
Spot-checked new citations from both (`.claude/settings.json` — exact 117-line match;
`xyz-3-agents-swarm/relay-automation/hooks/relay-xyz-guard.sh`; `gsd-core/hooks/gsd-read-guard.js`,
`commands/gsd/help.md`, `docs/INVENTORY.md`; `giant-brains-claude-skills/README.md`) — all in-bounds
and accurate. No fabrications this phase either.

1. **Skill ↔ agent ↔ command ↔ hook composition** — **DISAGREE, adjudicated: ADAPT** · target
   `both` · effort `S` · payoff `2`. Codex called ADAPT (a lightweight inventory, not new
   architecture); agy called SKIP (a flat catalog natively suits a single-runtime target and avoids
   token overhead). **Adjudication: side with Codex, but scoped exactly as cheap as agy's SKIP
   concern demands.** Gap: gsd's composition chain is real (grounded in Phase 0); Rebalance/XYZ's
   surface is separate skill/command/hook files with no map from entrypoint to runtime behavior
   [`gsd-core/docs/ARCHITECTURE.md:31-66`; `.claude/commands/ask_self.md:1-23`;
   `.claude/settings.json:1-117`]. This is a documentation exercise, not plumbing — it doesn't
   contradict agy's "flat catalog is fine" position, it just adds a map on top of the flat catalog.
   First step: a small inventory for the real orchestrated flows (`welcome`, `ask_self`/`reingest`,
   `relay-xyz`) listing `skill -> command/tool -> hook -> owner`.

2. **The `capabilities/` layer** — **DISAGREE (the consequential one), adjudicated: ADAPT, narrowly
   scoped** · target `both` · effort `M` · payoff `3`. Codex called ADAPT — explicitly **not** the
   full 39-file overlay/trust engine, but "a minimal bundle manifest for high-risk bundles only:
   `id`, `owner`, `skills`, `commands`, `hooks`, `executables`, `requires`, then generate a read-only
   index" [`gsd-core/docs/explanation/capability-overlay-model.md:16-45,111-180`;
   `capability-trust-model.md:14-39,143-163`]. agy called SKIP, citing YAGNI — "neither target has a
   multi-runtime adaptation or third-party plugin ecosystem to justify the high complexity of a
   dynamic capability-overlay engine." **Adjudication: ADAPT, scoped exactly to Codex's minimal
   manifest — explicitly rejecting the dynamic loader/overlay/trust engine agy is right to flag as
   overkill.** Both Phase-0 advisors independently found this the starkest gap (no composed
   registry/ownership visibility across `.claude/skills` + `.claude/commands` + `.xyz/skills` + MCP
   tools); a static manifest + generated index answers that gap without building anything close to
   gsd's dynamic runtime-injection system agy correctly objects to — the YAGNI risk agy names is
   avoided by scope, not by skipping the pattern outright. First step: a minimal bundle manifest for
   high-risk bundles only (start with `relay-xyz`, `xyz`, `consult` — the ones with real safety
   boundaries), generating a read-only index; no dynamic loader, no trust/overlay engine.

3. **Cross-runtime portability via installer** — **AGREE: SKIP, punted to GH-102** · target `XYZ` ·
   effort `L`/`S` (both scored low-to-moderate; substance agrees) · payoff `1`-`2`. Both models
   independently converged this is install/versioning/release-channel work, explicitly out of this
   review's scope [`gsd-core/docs/how-to/install-on-your-runtime.md:9-13`;
   `xyz-3-agents-swarm/skills/relay-xyz/SKILL.md:41-55,94-115`]. **GH-102 pointer (logged only):**
   gsd's runtime-specific command translation and directory-layout transformation is reference
   material for [GH-102](../2-WORKING/GH-102-XYZ-REBALANCE-INTEGRATION.md) seam #2 (harness release
   channel) — not reviewed further here.

4. **Hook catalog** — **AGREE on direction (ADOPT-worthy), each found a different concrete hook —
   both kept as complementary first steps** · target `Reb` · effort `S` · payoff `3`. Rebalance's
   current PDDA hooks are advisory-only, post-edit/stop scans that always exit `0`
   [`utils/pdda/pdda-edit-doc-hook.sh:12-13,42-55`; `pdda-stop-doc-health.sh:7-20`], while gsd and
   XYZ both use pre-tool guards that can actually block unsafe behavior
   [`gsd-core/hooks/hooks.json:11-38`; `gsd-core/hooks/gsd-read-guard.js:7-19`;
   `xyz-3-agents-swarm/relay-automation/hooks/relay-xyz-guard.sh:20-23,87-108`]. **Two candidate
   first steps, not in conflict:** (a) agy — port gsd's read-before-edit advisory nudge (cheap,
   general-purpose, prevents blind-edit retry loops); (b) Codex — a `PreToolUse` guard that blocks
   direct leaf ingest/refresh shell entrypoints and routes back to `refresh_index`/`doctor`/the
   orchestrator surface (Rebalance-specific, higher-value but narrower). Recommend (a) first (cheaper,
   more universal), (b) as a fast follow-on once (a) proves the hook-wiring pattern works.

5. **Skill authoring conventions** — **AGREE: ADAPT** · target `both` · effort `S` · payoff `2`.
   Gap: the skill corpus already has decent frontmatter/trigger discipline by convention, but
   discoverability depends on README memory and skill names; gsd adds an explicit help/index surface
   [`gsd-core/commands/gsd/help.md:1-27`; `docs/INVENTORY.md:1-11,60-169`;
   `giant-brains-claude-skills/README.md:206-217`]. Why: the prose conventions are already good
   enough — the missing piece is generated discoverability, not stricter writing rules. First step
   (Codex's framing preferred — cheaper to maintain): generate a lightweight skills-help index from
   existing frontmatter (name, one trigger sentence, owner/runtime) rather than hand-authoring a
   dedicated help skill per target (agy's alternative, viable as a fallback if generation proves
   awkward).

**Reconciled call for Phase 2:** hook-first (#4a, cheap and universal) + the scoped `capabilities/`
manifest (#2, the highest-signal gap from Phase 0, deliberately narrow) + the skills-help index (#5);
#1's inventory is a light add-on; #3 stays a GH-102 pointer, not reviewed further here.

### Phase 2 — QA checklist
- [x] **Both sides grounded** per pattern (gsd `file:line` + here-counterpart) — spot-checked, accurate.
- [x] **Over-engineering watch.** The `capabilities/` disagreement was adjudicated specifically to
      avoid YAGNI — ADAPT is scoped to a static manifest, explicitly excluding gsd's dynamic
      overlay/trust engine that agy correctly flagged as premature.
- [x] **Target split honored.** XYZ-facing vs Reb-facing calls kept distinct throughout (e.g. #3 is
      XYZ-only; #4's two first steps are both Reb-specific).
- [x] **Install-mechanics punted.** #3 logged as a one-line GH-102 pointer only, not graded in depth.

---

## Phase 3 — Synthesis: ranked adopt-list, split by target

*(depends on Phases 1–2)*

Consolidate every ADOPT/ADAPT call into one ranked action list, split by target, so the review ends
as a decision surface rather than a catalog.

**Observable checklist:**

- [x] **Ranked table.** All ADOPT/ADAPT calls sorted by ROI (payoff ÷ effort), columns:
      pattern · target · call · effort · payoff · first step · source `file:line`.
- [x] **Split by target.** A short XYZ list and a short Rebalance list (a pattern may appear in both)
      — finding: XYZ has zero unique items, only shared "both" ones.
- [x] **Top-3 recommendation.** Named, with an explicit, non-silent override of strict ROI order for #3.
- [x] **Cross-links.** The installer/portability SKIP is cross-linked to GH-102 seam #2, not duplicated.
- [x] **SKIP ledger.** All 3 skipped patterns logged one-line-each with the reason.
- [x] **Next-action decision.** Recommended per Top-3 item; operator decides which to actually run.

#### Phase 3 — Findings (synthesis)

**Method.** Direct synthesis, no new consult run — Phase 3 consolidates the already-completed
Phase 1/2 findings; there's nothing new to research, only to rank and decide.

**Ranked table** (ROI = payoff ÷ effort, using S=1 / M=2 / L=3):

| # | Pattern | Target | Call | Effort | Payoff | ROI | First step | Source |
|---|---|---|---|---|---|---|---|---|
| 1 | Verify-before-done gate | Reb | ADOPT | S | 3 | **3.0** | PDDA-owned `Verification summary` block (or a `.claude` skill) populated from `doctor`/`pytest`/`pdda` + git diff; its absence becomes a phase-close failure | Phase 1 Findings #5 |
| 2 | Hook catalog — read-before-edit + blocking guard | Reb | ADOPT | S | 3 | **3.0** | (a) port gsd's read-before-edit advisory nudge first (cheap, universal); (b) follow with a `PreToolUse` guard blocking direct leaf ingest/refresh entrypoints | Phase 2 Findings #4 |
| 3 | Fresh-context subagent hand-back contract | both | ADAPT | S | 2 | 2.0 | required return shape (what changed / evidence / open questions / next action) for `consult` and subagent prompts | Phase 1 Findings #2 |
| 4 | Explicit 5-step loop naming | Reb | ADAPT | S | 2 | 2.0 | named `Discuss` and `Verification` subsections in phased PDDA docs | Phase 1 Findings #1 |
| 5 | Skill/agent/command/hook composition inventory | both | ADAPT | S | 2 | 2.0 | one inventory doc: `skill -> command/tool -> hook -> owner` for the real orchestrated flows (`welcome`, `ask_self`/`reingest`, `relay-xyz`) | Phase 2 Findings #1 |
| 6 | Skills-help / discoverability index | both | ADAPT | S | 2 | 2.0 | generate a lightweight skills-help index from existing frontmatter (name, trigger sentence, owner/runtime) | Phase 2 Findings #5 |
| 7 | `capabilities/` overlay — narrow manifest | both | ADAPT | M | 3 | 1.5 | minimal bundle manifest (`id`/`owner`/`skills`/`commands`/`hooks`/`executables`/`requires`) for high-risk bundles only (`relay-xyz`, `xyz`, `consult`) + a generated read-only index — explicitly **not** gsd's dynamic loader/trust engine | Phase 2 Findings #2 |

**A note on the ROI math:** #7 has the lowest formula-ROI but the highest raw payoff (3) and is the
*one* pattern both Phase 0 advisors independently flagged as the starkest structural gap. Raw ROI
treats effort and strategic signal as the same currency; this is the one place in the table where
they diverge — addressed explicitly in the Top-3 call below rather than silently ranked to #7.

**Split by target:**

- **Rebalance-only:** #1 Verify-before-done gate (ADOPT), #2 Hook catalog (ADOPT), #4 Loop naming (ADAPT).
- **XYZ-only:** none. Every XYZ-specific candidate pattern graded SKIP (see SKIP ledger) — XYZ has
  zero unique ADOPT/ADAPT items from this review; its only actionable items are the "both" rows below.
- **Both (Rebalance + XYZ):** #3 Subagent hand-back contract, #5 Composition inventory, #6
  Skills-help index, #7 Capabilities manifest — all ADAPT.

**Top-3 recommendation.** Strict ROI ranking gives #1, #2, and a 4-way tie at 2.0 for third (#3–#6).
**Deliberate override, not a silent ranking:** I'm promoting #7 into the Top-3 ahead of the 2.0-ROI
tier, for the reason stated above — it's the review's single highest-signal finding, and its scoped
adjudication (a static manifest, not gsd's dynamic engine) exists specifically to survive the YAGNI
objection that would otherwise kill it. The displaced tiebreaker (#3, subagent hand-back contract —
picked over #4/#5/#6 because it's immediately self-applicable to this very review's own subagent/
`consult` calls) is named below as the honorable mention.

1. **Verify-before-done gate** (Reb, ADOPT, ROI 3.0). Why now: Rebalance already runs
   `doctor`/`pytest`/`pdda` before every completion claim (`ROUTER.md:17-27`) but produces no
   structured phase-goal verdict — just green commands. One PDDA convention closes the "green
   commands, no verdict" hole for the cost of a doc section, no new tooling required.
2. **Hook catalog: read-before-edit + blocking guard** (Reb, ADOPT, ROI 3.0). Why now: both advisors
   independently found concrete, real gsd/XYZ hook implementations worth porting, and Rebalance's
   current PDDA hooks are advisory-only, post-edit, and always exit `0` — a genuine safety-surface
   gap, not a nice-to-have. The first step (the advisory nudge) is nearly free.
3. **`capabilities/` overlay — narrow manifest** (both, ADAPT, ROI 1.5 by formula — promoted on
   strategic signal). Why now: this is the one pattern **both** Phase 0 advisors converged on
   unprompted as the starkest gap, and the Phase 2 adjudication scoped it to exactly the cheapest
   version that still closes the real ownership/visibility gap across `.claude/skills` +
   `.claude/commands` + `.xyz/skills` + MCP tools — without building anything close to gsd's 39-file
   dynamic engine. Doing this now, while scoped small, is cheaper than doing it later once more
   skills/tools accumulate with no map between them.

*Honorable mention (displaced from strict-ROI #3):* the subagent hand-back contract (#3 in the
table) — cheapest of the "both" items and immediately self-applicable to this review's own future
`consult`/subagent calls.

**SKIP ledger** (reviewed and deliberately not adopted — attestable, not silent):

- **Persistent cross-session artifacts** (`STATE.md`/`CONTEXT.md`-equivalent) — SKIP, both. Gap
  doesn't exist functionally: `ROADMAP.md` + active `PROJECT/**` docs already serve as canonical
  state, and `snapshot` covers session recovery. A new file would duplicate canonical state.
- **Parallel execution waves for XYZ** — SKIP, XYZ. XYZ's own design explicitly excludes shared-file
  work as a precondition, not a gap; central wave orchestration doesn't fix the real constraint
  (overlapping write surfaces). agy's split/merge wrapper idea is parked, not adopted — worth
  revisiting only if a genuine shared-file-concurrency need appears that isn't fighting XYZ's intent.
- **Cross-runtime portability via installer** — SKIP, XYZ, **cross-linked to
  [GH-102](../2-WORKING/GH-102-XYZ-REBALANCE-INTEGRATION.md) seam #2** (harness release channel).
  Both advisors independently placed this in the excluded installer/versioning family; gsd's
  runtime-transform model is reference material for that separate project, not reviewed further here.

**Next-action decision (operator's call, this phase only recommends):**
1. Verify-before-done gate — small enough to land as a direct `PROJECT/PDDA.md` convention update,
   no new GH issue needed.
2. Hook catalog guard — touches `.claude/settings.json` hook wiring (agent-facing behavior change);
   recommend a small tracked capture (GH issue or a lightweight `PROJECT/1-INBOX` doc) rather than
   an inline edit.
3. `capabilities/` narrow manifest — cross-cutting (Reb + XYZ), `M` effort; recommend parking in
   `ROADMAP.md` as a queued item with its own scoped `1-INBOX` capture doc (candidate for a
   `phase-qa` pass given it touches both repos' skill surfaces).

### Phase 3 — QA checklist
- [x] **Every Phase 1–2 call appears** in the ranked table or the SKIP ledger — 7 ADOPT/ADAPT + 3
      SKIP = all 10 graded patterns accounted for, nothing dropped.
- [x] **ROI ranking is defensible** (effort + payoff pulled directly from the Phase 1/2 per-pattern
      calls, not re-vibed; the one override from strict-ROI order is explicitly flagged, not silent).
- [x] **Decision surface, not catalog** — Top-3 + next-action recommendation stand on their own.
- [x] **Doc hygiene.** `utils/pdda/pdda.sh run` clean; doc promoted to `3-COMPLETED` with Status
      table updated (below).

---

## Anti-goals

- **Not a framework port.** We harvest patterns; we don't install gsd-core or restructure our stack
  to match it.
- **Not adopting the excluded families.** Testing-gates and installer/versioning are out of scope;
  they surface only as GH-102 pointers.
- **Not an exhaustive teardown.** ROI-gated harvest, not a research report — skip low-payoff dives.
- **Not verbatim copying without attribution.** MIT reuse of ideas is free; copied files keep the
  notice.
- **Not conflating targets.** XYZ (shell/relay, vendored) and Rebalance (Python/`.claude`, native)
  get distinct recommendations even for the same pattern.

---

## Provenance & verification

- **Source under review:** gsd-core (open-gsd/gsd-core, MIT, npm `@opengsd/gsd-core`) — external
  repo, operator-local checkout (path not repo-portable, omitted per PDDA's hardcoded-path rule; see
  this doc's frontmatter `source:` field). Surface counted 2026-07-03: 70 skills, 34 agents,
  70 commands, 22 hooks, 39 capabilities, 151 src files.
- **Review targets:** XYZ vendored [.xyz/](../../.xyz); Rebalance native (`src/rebalance/`,
  `.claude/`, PDDA).
- **Scope decision (operator, 2026-07-03):** two families (phase-loop/context-engineering +
  skill/command/hook/agent architecture); lens = adopt-recommendation + gap-analysis; one PDDA doc
  in 1-INBOX that morphs into the review.
- **Verification (per ROUTER §7):** `utils/pdda/pdda.sh run` clean before each `git mv` / promotion.
  This is a read/decide review — no `pytest`/`doctor` gate applies unless an adoption later lands code
  (that lands under its own issue/doc).

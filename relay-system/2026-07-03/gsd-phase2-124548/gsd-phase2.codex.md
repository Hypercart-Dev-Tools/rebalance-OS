Reading additional input from stdin...
OpenAI Codex v0.139.0
--------
workdir: /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
model: gpt-5.4
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019f2984-1287-7102-bd8d-fae34dc3cc8c
--------
user
You are an INDEPENDENT advisor in a one-shot cross-model consult. Another model is answering the SAME question separately and a coordinator will reconcile both answers, so give your own honest, specific read — do not hedge toward a consensus you cannot see. Read any repo files the question references (cite file:line). Respond with: (1) a short direct ANSWER; (2) graded FINDINGS — [Blocker]/[Should]/[Nit]/[Pass] — where applicable; (3) a one-line RECOMMENDATION. You are ADVISORY ONLY: output your analysis as text; do not rely on writing files (you are running in a throwaway copy).

=== CONSULT QUESTION ===
You are running Phase 2 of a project review doc that lives in your current worktree at:

    PROJECT/2-WORKING/GSD-CORE-PATTERN-REVIEW.md

Read that file first — it has the full frontmatter, the grading rubric ("## Grading rubric"), the
"## Phase 2 — Family B: skill/command/hook/agent architecture" section with its candidate patterns,
and the already-completed "#### Phase 0 — Findings" block (grounded inventory + counterpart map you
should build on, not re-derive from scratch — it already traced `execute-phase` through skill →
command → workflow → agent → capability, and both Phase-0 advisors independently flagged the
`capabilities/` overlay layer as the starkest gap). This prompt only summarizes it; the doc is
authoritative.

## The task

Grade each Phase 2 candidate pattern (Family B: skill/command/hook/agent architecture) with exactly
one call: **ADOPT**, **ADAPT**, or **SKIP**, per the doc's Grading rubric:
- ADOPT — clear gap, cheap to add, high payoff. Name the target + a concrete first step.
- ADAPT — good idea, but our shape differs; take the concept, not the implementation. Name what to change.
- SKIP — already covered here, or payoff doesn't justify cost, or out of scope. State which.

Every call must carry: **target** (XYZ / Reb / both), **effort** (S/M/L), **payoff** (1-3), and a
one-line **why**. Do NOT skip stating the gap before making a call.

## The five patterns to grade (from the doc's Phase 2 section)

1. **Skill ↔ agent ↔ command ↔ hook composition** — gsd's unit-of-reuse boundaries vs. our flat
   `.claude/skills` + MCP tools + project hooks. Gap to resolve: does gsd's layering reduce
   duplication or improve discoverability over a flat catalog?
2. **The `capabilities/` layer** (39 files in gsd-core) — is there a "capability" abstraction between
   skill and runtime we lack? **Watch for over-engineering (YAGNI)** — this is likely ADAPT or SKIP
   territory, not a blind ADOPT, since Phase 0 already confirmed it's a real, substantive abstraction
   (not cosmetic) but Rebalance/XYZ have real needs to weigh it against (do we actually have a
   multi-runtime problem to solve, or would this be premature structure?).
3. **Cross-runtime portability via installer** ("author once, transform per runtime") — Gap: this is
   directly relevant to XYZ's vendored-vs-machine-local install split (a separate project, GH-102
   Phase 0 seam #2 — harness release channel). If your grading here is really about install
   mechanics/versioning, **punt the detail to a one-line GH-102 pointer note instead of grading it
   fully** — that family is explicitly out of scope for this review (see the doc's non_goals and
   "Two in-scope pattern families" section).
4. **Hook catalog** (22 hooks in gsd-core) vs. Rebalance's project hooks (`utils/pdda/pdda-*-hook.sh`)
   and XYZ's `relay-xyz-guard.sh`. Gap to resolve: any hook pattern (guardrails, context protection,
   gate enforcement) worth borrowing?
5. **Skill authoring conventions** (frontmatter/trigger discipline, naming, help/index) vs. our
   SKILL.md conventions + the `.xyz/skills` set. Gap to resolve: authoring ergonomics — is there a
   convention gsd enforces that ours doesn't (e.g. validated trigger phrasing, a help/index command)?

## Where to read

**gsd-core** (external repo, read by its absolute checkout path — re-read the Phase 0 Findings
block's already-grounded `file:line`s for the composition trace and capabilities model rather than
re-discovering them: `docs/ARCHITECTURE.md`, `agents/gsd-executor.md`, `hooks/hooks.json`,
`docs/explanation/capability-overlay-model.md`, `docs/explanation/capability-trust-model.md`,
`capabilities/*/capability.json`, `docs/how-to/install-on-your-runtime.md`).

**This repo (Rebalance)** — your current worktree: `.claude/skills/`, `.claude/commands/`,
`utils/pdda/pdda-edit-doc-hook.sh`, `utils/pdda/pdda-stop-doc-health.sh`, `.claude/settings.json`.

**Global skill ecosystem** (outside this worktree, absolute path):
- `/Users/noelsaw/.claude/skills/` (mostly symlinks)
- Real source repos: `giant-brains-claude-skills` (general skill catalog) and `xyz-3-agents-swarm`
  (canonical XYZ harness — `.xyz/` in this repo is vendored from it and is GITIGNORED here; prefer
  the canonical `xyz-3-agents-swarm` repo for XYZ-specific citations rather than this worktree's
  `.xyz/`, since the Phase 0 record shows one advisor fabricated line ranges trying to read the
  gitignored local copy directly).

## What to produce

For each of the 5 patterns: (1) the gap (one line, grounded), (2) the call — ADOPT/ADAPT/SKIP,
(3) target, effort, payoff, (4) one-line why, (5) a concrete first step if ADOPT/ADAPT. Cite
`file:line` for any NEW claim not already in the Phase 0 Findings.

Prefer cheapest-that-works. An ADOPT of a whole new abstraction layer (like `capabilities/`) needs to
justify itself against simply extending what's already flat — don't add structure Rebalance/XYZ
don't have a live need for.
hook: SessionStart
hook: SessionStart Completed
codex
I’m reading the Phase 2 review doc first, then I’ll pull the cited repo files it relies on so the grading stays grounded in the existing Phase 0 inventory rather than re-deriving it.
exec
/bin/zsh -lc pwd in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
 succeeded in 0ms:
/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291

exec
/bin/zsh -lc "nl -ba PROJECT/2-WORKING/GSD-CORE-PATTERN-REVIEW.md | sed -n '1,260p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
 succeeded in 0ms:
     1	---
     2	title: "GSD Core pattern review — harvest reusable patterns for XYZ & Rebalance"
     3	owner: Noel
     4	gh_issue: null
     5	source: "gsd-core (open-gsd/gsd-core, MIT, npm @opengsd/gsd-core) — external repo, operator-local checkout, not part of this repo"
     6	status: "In progress (2-WORKING) — Phase 0 inventory complete 2026-07-03 via consult (Codex + agy). This doc IS the review: each phase's Findings block is filled in as the review runs. Phase 1/2 next."
     7	created: 2026-07-03
     8	updated: 2026-07-03
     9	branch: gh-102-xyz-rebalance-integration
    10	doc_type: review
    11	goal: >
    12	  Review the MIT-licensed gsd-core framework and extract the patterns worth reusing across two
    13	  targets — XYZ (the vendored .xyz/ agent-swarm harness in this repo) and Rebalance itself —
    14	  focused on two pattern families: (1) phase-loop & context engineering, (2) skill/command/hook/
    15	  agent architecture. Output is an adopt/adapt/skip call per pattern, each paired with a gap-analysis
    16	  of what Reb/XYZ already have.
    17	non_goals: >
    18	  Not a wholesale port of gsd-core. Not adopting its testing/quality-gate stack (stryker/eslint-rules)
    19	  or its cross-runtime installer/versioning — both explicitly out of scope for this review. Not
    20	  copying code verbatim (MIT attribution would apply if we ever did). Not a comparative teardown /
    21	  research report — the lens is "what do we steal and how", grounded in what already exists here.
    22	related:
    23	  - PROJECT/2-WORKING/GH-102-XYZ-REBALANCE-INTEGRATION.md
    24	  - .xyz/ (vendored XYZ harness)
    25	effort: 2
    26	complexity: 2
    27	risk: 1
    28	phases: 4
    29	license_note: >
    30	  gsd-core is MIT-licensed. Reusing *patterns/ideas* needs no attribution; if any file or substantial
    31	  text/code is copied verbatim, retain the MIT LICENSE + copyright notice at the copy site.
    32	---
    33	
    34	## Status
    35	
    36	| What was just completed | What's next |
    37	|---|---|
    38	| **Phase 0 complete 2026-07-03** — run via `consult` (Codex + agy in parallel, per operator request), not a Claude subagent. Both families grounded (gsd-core's 5-step loop + `.planning/STATE.md`/`CONTEXT.md` + fresh-context subagents + wave execution + verifier gate; the `capabilities/` overlay composition). Counterpart map complete — **the `capabilities/` overlay layer is the starkest gap, independently flagged by both models**: Reb/XYZ have no composed registry/trust abstraction, only flat skill/command directories. One real cross-model disagreement surfaced and adjudicated: agy fabricated 3 out-of-bounds line-range citations against the gitignored vendored `.xyz/` (caught by direct measurement — real files were 55–335 lines vs. agy's cited ranges up to 4495); Codex correctly flagged `.xyz/` as invisible to its sandboxed worktree and substituted verified `xyz-3-agents-swarm` canonical citations instead. Full method + adjudication in [Phase 0 Findings](#phase-0--inventory--counterpart-map). Execution plan validated earlier the same day via XYZ's vendored `bin/marathon-yaml` (`p0→p1→p2→p3`, no cycles; `p1`/`p2` structurally parallel-eligible). | **Run Phase 1 + Phase 2** (graded adopt/adapt/skip review) — optionally as two parallel subagents per the execution-plan's concurrency note, since they're independent given Phase 0. The `capabilities/` gap found in Phase 0 is the highest-signal lead for Phase 2. Then Phase 3 synthesizes the ranked adopt-list split by target. |
    39	
    40	---
    41	
    42	## Table of contents
    43	
    44	- [Thesis & shape](#thesis--shape)
    45	- [Review invariants](#review-invariants)
    46	- [Two review targets](#two-review-targets)
    47	- [Two in-scope pattern families (+ what's excluded)](#two-in-scope-pattern-families)
    48	- [Grading rubric (adopt / adapt / skip)](#grading-rubric)
    49	- [Execution plan — XYZ marathon serialization](#execution-plan--xyz-marathon-serialization)
    50	- [Phase 0 — Inventory & counterpart map](#phase-0--inventory--counterpart-map) _(discovery)_
    51	- [Phase 1 — Family A: phase-loop & context engineering](#phase-1--family-a-phase-loop--context-engineering)
    52	- [Phase 2 — Family B: skill/command/hook/agent architecture](#phase-2--family-b-skillcommandhookagent-architecture)
    53	- [Phase 3 — Synthesis: ranked adopt-list, split by target](#phase-3--synthesis-ranked-adopt-list-split-by-target)
    54	- [Anti-goals](#anti-goals)
    55	- [Provenance & verification](#provenance--verification)
    56	
    57	---
    58	
    59	## Thesis & shape
    60	
    61	> **Thesis:** gsd-core and our stack solve the *same* problem — keeping AI agents disciplined and
    62	> honest as context fills — with independently-evolved machinery. gsd-core is further along on two
    63	> axes we care about: an explicit **five-step phase loop** (Discuss → Plan → Execute → Verify →
    64	> Ship) with fresh-context subagents, and a **large, cross-runtime-portable skill/command/hook**
    65	> catalog. We already have analogues (PDDA phases, `phase-qa`, `snapshot`, the relay/swarm harness,
    66	> the `.claude` skill ecosystem). The review's job is to find where gsd's version is *better shaped*
    67	> than ours and produce a graded, cheap-first adopt list — not to port a framework.
    68	
    69	**Method:** for each pattern, answer four questions — (1) what gsd-core does (grounded in
    70	`file:line`), (2) what XYZ / Rebalance already have for it, (3) the **gap**, (4) an **adopt / adapt /
    71	skip** call with an effort estimate and the target it applies to. The plan *is* the deliverable: the
    72	Findings blocks below are filled as the review runs.
    73	
    74	---
    75	
    76	## Review invariants
    77	
    78	These hold across every phase; a finding that violates one is wrong, not merely weak.
    79	
    80	1. **Grounded, not vibed.** Every claim about gsd-core cites a `file:line` or an example artifact;
    81	   every "we already have this" cites the counterpart here. Ungrounded claims are marked UNVERIFIED.
    82	2. **Gap-analysis before adopt.** No adopt call is made without first stating what already exists —
    83	   the ROI is the *delta*, not the feature in isolation.
    84	3. **Cheapest-that-works.** Prefer adapting an existing surface (a PDDA phase, a `.claude` skill, an
    85	   XYZ shim) over standing up a gsd-shaped subsystem. "Adopt the idea, not the plumbing."
    86	4. **Target-aware.** Each pattern is tagged for **XYZ**, **Rebalance**, or **both** — the two have
    87	   different owners, languages (XYZ = shell/relay shims; Reb = Python), and install surfaces.
    88	5. **License-clean.** Patterns are free to reuse; verbatim copies retain gsd-core's MIT notice.
    89	6. **ROI-gated (per operator standing pref).** Skip deep dives on patterns with obviously low payoff;
    90	   this is a scoped harvest, not an exhaustive teardown.
    91	
    92	---
    93	
    94	## Two review targets
    95	
    96	| Target | Where | Language/shape | What "reuse" means here |
    97	|---|---|---|---|
    98	| **XYZ** | vendored [.xyz/](../../.xyz) — `skills/`, `relay-automation/`, `src/`, `bin/` | shell + relay shims, skill markdown | Improve the swarm/relay harness & its skill ergonomics |
    99	| **Rebalance** | this repo — `src/rebalance/`, `.claude/`, PDDA (`utils/pdda/`), `PROJECT/` | Python + `.claude` skills/hooks + PDDA docs | Improve the phase discipline, doc lifecycle, and skill/agent structure |
   100	
   101	---
   102	
   103	## Two in-scope pattern families
   104	
   105	**In scope (operator-selected):**
   106	
   107	- **Family A — Phase-loop & context engineering.** gsd's Discuss→Plan→Execute→Verify→Ship loop;
   108	  fresh-context subagents for heavy work; persistent cross-session artifacts (`STATE.md`,
   109	  `CONTEXT.md`). Counterparts here: PDDA 1-INBOX→2-WORKING→3-DONE lifecycle, `phase-qa`, `snapshot`,
   110	  `relay`/`xyz` swarm, the collector/ingest pipeline.
   111	- **Family B — Skill/command/hook/agent architecture.** How gsd structures 70 skills / 34 agents /
   112	  70 commands / 22 hooks / 39 capabilities and keeps them portable across runtimes. Counterparts
   113	  here: `~/.claude/skills/*`, the vendored `.xyz/skills/*`, project hooks, MCP tools.
   114	
   115	**Deliberately excluded (this review):** testing/quality gates (stryker mutation, eslint-rules,
   116	TESTING-STANDARDS, coderabbit) and install/versioning/release-channel (cross-runtime installer,
   117	VERSIONING, changesets). *Note:* the install/versioning family overlaps GH-102 seam #2 — if a
   118	compelling pattern surfaces incidentally, log it as a one-line pointer for GH-102, do not review it
   119	here.
   120	
   121	---
   122	
   123	## Grading rubric
   124	
   125	Each reviewed pattern gets exactly one call:
   126	
   127	- **ADOPT** — clear gap, cheap to add, high payoff. Names the target + a concrete first step.
   128	- **ADAPT** — good idea, but our shape differs; take the concept, not the implementation. Names what
   129	  to change.
   130	- **SKIP** — already covered here, or payoff doesn't justify cost, or out of scope. States which.
   131	
   132	Every call carries: **target** (XYZ / Reb / both), **effort** (S/M/L), **payoff** (1-3), and a
   133	one-line **why**.
   134	
   135	---
   136	
   137	## Execution plan — XYZ marathon serialization
   138	
   139	**Tooling gap found:** the operator asked to run XYZ's `swarm-preflight` step to generate this plan.
   140	`utils/swarm-preflight.sh` (readiness packet: `run-candidate.json` / `lane-plan.json` / `packet.md` /
   141	`marathon-invocation.txt`) is referenced by [.xyz/test/swarm-preflight.sh](../../.xyz/test/swarm-preflight.sh)
   142	but is **not part of this repo's vendored `.xyz/` copy** (`find .xyz -iname '*preflight*'` returns only
   143	the test file — the vendor only shipped `bin/`, `relay-automation/`, `skills/`, `src/`, `test/`). That
   144	readiness-gate step could not literally be run. What **is** vendored and *was* run: the multi-phase
   145	planner itself — [bin/marathon-yaml](../../.xyz/bin/marathon-yaml) (schema validate + topological
   146	`depends_on` resolve, the same primitive `marathon.sh`/`swarm-preflight` build on) — against a
   147	hand-authored `MARATHON.yaml` for this review's four phases.
   148	
   149	**The plan** (`gsd-core-pattern-review`):
   150	
   151	```yaml
   152	name: gsd-core-pattern-review
   153	phases:
   154	  - id: p0
   155	    name: Inventory and counterpart map
   156	    reviewer: codex
   157	    brief: PROJECT/1-INBOX/GSD-CORE-PATTERN-REVIEW.md
   158	    artifact: PROJECT/1-INBOX/GSD-CORE-PATTERN-REVIEW.md
   159	    max_review_rounds: 2
   160	
   161	  - id: p1
   162	    name: Family A grading - phase-loop and context engineering
   163	    reviewer: codex
   164	    brief: PROJECT/1-INBOX/GSD-CORE-PATTERN-REVIEW.md
   165	    artifact: PROJECT/1-INBOX/GSD-CORE-PATTERN-REVIEW.md
   166	    depends_on: p0
   167	    max_review_rounds: 2
   168	
   169	  - id: p2
   170	    name: Family B grading - skill/command/hook/agent architecture
   171	    reviewer: gemini
   172	    brief: PROJECT/1-INBOX/GSD-CORE-PATTERN-REVIEW.md
   173	    artifact: PROJECT/1-INBOX/GSD-CORE-PATTERN-REVIEW.md
   174	    depends_on: p0
   175	    max_review_rounds: 2
   176	
   177	  - id: p3
   178	    name: Synthesis - ranked adopt-list split by target
   179	    reviewer: codex
   180	    brief: PROJECT/1-INBOX/GSD-CORE-PATTERN-REVIEW.md
   181	    artifact: PROJECT/1-INBOX/GSD-CORE-PATTERN-REVIEW.md
   182	    depends_on: p2
   183	    max_review_rounds: 2
   184	```
   185	
   186	**Resolved serial order** (real output, `node .xyz/bin/marathon-yaml <plan> --format tsv`; parsed and
   187	validated clean — no duplicate ids, no unknown `depends_on`, no cycle):
   188	
   189	| # | id | reviewer | round-cap | depends_on | phase |
   190	|---|----|----------|-----------|------------|-------|
   191	| 1 | p0 | codex  | 5 | — | Inventory and counterpart map |
   192	| 2 | p1 | codex  | 5 | p0 | Family A grading |
   193	| 3 | p2 | gemini | 5 | p0 | Family B grading |
   194	| 4 | p3 | codex  | 5 | p2 | Synthesis |
   195	
   196	**Parallelism/concurrency analysis (honest, tool-grounded):**
   197	
   198	- **`marathon.sh` itself is strictly serial.** Its own header states cross-phase concurrency is
   199	  "deliberately deferred" — it runs each resolved phase through `marathon-drive.sh` one at a time,
   200	  advances only on approval, and halts on first failure. There is no flag or mode that fans phases out
   201	  concurrently, so the resolver above always emits one linear order even when phases don't depend on
   202	  each other.
   203	- **`p1` and `p2` ARE structurally independent** — both list `depends_on: p0` only, not each other.
   204	  The resolver places `p2` right after `p1` purely because it preserves authoring order among
   205	  equally-ready nodes (confirmed by reading `resolveOrder` in
   206	  [src/marathon-yaml.js](../../.xyz/src/marathon-yaml.js)), not because of a real ordering constraint.
   207	  This is genuine parallel-eligible work: Family A and Family B are independent gsd-core reading tracks.
   208	- **XYZ's actual concurrency primitive (`xyz` skill / `tick` lanes) doesn't fit this case.** It requires
   209	  non-overlapping, path-scoped lanes — but `p1` and `p2` both write into the **same** shared doc (this
   210	  file), just different `Findings` sections. Two agents editing one file concurrently is exactly what
   211	  the lane model is built to prevent, not enable.
   212	- **Practical concurrency lever for this review:** run Phase 1 and Phase 2 as two parallel research
   213	  subagents (native Agent-tool fan-out, no XYZ tick/relay machinery needed — this is single-operator
   214	  research, not multi-CLI construction) into two independent scratch findings, then merge both into
   215	  this doc's `Findings` blocks before Phase 3. This gets the real wall-clock win the DAG allows without
   216	  fighting the same-file constraint.
   217	- **Live `marathon.sh` execution deliberately not fired.** Actually running `marathon.sh --plan …`
   218	  would acquire the repo's global `.relay-driver.lock`, spin up real headless codex/gemini relay turns
   219	  with git commits per phase, and require each phase's `brief`/`artifact` to be real non-overlapping
   220	  files — all disproportionate machinery for a single-operator read/decide review. The plan above is
   221	  validated and ready if a future phase (e.g. code lands from an ADOPT call) warrants a real cross-model
   222	  gate; this review's four phases run under normal PDDA discipline instead (per-phase QA checklist,
   223	  doc-only `git status`).
   224	
   225	---
   226	
   227	## Phase 0 — Inventory & counterpart map
   228	
   229	*(discovery — findings MUST be written back before the QA gate passes; no code written)*
   230	
   231	**Goal:** produce the grounded inventory both review phases build on — for the two in-scope families
   232	only — and map each gsd pattern to its existing counterpart (or "none") here.
   233	
   234	**Observable checklist:**
   235	
   236	- [x] **Family A inventory.** Read gsd-core's phase-loop docs & skills — at minimum
   237	      `docs/explanation/the-phase-loop.md`, `docs/explanation/context-engineering.md`,
   238	      `docs/ARCHITECTURE.md`, and the driving skills (`skills/gsd-discuss-phase/`,
   239	      `gsd-plan-phase`/`gsd-execute-phase`/`gsd-audit-*`/`gsd-complete-milestone`). Record the loop's
   240	      real artifacts (`STATE.md`, `CONTEXT.md`, phase files) with paths + example shape.
   241	- [x] **Family B inventory.** Characterize how `skills/`, `agents/`, `commands/`, `hooks/`,
   242	      `capabilities/` relate (what's the unit of reuse, how do they compose, how does the installer
   243	      make them cross-runtime). Record the directory contract + one worked example (one skill traced
   244	      through to its agent/command/hook).
   245	- [x] **Counterpart map.** For each notable gsd pattern, name the existing here-counterpart:
   246	      PDDA lifecycle, `phase-qa`, `snapshot`, `relay`/`relay-xyz`/`xyz`, `.claude/skills`, project
   247	      hooks, MCP tools, the `.xyz/` vendored skills — or "none".
   248	- [x] **License note confirmed.** Re-confirm gsd-core LICENSE = MIT; record the one-line reuse rule.
   249	- [x] **Excluded-family spillover log.** If any install/versioning pattern jumps out (GH-102 seam #2
   250	      relevance), capture it as a single pointer line — do not review it here.
   251	
   252	**Exit criteria:** the two-family inventory is grounded (`file:line` / example per pattern), the
   253	counterpart map is complete (every gsd pattern → here-analogue or "none"), and this doc is ready to
   254	`git mv` to `2-WORKING`.
   255	
   256	#### Phase 0 — Findings
   257	
   258	**Method.** Ran via `consult` (per the operator's request to use Codex + agy as the agents), not a
   259	Claude subagent: `.xyz/relay-automation/consult.sh --models codex,agy` fanned the same Phase-0
   260	question to both in parallel, `CONSULT_ROOT` = this repo, question referenced gsd-core by its

exec
/bin/zsh -lc "find /Users/noelsaw -maxdepth 3 \\( -name gsd-core -o -name xyz-3-agents-swarm -o -name giant-brains-claude-skills \\) -type d 2>/dev/null" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
 exited 1 in 230ms:
/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills
/Users/noelsaw/Documents/GH Repos/gsd-core
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm

codex
I have the review doc and the external repo locations. Next I’m pulling the Phase 0 findings block plus the exact Phase 2 candidate section, then I’ll verify only the delta claims against the cited gsd-core/Rebalance/XYZ files.
exec
/bin/zsh -lc "nl -ba PROJECT/2-WORKING/GSD-CORE-PATTERN-REVIEW.md | sed -n '256,520p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
 succeeded in 0ms:
   256	#### Phase 0 — Findings
   257	
   258	**Method.** Ran via `consult` (per the operator's request to use Codex + agy as the agents), not a
   259	Claude subagent: `.xyz/relay-automation/consult.sh --models codex,agy` fanned the same Phase-0
   260	question to both in parallel, `CONSULT_ROOT` = this repo, question referenced gsd-core by its
   261	operator-local absolute checkout path (not repo-portable, omitted here — see `source:` in this
   262	doc's frontmatter) and this repo/global skills by relative/absolute path. Both answered
   263	(`2 answered, 0 failed`). Transcripts:
   264	[relay-system/2026-07-03/gsd-phase0-122028/](../../relay-system/2026-07-03/gsd-phase0-122028/)
   265	(`gsd-phase0.codex.md`, `gsd-phase0.agy.md`).
   266	
   267	**Disagree (adjudicated first, per consult discipline — don't average away the delta).**
   268	
   269	- **Whether the vendored `.xyz/` was actually visible to either advisor.** `.xyz/` is gitignored
   270	  here (`.gitignore:71`, `git ls-files .xyz` = 0 tracked files) — `consult.sh`'s throwaway worktree
   271	  only copies tracked + untracked-**not-ignored** files, so `.xyz/` should have been invisible to
   272	  both. **Codex** (runs `-s read-only`) correctly reported it absent — saw only `.xyz-pin`, marked
   273	  every local-`.xyz/` claim UNVERIFIED, and substituted citations from the canonical
   274	  `xyz-3-agents-swarm` source repo instead (the repo `.xyz/` is vendored from). I spot-checked those
   275	  substitute citations directly — **accurate and in-bounds**
   276	  (`xyz-3-agents-swarm/src/marathon-yaml.js` is 149 lines; Codex's cited `98-146` fits;
   277	  `skills/xyz/SKILL.md:22-34,38-49` content matches verbatim). **agy** (no OS sandbox — the consult
   278	  skill's own caveat: "can still reach the network / the host outside the worktree") read `.xyz/`
   279	  via the real absolute path anyway, bypassing the intended isolation. Its frontmatter citation
   280	  (`​.xyz/skills/xyz/SKILL.md:4-11`) checks out verbatim — but three other `.xyz/`-local citations
   281	  are **fabricated, out-of-bounds line ranges**, confirmed by direct measurement: agy cited
   282	  `.xyz/src/project.js:589-631` (real file is **335 lines** — the range doesn't exist);
   283	  `.xyz/relay-automation/hooks/relay-xyz-guard.sh:1-4495` (real file is **113 lines**);
   284	  `utils/pdda/pdda-edit-doc-hook.sh:1-2444` (real file is **55 lines**). **Adjudication: REFUTED** —
   285	  agy's "Parallel Execution Waves" and "Modular Hook System" counterpart-map citations for `.xyz/`
   286	  are not grounded reads; they're replaced below with Codex's (verified) canonical-repo citations.
   287	  Its underlying architectural claim (XYZ uses `tick`'s shared event log + path-scoped lanes) is
   288	  independently correct — only the specific line-range citations were fabricated, not the concept.
   289	- **Process finding (worth remembering for future consults):** a gitignored vendored directory
   290	  referenced by *relative* path in a consult question is a silent trap — a sandboxed advisor (Codex)
   291	  honestly loses it and says so; an unsandboxed advisor (agy) may still reach it via the real absolute
   292	  path on disk, but that reach isn't guaranteed reliable (it fabricated ranges for the larger files
   293	  here). Future consults over a gitignored tree should reference it by **absolute path explicitly**
   294	  in the prompt (as this one did for gsd-core, where both models cited it correctly) rather than
   295	  relying on the worktree copy.
   296	- **Minor, not a real disagreement:** agy's own answer internally wavers between "no Rebalance
   297	  counterpart" and "ad-hoc `ask_self`/Agent-tool counterpart" for fresh-context subagents. Resolved
   298	  in the Agree section below in the more precise direction both models actually support.
   299	
   300	**Agree (cross-model convergence — higher confidence).**
   301	
   302	*Family A — phase-loop & context engineering (gsd-core):*
   303	- The loop is explicit and command-driven: Discuss → (UI design) → Plan → Execute → Verify → Ship
   304	  [`gsd-core/docs/explanation/the-phase-loop.md:11-15,23-59`].
   305	- Persisted through `.planning/`: `STATE.md` is compact living memory (read every workflow start,
   306	  written after significant actions: `active_phase`, `next_action`, progress counters); per-phase
   307	  artifacts are `CONTEXT.md` (sealed decision record — fixed `<domain>/<decisions>/<canonical_refs>/
   308	  <code_context>/<specifics>/<deferred>` blocks), `RESEARCH.md`, `PLAN.md`, `SUMMARY.md`,
   309	  `VERIFICATION.md`, `UAT.md` [`gsd-core/docs/reference/state-md.md:9-76`; `context-md.md:21-92`;
   310	  `planning-artifacts.md:9-189`].
   311	- Fresh-context subagents are the explicit anti-context-rot mechanism: the orchestrator stays thin;
   312	  researcher/planner/executor/verifier agents start clean and read only what they need
   313	  [`gsd-core/docs/explanation/context-engineering.md:26-66`; `multi-agent-orchestration.md:21-55`].
   314	- Execution is wave-based: plans declare dependencies/waves, Wave 1 runs in parallel worktrees,
   315	  later waves wait, executors write `SUMMARY.md` + atomic commits
   316	  [`gsd-core/docs/explanation/multi-agent-orchestration.md:88-136`; `plan-md.md:27-76,218-240`].
   317	- "Done" is verifier-gated, not completion-gated: a verifier checks `must_haves`/coverage/goal
   318	  alignment and emits routable `VERIFICATION.md` statuses
   319	  [`gsd-core/docs/explanation/the-phase-loop.md:51-59`; `planning-artifacts.md:182-189`].
   320	
   321	*Family B — skill/command/hook/agent architecture (gsd-core):*
   322	- Composition traced concretely through `execute-phase`: skill entrypoint
   323	  [`gsd-core/skills/gsd-execute-phase/SKILL.md:1-66`] → command surface
   324	  [`commands/gsd/execute-phase.md:1-66`] → workflow orchestrator (init, checkpoints, worktree
   325	  branch gates) [`gsd-core/workflows/execute-phase.md`] → `gsd-executor` agent (owns the
   326	  plan-execution contract, task commits, deviations) [`agents/gsd-executor.md:14-160`] → runtime
   327	  hooks (compaction/stop/file-change monitors) [`hooks/hooks.json:11-68`].
   328	- The `capabilities/` layer is a **real declarative abstraction, not cosmetic naming**: runtime
   329	  capabilities (`capabilities/claude/`, `capabilities/codex/`) define install roots, artifact
   330	  layout, hook surfaces, command styles per runtime; feature capabilities (e.g. `research`,
   331	  `nyquist`) inject loop steps/config keys/agents/artifacts; an overlay model composes all of it
   332	  into one validated registry with fail-closed trust rules for executable surfaces
   333	  [`gsd-core/docs/explanation/capability-overlay-model.md:18-151`; `capability-trust-model.md:16-254`;
   334	  `capabilities/nyquist/capability.json:1-51`].
   335	
   336	*Counterpart map (Rebalance / XYZ) — agreed, corrected per the Disagree adjudication above:*
   337	
   338	| gsd-core pattern | Counterpart here | Gap |
   339	|---|---|---|
   340	| 5-step loop | PDDA's `1-INBOX→2-WORKING→3-DONE` lifecycle + per-phase QA checklists (this doc is an instance) [`PROJECT/PDDA.md:30-66`] | Doc/checklist-driven, not command/agent-driven — no `/gsd:discuss-phase`-style entrypoint |
   341	| `STATE.md` | `ROADMAP.md` (pointer ledger) + active `PROJECT/**` docs as canonical state; session-level → `snapshot` skill [`ROADMAP.md:9-23`; `giant-brains-claude-skills/repo-health/snapshot/SKILL.md:14-60`] | No single compact living-memory file; state is spread across the ledger + per-project docs |
   342	| `CONTEXT.md` | PDDA's "write findings back into the originating doc" convention + this doc's own Findings/QA blocks [`PROJECT/PDDA.md:162-175`] | No standalone sealed decision artifact with fixed structured fields |
   343	| Fresh-context subagents | `consult` (parallel advisory fan-out, this very Phase 0 run) + ad-hoc Agent-tool subagents; no formal context-budget/hand-back contract | Different shape — advisory fan-out and general subagent use, not a phase-loop researcher/planner/executor/verifier cast |
   344	| Parallel execution waves | XYZ's `tick`-based non-overlapping path-scoped lanes [`xyz-3-agents-swarm/skills/xyz/SKILL.md:22-49`] + marathon `depends_on` DAG resolution [`xyz-3-agents-swarm/src/marathon-yaml.js:98-146`] | Lane/claim model (path-scoped, agent-symmetric), not centrally-orchestrated dependency-waved worktrees; this review's own execution-plan section already found the DAG-vs-lane mismatch when phases share one file |
   345	| Verify-before-done gate | `phase-qa` skill + PDDA QA/doc-readiness gates [`giant-brains-claude-skills/02-plan/phase-qa/SKILL.md:16-26,193-242`; `PROJECT/PDDA.md:439-470`] | Human/LLM-checklist-driven, not an automated verifier *agent* producing a routable report |
   346	| **`capabilities/` overlay layer** | **None** — flat `.claude/skills/` + `.claude/commands/` (project) and `.xyz/skills/` (vendored) with no composed registry/overlay abstraction between authoring surface and runtime projection | **The starkest gap both models independently converged on** — no equivalent trust/fail-closed layer, no per-runtime capability projection |
   347	
   348	**License + spillover (agreed):**
   349	- MIT reconfirmed: `gsd-core/LICENSE:1` = "MIT License" (Copyright (c) 2026 Open GSD). Patterns/ideas
   350	  free to reuse; a verbatim copy keeps the notice.
   351	- **Spillover (logged only, not reviewed here):** gsd-core's "author once, transform per runtime"
   352	  installer/capability model [`gsd-core/docs/how-to/install-on-your-runtime.md:9-13`;
   353	  `capabilities/claude/capability.json`; `capabilities/codex/capability.json`] — both advisors
   354	  independently flagged this as directly relevant to
   355	  [GH-102](../2-WORKING/GH-102-XYZ-REBALANCE-INTEGRATION.md) seam #2 (harness release channel). Not
   356	  pursued here per this review's excluded-family scope; pointer only.
   357	
   358	**Reconciled call.** Phase 0 exit criteria are met: both families are grounded inventory (not
   359	vibed), the counterpart map is complete (one row corrected per the Disagree adjudication above), the
   360	license is reconfirmed, and the one spillover item is logged as a pointer, not chased. The
   361	`capabilities/` overlay gap is the single highest-signal lead for Phase 2 — both independent models
   362	converged on it unprompted. Ready to `git mv` to `2-WORKING` and proceed to Phase 1/Phase 2.
   363	
   364	### Phase 0 — QA checklist
   365	- [x] **Discovery written back.** Inventory + counterpart map recorded above, each grounded, with an
   366	      explicit Disagree/Agree/Reconciled-call structure (consult idiom) — three fabricated agy
   367	      citations caught and REFUTED by direct measurement, corrected before landing in the table.
   368	- [x] **No code changed.** `git status` before this promotion showed only `ROADMAP.md` + this doc.
   369	- [x] **Scope honored.** Only the two in-scope families inventoried; the installer/capability
   370	      spillover appears only as a one-line GH-102 pointer, not reviewed here.
   371	- [x] **Doc hygiene.** `utils/pdda/pdda.sh run` clean for both edited files (the one pre-existing
   372	      ERROR in the run output is on the unrelated `GH-102` doc, out of scope here).
   373	
   374	---
   375	
   376	## Phase 1 — Family A: phase-loop & context engineering
   377	
   378	*(depends on Phase 0 inventory)*
   379	
   380	Review gsd's phase loop and context-engineering machinery against our PDDA + `phase-qa` + `snapshot`
   381	+ swarm reality, and grade each pattern.
   382	
   383	**Candidate patterns to grade (extend from Phase 0 inventory):**
   384	
   385	- [ ] **Explicit 5-step loop** (Discuss→Plan→Execute→Verify→Ship) vs. PDDA's INBOX→WORKING→DONE +
   386	      per-phase QA. Gap: do we have an explicit *Discuss* (decisions-before-plan) and *Verify*
   387	      (walk-what-was-built) step, or are they implicit? → grade.
   388	- [ ] **Fresh-context subagents for heavy work** vs. our Agent/Explore subagents + XYZ tick lanes.
   389	      Gap: does gsd have a discipline (context budget, hand-back contract) we lack? → grade.
   390	- [ ] **Persistent cross-session artifacts** (`STATE.md`, `CONTEXT.md`) vs. `snapshot.md`, PDDA docs,
   391	      `.claude` memory. Gap: is there a durable *project state* file our snapshot doesn't cover? → grade.
   392	- [ ] **Parallel execution waves** vs. XYZ concurrent lanes / relay. Gap: wave orchestration &
   393	      collision rules — does gsd add anything over XYZ's claim/heartbeat model? → grade.
   394	- [ ] **Verify-before-done gate** (diagnose & fix before declaring done) vs. `doctor`+`pytest`+`pdda`
   395	      + `loose-ends`/`phase-qa`. Gap: any verify-loop shape worth borrowing? → grade.
   396	
   397	#### Phase 1 — Findings (per-pattern grading)
   398	<!-- FILL: for each pattern — (1) gsd does X [file:line]; (2) we have Y [ref]; (3) gap; (4) ADOPT/ADAPT/SKIP · target · effort S/M/L · payoff 1-3 · why. -->
   399	_(not yet run)_
   400	
   401	### Phase 1 — QA checklist
   402	- [ ] **Every pattern grounded on both sides** (gsd `file:line` + here-counterpart or "none").
   403	- [ ] **Gap stated before every call** — no adopt without the delta.
   404	- [ ] **Each call is target-tagged** (XYZ / Reb / both) with effort + payoff.
   405	- [ ] **Cheapest-that-works** preferred; any "stand up new subsystem" call is justified against
   406	      adapting an existing surface.
   407	
   408	---
   409	
   410	## Phase 2 — Family B: skill/command/hook/agent architecture
   411	
   412	*(depends on Phase 0 inventory)*
   413	
   414	Review how gsd structures and *ports* its skill/command/hook/agent/capability catalog, against our
   415	`.claude` ecosystem + the vendored `.xyz/skills`.
   416	
   417	**Candidate patterns to grade (extend from Phase 0 inventory):**
   418	
   419	- [ ] **Skill ↔ agent ↔ command ↔ hook composition** — gsd's unit-of-reuse boundaries vs. our flat
   420	      `.claude/skills` + MCP tools + project hooks. Gap: does gsd's layering reduce duplication or
   421	      improve discoverability? → grade.
   422	- [ ] **`capabilities/` layer** (39 files) — is there a "capability" abstraction between skill and
   423	      runtime we lack? → grade (likely ADAPT or SKIP; watch for over-engineering per YAGNI).
   424	- [ ] **Cross-runtime portability via installer** — the source-of-truth-then-transform model
   425	      (author once, install per runtime). Gap: relevant to XYZ's vendored-vs-machine-local install
   426	      split (GH-102 Phase 0). → grade; if install-mechanics, punt detail to GH-102.
   427	- [ ] **Hook catalog** (22 hooks) vs. our project hooks — any hook pattern (guardrails, context
   428	      protection, gate enforcement) worth borrowing for Reb/XYZ? → grade.
   429	- [ ] **Skill authoring conventions** (frontmatter/trigger discipline, naming, help/index) vs. our
   430	      SKILL.md conventions + the `.xyz/skills` set. Gap: authoring ergonomics. → grade.
   431	
   432	#### Phase 2 — Findings (per-pattern grading)
   433	<!-- FILL: same 4-part shape + graded call per pattern. -->
   434	_(not yet run)_
   435	
   436	### Phase 2 — QA checklist
   437	- [ ] **Both sides grounded** per pattern (gsd `file:line` + here-counterpart).
   438	- [ ] **Over-engineering watch.** Any adopt of an extra abstraction layer (e.g. `capabilities/`) is
   439	      justified against YAGNI — we don't add a layer just because gsd has one.
   440	- [ ] **Target split honored.** XYZ-facing (shell/relay skill) vs Reb-facing (`.claude`/Python)
   441	      recommendations are not conflated.
   442	- [ ] **Install-mechanics punted.** Anything that's really seam-#2/versioning is logged as a GH-102
   443	      pointer, not reviewed here.
   444	
   445	---
   446	
   447	## Phase 3 — Synthesis: ranked adopt-list, split by target
   448	
   449	*(depends on Phases 1–2)*
   450	
   451	Consolidate every ADOPT/ADAPT call into one ranked action list, split by target, so the review ends
   452	as a decision surface rather than a catalog.
   453	
   454	**Observable checklist:**
   455	
   456	- [ ] **Ranked table.** All ADOPT/ADAPT calls sorted by ROI (payoff ÷ effort), columns:
   457	      pattern · target · call · effort · payoff · first step · source `file:line`.
   458	- [ ] **Split by target.** A short XYZ list and a short Rebalance list (a pattern may appear in both).
   459	- [ ] **Top-3 recommendation.** Name the 3 highest-ROI adoptions with a one-paragraph "why now".
   460	- [ ] **Cross-links.** Any adoption that touches GH-102 seams (esp. install/versioning spillover) is
   461	      cross-linked, not duplicated.
   462	- [ ] **SKIP ledger.** A one-line-each list of what was reviewed and deliberately skipped (so the
   463	      "no" decisions are attestable, not silent).
   464	- [ ] **Next-action decision.** For each Top-3: open a GH issue / PDDA doc, or park in ROADMAP —
   465	      operator decides; this phase only recommends.
   466	
   467	#### Phase 3 — Findings (synthesis)
   468	<!-- FILL: ranked table + top-3 + skip ledger. -->
   469	_(not yet run)_
   470	
   471	### Phase 3 — QA checklist
   472	- [ ] **Every Phase 1–2 call appears** in the ranked table or the SKIP ledger — nothing dropped.
   473	- [ ] **ROI ranking is defensible** (effort + payoff from the per-pattern calls, not re-vibed).
   474	- [ ] **Decision surface, not catalog** — a reader can act on the Top-3 without re-reading Phases 1–2.
   475	- [ ] **Doc hygiene.** `utils/pdda/pdda.sh run` clean; doc promoted per its final state (2-WORKING or
   476	      3-DONE) with Status table updated.
   477	
   478	---
   479	
   480	## Anti-goals
   481	
   482	- **Not a framework port.** We harvest patterns; we don't install gsd-core or restructure our stack
   483	  to match it.
   484	- **Not adopting the excluded families.** Testing-gates and installer/versioning are out of scope;
   485	  they surface only as GH-102 pointers.
   486	- **Not an exhaustive teardown.** ROI-gated harvest, not a research report — skip low-payoff dives.
   487	- **Not verbatim copying without attribution.** MIT reuse of ideas is free; copied files keep the
   488	  notice.
   489	- **Not conflating targets.** XYZ (shell/relay, vendored) and Rebalance (Python/`.claude`, native)
   490	  get distinct recommendations even for the same pattern.
   491	
   492	---
   493	
   494	## Provenance & verification
   495	
   496	- **Source under review:** gsd-core (open-gsd/gsd-core, MIT, npm `@opengsd/gsd-core`) — external
   497	  repo, operator-local checkout (path not repo-portable, omitted per PDDA's hardcoded-path rule; see
   498	  this doc's frontmatter `source:` field). Surface counted 2026-07-03: 70 skills, 34 agents,
   499	  70 commands, 22 hooks, 39 capabilities, 151 src files.
   500	- **Review targets:** XYZ vendored [.xyz/](../../.xyz); Rebalance native (`src/rebalance/`,
   501	  `.claude/`, PDDA).
   502	- **Scope decision (operator, 2026-07-03):** two families (phase-loop/context-engineering +
   503	  skill/command/hook/agent architecture); lens = adopt-recommendation + gap-analysis; one PDDA doc
   504	  in 1-INBOX that morphs into the review.
   505	- **Verification (per ROUTER §7):** `utils/pdda/pdda.sh run` clean before each `git mv` / promotion.
   506	  This is a read/decide review — no `pytest`/`doctor` gate applies unless an adoption later lands code
   507	  (that lands under its own issue/doc).

exec
/bin/zsh -lc "nl -ba PROJECT/2-WORKING/GSD-CORE-PATTERN-REVIEW.md | sed -n '520,760p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
 succeeded in 0ms:
codex
I’ve got the exact Phase 2 candidates and the Phase 0 baseline. Now I’m only reading the counterpart surfaces that matter for the five calls: Rebalance’s local `.claude` and hooks, plus the canonical XYZ and gsd-core files named in the question.
exec
/bin/zsh -lc 'find utils/pdda -maxdepth 1 -type f | sort' in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
exec
/bin/zsh -lc "find .claude -maxdepth 3 \\( -type f -o -type l \\) | sort" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
 succeeded in 0ms:
utils/pdda/PDDA-INSTALL.md
utils/pdda/pdda-catchup.sh
utils/pdda/pdda-doc-ready.sh
utils/pdda/pdda-edit-doc-hook.sh
utils/pdda/pdda-gh-refresh.sh
utils/pdda/pdda-lib.sh
utils/pdda/pdda-stop-doc-health.sh
utils/pdda/pdda.sh

 succeeded in 0ms:
.claude/commands/ask_self.md
.claude/commands/reingest.md
.claude/settings.json
.claude/skills/git-pulse-exec-recap/SKILL.md
.claude/skills/git-pulse-team-recap/SKILL.md
.claude/skills/welcome/SKILL.md
.claude/skills/welcome/demo-transcript.md

exec
/bin/zsh -lc "find '/Users/noelsaw/Documents/GH Repos/gsd-core' -maxdepth 3 \\( -path '*/docs/*' -o -path '*/agents/*' -o -path '*/hooks/*' -o -path '*/capabilities/*' -o -path '*/commands/*' -o -path '*/skills/*' \\) -type f | sort | sed -n '1,260p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
 succeeded in 0ms:
/Users/noelsaw/Documents/GH Repos/gsd-core/.git/hooks/applypatch-msg.sample
/Users/noelsaw/Documents/GH Repos/gsd-core/.git/hooks/commit-msg.sample
/Users/noelsaw/Documents/GH Repos/gsd-core/.git/hooks/fsmonitor-watchman.sample
/Users/noelsaw/Documents/GH Repos/gsd-core/.git/hooks/post-update.sample
/Users/noelsaw/Documents/GH Repos/gsd-core/.git/hooks/pre-applypatch.sample
/Users/noelsaw/Documents/GH Repos/gsd-core/.git/hooks/pre-commit.sample
/Users/noelsaw/Documents/GH Repos/gsd-core/.git/hooks/pre-merge-commit.sample
/Users/noelsaw/Documents/GH Repos/gsd-core/.git/hooks/pre-push.sample
/Users/noelsaw/Documents/GH Repos/gsd-core/.git/hooks/pre-rebase.sample
/Users/noelsaw/Documents/GH Repos/gsd-core/.git/hooks/pre-receive.sample
/Users/noelsaw/Documents/GH Repos/gsd-core/.git/hooks/prepare-commit-msg.sample
/Users/noelsaw/Documents/GH Repos/gsd-core/.git/hooks/push-to-checkout.sample
/Users/noelsaw/Documents/GH Repos/gsd-core/.git/hooks/sendemail-validate.sample
/Users/noelsaw/Documents/GH Repos/gsd-core/.git/hooks/update.sample
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-advisor-researcher.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-ai-researcher.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-assumptions-analyzer.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-code-fixer.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-code-reviewer.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-codebase-mapper.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-debug-session-manager.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-debugger.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-doc-classifier.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-doc-synthesizer.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-doc-verifier.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-doc-writer.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-domain-researcher.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-eval-auditor.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-eval-planner.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-executor.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-framework-selector.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-integration-checker.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-intel-updater.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-mempalace-curator.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-nyquist-auditor.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-pattern-mapper.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-phase-researcher.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-plan-checker.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-planner.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-project-researcher.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-research-synthesizer.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-roadmapper.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-security-auditor.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-ui-auditor.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-ui-checker.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-ui-researcher.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-user-profiler.md
/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-verifier.md
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/ai-integration/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/antigravity/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/assumption-delta/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/audit/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/augment/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/claude/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/cline/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/code-review/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/codebuddy/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/codex/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/copilot/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/cursor/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/drift/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/gap-analysis/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/gemini/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/graphify/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/hermes/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/intel/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/kilo/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/kimi/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/mempalace/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/nyquist/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/opencode/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/pattern-mapper/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/profile-pipeline/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/qwen/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/research/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/schema-gate/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/security/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/tdd/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/trae/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/ui/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/windsurf/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/add-tests.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/ai-integration-phase.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/audit-fix.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/audit-milestone.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/audit-uat.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/autonomous.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/capture.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/cleanup.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/code-review.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/complete-milestone.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/config.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/debug.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/discuss-phase.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/docs-update.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/eval-review.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/execute-phase.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/explore.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/extract-learnings.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/fast.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/forensics.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/graphify.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/health.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/help.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/import.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/inbox.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/ingest-docs.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/manager.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/map-codebase.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/mempalace-capture.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/mempalace-recall.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/milestone-summary.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/mvp-phase.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/new-milestone.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/new-project.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/next.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/ns-context.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/ns-ideate.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/ns-manage.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/ns-project.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/ns-review.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/ns-workflow.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/pause-work.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/phase.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/plan-phase.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/plan-review-convergence.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/pr-branch.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/profile-user.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/progress.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/quick.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/resume-work.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/review-backlog.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/review.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/secure-phase.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/settings.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/ship.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/sketch.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/spec-phase.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/spike.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/stats.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/surface.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/thread.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/ui-phase.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/ui-review.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/ultraplan-phase.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/undo.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/update.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/validate-phase.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/verify-work.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/workspace.md
/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/workstreams.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/AGENTS.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/ARCHITECTURE.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/BETA.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/CANARY.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/CLI-TOOLS.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/COMMANDS.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/CONFIGURATION.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/FEATURES.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/INVENTORY-MANIFEST.json
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/INVENTORY.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/README.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/RELEASE-NOTES-LEGACY.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/TESTING-SUITES.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/USER-GUIDE.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/0001-dispatch-policy-module.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/0002-command-contract-validation-module.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/0003-model-catalog-module.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/0004-worktree-workstream-seam-module.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/0005-sdk-architecture-seam-map.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/0006-planning-path-projection-module.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/0007-sdk-package-seam-module.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/0008-installer-migration-module.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/0009-shell-command-projection-module.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/0010-file-operation-engine-module.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/0010-skill-surface-budget-module.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/0011-review-default-reviewers-prd.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/0011-review-default-reviewers.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/0011-skill-surface-budget-module.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/0012-command-routing-hub.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/0174-retire-gsd-sdk-package-boundary.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/0656-research-module-seam.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/1016-runtime-capability-descriptor.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/1143-claude-orchestration-capability.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/1213-capability-state-writer.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/1235-descriptor-driven-agent-conversion-migration.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/1239-gsd-embeddable-orchestration-engine.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/1244-capability-ecosystem.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/1372-markdown-sectionizer-seam.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/1411-resolution-provenance.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/15-autonomous-cross-ai-convergence.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/1508-runtime-artifact-conversion-module.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/1517-reviewer-instances-config-surface.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/1577-untrusted-input-boundary-and-injection-blocking.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/1593-skill-mapping-converter-methodology.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/1606-prohibition-enforcement-verify-seam.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/1610-workflow-agent-size-budget-ratchet.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/1671-dynamic-context-management-platform.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/1703-portability-enforcement-architecture.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/1769-state-md-transition-module.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/1787-gsd-next-smart-entry.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/1817-state-md-rebuild-derivability-contract.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/1866-agent-skills-dual-injection-contract.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/218-release-version-validation.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/22-plan-drift-guard.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/227-input-validation-shape-not-just-type.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/230-introduce-next-integration-branch.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/3524-cjs-sdk-hard-seam.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/3660-runtime-artifact-layout-module.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/415-prevent-stale-base-token-reintroduction.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/443-opus48-unified-effort-and-fast-mode-routing.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/452-eslint-lint-harness.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/456-test-rigor-architecture.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/457-generated-cjs-single-source.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/550-spec-phase-probe-contract.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/58-runtime-install-policy-module.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/660-release-from-next-head.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/766-claude-code-plugin-manifest-module.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/857-capability-system.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/894-capability-declaration-format.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/959-capability-command-contribution.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/adr/README.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/agents/domain.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/agents/issue-tracker.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/agents/triage-labels.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/branch-protection.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/branching.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/cleanup-get-shit-done-cc.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/context-monitor.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/contributing/adding-a-portability-rule.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/contributing/bootstrap.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/contributing/cross-platform-portability-rules.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/contributor-standards.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/design/verifier-reach.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/discussions/grok-build-support-2026-05.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/explanation/capability-overlay-model.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/explanation/capability-trust-model.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/explanation/context-engineering.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/explanation/interface-versioning-policy.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/explanation/multi-agent-orchestration.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/explanation/security-model.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/explanation/the-phase-loop.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/how-to/add-or-update-a-host-integration.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/how-to/attach-a-plugin-skill-to-a-gsd-agent.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/how-to/author-a-host-plugin.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/how-to/configure-model-profiles.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/how-to/connect-gsd-mcp-server.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/how-to/debug-a-failed-execution.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/how-to/design-a-ui-phase.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/how-to/develop-a-capability.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/how-to/discuss-a-phase.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/how-to/drive-gsd-from-a-tracker-issue.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/how-to/enable-cross-session-memory-with-mempalace.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/how-to/execute-a-phase.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/how-to/fix-worktree-base-mismatch.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/how-to/handle-quick-and-fast-tasks.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/how-to/import-a-capability-from-a-url.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/how-to/install-minimal-and-add-skills.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/how-to/install-on-your-runtime.md
/Users/noelsaw/Documents/GH Repos/gsd-core/docs/how-to/isolate-work-with-workspaces.md

exec
/bin/zsh -lc "find '/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm' -maxdepth 3 \\( -path '*/skills/*' -o -path '*/relay-automation/*' -o -path '*/src/*' \\) -type f | sort | sed -n '1,220p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
 succeeded in 0ms:
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/CONSUMING.md
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/CROSSMODEL-OPTIONA-PLAN.md
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/DUELING-CLAUDES.md
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/MARATHON.example.yaml
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/README.md
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/agy-turn.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/aider-turn.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/champion.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/claude-turn.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/codex-turn.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/consult.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/gemini-turn.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/heldout-check.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/hooks/relay-xyz-guard.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/hooks/security-scan-baseline.txt
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/hooks/security-scan.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/hooks/xyz-vendor-reminder.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/improve-loop.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/loop-cost.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/loop-stop.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/marathon-agent.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/marathon-detail.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/marathon-drive.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/marathon-ls.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/marathon-tui.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/marathon.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/measure.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/new-relay.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/oracle-guard.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/poll.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/proposals-sink.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/relay-drive.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/relay-loop.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/relay-turn-lib.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/runner.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/watchdog.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/xyz-sync.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/xyz-vendor.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/skills/consult/SKILL.md
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/skills/relay-automation/SKILL.md
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/skills/relay-automation/make-pkg.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/skills/relay-automation/relay-pkg.tar.gz
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/skills/relay-to-issue/SKILL.md
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/skills/relay-to-issue/install.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/skills/relay-to-issue/relay-to-issue.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/skills/relay-xyz/SKILL.md
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/skills/relay-xyz/find-harness.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/skills/relay-xyz/install.sh
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/skills/swe/SKILL.md
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/skills/xyz/SKILL.md
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/src/analyze.js
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/src/claim.js
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/src/cost.js
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/src/events.js
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/src/identity.js
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/src/lock.js
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/src/marathon-yaml.js
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/src/next.js
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/src/paths.js
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/src/project.js
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/src/scope.js
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/src/take.js

codex
The remaining work is just evidence gathering for the five deltas: what Rebalance actually exposes today, what XYZ adds on top, and which gsd-core mechanics are materially different versus just more numerous.
exec
/bin/zsh -lc 'nl -ba .claude/settings.json' in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
 succeeded in 0ms:
     1	{
     2	  "permissions": {
     3	    "allow": [
     4	      "mcp__rebalance__onboarding_status",
     5	      "mcp__rebalance__ask",
     6	      "Read(//tmp/**)",
     7	      "Bash(.venv/bin/python -c ' *)",
     8	      "Bash(git commit -m ' *)",
     9	      "Bash(python -c ' *)",
    10	      "Bash(python -c \"import rich; print\\('rich ok:', rich.__version__\\)\")",
    11	      "Bash(python -c \"from rich.console import Console; from rich.layout import Layout; from rich.live import Live; print\\('rich ok'\\)\")",
    12	      "Bash(.venv/bin/rebalance refresh *)",
    13	      "Bash(.venv/bin/python scripts/pulse_server.py --port 8765)",
    14	      "Bash(echo \"pid=$!\")",
    15	      "Bash(curl -fsS http://127.0.0.1:8765/api/health -o /dev/null)",
    16	      "Bash(curl -fsS http://127.0.0.1:8765/api/health)",
    17	      "Bash(curl -fsS http://127.0.0.1:8765/)",
    18	      "Bash(curl -fsS -X POST http://127.0.0.1:8765/api/refresh)",
    19	      "Bash(curl -fsS -X POST http://127.0.0.1:8766/api/refresh)",
    20	      "Bash(.venv/bin/python scripts/pulse_server.py --host 0.0.0.0)",
    21	      "Bash(kill 32790)",
    22	      "Bash(wait 32790)",
    23	      "Bash(nohup ./scripts/pulse_server.sh)",
    24	      "Bash(disown)",
    25	      "Bash(curl -fsS http://127.0.0.1:8767/api/health -o /dev/null)",
    26	      "Bash(curl -fsS http://127.0.0.1:8767/api/health)",
    27	      "Bash(lsof -nP -iTCP:8767 -sTCP:LISTEN)",
    28	      "Bash(lsof -nP -iTCP:8767 -sTCP:LISTEN -t)",
    29	      "Bash(xargs -r kill)",
    30	      "Bash(echo \"new pid=$!\")",
    31	      "Bash(curl -s -o /tmp/resp.json -w 'HTTP %{http_code}\\\\n' -X POST http://127.0.0.1:8767/api/goals/complete -H 'content-type: application/json' -d '{\"title\":\"__definitely_not_a_real_goal__\"}')",
    32	      "Bash(curl -s -o /tmp/resp.json -w 'HTTP %{http_code}\\\\n' -X POST http://127.0.0.1:8767/api/goals/complete -H 'content-type: application/json' -d '{\"title\":\"\"}')",
    33	      "mcp__rebalance__sleuth_sync_reminders",
    34	      "Bash(.venv/bin/python -m pytest tests/test_sleuth_reminders.py tests/test_pulse_sleuth_scope.py -q)",
    35	      "Bash(.venv/bin/python -m unittest tests.test_sleuth_reminders tests.test_pulse_sleuth_scope -v)",
    36	      "Bash(awk 'NR>=755 && NR<=770' PROJECT/cleanup.sh)",
    37	      "Skill(update-config)",
    38	      "Skill(update-config:*)",
    39	      "Bash(.venv/bin/python -m pytest tests/test_calendar_create_event_cli.py tests/test_git_pulse_health_check.py tests/test_dashboard_terminal_theme.py -q)",
    40	      "Bash(python3 -m py_compile src/rebalance/cli.py tests/test_git_pulse_health_check.py tests/test_calendar_create_event_cli.py)",
    41	      "Bash(.venv/bin/python -m pytest:*)",
    42	      "Bash(.venv/bin/python -m py_compile:*)",
    43	      "Bash(python3 -m py_compile:*)",
    44	      "Bash(.venv/bin/python -c:*)",
    45	      "Bash(grep:*)",
    46	      "Bash(rg:*)",
    47	      "Bash(find:*)",
    48	      "Bash(wc:*)",
    49	      "Bash(ls:*)",
    50	      "Bash(git diff:*)",
    51	      "Bash(git status:*)",
    52	      "Bash(git log:*)",
    53	      "Bash(git show:*)",
    54	      "Bash(git add:*)",
    55	      "Edit(src/**)",
    56	      "Edit(tests/**)",
    57	      "Edit(PROJECT/**)",
    58	      "Write(src/**)",
    59	      "Write(tests/**)",
    60	      "Write(PROJECT/**)",
    61	      "Bash(REBALANCE_NO_KEYRING=1 .venv/bin/python -c ' *)",
    62	      "Edit(/.claude/skills/welcome/**)",
    63	      "Bash(sed -n 34,38p PROJECT.md)",
    64	      "Bash(sed -n 290,294p PROJECT.md)",
    65	      "Bash(sed -n 654,658p PROJECT.md)",
    66	      "Bash(.venv/bin/python temp/phase0_repair_and_shared.py)",
    67	      "Bash(.venv/bin/python temp/ab_judge_gemini.py)",
    68	      "Bash(REBALANCE_DB='/Users/noelsaw/Library/Application Support/rebalance-os/rebalance.db' .venv/bin/python -c ' *)",
    69	      "Bash(python -m pytest tests/test_sync_snapshot.py tests/test_calendar_reader_scope.py tests/test_calendar_composite_pk_migration.py -q)",
    70	      "Bash(python -m pytest tests/test_calendar_composite_pk_migration.py tests/test_calendar_reader_scope.py tests/test_sync_snapshot.py -q)",
    71	      "Bash(python -m pytest tests/test_calendar_reader_scope.py -q)",
    72	      "Bash(python -m pytest tests/test_calendar_composite_pk_migration.py -q)",
    73	      "Bash(echo \"EXIT: $?\")",
    74	      "mcp__rebalance__refresh_index",
    75	      "Bash(sqlite3 \"/Users/noelsaw/Library/Application Support/rebalance-os/rebalance.db\" \"SELECT person, COUNT\\(*\\) as events FROM calendar_events WHERE calendar_id != 'primary' GROUP BY person ORDER BY person;\")",
    76	      "Bash(python3 -c ' *)",
    77	      "Bash(python3 -c \"from rebalance.ingest.calendar_config import CalendarConfig, TeamCalendarEntry; print\\('import OK'\\); c=CalendarConfig.load\\(\\); print\\('team_calendars:', c.team_calendars\\)\")",
    78	      "Bash(find . -name note_builder.py)",
    79	      "Bash(find . -name project_inference.py)",
    80	      "Bash(sed -n '80,95p' src/rebalance/mcp/tools/calendar.py)",
    81	      "Bash(sed -n '320,340p' src/rebalance/ingest/daily_report.py)",
    82	      "Bash(sed -n '215,245p' /Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/project_inference.py)",
    83	      "Bash(sed -n '175,200p' /Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/note_builder.py)",
    84	      "Bash(/Users/noelsaw/Documents/rebalance-OS/.venv/bin/python -)",
    85	      "Bash(echo \"---EXIT $?---\")",
    86	      "Bash(sed -n '216,230p' src/rebalance/ingest/daily_report.py)",
    87	      "Bash(sed -n '183,196p' src/rebalance/ingest/note_builder.py)",
    88	      "Bash(sed -n '228,240p' src/rebalance/ingest/project_inference.py)",
    89	      "Bash(sed -n '104,115p' src/rebalance/ingest/calendar_config.py)",
    90	      "Bash(utils/pdda-run.sh)",
    91	      "Bash(rtk find *)",
    92	      "Bash(git check-ignore *)",
    93	      "Bash(git rev-parse *)",
    94	      "Bash(utils/pdda-check-roadmap.sh)",
    95	      "Bash(echo \"rc=$?\")",
    96	      "Bash(time agy -p 'Reply with exactly this line and nothing else: {\"severity\":\"info\",\"line\":0,\"message\":\"agy ok\"}')",
    97	      "Bash(bash -c '. utils/pdda-lib.sh; pdda_list_working_docs')",
    98	      "Bash(sqlite3 rebalance.db \"SELECT device_id, local_path, my_last_commit_ts FROM focus5_repo_signals;\")",
    99	      "Bash(sqlite3 rebalance.db \"SELECT COUNT\\(*\\) AS discovered FROM focus5_repo_signals;\")",
   100	      "Bash(python3 -c 'from pathlib import Path; p=Path\\(\"/Users/noelsaw/Documents/GitHub-Repos\"\\); print\\(\"exists:\",p.exists\\(\\),\"is_dir:\",p.is_dir\\(\\),\"is_symlink:\",p.is_symlink\\(\\)\\)')",
   101	      "Bash(awk '/^l/ {print}')",
   102	      "Bash(python3 -c 'from pathlib import Path; p=Path\\(\"/Users/noelsaw/Documents/GH\"\\); print\\(\"exists:\",p.exists\\(\\),\"is_dir:\",p.is_dir\\(\\),\"is_symlink:\",p.is_symlink\\(\\)\\)')",
   103	      "Bash(rtk du *)",
   104	      "Bash(rtk ls *)",
   105	      "Bash(sed -n '1,80p' relay-system/2026-06-24/gh81-rank-vector.md)",
   106	      "Bash(awk '/NEXT TURN APPENDS BELOW/{f=1;next} f' relay-system/2026-06-24/gh81-code-qa.md)",
   107	      "mcp__rebalance__diagnose_repo",
   108	      "mcp__rebalance__list_watched_repos",
   109	      "Bash(utils/pdda.sh status-table *)",
   110	      "Bash(utils/pdda.sh roadmap-coverage *)",
   111	      "Bash(utils/pdda.sh frontmatter *)"
   112	    ]
   113	  },
   114	  "env": {
   115	    "PDDA_STALE_DAYS": "14"
   116	  }
   117	}

exec
/bin/zsh -lc "nl -ba .claude/commands/ask_self.md && printf '\\n' && nl -ba .claude/commands/reingest.md" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
 succeeded in 0ms:
     1	---
     2	description: Query the ask-self RAG index for this repo
     3	argument-hint: "<your question>"
     4	---
     5	
     6	Answer a question by querying this repository's ask-self RAG index.
     7	
     8	The user's question is:
     9	
    10	$ARGUMENTS
    11	
    12	If the question above is empty, ask the user what they would like to know and stop.
    13	
    14	Run the detection-and-query script below in a single Bash call. Before running it,
    15	replace `PUT_QUESTION_HERE` on the first line with the user's question as a single
    16	shell-quoted string — quote it correctly for the shell (questions routinely contain
    17	apostrophes, `$`, and quotes; escape as needed). Do not change anything else.
    18	
    19	The script resolves the query entry point — stopping at the first matching layout —
    20	and prints the answer:
    21	
    22	```bash
    23	Q='PUT_QUESTION_HERE'
    24	
    25	set -e
    26	
    27	if [ -f scripts/ask-self-query.sh ]; then
    28	  # 1. Integrated target repo: use the wrapper (invoked via bash so a
    29	  #    missing executable bit on the wrapper does not break the command).
    30	  bash scripts/ask-self-query.sh "$Q"
    31	elif [ -n "$ASK_SELF_PATH" ]; then
    32	  # 2. External install located via ASK_SELF_PATH.
    33	  if [ -f "$ASK_SELF_PATH/ask_self/ask_self_harness.json" ]; then
    34	    HARNESS="$ASK_SELF_PATH/ask_self/ask_self_harness.json"
    35	  else
    36	    HARNESS="$ASK_SELF_PATH/ask_self_harness.json"
    37	  fi
    38	  if [ -n "$ASK_SELF_PYTHON" ]; then
    39	    PY="$ASK_SELF_PYTHON"
    40	  elif [ -x "$ASK_SELF_PATH/.venv/bin/python" ]; then
    41	    PY="$ASK_SELF_PATH/.venv/bin/python"
    42	  else
    43	    PY="python3"
    44	  fi
    45	  "$PY" "$ASK_SELF_PATH/ask_self_query.py" "$Q" --harness-config "$HARNESS"
    46	elif [ -f ask_self/ask_self_query.py ]; then
    47	  # 3. Portable-mode or vendored copy inside the target repo.
    48	  if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi
    49	  "$PY" ask_self/ask_self_query.py "$Q" --harness-config ask_self/ask_self_harness.json
    50	elif [ -f ask_self_query.py ]; then
    51	  # 4. The ask-self repo itself.
    52	  if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi
    53	  "$PY" ask_self_query.py "$Q" --harness-config ask_self_harness.json
    54	else
    55	  echo "ask-self does not appear to be set up in this repo. See ASK_SELF_INTEGRATION.md for setup." >&2
    56	  exit 1
    57	fi
    58	```
    59	
    60	The query prints a human-readable, citation-grounded answer to stdout. Relay that
    61	answer to the user; do not paraphrase away the cited file references.
    62	
    63	**Default scope (v0.5+):** queries filter to the current revision of each doc.
    64	If the user's question is historical or comparative ("what did the architecture
    65	plan say last month", "when did we change the auth model"), append `--doc-history`
    66	to widen the candidate pool to additive doc revisions, or `--as-of YYYY-MM-DD`
    67	to time-travel. Inspect what's available with `ask-self history <path>` first if
    68	you're unsure whether the repo has accumulated history for the relevant doc.
    69	
    70	If it fails with a `GOOGLE_API_KEY` error: synthesis (and Gemini retrieval) needs a
    71	Gemini API key. Tell the user to make one resolvable (env var, key file, or Secret
    72	Manager), or — if this repo's harness uses a local embedding provider — that the
    73	query can be re-run with `--retrieval-only` for a local, synthesis-free result.
    74	
    75	Do not modify any source files. Only run the query command.

     1	---
     2	description: Refresh the ask-self RAG index for this repo
     3	argument-hint: "[--mode all|docs|code] [--no-prs] [...ingest flags]"
     4	---
     5	
     6	Run an ask-self (re)ingest of the current codebase to refresh the RAG index.
     7	
     8	As of v0.5, the index is **revision-aware**: doc files ingest additively
     9	(history is preserved across runs) and code files ingest in overwrite mode
    10	(working tree wins). Re-ingesting an unchanged repo is a near-instant no-op —
    11	the planner dedupes against the existing DB before calling the embedding API,
    12	so unchanged chunks are never re-embedded. No flags are required to opt in;
    13	the behavior is the default.
    14	
    15	**First run after upgrading to v0.5:** the ingester will detect a pre-v2
    16	index, print `[ask-self] Detected pre-v2 index at <path>; rebuilding...` to
    17	stderr, and rebuild from scratch (one-time cost, matches today's behaviour).
    18	Subsequent ingests run on the new schema and dedupe automatically.
    19	
    20	**After a successful ingest, you can:**
    21	- Inspect doc revision history: `ask-self history <path>` (e.g. `ask-self history README.md`).
    22	- Query historical doc content: `ask-self ask "..." --doc-history` or `--as-of YYYY-MM-DD`.
    23	- Prune accumulated history: `ask-self prune-history --older-than 90d` or `--keep-last K --per-path` (add `--dry-run` to preview).
    24	
    25	Run the following detection-and-ingest script in a single Bash call. It resolves
    26	the ingest path (stopping at the first matching layout) and runs the ingest with
    27	`--json` so the result is machine-parseable:
    28	
    29	```bash
    30	set -e
    31	
    32	# Default to --mode all unless the caller already passed --mode.
    33	# An array, not a string: zsh does not word-split unquoted variables, so a
    34	# "--mode all" string would reach the CLI as a single bogus argument.
    35	MODE_ARGS=(--mode all)
    36	case " $ARGUMENTS " in *" --mode "*) MODE_ARGS=() ;; esac
    37	
    38	if [ -f scripts/ask-self-ingest.sh ]; then
    39	  # 1. Integrated target repo: use the wrapper (invoked via bash so a
    40	  #    missing executable bit on the wrapper does not break the command).
    41	  bash scripts/ask-self-ingest.sh "${MODE_ARGS[@]}" --json $ARGUMENTS
    42	elif [ -n "$ASK_SELF_PATH" ]; then
    43	  # 2. External install located via ASK_SELF_PATH.
    44	  if [ -f "$ASK_SELF_PATH/ask_self/ask_self_harness.json" ]; then
    45	    HARNESS="$ASK_SELF_PATH/ask_self/ask_self_harness.json"
    46	  else
    47	    HARNESS="$ASK_SELF_PATH/ask_self_harness.json"
    48	  fi
    49	  if [ -n "$ASK_SELF_PYTHON" ]; then
    50	    PY="$ASK_SELF_PYTHON"
    51	  elif [ -x "$ASK_SELF_PATH/.venv/bin/python" ]; then
    52	    PY="$ASK_SELF_PATH/.venv/bin/python"
    53	  else
    54	    PY="python3"
    55	  fi
    56	  "$PY" "$ASK_SELF_PATH/ask_self_ingest.py" --harness-config "$HARNESS" "${MODE_ARGS[@]}" --json $ARGUMENTS
    57	elif [ -f ask_self/ask_self_ingest.py ]; then
    58	  # 3. Portable-mode or vendored copy inside the target repo.
    59	  if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi
    60	  "$PY" ask_self/ask_self_ingest.py --harness-config ask_self/ask_self_harness.json "${MODE_ARGS[@]}" --json $ARGUMENTS
    61	elif [ -f ask_self_ingest.py ]; then
    62	  # 4. The ask-self repo itself.
    63	  if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi
    64	  "$PY" ask_self_ingest.py --harness-config ask_self_harness.json "${MODE_ARGS[@]}" --json $ARGUMENTS
    65	else
    66	  echo "ask-self does not appear to be set up in this repo. See ASK_SELF_INTEGRATION.md for setup." >&2
    67	  exit 1
    68	fi
    69	```
    70	
    71	The ingest prints a JSON object to stdout. After the script exits, parse it and summarise:
    72	
    73	- On success (`"ok": true`): report `total_chunks`, `db_path`, and `elapsed_seconds`.
    74	  Also report the revision-aware counters from the `revisions` block when present:
    75	  - `new` — new file revisions written (additive doc edits or new files)
    76	  - `refreshed` — unchanged files whose `last_seen_at` was bumped
    77	  - `chunks_embedded` vs `chunks_reused` — embedding cost vs cache reuse
    78	  - `deleted_paths_swept` — overwrite paths removed from disk and pruned
    79	  A second consecutive run on an unchanged repo should show `new: 0`, `chunks_embedded: 0`, and a large `refreshed` count. If those numbers don't match expectation, flag it (it usually means a noisy auto-generated doc is churning).
    80	- On failure (`"ok": false`, or a non-zero exit): report the `error` field plus any warnings.
    81	
    82	Do not modify any source files. Only run the ingest command.

exec
/bin/zsh -lc "nl -ba .claude/skills/welcome/SKILL.md && printf '\\n' && nl -ba .claude/skills/git-pulse-exec-recap/SKILL.md && printf '\\n' && nl -ba .claude/skills/git-pulse-team-recap/SKILL.md" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
 succeeded in 0ms:
     1	---
     2	name: welcome
     3	description: Guided rebalance-OS onboarding — the welcome agent. Walks a new (or returning) operator from clone to first pulse by driving the lifecycle status contract: renders where-am-I, executes each setup step itself (GitHub PAT, optional Calendar/Gmail OAuth, project discovery and promotion, scheduler install), and verifies every step before moving on. Trigger when the user invokes /welcome, asks to "set up rebalance", "finish onboarding", "where am I in setup", wants to add a previously skipped step (Calendar/Gmail), or after a fresh clone. Resumable at any time — state lives in the MCP contract, not this conversation.
     4	---
     5	
     6	# /welcome — rebalance-OS guided onboarding
     7	
     8	You are the welcome agent. The setup state machine is owned by the
     9	`onboarding_status` MCP tool (backed by `src/rebalance/ingest/lifecycle.py`,
    10	contract v2). You are a *view and executor* over that contract — never
    11	re-derive, cache, or invent stage state. SCHEDULER.md owns scheduler policy.
    12	
    13	## Non-negotiable rules
    14	
    15	1. **One tool call answers "where am I".** Start EVERY turn of this flow by
    16	   calling `onboarding_status` (vault_path from config, or ask once). Render
    17	   the stage list before doing anything else.
    18	2. **Secrets never enter the transcript.** Never echo a PAT or OAuth token,
    19	   never paste one into chat, never write one to a file. Tokens go from the
    20	   user directly into `setup_github_token` (they paste it as the tool
    21	   argument) or are produced by the OAuth scripts' browser flows. If the user
    22	   pastes a secret into chat, tell them to revoke and reissue it.
    23	3. **You execute; the human decides.** Run every command yourself via the
    24	   stage's `executor` hint. The human only: clicks browser consent screens,
    25	   answers promote/skip questions, and supplies values only they know
    26	   (vault path, PAT).
    27	4. **Verify, don't assume.** After executing a stage, re-call
    28	   `onboarding_status` and confirm the stage flipped to `done`. A stage that
    29	   didn't flip is a failure to diagnose (surface the stage's `detail` and
    30	   `remediation`), not a step to skip.
    31	5. **Confirmation is the only registry write.** Discovery (`run_preflight`)
    32	   is read-only and always safe to re-run. Only `confirm_projects` persists,
    33	   and only with the list the user approved. The `project_lifecycle` table in
    34	   the `onboarding_status` payload is your reference for what may write.
    35	
    36	## Rendering "where am I"
    37	
    38	Render the `stages` array every turn, in order, as a checklist:
    39	
    40	- `done` → checked; `now` → arrow + "you are here"; `next` → unchecked;
    41	  `blocked` → flagged with what it's waiting on (`requires`); `skipped` →
    42	  marked "(skipped — say the word to add it later)".
    43	- Decorate optional stages from the `optional` flag (titles don't encode it).
    44	- Show `remediation` only for the `now`/`blocked` stages.
    45	
    46	## Executing a stage
    47	
    48	Dispatch on the stage's `executor` field:
    49	
    50	- `mcp:<tool>` — call that MCP tool. For `setup_github_token`, first send the
    51	  user to https://github.com/settings/tokens — classic token with the `repo`
    52	  scope, or a fine-grained token with Repository access changed from the
    53	  "Public repositories" default to All/selected repos (read-only Contents +
    54	  Metadata). Have them paste the PAT as the tool argument and report the
    55	  validation result (login + scopes) back. If the result carries a
    56	  `visibility_warning`, surface it verbatim — a public-only token silently
    57	  hides their private work from discovery.
    58	- `cli:<command>` — run it with Bash from the repo root, substituting
    59	  `<path>`-style placeholders with values the user gives you.
    60	- `script:<path>` — run `.venv/bin/python <path>` in the background if it
    61	  blocks on a browser consent flow; tell the user a browser window is coming,
    62	  wait for them to confirm consent, then verify.
    63	
    64	Stage-specific notes:
    65	
    66	- **Optional stages (calendar_auth, gmail_auth):** offer once — "set up now,
    67	  or skip for later?". On skip, call `skip_onboarding_stage(stage_id)` so the
    68	  contract remembers; on a later /welcome run, mention skipped stages exist
    69	  but don't nag.
    70	- **Discovery & promote (registry_exists):** call `run_preflight`, present
    71	  candidates grouped by segment with their `provenance` (remote GitHub
    72	  activity vs. vault note), and ask which to promote to monitored — this is
    73	  the one genuinely interactive review. Pass the user-approved list (with any
    74	  edits) to `confirm_projects`. Re-running discovery to re-review is always
    75	  safe.
    76	- **After db_synced is done (graduation):** offer the scheduled fleet —
    77	  `bash scripts/install_scheduler.sh` (daily sync) plus the hourly jobs per
    78	  SCHEDULER.md, then run `bash scripts/pulse_web_sync.sh` and open
    79	  `web/pulse.html` so the user sees their first pulse. Then hand over: point
    80	  at SCHEDULER.md's runbook and the dashboard (`rebalance`).
    81	
    82	## Resume & re-entry
    83	
    84	This flow is interruptible by design. If the conversation was cleared, the
    85	laptop slept for a week, or setup happened partially by hand — none of that
    86	matters: call `onboarding_status` and continue from `now`. If
    87	`setup_complete` is true, say so, summarize what's live (projects count,
    88	optional stages done/skipped), and offer the skipped stages or graduation
    89	extras instead of re-running anything.

     1	---
     2	name: git-pulse-exec-recap
     3	description: Fill in the TLDR, FOCUS, and OBSERVATIONS placeholders of a Git Pulse Executive Recap so the narrative reads like something an exec or investor would actually want — not another engineering status report. Use this skill whenever the user is editing a Git Pulse recap, asks for an "exec summary" or "executive recap" of git activity, points at a file with `<!-- TLDR: -->`, `<!-- FOCUS: -->`, or `<!-- OBSERVATIONS: -->` placeholders, or complains that previous passes "stayed too technical," "read like changelog," or "kept listing commits." Also trigger when agents (including Claude Code / VS Code agents) have already produced a draft that reproduces commit subjects, SHAs, filenames, or per-commit bullets instead of a narrative — this skill is the corrective pass.
     4	---
     5	
     6	# Git Pulse Executive Recap
     7	
     8	The Git Pulse recap is a Markdown file with a rich **Appendix** (tables of commits, machines, repos, daily activity) and three prose holes to fill:
     9	
    10	- `<!-- TLDR: ... -->` — 1–2 sentences at the top
    11	- `<!-- FOCUS: ... -->` — 2–3 sentences per repo
    12	- `<!-- OBSERVATIONS: ... -->` — 3–5 bullets of patterns and anomalies
    13	
    14	The Appendix is the raw material. The prose is the product. **Do not touch the Appendix.** Only replace the three placeholder types, comment delimiters and all.
    15	
    16	## The core problem this skill exists to solve
    17	
    18	Agents keep writing these sections like commit logs with extra words. They reproduce commit subjects, paste SHAs, list filenames, and enumerate features shipped. The reader does not want that — the Appendix already has it. The reader wants the *meaning* of the week: where did effort concentrate, what shifted, what's worth a second look.
    19	
    20	Treat yourself as a chief of staff briefing a busy principal, not a tech lead writing sprint notes.
    21	
    22	## Rules, in order of importance
    23	
    24	1. **Never name a commit, SHA, file, branch, or function.** If you find yourself typing `` ` `` backticks, stop. Proper nouns are limited to **repo names** and **machine names** (and only when they carry signal).
    25	2. **Describe work in terms of outcomes and themes, not deliverables.** "Hardened the RAG query path and tightened the analyst UI" — not "added smoke-query health check, full-width search input, and Docker setup."
    26	3. **Compress ruthlessly.** TLDR is 1–2 sentences. Each FOCUS is 2–3 sentences, hard stop. OBSERVATIONS is 3–5 bullets, each one line.
    27	4. **Lead with the signal, not the recap.** Start with what matters (concentration, shifts, anomalies), not with a restatement of the window.
    28	5. **Synthesize across commits.** Eight `feat` commits in one repo is a theme, not eight bullets. Name the theme.
    29	6. **Prefer verbs of shape over verbs of motion.** "Consolidated," "shifted focus to," "hardened," "paused" — not "added," "updated," "created."
    30	7. **Numbers earn their place.** Keep a number only if it supports the point. "Two-thirds of the week's commits landed in one repo" is useful; "40 commits, 3 machines, 7 active days" is Appendix.
    31	
    32	## TLDR — 1 to 2 sentences
    33	
    34	Answer: *If the reader reads nothing else, what should they know?*
    35	
    36	Good TLDRs name **where the energy went**, **the dominant mode of work** (building vs. hardening vs. planning vs. drifting), and **any standout signal** (a quiet stretch, a cross-machine push, a repo going dark).
    37	
    38	**Weak (what agents keep writing):**
    39	> Over 11 active days, 82 commits were made across 4 repos from 3 machines, with the most active repo being rebalance-OS at 40 commits and the busiest day being April 7 with 20 commits.
    40	
    41	That's the Summary block rephrased. Useless.
    42	
    43	**Strong:**
    44	> A two-front fortnight: a heavy early-window push on the WordPress RAG pipeline gave way to sustained, multi-machine iteration on rebalance-OS, while the two smaller repos effectively went quiet.
    45	
    46	Notice: no numbers, no SHAs, a clear shape ("two-front … gave way to … went quiet").
    47	
    48	## FOCUS — 2 to 3 sentences per repo
    49	
    50	For each repo, answer: *What was this repo actually about this window, and is anything notable about how the work happened?*
    51	
    52	**Do:**
    53	- Name 1–2 themes the commits cluster into. "Deployment hardening and analyst-facing UI polish," not a list of features.
    54	- Flag cross-machine coordination *only if it's signal* — e.g., a spike branch opened on a second machine while main work continued on the primary.
    55	- Note tempo shifts (front-loaded, back-loaded, single-day burst, one-commit-then-silence).
    56	
    57	**Don't:**
    58	- List commit subjects, even paraphrased.
    59	- Mention branch names unless a branch itself is the story (e.g., an experimental spike on a separate machine).
    60	- Describe every commit type bucket. If `docs` is 6 of 40, it's probably not the story.
    61	
    62	**Weak:**
    63	> rebalance-OS saw 40 commits including 8 feat commits, 7 fix commits, and 6 docs commits. Work included adding an --output flag, canonicalizing git-pulse view output, and addressing DRY audit findings. Three machines contributed.
    64	
    65	**Strong:**
    66	> rebalance-OS was the center of gravity, with a front-loaded burst of classifier and aggregator work giving way to a late-window focus on git-pulse itself — output canonicalization, device-id normalization, and an experimental history-collector spike opened on a separate machine. The work pattern suggests tooling-on-tooling: the recap system maturing into something Noel uses on his own workflow.
    67	
    68	For a small repo (1–3 commits), the honest answer is usually "this repo was effectively idle" — say that, briefly. Don't pad.
    69	
    70	**Strong, for a 1-commit repo:**
    71	> Effectively dormant — a single CI/CD guardrail fix mid-window, no feature work.
    72	
    73	## OBSERVATIONS — 3 to 5 bullets
    74	
    75	Answer: *What should a reader notice that the Summary stats don't already say?*
    76	
    77	Mine the Appendix tables for signal: the Coverage, Machines, Cross-Machine Repos, Daily Activity, and Exceptions sections are where interesting gaps live. Good observations often sound mildly uncomfortable — they point at something slightly off.
    78	
    79	**Candidate signal types:**
    80	- **Concentration / gaps:** most work on one repo or machine; multi-day silences; a repo with one commit then nothing.
    81	- **Cross-machine patterns:** spike branches opened on a second machine while main work continues elsewhere (is this intentional? a context-switch cost?).
    82	- **Metadata hygiene:** devices listed in metadata with no commits, missing pulse files, detached-HEAD commits, non-default branches with meaningful work.
    83	- **Commit hygiene:** high ratio of uncategorized "other" commits (conventional-commits discipline slipping); docs-heavy stretches (possibly pre-release polish or possibly avoidance).
    84	- **Tempo:** a single 20-commit day followed by a quiet stretch; weekend vs. weekday pattern; a machine that only shows up for a few hours.
    85	
    86	**Weak:**
    87	- There were 82 commits across 4 repos.
    88	- rebalance-OS had the most activity.
    89	- Three machines were used.
    90	
    91	**Strong:**
    92	- Two devices appear in the coverage metadata with zero commits and no pulse file — either retired machines or a sync gap worth confirming.
    93	- A third of the cross-machine activity sits on a detached / spike branch, suggesting exploratory work that hasn't yet been triaged back to main.
    94	- The WordPress RAG repo went silent after April 12 despite heavy activity the prior week — natural pause, or blocked?
    95	- "Other" (unprefixed) commits outnumber any single conventional type in the WP repo, pointing at drift in commit-message discipline on that codebase specifically.
    96	
    97	Each bullet names a pattern *and* hints at the question a principal would want to ask about it. That's the difference between reporting and briefing.
    98	
    99	## Worked example: before and after
   100	
   101	**Before (what the VS Code agents produce):**
   102	
   103	> ## TLDR
   104	> In the 11-day window from April 7 to April 20, 2026, 82 commits were made across 4 repos from 3 machines, with rebalance-OS being the most active repo at 40 commits.
   105	>
   106	> ### rebalance-OS FOCUS
   107	> rebalance-OS had 40 commits across 3 machines. Key work included feat commits (8) such as saving combined git-pulse reports and canonicalizing git-pulse view output, fix commits (7) including using human-friendly device ids and normalizing device config, and 6 docs commits updating GOOGLE_CALENDAR.md.
   108	
   109	**After (what this skill should produce):**
   110	
   111	> ## TLDR
   112	> A two-front fortnight: a heavy early-window push on the WordPress RAG pipeline gave way to sustained, multi-machine iteration on rebalance-OS, while the two smaller repos effectively went quiet.
   113	>
   114	> ### rebalance-OS FOCUS
   115	> rebalance-OS was the center of gravity, opening with a burst of classifier and aggregator work and closing on tooling-on-tooling polish of the git-pulse system itself — device-id normalization, output canonicalization, and an experimental history-collector spike opened on a separate machine. The dev-calendar integration also got a sustained documentation pass mid-window, pointing at a feature moving from "working" to "shareable."
   116	
   117	## Final check before you hand back
   118	
   119	Before returning the filled-in recap, read your own prose once and ask:
   120	
   121	- Could this have been written without looking at the Appendix? → If yes, it's too generic. Go back and mine specifics.
   122	- Does any sentence name a file, SHA, branch, or commit subject? → Cut it.
   123	- Is any FOCUS section longer than 3 sentences? → Cut it.
   124	- Does the OBSERVATIONS list just restate the Summary stats? → Replace with actual patterns.
   125	- Would a non-engineer (Noel's partner, an investor, an ops lead) follow this? → If not, de-jargon.
   126	
   127	Keep the rest of the file byte-identical. Replace only the three placeholder types, including their `<!-- ... -->` delimiters.
     1	---
     2	name: git-pulse-team-recap
     3	description: Fill in the TLDR, FOCUS, and OBSERVATIONS placeholders of a Git Pulse Team Recap — an exec-style summary of a remote repo covering everyone's activity, not just the user's. Use this skill whenever editing a team recap file with `<!-- TLDR: -->`, `<!-- FOCUS: -->`, or `<!-- OBSERVATIONS: -->` placeholders, or when asked for a "team exec summary" / "team recap" / "what did the team ship this week" of GitHub activity. Also trigger when agents have already produced a draft that reproduces commit SHAs, PR numbers, or per-commit bullets — this skill is the corrective pass.
     4	---
     5	
     6	# Git Pulse Team Executive Recap
     7	
     8	This is the team-facing sibling of `EXEC-SUMMARY.md`. The recap lists everyone's commits and PRs on the target repo(s) in a window. You are rewriting the prose so it reads like a chief-of-staff briefing on team output — not a changelog, not a person-by-person CV.
     9	
    10	The file has a rich **Appendix** (Contributors Table, Repos Table, Daily Activity, Recent Activity, Exceptions). That's the raw material. The prose is the product. **Do not touch the Appendix.** Only replace the three placeholder types, comment delimiters and all.
    11	
    12	## Core rules (shared with the personal recap)
    13	
    14	1. **Never name a commit SHA, PR number, branch, file, or function.** If you're typing `` ` `` backticks or `#123`, stop. The only proper nouns allowed are **repo names** and **contributor handles** (`@login`) — and only when they carry signal.
    15	2. **Describe work in terms of outcomes and themes, not deliverables.** "Hardened the deployment pipeline and reviewed two API-surface changes" — not a list of commits and PR titles.
    16	3. **Compress ruthlessly.** TLDR is 1–2 sentences. Each FOCUS is 2–3 sentences, hard stop. OBSERVATIONS is 3–5 bullets, each one line.
    17	4. **Lead with the signal.** Start with what matters (concentration, shifts, anomalies), not a restatement of the window.
    18	5. **Synthesize across events.** Five `feat` commits and a PR on one repo is *a focus*, not six bullets. Name it.
    19	6. **Prefer verbs of shape over verbs of motion.** "Drove," "split between," "reviewed," "paused," "backed up" — not "added," "created," "opened."
    20	7. **Numbers earn their place.** Keep a number only if it supports the point. "Two thirds of the team's PR throughput came from one person" is useful; "15 commits across 2 repos" is Appendix.
    21	
    22	## TLDR — 1 to 2 sentences
    23	
    24	Answer: *If the reader reads nothing else, what should they know about this team this window?*
    25	
    26	Good TLDRs name **where energy went** (which people and/or repos concentrated the work), **the dominant mode** (shipping features, reviewing, hardening, onboarding, drifting), and **any standout signal** (a quiet stretch, a bus-factor risk, a sudden newcomer, a PR-cadence shift).
    27	
    28	**Weak:**
    29	> Over 11 active days, the team made 82 commits and opened 12 PRs across 4 repos, with @alice being the most active contributor.
    30	
    31	**Strong:**
    32	> A lopsided week anchored on `repo-one`, where @alice and @bob drove most of the feature work while four others made minor, scattered touches. PR cadence stayed unusually low — most shipping went direct to main.
    33	
    34	Notice: no numbers, named shape ("lopsided... anchored on... minor, scattered... unusually low"), and a concrete pattern the reader can act on.
    35	
    36	## FOCUS — 2 to 3 sentences per contributor
    37	
    38	Each FOCUS block sits under a `### @login` header. Answer: *What is this person actually working on, and what's the shape of their contribution?*
    39	
    40	The `@login` in the header is the subject of the whole block — you may refer to them by handle inside the FOCUS if it reads naturally, but you don't have to.
    41	
    42	**Do:**
    43	- Name 1–2 themes across their repos (e.g., "split between feature work on `repo-one` and defensive fixes on `repo-two`").
    44	- Flag tempo shifts (single burst day, steady daily, back-loaded, one-and-done).
    45	- Note role signals (heavy PR opening = builder, lots of reviews = not visible in this data but infer where possible, direct-to-main pushing = owner/solo).
    46	
    47	**Don't:**
    48	- List commit SHAs, PR numbers, or individual titles.
    49	- Describe each repo separately if the person touched many — synthesize into themes.
    50	- Pad if they're a minor contributor. Two sentences is the ceiling, not the floor.
    51	
    52	**Weak:**
    53	> @alice made 15 commits and opened 2 PRs in `repo-one`. Her commits included 5 feat, 4 fix, and 6 docs. She also had 3 commits in `repo-two`.
    54	
    55	**Strong:**
    56	> @alice drove the widget work on `repo-one` — a sustained daily cadence ending in two merged PRs — and spent the tail of the window hardening error paths in `repo-two`. The docs-heavy mid-week reads as pre-release polish rather than fresh ground.
    57	
    58	**Strong, for a minor contributor (1–3 events, no PRs):**
    59	> @carol: a single CI fix in `repo-one` mid-window. No feature work.
    60	
    61	## OBSERVATIONS — 3 to 5 bullets
    62	
    63	Answer: *What should a reader notice about the team that the Summary stats don't already say?*
    64	
    65	Mine the Appendix. Good team observations often sound slightly uncomfortable — they flag risks, gaps, or process smells.
    66	
    67	**Candidate signal types:**
    68	
    69	- **Bus factor:** one person driving disproportionate activity on a critical repo. "@alice authored 60% of `repo-one`'s activity — intentional ownership or concentration risk?"
    70	- **Handoff / pair patterns:** two contributors' commits interleaving in the same repo on the same days — possible pair work, review relay, or stepped-on-toes.
    71	- **Direct-push vs. PR ratio:** lots of commits land on main without PRs — is that policy or drift?
    72	- **PR cadence:** PRs piled up early or late, or arriving without matching commit follow-through.
    73	- **Silent repos:** a repo in scope with near-zero activity — intentional freeze, blocked, or nobody remembered to push.
    74	- **New contributors:** logins appearing only in the tail of the window — likely onboarding, worth confirming mentorship.
    75	- **Commit hygiene:** high share of uncategorized (non-conventional-commit) messages in one repo only — discipline slipping in that repo specifically.
    76	
    77	**Weak:**
    78	- @alice was the most active contributor.
    79	- 4 contributors opened PRs.
    80	- Most work happened in `repo-one`.
    81	
    82	**Strong:**
    83	- @alice owns ~60% of `repo-one`'s activity — worth confirming whether this is intentional lead or concentration risk.
    84	- `repo-three` saw two commits from a previously-unseen contributor in the tail of the window — likely onboarding; confirm review coverage.
    85	- PR cadence is 1:8 against commits — most work lands direct to main; if that isn't policy, worth a process review.
    86	- Mid-week zero-activity days (Apr 13, 14) break an otherwise steady cadence — holiday, team offsite, or blocked?
    87	
    88	Each bullet names a pattern *and* hints at the question a principal would want asked about it. That's the difference between reporting and briefing.
    89	
    90	## Worked example: before and after
    91	
    92	**Before (what agents keep producing):**
    93	
    94	> ## TLDR
    95	> In the 11-day window from April 7 to April 20, the team made 82 commits and opened 12 PRs across 4 repos, with @alice being the most active with 42 commits.
    96	>
    97	> ### @alice FOCUS
    98	> @alice made 42 commits across `repo-one` and `repo-two`. Her commits included 15 feat, 12 fix, 8 docs, and 7 other. She also opened 2 PRs including #123 Add widget and #124 Fix bug.
    99	
   100	**After (what this skill should produce):**
   101	
   102	> ## TLDR
   103	> A lopsided fortnight anchored on `repo-one`: @alice and @bob split the feature load while four others made minor, scattered touches across the other repos. PR cadence trailed commit cadence by 8:1 — most work shipped direct to main.
   104	>
   105	> ### @alice FOCUS
   106	> @alice drove the widget work on `repo-one` through a sustained daily cadence, closing the window with two merged PRs and a docs pass that reads as pre-release polish. Her `repo-two` touches were narrower — a pair of defensive fixes, likely shared ownership rather than focus.
   107	
   108	## Final check before you hand back
   109	
   110	- Could this have been written without looking at the Appendix? → If yes, mine harder.
   111	- Does any sentence name a SHA, PR number, branch, file, or commit title? → Cut it.
   112	- Is any FOCUS section longer than 3 sentences? → Cut it.
   113	- Does OBSERVATIONS just restate contributor counts or the most-active-person bullet? → Replace with real patterns.
   114	- Would a non-engineer (a VP, an investor, an ops lead) follow this? → If not, de-jargon.
   115	
   116	Keep the Appendix byte-identical. Replace only the three placeholder types, including their `<!-- ... -->` delimiters.

exec
/bin/zsh -lc "nl -ba utils/pdda/pdda-edit-doc-hook.sh && printf '\\n' && nl -ba utils/pdda/pdda-stop-doc-health.sh" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
 succeeded in 0ms:
     1	#!/usr/bin/env bash
     2	# pdda-edit-doc-hook.sh — PostToolUse(Edit|Write|MultiEdit) fast LOCAL single-file doc lint.
     3	#
     4	# Tier 1 of the two-tier doc-health system (tier 2 is the Stop full-scan, pdda-stop-doc-health.sh).
     5	# Reads the hook JSON on stdin, pulls tool_input.file_path, and:
     6	#   - exits 0 INSTANTLY for anything that is not ROADMAP.md or PROJECT/**/*.md (not a PDDA doc),
     7	#   - otherwise runs only the FAST LOCAL checks for that one file — NO network, NO gh, NO LLM:
     8	#       ROADMAP.md       -> `pdda.sh roadmap`
     9	#       PROJECT/**/*.md  -> frontmatter + status-table + hardcoded-paths + roadmap-coverage,
    10	#                           scoped to the single file via PDDA_ONLY_FILE
    11	#
    12	# WARN-ONLY and FAIL-OPEN: it ALWAYS exits 0, so it can NEVER block the edit. Findings print to stderr
    13	# for visibility only. Wire it in .claude/settings.json (PostToolUse, matcher "Edit|Write|MultiEdit").
    14	set -u
    15	
    16	HERE="$(cd "$(dirname "$0")" && pwd)"
    17	# shellcheck source=utils/pdda/pdda-lib.sh
    18	. "$HERE/pdda-lib.sh" 2>/dev/null || exit 0   # fail-open: if the lib can't load, never block the edit
    19	PDDA="$HERE/pdda.sh"
    20	
    21	payload="$(cat 2>/dev/null || true)"
    22	
    23	# Extract tool_input.file_path. An Edit/Write payload's only file_path values all name the edited file,
    24	# so a simple capture is safe; if it yields nothing we just exit 0 (fail-open).
    25	file_path="$(printf '%s' "$payload" \
    26	  | sed -n 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n1)"
    27	[ -n "$file_path" ] || exit 0
    28	
    29	# Normalize to a repo-relative path for the doc-type test.
    30	case "$file_path" in
    31	  "$PDDA_REPO_ROOT"/*) rel="${file_path#"$PDDA_REPO_ROOT"/}" ;;
    32	  /*) exit 0 ;;                # absolute path outside this repo — not ours
    33	  *) rel="$file_path" ;;       # already repo-relative
    34	esac
    35	
    36	# Instant no-op unless it is a PDDA-governed doc.
    37	case "$rel" in
    38	  ROADMAP.md|PROJECT/*.md) : ;;
    39	  *) exit 0 ;;
    40	esac
    41	
    42	# Local-only, observe mode (warn severities never block); we exit 0 regardless of any check's result.
    43	export PDDA_MODE=observe
    44	printf 'pdda doc-health (edit): %s\n' "$rel" >&2
    45	
    46	if [ "$rel" = "ROADMAP.md" ]; then
    47	  PDDA_ROADMAP="$file_path" "$PDDA" roadmap 1>&2 || true
    48	else
    49	  PDDA_ONLY_FILE="$file_path" "$PDDA" frontmatter      1>&2 || true
    50	  PDDA_ONLY_FILE="$file_path" "$PDDA" status-table     1>&2 || true
    51	  PDDA_ONLY_FILE="$file_path" "$PDDA" hardcoded-paths  1>&2 || true
    52	  PDDA_ONLY_FILE="$file_path" "$PDDA" roadmap-coverage 1>&2 || true
    53	fi
    54	
    55	exit 0

     1	#!/usr/bin/env bash
     2	# pdda-stop-doc-health.sh — Stop-hook tier 2 of the doc-health system: ONE consolidated, system-wide
     3	# doc-health scan per turn. It runs the deterministic suite — which already includes `issue-doc-sync`,
     4	# read from the CACHED gh-state file (PDDA_ISSUE_SYNC_SOURCE=cache) so there is NO network call — and
     5	# prints a single consolidated report of the warn/error findings.
     6	#
     7	# NEVER blocks: it ALWAYS exits 0, so it can never prevent a stop. The report is surfaced for
     8	# visibility only. Wire it in .claude/settings.json as a `Stop` hook. Pairs with tier 1,
     9	# pdda-edit-doc-hook.sh (the per-edit single-file lint).
    10	set -u
    11	
    12	HERE="$(cd "$(dirname "$0")" && pwd)"
    13	# shellcheck source=utils/pdda/pdda-lib.sh
    14	. "$HERE/pdda-lib.sh" 2>/dev/null || exit 0   # fail-open: if the lib can't load, never block the stop
    15	PDDA="$HERE/pdda.sh"
    16	
    17	# One deterministic, offline, non-blocking pass: cached gh-state + observe mode + no LLM (doc-ready
    18	# self-skips when PDDA_LLM_BIN is unset). `|| true` keeps a non-zero check from ever surfacing here.
    19	report="$(PDDA_ISSUE_SYNC_SOURCE=cache PDDA_MODE=observe PDDA_FORMAT=text PDDA_LLM_BIN="" \
    20	  "$PDDA" run 2>&1 || true)"
    21	
    22	findings="$(printf '%s\n' "$report" | grep -E '^(ERROR|WARN) ' || true)"
    23	nerr="$(printf '%s\n' "$findings" | grep -c '^ERROR ' 2>/dev/null || true)"
    24	nwarn="$(printf '%s\n' "$findings" | grep -c '^WARN ' 2>/dev/null || true)"
    25	
    26	{
    27	  printf '── PDDA doc-health (stop scan) ──\n'
    28	  if [ "${nerr:-0}" -eq 0 ] && [ "${nwarn:-0}" -eq 0 ]; then
    29	    printf 'all clear: no error/warn doc-health findings across the working set (issue-doc-sync from cached gh-state)\n'
    30	  else
    31	    printf '%s error(s), %s warn(s) — incl. issue-doc-sync against the cached gh-state file:\n' "$nerr" "$nwarn"
    32	    printf '%s\n' "$findings"
    33	  fi
    34	} >&2
    35	
    36	exit 0

codex
I have the Rebalance side now: two commands, three local skills, and two PDDA hook scripts wired through `.claude/settings.json`. Next I’m sampling the specific gsd-core and XYZ files that distinguish “real architecture” from mere catalog size.
exec
/bin/zsh -lc "nl -ba '/Users/noelsaw/Documents/GH Repos/gsd-core/docs/ARCHITECTURE.md' | sed -n '1,220p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
 succeeded in 0ms:
     1	# GSD Core Architecture
     2	
     3	> System architecture for contributors and advanced users. For user-facing documentation, see [Feature Reference](FEATURES.md) or [User Guide](USER-GUIDE.md).
     4	
     5	---
     6	
     7	## Table of Contents
     8	
     9	- [System Overview](#system-overview)
    10	- [Design Principles](#design-principles)
    11	- [Component Architecture](#component-architecture)
    12	- [Agent Model](#agent-model)
    13	- [Data Flow](#data-flow)
    14	- [File System Layout](#file-system-layout)
    15	- [Installer Architecture](#installer-architecture)
    16	- [Hook System](#hook-system)
    17	- [CLI Tools Layer](#cli-tools-layer)
    18	- [Runtime Abstraction](#runtime-abstraction)
    19	
    20	---
    21	
    22	## System Overview
    23	
    24	GSD Core is a **meta-prompting framework** that sits between the user and AI coding agents (Claude Code, Gemini CLI, Kimi CLI, OpenCode, Kilo, Codex, Copilot, Antigravity, Trae, Cline, Augment Code). It provides:
    25	
    26	1. **Context engineering** — Structured artifacts that give the AI everything it needs per task (see [Context engineering](explanation/context-engineering.md))
    27	2. **Multi-agent orchestration** — Thin orchestrators that spawn specialized agents with fresh context windows (see [Multi-agent orchestration](explanation/multi-agent-orchestration.md))
    28	3. **Spec-driven development** — Requirements → research → plans → execution → verification pipeline
    29	4. **State management** — Persistent project memory across sessions and context resets
    30	
    31	```
    32	┌──────────────────────────────────────────────────────┐
    33	│                      USER                            │
    34	│            /gsd-command [args]                        │
    35	└─────────────────────┬────────────────────────────────┘
    36	                      │
    37	┌─────────────────────▼────────────────────────────────┐
    38	│              COMMAND LAYER                            │
    39	│   commands/gsd/*.md — Prompt-based command files      │
    40	│   (Claude Code custom commands / Codex skills)        │
    41	└─────────────────────┬────────────────────────────────┘
    42	                      │
    43	┌─────────────────────▼────────────────────────────────┐
    44	│              WORKFLOW LAYER                           │
    45	│   gsd-core/workflows/*.md — Orchestration logic  │
    46	│   (Reads references, spawns agents, manages state)    │
    47	└──────┬──────────────┬─────────────────┬──────────────┘
    48	       │              │                 │
    49	┌──────▼──────┐ ┌─────▼─────┐ ┌────────▼───────┐
    50	│  AGENT      │ │  AGENT    │ │  AGENT         │
    51	│  (fresh     │ │  (fresh   │ │  (fresh        │
    52	│   context)  │ │   context)│ │   context)     │
    53	└──────┬──────┘ └─────┬─────┘ └────────┬───────┘
    54	       │              │                 │
    55	┌──────▼──────────────▼─────────────────▼──────────────┐
    56	│              CLI TOOLS LAYER                          │
    57	│   gsd-tools.cjs command families + domain modules      │
    58	│   command-routing-hub + observability seams            │
    59	└──────────────────────┬───────────────────────────────┘
    60	                       │
    61	┌──────────────────────▼───────────────────────────────┐
    62	│              FILE SYSTEM (.planning/)                 │
    63	│   PROJECT.md | REQUIREMENTS.md | ROADMAP.md          │
    64	│   STATE.md | config.json | phases/ | research/       │
    65	└──────────────────────────────────────────────────────┘
    66	```
    67	
    68	---
    69	
    70	## Design Principles
    71	
    72	### 1. Fresh Context Per Agent
    73	
    74	Every agent spawned by an orchestrator gets a clean context window (up to 200K tokens). This eliminates context rot — the quality degradation that happens as an AI fills its context window with accumulated conversation.
    75	
    76	### 2. Thin Orchestrators
    77	
    78	Workflow files (`gsd-core/workflows/*.md`) never do heavy lifting. They:
    79	
    80	- Load context via `gsd-tools.cjs init <workflow>`
    81	- Spawn specialized agents with focused prompts
    82	- Collect results and route to the next step
    83	- Update state between steps
    84	
    85	### 3. File-Based State
    86	
    87	All state lives in `.planning/` as human-readable Markdown and JSON. No database, no server, no external dependencies. This means:
    88	
    89	- State survives context resets (`/clear`)
    90	- State is inspectable by both humans and agents
    91	- State can be committed to git for team visibility
    92	
    93	### 4. Absent = Enabled
    94	
    95	Workflow feature flags follow the **absent = enabled** pattern. If a key is missing from `config.json`, it defaults to `true`. Users explicitly disable features; they don't need to enable defaults.
    96	
    97	### 5. Defense in Depth
    98	
    99	Multiple layers prevent common failure modes:
   100	
   101	- Plans are verified before execution (plan-checker agent)
   102	- Execution produces atomic commits per task
   103	- Post-execution verification checks against phase goals
   104	- UAT provides human verification as final gate
   105	
   106	---
   107	
   108	## Component Architecture
   109	
   110	### Commands (`commands/gsd/*.md`)
   111	
   112	User-facing entry points. Each file contains YAML frontmatter (name, description, allowed-tools) and a prompt body that bootstraps the workflow. Commands are installed as:
   113	
   114	- **Claude Code:** Custom slash commands (hyphen form, `/gsd-command-name`)
   115	- **OpenCode / Kilo:** Slash commands (hyphen form, `/gsd-command-name`)
   116	- **Codex:** Skills (`$gsd-command-name`)
   117	- **Copilot:** Slash commands (hyphen form, `/gsd-command-name`)
   118	- **Gemini CLI:** Slash commands under the `gsd:` namespace (colon form, `/gsd:command-name`) — Gemini namespaces all custom commands under their plugin id, so the install path rewrites every body-text reference to colon form
   119	- **Kimi CLI:** Agent Skills (`/skill:gsd-command-name`) plus an explicit custom agent launch with `kimi --agent-file`
   120	- **Antigravity:** Skills
   121	
   122	**Total commands:** see [`docs/INVENTORY.md`](INVENTORY.md#commands) for the authoritative count and full roster.
   123	
   124	#### Two-stage hierarchical routing (v1.40, [#2792](https://github.com/open-gsd/gsd-core/issues/2792))
   125	
   126	To keep the eager skill-listing token cost low, v1.40 introduces six namespace **meta-skills** (`gsd-workflow`, `gsd-project`, `gsd-quality`, `gsd-context`, `gsd-manage`, `gsd-ideate` — sourced from `commands/gsd/ns-*.md`, but the invocable `name:` is the bare form shown here) layered above the concrete sub-skills. On runtimes with non-recursive skill loaders (cline, qwen, hermes, augment, trae) the installer now realizes this fully: it emits only the 6 namespace router bundles as top-level skills and nests the ~61 concrete skills under `<router>/skills/<name>/SKILL.md`, so the eager listing is ≈6 entries instead of ≈67. The model selects a namespace router, which instructs it to read the nested concrete skill file via a routing table embedded in the router body. On these runtimes concrete skills are **not** directly invocable by bare name via the Skill tool; they are reachable through the router. Slash commands (`/gsd-*`, via the separate commands surface) are unaffected where the runtime has one. On runtimes with recursive or unconfirmed skill loaders (claude global, cursor, codex, copilot, windsurf, codebuddy, opencode, kilo, antigravity) the layout remains flat — all skills emitted at the top level as before. Antigravity moved from nested to flat in #1614: `agy` scans only `skills/<name>/SKILL.md`, so nested sub-skills were unreachable. Claude was reverted to flat in #924: the Skill tool hard-errors on unknown names rather than re-routing via the router, so nested concrete skills were uninvokable.
   127	
   128	The router descriptions use pipe-separated keyword tags (≤ 60 chars) per the Tool Attention research showing keyword-dense tags outperform prose for routing at ~40 % the token cost.
   129	
   130	#### MCP token-budget interaction
   131	
   132	The eager skill listing is one of two recurring per-turn token costs. The other is the MCP tool schema injected by every enabled MCP server in `.claude/settings.json`. Heavyweight MCP servers (browser/playwright, Mac-tools, Windows-tools) can each cost 20 k+ tokens per turn — often dwarfing what `model_profile` tuning saves. The toggle lives in the Claude Code harness (`enabledMcpjsonServers` / `disabledMcpjsonServers` in `.claude/settings.json`) and is **not** a GSD concern. Together, the two-stage routing layer (#2792) and disciplined MCP enablement are the largest cost levers per turn. See [`docs/USER-GUIDE.md`](USER-GUIDE.md) and `references/context-budget.md` for the audit checklist.
   133	
   134	### Workflows (`gsd-core/workflows/*.md`)
   135	
   136	Orchestration logic that commands reference. Contains the step-by-step process including:
   137	
   138	- Context loading via `gsd-tools.cjs init` handlers
   139	- Agent spawn instructions with model resolution
   140	- Gate/checkpoint definitions
   141	- State update patterns
   142	- Error handling and recovery
   143	
   144	**Total workflows:** see [`docs/INVENTORY.md`](INVENTORY.md#workflows) for the authoritative count and full roster.
   145	
   146	#### Progressive disclosure for workflows
   147	
   148	Workflow files are loaded verbatim into Claude's context every time the
   149	corresponding `/gsd-*` command is invoked. The workflow size budget enforced by
   150	`tests/workflow-size-budget.test.cjs` keeps each file bounded, mirroring the
   151	the agent size-budget convention. The budget is measured in **bytes** (#717), not lines:
   152	line count over-penalizes prose and under-catches token-dense tables and code
   153	blocks, whereas bytes are deterministic and match the unit our vendors bound on
   154	— Codex truncates instruction docs past 32,768 bytes (`project_doc_max_bytes`).
   155	We adopt that unit, not that exact number: the XL/LARGE ceilings below sit above
   156	32,768 because these are grandfathered top-level orchestrators loaded by Claude,
   157	not Codex AGENTS.md docs.
   158	
   159	| Tier      | Per-file byte limit |
   160	|-----------|---------------------|
   161	| `XL`      | 90,000 — top-level orchestrators (`execute-phase`, `plan-phase`, `new-project`) |
   162	| `LARGE`   | 54,000 — multi-step planners and large feature workflows |
   163	| `DEFAULT` | 38,000 — focused single-purpose workflows (the target tier) |
   164	
   165	Ceilings are not fixed forever: under the tighten-only ratchet (#597) each one
   166	tracks its tier's current high-water mark within a small grace band, so budgets
   167	may only decrease over time.
   168	
   169	**Why the budget exists.** With prompt caching the per-invocation *cost* of a
   170	large workflow is modest (cache reads run ~10% of input). The stronger,
   171	caching-independent reason is **quality**: as context grows, recall and
   172	reasoning degrade ("context rot" / attention budget), so leaner, higher-signal
   173	instructions produce better plans. The ceiling protects the agent's attention,
   174	not just the token bill.
   175	
   176	Because the budget measures one file, it is a proxy for the real goal —
   177	*bounded loaded context*. Extraction only helps when the extracted content is
   178	loaded **lazily** (Read at the step that needs it). Moving prose into a file
   179	that is still eagerly `@`-imported shrinks the measured file without shrinking
   180	loaded context, which games the proxy rather than serving the goal.
   181	
   182	`workflows/discuss-phase.md` is held to a stricter <30,000-byte ceiling per
   183	the discuss-phase byte budget (#717; the discuss-phase/modes split keeps it ≈32000 bytes). When a workflow grows
   184	beyond its tier, extract per-mode bodies into
   185	`workflows/<workflow>/modes/<mode>.md`, templates into
   186	`workflows/<workflow>/templates/`, and shared knowledge into
   187	`gsd-core/references/`. The parent file becomes a thin dispatcher that
   188	Reads only the mode and template files needed for the current invocation.
   189	
   190	`workflows/discuss-phase/` is the canonical example of this pattern —
   191	parent dispatches, modes/ holds per-flag behavior (`power.md`, `all.md`,
   192	`auto.md`, `chain.md`, `text.md`, `batch.md`, `analyze.md`, `default.md`,
   193	`advisor.md`), and templates/ holds CONTEXT.md, DISCUSSION-LOG.md, and
   194	checkpoint.json schemas that are read only when the corresponding output
   195	file is being written.
   196	
   197	`workflows/plan-phase.md`, `workflows/execute-phase.md`, and the
   198	`gsd-planner` / `gsd-executor` agent definitions apply the same discipline
   199	to their MVP-only reference bodies — `planner-mvp-mode.md`,
   200	`user-story-template.md`, `skeleton-template.md`, and `execute-mvp-tdd.md`
   201	are referenced for the planner/executor to Read only on MVP,
   202	Walking-Skeleton, or MVP+TDD paths, rather than eagerly `@`-imported, so
   203	non-MVP runs do not pay their context cost (guards against the "`@`-import
   204	behind a conditional still loads eagerly" leak; see #720). The dedicated
   205	`mvp-phase` workflow keeps its eager imports, since it is always MVP.
   206	
   207	### Agents (`agents/*.md`)
   208	
   209	Specialized agent definitions with frontmatter specifying:
   210	
   211	- `name` — Agent identifier
   212	- `description` — Role and purpose
   213	- `tools` — Allowed tool access (Read, Write, Edit, Bash, Grep, Glob, WebSearch, etc.)
   214	- `color` — Terminal output color for visual distinction
   215	
   216	**Total agents:** 33
   217	
   218	### References (`gsd-core/references/*.md`)
   219	
   220	Shared knowledge documents that workflows and agents `@-reference` (see [`docs/INVENTORY.md`](INVENTORY.md#references) for the authoritative full roster):

exec
/bin/zsh -lc "nl -ba '/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/execute-phase.md' | sed -n '1,180p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
 succeeded in 0ms:
     1	---
     2	name: gsd:execute-phase
     3	description: Execute all plans in a phase with wave-based parallelization
     4	argument-hint: "<phase-number> [--wave N] [--gaps-only] [--interactive] [--tdd]"
     5	effort: max
     6	allowed-tools:
     7	  - Read
     8	  - Write
     9	  - Edit
    10	  - Glob
    11	  - Grep
    12	  - Bash
    13	  - Agent
    14	  - TodoWrite
    15	  - AskUserQuestion
    16	requires: [phase, verify-work]
    17	---
    18	<objective>
    19	Execute all plans in a phase using wave-based parallel execution.
    20	
    21	Orchestrator stays lean: discover plans, analyze dependencies, group into waves, spawn subagents, collect results. Each subagent loads the full execute-plan context and handles its own plan.
    22	
    23	Optional wave filter:
    24	- `--wave N` executes only Wave `N` for pacing, quota management, or staged rollout
    25	- phase verification/completion still only happens when no incomplete plans remain after the selected wave finishes
    26	
    27	Flag handling rule:
    28	- The optional flags documented below are available behaviors, not implied active behaviors
    29	- A flag is active only when its literal token appears in `$ARGUMENTS`
    30	- If a documented flag is absent from `$ARGUMENTS`, treat it as inactive
    31	
    32	Context budget: ~15% orchestrator, 100% fresh per subagent.
    33	</objective>
    34	
    35	<execution_context>
    36	@~/.claude/gsd-core/workflows/execute-phase.md
    37	@~/.claude/gsd-core/references/ui-brand.md
    38	</execution_context>
    39	
    40	<runtime_note>
    41	**Copilot (VS Code):** Use `vscode_askquestions` wherever this workflow calls `AskUserQuestion`. They are equivalent — `vscode_askquestions` is the VS Code Copilot implementation of the same interactive question API.
    42	</runtime_note>
    43	
    44	<context>
    45	Phase: $ARGUMENTS
    46	
    47	**Available optional flags (documentation only — not automatically active):**
    48	- `--wave N` — Execute only Wave `N` in the phase. Use when you want to pace execution or stay inside usage limits.
    49	- `--gaps-only` — Execute only gap closure plans (plans with `gap_closure: true` in frontmatter). Use after verify-work creates fix plans.
    50	- `--interactive` — Execute plans sequentially inline (no subagents) with user checkpoints between tasks. Lower token usage, pair-programming style. Best for small phases, bug fixes, and verification gaps.
    51	
    52	**Active flags must be derived from `$ARGUMENTS`:**
    53	- `--wave N` is active only if the literal `--wave` token is present in `$ARGUMENTS`
    54	- `--gaps-only` is active only if the literal `--gaps-only` token is present in `$ARGUMENTS`
    55	- `--interactive` is active only if the literal `--interactive` token is present in `$ARGUMENTS`
    56	- If none of these tokens appear, run the standard full-phase execution flow with no flag-specific filtering
    57	- Do not infer that a flag is active just because it is documented in this prompt
    58	
    59	Context files are resolved inside the workflow via `gsd-tools query init.execute-phase` and per-subagent `<files_to_read>` blocks.
    60	</context>
    61	
    62	<process>
    63	Execute end-to-end.
    64	Preserve all workflow gates (wave execution, checkpoint handling, verification, state updates, routing).
    65	</process>

exec
/bin/zsh -lc "nl -ba '/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-executor.md' | sed -n '1,220p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
 succeeded in 0ms:
     1	---
     2	name: gsd-executor
     3	description: Executes GSD plans with atomic commits, deviation handling, checkpoint protocols, and state management. Spawned by execute-phase orchestrator or execute-plan command.
     4	tools: Read, Write, Edit, Bash, Grep, Glob, Skill, mcp__context7__*
     5	color: yellow
     6	# hooks:
     7	#   PostToolUse:
     8	#     - matcher: "Write|Edit"
     9	#       hooks:
    10	#         - type: command
    11	#           command: "npx eslint --fix $FILE 2>/dev/null || true"
    12	---
    13	
    14	<role>
    15	You are a GSD plan executor. You execute PLAN.md files atomically, creating per-task commits, handling deviations automatically, pausing at checkpoints, and producing SUMMARY.md files.
    16	
    17	Spawned by `/gsd:execute-phase` orchestrator.
    18	
    19	Your job: Execute the plan completely, commit each task, create SUMMARY.md, update STATE.md.
    20	
    21	@~/.claude/gsd-core/references/mandatory-initial-read.md
    22	</role>
    23	
    24	<documentation_lookup>
    25	When you need library or framework documentation, check in this order:
    26	
    27	1. If Context7 MCP tools (`mcp__context7__*`) are available in your environment, use them:
    28	   - Resolve library ID: `mcp__context7__resolve-library-id` with `libraryName`
    29	   - Fetch docs: `mcp__context7__get-library-docs` with `context7CompatibleLibraryId` and `topic`
    30	
    31	2. If Context7 MCP is not available (upstream bug anthropics/claude-code#13898 strips MCP
    32	   tools from agents with a `tools:` frontmatter restriction), use the CLI fallback via Bash:
    33	
    34	   Step 1 — Resolve library ID:
    35	   ```bash
    36	   if command -v ctx7 &>/dev/null; then
    37	     ctx7 library <name> "<query>"
    38	   else
    39	     echo "ctx7 not found — install with: npm install -g ctx7 (verify at npmjs.com/package/ctx7 first)"
    40	   fi
    41	   ```
    42	
    43	   Step 2 — Fetch documentation:
    44	   ```bash
    45	   if command -v ctx7 &>/dev/null; then
    46	     ctx7 docs <libraryId> "<query>"
    47	   else
    48	     echo "ctx7 not found — install with: npm install -g ctx7 (verify at npmjs.com/package/ctx7 first)"
    49	   fi
    50	   ```
    51	
    52	Do not skip documentation lookups because MCP tools are unavailable — the CLI fallback
    53	works via Bash and produces equivalent output. Do not rely on training knowledge alone
    54	for library APIs where version-specific behavior matters. Do NOT use `npx --yes` to
    55	auto-download ctx7 — this silently executes unverified packages from the registry.
    56	</documentation_lookup>
    57	
    58	<project_context>
    59	Before executing, discover project context:
    60	
    61	**Project instructions:** Read `./CLAUDE.md` if it exists in the working directory. Follow all project-specific guidelines, security requirements, and coding conventions.
    62	
    63	**Project skills:** @~/.claude/gsd-core/references/project-skills-discovery.md
    64	- Load `rules/*.md` as needed during **implementation**.
    65	- Follow skill rules relevant to the task you are about to commit.
    66	
    67	**agent_skills:** self-load per @~/.claude/gsd-core/references/agent-skills-bootstrap.md
    68	
    69	**CLAUDE.md enforcement:** If `./CLAUDE.md` exists, treat its directives as hard constraints during execution. Before committing each task, verify that code changes do not violate CLAUDE.md rules (forbidden patterns, required conventions, mandated tools). If a task action would contradict a CLAUDE.md directive, apply the CLAUDE.md rule — it takes precedence over plan instructions. Document any CLAUDE.md-driven adjustments as deviations (Rule 2: auto-add missing critical functionality).
    70	</project_context>
    71	
    72	<execution_flow>
    73	
    74	<step name="load_project_state" priority="first">
    75	Load execution context:
    76	
    77	```bash
    78	_GSD_SHIM_NAME="gsd-tools.cjs"; _GSD_RUNTIME_ROOT="${RUNTIME_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"; GSD_TOOLS="${_GSD_RUNTIME_ROOT}/gsd-core/bin/${_GSD_SHIM_NAME}"; if [ -f "$GSD_TOOLS" ]; then gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${_GSD_RUNTIME_ROOT}/.claude/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${_GSD_RUNTIME_ROOT}/.claude/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${_GSD_RUNTIME_ROOT}/.codex/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${_GSD_RUNTIME_ROOT}/.codex/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif command -v gsd-tools >/dev/null 2>&1; then GSD_TOOLS="$(command -v gsd-tools)"; gsd_run() { "$GSD_TOOLS" "$@"; }; elif [ -f "$HOME/.claude/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="$HOME/.claude/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${HERMES_HOME:-$HOME/.hermes}/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${HERMES_HOME:-$HOME/.hermes}/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${CURSOR_CONFIG_DIR:-$HOME/.cursor}/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${CURSOR_CONFIG_DIR:-$HOME/.cursor}/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${CODEX_HOME:-$HOME/.codex}/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${CODEX_HOME:-$HOME/.codex}/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${GEMINI_CONFIG_DIR:-$HOME/.gemini}/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${GEMINI_CONFIG_DIR:-$HOME/.gemini}/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${COPILOT_CONFIG_DIR:-$HOME/.copilot}/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${COPILOT_CONFIG_DIR:-$HOME/.copilot}/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${WINDSURF_CONFIG_DIR:-$HOME/.codeium/windsurf}/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${WINDSURF_CONFIG_DIR:-$HOME/.codeium/windsurf}/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${AUGMENT_CONFIG_DIR:-$HOME/.augment}/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${AUGMENT_CONFIG_DIR:-$HOME/.augment}/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${TRAE_CONFIG_DIR:-$HOME/.trae}/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${TRAE_CONFIG_DIR:-$HOME/.trae}/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${QWEN_CONFIG_DIR:-$HOME/.qwen}/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${QWEN_CONFIG_DIR:-$HOME/.qwen}/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${CODEBUDDY_CONFIG_DIR:-$HOME/.codebuddy}/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${CODEBUDDY_CONFIG_DIR:-$HOME/.codebuddy}/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${CLINE_CONFIG_DIR:-$HOME/.cline}/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${CLINE_CONFIG_DIR:-$HOME/.cline}/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${GROK_AGENTS_HOME:-$HOME/.agents}/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${GROK_AGENTS_HOME:-$HOME/.agents}/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${ANTIGRAVITY_CONFIG_DIR:-$HOME/.gemini/antigravity}/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${ANTIGRAVITY_CONFIG_DIR:-$HOME/.gemini/antigravity}/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${OPENCODE_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/opencode}/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${OPENCODE_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/opencode}/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${KILO_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/kilo}/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${KILO_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/kilo}/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; else echo "ERROR: gsd-tools.cjs not found at $GSD_TOOLS and gsd-tools is not on PATH. Run: npx -y @opengsd/gsd-core@latest --claude --local" >&2; exit 1; fi; if [ -n "${CLAUDE_ENV_FILE:-}" ] && [ -n "${GSD_TOOLS:-}" ]; then printf "export PATH='%s':\"\$PATH\"\n" "${GSD_TOOLS%/*}" >> "$CLAUDE_ENV_FILE" 2>/dev/null || true; fi
    79	INIT=$(gsd_run query init.execute-phase "${PHASE}")
    80	if [[ "$INIT" == @file:* ]]; then INIT=$(cat "${INIT#@file:}"); fi
    81	```
    82	
    83	Extract from init JSON: `executor_model`, `commit_docs`, `sub_repos`, `phase_dir`, `plans`, `incomplete_plans`.
    84	
    85	Also load planning state (position, decisions, blockers) via the SDK — **use `node` to invoke the CLI** (not `npx`):
    86	```bash
    87	gsd_run query state.load 2>/dev/null
    88	```
    89	If STATE.md missing but .planning/ exists: offer to reconstruct or continue without.
    90	If .planning/ missing: Error — project not initialized.
    91	</step>
    92	
    93	<step name="load_plan">
    94	Read the plan file provided in your prompt context.
    95	
    96	Parse: frontmatter (phase, plan, type, autonomous, wave, depends_on), objective, context (@-references), tasks with types, verification/success criteria, output spec.
    97	
    98	**If plan references CONTEXT.md:** Honor user's vision throughout execution.
    99	</step>
   100	
   101	<step name="record_start_time">
   102	```bash
   103	PLAN_START_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
   104	PLAN_START_EPOCH=$(date +%s)
   105	```
   106	</step>
   107	
   108	<worktree_metadata_capture>
   109	If running inside a git worktree, capture authoritative worktree identity before
   110	any task commit changes HEAD. The execute-phase orchestrator consumes this from
   111	your final `<worktree_metadata>` return block to build the wave cleanup manifest
   112	without relying on runtime harness metadata (#1297).
   113	
   114	```bash
   115	GSD_WORKTREE_PATH=""
   116	GSD_WORKTREE_BRANCH=""
   117	GSD_WORKTREE_EXPECTED_BASE=""
   118	if [ -f .git ]; then
   119	  GSD_WORKTREE_PATH=$(git rev-parse --show-toplevel)
   120	  GSD_WORKTREE_BRANCH=$(git rev-parse --abbrev-ref HEAD)
   121	  GSD_WORKTREE_EXPECTED_BASE=$(git rev-parse HEAD)
   122	fi
   123	```
   124	</worktree_metadata_capture>
   125	
   126	<step name="determine_execution_pattern">
   127	```bash
   128	grep -n "type=\"checkpoint" [plan-path]
   129	```
   130	
   131	**Pattern A: Fully autonomous (no checkpoints)** — Execute all tasks, create SUMMARY, commit.
   132	
   133	**Pattern B: Has checkpoints** — Execute until checkpoint, STOP, return structured message. You will NOT be resumed.
   134	
   135	**Pattern C: Continuation** — Check `<completed_tasks>` in prompt, verify commits exist, resume from specified task.
   136	</step>
   137	
   138	<step name="execute_tasks">
   139	At execution decision points, apply structured reasoning:
   140	@~/.claude/gsd-core/references/thinking-models-execution.md
   141	
   142	**iOS app scaffolding:** If this plan creates an iOS app target, follow ios-scaffold guidance:
   143	@~/.claude/gsd-core/references/ios-scaffold.md
   144	
   145	For each task:
   146	
   147	1. **If `type="auto"`:**
   148	   - Check for `tdd="true"` → follow TDD execution flow
   149	   - Execute task, apply deviation rules as needed
   150	   - Handle auth errors as authentication gates
   151	   - Run verification, confirm done criteria
   152	   - Commit (see task_commit_protocol)
   153	   - Track completion + commit hash for Summary
   154	
   155	2. **If `type="checkpoint:*"`:**
   156	   - STOP immediately — return structured checkpoint message
   157	   - A fresh agent will be spawned to continue
   158	
   159	3. After all tasks: run overall verification, confirm success criteria, document deviations
   160	</step>
   161	
   162	</execution_flow>
   163	
   164	<deviation_rules>
   165	**While executing, you WILL discover work not in the plan.** Apply these rules automatically. Track all deviations for Summary.
   166	
   167	**Shared process for Rules 1-3:** Fix inline → add/update tests if applicable → verify fix → continue task → track as `[Rule N - Type] description`
   168	
   169	No user permission needed for Rules 1-3.
   170	
   171	---
   172	
   173	**RULE 1: Auto-fix bugs**
   174	
   175	**Trigger:** Code doesn't work as intended (broken behavior, errors, incorrect output)
   176	
   177	**Examples:** Wrong queries, logic errors, type errors, null pointer exceptions, broken validation, security vulnerabilities, race conditions, memory leaks
   178	
   179	---
   180	
   181	**RULE 2: Auto-add missing critical functionality**
   182	
   183	**Trigger:** Code missing essential features for correctness, security, or basic operation
   184	
   185	**Examples:** Missing error handling, no input validation, missing null checks, no auth on protected routes, missing authorization, no CSRF/CORS, no rate limiting, missing DB indexes, no error logging
   186	
   187	**Critical = required for correct/secure/performant operation.** These aren't "features" — they're correctness requirements.
   188	
   189	**Threat model reference:** Before starting each task, check if the plan's `<threat_model>` assigns `mitigate` dispositions to this task's files. Mitigations in the threat register are correctness requirements — apply Rule 2 if absent from implementation.
   190	
   191	---
   192	
   193	**RULE 3: Auto-fix blocking issues**
   194	
   195	**Trigger:** Something prevents completing current task
   196	
   197	**Examples:** Wrong types, broken imports, missing env var, DB connection error, build config error, missing referenced file, circular dependency
   198	
   199	**EXCLUDED from RULE 3 — package manager installs:**
   200	Running `npm install <pkg>`, `pip install <pkg>`, `cargo add <pkg>`, or any equivalent package-manager install command is **NOT** auto-fixable. If a referenced package fails to install or cannot be found:
   201	1. Do NOT attempt to install a similarly-named alternative.
   202	2. Do NOT retry with a different package name.
   203	3. Return a `checkpoint:human-verify` task — the user must verify the package is legitimate before the executor proceeds.
   204	
   205	This exclusion exists because a failed install may indicate a slopsquatted or hallucinated package name. Auto-substituting an alternative could install something more dangerous. If a package install fails, emit:
   206	
   207	```xml
   208	<task type="checkpoint:human-verify" gate="blocking-human">
   209	  <what-built>Package install failed — human verification required</what-built>
   210	  <how-to-verify>
   211	    `[package-name]` could not be installed. Before proceeding:
   212	    1. Verify the package exists and is legitimate: https://npmjs.com/package/[package-name]
   213	    2. Confirm the package name is spelled correctly in PLAN.md
   214	    3. If the package does not exist, re-run /gsd:plan-phase --research-phase <N> to find the correct package
   215	  </how-to-verify>
   216	  <resume-signal>Type "verified" with the correct package name, or "abort" to stop the phase</resume-signal>
   217	</task>
   218	```
   219	
   220	Use `gate="blocking-human"` for package-legitimacy checkpoints so they are unambiguously excluded from auto-approval behavior.

exec
/bin/zsh -lc "nl -ba '/Users/noelsaw/Documents/GH Repos/gsd-core/skills/gsd-execute-phase/SKILL.md' | sed -n '1,180p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
 succeeded in 0ms:
     1	---
     2	name: gsd-execute-phase
     3	description: "Execute all plans in a phase with wave-based parallelization"
     4	argument-hint: "<phase-number> [--wave N] [--gaps-only] [--interactive] [--tdd]"
     5	effort: max
     6	allowed-tools:
     7	  - Read
     8	  - Write
     9	  - Edit
    10	  - Glob
    11	  - Grep
    12	  - Bash
    13	  - Agent
    14	  - TodoWrite
    15	  - AskUserQuestion
    16	---
    17	
    18	<objective>
    19	Execute all plans in a phase using wave-based parallel execution.
    20	
    21	Orchestrator stays lean: discover plans, analyze dependencies, group into waves, spawn subagents, collect results. Each subagent loads the full execute-plan context and handles its own plan.
    22	
    23	Optional wave filter:
    24	- `--wave N` executes only Wave `N` for pacing, quota management, or staged rollout
    25	- phase verification/completion still only happens when no incomplete plans remain after the selected wave finishes
    26	
    27	Flag handling rule:
    28	- The optional flags documented below are available behaviors, not implied active behaviors
    29	- A flag is active only when its literal token appears in `$ARGUMENTS`
    30	- If a documented flag is absent from `$ARGUMENTS`, treat it as inactive
    31	
    32	Context budget: ~15% orchestrator, 100% fresh per subagent.
    33	</objective>
    34	
    35	<execution_context>
    36	@~/.claude/gsd-core/workflows/execute-phase.md
    37	@~/.claude/gsd-core/references/ui-brand.md
    38	</execution_context>
    39	
    40	<runtime_note>
    41	**Copilot (VS Code):** Use `vscode_askquestions` wherever this workflow calls `AskUserQuestion`. They are equivalent — `vscode_askquestions` is the VS Code Copilot implementation of the same interactive question API.
    42	</runtime_note>
    43	
    44	<context>
    45	Phase: $ARGUMENTS
    46	
    47	**Available optional flags (documentation only — not automatically active):**
    48	- `--wave N` — Execute only Wave `N` in the phase. Use when you want to pace execution or stay inside usage limits.
    49	- `--gaps-only` — Execute only gap closure plans (plans with `gap_closure: true` in frontmatter). Use after verify-work creates fix plans.
    50	- `--interactive` — Execute plans sequentially inline (no subagents) with user checkpoints between tasks. Lower token usage, pair-programming style. Best for small phases, bug fixes, and verification gaps.
    51	
    52	**Active flags must be derived from `$ARGUMENTS`:**
    53	- `--wave N` is active only if the literal `--wave` token is present in `$ARGUMENTS`
    54	- `--gaps-only` is active only if the literal `--gaps-only` token is present in `$ARGUMENTS`
    55	- `--interactive` is active only if the literal `--interactive` token is present in `$ARGUMENTS`
    56	- If none of these tokens appear, run the standard full-phase execution flow with no flag-specific filtering
    57	- Do not infer that a flag is active just because it is documented in this prompt
    58	
    59	Context files are resolved inside the workflow via `gsd-tools query init.execute-phase` and per-subagent `<files_to_read>` blocks.
    60	</context>
    61	
    62	<process>
    63	Execute end-to-end.
    64	Preserve all workflow gates (wave execution, checkpoint handling, verification, state updates, routing).
    65	</process>

exec
/bin/zsh -lc "nl -ba '/Users/noelsaw/Documents/GH Repos/gsd-core/hooks/hooks.json' | sed -n '1,220p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
 succeeded in 0ms:
     1	{
     2	  "hooks": {
     3	    "SessionStart": [
     4	      {
     5	        "hooks": [
     6	          { "type": "command", "command": "node \"${CLAUDE_PLUGIN_ROOT}/hooks/gsd-ensure-canonical-path.js\"", "timeout": 5 },
     7	          { "type": "command", "command": "node \"${CLAUDE_PLUGIN_ROOT}/hooks/gsd-check-update.js\"" }
     8	        ]
     9	      }
    10	    ],
    11	    "PreToolUse": [
    12	      {
    13	        "matcher": "Write|Edit",
    14	        "hooks": [
    15	          { "type": "command", "command": "node \"${CLAUDE_PLUGIN_ROOT}/hooks/gsd-prompt-guard.js\"", "timeout": 5 },
    16	          { "type": "command", "command": "node \"${CLAUDE_PLUGIN_ROOT}/hooks/gsd-read-guard.js\"", "timeout": 5 }
    17	        ]
    18	      },
    19	      {
    20	        "matcher": "Write|Edit|MultiEdit",
    21	        "hooks": [
    22	          { "type": "command", "command": "node \"${CLAUDE_PLUGIN_ROOT}/hooks/gsd-worktree-path-guard.js\"", "timeout": 5 }
    23	        ]
    24	      }
    25	    ],
    26	    "PostToolUse": [
    27	      {
    28	        "matcher": "Bash|Edit|Write|MultiEdit|Agent|Task",
    29	        "hooks": [
    30	          { "type": "command", "command": "node \"${CLAUDE_PLUGIN_ROOT}/hooks/gsd-context-monitor.js\"", "timeout": 10 }
    31	        ]
    32	      },
    33	      {
    34	        "matcher": "Read|WebFetch|WebSearch",
    35	        "hooks": [
    36	          { "type": "command", "command": "node \"${CLAUDE_PLUGIN_ROOT}/hooks/gsd-read-injection-scanner.js\"", "timeout": 5 }
    37	        ]
    38	      }
    39	    ],
    40	    "SubagentStop": [
    41	      {
    42	        "hooks": [
    43	          { "type": "command", "command": "node \"${CLAUDE_PLUGIN_ROOT}/hooks/gsd-context-monitor.js\"", "timeout": 10 }
    44	        ]
    45	      }
    46	    ],
    47	    "Stop": [
    48	      {
    49	        "hooks": [
    50	          { "type": "command", "command": "node \"${CLAUDE_PLUGIN_ROOT}/hooks/gsd-context-monitor.js\"", "timeout": 10 }
    51	        ]
    52	      }
    53	    ],
    54	    "PreCompact": [
    55	      {
    56	        "hooks": [
    57	          { "type": "command", "command": "node \"${CLAUDE_PLUGIN_ROOT}/hooks/gsd-context-monitor.js\"", "timeout": 10 }
    58	        ]
    59	      }
    60	    ],
    61	    "FileChanged": [
    62	      {
    63	        "matcher": "config.json",
    64	        "hooks": [
    65	          { "type": "command", "command": "node \"${CLAUDE_PLUGIN_ROOT}/hooks/gsd-config-reload.js\"", "timeout": 8 }
    66	        ]
    67	      }
    68	    ]
    69	  }
    70	}

exec
/bin/zsh -lc "nl -ba '/Users/noelsaw/Documents/GH Repos/gsd-core/docs/explanation/capability-trust-model.md' | sed -n '1,300p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
 succeeded in 0ms:
     1	# The capability trust model
     2	
     3	> **Explanation** — This document describes *why* GSD draws its trust
     4	> boundaries where it does, and *what the trade-offs are*. It is not a
     5	> step-by-step guide to installing capabilities; for that, see the how-to
     6	> guides for [importing a capability](../how-to/import-a-capability-from-a-url.md) and
     7	> [version management](../how-to/version-a-capability.md). For the decision record, see
     8	> [ADR-1244 D5](../adr/1244-capability-ecosystem.md#d5--trust-model-artifact-parity-is-full-trust-posture-is-tiered).
     9	> For the capability field reference, see the
    10	> [capability matrix](../reference/capability-matrix.md).
    11	
    12	---
    13	
    14	## The central thesis: artifact parity is not trust parity
    15	
    16	GSD 1.6.0 opens the capability platform to third-party authors with **full
    17	artifact parity**: a third-party capability may ship the same executable
    18	surfaces that GSD Core ships — hooks, MCP servers, command modules. This is a
    19	deliberate product choice, and it carries real security weight.
    20	
    21	Full parity means a third-party capability, once installed, can execute code
    22	the next time a relevant loop event fires. There is no "first use" gate.
    23	There is no sandbox. The capability author has, in effect, a code-execution
    24	path into your runtime.
    25	
    26	The maintainer's response to this is not to deny parity but to draw a sharp
    27	line between two things that are often conflated:
    28	
    29	- **Artifact parity** — what a third-party capability is *allowed to ship*.
    30	- **Trust posture** — the evidence and consent required before that capability
    31	  *executes* on your machine.
    32	
    33	GSD grants full artifact parity. It does not grant symmetric trust. First-party
    34	capabilities are implicitly trusted because they *are* the shipped package —
    35	their provenance is the GSD Core release process itself. Third-party
    36	capabilities require explicit, informed, revocable consent plus SHA-pinned
    37	integrity before any executable surface is activated. These two things are
    38	structurally separate, and keeping them separate is what makes full parity
    39	defensible.
    40	
    41	---
    42	
    43	## What the ecosystem learnt the hard way
    44	
    45	GSD's trust model is not designed in isolation. It is informed by failures in
    46	four ecosystems that tackled the same problem — and each one paid tuition.
    47	
    48	### VS Code: auto-update + stolen publisher credentials
    49	
    50	VS Code's extension marketplace grants extensions the same permissions as the
    51	editor itself. In 2023 a publisher's personal access token was stolen; the
    52	attacker published a backdoored update to an existing, trusted extension. Every
    53	user with auto-update enabled received the malicious version silently, on the
    54	next launch, with no prompt. The lesson: auto-update for executable surfaces is
    55	a liability when credentials can be compromised, because the user's last
    56	explicit act of trust was for *version N* — not for whatever version N+1
    57	contains.
    58	
    59	GSD's response: auto-update is **off by default** for third-party capabilities.
    60	When it is enabled, a change to the *executable set* (the set of hooks, MCP
    61	servers, or command modules the capability declares) triggers a re-consent
    62	prompt before the update applies. Updating a non-executable capability
    63	(documentation, agents, skills) does not require re-consent.
    64	
    65	VS Code also has no signature check on VSIX packages. GSD requires an
    66	`integrity` SHA-512 pin in the ledger, verified before extraction.
    67	
    68	### npm: the supply-chain attack surface
    69	
    70	npm's `postinstall` scripts mean that downloading a package can execute
    71	arbitrary code on the developer's machine — a property that supply-chain
    72	attackers have exploited in the s1ngularity attack class (a malicious package
    73	is published under a name a legitimate package depends on). npm's own
    74	recommendation for sensitive environments is `--ignore-scripts`.
    75	
    76	GSD takes a stronger position: **install never executes capability code**,
    77	full stop. Installation is a copy-only staging operation. There is no
    78	`postinstall`-equivalent. A capability's hooks, MCP server, and command
    79	modules are not invoked during install; they are first invoked when the loop
    80	fires after install. This means a malicious payload in an executable surface
    81	cannot be triggered by the act of downloading it — the user has a window
    82	between install and first use to verify what they consented to.
    83	
    84	SLSA provenance (the `provenance` field in `capability.json`) provides a
    85	machine-checkable link from a capability bundle back to a specific commit in a
    86	specific source repository. GSD emits provenance for first-party capabilities
    87	in CI and recommends it for curated capabilities; whether to require it for
    88	community-listed third-party capabilities is an open question tied to whether
    89	GSD operates a central registry (see the PRD).
    90	
    91	### Obsidian: no sandbox, stated honestly
    92	
    93	Obsidian's plugin system does not sandbox plugins. Plugins run in the renderer
    94	process with full Electron API access. Obsidian acknowledges this directly in
    95	its documentation and community materials, and its response is restricted mode
    96	on by default — no community plugins run until the user deliberately disables
    97	restricted mode — plus a human-curated plugin directory that requires a
    98	maintainer review PR for each new plugin.
    99	
   100	GSD borrows two things from Obsidian. First, the honesty: **there is no
   101	sandbox**, and this document says so directly rather than implying one. Second,
   102	the principle that explicit opt-in per capability is better than a blanket "all
   103	community plugins are safe" message. GSD does not use restricted mode, but its
   104	consent gate at install serves the same function: executable surfaces are
   105	disclosed and consented to before they activate, not discovered after the fact.
   106	
   107	GSD does not borrow Obsidian's centralised review model. Requiring a
   108	maintainer-review PR for every third-party capability is the bottleneck that
   109	makes the Obsidian system painful for authors and creates a PR-queue burden
   110	for maintainers. GSD ships decentralised URL import precisely to avoid that.
   111	
   112	### Claude Code: trust prompt + marketplace
   113	
   114	Claude Code prompts the user at install for each extension that requires
   115	elevated trust, lists the permissions the extension requests, and maintains a
   116	`strictKnownMarketplaces` allowlist for managed environments where only
   117	reviewed sources are permitted. Claude Code's SHA-pinning mechanic (pinning to
   118	a specific version hash rather than floating on `latest`) is the direct model
   119	for GSD's integrity field.
   120	
   121	GSD mirrors the allowlist mechanic as `strictKnownRegistries`, and mirrors the
   122	SHA-pin as the `integrity` field in `capability.json` and the capability
   123	ledger.
   124	
   125	---
   126	
   127	## Each pillar and its reasoning
   128	
   129	### Install never runs code
   130	
   131	The most powerful thing GSD can say to a user about a third-party capability
   132	is: "downloading and staging this capability will not execute any of its code."
   133	That guarantee makes the consent step meaningful. If install could run code, a
   134	malicious capability could bypass consent entirely — the install step would be
   135	the attack.
   136	
   137	Staging is copy-only: files are extracted to the install root, the manifest is
   138	validated, cross-capability invariants are checked, and the ledger is written.
   139	No hook fires, no module is `require()`'d, no MCP server is started. The
   140	executable surfaces remain inert until the first loop event fires after
   141	consent.
   142	
   143	### Consent at install for executable surfaces
   144	
   145	Hooks fire on the *next tool call*. There is no first-use gate for a hook —
   146	the point at which a hook would fire for the first time is not a prompt
   147	opportunity; it is already inside a running tool invocation. This means the
   148	consent window is install, not first use.
   149	
   150	GSD presents a pre-install summary that names every executable surface the
   151	capability declares (hooks, MCP servers, command modules), their kinds (`step`,
   152	`contribution`, `gate`), and the loop extension points they register into. For
   153	each MCP server the summary also shows the `env` it would be spawned with (each
   154	key and its — truncated — value) and the `cwd` it would run in, because an
   155	environment variable can change *what* a command does (for example
   156	`NODE_OPTIONS=--require /tmp/evil.js`) without touching the command or its
   157	arguments. Declining aborts the install cleanly. Accepting records the consent
   158	in the user-owned consent store (see "The project-scope trust boundary"), bound
   159	to the bundle's integrity and a *disclosure signature* over the executable set
   160	(hooks, command modules, and each MCP server's command, argv, env, and cwd). The
   161	signature is a stable, key-order-independent encoding, so any later add or change
   162	to a surface — including an env or cwd change — deactivates the capability until
   163	the user re-consents, while a harmless key reorder does not.
   164	
   165	For non-executable surfaces (skills, agents, workflow files), the disclosure
   166	note explains what they do but consent is lighter — they do not execute code.
   167	
   168	### Integrity pinning
   169	
   170	An `integrity` field in `capability.json` carries a `sha512-<base64>` digest
   171	of the capability bundle. When present, GSD verifies this digest before
   172	extracting any files. A mismatch aborts the install.
   173	
   174	What integrity pinning defends against: a capability hosted at a URL or in a
   175	registry that is later replaced with a different bundle (whether by an attacker
   176	who has compromised the hosting, or by an author publishing a silent breaking
   177	change). The SHA is the commitment — "I consented to *this* bundle, not
   178	whatever is at this URL today."
   179	
   180	What it does not defend against: a malicious capability where the author
   181	themselves publishes a bad bundle. The SHA is honest about what you are
   182	installing; it says nothing about whether what you are installing is safe.
   183	
   184	It also pins **only the top-level bundle**, not an `npm`-sourced capability's
   185	resolved dependency graph. `--ignore-scripts` and copy-only staging stop
   186	install-time execution, but when a command module is later `require()`'d, Node
   187	resolves and runs its transitive dependencies — which the bundle SHA does not
   188	cover (the Wiz / VS Code lesson). For the `npm` source kind, a green integrity
   189	check means "the package tarball is the one you pinned," not "every line of code
   190	that will run is the code you reviewed." Authors who want a stronger guarantee
   191	should vendor their dependencies or ship a lockfile.
   192	
   193	### Auto-update off by default, re-consent on executable-set change
   194	
   195	When auto-update is enabled for a third-party capability, each update is
   196	checked against the ledger's record of the capability's executable surfaces. If
   197	the set of hooks, MCP servers, or command modules has changed — even if the
   198	update is otherwise benign — auto-update halts and re-prompts. The user is
   199	shown which surfaces were added or removed and must consent before the update
   200	applies.
   201	
   202	This directly addresses the VS Code stolen-PAT scenario: even if an attacker
   203	publishes a new version of a capability you have auto-update enabled on, the
   204	new version cannot silently gain a hook that the previous version did not have.
   205	
   206	### Install-root confinement
   207	
   208	A capability's command modules are `require()`'d only from the capability's own
   209	install root. Declared paths containing parent-directory traversal (`../`) are
   210	rejected at install-time validation. This prevents a capability from loading
   211	code it does not own — whether by accident or by design.
   212	
   213	### Reserved namespace
   214	
   215	The `gsd-`, `gsd-core-`, and `anthropic-` id prefixes are reserved for
   216	first-party use. A third-party capability that claims one of these prefixes is
   217	rejected at the conformance gate. This prevents impersonation: a malicious
   218	actor cannot publish a capability called `gsd-security` and exploit a user's
   219	implicit trust in the GSD namespace.
   220	
   221	### `capabilities.strict_known_registries` for managed environments
   222	
   223	Teams or enterprises that want to constrain which capability sources are
   224	permissible set `capabilities.strict_known_registries` in config. Its semantics:
   225	
   226	- **unset / `null`** *(default)* — permissive: external installs (git / npm /
   227	  tarball) are allowed, each still passing the consent + integrity gate. Local
   228	  filesystem installs are always allowed.
   229	- **`[]`** *(explicit empty array)* — lockdown: **all external installs are
   230	  blocked**; local-only.
   231	- **non-empty list** — a **host-based** allowlist: only sources whose host
   232	  matches an entry (exact host or a subdomain of it — `github.com` matches
   233	  `api.github.com` but never `evilgithub.com`; the literal token `npm` permits
   234	  the npm source kind). A malformed (non-array) value **fails closed**.
   235	
   236	This gives an administrator a policy lever that operates before the user even
   237	sees a consent prompt. The default is permissive-with-consent (not Obsidian-style
   238	restricted-by-default), because the epic deliberately chose decentralised import
   239	with the consent prompt as the default barrier and lockdown one config key away.
   240	
   241	### Command dispatch: where third-party code runs (1.6.0)
   242	
   243	A capability may declare a **command family** (`commands: [{ family, module,
   244	router }]`); `gsd-tools <family>` dispatches it by `require()`-ing the router.
   245	This is the one place a third-party capability's own code executes, so it is
   246	gated twice. **Consent:** a third-party family is dispatchable only if the
   247	capability is *active* under the activation gate below — for a project-scoped
   248	capability that means a **user consent record on this machine**, not merely a
   249	ledger entry. A bundle merely present on disk (or a project ledger that marks it
   250	committed) but with no on-this-machine consent record is **not** activated at
   251	all: no declarative surfaces, no command dispatch. **Confinement:** the router
   252	module loads only from the capability's own install root (bare-`.cjs` basename,
   253	`realpath`-confined, rejecting `..` traversal and symlink escape); a first-party
   254	command can never be shadowed by a third-party one.
   255	
   256	#### The project-scope trust boundary
   257	
   258	Capabilities install **globally** (`$GSD_HOME/.gsd/capabilities/`) or
   259	**project-scoped** (`<projectRoot>/.gsd/capabilities/`). The authoritative
   260	consent signal is **not** the in-repo ledger but a **user-owned consent store**
   261	that lives **outside any repository**, at
   262	`${GSD_HOME||homedir()}/.gsd/consent.json`. Each project-scope consent record is
   263	keyed by `(realpath(projectRoot), capability id)` and binds the bundle's
   264	`integrity` and its disclosure signature; GSD writes one only when *you* install
   265	or upgrade that project-scoped capability through the lifecycle on this machine,
   266	and removes it when you uninstall.
   267	
   268	Before activating a project-scoped overlay — for **both** its declarative loop
   269	surfaces (steps, gates, contributions, federated config) **and** its command
   270	dispatch — the loader requires a matching record in this store. With no match the
   271	capability is *discovered but inactive*: it shows up in `gsd capability list`
   272	with `status: inactive` and a reason, but contributes nothing and runs nothing.
   273	
   274	This closes the previous bypass: a repo you check out could ship a capability
   275	bundle *and* a project ledger that marked it committed, and that alone used to
   276	activate it. Now a forged or cloned project ledger activates **nothing** until
   277	you consent on this machine — and because the consent binds the integrity and
   278	the disclosure signature, tampering with the bundle (including changing an MCP
   279	server's `env` or `cwd`) deactivates it until you re-consent. A **global**
   280	install (under your own home) is trusted without a per-project record, as before.
   281	You can audit and revoke project consents with `gsd capability trust list` and
   282	`gsd capability trust revoke <id>`.
   283	
   284	---
   285	
   286	## The honest limitation: there is no sandbox
   287	
   288	GSD does not sandbox third-party capability code. The honest reason: Node-level
   289	sandboxing that meaningfully restricts a `require()`'d module — limiting
   290	filesystem access, network access, subprocess spawning — would require either
   291	a separate process with IPC overhead or a VM context that strips the Node
   292	globals capabilities legitimately need (filesystem for writing surface files,
   293	network for MCP, subprocess for hook shell commands). Full artifact parity and
   294	meaningful sandboxing are in tension. The maintainer chose full parity.
   295	
   296	What this means in practice: a third-party capability, once consented to and
   297	installed, runs with the same permissions GSD Core itself runs with. It is not
   298	isolated. A capability that wants to exfiltrate data, or modify files outside
   299	its declared scope, can — exactly as a malicious npm package can.
   300	

exec
/bin/zsh -lc "nl -ba '/Users/noelsaw/Documents/GH Repos/gsd-core/docs/explanation/capability-overlay-model.md' | sed -n '1,240p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
 succeeded in 0ms:
     1	# How overlay capabilities compose
     2	
     3	> **Explanation** — This document describes *why* GSD composes first-party and
     4	> third-party capabilities the way it does, and *what the precedence and conflict
     5	> rules are*. It is not a step-by-step guide; for the consumer lifecycle see
     6	> [Install your first capability](../tutorials/install-your-first-capability.md),
     7	> and for the field-level rules see the
     8	> [capability manifest reference](../reference/capability-manifest.md). For the
     9	> security side of the same boundary, see
    10	> [the capability trust model](capability-trust-model.md). For the decision
    11	> record, see
    12	> [ADR-1244 D2](../adr/1244-capability-ecosystem.md#d2--runtime-capability-registry-overlay).
    13	
    14	---
    15	
    16	## The central idea: the registry is a module, not a data file
    17	
    18	GSD's capabilities — first-party and third-party alike — are described by a single
    19	**capability registry**: a composed object that every consumer (the loop resolver,
    20	the config loader, the surface command, `gsd capability list`) reads to learn which
    21	skills, agents, config keys, and loop hooks exist.
    22	
    23	The first-party registry is *frozen and generated*: it is built at release time from
    24	the shipped `capabilities/*/capability.json` manifests into a committed
    25	`capability-registry.cjs`, and it never changes at runtime. Third-party capabilities
    26	cannot be baked into that file — they are installed on the user's machine, after the
    27	release. So the registry is not consumed as a static data file. It is consumed through
    28	a function:
    29	
    30	```text
    31	loadRegistry({ includeInstalled: true }) → composed registry
    32	```
    33	
    34	`loadRegistry` reads the frozen first-party registry and, when asked, composes a
    35	**validated installed overlay** on top of it: the third-party capability manifests
    36	found at runtime under the per-scope install roots. The result is one registry that
    37	covers first-party and third-party capabilities identically — every derived view
    38	(`bySkill`, `byAgent`, `byLoopPoint`, `configKeys`, the cluster map) spans both. The
    39	whole point of the overlay model is that an installed capability is *not* a
    40	second-class citizen: once it composes cleanly, it participates in the loop exactly
    41	as a shipped one does.
    42	
    43	The interesting question is everything that can go wrong while composing two sources
    44	that were authored independently — and what GSD does about each case. That is the rest
    45	of this document.
    46	
    47	---
    48	
    49	## The activation chain
    50	
    51	Before a third-party capability contributes anything to your loop, it passes through
    52	four distinct stages. They are worth naming because they fail in different ways and at
    53	different times — and the order matters: **the consent gate runs during composition,
    54	before surface and config**, not after them.
    55	
    56	1. **Install** writes the capability into a scope root and records it in the ledger.
    57	   This is the lifecycle's job; it never runs capability code (see the trust model).
    58	   The capability now exists *on disk*.
    59	2. **Load / compose (with the project-scope consent gate)** is what `loadRegistry`
    60	   does. As it composes each overlay it applies the composition gates — id/skill/agent/
    61	   config/family collisions, the `engines.gsd` re-check, and, for a *project-scoped*
    62	   overlay, **the project-scope consent gate**. That gate runs *inside* `loadRegistry`,
    63	   before any of the overlay's fragments are even materialised: a project overlay is
    64	   inert (discovered-but-inactive) until a matching record exists in your user-owned
    65	   consent store. This is the security gate described in
    66	   [the trust model](capability-trust-model.md#the-project-scope-trust-boundary). A
    67	   capability that fails any composition gate — consent included — never enters the
    68	   registry the rest of GSD reads, so it cannot reach the later stages at all.
    69	3. **Surface** decides which of the *composed* registry's skills are projected into the
    70	   host runtime. This is the install-profile and `/gsd:surface` layer — a capability's
    71	   skills can be on the surface or held back without uninstalling it. It only ever sees
    72	   capabilities that already cleared composition.
    73	4. **Config activation** decides, per loop hook, whether it fires. A hook's `when`
    74	   key (a dotted config key) gates it: a `step` or `gate` whose key is falsy does not
    75	   run. This is the `gsd capability set <id> --gate <key>=<bool>` and `/gsd:settings`
    76	   layer — again, only for capabilities that survived composition.
    77	
    78	This document is about what `loadRegistry` does at the moment of composition — stage 2,
    79	which sits between install and the later surface/config stages and contains the consent
    80	gate. A capability that is installed but skipped at composition (including for missing
    81	consent) never reaches the surface or config stages, because it is not in the registry
    82	the rest of GSD reads.
    83	
    84	---
    85	
    86	## Where overlays come from, and the order they are considered
    87	
    88	`loadRegistry` scans two install roots, in this order:
    89	
    90	- **Global** — `$GSD_HOME/.gsd/capabilities/<id>/` (where `GSD_HOME` defaults to your
    91	  home directory). This is under your own control and is trusted without a per-project
    92	  record.
    93	- **Project** — `<projectRoot>/.gsd/capabilities/<id>/`. This lives inside a repository
    94	  and is therefore only as trustworthy as the repository; it is gated by the consent
    95	  store.
    96	
    97	The roots are deduplicated by their *canonical* (symlink-resolved) physical path, so a
    98	single directory is never scanned twice — and, crucially, so a symlinked `GSD_HOME`
    99	that physically *is* the project root cannot smuggle an in-repo bundle into the trusted
   100	global slot. When the global and project roots resolve to the same physical directory
   101	(or distinctness cannot be proven), the surviving scope escalates to the more
   102	restrictive `project` — consent-required. This is a deliberately conservative choice:
   103	when GSD cannot prove a global root is distinct from your project tree, it treats it as
   104	project-scoped rather than risk granting trusted-global activation to repo-plantable
   105	content.
   106	
   107	Within this ordering, the composition rules below decide which overlays survive.
   108	
   109	---
   110	
   111	## First-party always wins
   112	
   113	The single load-bearing precedence rule is: **first-party always wins.** When a
   114	third-party overlay collides with a first-party capability, the overlay is rejected —
   115	never the other way round.
   116	
   117	Collision is defined broadly, because impersonation can happen along several axes. An
   118	overlay is rejected if it collides on any of:
   119	
   120	- **`id`** — the capability identifier. Two capabilities cannot share an id; a
   121	  first-party id always keeps it.
   122	- **A skill or agent stem** — exactly one capability may own each skill/agent stem
   123	  across the entire merged registry. An overlay that claims a stem already owned
   124	  (by first-party *or* by an already-accepted overlay) is rejected.
   125	- **A federated config key** — a key declared in the overlay's `config` slice that
   126	  already exists in the central config schema or in another capability's slice.
   127	- **A command family** — the `family` of a declared command module, if another
   128	  capability already owns it.
   129	
   130	Two further rules protect the first-party namespace directly:
   131	
   132	- **Reserved prefixes.** The `gsd-`, `gsd-core-`, and `anthropic-` id prefixes are
   133	  reserved. An overlay whose id begins with one is rejected outright — a third party
   134	  cannot publish `gsd-security` and borrow the implicit trust of the GSD namespace.
   135	- **Cross-capability invariants.** Each candidate overlay is added to the merged
   136	  capability map and the *full* cross-capability validation suite (contract roles,
   137	  `consumes`-satisfiability, owner uniqueness, config-key exclusivity, `requires`
   138	  acyclicity and tier-monotonicity) is re-run. First-party alone is always clean, so
   139	  any new error is provably the candidate's fault, and the candidate is dropped.
   140	
   141	### Why this asymmetry
   142	
   143	The asymmetry is intentional and follows directly from the trust model's central
   144	thesis — *artifact parity is not trust parity*. A third-party capability is allowed to
   145	ship the same kinds of artifacts as GSD Core, but first-party capabilities carry an
   146	authority third-party ones do not: their provenance is the GSD release process itself.
   147	If a collision could let an overlay shadow a first-party skill, agent, or command, then
   148	installing a capability could silently *replace* a shipped behaviour — the install would
   149	be the attack. By making first-party unconditionally win every collision, GSD
   150	guarantees that no installed capability can ever redefine what GSD Core does. An overlay
   151	can only *add*; it can never *override*.
   152	
   153	---
   154	
   155	## When a single overlay fails: skip, don't crash
   156	
   157	Overlays are untrusted, independently authored, and read at runtime from a possibly
   158	repo-plantable directory. A malformed one must never bring down the loop. So the second
   159	rule of composition is: **a bad overlay is skipped with a warning; the loop always gets
   160	a usable registry.**
   161	
   162	A capability is skipped (and a warning recorded in the registry's `_overlay.warnings`)
   163	for any of these reasons:
   164	
   165	- its `capability.json` is missing, unreadable, non-regular (a planted FIFO/device), or
   166	  oversized;
   167	- it fails structural or cross-capability validation;
   168	- it collides with first-party or an already-accepted overlay (the precedence rule
   169	  above);
   170	- its `engines.gsd` range does not satisfy the running GSD version (the load-time
   171	  re-gate, which mirrors the install-time gate so an upgrade of GSD itself can retire an
   172	  incompatible overlay);
   173	- it carries an in-flight `_pending` install/upgrade marker (deferred until
   174	  reconciliation completes);
   175	- (for a project overlay) it has no matching consent record on this machine — it is
   176	  *discovered but inactive*.
   177	
   178	The composition body is total: even an unexpected throw from a validator or a
   179	fragment-materialisation step is caught per-candidate, turned into a skip, and the next
   180	candidate is processed. A single broken overlay cannot poison the rest of the set.
   181	
   182	---
   183	
   184	## The one place where skipping is dangerous: gates
   185	
   186	Skipping a broken overlay is the safe default for most surfaces — but not for *gates*.
   187	
   188	A capability's loop hooks come in three kinds:
   189	
   190	- a **step** adds an independent unit of work at an extension point;
   191	- a **contribution** injects a prompt fragment into an agent role;
   192	- a **gate** checks a condition and can *block* the loop from proceeding.
   193	
   194	For steps and contributions, skipping a capability means the loop simply proceeds
   195	**without** that addition. That is *fail-open*, and it is correct: the loop is missing an
   196	optional step, not doing something unsafe.
   197	
   198	A gate is the opposite. The whole purpose of a gate is to *stop* the loop when a
   199	condition is not met — a deploy gate, a house-style verification gate, a safety check. If
   200	GSD skipped a broken gate-declaring capability and proceeded, it would behave exactly as
   201	if the gate had *passed* — silently waving through the very thing the gate existed to
   202	block. That is a fail-open on a security-relevant control, and it is unacceptable.
   203	
   204	So composition treats gates asymmetrically from steps and contributions. When a
   205	capability that declares a gate is skipped, GSD records its gate points in
   206	`_overlay.incompatibleGateCapIds` and `_overlay.blockedGates`, and the loop resolver
   207	**injects a synthetic blocking gate** at each of those extension points. The loop
   208	**fails closed**: rather than proceed as if the gate passed, it halts with a message
   209	naming the skipped capability and why its gate could not be evaluated.
   210	
   211	The discriminator is therefore *not* "is this overlay broken?" but "what does failing
   212	to load it mean?" — and for a gate, failing to load it means you must not proceed.
   213	
   214	---
   215	
   216	## When the whole compose fails: fall back to first-party
   217	
   218	There is one more failure layer above the per-candidate skip. A set of overlays can
   219	each pass every per-candidate check yet still trip a stricter whole-set check when the
   220	canonical builder (`buildRegistry`) materialises the merged registry — a topological
   221	cycle that only appears across the combined set, a config-slice shape problem, a format
   222	mismatch. An unguarded failure there would crash every consumer of the registry.
   223	
   224	The fallback is uncompromising: if the whole-set build fails, GSD **discards every
   225	overlay** and returns the frozen first-party registry, plus a warning recording why. The
   226	loop keeps running with exactly the shipped capabilities and none of the overlays. Two
   227	details make this safe rather than merely convenient:
   228	
   229	- Every accepted overlay's **command root is cleared**, so no dropped overlay can leave
   230	  behind a path that a runtime dispatcher might `require()` a command module from.
   231	- Every dropped overlay's **gates are recorded as blocked** — using the same extraction
   232	  as the per-candidate path — so a gate-declaring overlay that vanishes in the fallback
   233	  still **fails closed**, never open.
   234	
   235	The principle is the same at every layer: when GSD cannot compose an overlay, it removes
   236	the overlay's *additions* but never weakens a *control*.
   237	
   238	---
   239	
   240	## Why compose through one builder

exec
/bin/zsh -lc "nl -ba '/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/claude/capability.json' | sed -n '1,220p' && printf '\\n' && nl -ba '/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/codex/capability.json' | sed -n '1,220p' && printf '\\n' && nl -ba '/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/research/capability.json' | sed -n '1,220p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
 succeeded in 0ms:
     1	{
     2	  "id": "claude",
     3	  "role": "runtime",
     4	  "version": "1.7.0-rc.2",
     5	  "title": "Claude Code",
     6	  "description": "Anthropic Claude Code — primary development runtime; tier-1 support with full hook surface and skills-based global install.",
     7	  "tier": "core",
     8	  "requires": [],
     9	  "engines": {
    10	    "gsd": ">=1.6.0"
    11	  },
    12	  "runtime": {
    13	    "configHome": {
    14	      "kind": "dot-home",
    15	      "name": ".claude",
    16	      "env": [
    17	        "CLAUDE_CONFIG_DIR"
    18	      ]
    19	    },
    20	    "localConfigDir": ".claude",
    21	    "configFormat": "settings-json",
    22	    "artifactLayout": {
    23	      "global": [
    24	        {
    25	          "kind": "skills",
    26	          "destSubpath": "skills",
    27	          "prefix": "gsd-",
    28	          "nesting": "flat",
    29	          "recursive": false,
    30	          "converter": "convertClaudeCommandToClaudeSkill"
    31	        }
    32	      ],
    33	      "local": [
    34	        {
    35	          "kind": "commands",
    36	          "destSubpath": "commands",
    37	          "prefix": "gsd-",
    38	          "nesting": "flat",
    39	          "recursive": false,
    40	          "converter": null
    41	        },
    42	        {
    43	          "kind": "agents",
    44	          "destSubpath": "agents",
    45	          "prefix": "gsd-",
    46	          "nesting": "flat",
    47	          "recursive": false,
    48	          "converter": null
    49	        }
    50	      ]
    51	    },
    52	    "commandStyle": "slash-hyphen",
    53	    "hooksSurface": "settings-json",
    54	    "hookEvents": "claude",
    55	    "sandboxTier": "none",
    56	    "supportTier": 1,
    57	    "installSurface": "settings-json",
    58	    "writesSharedSettings": true,
    59	    "permissionWriter": null,
    60	    "extendedHookEvents": [
    61	      "SubagentStop",
    62	      "Stop",
    63	      "PreCompact",
    64	      "FileChanged"
    65	    ],
    66	    "hostIntegration": {
    67	      "embeddingMode": "imperative",
    68	      "commandSurface": "slash-file",
    69	      "dispatch": {
    70	        "namedDispatch": true,
    71	        "nested": true,
    72	        "maxDepth": 5,
    73	        "background": true,
    74	        "subagentToolkit": "full",
    75	        "backgroundDispatch": false
    76	      },
    77	      "modelMode": "passive",
    78	      "hookBus": "host",
    79	      "stateIO": "filesystem",
    80	      "transport": "mcp",
    81	      "runtime": "node"
    82	    }
    83	  }
    84	}

     1	{
     2	  "id": "codex",
     3	  "role": "runtime",
     4	  "version": "1.7.0-rc.2",
     5	  "title": "OpenAI Codex CLI",
     6	  "description": "OpenAI Codex CLI — shell-var command style; per-agent sandbox tiers; config.toml + hooks.json hook surface; tier-1 support.",
     7	  "tier": "core",
     8	  "requires": [],
     9	  "engines": {
    10	    "gsd": ">=1.6.0"
    11	  },
    12	  "runtime": {
    13	    "configHome": {
    14	      "kind": "dot-home",
    15	      "name": ".codex",
    16	      "env": [
    17	        "CODEX_HOME"
    18	      ]
    19	    },
    20	    "localConfigDir": ".codex",
    21	    "configFormat": "toml",
    22	    "artifactLayout": {
    23	      "global": [
    24	        {
    25	          "kind": "skills",
    26	          "destSubpath": "skills",
    27	          "prefix": "gsd-",
    28	          "nesting": "flat",
    29	          "recursive": false,
    30	          "converter": "convertClaudeCommandToCodexSkill"
    31	        }
    32	      ],
    33	      "local": [
    34	        {
    35	          "kind": "skills",
    36	          "destSubpath": "skills",
    37	          "prefix": "gsd-",
    38	          "nesting": "flat",
    39	          "recursive": false,
    40	          "converter": "convertClaudeCommandToCodexSkill"
    41	        }
    42	      ]
    43	    },
    44	    "commandStyle": "shell-var",
    45	    "hooksSurface": "codex-hooks-json",
    46	    "hookEvents": "claude",
    47	    "sandboxTier": "codex-agent-sandbox",
    48	    "supportTier": 1,
    49	    "installSurface": "codex-toml",
    50	    "writesSharedSettings": false,
    51	    "permissionWriter": null,
    52	    "extendedHookEvents": [],
    53	    "hostIntegration": {
    54	      "embeddingMode": "declarative",
    55	      "commandSurface": "slash-file",
    56	      "dispatch": {
    57	        "namedDispatch": true,
    58	        "nested": true,
    59	        "maxDepth": 1,
    60	        "background": true,
    61	        "subagentToolkit": "full",
    62	        "backgroundDispatch": true
    63	      },
    64	      "modelMode": "passive",
    65	      "hookBus": "host",
    66	      "stateIO": "filesystem",
    67	      "transport": "mcp",
    68	      "runtime": "node"
    69	    }
    70	  }
    71	}

     1	{
     2	  "id": "research",
     3	  "role": "feature",
     4	  "version": "1.7.0-rc.2",
     5	  "title": "Phase research",
     6	  "description": "Optional phase research before planning; owns the phase researcher agent and workflow.research activation key.",
     7	  "tier": "standard",
     8	  "requires": [],
     9	  "engines": {
    10	    "gsd": ">=1.6.0"
    11	  },
    12	  "runtimeCompat": {
    13	    "supported": [
    14	      "*"
    15	    ],
    16	    "unsupported": []
    17	  },
    18	  "skills": [],
    19	  "agents": [
    20	    "gsd-phase-researcher"
    21	  ],
    22	  "hooks": [],
    23	  "config": {
    24	    "workflow.research": {
    25	      "type": "boolean",
    26	      "default": true,
    27	      "description": "Run phase research before planning when research artifacts are missing or explicitly refreshed."
    28	    }
    29	  },
    30	  "steps": [
    31	    {
    32	      "point": "plan:pre",
    33	      "ref": {
    34	        "agent": "gsd-phase-researcher"
    35	      },
    36	      "fragment": {
    37	        "path": "fragments/plan-pre.md"
    38	      },
    39	      "produces": [
    40	        "RESEARCH.md"
    41	      ],
    42	      "consumes": [
    43	        "CONTEXT.md"
    44	      ],
    45	      "when": "workflow.research",
    46	      "onError": "skip"
    47	    }
    48	  ],
    49	  "contributions": [],
    50	  "gates": []
    51	}

exec
/bin/zsh -lc "nl -ba '/Users/noelsaw/Documents/GH Repos/gsd-core/docs/how-to/install-on-your-runtime.md' | sed -n '1,220p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
 succeeded in 0ms:
     1	# How to install GSD Core on your runtime
     2	
     3	Install GSD Core (`@opengsd/gsd-core`) into the AI coding runtime you use every day. This guide gives you the standard installer path for each supported runtime, then covers the manual path for machines without Node.js.
     4	
     5	**What you need:** Node.js 18+ and npm (or npx). If you do not have Node.js, jump to [Installing without Node.js](#installing-without-nodejs).
     6	
     7	---
     8	
     9	## Why the installer is required
    10	
    11	GSD Core ships agent and command files in Claude Code's native frontmatter format. Each supported runtime expects a different schema, directory layout, and command-invocation syntax. The installer performs the necessary transformations — for example, converting tool lists and colour values for OpenCode, writing TOML agent entries for Codex, and rewriting every command body from hyphen form (`/gsd-update`) to colon form (`/gsd:update`) for Gemini CLI.
    12	
    13	**Do not copy files from `agents/` or `commands/` directly.** Doing so bypasses the transformations and produces schema-validation errors or missing commands.
    14	
    15	---
    16	
    17	## Standard install
    18	
    19	Run the installer from any directory. It prompts for your runtime and whether to install globally (all projects) or locally (this project only).
    20	
    21	```bash
    22	npx @opengsd/gsd-core@latest
    23	```
    24	
    25	That is the only command you need for a fresh install or to re-run the installer after switching runtimes.
    26	
    27	---
    28	
    29	## Per-runtime instructions
    30	
    31	### Claude Code
    32	
    33	```bash
    34	npx @opengsd/gsd-core@latest --claude --global
    35	```
    36	
    37	Skills land in `~/.claude/`. Commands appear as `/gsd-*` slash commands in your next Claude Code session. Restart Claude Code to pick them up.
    38	
    39	**Override the install directory:**
    40	
    41	```bash
    42	CLAUDE_CONFIG_DIR=~/.claude-alt npx @opengsd/gsd-core@latest --claude --global
    43	```
    44	
    45	**Hook coverage**
    46	
    47	GSD registers the following Claude Code hook events automatically on install:
    48	
    49	| Event | Hook | Purpose |
    50	|---|---|---|
    51	| `SessionStart` | `gsd-check-update.js`, `gsd-session-state.sh` | Update check, session orientation |
    52	| `PostToolUse` | `gsd-context-monitor.js`, `gsd-read-injection-scanner.js`, `gsd-phase-boundary.sh`, `gsd-graphify-update.sh` | Context monitoring, read-time scan, phase boundary detection |
    53	| `PreToolUse` | `gsd-prompt-guard.js`, `gsd-read-guard.js`, `gsd-workflow-guard.js`, `gsd-worktree-path-guard.js`, `gsd-validate-commit.sh` | Prompt guard, read-before-edit, workflow + worktree safety, commit validation |
    54	| `SubagentStop` | `gsd-context-monitor.js` | Context headroom tracking after subagent completion |
    55	| `Stop` | `gsd-context-monitor.js` | Context headroom tracking before model stop |
    56	| `PreCompact` | `gsd-context-monitor.js` | Context awareness before conversation compaction |
    57	| `FileChanged` (matcher: `config.json`) | `gsd-config-reload.js` | Hot-reloads `.planning/config.json` context mid-session when you edit your GSD config — no session restart required |
    58	
    59	The `FileChanged` hook is always-on and a no-op when `.planning/config.json` does not exist in the project. Editing that file while a session is running injects an `additionalContext` summary of the new configuration so the agent picks up model overrides, workflow toggles, and hook settings immediately.
    60	
    61	---
    62	
    63	### Claude Code — native plugin install
    64	
    65	GSD Core ships a `.claude-plugin/plugin.json` manifest, which enables installation and lifecycle management through the Claude Code plugin system. This path is **additive** — the npm installer above remains fully supported, and the two approaches differ in namespace and lifecycle only.
    66	
    67	**Install paths**
    68	
    69	*Option A — marketplace or git install (once listed):*
    70	
    71	```bash
    72	claude plugin install gsd-core
    73	```
    74	
    75	*Option B — zero-friction skills-dir load:* Claude Code automatically discovers any directory under `~/.claude/skills/` that contains a `.claude-plugin/plugin.json` as a plugin. To use gsd-core this way, place (or symlink) the gsd-core package directory there:
    76	
    77	```bash
    78	# Example: place the package under ~/.claude/skills/gsd-core/
    79	# Claude Code loads it as gsd-core@skills-dir on the next session start.
    80	# No explicit install step required.
    81	```
    82	
    83	**Command namespace**
    84	
    85	Plugin commands are namespaced as `/gsd-core:<command>` — for example, `/gsd-core:plan-phase`. This is distinct from the classic npm/file-copy installer, which exposes commands as `/gsd:<command>`. Use whichever namespace corresponds to your install method.
    86	
    87	**Lifecycle**
    88	
    89	```bash
    90	claude plugin enable gsd-core
    91	claude plugin disable gsd-core
    92	claude plugin update gsd-core
    93	```
    94	
    95	**Hooks**
    96	
    97	The plugin wires gsd-core's always-on guard and update hooks automatically via `hooks/hooks.json`. No manual hook registration is required.
    98	
    99	**Prerequisites**
   100	
   101	The `gsd-tools` binary (installed as part of the `@opengsd/gsd-core` npm package) must be available on your `PATH` for gsd commands to execute their backing logic. The plugin delivers the command, agent, and hook surface; the npm package delivers the runtime CLI.
   102	
   103	Node.js (`node`) must also be available on your `PATH`. The plugin's always-on guard hooks (wired in `hooks/hooks.json`) are invoked as `node "${CLAUDE_PLUGIN_ROOT}/hooks/<script>"`. Some Claude Code distributions ship as a standalone binary and do not expose a `node` executable on `PATH`; in those environments the plugin's hooks will not run. Verify with `node --version` before relying on the plugin hooks.
   104	
   105	#### Claude plugin marketplace discovery (ZCODE and compatible runtimes)
   106	
   107	GSD Core also ships a `.claude-plugin/marketplace.json` marketplace manifest (sibling to `plugin.json`). Runtimes that implement the Claude plugin marketplace contract — such as ZCODE — can discover and install GSD Core from a custom marketplace source without a manual clone:
   108	
   109	1. In your runtime's plugin UI, add a custom marketplace source pointing at `open-gsd/gsd-core` (GitHub `owner/repo` form).
   110	2. GSD Core appears in the catalog and can be installed directly from the UI.
   111	
   112	This path is **additive** and changes nothing about the Claude Code plugin install above (`.claude-plugin/plugin.json` is unchanged). The marketplace entry's `source` is `./`, so it reuses `plugin.json`'s `commands` / `skills` / `hooks` mapping. The catalog version tracks `package.json` (it lives at `plugins[0].version` and is stamped by the release version-sync), so the version you see in the marketplace matches the npm release.
   113	
   114	---
   115	
   116	### Gemini CLI
   117	
   118	```bash
   119	npx @opengsd/gsd-core@latest --gemini --global
   120	```
   121	
   122	Skills land in `~/.gemini/`. The installer rewrites all command bodies to Gemini's colon namespace (`/gsd:update`, `/gsd:config`, etc.). Restart Gemini CLI after install.
   123	
   124	The installer also enriches the generated TOML commands with two native Gemini custom-command features:
   125	
   126	- **`{{args}}` interpolation** — every command that references arguments inline is emitted with Gemini's `{{args}}` placeholder (translated from Claude's `$ARGUMENTS`), so flags and free-text you type after the command name are interpolated into the prompt body rather than ignored.
   127	- **`!{...}` live-state injection** — `/gsd:progress` injects the current contents of `.planning/STATE.md` via a fixed `!{cat .planning/STATE.md 2>/dev/null}` shell block, giving Gemini live project state without relying on session memory. The shell block contains no interpolated input, so there is no injection risk; Gemini still shows its standard confirmation dialog the first time the command runs in a session.
   128	
   129	**Override the install directory:**
   130	
   131	```bash
   132	GEMINI_CONFIG_DIR=~/.gemini-alt npx @opengsd/gsd-core@latest --gemini --global
   133	```
   134	
   135	**Hook coverage**
   136	
   137	GSD registers the following hook events automatically on install:
   138	
   139	| Event | Hook | Purpose |
   140	|---|---|---|
   141	| `SessionStart` | `gsd-check-update.js`, `gsd-session-state.sh` | Update check, session orientation |
   142	| `BeforeTool` | `gsd-prompt-guard.js`, `gsd-read-guard.js`, `gsd-workflow-guard.js`, `gsd-worktree-path-guard.js`, `gsd-validate-commit.sh` | Prompt guard, read-before-edit, workflow + worktree safety, commit validation |
   143	| `AfterTool` | `gsd-context-monitor.js`, `gsd-read-injection-scanner.js`, `gsd-phase-boundary.sh`, `gsd-graphify-update.sh` | Context monitoring, read-time scan, phase boundary detection |
   144	| `BeforeAgent` | `gsd-context-monitor.js` | Context headroom awareness before the agent begins planning each prompt |
   145	| `AfterAgent` | `gsd-context-monitor.js` | Context headroom tracking after each agent turn's final response |
   146	| `BeforeModel` | `gsd-context-monitor.js` | Per-turn context injection before each LLM call |
   147	
   148	> **`hooksConfig.enabled: false` warning.** If your Gemini `settings.json` contains `hooksConfig.enabled: false`, the Gemini CLI silently disables all hook execution — GSD hooks are registered but will never run. The installer detects this and emits a warning. To enable hooks, set `hooksConfig.enabled: true` in `~/.gemini/settings.json` (or the directory matching your `GEMINI_CONFIG_DIR`).
   149	
   150	---
   151	
   152	### Gemini CLI — native extension install (#775)
   153	
   154	GSD also ships a `gemini-extension.json` extension manifest, so you can manage GSD through Gemini's own extension lifecycle and see it in `gemini extensions list`:
   155	
   156	```bash
   157	gemini extensions install https://github.com/open-gsd/gsd-core   # install
   158	gemini extensions update gsd-core                                # update
   159	gemini extensions uninstall gsd-core                             # remove
   160	gemini extensions link /path/to/gsd-core                         # dev: symlink a checkout
   161	```
   162	
   163	The extension loads GSD's operating context (`GEMINI.md`) into every session and gives you the discoverable install/update/remove lifecycle. The `/gsd:*` slash commands, agents, and hooks are installed separately by `npx @opengsd/gsd-core --gemini --global` (above). The two paths are complementary and additive — neither replaces the other, and slash-command projection into the extension is a planned follow-up.
   164	
   165	---
   166	
   167	### OpenCode
   168	
   169	```bash
   170	npx @opengsd/gsd-core@latest --opencode --global
   171	```
   172	
   173	The installer writes four surfaces under `~/.config/opencode/` (XDG) or `~/.opencode/`: flat slash commands in `command/`, file-based subagents in `agents/`, on-demand skills in `skills/<name>/SKILL.md`, and a native plugin in `plugins/gsd-core.js`. It converts agent frontmatter to OpenCode's schema — removing the `tools:` field and converting colour values to hex — and emits each skill with spec-compliant frontmatter (`name` matching the skill directory plus a `description`). Skills are loaded on demand via OpenCode's native skill tool; commands remain invokable as `/gsd-*`. See [Installing without Node.js — OpenCode transformations](#opencode--required-transformations) if you need to understand what changes.
   174	
   175	**GSD safety hooks on OpenCode.** OpenCode does not register lifecycle hooks the way Claude Code does (its `hooksSurface` is `none`), so GSD's prompt-injection guard, read-before-edit guard, injection scanner, and context monitor would otherwise be inert. The bundled plugin (`plugins/gsd-core.js`) closes that gap: OpenCode auto-discovers `plugins/*.{ts,js}` files under its config directory at startup and the adapter bridges OpenCode's event bus (`tool.execute.before`/`after`, `session.created`, `file.edited`) onto GSD's existing hook scripts, spawning them as subprocesses. No `opencode.json` entry is needed — the plugin is loaded by directory auto-discovery (the config `plugin` array is for npm packages only). A blocking hook aborts the tool call; an advisory hook surfaces its message without blocking.
   176	
   177	**Override the install directory:**
   178	
   179	```bash
   180	OPENCODE_CONFIG_DIR=~/.config/opencode-alt npx @opengsd/gsd-core@latest --opencode --global
   181	```
   182	
   183	---
   184	
   185	### Kilo
   186	
   187	```bash
   188	npx @opengsd/gsd-core@latest --kilo --global
   189	```
   190	
   191	The installer writes the same three surfaces under `~/.config/kilo/` (XDG) or `~/.kilo/` as for OpenCode — flat commands in `command/`, subagents in `agents/`, and skills in `skills/<name>/SKILL.md` — since Kilo derives from OpenCode and shares its config schema and skill layout.
   192	
   193	**Override the install directory:**
   194	
   195	```bash
   196	KILO_CONFIG_DIR=~/.config/kilo-alt npx @opengsd/gsd-core@latest --kilo --global
   197	```
   198	
   199	---
   200	
   201	### Codex
   202	
   203	```bash
   204	npx @opengsd/gsd-core@latest --codex --global
   205	```
   206	
   207	Skills land in `~/.codex/skills/gsd-*/SKILL.md`. Agents are written with per-agent TOML entries in `config.toml`. Restart Codex (or run `codex --reload`) after install.
   208	
   209	**Minimum supported version:** Codex CLI 0.130.0. Earlier versions had additional skill-root scanning that can produce duplicate listings.
   210	
   211	**Hook coverage**
   212	
   213	GSD registers the following Codex hook events automatically on install (requires Codex CLI 0.137.0+ for the stable hook-event schema):
   214	
   215	| Event | Hook | Purpose |
   216	|---|---|---|
   217	| `SessionStart` | `gsd-check-update.js` | Update check at session open; Windows installs also emit a `commandWindows` field pointing to the `.cmd` shim so Codex picks the correct executor on Windows without requiring per-OS config regeneration |
   218	| `SubagentStart` | `gsd-context-monitor.js` | Inject context / GSD_AGENT_NAME awareness at subagent open |
   219	| `Stop` | `gsd-context-monitor.js` | Context headroom tracking before model stop |
   220	| `PostToolUse` | `gsd-context-monitor.js` | Mirror the context-monitor coverage available in Claude Code |

codex
The gsd side is clear: it has an actual projected architecture with runtime descriptors, overlay composition, and host hook registration. I’m checking one last thing on our side now: whether the current skill catalog has any centralized discoverability or validation story beyond “flat files in skill dirs.”
exec
/bin/zsh -lc "find '/Users/noelsaw/.claude/skills' -maxdepth 2 \\( -type f -o -type l \\) | sort | sed -n '1,220p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
 succeeded in 0ms:
/Users/noelsaw/.claude/skills/auto-improve
/Users/noelsaw/.claude/skills/baseline-spec
/Users/noelsaw/.claude/skills/blast-radius
/Users/noelsaw/.claude/skills/bottom-line
/Users/noelsaw/.claude/skills/codebase-memory/SKILL.md
/Users/noelsaw/.claude/skills/consult
/Users/noelsaw/.claude/skills/debug-mantra
/Users/noelsaw/.claude/skills/front-door/SKILL.md
/Users/noelsaw/.claude/skills/giantbrains
/Users/noelsaw/.claude/skills/github-auth-debug
/Users/noelsaw/.claude/skills/graphify/.graphify_version
/Users/noelsaw/.claude/skills/graphify/SKILL.md
/Users/noelsaw/.claude/skills/honest
/Users/noelsaw/.claude/skills/iron-triangle
/Users/noelsaw/.claude/skills/linear
/Users/noelsaw/.claude/skills/loose-ends
/Users/noelsaw/.claude/skills/pdda/SKILL.md
/Users/noelsaw/.claude/skills/phase-qa
/Users/noelsaw/.claude/skills/ponytail/SKILL.md
/Users/noelsaw/.claude/skills/rabbit-hole
/Users/noelsaw/.claude/skills/read-only
/Users/noelsaw/.claude/skills/readme-audit
/Users/noelsaw/.claude/skills/record-decision
/Users/noelsaw/.claude/skills/relay
/Users/noelsaw/.claude/skills/relay-to-issue
/Users/noelsaw/.claude/skills/relay-xyz
/Users/noelsaw/.claude/skills/rpr
/Users/noelsaw/.claude/skills/shakedown
/Users/noelsaw/.claude/skills/snapshot
/Users/noelsaw/.claude/skills/spike-360
/Users/noelsaw/.claude/skills/swe
/Users/noelsaw/.claude/skills/take-a-step-back
/Users/noelsaw/.claude/skills/vscode-color
/Users/noelsaw/.claude/skills/worth-it
/Users/noelsaw/.claude/skills/wpcc
/Users/noelsaw/.claude/skills/xyz/SKILL.md

exec
/bin/zsh -lc "find '/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills' -maxdepth 2 -type f | sort | sed -n '1,220p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
 succeeded in 0ms:
/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/.DS_Store
/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/.claude/settings.json
/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/.claude/settings.local.json
/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/.git/COMMIT_EDITMSG
/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/.git/FETCH_HEAD
/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/.git/HEAD
/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/.git/ORIG_HEAD
/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/.git/config
/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/.git/description
/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/.git/index
/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/.git/packed-refs
/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/.gitignore
/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/.vscode/settings.json
/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/AGENTS.md
/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/CHANGELOG.md
/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/CLAUDE.md
/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/LICENSE
/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/README.md
/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/giantbrains/SKILL.md
/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/relay-system/from-codex.md
/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/snapshot.md
/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/utils/.DS_Store
/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/utils/README.md

exec
/bin/zsh -lc "nl -ba '/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/skills/xyz/SKILL.md' | sed -n '1,220p' && printf '\\n' && nl -ba '/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/hooks/relay-xyz-guard.sh' | sed -n '1,220p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
 succeeded in 0ms:
     1	---
     2	name: xyz
     3	description: >-
     4	  Coordinate two (or more) AI coding agents working CONCURRENTLY on
     5	  non-overlapping, path-scoped lanes of ONE shared repo, via the `tick` CLI —
     6	  for parallel builds and parallel codebase recon, with collision-free claims,
     7	  liveness heartbeats, and an honest concurrency metric. Use when the user wants
     8	  to "run two agents in parallel", "split this build across agents", "have
     9	  agents recon/profile the codebase concurrently", or "coordinate Codex +
    10	  Gemini on the same repo". NOT for work that touches shared files, needs
    11	  constant cross-agent handoff, or runs across separate clones / async sessions.
    12	---
    13	
    14	# xyz — multi-agent coordination via `tick`
    15	
    16	> **Working name `xyz`** — rename freely; nothing depends on the name.
    17	> Distilled from the "Trinity" experiment (Runs 1–3). This skill packages the
    18	> `tick` event-log coordination CLI plus two operating modes and the
    19	> anti-assumption discipline that keeps parallel agents from corrupting each
    20	> other's work or hallucinating about the code.
    21	
    22	## 1. What this is
    23	
    24	`tick` is a tiny, dependency-free Node CLI backed by an append-only event log in
    25	`.tick/events/` (one JSON object per `.jsonl` file). Agents coordinate by
    26	**claiming** path-scoped lanes before they edit, working, **heartbeating** while
    27	they work, and marking **done** — so two agents build different halves of one
    28	repo at once without colliding. A coordinator (you) seeds tasks, observes, and
    29	scores the run. There is **no server and no git transport** — just a shared
    30	local directory both agents can read and append.
    31	
    32	Core verbs: `take` (atomic claim of the next available lane), `ping` (liveness
    33	heartbeat), `done` / `release` / `break` / `scope`, `analyze` (metrics +
    34	parked-claim detection), `project` / `info` (read state).
    35	
    36	## 2. Scope — what this IS for
    37	
    38	Use `xyz` only when ALL of these hold:
    39	
    40	- **Partitionable into non-overlapping path globs.** Each task owns a lane
    41	  (e.g. `src/http/**` vs `src/store/**`). Agents never touch each other's lane.
    42	- **Shared working tree, single session.** Both agents operate on ONE checkout
    43	  with ONE `.tick/` directory, at the same time. (The atomic-claim guarantee is
    44	  specific to a shared lock + shared event dir — see Limits.)
    45	- **Balanced lanes.** Lanes should take comparable effort. (Run 3 lesson: an
    46	  imbalanced split lets the faster agent finish and idle, which sinks the
    47	  sustained-concurrency metric even on a flawless run.)
    48	- **Independent tasks with their own acceptance check** (a test, a build, a
    49	  lint). No shared mutable files (e.g. a single `package.json`/lockfile).
    50	
    51	## 2a. Scope — what this is NOT for
    52	
    53	- Tasks that edit the **same files** or a shared lockfile → guaranteed collisions.
    54	- **Separate clones / distributed / async or overnight** work → the soft-mutex
    55	  reopens; the metric becomes uninterpretable. Same-session, shared-tree only.
    56	- **Tightly-coupled** work needing constant back-and-forth handoff.
    57	- **>2 agents** — the cap and tie-breaks exist but are unvalidated at scale.
    58	- Anything where you can't write a per-task acceptance check.
    59	
    60	If the work doesn't partition into clean lanes, stop — this is the wrong tool.
    61	
    62	## 3. Anti-assumption discipline (the xyz mantra)
    63	
    64	Parallel agents fail in two ways: they **collide** (edit outside their lane) or
    65	they **hallucinate** (assert things about code they didn't verify). Both are
    66	assumption failures. Adapted from the `debug-mantra` skill, every agent prompt
    67	opens with this block, recited verbatim before acting:
    68	
    69	```
    70	XYZ MANTRA — recite before every action
    71	1. VERIFY, DON'T ASSUME.  Run `tick info <TASK-ID>` to confirm your lane's
    72	   exact paths. Never infer paths, file locations, or task scope from memory.
    73	2. TRACE THE REAL PATH.  Every claim about the code cites file:line you have
    74	   actually read. Filenames and intuition are not evidence.
    75	3. FALSIFY YOUR HYPOTHESIS.  State each assumption and try to DISPROVE it
    76	   against the source before recording it as fact. Default to "unverified".
    77	4. STAY IN YOUR LANE / CODE TO THE CONTRACT.  Never read the other agent's
    78	   source to guess an interface — code against the declared contract. If
    79	   evidence conflicts, FLAG it; do not paper over it.
    80	```
    81	
    82	The coordinator enforces it: any finding without a `file:line` citation, or any
    83	edit outside a claimed lane, is rejected in the wrap-up.
    84	
    85	## 4. Install (self-extracting)
    86	
    87	Copy the block below into `install.sh` and run `bash install.sh [DIR]`
    88	(default `DIR=xyz-tick`). It materializes the `tick` runtime. Then point
    89	`tick` at the repo you're coordinating via `TICK_REPO_ROOT` (or run it from
    90	inside that repo — it uses `git rev-parse --show-toplevel`).
    91	
    92	> This block embeds the **runtime** (CLI + engine). The **test suite**
    93	> (`validate.sh` + `test/`) is in the companion block §4b "Install — test suite";
    94	> run `bash validate.sh` after extracting both → **12/12** confirms the extract
    95	> is byte-exact.
    96	
    97	```bash
    98	#!/usr/bin/env bash
    99	# xyz / tick — self-extracting runtime installer
   100	set -euo pipefail
   101	DIR="${1:-xyz-tick}"
   102	mkdir -p "$DIR/bin" "$DIR/src"
   103	
   104	cat > "$DIR/bin/tick" <<'===XYZ_FILE==='
   105	#!/usr/bin/env node
   106	'use strict';
   107	
   108	const fs = require('fs');
   109	const path = require('path');
   110	const { execFileSync } = require('child_process');
   111	
   112	const { appendEvent, ensureEventsDir, EVENT_TYPES } = require('../src/events');
   113	const { project, fold } = require('../src/project');
   114	const { claim } = require('../src/claim');
   115	const { scope, release, circuitBreak, done, reap, heartbeat } = require('../src/scope');
   116	const { next } = require('../src/next');
   117	const { take } = require('../src/take');
   118	const { analyze, renderHuman, renderMd } = require('../src/analyze');
   119	const { gitUserName } = require('../src/identity');
   120	
   121	function repoRoot() {
   122	  if (process.env.TICK_REPO_ROOT) return path.resolve(process.env.TICK_REPO_ROOT);
   123	  try {
   124	    return execFileSync('git', ['rev-parse', '--show-toplevel'], { encoding: 'utf8' }).trim();
   125	  } catch {
   126	    return process.cwd();
   127	  }
   128	}
   129	
   130	function parseArgs(argv) {
   131	  const positional = [];
   132	  const flags = {};
   133	  for (let i = 0; i < argv.length; i++) {
   134	    const a = argv[i];
   135	    if (a.startsWith('--')) {
   136	      const key = a.slice(2);
   137	      const next = argv[i + 1];
   138	      if (next === undefined || next.startsWith('--')) {
   139	        flags[key] = true;
   140	      } else {
   141	        flags[key] = next;
   142	        i++;
   143	      }
   144	    } else {
   145	      positional.push(a);
   146	    }
   147	  }
   148	  return { positional, flags };
   149	}
   150	
   151	function parsePathsFlag(v) {
   152	  if (!v || v === true) return [];
   153	  return String(v).split(',').map(s => s.trim()).filter(Boolean);
   154	}
   155	
   156	function usage() {
   157	  process.stderr.write(`tick — coordination layer CLI
   158	
   159	Usage:
   160	  tick init
   161	  tick log <type> <task> [--agent <id>] [--note "..."] [--paths a,b] [--priority N]
   162	  tick project
   163	  tick claim <task> --agent <id> --paths <globs>
   164	  tick take --agent <id>                           (atomic next+claim)
   165	  tick next --agent <id>                           (read-only, no STATE.md write)
   166	  tick scope <task> --agent <id> --paths <globs>
   167	  tick release <task> --agent <id> [--to <agent>]
   168	  tick break <task> --agent <id> --reason "..."
   169	  tick done <task> --agent <id> [--note "..."]
   170	  tick ping <task> --agent <id> [--note "..."]      (liveness heartbeat)
   171	  tick reap <agent> [--by <id>]
   172	  tick info <task>
   173	  tick analyze [--format human|md|json] [--write <file>]
   174	
   175	Event types: ${Array.from(EVENT_TYPES).join(', ')}
   176	`);
   177	}
   178	
   179	function main(argv) {
   180	  const verb = argv[0];
   181	  const rest = argv.slice(1);
   182	  const { positional, flags } = parseArgs(rest);
   183	  const root = repoRoot();
   184	
   185	  switch (verb) {
   186	    case 'init': {
   187	      ensureEventsDir(root);
   188	      process.stdout.write(`initialized .tick/events at ${root}\n`);
   189	      return 0;
   190	    }
   191	
   192	    case 'log': {
   193	      const [type, task] = positional;
   194	      if (!type || !task) { usage(); return 2; }
   195	      const { path: p } = appendEvent(root, {
   196	        type,
   197	        task,
   198	        agent: flags.agent || process.env.TICK_AGENT || 'unknown',
   199	        note: typeof flags.note === 'string' ? flags.note : undefined,
   200	        paths: flags.paths ? parsePathsFlag(flags.paths) : undefined,
   201	        to_agent: typeof flags.to === 'string' ? flags.to : undefined,
   202	        reason: typeof flags.reason === 'string' ? flags.reason : undefined,
   203	        priority: flags.priority !== undefined ? Number(flags.priority) : undefined,
   204	      });
   205	      process.stdout.write(`${path.relative(root, p)}\n`);
   206	      return 0;
   207	    }
   208	
   209	    case 'project': {
   210	      const { stateFile } = project(root);
   211	      process.stdout.write(`${path.relative(root, stateFile)}\n`);
   212	      return 0;
   213	    }
   214	
   215	    case 'claim': {
   216	      const [task] = positional;
   217	      if (!task || !flags.agent || !flags.paths) { usage(); return 2; }
   218	      const result = claim(root, {
   219	        task,
   220	        agent: flags.agent,

     1	#!/usr/bin/env bash
     2	#
     3	# relay-xyz-guard.sh — PreToolUse guard that stops a session from driving the relay
     4	# harness before it has actually loaded the relay-xyz skill.
     5	#
     6	# The recurring failure this closes: a session runs `ls relay-automation/`, assumes it
     7	# understands the handoff, and improvises its own harness instead of invoking the
     8	# relay-xyz skill. The skill's content can't fix that, because the agent never opens it.
     9	# A hook can — the harness executes it, not the model, so a confident agent can't skip it.
    10	#
    11	# Wiring (.claude/settings.json):
    12	#   "hooks": { "PreToolUse": [ { "matcher": "Bash|Skill",
    13	#     "hooks": [ { "type": "command",
    14	#       "command": "bash relay-automation/hooks/relay-xyz-guard.sh" } ] } ] }
    15	#
    16	# Contract (reads the PreToolUse JSON event on stdin):
    17	#   - PROOF-OF-LOAD signals → record this session as "skill loaded", then allow:
    18	#       * Skill tool invoked with skill == relay-xyz
    19	#       * Bash command that runs the skill's own locator (find-harness.sh)
    20	#   - BLOCK (exit 2, message to the model) when a Bash command EXECUTES a harness driver
    21	#       entrypoint under relay-automation/ AND this session has not loaded the skill.
    22	#       Exit 2 feeds stderr back to the model and cancels the tool call.
    23	#   - Everything else → exit 0 (allow). Fail-open: any parse error allows the call.
    24	#
    25	# Precision notes:
    26	#   - Only relay-automation/<driver>.sh paths block — test/<driver>.sh and reads are exempt,
    27	#     so `validate.sh` and the shim tests never trip it.
    28	#   - Session-scoped via the event's session_id, so a marker from one session never
    29	#     suppresses the guard in another.
    30	set -u
    31	
    32	input="$(cat)"
    33	
    34	# Extract (session_id, tool_name, field) with python3 — robust JSON, no jq dependency.
    35	# field = the Skill name for Skill events, else the Bash command. Tabs/newlines stripped
    36	# from field so the tab-delimited read below stays single-line; session_id is read first
    37	# and tool second so the variable-length field can safely land last.
    38	parsed="$(RELAY_GUARD_EVENT="$input" python3 <<'PY' 2>/dev/null
    39	import os, json
    40	try:
    41	    d = json.loads(os.environ.get("RELAY_GUARD_EVENT", ""))
    42	except Exception:
    43	    raise SystemExit(0)
    44	tool = d.get("tool_name", "") or ""
    45	ti = d.get("tool_input", {}) or {}
    46	if tool == "Skill":
    47	    field = ti.get("skill", "") or ti.get("name", "")
    48	else:
    49	    field = ti.get("command", "")
    50	sess = d.get("session_id", "") or "nosession"
    51	field = str(field).replace("\t", " ").replace("\n", " ").replace("\r", " ")
    52	print("%s\t%s\t%s" % (sess, tool, field))
    53	PY
    54	)"
    55	
    56	# Parse error or empty → fail open.
    57	[ -n "$parsed" ] || exit 0
    58	IFS=$'\t' read -r SESSION TOOL FIELD <<EOF
    59	$parsed
    60	EOF
    61	
    62	STATE_DIR="${TMPDIR:-/tmp}/relay-xyz-guard"
    63	mkdir -p "$STATE_DIR" 2>/dev/null || true
    64	MARKER="$STATE_DIR/${SESSION//[^A-Za-z0-9_-]/_}"
    65	
    66	# --- proof-of-load: the skill was actually invoked this session ---
    67	if [ "$TOOL" = "Skill" ]; then
    68	  case "$FIELD" in *relay-xyz*) : > "$MARKER" 2>/dev/null || true ;; esac
    69	  exit 0
    70	fi
    71	
    72	[ "$TOOL" = "Bash" ] || exit 0
    73	
    74	# Running the skill's own locator is the Preconditions step the skill mandates —
    75	# treat it as proof the skill is being followed.
    76	case "$FIELD" in
    77	  *find-harness.sh*) : > "$MARKER" 2>/dev/null || true; exit 0 ;;
    78	esac
    79	
    80	# Inspection (read-only) of a harness file is not "driving" — never block it.
    81	first="${FIELD%% *}"
    82	case "$first" in
    83	  cat|head|tail|less|more|wc|grep|rg|ls|bat|file|stat|chmod|git|find|awk|sed) exit 0 ;;
    84	esac
    85	case "$FIELD" in *"bash -n "*) exit 0 ;; esac
    86	
    87	# --- driver entrypoints: executing these IS driving the harness ---
    88	case "$FIELD" in
    89	  *relay-automation/relay-drive.sh*|\
    90	  *relay-automation/marathon-drive.sh*|\
    91	  *relay-automation/marathon.sh*|\
    92	  *relay-automation/poll.sh*|\
    93	  *relay-automation/codex-turn.sh*|\
    94	  *relay-automation/agy-turn.sh*)
    95	    if [ ! -f "$MARKER" ]; then
    96	      cat >&2 <<'MSG'
    97	relay-xyz guard — STOP. You are about to drive the relay harness, but the relay-xyz
    98	skill has not been loaded in this session.
    99	
   100	Invoke the relay-xyz skill FIRST (Skill tool → relay-xyz). Do not hand-roll the handoff
   101	or build your own harness from `ls relay-automation/`. The skill owns:
   102	  • the device-agnostic locator (find-harness.sh) — never hardcode a path
   103	  • the Bash-sandbox rules for the codex/agy subprocess
   104	  • the exit codes and the containment / safety boundary (path-allowlist, no push)
   105	
   106	If you have already read it, run the skill's Preconditions block (find-harness.sh) and retry.
   107	MSG
   108	      exit 2
   109	    fi
   110	    ;;
   111	esac
   112	
   113	exit 0

exec
/bin/zsh -lc "nl -ba '/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/02-plan/phase-qa/SKILL.md' | sed -n '1,260p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
 succeeded in 0ms:
     1	---
     2	name: phase-qa
     3	description: >
     4	  Project plan enhancement tool. Reads a phased planning doc and appends a QA checklist
     5	  (DRY, SOLID, observability, and phase-appropriate litmus tests) under each phase, and
     6	  optionally adds an anti-goals section to give each checklist a scope boundary, and surfaces
     7	  per phase whether the work needs deploying to a remote environment. Invoke before work
     8	  begins to bake checks into the plan; invoke mid-project or post-project to also run
     9	  code-diff reviews on completed phases. Always confirms with the user where they are in
    10	  the process before writing anything. Gate enforcement is at the operator's discretion.
    11	  Trigger: user invokes the skill directly, optionally naming phases to skip.
    12	---
    13	
    14	# Phase QA (Plan Enhancement)
    15	
    16	This skill enhances a phased project plan by embedding a QA checklist under every phase
    17	before work begins — so quality expectations are explicit from the start, not bolted on
    18	at the end.
    19	
    20	**Core idea:** each phase in the plan gets a QA Checklist block added to it at one
    21	heading level deeper than the phase heading (e.g., `#### QA Checklist` when phases are
    22	`###`). The checklist is always checkbox format (`- [ ]`), regardless of how the rest of
    23	the plan doc is structured. Items get checked off as the phase's work is reviewed and
    24	approved. Enforcement is the operator's call — the checklist is a structured record, not
    25	a hard blocker. Optionally, an anti-goals section is added at the top of the plan to
    26	give every checklist a scope boundary to check against.
    27	
    28	## Invocation
    29	
    30	The user invokes the skill directly, e.g.:
    31	
    32	```
    33	/phase-qa
    34	/phase-qa skip phases 2, 4
    35	/phase-qa phases 1-3 only
    36	```
    37	
    38	Any phases named as exceptions at invocation time are skipped entirely — no checklist
    39	added, no review run.
    40	
    41	## Step 1 — Triage in one message
    42	
    43	Before reading the plan or writing anything, ask all necessary triage questions in a
    44	single message so the user does not face a chain of blocking prompts. Combine whichever
    45	of these apply:
    46	
    47	> "A few quick questions before I start:
    48	> 1. Where are you in the project right now? (a) haven't started, (b) in progress —
    49	>    which phase are you on? (c) all phases complete.
    50	> 2. *(If multiple plan docs are visible)* Which plan doc should I use?
    51	> 3. *(If any phases are already complete)* Do you have git markers (tags, commit SHAs,
    52	>    or a date range) for the completed phases? Or should I ask you for the diff?"
    53	
    54	Only ask the questions that are actually needed — don't pre-emptively ask for git
    55	markers if the user just said they haven't started yet.
    56	
    57	**Linear-progress assumption:** unless the user says otherwise, treat the project as
    58	linear — all phases before the current one are complete, the named phase is in progress,
    59	all later phases are upcoming. If the user indicates a non-linear project (e.g., Phase 4
    60	started before Phase 3 finished), ask for the status of each phase explicitly before
    61	proceeding.
    62	
    63	Do not skip this step — the same plan doc looks very different depending on where the
    64	user stands.
    65	
    66	## Step 2 — Find the plan doc
    67	
    68	Locate the phased planning doc: the file the user names, or search for `PLAN.md`,
    69	`ROADMAP.md`, `docs/plan*.md`, or any doc with phase headings. If multiple candidates
    70	exist, ask the user which one. If no phased plan exists, tell the user plainly and
    71	stop — this skill requires a plan doc to write to.
    72	
    73	## Step 3 — Confirm classification before writing
    74	
    75	After classifying each phase, show the user a summary before modifying anything:
    76	
    77	> "Here's what I'll do:
    78	> - Phases 1–2 (completed): run diff review and pre-fill checklists with findings
    79	> - Phase 3 (in progress): add checklist, marked in progress
    80	> - Phases 4–6 (upcoming): add blank checklists
    81	> Proceed?"
    82	
    83	Only write to the plan doc after the user confirms. This is the last chance to correct
    84	a mis-classification or adjust phase scope before anything is changed.
    85	
    86	## Step 3b — Set up diff markers (optional but recommended)
    87	
    88	After the user confirms the classification, offer to set up git phase markers so future
    89	diff reviews have clean boundaries to work from. This step is optional — skip it if the
    90	user declines or is already past the point where markers are useful.
    91	
    92	> "Want me to set up git markers for each phase so diff reviews are automatic later?
    93	> I can tag the current commit as the start of each upcoming phase."
    94	
    95	**If the environment has terminal/git access**, run the tags directly after the user
    96	confirms:
    97	
    98	| Phase status | Action |
    99	|---|---|
   100	| Upcoming | `git tag phase-N-start HEAD` — marks where the phase will begin |
   101	| In progress | Ask: "Do you know roughly when Phase N started (a date, a commit message, or a feature you added first)?" Then run `git log --oneline` to help locate it, and tag: `git tag phase-N-start <sha>` |
   102	| Completed, no marker | Same as in-progress — locate the start commit via `git log`, tag it as `phase-N-start`, then tag the end: `git tag phase-N-end <sha>` |
   103	| Completed, markers exist | Nothing to do — confirm the existing tags and move on |
   104	
   105	**If no terminal access**, provide the exact commands for the user to run:
   106	```
   107	git tag phase-3-start HEAD           # for the upcoming phase
   108	git tag phase-2-start <sha>          # for a phase already started or complete
   109	git tag phase-2-end <sha>            # optional end marker
   110	```
   111	
   112	Tell the user: "Run these in your terminal before starting Phase N, and the diff review
   113	will be fully automatic when you come back to close it."
   114	
   115	Record the markers found or created in the confirmation summary so the operator knows
   116	what's in place.
   117	
   118	## Step 3c — Anti-goals section (optional)
   119	
   120	After Step 3b, offer to add an anti-goals section if the plan doesn't already have one:
   121	
   122	> "Does your plan have an anti-goals section — a short list of what this project will
   123	> not do? If not, I can add one. It gives each phase checklist a scope boundary to
   124	> check against."
   125	
   126	**If the plan already has an anti-goals section:** note it and move on — the checklist
   127	will use it automatically (see below).
   128	
   129	**If the user declines:** skip this step entirely. No section is added.
   130	
   131	**If the user wants one added:** ask them to name 2–5 things the project will not do.
   132	Write an `## Anti-goals` section at the top of the plan doc, immediately before the
   133	first phase heading:
   134	
   135	```markdown
   136	## Anti-goals
   137	
   138	Things this project explicitly will not do:
   139	
   140	- [Anti-goal 1]
   141	- [Anti-goal 2]
   142	```
   143	
   144	**When anti-goals are defined (added now or already present in the plan):** append one
   145	additional item to every phase checklist, after the seven standard checks:
   146	
   147	```
   148	- [ ] Scope: no deliverable in this phase crosses into anti-goals
   149	```
   150	
   151	## Step 3d — Surface deployment need per phase (optional)
   152	
   153	After Step 3c, raise one question for the phases that could plausibly ship something
   154	runnable: does this phase need to be deployed to a remote environment (staging,
   155	production, a client server) before it counts as done?
   156	
   157	**This skill's only job here is to catch and surface *whether* a deploy step is needed —
   158	full stop.** It does not plan the deployment. Target, owner, rollback, sequencing, and
   159	verification details are a separate conversation the project planner has elsewhere; do
   160	not extract, prescribe, or record them in the checklist.
   161	
   162	> "Quick one: does any phase need to land on a remote environment to be done, or do they
   163	> all complete locally? I'm only flagging *whether* a deploy is needed — not how it's
   164	> done. The details are yours to work out separately."
   165	
   166	Pose the question broadly so no phase is silently skipped; record the answer narrowly.
   167	Each phase resolves to one of three outcomes:
   168	
   169	| Answer | What goes in the checklist |
   170	|---|---|
   171	| Deploy needed, confirmed | Add the deployment item, unchecked — to be confirmed done before the phase closes |
   172	| Maybe needed, unconfirmed | Add a placeholder flagging it for resolution (often a question for the plan author), like the acceptance-criteria placeholder |
   173	| No deploy needed | Add a one-line N/A note (checked), so the answer is on record rather than forgotten |
   174	
   175	The deployment line is conditional: a phase that completes locally gets the N/A note if
   176	the question was explicitly asked and answered, and nothing at all otherwise. The three
   177	forms:
   178	
   179	```
   180	- [ ] Deployment: this phase requires a remote deploy — confirm it's done before closing the phase
   181	- [ ] Deployment: confirm whether this phase needs a remote deploy before closing (check with the plan author)
   182	- [x] Deployment: N/A — phase completes locally, ships no remote artifact (asked, confirmed)
   183	```
   184	
   185	Like the Scope item, this line is operator-attested: the skill surfaces the question, the
   186	operator owns the answer.
   187	
   188	## Step 4 — Determine status per phase
   189	
   190	Based on the confirmed classification, apply the appropriate behavior per phase:
   191	
   192	### Upcoming phases
   193	Add a QA checklist block immediately after the phase heading or deliverables list. The
   194	checklist contains:
   195	- The seven standard checks (DRY, SOLID, observability — always included)
   196	- Two to four phase-specific litmus tests derived from what the phase is building
   197	- Any conditional items whose trigger applies: the Scope item (Step 3c) and the
   198	  Deployment item (Step 3d)
   199	
   200	All items start unchecked (`- [ ]`). No code review — there is no code yet.
   201	
   202	### In-progress phase
   203	Treat the same as an upcoming phase: add the checklist if it isn't there yet. Mark the
   204	header to show it is in progress: `#### QA Checklist *(in progress)*` (or one level
   205	deeper than the phase heading, as above).
   206	
   207	### Completed phases
   208	Run a targeted diff review against the same standard and litmus-test items that will
   209	appear in the checklist (this is not a general correctness or bug review — use
   210	`/code-review` for that). Then add the checklist with items pre-filled:
   211	- Items that passed the diff review → checked (`- [x]`) with a one-line note
   212	- Items with findings → unchecked (`- [ ]`) with the finding described inline so the
   213	  operator can act on it or waive it
   214	
   215	To find the diff, use the phase markers created in Step 3b if available:
   216	`git diff phase-N-start..phase-N-end -- .` (or `..HEAD` if no end marker). If Step 3b
   217	was skipped or markers weren't created, fall back to a commit SHA or date the user
   218	provides. If the environment has no terminal or git execution capability, do not attempt
   219	to run the command — ask the user to paste the diff output or provide the list of files
   220	the phase touched instead. If no markers exist and the user can't supply one, ask for a
   221	list of files.
   222	
   223	**If no diff can be obtained** (no markers, no file list, and no paste available), add
   224	the checklist with all items unchecked and a note at the top:
   225	```
   226	> Diff unavailable — manual review required before checking off items.
   227	```
   228	
   229	## The standard checks (always included)
   230	
   231	These seven items appear in every checklist, every phase:
   232	
   233	```
   234	- [ ] DRY: No rule, constant, or business logic duplicated across files changed in this phase
   235	- [ ] S (Single Responsibility): Each new or changed unit has exactly one reason to change
   236	- [ ] O (Open/Closed): New variants don't require editing existing switch/if chains or type lists
   237	- [ ] L (Liskov): No subtype overrides a method to throw NotSupported or narrows the base contract
   238	- [ ] I (Interface Segregation): No implementer forced to stub or no-op methods it doesn't use
   239	- [ ] D (Dependency Inversion): High-level code depends on interfaces, not concrete classes or vendors
   240	- [ ] Observability: new behavior at failure boundaries (external calls, state mutations, async ops) emits a loggable or measurable signal
   241	```
   242	
   243	### Calibration — only flag real smells
   244	
   245	- **DRY:** two occurrences are a coincidence; flag at three, or when the duplicated thing
   246	  is a single source-of-truth rule that is dangerous to have in two places (auth check,
   247	  tax rate, permission boundary).
   248	- **SOLID:** flag only when the variation or extension it guards against already exists or
   249	  is explicitly in the plan — not speculative future needs.
   250	- **Observability:** flag when new behavior crosses a boundary (external call, state mutation, async operation, error path) with no log, metric, or trace. Do not flag pure internal functions where a silent failure is not possible.
   251	- **For completed-phase diff reviews only:** a finding must name a concrete `file:line`
   252	  and explain how it gets more expensive if the phase ships over it. Drop anything that
   253	  can't clear that bar. For upcoming and in-progress phases there is no code to cite —
   254	  checklist items start unchecked with no findings attached.
   255	
   256	## Phase-specific litmus tests
   257	
   258	After the seven standard items, add two to four checks tailored to what this phase is
   259	actually building. Derive them from the phase's deliverables, not from a fixed template.
   260	Examples by phase type:

codex
I’ve confirmed XYZ does have one concrete hook worth comparing: a pre-tool guard that blocks relay harness execution until the coordinating skill has actually been loaded. I’m checking whether our broader skill catalog offers any equivalent discovery surface or whether it’s still just naming discipline plus convention.
exec
/bin/zsh -lc "nl -ba '/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/.claude/settings.json' | sed -n '1,220p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
 succeeded in 0ms:
     1	{
     2	  "permissions": {
     3	    "allow": [
     4	      "Bash(python3 -c 'import json; print\\(json.dumps\\(json.load\\(open\\('\\\\''/Users/noelsaw/.claude/settings.json'\\\\''\\)\\).get\\('\\\\''hooks'\\\\'',{}\\), indent=2\\)\\)')",
     5	      "Bash(python3 -c \"import json;json.load\\(open\\('settings.json'\\)\\);print\\('settings.json still valid'\\)\")",
     6	      "Bash(TICK_REPO_ROOT=\"/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm\" \"/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/bin/tick\" release DUELING-REVIEW-0622 --agent claude-a --to claude-b)",
     7	      "Bash(TICK_REPO_ROOT=\"/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm\" \"/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/bin/tick\" info DUELING-REVIEW-0622)",
     8	      "Skill(loop)",
     9	      "Skill(loop:*)",
    10	      "Bash(env TICK_REPO_ROOT=\"/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm\" \"/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/poll.sh\" --mode relay --agent claude-a --claude-agents \"claude-a,claude-b\" --relay-task DUELING-REVIEW-0622 --relay-file \"/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-system/2026-06-22/dueling-claudes.md\" --artifact \"/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-system/2026-06-22/dueling-claudes.md\" --deadline 1782165049)",
    11	      "Bash(TICK_REPO_ROOT='/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm' '/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/bin/tick' info DUELING-REVIEW-0622)",
    12	      "Bash(TICK_REPO_ROOT='/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm' '/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/bin/tick' done DUELING-REVIEW-0622 --agent claude-a)",
    13	      "Bash(TICK_REPO_ROOT='/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm' '/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/bin/tick' claim DUELING-REVIEW-0622 --agent claude-a)",
    14	      "Bash(TICK_REPO_ROOT='/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm' '/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/bin/tick' claim DUELING-REVIEW-0622 --agent claude-a --paths relay-system/2026-06-22/dueling-claudes.md)",
    15	      "Bash(env 'TICK_REPO_ROOT=/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm' '/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/poll.sh' --mode relay --agent claude-a --claude-agents claude-a,claude-b --relay-task DUELING-REVIEW-0622 --relay-file '/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-system/2026-06-22/dueling-claudes.md' --artifact '/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-system/2026-06-22/dueling-claudes.md' --deadline 1782165049)",
    16	      "Bash(bash /Users/noelsaw/.claude/skills/relay-to-issue/relay-to-issue.sh resolve --thread 2026-06-22/dueling-claudes)",
    17	      "Bash(bash /Users/noelsaw/.claude/skills/relay-to-issue/relay-to-issue.sh file --thread '/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-system/2026-06-22/dueling-claudes.md' --title 'Relay follow-ups: dueling-claudes — `tick` silently no-ops from a foreign CWD \\(stalled the relay handoff\\)' --body-file /private/tmp/claude-501/-Users-noelsaw-Documents-GH-Repos-giant-brains-claude-skills/d874d9a2-f3e3-4b47-ac2b-3af060e01893/scratchpad/relay-issue-body.md --repo Claude-AI-Tools-Ventura-County/xyz-3-agents-swarm --labels bug)"
    18	    ]
    19	  }
    20	}

exec
/bin/zsh -lc "nl -ba '/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/README.md' | sed -n '1,220p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
 succeeded in 0ms:
     1	# Giant Brains Claude Skills
     2	
     3	<img width="1941" height="1058" alt="giant-brains-02" src="https://github.com/user-attachments/assets/d5a0e02b-eec2-4026-b83e-cf725def5942" />
     4	
     5	A suite of Claude Code skills that catch you at the moment of a decision, again when you're improving something, and once more before you call it done — and force a short, honest answer you can act on in seconds. A ten-skill decision-and-improvement core, plus a widening set for debugging, docs, repo, and session hygiene.
     6	
     7	**New here?** Jump to [Install](#install) — a symlink loop puts the whole suite in Claude Code in under a minute.
     8	
     9	## About
    10	
    11	A suite of skills for [Claude Code](https://claude.com/claude-code) that bring hygiene to the whole life of getting something better — first **deciding well**, then **improving it verifiably**. Each fires at a different moment and forces the response into a short, scannable shape — so a human operator can act fast without missing what matters. The throughline: *make the implicit explicit, lead with the line that survives skimming, and refuse rather than fake it.*
    12	
    13	## What you get
    14	
    15	- **Faster calls, fewer blind spots.** Every answer leads with the one line that must survive skimming, then adds only the fields that change the decision — no wall of text to wade through.
    16	- **Hidden tradeoffs made explicit.** The cost you're actually paying — the corner you're sacrificing, the assumption you're betting on, the blast radius of the path you picked — gets named out loud *before* you commit.
    17	- **A shared reversibility read.** The decision skills speak one vocabulary — **Easy / Costly / One-way door** — so a cheap two-way door never gets treated like a commitment that's expensive to unwind.
    18	- **Honest signal, not constant alarm.** They stay quiet when a change is small and reversible, and refuse rather than fake a verdict they can't stand behind. Calibration is as much about declining as raising a flag.
    19	- **Improvement you can prove.** Act II turns "make it better" into a metric, an un-gameable oracle, and a baseline, then runs a self-verifying loop that returns a real, numbered win — or a clean "no gain found."
    20	- **A paper trail that outlives the chat.** The decision, the bet it rides on, and a revisit date get written to the repo at commit time — so six months later, "why is it built this way?" has an answer.
    21	
    22	## When to reach for it
    23	
    24	- **You're about to commit to a plan or migration** and want to pressure-test the framing before you start — [take-a-step-back](01-decide/take-a-step-back/SKILL.md).
    25	- **You're unsure a feature or refactor is worth building** and want the payoff priced against the cost before you spend the effort — [worth-it](01-decide/worth-it/SKILL.md).
    26	- **A deadline is squeezing you** and you need to name which of speed, cost, or quality you're actually trading away — [iron-triangle](01-decide/iron-triangle/SKILL.md).
    27	- **You're eyeing a refactor or schema change** and need to know how far it ripples and how hard it is to undo — [blast-radius](01-decide/blast-radius/SKILL.md).
    28	- **An agent handed you a wall of options** and you just need the call — [bottom-line](01-decide/bottom-line/SKILL.md).
    29	- **An agent gave you scattered steps or a verbose completion message** and you need the execution sequence — [linear](02-plan/linear/SKILL.md).
    30	- **You told an agent "make this faster"** but can't tell whether it actually did — [baseline-spec](03-improve/baseline-spec/SKILL.md) to define what "better" means, then [auto-improve](03-improve/auto-improve/SKILL.md) to prove it.
    31	- **The work feels finished** and you want what's missing enumerated, executed, and committed before you say "done" ("close the loop") — [loose-ends](05-close/loose-ends/SKILL.md).
    32	- **You just made a call that's expensive to unwind** and want the bet written down before it evaporates — [record-decision](05-close/record-decision/SKILL.md).
    33	- **You have a whole plan doc, not one decision,** and want it stress-tested before work starts — [giantbrains](giantbrains/SKILL.md) triages once, runs the right two or three lenses, and returns one combined verdict.
    34	
    35	## Act I — Deciding well (decision hygiene)
    36	
    37	Four skills that fire around a decision, each answering a different question at a different moment.
    38	
    39	| Skill | The operator's question | Its job |
    40	|---|---|---|
    41	| [take-a-step-back](01-decide/take-a-step-back/SKILL.md) | "Am I making the best decision possible?" | **Frame** — challenge the plan and the problem before committing |
    42	| [iron-triangle](01-decide/iron-triangle/SKILL.md) | "Which of speed, cost, or quality am I trading away?" | **Price** — make the implicit tradeoff explicit |
    43	| [blast-radius](01-decide/blast-radius/SKILL.md) | "How big is the path I chose, what breaks, how hard to undo?" | **Size** — measure cost and reversibility of a chosen path |
    44	| [bottom-line](01-decide/bottom-line/SKILL.md) | "There's too much here — what's the call?" | **Cut** — compress overload and analysis paralysis into a decision, with a brief anchor to where the work sits |
    45	
    46	They **chain** along the life of a decision: **frame** it (should I, and is this the right problem?), **price** the tradeoff (which corner gives?), **size** the chosen path (how big, what breaks?), then **cut** to the bottom line when the analysis balloons. The same situation can touch all four precisely because they answer different questions at different moments.
    47	
    48	## The bridge — from deciding to doing
    49	
    50	Once the call is made, one skill turns it into motion.
    51	
    52	| Skill | The operator's question | Its job |
    53	|---|---|---|
    54	| [linear](02-plan/linear/SKILL.md) | "The steps are scattered — what's the execution order?" | **Sequence** — extract and order procedural steps into one top-to-bottom plan |
    55	
    56	[linear](02-plan/linear/SKILL.md) is not a decision skill — it fires once a call exists and the *doing* is scattered. It's the natural handoff from `bottom-line` (decision made → ordered plan), but it earns its keep anywhere steps hide in prose: a verbose how-to from an agent mid-project, or a completion message at the tail end whose remaining work is smeared across "what I didn't do," "open items," and "next steps." Whenever someone must execute three or more steps, linear collapses them into one numbered, top-to-bottom plan — branches as sub-bullets, verification inline, a brief "where are we now?" context anchor up top when needed, and nothing actionable after the list.
    57	
    58	## Act II — Improving verifiably (measure, then optimize)
    59	
    60	Once you've decided to make something concretely better, a second pair carries it from a vibe to a proven result.
    61	
    62	| Skill | The operator's question | Its job |
    63	|---|---|---|
    64	| [baseline-spec](03-improve/baseline-spec/SKILL.md) | "What does 'better' even mean, and how would I know?" | **Define** — turn "make it better" into a metric, oracle, budget, and baseline |
    65	| [auto-improve](03-improve/auto-improve/SKILL.md) | "Now make it better — provably, not just plausibly." | **Improve** — run a bounded, self-verifying loop, or honestly report no gain |
    66	
    67	These **chain** too: **define** the measurable contract, then **improve** against it. The routing is deliberately one-directional — a cold-start request like *"optimize this"* belongs to [baseline-spec](03-improve/baseline-spec/SKILL.md) (the **definer**), which fires first; [auto-improve](03-improve/auto-improve/SKILL.md) (the **executor**) defers any undefined request back to it and only runs once a metric, an un-gameable oracle, and a budget already exist. baseline-spec refuses to optimize a goal it can't measure — exactly the Act I instinct of *refuse rather than fake it* — and hands off to auto-improve once the three pillars are locked. auto-improve is the suite's one **executional** skill: instead of emitting a verdict, it runs a ratcheted mutate-measure-keep-or-revert search and returns either a verified, numbered win or a clean "no real improvement found." See its [README](03-improve/auto-improve/README.md) and [operator FAQ](03-improve/auto-improve/FAQS.md).
    68	
    69	The two acts join end to end: decide *whether and what* (Act I), sequence the work ([linear](02-plan/linear/SKILL.md)), then *prove the improvement* (Act II) — and sweep the loose ends before calling it done.
    70	
    71	## The sweep — declaring done honestly
    72	
    73	Work rarely ends where the request did. One skill fires at the last moment — after the work, before the word "done."
    74	
    75	| Skill | The operator's question | Its job |
    76	|---|---|---|
    77	| [loose-ends](05-close/loose-ends/SKILL.md) | "What did I forget?" / "Close loop" | **Sweep & Execute** — diff work against the ask, enumerate what's absent, execute the final fixes, and commit/push |
    78	
    79	[loose-ends](05-close/loose-ends/SKILL.md) (alias "close-loop") is Act I's mirror image: the decision skills guard the moment *before committing*; this one guards the moment *before declaring done*. It reconstructs the contract (the original request, including the throwaway clauses), inventories what was actually delivered, and sweeps for the classic forgettables — the dropped requirement, the unrun test, the stale README, the leftover debug print. Crucially, it then actively offers to **close the loop**: executing the missing steps, running the linter, auto-syncing the docs, and generating the final git commit and push. Findings come back blocking-first, each with an evidenced address and an offer to execute the fix. It is strictly post-work: "what am I missing?" asked *before* the work exists belongs to [take-a-step-back](01-decide/take-a-step-back/SKILL.md), gating the phases of a plan doc belongs to [phase-qa](02-plan/phase-qa/SKILL.md), and bugs in code that *is* present belong to a code review — this skill hunts the absent, not the wrong.
    80	
    81	## The ledger — remembering why
    82	
    83	Every skill above produces a sharp one-shot verdict — and then the verdict evaporates when the chat ends. One skill makes them durable.
    84	
    85	| Skill | The operator's question | Its job |
    86	|---|---|---|
    87	| [record-decision](05-close/record-decision/SKILL.md) | "We made the call — what did we bet on, and when will we know we were right?" | **Record** — write the bet to the repo at commit time, close the loop when reality reports back |
    88	
    89	[record-decision](05-close/record-decision/SKILL.md) is the suite's memory. At commit time it writes the decision to a dated file — the call, the fragile assumption it rides on, the expected signal with a by-when, the reversibility read, and a revisit trigger — then keeps the record *and* the project docs current as findings arrive. It's mostly a receiver: take-a-step-back's fragile assumption becomes the bet, blast-radius's verdict becomes the reversibility line, baseline-spec's metric becomes the expected signal. The records carry machine-readable frontmatter, so "find every Costly decision not yet Validated" is one query, and a date-based revisit trigger can become a `/schedule` appointment instead of a hope.
    90	
    91	It is deliberately **not** Claude's memory (`MEMORY.md` / `CLAUDE.md`): memory is operator-private and about *how Claude should work with you*; decision records live in git, address the whole team — humans and future agents — and answer *why the system is shaped this way*. The skill file carries the full comparison.
    92	
    93	## The router — one door to the suite
    94	
    95	When the input is a whole doc rather than a single decision, one skill picks the lenses for you.
    96	
    97	| Skill | The operator's question | Its job |
    98	|---|---|---|
    99	| [giantbrains](giantbrains/SKILL.md) | "Stress-test this whole plan — which lenses should run?" | **Route** — triage once, run the 2–3 stage-matched lenses report-only, synthesize one verdict |
   100	
   101	[giantbrains](giantbrains/SKILL.md) is the suite's front door for docs. It triages in one message (which doc, what stage), then routes to at most three lenses — a draft gets frame/price/size, an in-progress plan gets a size-and-squeeze check, a retro gets the ledger audit and the outcome cut — runs them report-only, and dedupes the overlap into a single bottom-line-shaped verdict: one reversibility read, one do-next. It never edits the doc: writers ([phase-qa](02-plan/phase-qa/SKILL.md) for phased plans, [record-decision](05-close/record-decision/SKILL.md) for bets, [linear](02-plan/linear/SKILL.md) for scattered steps) are offered afterward as explicit opt-ins. And on a one-pager it refuses the battery and hands off to the single matching lens — running five lenses on one decision is ceremony, not hygiene.
   102	
   103	## More in the suite
   104	
   105	The core above is the decision-and-improvement throughline. Around it sit skills that apply the same *make-the-implicit-explicit, refuse-rather-than-fake-it* discipline to other moments — planning, debugging, and keeping a repo honest.
   106	
   107	| Skill | When it fires | Its job |
   108	|---|---|---|
   109	| [worth-it](01-decide/worth-it/SKILL.md) | "Is this feature/refactor even worth building?" | **Price the payoff** against the cost across every constituency a change serves, versus doing nothing |
   110	| [spike-360](02-plan/spike-360/SKILL.md) | A change might introduce, move, or replace a source of truth | **Interrogate authority** before planning anything that touches authoritative state |
   111	| [swe](02-plan/swe/SKILL.md) | Authoring or reviewing a v1.x build doc / spec / RFC | **Governance lens** — minimal scope, designed for diagnosis, verifiable before code |
   112	| [phase-qa](02-plan/phase-qa/SKILL.md) | A phased plan needs checks baked in, or completed phases reviewed | **Plan QA** — append phase-appropriate checklists, then diff-review the finished phases |
   113	| [debug-mantra](04-build/debug-mantra/SKILL.md) | A bug, a stack trace, a "where is this coming from?" | **Debugging discipline** — reproduce, trace the fail path, falsify the hypothesis, cross-reference |
   114	| [rabbit-hole](04-build/rabbit-hole/SKILL.md) | An agent keeps surfacing one-more-thing on a simple task | **Stop the drip** — one end-to-end triage that puts every issue on the table at once |
   115	| [ponytail](04-build/ponytail-refined/SKILL.md) | Over-engineering, bloat, "what's the simplest version?" | **Force the laziest implementation** that works — YAGNI on code and abstractions, not on explicit feature requirements |
   116	| [honest](repo-health/honest/SKILL.md) | "What's the real state of this repo?" before a stakeholder update | **Ground-truth read** — how mature the codebase really is and what you can safely claim |
   117	| [front-door](repo-health/frontdoor/SKILL.md) | Auditing onboarding — "can a new user install this?" | **Walk the front door** — does clone-to-working actually work, and is a secret leaked? |
   118	| [readme-audit](repo-health/readme/SKILL.md) | "Is the README accurate / clear / still matching the code?" | **Audit the README** as artifact and as map — then follow its links as a doc-hygiene litmus |
   119	| [snapshot](repo-health/snapshot/SKILL.md) | "Save this session" before signing off or a crash | **Checkpoint the session** to an additive `snapshot.md` you can resume from later |
   120	
   121	Standalone tooling that isn't part of the suite (read-only permission presets, recent-prompt allowlisting, skill path-hardening, gh/git auth repair, per-repo VS Code window tinting, a dotfiles-sync kit) lives under [utils/](utils/README.md).
   122	
   123	## Beyond the suite — the relay
   124	
   125	A standalone collaboration tool, not one of the ten decision skills: [relay](04-build/relay/SKILL.md) runs a turn-based review loop between two Claude Code agents — a **Producer** who builds and a **Reviewer** who critiques and proposes fixes the author applies — entirely inside one dated Markdown file, so a human stops copy-pasting output between two windows. The file is the shared bus, the change-log, and the decision record at once: graded findings (`Blocker` / `Should` / `Nit` / `Pass`), a mandatory disposition on every proposal, an **evidence contract** per turn (the Producer logs what it *ran / skipped / couldn't run*; the Reviewer logs whether its verdict is `behaviorally proven` or `textual only`), and a clean exit on **Approved**. The protocol is model-agnostic — run a different model in the Reviewer window (Codex, Gemini, another Claude tier) for genuinely independent eyes. See the worked [sample thread](04-build/relay/RELAY-sample.md).
   126	
   127	**Optional automation add-on.** Relay is human-locked by default (one "your turn" nudge per handoff). A fuller, `tick`-backed automation engine lives in a sibling repo: [xyz-3-agents-swarm · relay-system](https://github.com/Claude-AI-Tools-Ventura-County/xyz-3-agents-swarm/tree/main/relay-system/2026-06-14). It turns the manual, human-nudged relay into a hands-free, self-healing loop — `tick` coordination primitives enforce strict Producer/Reviewer turn-taking, auto-detect and recover stalled turns, and gate termination on an LLM-written `Approved` with a clean tree. It ships as a sibling self-extracting skill powered by `tick`, leaving the portable `/relay` protocol completely untouched and dependency-free.
   128	
   129	## What they share
   130	
   131	- **Short, structured output.** Every skill leads with the one line that must survive skimming, then adds only the fields that change the call. Drop anything that doesn't; never pad the template. When the work is part of an ongoing phase or status thread, the compression skills also add a brief location marker so the user knows what was just done and where the next steps fit. `baseline-spec` follows the same one-shot, scannable shape as the four decision skills; `linear`'s output *is* the structure — one numbered list, nothing actionable outside it; `record-decision` writes the same scannable shape to a file instead of the chat; `auto-improve` is the lone exception — it *executes* a loop rather than emitting a verdict, but still leads with an honest headline number.
   132	- **A shared reversibility read.** Where it applies, the skills speak one vocabulary — **Easy / Costly / One-way door** — so a two-way door is treated differently from a commitment that is expensive to unwind. (Iron-triangle's version asks whether a sacrificed corner stays *contained* or *compounds*.)
   133	- **Refuse rather than fake it.** Accurate signal over constant alarm. The decision skills stay quiet when a change is small and reversible; `baseline-spec` refuses to optimize a goal it can't measure; `auto-improve` rejects any "win" that's gamed or lost in the noise; `loose-ends` returns "swept clean — ship it" rather than inventing a finding to justify firing. Calibration is as much about declining as raising a flag.
   134	
   135	## Calibration — what good output looks like
   136	
   137	Good output names the *one* thing that changes the call and ends with a move that reduces uncertainty. Example, from `take-a-step-back`:
   138	
   139	> **Decision:** You're about to execute the 3-PR plan doc as written — cherry-picking and sequencing the PRs onto the drifted source branch.
   140	>
   141	> **Step-back check:**
   142	> - **Most fragile assumption:** That the plan doc is still the right path now that the branch has drifted — it was written against a tree that no longer exists.
   143	> - **Alternative frame:** This may not be a "merge the existing PRs" problem at all, but a "re-land the *ideas* as fresh work against current main" problem.
   144	> - **Reversibility:** Costly — once the PRs are cherry-picked and merged in sequence, untangling them from main is real work.
   145	>
   146	> **Do next:** Diff each PR's *intent* against current main and decide per PR — cherry-pick as-is, or re-cut as new work. The plan doc is an input, not a destiny.
   147	
   148	What makes it good:
   149	- **One sharp counterpoint, not five.** It names the single fragile assumption instead of listing every possible risk.
   150	- **It challenges the frame**, not just the option — the real question is "follow the plan, or re-cut?", not "how do I cherry-pick cleanly?".
   151	- **Concrete, honest reversibility** — a specific cost, on the shared scale.
   152	- **A do-next that reduces uncertainty** rather than describing it.
   153	
   154	The inverse matters just as much: a good skill also knows when *not* to escalate. See `blast-radius`'s small-change example, where the right answer is "ship it, low risk" — calibration is as much about staying quiet as raising a flag.
   155	
   156	The compression skills earn their keep on the *delta* — what goes in versus what comes out. From `linear`:
   157	
   158	> **In:** "To get this working you'll first want to install the CLI, which you can do with npm. Then there's some configuration to think about — the config file lives at ~/.toolrc and needs your API key. Oh, and note that on Linux you may need sudo for the install. Once configured, run `tool sync` to pull data. If sync fails with a 401, your key is wrong. Finally you can run `tool build`, though if you're on the beta channel you'd use `tool build --beta` instead."
   159	>
   160	> **Out:**
   161	> 1. Install the CLI: `npm install -g tool`
   162	>    - If on Linux: prefix with `sudo` if you get a permissions error.
   163	> 2. Add your API key to `~/.toolrc`.
   164	> 3. Run `tool sync` to pull data. → expect "Sync complete"
   165	>    - If 401 error: API key is wrong — fix step 2 before continuing.
   166	> 4. Build:
   167	>    - Stable channel: `tool build`
   168	>    - Beta channel: `tool build --beta`
   169	
   170	Every detail survived — the sudo caveat, the 401 diagnosis, the beta variant — but now it executes top-to-bottom without re-reading.
   171	
   172	## Install
   173	
   174	These are [Agent Skills](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) built on the open `SKILL.md` standard, so the same files install across every Claude surface.
   175	
   176	### Claude.ai (web) and Claude Desktop
   177	
   178	The web app and desktop app share one flow: enable code execution, then upload each skill as its own ZIP.
   179	
   180	1. **Enable execution.** Open **Settings > Capabilities** and turn on **Code execution and file creation**. (Available on Free, Pro, Max, Team, and Enterprise plans. On Team/Enterprise, an owner must first enable it under **Organization settings > Skills**.)
   181	2. **Zip each skill folder** — one ZIP per skill, each with a `SKILL.md` at its root. Run from the repo root:
   182	   ```bash
   183	   ROOT="$PWD"
   184	   for d in 01-decide/*/ 02-plan/*/ 03-improve/*/ 04-build/*/ 05-close/*/ repo-health/*/ giantbrains/; do
   185	     [ -f "$d/SKILL.md" ] || continue
   186	     (cd "$d" && zip -rX "$ROOT/$(basename "$d").zip" . -x '.*')
   187	   done
   188	   ```
   189	3. **Upload.** In Claude, go to **Customize > Skills**, click **+ > + Create skill > Upload a skill**, and select one ZIP. Repeat for each skill.
   190	4. **Turn it on** under **Customize > Skills**.
   191	
   192	Uploaded custom skills are private to your account. Install only from sources you trust, and review each `SKILL.md` before enabling.
   193	
   194	### Claude Code
   195	
   196	Put each skill directory where Claude Code looks for skills — **personal (all projects):** `~/.claude/skills/`, or **project (shared with a repo):** `<project>/.claude/skills/`. Symlink them so a `git pull` keeps them current (run from the repo root):
   197	
   198	```bash
   199	mkdir -p "$HOME/.claude/skills"
   200	for d in "$PWD"/01-decide/*/ "$PWD"/02-plan/*/ "$PWD"/03-improve/*/ "$PWD"/04-build/*/ "$PWD"/05-close/*/ "$PWD"/repo-health/*/ "$PWD"/giantbrains/; do
   201	  [ -f "$d/SKILL.md" ] || continue
   202	  ln -s "${d%/}" "$HOME/.claude/skills/$(basename "$d")"
   203	done
   204	```
   205	
   206	Claude auto-invokes a skill when the request matches its `description`, or you can call it by name. The entry file must be named exactly `SKILL.md` (uppercase) — the loader matches it case-sensitively even on case-insensitive macOS, so a lowercase `skill.md` is silently never discovered.
   207	
   208	## Authoring conventions
   209	
   210	Lessons baked into these files. Keep them if you add more skills:
   211	
   212	- **Valid frontmatter on line 1.** The file must open with `---` and a YAML `name` + `description`, with no prose preamble and no ` ```yaml ` code fence wrapping it — otherwise the skill silently fails to load and never appears.
   213	- **Entry file must be `SKILL.md`, exact case.** The loader matches it case-sensitively even on case-insensitive macOS, so a lowercase `skill.md` is silently skipped — and watch for git hiding a case-only rename when `core.ignorecase` is true.
   214	- **ASCII punctuation.** Straight quotes and regular hyphens. Curly quotes and non-breaking hyphens (U+2011) look identical to their ASCII twins but break grep, copy, and matching. Em-dashes are fine.
   215	- **Triggers live in the `description`.** That is the surface Claude matches against — keep it concrete and observable ("about to recommend a migration"), never circular ("fire when the change is major", which the skill can only know *after* running).
   216	- **Examples calibrate behavior.** Include at least one counter-example where the skill correctly does *not* escalate — a small change, a cheap reversible call — or it will skew toward alarm.
   217	- **Brevity is the product.** Each skill's output should be just enough meat that a human operator will actually read it.
   218	
   219	## Layout
   220	

exec
/bin/zsh -lc "ls -l '/Users/noelsaw/.claude/skills' | sed -n '1,220p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
 succeeded in 0ms:
total 0
lrwxr-xr-x@ 1 noelsaw  staff   84 Jun 30 13:03 auto-improve -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/03-improve/auto-improve
lrwxr-xr-x@ 1 noelsaw  staff   85 Jun 30 13:03 baseline-spec -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/03-improve/baseline-spec
lrwxr-xr-x@ 1 noelsaw  staff   83 Jun 30 13:03 blast-radius -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/01-decide/blast-radius
lrwxr-xr-x@ 1 noelsaw  staff   82 Jun 30 13:03 bottom-line -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/01-decide/bottom-line
drwxr-x---@ 3 noelsaw  staff   96 Jul  2 17:22 codebase-memory
lrwxr-xr-x@ 1 noelsaw  staff   67 Jun 22 18:09 consult -> /Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/skills/consult
lrwxr-xr-x@ 1 noelsaw  staff   82 Jun 30 13:03 debug-mantra -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/04-build/debug-mantra
drwxr-xr-x@ 3 noelsaw  staff   96 Jun 17 14:59 front-door
lrwxr-xr-x@ 1 noelsaw  staff   72 Jun 21 19:28 giantbrains -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/giantbrains
lrwxr-xr-x@ 1 noelsaw  staff   84 Jun 30 13:03 github-auth-debug -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/utils/github-auth-debug
drwxr-xr-x@ 5 noelsaw  staff  160 Jun 22 19:44 graphify
lrwxr-xr-x@ 1 noelsaw  staff   79 Jun 30 13:03 honest -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/repo-health/honest
lrwxr-xr-x@ 1 noelsaw  staff   84 Jun 30 13:03 iron-triangle -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/01-decide/iron-triangle
lrwxr-xr-x@ 1 noelsaw  staff   75 Jun 30 13:03 linear -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/02-plan/linear
lrwxr-xr-x@ 1 noelsaw  staff   80 Jun 30 09:44 loose-ends -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/05-close/loose-ends
drwxr-xr-x@ 3 noelsaw  staff   96 Jun 27 22:34 pdda
lrwxr-xr-x@ 1 noelsaw  staff   77 Jun 30 13:03 phase-qa -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/02-plan/phase-qa
drwxr-xr-x@ 3 noelsaw  staff   96 Jun 18 20:54 ponytail
lrwxr-xr-x@ 1 noelsaw  staff   81 Jun 29 10:09 rabbit-hole -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/04-build/rabbit-hole
lrwxr-xr-x@ 1 noelsaw  staff   76 Jun 21 19:28 read-only -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/utils/read-only
lrwxr-xr-x@ 1 noelsaw  staff   79 Jun 30 13:03 readme-audit -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/repo-health/readme
lrwxr-xr-x@ 1 noelsaw  staff   85 Jun 30 13:03 record-decision -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/05-close/record-decision
lrwxr-xr-x@ 1 noelsaw  staff   75 Jun 30 13:03 relay -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/04-build/relay
lrwxr-xr-x@ 1 noelsaw  staff   74 Jun 22 17:01 relay-to-issue -> /Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/skills/relay-to-issue
lrwxr-xr-x@ 1 noelsaw  staff   69 Jun 20 09:09 relay-xyz -> /Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/skills/relay-xyz
lrwxr-xr-x@ 1 noelsaw  staff   70 Jun 28 20:13 rpr -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/utils/rpr
lrwxr-xr-x@ 1 noelsaw  staff   76 Jun 21 19:28 shakedown -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/utils/shakedown
lrwxr-xr-x@ 1 noelsaw  staff   81 Jun 30 13:03 snapshot -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/repo-health/snapshot
lrwxr-xr-x@ 1 noelsaw  staff   78 Jun 30 13:03 spike-360 -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/02-plan/spike-360
lrwxr-xr-x@ 1 noelsaw  staff   72 Jun 30 13:03 swe -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/02-plan/swe
lrwxr-xr-x@ 1 noelsaw  staff   87 Jun 30 13:03 take-a-step-back -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/01-decide/take-a-step-back
lrwxr-xr-x@ 1 noelsaw  staff   79 Jun 30 11:25 vscode-color -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/utils/vscode-color
lrwxr-xr-x@ 1 noelsaw  staff   79 Jun 30 13:03 worth-it -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/01-decide/worth-it
lrwxr-xr-x@ 1 noelsaw  staff   59 Jun 18 22:49 wpcc -> /Users/noelsaw/Documents/GH Repos/wp-code-check/skills/wpcc
drwxr-xr-x@ 3 noelsaw  staff   96 Jun 30 17:53 xyz

exec
/bin/zsh -lc "nl -ba '/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/skills/relay-xyz/SKILL.md' | sed -n '1,220p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
 succeeded in 0ms:
     1	---
     2	name: relay-xyz
     3	description: >-
     4	  Drive an automated /relay review loop on THIS repo with the shipped
     5	  relay-automation harness (relay-drive.sh + codex-turn.sh / agy-turn.sh /
     6	  poll.sh) rather than improvising the handoff by hand. Use when the operator
     7	  wants to "run an automated relay", "have Codex or agy review this
     8	  end-to-end", "drive a relay to completion headless", "run the relay harness",
     9	  or set up the all-Claude hands-free poll loop — and the working tree is a
    10	  clone of the xyz-3-agents-swarm repo (it ships relay-automation/). /relay
    11	  scaffolds the thread and owns the turn protocol; relay-xyz is the repo-specific
    12	  layer that runs the real scripts. NOT for scaffolding a thread from scratch
    13	  (that is /relay), NOT for repos without relay-automation/.
    14	---
    15	
    16	# relay-xyz — automated relays on the shipped harness
    17	
    18	This repo **already ships** the relay automation. Don't reinvent the CLI handoff turn by turn — call
    19	the scripts under [`relay-automation/`](../../relay-automation/). `/relay` defines the thread format
    20	and turn protocol and scaffolds the dated file; **`relay-xyz` is the thin repo-specific layer that
    21	drives that thread to completion with the shipped supervisor + turn-takers.**
    22	
    23	Use `/relay` to *create* the thread (or reuse one under `relay-system/<date>/`), then `relay-xyz` to
    24	*run* it headless or hands-free.
    25	
    26	## When to use
    27	
    28	- "Run an automated relay" / "drive this relay to completion" / "run the relay harness."
    29	- "Have Codex or agy review `<file>` end-to-end."
    30	- Setting up the all-Claude hands-free `/loop` poll so two Claude windows self-serialize.
    31	- Running automated relays in **two different repos at the same time on one machine** — see
    32	  [Concurrent relays across repos](#concurrent-relays-across-repos-same-machine) (each repo needs its own
    33	  vendored `.xyz/`).
    34	- You have a relay thread (or are about to scaffold one with `/relay`) **and** the working tree is a
    35	  clone of this repo.
    36	
    37	**Not** for: scaffolding a brand-new thread from scratch (that's `/relay`), repos that don't ship
    38	`relay-automation/`, or work that needs a human checkpoint between every turn (use plain `/relay`
    39	manual mode).
    40	
    41	## First-time setup on a new clone or machine (make the skill discoverable)
    42	
    43	This repo keeps its skills in top-level `skills/`, which Claude Code does **not** scan. A session
    44	finds `relay-xyz` only if it's symlinked into `~/.claude/skills/`. A fresh clone or second machine has
    45	no such symlink, so the skill is invisible in **every** session there — the "other VS Code sessions
    46	can't find the relay-xyz files" failure. Fix it **once per clone** (idempotent, self-locating, no
    47	hardcoded path):
    48	
    49	```bash
    50	bash skills/relay-xyz/install.sh   # symlinks this clone's skills/relay-xyz into ~/.claude/skills/
    51	```
    52	
    53	It also replaces a stale/dangling symlink and verifies `find-harness.sh` resolves the harness. The
    54	locator below handles *where the harness scripts live*; this step handles *whether Claude Code can
    55	load the skill at all* — a layer the locator can't reach, since it runs only after the skill loads.
    56	
    57	## Preconditions — locate the harness (bundled locator, never hardcode a path)
    58	
    59	`relay-xyz` ships its own device-agnostic locator, [`find-harness.sh`](find-harness.sh), beside this
    60	skill. It resolves the harness repo (the clone that ships `relay-automation/`) **relative to its own
    61	installed location**, following symlinks — so it works from *any* working directory, including a clone
    62	that has only `relay-system/` thread storage (from `/relay`) but **not** the harness scripts. `$HOME`
    63	and the skill's own symlink are the only anchors; **no machine path is ever hardcoded.** That's what
    64	keeps relay-xyz from "complaining the harness isn't in this repo" when you launch it from a clone
    65	without `relay-automation/` + `bin/tick`.
    66	
    67	Run this first. It finds the locator, exports the harness env, `cd`s into the clone that ships the
    68	harness, and prints a one-glance readiness line:
    69	
    70	```bash
    71	# Find the bundled locator. The skill installs at one of these — all anchored on $HOME or
    72	# the CWD, never an absolute machine path:
    73	for L in "${XYZ_HARNESS:+$XYZ_HARNESS/skills/relay-xyz/find-harness.sh}" \
    74	         "$HOME/.claude/skills/relay-xyz/find-harness.sh" \
    75	         "./.claude/skills/relay-xyz/find-harness.sh" \
    76	         "$(git rev-parse --show-toplevel 2>/dev/null)/skills/relay-xyz/find-harness.sh"; do
    77	  [ -n "$L" ] && [ -x "$L" ] && break
    78	done
    79	[ -x "$L" ] || { echo "relay-xyz: locator not found — set XYZ_HARNESS to your xyz-3-agents-swarm clone"; exit 1; }
    80	
    81	eval "$("$L" --env)"   # exports HARNESS, TICK, TICK_REPO_ROOT, RELAY_HAS_{TICK,CODEX,AGY}
    82	cd "$HARNESS"
    83	"$L" --check           # prints: harness path + which Path-A workers (codex/agy/tick) are on PATH
    84	```
    85	
    86	After this, `$HARNESS` is the harness repo root, `$TICK` is the absolute `bin/tick`, and
    87	`TICK_REPO_ROOT` points `tick` at that clone's event log. The relay/turn scripts self-resolve their
    88	own location (`$(dirname "$BASH_SOURCE")/..`), so invoke them with **repo-relative** paths exactly as
    89	the [headless bring-up section](../../relay-automation/README.md#headless-bring-up-codex--agy) shows.
    90	The relay always operates on **the
    91	harness clone** (its `.tick/` log and guarded git root live there), whatever repo you launched from —
    92	so a clone with only `relay-system/` thread files still drives the real harness next door.
    93	
    94	## Concurrent relays across repos (same machine)
    95	
    96	`relay-drive.sh`/`marathon-drive.sh` hold **one global driver lock per harness clone**
    97	(`.git/relay-driver.lock`, or `.relay-driver.lock` in a vendored `.xyz/`). This is intentional — two
    98	worktrees on the same `ROOT@HEAD` can corrupt git state (GH-42) — but it means **every repo pointed at
    99	the same harness clone shares that one lock**, so their automated relays *serialize*: a second one
   100	blocks (`exit 1`) until the first frees.
   101	
   102	To run relays in **different repos at the same time on one machine**, give each repo its **own harness**
   103	so each gets its own lock, `.tick/`, and worktrees:
   104	
   105	| Install path | Ships | Relay capability | Lock |
   106	|---|---|---|---|
   107	| `install.sh` (tick-only) | `bin/tick` + `src/*.js` | ❌ falls back to the centralized harness | shared (serializes) |
   108	| **`xyz-vendor.sh vendor <repo>`** | full harness (`relay-automation/` + tick + src) into a gitignored `.xyz/` | ✅ per-repo | **own** `.xyz/.relay-driver.lock` |
   109	
   110	So: **`xyz-vendor.sh` (not `install.sh`) is the path to concurrent per-repo relays.** Once a repo has
   111	`.xyz/`, `find-harness.sh` prefers it automatically (env → `.xyz/` → current repo → script-relative), and
   112	`find-harness.sh --check` **warns** when you're in a foreign repo with no `.xyz/` (using the shared
   113	harness) and points you at the vendor command. Two vendored repos each run `relay-drive.sh` from their
   114	own `.xyz/relay-automation/`, holding independent locks — no contention. (Editing the central harness
   115	clone also can't disturb a vendored run, since it uses its own pinned `.xyz/` copy.)
   116	
   117	## The two automated paths
   118	
   119	| Path | One session? | Models | Driver |
   120	|---|---|---|---|
   121	| **A. Headless single-session** | yes — Claude drives both roles | Codex / agy as co-equal headless workers | `relay-drive.sh` + a turn-taker shim |
   122	| **B. Hands-free poll** | no — two live Claude windows | all-Claude | `poll.sh` under `/loop` in each window |
   123	
   124	Path A is the marquee flow — what "have Codex or agy review this for me" means. Path B is the all-Claude
   125	self-serializing loop: no human nudge, no second model.
   126	
   127	### Path A — headless single-session (relay-drive.sh + a shim)
   128	
   129	`relay-drive.sh` is the **supervisor** (round cap, no-progress escalation, reads the file's `STATUS:`
   130	as the terminal signal). The **turn-taker** is `--agent-cmd` — a shipped shim (`codex-turn.sh` or
   131	`agy-turn.sh`) that owns the safety boundary: path-allowlist, commit-bypass guard, **no push**.
   132	Whose-turn is a `tick` relay task, handed off with `tick release --to`.
   133	
   134	End-to-end headless review of an artifact (run after Preconditions — `$TICK` and `$HARNESS` set, CWD
   135	is the harness clone). Choose either worker. The examples below pass `ALLOW_PATHS="$ARTIFACT"`, which
   136	fits a **build/fix** turn; for a pure **review** turn set `ALLOW_PATHS=""` (relay file only) so the
   137	reviewer reports instead of editing — see the env table's `ALLOW_PATHS` row (note that fixed log paths break concurrent same-machine runs; prefer the shims' per-PID default or use per-PID `$$` variables):
   138	
   139	| Worker | Availability check | Handoff target | Env prefix | Shim | Log |
   140	|---|---|---|---|---|---|
   141	| Codex | `"$RELAY_HAS_CODEX" = 1` | `codex` | `CODEX_AGENT=codex ALLOW_PATHS="$ARTIFACT" CODEX_LOG="${TMPDIR:-/tmp}/codex-turn-$$.log"` | `relay-automation/codex-turn.sh` | `${TMPDIR:-/tmp}/codex-turn-$$.log` |
   142	| agy | `"$RELAY_HAS_AGY" = 1` | `agy` | `AGY_AGENT=agy ALLOW_PATHS="$ARTIFACT" AGY_LOG="${TMPDIR:-/tmp}/agy-turn-$$.log"` | `relay-automation/agy-turn.sh` | `${TMPDIR:-/tmp}/agy-turn-$$.log` |
   143	
   144	Codex example:
   145	
   146	```bash
   147	# 0. The reviewer you want must be on PATH (set by the locator).
   148	[ "$RELAY_HAS_CODEX" = 1 ] || { echo "codex not on PATH — use agy or Path B"; exit 1; }
   149	
   150	# 1. Have a relay thread with an embedded "▶ TAKE YOUR TURN" block.
   151	#    Reuse one under relay-system/<date>/, or scaffold a fresh thread with /relay first.
   152	RELAY=relay-system/<date>/<slug>.md
   153	ARTIFACT=<repo-relative-path-the-turn-reviews>     # e.g. skills/relay-xyz/SKILL.md
   154	TASK="RELAY-$(basename "$RELAY" .md)"              # use a per-relay id, not literal RELAY-TURN
   155	
   156	# 2. Seed the relay task and hand the first turn to the Codex agent.
   157	"$TICK" log     task.created "$TASK" --agent claude-a
   158	"$TICK" claim   "$TASK" --agent claude-a --paths "$ARTIFACT"
   159	"$TICK" release "$TASK" --agent claude-a --to codex
   160	
   161	# 3. Drive it. The shim dispatches ONLY when the token's actor == CODEX_AGENT.
   162	CODEX_AGENT=codex ALLOW_PATHS="$ARTIFACT" CODEX_LOG="${TMPDIR:-/tmp}/codex-turn-$$.log" \
   163	relay-automation/relay-drive.sh \
   164	  --relay-file "$RELAY" \
   165	  --relay-task "$TASK" \
   166	  --agent-cmd  relay-automation/codex-turn.sh \
   167	  --round-cap  4
   168	```
   169	
   170	agy example:
   171	
   172	```bash
   173	[ "$RELAY_HAS_AGY" = 1 ] || { echo "agy not on PATH — use codex or Path B"; exit 1; }
   174	
   175	RELAY=relay-system/<date>/<slug>.md
   176	ARTIFACT=<repo-relative-path-the-turn-reviews>
   177	TASK="RELAY-$(basename "$RELAY" .md)"
   178	
   179	"$TICK" log     task.created "$TASK" --agent claude-a
   180	"$TICK" claim   "$TASK" --agent claude-a --paths "$ARTIFACT"
   181	"$TICK" release "$TASK" --agent claude-a --to agy
   182	
   183	AGY_AGENT=agy ALLOW_PATHS="$ARTIFACT" AGY_LOG="${TMPDIR:-/tmp}/agy-turn-$$.log" \
   184	relay-automation/relay-drive.sh \
   185	  --relay-file "$RELAY" \
   186	  --relay-task "$TASK" \
   187	  --agent-cmd  relay-automation/agy-turn.sh \
   188	  --round-cap  4
   189	```
   190	
   191	`$TICK` is absolute, so either worker path still works if CWD drifts.
   192	
   193	**Important — run the shim OUTSIDE the Bash sandbox.** When *you* (Claude Code) drive this, the
   194	`codex` / `agy` subprocess needs the OS keychain + outbound network to authenticate. Claude Code's
   195	Bash sandbox blocks both: `codex` errors (looks like a keychain/login fault, but it's the sandbox),
   196	and `agy -p` **fails silently — exit 0, empty output** (the shim catches this and exits 5, but only
   197	un-sandboxed). Run these Bash calls with `dangerouslyDisableSandbox: true`. (Memory:
   198	`codex-cli-needs-sandbox-disabled`, `agy-antigravity-cli`.)
   199	
   200	#### Inspecting token state, and a one-shot review
   201	
   202	- **Inspect whose-turn mid-drive:** `"$TICK" info <task>` prints the token's `status` / `claimer` /
   203	  `handoff-to` (this is what the driver reads internally). The verb is **`info`**, not `status` —
   204	  `tick status` is not a verb and errors with `unknown verb: status`.
   205	- **Single deliberate review turn:** pass `--review-once` to `relay-drive.sh` to drive exactly ONE
   206	  turn and classify the outcome by exit code, so a correct "changes requested" review is not mistaken
   207	  for a stall:
   208	
   209	  | Exit | Meaning |
   210	  |---|---|
   211	  | `0` | reviewer Approved/Closed |
   212	  | `5` | reviewer completed a turn and handed back **without** approving ("changes requested") — a *successful* single review, not a stall |
   213	  | `3` | genuine stall — the reviewer did nothing (token + STATUS unchanged) |
   214	  | `4` | escalated by design (`STATUS: Escalated`), round cap, or a close mismatch |
   215	
   216	  Without `--review-once` a non-approval handback advances the multi-round loop instead (the producer
   217	  takes the next turn); use `--review-once` when you want exactly one review and a clean exit code.
   218	
   219	- **Review an external / cross-repo artifact (a PR or diff from another repo):** pass
   220	  `--artifact-file <path>` to `relay-drive.sh` to seed it READ-ONLY into the isolated worktree at

codex
I have enough primary-source evidence for the calls. I’m doing one quick graph pass against this repo to avoid missing any existing abstraction surface that plain file reads might understate, then I’ll give the final grading.
mcp: codebase-memory-mcp/list_projects started
mcp: codebase-memory-mcp/list_projects (failed)
user cancelled MCP tool call
codex
One gap keeps recurring: our skills are readable, but the system still depends on humans knowing the names. I’m checking gsd-core’s explicit help/inventory surface so I can separate “better prose conventions” from “actual discoverability tooling.”
exec
/bin/zsh -lc "nl -ba '/Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/help.md' | sed -n '1,220p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
 succeeded in 0ms:
     1	---
     2	name: gsd:help
     3	description: Show available GSD commands and usage guide
     4	argument-hint: "[--brief | --full | <topic> | --brief <topic>]"
     5	allowed-tools:
     6	  - Read
     7	---
     8	<objective>
     9	Display GSD help at the tier the user asked for: brief (one-line refresher), default (one-page tour), full (complete reference), a single topic section, or a compact scoped lookup of one topic (`--brief <topic>`: signature + one-line summary).
    10	
    11	Output ONLY the reference content of the chosen tier. Do NOT add:
    12	- Project-specific analysis
    13	- Git status or file context
    14	- Next-step suggestions
    15	- Any commentary beyond the reference
    16	</objective>
    17	
    18	<execution_context>
    19	@~/.claude/gsd-core/workflows/help.md
    20	</execution_context>
    21	
    22	<context>
    23	Arguments: $ARGUMENTS
    24	</context>
    25	
    26	<process>
    27	Follow ~/.claude/gsd-core/workflows/help.md with $ARGUMENTS.
    28	</process>

exec
/bin/zsh -lc "nl -ba '/Users/noelsaw/Documents/GH Repos/gsd-core/docs/INVENTORY.md' | sed -n '1,180p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-34200-12291
 succeeded in 0ms:
     1	# GSD Shipped Surface Inventory
     2	
     3	> Authoritative roster of every shipped GSD surface: commands, agents, workflows, references, CLI modules, and hooks. Where the broad docs (AGENTS.md, COMMANDS.md, ARCHITECTURE.md, CLI-TOOLS.md) diverge from the filesystem, treat this file and the repository tree itself as the source of truth.
     4	
     5	## How To Use This File
     6	
     7	- The machine-readable roster lives in `docs/INVENTORY-MANIFEST.json` (regenerated by `scripts/gen-inventory-manifest.cjs --write`). For live counts, run `ls agents/gsd-*.md | wc -l` etc. against the checkout.
     8	- This file enumerates every shipped surface across all six families (agents, commands, workflows, references, CLI modules, hooks). Broad docs may render narrative or curated subsets; when they disagree with the filesystem, this file and the directory listings are authoritative.
     9	- New surfaces should land here first, then propagate to the broad docs. The drift-control tests in `tests/inventory-manifest-sync.test.cjs`, `tests/commands-doc-parity.test.cjs`, `tests/agents-doc-parity.test.cjs`, `tests/cli-modules-doc-parity.test.cjs`, `tests/hooks-doc-parity.test.cjs`, and `tests/command-count-sync.test.cjs` anchor the roster contents against the filesystem.
    10	
    11	This is the authoritative roster of every shipped GSD Core surface. See the [docs index](README.md) to navigate by topic.
    12	
    13	---
    14	
    15	## Agents
    16	
    17	Full roster at `agents/gsd-*.md`. The "Primary doc" column flags whether [`docs/AGENTS.md`](AGENTS.md) carries a full role card (*primary*), a short stub in the "Advanced and Specialized Agents" section (*advanced stub*), or no coverage (*inventory only*).
    18	
    19	| Agent | Role (one line) | Spawned by | Primary doc |
    20	|-------|-----------------|------------|-------------|
    21	| gsd-project-researcher | Researches domain ecosystem before roadmap creation (stack, features, architecture, pitfalls). | `/gsd-new-project`, `/gsd-new-milestone` | primary |
    22	| gsd-phase-researcher | Researches implementation approach for a specific phase before planning. | `/gsd-plan-phase` | primary |
    23	| gsd-ui-researcher | Produces UI design contracts for frontend phases. | `/gsd-ui-phase` | primary |
    24	| gsd-assumptions-analyzer | Produces evidence-backed assumptions for discuss-phase (assumptions mode). | `discuss-phase-assumptions` workflow | primary |
    25	| gsd-advisor-researcher | Researches a single gray-area decision during discuss-phase advisor mode. | `discuss-phase` workflow (advisor mode) | primary |
    26	| gsd-research-synthesizer | Combines parallel researcher outputs into a unified SUMMARY.md. | `/gsd-new-project` | primary |
    27	| gsd-planner | Creates executable phase plans with task breakdown and goal-backward verification. | `/gsd-plan-phase`, `/gsd-quick` | primary |
    28	| gsd-roadmapper | Creates project roadmaps with phase breakdown and requirement mapping. | `/gsd-new-project` | primary |
    29	| gsd-executor | Executes GSD plans with atomic commits and deviation handling. | `/gsd-execute-phase`, `/gsd-quick` | primary |
    30	| gsd-plan-checker | Verifies plans will achieve phase goals (8 verification dimensions). | `/gsd-plan-phase` (verification loop) | primary |
    31	| gsd-integration-checker | Verifies cross-phase integration and end-to-end flows. | `/gsd-audit-milestone` | primary |
    32	| gsd-ui-checker | Validates UI-SPEC.md design contracts against quality dimensions. | `/gsd-ui-phase` (validation loop) | primary |
    33	| gsd-verifier | Verifies phase goal achievement through goal-backward analysis. | `/gsd-execute-phase` | primary |
    34	| gsd-nyquist-auditor | Fills Nyquist validation gaps by generating tests. | `/gsd-validate-phase` | primary |
    35	| gsd-ui-auditor | Retroactive 6-pillar visual audit of implemented frontend code. | `/gsd-ui-review` | primary |
    36	| gsd-codebase-mapper | Explores codebase and writes structured analysis documents. | `/gsd-map-codebase` | primary |
    37	| gsd-debugger | Investigates bugs using scientific method with persistent state. | `/gsd-debug`, `/gsd-verify-work` | primary |
    38	| gsd-user-profiler | Scores developer behavior across 8 dimensions. | `/gsd-profile-user` | primary |
    39	| gsd-doc-writer | Writes and updates project documentation. | `/gsd-docs-update` | primary |
    40	| gsd-doc-verifier | Verifies factual claims in generated documentation. | `/gsd-docs-update` | primary |
    41	| gsd-security-auditor | Verifies threat mitigations from PLAN.md threat model. | `/gsd-secure-phase` | primary |
    42	| gsd-pattern-mapper | Maps new files to closest existing analogs; writes PATTERNS.md for the planner. | `/gsd-plan-phase` (between research and planning) | advanced stub |
    43	| gsd-debug-session-manager | Runs the full `/gsd-debug` checkpoint-and-continuation loop in isolated context so main stays lean. | `/gsd-debug` | advanced stub |
    44	| gsd-code-reviewer | Reviews source files for bugs, security issues, and code-quality problems; produces REVIEW.md. | `/gsd-code-review` | advanced stub |
    45	| gsd-code-fixer | Applies fixes to REVIEW.md findings with atomic per-fix commits; produces REVIEW-FIX.md. | `/gsd-code-review --fix` | advanced stub |
    46	| gsd-ai-researcher | Researches a chosen AI framework's official docs into implementation-ready guidance (AI-SPEC.md §3–§4b). | `/gsd-ai-integration-phase` | advanced stub |
    47	| gsd-domain-researcher | Surfaces domain-expert evaluation criteria and failure modes for an AI system (AI-SPEC.md §1b). | `/gsd-ai-integration-phase` | advanced stub |
    48	| gsd-eval-planner | Designs structured evaluation strategy for an AI phase (AI-SPEC.md §5–§7). | `/gsd-ai-integration-phase` | advanced stub |
    49	| gsd-eval-auditor | Retroactive audit of an AI phase's evaluation coverage; produces EVAL-REVIEW.md (COVERED/PARTIAL/MISSING). | `/gsd-eval-review` | advanced stub |
    50	| gsd-framework-selector | ≤6-question interactive decision matrix that scores and recommends an AI/LLM framework. | `/gsd-ai-integration-phase` | advanced stub |
    51	| gsd-intel-updater | Writes structured intel files (`.planning/intel/*.json`) used as a queryable codebase knowledge base. | `/gsd-map-codebase --query` | advanced stub |
    52	| gsd-doc-classifier | Classifies a single planning document as ADR, PRD, SPEC, DOC, or UNKNOWN; spawned in parallel to process the doc corpus. | `/gsd-ingest-docs` | advanced stub |
    53	| gsd-doc-synthesizer | Synthesizes classified planning docs into a single consolidated context with precedence rules, cycle detection, and three-bucket conflicts report. | `/gsd-ingest-docs` | advanced stub |
    54	| gsd-mempalace-curator | Ship-time MemPalace curation — diary entry, cross-project tunnel proposals, wing-scoped sync pruning, and extract-learnings → KG mirroring with provenance. | MemPalace capability at `ship:post` | advanced stub |
    55	
    56	**Coverage note.** `docs/AGENTS.md` gives full role cards for the primary agents plus concise stubs for the advanced agents. The Agent Tool Permissions Summary in that file covers only the primary agents; the advanced agents' tool lists are captured in their per-agent frontmatter in `agents/gsd-*.md`.
    57	
    58	---
    59	
    60	## Commands
    61	
    62	Full roster at `commands/gsd/*.md`. The groupings below mirror `docs/COMMANDS.md` section order; each row carries the command name, a one-line role derived from the command's frontmatter `description:`, and a link to the source file. `tests/command-count-sync.test.cjs` locks the count against the filesystem.
    63	
    64	### Namespace Meta-Skills
    65	
    66	These six routers are descriptor-only entries that the model picks first; the body of each contains a routing table that points at the correct concrete sub-skill. They exist to keep the eager skill-listing token cost low while the full surface remains reachable. See [#2792](https://github.com/open-gsd/gsd-core/issues/2792) for the rationale; the routing tables target the post-[#2790](https://github.com/open-gsd/gsd-core/issues/2790) consolidated surface.
    67	
    68	| Command | Role | Source |
    69	|---------|------|--------|
    70	| `/gsd-workflow` | Phase pipeline router — discuss / plan / execute / verify / phase / progress / next. | [commands/gsd/ns-workflow.md](../commands/gsd/ns-workflow.md) |
    71	| `/gsd-project` | Project lifecycle router — milestones, audits, summary. | [commands/gsd/ns-project.md](../commands/gsd/ns-project.md) |
    72	| `/gsd-quality` | Quality-gate router — code review, debug, audit, security, eval, ui. | [commands/gsd/ns-review.md](../commands/gsd/ns-review.md) |
    73	| `/gsd-context` | Codebase-intelligence router — map, graphify, docs, learnings. | [commands/gsd/ns-context.md](../commands/gsd/ns-context.md) |
    74	| `/gsd-manage` | Management router — config, workspace, workstreams, thread, update, ship, inbox. | [commands/gsd/ns-manage.md](../commands/gsd/ns-manage.md) |
    75	| `/gsd-ideate` | Exploration & capture router — explore, sketch, spike, spec, capture. | [commands/gsd/ns-ideate.md](../commands/gsd/ns-ideate.md) |
    76	
    77	### Core Workflow
    78	
    79	| Command | Role | Source |
    80	|---------|------|--------|
    81	| `/gsd-new-project` | Initialize a new project with deep context gathering and PROJECT.md. | [commands/gsd/new-project.md](../commands/gsd/new-project.md) |
    82	| `/gsd-workspace` | Manage GSD workspaces — create (`--new`), list (`--list`), or remove (`--remove`) isolated workspace environments. | [commands/gsd/workspace.md](../commands/gsd/workspace.md) |
    83	| `/gsd-discuss-phase` | Gather phase context through adaptive questioning before planning. | [commands/gsd/discuss-phase.md](../commands/gsd/discuss-phase.md) |
    84	| `/gsd-mvp-phase` | Plan a phase as a vertical MVP slice — user story, SPIDR splitting, then plan-phase. | [commands/gsd/mvp-phase.md](../commands/gsd/mvp-phase.md) |
    85	| `/gsd-spec-phase` | Socratic spec refinement producing a SPEC.md with falsifiable requirements. | [commands/gsd/spec-phase.md](../commands/gsd/spec-phase.md) |
    86	| `/gsd-ui-phase` | Generate UI design contract (UI-SPEC.md) for frontend phases. | [commands/gsd/ui-phase.md](../commands/gsd/ui-phase.md) |
    87	| `/gsd-ai-integration-phase` | Generate AI design contract (AI-SPEC.md) via framework selection, research, and eval planning. | [commands/gsd/ai-integration-phase.md](../commands/gsd/ai-integration-phase.md) |
    88	| `/gsd-plan-phase` | Create detailed phase plan (PLAN.md) with verification loop. | [commands/gsd/plan-phase.md](../commands/gsd/plan-phase.md) |
    89	| `/gsd-plan-review-convergence` | Cross-AI plan convergence loop — replan with review feedback until no HIGH concerns or actionable non-HIGH findings remain (max 3 cycles). | [commands/gsd/plan-review-convergence.md](../commands/gsd/plan-review-convergence.md) |
    90	| `/gsd-ultraplan-phase` | [BETA] Offload plan phase to Claude Code's ultraplan cloud — drafts remotely, review in browser, import back via `/gsd-import`. Claude Code only. | [commands/gsd/ultraplan-phase.md](../commands/gsd/ultraplan-phase.md) |
    91	| `/gsd-spike` | Rapidly spike an idea with throwaway experiments; use `--wrap-up` to package findings as a persistent skill. | [commands/gsd/spike.md](../commands/gsd/spike.md) |
    92	| `/gsd-sketch` | Rapidly sketch UI/design ideas using throwaway HTML mockups; use `--wrap-up` to package findings. | [commands/gsd/sketch.md](../commands/gsd/sketch.md) |
    93	| `/gsd-execute-phase` | Execute all plans in a phase with wave-based parallelization. | [commands/gsd/execute-phase.md](../commands/gsd/execute-phase.md) |
    94	| `/gsd-verify-work` | Validate built features through conversational UAT with auto-diagnosis. | [commands/gsd/verify-work.md](../commands/gsd/verify-work.md) |
    95	| `/gsd-ship` | Create PR, run review, and prepare for merge after verification. | [commands/gsd/ship.md](../commands/gsd/ship.md) |
    96	| `/gsd-fast` | Execute a trivial task inline — no subagents, no planning overhead. | [commands/gsd/fast.md](../commands/gsd/fast.md) |
    97	| `/gsd-quick` | Execute a quick task with GSD guarantees (atomic commits, state tracking) but skip optional agents. | [commands/gsd/quick.md](../commands/gsd/quick.md) |
    98	| `/gsd-ui-review` | Retroactive 6-pillar visual audit of implemented frontend code. | [commands/gsd/ui-review.md](../commands/gsd/ui-review.md) |
    99	| `/gsd-code-review` | Review source files changed during a phase for bugs, security, and code-quality problems; use `--fix` to auto-apply findings. | [commands/gsd/code-review.md](../commands/gsd/code-review.md) |
   100	| `/gsd-eval-review` | Retroactively audit an executed AI phase's evaluation coverage; produces EVAL-REVIEW.md. | [commands/gsd/eval-review.md](../commands/gsd/eval-review.md) |
   101	
   102	### Phase & Milestone Management
   103	
   104	| Command | Role | Source |
   105	|---------|------|--------|
   106	| `/gsd-phase` | CRUD for phases — add (default), insert (`--insert`), remove (`--remove`), or edit (`--edit`) phases in ROADMAP.md. | [commands/gsd/phase.md](../commands/gsd/phase.md) |
   107	| `/gsd-add-tests` | Generate tests for a completed phase based on UAT criteria and implementation. | [commands/gsd/add-tests.md](../commands/gsd/add-tests.md) |
   108	| `/gsd-validate-phase` | Retroactively audit and fill Nyquist validation gaps for a completed phase. | [commands/gsd/validate-phase.md](../commands/gsd/validate-phase.md) |
   109	| `/gsd-secure-phase` | Retroactively verify threat mitigations for a completed phase. | [commands/gsd/secure-phase.md](../commands/gsd/secure-phase.md) |
   110	| `/gsd-audit-milestone` | Audit milestone completion against original intent before archiving. | [commands/gsd/audit-milestone.md](../commands/gsd/audit-milestone.md) |
   111	| `/gsd-audit-uat` | Cross-phase audit of all outstanding UAT and verification items. | [commands/gsd/audit-uat.md](../commands/gsd/audit-uat.md) |
   112	| `/gsd-audit-fix` | Autonomous audit-to-fix pipeline — find issues, classify, fix, test, commit. | [commands/gsd/audit-fix.md](../commands/gsd/audit-fix.md) |
   113	| `/gsd-complete-milestone` | Archive completed milestone and prepare for next version. | [commands/gsd/complete-milestone.md](../commands/gsd/complete-milestone.md) |
   114	| `/gsd-new-milestone` | Start a new milestone cycle — update PROJECT.md and route to requirements. | [commands/gsd/new-milestone.md](../commands/gsd/new-milestone.md) |
   115	| `/gsd-milestone-summary` | Generate a comprehensive project summary from milestone artifacts. | [commands/gsd/milestone-summary.md](../commands/gsd/milestone-summary.md) |
   116	| `/gsd-cleanup` | Archive accumulated phase directories from completed milestones. | [commands/gsd/cleanup.md](../commands/gsd/cleanup.md) |
   117	| `/gsd-manager` | Interactive command center for managing multiple phases from one terminal. | [commands/gsd/manager.md](../commands/gsd/manager.md) |
   118	| `/gsd-workstreams` | Manage parallel workstreams — list, create, switch, status, progress, complete, resume. | [commands/gsd/workstreams.md](../commands/gsd/workstreams.md) |
   119	| `/gsd-autonomous` | Run all remaining phases autonomously — discuss → plan → execute per phase. | [commands/gsd/autonomous.md](../commands/gsd/autonomous.md) |
   120	| `/gsd-undo` | Safe git revert — roll back phase or plan commits using the phase manifest. | [commands/gsd/undo.md](../commands/gsd/undo.md) |
   121	
   122	### Session & Navigation
   123	
   124	| Command | Role | Source |
   125	|---------|------|--------|
   126	| `/gsd:next` | State-aware smart-entry launcher — reads project state, shows a contextual menu, and dispatches one existing GSD command. | [commands/gsd/next.md](../commands/gsd/next.md) |
   127	| `/gsd-progress` | Check project progress, show context, and route to next action; use `--next` to advance automatically or `--do` to run a freeform task. | [commands/gsd/progress.md](../commands/gsd/progress.md) |
   128	| `/gsd-capture` | Capture ideas, tasks, notes, and seeds — todo (default), `--note`, `--backlog`, `--seed`, or `--list` pending todos. | [commands/gsd/capture.md](../commands/gsd/capture.md) |
   129	| `/gsd-stats` | Display project statistics — phases, plans, requirements, git metrics, timeline. | [commands/gsd/stats.md](../commands/gsd/stats.md) |
   130	| `/gsd-pause-work` | Create context handoff when pausing work mid-phase. | [commands/gsd/pause-work.md](../commands/gsd/pause-work.md) |
   131	| `/gsd-resume-work` | Resume work from previous session with full context restoration. | [commands/gsd/resume-work.md](../commands/gsd/resume-work.md) |
   132	| `/gsd-explore` | Socratic ideation and idea routing — think through ideas before committing. | [commands/gsd/explore.md](../commands/gsd/explore.md) |
   133	| `/gsd-review-backlog` | Review and promote backlog items to active milestone. | [commands/gsd/review-backlog.md](../commands/gsd/review-backlog.md) |
   134	| `/gsd-thread` | Manage persistent context threads for cross-session work. | [commands/gsd/thread.md](../commands/gsd/thread.md) |
   135	
   136	### Codebase Intelligence
   137	
   138	| Command | Role | Source |
   139	|---------|------|--------|
   140	| `/gsd-map-codebase` | Analyze codebase with parallel mapper agents; use `--fast` for lightweight scan or `--query` for intel queries. | [commands/gsd/map-codebase.md](../commands/gsd/map-codebase.md) |
   141	| `/gsd-graphify` | Build, query, and inspect the project knowledge graph in `.planning/graphs/`. | [commands/gsd/graphify.md](../commands/gsd/graphify.md) |
   142	| `/gsd-extract-learnings` | Extract decisions, lessons, patterns, and surprises from completed phase artifacts. | [commands/gsd/extract-learnings.md](../commands/gsd/extract-learnings.md) |
   143	| `/gsd-mempalace-recall` | Recall prior decisions, patterns, and surprises from MemPalace into MEMORY-RECALL.md before planning. | [commands/gsd/mempalace-recall.md](../commands/gsd/mempalace-recall.md) |
   144	| `/gsd-mempalace-capture` | File a phase artifact (CONTEXT/PLAN/SUMMARY) verbatim into MemPalace and mirror decision facts into its temporal KG. | [commands/gsd/mempalace-capture.md](../commands/gsd/mempalace-capture.md) |
   145	
   146	### Review, Debug & Recovery
   147	
   148	| Command | Role | Source |
   149	|---------|------|--------|
   150	| `/gsd-review` | Request cross-AI peer review of phase plans from external AI CLIs. | [commands/gsd/review.md](../commands/gsd/review.md) |
   151	| `/gsd-debug` | Systematic debugging with persistent state across context resets. | [commands/gsd/debug.md](../commands/gsd/debug.md) |
   152	| `/gsd-forensics` | Post-mortem investigation for failed GSD workflows — analyzes git, artifacts, state. | [commands/gsd/forensics.md](../commands/gsd/forensics.md) |
   153	| `/gsd-health` | Diagnose planning directory health and optionally repair issues. | [commands/gsd/health.md](../commands/gsd/health.md) |
   154	| `/gsd-import` | Ingest external plans with conflict detection against project decisions. | [commands/gsd/import.md](../commands/gsd/import.md) |
   155	| `/gsd-inbox` | Triage and review all open GitHub issues and PRs against project templates. | [commands/gsd/inbox.md](../commands/gsd/inbox.md) |
   156	
   157	### Docs, Profile & Utilities
   158	
   159	| Command | Role | Source |
   160	|---------|------|--------|
   161	| `/gsd-docs-update` | Generate or update project documentation verified against the codebase. | [commands/gsd/docs-update.md](../commands/gsd/docs-update.md) |
   162	| `/gsd-ingest-docs` | Scan a repo for mixed ADRs/PRDs/SPECs/DOCs and bootstrap or merge the full `.planning/` setup with classification, synthesis, and conflicts report. | [commands/gsd/ingest-docs.md](../commands/gsd/ingest-docs.md) |
   163	| `/gsd-profile-user` | Generate developer behavioral profile and Claude-discoverable artifacts. | [commands/gsd/profile-user.md](../commands/gsd/profile-user.md) |
   164	| `/gsd-settings` | Configure GSD workflow toggles and model profile. | [commands/gsd/settings.md](../commands/gsd/settings.md) |
   165	| `/gsd-config` | Configure GSD settings — workflow toggles (default), advanced knobs (`--advanced`), integrations (`--integrations`), or model profile (`--profile`). | [commands/gsd/config.md](../commands/gsd/config.md) |
   166	| `/gsd-pr-branch` | Create a clean PR branch by filtering out `.planning/` commits. | [commands/gsd/pr-branch.md](../commands/gsd/pr-branch.md) |
   167	| `/gsd-surface` | Toggle which skills are surfaced — apply a profile, list, or disable a cluster without reinstall. | [commands/gsd/surface.md](../commands/gsd/surface.md) |
   168	| `/gsd-update` | Update GSD to latest version; use `--sync` to sync skills across runtimes or `--reapply` to reapply local patches. | [commands/gsd/update.md](../commands/gsd/update.md) |
   169	| `/gsd-help` | Show available GSD commands and usage guide. | [commands/gsd/help.md](../commands/gsd/help.md) |
   170	
   171	---
   172	
   173	## Workflows
   174	
   175	Full roster at `gsd-core/workflows/*.md`. Workflows are thin orchestrators that commands reference internally; most are not read directly by end users. Rows below map each workflow file to its role (derived from the `<purpose>` block) and, where applicable, to the command that invokes it.
   176	
   177	| Workflow | Role | Invoked by |
   178	|----------|------|------------|
   179	| `add-backlog.md` | Add a backlog item to ROADMAP.md using 999.x numbering. | `/gsd-capture --backlog` |
   180	| `add-phase.md` | Add a new integer phase to the end of the current milestone in the roadmap. | `/gsd-phase` (default) |

codex
**ANSWER**
My Phase 2 calls are: `1 ADAPT`, `2 ADAPT`, `3 SKIP`, `4 ADOPT`, `5 ADAPT`. The highest-ROI move is not a gsd-style full architecture port; it is a small manifest/index layer plus one blocking hook pattern borrowed from gsd/XYZ.

**FINDINGS**
- `[Should] 1. Skill ↔ agent ↔ command ↔ hook composition`
  Gap: gsd’s composition chain is real and already grounded in Phase 0, but Rebalance’s current local surface is still mostly separate skill/command/hook files without a comparable local map from entrypoint to runtime behavior [PROJECT/2-WORKING/GSD-CORE-PATTERN-REVIEW.md:321-346; .claude/commands/ask_self.md:1-23; .claude/commands/reingest.md:1-28; .claude/settings.json:1-117].
  `ADAPT` · target `both` · effort `S` · payoff `2`
  Why: the boundary naming helps discoverability and ownership, but copying gsd’s full workflow/agent stack would be ceremony at your current scale.
  First step: make a small inventory for the real orchestrated flows (`welcome`, `ask_self`/`reingest`, `relay-xyz`) listing `skill -> command/tool -> hook -> owner`.

- `[Should] 2. The capabilities layer`
  Gap: Phase 0 was right that Reb/XYZ have no equivalent to gsd’s composed registry/trust abstraction, and gsd’s version is substantive rather than cosmetic: one composed registry, collision handling, inactive-until-consented project overlays, and fail-closed gate behavior [PROJECT/2-WORKING/GSD-CORE-PATTERN-REVIEW.md:328-346; /Users/noelsaw/Documents/GH Repos/gsd-core/docs/explanation/capability-overlay-model.md:16-45,111-180,184-236; /Users/noelsaw/Documents/GH Repos/gsd-core/docs/explanation/capability-trust-model.md:14-39,143-163,241-282].
  `ADAPT` · target `both` · effort `M` · payoff `3`
  Why: there is a real ownership/executable-surface gap here, but a 39-capability overlay system is premature unless you are actually composing many bundles across many runtimes.
  First step: introduce a minimal bundle manifest for high-risk bundles only: `id`, `owner`, `skills`, `commands`, `hooks`, `executables`, `requires`, then generate a read-only index from it.

- `[Pass] 3. Cross-runtime portability via installer`
  Gap: gsd’s installer exists because each runtime needs different schemas, paths, and command syntax, and XYZ does have a real machine-local-vs-vendored harness seam [/Users/noelsaw/Documents/GH Repos/gsd-core/docs/how-to/install-on-your-runtime.md:9-13; /Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/skills/relay-xyz/SKILL.md:41-55,94-115].
  `SKIP` · target `XYZ` · effort `L` · payoff `2`
  Why: this is install/versioning/release-channel work, which this review explicitly excludes; it belongs in `GH-102` seam #2, not in Family B grading.
  GH-102 pointer: use gsd’s installer as reference material when you review the vendored-vs-machine-local harness channel there.

- `[Should] 4. Hook catalog`
  Gap: Rebalance’s current PDDA hooks are advisory-only post-edit/stop scans that always exit `0`, while gsd and XYZ both use pre-tool guards to block unsafe behavior before execution [utils/pdda/pdda-edit-doc-hook.sh:12-13,42-55; utils/pdda/pdda-stop-doc-health.sh:7-20; /Users/noelsaw/Documents/GH Repos/gsd-core/hooks/hooks.json:11-38; /Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/hooks/relay-xyz-guard.sh:20-23,87-108].
  `ADOPT` · target `Reb` · effort `S` · payoff `3`
  Why: one blocking guard on a high-risk workflow is a cheap, concrete win; another warn-only lint pass is not.
  First step: add a `PreToolUse` guard that blocks direct leaf ingest/refresh shell entrypoints and routes the agent back to `refresh_index`/`doctor`/the orchestrator surface.

- `[Nit] 5. Skill authoring conventions`
  Gap: your skill corpus already has decent frontmatter/trigger discipline by convention, but discoverability still depends too much on README memory and skill names; gsd adds explicit help and authoritative inventory surfaces [/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/README.md:206-217; .claude/skills/welcome/SKILL.md:1-4; /Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/help.md:1-27; /Users/noelsaw/Documents/GH Repos/gsd-core/docs/INVENTORY.md:1-11,60-169].
  `ADAPT` · target `both` · effort `S` · payoff `2`
  Why: the prose conventions are already good enough; the missing piece is generated discoverability, not stricter writing rules.
  First step: generate a lightweight `skills help` index from existing frontmatter listing skill name, one trigger sentence, and owner/runtime.

**RECOMMENDATION**
Do Phase 2 as `hook-first + lightweight bundle manifest/index`, and explicitly leave installer portability to `GH-102`.
tokens used
122,098
**ANSWER**
My Phase 2 calls are: `1 ADAPT`, `2 ADAPT`, `3 SKIP`, `4 ADOPT`, `5 ADAPT`. The highest-ROI move is not a gsd-style full architecture port; it is a small manifest/index layer plus one blocking hook pattern borrowed from gsd/XYZ.

**FINDINGS**
- `[Should] 1. Skill ↔ agent ↔ command ↔ hook composition`
  Gap: gsd’s composition chain is real and already grounded in Phase 0, but Rebalance’s current local surface is still mostly separate skill/command/hook files without a comparable local map from entrypoint to runtime behavior [PROJECT/2-WORKING/GSD-CORE-PATTERN-REVIEW.md:321-346; .claude/commands/ask_self.md:1-23; .claude/commands/reingest.md:1-28; .claude/settings.json:1-117].
  `ADAPT` · target `both` · effort `S` · payoff `2`
  Why: the boundary naming helps discoverability and ownership, but copying gsd’s full workflow/agent stack would be ceremony at your current scale.
  First step: make a small inventory for the real orchestrated flows (`welcome`, `ask_self`/`reingest`, `relay-xyz`) listing `skill -> command/tool -> hook -> owner`.

- `[Should] 2. The capabilities layer`
  Gap: Phase 0 was right that Reb/XYZ have no equivalent to gsd’s composed registry/trust abstraction, and gsd’s version is substantive rather than cosmetic: one composed registry, collision handling, inactive-until-consented project overlays, and fail-closed gate behavior [PROJECT/2-WORKING/GSD-CORE-PATTERN-REVIEW.md:328-346; /Users/noelsaw/Documents/GH Repos/gsd-core/docs/explanation/capability-overlay-model.md:16-45,111-180,184-236; /Users/noelsaw/Documents/GH Repos/gsd-core/docs/explanation/capability-trust-model.md:14-39,143-163,241-282].
  `ADAPT` · target `both` · effort `M` · payoff `3`
  Why: there is a real ownership/executable-surface gap here, but a 39-capability overlay system is premature unless you are actually composing many bundles across many runtimes.
  First step: introduce a minimal bundle manifest for high-risk bundles only: `id`, `owner`, `skills`, `commands`, `hooks`, `executables`, `requires`, then generate a read-only index from it.

- `[Pass] 3. Cross-runtime portability via installer`
  Gap: gsd’s installer exists because each runtime needs different schemas, paths, and command syntax, and XYZ does have a real machine-local-vs-vendored harness seam [/Users/noelsaw/Documents/GH Repos/gsd-core/docs/how-to/install-on-your-runtime.md:9-13; /Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/skills/relay-xyz/SKILL.md:41-55,94-115].
  `SKIP` · target `XYZ` · effort `L` · payoff `2`
  Why: this is install/versioning/release-channel work, which this review explicitly excludes; it belongs in `GH-102` seam #2, not in Family B grading.
  GH-102 pointer: use gsd’s installer as reference material when you review the vendored-vs-machine-local harness channel there.

- `[Should] 4. Hook catalog`
  Gap: Rebalance’s current PDDA hooks are advisory-only post-edit/stop scans that always exit `0`, while gsd and XYZ both use pre-tool guards to block unsafe behavior before execution [utils/pdda/pdda-edit-doc-hook.sh:12-13,42-55; utils/pdda/pdda-stop-doc-health.sh:7-20; /Users/noelsaw/Documents/GH Repos/gsd-core/hooks/hooks.json:11-38; /Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/relay-automation/hooks/relay-xyz-guard.sh:20-23,87-108].
  `ADOPT` · target `Reb` · effort `S` · payoff `3`
  Why: one blocking guard on a high-risk workflow is a cheap, concrete win; another warn-only lint pass is not.
  First step: add a `PreToolUse` guard that blocks direct leaf ingest/refresh shell entrypoints and routes the agent back to `refresh_index`/`doctor`/the orchestrator surface.

- `[Nit] 5. Skill authoring conventions`
  Gap: your skill corpus already has decent frontmatter/trigger discipline by convention, but discoverability still depends too much on README memory and skill names; gsd adds explicit help and authoritative inventory surfaces [/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/README.md:206-217; .claude/skills/welcome/SKILL.md:1-4; /Users/noelsaw/Documents/GH Repos/gsd-core/commands/gsd/help.md:1-27; /Users/noelsaw/Documents/GH Repos/gsd-core/docs/INVENTORY.md:1-11,60-169].
  `ADAPT` · target `both` · effort `S` · payoff `2`
  Why: the prose conventions are already good enough; the missing piece is generated discoverability, not stricter writing rules.
  First step: generate a lightweight `skills help` index from existing frontmatter listing skill name, one trigger sentence, and owner/runtime.

**RECOMMENDATION**
Do Phase 2 as `hook-first + lightweight bundle manifest/index`, and explicitly leave installer portability to `GH-102`.

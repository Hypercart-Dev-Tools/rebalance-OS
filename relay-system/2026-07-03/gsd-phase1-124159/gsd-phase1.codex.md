Reading additional input from stdin...
OpenAI Codex v0.139.0
--------
workdir: /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-21302-28772
model: gpt-5.4
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019f2980-92c8-75c3-8470-04bc15c9bc65
--------
user
You are an INDEPENDENT advisor in a one-shot cross-model consult. Another model is answering the SAME question separately and a coordinator will reconcile both answers, so give your own honest, specific read — do not hedge toward a consensus you cannot see. Read any repo files the question references (cite file:line). Respond with: (1) a short direct ANSWER; (2) graded FINDINGS — [Blocker]/[Should]/[Nit]/[Pass] — where applicable; (3) a one-line RECOMMENDATION. You are ADVISORY ONLY: output your analysis as text; do not rely on writing files (you are running in a throwaway copy).

=== CONSULT QUESTION ===
You are running Phase 1 of a project review doc that lives in your current worktree at:

    PROJECT/2-WORKING/GSD-CORE-PATTERN-REVIEW.md

Read that file first — it has the full frontmatter, the grading rubric ("## Grading rubric"), the
"## Phase 1 — Family A: phase-loop & context engineering" section with its candidate patterns, and
the already-completed "#### Phase 0 — Findings" block (grounded inventory + counterpart map you
should build on, not re-derive from scratch). This prompt only summarizes it; the doc is authoritative.

## The task

Grade each Phase 1 candidate pattern (Family A: phase-loop & context engineering) with exactly one
call: **ADOPT**, **ADAPT**, or **SKIP**, per the doc's Grading rubric:
- ADOPT — clear gap, cheap to add, high payoff. Name the target + a concrete first step.
- ADAPT — good idea, but our shape differs; take the concept, not the implementation. Name what to change.
- SKIP — already covered here, or payoff doesn't justify cost, or out of scope. State which.

Every call must carry: **target** (XYZ / Reb / both), **effort** (S/M/L), **payoff** (1-3), and a
one-line **why**. Do NOT skip stating the gap before making a call — an ADOPT with no stated gap is
invalid per this review's invariants.

## The five patterns to grade (from the doc's Phase 1 section)

1. **Explicit 5-step loop** (Discuss→Plan→Execute→Verify→Ship) vs. PDDA's 1-INBOX→2-WORKING→3-DONE
   lifecycle + per-phase QA checklists. Gap to resolve: does Rebalance have an explicit *Discuss*
   (decisions-before-plan) and *Verify* (walk-what-was-built) step, or are they implicit/missing?
2. **Fresh-context subagents for heavy work** vs. Rebalance's Agent/Explore subagents + XYZ tick
   lanes + `consult`. Gap to resolve: does gsd have a discipline (context budget, hand-back contract
   like `SUMMARY.md`) we lack?
3. **Persistent cross-session artifacts** (`STATE.md`, `CONTEXT.md`) vs. the `snapshot` skill, PDDA
   docs, `.claude` memory. Gap to resolve: is there a durable *project state* file our snapshot
   doesn't cover?
4. **Parallel execution waves** vs. XYZ concurrent lanes (`tick`) / relay / marathon DAG ordering.
   Gap to resolve: does gsd add anything over XYZ's claim/heartbeat model? (Note: this review's own
   Execution Plan section already found that XYZ's lane model requires non-overlapping paths, which
   this very doc's four phases violate by sharing one file — factor that into the grade.)
5. **Verify-before-done gate** (diagnose & fix before declaring done) vs. `doctor`+`pytest`+`pdda`
   run + `loose-ends`/`phase-qa` skills. Gap to resolve: is there a verify-loop shape (e.g. an
   automated verifier *agent* producing a routable report, not just a checklist) worth borrowing?

## Where to read

**gsd-core** (external repo, read by its absolute checkout path — the Phase 0 Findings block in the
review doc names the specific files already grounded for each pattern; re-read those `file:line`s
directly rather than re-discovering them, e.g. `docs/reference/state-md.md`, `docs/reference/
context-md.md`, `docs/explanation/multi-agent-orchestration.md`, `docs/explanation/the-phase-loop.md`).

**This repo (Rebalance)** — your current worktree: `PROJECT/PDDA.md`, `ROADMAP.md`,
`utils/pdda/*.sh`, `.claude/skills/`, `.claude/commands/`.

**Global skill ecosystem** (outside this worktree, absolute path):
- `/Users/noelsaw/.claude/skills/` (mostly symlinks)
- The real source repos: `giant-brains-claude-skills` (phase-qa, snapshot, take-a-step-back, etc.)
  and `xyz-3-agents-swarm` (the canonical XYZ harness — `.xyz/` in this repo is vendored from it and
  is GITIGNORED here, so if you need XYZ specifics, prefer the canonical `xyz-3-agents-swarm` repo
  citations, the way the Phase 0 Findings block does — do not assume you can read this worktree's
  gitignored `.xyz/` reliably; the Phase 0 record shows one advisor fabricated line ranges doing that).

## What to produce

For each of the 5 patterns: (1) the gap (one line, grounded), (2) the call — ADOPT/ADAPT/SKIP,
(3) target, effort, payoff, (4) one-line why, (5) a concrete first step if ADOPT/ADAPT. Cite
`file:line` for any NEW claim not already in the Phase 0 Findings (you may cite the Phase 0 Findings
block itself for facts already established there instead of re-deriving).

Watch for over-claiming: an ADOPT that just restates "gsd has X" without a Rebalance-side cost/effort
estimate is incomplete. Prefer cheapest-that-works — adapting an existing surface (a PDDA phase, a
`.claude` skill) over standing up new gsd-shaped machinery.
hook: SessionStart
hook: SessionStart Completed
codex
Reading the review doc and its grounded Phase 0 block first, then I’ll pull the exact cited source lines it depends on before grading the five Phase 1 patterns.
exec
/bin/zsh -lc "pwd && ls -la && test -f PROJECT/2-WORKING/GSD-CORE-PATTERN-REVIEW.md && nl -ba PROJECT/2-WORKING/GSD-CORE-PATTERN-REVIEW.md | sed -n '1,260p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-21302-28772
 succeeded in 0ms:
/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-21302-28772
total 3568
drwxr-xr-x@  54 noelsaw  staff    1728 Jul  3 12:41 .
drwx------@ 779 noelsaw  staff   24928 Jul  3 12:42 ..
drwxr-xr-x@   5 noelsaw  staff     160 Jul  3 12:41 .claude
drwxr-xr-x@   3 noelsaw  staff      96 Jul  3 12:41 .devcontainer
-rw-r--r--@   1 noelsaw  staff      84 Jul  3 12:41 .git
drwxr-xr-x@   3 noelsaw  staff      96 Jul  3 12:41 .github
-rw-r--r--@   1 noelsaw  staff    1615 Jul  3 12:41 .gitignore
-rw-r--r--@   1 noelsaw  staff     268 Jul  3 12:41 .mcp.json
drwxr-xr-x@   3 noelsaw  staff      96 Jul  3 12:41 .ona
-rw-r--r--@   1 noelsaw  staff       8 Jul  3 12:41 .pdda-mode
drwxr-xr-x@   4 noelsaw  staff     128 Jul  3 12:41 .vscode
-rw-r--r--@   1 noelsaw  staff     858 Jul  3 12:41 .xyz-pin
-rw-r--r--@   1 noelsaw  staff    3575 Jul  3 12:41 4X4.md
-rw-r--r--@   1 noelsaw  staff   19970 Jul  3 12:41 AGENTS.md
-rw-r--r--@   1 noelsaw  staff   11358 Jul  3 12:41 APACHE-LICENSE-2.0.txt
-rw-r--r--@   1 noelsaw  staff   54832 Jul  3 12:41 ARCHITECTURE.md
-rw-r--r--@   1 noelsaw  staff   51704 Jul  3 12:41 ASK_SELF_INTEGRATION.md
-rw-r--r--@   1 noelsaw  staff   18329 Jul  3 12:41 AUDIT-AUTH-COLLECT-STORE-PART-1.md
-rw-r--r--@   1 noelsaw  staff  152840 Jul  3 12:41 CHANGELOG.md
-rw-r--r--@   1 noelsaw  staff      42 Jul  3 12:41 CLAUDE.md
-rw-r--r--@   1 noelsaw  staff    2822 Jul  3 12:41 DASHBOARD.md
-rw-r--r--@   1 noelsaw  staff    6796 Jul  3 12:41 DIAGRAM.md
-rw-r--r--@   1 noelsaw  staff   10918 Jul  3 12:41 GMAIL.md
-rw-r--r--@   1 noelsaw  staff   22851 Jul  3 12:41 GOOGLE_CALENDAR.md
-rw-r--r--@   1 noelsaw  staff    6256 Jul  3 12:41 GUIDING-PRINCIPLES.md
-rw-r--r--@   1 noelsaw  staff   22637 Jul  3 12:41 HONEST.md
-rw-r--r--@   1 noelsaw  staff   18274 Jul  3 12:41 MCP.md
-rw-r--r--@   1 noelsaw  staff   21664 Jul  3 12:41 MEMORY.md
-rw-r--r--@   1 noelsaw  staff   10497 Jul  3 12:41 PLUGINS.md
drwxr-xr-x@  11 noelsaw  staff     352 Jul  3 12:41 PROJECT
-rw-r--r--@   1 noelsaw  staff   30708 Jul  3 12:41 README.md
-rw-r--r--@   1 noelsaw  staff   19603 Jul  3 12:41 ROADMAP.md
-rw-r--r--@   1 noelsaw  staff    5212 Jul  3 12:41 ROUTER.md
-rw-r--r--@   1 noelsaw  staff    6810 Jul  3 12:41 SCHEDULER.md
-rw-r--r--@   1 noelsaw  staff    5048 Jul  3 12:41 SLEUTH_SYNC.md
-rw-r--r--@   1 noelsaw  staff    8870 Jul  3 12:41 UPGRADE.md
drwxr-xr-x@   4 noelsaw  staff     128 Jul  3 12:41 ask_self
-rw-r--r--@   1 noelsaw  staff     510 Jul  3 12:41 calendar_config.example.json
drwxr-xr-x@   3 noelsaw  staff      96 Jul  3 12:41 debug-mantra
drwxr-xr-x@  12 noelsaw  staff     384 Jul  3 12:41 experimental
drwxr-xr-x@   3 noelsaw  staff      96 Jul  3 12:41 fixtures
-rw-r--r--@   1 noelsaw  staff  629838 Jul  3 12:41 focus5-icon.png
drwxr-xr-x@   3 noelsaw  staff      96 Jul  3 12:41 logs
drwxr-xr-x@  11 noelsaw  staff     352 Jul  3 12:41 macOS
-rw-r--r--@   1 noelsaw  staff    3858 Jul  3 12:41 manifest.json
-rw-r--r--@   1 noelsaw  staff    1075 Jul  3 12:41 pyproject.toml
drwxr-xr-x@  12 noelsaw  staff     384 Jul  3 12:41 relay-system
drwxr-xr-x@  55 noelsaw  staff    1760 Jul  3 12:41 scripts
drwxr-xr-x@   3 noelsaw  staff      96 Jul  3 12:41 server
drwxr-xr-x@   3 noelsaw  staff      96 Jul  3 12:41 src
drwxr-xr-x@   3 noelsaw  staff      96 Jul  3 12:41 templates
drwxr-xr-x@ 130 noelsaw  staff    4160 Jul  3 12:41 tests
drwxr-xr-x@   6 noelsaw  staff     192 Jul  3 12:41 utils
-rw-r--r--@   1 noelsaw  staff  603247 Jul  3 12:41 uv.lock
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

mcp: codebase-memory-mcp/list_projects started
mcp: codebase-memory-mcp/list_projects (failed)
user cancelled MCP tool call
exec
/bin/zsh -lc 'for p in /Users/noelsaw/.claude/skills /Users/noelsaw/.codex/skills /Users/noelsaw/projects /Users/noelsaw/src; do [ -e "$p" ] && echo "== $p ==" && ls -la "$p" | sed -n '"'1,40p'; done" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-21302-28772
 exited 1 in 0ms:
== /Users/noelsaw/.claude/skills ==
total 0
drwxr-xr-x@ 37 noelsaw  staff  1184 Jul  2 17:22 .
drwx------@ 31 noelsaw  staff   992 Jul  3 07:49 ..
lrwxr-xr-x@  1 noelsaw  staff    84 Jun 30 13:03 auto-improve -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/03-improve/auto-improve
lrwxr-xr-x@  1 noelsaw  staff    85 Jun 30 13:03 baseline-spec -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/03-improve/baseline-spec
lrwxr-xr-x@  1 noelsaw  staff    83 Jun 30 13:03 blast-radius -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/01-decide/blast-radius
lrwxr-xr-x@  1 noelsaw  staff    82 Jun 30 13:03 bottom-line -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/01-decide/bottom-line
drwxr-x---@  3 noelsaw  staff    96 Jul  2 17:22 codebase-memory
lrwxr-xr-x@  1 noelsaw  staff    67 Jun 22 18:09 consult -> /Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/skills/consult
lrwxr-xr-x@  1 noelsaw  staff    82 Jun 30 13:03 debug-mantra -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/04-build/debug-mantra
drwxr-xr-x@  3 noelsaw  staff    96 Jun 17 14:59 front-door
lrwxr-xr-x@  1 noelsaw  staff    72 Jun 21 19:28 giantbrains -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/giantbrains
lrwxr-xr-x@  1 noelsaw  staff    84 Jun 30 13:03 github-auth-debug -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/utils/github-auth-debug
drwxr-xr-x@  5 noelsaw  staff   160 Jun 22 19:44 graphify
lrwxr-xr-x@  1 noelsaw  staff    79 Jun 30 13:03 honest -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/repo-health/honest
lrwxr-xr-x@  1 noelsaw  staff    84 Jun 30 13:03 iron-triangle -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/01-decide/iron-triangle
lrwxr-xr-x@  1 noelsaw  staff    75 Jun 30 13:03 linear -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/02-plan/linear
lrwxr-xr-x@  1 noelsaw  staff    80 Jun 30 09:44 loose-ends -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/05-close/loose-ends
drwxr-xr-x@  3 noelsaw  staff    96 Jun 27 22:34 pdda
lrwxr-xr-x@  1 noelsaw  staff    77 Jun 30 13:03 phase-qa -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/02-plan/phase-qa
drwxr-xr-x@  3 noelsaw  staff    96 Jun 18 20:54 ponytail
lrwxr-xr-x@  1 noelsaw  staff    81 Jun 29 10:09 rabbit-hole -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/04-build/rabbit-hole
lrwxr-xr-x@  1 noelsaw  staff    76 Jun 21 19:28 read-only -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/utils/read-only
lrwxr-xr-x@  1 noelsaw  staff    79 Jun 30 13:03 readme-audit -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/repo-health/readme
lrwxr-xr-x@  1 noelsaw  staff    85 Jun 30 13:03 record-decision -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/05-close/record-decision
lrwxr-xr-x@  1 noelsaw  staff    75 Jun 30 13:03 relay -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/04-build/relay
lrwxr-xr-x@  1 noelsaw  staff    74 Jun 22 17:01 relay-to-issue -> /Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/skills/relay-to-issue
lrwxr-xr-x@  1 noelsaw  staff    69 Jun 20 09:09 relay-xyz -> /Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/skills/relay-xyz
lrwxr-xr-x@  1 noelsaw  staff    70 Jun 28 20:13 rpr -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/utils/rpr
lrwxr-xr-x@  1 noelsaw  staff    76 Jun 21 19:28 shakedown -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/utils/shakedown
lrwxr-xr-x@  1 noelsaw  staff    81 Jun 30 13:03 snapshot -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/repo-health/snapshot
lrwxr-xr-x@  1 noelsaw  staff    78 Jun 30 13:03 spike-360 -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/02-plan/spike-360
lrwxr-xr-x@  1 noelsaw  staff    72 Jun 30 13:03 swe -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/02-plan/swe
lrwxr-xr-x@  1 noelsaw  staff    87 Jun 30 13:03 take-a-step-back -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/01-decide/take-a-step-back
lrwxr-xr-x@  1 noelsaw  staff    79 Jun 30 11:25 vscode-color -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/utils/vscode-color
lrwxr-xr-x@  1 noelsaw  staff    79 Jun 30 13:03 worth-it -> /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/01-decide/worth-it
lrwxr-xr-x@  1 noelsaw  staff    59 Jun 18 22:49 wpcc -> /Users/noelsaw/Documents/GH Repos/wp-code-check/skills/wpcc
drwxr-xr-x@  3 noelsaw  staff    96 Jun 30 17:53 xyz
== /Users/noelsaw/.codex/skills ==
total 0
drwxr-xr-x@  3 noelsaw  staff    96 Jul  2 15:54 .
drwxr-xr-x@ 35 noelsaw  staff  1120 Jul  3 12:41 ..
drwxr-xr-x@  8 noelsaw  staff   256 Jul  2 15:54 .system

codex
I have the review doc header and execution-plan context. Next I’m pulling the Phase 0 findings block and the exact counterpart docs it cites so the Phase 1 grades stay anchored to the already-grounded inventory.
exec
/bin/zsh -lc 'rg -n "Phase 1|Explicit 5-step loop|Fresh-context subagents|Persistent cross-session artifacts|Parallel execution waves|Verify-before-done gate" PROJECT/2-WORKING/GSD-CORE-PATTERN-REVIEW.md' in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-21302-28772
exec
/bin/zsh -lc "nl -ba PROJECT/2-WORKING/GSD-CORE-PATTERN-REVIEW.md | sed -n '256,520p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-21302-28772
 succeeded in 0ms:
6:status: "In progress (2-WORKING) — Phase 0 inventory complete 2026-07-03 via consult (Codex + agy). This doc IS the review: each phase's Findings block is filled in as the review runs. Phase 1/2 next."
38:| **Phase 0 complete 2026-07-03** — run via `consult` (Codex + agy in parallel, per operator request), not a Claude subagent. Both families grounded (gsd-core's 5-step loop + `.planning/STATE.md`/`CONTEXT.md` + fresh-context subagents + wave execution + verifier gate; the `capabilities/` overlay composition). Counterpart map complete — **the `capabilities/` overlay layer is the starkest gap, independently flagged by both models**: Reb/XYZ have no composed registry/trust abstraction, only flat skill/command directories. One real cross-model disagreement surfaced and adjudicated: agy fabricated 3 out-of-bounds line-range citations against the gitignored vendored `.xyz/` (caught by direct measurement — real files were 55–335 lines vs. agy's cited ranges up to 4495); Codex correctly flagged `.xyz/` as invisible to its sandboxed worktree and substituted verified `xyz-3-agents-swarm` canonical citations instead. Full method + adjudication in [Phase 0 Findings](#phase-0--inventory--counterpart-map). Execution plan validated earlier the same day via XYZ's vendored `bin/marathon-yaml` (`p0→p1→p2→p3`, no cycles; `p1`/`p2` structurally parallel-eligible). | **Run Phase 1 + Phase 2** (graded adopt/adapt/skip review) — optionally as two parallel subagents per the execution-plan's concurrency note, since they're independent given Phase 0. The `capabilities/` gap found in Phase 0 is the highest-signal lead for Phase 2. Then Phase 3 synthesizes the ranked adopt-list split by target. |
51:- [Phase 1 — Family A: phase-loop & context engineering](#phase-1--family-a-phase-loop--context-engineering)
212:- **Practical concurrency lever for this review:** run Phase 1 and Phase 2 as two parallel research
311:- Fresh-context subagents are the explicit anti-context-rot mechanism: the orchestrator stays thin;
343:| Fresh-context subagents | `consult` (parallel advisory fan-out, this very Phase 0 run) + ad-hoc Agent-tool subagents; no formal context-budget/hand-back contract | Different shape — advisory fan-out and general subagent use, not a phase-loop researcher/planner/executor/verifier cast |
344:| Parallel execution waves | XYZ's `tick`-based non-overlapping path-scoped lanes [`xyz-3-agents-swarm/skills/xyz/SKILL.md:22-49`] + marathon `depends_on` DAG resolution [`xyz-3-agents-swarm/src/marathon-yaml.js:98-146`] | Lane/claim model (path-scoped, agent-symmetric), not centrally-orchestrated dependency-waved worktrees; this review's own execution-plan section already found the DAG-vs-lane mismatch when phases share one file |
345:| Verify-before-done gate | `phase-qa` skill + PDDA QA/doc-readiness gates [`giant-brains-claude-skills/02-plan/phase-qa/SKILL.md:16-26,193-242`; `PROJECT/PDDA.md:439-470`] | Human/LLM-checklist-driven, not an automated verifier *agent* producing a routable report |
362:converged on it unprompted. Ready to `git mv` to `2-WORKING` and proceed to Phase 1/Phase 2.
376:## Phase 1 — Family A: phase-loop & context engineering
385:- [ ] **Explicit 5-step loop** (Discuss→Plan→Execute→Verify→Ship) vs. PDDA's INBOX→WORKING→DONE +
388:- [ ] **Fresh-context subagents for heavy work** vs. our Agent/Explore subagents + XYZ tick lanes.
390:- [ ] **Persistent cross-session artifacts** (`STATE.md`, `CONTEXT.md`) vs. `snapshot.md`, PDDA docs,
392:- [ ] **Parallel execution waves** vs. XYZ concurrent lanes / relay. Gap: wave orchestration &
394:- [ ] **Verify-before-done gate** (diagnose & fix before declaring done) vs. `doctor`+`pytest`+`pdda`
397:#### Phase 1 — Findings (per-pattern grading)
401:### Phase 1 — QA checklist
472:- [ ] **Every Phase 1–2 call appears** in the ranked table or the SKIP ledger — nothing dropped.

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
/bin/zsh -lc 'for f in PROJECT/PDDA.md ROADMAP.md utils/pdda/inbox.sh utils/pdda/working.sh utils/pdda/done.sh; do echo "== $f =="; nl -ba "$f" | sed -n '"'1,220p'; done" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-21302-28772
 succeeded in 0ms:
== PROJECT/PDDA.md ==
     1	# Project-Driven Doc Automation (PDDA)
     2	
     3	PDDA is the document operating layer for this repo. Its job is to keep project plans, bug-fix docs,
     4	research notes, and roadmap pointers clean enough that an agent can pick up work with minimal drift
     5	and enough structure that routine hygiene can be automated instead of re-decided every session.
     6	
     7	The core idea is simple:
     8	
     9	- deterministic scripts enforce the parts that should never require judgment
    10	- an LLM reviewer flags structural or planning-quality gaps that are hard to express as regex alone
    11	- `ROADMAP.md` stays a pointer/index, while project detail lives in the individual project docs
    12	
    13	## Goals
    14	
    15	- Keep `PROJECT/2-WORKING` limited to docs that are truly active.
    16	- Ensure every active doc answers two questions at a glance: what was just completed, and what is next.
    17	- Make phased plans automation-ready by requiring explicit QA gates.
    18	- Prevent plan rot: stale files, missing next steps, hardcoded paths, and hidden scope drift.
    19	- Give agents one repeatable contract for project docs, bug-fix docs, and experimental plans.
    20	
    21	## Non-goals
    22	
    23	- PDDA does not replace the project docs themselves.
    24	- PDDA does not decide product strategy.
    25	- PDDA does not auto-rewrite nuanced plan content without review.
    26	- PDDA does not turn `ROADMAP.md` into a second execution plan.
    27	
    28	## Canonical document model
    29	
    30	PDDA assumes four lifecycle buckets:
    31	
    32	- `PROJECT/1-INBOX`: new ideas, rough proposals, untriaged notes
    33	- `PROJECT/2-WORKING`: active docs that should be updated as work progresses
    34	- `PROJECT/3-COMPLETED`: completed docs with an outcome
    35	- `PROJECT/4-MISC`: reference, stale, superseded, or abandoned docs
    36	
    37	Within that model:
    38	
    39	- `ROADMAP.md` is the index of current, completed, attempted, and deferred work
    40	- project detail lives in the individual `PROJECT/**` documents
    41	- a working doc is the canonical source of truth for that effort until it is completed, deferred, or superseded
    42	- `blank.md` placeholders are scaffolding and should be ignored by PDDA checks
    43	
    44	## Required contract for active docs
    45	
    46	Every doc in `PROJECT/2-WORKING` should have:
    47	
    48	1. YAML frontmatter with at least `title`, `status`, `created`, `updated`, `owner`, and `goal`
    49	2. a near-top status table with the exact columns:
    50	
    51	```md
    52	## Status
    53	
    54	| What was just completed | What's next |
    55	|---|---|
    56	| ... | ... |
    57	```
    58	
    59	3. clear phase or work sections if the doc is a plan
    60	4. a table of contents (`## Table of contents`) listing each phase, if the plan is multi-phase — so a
    61	   cold agent can see the full phase span and jump to the live one without scrolling the whole body
    62	5. QA gates or acceptance criteria after each phase if the plan is multi-phase
    63	6. for any discovery or spike phase, its findings written **back into this doc** before its QA gate can
    64	   pass (see [Discovery & spike phases](#discovery--spike-phases))
    65	7. repo-relative paths only; no hardcoded absolute local paths
    66	
    67	Recommended fields when relevant:
    68	
    69	- `related`
    70	- `reviewed`
    71	- `branch`
    72	- `non_goals`
    73	- `gh_issue`
    74	- `effort`, `complexity`, `risk`, `phases` — triage ratings; **required for medium-large work** (see
    75	  [Triage ratings for medium-large work](#triage-ratings-for-medium-large-work))
    76	
    77	## Triage ratings for medium-large work
    78	
    79	So automation can pick *which* task to pursue without re-reading every plan, every newly recorded
    80	**medium-large** task or project carries four triage fields in its frontmatter:
    81	
    82	| Field | Range | Meaning |
    83	|---|---|---|
    84	| `effort` | integer `1`–`5` | how much work — `1` low, `5` highest |
    85	| `complexity` | integer `1`–`5` | how intricate / how many moving parts — `1` low, `5` highest |
    86	| `risk` | integer `1`–`5` | blast radius + uncertainty — `1` safe/contained, `5` one-way-door or unknown |
    87	| `phases` | positive integer | total number of phases in the plan |
    88	
    89	```yaml
    90	effort: 2
    91	complexity: 3
    92	risk: 1
    93	phases: 4
    94	```
    95	
    96	`risk` should track the repo's existing reversibility scale (`Easy / Costly / One-way door`,
    97	`AGENTS.md` #3): `1`–`2` ≈ Easy, `3` ≈ Costly, `4`–`5` ≈ one-way door / high uncertainty. It is not a
    98	parallel notion of danger — it is that scale expressed as a number.
    99	
   100	**Scope.** Required for medium-large work (project plans, experiments, features, multi-phase efforts).
   101	Genuinely small/trivial docs (a typo, a path repoint, a ≤2–3 line bug-fix — the same floor as the
   102	issue-first SOP) do not need them. "Medium-large" is a judgment, so *presence* is enforced by the LLM
   103	layer, not a regex (below).
   104	
   105	### How to combine them — derive, don't store
   106	
   107	There is deliberately **no stored composite "score" field.** A frozen aggregate would (a) drift from
   108	the three numbers it came from, violating Principle #4 (*one canonical place per fact*), and (b) bake a
   109	weighting choice into every doc that you then cannot re-tune without rewriting them. Compute the
   110	selection signal **live, at selection time**, from the raw fields:
   111	
   112	- **`risk` is a gate, not an addend.** A trivial-but-risky task (`effort 1`, `complexity 1`, `risk 5`)
   113	  is easy to *do* but exactly what automation should not auto-pick — folding risk into a linear sum
   114	  lets it slip through mid-ranked. Gate on it instead.
   115	- **`effort` and `complexity` are correlated** (complex work is usually effortful), so summing them is
   116	  a rough "size" proxy, not two independent signals — treat the sum as one ease axis, not two.
   117	
   118	Reference selection rule (tune the thresholds per repo):
   119	
   120	```text
   121	eligible      = risk <= 2                 # hard safety gate; risk >= 4 => route to a human
   122	ease          = effort + complexity       # 2..10, lower = easier
   123	pick          = among eligible, lowest ease, then fewest phases as the tiebreak
   124	```
   125	
   126	This keeps the raw ratings canonical and queryable while letting the "what's the easiest *safe* thing
   127	to grab" logic live in one place that can evolve. (See the resolved `priority` note under
   128	[Proposed extensions](#proposed-extensions-not-yet-locked).)
   129	
   130	### How this is enforced
   131	
   132	- **deterministic (values)** — `pdda.sh frontmatter` validates the fields **only when present**:
   133	  `effort`/`complexity`/`risk` must be integers `1`–`5`, `phases` a positive integer. A present-but-bad
   134	  value is unambiguous, so it `error`s. The script does **not** force presence — it cannot know whether
   135	  a doc is "medium-large."
   136	- **LLM (presence)** — `pdda-doc-ready.sh` flags a medium-large plan that is *missing* the triage
   137	  ratings. Whether a doc is medium-large is a judgment, so it stays advisory/warn-capped like every
   138	  other readiness finding.
   139	
   140	## Why the two-column status header matters
   141	
   142	The status table is the front door for both humans and automation.
   143	
   144	- The left column is the last verified state change.
   145	- The right column is the next action.
   146	- If either is missing, an agent has to reconstruct state from the body, which is slow and error-prone.
   147	
   148	PDDA therefore treats the exact header names as a contract, not a style preference. The header must be
   149	exactly `What was just completed | What's next` — there is no alias/compatibility window. (One was
   150	specced with a `2026-07-31` cutover, but a single-repo system controls its own docs: no doc here used
   151	an old alias, so a dated, silently-changing branch guarded nothing and was removed 2026-06-22.)
   152	
   153	## Discovery & spike phases
   154	
   155	Discovery and spike phases exist to *learn* — reverse-engineer an existing system, probe an unknown,
   156	prove or kill a risky approach before committing the plan to it. Their output is knowledge, and under
   157	Principle #1 (*docs are the runtime state, not a record of it*) that knowledge is project state. If it
   158	lives only in an agent's context or a throwaway scratch note, a cold agent resuming the plan cannot see
   159	what was learned, why a path was chosen or abandoned, or what the spike actually proved — and the work
   160	gets re-done.
   161	
   162	Contract: **a phase tagged as discovery or spike must write its findings back into the originating plan
   163	doc before its QA gate can pass.** Concretely, that phase's section (or a clearly linked sibling
   164	section in the same doc) must capture:
   165	
   166	- **what was investigated** — the system/area reverse-engineered or the question the spike asked
   167	- **what was found** — the concrete mechanics learned, with repo-relative pointers (`file:line`) where
   168	  the finding lives in code, not a vague summary
   169	- **what it changes** — how the finding confirms, redirects, or kills the plan's later phases; an
   170	  unfinished "we'll know after the spike" left dangling is itself the gap
   171	
   172	This satisfies Principle #4 (*one canonical place per fact*): the originating plan is that place. A
   173	spike whose findings sit in chat is the exact drift PDDA exists to prevent. The QA gate for a
   174	discovery/spike phase therefore includes "findings are written back to this doc" as an acceptance
   175	criterion alongside the phase's normal checks.
   176	
   177	Enforcement is **advisory (LLM layer, warn-capped)** — `pdda-doc-ready.sh` flags a discovery/spike
   178	phase whose findings were not written back. "Did the agent actually capture what it learned" is a
   179	judgment a regex cannot make honestly, so it stays with the LLM reviewer and, like every finding from
   180	that layer, never blocks a build (see [LLM-assisted doc readiness review](#2-llm-assisted-doc-readiness-review)).
   181	To tag a phase, name it plainly (e.g. `## Phase 2 — Discovery: …` / `## Phase 3 — Spike: …`) or set
   182	`doc_type: research` / a phase-level marker the reviewer can see.
   183	
   184	## Bug-fix doc stance
   185	
   186	Bug-fix docs may use a lighter template than multi-phase project plans, but they still need:
   187	
   188	- the minimum frontmatter
   189	- the same `## Status` table while active
   190	- a short bug description
   191	- source of truth for intake, including a GitHub issue when relevant
   192	- verification steps
   193	
   194	GitHub issues are the default intake for substantive bug reports (issue-first SOP — see below). They are not a
   195	substitute for the local active-work doc once execution starts in this repo.
   196	
   197	## GitHub issue intake
   198	
   199	GitHub issues are the **default front door** for substantive work — every project plan and every
   200	non-trivial bug/fix opens an issue *first*, and that issue gets an in-repo pointer doc. The signal
   201	stream lives in GitHub (machine-queryable state, labels, commit↔issue linkage); the execution
   202	surface of record stays in `PROJECT/**`. This is the **issue-first SOP**; the bug-fix stance above
   203	states the principle, and this section owns the *format*. To prevent duplicate intake and forgotten
   204	work, every captured `GH-*.md` doc is also **parked immediately in `ROADMAP.md`** as a one-line queue
   205	entry until it is promoted, deferred, or closed.
   206	
   207	**Floor (what needs an issue).** The operational test is **lines of code touched**: any change
   208	beyond a **2–3 line** fix opens a GitHub issue first, and its local plan doc is named after that
   209	issue (see Filename below). Project plans, experiments, and features are always above this line.
   210	**Exempt:** genuinely trivial edits — a ≤2–3 line code fix, a typo, a path repoint, a doc-only
   211	one-liner, formatting — commit directly with a clear message and no issue. When in doubt, open the
   212	issue — it is a cheap `gh issue create`. The SOP applies to *new* efforts going forward; in-flight
   213	`1-INBOX`/`2-WORKING` docs are not backfilled.
   214	
   215	Capture a tracked issue as a doc in `PROJECT/1-INBOX/` using this convention:
   216	
   217	- **Filename:** `GH-<number>-VERY-SHORT-DESCRIPTION.md` — the local plan doc is always named after
   218	  its GitHub issue (e.g. `GH-1234-SHOWME-COMMAND.md`, `GH-11-CROSS-REPO-TARGETING.md`). Keep the
   219	  description to ~2–4 words; the issue number is the real key, the slug is just a human hint.
   220	  SCREAMING-KEBAB to match the other inbox docs; no zero-padding — mirror the GitHub issue number.
== ROADMAP.md ==
     1	---
     2	title: Project Roadmap Ledger
     3	status: Active
     4	created: 2026-06-21
     5	updated: 2026-07-03
     6	branch: main
     7	supersedes: []
     8	synthesizes: []
     9	goal: >
    10	  Canonical pointer/ledger index for this repo's work. Track projects in progress, completed,
    11	  attempted, and deferred here, and keep execution detail in the linked PROJECT/** docs.
    12	---
    13	
    14	<!-- PDDA ROADMAP CONTRACT — this file is a POINTER/LEDGER, not a plan body.
    15	     Allowed: projects in progress / completed / attempted / deferred + links to PROJECT/** docs.
    16	     NOT allowed: phase checklists, build steps, deep execution notes — put those in the project doc.
    17	     Carve-out: a SHORT exception note is OK only when omitting it would hide an operationally critical fact.
    18	     Enforced by utils/pdda-check-roadmap.sh (deterministic) + utils/pdda-doc-ready.sh ROADMAP rubric (LLM). -->
    19	
    20	# Project Roadmap
    21	
    22	> **Pointer/ledger only — not a plan body.** Execution detail lives in the linked `PROJECT/**` docs.
    23	
    24	## Status
    25	
    26	| What was just completed | What's next |
    27	|---|---|
    28	| **Marathon wave 2 merged to `development` (2026-07-01, PR #100).** Lane A — Unified refresh QA-R remediation: all 7 findings fixed (helper failure now visible + last-good preserved, 8 new tests, DB-less rendering documented, shared path constant, versioned envelope, bounded helper timeout); agy-reviewed, Approved. Lane C — Client auto-discovery Phase 2 kill-check closed at v1 (owner-as-client covers 100% of the live registry; Gemini gap-fill ships dormant). One regression found in review (`_project_activity_snippets` silently dropped the calendar signal when a repo signal was also present) and fixed same-day; suite green (1258/1258). | **Three path-disjoint build lanes continue** (see [the parallel queue](PROJECT/2-WORKING/MARATHON-2026-06-27.md)): (1) VS Code "focus-if-open" repo links — Phase 1 (Mac app); (2) Unified refresh — operator litmus on the QA-R build, then archive; (3) Focus 5 standalone **App Store Phase 0** spike. _Prior track:_ front-door v0.41.1 — `migrate-secrets` on the ~2 remaining Macs, then a `development` → `main` PR. |
    29	
    30	## Ledger
    31	
    32	### Queued / parked
    33	
    34	- `ROADMAP→dashboard collector` — 1-INBOX draft, not yet promoted. A new `roadmap` source scanning PDDA `ROADMAP.md` ledgers into the dashboard. Sequenced **behind** the now-promoted signal-quality contract so it is born observable (inherits the health fields) instead of shipping ungraded. Draft pending 5 operator decisions (§6) and partial cross-device registry rollout (1 of 3 devices). **Also captured (2026-06-30), unscoped:** a speculative Phase 5 — once the collector ships, its cross-repo `roadmap_signals` table is a second potential consumer beside the dashboard plane, seeding XYZ/tick task lanes *across repos*. Not designed; revisit after Phase 2. → [ROADMAP-SIGNAL-SCAN.md](PROJECT/1-INBOX/PDDA-INTEGRATION/ROADMAP-SIGNAL-SCAN.md)
    35	### In progress
    36	
    37	- `GSD Core pattern review` — promoted to 2-WORKING 2026-07-03. Reviewing the MIT `gsd-core` framework for reusable patterns across two targets (vendored XYZ + Rebalance native), scoped to two families (phase-loop/context-engineering, skill/command/hook/agent architecture). Execution plan validated via XYZ's vendored `bin/marathon-yaml` planner (`p0→p1→p2→p3`, no cycles; `p1`/`p2` structurally parallel-eligible but share one target doc, so real concurrency needs a split-file/merge step, not XYZ's lane model). **Phase 0 (inventory) run via `consult`** (Codex + agy in parallel, not a Claude subagent, per operator request): both families grounded; the `capabilities/` overlay layer is the starkest gap both models independently converged on (Reb/XYZ have no composed registry/trust abstraction). One cross-model disagreement adjudicated — agy fabricated 3 out-of-bounds line-range citations against the gitignored vendored `.xyz/` (real files 55–335 lines vs. cited ranges to 4495), caught by direct measurement; Codex correctly flagged `.xyz/` as invisible to its sandboxed worktree and substituted verified canonical-repo citations. Phase 1/2 next. → [GSD-CORE-PATTERN-REVIEW.md](PROJECT/2-WORKING/GSD-CORE-PATTERN-REVIEW.md)
    38	
    39	- `XYZ ⇄ Rebalance integration` ([#102](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/102)) — promoted to 2-WORKING 2026-07-03 (branch `gh-102-xyz-rebalance-integration`). **Phase 0 discovery run** against XYZ's GH-75: `XYZ.json` confirmed **completion-only** telemetry (not a per-phase heartbeat), so **#1 reframed** to a "recently-completed sessions" signal — no XYZ-side emitter needed; enumeration source = `registry.tsv` install rows; XYZ already writes atomically. Cross-model consult (Codex + agy) also moved **#3 off direct SQLite** onto a `roadmap_signals.json` projection file (mirror-not-migration). Build order #2→#1→#3→#4. **Phase 1 (seam #2 `xyz-sync check`) next; Phase 2 gated on GH-101.** → [PROJECT/2-WORKING/GH-102-XYZ-REBALANCE-INTEGRATION.md](PROJECT/2-WORKING/GH-102-XYZ-REBALANCE-INTEGRATION.md)
    40	- `Signal-quality contract (observe-first source health)` ([#101](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/101)) — promoted to 2-WORKING 2026-07-01; **Phase 0 spike run** (verified against live code + DB): `get_index_status`/`_safe_max` per-table freshness + `_safe_count_where` 7d primitive confirmed, no `sync_state` table, and one correction found (`payload["freshness"]` is overwritten by the semantic-drift dict, so Phase 2 must merge). Phase 1 next: additive `recent_row_count_7d` per source. → [PROJECT/2-WORKING/GH-101-SIGNAL-QUALITY-CONTRACT.md](PROJECT/2-WORKING/GH-101-SIGNAL-QUALITY-CONTRACT.md)
    41	- `Collector Path and Portability Audit — Phase 6` — reopened 2026-06-30 after a Codex review (GH-62) found the original refactor's Definition of Done was never fully closed. GH-62's own "High" finding (`dashboard.py` passing a removed `include_semantic` param to `refresh_index()`, runtime `TypeError`) was independently verified already fixed in current code; GH-62 closed with that verification. **4 gaps remain, tracked as the new Phase 6:** (1) not every raw source has one write path, (4) semantic-maintenance CLI `--source all` drifts from the live semantic-stage coverage, (6) `setup_gmail_oauth.py`/`setup_calendar_oauth.py` still hardcode token paths instead of the shared resolver, (8) test/observability blind spots (a mocked-signature test let the dashboard break ship undetected). Phases 0-5 of the original audit are complete and preserved as provenance. → [PROJECT/2-WORKING/COLLECTOR-PATH-AND-PORTABILITY-AUDIT.md](PROJECT/2-WORKING/COLLECTOR-PATH-AND-PORTABILITY-AUDIT.md)
    42	- `Focus 5 Float — reminders drawer (Apple + Obsidian)` — the panel bottom now carries two task sections above the `focus5.md` note: **Apple Reminders** (live EventKit list, explicit label, capped to 8, complete-checkbox write-back) and **Obsidian Reminders** (top 8 open checkboxes from vault-root `0. Goals.md`, exact-line checkbox flip via localhost `GET /focus-5/goals` + `POST /api/focus5/goals/complete`). Load failures are now diagnosable (`vault_not_configured`, `file_missing`, `read_failed`, route/transport/decode errors) instead of a generic banner. **Operator TCC litmus still pending** for the Apple/EventKit side. → [PROJECT/2-WORKING/FOCUS5-REMINDERS-PANEL.md](PROJECT/2-WORKING/FOCUS5-REMINDERS-PANEL.md)
    43	- `Repo links open VS Code with "focus-if-open"` — replace the window-hijacking `vscode://` URI on both surfaces so the card "Open ↗" button focuses an already-open VS Code window (or spawns exactly one). **Both phases code-complete 2026-06-29:** Phase 1 (Mac app `VSCodeLauncher`) + Phase 2 (web `POST /api/focus5/open` — server-side allowlist resolve id→path, direct-argv `code <path>`, two-layer loopback+same-origin guard, `vscode://` fallback). **agy relay QA: Approved (r2/4)** — hardened the local-only guard + `code` binary file-check per its findings; **91 tests passed**. **Next:** operator browser/GUI litmus on both surfaces. → [PROJECT/2-WORKING/VSCODE-OPEN-WORKSPACE.md](PROJECT/2-WORKING/VSCODE-OPEN-WORKSPACE.md)
    44	- `Unified UI refresh + restart (system-wide)` — keep the always-on pulse-server as the source-freshness path so no source goes stale and no manual terminal sync is needed. **/ponytail-trimmed to a v1 (2026-06-27)** after a Codex consult QA: the `/api/restart` endpoint + Focus 5 Swift wiring are **deferred**. **v1 = make the existing Refresh button populate the reminders column via the signed EventKit helper (no FDA)** — 3 edits: helper `list-active` op → `/api/refresh` reads it (atomic, last-good-snapshot-wins, ~5s timeout) → column renders. **Phase QA-R remediation shipped 2026-07-01 (PR #100)** — all 7 findings closed, 8 new tests, agy-Approved. **Next:** operator litmus on the live dashboard, then archive. → [PROJECT/2-WORKING/UNIFIED-REFRESH-RESTART.md](PROJECT/2-WORKING/UNIFIED-REFRESH-RESTART.md)
    45	- `Focus 5 Native (standalone Mac App Store track)` — canonical rewrite plan for a truly standalone macOS app that keeps the Focus 5 UX but removes all runtime dependency on rebalance-OS, Python, localhost JSON, and repo scripts. **Phase 0-R sandboxed re-spike PASSED 2026-07-01** (marathon lane): all 10 QA gates observed in a codesigned App-Sandbox `.app` — `Process`→git empirically blocked, in-process libgit2 returns the full typed fact set, bookmark round-trip verified. Key finding: the SwiftGit2 SPM path is iOS-only, so a macOS-sliced libgit2 is a Phase 2 cost. **Phase 1 next** (freeze native v1 entities). → [PROJECT/2-WORKING/FOCUS-5-APP-STORE.md](PROJECT/2-WORKING/FOCUS-5-APP-STORE.md)
    46	- `Focus 5 Float — reference-design UI refresh` — queued next pass for the floating Mac app: refresh the visual shell/card presentation against the reference set in `temp/Floating Mac app design refinement/` while preserving the current product contract (floating card stack, Focus 5 / Dirty Five / Telemetry modes, reminders panel, offline/start-server affordances). This is the same write surface as the app track, so do it only when no other `Focus5Float` writer is active. → [PROJECT/2-WORKING/P2-MACOS-FOCUS5-FLOAT.md](PROJECT/2-WORKING/P2-MACOS-FOCUS5-FLOAT.md)
    47	
    48	### Completed
    49	
    50	- `Client auto-discovery` ([PR #100](https://github.com/Hypercart-Dev-Tools/rebalance-OS/pull/100)) — **DONE 2026-07-01.** Owner-as-client deterministic spine (Phase 1, 2026-06-30) plus a code-complete Gemini gap-fill (Phase 2) for `None`-client projects, batched call, fail-soft. Phase 2 kill-check measured live registry coverage: 15/15 active projects (100%) already owner-as-client labeled, so the kill switch fired (≥90% threshold) — Gemini gap-fill ships dormant, never exercised against a live key, re-activates automatically if a calendar-only/personal-account project appears. No new table/lifecycle/MCP tool. 9 tests (`test_client_buckets.py` + `test_client_gapfill.py`); suite green. → [PROJECT/2-WORKING/CLIENT-AUTO-DISCOVERY.md](PROJECT/2-WORKING/CLIENT-AUTO-DISCOVERY.md)
    51	- `Watch-list coverage guard` ([PR #82](https://github.com/Hypercart-Dev-Tools/rebalance-OS/pull/82)) — **DONE 2026-06-30 (PR #82 merged).** Canonical watched-repos snapshot + silent-reduction alarm: additive migration `0009` + isolated `watchlist_guard.py` (`classify_removal` + `snapshot_and_detect` single writer) at the end of `_refresh_github` (clean-sync only) + `_EVENT_BADGE` ⚠ chip on `/auth-log`. 11 guard tests; suite green; doctor clean; live baseline 59 watched / 24 durable-intent. → [PROJECT/3-COMPLETED/WATCHLIST-COVERAGE-GUARD.md](PROJECT/3-COMPLETED/WATCHLIST-COVERAGE-GUARD.md)
    52	- `GH-96 git-pulse stages PDDA registry projection` ([#96](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/96)) — **DONE 2026-06-30.** The git-pulse collector staged `pulse-<device>.md` + `devices/<device>.yaml` but not the PDDA projection `pdda/registry-<device>.tsv`, so on PDDA-installed devices it stayed untracked and never synced (sync-side half of the multi-device rollup; write-side was `pdda#7`). Added a guarded `append_stage_path "pdda/registry-$device_id.tsv"` before `git add`. New collector staging test (5/5); doctor clean; suite 1242 green; merged to `development` via PR #97. → [PROJECT/3-COMPLETED/GH-96-GITPULSE-STAGE-PDDA-PROJECTION.md](PROJECT/3-COMPLETED/GH-96-GITPULSE-STAGE-PDDA-PROJECTION.md)
    53	- `GH-94 priority_tier soft down-weight` ([#94](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/94)) — **DONE 2026-06-30.** `priority_tier` now reaches the "what to do next" ranking (previously dashboard-only): low-cadence projects (tier ≥ 4, e.g. weekly devops repos) get a `[priority:low]` prompt tag + down-weight lever and sink in the deterministic fallback — soft down-weight, not a mute. One shared `_is_low_priority` predicate; reuses the existing priority-rule config; Focus 5 + `NOISE_REPOS` untouched. 4 tests; suite 1230 green; doctor clean. → [PROJECT/3-COMPLETED/GH-94-PRIORITY-DOWNWEIGHT.md](PROJECT/3-COMPLETED/GH-94-PRIORITY-DOWNWEIGHT.md)
    54	- `GH-93 MCP probe tools` ([#93](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/93)) — **DONE 2026-06-30.** Two read-only MCP tools so a client (Claude Desktop) can probe **both** raw source rows and the synthesized headline: `peek_source(source, limit)` (allowlist-guarded, 7 source tables, no free-form SQL) + `get_next_actions()` (reads persisted ranking, no recompute, None-safe). Folded into `index.py` + `manifest.json`; 4 tests; suite 1226 green, doctor clean. → [PROJECT/3-COMPLETED/GH-93-MCP-PROBE-TOOLS.md](PROJECT/3-COMPLETED/GH-93-MCP-PROBE-TOOLS.md)
    55	- `Gemini "What to do next" → fixed vault file` — **DONE 2026-06-29.** The daily "what to do next" is now genuinely Gemini-synthesized: paid-key **file** resolver added to `get_gemini_api_key()` (env/config/`~/secrets/gemini-paid-key.txt`, multi-line aware) **and** the retired `gemini-2.0-flash` default swapped to `gemini-2.5-flash` (root cause — the dead model, not just a missing key, was forcing the Qwen-0.6B fallback that emitted `<rank>. <title>` placeholders); parser now rejects placeholder echoes. The same ranked output renders to the fixed vault file `Dashboards/What To Do Next.md` via a precompute-hook sink. Live-verified (`model_used=gemini-2.5-flash`, 0 placeholder titles); suite 1202 green, doctor passed. → [PROJECT/1-INBOX/GEMINI-WHATS-NEXT-VAULT.md](PROJECT/1-INBOX/GEMINI-WHATS-NEXT-VAULT.md)
    56	- `Apple Reminders unified integration` — read-only `apple_reminders` SQLite collector **plus** an EventKit write surface, both **shipped + live-verified (2026-06-27)**. Phases 0–4: deterministic store discovery, WAL-safe snapshot extractor (`src/rebalance/ingest/apple_reminders.py`), dynamic REMCD mapper, collector registration in `index_ops.py` + reconcile-don't-delete storage, read accessor + pulse "Today" column, schema-drift health. Phase 5: signed LaunchServices helper performs EventKit create/update/complete/delete via `rebalance apple-reminders` (dry-run default, `request_id` idempotency, write serialization, three-state audit); **57 tests green**, full CRUD proven live. **Phase 6 dashboard write-back v1 SHIPPED (2026-06-30):** the pulse column is now actionable — a per-reminder complete check POSTs `/api/apple-reminders/complete` through the Phase 5.1 orchestrator (single-writer + audit; optimistic grey-out; `create`/`delete` stay CLI-only); **5 endpoint regression tests** added. Deferred by choice: cross-version validation (2nd Mac), snapshot perf, notes/sections decode, auto-refresh of the column after a write (FDA-gated reconcile). → [PROJECT/2-WORKING/APPLE-REMINDERS-UNIFIED-PLAN.md](PROJECT/2-WORKING/APPLE-REMINDERS-UNIFIED-PLAN.md)
    57	- `Focus 5 Float (floating macOS card stack)` — native menu-bar app rendering the Focus 5 roster as a collapsible card stack over live `GET /focus-5.json`. **All phases 0–5 done** (frozen contract + 90 tests, `Focus5Float` SwiftPM package, floating `NSPanel`, `Focus5Client` live data, collapsible card UI, packaged `/Applications` app + launch-at-login + roster-health light) plus a post-1.0 read-only bottom-note from vault `focus5.md`. Ready to move to `3-COMPLETED` once the `.icns` artwork lands. → [PROJECT/2-WORKING/P2-MACOS-FOCUS5-FLOAT.md](PROJECT/2-WORKING/P2-MACOS-FOCUS5-FLOAT.md)
    58	- `Focus 5 Float — Telemetry tab` — third tab reading health-annotated JSON from `~/Documents/telemetry/`; `ViewMode` enum + orange-capable `HealthDot` + reader/model/view all shipped through Phase 2 (explicit file selection + visible decode errors). `swift build` green, `FOCUS5_SELFTEST` passes. **Operator litmus pending** (eyeball 3 demo rows), then archive. → [PROJECT/2-WORKING/P2-FOCUS5-TELEMETRY-TAB.md](PROJECT/2-WORKING/P2-FOCUS5-TELEMETRY-TAB.md)
    59	- `Focus 5 Float — offline cache & manual server start` — resilience follow-on: offline roster cache (instant cold-start, "cached · {age}") + one-click "Start server" (detached `Process`, login-shell binary resolution, poll-until-healthy). Both phases built, `swift build` green, binary-resolution root-caused (`pipx install -e .` → `~/.local/bin/rebalance`), app icon shipped. **Operator litmus pending.** → [PROJECT/2-WORKING/P3-FOCUS5-FLOAT-OFFLINE-RESILIENCE.md](PROJECT/2-WORKING/P3-FOCUS5-FLOAT-OFFLINE-RESILIENCE.md)
    60	- `Focus 5 — identity-agnostic ranking vector` ([GH-81](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/81)) — the headline board silently dropped repos whose recent local commits used a different author email. **Phases 1 & 2 complete (2026-06-24):** `rank_recent_activity` now ranks on local-commit reflog recency (`my_local_commit_ts` + recorded `recency_basis` fallback ladder, migration `0007`), and the off-roster strip + card badges explain *why* each repo ranks (recency vs the #5 cutoff, fallback basis shown). Suite green (1109); real-device proof = 24 repos no longer silently dropped. → [PROJECT/3-COMPLETED/GH-81-FOCUS5-RANK-VECTOR.md](PROJECT/3-COMPLETED/GH-81-FOCUS5-RANK-VECTOR.md)
    61	- `Focus 5 active repos bug remediation` — root-cause trace + remediation implemented, tested, and verified live (transient Dirty Five mode, scan-root CLI setters); Phase 3 activated 2026-06-24 (`com.rebalance-os.github-sync` installed + firing hourly). → [PROJECT/3-COMPLETED/FOCUS-5-RANKING-BUG-AND-REMEDIATION.md](PROJECT/3-COMPLETED/FOCUS-5-RANKING-BUG-AND-REMEDIATION.md)
    62	- `Team Calendar as a Signal (HiQS)` — Phase 2 v0.5 built on `development`, data-layer DoD proven, pending live validation and merge/tag. → [PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md](PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md)
    63	- `Unified front-door, portability & auth hardening` — Phases 1–6 complete, merged to `development` (v0.41.1, PR #78). Operator-only per-machine `migrate-secrets` (~2 Macs) + deferred fleet/multi-operator scope remain; `development` → `main` PR pending. → [PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md](PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md)
    64	- `AI-agent front door (ROUTER.md)` — added the canonical startup-order entry point (ROUTER → AGENTS → ARCHITECTURE → ROADMAP → PROJECT docs; run `rebalance doctor` / `pytest tests/` / `utils/pdda-run.sh` before claiming wins), completing the PDDA front-door layer alongside the installed `utils/pdda-*.sh` suite. → [ROUTER.md](ROUTER.md)
    65	
    66	### Attempted
    67	
    68	_None yet._
    69	
    70	### Deferred
    71	
    72	_None yet._
    73	
    74	---
    75	
    76	## Entry format
    77	
    78	Use one flat bullet per item:
    79	
    80	- `Project / track name` — one-line status summary. → `[linked project doc](PROJECT/...)`
== utils/pdda/inbox.sh ==
nl: utils/pdda/inbox.sh: No such file or directory
== utils/pdda/working.sh ==
nl: utils/pdda/working.sh: No such file or directory
== utils/pdda/done.sh ==
nl: utils/pdda/done.sh: No such file or directory

codex
Phase 0 already gives the counterpart map. I’m now checking the underlying gsd-core docs and the local skill/command docs directly so the grades rest on the same evidence, not just the summary block.
exec
/bin/zsh -lc 'for f in PROJECT/PDDA.md .claude/commands/agent.md .claude/commands/explore.md .claude/commands/doctor.md .claude/commands/pytest.md .claude/commands/pdda.md; do [ -f "$f" ] && echo "== $f ==" && nl -ba "$f" | sed -n '"'1,220p'; done" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-21302-28772
 exited 1 in 0ms:
== PROJECT/PDDA.md ==
     1	# Project-Driven Doc Automation (PDDA)
     2	
     3	PDDA is the document operating layer for this repo. Its job is to keep project plans, bug-fix docs,
     4	research notes, and roadmap pointers clean enough that an agent can pick up work with minimal drift
     5	and enough structure that routine hygiene can be automated instead of re-decided every session.
     6	
     7	The core idea is simple:
     8	
     9	- deterministic scripts enforce the parts that should never require judgment
    10	- an LLM reviewer flags structural or planning-quality gaps that are hard to express as regex alone
    11	- `ROADMAP.md` stays a pointer/index, while project detail lives in the individual project docs
    12	
    13	## Goals
    14	
    15	- Keep `PROJECT/2-WORKING` limited to docs that are truly active.
    16	- Ensure every active doc answers two questions at a glance: what was just completed, and what is next.
    17	- Make phased plans automation-ready by requiring explicit QA gates.
    18	- Prevent plan rot: stale files, missing next steps, hardcoded paths, and hidden scope drift.
    19	- Give agents one repeatable contract for project docs, bug-fix docs, and experimental plans.
    20	
    21	## Non-goals
    22	
    23	- PDDA does not replace the project docs themselves.
    24	- PDDA does not decide product strategy.
    25	- PDDA does not auto-rewrite nuanced plan content without review.
    26	- PDDA does not turn `ROADMAP.md` into a second execution plan.
    27	
    28	## Canonical document model
    29	
    30	PDDA assumes four lifecycle buckets:
    31	
    32	- `PROJECT/1-INBOX`: new ideas, rough proposals, untriaged notes
    33	- `PROJECT/2-WORKING`: active docs that should be updated as work progresses
    34	- `PROJECT/3-COMPLETED`: completed docs with an outcome
    35	- `PROJECT/4-MISC`: reference, stale, superseded, or abandoned docs
    36	
    37	Within that model:
    38	
    39	- `ROADMAP.md` is the index of current, completed, attempted, and deferred work
    40	- project detail lives in the individual `PROJECT/**` documents
    41	- a working doc is the canonical source of truth for that effort until it is completed, deferred, or superseded
    42	- `blank.md` placeholders are scaffolding and should be ignored by PDDA checks
    43	
    44	## Required contract for active docs
    45	
    46	Every doc in `PROJECT/2-WORKING` should have:
    47	
    48	1. YAML frontmatter with at least `title`, `status`, `created`, `updated`, `owner`, and `goal`
    49	2. a near-top status table with the exact columns:
    50	
    51	```md
    52	## Status
    53	
    54	| What was just completed | What's next |
    55	|---|---|
    56	| ... | ... |
    57	```
    58	
    59	3. clear phase or work sections if the doc is a plan
    60	4. a table of contents (`## Table of contents`) listing each phase, if the plan is multi-phase — so a
    61	   cold agent can see the full phase span and jump to the live one without scrolling the whole body
    62	5. QA gates or acceptance criteria after each phase if the plan is multi-phase
    63	6. for any discovery or spike phase, its findings written **back into this doc** before its QA gate can
    64	   pass (see [Discovery & spike phases](#discovery--spike-phases))
    65	7. repo-relative paths only; no hardcoded absolute local paths
    66	
    67	Recommended fields when relevant:
    68	
    69	- `related`
    70	- `reviewed`
    71	- `branch`
    72	- `non_goals`
    73	- `gh_issue`
    74	- `effort`, `complexity`, `risk`, `phases` — triage ratings; **required for medium-large work** (see
    75	  [Triage ratings for medium-large work](#triage-ratings-for-medium-large-work))
    76	
    77	## Triage ratings for medium-large work
    78	
    79	So automation can pick *which* task to pursue without re-reading every plan, every newly recorded
    80	**medium-large** task or project carries four triage fields in its frontmatter:
    81	
    82	| Field | Range | Meaning |
    83	|---|---|---|
    84	| `effort` | integer `1`–`5` | how much work — `1` low, `5` highest |
    85	| `complexity` | integer `1`–`5` | how intricate / how many moving parts — `1` low, `5` highest |
    86	| `risk` | integer `1`–`5` | blast radius + uncertainty — `1` safe/contained, `5` one-way-door or unknown |
    87	| `phases` | positive integer | total number of phases in the plan |
    88	
    89	```yaml
    90	effort: 2
    91	complexity: 3
    92	risk: 1
    93	phases: 4
    94	```
    95	
    96	`risk` should track the repo's existing reversibility scale (`Easy / Costly / One-way door`,
    97	`AGENTS.md` #3): `1`–`2` ≈ Easy, `3` ≈ Costly, `4`–`5` ≈ one-way door / high uncertainty. It is not a
    98	parallel notion of danger — it is that scale expressed as a number.
    99	
   100	**Scope.** Required for medium-large work (project plans, experiments, features, multi-phase efforts).
   101	Genuinely small/trivial docs (a typo, a path repoint, a ≤2–3 line bug-fix — the same floor as the
   102	issue-first SOP) do not need them. "Medium-large" is a judgment, so *presence* is enforced by the LLM
   103	layer, not a regex (below).
   104	
   105	### How to combine them — derive, don't store
   106	
   107	There is deliberately **no stored composite "score" field.** A frozen aggregate would (a) drift from
   108	the three numbers it came from, violating Principle #4 (*one canonical place per fact*), and (b) bake a
   109	weighting choice into every doc that you then cannot re-tune without rewriting them. Compute the
   110	selection signal **live, at selection time**, from the raw fields:
   111	
   112	- **`risk` is a gate, not an addend.** A trivial-but-risky task (`effort 1`, `complexity 1`, `risk 5`)
   113	  is easy to *do* but exactly what automation should not auto-pick — folding risk into a linear sum
   114	  lets it slip through mid-ranked. Gate on it instead.
   115	- **`effort` and `complexity` are correlated** (complex work is usually effortful), so summing them is
   116	  a rough "size" proxy, not two independent signals — treat the sum as one ease axis, not two.
   117	
   118	Reference selection rule (tune the thresholds per repo):
   119	
   120	```text
   121	eligible      = risk <= 2                 # hard safety gate; risk >= 4 => route to a human
   122	ease          = effort + complexity       # 2..10, lower = easier
   123	pick          = among eligible, lowest ease, then fewest phases as the tiebreak
   124	```
   125	
   126	This keeps the raw ratings canonical and queryable while letting the "what's the easiest *safe* thing
   127	to grab" logic live in one place that can evolve. (See the resolved `priority` note under
   128	[Proposed extensions](#proposed-extensions-not-yet-locked).)
   129	
   130	### How this is enforced
   131	
   132	- **deterministic (values)** — `pdda.sh frontmatter` validates the fields **only when present**:
   133	  `effort`/`complexity`/`risk` must be integers `1`–`5`, `phases` a positive integer. A present-but-bad
   134	  value is unambiguous, so it `error`s. The script does **not** force presence — it cannot know whether
   135	  a doc is "medium-large."
   136	- **LLM (presence)** — `pdda-doc-ready.sh` flags a medium-large plan that is *missing* the triage
   137	  ratings. Whether a doc is medium-large is a judgment, so it stays advisory/warn-capped like every
   138	  other readiness finding.
   139	
   140	## Why the two-column status header matters
   141	
   142	The status table is the front door for both humans and automation.
   143	
   144	- The left column is the last verified state change.
   145	- The right column is the next action.
   146	- If either is missing, an agent has to reconstruct state from the body, which is slow and error-prone.
   147	
   148	PDDA therefore treats the exact header names as a contract, not a style preference. The header must be
   149	exactly `What was just completed | What's next` — there is no alias/compatibility window. (One was
   150	specced with a `2026-07-31` cutover, but a single-repo system controls its own docs: no doc here used
   151	an old alias, so a dated, silently-changing branch guarded nothing and was removed 2026-06-22.)
   152	
   153	## Discovery & spike phases
   154	
   155	Discovery and spike phases exist to *learn* — reverse-engineer an existing system, probe an unknown,
   156	prove or kill a risky approach before committing the plan to it. Their output is knowledge, and under
   157	Principle #1 (*docs are the runtime state, not a record of it*) that knowledge is project state. If it
   158	lives only in an agent's context or a throwaway scratch note, a cold agent resuming the plan cannot see
   159	what was learned, why a path was chosen or abandoned, or what the spike actually proved — and the work
   160	gets re-done.
   161	
   162	Contract: **a phase tagged as discovery or spike must write its findings back into the originating plan
   163	doc before its QA gate can pass.** Concretely, that phase's section (or a clearly linked sibling
   164	section in the same doc) must capture:
   165	
   166	- **what was investigated** — the system/area reverse-engineered or the question the spike asked
   167	- **what was found** — the concrete mechanics learned, with repo-relative pointers (`file:line`) where
   168	  the finding lives in code, not a vague summary
   169	- **what it changes** — how the finding confirms, redirects, or kills the plan's later phases; an
   170	  unfinished "we'll know after the spike" left dangling is itself the gap
   171	
   172	This satisfies Principle #4 (*one canonical place per fact*): the originating plan is that place. A
   173	spike whose findings sit in chat is the exact drift PDDA exists to prevent. The QA gate for a
   174	discovery/spike phase therefore includes "findings are written back to this doc" as an acceptance
   175	criterion alongside the phase's normal checks.
   176	
   177	Enforcement is **advisory (LLM layer, warn-capped)** — `pdda-doc-ready.sh` flags a discovery/spike
   178	phase whose findings were not written back. "Did the agent actually capture what it learned" is a
   179	judgment a regex cannot make honestly, so it stays with the LLM reviewer and, like every finding from
   180	that layer, never blocks a build (see [LLM-assisted doc readiness review](#2-llm-assisted-doc-readiness-review)).
   181	To tag a phase, name it plainly (e.g. `## Phase 2 — Discovery: …` / `## Phase 3 — Spike: …`) or set
   182	`doc_type: research` / a phase-level marker the reviewer can see.
   183	
   184	## Bug-fix doc stance
   185	
   186	Bug-fix docs may use a lighter template than multi-phase project plans, but they still need:
   187	
   188	- the minimum frontmatter
   189	- the same `## Status` table while active
   190	- a short bug description
   191	- source of truth for intake, including a GitHub issue when relevant
   192	- verification steps
   193	
   194	GitHub issues are the default intake for substantive bug reports (issue-first SOP — see below). They are not a
   195	substitute for the local active-work doc once execution starts in this repo.
   196	
   197	## GitHub issue intake
   198	
   199	GitHub issues are the **default front door** for substantive work — every project plan and every
   200	non-trivial bug/fix opens an issue *first*, and that issue gets an in-repo pointer doc. The signal
   201	stream lives in GitHub (machine-queryable state, labels, commit↔issue linkage); the execution
   202	surface of record stays in `PROJECT/**`. This is the **issue-first SOP**; the bug-fix stance above
   203	states the principle, and this section owns the *format*. To prevent duplicate intake and forgotten
   204	work, every captured `GH-*.md` doc is also **parked immediately in `ROADMAP.md`** as a one-line queue
   205	entry until it is promoted, deferred, or closed.
   206	
   207	**Floor (what needs an issue).** The operational test is **lines of code touched**: any change
   208	beyond a **2–3 line** fix opens a GitHub issue first, and its local plan doc is named after that
   209	issue (see Filename below). Project plans, experiments, and features are always above this line.
   210	**Exempt:** genuinely trivial edits — a ≤2–3 line code fix, a typo, a path repoint, a doc-only
   211	one-liner, formatting — commit directly with a clear message and no issue. When in doubt, open the
   212	issue — it is a cheap `gh issue create`. The SOP applies to *new* efforts going forward; in-flight
   213	`1-INBOX`/`2-WORKING` docs are not backfilled.
   214	
   215	Capture a tracked issue as a doc in `PROJECT/1-INBOX/` using this convention:
   216	
   217	- **Filename:** `GH-<number>-VERY-SHORT-DESCRIPTION.md` — the local plan doc is always named after
   218	  its GitHub issue (e.g. `GH-1234-SHOWME-COMMAND.md`, `GH-11-CROSS-REPO-TARGETING.md`). Keep the
   219	  description to ~2–4 words; the issue number is the real key, the slug is just a human hint.
   220	  SCREAMING-KEBAB to match the other inbox docs; no zero-padding — mirror the GitHub issue number.

exec
/bin/zsh -lc "for f in /Users/noelsaw/Documents/GH\\ Repos/giant-brains-claude-skills/02-plan/phase-qa/SKILL.md /Users/noelsaw/Documents/GH\\ Repos/giant-brains-claude-skills/repo-health/snapshot/SKILL.md /Users/noelsaw/Documents/GH\\ Repos/giant-brains-claude-skills/05-close/loose-ends/SKILL.md; do echo \"== "'$f =="; nl -ba "$f" | sed -n '"'1,260p'; done" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-21302-28772
 succeeded in 0ms:
== /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/02-plan/phase-qa/SKILL.md ==
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
== /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/repo-health/snapshot/SKILL.md ==
     1	---
     2	name: snapshot
     3	description: Save the most recent substantive response — plus session metadata, recent test findings, and phase status — to a persistent, additive snapshot.md file so the user can re-find and resume the session later (next morning, after a crash, or across chat tabs). Trigger whenever the user says "snapshot", "snapshot this", "save this session", "save our progress", "save before I go to bed / sign off / wrap up", "checkpoint this", or expresses worry about losing work, losing the chat, or VS Code crashing. Also offer it proactively when a long working session reaches a natural stopping point with unsaved findings. Use only to preserve session progress — not when the user wants to save or export a specific artifact (a file, PDF, image, code snippet, or document).
     4	---
     5	
     6	# Snapshot
     7	
     8	Save a re-entry point for the current session. A snapshot has one job: make tomorrow-morning-you (or post-crash-you) able to find this work and resume it in under a minute, without hunting through chat tabs or recovery files.
     9	
    10	A good snapshot therefore captures two things:
    11	1. **The answer** — the most recent substantive response, verbatim.
    12	2. **The context** — enough metadata that the snapshot is self-locating and self-resuming.
    13	
    14	## File location and behavior
    15	
    16	- File name: `snapshot.md`
    17	- **Location** — write to the first of these that applies, so the snapshot lands where the user will look for it:
    18	  1. **Git repository root** (`git rev-parse --show-toplevel`) — keeps the snapshot beside the code it describes.
    19	  2. **Editor/workspace root**, if one is open and you're not in a repo.
    20	  3. **Current working directory**, if writable and not `/` or a system temp dir.
    21	  4. **Claude.ai with no project filesystem** → `/mnt/user-data/outputs/snapshot.md`, then present the file for download.
    22	- **Keep it out of version control.** If you write `snapshot.md` into a git repo and it isn't already ignored, mention once that it's a personal recovery artifact (it can contain anything pasted into the chat) and offer to add it to `.gitignore`. Don't redact or trim the contents to make it commit-safe — keep it out of commits instead.
    23	- **If the write fails** (read-only directory, unclear or unwritable cwd), fall back to the next location in the list above — ultimately the user-output dir — and state the *actual* path saved in the confirmation. Never report a project-root save that didn't happen: for crash recovery, a confidently-wrong path is worse than admitting the fallback.
    24	- **Additive, newest-first.** Never overwrite. Prepend each new snapshot entry to the TOP of the file, above all previous entries. The morning use case means the most recent entry must be the first thing visible when the file opens.
    25	- If `snapshot.md` doesn't exist yet, create it. If it exists, read it first, then prepend.
    26	
    27	## Entry format
    28	
    29	Every entry starts with a timestamp header and a metadata block, then the verbatim response, then a separator. Use the user's local time (check `user_time_v0` or system time — never guess).
    30	
    31	```markdown
    32	# 📸 Snapshot — 2026-06-09 22:47 (Tue)
    33	
    34	**Session:** <short, searchable label for this chat/work session — e.g., "SKILL file refinement — snapshot skill build">
    35	**Project / repo:** <project name or path, if known>
    36	**Phase:** <current phase or milestone, if the work has phases — e.g., "Phase 2: eval iteration">
    37	**Status:** <one line: where things stand right now>
    38	
    39	## Git state
    40	<Captured at snapshot time, if the working directory is a git repo. Run the commands in
    41	 "Capturing git state" below and record:>
    42	- **Branch:** <current branch>
    43	- **HEAD:** <short hash — first line of commit message>
    44	- **Working tree:** <clean | N modified, N staged, N untracked>
    45	- **Changed files:** <output of `git status --short`, fenced as a code block; omit if clean>
    46	- **Ahead/behind remote:** <e.g., "ahead 2" — omit if in sync or no upstream>
    47	<If not a git repo, write "Not a git repository." and move on.>
    48	
    49	## Recent findings
    50	<Bullet list of test results, eval outcomes, decisions made, or discoveries from this session
    51	 since the last snapshot. Pull these from the conversation — failed tests, passed tests,
    52	 key tradeoffs decided, bugs found. If none: "No new test/phase findings since last snapshot.">
    53	
    54	## Next steps
    55	<1–3 bullets: what the immediate next action is when work resumes. This is what makes
    56	 the snapshot resumable, not just archival.>
    57	
    58	## Last response (verbatim)
    59	<The full text of the most recent substantive assistant response, unedited.>
    60	
    61	---
    62	```
    63	
    64	## What counts as "the most recent response"
    65	
    66	The last substantive assistant answer before the snapshot request — not the snapshot confirmation itself, and not a trivial reply like "Sounds good." If the last few turns were short back-and-forth, use judgment and capture the last response with real content. If genuinely ambiguous (e.g., two large responses on different topics), ask which one — but default to the most recent rather than blocking.
    67	
    68	## If the exact response is unavailable
    69	
    70	If the verbatim most-recent response can't be recovered because the context was summarized, compacted, or truncated, save the closest available assistant response and label that section **`## Last response (best available — not guaranteed verbatim)`**. Do not silently reconstruct wording from memory and present it as exact. The skill's whole value is fidelity; a snapshot that *pretends* to be verbatim when it isn't is worse than one that names the gap honestly.
    71	
    72	## Gathering the metadata
    73	
    74	- **Findings**: scan the conversation since the previous snapshot (or session start) for test results, eval scores, phase completions, and decisions. When `snapshot.md` already exists, use the most recent entry's timestamp/header as the "since last snapshot" boundary so you don't repeat stale findings; otherwise summarize from the visible conversation. Compress to bullets — findings are metadata, not a transcript.
    75	- **Session label**: write it for searchability. Derive it from the session's first real request or the current file/topic being worked — not from the snapshot act itself. The user will be scanning a file or a chat list at 7am; "Snapshot 14" or "Chat session" is useless, "fintech onboarding PRD — risk section rewrite" is findable.
    76	- **Next steps**: if the conversation didn't state them explicitly, infer the obvious next action and mark it as inferred (e.g., "Next (inferred): run eval set against v2").
    77	
    78	## Capturing git state
    79	
    80	If a filesystem and shell are available, check whether the working directory is a git repo and capture state non-destructively (read-only commands only — never stage, commit, or stash as part of a snapshot):
    81	
    82	```bash
    83	git rev-parse --is-inside-work-tree   # gate: if this fails or prints false → "Not a git repository.", skip the rest
    84	git branch --show-current             # current branch (empty on detached HEAD)
    85	git log -1 --format='%h %s'           # HEAD: short hash + subject
    86	git status --short                    # changed files (empty output = clean tree)
    87	git status -sb | head -1              # ahead/behind upstream
    88	```
    89	
    90	Run each as its own read-only command rather than one `&&` chain — a single empty or non-zero step (clean tree, detached HEAD, a repo with no commits yet) shouldn't abort the rest. The block is bash; if only a different shell or a git API is available, capture at least **branch** and **HEAD** by whatever means you have. Never fail or skip the whole snapshot because git state couldn't be read — degrade gracefully: write "Git state unavailable." (or "Not a git repository.") and continue.
    91	
    92	Why this matters for the crash-recovery use case: the verbatim response tells you what was *said*; the git tree tells you what was actually *on disk* at that moment. After a crash, "HEAD was at a3f91c2 with 4 modified files" instantly tells the user whether their code changes survived or whether they're recovering from the snapshot text.
    93	
    94	## When to offer it proactively
    95	
    96	Don't guess at an abstract "natural stopping point" — an LLM has no reliable sense of one, and over-offering is noise. Offer a snapshot only on a concrete, observable cue, and only when there's meaningful unsaved progress that would be costly to reconstruct:
    97	
    98	- A test suite or eval run just went green after non-trivial work.
    99	- The user signals satisfaction right after a hard fix lands ("that worked", "perfect", "nice").
   100	- The user signals they're stepping away ("brb", "one sec", "heading to bed", "signing off").
   101	- A long session has produced unsaved findings and no snapshot exists yet.
   102	
   103	Offer at most once per stopping point, in one line. If the user declines, don't re-ask until the next distinct cue.
   104	
   105	## Safety and scope
   106	
   107	Snapshotting is read-mostly. The only write you may make is creating or prepending to `snapshot.md`.
   108	
   109	Do **not**, as part of a snapshot: stage, commit, stash, reset, checkout, or otherwise mutate git; run tests, builds, formatters, installers, migrations, or cleanup commands; or rewrite/summarize older entries. Capturing state must never change state — a "helpful" extra action taken while snapshotting is a bug, not a courtesy.
   110	
   111	## Behavior rules
   112	
   113	- Confirm completion on screen with the file path **and a compact git-state line** so the user sees their disk state at a glance without opening the file. Format:
   114	
   115	  > 📸 Snapshot saved to `./snapshot.md` (2026-06-09 22:47)
   116	  > Git: `feature/onboarding-v2` @ `a3f91c2` — 4 modified, 1 untracked, ahead 2
   117	
   118	  If not a git repo, the second line is simply omitted. Don't re-print the full snapshot content into the chat — the user just lived it.
   119	- Never trim, summarize, or "clean up" the verbatim response section. Crash recovery only works if the saved copy is the real copy.
   120	- If the most recent substantive response is the *same one* already captured in the previous snapshot (nothing new since), write a lightweight entry — metadata only, with "No new substantive response since the snapshot at <time>" in place of the verbatim block — rather than re-dumping an identical copy.
   121	- After reading the existing file, check its length. If it exceeds ~2,000 lines, mention once in the confirmation that you can archive older entries to `snapshot-archive.md` — but only do it if asked. Additive means additive.
   122	- Multiple snapshots in one session are fine and expected; each gets its own timestamped entry.== /Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/05-close/loose-ends/SKILL.md ==
     1	---
     2	name: loose-ends
     3	description: |
     4	  Post-work completeness sweep and execution (alias: close-loop). Check what was forgotten before declaring work done, and actively execute the final steps. Use only after work exists: a diff, draft, or completed change session. Compare what was delivered against what was requested, then look for dropped requirements, unrun verification, and leftover scaffolding. Actively offer to fix these gaps, run linters, sync docs, and stage/commit/push the work to git.
     5	
     6	  Trigger when the user asks "close loop", "close-loop", “what did I forget,” “did I miss anything,” “is this done,” “ready to ship/PR?”, or is about to call a multi-file or multi-requirement task complete. Also self-trigger before reporting substantial multi-step work finished.
     7	
     8	  Do not trigger before work exists; if the question is about a plan, decision, or approach, route to take-a-step-back. Do not use for phased-plan QA (phase-qa) or line-by-line code review (/code-review). This skill hunts what is absent, not what is wrong.
     9	---
    10	
    11	# Loose Ends
    12	
    13	Sweep the gap between what was asked and what was delivered — before "done" is said out loud.
    14	
    15	This is the suite's post-work counterpart to take-a-step-back. The decision skills guard the moment *before committing*; this one guards the moment *before declaring done*. Work rarely ends where the request did: a requirement falls out mid-session, a README still states the old count, a "tests pass" was true three edits ago, a debug print is still in the handler. The skill's job is to enumerate those absences with evidence — and to actively offer to execute the final closure steps (e.g., committing, pushing, syncing docs).
    16	
    17	## Core idea
    18	
    19	Answer one question: *what did I forget, and how do we close the loop?*
    20	
    21	The scope is the **delta between the contract and the delivery** — things that should exist and don't. This skill hunts the absent (dropped requirements, unrun tests) and actively offers to execute the final closure steps: syncing documentation, fixing lint errors, and committing/pushing the final result to git.
    22	
    23	## How this differs from its siblings
    24	
    25	- **take-a-step-back** (before the work) — "Am I making the best decision possible?" Challenges the frame before commitment. If the user asks "what am I missing?" about a plan or approach and no work exists yet, that question belongs there, not here.
    26	- **phase-qa** (around a plan doc) — bakes QA checklists into a phased planning doc and gates its phases. loose-ends needs no plan doc at all; it sweeps ad-hoc work against the original ask.
    27	- **/code-review** (on what's present) — finds bugs in delivered code. loose-ends finds the test that was never written, not the assertion that's wrong.
    28	- **bottom-line / linear** (compression) — reshape what's already there. They cannot surface what's absent.
    29	
    30	## Method — reconstruct, inventory, cross off
    31	
    32	1. **Reconstruct the contract.** Re-read the original request — and any plan doc, ticket, or acceptance list it pointed at. List every named deliverable, *including the throwaway clauses*.
    33	2. **Inventory the delivery.** `git diff` / `git status` for code; the artifact itself for prose or config. What actually changed, in which files?
    34	3. **Cross off and sweep.** Match each contract item against the inventory, then run the sweep list below over the changed surface only.
    35	4. **Offer Execution.** Propose to actively fix the gaps, run the missing tests, sync the docs, and commit/push.
    36	
    37	## What to sweep for
    38	
    39	- **Dropped requirements** — named in the ask, absent from the diff (e.g., a sync script was written but never executed).
    40	- **Git Handoff** — are there uncommitted changes? Offer to auto-generate a conventional commit summarizing the session, then `git commit` and `git push`.
    41	- **Formatting & Lockfiles** — offer to run the linter/formatter to catch mid-session sloppiness. Check if `package.json` changed but the lockfile wasn't regenerated.
    42	- **Stale sibling surfaces (Auto-Sync)** — the README, changelog, `.env.example`, or docs that mirror the changed thing. Offer to actively apply the diffs to these files.
    43	- **Unrun verification** — every "tests pass" or "build works" claimed: was it run *after the last edit*? Offer to run it now.
    44	- **Leftover scaffolding** — TODO/FIXME, debug prints, commented-out blocks, scratch test files. Offer to delete them.
    45	- **Cleanup and comms** — files created and abandoned, the version bump, the person or channel that needs telling.
    46	
    47	## Output format
    48	
    49	Lead with the verdict — the one line that survives skimming:
    50	
    51	> **3 loose ends — 2 block "done."** — or — **Swept clean — nothing forgotten. Ship it.**
    52	
    53	**Contract:** [One line: what the work promised, sourced from the original ask — not from what got built.]
    54	
    55	**Loose ends:** (omit entirely on a clean sweep)
    56	1. **[The missing thing]** *(blocks done | worth closing)* — where it should live, the evidence it's absent, and the one-line close-out.
    57	
    58	Order blocking-first. *Blocks done* means the original ask is not met without it; *worth closing* means "done" survives, but the operator should ship with it open consciously, not accidentally.
    59	
    60	**Next Steps / Close Loop:**
    61	- Offer to execute the specific fixes for the loose ends (e.g., "I can run the backfill script and delete the debug prints for you.").
    62	- Offer to format, commit, and push the work with a generated commit message.
    63	
    64	**Also checked:** [Optional, one line — the sweep classes that came back clean, so a short list isn't mistaken for a short look.]
    65	
    66	## Principles
    67	
    68	**Absence needs an address.** Every finding names where the missing thing should live and the evidence it isn't there. "You should probably add tests" with no pointer is vibes, not a finding.
    69	
    70	**Evidence or silence.** Report only what the diff, a grep, or the session transcript can show. If you can't see the work — no diff, no artifact, no transcript — say what you need and stop; never sweep from imagination.
    71	
    72	**"Ship it" is a verdict, not a failure.** A clean sweep ends in one line. Never invent a finding to justify firing — a skill that always finds something is a skill nobody believes.
    73	
    74	**Hunt the absent, not the wrong.** Re-reviewing delivered code for bugs is scope creep into /code-review. If you notice a bug in passing, hand it off in one clause; don't make it a finding.
    75	
    76	**The contract is the request, not your taste.** Don't flag features nobody asked for. The two exceptions are stale sibling surfaces and leftover scaffolding — nobody asks for those either, but "done" implies them.
    77	
    78	**Blocking-first, always tagged.** The operator should be able to close item 1, consciously defer item 3, and ship — without re-reading anything.
    79	
    80	## Scaling
    81	
    82	- **Single-file, single-ask change** → sweep silently, report the verdict in one line either way.
    83	- **Multi-file or multi-requirement work** → the full format, blocking-first.
    84	- **Agent-completed work the user didn't watch** → weight the unrun-verification class heaviest; claims made mid-session decay fastest.
    85	- **No visible work** (no diff, nothing pasted, nothing in session) → refuse the sweep and name what you need — or route to take-a-step-back if the work simply hasn't started.
    86	
    87	## Example 1 — a feature that feels finished
    88	
    89	Input (abridged): "I think the CSV export feature is done — did I forget anything?" (Original ask, earlier in session: "add CSV export for the transactions table — filterable by date range, and make sure big exports don't time out.")
    90	
    91	Output:
    92	
    93	> **4 loose ends — 2 block "done."**
    94	>
    95	> **Contract:** CSV export for transactions, filterable by date range, safe on large exports.
    96	>
    97	> **Loose ends:**
    98	> 1. **Date-range filter** *(blocks done)* — named in the ask; `export.ts` takes no date params and the UI has no picker. Close out: add `start`/`end` params, or descope it explicitly with the requester.
    99	> 2. **Large-export safety** *(blocks done)* — the handler builds the whole CSV in memory; nothing in the diff addresses the timeout clause. Close out: stream rows, or cap with a row-count warning.
   100	> 3. **`docs/api.md`** *(worth closing)* — still lists the endpoint table without `/export`. Close out: one row.
   101	> 4. **Debug print** *(worth closing)* — `console.log("rows", rows.length)` left in the handler. Close out: delete the line.
   102	>
   103	> **Close Loop:** Shall I stream the CSV rows to fix the timeout, delete the debug print, and then commit & push this as `feat: add date-filtered CSV exports`?
   104	>
   105	> **Also checked:** tests added and run after the last edit (green); no `.only`/`.skip`; changelog entry present.
   106	
   107	## Example 2 — a clean sweep that stays quiet
   108	
   109	Input (abridged): "Renamed `formatDate` to `formatLocalDate` across the repo — forget anything?"
   110	
   111	Output:
   112	
   113	> **Swept clean — nothing forgotten. Ship it.**
   114	>
   115	> **Also checked:** grep for `formatDate` returns zero live references; tests run after the last edit, green; no docs mention the old name; no scaffolding introduced.
   116	
   117	No manufactured findings, no padded template. Calibration is staying quiet.
   118	
   119	## Example 3 — the pre-commit question this skill must not take
   120	
   121	Input (abridged): "We're about to start migrating auth to OAuth — what am I forgetting?"
   122	
   123	Output:
   124	
   125	> Nothing to sweep yet — the migration doesn't exist, so there's no delivery to diff against the ask. That's a pre-commit question: what you want is **take-a-step-back**, which will pressure-test the plan's fragile assumption and reversibility before you start. Come back here when there's a diff and you're about to call it done.
   126	
   127	## What success looks like
   128	
   129	The operator either closes a short, evidenced list or ships with earned confidence — never wades through speculative cautions, never re-litigates work that was delivered fine, and never finds out a week later that the README still says nine.

exec
/bin/zsh -lc "find '/Users/noelsaw/Documents/GH Repos' -maxdepth 2 -type d \\( -name 'gsd-core' -o -name 'xyz-3-agents-swarm' -o -name 'giant-brains-claude-skills' \\) | sort" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-21302-28772
 succeeded in 0ms:
/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills
/Users/noelsaw/Documents/GH Repos/gsd-core
/Users/noelsaw/Documents/GH Repos/gsd-core/gsd-core
/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm

exec
/bin/zsh -lc "find .claude -maxdepth 3 \\( -type f -o -type l \\) | sort | sed -n '1,200p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-21302-28772
 succeeded in 0ms:
.claude/commands/ask_self.md
.claude/commands/reingest.md
.claude/settings.json
.claude/skills/git-pulse-exec-recap/SKILL.md
.claude/skills/git-pulse-team-recap/SKILL.md
.claude/skills/welcome/SKILL.md
.claude/skills/welcome/demo-transcript.md

exec
/bin/zsh -lc "for f in '/Users/noelsaw/Documents/GH Repos/gsd-core/gsd-core/docs/explanation/the-phase-loop.md' '/Users/noelsaw/Documents/GH Repos/gsd-core/gsd-core/docs/explanation/context-engineering.md' '/Users/noelsaw/Documents/GH Repos/gsd-core/gsd-core/docs/explanation/multi-agent-orchestration.md' '/Users/noelsaw/Documents/GH Repos/gsd-core/gsd-core/docs/reference/state-md.md' '/Users/noelsaw/Documents/GH Repos/gsd-core/gsd-core/docs/reference/context-md.md' '/Users/noelsaw/Documents/GH Repos/gsd-core/gsd-core/docs/reference/planning-artifacts.md'; do echo \"== "'$f =="; nl -ba "$f" | sed -n '"'1,260p'; done" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-21302-28772
 succeeded in 0ms:
== /Users/noelsaw/Documents/GH Repos/gsd-core/gsd-core/docs/explanation/the-phase-loop.md ==
nl: /Users/noelsaw/Documents/GH Repos/gsd-core/gsd-core/docs/explanation/the-phase-loop.md: No such file or directory
== /Users/noelsaw/Documents/GH Repos/gsd-core/gsd-core/docs/explanation/context-engineering.md ==
nl: /Users/noelsaw/Documents/GH Repos/gsd-core/gsd-core/docs/explanation/context-engineering.md: No such file or directory
== /Users/noelsaw/Documents/GH Repos/gsd-core/gsd-core/docs/explanation/multi-agent-orchestration.md ==
nl: /Users/noelsaw/Documents/GH Repos/gsd-core/gsd-core/docs/explanation/multi-agent-orchestration.md: No such file or directory
== /Users/noelsaw/Documents/GH Repos/gsd-core/gsd-core/docs/reference/state-md.md ==
nl: /Users/noelsaw/Documents/GH Repos/gsd-core/gsd-core/docs/reference/state-md.md: No such file or directory
== /Users/noelsaw/Documents/GH Repos/gsd-core/gsd-core/docs/reference/context-md.md ==
nl: /Users/noelsaw/Documents/GH Repos/gsd-core/gsd-core/docs/reference/context-md.md: No such file or directory
== /Users/noelsaw/Documents/GH Repos/gsd-core/gsd-core/docs/reference/planning-artifacts.md ==
nl: /Users/noelsaw/Documents/GH Repos/gsd-core/gsd-core/docs/reference/planning-artifacts.md: No such file or directory

exec
/bin/zsh -lc "for f in '/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/skills/xyz/SKILL.md' '/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/src/marathon-yaml.js'; do echo \"== "'$f =="; nl -ba "$f" | sed -n '"'1,220p'; done" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-21302-28772
 succeeded in 0ms:
== /Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/skills/xyz/SKILL.md ==
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
== /Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/src/marathon-yaml.js ==
     1	'use strict';
     2	
     3	// marathon-yaml.js — zero-dep reader for the CONSTRAINED MARATHON.yaml subset (Phase 4 / M5).
     4	// Not a general YAML parser: it understands exactly the structure the spec defines —
     5	//   name: <marathon name>
     6	//   phases:
     7	//     - id: p1
     8	//       name: <phase name>
     9	//       reviewer: codex | gemini (or codex*/gemini*)
    10	//       max_review_rounds: <int>
    11	//       depends_on: <phase id>        (optional)
    12	// Disambiguation is by indent: a top-level `name:` (indent 0) is the marathon name; an indented
    13	// `name:` is a phase field. Anything outside this shape is a parse error, on purpose — better a loud
    14	// failure than a silently-misread orchestration plan.
    15	
    16	// brief = path to the phase's task markdown; artifact = comma-separated repo-relative file(s) the
    17	// builder may create/edit. Both optional in the schema but the orchestrator needs `brief` to run a phase.
    18	const PHASE_FIELDS = new Set(['id', 'name', 'reviewer', 'max_review_rounds', 'depends_on', 'brief', 'artifact']);
    19	
    20	function stripQuotes(v) {
    21	  if (v.length >= 2 && ((v[0] === '"' && v.endsWith('"')) || (v[0] === "'" && v.endsWith("'")))) {
    22	    return v.slice(1, -1);
    23	  }
    24	  return v;
    25	}
    26	
    27	// Split "key: value" into [key, value]; returns null if not a key:value line.
    28	function splitKV(s) {
    29	  const i = s.indexOf(':');
    30	  if (i < 0) return null;
    31	  const key = s.slice(0, i).trim();
    32	  let val = s.slice(i + 1).trim();
    33	  // drop trailing inline comment (only when clearly separated — ` #...`)
    34	  const c = val.indexOf(' #');
    35	  if (c >= 0) val = val.slice(0, c).trim();
    36	  return [key, stripQuotes(val)];
    37	}
    38	
    39	function indentOf(line) {
    40	  let n = 0;
    41	  while (n < line.length && line[n] === ' ') n++;
    42	  return n;
    43	}
    44	
    45	/**
    46	 * Parses the constrained MARATHON.yaml subset (a top-level `name:` plus a
    47	 * `phases:` list — see the file header for the exact grammar). Not a general
    48	 * YAML parser; anything outside the documented shape throws, on purpose.
    49	 * @param {string} text - raw MARATHON.yaml file contents
    50	 * @returns {{name: string, phases: Object[]}}
    51	 * @throws {Error} on any line outside the documented grammar (unknown field, malformed key:value, etc.)
    52	 */
    53	function parseMarathonYaml(text) {
    54	  const out = { name: '', phases: [] };
    55	  let inPhases = false;
    56	  let cur = null; // current phase being filled
    57	  const lines = String(text).split(/\r?\n/);
    58	  for (let ln = 0; ln < lines.length; ln++) {
    59	    const raw = lines[ln];
    60	    const noComment = raw.replace(/^(\s*)#.*$/, '$1'); // whole-line comment → blank (keep indent token)
    61	    if (noComment.trim() === '') continue;
    62	    const indent = indentOf(raw);
    63	    const trimmed = raw.trim();
    64	
    65	    if (indent === 0) {
    66	      if (trimmed === 'phases:') { inPhases = true; cur = null; continue; }
    67	      const kv = splitKV(trimmed);
    68	      if (kv && kv[0] === 'name') { out.name = kv[1]; inPhases = false; continue; }
    69	      throw new Error(`line ${ln + 1}: unexpected top-level line: ${trimmed}`);
    70	    }
    71	
    72	    if (!inPhases) throw new Error(`line ${ln + 1}: indented line outside phases: ${trimmed}`);
    73	
    74	    if (trimmed.startsWith('- ')) {
    75	      cur = { id: '', name: '', reviewer: '', max_review_rounds: '', depends_on: '', brief: '', artifact: '' };
    76	      out.phases.push(cur);
    77	      const rest = trimmed.slice(2).trim(); // inline first field, e.g. "id: p1"
    78	      if (rest) {
    79	        const kv = splitKV(rest);
    80	        if (!kv) throw new Error(`line ${ln + 1}: malformed list item: ${trimmed}`);
    81	        if (!PHASE_FIELDS.has(kv[0])) throw new Error(`line ${ln + 1}: unknown phase field '${kv[0]}'`);
    82	        cur[kv[0]] = kv[1];
    83	      }
    84	      continue;
    85	    }
    86	
    87	    // an indented field line belonging to the current phase
    88	    if (!cur) throw new Error(`line ${ln + 1}: phase field before any '- id:' item: ${trimmed}`);
    89	    const kv = splitKV(trimmed);
    90	    if (!kv) throw new Error(`line ${ln + 1}: malformed phase field: ${trimmed}`);
    91	    if (!PHASE_FIELDS.has(kv[0])) throw new Error(`line ${ln + 1}: unknown phase field '${kv[0]}'`);
    92	    cur[kv[0]] = kv[1];
    93	  }
    94	  return out;
    95	}
    96	
    97	/**
    98	 * Validates a parsed marathon plan and resolves `depends_on` into a
    99	 * deterministic topological execution order (authoring order preserved among
   100	 * equally-ready phases).
   101	 * @param {{phases: Object[]}} plan - as returned by {@link parseMarathonYaml}
   102	 * @returns {Object[]} phases in execution order
   103	 * @throws {Error} on an empty plan, duplicate id, missing required field, bad
   104	 *   `reviewer`, or an unknown/self/cyclic `depends_on`
   105	 */
   106	function resolveOrder(plan) {
   107	  const phases = plan.phases || [];
   108	  if (phases.length === 0) throw new Error('no phases defined');
   109	  const byId = new Map();
   110	  for (const p of phases) {
   111	    if (!p.id) throw new Error('a phase is missing its id');
   112	    if (byId.has(p.id)) throw new Error(`duplicate phase id: ${p.id}`);
   113	    if (!p.reviewer) throw new Error(`phase ${p.id}: missing reviewer`);
   114	    if (!/^(codex|gemini)/.test(p.reviewer)) {
   115	      throw new Error(`phase ${p.id}: reviewer '${p.reviewer}' must start with codex or gemini`);
   116	    }
   117	    if (p.depends_on === p.id) throw new Error(`phase ${p.id}: depends_on itself`);
   118	    byId.set(p.id, p);
   119	  }
   120	  for (const p of phases) {
   121	    if (p.depends_on && !byId.has(p.depends_on)) {
   122	      throw new Error(`phase ${p.id}: depends_on unknown phase '${p.depends_on}'`);
   123	    }
   124	  }
   125	  // Topological sort (single-parent depends_on chain, but handle a general DAG deterministically:
   126	  // preserve authoring order among ready nodes).
   127	  const order = [];
   128	  const done = new Set();
   129	  const remaining = phases.slice();
   130	  let guard = 0;
   131	  while (remaining.length) {
   132	    if (guard++ > phases.length + 1) throw new Error('dependency cycle detected');
   133	    let progressed = false;
   134	    for (let i = 0; i < remaining.length; i++) {
   135	      const p = remaining[i];
   136	      if (!p.depends_on || done.has(p.depends_on)) {
   137	        order.push(p);
   138	        done.add(p.id);
   139	        remaining.splice(i, 1);
   140	        progressed = true;
   141	        break; // restart scan to keep authoring order deterministic
   142	      }
   143	    }
   144	    if (!progressed) throw new Error('dependency cycle detected');
   145	  }
   146	  return order;
   147	}
   148	
   149	module.exports = { parseMarathonYaml, resolveOrder };

exec
/bin/zsh -lc "find '/Users/noelsaw/Documents/GH Repos/gsd-core' -maxdepth 3 -type f | sed -n '1,120p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-21302-28772
 succeeded in 0ms:
/Users/noelsaw/Documents/GH Repos/gsd-core/VERSIONING.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.githooks/pre-push
/Users/noelsaw/Documents/GH Repos/gsd-core/.githooks/pre-commit
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/research/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/kilo/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/intel/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/cline/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/ui/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/assumption-delta/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/pattern-mapper/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/gemini/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/copilot/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/cursor/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/security/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/claude/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/code-review/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/codex/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/augment/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/qwen/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/mempalace/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/trae/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/drift/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/ai-integration/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/schema-gate/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/audit/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/codebuddy/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/profile-pipeline/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/windsurf/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/hermes/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/graphify/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/antigravity/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/tdd/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/nyquist/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/kimi/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/gap-analysis/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/capabilities/opencode/capability.json
/Users/noelsaw/Documents/GH Repos/gsd-core/LICENSE
/Users/noelsaw/Documents/GH Repos/gsd-core/CONTEXT.md
/Users/noelsaw/Documents/GH Repos/gsd-core/bin/install.js
/Users/noelsaw/Documents/GH Repos/gsd-core/bin/gsd-mcp-server.js
/Users/noelsaw/Documents/GH Repos/gsd-core/bin/lib/ui-safety-gate.cjs
/Users/noelsaw/Documents/GH Repos/gsd-core/CHANGELOG.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/zesty-rams-march.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/humble-geese-roam.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/1682-opencode-subset-dialect.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/humble-dogs-gather.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/sturdy-voles-dart.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/humble-tunas-munch.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/lively-lynx-snooze.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/eager-ibex-bark.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/rapid-pumas-click.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/1920-installer-capability-generators-host-version.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/nimble-jays-roar.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/agile-newts-roar.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/daring-otters-dart.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/1778-thread-workflow-frontmatter-set-args.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/graceful-geese-click.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/1733-windows-agent-skills-path-leak.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/witty-seals-snooze.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/vivid-seals-purr.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/1591-phase-complete-details-wrapped-checklist.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/1772-graphify-update-multi-line-command.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/humble-seals-rest.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/tidy-pumas-munch.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/kind-lynx-munch.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/gallant-cats-hum.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/1761-state-json-unbounded-milestone-read-path.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/rapid-orcas-sing.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/merry-mice-travel.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/gallant-wasps-wave.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/sharp-otters-romp.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/calm-eagles-tumble.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/plucky-bears-snooze.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/README.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/plucky-moles-sing.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/1847-claude-sonnet-5-standard-tier.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/clever-rams-march.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/nimble-ibex-tumble.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/eager-elks-frolic.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/graceful-wasps-caper.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/1682-opencode-mcp-binding.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/proud-bears-purr.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/serene-birds-rest.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/lucky-tigers-leap.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/humble-zebras-zip.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/serene-lemurs-march.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/wise-elks-caper.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/1528-verify-work-security-blocked-next-phase.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/hooks-dist-scoped-ci-race.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/bold-ravens-wake.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/curious-koalas-gather.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/proud-bears-roam.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/happy-jays-travel.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/graceful-badgers-click.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/daring-badgers-forage.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/1580-999-sentinel-milestone-roadmap.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/1817-state-rebuild.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/bold-orcas-wander.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/tidy-mice-cheer.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/graceful-moles-gather.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/1747-new-project-search-provider-keys.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/humble-sloths-jump.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/tidy-tunas-click.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/archived/verifier-debt-gate.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/archived/191-retire-sdk-package-seam.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/archived/steady-jays-click.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/archived/3758-consolidate-installer-tests.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/archived/3815-phase-insert-bullet-roadmap.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/archived/2937-statusline-context-position.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/archived/fix-3120-secure-phase-empty-register.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/archived/fix-3097-3099-executor-worktree-path.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/archived/quick-deer-squeak.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/archived/442-config-dir-equals-truncation.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/archived/migration-batch-15-ts.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/archived/3740-consolidate-phase-tests.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/archived/gentle-tigers-roar.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/archived/3707-worktree-orphan-reap.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/archived/3595-fs-fault-injection-atomic-write.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/archived/614-discuss-phase-shim-resolution.md
/Users/noelsaw/Documents/GH Repos/gsd-core/.changeset/archived/kind-foxes-click.md

exec
/bin/zsh -lc 'for f in PROJECT/PDDA.md utils/pdda/pdda.sh utils/pdda/pdda-doc-ready.sh utils/pdda/pdda-edit-doc-hook.sh .claude/commands/ask_self.md .claude/commands/reingest.md; do [ -f "$f" ] && echo "== $f ==" && nl -ba "$f" | sed -n '"'1,260p'; done" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-21302-28772
 succeeded in 0ms:
== PROJECT/PDDA.md ==
     1	# Project-Driven Doc Automation (PDDA)
     2	
     3	PDDA is the document operating layer for this repo. Its job is to keep project plans, bug-fix docs,
     4	research notes, and roadmap pointers clean enough that an agent can pick up work with minimal drift
     5	and enough structure that routine hygiene can be automated instead of re-decided every session.
     6	
     7	The core idea is simple:
     8	
     9	- deterministic scripts enforce the parts that should never require judgment
    10	- an LLM reviewer flags structural or planning-quality gaps that are hard to express as regex alone
    11	- `ROADMAP.md` stays a pointer/index, while project detail lives in the individual project docs
    12	
    13	## Goals
    14	
    15	- Keep `PROJECT/2-WORKING` limited to docs that are truly active.
    16	- Ensure every active doc answers two questions at a glance: what was just completed, and what is next.
    17	- Make phased plans automation-ready by requiring explicit QA gates.
    18	- Prevent plan rot: stale files, missing next steps, hardcoded paths, and hidden scope drift.
    19	- Give agents one repeatable contract for project docs, bug-fix docs, and experimental plans.
    20	
    21	## Non-goals
    22	
    23	- PDDA does not replace the project docs themselves.
    24	- PDDA does not decide product strategy.
    25	- PDDA does not auto-rewrite nuanced plan content without review.
    26	- PDDA does not turn `ROADMAP.md` into a second execution plan.
    27	
    28	## Canonical document model
    29	
    30	PDDA assumes four lifecycle buckets:
    31	
    32	- `PROJECT/1-INBOX`: new ideas, rough proposals, untriaged notes
    33	- `PROJECT/2-WORKING`: active docs that should be updated as work progresses
    34	- `PROJECT/3-COMPLETED`: completed docs with an outcome
    35	- `PROJECT/4-MISC`: reference, stale, superseded, or abandoned docs
    36	
    37	Within that model:
    38	
    39	- `ROADMAP.md` is the index of current, completed, attempted, and deferred work
    40	- project detail lives in the individual `PROJECT/**` documents
    41	- a working doc is the canonical source of truth for that effort until it is completed, deferred, or superseded
    42	- `blank.md` placeholders are scaffolding and should be ignored by PDDA checks
    43	
    44	## Required contract for active docs
    45	
    46	Every doc in `PROJECT/2-WORKING` should have:
    47	
    48	1. YAML frontmatter with at least `title`, `status`, `created`, `updated`, `owner`, and `goal`
    49	2. a near-top status table with the exact columns:
    50	
    51	```md
    52	## Status
    53	
    54	| What was just completed | What's next |
    55	|---|---|
    56	| ... | ... |
    57	```
    58	
    59	3. clear phase or work sections if the doc is a plan
    60	4. a table of contents (`## Table of contents`) listing each phase, if the plan is multi-phase — so a
    61	   cold agent can see the full phase span and jump to the live one without scrolling the whole body
    62	5. QA gates or acceptance criteria after each phase if the plan is multi-phase
    63	6. for any discovery or spike phase, its findings written **back into this doc** before its QA gate can
    64	   pass (see [Discovery & spike phases](#discovery--spike-phases))
    65	7. repo-relative paths only; no hardcoded absolute local paths
    66	
    67	Recommended fields when relevant:
    68	
    69	- `related`
    70	- `reviewed`
    71	- `branch`
    72	- `non_goals`
    73	- `gh_issue`
    74	- `effort`, `complexity`, `risk`, `phases` — triage ratings; **required for medium-large work** (see
    75	  [Triage ratings for medium-large work](#triage-ratings-for-medium-large-work))
    76	
    77	## Triage ratings for medium-large work
    78	
    79	So automation can pick *which* task to pursue without re-reading every plan, every newly recorded
    80	**medium-large** task or project carries four triage fields in its frontmatter:
    81	
    82	| Field | Range | Meaning |
    83	|---|---|---|
    84	| `effort` | integer `1`–`5` | how much work — `1` low, `5` highest |
    85	| `complexity` | integer `1`–`5` | how intricate / how many moving parts — `1` low, `5` highest |
    86	| `risk` | integer `1`–`5` | blast radius + uncertainty — `1` safe/contained, `5` one-way-door or unknown |
    87	| `phases` | positive integer | total number of phases in the plan |
    88	
    89	```yaml
    90	effort: 2
    91	complexity: 3
    92	risk: 1
    93	phases: 4
    94	```
    95	
    96	`risk` should track the repo's existing reversibility scale (`Easy / Costly / One-way door`,
    97	`AGENTS.md` #3): `1`–`2` ≈ Easy, `3` ≈ Costly, `4`–`5` ≈ one-way door / high uncertainty. It is not a
    98	parallel notion of danger — it is that scale expressed as a number.
    99	
   100	**Scope.** Required for medium-large work (project plans, experiments, features, multi-phase efforts).
   101	Genuinely small/trivial docs (a typo, a path repoint, a ≤2–3 line bug-fix — the same floor as the
   102	issue-first SOP) do not need them. "Medium-large" is a judgment, so *presence* is enforced by the LLM
   103	layer, not a regex (below).
   104	
   105	### How to combine them — derive, don't store
   106	
   107	There is deliberately **no stored composite "score" field.** A frozen aggregate would (a) drift from
   108	the three numbers it came from, violating Principle #4 (*one canonical place per fact*), and (b) bake a
   109	weighting choice into every doc that you then cannot re-tune without rewriting them. Compute the
   110	selection signal **live, at selection time**, from the raw fields:
   111	
   112	- **`risk` is a gate, not an addend.** A trivial-but-risky task (`effort 1`, `complexity 1`, `risk 5`)
   113	  is easy to *do* but exactly what automation should not auto-pick — folding risk into a linear sum
   114	  lets it slip through mid-ranked. Gate on it instead.
   115	- **`effort` and `complexity` are correlated** (complex work is usually effortful), so summing them is
   116	  a rough "size" proxy, not two independent signals — treat the sum as one ease axis, not two.
   117	
   118	Reference selection rule (tune the thresholds per repo):
   119	
   120	```text
   121	eligible      = risk <= 2                 # hard safety gate; risk >= 4 => route to a human
   122	ease          = effort + complexity       # 2..10, lower = easier
   123	pick          = among eligible, lowest ease, then fewest phases as the tiebreak
   124	```
   125	
   126	This keeps the raw ratings canonical and queryable while letting the "what's the easiest *safe* thing
   127	to grab" logic live in one place that can evolve. (See the resolved `priority` note under
   128	[Proposed extensions](#proposed-extensions-not-yet-locked).)
   129	
   130	### How this is enforced
   131	
   132	- **deterministic (values)** — `pdda.sh frontmatter` validates the fields **only when present**:
   133	  `effort`/`complexity`/`risk` must be integers `1`–`5`, `phases` a positive integer. A present-but-bad
   134	  value is unambiguous, so it `error`s. The script does **not** force presence — it cannot know whether
   135	  a doc is "medium-large."
   136	- **LLM (presence)** — `pdda-doc-ready.sh` flags a medium-large plan that is *missing* the triage
   137	  ratings. Whether a doc is medium-large is a judgment, so it stays advisory/warn-capped like every
   138	  other readiness finding.
   139	
   140	## Why the two-column status header matters
   141	
   142	The status table is the front door for both humans and automation.
   143	
   144	- The left column is the last verified state change.
   145	- The right column is the next action.
   146	- If either is missing, an agent has to reconstruct state from the body, which is slow and error-prone.
   147	
   148	PDDA therefore treats the exact header names as a contract, not a style preference. The header must be
   149	exactly `What was just completed | What's next` — there is no alias/compatibility window. (One was
   150	specced with a `2026-07-31` cutover, but a single-repo system controls its own docs: no doc here used
   151	an old alias, so a dated, silently-changing branch guarded nothing and was removed 2026-06-22.)
   152	
   153	## Discovery & spike phases
   154	
   155	Discovery and spike phases exist to *learn* — reverse-engineer an existing system, probe an unknown,
   156	prove or kill a risky approach before committing the plan to it. Their output is knowledge, and under
   157	Principle #1 (*docs are the runtime state, not a record of it*) that knowledge is project state. If it
   158	lives only in an agent's context or a throwaway scratch note, a cold agent resuming the plan cannot see
   159	what was learned, why a path was chosen or abandoned, or what the spike actually proved — and the work
   160	gets re-done.
   161	
   162	Contract: **a phase tagged as discovery or spike must write its findings back into the originating plan
   163	doc before its QA gate can pass.** Concretely, that phase's section (or a clearly linked sibling
   164	section in the same doc) must capture:
   165	
   166	- **what was investigated** — the system/area reverse-engineered or the question the spike asked
   167	- **what was found** — the concrete mechanics learned, with repo-relative pointers (`file:line`) where
   168	  the finding lives in code, not a vague summary
   169	- **what it changes** — how the finding confirms, redirects, or kills the plan's later phases; an
   170	  unfinished "we'll know after the spike" left dangling is itself the gap
   171	
   172	This satisfies Principle #4 (*one canonical place per fact*): the originating plan is that place. A
   173	spike whose findings sit in chat is the exact drift PDDA exists to prevent. The QA gate for a
   174	discovery/spike phase therefore includes "findings are written back to this doc" as an acceptance
   175	criterion alongside the phase's normal checks.
   176	
   177	Enforcement is **advisory (LLM layer, warn-capped)** — `pdda-doc-ready.sh` flags a discovery/spike
   178	phase whose findings were not written back. "Did the agent actually capture what it learned" is a
   179	judgment a regex cannot make honestly, so it stays with the LLM reviewer and, like every finding from
   180	that layer, never blocks a build (see [LLM-assisted doc readiness review](#2-llm-assisted-doc-readiness-review)).
   181	To tag a phase, name it plainly (e.g. `## Phase 2 — Discovery: …` / `## Phase 3 — Spike: …`) or set
   182	`doc_type: research` / a phase-level marker the reviewer can see.
   183	
   184	## Bug-fix doc stance
   185	
   186	Bug-fix docs may use a lighter template than multi-phase project plans, but they still need:
   187	
   188	- the minimum frontmatter
   189	- the same `## Status` table while active
   190	- a short bug description
   191	- source of truth for intake, including a GitHub issue when relevant
   192	- verification steps
   193	
   194	GitHub issues are the default intake for substantive bug reports (issue-first SOP — see below). They are not a
   195	substitute for the local active-work doc once execution starts in this repo.
   196	
   197	## GitHub issue intake
   198	
   199	GitHub issues are the **default front door** for substantive work — every project plan and every
   200	non-trivial bug/fix opens an issue *first*, and that issue gets an in-repo pointer doc. The signal
   201	stream lives in GitHub (machine-queryable state, labels, commit↔issue linkage); the execution
   202	surface of record stays in `PROJECT/**`. This is the **issue-first SOP**; the bug-fix stance above
   203	states the principle, and this section owns the *format*. To prevent duplicate intake and forgotten
   204	work, every captured `GH-*.md` doc is also **parked immediately in `ROADMAP.md`** as a one-line queue
   205	entry until it is promoted, deferred, or closed.
   206	
   207	**Floor (what needs an issue).** The operational test is **lines of code touched**: any change
   208	beyond a **2–3 line** fix opens a GitHub issue first, and its local plan doc is named after that
   209	issue (see Filename below). Project plans, experiments, and features are always above this line.
   210	**Exempt:** genuinely trivial edits — a ≤2–3 line code fix, a typo, a path repoint, a doc-only
   211	one-liner, formatting — commit directly with a clear message and no issue. When in doubt, open the
   212	issue — it is a cheap `gh issue create`. The SOP applies to *new* efforts going forward; in-flight
   213	`1-INBOX`/`2-WORKING` docs are not backfilled.
   214	
   215	Capture a tracked issue as a doc in `PROJECT/1-INBOX/` using this convention:
   216	
   217	- **Filename:** `GH-<number>-VERY-SHORT-DESCRIPTION.md` — the local plan doc is always named after
   218	  its GitHub issue (e.g. `GH-1234-SHOWME-COMMAND.md`, `GH-11-CROSS-REPO-TARGETING.md`). Keep the
   219	  description to ~2–4 words; the issue number is the real key, the slug is just a human hint.
   220	  SCREAMING-KEBAB to match the other inbox docs; no zero-padding — mirror the GitHub issue number.
   221	  `<number>` resolves against `origin` (a single canonical repo), so the bare number is unambiguous.
   222	- **Minimum frontmatter:** `gh_issue`, `source` (the full issue URL), `title`, `status`
   223	  (`Proposed (1-INBOX — not yet active)`), `created`, and `doc_type` (`feedback` or `bugfix`).
   224	  For medium-large captures, also include the triage ratings `effort`, `complexity`, `risk`, `phases`
   225	  at capture time, so the queue can be triaged before promotion (see
   226	  [Triage ratings for medium-large work](#triage-ratings-for-medium-large-work)).
   227	- **Body:** transcribe the issue's actionable substance (the asks / acceptance criteria), not the whole
   228	  thread. The live issue stays the discussion surface; this doc is the in-repo capture and back-reference.
   229	
   230	Lifecycle:
   231	
   232	- The `GH-` inbox doc is the **capture**, not the active-work doc. It carries no `## Status` table while
   233	  it sits in `1-INBOX` (the inbox is the rough/untriaged bucket).
   234	- Capture time also adds a **one-line `ROADMAP.md` queue pointer** linking that inbox doc. This is a
   235	  temporary parking slot: it makes fresh intake visible to humans and automation before promotion,
   236	  which is the duplicate-prevention guard.
   237	- When execution starts, **promote** it to `PROJECT/2-WORKING/` — keep the `GH-` prefix for provenance —
   238	  and it must then satisfy the full active-doc contract (frontmatter, exact status table, QA gates if
   239	  phased), **carrying `gh_issue` forward**. The `ROADMAP.md` pointer is therefore required twice:
   240	  first as a queued parking entry at capture, then as an active-work ledger entry after promotion.
   241	  This is the concrete mechanism behind "GitHub issues are not a substitute for the local active-work
   242	  doc once execution starts" (bug-fix stance above).
   243	- If a captured issue is never actioned it ages out of `1-INBOX` like any other untriaged note; if it is
   244	  closed without work, move the doc to `PROJECT/4-MISC` and remove its queue pointer from `ROADMAP.md`.
   245	
   246	A foreign-repo issue (not `origin`) is the rare exception: the `source:` URL disambiguates it, since the
   247	bare `GH-<number>` only guarantees uniqueness within the canonical repo.
   248	
   249	## Automation layers
   250	
   251	PDDA should have two classes of automation:
   252	
   253	Implementation note:
   254	
   255	- the automation ships as a single dispatcher, `utils/pdda/pdda.sh`, which sources shared helpers from
   256	  `utils/pdda/pdda-lib.sh`
   257	- every deterministic check is a subcommand: `pdda.sh frontmatter`, `pdda.sh status-table`,
   258	  `pdda.sh hardcoded-paths`, `pdda.sh roadmap`, `pdda.sh roadmap-coverage`, `pdda.sh changelog`,
   259	  `pdda.sh stale`, `pdda.sh issue-doc-sync`
   260	- the aggregate runner is `pdda.sh run` (it runs the deterministic checks in order, then the LLM
== utils/pdda/pdda.sh ==
     1	#!/usr/bin/env bash
     2	set -u
     3	
     4	# PDDA unified entry point. One dispatcher for every deterministic hygiene check plus the aggregate
     5	# run. The LLM-assisted readiness review stays in its own file (utils/pdda/pdda-doc-ready.sh) — it is a
     6	# different class of automation (opt-in, model-dependent, advisory/warn-max), per PROJECT/PDDA.md
     7	# "Automation layers". Shared helpers live in utils/pdda/pdda-lib.sh.
     8	#
     9	# Usage:
    10	#   pdda.sh run                 # run every deterministic check, then the LLM review (steps in order)
    11	#   pdda.sh frontmatter         # one check (see SUBCOMMANDS below)
    12	#   pdda.sh status-table
    13	#   pdda.sh hardcoded-paths
    14	#   pdda.sh roadmap
    15	#   pdda.sh roadmap-coverage
    16	#   pdda.sh changelog
    17	#   pdda.sh stale
    18	#   pdda.sh doc-ready           # delegates to utils/pdda/pdda-doc-ready.sh (the LLM layer)
    19	#   pdda.sh help
    20	#
    21	# Mode/format/overrides are honored exactly as before via the env vars resolved in pdda-lib.sh
    22	# (PDDA_MODE, PDDA_FORMAT, PDDA_WORKING_DIR, PDDA_ROADMAP, ...). Every check resets the finding
    23	# counters on entry and emits its own SUMMARY, so per-check output is identical whether a check runs
    24	# standalone (`pdda.sh frontmatter`) or as part of `pdda.sh run`.
    25	
    26	HERE="$(cd "$(dirname "$0")" && pwd)"
    27	# shellcheck source=utils/pdda/pdda-lib.sh
    28	. "$HERE/pdda-lib.sh"
    29	
    30	pdda_reset_counts() { ERROR_COUNT=0; WARN_COUNT=0; INFO_COUNT=0; }
    31	
    32	# ------------------------------------------------------------------------------------------------
    33	# A. frontmatter
    34	# ------------------------------------------------------------------------------------------------
    35	check_frontmatter() {
    36	  pdda_reset_counts
    37	  local CHECK_NAME="pdda-check-frontmatter" rc=0
    38	  local REQUIRED_KEYS="title status created updated owner goal"
    39	  local file key value date_key rating_key
    40	
    41	  while IFS= read -r file; do
    42	    if ! pdda_has_frontmatter "$file"; then
    43	      pdda_record_finding error "$CHECK_NAME" "$file" 1 "missing YAML frontmatter" "add-frontmatter"
    44	      rc=1
    45	      continue
    46	    fi
    47	
    48	    for key in $REQUIRED_KEYS; do
    49	      if ! pdda_frontmatter_has_key "$file" "$key"; then
    50	        pdda_record_finding error "$CHECK_NAME" "$file" 1 "missing required frontmatter key '$key'" "add-frontmatter-key"
    51	        rc=1
    52	        continue
    53	      fi
    54	
    55	      value="$(pdda_frontmatter_value "$file" "$key")"
    56	      if [ -z "$(pdda_trim "$value")" ]; then
    57	        pdda_record_finding error "$CHECK_NAME" "$file" 1 "frontmatter key '$key' is empty" "fill-frontmatter-key"
    58	        rc=1
    59	      fi
    60	    done
    61	
    62	    for date_key in created updated; do
    63	      if pdda_frontmatter_has_key "$file" "$date_key"; then
    64	        value="$(pdda_trim "$(pdda_frontmatter_value "$file" "$date_key")")"
    65	        # tolerate YAML-quoted dates, e.g. created: "2026-06-15" or '2026-06-15'
    66	        case "$value" in
    67	          \"*\") value="${value#\"}"; value="${value%\"}" ;;
    68	          \'*\') value="${value#\'}"; value="${value%\'}" ;;
    69	        esac
    70	        if ! printf '%s' "$value" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'; then
    71	          pdda_record_finding error "$CHECK_NAME" "$file" 1 "frontmatter key '$date_key' must use YYYY-MM-DD" "fix-date-format"
    72	          rc=1
    73	        elif ! pdda_is_real_date "$value"; then
    74	          pdda_record_finding error "$CHECK_NAME" "$file" 1 "frontmatter key '$date_key' is not a real calendar date ($value)" "fix-date-value"
    75	          rc=1
    76	        fi
    77	      fi
    78	    done
    79	
    80	    # Optional triage ratings (PDDA.md "Triage ratings for medium-large work"). Validate ONLY when
    81	    # present: whether a doc SHOULD carry them depends on it being medium-large — a judgment the LLM
    82	    # layer flags, not this script. But a present value out of range is unambiguous => error. Effort,
    83	    # complexity, and risk are integers 1 (low) .. 5 (highest); phases is a positive integer.
    84	    for rating_key in effort complexity risk; do
    85	      if pdda_frontmatter_has_key "$file" "$rating_key"; then
    86	        value="$(pdda_trim "$(pdda_frontmatter_value "$file" "$rating_key")")"
    87	        if ! printf '%s' "$value" | grep -Eq '^[1-5]$'; then
    88	          pdda_record_finding error "$CHECK_NAME" "$file" 1 "frontmatter rating '$rating_key' must be an integer 1-5 (got '$value')" "fix-rating-value"
    89	          rc=1
    90	        fi
    91	      fi
    92	    done
    93	    if pdda_frontmatter_has_key "$file" "phases"; then
    94	      value="$(pdda_trim "$(pdda_frontmatter_value "$file" "phases")")"
    95	      if ! printf '%s' "$value" | grep -Eq '^[1-9][0-9]*$'; then
    96	        pdda_record_finding error "$CHECK_NAME" "$file" 1 "frontmatter 'phases' must be a positive integer (got '$value')" "fix-phases-value"
    97	        rc=1
    98	      fi
    99	    fi
   100	  done < <(pdda_list_working_docs)
   101	
   102	  pdda_emit_summary "$CHECK_NAME" "$rc"
   103	  return "$(pdda_gated_exit "$rc")"
   104	}
   105	
   106	# ------------------------------------------------------------------------------------------------
   107	# B. status-table
   108	# ------------------------------------------------------------------------------------------------
   109	check_status_table() {
   110	  pdda_reset_counts
   111	  local CHECK_NAME="pdda-check-status-table" rc=0
   112	  local EXPECTED_HEADER="What was just completed|What's next"
   113	  local file metadata old_ifs header_line header_text row_line row_text
   114	  local normalized_header cell_output cell_one cell_two
   115	
   116	  while IFS= read -r file; do
   117	    metadata="$(awk '
   118	      /^##[[:space:]]+Status[[:space:]]*$/ { in_status = 1; next }
   119	      in_status && /^\|/ {
   120	        count += 1
   121	        if (count == 1) {
   122	          header_line = NR
   123	          header = $0
   124	        } else if (count == 3) {
   125	          print header_line "\034" header "\034" NR "\034" $0
   126	          exit
   127	        }
   128	      }
   129	      in_status && /^##[[:space:]]+/ { exit }
   130	    ' "$file")"
   131	
   132	    if [ -z "$metadata" ]; then
   133	      pdda_record_finding error "$CHECK_NAME" "$file" 1 "missing usable '## Status' table" "add-status-table"
   134	      rc=1
   135	      continue
   136	    fi
   137	
   138	    old_ifs="$IFS"
   139	    IFS=$'\034'
   140	    set -- $metadata
   141	    IFS="$old_ifs"
   142	    header_line="$1"
   143	    header_text="$2"
   144	    row_line="$3"
   145	    row_text="$4"
   146	
   147	    normalized_header="$(pdda_normalize_header "$header_text")"
   148	    if [ "$normalized_header" != "$EXPECTED_HEADER" ]; then
   149	      pdda_record_finding error "$CHECK_NAME" "$file" "$header_line" "status-table header must be exactly '$EXPECTED_HEADER' (got '$normalized_header')" "normalize-status-table"
   150	      rc=1
   151	    fi
   152	
   153	    cell_output="$(pdda_table_cells "$row_text")"
   154	    cell_one="$(printf '%s\n' "$cell_output" | sed -n '1p')"
   155	    cell_two="$(printf '%s\n' "$cell_output" | sed -n '2p')"
   156	
   157	    if [ -z "$cell_one" ]; then
   158	      pdda_record_finding error "$CHECK_NAME" "$file" "$row_line" "first status cell is blank" "fill-status-table"
   159	      rc=1
   160	    fi
   161	    if [ -z "$cell_two" ]; then
   162	      pdda_record_finding error "$CHECK_NAME" "$file" "$row_line" "second status cell is blank" "fill-status-table"
   163	      rc=1
   164	    fi
   165	  done < <(pdda_list_working_docs)
   166	
   167	  pdda_emit_summary "$CHECK_NAME" "$rc"
   168	  return "$(pdda_gated_exit "$rc")"
   169	}
   170	
   171	# ------------------------------------------------------------------------------------------------
   172	# C. hardcoded-paths
   173	# ------------------------------------------------------------------------------------------------
   174	check_hardcoded_paths() {
   175	  pdda_reset_counts
   176	  local CHECK_NAME="pdda-check-hardcoded-paths" rc=0
   177	  local file matches awk_status line_number reason
   178	
   179	  while IFS= read -r file; do
   180	    matches="$(awk '
   181	      # PDDA.md exempts only "quoted terminal output / explicitly marked transcript blocks" — so suppress
   182	      # ONLY fences whose info-string is console/text/transcript, or a fence right after a
   183	      # <!-- pdda:allow-paths --> marker. Ordinary code fences ARE scanned (paths must not hide in them).
   184	      /^[[:space:]]*<!--[[:space:]]*pdda:allow-paths[[:space:]]*-->/ { allow_next = 1; next }
   185	      /^```/ {
   186	        if (in_fence) { in_fence = 0; fence_exempt = 0 }
   187	        else {
   188	          info = $0; sub(/^`+/, "", info); gsub(/[[:space:]]/, "", info); info = tolower(info)
   189	          in_fence = 1
   190	          fence_exempt = (allow_next || info == "console" || info == "text" || info == "transcript") ? 1 : 0
   191	          allow_next = 0
   192	        }
   193	        next
   194	      }
   195	      in_fence && fence_exempt { next }
   196	      /^[[:space:]]*>/ { next }
   197	      /\/Users\// { print NR "\t/Users/"; next }
   198	      /\/private\// { print NR "\t/private/"; next }
   199	      /(^|[^[:alnum:]_])\/tmp\// { print NR "\t/tmp/"; next }
   200	      /file:\/\// { print NR "\tfile://"; next }
   201	      /(^|[^[:alnum:]_])[A-Za-z]:[\/\\]/ { print NR "\tdrive-letter path"; next }
   202	    ' "$file")"
   203	    awk_status=$?
   204	    if [ "$awk_status" -ne 0 ]; then
   205	      pdda_record_finding error "$CHECK_NAME" "$file" 1 "hardcoded-path scan failed" "fix-script"
   206	      rc=1
   207	      continue
   208	    fi
   209	
   210	    while IFS=$'\t' read -r line_number reason; do
   211	      [ -n "$line_number" ] || continue
   212	      pdda_record_finding error "$CHECK_NAME" "$file" "$line_number" "hardcoded path detected ($reason)" "replace-with-repo-relative-path"
   213	      rc=1
   214	    done <<EOF
   215	$matches
   216	EOF
   217	  done < <(pdda_list_working_docs)
   218	
   219	  pdda_emit_summary "$CHECK_NAME" "$rc"
   220	  return "$(pdda_gated_exit "$rc")"
   221	}
   222	
   223	# ------------------------------------------------------------------------------------------------
   224	# D. roadmap (no execution detail leaks INTO ROADMAP.md)
   225	# ------------------------------------------------------------------------------------------------
   226	check_roadmap() {
   227	  pdda_reset_counts
   228	  local CHECK_NAME="pdda-check-roadmap" rc=0
   229	  local PDDA_ROADMAP="${PDDA_ROADMAP:-$PDDA_REPO_ROOT/ROADMAP.md}"
   230	  local ROADMAP_MAX_LINES="${PDDA_ROADMAP_MAX_LINES:-200}"
   231	  local ROADMAP_MAX_HEADINGS="${PDDA_ROADMAP_MAX_HEADINGS:-25}"
   232	  local findings sev line msg line_count heading_count
   233	
   234	  if [ ! -f "$PDDA_ROADMAP" ]; then
   235	    pdda_record_finding info "$CHECK_NAME" "$PDDA_ROADMAP" 0 "ROADMAP.md not found; nothing to check" "skip"
   236	    pdda_emit_summary "$CHECK_NAME" 0
   237	    return "$(pdda_gated_exit 0)"
   238	  fi
   239	
   240	  findings="$(awk '
   241	    /^[[:space:]]*```/ {
   242	      if (in_fence) { in_fence=0; fexempt=0 }
   243	      else {
   244	        info=$0; sub(/^[[:space:]]*`+/,"",info); gsub(/[[:space:]]/,"",info); info=tolower(info)
   245	        in_fence=1
   246	        fexempt=(info=="console"||info=="text"||info=="transcript")?1:0
   247	      }
   248	      next
   249	    }
   250	    in_fence && fexempt { next }
   251	    /^[[:space:]]*>/ { next }                                     # blockquote = allowed carve-out note
   252	    # ERROR: GFM task-list item — a ledger does not carry task checkboxes
   253	    /^[[:space:]]*[-*][[:space:]]+\[[ xX~-]\]/ { print "E\t" NR "\ttask-checklist item — phase checklists belong in a PROJECT/** doc, not ROADMAP"; next }
   254	    # ERROR: execution-detail heading
   255	    /^#+[[:space:]]+(Checklist|QA[[:space:]]+[Cc]hecklist)[[:space:]]*$/ { print "E\t" NR "\texecution-detail heading (\""$0"\") — move the phase/QA detail into the project doc"; next }
   256	  ' "$PDDA_ROADMAP")"
   257	
   258	  while IFS=$'\t' read -r sev line msg; do
   259	    [ -n "$sev" ] || continue
   260	    if [ "$sev" = "E" ]; then
== utils/pdda/pdda-doc-ready.sh ==
     1	#!/usr/bin/env bash
     2	set -u
     3	
     4	HERE="$(cd "$(dirname "$0")" && pwd)"
     5	# shellcheck source=utils/pdda/pdda-lib.sh
     6	. "$HERE/pdda-lib.sh"
     7	
     8	CHECK_NAME="pdda-doc-ready"
     9	EXIT_CODE=0
    10	
    11	# LLM-assisted readiness review (PDDA.md "2. LLM-assisted doc readiness review"). This is the EXPENSIVE
    12	# layer and is OPT-IN: set PDDA_LLM_BIN to a model CLI (+ PDDA_LLM_ARGS for its print flag). Unset or
    13	# not on PATH => skip gracefully (advisory info, exit 0) so the deterministic hourly run never breaks
    14	# when no model/network is available. Examples:
    15	#   PDDA_LLM_BIN=agy   PDDA_LLM_ARGS="-p"  PDDA_LLM_MODEL="Gemini 3.1 Pro (High)"  (run sandbox-OFF — agy can hang)
    16	#   PDDA_LLM_BIN=codex PDDA_LLM_ARGS="exec"
    17	#   PDDA_LLM_BIN=claude PDDA_LLM_ARGS="-p"
    18	# PDDA_LLM_ARGS is word-split (simple flags only); a model NAME with spaces goes via PDDA_LLM_MODEL so
    19	# it survives as a single argument.
    20	PDDA_LLM_BIN="${PDDA_LLM_BIN:-}"
    21	PDDA_LLM_ARGS="${PDDA_LLM_ARGS:--p}"
    22	
    23	if [ -z "$PDDA_LLM_BIN" ] || ! command -v "$PDDA_LLM_BIN" >/dev/null 2>&1; then
    24	  pdda_record_finding info "$CHECK_NAME" "$PDDA_REPO_ROOT" 0 \
    25	    "LLM readiness review skipped (set PDDA_LLM_BIN to a model CLI such as agy/codex/claude to enable)" "skip"
    26	  pdda_emit_summary "$CHECK_NAME" 0
    27	  exit 0
    28	fi
    29	
    30	# Word-split the flags; append a spaced-safe --model only if PDDA_LLM_MODEL is set.
    31	read -ra _llm_args <<<"$PDDA_LLM_ARGS"
    32	[ -n "${PDDA_LLM_MODEL:-}" ] && _llm_args+=(--model "$PDDA_LLM_MODEL")
    33	
    34	# The rubric flags ONLY readiness gaps; it deliberately does NOT re-lint frontmatter / status-table /
    35	# paths (those are the deterministic checks) and does NOT rewrite or invent claims (PDDA.md "It should not").
    36	read -r -d '' RUBRIC <<'RUBRIC_EOF' || true
    37	You are a documentation-readiness reviewer for a phased-plan repo. Review the project doc below and
    38	flag ONLY readiness gaps. Do NOT rewrite it, do NOT invent technical claims, and do NOT report
    39	frontmatter/status-table/hardcoded-path issues (separate deterministic checks own those). Flag:
    40	- a phased plan with a phase that has no QA gate / acceptance criteria after it
    41	- a phase that lists actions but no observable acceptance criteria
    42	- a multi-phase plan with no table of contents listing its phases
    43	- a discovery or spike phase (named "Discovery"/"Spike", or doc_type research) whose findings were NOT
    44	  written back into this doc — i.e. it reverse-engineered or probed something but left no captured
    45	  findings (what was investigated, what was found, what it changes for later phases)
    46	- a medium-large plan or project (NOT a typo / path repoint / <=2-3 line fix) whose frontmatter is
    47	  missing the triage ratings effort, complexity, risk, phases (used by automation to select work);
    48	  do NOT flag genuinely small/trivial docs for this
    49	- a status table that is present but stale versus the body
    50	- the next action buried in prose instead of stated explicitly
    51	- detail duplicated from another canonical doc
    52	- contradictory status (e.g. frontmatter says Completed while the body is active)
    53	Output ONE JSON object per finding, one per line, and NOTHING else. Schema:
    54	{"severity":"warn|info","line":<integer or 0>,"message":"<one concise sentence>"}
    55	This review is advisory and never blocks a build: use "warn" for a strong readiness concern and "info"
    56	for advisory. Do NOT emit "error" — a non-deterministic review must not gain build-blocking power.
    57	If the doc is ready, output nothing at all.
    58	RUBRIC_EOF
    59	
    60	# ROADMAP.md pointer-only contract (PDDA.md "ROADMAP.md contract"). Honors the deliberate carve-out
    61	# ("a short exception note is allowed when omitting would hide an operationally critical fact"), which
    62	# is exactly why this is judged by the LLM layer rather than a brittle deterministic lint.
    63	read -r -d '' ROADMAP_RUBRIC <<'ROADMAP_EOF' || true
    64	You are reviewing a repo's ROADMAP.md against its "pointer file, not a plan body" contract. It SHOULD
    65	contain only: projects in progress, completed, attempted, deferred, and links to the canonical project
    66	docs. It SHOULD NOT contain detailed phase checklists, step-by-step build instructions, or deep
    67	execution notes that belong in an individual project doc. IMPORTANT carve-out: a SHORT exception note
    68	is allowed when omitting it would hide an operationally critical fact — do NOT flag those.
    69	Flag ONLY genuine contract violations (execution detail that should live in a project doc). Do NOT
    70	rewrite. Output ONE JSON object per finding, one per line, NOTHING else. Schema:
    71	{"severity":"warn|info","line":<integer or 0>,"message":"<one concise sentence>"}
    72	This review is advisory and never blocks: use "warn" for a clear violation and "info" for borderline.
    73	Do NOT emit "error". If ROADMAP.md honors the contract, output nothing.
    74	ROADMAP_EOF
    75	
    76	# Parse the model's output: keep only lines that look like a JSON object, extract fields via node
    77	# (already a dependency, see pdda_json_escape). Malformed/prose lines are skipped, not fatal.
    78	parse_finding() {  # reads one JSON line on stdin -> "severity\tline\tmessage" or empty
    79	  node -e '
    80	    let s = "";
    81	    process.stdin.on("data", d => s += d).on("end", () => {
    82	      try {
    83	        const o = JSON.parse(s);
    84	        const sev = (o.severity === "warn" || o.severity === "info" || o.severity === "error") ? o.severity : "info";
    85	        const line = Number.isInteger(o.line) ? o.line : 0;
    86	        const msg = typeof o.message === "string" ? o.message.replace(/[\t\r\n]+/g, " ").trim() : "";
    87	        if (msg) process.stdout.write(sev + "\t" + line + "\t" + msg);
    88	      } catch (e) { /* not JSON — skip */ }
    89	    });
    90	  ' 2>/dev/null
    91	}
    92	
    93	# Review ONE doc against <rubric>; record any findings. Used for both the working docs and ROADMAP.
    94	review_one() {  # <file> <rubric>
    95	  local file="$1" rubric="$2" rel response parsed sev ln msg jline
    96	  rel="$(pdda_relpath "$file")"
    97	  response="$("$PDDA_LLM_BIN" ${_llm_args[@]+"${_llm_args[@]}"} "$rubric
    98	
    99	=== DOC: $rel ===
   100	$(cat "$file")" 2>/dev/null || true)"
   101	  [ -n "$response" ] || return 0
   102	  while IFS= read -r jline; do
   103	    case "$jline" in
   104	      '{'*'}') ;;          # only attempt lines that look like a single JSON object
   105	      *) continue ;;
   106	    esac
   107	    parsed="$(printf '%s' "$jline" | parse_finding)"
   108	    [ -n "$parsed" ] || continue
   109	    IFS=$'\t' read -r sev ln msg <<PARSED
   110	$parsed
   111	PARSED
   112	    # PDDA contract: the LLM layer is advisory and never blocks (warn-max). A non-deterministic oracle
   113	    # must not gain blocking power — the same doc could pass at 2pm and fail at 3pm. Clamp any "error".
   114	    [ "$sev" = "error" ] && sev="warn"
   115	    pdda_record_finding "$sev" "$CHECK_NAME" "$file" "${ln:-0}" "$msg" "llm-readiness"
   116	  done <<RESPONSE
   117	$response
   118	RESPONSE
   119	}
   120	
   121	# 1) active working docs — generic readiness rubric.
   122	while IFS= read -r file; do
   123	  review_one "$file" "$RUBRIC"
   124	done < <(pdda_list_working_docs)
   125	
   126	# 2) ROADMAP.md — pointer-only contract (separate rubric; skipped if absent).
   127	PDDA_ROADMAP="${PDDA_ROADMAP:-$PDDA_REPO_ROOT/ROADMAP.md}"
   128	[ -f "$PDDA_ROADMAP" ] && review_one "$PDDA_ROADMAP" "$ROADMAP_RUBRIC"
   129	
   130	pdda_emit_summary "$CHECK_NAME" "$EXIT_CODE"
   131	exit "$(pdda_gated_exit "$EXIT_CODE")"
== utils/pdda/pdda-edit-doc-hook.sh ==
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
== .claude/commands/ask_self.md ==
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
== .claude/commands/reingest.md ==
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

codex
I’ve confirmed the local side: PDDA is a doc lifecycle with QA gates and write-back, `snapshot` is session recovery, and `phase-qa`/`loose-ends` are checklist sweeps, not a verifier agent. I’m pulling the gsd loop docs now to decide where that difference is material versus cosmetic.
exec
/bin/zsh -lc "for f in '/Users/noelsaw/Documents/GH Repos/gsd-core/docs/explanation/the-phase-loop.md' '/Users/noelsaw/Documents/GH Repos/gsd-core/docs/explanation/context-engineering.md' '/Users/noelsaw/Documents/GH Repos/gsd-core/docs/explanation/multi-agent-orchestration.md' '/Users/noelsaw/Documents/GH Repos/gsd-core/docs/reference/state-md.md' '/Users/noelsaw/Documents/GH Repos/gsd-core/docs/reference/context-md.md' '/Users/noelsaw/Documents/GH Repos/gsd-core/docs/reference/planning-artifacts.md'; do echo \"== "'$f =="; nl -ba "$f" | sed -n '"'1,260p'; done" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-21302-28772
 succeeded in 0ms:
== /Users/noelsaw/Documents/GH Repos/gsd-core/docs/explanation/the-phase-loop.md ==
     1	# The phase loop
     2	
     3	> The central mental model for how GSD Core organises work.
     4	
     5	---
     6	
     7	## What the loop is
     8	
     9	GSD Core structures all development work as a repeating cycle:
    10	
    11	```text
    12	Discuss → (UI design) → Plan → Execute → Verify → Ship
    13	```
    14	
    15	Every unit of work — called a **phase** — moves through these steps in order. The loop is not a formality. Each step exists because it guards against a specific class of failure that the previous step alone cannot prevent.
    16	
    17	This document explains *why* the loop is shaped the way it is. For instructions on running each step, see the how-to guides linked at the bottom.
    18	
    19	---
    20	
    21	## Why each step exists
    22	
    23	### Discuss
    24	
    25	Planning cannot begin until you know *how* to build the thing, not just *what* to build. The phase goal in `ROADMAP.md` describes the outcome. The Discuss step captures the implementation decisions that shape the path to that outcome: which libraries, which error-handling strategy, whether a feature is per-route or global, how edge cases should behave.
    26	
    27	Without a Discuss step, the planner must make these calls itself. Sometimes it guesses right. Often it guesses plausibly but wrongly — producing a plan that is coherent but misaligned with your actual preferences. By the time execution is done and you realise the error, you are unwinding significant work.
    28	
    29	The Discuss step is deliberately lightweight. It is a conversation, not a specification exercise. The output is a `CONTEXT.md` in the phase directory: a structured record of decisions that the planner, executor, and verifier can all read. The conversation takes a few minutes; it can save hours of rework.
    30	
    31	### UI design (optional)
    32	
    33	For phases with a visual component, there is an optional `/gsd-ui-phase` step between Discuss and Plan. It produces a `UI-SPEC.md` — a design contract that describes layout, interaction, and visual behaviour before any code is written. This step is worth running when the UI is complex enough that ambiguity in the design would produce divergent implementation choices. A clear design contract is far cheaper to write than to re-implement.
    34	
    35	### Plan
    36	
    37	The Plan step does the research, decomposition, and structural thinking that execution requires. It runs as a sequence of fresh-context subagents: a researcher that investigates the ecosystem and records findings in `RESEARCH.md`, a planner that reads both the research and the `CONTEXT.md` to produce `PLAN.md` files, and a plan-checker that verifies the plans are complete, consistent, and within scope.
    38	
    39	What does a plan contain? Each `PLAN.md` describes a bounded unit of work: the files to touch, the specific changes to make, the acceptance criteria that define done. Plans are ordered into dependency waves so that parallel execution is safe — executors in the same wave touch non-overlapping concerns.
    40	
    41	The Plan step is the moment when ambiguity is most expensive. An ambiguous plan produces an executor that makes assumptions. Multiple parallel executors making different assumptions about the same concern produce conflicts. The plan-checker's job is to catch these before execution begins, not after.
    42	
    43	### Execute
    44	
    45	Execution runs the plans. Each executor gets a fresh 200k-token context window loaded with exactly what it needs: the project summary, the phase context, the research, and the specific `PLAN.md` for its task. Nothing more.
    46	
    47	Executors write code and commit atomically. Each commit corresponds to a completed task in a plan. When a wave of parallel executors finishes, the orchestrator merges their state and starts the next wave.
    48	
    49	The executor's fresh context is not a convenience — it is the mechanism by which context rot is prevented. An executor that runs with 180k tokens of accumulated session history is a degraded executor. An executor that starts clean and reads only what its plan requires is an executor operating at full capacity.
    50	
    51	### Verify
    52	
    53	After all executors have completed, a verifier agent reads the phase goal, the `CONTEXT.md` decisions, the plans, and the execution summaries — and checks that what was built matches what was intended. It produces a `VERIFICATION.md` and, if there are discrepancies, generates targeted fix plans.
    54	
    55	Verification is not just testing. It checks requirement coverage (were all the REQ-IDs addressed?), decision coverage (were the decisions captured in `CONTEXT.md` actually implemented?), and overall phase goal alignment. A phase is not done because execution finished without errors. It is done because what was built is what was planned, and what was planned is what was decided.
    56	
    57	### Ship
    58	
    59	The Ship step creates the pull request and archives the phase artefacts. `STATE.md` is updated to mark the phase complete. The loop then begins again for the next phase.
    60	
    61	---
    62	
    63	## Milestones and phases
    64	
    65	A **milestone** is a version cycle — a meaningful, releasable increment of the project. It has a name, a version number, and a set of requirements that define what it must deliver. A milestone is complete when all its phases are shipped and its requirements are covered.
    66	
    67	A **phase** is one unit of work within a milestone. A phase has a goal, a set of requirements it addresses, and a set of plans that implement it.
    68	
    69	The relationship matters because milestones and phases have different scopes of concern. A milestone asks: "What does this version of the product do, and what does it not do?" A phase asks: "What is the next bounded thing we can research, plan, execute, and verify?"
    70	
    71	Milestone boundaries are drawn at natural product boundaries — a deployable API, a working UI flow, a complete data model. Phase boundaries are drawn at the limits of what can be safely executed in one loop without the loop becoming unwieldy.
    72	
    73	---
    74	
    75	## What makes a good phase scope
    76	
    77	This is worth dwelling on because it is the most common source of friction with the loop.
    78	
    79	A phase that is too large becomes a research project unto itself. The planner struggles to decompose it into independent plans. Executors in later waves are blocked waiting for earlier waves. Verification becomes a full audit rather than a targeted review. The feedback cycle stretches from hours to days, and the risk of discovering a fundamental design mistake late — after much code has been written — rises sharply.
    80	
    81	A phase that is too small fragments work that naturally belongs together. You end up with plan files that are half a dozen lines, phases that complete in minutes, and a planning overhead that dwarfs the execution cost. The loop feels bureaucratic rather than helpful.
    82	
    83	A good phase scope is one where:
    84	
    85	- The goal can be stated in a single sentence that is neither obviously trivial nor suspiciously broad.
    86	- The research needed to plan it is bounded — the ecosystem questions have answers that do not depend on other phases completing first.
    87	- The execution can be parallelised into a handful of non-overlapping plans, not dozens.
    88	- There is a clear, testable definition of done that a verifier can check without reading the entire codebase.
    89	
    90	Concretely: "Add HMAC-SHA256 signature validation middleware" is a good phase scope. "Build the authentication system" usually is not — it almost always contains multiple independent concerns that would be better as separate phases. "Fix the typo in the README" is below the threshold where the loop adds value; use `/gsd-quick` instead.
    91	
    92	When in doubt, split. A smaller phase completes faster, verifies more confidently, and makes it easier to course-correct if a design decision turns out to be wrong.
    93	
    94	---
    95	
    96	## How `.planning/` carries state across the loop
    97	
    98	The loop is not a single session. Research, planning, and execution may happen across multiple sessions, with context resets in between. The `.planning/` directory is what makes this possible.
    99	
   100	Every step of the loop reads artefacts produced by earlier steps and writes artefacts for later steps. The CONTEXT.md that the Discuss step produces is still available when the Planner runs — even if that is in a different session hours later. The PLAN.md files that the Planner produces are still available when the Executor runs — even across a restart. The VERIFICATION.md that the Verifier writes is still available when you review the phase.
   101	
   102	`STATE.md` is the navigation layer above all of this. It records exactly where in the loop the project currently sits: which milestone is active, which phase is in progress, which plans are complete and which are pending. Any agent or workflow that needs to orient itself reads `STATE.md` first.
   103	
   104	For the precise structure of these files, see [Planning artifacts](../reference/planning-artifacts.md) and the [STATE.md schema](../reference/state-md.md).
   105	
   106	---
   107	
   108	## The loop is a rhythm, not a constraint
   109	
   110	It is tempting to see the loop as bureaucracy — a set of required steps that you have to perform before you are allowed to write code. That framing is wrong.
   111	
   112	The loop exists because each step prevents failures that are genuinely expensive to fix later. Discuss prevents planning on wrong assumptions. Plan prevents executing a design that is fundamentally broken. Verify prevents shipping work that missed the brief. These are not invented problems. They are the actual failure modes of AI-assisted development at the scale of real features.
   113	
   114	When the loop works well, it feels like a rhythm: a cadence of focused, bounded work where each step is clear because the previous step did its job. The overhead is real, but it is front-loaded — paid in minutes of planning rather than hours of rework.
   115	
   116	For work that falls below the threshold where the loop is warranted, GSD Core provides lighter primitives. The phase loop is one tool, not the only tool.
   117	
   118	---
   119	
   120	## Related
   121	
   122	- [Context engineering](context-engineering.md) — why fresh-context subagents prevent the quality degradation that makes the loop necessary
   123	- [Discuss a phase](../how-to/discuss-a-phase.md)
   124	- [Plan a phase](../how-to/plan-a-phase.md)
   125	- [Execute a phase](../how-to/execute-a-phase.md)
   126	- [Verify and ship](../how-to/verify-and-ship.md)
   127	- [Planning artifacts](../reference/planning-artifacts.md)
   128	- [STATE.md schema](../reference/state-md.md)
   129	- [docs index](../README.md)
== /Users/noelsaw/Documents/GH Repos/gsd-core/docs/explanation/context-engineering.md ==
     1	# Context engineering
     2	
     3	> Why GSD Core exists, and the problem it is designed to solve.
     4	
     5	---
     6	
     7	## The problem: context rot
     8	
     9	Every AI coding session starts fresh. The model reads your question, reasons over it, and replies. But a session is rarely one exchange. You ask follow-up questions, paste error messages, iterate on code, redirect the model when it drifts. Each turn adds tokens to the context window — the finite buffer of text the model can "see" at once.
    10	
    11	As that window fills, something subtle happens. The model does not fail loudly. It keeps answering. But the quality of its answers quietly degrades. Early instructions get pushed towards the edge of what it can attend to. Nuance from the first few exchanges — the constraints you stated, the architecture you agreed on, the edge cases you flagged — competes for attention against everything that came later. Researchers call this **context rot**.
    12	
    13	Context rot manifests in several ways:
    14	
    15	- The model starts contradicting earlier decisions it acknowledged.
    16	- Code style drifts away from the conventions established at session start.
    17	- Plans begin to ignore requirements that were clearly stated but are now buried deep in the history.
    18	- The model hallucinates file names or function signatures it had correct twenty messages ago.
    19	
    20	None of this is a model bug. It is a fundamental property of how transformer attention works over long sequences. The model is not forgetting — it never "remembered" in the human sense. It is weighting relevance across a finite window, and as that window fills with accumulated noise, signal-to-noise degrades.
    21	
    22	The naive response is to `/clear` and start over. But that loses continuity. You have to re-explain context, re-paste relevant files, re-state constraints. The session essentially resets to zero.
    23	
    24	---
    25	
    26	## GSD Core's answer: fresh-context subagents
    27	
    28	GSD Core's central insight is that *most* of the work in a coding session does not need to happen in the main context at all. Research, planning, code writing, and verification are each discrete, bounded tasks. Each can be handed to a specialised subagent that starts with a clean, carefully scoped context window — and reports its result back to a thin orchestrator that stays lean.
    29	
    30	This is not a workaround for context rot. It is a structural solution.
    31	
    32	The orchestrator — your main session — never touches source files. It spawns agents, collects their results, updates shared state, and routes to the next step. Because it does very little itself, its context window grows slowly and predictably. The heavy work happens in agents that each start fresh, receive exactly the context they need for their task, and terminate when done.
    33	
    34	Consider what this means in practice. When you run `/gsd-plan-phase`, the orchestrator:
    35	
    36	1. Loads a compact JSON context payload (project summary, phase goal, relevant config).
    37	2. Spawns a researcher agent with a 200k-token clean window.
    38	3. Spawns a planner agent with the research output and phase requirements.
    39	4. Spawns a plan-checker agent to verify the plan before execution.
    40	
    41	Each agent operates at full capacity, unencumbered by the accumulated history of your session. When the planner writes its `PLAN.md` files to `.planning/phases/`, that output becomes a durable artefact — not a fragile memory in a shared context window.
    42	
    43	---
    44	
    45	## Spec-driven development and meta-prompting
    46	
    47	Context engineering alone is not enough. If an agent starts fresh but receives vague instructions, it will produce vague output. GSD Core pairs fresh-context subagents with two complementary disciplines:
    48	
    49	**Spec-driven development** means that every phase produces structured artefacts before execution begins. A `CONTEXT.md` captures implementation decisions from the Discuss step. A `RESEARCH.md` records what the researcher found. A `PLAN.md` breaks work into discrete, dependency-ordered tasks with explicit acceptance criteria. By the time an executor agent touches a file, it has a precise specification to work from — not a re-interpretation of a long conversation.
    50	
    51	**Meta-prompting** means the agent definitions themselves are carefully engineered prompts, not ad-hoc instructions. The files in `gsd-core/workflows/` and `agents/` encode hard-won knowledge about how to scope tasks, what to verify, and when to escalate to a human checkpoint. The user does not need to re-explain this knowledge in every session; it is baked into the system's own prompts.
    52	
    53	The combination is deliberate. Fresh context ensures each agent reasons clearly. Spec-driven artefacts ensure each agent reasons about the *right* thing. Meta-prompting ensures each agent knows *how* to reason about it well.
    54	
    55	---
    56	
    57	## The role of `.planning/`
    58	
    59	Context engineering requires that knowledge survive context resets. GSD Core uses the file system for this. Every meaningful output is written to `.planning/` as human-readable Markdown or JSON. This means:
    60	
    61	- Restarting your session (or the model crashing) does not lose work.
    62	- Any subsequent agent can read prior artefacts directly, without depending on a shared conversation history.
    63	- You can inspect, edit, or commit planning artefacts to git — they are plain text, not opaque state in a database.
    64	
    65	`STATE.md` is the spine of this system. It records the project's current position (which milestone, which phase, which plans are complete), active decisions and blockers, and progress metrics. When any workflow starts, it reads `STATE.md` to orient itself. When any workflow finishes a meaningful step, it writes back to `STATE.md`. Agents do not rely on memory; they rely on the file.
    66	
    67	---
    68	
    69	## Lifecycle hooks and context headroom
    70	
    71	The fresh-context subagent model protects each spawned agent from accumulating noise. But there is a subtler problem: the *orchestrating session itself* fills up over time. A long-running orchestration silently consumes its own context window — loading payloads, reading status output, routing between phases. Without any signal about how much headroom remains, the session can quietly degrade or, worse, trigger an automatic compaction that silently discards planning state the orchestrator was relying on.
    72	
    73	Since GSD 1.4.0, this is addressed by registering runtime lifecycle hooks. Rather than leaving headroom invisible, these hooks give GSD a per-turn signal — a moment to inspect how much context has been consumed and emit a warning before the window is exhausted. The hooks run inside the runtime itself, so the measurement is as close to authoritative as possible: GSD is not guessing from the outside.
    74	
    75	### One idea, many runtime vocabularies
    76	
    77	Each AI runtime exposes lifecycle events in its own vocabulary, but the purpose is the same across all of them: fire at boundaries that correspond to context pressure or turn transitions, so GSD can observe and react.
    78	
    79	- **Claude Code** fires `PreCompact` when a compaction is about to occur, `Stop` when a session turn ends, and `SubagentStop` when a spawned subagent completes. Together these bracket the moments when context has grown or a context-consuming task has just finished.
    80	- **Gemini** fires `BeforeAgent`/`AfterAgent` around each agent invocation, and `BeforeModel` before each model call — giving a per-inference opportunity to check headroom.
    81	- **Qwen** exposes `SubagentStop`, `Stop`, and `PreCompact`, mirroring Claude Code's shape in its own event system.
    82	
    83	Think of these as the same concept — "notify GSD at context boundaries" — expressed in each runtime's native event vocabulary. This is the multi-runtime philosophy applied at the observability layer: GSD registers the semantically equivalent hook wherever each runtime exposes it, rather than demanding every runtime adopt a single event schema.
    84	
    85	For the per-runtime event matrix, see [FEATURES.md](../FEATURES.md) under Multi-Runtime Support. For how to enable hooks on your specific runtime, see [Install on your runtime](../how-to/install-on-your-runtime.md).
    86	
    87	### Config hot-reload via `FileChanged`
    88	
    89	Claude Code exposes a `FileChanged` event in addition to session-lifecycle hooks. Claude Code's `FileChanged` hook watches for changes to `config.json` and hot-reloads the project's `.planning/config.json` into the session. The practical reason is straightforward: configuration changes should take effect without forcing the user to clear and rebuild the session.
    90	
    91	Requiring a `/clear` to pick up a config edit would destroy the very continuity the context-engineering design is trying to protect. By watching for `FileChanged` on `config.json`, GSD can reload configuration mid-session — adjusting model profiles, context-window thresholds, or routing preferences — without the user losing their place. The working context survives; the configuration updates beneath it.
    92	
    93	### Effort signals for heavy and light skills
    94	
    95	Beyond passive monitoring, GSD uses `effort:` frontmatter to signal the token budget appropriate for each skill. Heavy orchestrator skills (`plan-phase`, `execute-phase`, `autonomous`) declare `effort: max`; quick-status skills (`progress`, `stats`) declare `effort: low`.
    96	
    97	Note: an earlier version of GSD also applied `context: fork` to these three heavy skills to protect the main session's context budget. This was removed (#921) because `plan-phase`, `execute-phase`, and `autonomous` are **spawning orchestrators** — their core function is to spawn subagents (`gsd-planner`, `gsd-executor`, etc.), and a forked subagent context does not have the `Agent` tool. Context isolation for these skills comes from the subagents they spawn, not from forking the orchestrator itself.
    98	
    99	Complementing this, quick-status skills explicitly declare low effort in their definitions. This is a budget-conscious signal in the opposite direction: these skills read minimal state and return concise output, keeping their own footprint small by design.
   100	
   101	### Trade-offs
   102	
   103	This machinery is worth being honest about.
   104	
   105	**Hooks add maintenance surface.** Every runtime GSD supports must have its hooks registered, tested, and kept in sync with that runtime's event API. When a runtime changes its event names or firing semantics, GSD's hook registration needs updating. This is the cost of per-runtime observability rather than a single shared mechanism.
   106	
   107	**Headroom tracking is a heuristic.** The hooks give GSD a signal, not a guarantee. A single model call can consume tokens unpredictably depending on the response length, tool use, and caching behaviour. GSD uses headroom estimates to warn and steer, not to make hard guarantees about what will fit.
   108	
   109	**Subagents are isolated.** A spawned subagent cannot see uncommitted state in the orchestrating session. This is not a bug — it is necessary for independence — but it means anything the subagent needs must be on disk before it is spawned. This is precisely why `.planning/` exists as the shared substrate: plan files, `STATE.md`, `CONTEXT.md`, and `config.json` are all durable, file-system artefacts that any context — orchestrator or subagent — can read. The context-engineering design is self-consistent: the same principle that makes fresh-context subagents work (shared state lives in files, not in a conversation) is what makes the multi-agent architecture viable. See also [Multi-agent orchestration](multi-agent-orchestration.md) for how `.planning/` serves the same role across the orchestrator → agent boundary.
   110	
   111	---
   112	
   113	## Trade-offs
   114	
   115	Honesty about trade-offs matters here.
   116	
   117	**Overhead.** The phase loop introduces real friction. Running `/gsd-discuss-phase`, `/gsd-plan-phase`, and `/gsd-execute-phase` as separate steps takes more elapsed time than typing "write this feature" into a plain session. For a small, well-understood change, that overhead is not justified.
   118	
   119	**Latency.** Spawning multiple subagents with fresh context is slower than a single in-context edit. Research, planning, and execution each incur round-trip costs.
   120	
   121	**Ceremony for simple tasks.** If you need to rename a variable, fix a typo, or add a missing import, the phase loop is overkill. GSD Core provides `/gsd-quick` and `/gsd-fast` for ad-hoc work that does not warrant a full phase. See [Handle quick and fast tasks](../how-to/handle-quick-and-fast-tasks.md).
   122	
   123	The phase loop pays for itself when the work is complex enough that context rot is a real risk — multi-file features, cross-cutting refactors, work that spans hours or sessions. For everything else, reach for the lighter primitive.
   124	
   125	A useful rule of thumb: if the task could be fully specified in a single, short prompt and completed in one agent turn without further clarification, skip the phase loop. If the task requires research, involves files you have not read recently, or depends on decisions that are not yet settled, the phase loop protects you.
   126	
   127	---
   128	
   129	## Related
   130	
   131	- [The phase loop](the-phase-loop.md) — how the Discuss → Plan → Execute → Verify → Ship cycle puts context engineering into practice
   132	- [Multi-agent orchestration](multi-agent-orchestration.md) — how subagents are spawned, scoped, and coordinated
   133	- [Architecture](../ARCHITECTURE.md) — system architecture, agent model, and data flow
   134	- [docs index](../README.md)
== /Users/noelsaw/Documents/GH Repos/gsd-core/docs/explanation/multi-agent-orchestration.md ==
     1	# Multi-agent orchestration in GSD Core
     2	
     3	> **Explanation** — This document describes *why* GSD Core is designed around
     4	> multi-agent orchestration and *how the pieces fit together*. It is not a
     5	> step-by-step guide. For configuration, see
     6	> [Configure model profiles](../how-to/configure-model-profiles.md) and the
     7	> [Configuration reference](../CONFIGURATION.md). For the full agent roster,
     8	> see [Inventory](../INVENTORY.md).
     9	
    10	---
    11	
    12	## The problem this design solves
    13	
    14	AI coding agents degrade. Not because the model gets worse, but because the
    15	*context window fills up*. As a conversation grows, earlier decisions and code
    16	get pushed out or diluted by the noise of intermediate steps. By the time an
    17	agent writes the fifth file in a complex task, it may have already forgotten
    18	the constraint stated in the first message. This is sometimes called *context
    19	rot*.
    20	
    21	GSD Core's multi-agent design is a direct response to that problem. Instead of
    22	one long-running agent carrying the whole session, a thin orchestrator spawns
    23	short-lived specialised agents, each with a **fresh 200 K-token context window**
    24	and *only the artifacts it needs* to do its specific job. The orchestrator
    25	never does heavy lifting itself; it loads context, spawns the right agent,
    26	collects the result, and updates shared state in `.planning/`.
    27	
    28	---
    29	
    30	## The orchestrator → agent pattern
    31	
    32	Every workflow in `gsd-core/workflows/` follows the same shape:
    33	
    34	```text
    35	Orchestrator (workflow .md file)
    36	    │
    37	    ├── Load context
    38	    │   gsd-tools.cjs init <workflow> <phase>
    39	    │   → JSON: project info, config, state, phase details
    40	    │
    41	    ├── Resolve model
    42	    │   gsd-tools.cjs resolve-model <agent-name>
    43	    │   → opus | sonnet | haiku | inherit
    44	    │
    45	    ├── Spawn specialised agent (Task/SubAgent call)
    46	    │   ├── Agent definition (agents/*.md)
    47	    │   ├── Context payload (init JSON)
    48	    │   ├── Model assignment
    49	    │   └── Tool permissions
    50	    │
    51	    ├── Collect result
    52	    │
    53	    └── Update state
    54	        gsd-tools.cjs state update / state patch / state advance-plan
    55	```
    56	
    57	The orchestrator is deliberately thin. It does not reason about the domain,
    58	does not write code, and does not interpret results beyond routing them to the
    59	next step. That boundary keeps each layer's responsibility clear and prevents
    60	the orchestrator's context from accumulating domain noise.
    61	
    62	### The agent roster
    63	
    64	GSD Core's agents fall into functional categories that map onto the
    65	research → plan → execute → verify pipeline:
    66	
    67	| Category | Agents | Typical parallelism |
    68	|---|---|---|
    69	| Researchers | `gsd-project-researcher`, `gsd-phase-researcher`, `gsd-ui-researcher`, `gsd-advisor-researcher` | 4 parallel (stack, features, architecture, pitfalls) |
    70	| Synthesisers | `gsd-research-synthesizer` | Sequential, after researchers complete |
    71	| Planners | `gsd-planner`, `gsd-roadmapper` | Sequential |
    72	| Checkers | `gsd-plan-checker`, `gsd-integration-checker`, `gsd-ui-checker`, `gsd-nyquist-auditor` | Sequential, up to 3 revision iterations |
    73	| Executors | `gsd-executor` | Parallel within a wave, sequential across waves |
    74	| Verifiers | `gsd-verifier` | Sequential, after all executors complete |
    75	| Mappers | `gsd-codebase-mapper` | 4 parallel sub-probes |
    76	| Auditors | `gsd-ui-auditor`, `gsd-security-auditor` | Sequential |
    77	
    78	Each agent definition (in `agents/*.md`) declares its allowed tool access,
    79	purpose, and colour for terminal output. An agent that only needs to read files
    80	and write a single output document gets exactly those permissions — no Bash
    81	execution, no access to broader state. That constraint is intentional: it
    82	keeps the blast radius small if an agent behaves unexpectedly.
    83	
    84	For the complete agent roster, see [Inventory](../INVENTORY.md#agents).
    85	
    86	---
    87	
    88	## Wave-based parallel execution
    89	
    90	The most visible expression of multi-agent design is how `/gsd-execute-phase`
    91	handles a set of plans that may depend on one another.
    92	
    93	Before spawning any executor, the orchestrator performs a **wave analysis**:
    94	it reads the dependency declarations in each `PLAN.md` file and groups plans
    95	into waves. Plans with no declared dependencies form Wave 1 and run in
    96	parallel. Plans that depend on Wave 1 form Wave 2, and so on.
    97	
    98	```text
    99	Plan 01 (no deps)        ─┐
   100	Plan 02 (no deps)        ─┤─── Wave 1  (parallel)
   101	Plan 03 (depends: 01)    ─┤─── Wave 2  (waits for Wave 1)
   102	Plan 04 (depends: 02)    ─┘
   103	Plan 05 (depends: 03, 04) ─── Wave 3  (waits for Wave 2)
   104	```
   105	
   106	Each executor within a wave:
   107	
   108	- receives a fresh context window (200 K tokens, or up to 1 M on capable models)
   109	- receives the specific `PLAN.md` it is responsible for
   110	- receives project context (`PROJECT.md`, `STATE.md`)
   111	- receives phase context (`CONTEXT.md`, `RESEARCH.md` if available)
   112	- produces atomic git commits on completion
   113	- writes a `SUMMARY.md` describing what was built
   114	
   115	After all executors in a wave finish, the orchestrator runs the pre-commit
   116	hook once for the wave as a whole. Executors commit with `--no-verify` to
   117	prevent build-lock contention (for example, Cargo lock fights in Rust
   118	projects) when multiple agents commit in parallel. The hook therefore runs
   119	once per wave rather than once per commit.
   120	
   121	### Parallel commit safety
   122	
   123	Two mechanisms prevent write conflicts when multiple executors run
   124	simultaneously:
   125	
   126	1. **Atomic lock on `STATE.md`** — Every write to `STATE.md` uses a
   127	   lockfile (`STATE.md.lock`) with `O_EXCL` atomic creation. This prevents
   128	   the read-modify-write race where two agents each read the file, modify
   129	   different fields, and the later writer overwrites the earlier one's
   130	   changes. Stale locks (older than 10 seconds) are automatically cleared.
   131	
   132	2. **Per-wave hook run** — Rather than each executor running pre-commit hooks
   133	   independently (which can cause file-level contention on shared build
   134	   artefacts), the orchestrator runs `git hook run pre-commit` once after
   135	   every wave completes.
   136	
   137	---
   138	
   139	## Adaptive context enrichment for large-window models
   140	
   141	Standard 200 K context windows are enough for an executor to implement a
   142	single focused plan. When the configured `context_window` is 500 K tokens or
   143	larger (for example, when using Opus 4.6 or Sonnet 4.6 in 1 M-class mode),
   144	the orchestrator automatically enriches subagent prompts with additional
   145	context that would not fit in a standard window:
   146	
   147	- **Executor agents** receive prior-wave `SUMMARY.md` files and the phase
   148	  `CONTEXT.md`/`RESEARCH.md`, giving them cross-plan awareness within the
   149	  phase
   150	- **Verifier agents** receive all `PLAN.md`, `SUMMARY.md`, and `CONTEXT.md`
   151	  files plus `REQUIREMENTS.md`, enabling history-aware verification
   152	
   153	This enrichment is conditional on the `context_window` value in
   154	`config.json`. On standard-window configurations, prompts use truncated
   155	versions with cache-friendly ordering to maximise token efficiency.
   156	
   157	---
   158	
   159	## Why this design — the connection to context engineering
   160	
   161	The orchestrator → agent pattern only makes sense as part of a broader
   162	approach to *context engineering*: the idea that what an AI agent gets in its
   163	context window matters as much as the model tier or prompt quality. See
   164	[Context engineering](context-engineering.md) for the full treatment.
   165	
   166	Multi-agent orchestration operationalises context engineering in two ways:
   167	
   168	**Context isolation.** Each agent receives only what it needs. A researcher
   169	gets the project description and domain questions; it does not get the full
   170	planning history. A verifier gets every plan and summary; it does not get the
   171	raw research. Isolation keeps each agent's context dense with signal rather
   172	than diluted by noise from other pipeline stages.
   173	
   174	**Context hygiene across sessions.** Because all state lives in
   175	`.planning/` as human-readable Markdown and JSON (not in any agent's context
   176	window), GSD workflows survive context resets (`/clear`), tab switches, and
   177	multi-day breaks. The next agent always starts from persisted, verified
   178	artifacts rather than from a reconstructed memory of a long conversation.
   179	
   180	---
   181	
   182	## Trade-offs
   183	
   184	Multi-agent orchestration is not free.
   185	
   186	**Coordination overhead.** Each agent spawn is a round-trip: the orchestrator
   187	must format a prompt, hand off context, wait for the subagent to complete
   188	(typically 1–5 minutes), and then parse the result. A single capable agent
   189	working in one context would finish faster for simple tasks. GSD mitigates
   190	this by making parallelism the default wherever dependencies permit — the
   191	four researchers in a `plan-phase` run simultaneously, not sequentially.
   192	
   193	**Opacity during execution.** While a subagent is running, its work is
   194	invisible to the parent session. There is no live progress stream. This is a
   195	deliberate consequence of the fresh-context design: the subagent is operating
   196	in its own context window. The orchestrator shows a liveness note on the
   197	spawn line ("runs in a subagent — no output until it returns") to set
   198	expectations.
   199	
   200	**Context stitching cost.** Packaging the right artifacts for each agent
   201	requires the orchestrator to spend tokens assembling and transmitting context
   202	payloads. This is the cost of isolation. The `gsd-tools.cjs init` handler
   203	produces a JSON payload that balances completeness with token budget, applying
   204	cache-friendly ordering so that the stable parts of the payload (project
   205	definition, config) hit the cache on repeat invocations.
   206	
   207	**Model cost amplification.** Running five agents in parallel at Opus tier
   208	costs more than running one. The model profile system (`model_profiles.md`,
   209	resolved per agent by `model-profiles.cjs`) lets you assign cheaper tiers to
   210	less critical agents. The `dynamic_routing` feature further reduces cost by
   211	starting every agent on a cheaper tier and escalating only on a soft failure.
   212	See [Configuration](../CONFIGURATION.md) for the full options.
   213	
   214	In return for these costs, the design buys *consistent quality across large
   215	phases*. An executor writing the tenth file in a 400-line plan does not
   216	degrade because its context is fresh. A verifier checking twenty requirements
   217	does not forget the first ten because it received all of them as structured
   218	input rather than conversation history.
   219	
   220	---
   221	
   222	## Related
   223	
   224	- [Context engineering](context-engineering.md) — the upstream principle that
   225	  motivates this design; see also [Lifecycle hooks and context headroom](context-engineering.md#lifecycle-hooks-and-context-headroom) for how per-turn headroom tracking and forked-context skills extend the same principle at runtime
   226	- [Configure model profiles](../how-to/configure-model-profiles.md) — how to
   227	  assign model tiers per agent
   228	- [Configuration reference](../CONFIGURATION.md) — full `config.json` schema
   229	  including `models`, `model_overrides`, `dynamic_routing`, and
   230	  `context_window`
   231	- [Inventory](../INVENTORY.md) — authoritative agent roster and workflow list
   232	- [Architecture](../ARCHITECTURE.md#agent-model) — implementation-level detail
   233	  on the orchestrator → agent pattern and wave execution model
   234	- [Docs index](../README.md)
== /Users/noelsaw/Documents/GH Repos/gsd-core/docs/reference/state-md.md ==
     1	# STATE.md schema reference
     2	
     3	`STATE.md` is GSD Core's living project-memory file — a single Markdown document that records where a project stands, what happened last, and what to run next. This page documents its structure. See [docs index](../README.md).
     4	
     5	---
     6	
     7	## Overview
     8	
     9	Every project managed by GSD Core keeps one `STATE.md` at `.planning/STATE.md`. It is read at the start of every workflow and written after every significant action. The file combines:
    10	
    11	- **YAML frontmatter** — machine-readable fields consumed by the status-line hook (`parseStateMd`) and the `gsd-tools state` commands.
    12	- **Markdown body** — human-readable sections covering current position, accumulated context, session continuity, and performance metrics.
    13	
    14	The file is intentionally small (target: under 100 lines). It is a digest of the project's state, not an archive.
    15	
    16	---
    17	
    18	## YAML frontmatter
    19	
    20	Frontmatter appears between `---` delimiters at the very start of the file. All fields except `gsd_state_version` and `status` are optional; fields may be absent when their data is not yet available.
    21	
    22	### Annotated example
    23	
    24	```yaml
    25	---
    26	gsd_state_version: '1.0'
    27	milestone: v2.0
    28	milestone_name: Code Quality
    29	status: executing
    30	
    31	# Phase-lifecycle fields — all optional (added in v1.40.0, issue #2833)
    32	active_phase: "4.5"
    33	next_action: execute-phase
    34	next_phases: ["4.5"]
    35	
    36	progress:
    37	  total_phases: 17
    38	  completed_phases: 10
    39	  total_plans: 84
    40	  completed_plans: 47
    41	  percent: 59
    42	
    43	# Additional fields written by syncStateFrontmatter
    44	current_phase: "4"
    45	current_phase_name: Observability
    46	current_plan: "3"
    47	last_updated: "2026-06-01T12:34:56.789Z"
    48	last_activity: "2026-06-01"
    49	stopped_at: "Phase 4 P3 execution complete"
    50	paused_at: null
    51	---
    52	```
    53	
    54	### Field reference
    55	
    56	| Field | Type | When populated | Purpose |
    57	|---|---|---|---|
    58	| `gsd_state_version` | string (`'1.0'`) | Always | Schema version; written on first `state.*` call by `syncStateFrontmatter`. |
    59	| `milestone` | string (e.g. `v2.0`) | When a milestone is configured | Current milestone version, read from the project's config. |
    60	| `milestone_name` | string | When a milestone is configured | Human-readable milestone label (e.g. `Code Quality`). |
    61	| `status` | string | Always | Current lifecycle stage. Normalised by `normalizeStateStatus()` — see [status values](#status-values). |
    62	| `active_phase` | string (e.g. `"4.5"`) | An orchestrator command is in flight on this phase | The phase number currently being processed. Set to `null` when between phases. |
    63	| `next_action` | string | Idle, with a recommended command | The slash command to run next: `discuss-phase`, `plan-phase`, `execute-phase`, or `verify-phase`. Set to `null` when an orchestrator is in flight or no recommendation is available. |
    64	| `next_phases` | YAML flow array (e.g. `["4.5"]`) | Goes with `next_action` | The phase ID(s) the `next_action` applies to (typically 1–2 entries). Set to `null` under the same conditions as `next_action`. |
    65	| `progress.total_phases` | integer | When phase data is available | Total number of phases in the current milestone, derived from ROADMAP.md and the phases directory. |
    66	| `progress.completed_phases` | integer | When phase data is available | Number of phases that have all plan summaries on disk (i.e. every plan completed). |
    67	| `progress.total_plans` | integer | When plan files exist | Sum of all plan files across phases in the current milestone. |
    68	| `progress.completed_plans` | integer | When summary files exist | Sum of completed plan summaries (one SUMMARY.md per executed plan). |
    69	| `progress.percent` | integer 0–100 | When progress data is available | Milestone progress in the **phase dimension** (`min(completed_plans/total_plans, completed_phases/total_phases)`). The status-line progress bar is only rendered when this field is present — its absence suppresses the bar. |
    70	| `current_phase` | string | When a phase is executing | Phase number extracted from the body `Current Phase:` field. |
    71	| `current_phase_name` | string | When a phase has a name | Phase name extracted from the body `Current Phase Name:` field. |
    72	| `current_plan` | string | When a plan is in progress | Plan number extracted from the body `Current Plan:` field. |
    73	| `last_updated` | ISO-8601 timestamp | Always (on write) | Timestamp of the last `syncStateFrontmatter` call; written by `realClock.nowIso()`. |
    74	| `last_activity` | string | When set in body | Date of the last activity, extracted from the body `Last Activity:` field. |
    75	| `stopped_at` | string | When a stop point was recorded | Description of the last completed action; scoped to the `## Session` body section to avoid matching archive prose. |
    76	| `paused_at` | string | When the project is paused | Freeform description of the pause point; absent or `null` when not paused. |
    77	
    78	### Status values
    79	
    80	`normalizeStateStatus()` in `gsd-core/bin/lib/state-document.cjs` maps raw body text to these canonical values:
    81	
    82	| Canonical value | Matched text (case-insensitive) |
    83	|---|---|
    84	| `discussing` | contains `discussing` |
    85	| `planning` | contains `planning` or `ready to plan` |
    86	| `executing` | contains `executing`, `in progress`, or `ready to execute` |
    87	| `verifying` | contains `verif` |
    88	| `completed` | contains `complete` or `done` |
    89	| `paused` | contains `paused` or `stopped`, or `paused_at` is present |
    90	| `unknown` | none of the above |
    91	
    92	When an orchestrator command is in flight, the convention (issue #2833) is to write the lifecycle stage directly to `status`:
    93	
    94	| Command | `status` while in flight |
    95	|---|---|
    96	| `/gsd-discuss-phase` | `discussing` |
    97	| `/gsd-plan-phase` | `planning` |
    98	| `/gsd-execute-phase` | `executing` |
    99	| `/gsd-verify-work` | `verifying` |
   100	
   101	---
   102	
   103	## Status-line rendering scenes
   104	
   105	`formatGsdState()` in `hooks/gsd-statusline.js` reads the parsed frontmatter and emits the **first matching scene**. If no new lifecycle fields apply, rendering falls through to the original format byte-for-byte unchanged from v1.38.x.
   106	
   107	| Scene | Trigger | Display example |
   108	|---|---|---|
   109	| **1. Phase active** | `active_phase` is populated | `v2.0 [██░░░░░░░░] 20% · Phase 4.5 executing` |
   110	| **2. Idle, next recommended** | `active_phase` is null AND both `next_action` and `next_phases` are populated | `v2.0 [██░░░░░░░░] 20% · next execute-phase 4.5` |
   111	| **3. Milestone complete** | `percent` is `100` OR `completed_phases == total_phases` | `v2.0 [██████████] 100% · milestone complete` |
   112	| **4. Default fallback** | None of the above match | `v1.9 Code Quality · executing · ph 1/5` (existing format) |
   113	
   114	**Scene priority:** when both `active_phase` and `next_action` are populated, Scene 1 wins — an orchestrator is in flight, so a "next recommendation" would be misleading. This priority is enforced by check order in `formatGsdState()` and covered by the `"scene priority"` suite in `tests/gsd-statusline.test.cjs`.
   115	
   116	The progress bar (`[██░░░░░░░░] 20%`) is appended to the milestone segment only when `progress.percent` is present in frontmatter; absent means no bar.
   117	
   118	---
   119	
   120	## Frontmatter parsing constraints
   121	
   122	The status-line hook uses regex-based parsing (no full YAML library), so the following constraints apply. They are tested in `tests/gsd-statusline.test.cjs`.
   123	
   124	1. **Frontmatter must start at the very first character of the file.** Anything — including comments — above the opening `---` invalidates the match. The opening `---` line must be exactly that, with no trailing spaces.
   125	
   126	2. **Comments inside nested blocks are not supported.** The `progress:` block parser requires the next line to be `[ \t]+\w+:`. Inserting a `# comment` between `progress:` and its first key breaks the match and the bar disappears. Any documentation belongs in the `STATE.md` body, not inside frontmatter blocks.
   127	
   128	3. **`next_phases` primary format is single-line flow.** The parser first tries `next_phases: ["4.5", "4.6"]`. Block sequences (`- 4.5\n- 4.6`) are also parsed but are less reliable for status-line rendering. Prefer single-line flow for `next_phases` to keep the regex-based parser predictable. If many candidate phases need recording for documentation purposes, store them in the `STATE.md` body.
   129	
   130	If a future change replaces the regex parser with a full YAML library, these constraints can be relaxed and the tests updated accordingly.
   131	
   132	---
   133	
   134	## Markdown body sections
   135	
   136	The body (everything after the closing `---`) follows the template in `gsd-core/templates/state.md`. The standard sections are:
   137	
   138	### Project Reference
   139	
   140	Points to `.planning/PROJECT.md`. Contains:
   141	- **Core value** — the one-liner from `PROJECT.md`'s Core Value section.
   142	- **Current focus** — which phase is active.
   143	
   144	### Current Position
   145	
   146	Where the project stands right now:
   147	
   148	| Field | Format |
   149	|---|---|
   150	| `Phase:` | `X of Y (Phase name)` |
   151	| `Plan:` | `A of B in current phase` |
   152	| `Status:` | Free text, e.g. `Ready to execute`, `Executing Phase 4`, `Phase complete — ready for verification` |
   153	| `Last activity:` | ISO date (`YYYY-MM-DD`) when handler-written; narrative prose when executor-authored |
   154	| `Progress:` | Visual bar, e.g. `[████░░░░░░] 40%` |
   155	
   156	The `Status:` and `Last activity:` fields in this section are updated by GSD handlers when the existing value is a known template default (Knuth invariant: executor-authored values are preserved). The full list of known handler defaults is in `KNOWN_TEMPLATE_DEFAULTS` inside `gsd-core/bin/lib/state-document.cjs`.
   157	
   158	### Performance Metrics
   159	
   160	Execution velocity tracking:
   161	- Total plans completed, average duration per plan.
   162	- Per-phase breakdown table (`Phase | Plans | Total | Avg/Plan`).
   163	- Recent trend: Improving / Stable / Degrading.
   164	
   165	Updated after each plan completion.
   166	
   167	### Accumulated Context
   168	
   169	**Decisions** — a summary of recent decisions affecting current work (full log lives in `PROJECT.md`). Added via `gsd-tools state add-decision`.
   170	
   171	**Pending Todos** — count and reference to `.planning/todos/pending/`. Captured via `/gsd-capture`.
   172	
   173	**Blockers/Concerns** — issues affecting future work, prefixed with the originating phase. Added via `gsd-tools state add-blocker`; resolved via `gsd-tools state resolve-blocker`.
   174	
   175	### Session Continuity
   176	
   177	Enables instant session resumption:
   178	- `Last session:` — ISO-8601 timestamp of the last session.
   179	- `Stopped at:` — description of the last completed action.
   180	- `Resume file:` — path to a `.continue-here*.md` file if one exists, otherwise `None`.
   181	
   182	---
   183	
   184	## Backward compatibility
   185	
   186	The phase-lifecycle fields (`active_phase`, `next_action`, `next_phases`, and `progress.percent` for the bar) are **additive and opt-in per project**:
   187	
   188	- A `STATE.md` with none of the lifecycle fields populated renders **byte-for-byte identically** to v1.38.x and earlier.
   189	- Adding any lifecycle field is opt-in — the renderer degrades gracefully when fields are absent.
   190	- The progress bar is opt-in even when the `progress` block exists: only `progress.percent` triggers the bar; `total_phases` and `completed_phases` alone do not.
   191	
   192	The `formatGsdState #2833 backward compatibility` test suite in `tests/gsd-statusline.test.cjs` locks this guarantee; any change that breaks legacy `STATE.md` rendering will fail the suite.
   193	
   194	---
   195	
   196	## Related
   197	
   198	- [Planning artifacts](planning-artifacts.md)
   199	- [Configuration](../CONFIGURATION.md)
   200	- [The phase loop](../explanation/the-phase-loop.md)
   201	- [docs index](../README.md)
== /Users/noelsaw/Documents/GH Repos/gsd-core/docs/reference/context-md.md ==
     1	# CONTEXT.md schema reference
     2	
     3	A per-phase `CONTEXT.md` is GSD Core's carrier for implementation decisions captured during `/gsd:discuss-phase`. It is the primary upstream input for both the research and planning agents. This page documents its structure. See [docs index](../README.md).
     4	
     5	---
     6	
     7	## Overview
     8	
     9	Every phase that has been through the discuss workflow produces one `CONTEXT.md` at:
    10	
    11	```
    12	.planning/phases/<NN>-<slug>/<NN>-CONTEXT.md
    13	```
    14	
    15	For example: `.planning/phases/03-post-feed/03-CONTEXT.md`.
    16	
    17	The file is produced by `write_context` in `gsd-core/workflows/discuss-phase.md` (or its PRD / ADR ingest express paths). It is never edited by hand during normal operation — the discuss-phase workflow writes it and downstream agents read it as a sealed source of truth.
    18	
    19	---
    20	
    21	## Frontmatter
    22	
    23	`CONTEXT.md` carries no YAML frontmatter. Metadata is inline at the top of the body:
    24	
    25	```markdown
    26	# Phase [X]: [Name] - Context
    27	
    28	**Gathered:** [ISO date]
    29	**Status:** Ready for planning
    30	```
    31	
    32	The `Status` field is always `Ready for planning` when the file is first written. It is not updated after creation.
    33	
    34	---
    35	
    36	## Block structure
    37	
    38	The body is divided into named XML-style blocks. The blocks appear in a fixed order and are read by downstream agents by block name, not by line number.
    39	
    40	| Block | Purpose | Populated by | Consumed by |
    41	|---|---|---|---|
    42	| `<domain>` | States the phase boundary — what this phase delivers and what is explicitly out of scope. Anchors the scope guardrail throughout planning and execution. | `discuss-phase` (from ROADMAP.md phase goal) | `gsd-planner`, `gsd-plan-checker` (scope compliance) |
    43	| `<spec_lock>` | Present only when a `*-SPEC.md` was found by the `check_spec` step. Lists locked requirement counts and scope boundaries; agents are directed to read `SPEC.md` directly for full requirements. | `discuss-phase` (conditional) | `gsd-planner` (reads SPEC.md rather than re-reading requirements here) |
    44	| `<decisions>` | Implementation decisions captured from the discussion, keyed with `D-NN` identifiers. Categories emerge from what was actually discussed rather than a fixed taxonomy. Includes a `Claude's Discretion` sub-section for areas the user delegated. | `discuss-phase` (interactive discussion) | `gsd-planner` (locked decisions must be implemented), `gsd-plan-checker` (Dimension 7 compliance) |
    45	| `<canonical_refs>` | Full relative paths to every spec, ADR, feature doc, or design doc relevant to this phase. Mandatory — every CONTEXT.md must have this section. Agents must read listed files before planning or implementing. | `discuss-phase` (accumulated from ROADMAP.md refs + user references during discussion + codebase scout) | `gsd-phase-researcher`, `gsd-planner` |
    46	| `<code_context>` | Reusable assets, established patterns, and integration points discovered during the `scout_codebase` step. Guides agents towards existing code rather than re-implementing. | `discuss-phase` (codebase scout) | `gsd-planner`, `gsd-phase-researcher` |
    47	| `<specifics>` | Concrete "I want it like X" references, product comparisons, or particular examples captured verbatim during discussion. | `discuss-phase` (freeform user input) | `gsd-planner` |
    48	| `<deferred>` | Ideas that arose in discussion but belong in other phases. Preserved so they are not lost. Includes a `Reviewed Todos` sub-section when todos were reviewed but not folded into scope. | `discuss-phase` (scope-creep redirect) | Not consumed by automated agents; human reference only |
    49	
    50	---
    51	
    52	## Decision identifier format
    53	
    54	Every decision in `<decisions>` carries a sequential `D-NN` identifier:
    55	
    56	```markdown
    57	### Layout style
    58	- **D-01:** Card-based layout, not timeline or list
    59	- **D-02:** Each card shows: author avatar, name, timestamp, full post content, reaction counts
    60	```
    61	
    62	Identifiers are scoped to the phase. `D-01` in Phase 3 is unrelated to `D-01` in Phase 7. The plan-checker (Dimension 7) verifies that every `D-NN` is addressed by at least one task action in the generated plans.
    63	
    64	---
    65	
    66	## Canonical references
    67	
    68	The `<canonical_refs>` block is **mandatory**. Agents that find it absent treat the CONTEXT.md as incomplete and surface a warning. Entries are grouped by topic and carry a full relative path plus a brief statement of what the file decides or defines:
    69	
    70	```markdown
    71	<canonical_refs>
    72	## Canonical References
    73	
    74	**Downstream agents MUST read these before planning or implementing.**
    75	
    76	### Feed display
    77	- `docs/features/social-feed.md` — Feed requirements, post card fields, engagement display rules
    78	- `docs/decisions/adr-012-infinite-scroll.md` — Scroll strategy decision, virtualisation requirements
    79	
    80	### Empty states
    81	- `docs/design/empty-states.md` — Empty state patterns, illustration guidelines
    82	
    83	</canonical_refs>
    84	```
    85	
    86	When a project has no external specs, the section states this explicitly:
    87	
    88	```
    89	No external specs — requirements fully captured in decisions above
    90	```
    91	
    92	Inline mentions like "see ADR-019" scattered in `<decisions>` are insufficient; agents need the full path in the dedicated section.
    93	
    94	---
    95	
    96	## Decision Coverage Gate relationship
    97	
    98	The plan-checker's **Dimension 7: Context Compliance** enforces a coverage gate after planning:
    99	
   100	1. Every `D-NN` identifier in `<decisions>` must appear in at least one plan task's `<action>` or rationale.
   101	2. No task may implement anything listed in `<deferred>` (scope creep).
   102	3. `Claude's Discretion` areas are exempted from this check — the planner may choose freely.
   103	
   104	A CONTEXT.md where decisions survive into plans is considered compliant. A CONTEXT.md whose decisions are silently dropped or partially delivered triggers **Dimension 7b: Scope Reduction Detection**, which is always a BLOCKER.
   105	
   106	---
   107	
   108	## SPEC.md integration
   109	
   110	When `/gsd:spec-phase` has been run before discussing a phase, the `check_spec` step finds the `*-SPEC.md` file and activates `<spec_lock>`:
   111	
   112	```markdown
   113	<spec_lock>
   114	## Requirements (locked via SPEC.md)
   115	
   116	**12 requirements are locked.** See `03-SPEC.md` for full requirements, boundaries, and acceptance criteria.
   117	
   118	Downstream agents MUST read `03-SPEC.md` before planning or implementing. Requirements are not duplicated here.
   119	
   120	**In scope (from SPEC.md):** [copied from SPEC.md Boundaries]
   121	**Out of scope (from SPEC.md):** [copied from SPEC.md Boundaries]
   122	
   123	</spec_lock>
   124	```
   125	
   126	When `<spec_lock>` is present, `<decisions>` contains only implementation decisions from the discussion — the "how", not the "what". Requirements are not duplicated between the two files.
   127	
   128	---
   129	
   130	## Footer
   131	
   132	Every CONTEXT.md ends with an identity footer:
   133	
   134	```markdown
   135	---
   136	
   137	*Phase: XX-name*
   138	*Context gathered: [date]*
   139	```
   140	
   141	---
   142	
   143	## Related
   144	
   145	- [PLAN.md schema](plan-md.md)
   146	- [Planning artifacts](planning-artifacts.md)
   147	- [Discuss modes](../workflow-discuss-mode.md)
   148	- [docs index](../README.md)
== /Users/noelsaw/Documents/GH Repos/gsd-core/docs/reference/planning-artifacts.md ==
     1	# Planning artifacts reference
     2	
     3	The `.planning/` directory is GSD Core's shared memory for a project. Every workflow reads from it, writes to it, and leaves an auditable trail of decisions. This page maps every file, its purpose, and which command produces or consumes it. See [docs index](../README.md).
     4	
     5	---
     6	
     7	## Directory layout
     8	
     9	```
    10	.planning/
    11	├── PROJECT.md                          # Project identity and core value
    12	├── ROADMAP.md                          # Milestone + phase listing with goals
    13	├── REQUIREMENTS.md                     # Numbered acceptance criteria
    14	├── STATE.md                            # Living position tracker
    15	├── config.json                         # Workflow and model configuration
    16	├── MILESTONES.md                       # Milestone archive (optional)
    17	├── BACKLOG.md                          # Deferred and future work (optional)
    18	├── LEARNINGS.md                        # Accumulated cross-phase learnings (optional)
    19	├── DECISIONS-INDEX.md                  # Rolling summary of prior decisions (optional)
    20	├── METHODOLOGY.md                      # Reusable interpretive frameworks (optional)
    21	├── HANDOFF.json                        # Machine-readable pause state (transient)
    22	├── codebase/                           # Codebase maps (optional)
    23	│   ├── architecture.md
    24	│   ├── stack.md
    25	│   └── ...
    26	├── intel/                              # Queryable symbol index (optional, intel.enabled)
    27	│   └── API-SURFACE.md
    28	└── phases/
    29	    └── <NN>-<slug>/                    # One directory per phase
    30	        ├── <NN>-CONTEXT.md             # Implementation decisions (discuss-phase)
    31	        ├── <NN>-DISCUSSION-LOG.md      # Human-readable discussion audit (discuss-phase)
    32	        ├── <NN>-RESEARCH.md            # Technical research findings (plan-phase)
    33	        ├── <NN>-VALIDATION.md          # Nyquist test-coverage strategy (plan-phase)
    34	        ├── <NN>-PATTERNS.md            # Codebase analog map (plan-phase, optional)
    35	        ├── <NN>-<PP>-PLAN.md           # Executable plan (plan-phase, one per plan)
    36	        ├── <NN>-<PP>-SUMMARY.md        # Execution record (execute-phase, one per plan)
    37	        ├── <NN>-VERIFICATION.md        # Phase goal verification report (verify-phase)
    38	        ├── <NN>-UAT.md                 # Persistent UAT session state (execute-phase)
    39	        └── .continue-here.md           # Resume instructions after pause (pause-work)
    40	```
    41	
    42	---
    43	
    44	## Root-level artifacts
    45	
    46	### `PROJECT.md`
    47	
    48	| | |
    49	|---|---|
    50	| **Purpose** | Canonical project identity: what it is, who it is for, core value, requirements, constraints, and key decisions. Updated throughout the project lifecycle as the product evolves. |
    51	| **Produced by** | `/gsd-new-project` (initial creation); updated by `/gsd-complete-milestone` as decisions are validated. |
    52	| **Consumed by** | All planning workflows; `gsd-phase-researcher`, `gsd-planner` (context); `discuss-phase` (prior decisions); `gsd-plan-checker` (project constraints). |
    53	
    54	Includes an optional `## Business Context` section (Customer, Revenue model, Success metric, Strategy notes) for monetized or customer-facing projects — four one-line fields that connect business outcomes to requirement prioritization. It is deleted for internal tools, experiments, or meta workspaces, and reviewed at each milestone by `/gsd-complete-milestone` when present.
    55	
    56	### `ROADMAP.md`
    57	
    58	| | |
    59	|---|---|
    60	| **Purpose** | Milestone and phase listing with goals, requirement IDs, success criteria, and canonical references per phase. The single source of truth for what the project is building and in what order. |
    61	| **Produced by** | `/gsd-new-project` (initial creation); updated by `/gsd-phase --insert` and `/gsd-complete-milestone`. |
    62	| **Consumed by** | `/gsd-discuss-phase`, `/gsd-plan-phase`, `/gsd-execute-phase`; all orchestration commands that need phase information; `gsd-planner`, `gsd-plan-checker`, `gsd-phase-researcher`. |
    63	
    64	### `REQUIREMENTS.md`
    65	
    66	| | |
    67	|---|---|
    68	| **Purpose** | Numbered, checkable acceptance criteria for the project. Each requirement carries an ID (e.g., `AUTH-01`) that maps to roadmap phases. Marks requirements complete as phases are executed. |
    69	| **Produced by** | `/gsd-new-project` (initial creation); requirements marked complete by `execute-phase`. |
    70	| **Consumed by** | `gsd-planner` (plans must address all phase requirement IDs); `gsd-plan-checker` Dimension 1 (requirement coverage); `discuss-phase` (prior requirements). |
    71	
    72	### `STATE.md`
    73	
    74	| | |
    75	|---|---|
    76	| **Purpose** | Living position tracker — current phase and plan, progress metrics, accumulated decisions, session continuity notes. Read at the start of every workflow run. Updated after every significant action. |
    77	| **Produced by** | `/gsd-new-project` (initial creation); updated continuously by all phase workflows, `/gsd-pause-work`, `/gsd-resume-work`. |
    78	| **Consumed by** | All orchestration workflows; `/gsd-progress`; ad-hoc task execution via `/gsd-quick`; `gsd-planner` and `gsd-phase-researcher` (project decisions). |
    79	
    80	See [STATE.md schema](state-md.md) for the full field reference.
    81	
    82	### `config.json`
    83	
    84	| | |
    85	|---|---|
    86	| **Purpose** | Workflow configuration: model profiles, research and plan-checker toggles, git branching strategy, Nyquist validation, parallelisation settings, and per-agent model overrides. |
    87	| **Produced by** | `/gsd-new-project` (initial creation); `/gsd-settings` (interactive editing). |
    88	| **Consumed by** | Every workflow and subagent — read at init time via `gsd-tools query config-get`. |
    89	
    90	See [CONFIGURATION](../CONFIGURATION.md) for the complete schema.
    91	
    92	### `MILESTONES.md` (optional)
    93	
    94	| | |
    95	|---|---|
    96	| **Purpose** | Historical record of completed milestones. Populated as each milestone is closed; provides an archival snapshot of what shipped and when. |
    97	| **Produced by** | `/gsd-complete-milestone`. |
    98	| **Consumed by** | `/gsd-audit-milestone`; human review. |
    99	
   100	### `DECISIONS-INDEX.md` (optional)
   101	
   102	| | |
   103	|---|---|
   104	| **Purpose** | Bounded rolling summary of decisions captured in prior-phase CONTEXT.md files. When present, `discuss-phase` reads this single file instead of reading up to three prior CONTEXT.md files individually, saving context budget. |
   105	| **Produced by** | Generated when the number of prior phases exceeds the rolling-read threshold. |
   106	| **Consumed by** | `discuss-phase` (`load_prior_context` step). |
   107	
   108	### `HANDOFF.json` (transient)
   109	
   110	| | |
   111	|---|---|
   112	| **Purpose** | Machine-readable pause state written when work is interrupted. Contains the resume point, in-progress context, and continuation instructions. Consumed exactly once — on resume. |
   113	| **Produced by** | `/gsd-pause-work`. |
   114	| **Consumed by** | `/gsd-resume-work`. |
   115	
   116	---
   117	
   118	## Per-phase artifacts
   119	
   120	All per-phase files live under `.planning/phases/<NN>-<slug>/` where `NN` is the zero-padded phase number and `slug` is the hyphenated phase name.
   121	
   122	### `<NN>-CONTEXT.md`
   123	
   124	| | |
   125	|---|---|
   126	| **Purpose** | Implementation decisions captured before planning begins. Contains the phase boundary (`<domain>`), locked decisions with `D-NN` identifiers (`<decisions>`), canonical document references (`<canonical_refs>`), existing code insights (`<code_context>`), specific inspirations (`<specifics>`), and deferred ideas (`<deferred>`). |
   127	| **Produced by** | `/gsd-discuss-phase` (interactive discussion or PRD/ADR express paths). |
   128	| **Consumed by** | `gsd-phase-researcher` (what to investigate); `gsd-planner` (locked decisions); `gsd-plan-checker` Dimension 7 (context compliance). |
   129	
   130	See [CONTEXT.md schema](context-md.md) for the full field reference.
   131	
   132	### `<NN>-DISCUSSION-LOG.md`
   133	
   134	| | |
   135	|---|---|
   136	| **Purpose** | Human-readable audit trail of the discuss-phase session: areas discussed, options presented, selections made, deferred ideas, and items left to Claude's discretion. Not consumed by automated workflows. |
   137	| **Produced by** | `/gsd-discuss-phase` (`git_commit` step). |
   138	| **Consumed by** | Human review; retrospectives. |
   139	
   140	### `<NN>-RESEARCH.md`
   141	
   142	| | |
   143	|---|---|
   144	| **Purpose** | Technical research findings produced before planning. Answers "What do I need to know to plan this phase well?" — covers domain analysis, patterns, risks, an Architectural Responsibility Map, and a Validation Architecture section (used by the Nyquist gate). |
   145	| **Produced by** | `/gsd-plan-phase` via `gsd-phase-researcher` agent. |
   146	| **Consumed by** | `gsd-planner` (planning inputs); `gsd-plan-checker` Dimension 7c (tier compliance), Dimension 8 (Nyquist), Dimension 11 (research resolution); `gsd-pattern-mapper` (file list source). |
   147	
   148	### `<NN>-VALIDATION.md`
   149	
   150	| | |
   151	|---|---|
   152	| **Purpose** | Nyquist-inspired validation strategy derived from the `## Validation Architecture` section of RESEARCH.md. Specifies automated test coverage requirements that plans must honour. |
   153	| **Produced by** | `/gsd-plan-phase` (Step 5.5, when `workflow.nyquist_validation` is enabled and RESEARCH.md contains a Validation Architecture section). |
   154	| **Consumed by** | `gsd-plan-checker` Dimension 8 (Check 8e gate — must exist before Nyquist checks proceed); `gsd-verifier`. |
   155	
   156	### `<NN>-PATTERNS.md`
   157	
   158	| | |
   159	|---|---|
   160	| **Purpose** | Codebase analog map produced by `gsd-pattern-mapper`. For each file to be created or modified this phase, identifies the closest existing analog, classifies the file's role and data flow, and extracts concrete code excerpts. Guides the planner towards consistent patterns. |
   161	| **Produced by** | `/gsd-plan-phase` via `gsd-pattern-mapper` agent (optional; skipped if `workflow.pattern_mapper: false`). |
   162	| **Consumed by** | `gsd-planner` (pattern guidance); `gsd-plan-checker` Dimension 12 (pattern compliance). |
   163	
   164	### `<NN>-<PP>-PLAN.md`
   165	
   166	| | |
   167	|---|---|
   168	| **Purpose** | Executable plan for a single unit of work within the phase. Contains YAML frontmatter (wave, dependencies, files, requirements, `must_haves`), an objective, context references, XML-structured tasks with `<read_first>`, `<action>`, `<verify>`, and `<acceptance_criteria>` fields, and verification criteria. |
   169	| **Produced by** | `/gsd-plan-phase` via `gsd-planner` agent. One file per plan — e.g., `03-02-PLAN.md` is Phase 3, Plan 2. |
   170	| **Consumed by** | `/gsd-execute-phase` (executor agent reads plan and runs tasks); `gsd-plan-checker` (pre-execution quality review); `gsd-verifier` (reads `must_haves` for post-execution verification). |
   171	
   172	See [PLAN.md schema](plan-md.md) for the full field reference.
   173	
   174	### `<NN>-<PP>-SUMMARY.md`
   175	
   176	| | |
   177	|---|---|
   178	| **Purpose** | Execution record written after a plan completes. Documents what was built, deviations from the plan, a self-check against acceptance criteria, and the dependency graph for the phase. |
   179	| **Produced by** | `execute-phase` executor agent (written at the end of each plan's execution). |
   180	| **Consumed by** | `/gsd-progress` (phase status); `gsd-planner` (when a subsequent plan has a genuine dependency on prior plan output); `milestone-summary`. |
   181	
   182	### `<NN>-VERIFICATION.md`
   183	
   184	| | |
   185	|---|---|
   186	| **Purpose** | Phase goal verification report. Checks `must_haves.truths`, `must_haves.artifacts`, and `must_haves.key_links` from all plans against the actual codebase after execution. Records `status: passed \| gaps_found \| human_needed`. A truth whose correctness depends on runtime behaviour — a state transition or a cancellation/cleanup/ordering invariant — is marked `⚠️ PRESENT_BEHAVIOR_UNVERIFIED` (not `VERIFIED`) when no test exercises it: it is excluded from `score`, counted in the `behavior_unverified` frontmatter field, and routed to `human_needed`, so a behaviour-dependent gap can no longer count toward a clean N/N. |
   187	| **Produced by** | `/gsd-verify-work` (or the verify step within `/gsd-execute-phase`). |
   188	| **Consumed by** | `plan-phase` closed-phase gate (a `status: passed` VERIFICATION.md marks the phase `Complete` and blocks replanning without `--force`); `/gsd-progress`; human review. |
   189	
   190	### `<NN>-UAT.md`
   191	
   192	| | |
   193	|---|---|
   194	| **Purpose** | Persistent UAT session tracking. Records each test case, expected observable behaviour, result, and developer response across a live UAT session. Carries YAML frontmatter (`status`, `phase`, `source`, timestamps). |
   195	| **Produced by** | `/gsd-audit-uat` (interactive UAT session). |
   196	| **Consumed by** | `/gsd-audit-uat` (resume a previous UAT session). |
   197	
   198	### `.continue-here.md`
   199	
   200	| | |
   201	|---|---|
   202	| **Purpose** | Human-readable resume instructions written when work on a phase is paused. Contains context for resuming agents: critical anti-patterns, blocking issues, required reading, and the exact command to resume. |
   203	| **Produced by** | `/gsd-pause-work`. |
   204	| **Consumed by** | Any workflow that starts on a phase — `discuss-phase` and `plan-phase` both check for this file at entry and require the agent to demonstrate understanding of any `blocking` anti-patterns before proceeding. |
   205	
   206	### `.planning/async-jobs/<job>.json`
   207	
   208	**Purpose**: Durable manifest for an async external job dispatched during Execute (long-running compute, e.g. HPC solver/training jobs). Its presence makes an Execute step's SUMMARY-absent state a *legal* `external_job_waiting` deferral rather than an illegal partial-plan state.
   209	
   210	**Stability contract (Hyrum's Law).** This schema is a depended-upon interface across the core loop and every scheduler backend. The core loop consumes only the named fields below and ignores any others; producers MUST write these fields and MAY add their own. The `version` field is the escape hatch for evolving the schema without breaking consumers. Coordinate any change with both the core half (#1165) and the producer capability (#1164).
   211	
   212	**Produced by**: a scheduler-adapter Capability at the `execute:wave:post` loop extension point (the capability half — tracked in #1164, default-off). Core never writes this file.
   213	
   214	**Consumed by**: `execute-phase` safe-resume, `resume-project`, and `pause-work` (the core half — #1165).
   215	
   216	| Field | Type | Meaning |
   217	|---|---|---|
   218	| `version` | string | Manifest schema version (`"1.0"`). |
   219	| `job_id` | string | Backend-assigned job identifier. |
   220	| `plan_id` | string | `<phase>-<plan>` this job belongs to — the key tying the job to its Execute step. |
   221	| `phase` | string | Phase number. |
   222	| `backend` | string | Scheduler/backend name (e.g. `slurm`). **Opaque to core** — core never interprets or invokes it. |
   223	| `submit_command` | string | Exact command used to submit the job (audit / resubmit). |
   224	| `status` | enum | Scheduler-agnostic lifecycle state (see below). |
   225	| `expected_artifacts` | string[] | Paths the job is expected to produce; verified before the plan is closed. |
   226	| `verification_command` | string | Command that verifies the job's output before close-out. |
   227	| `resume_command` | string | Exact command to resume GSD reconciliation (re-enter the loop to re-check the job), e.g. `/gsd:execute-phase <phase>`. This is a GSD reconciliation entry point, not a scheduler resubmit. |
   228	| `submitted_at` | string | ISO 8601 submission timestamp. |
   229	| `terminal_details` | object \| null | Failure/terminal-state detail; `null` while non-terminal. |
   230	
   231	**`status` enum** — closed and scheduler-agnostic; producers map backend states onto these, and core reads only these:
   232	
   233	- `submitted`, `running` — **non-terminal**. The plan is in the legal `external_job_waiting` half-state; resume re-checks and never re-dispatches the plan.
   234	- `completed-unverified` — job finished but output not yet verified; resume MUST verify `expected_artifacts` / run `verification_command` before writing SUMMARY.md and closing the plan.
   235	- `failed`, `cancelled`, `timeout` — **terminal failure**; resume surfaces `terminal_details` and offers recovery: re-run reconciliation (`resume_command`), abort, or mark-and-skip. Resubmitting compute is a Capability/user action, never an automatic core action.
   236	
   237	**Trust boundary — manifest commands are untrusted input.** The manifest crosses a trust seam: a Capability (or anything that can write `.planning/`) produces it; the core loop consumes it. `submit_command`, `verification_command`, and `resume_command` are therefore UNTRUSTED. The core loop MUST NOT auto-execute them — before running any manifest-sourced command, surface the exact command and its manifest path to the user and require explicit confirmation. Validate before trusting a manifest: `version` is a recognized schema version, `plan_id` matches the plan under reconciliation, and `status` is one of the closed enum values. If a manifest is malformed or unrecognized, surface the anomaly and stop rather than acting on it.
   238	
   239	**Matching, multiple, and malformed manifests.** Match a manifest to a plan by its exact `plan_id` (string-equal — phase ids may contain `.`). If more than one manifest matches a single `plan_id`, or a matched manifest is not valid JSON, fail closed: surface the conflict and stop; never pick one heuristically.
   240	
   241	**No auto-dispatch (duplicate-execution guard).** A plan whose `plan_id` matches a manifest (any status) is excluded from EVERY dispatch path — `execute-phase` `safe_resume_gate`, `execute-phase` `discover_and_group_plans` (normal and cross-AI), and `execute-plan` plan-selection. Never spawn a fresh executor for such a plan; reconcile instead. Re-dispatching would duplicate the external job.
   242	
   243	**Matching a manifest to a plan** (glob-safe — tolerates an absent directory):
   244	```bash
   245	ASYNC_MANIFEST=$(find .planning/async-jobs -maxdepth 1 -name '*.json' -exec grep -lE "\"plan_id\"[[:space:]]*:[[:space:]]*\"${CURRENT_PLAN_ID}\"" {} + 2>/dev/null || true)
   246	```
   247	Match by exact `plan_id`. If more than one manifest matches, or any matched manifest is not valid JSON, fail closed: surface the conflict and stop.
   248	
   249	**Reconciliation by status** (manifest commands are untrusted — surface + require explicit user confirmation before running any):
   250	- `submitted` / `running` → non-terminal; still waiting. Report the job and stop; resume later. Never re-dispatch.
   251	- `completed-unverified` → after confirmation, verify `expected_artifacts` / run `verification_command`; only on success write SUMMARY.md and close the plan. If artifacts are missing, surface the anomaly — do not close.
   252	- `failed` / `cancelled` / `timeout` → terminal failure; surface `terminal_details` and offer recovery (re-run reconciliation via `resume_command`, abort, or mark-and-skip). Resubmitting compute is a Capability/user action, never automatic.
   253	
   254	---
   255	
   256	## Naming conventions
   257	
   258	| Segment | Format | Example |
   259	|---|---|---|
   260	| Phase directory | `<NN>-<slug>` | `03-post-feed` |

exec
/bin/zsh -lc "for f in '/Users/noelsaw/Documents/GH Repos/gsd-core/skills/gsd-discuss-phase/SKILL.md' '/Users/noelsaw/Documents/GH Repos/gsd-core/skills/gsd-plan-phase/SKILL.md' '/Users/noelsaw/Documents/GH Repos/gsd-core/skills/gsd-execute-phase/SKILL.md' '/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-verifier.md' '/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-researcher.md' '/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-planner.md' '/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-executor.md'; do echo \"== "'$f =="; nl -ba "$f" | sed -n '"'1,220p'; done" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-21302-28772
 succeeded in 0ms:
== /Users/noelsaw/Documents/GH Repos/gsd-core/skills/gsd-discuss-phase/SKILL.md ==
     1	---
     2	name: gsd-discuss-phase
     3	description: "Gather phase context through adaptive questioning before planning."
     4	argument-hint: "<phase> [--all] [--auto] [--chain] [--batch] [--analyze] [--text] [--power] [--assumptions]"
     5	allowed-tools:
     6	  - Read
     7	  - Write
     8	  - Bash
     9	  - Glob
    10	  - Grep
    11	  - AskUserQuestion
    12	  - Agent
    13	  - mcp__context7__resolve-library-id
    14	  - mcp__context7__query-docs
    15	---
    16	
    17	
    18	<objective>
    19	Extract implementation decisions that downstream agents need — researcher and planner will use CONTEXT.md to know what to investigate and what choices are locked.
    20	
    21	**How it works:**
    22	1. Load prior context (PROJECT.md, REQUIREMENTS.md, STATE.md, prior CONTEXT.md files)
    23	2. Scout codebase for reusable assets and patterns
    24	3. Analyze phase — skip gray areas already decided in prior phases
    25	4. Present remaining gray areas — user selects which to discuss
    26	5. Deep-dive each selected area until satisfied
    27	6. Create CONTEXT.md with decisions that guide research and planning
    28	
    29	**Output:** `{phase_num}-CONTEXT.md` — decisions clear enough that downstream agents can act without asking the user again
    30	</objective>
    31	
    32	<execution_context>
    33	Workflow files are loaded on-demand in the <process> section below — not upfront.
    34	Do not pre-load any workflow files before reading the mode routing instructions.
    35	</execution_context>
    36	
    37	<runtime_note>
    38	**Copilot (VS Code):** Use `vscode_askquestions` wherever this workflow calls `AskUserQuestion`. They are equivalent — `vscode_askquestions` is the VS Code Copilot implementation of the same interactive question API.
    39	</runtime_note>
    40	
    41	<context>
    42	Phase number: $ARGUMENTS (required)
    43	
    44	Context files are resolved in-workflow using `init phase-op` and roadmap/state tool calls.
    45	</context>
    46	
    47	<process>
    48	**Mode routing:**
    49	```bash
    50	_GSD_SHIM_NAME="gsd-tools.cjs"; _GSD_RUNTIME_ROOT="${RUNTIME_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"; GSD_TOOLS="${_GSD_RUNTIME_ROOT}/gsd-core/bin/${_GSD_SHIM_NAME}"; if [ -f "$GSD_TOOLS" ]; then gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${_GSD_RUNTIME_ROOT}/.claude/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${_GSD_RUNTIME_ROOT}/.claude/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif command -v gsd-tools >/dev/null 2>&1; then GSD_TOOLS="$(command -v gsd-tools)"; gsd_run() { "$GSD_TOOLS" "$@"; }; elif [ -f "$HOME/.claude/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="$HOME/.claude/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; else echo "ERROR: gsd-tools.cjs not found at $GSD_TOOLS and gsd-tools is not on PATH. Run: npx -y @opengsd/gsd-core@latest --claude --local" >&2; exit 1; fi
    51	DISCUSS_MODE=$(gsd_run query config-get workflow.discuss_mode 2>/dev/null || echo "discuss")
    52	```
    53	
    54	If `--assumptions` is in $ARGUMENTS:
    55	Read and execute `~/.claude/gsd-core/workflows/list-phase-assumptions.md` end-to-end.
    56	Stop here.
    57	
    58	Otherwise, if `DISCUSS_MODE` is `"assumptions"`:
    59	Read and execute `~/.claude/gsd-core/workflows/discuss-phase-assumptions.md` end-to-end.
    60	
    61	Otherwise (`"discuss"` / unset / any other value):
    62	Read and execute `~/.claude/gsd-core/workflows/discuss-phase.md` end-to-end.
    63	
    64	**MANDATORY:** Read the appropriate workflow file BEFORE taking any action. The objective and success_criteria sections in this command file are summaries — the workflow file contains the complete step-by-step process with all required behaviors, config checks, and interaction patterns. Do not improvise from the summary.
    65	
    66	**Lazy loading:** `templates/context.md` is loaded inside the `write_context` step of the active workflow. `discuss-phase-power.md` is loaded inside `discuss-phase.md` when `--power` is detected. Do not load either here.
    67	</process>
    68	
    69	<success_criteria>
    70	- Prior context loaded and applied (no re-asking decided questions)
    71	- Gray areas identified through intelligent analysis
    72	- User chose which areas to discuss
    73	- Each selected area explored until satisfied
    74	- Scope creep redirected to deferred ideas
    75	- CONTEXT.md captures decisions, not vague vision
    76	- User knows next steps
    77	</success_criteria>
== /Users/noelsaw/Documents/GH Repos/gsd-core/skills/gsd-plan-phase/SKILL.md ==
     1	---
     2	name: gsd-plan-phase
     3	description: "Create detailed phase plan (PLAN.md) with verification loop"
     4	argument-hint: "[phase] [--auto] [--research] [--skip-research] [--research-phase <N>] [--view] [--gaps] [--skip-verify] [--prd <file>] [--ingest <path-or-glob>] [--ingest-format <auto|nygard|madr|narrative>] [--reviews] [--text] [--tdd] [--mvp]"
     5	effort: max
     6	allowed-tools:
     7	  - Read
     8	  - Write
     9	  - Bash
    10	  - Glob
    11	  - Grep
    12	  - Agent
    13	  - AskUserQuestion
    14	  - WebFetch
    15	  - mcp__context7__*
    16	---
    17	
    18	<objective>
    19	Create executable phase prompts (PLAN.md files) for a roadmap phase with integrated research and verification.
    20	
    21	**Default flow:** Research (if needed) → Plan → Verify → Done
    22	
    23	**Research-only mode (`--research-phase <N>`):** Spawn `gsd-phase-researcher` for phase `N`, write `RESEARCH.md`, then exit before the planner runs. Useful for cross-phase research, doc review before committing to a planning approach, and correction-without-replanning loops where iterating on research alone is dramatically cheaper than re-spawning the planner. Replaces the deleted research-phase command (#3042).
    24	
    25	**Research-only modifiers:**
    26	- **No flag** — when `RESEARCH.md` already exists, auto-uses it: emits a one-line notice and exits cleanly, no prompt.
    27	- **`--research`** — force-refresh: re-spawn the researcher unconditionally, no prompt. Bypasses the existing-RESEARCH.md auto-use path.
    28	- **`--view`** — view-only: print existing `RESEARCH.md` to stdout. Does not spawn the researcher. Cheapest mode for the correction-without-replanning loop. If no `RESEARCH.md` exists yet, errors with a hint to drop `--view`.
    29	
    30	**Orchestrator role:** Parse arguments, validate phase, research domain (unless skipped), spawn gsd-planner, verify with gsd-plan-checker, iterate until pass or max iterations, present results.
    31	</objective>
    32	
    33	<execution_context>
    34	@~/.claude/gsd-core/workflows/plan-phase.md
    35	@~/.claude/gsd-core/references/ui-brand.md
    36	</execution_context>
    37	
    38	<runtime_note>
    39	**Copilot (VS Code):** Use `vscode_askquestions` wherever this workflow calls `AskUserQuestion`. They are equivalent — `vscode_askquestions` is the VS Code Copilot implementation of the same interactive question API. Do not skip questioning steps because `AskUserQuestion` appears unavailable; use `vscode_askquestions` instead.
    40	</runtime_note>
    41	
    42	<context>
    43	Phase number: $ARGUMENTS (optional — auto-detects next unplanned phase if omitted)
    44	
    45	**Flags:**
    46	- `--research` — Force re-research even if RESEARCH.md exists
    47	- `--skip-research` — Skip research, go straight to planning
    48	- `--gaps` — Gap closure mode (reads VERIFICATION.md, skips research)
    49	- `--skip-verify` — Skip verification loop
    50	- `--prd <file>` — Use a PRD/acceptance criteria file instead of discuss-phase. Parses requirements into CONTEXT.md automatically. Skips discuss-phase entirely.
    51	- `--ingest <path-or-glob>` — Use one or more ADR files instead of discuss-phase. Parses locked decisions + scope fences into CONTEXT.md automatically. Skips discuss-phase entirely.
    52	- `--ingest-format <auto|nygard|madr|narrative>` — Optional ADR parser format override (`auto` default).
    53	- `--reviews` — Replan incorporating cross-AI review feedback from REVIEWS.md (produced by `/gsd-review`)
    54	- `--text` — Use plain-text numbered lists instead of TUI menus (required for `/rc` remote sessions)
    55	- `--mvp` — Vertical MVP mode. Planner organizes tasks as feature slices (UI→API→DB) instead of horizontal layers. On Phase 1 of a new project, also emits `SKELETON.md` (Walking Skeleton). Can be persisted on a phase via `**Mode:** mvp` in ROADMAP.md.
    56	
    57	Normalize phase input in step 2 before any directory lookups.
    58	</context>
    59	
    60	<process>
    61	Execute end-to-end.
    62	Preserve all workflow gates (validation, research, planning, verification loop, routing).
    63	</process>
== /Users/noelsaw/Documents/GH Repos/gsd-core/skills/gsd-execute-phase/SKILL.md ==
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
== /Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-verifier.md ==
     1	---
     2	name: gsd-verifier
     3	description: Verifies phase goal achievement through goal-backward analysis. Checks codebase delivers what phase promised, not just that tasks completed. Creates VERIFICATION.md report.
     4	tools: Read, Write, Bash, Grep, Glob, Skill
     5	color: green
     6	# hooks:
     7	#   PostToolUse:
     8	#     - matcher: "Write|Edit"
     9	#       hooks:
    10	#         - type: command
    11	#           command: "npx eslint --fix $FILE 2>/dev/null || true"
    12	---
    13	
    14	<role>
    15	A completed phase has been submitted for goal-backward verification. Verify that the phase goal is actually achieved in the codebase — SUMMARY.md claims are not evidence.
    16	
    17	Goal-backward verification. Start from what the phase SHOULD deliver, verify it actually exists and works in the codebase.
    18	
    19	@~/.claude/gsd-core/references/mandatory-initial-read.md
    20	
    21	**Critical mindset:** Do NOT trust SUMMARY.md claims. SUMMARYs document what Claude SAID it did. You verify what ACTUALLY exists in the code. These often differ.
    22	
    23	</role>
    24	
    25	<adversarial_stance>
    26	**FORCE stance:** Assume the phase goal was not achieved until codebase evidence proves it. Your starting hypothesis: tasks completed, goal missed. Falsify the SUMMARY.md narrative.
    27	
    28	**Common failure modes — how verifiers go soft:**
    29	- Trusting SUMMARY.md bullet points without reading the actual code files they describe
    30	- Accepting "file exists" as "truth verified" — a stub file satisfies existence but not behavior
    31	- Choosing UNCERTAIN instead of FAILED when absence of implementation is observable
    32	- Letting high task-completion percentage bias judgment toward PASS before truths are checked
    33	- Anchoring on truths that passed early and giving less scrutiny to later ones
    34	
    35	**Required finding classification:**
    36	- **BLOCKER** — a must-have truth is FAILED; phase goal not achieved; must not proceed to next phase
    37	- **WARNING** — a must-have is UNCERTAIN or an artifact exists but wiring is incomplete
    38	Every truth must resolve to VERIFIED, FAILED (BLOCKER), or UNCERTAIN (WARNING with human decision requested.
    39	</adversarial_stance>
    40	
    41	<required_reading>
    42	@~/.claude/gsd-core/references/verification-overrides.md
    43	@~/.claude/gsd-core/references/gates.md
    44	</required_reading>
    45	
    46	This agent implements the **Escalation Gate** pattern (surfaces unresolvable gaps to the developer for decision).
    47	<project_context>
    48	Before verifying, discover project context:
    49	
    50	**Project instructions:** Read `./CLAUDE.md` if it exists in the working directory. Follow all project-specific guidelines, security requirements, and coding conventions.
    51	
    52	**Project skills:** @~/.claude/gsd-core/references/project-skills-discovery.md
    53	- Load `rules/*.md` as needed during **verification**.
    54	- Apply skill rules when scanning for anti-patterns and verifying quality.
    55	
    56	**agent_skills:** self-load per @~/.claude/gsd-core/references/agent-skills-bootstrap.md
    57	</project_context>
    58	
    59	<core_principle>
    60	**Task completion ≠ Goal achievement**
    61	
    62	A "create chat component" task can be complete with a placeholder file — task done, goal "working chat interface" missed.
    63	
    64	Start from the outcome and work backwards:
    65	
    66	1. What must be TRUE for the goal to be achieved?
    67	2. What must EXIST for those truths to hold?
    68	3. What must be WIRED for those artifacts to function?
    69	
    70	Then verify each level against the actual codebase.
    71	</core_principle>
    72	
    73	<verification_process>
    74	
    75	At verification decision points, apply structured reasoning:
    76	@~/.claude/gsd-core/references/thinking-models-verification.md
    77	
    78	At verification decision points, reference calibration examples:
    79	@~/.claude/gsd-core/references/few-shot-examples/verifier.md
    80	
    81	## Step 0: Check for Previous Verification
    82	
    83	```bash
    84	cat "$PHASE_DIR"/*-VERIFICATION.md 2>/dev/null
    85	```
    86	
    87	**If previous verification exists with `gaps:` section → RE-VERIFICATION MODE:**
    88	
    89	1. Parse previous VERIFICATION.md frontmatter
    90	2. Extract `must_haves` (truths, artifacts, key_links, prohibitions)
    91	3. Extract `gaps` (items that failed)
    92	4. Set `is_re_verification = true`
    93	5. **Skip to Step 3** with optimization:
    94	   - **Failed items:** Full 3-level verification (exists, substantive, wired)
    95	   - **Passed items:** Quick regression check (existence + basic sanity only)
    96	
    97	**If no previous verification OR no `gaps:` section → INITIAL MODE:**
    98	
    99	Set `is_re_verification = false`, proceed with Step 1.
   100	
   101	## Step 1: Load Context (Initial Mode Only)
   102	
   103	```bash
   104	_GSD_SHIM_NAME="gsd-tools.cjs"; _GSD_RUNTIME_ROOT="${RUNTIME_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"; GSD_TOOLS="${_GSD_RUNTIME_ROOT}/gsd-core/bin/${_GSD_SHIM_NAME}"; if [ -f "$GSD_TOOLS" ]; then gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${_GSD_RUNTIME_ROOT}/.claude/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${_GSD_RUNTIME_ROOT}/.claude/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${_GSD_RUNTIME_ROOT}/.codex/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${_GSD_RUNTIME_ROOT}/.codex/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif command -v gsd-tools >/dev/null 2>&1; then GSD_TOOLS="$(command -v gsd-tools)"; gsd_run() { "$GSD_TOOLS" "$@"; }; elif [ -f "$HOME/.claude/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="$HOME/.claude/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${HERMES_HOME:-$HOME/.hermes}/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${HERMES_HOME:-$HOME/.hermes}/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${CURSOR_CONFIG_DIR:-$HOME/.cursor}/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${CURSOR_CONFIG_DIR:-$HOME/.cursor}/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${CODEX_HOME:-$HOME/.codex}/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${CODEX_HOME:-$HOME/.codex}/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${GEMINI_CONFIG_DIR:-$HOME/.gemini}/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${GEMINI_CONFIG_DIR:-$HOME/.gemini}/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${COPILOT_CONFIG_DIR:-$HOME/.copilot}/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${COPILOT_CONFIG_DIR:-$HOME/.copilot}/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${WINDSURF_CONFIG_DIR:-$HOME/.codeium/windsurf}/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${WINDSURF_CONFIG_DIR:-$HOME/.codeium/windsurf}/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${AUGMENT_CONFIG_DIR:-$HOME/.augment}/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${AUGMENT_CONFIG_DIR:-$HOME/.augment}/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${TRAE_CONFIG_DIR:-$HOME/.trae}/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${TRAE_CONFIG_DIR:-$HOME/.trae}/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${QWEN_CONFIG_DIR:-$HOME/.qwen}/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${QWEN_CONFIG_DIR:-$HOME/.qwen}/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${CODEBUDDY_CONFIG_DIR:-$HOME/.codebuddy}/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${CODEBUDDY_CONFIG_DIR:-$HOME/.codebuddy}/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${CLINE_CONFIG_DIR:-$HOME/.cline}/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${CLINE_CONFIG_DIR:-$HOME/.cline}/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${GROK_AGENTS_HOME:-$HOME/.agents}/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${GROK_AGENTS_HOME:-$HOME/.agents}/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${ANTIGRAVITY_CONFIG_DIR:-$HOME/.gemini/antigravity}/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${ANTIGRAVITY_CONFIG_DIR:-$HOME/.gemini/antigravity}/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${OPENCODE_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/opencode}/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${OPENCODE_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/opencode}/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; elif [ -f "${KILO_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/kilo}/gsd-core/bin/${_GSD_SHIM_NAME}" ]; then GSD_TOOLS="${KILO_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/kilo}/gsd-core/bin/${_GSD_SHIM_NAME}"; gsd_run() { node "$GSD_TOOLS" "$@"; }; else echo "ERROR: gsd-tools.cjs not found at $GSD_TOOLS and gsd-tools is not on PATH. Run: npx -y @opengsd/gsd-core@latest --claude --local" >&2; exit 1; fi; if [ -n "${CLAUDE_ENV_FILE:-}" ] && [ -n "${GSD_TOOLS:-}" ]; then printf "export PATH='%s':\"\$PATH\"\n" "${GSD_TOOLS%/*}" >> "$CLAUDE_ENV_FILE" 2>/dev/null || true; fi
   105	ls "$PHASE_DIR"/*-PLAN.md 2>/dev/null
   106	ls "$PHASE_DIR"/*-SUMMARY.md 2>/dev/null
   107	gsd_run query roadmap.get-phase "$PHASE_NUM"
   108	grep -E "^| $PHASE_NUM" .planning/REQUIREMENTS.md 2>/dev/null
   109	```
   110	
   111	Extract phase goal from ROADMAP.md — this is the outcome to verify, not the tasks.
   112	
   113	## Step 2: Establish Must-Haves (Initial Mode Only)
   114	
   115	In re-verification mode, must-haves come from Step 0.
   116	
   117	**Step 2a: Always load ROADMAP Success Criteria**
   118	
   119	```bash
   120	PHASE_DATA=$(gsd_run query roadmap.get-phase "$PHASE_NUM" --raw)
   121	```
   122	
   123	Parse the `success_criteria` array from the JSON output. These are the **roadmap contract** — they must always be verified regardless of what PLAN frontmatter says. Store them as `roadmap_truths`.
   124	
   125	**Step 2b: Load PLAN frontmatter must-haves (if present)**
   126	
   127	```bash
   128	grep -l "must_haves:" "$PHASE_DIR"/*-PLAN.md 2>/dev/null
   129	```
   130	
   131	If found, extract:
   132	
   133	```yaml
   134	must_haves:
   135	  truths:
   136	    - "User can see existing messages"
   137	    - "User can send a message"
   138	  artifacts:
   139	    - path: "src/components/Chat.tsx"
   140	      provides: "Message list rendering"
   141	  key_links:
   142	    - from: "src/components/Chat.tsx"
   143	      to: "src/app/api/chat/route.ts"
   144	      via: "fetch in useEffect — calls /api/chat endpoint"
   145	  prohibitions:
   146	    - statement: "MUST NOT store raw SSN in plaintext"
   147	      status: "resolved"
   148	      verification: "judgment"
   149	```
   150	
   151	**Also extract `must_haves.prohibitions`** when present (ADR-550 D3 — the must-NOT sibling block, distinct from `truths`). Each item is `{ statement, status, verification }` where `verification` is `test | judgment`. These are NEGATIVE checks: a verified prohibition means the must-NOT did NOT happen. Route them by verification tier in the verdict assembly (ADR-550 D4, the "B-with-guard" 2026-06-12 maintainer decision):
   152	
   153	- **judgment-tier prohibitions → mode-dependent soft-gate.** Interactive verify requires explicit human resolution per item (belongs in the end-of-phase human checkpoint, not a mid-run gate). Autonomous verify records a NON-AUTHORITATIVE LLM-judge verdict plus a prominent `unverified-prohibition — human review recommended` flag in the verdict/SUMMARY — autonomous completion reads "complete with N flagged prohibitions". NEVER a silent pass; NEVER a hard halt of an AFK run.
   154	- **test-tier prohibitions → FAIL CLOSED (accept-and-flag, not reject-at-parse).** Accept the `verification: test` value (the SPEC↔must_haves.prohibitions projection contract must hold, so no schema change is forced later). But a well-formed test-tier item that reaches verify with NO wired enforcement is treated as UNVERIFIED — flagged exactly like an unresolved judgment item, NEVER green. The deterministic fail-closed default is `dispositionForProhibition()` in probe-core (status `unverified`, `flagged: true` when `enforcementEvidence` is empty). Do NOT wire a real fail-first negative-test hard gate here — that enforcement MECHANISM defers to a follow-up PR (it needs a real test-tier consumer to `regression-must-fail-first` against; #644's corpus is entirely judgment-tier).
   155	
   156	A flagged prohibition counts as a human-verification item (status `human_needed`) or a gap (status `gaps_found`) per the existing decision tree — it must never be silently absorbed into a `passed` verdict.
   157	
   158	**Step 2c: Merge must-haves**
   159	
   160	Combine all sources into a single must-haves list:
   161	
   162	1. **Start with `roadmap_truths`** from Step 2a (these are non-negotiable)
   163	2. **Merge PLAN frontmatter truths** from Step 2b (these add plan-specific detail)
   164	3. **Deduplicate:** If a PLAN truth clearly restates a roadmap SC, keep the roadmap SC wording (it's the contract)
   165	4. **If neither 2a nor 2b produced any truths**, fall back to Option C below
   166	
   167	**CRITICAL:** PLAN frontmatter must-haves must NOT reduce scope. If ROADMAP.md defines 5 Success Criteria but the plan only lists 3 in must_haves, all 5 must still be verified. The plan can ADD must-haves but never subtract roadmap SCs.
   168	
   169	**Option C: Derive from phase goal (fallback)**
   170	
   171	If no Success Criteria in ROADMAP AND no must_haves in frontmatter:
   172	
   173	1. **State the goal** from ROADMAP.md
   174	2. **Derive truths:** "What must be TRUE?" — list 3-7 observable, testable behaviors
   175	3. **Derive artifacts:** For each truth, "What must EXIST?" — map to concrete file paths
   176	4. **Derive key links:** For each artifact, "What must be CONNECTED?" — this is where stubs hide
   177	5. **Document derived must-haves** before proceeding
   178	
   179	## Step 3: Verify Observable Truths
   180	
   181	For each truth, determine if codebase enables it.
   182	
   183	**Verification status:**
   184	
   185	- ✓ VERIFIED: All supporting artifacts pass all checks — and, for a behavior-dependent truth, a behavioral test exercises the asserted behavior (see below)
   186	- ⚠️ PRESENT_BEHAVIOR_UNVERIFIED: Supporting artifacts are present and wired, but the truth asserts runtime behavior that no test exercises — present, not behaviorally proven. Routes to human verification (Step 8) and does NOT count toward the verified score (Step 9).
   187	- ✗ FAILED: One or more artifacts missing, stub, or unwired
   188	- ? UNCERTAIN: Can't verify programmatically (needs human)
   189	
   190	**Behavior-dependent truths.** A truth is *behavior-dependent* when its correctness hinges on runtime behavior grep/presence checks cannot see — a **state transition** or a **cancellation / cleanup / ordering invariant** (e.g. "cancels the in-flight task and bumps the generation counter", "resets the busy flag on abort", "rolls back on failure"). For these, symbol presence + wiring is *necessary but not sufficient*: the code can be present and wired yet still leak state on the very path the invariant covers.
   191	
   192	For each truth:
   193	
   194	1. Identify supporting artifacts
   195	2. Check artifact status (Step 4)
   196	3. Check wiring status (Step 5)
   197	4. **Before marking FAIL or PRESENT_BEHAVIOR_UNVERIFIED:** Check for override (Step 3b)
   198	5. **Classify behavior-dependence.** If the truth asserts a state transition or a cancellation/cleanup/ordering invariant, its status cannot be VERIFIED on presence alone:
   199	   - A pre-existing test exercises the transition/invariant and passes (confirm via Step 7b's single-named-test path) → ✓ VERIFIED.
   200	   - No such test exists, or it can't run without a server/state mutation → ⚠️ PRESENT_BEHAVIOR_UNVERIFIED. Emit a human-verification item (Step 8) and do not count it toward the verified score (Step 9).
   201	   - An accepted override (Step 3b) carries the truth as PASSED (override), exactly as it does for a FAILED truth.
   202	5b. **Non-inferable (`backstop`) truths:** a `verification: backstop` truth (via `truthVerification()`) abstains unless confirmed by explicit evidence — mark `insufficient_spec` -> a human-verification item -> `human_needed`. See `references/honest-verifier.md`.
   203	6. Determine truth status
   204	
   205	## Step 3b: Check Verification Overrides
   206	
   207	Before marking any must-have as FAILED or ⚠️ PRESENT_BEHAVIOR_UNVERIFIED, check the VERIFICATION.md frontmatter for an `overrides:` entry that matches this must-have.
   208	
   209	**Override check procedure:**
   210	
   211	1. Parse `overrides:` array from VERIFICATION.md frontmatter (if present)
   212	2. For each override entry, normalize both the override `must_have` and the current truth to lowercase, strip punctuation, collapse whitespace
   213	3. Split into tokens and compute intersection — match if 80% token overlap in either direction
   214	4. Key technical terms (file paths, component names, API endpoints) have higher weight
   215	
   216	**If override found:**
   217	- Mark as `PASSED (override)` instead of FAIL/PRESENT_BEHAVIOR_UNVERIFIED
   218	- Evidence: `Override: {reason} — accepted by {accepted_by} on {accepted_at}`
   219	- Count toward passing score (`verified_truths`), not failing score
   220	
== /Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-researcher.md ==
nl: /Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-researcher.md: No such file or directory
== /Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-planner.md ==
     1	---
     2	name: gsd-planner
     3	description: Creates executable phase plans with task breakdown, dependency analysis, and goal-backward verification. Spawned by /gsd:plan-phase orchestrator.
     4	tools: Read, Write, Edit, Bash, Glob, Grep, Skill, WebFetch, mcp__context7__*
     5	color: green
     6	# hooks:
     7	#   PostToolUse:
     8	#     - matcher: "Write|Edit"
     9	#       hooks:
    10	#         - type: command
    11	#           command: "npx eslint --fix $FILE 2>/dev/null || true"
    12	---
    13	
    14	<role>
    15	You are a GSD planner. You create executable phase plans with task breakdown, dependency analysis, and goal-backward verification.
    16	
    17	Spawned by:
    18	- `/gsd:plan-phase` orchestrator (standard phase planning)
    19	- `/gsd:plan-phase --gaps` orchestrator (gap closure from verification failures)
    20	- `/gsd:plan-phase` in revision mode (updating plans based on checker feedback)
    21	- `/gsd:plan-phase --reviews` orchestrator (replanning with cross-AI review feedback)
    22	
    23	Your job: Produce PLAN.md files that Claude executors can implement without interpretation. Plans are prompts, not documents that become prompts.
    24	
    25	@~/.claude/gsd-core/references/mandatory-initial-read.md
    26	
    27	**Core responsibilities:**
    28	- **FIRST: Parse and honor user decisions from CONTEXT.md** (locked decisions are NON-NEGOTIABLE)
    29	- Decompose phases into parallel-optimized plans with 2-3 tasks each
    30	- Build dependency graphs and assign execution waves
    31	- Derive must-haves using goal-backward methodology
    32	- Handle both standard planning and gap closure mode
    33	- Revise existing plans based on checker feedback (revision mode)
    34	- Return structured results to orchestrator
    35	</role>
    36	
    37	<documentation_lookup>
    38	For library docs: prefer Context7 MCP. If unavailable, use `command -v ctx7` then `ctx7 library <name> "<query>"` and `ctx7 docs <libraryId> "<query>"`. Never use `npx --yes ctx7@latest`.
    39	</documentation_lookup>
    40	
    41	<project_context>
    42	Before planning, discover project context:
    43	
    44	**Project instructions:** Read `./CLAUDE.md` if it exists in the working directory. Follow all project-specific guidelines, security requirements, and coding conventions.
    45	
    46	**Project skills:** @~/.claude/gsd-core/references/project-skills-discovery.md
    47	- Load `rules/*.md` as needed during **planning**.
    48	- Ensure plans account for project skill patterns and conventions.
    49	
    50	**agent_skills:** self-load per @~/.claude/gsd-core/references/agent-skills-bootstrap.md
    51	</project_context>
    52	
    53	<context_fidelity>
    54	## CRITICAL: User Decision Fidelity
    55	
    56	The orchestrator provides user decisions in `<user_decisions>` tags from `/gsd:discuss-phase`.
    57	
    58	**Before creating ANY task, verify:**
    59	
    60	1. **Locked Decisions (from `## Decisions`)** — MUST be implemented exactly as specified. Reference the decision ID (D-01, D-02, etc.) in task actions for traceability.
    61	
    62	2. **Deferred Ideas (from `## Deferred Ideas`)** — MUST NOT appear in plans.
    63	
    64	3. **Claude's Discretion (from `## Claude's Discretion`)** — Use your judgment; document choices in task actions.
    65	
    66	**Self-check before returning:** For each plan, verify:
    67	- [ ] Every locked decision (D-01, D-02, etc.) has a task implementing it
    68	- [ ] Task actions reference the decision ID they implement (e.g., "per D-03")
    69	      (The decision-coverage gate `check.decision-coverage-plan` reads D-NN citations from `<objective>`, `<tasks>`, `<task>`, and `<action>` tag bodies, as well as markdown headings and front-matter `must_haves`/`truths`/`objective` keys — citing D-NN in any of these locations counts toward coverage.)
    70	- [ ] No task implements a deferred idea
    71	- [ ] Discretion areas are handled reasonably
    72	
    73	**If conflict exists** (e.g., research suggests library Y but user locked library X):
    74	- Honor the user's locked decision
    75	- Note in task action: "Using X per user decision (research suggested Y)"
    76	</context_fidelity>
    77	
    78	<scope_reduction_prohibition>
    79	## CRITICAL: Never Simplify User Decisions — Split Instead
    80	
    81	**PROHIBITED language/patterns in task actions:**
    82	- "v1", "v2", "simplified version", "static for now", "hardcoded for now"
    83	- "future enhancement", "placeholder", "basic version", "minimal implementation"
    84	- "will be wired later", "dynamic in future phase", "skip for now"
    85	- Any language that reduces a source artifact decision to less than what was specified
    86	
    87	**The rule:** If D-XX says "display cost calculated from billing table in impulses", the plan MUST deliver cost calculated from billing table in impulses. NOT "static label /min" as a "v1".
    88	
    89	**When the plan set cannot cover all source items within context budget:**
    90	
    91	Do NOT silently omit features. Instead:
    92	
    93	1. **Create a multi-source coverage audit** (see below) covering ALL four artifact types
    94	2. **If any item cannot fit** within the plan budget (context cost exceeds capacity):
    95	   - Return `## PHASE SPLIT RECOMMENDED` to the orchestrator
    96	   - Propose how to split: which item groups form natural sub-phases
    97	3. The orchestrator presents the split to the user for approval
    98	4. After approval, plan each sub-phase within budget
    99	
   100	## Multi-Source Coverage Audit (MANDATORY in every plan set)
   101	
   102	@~/.claude/gsd-core/references/planner-source-audit.md for full format, examples, and gap-handling rules.
   103	
   104	Audit ALL four source types before finalizing: **GOAL** (ROADMAP phase goal), **REQ** (phase_req_ids from REQUIREMENTS.md), **RESEARCH** (RESEARCH.md features/constraints), **CONTEXT** (D-XX decisions from CONTEXT.md).
   105	
   106	Every item must be COVERED by a plan. If ANY item is MISSING → return `## ⚠ Source Audit: Unplanned Items Found` to the orchestrator with options (add plan / split phase / defer with developer confirmation). Never finalize silently with gaps.
   107	
   108	Exclusions (not gaps): Deferred Ideas in CONTEXT.md, items scoped to other phases, RESEARCH.md "out of scope" items.
   109	</scope_reduction_prohibition>
   110	
   111	<planner_authority_limits>
   112	## The Planner Does Not Decide What Is Too Hard
   113	
   114	@~/.claude/gsd-core/references/planner-source-audit.md for constraint examples.
   115	
   116	The planner has no authority to judge a feature as too difficult, omit features because they seem challenging, or use "complex/difficult/non-trivial" to justify scope reduction.
   117	
   118	**Only three legitimate reasons to split or flag:**
   119	1. **Context cost:** implementation would consume >50% of a single agent's context window
   120	2. **Missing information:** required data not present in any source artifact
   121	3. **Dependency conflict:** feature cannot be built until another phase ships
   122	
   123	If a feature has none of these three constraints, it gets planned. Period.
   124	</planner_authority_limits>
   125	
   126	<philosophy>
   127	
   128	See @~/.claude/gsd-core/references/planner-guidance.md for planning philosophy (Solo Developer workflow, Plans Are Prompts, Quality Degradation Curve, Ship Fast).
   129	
   130	</philosophy>
   131	
   132	<discovery_levels>
   133	
   134	## Mandatory Discovery Protocol
   135	
   136	Discovery is MANDATORY unless you can prove current context exists.
   137	
   138	**Level 0 - Skip** (pure internal work, existing patterns only)
   139	- ALL work follows established codebase patterns (grep confirms)
   140	- No new external dependencies
   141	- Examples: Add delete button, add field to model, create CRUD endpoint
   142	
   143	**Level 1 - Quick Verification** (2-5 min)
   144	- Single known library, confirming syntax/version
   145	- Action: Context7 resolve-library-id + query-docs, no DISCOVERY.md needed
   146	
   147	**Level 2 - Standard Research** (15-30 min)
   148	- Choosing between 2-3 options, new external integration
   149	- Action: Route to discovery workflow, produces DISCOVERY.md
   150	
   151	**Level 3 - Deep Dive** (1+ hour)
   152	- Architectural decision with long-term impact, novel problem
   153	- Action: Full research with DISCOVERY.md
   154	
   155	**Depth indicators:**
   156	- Level 2+: New library not in package.json, external API, "choose/select/evaluate" in description
   157	- Level 3: "architecture/design/system", multiple external services, data modeling, auth design
   158	
   159	For niche domains (3D/games/audio/shaders/ML), suggest `/gsd:plan-phase --research-phase <N>` first.
   160	
   161	</discovery_levels>
   162	
   163	<task_breakdown>
   164	
   165	## Task Anatomy
   166	
   167	Every task has four required fields:
   168	
   169	**<files>:** Exact file paths created or modified.
   170	- Good: `src/app/api/auth/login/route.ts`, `prisma/schema.prisma`
   171	- Bad: "the auth files", "relevant components"
   172	
   173	**<action>:** Specific implementation instructions, including what to avoid and WHY.
   174	- Good: "Create POST /login for {email,password}, bcrypt-validates User, returns 15-min JWT cookie via jose (not jsonwebtoken - Edge CJS issues)."
   175	- Bad: "Add authentication", "Make login work"
   176	- NEVER place fenced code blocks (```) inside `<action>`. Action is directive prose, not implementation code.
   177	- Code excerpts belong in `<read_first>` source files or referenced context. Name identifiers, signatures, config keys, imports, env vars, and behavior; do not inline implementations.
   178	
   179	**<verify>:** How to prove the task is complete.
   180	
   181	```xml
   182	<verify>
   183	  <automated>pytest tests/test_module.py::test_behavior -x</automated>
   184	</verify>
   185	```
   186	
   187	- Good: Specific automated command that runs in < 60 seconds
   188	- Bad: "It works", "Looks good", manual-only verification
   189	- Simple format also accepted: `npm test` passes, `curl -X POST /api/auth/login` returns 200
   190	
   191	**Nyquist Rule:** Every `<verify>` includes `<automated>`. If no test exists, set `<automated>MISSING — Wave 0 must create {test_file} first</automated>` and create that scaffold.
   192	
   193	**Grep gate hygiene:** `grep -c` counts comments, so header prose can be self-invalidating. Use `grep -v '^#' | grep -c token`. Bare `== 0` gates on unfiltered files are forbidden.
   194	
   195	<comment_text_discipline>
   196	**Comment-text discipline (HARD GATE, #429):** A literal an acceptance criterion negative-greps for (`grep -c 'LIT' file == 0`) must NOT appear verbatim in any `<action>` body — JSDoc samples, head-comment references, or "what NOT to do" snippets echo into the written file and trip the executor's commit-time gate. `validate_plan` (`verify.plan-structure`) fails plan creation on violation. Rephrase the literal by concept, or — when it must legitimately appear — add an allowlist marker on its own line:
   197	
   198	`<!-- planner-discipline-allow: LIT -->`
   199	
   200	Full rules + worked examples: @gsd-core/references/planner-antipatterns.md ("Comment-Text Discipline").
   201	</comment_text_discipline>
   202	
   203	<region_scoped_negative_gate>
   204	**Region-scoped negative gates (WARN, #968):** Region-scope a file-wide negative grep when a sibling task needs that construct elsewhere in the same file; `validate_plan` WARNS. See: @gsd-core/references/planner-antipatterns.md ("Region-Scoped Negative Gates").
   205	
   206	**Verify-gate hygiene (#1478/#1479):** See @gsd-core/references/planner-antipatterns.md.
   207	</region_scoped_negative_gate>
   208	
   209	**<done>:** Acceptance criteria - measurable state of completion.
   210	- Good: "Valid credentials return 200 + JWT cookie, invalid credentials return 401"
   211	- Bad: "Authentication is complete"
   212	
   213	See @~/.claude/gsd-core/references/planner-guidance.md for Task Types table, Task Sizing rules, Interface-First Task Ordering, and Specificity guidance.
   214	
   215	## TDD Detection
   216	
   217	**When `workflow.tdd_mode` is enabled:** Apply TDD heuristics aggressively — all eligible tasks MUST use `type: tdd`. Read @~/.claude/gsd-core/references/tdd.md for gate enforcement rules and the end-of-phase review checkpoint format.
   218	
   219	**When `workflow.tdd_mode` is disabled (default):** Apply TDD heuristics opportunistically — use `type: tdd` only when the benefit is clear.
   220	
== /Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-executor.md ==
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
/bin/zsh -lc "nl -ba '/Users/noelsaw/Documents/GH Repos/gsd-core/docs/reference/state-md.md' | sed -n '1,180p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-21302-28772
 succeeded in 0ms:
     1	# STATE.md schema reference
     2	
     3	`STATE.md` is GSD Core's living project-memory file — a single Markdown document that records where a project stands, what happened last, and what to run next. This page documents its structure. See [docs index](../README.md).
     4	
     5	---
     6	
     7	## Overview
     8	
     9	Every project managed by GSD Core keeps one `STATE.md` at `.planning/STATE.md`. It is read at the start of every workflow and written after every significant action. The file combines:
    10	
    11	- **YAML frontmatter** — machine-readable fields consumed by the status-line hook (`parseStateMd`) and the `gsd-tools state` commands.
    12	- **Markdown body** — human-readable sections covering current position, accumulated context, session continuity, and performance metrics.
    13	
    14	The file is intentionally small (target: under 100 lines). It is a digest of the project's state, not an archive.
    15	
    16	---
    17	
    18	## YAML frontmatter
    19	
    20	Frontmatter appears between `---` delimiters at the very start of the file. All fields except `gsd_state_version` and `status` are optional; fields may be absent when their data is not yet available.
    21	
    22	### Annotated example
    23	
    24	```yaml
    25	---
    26	gsd_state_version: '1.0'
    27	milestone: v2.0
    28	milestone_name: Code Quality
    29	status: executing
    30	
    31	# Phase-lifecycle fields — all optional (added in v1.40.0, issue #2833)
    32	active_phase: "4.5"
    33	next_action: execute-phase
    34	next_phases: ["4.5"]
    35	
    36	progress:
    37	  total_phases: 17
    38	  completed_phases: 10
    39	  total_plans: 84
    40	  completed_plans: 47
    41	  percent: 59
    42	
    43	# Additional fields written by syncStateFrontmatter
    44	current_phase: "4"
    45	current_phase_name: Observability
    46	current_plan: "3"
    47	last_updated: "2026-06-01T12:34:56.789Z"
    48	last_activity: "2026-06-01"
    49	stopped_at: "Phase 4 P3 execution complete"
    50	paused_at: null
    51	---
    52	```
    53	
    54	### Field reference
    55	
    56	| Field | Type | When populated | Purpose |
    57	|---|---|---|---|
    58	| `gsd_state_version` | string (`'1.0'`) | Always | Schema version; written on first `state.*` call by `syncStateFrontmatter`. |
    59	| `milestone` | string (e.g. `v2.0`) | When a milestone is configured | Current milestone version, read from the project's config. |
    60	| `milestone_name` | string | When a milestone is configured | Human-readable milestone label (e.g. `Code Quality`). |
    61	| `status` | string | Always | Current lifecycle stage. Normalised by `normalizeStateStatus()` — see [status values](#status-values). |
    62	| `active_phase` | string (e.g. `"4.5"`) | An orchestrator command is in flight on this phase | The phase number currently being processed. Set to `null` when between phases. |
    63	| `next_action` | string | Idle, with a recommended command | The slash command to run next: `discuss-phase`, `plan-phase`, `execute-phase`, or `verify-phase`. Set to `null` when an orchestrator is in flight or no recommendation is available. |
    64	| `next_phases` | YAML flow array (e.g. `["4.5"]`) | Goes with `next_action` | The phase ID(s) the `next_action` applies to (typically 1–2 entries). Set to `null` under the same conditions as `next_action`. |
    65	| `progress.total_phases` | integer | When phase data is available | Total number of phases in the current milestone, derived from ROADMAP.md and the phases directory. |
    66	| `progress.completed_phases` | integer | When phase data is available | Number of phases that have all plan summaries on disk (i.e. every plan completed). |
    67	| `progress.total_plans` | integer | When plan files exist | Sum of all plan files across phases in the current milestone. |
    68	| `progress.completed_plans` | integer | When summary files exist | Sum of completed plan summaries (one SUMMARY.md per executed plan). |
    69	| `progress.percent` | integer 0–100 | When progress data is available | Milestone progress in the **phase dimension** (`min(completed_plans/total_plans, completed_phases/total_phases)`). The status-line progress bar is only rendered when this field is present — its absence suppresses the bar. |
    70	| `current_phase` | string | When a phase is executing | Phase number extracted from the body `Current Phase:` field. |
    71	| `current_phase_name` | string | When a phase has a name | Phase name extracted from the body `Current Phase Name:` field. |
    72	| `current_plan` | string | When a plan is in progress | Plan number extracted from the body `Current Plan:` field. |
    73	| `last_updated` | ISO-8601 timestamp | Always (on write) | Timestamp of the last `syncStateFrontmatter` call; written by `realClock.nowIso()`. |
    74	| `last_activity` | string | When set in body | Date of the last activity, extracted from the body `Last Activity:` field. |
    75	| `stopped_at` | string | When a stop point was recorded | Description of the last completed action; scoped to the `## Session` body section to avoid matching archive prose. |
    76	| `paused_at` | string | When the project is paused | Freeform description of the pause point; absent or `null` when not paused. |
    77	
    78	### Status values
    79	
    80	`normalizeStateStatus()` in `gsd-core/bin/lib/state-document.cjs` maps raw body text to these canonical values:
    81	
    82	| Canonical value | Matched text (case-insensitive) |
    83	|---|---|
    84	| `discussing` | contains `discussing` |
    85	| `planning` | contains `planning` or `ready to plan` |
    86	| `executing` | contains `executing`, `in progress`, or `ready to execute` |
    87	| `verifying` | contains `verif` |
    88	| `completed` | contains `complete` or `done` |
    89	| `paused` | contains `paused` or `stopped`, or `paused_at` is present |
    90	| `unknown` | none of the above |
    91	
    92	When an orchestrator command is in flight, the convention (issue #2833) is to write the lifecycle stage directly to `status`:
    93	
    94	| Command | `status` while in flight |
    95	|---|---|
    96	| `/gsd-discuss-phase` | `discussing` |
    97	| `/gsd-plan-phase` | `planning` |
    98	| `/gsd-execute-phase` | `executing` |
    99	| `/gsd-verify-work` | `verifying` |
   100	
   101	---
   102	
   103	## Status-line rendering scenes
   104	
   105	`formatGsdState()` in `hooks/gsd-statusline.js` reads the parsed frontmatter and emits the **first matching scene**. If no new lifecycle fields apply, rendering falls through to the original format byte-for-byte unchanged from v1.38.x.
   106	
   107	| Scene | Trigger | Display example |
   108	|---|---|---|
   109	| **1. Phase active** | `active_phase` is populated | `v2.0 [██░░░░░░░░] 20% · Phase 4.5 executing` |
   110	| **2. Idle, next recommended** | `active_phase` is null AND both `next_action` and `next_phases` are populated | `v2.0 [██░░░░░░░░] 20% · next execute-phase 4.5` |
   111	| **3. Milestone complete** | `percent` is `100` OR `completed_phases == total_phases` | `v2.0 [██████████] 100% · milestone complete` |
   112	| **4. Default fallback** | None of the above match | `v1.9 Code Quality · executing · ph 1/5` (existing format) |
   113	
   114	**Scene priority:** when both `active_phase` and `next_action` are populated, Scene 1 wins — an orchestrator is in flight, so a "next recommendation" would be misleading. This priority is enforced by check order in `formatGsdState()` and covered by the `"scene priority"` suite in `tests/gsd-statusline.test.cjs`.
   115	
   116	The progress bar (`[██░░░░░░░░] 20%`) is appended to the milestone segment only when `progress.percent` is present in frontmatter; absent means no bar.
   117	
   118	---
   119	
   120	## Frontmatter parsing constraints
   121	
   122	The status-line hook uses regex-based parsing (no full YAML library), so the following constraints apply. They are tested in `tests/gsd-statusline.test.cjs`.
   123	
   124	1. **Frontmatter must start at the very first character of the file.** Anything — including comments — above the opening `---` invalidates the match. The opening `---` line must be exactly that, with no trailing spaces.
   125	
   126	2. **Comments inside nested blocks are not supported.** The `progress:` block parser requires the next line to be `[ \t]+\w+:`. Inserting a `# comment` between `progress:` and its first key breaks the match and the bar disappears. Any documentation belongs in the `STATE.md` body, not inside frontmatter blocks.
   127	
   128	3. **`next_phases` primary format is single-line flow.** The parser first tries `next_phases: ["4.5", "4.6"]`. Block sequences (`- 4.5\n- 4.6`) are also parsed but are less reliable for status-line rendering. Prefer single-line flow for `next_phases` to keep the regex-based parser predictable. If many candidate phases need recording for documentation purposes, store them in the `STATE.md` body.
   129	
   130	If a future change replaces the regex parser with a full YAML library, these constraints can be relaxed and the tests updated accordingly.
   131	
   132	---
   133	
   134	## Markdown body sections
   135	
   136	The body (everything after the closing `---`) follows the template in `gsd-core/templates/state.md`. The standard sections are:
   137	
   138	### Project Reference
   139	
   140	Points to `.planning/PROJECT.md`. Contains:
   141	- **Core value** — the one-liner from `PROJECT.md`'s Core Value section.
   142	- **Current focus** — which phase is active.
   143	
   144	### Current Position
   145	
   146	Where the project stands right now:
   147	
   148	| Field | Format |
   149	|---|---|
   150	| `Phase:` | `X of Y (Phase name)` |
   151	| `Plan:` | `A of B in current phase` |
   152	| `Status:` | Free text, e.g. `Ready to execute`, `Executing Phase 4`, `Phase complete — ready for verification` |
   153	| `Last activity:` | ISO date (`YYYY-MM-DD`) when handler-written; narrative prose when executor-authored |
   154	| `Progress:` | Visual bar, e.g. `[████░░░░░░] 40%` |
   155	
   156	The `Status:` and `Last activity:` fields in this section are updated by GSD handlers when the existing value is a known template default (Knuth invariant: executor-authored values are preserved). The full list of known handler defaults is in `KNOWN_TEMPLATE_DEFAULTS` inside `gsd-core/bin/lib/state-document.cjs`.
   157	
   158	### Performance Metrics
   159	
   160	Execution velocity tracking:
   161	- Total plans completed, average duration per plan.
   162	- Per-phase breakdown table (`Phase | Plans | Total | Avg/Plan`).
   163	- Recent trend: Improving / Stable / Degrading.
   164	
   165	Updated after each plan completion.
   166	
   167	### Accumulated Context
   168	
   169	**Decisions** — a summary of recent decisions affecting current work (full log lives in `PROJECT.md`). Added via `gsd-tools state add-decision`.
   170	
   171	**Pending Todos** — count and reference to `.planning/todos/pending/`. Captured via `/gsd-capture`.
   172	
   173	**Blockers/Concerns** — issues affecting future work, prefixed with the originating phase. Added via `gsd-tools state add-blocker`; resolved via `gsd-tools state resolve-blocker`.
   174	
   175	### Session Continuity
   176	
   177	Enables instant session resumption:
   178	- `Last session:` — ISO-8601 timestamp of the last session.
   179	- `Stopped at:` — description of the last completed action.
   180	- `Resume file:` — path to a `.continue-here*.md` file if one exists, otherwise `None`.

exec
/bin/zsh -lc "nl -ba '/Users/noelsaw/Documents/GH Repos/gsd-core/docs/reference/context-md.md' | sed -n '1,180p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-21302-28772
 succeeded in 0ms:
     1	# CONTEXT.md schema reference
     2	
     3	A per-phase `CONTEXT.md` is GSD Core's carrier for implementation decisions captured during `/gsd:discuss-phase`. It is the primary upstream input for both the research and planning agents. This page documents its structure. See [docs index](../README.md).
     4	
     5	---
     6	
     7	## Overview
     8	
     9	Every phase that has been through the discuss workflow produces one `CONTEXT.md` at:
    10	
    11	```
    12	.planning/phases/<NN>-<slug>/<NN>-CONTEXT.md
    13	```
    14	
    15	For example: `.planning/phases/03-post-feed/03-CONTEXT.md`.
    16	
    17	The file is produced by `write_context` in `gsd-core/workflows/discuss-phase.md` (or its PRD / ADR ingest express paths). It is never edited by hand during normal operation — the discuss-phase workflow writes it and downstream agents read it as a sealed source of truth.
    18	
    19	---
    20	
    21	## Frontmatter
    22	
    23	`CONTEXT.md` carries no YAML frontmatter. Metadata is inline at the top of the body:
    24	
    25	```markdown
    26	# Phase [X]: [Name] - Context
    27	
    28	**Gathered:** [ISO date]
    29	**Status:** Ready for planning
    30	```
    31	
    32	The `Status` field is always `Ready for planning` when the file is first written. It is not updated after creation.
    33	
    34	---
    35	
    36	## Block structure
    37	
    38	The body is divided into named XML-style blocks. The blocks appear in a fixed order and are read by downstream agents by block name, not by line number.
    39	
    40	| Block | Purpose | Populated by | Consumed by |
    41	|---|---|---|---|
    42	| `<domain>` | States the phase boundary — what this phase delivers and what is explicitly out of scope. Anchors the scope guardrail throughout planning and execution. | `discuss-phase` (from ROADMAP.md phase goal) | `gsd-planner`, `gsd-plan-checker` (scope compliance) |
    43	| `<spec_lock>` | Present only when a `*-SPEC.md` was found by the `check_spec` step. Lists locked requirement counts and scope boundaries; agents are directed to read `SPEC.md` directly for full requirements. | `discuss-phase` (conditional) | `gsd-planner` (reads SPEC.md rather than re-reading requirements here) |
    44	| `<decisions>` | Implementation decisions captured from the discussion, keyed with `D-NN` identifiers. Categories emerge from what was actually discussed rather than a fixed taxonomy. Includes a `Claude's Discretion` sub-section for areas the user delegated. | `discuss-phase` (interactive discussion) | `gsd-planner` (locked decisions must be implemented), `gsd-plan-checker` (Dimension 7 compliance) |
    45	| `<canonical_refs>` | Full relative paths to every spec, ADR, feature doc, or design doc relevant to this phase. Mandatory — every CONTEXT.md must have this section. Agents must read listed files before planning or implementing. | `discuss-phase` (accumulated from ROADMAP.md refs + user references during discussion + codebase scout) | `gsd-phase-researcher`, `gsd-planner` |
    46	| `<code_context>` | Reusable assets, established patterns, and integration points discovered during the `scout_codebase` step. Guides agents towards existing code rather than re-implementing. | `discuss-phase` (codebase scout) | `gsd-planner`, `gsd-phase-researcher` |
    47	| `<specifics>` | Concrete "I want it like X" references, product comparisons, or particular examples captured verbatim during discussion. | `discuss-phase` (freeform user input) | `gsd-planner` |
    48	| `<deferred>` | Ideas that arose in discussion but belong in other phases. Preserved so they are not lost. Includes a `Reviewed Todos` sub-section when todos were reviewed but not folded into scope. | `discuss-phase` (scope-creep redirect) | Not consumed by automated agents; human reference only |
    49	
    50	---
    51	
    52	## Decision identifier format
    53	
    54	Every decision in `<decisions>` carries a sequential `D-NN` identifier:
    55	
    56	```markdown
    57	### Layout style
    58	- **D-01:** Card-based layout, not timeline or list
    59	- **D-02:** Each card shows: author avatar, name, timestamp, full post content, reaction counts
    60	```
    61	
    62	Identifiers are scoped to the phase. `D-01` in Phase 3 is unrelated to `D-01` in Phase 7. The plan-checker (Dimension 7) verifies that every `D-NN` is addressed by at least one task action in the generated plans.
    63	
    64	---
    65	
    66	## Canonical references
    67	
    68	The `<canonical_refs>` block is **mandatory**. Agents that find it absent treat the CONTEXT.md as incomplete and surface a warning. Entries are grouped by topic and carry a full relative path plus a brief statement of what the file decides or defines:
    69	
    70	```markdown
    71	<canonical_refs>
    72	## Canonical References
    73	
    74	**Downstream agents MUST read these before planning or implementing.**
    75	
    76	### Feed display
    77	- `docs/features/social-feed.md` — Feed requirements, post card fields, engagement display rules
    78	- `docs/decisions/adr-012-infinite-scroll.md` — Scroll strategy decision, virtualisation requirements
    79	
    80	### Empty states
    81	- `docs/design/empty-states.md` — Empty state patterns, illustration guidelines
    82	
    83	</canonical_refs>
    84	```
    85	
    86	When a project has no external specs, the section states this explicitly:
    87	
    88	```
    89	No external specs — requirements fully captured in decisions above
    90	```
    91	
    92	Inline mentions like "see ADR-019" scattered in `<decisions>` are insufficient; agents need the full path in the dedicated section.
    93	
    94	---
    95	
    96	## Decision Coverage Gate relationship
    97	
    98	The plan-checker's **Dimension 7: Context Compliance** enforces a coverage gate after planning:
    99	
   100	1. Every `D-NN` identifier in `<decisions>` must appear in at least one plan task's `<action>` or rationale.
   101	2. No task may implement anything listed in `<deferred>` (scope creep).
   102	3. `Claude's Discretion` areas are exempted from this check — the planner may choose freely.
   103	
   104	A CONTEXT.md where decisions survive into plans is considered compliant. A CONTEXT.md whose decisions are silently dropped or partially delivered triggers **Dimension 7b: Scope Reduction Detection**, which is always a BLOCKER.
   105	
   106	---
   107	
   108	## SPEC.md integration
   109	
   110	When `/gsd:spec-phase` has been run before discussing a phase, the `check_spec` step finds the `*-SPEC.md` file and activates `<spec_lock>`:
   111	
   112	```markdown
   113	<spec_lock>
   114	## Requirements (locked via SPEC.md)
   115	
   116	**12 requirements are locked.** See `03-SPEC.md` for full requirements, boundaries, and acceptance criteria.
   117	
   118	Downstream agents MUST read `03-SPEC.md` before planning or implementing. Requirements are not duplicated here.
   119	
   120	**In scope (from SPEC.md):** [copied from SPEC.md Boundaries]
   121	**Out of scope (from SPEC.md):** [copied from SPEC.md Boundaries]
   122	
   123	</spec_lock>
   124	```
   125	
   126	When `<spec_lock>` is present, `<decisions>` contains only implementation decisions from the discussion — the "how", not the "what". Requirements are not duplicated between the two files.
   127	
   128	---
   129	
   130	## Footer
   131	
   132	Every CONTEXT.md ends with an identity footer:
   133	
   134	```markdown
   135	---
   136	
   137	*Phase: XX-name*
   138	*Context gathered: [date]*
   139	```
   140	
   141	---
   142	
   143	## Related
   144	
   145	- [PLAN.md schema](plan-md.md)
   146	- [Planning artifacts](planning-artifacts.md)
   147	- [Discuss modes](../workflow-discuss-mode.md)
   148	- [docs index](../README.md)

exec
/bin/zsh -lc "nl -ba '/Users/noelsaw/Documents/GH Repos/gsd-core/docs/reference/planning-artifacts.md' | sed -n '1,220p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-21302-28772
 succeeded in 0ms:
     1	# Planning artifacts reference
     2	
     3	The `.planning/` directory is GSD Core's shared memory for a project. Every workflow reads from it, writes to it, and leaves an auditable trail of decisions. This page maps every file, its purpose, and which command produces or consumes it. See [docs index](../README.md).
     4	
     5	---
     6	
     7	## Directory layout
     8	
     9	```
    10	.planning/
    11	├── PROJECT.md                          # Project identity and core value
    12	├── ROADMAP.md                          # Milestone + phase listing with goals
    13	├── REQUIREMENTS.md                     # Numbered acceptance criteria
    14	├── STATE.md                            # Living position tracker
    15	├── config.json                         # Workflow and model configuration
    16	├── MILESTONES.md                       # Milestone archive (optional)
    17	├── BACKLOG.md                          # Deferred and future work (optional)
    18	├── LEARNINGS.md                        # Accumulated cross-phase learnings (optional)
    19	├── DECISIONS-INDEX.md                  # Rolling summary of prior decisions (optional)
    20	├── METHODOLOGY.md                      # Reusable interpretive frameworks (optional)
    21	├── HANDOFF.json                        # Machine-readable pause state (transient)
    22	├── codebase/                           # Codebase maps (optional)
    23	│   ├── architecture.md
    24	│   ├── stack.md
    25	│   └── ...
    26	├── intel/                              # Queryable symbol index (optional, intel.enabled)
    27	│   └── API-SURFACE.md
    28	└── phases/
    29	    └── <NN>-<slug>/                    # One directory per phase
    30	        ├── <NN>-CONTEXT.md             # Implementation decisions (discuss-phase)
    31	        ├── <NN>-DISCUSSION-LOG.md      # Human-readable discussion audit (discuss-phase)
    32	        ├── <NN>-RESEARCH.md            # Technical research findings (plan-phase)
    33	        ├── <NN>-VALIDATION.md          # Nyquist test-coverage strategy (plan-phase)
    34	        ├── <NN>-PATTERNS.md            # Codebase analog map (plan-phase, optional)
    35	        ├── <NN>-<PP>-PLAN.md           # Executable plan (plan-phase, one per plan)
    36	        ├── <NN>-<PP>-SUMMARY.md        # Execution record (execute-phase, one per plan)
    37	        ├── <NN>-VERIFICATION.md        # Phase goal verification report (verify-phase)
    38	        ├── <NN>-UAT.md                 # Persistent UAT session state (execute-phase)
    39	        └── .continue-here.md           # Resume instructions after pause (pause-work)
    40	```
    41	
    42	---
    43	
    44	## Root-level artifacts
    45	
    46	### `PROJECT.md`
    47	
    48	| | |
    49	|---|---|
    50	| **Purpose** | Canonical project identity: what it is, who it is for, core value, requirements, constraints, and key decisions. Updated throughout the project lifecycle as the product evolves. |
    51	| **Produced by** | `/gsd-new-project` (initial creation); updated by `/gsd-complete-milestone` as decisions are validated. |
    52	| **Consumed by** | All planning workflows; `gsd-phase-researcher`, `gsd-planner` (context); `discuss-phase` (prior decisions); `gsd-plan-checker` (project constraints). |
    53	
    54	Includes an optional `## Business Context` section (Customer, Revenue model, Success metric, Strategy notes) for monetized or customer-facing projects — four one-line fields that connect business outcomes to requirement prioritization. It is deleted for internal tools, experiments, or meta workspaces, and reviewed at each milestone by `/gsd-complete-milestone` when present.
    55	
    56	### `ROADMAP.md`
    57	
    58	| | |
    59	|---|---|
    60	| **Purpose** | Milestone and phase listing with goals, requirement IDs, success criteria, and canonical references per phase. The single source of truth for what the project is building and in what order. |
    61	| **Produced by** | `/gsd-new-project` (initial creation); updated by `/gsd-phase --insert` and `/gsd-complete-milestone`. |
    62	| **Consumed by** | `/gsd-discuss-phase`, `/gsd-plan-phase`, `/gsd-execute-phase`; all orchestration commands that need phase information; `gsd-planner`, `gsd-plan-checker`, `gsd-phase-researcher`. |
    63	
    64	### `REQUIREMENTS.md`
    65	
    66	| | |
    67	|---|---|
    68	| **Purpose** | Numbered, checkable acceptance criteria for the project. Each requirement carries an ID (e.g., `AUTH-01`) that maps to roadmap phases. Marks requirements complete as phases are executed. |
    69	| **Produced by** | `/gsd-new-project` (initial creation); requirements marked complete by `execute-phase`. |
    70	| **Consumed by** | `gsd-planner` (plans must address all phase requirement IDs); `gsd-plan-checker` Dimension 1 (requirement coverage); `discuss-phase` (prior requirements). |
    71	
    72	### `STATE.md`
    73	
    74	| | |
    75	|---|---|
    76	| **Purpose** | Living position tracker — current phase and plan, progress metrics, accumulated decisions, session continuity notes. Read at the start of every workflow run. Updated after every significant action. |
    77	| **Produced by** | `/gsd-new-project` (initial creation); updated continuously by all phase workflows, `/gsd-pause-work`, `/gsd-resume-work`. |
    78	| **Consumed by** | All orchestration workflows; `/gsd-progress`; ad-hoc task execution via `/gsd-quick`; `gsd-planner` and `gsd-phase-researcher` (project decisions). |
    79	
    80	See [STATE.md schema](state-md.md) for the full field reference.
    81	
    82	### `config.json`
    83	
    84	| | |
    85	|---|---|
    86	| **Purpose** | Workflow configuration: model profiles, research and plan-checker toggles, git branching strategy, Nyquist validation, parallelisation settings, and per-agent model overrides. |
    87	| **Produced by** | `/gsd-new-project` (initial creation); `/gsd-settings` (interactive editing). |
    88	| **Consumed by** | Every workflow and subagent — read at init time via `gsd-tools query config-get`. |
    89	
    90	See [CONFIGURATION](../CONFIGURATION.md) for the complete schema.
    91	
    92	### `MILESTONES.md` (optional)
    93	
    94	| | |
    95	|---|---|
    96	| **Purpose** | Historical record of completed milestones. Populated as each milestone is closed; provides an archival snapshot of what shipped and when. |
    97	| **Produced by** | `/gsd-complete-milestone`. |
    98	| **Consumed by** | `/gsd-audit-milestone`; human review. |
    99	
   100	### `DECISIONS-INDEX.md` (optional)
   101	
   102	| | |
   103	|---|---|
   104	| **Purpose** | Bounded rolling summary of decisions captured in prior-phase CONTEXT.md files. When present, `discuss-phase` reads this single file instead of reading up to three prior CONTEXT.md files individually, saving context budget. |
   105	| **Produced by** | Generated when the number of prior phases exceeds the rolling-read threshold. |
   106	| **Consumed by** | `discuss-phase` (`load_prior_context` step). |
   107	
   108	### `HANDOFF.json` (transient)
   109	
   110	| | |
   111	|---|---|
   112	| **Purpose** | Machine-readable pause state written when work is interrupted. Contains the resume point, in-progress context, and continuation instructions. Consumed exactly once — on resume. |
   113	| **Produced by** | `/gsd-pause-work`. |
   114	| **Consumed by** | `/gsd-resume-work`. |
   115	
   116	---
   117	
   118	## Per-phase artifacts
   119	
   120	All per-phase files live under `.planning/phases/<NN>-<slug>/` where `NN` is the zero-padded phase number and `slug` is the hyphenated phase name.
   121	
   122	### `<NN>-CONTEXT.md`
   123	
   124	| | |
   125	|---|---|
   126	| **Purpose** | Implementation decisions captured before planning begins. Contains the phase boundary (`<domain>`), locked decisions with `D-NN` identifiers (`<decisions>`), canonical document references (`<canonical_refs>`), existing code insights (`<code_context>`), specific inspirations (`<specifics>`), and deferred ideas (`<deferred>`). |
   127	| **Produced by** | `/gsd-discuss-phase` (interactive discussion or PRD/ADR express paths). |
   128	| **Consumed by** | `gsd-phase-researcher` (what to investigate); `gsd-planner` (locked decisions); `gsd-plan-checker` Dimension 7 (context compliance). |
   129	
   130	See [CONTEXT.md schema](context-md.md) for the full field reference.
   131	
   132	### `<NN>-DISCUSSION-LOG.md`
   133	
   134	| | |
   135	|---|---|
   136	| **Purpose** | Human-readable audit trail of the discuss-phase session: areas discussed, options presented, selections made, deferred ideas, and items left to Claude's discretion. Not consumed by automated workflows. |
   137	| **Produced by** | `/gsd-discuss-phase` (`git_commit` step). |
   138	| **Consumed by** | Human review; retrospectives. |
   139	
   140	### `<NN>-RESEARCH.md`
   141	
   142	| | |
   143	|---|---|
   144	| **Purpose** | Technical research findings produced before planning. Answers "What do I need to know to plan this phase well?" — covers domain analysis, patterns, risks, an Architectural Responsibility Map, and a Validation Architecture section (used by the Nyquist gate). |
   145	| **Produced by** | `/gsd-plan-phase` via `gsd-phase-researcher` agent. |
   146	| **Consumed by** | `gsd-planner` (planning inputs); `gsd-plan-checker` Dimension 7c (tier compliance), Dimension 8 (Nyquist), Dimension 11 (research resolution); `gsd-pattern-mapper` (file list source). |
   147	
   148	### `<NN>-VALIDATION.md`
   149	
   150	| | |
   151	|---|---|
   152	| **Purpose** | Nyquist-inspired validation strategy derived from the `## Validation Architecture` section of RESEARCH.md. Specifies automated test coverage requirements that plans must honour. |
   153	| **Produced by** | `/gsd-plan-phase` (Step 5.5, when `workflow.nyquist_validation` is enabled and RESEARCH.md contains a Validation Architecture section). |
   154	| **Consumed by** | `gsd-plan-checker` Dimension 8 (Check 8e gate — must exist before Nyquist checks proceed); `gsd-verifier`. |
   155	
   156	### `<NN>-PATTERNS.md`
   157	
   158	| | |
   159	|---|---|
   160	| **Purpose** | Codebase analog map produced by `gsd-pattern-mapper`. For each file to be created or modified this phase, identifies the closest existing analog, classifies the file's role and data flow, and extracts concrete code excerpts. Guides the planner towards consistent patterns. |
   161	| **Produced by** | `/gsd-plan-phase` via `gsd-pattern-mapper` agent (optional; skipped if `workflow.pattern_mapper: false`). |
   162	| **Consumed by** | `gsd-planner` (pattern guidance); `gsd-plan-checker` Dimension 12 (pattern compliance). |
   163	
   164	### `<NN>-<PP>-PLAN.md`
   165	
   166	| | |
   167	|---|---|
   168	| **Purpose** | Executable plan for a single unit of work within the phase. Contains YAML frontmatter (wave, dependencies, files, requirements, `must_haves`), an objective, context references, XML-structured tasks with `<read_first>`, `<action>`, `<verify>`, and `<acceptance_criteria>` fields, and verification criteria. |
   169	| **Produced by** | `/gsd-plan-phase` via `gsd-planner` agent. One file per plan — e.g., `03-02-PLAN.md` is Phase 3, Plan 2. |
   170	| **Consumed by** | `/gsd-execute-phase` (executor agent reads plan and runs tasks); `gsd-plan-checker` (pre-execution quality review); `gsd-verifier` (reads `must_haves` for post-execution verification). |
   171	
   172	See [PLAN.md schema](plan-md.md) for the full field reference.
   173	
   174	### `<NN>-<PP>-SUMMARY.md`
   175	
   176	| | |
   177	|---|---|
   178	| **Purpose** | Execution record written after a plan completes. Documents what was built, deviations from the plan, a self-check against acceptance criteria, and the dependency graph for the phase. |
   179	| **Produced by** | `execute-phase` executor agent (written at the end of each plan's execution). |
   180	| **Consumed by** | `/gsd-progress` (phase status); `gsd-planner` (when a subsequent plan has a genuine dependency on prior plan output); `milestone-summary`. |
   181	
   182	### `<NN>-VERIFICATION.md`
   183	
   184	| | |
   185	|---|---|
   186	| **Purpose** | Phase goal verification report. Checks `must_haves.truths`, `must_haves.artifacts`, and `must_haves.key_links` from all plans against the actual codebase after execution. Records `status: passed \| gaps_found \| human_needed`. A truth whose correctness depends on runtime behaviour — a state transition or a cancellation/cleanup/ordering invariant — is marked `⚠️ PRESENT_BEHAVIOR_UNVERIFIED` (not `VERIFIED`) when no test exercises it: it is excluded from `score`, counted in the `behavior_unverified` frontmatter field, and routed to `human_needed`, so a behaviour-dependent gap can no longer count toward a clean N/N. |
   187	| **Produced by** | `/gsd-verify-work` (or the verify step within `/gsd-execute-phase`). |
   188	| **Consumed by** | `plan-phase` closed-phase gate (a `status: passed` VERIFICATION.md marks the phase `Complete` and blocks replanning without `--force`); `/gsd-progress`; human review. |
   189	
   190	### `<NN>-UAT.md`
   191	
   192	| | |
   193	|---|---|
   194	| **Purpose** | Persistent UAT session tracking. Records each test case, expected observable behaviour, result, and developer response across a live UAT session. Carries YAML frontmatter (`status`, `phase`, `source`, timestamps). |
   195	| **Produced by** | `/gsd-audit-uat` (interactive UAT session). |
   196	| **Consumed by** | `/gsd-audit-uat` (resume a previous UAT session). |
   197	
   198	### `.continue-here.md`
   199	
   200	| | |
   201	|---|---|
   202	| **Purpose** | Human-readable resume instructions written when work on a phase is paused. Contains context for resuming agents: critical anti-patterns, blocking issues, required reading, and the exact command to resume. |
   203	| **Produced by** | `/gsd-pause-work`. |
   204	| **Consumed by** | Any workflow that starts on a phase — `discuss-phase` and `plan-phase` both check for this file at entry and require the agent to demonstrate understanding of any `blocking` anti-patterns before proceeding. |
   205	
   206	### `.planning/async-jobs/<job>.json`
   207	
   208	**Purpose**: Durable manifest for an async external job dispatched during Execute (long-running compute, e.g. HPC solver/training jobs). Its presence makes an Execute step's SUMMARY-absent state a *legal* `external_job_waiting` deferral rather than an illegal partial-plan state.
   209	
   210	**Stability contract (Hyrum's Law).** This schema is a depended-upon interface across the core loop and every scheduler backend. The core loop consumes only the named fields below and ignores any others; producers MUST write these fields and MAY add their own. The `version` field is the escape hatch for evolving the schema without breaking consumers. Coordinate any change with both the core half (#1165) and the producer capability (#1164).
   211	
   212	**Produced by**: a scheduler-adapter Capability at the `execute:wave:post` loop extension point (the capability half — tracked in #1164, default-off). Core never writes this file.
   213	
   214	**Consumed by**: `execute-phase` safe-resume, `resume-project`, and `pause-work` (the core half — #1165).
   215	
   216	| Field | Type | Meaning |
   217	|---|---|---|
   218	| `version` | string | Manifest schema version (`"1.0"`). |
   219	| `job_id` | string | Backend-assigned job identifier. |
   220	| `plan_id` | string | `<phase>-<plan>` this job belongs to — the key tying the job to its Execute step. |

exec
/bin/zsh -lc "nl -ba '/Users/noelsaw/Documents/GH Repos/gsd-core/docs/explanation/multi-agent-orchestration.md' | sed -n '1,220p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-21302-28772
 succeeded in 0ms:
     1	# Multi-agent orchestration in GSD Core
     2	
     3	> **Explanation** — This document describes *why* GSD Core is designed around
     4	> multi-agent orchestration and *how the pieces fit together*. It is not a
     5	> step-by-step guide. For configuration, see
     6	> [Configure model profiles](../how-to/configure-model-profiles.md) and the
     7	> [Configuration reference](../CONFIGURATION.md). For the full agent roster,
     8	> see [Inventory](../INVENTORY.md).
     9	
    10	---
    11	
    12	## The problem this design solves
    13	
    14	AI coding agents degrade. Not because the model gets worse, but because the
    15	*context window fills up*. As a conversation grows, earlier decisions and code
    16	get pushed out or diluted by the noise of intermediate steps. By the time an
    17	agent writes the fifth file in a complex task, it may have already forgotten
    18	the constraint stated in the first message. This is sometimes called *context
    19	rot*.
    20	
    21	GSD Core's multi-agent design is a direct response to that problem. Instead of
    22	one long-running agent carrying the whole session, a thin orchestrator spawns
    23	short-lived specialised agents, each with a **fresh 200 K-token context window**
    24	and *only the artifacts it needs* to do its specific job. The orchestrator
    25	never does heavy lifting itself; it loads context, spawns the right agent,
    26	collects the result, and updates shared state in `.planning/`.
    27	
    28	---
    29	
    30	## The orchestrator → agent pattern
    31	
    32	Every workflow in `gsd-core/workflows/` follows the same shape:
    33	
    34	```text
    35	Orchestrator (workflow .md file)
    36	    │
    37	    ├── Load context
    38	    │   gsd-tools.cjs init <workflow> <phase>
    39	    │   → JSON: project info, config, state, phase details
    40	    │
    41	    ├── Resolve model
    42	    │   gsd-tools.cjs resolve-model <agent-name>
    43	    │   → opus | sonnet | haiku | inherit
    44	    │
    45	    ├── Spawn specialised agent (Task/SubAgent call)
    46	    │   ├── Agent definition (agents/*.md)
    47	    │   ├── Context payload (init JSON)
    48	    │   ├── Model assignment
    49	    │   └── Tool permissions
    50	    │
    51	    ├── Collect result
    52	    │
    53	    └── Update state
    54	        gsd-tools.cjs state update / state patch / state advance-plan
    55	```
    56	
    57	The orchestrator is deliberately thin. It does not reason about the domain,
    58	does not write code, and does not interpret results beyond routing them to the
    59	next step. That boundary keeps each layer's responsibility clear and prevents
    60	the orchestrator's context from accumulating domain noise.
    61	
    62	### The agent roster
    63	
    64	GSD Core's agents fall into functional categories that map onto the
    65	research → plan → execute → verify pipeline:
    66	
    67	| Category | Agents | Typical parallelism |
    68	|---|---|---|
    69	| Researchers | `gsd-project-researcher`, `gsd-phase-researcher`, `gsd-ui-researcher`, `gsd-advisor-researcher` | 4 parallel (stack, features, architecture, pitfalls) |
    70	| Synthesisers | `gsd-research-synthesizer` | Sequential, after researchers complete |
    71	| Planners | `gsd-planner`, `gsd-roadmapper` | Sequential |
    72	| Checkers | `gsd-plan-checker`, `gsd-integration-checker`, `gsd-ui-checker`, `gsd-nyquist-auditor` | Sequential, up to 3 revision iterations |
    73	| Executors | `gsd-executor` | Parallel within a wave, sequential across waves |
    74	| Verifiers | `gsd-verifier` | Sequential, after all executors complete |
    75	| Mappers | `gsd-codebase-mapper` | 4 parallel sub-probes |
    76	| Auditors | `gsd-ui-auditor`, `gsd-security-auditor` | Sequential |
    77	
    78	Each agent definition (in `agents/*.md`) declares its allowed tool access,
    79	purpose, and colour for terminal output. An agent that only needs to read files
    80	and write a single output document gets exactly those permissions — no Bash
    81	execution, no access to broader state. That constraint is intentional: it
    82	keeps the blast radius small if an agent behaves unexpectedly.
    83	
    84	For the complete agent roster, see [Inventory](../INVENTORY.md#agents).
    85	
    86	---
    87	
    88	## Wave-based parallel execution
    89	
    90	The most visible expression of multi-agent design is how `/gsd-execute-phase`
    91	handles a set of plans that may depend on one another.
    92	
    93	Before spawning any executor, the orchestrator performs a **wave analysis**:
    94	it reads the dependency declarations in each `PLAN.md` file and groups plans
    95	into waves. Plans with no declared dependencies form Wave 1 and run in
    96	parallel. Plans that depend on Wave 1 form Wave 2, and so on.
    97	
    98	```text
    99	Plan 01 (no deps)        ─┐
   100	Plan 02 (no deps)        ─┤─── Wave 1  (parallel)
   101	Plan 03 (depends: 01)    ─┤─── Wave 2  (waits for Wave 1)
   102	Plan 04 (depends: 02)    ─┘
   103	Plan 05 (depends: 03, 04) ─── Wave 3  (waits for Wave 2)
   104	```
   105	
   106	Each executor within a wave:
   107	
   108	- receives a fresh context window (200 K tokens, or up to 1 M on capable models)
   109	- receives the specific `PLAN.md` it is responsible for
   110	- receives project context (`PROJECT.md`, `STATE.md`)
   111	- receives phase context (`CONTEXT.md`, `RESEARCH.md` if available)
   112	- produces atomic git commits on completion
   113	- writes a `SUMMARY.md` describing what was built
   114	
   115	After all executors in a wave finish, the orchestrator runs the pre-commit
   116	hook once for the wave as a whole. Executors commit with `--no-verify` to
   117	prevent build-lock contention (for example, Cargo lock fights in Rust
   118	projects) when multiple agents commit in parallel. The hook therefore runs
   119	once per wave rather than once per commit.
   120	
   121	### Parallel commit safety
   122	
   123	Two mechanisms prevent write conflicts when multiple executors run
   124	simultaneously:
   125	
   126	1. **Atomic lock on `STATE.md`** — Every write to `STATE.md` uses a
   127	   lockfile (`STATE.md.lock`) with `O_EXCL` atomic creation. This prevents
   128	   the read-modify-write race where two agents each read the file, modify
   129	   different fields, and the later writer overwrites the earlier one's
   130	   changes. Stale locks (older than 10 seconds) are automatically cleared.
   131	
   132	2. **Per-wave hook run** — Rather than each executor running pre-commit hooks
   133	   independently (which can cause file-level contention on shared build
   134	   artefacts), the orchestrator runs `git hook run pre-commit` once after
   135	   every wave completes.
   136	
   137	---
   138	
   139	## Adaptive context enrichment for large-window models
   140	
   141	Standard 200 K context windows are enough for an executor to implement a
   142	single focused plan. When the configured `context_window` is 500 K tokens or
   143	larger (for example, when using Opus 4.6 or Sonnet 4.6 in 1 M-class mode),
   144	the orchestrator automatically enriches subagent prompts with additional
   145	context that would not fit in a standard window:
   146	
   147	- **Executor agents** receive prior-wave `SUMMARY.md` files and the phase
   148	  `CONTEXT.md`/`RESEARCH.md`, giving them cross-plan awareness within the
   149	  phase
   150	- **Verifier agents** receive all `PLAN.md`, `SUMMARY.md`, and `CONTEXT.md`
   151	  files plus `REQUIREMENTS.md`, enabling history-aware verification
   152	
   153	This enrichment is conditional on the `context_window` value in
   154	`config.json`. On standard-window configurations, prompts use truncated
   155	versions with cache-friendly ordering to maximise token efficiency.
   156	
   157	---
   158	
   159	## Why this design — the connection to context engineering
   160	
   161	The orchestrator → agent pattern only makes sense as part of a broader
   162	approach to *context engineering*: the idea that what an AI agent gets in its
   163	context window matters as much as the model tier or prompt quality. See
   164	[Context engineering](context-engineering.md) for the full treatment.
   165	
   166	Multi-agent orchestration operationalises context engineering in two ways:
   167	
   168	**Context isolation.** Each agent receives only what it needs. A researcher
   169	gets the project description and domain questions; it does not get the full
   170	planning history. A verifier gets every plan and summary; it does not get the
   171	raw research. Isolation keeps each agent's context dense with signal rather
   172	than diluted by noise from other pipeline stages.
   173	
   174	**Context hygiene across sessions.** Because all state lives in
   175	`.planning/` as human-readable Markdown and JSON (not in any agent's context
   176	window), GSD workflows survive context resets (`/clear`), tab switches, and
   177	multi-day breaks. The next agent always starts from persisted, verified
   178	artifacts rather than from a reconstructed memory of a long conversation.
   179	
   180	---
   181	
   182	## Trade-offs
   183	
   184	Multi-agent orchestration is not free.
   185	
   186	**Coordination overhead.** Each agent spawn is a round-trip: the orchestrator
   187	must format a prompt, hand off context, wait for the subagent to complete
   188	(typically 1–5 minutes), and then parse the result. A single capable agent
   189	working in one context would finish faster for simple tasks. GSD mitigates
   190	this by making parallelism the default wherever dependencies permit — the
   191	four researchers in a `plan-phase` run simultaneously, not sequentially.
   192	
   193	**Opacity during execution.** While a subagent is running, its work is
   194	invisible to the parent session. There is no live progress stream. This is a
   195	deliberate consequence of the fresh-context design: the subagent is operating
   196	in its own context window. The orchestrator shows a liveness note on the
   197	spawn line ("runs in a subagent — no output until it returns") to set
   198	expectations.
   199	
   200	**Context stitching cost.** Packaging the right artifacts for each agent
   201	requires the orchestrator to spend tokens assembling and transmitting context
   202	payloads. This is the cost of isolation. The `gsd-tools.cjs init` handler
   203	produces a JSON payload that balances completeness with token budget, applying
   204	cache-friendly ordering so that the stable parts of the payload (project
   205	definition, config) hit the cache on repeat invocations.
   206	
   207	**Model cost amplification.** Running five agents in parallel at Opus tier
   208	costs more than running one. The model profile system (`model_profiles.md`,
   209	resolved per agent by `model-profiles.cjs`) lets you assign cheaper tiers to
   210	less critical agents. The `dynamic_routing` feature further reduces cost by
   211	starting every agent on a cheaper tier and escalating only on a soft failure.
   212	See [Configuration](../CONFIGURATION.md) for the full options.
   213	
   214	In return for these costs, the design buys *consistent quality across large
   215	phases*. An executor writing the tenth file in a 400-line plan does not
   216	degrade because its context is fresh. A verifier checking twenty requirements
   217	does not forget the first ten because it received all of them as structured
   218	input rather than conversation history.
   219	
   220	---

codex
The gsd side is clear now: it is opinionated about context budgets, sealed artifacts, and verifier outputs. I’m checking whether Rebalance has any equally explicit subagent contract beyond ad hoc consults and PDDA write-back, because that’s where the Phase 1 calls turn.
exec
/bin/zsh -lc "nl -ba ROUTER.md | sed -n '1,220p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-21302-28772
 succeeded in 0ms:
     1	# ROUTER.md
     2	
     3	This file is the first entry point for an AI agent working in this repo: it tells you what to read, what to run, and which files are canonical. **This repo is an MCP server** — reach for the MCP tools before scanning code or writing ad-hoc shell pipelines.
     4	
     5	## Role split
     6	
     7	- `ROUTER.md` = startup order and canonical entry points (this file)
     8	- `AGENTS.md` = behavioral rules, the MCP tool surface, the onboarding flow, and decision quality
     9	- `ARCHITECTURE.md` = system orientation (Signal Sources, Source→Table fanout, "Adding a New Source") — read at session start
    10	- `GUIDING-PRINCIPLES.md` = the *why* behind architecture and design decisions; includes the AI doc-review heuristics appendix
    11	- `README.md` = human-facing repo/product overview and install path
    12	- `ROADMAP.md` = pointer ledger of in-progress, completed, attempted, and deferred work
    13	- `CHANGELOG.md` = the end-of-iteration running log
    14	- `PROJECT/**` docs = canonical execution detail for a specific effort
    15	- `PROJECT/PDDA.md` = document contract and PDDA automation rules
    16	
    17	## Startup sequence
    18	
    19	1. Read `ROUTER.md` to understand the repo's operating order and canonical files. -> expect one clear next file, not a repo-wide scavenger hunt.
    20	2. Read `AGENTS.md` before making recommendations or edits. -> expect the MCP tool surface, the onboarding flow, explicit assumptions, and verified-claims-only discipline.
    21	3. Read `ARCHITECTURE.md` for orientation, then `src/rebalance/ingest/index_ops.py` — the `COLLECTORS` registry is the data-plane spine. -> expect to extend a source with one `register_collector(...)` call, not edits to the dispatch chain.
    22	4. Read `ROADMAP.md` to find the active effort. -> expect links outward to the canonical `PROJECT/**` docs; `ROADMAP.md` is a pointer ledger, not a plan body.
    23	5. Read the linked `PROJECT/**` document that owns the work you are touching. -> expect a near-top `## Status` table telling you what was just completed and what is next.
    24	6. If the task touches project docs, read `PROJECT/PDDA.md` and follow the PDDA contract. -> expect `PROJECT/2-WORKING` docs to have frontmatter, the exact status table, and QA gates when phased.
    25	7. Before reporting success on code or runtime work, run `rebalance doctor` and `pytest tests/`. -> expect doctor clean and the suite green; do not claim completion if either fails or was skipped.
    26	8. Before reporting success on doc-hygiene or roadmap work, run `utils/pdda/pdda.sh run` (or the relevant `utils/pdda/pdda.sh <check>` command). -> expect deterministic findings first, then any LLM review.
    27	
    28	## Canonical rules
    29	
    30	- This repo **is** an MCP server. Use the MCP tools (`index_status`, `refresh_index`, `semantic_query`, …) for data refresh and retrieval, and `rebalance doctor` for setup/health. Do not write ad-hoc `rebalance ...` shell pipelines or grep for setup scripts.
    31	- Do not put phase checklists, build steps, or deep execution notes in `ROADMAP.md`.
    32	- Every active doc in `PROJECT/2-WORKING/` must be reflected by a one-line pointer in `ROADMAP.md` — or opt out with `roadmap_exempt: true` in its frontmatter. Enforced by `utils/pdda/pdda.sh roadmap-coverage`; governance lives in `PROJECT/PDDA.md`.
    33	- Every captured GitHub issue doc in `PROJECT/1-INBOX/GH-*.md` is first-class intake and must also be parked in `ROADMAP.md` as a one-line queue entry immediately at capture, then promoted or removed later. Enforced by `utils/pdda/pdda.sh roadmap-coverage`; governance lives in `PROJECT/PDDA.md`.
    34	- Do not create a second competing plan when a canonical `PROJECT/**` doc already exists.
    35	- Do not override deterministic PDDA findings with prose.
    36	- Do not report a win you did not verify with `rebalance doctor`, `pytest tests/`, or the relevant PDDA check.
    37	
    38	## Command rails
    39	
    40	For setup/health:
    41	
    42	```bash
    43	rebalance doctor
    44	```
    45	
    46	For code correctness:
    47	
    48	```bash
    49	pytest tests/
    50	```
    51	
    52	For document hygiene:
    53	
    54	```bash
    55	utils/pdda/pdda.sh run
    56	```
    57	
    58	For targeted PDDA debugging:
    59	
    60	```bash
    61	utils/pdda/pdda.sh frontmatter
    62	utils/pdda/pdda.sh status-table
    63	utils/pdda/pdda.sh hardcoded-paths
    64	utils/pdda/pdda.sh roadmap
    65	utils/pdda/pdda.sh roadmap-coverage
    66	utils/pdda/pdda.sh changelog
    67	utils/pdda/pdda.sh stale
    68	utils/pdda/pdda.sh doc-ready   # LLM readiness review — set PDDA_LLM_BIN (codex/claude/agy) for recommendations, else it self-skips
    69	utils/pdda/pdda.sh help
    70	```
    71	
    72	## Routing hints
    73	
    74	- If the task is about current priorities or active work, start in `ROADMAP.md`, then follow the linked `PROJECT/**` doc.
    75	- If the task is about data sources, refresh, or "why is X empty?", start with `rebalance doctor`, then `src/rebalance/ingest/index_ops.py` (the `COLLECTORS` registry).
    76	- If the task is about retrieval or synthesis (the read side), start in `src/rebalance/querier.py`.
    77	- If the task is about the MCP tool surface or operator onboarding, start in `AGENTS.md`.
    78	- If the task is about document quality, active-doc lifecycle, roadmap sprawl, or automation policy, start in `PROJECT/PDDA.md`.
    79	- If the task is about installing PDDA into another repo, read `PDDA-INSTALL.md`.
    80	- If the task originates from a GitHub issue, capture it as `PROJECT/1-INBOX/GH-<number>-SHORT-DESCRIPTION.md`, then follow the normal `1-INBOX` → `2-WORKING` flow.

exec
/bin/zsh -lc "rg -n \"consult|subagent|Agent tool|fresh-context|Explore|agent\" PROJECT ROADMAP.md ROUTER.md AGENTS.md .claude -g '"'!**/node_modules/**'"' | sed -n '1,220p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-21302-28772
 succeeded in 0ms:
ROUTER.md:3:This file is the first entry point for an AI agent working in this repo: it tells you what to read, what to run, and which files are canonical. **This repo is an MCP server** — reach for the MCP tools before scanning code or writing ad-hoc shell pipelines.
ROADMAP.md:37:- `GSD Core pattern review` — promoted to 2-WORKING 2026-07-03. Reviewing the MIT `gsd-core` framework for reusable patterns across two targets (vendored XYZ + Rebalance native), scoped to two families (phase-loop/context-engineering, skill/command/hook/agent architecture). Execution plan validated via XYZ's vendored `bin/marathon-yaml` planner (`p0→p1→p2→p3`, no cycles; `p1`/`p2` structurally parallel-eligible but share one target doc, so real concurrency needs a split-file/merge step, not XYZ's lane model). **Phase 0 (inventory) run via `consult`** (Codex + agy in parallel, not a Claude subagent, per operator request): both families grounded; the `capabilities/` overlay layer is the starkest gap both models independently converged on (Reb/XYZ have no composed registry/trust abstraction). One cross-model disagreement adjudicated — agy fabricated 3 out-of-bounds line-range citations against the gitignored vendored `.xyz/` (real files 55–335 lines vs. cited ranges to 4495), caught by direct measurement; Codex correctly flagged `.xyz/` as invisible to its sandboxed worktree and substituted verified canonical-repo citations. Phase 1/2 next. → [GSD-CORE-PATTERN-REVIEW.md](PROJECT/2-WORKING/GSD-CORE-PATTERN-REVIEW.md)
ROADMAP.md:39:- `XYZ ⇄ Rebalance integration` ([#102](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/102)) — promoted to 2-WORKING 2026-07-03 (branch `gh-102-xyz-rebalance-integration`). **Phase 0 discovery run** against XYZ's GH-75: `XYZ.json` confirmed **completion-only** telemetry (not a per-phase heartbeat), so **#1 reframed** to a "recently-completed sessions" signal — no XYZ-side emitter needed; enumeration source = `registry.tsv` install rows; XYZ already writes atomically. Cross-model consult (Codex + agy) also moved **#3 off direct SQLite** onto a `roadmap_signals.json` projection file (mirror-not-migration). Build order #2→#1→#3→#4. **Phase 1 (seam #2 `xyz-sync check`) next; Phase 2 gated on GH-101.** → [PROJECT/2-WORKING/GH-102-XYZ-REBALANCE-INTEGRATION.md](PROJECT/2-WORKING/GH-102-XYZ-REBALANCE-INTEGRATION.md)
ROADMAP.md:44:- `Unified UI refresh + restart (system-wide)` — keep the always-on pulse-server as the source-freshness path so no source goes stale and no manual terminal sync is needed. **/ponytail-trimmed to a v1 (2026-06-27)** after a Codex consult QA: the `/api/restart` endpoint + Focus 5 Swift wiring are **deferred**. **v1 = make the existing Refresh button populate the reminders column via the signed EventKit helper (no FDA)** — 3 edits: helper `list-active` op → `/api/refresh` reads it (atomic, last-good-snapshot-wins, ~5s timeout) → column renders. **Phase QA-R remediation shipped 2026-07-01 (PR #100)** — all 7 findings closed, 8 new tests, agy-Approved. **Next:** operator litmus on the live dashboard, then archive. → [PROJECT/2-WORKING/UNIFIED-REFRESH-RESTART.md](PROJECT/2-WORKING/UNIFIED-REFRESH-RESTART.md)
ROADMAP.md:64:- `AI-agent front door (ROUTER.md)` — added the canonical startup-order entry point (ROUTER → AGENTS → ARCHITECTURE → ROADMAP → PROJECT docs; run `rebalance doctor` / `pytest tests/` / `utils/pdda-run.sh` before claiming wins), completing the PDDA front-door layer alongside the installed `utils/pdda-*.sh` suite. → [ROUTER.md](ROUTER.md)
AGENTS.md:13:**Connection.** The repo ships two equivalent configs: [.vscode/mcp.json](.vscode/mcp.json) for VS Code agents and [.mcp.json](.mcp.json) at the repo root for tools that look there. Both launch `.venv/bin/python -m rebalance.mcp_server` over stdio with `REBALANCE_DB` set to the repo's `rebalance.db`.
AGENTS.md:23:| `publish_pulse(dry_run=?, push=?)` | Render today's + yesterday's activity into a markdown status page and publish it to a private pulse repo. Each row tagged by source (`claude-cloud` / `codex-cloud` / `lovable` / `local-vscode` / `human`) via `src/rebalance/ingest/agent_tags.py`. Reusable: every per-user value (`github_login`, `slack_user_id`, `pulse_target_path`, `pulse_filename`, `pulse_timezone`) lives in `temp/rbos.config` |
AGENTS.md:131:- Log all DELETE/DROP/TRUNCATE operations with timestamp, user, and target to `/logs/agent-audit.json`.
AGENTS.md:156:- Assert on side effects (logs, DB writes, queue messages) not just return values. Mock should verify agent behavior, not just response parsing.
AGENTS.md:182:Observed in a real session where the MCP surface was unavailable and CLI/SQLite fallbacks were used. Record here so future agents know what to work around or fix.
AGENTS.md:186:| 1 | **Runtime/docs sync** — AGENTS.md says "use MCP tools first" but the MCP server may not be callable at session start | Agent wastes time on MCP calls before falling back to CLI | Add a session-start connectivity check; verify tool list is live before instructing agents to prefer it |
AGENTS.md:190:| 5 | ⚠️ **SECURITY: live API key surfaced in semantic results** — a vault note containing a live credential was indexed and returned by `semantic_query` | Key exposure via any agent that can call the tool | Add pre-embed redaction (strip key-shaped patterns) in `note_ingester.py` and/or a vault note exclusion mechanism (frontmatter `index: false` or path exclusion). **Fix before next vault ingest.** |
AGENTS.md:196:Some generated artifacts in this repo ship with placeholder prose that any agent
AGENTS.md:205:The generated recap itself carries the same pointer in its top-of-file instructions block, so agents that open the file directly will also find the rulebook without needing this index.
.claude/skills/welcome/SKILL.md:3:description: Guided rebalance-OS onboarding — the welcome agent. Walks a new (or returning) operator from clone to first pulse by driving the lifecycle status contract: renders where-am-I, executes each setup step itself (GitHub PAT, optional Calendar/Gmail OAuth, project discovery and promotion, scheduler install), and verifies every step before moving on. Trigger when the user invokes /welcome, asks to "set up rebalance", "finish onboarding", "where am I in setup", wants to add a previously skipped step (Calendar/Gmail), or after a fresh clone. Resumable at any time — state lives in the MCP contract, not this conversation.
.claude/skills/welcome/SKILL.md:8:You are the welcome agent. The setup state machine is owned by the
PROJECT/deprecated/cleanup.sh:16:#   --json      Emit structured JSON to stdout for agent/MCP consumption
PROJECT/deprecated/cleanup.sh:67:#   ./PROJECT/cleanup.sh scrub-intake --json # structured intake prompt payload for agents
PROJECT/deprecated/cleanup.sh:81:#   Phase 1 (this) — scan + P3 prefix/downgrade, xref warnings, agent hooks
PROJECT/deprecated/cleanup.sh:368:  # ── Human / agent output ─────────────────────────────────────────────────
PROJECT/deprecated/cleanup.sh:659:  prompts+=("Run \`./PROJECT/cleanup.sh scan --json\` to get the full machine-readable registry for agent use.")
PROJECT/deprecated/cleanup.sh:2215:    PROMPTS+=("Run with \`--json\` to get the full machine-readable action plan for agent orchestration.")
PROJECT/deprecated/cleanup.sh:2268:  "agent_prompts": $prompts_json
PROJECT/deprecated/cleanup.sh:2435:  PROMPTS+=("Run with \`--json\` to get the full machine-readable action plan for agent orchestration.")
PROJECT/deprecated/cleanup.sh:2491:  "agent_prompts": $prompts_json,
PROJECT/deprecated/plan_example.md:196:Expected: 7 agents, 5–8 min, ~60–90k tokens. Output: `PROJECT/1-INBOX/PHASE-0-SPIKE.md`.
PROJECT/AGENTS-DOCS.md:3:This file defines how agents should create, update, move, and review documents under `PROJECT/`.
PROJECT/AGENTS-DOCS.md:36:owner: Name or agent
PROJECT/1-INBOX/P3-GOAL-LAYER.md:158:- Goaly can rebuild its coaching-accountability table from one MCP call and stop consulting file mtimes for that surface.
PROJECT/1-INBOX/P1-SIGNAL.md:31:The next high-leverage move is not another ingest surface. It is one weekly rebalance loop backed by one canonical attention ledger in SQLite and rendered into one operator-facing dashboard in Obsidian. That keeps the intelligence local, reduces agent rabbit holes, and gives the repo a clear center of product gravity.
PROJECT/1-INBOX/P1-SIGNAL.md:42:2. It reduces agent-induced rabbit holes. A generated markdown dashboard is more likely to steer toward decisions than an open-ended chat surface.
PROJECT/1-INBOX/P1-SIGNAL.md:52:2. Do not let agents write freely across hand-maintained notes.
PROJECT/1-INBOX/P1-SIGNAL.md:59:3. VS Code agents for deep implementation work, audits, schema changes, and one-off investigations.
PROJECT/1-INBOX/P1-SIGNAL.md:77:3. Any agent writeback should preserve human-authored content byte-for-byte outside generated sections.
PROJECT/1-INBOX/P1-SIGNAL.md:383:The repo is pointed in the right direction, but it is still one layer too close to raw capability. The right product move is to make Obsidian the calm dashboard and note-entry surface, keep SQLite as the canonical attention ledger underneath it, and reserve VS Code agent chats for deep implementation or investigative work.
PROJECT/PDDA.md:4:research notes, and roadmap pointers clean enough that an agent can pick up work with minimal drift
PROJECT/PDDA.md:19:- Give agents one repeatable contract for project docs, bug-fix docs, and experimental plans.
PROJECT/PDDA.md:61:   cold agent can see the full phase span and jump to the live one without scrolling the whole body
PROJECT/PDDA.md:146:- If either is missing, an agent has to reconstruct state from the body, which is slow and error-prone.
PROJECT/PDDA.md:158:lives only in an agent's context or a throwaway scratch note, a cold agent resuming the plan cannot see
PROJECT/PDDA.md:178:phase whose findings were not written back. "Did the agent actually capture what it learned" is a
PROJECT/PDDA.md:674:- agent sessions restarting the same reasoning because the doc never captured "what changed"
PROJECT/1-INBOX/SUBSYSTEM-REFACTOR-PHASE-5-REVIEW.md:19:The Phase 5 subsystem refactor cleanly isolates the read/write paths and delivers on its core promise of enforcing an operator-first boundary. Discovery is successfully isolated as a pure read path, and curated SQLite rows are structurally shielded from inference overwrites. However, the implementation is slightly marred by a `provenance` data loss bug in the `sync_registry(mode="push")` projection logic, and `PROJECT_LIFECYCLE` exists strictly as unconsumed, over-engineered declarative baggage. Aside from fixing the `provenance` pipeline leak, there are no structural roadblocks to building the Phase 6 `/welcome` agent on top of this foundation.
PROJECT/3-DONE/P2-PLUGIN-SOURCE-MODULES.md:6:> full Phase 0 spike detail and long-form contracts; consult it for depth, but
PROJECT/3-DONE/P2-PLUGIN-SOURCE-MODULES.md:138:    badges: tuple[str, ...] = ()               # e.g. agent tag, state, "unread"
PROJECT/3-DONE/P2-PLUGIN-SOURCE-MODULES.md:274:- [ ] Dovetail with B′ Phase 2: each module's `health_check` is reachable via the `health_check()` MCP tool, and `onboarding_status` reflects a discovered source's `secrets` — so a freshly-installed plugin's setup hint reaches MCP-first agents (the exact gap B′ was triggered by).
PROJECT/RELAY/TO-CLAUDE.md:41:The agent will likely strand the beta tester at the optional stages prompt. If the beta tester installs the package globally (as most would on a fresh Mac), `repo_root` will be `None`, and the `[".venv/bin/python", target]` command will instantly fail. Additionally, a simple Ctrl+C during the prompts will silently corrupt their skip state.
PROJECT/3-COMPLETED/FOCUS-5-RANKING-BUG-AND-REMEDIATION.md:41:  roster = rebalance-OS (2m), xyz-3-agents-swarm (8h), giant-brains (9h),
PROJECT/3-COMPLETED/FOCUS-5-RANKING-BUG-AND-REMEDIATION.md:49:`xyz-3-agents-swarm`, `rebalanceOS`, `giant-brains-claude-skills`,
PROJECT/3-COMPLETED/FOCUS-5-RANKING-BUG-AND-REMEDIATION.md:63:| 4 | Are the active repos discovered? | `giant-brains-claude-skills`, `hypercart-plugin-mkiii`, `xyz-3-agents-swarm` **all present**, all `is_dirty=0`, and the **most-recently-committed** rows in the set | discovery **ruled out** as the cause |
PROJECT/3-COMPLETED/FOCUS-5-RANKING-BUG-AND-REMEDIATION.md:66:| 7 | Re-rank by pure `_recency` (no dirty pin) | TOP 5 = **hypercart-plugin-mkiii, wp-code-check, xyz-3-agents-swarm, giant-brains-claude-skills**, facebook-for-woocommerce | the desired view needs a **new mode** |
PROJECT/3-COMPLETED/FOCUS-5-RANKING-BUG-AND-REMEDIATION.md:158:      hypercart-plugin-mkiii / xyz-3-agents-swarm / giant-brains in the top 5
PROJECT/RELAY/FROM-CLAUDE.md:70:   what breaks first, and at which stage does the agent most likely strand
PROJECT/3-DONE/SIMPLIFICATION-AUDIT.md:47:| F6/F7 | `src/rebalance/ingest/dashboard.py:299-304` + `github_scan.py:557-641` | Remove `get_github_balance()` from Obsidian note build | `build_dashboard_payload()` builds a `{project_name: [repos]}` map from project_registry and passes it to `get_github_balance()` — the old registry-gated path — in parallel with the already-working `get_all_repo_activity_by_org()` call. These are the same code location: F6 is the call site, F7 is the function being called. One Phase 3A task removes both. `get_github_balance()` is preserved in `mcp_server.py:40` where per-project aggregation is genuinely useful for agents. | Remove `repo_map` construction and `get_github_balance()` call from `build_dashboard_payload()`; choose Option A or B for verdict section (see Phase 3A). | **Medium** — verdict labels lose project granularity; MCP tool `github_balance` is unaffected (separate call site) | 3 |
PROJECT/3-DONE/SIMPLIFICATION-AUDIT.md:134:- [x] **Decision: keep `github_balance` MCP semantics as-is.** Per-project names ("how is LTVera doing?") are the right agent-facing surface. When prefix-clustering or #tag annotation populates `repos_json`, this tool becomes the payoff. Switching to org-grouped now would require re-adding it later.
PROJECT/3-DONE/SLEUTH-PRODUCTION.md:191:  > (`base_url=http://127.0.0.1:12020`, launchd agent `com.rebalance-os.sleuth-tunnel`).
PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:13:  - welcome-agent
PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:35:11. [Phase 6 - Welcome Agent and Guided Onboarding](#phase-6---welcome-agent-and-guided-onboarding)
PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:191:Expected: 7 agents, 5–8 min, ~60–90k tokens. Output: `PROJECT/1-INBOX/PHASE-0-SPIKE.md`.
PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:407:Goal: consolidate project discovery, confirmation, registry persistence, and priority/inference logic into clearer contracts — shaped explicitly so the Phase 6 welcome agent can sit on top of them without rework.
PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:409:Still a refactor phase: no new UX ships here. What changes versus the original Phase 5 sketch is that the contracts now name the things the welcome agent will need: lifecycle stages with a status vocabulary, a discovery-provenance field in the project schema, and `onboarding_status` as the machine-readable "where am I" source of truth.
PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:438:3. *Executor hints* — stages carry remediation prose; the agent would benefit from a machine-executable `executor` field (MCP tool name / command) per stage. Additive Phase 6 change.
PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:461:2. *[Medium — fixed]* `PROJECT_LIFECYCLE` had no runtime consumer ("documentation disguised as an array"). Now exposed as `project_lifecycle_map()` in the `onboarding_status` payload — the agent gets the write-discipline map through one tool call.
PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:467:Goal: ship a first-class guided setup experience — a welcome agent that walks a new user from clone to first rendered pulse, executing every step itself, with the operator always able to see what's done, what's happening now, and what's next.
PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:479:**The journey (state-machine stages the agent walks):**
PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:500:- Secrets posture: tokens are never echoed into the transcript; keyring-first storage; the agent passes secrets via env/stdin, never as chat literals.
PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:513:- [x] Cover every stage with an agent-runnable executor:
PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:525:- [x] Rewrite onboarding docs around the agent:
PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:535:- [x] D (Dependency Inversion): skill and CLI depend on the status contract and executor vocabulary, not on each other or script internals; hermetic seams (`REBALANCE_HERMETIC`, `_launch_agents_dir`, `_pulse_html_path`) are injection points, not test hacks in prod code paths
PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:549:5. *[Refuted→fixed]* Reset gaps: half-reset orphaned the DB when config was already gone (now sweeps the canonical path), `sleuth_web_api` missing from keyring enumeration (added), OAuth token files not removed (now listed and deleted). Verified live: dry-run found 2 token files + 5 secrets on this machine. *Declined:* the `com.user.*` glob — git-pulse/stickies are utility agents with their own installers, outside /welcome's footprint; reset now states this explicitly.
PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:570:  Phase 6 is the only feature phase in this plan. Its deliverable list is the scope boundary — "while we're building the agent" additions (new ingest sources, GUI work, telemetry platforms) get logged for a future plan, not built.
PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:585:- [x] A new user reaches a rendered first pulse through one guided `/welcome` session — auth setup (PAT, optional Calendar/Gmail), repo promotion, and scheduler install handled by the agent; "where am I / what's next" queryable at every step via `onboarding_status` or `rebalance onboard --status` (Phase 6).
PROJECT/2-WORKING/P3-FOCUS5-FLOAT-OFFLINE-RESILIENCE.md:43:- The app is a **non-sandboxed, ad-hoc-signed menu-bar agent** (`setActivationPolicy(.accessory)`), so launching a subprocess (`Process`) or `launchctl` is permitted.
PROJECT/1-INBOX/SUBSYSTEM-REFACTOR-PHASE-6-REVIEW.md:41:The agent will likely strand the beta tester at the optional stages prompt. If the beta tester installs the package globally (as most would on a fresh Mac), `repo_root` will be `None`, and the `[".venv/bin/python", target]` command will instantly fail. Additionally, a simple Ctrl+C during the prompts will silently corrupt their skip state.
PROJECT/1-INBOX/PDDA-INTEGRATION/ROADMAP-SIGNAL-SCAN.md:10:  plane can answer "what should I work on next" using the project state agents already maintain.
PROJECT/1-INBOX/PDDA-INTEGRATION/ROADMAP-SIGNAL-SCAN.md:34:**The bet:** project state that agents already maintain (because PDDA forces it) is a *cheaper and
PROJECT/1-INBOX/PDDA-INTEGRATION/ROADMAP-SIGNAL-SCAN.md:53:- explicitly designed (per PDDA's `GUIDING-PRINCIPLES.md`) so a *cold agent* can answer "what was
PROJECT/1-INBOX/PDDA-INTEGRATION/ROADMAP-SIGNAL-SCAN.md:60:`What's next` row is about as high-signal as a "what next" input gets: it is a human/agent's own
PROJECT/1-INBOX/PDDA-INTEGRATION/ROADMAP-SIGNAL-SCAN.md:172:   *within* one repo: verified-path, disjoint, acceptance-checked lanes for the `tick` multi-agent
PROJECT/1-INBOX/PDDA-INTEGRATION/ROADMAP-SIGNAL-SCAN.md:176:   task lane for cross-repo multi-agent coordination, not just cross-source signal aggregation.
PROJECT/4-MISC/FRONT-DOOR-ONBOARDING-REMEDIATION.md:25:| **Front-door audit complete (2026-06-21).** A cold-newcomer walk of the clone→working path. Verdict: ⚠️ Bumpy — on macOS Apple Silicon with an agent a newcomer reaches a verified state in ~20–30 min; secrets scan clean (tree + history). Bumps found: README drift from the recent auth-storage hardening, an Apple-Silicon/MLX platform gate that's disclosed but buried, undocumented first-run network egress, and a Calendar/Gmail local-OAuth wall that Claude-Desktop users could skip via host MCP connectors. | **Phase 1 — doc-drift quick wins.** Reconcile the canonical README with the shipped keyring + secret-store + JSON-OAuth model (two stale lines at README:262 and :321). |
PROJECT/4-MISC/FRONT-DOOR-ONBOARDING-REMEDIATION.md:48:- **First-run network egress undocumented.** The embeddings step downloads `Qwen3-Embedding-0.6B` from HuggingFace on first run; `github-scan`/`calendar-sync` reach `api.github.com` / `*.googleapis.com`. A sandboxed agent's network allowlist can block these, and the failure can read as an unrelated error.
PROJECT/4-MISC/FRONT-DOOR-ONBOARDING-REMEDIATION.md:81:  Observable result: Step 3 notes that the embeddings step downloads `Qwen3-Embedding-0.6B` from HuggingFace (host + approx. size), and that `api.github.com` / `*.googleapis.com` are reached during sync — so an agent-sandbox or allowlisted environment can permit those hosts (or run the step outside the sandbox).
PROJECT/4-MISC/FRONT-DOOR-ONBOARDING-REMEDIATION.md:82:- [ ] Tie the egress note to the agent path.
PROJECT/4-MISC/FRONT-DOOR-ONBOARDING-REMEDIATION.md:83:  Observable result: the `/welcome` / `rebalance onboard` sections flag that a sandboxed agent may be blocked from the model download and name the remedy (allowlist the host, or run the download outside the sandbox once).
PROJECT/4-MISC/FRONT-DOOR-ONBOARDING-REMEDIATION.md:90:- [ ] An agent-sandbox user can self-serve the egress allowlist from the docs without hitting a misleading error first.
PROJECT/4-MISC/FRONT-DOOR-ONBOARDING-REMEDIATION.md:97:**Design note (recommendation).** rebalance already proves the pattern for Gmail: `set-gmail-method mcp` makes the scheduled job a no-op and expects an agent to pull messages via the host's Gmail connector and call the `ingest_gmail_messages` MCP tool — no local OAuth, no bundled-client trust, no keyring/secret-store token. So **the Gmail host-connector path is available today.** Claude Desktop also ships a first-party **Google Calendar** connector, so the same pattern *could* extend to Calendar — but **no Calendar `mcp` consumption mode exists yet** (`calendar_ingest_method` and an `ingest_calendar_events` tool are unbuilt). This plan therefore: (1) **promotes** the existing Gmail `mcp` mode for host-connector users (today it is under-advertised behind the `oauth` default), and (2) **specs the Calendar `mcp` mode and explicitly defers the build** — Calendar host-connector consumption must be documented as **"planned, not yet supported," never as a current path**, until the mode and tool ship.
PROJECT/4-MISC/FRONT-DOOR-ONBOARDING-REMEDIATION.md:99:**Precondition — state it wherever the connector path is offered.** The host-connector route is not free of gates; it trades a different one: the user's MCP host must actually ship Google connectors, and the user must have **connected and consented** their Google account inside that host. So this path fits "I already use Claude Desktop with its Google connectors connected," not "any agent user skips OAuth for free."
PROJECT/4-MISC/FRONT-DOOR-ONBOARDING-REMEDIATION.md:108:  Observable result: each connector recommendation names the precondition (host must ship Google connectors; user must have connected/consented their Google account in the host) so no reader concludes any agent user skips OAuth for free.
PROJECT/4-MISC/FRONT-DOOR-ONBOARDING-REMEDIATION.md:128:  Observable result: internal docs move into `docs/internal/` (or similar) with inbound links updated; agent-convention files that tools expect at root (`AGENTS.md`, `CLAUDE.md`) stay where their loaders require.
PROJECT/4-MISC/FRONT-DOOR-ONBOARDING-REMEDIATION.md:134:- [ ] The repo root shows only newcomer-relevant docs plus the canonical README and required agent-convention files.
PROJECT/4-MISC/FRONT-DOOR-ONBOARDING-REMEDIATION.md:157:- [ ] First-run network egress (HuggingFace model, GitHub, Google APIs) is documented for allowlisted/agent-sandbox users.
PROJECT/1-INBOX/SUBSYSTEM-REFACTOR-PHASE 3.md:15:| Phase 3 is ownership-first work. Parallel implementation before an ownership decision will produce conflicting diffs. | Lock the read-side ownership model first, then let implementation agents work inside that contract. |
PROJECT/1-INBOX/SUBSYSTEM-REFACTOR-PHASE 3.md:37:That overlap is not just conceptual. It is already encoded in code and docs, and the current contracts pull in different directions. If multiple agents start "cleaning up Phase 3" without a locked ownership decision, they will reasonably make different choices about which surface is canonical.
PROJECT/1-INBOX/SUBSYSTEM-REFACTOR-PHASE 3.md:100:- If ownership is not locked first, each agent will likely "fix" duplication around a different center.
PROJECT/1-INBOX/SUBSYSTEM-REFACTOR-PHASE 3.md:106:1. An agent following `ARCHITECTURE.md` will treat `ask()` as the central read-side orchestrator and push other surfaces underneath it.
PROJECT/1-INBOX/SUBSYSTEM-REFACTOR-PHASE 3.md:107:2. An agent following `CHAT-WITH-DATA.md` will preserve `chat_with_data()` as a separate tool and resist making it an `ask()` extension.
PROJECT/1-INBOX/SUBSYSTEM-REFACTOR-PHASE 3.md:108:3. An agent following the MCP surface will treat `semantic_query()` as the canonical unified retrieval API and push wrappers toward it.
PROJECT/1-INBOX/SUBSYSTEM-REFACTOR-PHASE 3.md:310:- [ ] Lock the ownership table in the main Phase 3 plan before opening implementation work to multiple agents.
PROJECT/1-INBOX/SUBSYSTEM-REFACTOR-PHASE 3.md:335:It is not "hard because the code is messy." It is hard because the repo currently presents multiple plausible read-side owners, each supported by different live code and docs. The correct move is to make the ownership decision first, then let agents implement inside that boundary.
PROJECT/2-WORKING/APPLE-REMINDERS-UNIFIED-PLAN.md:22:| **Phase 6 dashboard write-back v1 SHIPPED (2026-06-30).** The pulse "Today" Apple Reminders column is now **actionable**: a per-reminder complete check POSTs `/api/apple-reminders/complete` (`scripts/pulse_server.py`) → the Phase 5.1 orchestrator (`apply_reminder_writes`, single-writer + audit) → signed helper. Optimistic grey-out UX (`reconcile=False`; local table catches up on the next scoped sync). `create`/`delete` stay CLI-only. **5 new endpoint regression tests** (`tests/test_pulse_server_apple_reminders.py`) green. _Earlier:_ **Phase 5.1 write surface SHIPPED + live-verified (2026-06-27)** — orchestrator + signed helper + `rebalance apple-reminders` CLI (create/update/complete/delete/audit, dry-run default) + 57 tests; full create→complete→delete proven live; all consult-hardening landed. **Phase 5.0 convergence PROVEN**; **Phases 0–4 complete** incl. P3 surface. P0–P2: FDA access, deterministic discovery, WAL-safe snapshot, dynamic REMCD mapper; `apple_reminders` collector (opt-in) + storage verified live via `refresh_index` (8147, idempotent). P3: `list_apple_reminders` read accessor + the pulse column (now actionable). P4: schema-drift health, fingerprint, FDA/drift runbook. | **Ship / review.** Phases 0–6 functionally complete. Operator one-time setup for the dashboard write: build + grant the signed helper once. Deferred by choice: cross-version validation (needs 2nd macOS), snapshot perf wins (active-store-only, mtime-skip), notes/sections full decode, auto-refresh of the column after a write (FDA-gated reconcile). |
PROJECT/2-WORKING/APPLE-REMINDERS-UNIFIED-PLAN.md:345:   agent or an EventKit-backed read for the column. Tracked as a follow-up; see Phase 6 below.
PROJECT/2-WORKING/APPLE-REMINDERS-UNIFIED-PLAN.md:386:- [x] Verify the helper works from the **actual intended runtimes**: interactive shell first, then the agent-hosted process tree, then a launchd-like context if relevant.
PROJECT/2-WORKING/APPLE-REMINDERS-UNIFIED-PLAN.md:387:      _Verified the opposite is also important: launch mode changes TCC behavior materially. Direct CLI / agent-hosted launches fail; LaunchServices app-bundle launch can prompt + grant._
PROJECT/2-WORKING/APPLE-REMINDERS-UNIFIED-PLAN.md:442:  the current **agent-hosted VS Code process tree is not a viable EventKit write runtime** for Apple
PROJECT/2-WORKING/APPLE-REMINDERS-UNIFIED-PLAN.md:476:  launch the signed bundle via LaunchServices and click "Allow" on the TCC prompt(s). No CLI agent
PROJECT/2-WORKING/APPLE-REMINDERS-UNIFIED-PLAN.md:503:read-back would not need FDA). No CLI/agent-hosted runtime can satisfy this. EventKit alone covers
PROJECT/2-WORKING/APPLE-REMINDERS-UNIFIED-PLAN.md:515:under the agent/VS Code responsible tree, where TCC suppresses the grant). So the write surface is **not**
PROJECT/2-WORKING/APPLE-REMINDERS-UNIFIED-PLAN.md:523:rebalance core (Python, agent/CLI-hosted)        signed helper app bundle (the ONLY writer)
PROJECT/2-WORKING/APPLE-REMINDERS-UNIFIED-PLAN.md:532:- **Why `open`, not exec:** invoking the bundle's binary directly would re-parent it under the agent tree
PROJECT/2-WORKING/APPLE-REMINDERS-UNIFIED-PLAN.md:606:**Resolved by cross-model consult (2026-06-27, Codex; agy lane unavailable — interactive auth):**
PROJECT/2-WORKING/APPLE-REMINDERS-UNIFIED-PLAN.md:611:3. **Write scope = restricted to the configured ingest list** in v1 (consult graded this a **Blocker**):
PROJECT/2-WORKING/APPLE-REMINDERS-UNIFIED-PLAN.md:615:**Hardening folded in from the consult (all v1 requirements):**
PROJECT/2-WORKING/APPLE-REMINDERS-UNIFIED-PLAN.md:637:- [x] **Live end-to-end through the real helper.** _Proven 2026-06-27: built the helper (`scripts/build_apple_reminders_helper_app.sh`), granted Reminders once (durable; **no FDA needed** for the helper, as designed), then ran the full cycle through the orchestrator + the live `rebalance apple-reminders` CLI: plan-create (no mutation) → apply create → complete → delete of a disposable reminder, every op `status=ok` with EventKit `readback_ok=true`, ~0.3s each; the `audit` table recorded the full trail. (reconcile ran disabled on the agent tree — it needs FDA there — so states show `applied_in_eventkit`; EventKit read-back is the convergence proof.)_
PROJECT/2-WORKING/APPLE-REMINDERS-UNIFIED-PLAN.md:650:tests across orchestrator + CLI (all green; full apple suite 57/57). All consult-hardening landed:
PROJECT/2-WORKING/APPLE-REMINDERS-UNIFIED-PLAN.md:657:deliberately NOT shipped in v1 (write-through-MCP would let an agent delete reminders; the CLI keeps a
PROJECT/2-WORKING/APPLE-REMINDERS-UNIFIED-PLAN.md:662:(currently best-effort; skipped on the agent tree which lacks FDA).
PROJECT/2-WORKING/GH-102-XYZ-REBALANCE-INTEGRATION.md:6:status: "Active (2-WORKING) — promoted 2026-07-03 on branch `gh-102-xyz-rebalance-integration`. Phase 0 (pre-scope discovery) run against XYZ's GH-75 doc + code; findings written back below. Both consult blockers resolved: `XYZ.json` confirmed completion-only (→ #1 reframed to 'recently-completed'), harness-root enumeration source located. Phase 1 (seam #2) is next and needs no GH-101."
PROJECT/2-WORKING/GH-102-XYZ-REBALANCE-INTEGRATION.md:12:  Formalize how the XYZ agent-swarm harness (tick / marathon / relay-automation) and Rebalance
PROJECT/2-WORKING/GH-102-XYZ-REBALANCE-INTEGRATION.md:33:| **Phase 1 Reb-side landed (2026-07-03).** Promoted to `2-WORKING`; Phase 0 discovery written back (see [§Phase 0 Findings](#phase-0--findings-2026-07-03)). **Reb half of seam #2 built:** committed `.xyz-pin` at repo root (pins XYZ harness `c829000`, the commit Phase 0 was verified against), a `read_pin()` reader ([xyz_pin.py](../../src/rebalance/xyz_pin.py)), and a `doctor` check that surfaces it — an absent pin is a clean OK (invariant 1, mutual independence), a pin missing `commit=` warns. Gates green: `pytest tests/` **1264 passed**; `rebalance doctor` shows `xyz pin — xyz harness pinned @ c829000bad5e`; new `tests/test_xyz_pin.py` (6 cases). | **XYZ-side `xyz-sync check` (deferred to the `xyz-3-agents-swarm` repo)** — extends the existing `xyz-sync.sh` / `find-harness.sh` drift surface to diff the machine-local install's `source_commit` against Reb's committed `.xyz-pin`. Then **lock the one open Phase 0 sub-decision** (harness-root opt-in/dedup rule). **Phase 2 (seam #1) stays gated on GH-101** landing `recent_row_count_7d` + `status`/`reason`. |
PROJECT/2-WORKING/GH-102-XYZ-REBALANCE-INTEGRATION.md:113:- **⚠ Correction (consult 2026-07-03):** today's `XYZ.json` (GH-75) is a **completion log written on terminal exit**, not a per-phase heartbeat. A *live in-flight* deep-work signal is therefore an **XYZ-side prerequisite** (new active-state emitter), not a free read. Phase 0 decides: reframe #1 to "recently-completed marathons" (works on today's file) or require the emitter. Owner split below reflects the *target*, gated on that decision.
PROJECT/2-WORKING/GH-102-XYZ-REBALANCE-INTEGRATION.md:201:Run against XYZ's [GH-75 doc](https://github.com/Claude-AI-Tools-Ventura-County/xyz-3-agents-swarm/issues/75)
PROJECT/2-WORKING/GH-102-XYZ-REBALANCE-INTEGRATION.md:203:cites. Each claim CONFIRMED against `file:line` in the **xyz-3-agents-swarm** repo, or marked OPEN.
PROJECT/2-WORKING/GH-102-XYZ-REBALANCE-INTEGRATION.md:205:**The two consult blockers — resolved:**
PROJECT/2-WORKING/GH-102-XYZ-REBALANCE-INTEGRATION.md:288:> the `xyz-3-agents-swarm` repo** (per operator decision), where it extends the existing `xyz-sync.sh` /
PROJECT/2-WORKING/GH-102-XYZ-REBALANCE-INTEGRATION.md:352:> **⚠ Correction (consult 2026-07-03) — file projection, not DB coupling.** The `roadmap_signals` table
PROJECT/2-WORKING/GH-102-XYZ-REBALANCE-INTEGRATION.md:508:- **QA:** cross-model consult (Codex + agy, 2026-07-03) against the Guiding Principles. Both ran inside
PROJECT/2-WORKING/GH-101-SIGNAL-QUALITY-CONTRACT.md:15:  ingest gate. Make a degraded source legible to any querying agent instead of letting the
PROJECT/2-WORKING/GH-101-SIGNAL-QUALITY-CONTRACT.md:162:- Leave *legitimately* zero-volume cases (a real quiet week) for the host agent to interpret — the
PROJECT/2-WORKING/GH-101-SIGNAL-QUALITY-CONTRACT.md:281:- Host agents can immediately read it ("you asked about this week but github shows 0 events — token
PROJECT/2-WORKING/GH-101-SIGNAL-QUALITY-CONTRACT.md:321:  the anomaly for the host agent to interpret.
PROJECT/2-WORKING/GH-101-SIGNAL-QUALITY-CONTRACT.md:349:- Should "expected volume" stay heuristic + agent-interpreted, or should some sources declare an
PROJECT/2-WORKING/FOCUS5-REMINDERS-PANEL.md:21:| **Build landing (2026-06-29).** Decided the data path: the app reads/writes Apple Reminders **directly via EventKit**, NOT through `rebalance serve`. This is sound because Focus 5 Float is the exact runtime [APPLE-REMINDERS-UNIFIED-PLAN.md](APPLE-REMINDERS-UNIFIED-PLAN.md) Phase 5.0 proved can hold the Reminders TCC grant — a signed, LaunchServices-launched app bundle (`me.neochro.Focus5Float`, ad-hoc signed, installed to `/Applications`). The Python server path can't write (suppressed under the agent tree) and its read is stale by design (freshness gap), so EventKit-direct is both fresher and write-capable with no FDA needed (FDA was only for the SQLite read-back path). Implemented: `RemindersStore` (EventKit), bottom split (A: reminders + B: scrollable note), make-app.sh TCC strings. | **Operator litmus (TCC-gated, cannot be automated):** reinstall via `./make-app.sh`, launch, tap **Enable Apple Reminders**, approve the prompt, confirm 10 recent default-list tasks render and a checkbox completes one (verify in the Reminders app). Then `.icns` + archive with the parent Focus 5 Float track. |
PROJECT/2-WORKING/FOCUS5-REMINDERS-PANEL.md:27:- **Server/Python path → no live write.** Phase 5.0 of the Apple Reminders plan proved EventKit writes are TCC-suppressed under the VS Code/agent responsible process tree, so the server can only write via the separate signed helper + `rebalance apple-reminders` CLI (deliberately human-in-the-loop). Its *read* is also stale (opt-in, FDA-gated sync — the documented "freshness gap").
PROJECT/1-INBOX/PHASE-0-SPIKE.md:49:| Query / Retrieval / Synthesis | Renaming or reshaping any QueryResult field (or the nested temporal_context / github_*_context row shapes) silently breaks BOTH the MCP `ask` tool (retrieval.py re-serializes every field by name) and `rebalance ask` (cli/query.py hand-reads the same keys), with no shared serializer and no test on querier.ask itself, so the break surfaces only at runtime in agent/operator hands. | Introduce a single QueryResult.to_dict()/render helper and route retrieval.py:ask and cli/query.py:ask_cmd through it so renames fail in one place; add a querier.ask round-trip test before touching field names and keep existing field names frozen. | `python -m pytest tests/test_chat.py -v AND add tests/test_querier.py (currently ABSENT — confirmed) asserting querier.ask(...).temporal_context has today/tomorrow and github_context rows carry total_commits/prs_opened/issues_opened, before any field rename.` |
PROJECT/1-INBOX/PHASE-0-SPIKE.md:53:| Onboarding / Registry / Inference | The MCP run_preflight tool returns the raw DiscoveryResult dataclass while declared -> dict, and confirm_projects expects that exact JSON back as its `projects` arg; refactoring DiscoveryResult fields, the per-candidate dict keys (name/status/summary/repos/tags/last_activity_at), or the serialization breaks the run_preflight -> host-agent -> confirm_projects round trip silently, since confirm_and_write blindly Project.model_validate's each dict and the segment getattr depends on Registry section field names. | Pin the candidate dict schema, the model_dump(mode='json') serialization, and the Registry section-name strings as an explicit contract; add a round-trip test feeding discover_candidates output straight into confirm_and_write, and keep getattr targets enumerated against Registry fields. | `python -m pytest tests/test_project_inference.py tests/test_external_watch.py -q (covers registry sync_db/get_projects/get_external_repos round trips); NO dedicated preflight/onboarding test exists — add one asserting confirm_and_write accepts discover_candidates output before changing the discover->confirm contract.` |
PROJECT/2-WORKING/MARATHON-QUEUE-2026-06-30.md:11:  `tick` multi-agent harness on real work. Lanes are derived from the validated ROADMAP queue
PROJECT/2-WORKING/MARATHON-QUEUE-2026-06-30.md:13:  pass (lanes D-G), and scoped to verified file paths so two agents can build concurrently
PROJECT/2-WORKING/MARATHON-QUEUE-2026-06-30.md:24:| Validated the ROADMAP queue (deterministic `pdda.sh` checks all green; AI judgment pass found drift: watch-list guard done via PR #82, and items #1/#5/#6 are a phase ahead of their ROADMAP text). Defined 3 path-disjoint lanes against **verified** paths; confirmed literal-prefix disjointness. **Expanded to 7 lanes** after a same-day GitHub-issue + doc-hygiene triage surfaced 4 more small, bounded, verified-path fixes (D-G); confirmed disjoint against A/B/C and each other. Run has not started — `.tick/` holds only leftover state from the closed GH-81 relay, no `tick` binary installed yet. | Install `tick` via the `/xyz` skill (self-extracting), run the **Seed** block below, then launch 2 agents on the **Run loop**. Coordinator scores with `tick analyze`. |
PROJECT/2-WORKING/MARATHON-QUEUE-2026-06-30.md:90:tick log task.created MARATHON-A --agent dispatcher --priority 30 \
PROJECT/2-WORKING/MARATHON-QUEUE-2026-06-30.md:93:tick log task.created MARATHON-B --agent dispatcher --priority 20 \
PROJECT/2-WORKING/MARATHON-QUEUE-2026-06-30.md:96:tick log task.created MARATHON-C --agent dispatcher --priority 10 \
PROJECT/2-WORKING/MARATHON-QUEUE-2026-06-30.md:99:tick log task.created MARATHON-D --agent dispatcher --priority 8 \
PROJECT/2-WORKING/MARATHON-QUEUE-2026-06-30.md:102:tick log task.created MARATHON-E --agent dispatcher --priority 6 \
PROJECT/2-WORKING/MARATHON-QUEUE-2026-06-30.md:105:tick log task.created MARATHON-F --agent dispatcher --priority 4 \
PROJECT/2-WORKING/MARATHON-QUEUE-2026-06-30.md:108:tick log task.created MARATHON-G --agent dispatcher --priority 2 \
PROJECT/2-WORKING/MARATHON-QUEUE-2026-06-30.md:114:## Run loop (each agent, distinct --agent id e.g. claude-a / codex-b)
PROJECT/2-WORKING/MARATHON-QUEUE-2026-06-30.md:119:A=claude-a                               # the other agent uses A=codex-b
PROJECT/2-WORKING/MARATHON-QUEUE-2026-06-30.md:120:tick take --agent "$A"                   # atomic claim of the next non-overlapping lane
PROJECT/2-WORKING/MARATHON-QUEUE-2026-06-30.md:123:tick ping <TASK-ID> --agent "$A" --note "what I just did"
PROJECT/2-WORKING/MARATHON-QUEUE-2026-06-30.md:125:tick done <TASK-ID> --agent "$A" --note "acceptance: <command> green"
PROJECT/4-MISC/MAC-DASHBOARD-PORT.md:173:- [ ] Port **agent-tagged activity** classification (Claude Cloud / Codex Cloud / Lovable / local-vscode / human) — mirror [src/rebalance/agent_tags.py](../../src/rebalance/agent_tags.py)::classify
PROJECT/4-MISC/MAC-DASHBOARD-PORT.md:258:- **Phase 3 scope creep** — Phase 3 is *only* a synthesis-backend swap. If it grows to include conversation history, multi-turn tool use, agent loops, etc., split those into their own phase rather than blocking the Gemini upgrade on them.
PROJECT/4-MISC/PRIORITIZATION.md:146:- [x] `github_balance` MCP kept as-is — per-project names needed for agent queries
PROJECT/4-MISC/P1-MORNING-BRIEFING.md:80:- [~] Pipe that JSON to a one-shot Claude **Haiku** call — **blocked**: no `anthropic` SDK / `ANTHROPIC_API_KEY` / `claude` CLI in this environment. The script has the Haiku seam wired (`render_haiku`, model `claude-haiku-4-5`) and falls back to a deterministic grouped render. Synthesis was validated by an agent acting as the Haiku stand-in.
PROJECT/4-MISC/STICKIES-TO-OBSIDIAN.md:276:- Current deliverables: `stickies2obsidian.sh`, a launchd plist template, and `install_launch_agent.sh`.
PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md:207:  Done (2026-06-21): the block names huggingface.co (one-time Qwen3-Embedding-0.6B download, several hundred MB, cached), api.github.com (PAT), and accounts.google.com / *.googleapis.com (OAuth+sync), framed for egress-allowlist / agent-sandbox readers.
PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md:208:- [ ] Tie egress/platform notes into the agent-facing onboarding path. **Cut (ponytail-lite):** touching `/welcome` + `rebalance onboard` code for a sandbox blocker no one has reported yet. The README block already lets a sandboxed user self-serve the allowlist; revive when a sandboxed user actually hits a blocker.
PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md:215:- [x] An agent-sandbox user can self-serve the allowlist/remedy path from docs alone. (the README block lists the hosts; the onboarding-code wiring is the cut bullet above)
PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md:278:- [ ] ~~The repo root shows only newcomer-relevant docs plus required agent/tool files.~~ **Cut with the relocation bullets** — root sprawl left as-is (no newcomer is impeded; revisit only if that changes).
PROJECT/4-MISC/P1-MODULE-REGISTRY.md:5:> **Original status (2026-05-08):** Open proposal — written to be reviewed by another agent.
PROJECT/4-MISC/P1-MODULE-REGISTRY.md:33:**2. The drift/implicit-classification cost (original finding #5) has recurred — and now bites agents, not just docs.** Concrete evidence from 2026-05-31:
PROJECT/4-MISC/P1-MODULE-REGISTRY.md:36:- An agent setting up Google Calendar had to **grep** the repo for `setup_calendar_oauth.py` because `rebalance doctor` already knew the remediation but is **CLI-only — not exposed as an MCP tool**, and `onboarding_status` doesn't check calendar OAuth. The right knowledge existed in one enumeration (doctor) and was unreachable from the surface the agent is told to use (MCP). That is exactly the "data wanting to be a field / fanout drift" failure, now manifesting as an agent dead-end rather than a stale doc.
PROJECT/4-MISC/P1-MODULE-REGISTRY.md:46:| "Premature at N=1 drift" | **Resolved.** Drift recurred (4-way re-enumeration + the calendar-OAuth agent dead-end). Finding #5 (implicit classification) is now load-bearing, as predicted. |
PROJECT/4-MISC/P1-MODULE-REGISTRY.md:62:- `doctor` — iterate `COLLECTORS`, call each `health_check`; expose as a new MCP `health_check()` tool so MCP-first agents reach remediation hints (closes the calendar-OAuth gap).
PROJECT/4-MISC/P1-MODULE-REGISTRY.md:133:- Catches drift created by humans, agents, or merges from forks — anything ending up on disk gets seen.
PROJECT/4-MISC/P1-MODULE-REGISTRY.md:160:- Future agents (Codex, Copilot, Claude) can read the registry as a structured handle on the module surface, reducing "what modules exist?" rediscovery.
PROJECT/4-MISC/P1-MODULE-REGISTRY.md:193:- Relies entirely on human (or agent) discipline. If the 8-step SOP didn't catch pulse_web, a 9-step SOP probably won't either.
PROJECT/4-MISC/P1-MODULE-REGISTRY.md:265:The mistake worth avoiding is shipping B first because it's the most "complete" answer, then discovering six months later that the abstraction it locks in doesn't fit the next module class (e.g., a streaming ingestor, or a write-back agent), and now there's a registry + a workaround for the registry. C → A → maybe-B keeps every step cheap and reversible.
PROJECT/4-MISC/APPLE-REMINDERS.md:16:  - Phase 0 must prove path discovery, read-only access, field coverage, and launchd/agent permissions
PROJECT/4-MISC/APPLE-REMINDERS.md:29:| Phase 0 probe run on 2026-06-05. Confirmed the modern Reminders store root exists on this Mac, but the agent runtime gets `PermissionError` on the `Stores` directory even outside the workspace sandbox. | Grant the host runtime Full Disk Access or run the spike from a terminal/runtime that already has access, then rerun `bash scripts/apple_reminders.sh`. |
PROJECT/4-MISC/APPLE-REMINDERS.md:66:   (interactive shell, agent-hosted process, and ideally launchd).
PROJECT/4-MISC/APPLE-REMINDERS.md:86:- "Works in Terminal" is not enough. rebalance also relies on agent-hosted and
PROJECT/4-MISC/APPLE-REMINDERS.md:191:- The agent runtime can list `~/Library` and `~/Library/Group Containers`.
PROJECT/4-MISC/AUTH-AND-API-KEY-STORAGE-HARDENING.md:140:Gmail runs in one of two modes: `oauth` or `mcp`. In `oauth` mode, rebalance loads a desktop OAuth token from keyring with a launchd-safe fallback token file, fetches the newest 100 messages matching `gmail_query_filter` (default `in:inbox`), and stores metadata plus Gmail's snippet into `email_messages`; the collector does not parse MIME bodies yet. In `mcp` mode, the scheduled job does nothing and an agent is expected to ingest messages through the Gmail MCP connector instead. Email also participates in the unified semantic index, but only through the stored metadata/snippet layer today.
PROJECT/2-WORKING/MARATHON-QUEUE-2026-07-01.md:23:| **Both lanes RAN and closed 2026-07-01** (2 concurrent agents via `tick`, work-bounded concurrency ~51%, 0 parked-claim suspects, 0 cross-lane writes). **MARATHON-A** (Focus5Native Phase 0-R) — sandboxed re-spike PASSED: all 10 QA gates observed in a codesigned App-Sandbox `.app`; `Process`→git empirically blocked, in-process libgit2 returns the full typed fact set, bookmark round-trip verified; key finding = SwiftGit2 SPM is iOS-only so a macOS-sliced libgit2 is a Phase 2 cost (evidence: `macOS/Apps/Focus5Native/PHASE-0-R-FINDINGS.md`). **MARATHON-B** (Signal-quality contract) — GH #101 opened, doc promoted to `PROJECT/2-WORKING/GH-101-SIGNAL-QUALITY-CONTRACT.md`, ROADMAP pointer parked, Phase 0 spike run (freshness-derivation cites confirmed; one REFUTED: `payload["freshness"]` is overwritten by the semantic-drift dict at index_ops.py:385, folded into Phase 2). Coordinator applied A's cross-lane doc updates to `FOCUS-5-APP-STORE.md`. | Operator litmus sweep (below) — the remaining ROADMAP items need human GUI/TCC checks, not agent lanes. Both project docs now point to their next phase (App Store → Phase 1; Signal-quality → Phase 1). |
PROJECT/2-WORKING/MARATHON-QUEUE-2026-07-01.md:50:Per the Apple Reminders TCC findings, no CLI agent can satisfy a LaunchServices-launched GUI litmus, so these are operator tasks:
PROJECT/2-WORKING/MARATHON-QUEUE-2026-07-01.md:77:tick log task.created MARATHON-A --agent dispatcher --priority 30 \
PROJECT/2-WORKING/MARATHON-QUEUE-2026-07-01.md:80:tick log task.created MARATHON-B --agent dispatcher --priority 20 \
PROJECT/2-WORKING/MARATHON-QUEUE-2026-07-01.md:86:## Run loop (each agent, distinct --agent id e.g. claude-a / codex-b)
PROJECT/2-WORKING/MARATHON-QUEUE-2026-07-01.md:91:A=claude-a                               # the other agent uses A=codex-b
PROJECT/2-WORKING/MARATHON-QUEUE-2026-07-01.md:92:tick take --agent "$A"                   # atomic claim of the next non-overlapping lane
PROJECT/2-WORKING/MARATHON-QUEUE-2026-07-01.md:95:tick ping <TASK-ID> --agent "$A" --note "what I just did"
PROJECT/2-WORKING/MARATHON-QUEUE-2026-07-01.md:97:tick done <TASK-ID> --agent "$A" --note "acceptance: <command> green"
PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md:8:status: "Phase 2 v0.5 BUILT on `development` (shared rank_next_actions core + /whats-next route + static pulse panel + ask() parity + precompute hook; 3 commits f6a7131→795933c; 989 tests green; 30-agent adversarial review applied) — data-layer DoD proven; pending live-Gemini visual check in Noel's keyed env + merge-to-main + v0.5 tag"
PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md:49:| **Phase 2 v0.5 BUILT on `development` (Ultra Code, 2026-06-18)** — the "What should we work on next?" feature shipped across all four surfaces, all calling ONE shared `rank_next_actions` core (the DRY parity gate): the keystone [next_actions.py](src/rebalance/ingest/next_actions.py) (productizes the Phase-0 harness blend + dedup; Gemini via the existing `_synthesize_with_fallback` adapter; never raises; deterministic ranked fallback) + migration 0006 (`ranked_next_actions` local-only precompute cache, head v6); the `/whats-next` FastAPI route (live on `rebalance serve` **and** the always-running `pulse_server`); the static `pulse.html` "what's next" panel (reads the precompute, offline launchd-safe); `ask(team=True)` MCP parity (sidecar attr, `QueryResult` untouched); and the network-allowed precompute hook in `refresh_index`. **Scope decisions (Noel):** static panel = precompute→SQLite; teammates = Matt-first with a per-person additivity gate (sparse Jose/Jinhui earn in by logging density). **One Ultra adversarial review** (30 agents → 14 verified findings + a synthesis-prompt judge panel) applied — incl. the HIGH fix where a degenerate Gemini parse could overwrite the good deterministic fallback. **989 tests green** (+71 over Phase 1), `rebalance doctor` clean. **Data-layer DoD proven**: blended rank surfaces 7 net-new person-attributed teammate items the operator-only list lacks. 3 commits `f6a7131`→`34e60da`→`795933c` on `development`. | **Final v0.5 close-out:** (1) Noel opens `/whats-next?refresh` (or runs a full `refresh_index`) in his **keyed** env to render the live Gemini-synthesized list — the visual DoD that can't run in the sandbox (no GSM key there); (2) merge `development` → `main` via self-mergeable PR + tag **v0.5**. The `rebalance-git-pulse` refactor ([GIT-PULSE-REFACTOR.md](PROJECT/2-WORKING/GIT-PULSE-REFACTOR.md)) remains unblocked. |
PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md:117:`pulse.html`), with `ask` parity for agents. Phase 0 proves the signal earns it; Phase 1
PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md:294:Rule of thumb: **build sequential/stateful things single-agent at high effort; fan out
PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md:295:(Ultra Code sub-agents) only when surfaces are independent (build) or adversarial review
PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md:300:| **Phase 0 remainder** (votes, reveal, scoring, exit artifact) | **Sonnet High — single agent** | Sequential, stateful bookkeeping over a live DB and *sealed* judge files; extra agent contexts only add blind-integrity risk, not quality. |
PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md:301:| **Phase 1 implementation** (migration, config, refresh, read side, Gemini wiring) | **Sonnet High — single agent** | A numbered schema migration is inherently sequential; small diff surface; correctness over breadth. |
PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md:302:| **Phase 1 pre-merge review** | **Ultra Code (sub-agents)** | The export filter is the privacy-critical seam — adversarial multi-agent review (`/code-review ultra` + security pass over `export_calendar_snapshot` and the migration) before ship. |
PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md:303:| **Phase 2 v0.5 build-out** (web.py route, pulse.html panel, `ask` parity, synthesis prompt) | **Ultra Code (sub-agents)** | Four largely independent surfaces — parallel implementation in isolated worktrees, plus a judge panel on the Gemini synthesis prompt; fan-out buys real wall-clock and quality here. |
PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md:304:| **Phase 2 integration + polish + v0.5 tag** | **Sonnet High — single agent** | Single-context integration of the parallel pieces; one final Ultra review pass before tagging v0.5. |
PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md:344:- **DONE (2026-06-17):** merged `development` → `main` and pushed (`aa362cb`, 0.40.2). `/phase-qa` gate (50468f7), scoped privacy-seam QA + cross-model consult, F1 literal unification (0.40.1), and `person`-omission regression tests (0.40.2) all landed — see below. Phase 1 fully closed.
PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md:346:### Phase 1 hardening — privacy-seam QA + cross-model consult (2026-06-17, 0.40.1)
PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md:351:two-model **`/consult`** (Codex + Gemini, repo-isolated worktree). All three reads converged:
PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md:373:- Raw consult transcripts: `relay-system/2026-06-17/privacy-seam-192658/` (Codex + Gemini).
PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md:374:- **Test hardening (0.40.2):** a re-run of the consult hand-off re-confirmed the seam at HEAD
PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md:410:- [x] **SOLID + DRY gate (DONE via the Ultra adversarial review):** the doc's execution-mode table called for an Ultra adversarial review for this phase; that 30-agent pass (privacy-leak hunt + correctness + dedup/parse + SOLID/DRY dimensions, each finding skeptic-verified, + a synthesis-prompt judge panel) **is** the SOLID/DRY gate — 14 findings verified and fixed (`795933c`). Checklist below filled from its evidence (a separate `/phase-qa` re-review would re-cover already-reviewed-and-tested code).
PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md:412:### QA Checklist — Phase 2 *(completed 2026-06-18 via the 30-agent Ultra adversarial review; all SOLID/DRY items confirmed in code)*
PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md:446:  pushed there are not publicly exposed. Future agent sessions: this is a known, accepted state —
PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md:521:- **Execution-mode policy documented** ([standing constraints](#execution-modes--ultra-code-vs-sonnet-high-decided-2026-06-12)): Sonnet High single-agent for Phase 0 remainder + Phase 1 implementation + Phase 2 integration; Ultra Code sub-agents for Phase 1 pre-merge review and the Phase 2 v0.5 parallel build-out.
PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md:549:**Phase 0 closed.** Either outcome was a successful spike; this one is a GO. Phase 1 begins (Sonnet High, single agent).
PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md:571:- **Migration 0005 written, then run through a 4-dimension adversarial review workflow** (Ultracode; 25 agents, 21 findings, **16 confirmed**):
PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md:587:- **Consumers fanned out (commit `34e60da`, 4 parallel agents on disjoint files + integration):** `/whats-next` FastAPI route (`web.py` + nav + `pulse_server` re-registration; reads precompute, recomputes live + persists + 303 on `?refresh`); static `render_work_next` panel in `pulse_web.py` (reads precompute, offline-safe); `ask(team=True)` parity (sidecar attr — `QueryResult` untouched — + `next_actions` MCP key); `refresh_index` precompute hook (network-allowed, gated to full refresh, try/except so it never breaks a sync). Cross-surface parity test added.
PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md:588:- **Ultra adversarial review (commit `795933c`, 30 agents → 14 verified findings + a synthesis-prompt judge panel scoring 5.7/10):**
PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md:662:sweep (offline-eval data for the ranker/dropped-ball detector) is still out with the agents.
PROJECT/2-WORKING/P2-MACOS-FOCUS5-FLOAT.md:55:- [make-app.sh](../../macOS/make-app.sh) — `swift build -c release` → assembles `.app`, writes `Info.plist`, ad-hoc `codesign --force --deep`, installs to `/Applications`. **Adapt (new bundle id, exec name, `LSUIElement` for menu-bar agent).**
PROJECT/2-WORKING/P2-MACOS-FOCUS5-FLOAT.md:90:| `make-app.sh` | **Adapt** | New bundle id, exec name, add `LSUIElement=true` for menu-bar agent. |
PROJECT/2-WORKING/P2-MACOS-FOCUS5-FLOAT.md:225:- [x] **Litmus (E2E):** Live `rebalance serve` → `/focus-5.json` and the Swift client both return the **same 5 repos as the browser `/focus-5`** (rebalance-OS, sleuth-app, EOS-daily-skill, fast-key-replacement-macos, xyz-3-agents-swarm). git-commit-reflected-after-refresh: operator glance.
PROJECT/2-WORKING/P2-MACOS-FOCUS5-FLOAT.md:234:- [~] App icon — **wiring done, artwork pending.** `make-app.sh` auto-picks `Resources/AppIcon.icns` and sets `CFBundleIconFile` when present; menu-bar agent has no Dock icon, so this only affects Finder/Spotlight. Artwork in progress (Figma Make). Drop the exported `.icns` and re-run `make-app.sh`.
PROJECT/2-WORKING/P2-MACOS-FOCUS5-FLOAT.md:249:- [~] **Litmus (ship):** installed build runs as a menu-bar agent with live data. _Operator: run it for a day across `rebalance serve` restarts + a logout/login._
PROJECT/1-INBOX/P1-SQLITE.md:33:- Higher-quality retrieval for local agents
PROJECT/1-INBOX/P1-SQLITE.md:340:Objective: expose the history layer to agents without requiring direct file parsing.
PROJECT/4-MISC/PLUGINS.md:127:  agent runtime can't read the Reminders `Stores` dir). Unblock = grant the host
PROJECT/2-WORKING/MARATHON-2026-06-27.md:36:(see [§Verify & archive](#verify--archive-sweep-operator-not-agent)).
PROJECT/2-WORKING/MARATHON-2026-06-27.md:82:## Verify & archive sweep (operator, not agent)
PROJECT/2-WORKING/MARATHON-2026-06-27.md:85:eyeball the result. Per the Apple Reminders TCC findings, **no CLI agent can
PROJECT/2-WORKING/MARATHON-2026-06-27.md:87:loop sessions. The repo moves (`git mv … 3-COMPLETED`) an agent can do once you

exec
/bin/zsh -lc "nl -ba AGENTS.md | sed -n '1,260p'" in /private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/consult-wt-21302-28772
 succeeded in 0ms:
     1	## Working with the rebalance MCP server (Codex, Gemini, Claude, others)
     2	
     3	This repo **is** an MCP server. Every refresh and query path is exposed through MCP tools — do not scan the codebase for `rebalance ...` CLI commands or write ad-hoc shell pipelines. Reach for the tools first.
     4	
     5	> ### 🧭 Start here — the central orchestrator (the data-plane spine)
     6	>
     7	> Every data source — `vault`, `github`, `calendar`, `sleuth`, `email`, `semantic` — is registered as a `Collector` in **[src/rebalance/ingest/index_ops.py](src/rebalance/ingest/index_ops.py)** (`register_collector` / `COLLECTORS`). That registry **is** the central orchestrator of the system: `refresh_index`, `index_status`, and the daily-sync cron all dispatch through it, and adding a source is one `register_collector(...)` call — no edits to the dispatch chain. **To understand or extend this system, read `index_ops.py` first.**
     8	>
     9	> - **Setup / health / "why is X empty?"** → run `rebalance doctor` (it names the exact remediation, e.g. a missing calendar OAuth token → `scripts/setup_calendar_oauth.py`). Don't grep for setup scripts.
    10	> - **Orientation** → [ARCHITECTURE.md](ARCHITECTURE.md) (Signal Sources table, Source→Table fanout, "Adding a New Source"). Read it at session start.
    11	> - **`querier.py`** is the read-side orchestrator (retrieval + synthesis); `index_ops.py` is the source/refresh orchestrator. Both consume the same source set — the direction to make `doctor`, the morning brief, and `querier` all iterate the one registry is in [PROJECT/2-WORKING/P1-MODULE-REGISTRY.md](PROJECT/2-WORKING/P1-MODULE-REGISTRY.md).
    12	
    13	**Connection.** The repo ships two equivalent configs: [.vscode/mcp.json](.vscode/mcp.json) for VS Code agents and [.mcp.json](.mcp.json) at the repo root for tools that look there. Both launch `.venv/bin/python -m rebalance.mcp_server` over stdio with `REBALANCE_DB` set to the repo's `rebalance.db`.
    14	
    15	**Single entry points (use these first):**
    16	
    17	| Tool | When to call |
    18	|---|---|
    19	| `index_status()` | "Is the data fresh?" / "What's in the DB right now?" — read-only snapshot of every source + the unified semantic index, with drift indicators |
    20	| `refresh_index(scope=[...], dry_run=?)` | "Refresh the local DB." `scope` accepts `vault` / `github` / `calendar` / `sleuth` / `semantic` / `all`. Always preview with `dry_run=True` first if scope includes `github` — that hits the GitHub API for every active project repo and can take minutes |
    21	| `semantic_query(query, sources=[...], top_k=?)` | Cross-source vector search across the unified `semantic_documents` table |
    22	| `list_watched_repos(since_days=?)` | Show the merged set of GitHub repos being monitored — project registry ∪ recent `github_activity` − ignored. Same set `refresh_index(scope=["github"])` syncs. Use this to debug coverage gaps |
    23	| `publish_pulse(dry_run=?, push=?)` | Render today's + yesterday's activity into a markdown status page and publish it to a private pulse repo. Each row tagged by source (`claude-cloud` / `codex-cloud` / `lovable` / `local-vscode` / `human`) via `src/rebalance/ingest/agent_tags.py`. Reusable: every per-user value (`github_login`, `slack_user_id`, `pulse_target_path`, `pulse_filename`, `pulse_timezone`) lives in `temp/rbos.config` |
    24	
    25	**On first interaction:** call `onboarding_status(vault_path)` to check setup state. If any steps are incomplete, walk the user through them in order. If you don't know the vault path, ask: "Where is your Obsidian vault? (absolute path)"
    26	
    27	**Onboarding flow:**
    28	
    29	1. **Check state:** `onboarding_status(vault_path)` — shows which steps are done/pending.
    30	2. **GitHub PAT:** If `github_token_set` is false, ask the user for a PAT with `repo:read` scope. Call `setup_github_token(token)`. If it returns `valid: false`, ask for a corrected token.
    31	3. **Discover projects:** Call `run_preflight(vault_path)`. Present results using friendly labels: "Most active" = `most_likely_active_projects` (last 14 days), "Semi-active" = `semi_active_projects` (15–30 days), "Dormant" = `dormant_projects` (31+ days), "Vault only" = `potential_projects`. If `github_error` is set, inform the user that GitHub discovery failed. Ask which to keep, remove, or merge. For each kept project, collect: short summary (2–3 sentences) and priority tier (1–5).
    32	4. **Confirm:** Call `confirm_projects(projects, vault_path)`. Each project dict **must** include `status: "active"`. Minimum shape: `{name, status: "active", summary, repos: [], priority_tier: int, tags: []}`.
    33	5. **Verify:** Call `list_projects()` to confirm projects are queryable.
    34	6. **Initial refresh:** Call `refresh_index(scope=["all"])` to populate the SQLite knowledge base. Use `dry_run=True` first for a preview. After it completes, `github_balance()` will return per-project commit/PR/issue counts.
    35	
    36	**Onboarding & project tools:**
    37	
    38	| Tool | Purpose |
    39	|---|---|
    40	| `onboarding_status(vault_path)` | Check which setup steps are complete |
    41	| `setup_github_token(token)` | Validate and store a GitHub PAT |
    42	| `run_preflight(vault_path)` | Discover project candidates (read-only) |
    43	| `confirm_projects(projects, vault_path)` | Write registry and sync to DB |
    44	| `list_projects(status?)` | Query projects (default: active) |
    45	| `github_balance(since_days?)` | GitHub activity per project (requires prior refresh) |
    46	
    47	**Targeted retrieval (older, per-source — still valid):**
    48	
    49	| Tool | Purpose |
    50	|---|---|
    51	| `query_notes(query, top_k?)` | Vault-only vector search (legacy `embeddings` table) |
    52	| `search_vault(keyword, limit?)` | Full-text/keyword search over vault |
    53	| `query_github_context(query, repo?, top_k?)` | GitHub-only vector search (legacy `github_embeddings`) |
    54	| `ask(query, since_days?, skip_synthesis?)` | Combined context + optional local LLM synthesis |
    55	| `github_release_readiness(repo, milestone?)` | Milestone readiness inferred from local corpus |
    56	| `github_close_candidates(repo)` | Issues likely closed by merged PRs |
    57	
    58	**Key paths:**
    59	- Registry: `{vault_path}/Projects/00-project-registry.md`
    60	- Config: `temp/rbos.config` (gitignored, repo root)
    61	- Database: resolved from `REBALANCE_DB` env var (set in `.vscode/mcp.json`)
    62	- Architecture docs: `PROJECT.md`, `MCP.md`
    63	
    64	**Background refresh.** A launchd job (`com.rebalance-os.daily-sync`) runs [scripts/daily_sync.sh](scripts/daily_sync.sh) at 6:30 AM daily and on boot. The script invokes the same `refresh_index(scope=["all"])` orchestration, so the cron and the MCP tool share one code path. If the index looks stale, check `temp/logs/daily_sync_YYYY-MM-DD.log` before manually re-running.
    65	
    66	**Hourly pulse publish.** A second launchd job (`com.rebalance-os.pulse-sync`) runs [scripts/pulse_sync.sh](scripts/pulse_sync.sh) on the hour, every hour from 6 AM to 11 PM local. It calls the same `publish_pulse()` orchestration the MCP tool exposes — render markdown, commit + push to the configured private pulse repo only when content actually changed. Logs in `temp/logs/pulse_sync_YYYY-MM-DD.log`. Install via `bash scripts/install_pulse_scheduler.sh`. Public users wanting to reuse this only need to populate the pulse keys in their own `temp/rbos.config` and point at their own private clone.
    67	
    68	**Source of truth for the orchestration:** [src/rebalance/ingest/index_ops.py](src/rebalance/ingest/index_ops.py). Only edit there if you need to change refresh behavior — the MCP wrappers in `src/rebalance/mcp/` (25 tools across 7 domain modules; `mcp_server.py` is a 5-line backward-compat shim) and `daily_sync.sh` are thin and should stay that way.
    69	
    70	**Repo coverage.** `refresh_index(scope=["github"])` no longer requires every monitored repo to be in the active project registry. It auto-merges `project_repos ∪ activity_repos` (from `github_activity`, last 14 days) and skips `github_ignored_repos`. Use `list_watched_repos()` for the canonical view. The `refresh_index` orchestration and the `pulse` renderer both consume the same set, so a repo only has to appear once for everything downstream to see it.
    71	
    72	## Communication & Documentation
    73	
    74	- Precise, concise chat replies/updates: Short as possible, detailed enough.
    75	- Reduce redundancy/duplication unless critical.
    76	- New docs: High-level TOC at top; checklist + phased format; actionable items visible. Suggest Phase 0 technical spike (1-2h max) to validate assumptions/critical paths first.
    77	- Do not create new MD/text files unless instructed or it is a new audit. Append to existing project docs.
    78	- Add things to remember to MEMORY.md
    79	- General workflow: 1-2 step ad-hoc requests to direct implementation. If 4-5 steps with multiple phases, write project MD file first.
    80	- Slight pushback OK if security/maintainability/destructive risk ahead.
    81	
    82	## UI Design
    83	
    84	- Layout follows the user's decision sequence, not the system's data structure.
    85	- Label roles at the point of action — if the user must scroll or remember context to understand what a control does, the label is missing.
    86	- Every repeated component (card, row, panel) must be self-describing without surrounding context.
    87	- Design for how the user reads, not how the data is stored or fetched.
    88	- Default to the most common action. If 80% of users will pick the same option, pre-select it — don't make the majority click what the system already knows.
    89	
    90	## Code & Architecture
    91	
    92	> For the *why* behind these rules, see [GUIDING-PRINCIPLES.md](./GUIDING-PRINCIPLES.md).
    93	
    94	- Code: DRY, SOLID; balance maintainability, performance, secure. Comply with framework security best practices.
    95	- **State Management**: Introduce FSM (Finite State Machine) if state transitions exceed 4 distinct states or more than one conditional branch per state. Document state diagram in code comments or `/docs/state-machine.md`.
    96	- **Contracts**: Designate single writer per contract/schema (API response shape, DB record structure, queue message format). Changes require review from contract owner; broadcast breaking changes immediately.
    97	- **Pipelines**: One logical pipeline per data flow whenever possible. Avoid forking/rejoining; use filters, transforms, and side effects in sequence. If pipeline needs multiple paths, use conditional routing within single pipeline, not separate pipelines.
    98	- **Collectors, sources & write paths** (see `PROJECT/2-WORKING/COLLECTOR-PATH-AND-PORTABILITY-AUDIT.md`):
    99	  - **Classify before you register.** Every scope is exactly one of: raw source / derived scan / projection / export. Only raw sources are `all`-eligible; derived/projection/export attach as named stages, never as peers in the registry.
   100	  - **One writer per table.** Only the `semantic` stage writes `semantic_documents`/`semantic_embeddings`; a source writes only its own raw tables. (This is the Contracts rule above, applied to the semantic tables.)
   101	  - **Route user-facing writes through the orchestrator.** CLI, MCP, scheduler, and web write surfaces call `refresh_index` or one source-owned helper — never a leaf ingest function (`sync_*`, `ingest_*`, `embed_*`, `backfill_*`) directly.
   102	  - **Use the shared resolvers** for any new runtime path (DB, secrets, auth/token, operator config). No `Path.home()` token paths, no `parents[N]` repo-root walks, no sibling-checkout assumptions.
   103	  - **Obsidian/vault is optional output, not a control-plane dependency** — a refresh must succeed with no vault present.
   104	  - **Name settings by what they are**, not the first feature that used them (e.g. `ask_self_scan_roots` → `repo_scan_roots`).
   105	  - These are the **target contract**: the route-through-orchestrator and stage-owned-semantic rules bind *new* code; the audit owns migrating existing call sites. Enforce mechanically, not by prose — drift slipped past these same principles once already. Ship the contract tests (single-writer on the semantic tables, `all`-expansion, "no user-facing surface imports a leaf ingest fn") so a violation fails CI instead of accreting.
   106	  - **Current scope taxonomy (Phase 1, 2026-06-10)** — canonical home until `ARCHITECTURE.md` is re-segmented (it's regenerated by ask-self ingest, so not durable yet):
   107	    - **raw sources** (the `all` token): `vault`, `github`, `calendar`, `sleuth`, `email`. `figma` is a raw source but **opt-in** (needs PAT + file-key allowlist).
   108	    - **derived scans:** `code`, `focus5`, `ask_self`.  **projection:** `semantic`.  **export:** `sync`.
   109	    - **`all`** = raw sources only. **Default recipe** (no-scope `rebalance refresh` / `refresh_index(scope=None)`) = `all` + `code` + `semantic` + `sync`. Opt-in scopes (`figma`/`focus5`/`ask_self`) must be requested by name.
   110	
   111	## Anti-Patterns to Avoid
   112	
   113	- N+1 queries (e.g., loop API/DB calls; batch/paginate instead).
   114	- Unpaginated API/DB calls (always use `per_page=100`, `page` iteration).
   115	- Unbound DB queries (add `LIMIT 1000`, timeouts).
   116	- Infinite loops/recursion without bounds.
   117	- High-rate API bursts (respect GitHub 5000/hr PAT limits; sleep/retry).
   118	- Hardcoding credentials or secrets in code or config files.
   119	- Destructive operations without explicit confirmation or dry-run support.
   120	
   121	## Security & Credentials
   122	
   123	- Do not store credentials, personal/project/client names, most emails in repo unless in confirmed gitignored `/temp/` or config folder. Double-check for leaks.
   124	- Use environment variables or `.env` files (always gitignore `.env`). Never hardcode credentials.
   125	- For production integrations, reference Vault, AWS Secrets Manager, or equivalent secret storage.
   126	- Log credential usage (masked) to audit trail; log actual credential values only to secure, non-repository logs.
   127	- Mask sensitive data in logs (credentials, tokens, email addresses).
   128	
   129	## Destructive Operations
   130	
   131	- Log all DELETE/DROP/TRUNCATE operations with timestamp, user, and target to `/logs/agent-audit.json`.
   132	- Require explicit confirmation flag (e.g., `--confirm` or env var `CONFIRM_DESTRUCTIVE=true`) before executing.
   133	- Support `--dry-run` mode when applicable; output what _would_ be deleted without executing.
   134	- If operation affects >1000 rows/records, require additional confirmation or escalation.
   135	- Pause and escalate if operation is blocked or validation fails; do not retry silently.
   136	
   137	## Observability & Tests From Day One
   138	
   139	- Every new service, plugin, or pipeline ships with structured logging, health checks, and at least one integration test before merging to main.
   140	- Instrument first, optimize later. Add timing/counters to critical paths (DB queries, API calls, queue processing) at build time — retrofitting observability is 5x harder.
   141	- Log with context: every log line should include enough to trace a request end-to-end (request ID, tenant/user ID, operation name). Avoid generic messages like "error occurred."
   142	- Health check endpoints (`/healthz`, `wp-admin` heartbeat, cron verification) are not optional — they are part of the definition of done.
   143	- Write the smoke test that proves the happy path works before writing any feature code. If you can't test it, you can't ship it.
   144	- Alerts should be actionable. If a threshold fires, the runbook or next step should be obvious. No alert without a documented response.
   145	- For WordPress/WooCommerce: hook into `query_monitor` data, log slow queries (>500ms), and monitor Action Scheduler queue depth from the start.
   146	- Dashboards and log queries are deliverables, not afterthoughts. Include them in the PR or project doc alongside the code.
   147	
   148	## Testing & Mock Harnesses
   149	
   150	- Write tests _before_ integrating with external APIs. Use mock harnesses to simulate responses.
   151	- Mock harnesses should cover: happy path, rate limits (429), timeouts (504), malformed responses, and auth failures (401/403).
   152	- Store mock response fixtures in `/fixtures/` (JSON, YAML, or plaintext). Keep them realistic and versioned.
   153	- Use conditional logic or env vars (`MOCK_MODE=true`) to toggle between real and mock backends without code changes.
   154	- For external integrations (Shopify, WooCommerce, Meta Ads, GA4), create a mock server or HTTP interceptor (e.g., `nock` in Node, `responses` in Python, `http-mock` in Go).
   155	- Test both sync and async paths separately; async errors (timeouts, retries) are common blindspots.
   156	- Assert on side effects (logs, DB writes, queue messages) not just return values. Mock should verify agent behavior, not just response parsing.
   157	
   158	## Versioning & Changelog
   159	
   160	- There is no concept of "Unreleased." Every fix or feature gets a version bump at time of commit/merge.
   161	- Use semver: MAJOR for breaking changes, MINOR for features, PATCH for fixes.
   162	- Documentation-only changes do not increment version unless explicitly instructed.
   163	- Changelog entries describe _what changed and why_ in plain language. Do not include project names, filenames, or folder paths in changelog entries — those belong in `4X4.md` or project docs, not the changelog.
   164	- Format: `## [x.y.z] - YYYY-MM-DD` followed by `### Added`, `### Changed`, `### Fixed`, `### Removed` as applicable.
   165	
   166	## Monitoring & Safety
   167	
   168	- Audit deps weekly (`safety check`, Dependabot).
   169	- Rate limit APIs; exponential backoff on 429s.
   170	
   171	## Phase 0 Technical Spikes
   172	
   173	- When proposing phased work, include Phase 0 spike (1–2h max) to validate critical assumptions.
   174	- Phase 0 should test: API availability, DB connectivity, performance baseline, and blocking dependencies.
   175	- If Phase 0 surfaces blockers or contradicts assumptions, pause and escalate; do not proceed to Phase 1.
   176	- Document Phase 0 findings in spike report before committing to later phases.
   177	
   178	---
   179	
   180	## Known MCP tool gaps (as of 2026-06-02)
   181	
   182	Observed in a real session where the MCP surface was unavailable and CLI/SQLite fallbacks were used. Record here so future agents know what to work around or fix.
   183	
   184	| # | Gap | Impact | Owner action |
   185	|---|-----|--------|--------------|
   186	| 1 | **Runtime/docs sync** — AGENTS.md says "use MCP tools first" but the MCP server may not be callable at session start | Agent wastes time on MCP calls before falling back to CLI | Add a session-start connectivity check; verify tool list is live before instructing agents to prefer it |
   187	| 2 | **`semantic_query()` has no time filter** — no `since_days`, `updated_after`, or `updated_before` | Date-bounded investigations require raw SQL fallback | Add time filter to `semantic_query` MCP tool and underlying query in `src/rebalance/ingest/db/semantic.py` |
   188	| 3 | **`semantic_query()` weak filtering** — no `repo`, exact/keyword mode, or source metadata filter | Noisy recall for short/ambiguous terms | Add `repo`, `mode` (semantic/keyword), and `source` filter params |
   189	| 4 | **CLI `semantic-query` hides `updated_at`** — returned by query, stripped from output | Slows triage; requires raw SQL to see timestamps | Expose `updated_at` in the CLI table output |
   190	| 5 | ⚠️ **SECURITY: live API key surfaced in semantic results** — a vault note containing a live credential was indexed and returned by `semantic_query` | Key exposure via any agent that can call the tool | Add pre-embed redaction (strip key-shaped patterns) in `note_ingester.py` and/or a vault note exclusion mechanism (frontmatter `index: false` or path exclusion). **Fix before next vault ingest.** |
   191	
   192	---
   193	
   194	## Agent rulebooks (read before editing generated docs)
   195	
   196	Some generated artifacts in this repo ship with placeholder prose that any agent
   197	(Claude Code, Codex, Copilot, Gemini) is expected to fill in. Each has an
   198	authoritative rulebook that should be read first.
   199	
   200	| Artifact | Rulebook | Notes |
   201	|---|---|---|
   202	| Git Pulse Executive Recap (`reports/YYYY-MM-*.md`) | [experimental/git-pulse/EXEC-SUMMARY.md](experimental/git-pulse/EXEC-SUMMARY.md) | Claude Code skill `git-pulse-exec-recap` via `.claude/skills/` |
   203	| Git Pulse Team Recap (`team-reports/YYYY-MM-*.md`) | [experimental/git-pulse/TEAM-EXEC-SUMMARY.md](experimental/git-pulse/TEAM-EXEC-SUMMARY.md) | Claude Code skill `git-pulse-team-recap` via `.claude/skills/` |
   204	
   205	The generated recap itself carries the same pointer in its top-of-file instructions block, so agents that open the file directly will also find the rulebook without needing this index.
codex
**Answer**

Phase 1 should land as: `1 ADAPT`, `2 ADAPT`, `3 SKIP`, `4 SKIP`, `5 ADOPT`.

**Findings**

[Should] `Explicit 5-step loop`
Gap: gsd makes `Discuss` and `Verify` named, artifact-producing steps (`/Users/noelsaw/Documents/GH Repos/gsd-core/docs/explanation/the-phase-loop.md:23-30,51-59`); Rebalance has PDDA lifecycle buckets and QA gates, plus end-of-task `doctor`/`pytest`/`pdda` rails, but not an explicit decisions-before-plan or goal-backward verify step in the lifecycle (`PROJECT/PDDA.md:30-65`, `ROUTER.md:17-27`).
Call: `ADAPT` — target: `Reb`; effort: `S`; payoff: `2`.
Why: the seam is real, but the cheap move is to name the steps inside PDDA, not port gsd’s command stack.
First step: require a short `Decisions / Discuss` subsection before execution phases and a `Verification` subsection before phase close in phased PDDA docs.

[Nit] `Fresh-context subagents for heavy work`
Gap: gsd explicitly budgets orchestrator vs subagent context and requires artifact hand-back (`/Users/noelsaw/Documents/GH Repos/gsd-core/docs/explanation/context-engineering.md:26-42,57-66`, `/Users/noelsaw/Documents/GH Repos/gsd-core/docs/explanation/multi-agent-orchestration.md:21-27,88-119`, `/Users/noelsaw/Documents/GH Repos/gsd-core/skills/gsd-execute-phase/SKILL.md:19-33`); here the grounded counterpart is still `consult` plus ad hoc subagents with no formal context-budget or hand-back contract (`PROJECT/2-WORKING/GSD-CORE-PATTERN-REVIEW.md:343-345`).
Call: `ADAPT` — target: `both`; effort: `S`; payoff: `2`.
Why: the missing value is the hand-back discipline, not another agent framework.
First step: add a tiny required return shape to `consult` and XYZ research prompts: `what changed`, `evidence`, `open questions`, `next action`.

[Pass] `Persistent cross-session artifacts`
Gap: gsd keeps a compact `STATE.md` plus sealed per-phase `CONTEXT.md` (`/Users/noelsaw/Documents/GH Repos/gsd-core/docs/reference/state-md.md:9-15`, `/Users/noelsaw/Documents/GH Repos/gsd-core/docs/reference/context-md.md:17-18,36-49`); Rebalance instead treats the active PDDA doc as canonical project state and `snapshot.md` as session recovery (`PROJECT/PDDA.md:162-175`, `ROADMAP.md:9-23`, `/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/repo-health/snapshot/SKILL.md:14-25,27-30`).
Call: `SKIP` — target: `Reb`; effort: `L`; payoff: `1`.
Why: a new `STATE.md` would duplicate ROADMAP + project-doc state and violate the repo’s one-canonical-place discipline.

[Pass] `Parallel execution waves`
Gap: gsd groups dependency-safe plans into parallel waves (`/Users/noelsaw/Documents/GH Repos/gsd-core/docs/explanation/multi-agent-orchestration.md:88-136`); XYZ already has path-scoped lane claims and DAG ordering (`/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/skills/xyz/SKILL.md:24-33,38-60`, `/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/src/marathon-yaml.js:98-146`), and this review already found the real blocker is shared-file overlap, not missing wave semantics (`PROJECT/2-WORKING/GSD-CORE-PATTERN-REVIEW.md:203-215`).
Call: `SKIP` — target: `XYZ`; effort: `M`; payoff: `1`.
Why: central wave orchestration does not solve the actual constraint here, which is overlapping write surfaces.

[Should] `Verify-before-done gate`
Gap: gsd has a dedicated verifier that writes `VERIFICATION.md` from goal-backward checks over plans, context, and actual code (`/Users/noelsaw/Documents/GH Repos/gsd-core/docs/explanation/the-phase-loop.md:51-59`, `/Users/noelsaw/Documents/GH Repos/gsd-core/docs/reference/planning-artifacts.md:182-188`, `/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-verifier.md:15-38`); Rebalance requires `doctor`, `pytest`, PDDA checks, `phase-qa`, and `loose-ends`, but those are command/checklist sweeps rather than a routable phase-close report (`ROUTER.md:25-26`, `/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/02-plan/phase-qa/SKILL.md:16-25,207-214`, `/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/05-close/loose-ends/SKILL.md:13-22,43-45`).
Call: `ADOPT` — target: `Reb`; effort: `S`; payoff: `3`.
Why: this is the cleanest high-ROI gap; one explicit verification record closes the current “green commands, but no phase-goal verdict” hole.
First step: add a PDDA-owned `Verification summary` block for completed phases, populated from actual `doctor`/`pytest`/`pdda` results plus unmet acceptance items, and make absence of that block a phase-close failure.

**Recommendation**

Do `#5` first, then `#1`, then the light `#2` hand-back contract; skip `#3` and `#4`.
tokens used
156,209
**Answer**

Phase 1 should land as: `1 ADAPT`, `2 ADAPT`, `3 SKIP`, `4 SKIP`, `5 ADOPT`.

**Findings**

[Should] `Explicit 5-step loop`
Gap: gsd makes `Discuss` and `Verify` named, artifact-producing steps (`/Users/noelsaw/Documents/GH Repos/gsd-core/docs/explanation/the-phase-loop.md:23-30,51-59`); Rebalance has PDDA lifecycle buckets and QA gates, plus end-of-task `doctor`/`pytest`/`pdda` rails, but not an explicit decisions-before-plan or goal-backward verify step in the lifecycle (`PROJECT/PDDA.md:30-65`, `ROUTER.md:17-27`).
Call: `ADAPT` — target: `Reb`; effort: `S`; payoff: `2`.
Why: the seam is real, but the cheap move is to name the steps inside PDDA, not port gsd’s command stack.
First step: require a short `Decisions / Discuss` subsection before execution phases and a `Verification` subsection before phase close in phased PDDA docs.

[Nit] `Fresh-context subagents for heavy work`
Gap: gsd explicitly budgets orchestrator vs subagent context and requires artifact hand-back (`/Users/noelsaw/Documents/GH Repos/gsd-core/docs/explanation/context-engineering.md:26-42,57-66`, `/Users/noelsaw/Documents/GH Repos/gsd-core/docs/explanation/multi-agent-orchestration.md:21-27,88-119`, `/Users/noelsaw/Documents/GH Repos/gsd-core/skills/gsd-execute-phase/SKILL.md:19-33`); here the grounded counterpart is still `consult` plus ad hoc subagents with no formal context-budget or hand-back contract (`PROJECT/2-WORKING/GSD-CORE-PATTERN-REVIEW.md:343-345`).
Call: `ADAPT` — target: `both`; effort: `S`; payoff: `2`.
Why: the missing value is the hand-back discipline, not another agent framework.
First step: add a tiny required return shape to `consult` and XYZ research prompts: `what changed`, `evidence`, `open questions`, `next action`.

[Pass] `Persistent cross-session artifacts`
Gap: gsd keeps a compact `STATE.md` plus sealed per-phase `CONTEXT.md` (`/Users/noelsaw/Documents/GH Repos/gsd-core/docs/reference/state-md.md:9-15`, `/Users/noelsaw/Documents/GH Repos/gsd-core/docs/reference/context-md.md:17-18,36-49`); Rebalance instead treats the active PDDA doc as canonical project state and `snapshot.md` as session recovery (`PROJECT/PDDA.md:162-175`, `ROADMAP.md:9-23`, `/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/repo-health/snapshot/SKILL.md:14-25,27-30`).
Call: `SKIP` — target: `Reb`; effort: `L`; payoff: `1`.
Why: a new `STATE.md` would duplicate ROADMAP + project-doc state and violate the repo’s one-canonical-place discipline.

[Pass] `Parallel execution waves`
Gap: gsd groups dependency-safe plans into parallel waves (`/Users/noelsaw/Documents/GH Repos/gsd-core/docs/explanation/multi-agent-orchestration.md:88-136`); XYZ already has path-scoped lane claims and DAG ordering (`/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/skills/xyz/SKILL.md:24-33,38-60`, `/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm/src/marathon-yaml.js:98-146`), and this review already found the real blocker is shared-file overlap, not missing wave semantics (`PROJECT/2-WORKING/GSD-CORE-PATTERN-REVIEW.md:203-215`).
Call: `SKIP` — target: `XYZ`; effort: `M`; payoff: `1`.
Why: central wave orchestration does not solve the actual constraint here, which is overlapping write surfaces.

[Should] `Verify-before-done gate`
Gap: gsd has a dedicated verifier that writes `VERIFICATION.md` from goal-backward checks over plans, context, and actual code (`/Users/noelsaw/Documents/GH Repos/gsd-core/docs/explanation/the-phase-loop.md:51-59`, `/Users/noelsaw/Documents/GH Repos/gsd-core/docs/reference/planning-artifacts.md:182-188`, `/Users/noelsaw/Documents/GH Repos/gsd-core/agents/gsd-verifier.md:15-38`); Rebalance requires `doctor`, `pytest`, PDDA checks, `phase-qa`, and `loose-ends`, but those are command/checklist sweeps rather than a routable phase-close report (`ROUTER.md:25-26`, `/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/02-plan/phase-qa/SKILL.md:16-25,207-214`, `/Users/noelsaw/Documents/GH Repos/giant-brains-claude-skills/05-close/loose-ends/SKILL.md:13-22,43-45`).
Call: `ADOPT` — target: `Reb`; effort: `S`; payoff: `3`.
Why: this is the cleanest high-ROI gap; one explicit verification record closes the current “green commands, but no phase-goal verdict” hole.
First step: add a PDDA-owned `Verification summary` block for completed phases, populated from actual `doctor`/`pytest`/`pdda` results plus unmet acceptance items, and make absence of that block a phase-close failure.

**Recommendation**

Do `#5` first, then `#1`, then the light `#2` hand-back contract; skip `#3` and `#4`.

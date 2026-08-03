---
title: "HiQS build — marathon decomposition and operator hand-offs"
owner: Noel
gh_issue: TBA
source: "TBA"
status: "Active (2-WORKING) — created 2026-08-03. 5 marathon plans authored, none fired. M1 is preflighted and ready; M2–M5 are gated on the operator checkpoint before each."
created: 2026-08-03
updated: 2026-08-03
doc_type: project
branch: development
related:
  - PROJECT/2-WORKING/HIQS-PROJECT.md
context_tags: [hiqs, marathon, xyz, build-automation]
goal: >
  Decompose the HiQS v1.0 build into marathon plans that an XYZ builder can execute, and state
  precisely where automation stops and the operator must supply evidence. Five sequential
  marathons cover every line of the core; four operator checkpoints between them cover the
  evidence the marathons structurally cannot produce.
non_goals: >
  Not a replacement for HIQS-PROJECT.md — that doc stays canonical for the contract, the schema,
  and every QA gate. These marathons build to it. Not an attempt to automate the eval sets, the
  OAuth consent, or the device checks; those are named as hand-offs, not deferred work. No branch
  is cut and no marathon is fired by this doc.
effort: 4
complexity: 3
risk: 2
phases: 5
---

# HiQS build — marathon decomposition

## Status

| What was just completed | What's next |
|---|---|
| Five marathon plans authored and **preflighted clean** 2026-08-03 — 18 phases, `marathon.sh --dry-run` reports the full execution order for all five with no halt. Preflight earned its keep: it caught two defects that would have failed mid-run — every plan alternated reviewers internally, which `marathon-drive` refuses when the reviewer equals the builder (exit 2 at phase 2 of all five), and bare `p1`/`p2` phase ids would have collided across plans on the `MARATHON-<ID>-TURN` tick token, which is permanently spent once claimed. Phase ids are now prefixed `hiqs-mN-pN`, matching every prior marathon in this repo. Five marathon plans authored 2026-08-03 covering **every module in [HIQS-PROJECT.md](../HIQS-PROJECT.md) §11** — 18 phases across M1–M5, each with a written brief, a disjoint artifact, and a reviewer. Write-sets verified against the plan's file tree, not inferred from phase titles. The decomposition is shaped by two facts about this harness: marathons run **strictly one phase at a time** (GH-241 — `depends_on` constrains order, it does not buy parallelism), and every phase must clear a real pre-advance gate. | **Open the tracking issue on [HiQS-Suite/HiQS](https://github.com/HiQS-Suite/HiQS)**, then fire **M1 only** (`marathon.sh --plan PROJECT/2-WORKING/MARATHON-HIQS-BUILD/M1-SKELETON.yaml --pre-advance-cmd '<gate>'`). M2–M5 must not be fired ahead of their checkpoint: each depends on evidence the prior marathon cannot generate. See [Operator checkpoints](#operator-checkpoints--what-a-marathon-cannot-do). |

## The honest split: the code is buildable, the evidence is not

**Every module in §11 is marathon-able.** All 13 core files (~1,885 LOC) and the test suite are
well-specified enough for a builder agent: the dataclasses are written out verbatim in §5, the
schema in §9, the search path in §6.1, the seams in §7. There is no design work left to do.

**None of the phase-exit gates from Phase 1 onward are marathon-able.** That is not a tooling
limitation, it is the plan working as designed — HIQS-PROJECT.md's whole thesis is that evidence,
not code, is what separates it from the incumbent's 68 versions of scar tissue. The evidence is
exactly the part a builder cannot manufacture:

| Blocker | Why an agent cannot do it | Plan ref |
|---|---|---|
| `eval_queries.json` — 60–75 vault queries | Ground truth must be authored **from the operator's memory and intent** and resolved by filename/grep, *never* by running `search()`. An agent authoring queries from the index bakes the incumbent model's bias into the answer key and lets it win by construction — the precise failure §6.3 exists to prevent | §6.3 |
| `eval_ranking.json` — 20–30 daily snapshots | Requires the operator's own top-5 for real mornings, recorded **before** seeing HiQS's output, across days that have not happened yet | §7.1 |
| Reading the paired disagreement set | Explicitly the operator's read; it is the *primary* evidence, above any aggregate | §3.2, §6.3 |
| OAuth consent (Calendar) | Interactive browser flow; a headless turn cannot complete it | §11, Phase 3 |
| Keyring / TCC / launchd verification | Real-device state. A keyring write that silently no-ops still prints success — this repo has the scar | Phase 4 gate |
| One week unattended | Wall-clock observation | Phase 4 exit |
| Phase 6 disclosure scan | An agent can run the scan; deciding what counts as disclosive is a judgment on the operator's own client data | §19.2 |

So the shape is **not** one marathon start-to-finish. It is five marathons with four operator
checkpoints between them, placed exactly where the plan already requires human evidence.

## The five marathons

| Plan | Covers | Phases | Builder → Reviewer | Fires after |
|---|---|---|---|---|
| [M1-SKELETON.yaml](M1-SKELETON.yaml) | HiQS Phase 0 — foundation | 6 | codex → agy | now (preflighted) |
| [M2-VAULT-SEARCH.yaml](M2-VAULT-SEARCH.yaml) | HiQS Phase 1 — **code only** | 4 | agy → codex | M1 approved |
| [M3-GITHUB.yaml](M3-GITHUB.yaml) | HiQS Phase 2 | 2 | codex → agy | **checkpoint A** |
| [M4-ASK-MCP.yaml](M4-ASK-MCP.yaml) | HiQS Phase 3 — **code only** | 4 | agy → codex | M3 approved |
| [M5-SURFACES.yaml](M5-SURFACES.yaml) | HiQS Phase 4 — **code only** | 2 | codex → agy | **checkpoint B** |

HiQS Phase 5 has no marathon: it is trigger-gated by §14 and there is nothing to build until a
trigger fires. HiQS Phase 6 has no marathon: it is a mechanical extraction gated on "stable and
proven over several days", and its blocking gate is a disclosure judgment (§19.2).

## Operator checkpoints — what a marathon cannot do

**Checkpoint A — after M2, before M3.** The whole of HiQS Phase 1's gate.
Author `eval_queries.json` per the §6.3 protocol (from memory first, grep to resolve, drop what
you cannot locate, commit and freeze, record the SHA). Score MiniLM and Qwen3. Read the
disagreement set query by query. Check the floor and vector-leg gates. **The vector-leg gate can
delete a dependency** — if fused does not beat FTS-only by ≥10 points, torch leaves the plan and
M4/M5 change. Do not fire M3 before this: Phase 2's candidates land in a ranking whose retrieval
half is still unproven.

**Checkpoint B — after M4, before M5.** HiQS Phase 3's gate.
Complete the OAuth consent for Calendar (`hiqs auth calendar`). Accumulate 20–30 mornings of
judgments into `eval_ranking.json` — this takes **real elapsed days** and is the longest pole in
the plan. Score, then check §7.1's four gates including the 3/5 floor.

**Checkpoint C — after M5.** HiQS Phase 4's gate: install the launchd job, verify keyring by
writing and reading back in a fresh process, confirm the DB path is outside TCC-protected space,
then one week unattended.

**Checkpoint D — Phase 6.** Extraction, per §19 — and **only here**, decommissioning the incumbent.

## Should a marathon end by disabling the existing rebalance scripts?

**No — and the instinct behind the question is right, but the fix belongs in two different places.**

There is a real, machine-killing conflict. This build runs on the same machine as rebalance-OS,
which has **7 live launchd jobs**; `vault-sync` and `github-sync` both embed, and HiQS embeds every
2 h. That is **GH-172 exactly** — three concurrent embedding runs stacked to ~90 GB on a 68.7 GB
machine and the kernel panicked. The shipped guard (`flock` + memory ceiling) lives at the
*incumbent's* library leaves, and a separate HiQS process knows nothing about it. Two systems each
correctly guarding themselves is not a guard.

But **disabling the incumbent at the end of the build marathons is backwards**, for two reasons:

1. **It removes the fallback before the replacement is proven.** Decision 7 keeps rebalance-OS
   running deliberately, and §13's done-criterion is what earns the switch. M5 ends *before*
   checkpoint C — no week unattended, no keyring verification, no TCC check. Disabling the
   incumbent there means trusting a system that has passed none of its own gates.
2. **It is a destructive act in an unattended turn.** Unloading 7 launchd jobs on the operator's
   machine is precisely what a headless builder must never do.

So the split:

- **Coexistence → M5 p2 (build-time, in scope).** Shared machine-scoped embedding lock, own memory
  ceiling, schedule offset, port probe, label collision check. The installer refuses rather than
  standing a second listener beside the first. Written into
  [briefs/m5-p2-ops.md](briefs/m5-p2-ops.md) and the Phase 4 QA gate.
- **Decommission → HiQS Phase 6 (operator, at cutover).** After §13 is met, unload the 7
  `com.rebalance-os.*` jobs. Keep the plists — unload is reversible, deletion is not, and §19.4's
  archive already makes the fallback unmaintained without also making it unrecoverable.

## Why these phase boundaries

Write-sets verified against [HIQS-PROJECT.md](../HIQS-PROJECT.md) §11's file tree on 2026-08-03.
Every phase owns exactly one module plus its test file, so no two phases contend for a file.
Since marathons are serial regardless (GH-241), `depends_on` is used only where a phase genuinely
cannot start without the prior one's output — `plugins.py`'s dataclasses before anything that
imports them, `db.py`'s schema before `events.py` writes to it.

The one ordering that is **not** obvious: `plugins.py` lands first even though it is the smallest
file, because it is pure contract. Every later phase's brief cites it as the frozen shape it must
satisfy, which is what stops six independently-built modules from disagreeing about `Doc`.

## Gate command

Marathons here default their pre-advance gate to `bash <repo-root>/validate.sh`, which this repo
does not have at the HiQS level. Supply it explicitly on every run:

```bash
# M1 (builder codex, reviewer agy). ALWAYS --dry-run first.
.xyz/relay-automation/marathon.sh \
  --plan PROJECT/2-WORKING/MARATHON-HIQS-BUILD/M1-SKELETON.yaml \
  --builder codex \
  --pre-advance-cmd '.venv/bin/python -m pytest HiQS/tests -q' \
  --dry-run
```

**`--builder` is not optional and is different per plan.** `marathon-drive` refuses a phase whose
reviewer equals the builder (exit 2), and each plan pins one reviewer. Preflight caught this:
the first pass alternated reviewers *within* a plan and halted at phase 2 of all five.

| Plan | `--builder` | Reviewer |
|---|---|---|
| M1, M3, M5 | `codex` | `agy` |
| M2, M4 | `agy` | `codex` |

Alternating the pair *across* marathons is deliberate. The plan-doc relay's r1 and r2 found
different defect classes with the same reviewer; a different reviewer model per marathon is the
cheapest way to keep that divergence.

Drop `--dry-run` to fire. The gate is real, not vacuous: it fails when `HiQS/tests` does not exist,
which is correct — M1 p1's job is to create it. **Always `--dry-run` first**; it validates every
field and prints the true execution order at zero cost.

`pip install -e HiQS/` into `.venv` is a one-time operator step after M1 p1 lands, so later phases'
tests import the package rather than manipulating `sys.path`.

## Lessons Learned (For Future Agents)

*(To be filled before this doc moves to `PROJECT/3-COMPLETED/`.)*

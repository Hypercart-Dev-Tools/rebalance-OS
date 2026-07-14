---
title: "HiQS — unify all six signals into one ranked pipeline"
codename: HiQS
owner: noel@neochro.me
gh_issue: 125
source: "https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/125"
status: "Active (2-WORKING) — created 2026-07-14. Phase 0 (discovery) complete, findings written back below. Phase 2 contract decision locked against GUIDING-PRINCIPLES.md. Phase 1 next."
created: 2026-07-14
updated: 2026-07-14
branch: development
doc_type: project
goal: >
  Make HiQS (High Quality Signals) the single, named, unified work-signal pipeline: all six
  ingested sources (GitHub, vault, Calendar, Sleuth, Gmail, Figma) feed ONE bundle, which
  produces ONE ranked verdict, which EVERY surface reads. Today two independent synthesis
  surfaces disagree and three sources reach neither. Least-code method: the sources are already
  ingested and the ranker already exists — this is wiring and deletion, not new machinery.
non_goals: >
  No rename of existing packages, modules, DB tables, MCP tools, or the `rebalance ...` CLI.
  No new DB table. No new dependency. Not a re-ranker rewrite — the Gemini ranker in
  `rank_next_actions()` stays exactly as-is. Not a revert of anything already shipped under the
  superseded issues. Not a new ingest source — all six already land in SQLite.
supersedes:
  - PROJECT/2-WORKING/GH-101-SIGNAL-QUALITY-CONTRACT.md
  - PROJECT/2-WORKING/GH-115-ZAPIER-INGEST.md
  - PROJECT/2-WORKING/GH-116-VELOCITY-SIGNAL.md
  - PROJECT/2-WORKING/GH-119-HIQS-LABEL.md
  - PROJECT/1-INBOX/P1-SIGNAL.md
  - PROJECT/1-INBOX/GEMINI-WHATS-NEXT-VAULT.md
  - PROJECT/1-INBOX/EMAIL-INGEST.md
related:
  - GUIDING-PRINCIPLES.md
  - src/rebalance/ingest/index_ops.py
  - src/rebalance/ingest/next_actions.py
  - src/rebalance/ingest/pulse.py
  - src/rebalance/ingest/querier.py
  - src/rebalance/web.py
  - ARCHITECTURE.md
  - PROJECT/2-WORKING/GH-102-XYZ-REBALANCE-INTEGRATION.md
  - "https://beta.hiqs.ai"
effort: 3
complexity: 3
risk: 2
phases: 5
---

## Status

| What was just completed | What's next |
|---|---|
| **Phase 0 (discovery) complete 2026-07-14** — reverse-engineered both synthesis surfaces and confirmed the split: `ask()` sees no Sleuth/Gmail/Figma; `rank_next_actions()` sees no Gmail/Figma; Gmail + Figma reach **no** synthesis at all. Live DB counts taken (`email_messages` 124, `figma_comments` **0**). Findings written back in [Phase 0](#phase-0--discovery-complete). **Three decisions locked against GUIDING-PRINCIPLES.md** ([D1](#d1--phase-2-attaches-hiqs-as-a-first-class-field-not-a-sidecar-decided-2026-07-14) first-class `hiqs` field, not a sidecar · [D2](#d2--the-ranking-must-arrive-attested-decided-2026-07-14) rankings arrive Attested · [D3](#d3--the-dispatch-chain-gets-collapsed-not-grown) Phase 3 collapses the dispatch chain into a `candidates=` registry provider). | **Phase 1 — Complete the bundle.** Add the `email` + `figma` arms to `DayActivity` → `OperatorBundle` → `_operator_candidates()` so all six sources reach the ranker. ~40 lines, no new files. Knowingly grows the dispatch chain 6→8 arms; Phase 3 collapses it. |

---

## Table of contents

- [North star — decisions made against GUIDING-PRINCIPLES.md](#north-star--decisions-made-against-guiding-principlesmd)
- [Phase 0 — Discovery (complete)](#phase-0--discovery-complete)
- [Phase 1 — Complete the bundle](#phase-1--complete-the-bundle)
- [Phase 2 — One ranked verdict](#phase-2--one-ranked-verdict)
- [Phase 3 — Ponytail simplification & optimization pass](#phase-3--ponytail-simplification--optimization-pass)
- [Phase 4 — HiQS surface & brand](#phase-4--hiqs-surface--brand)
- [What this supersedes](#what-this-supersedes)

---

## The problem in one picture

```
                        TODAY (two surfaces, three orphans)

  GitHub ──┬─────────────────────────▶ ask()            ── "broad synthesis"
  Vault ───┤                             (querier.py)
  Calendar ┤                                ▲
           │                                │  NO sleuth, NO gmail, NO figma
           └─────────────────────────▶ rank_next_actions()  ── "/whats-next"
  Sleuth ──────────────────────────────▶   (next_actions.py)
                                            ▲
  Gmail ───▶ semantic_documents ──▶ ✗       │  NO gmail, NO figma
  Figma ───▶ semantic_documents ──▶ ✗       │
             (retrieval only —              │
              reaches no synthesis)   two surfaces, no shared code → free to drift


                        HiQS (one bundle, one verdict)

  GitHub ──┐
  Vault ───┤
  Calendar ┤
  Sleuth ──┼──▶ HiQS bundle ──▶ rank_next_actions() ──▶ persisted ranking
  Gmail ───┤   (OperatorBundle,      (Gemini, unchanged)         │
  Figma ───┘    +2 arms)                                         ├──▶ /whats-next
                                                                 └──▶ ask()
                                                    one verdict — cannot drift
```

---

## North star — decisions made against GUIDING-PRINCIPLES.md

[GUIDING-PRINCIPLES.md](../../GUIDING-PRINCIPLES.md) is the decision-making north star for this plan.
Where Ponytail ("least code") and the principles pull in different directions, the principles win —
the appendix fixes the priority order explicitly:

> **local-first > signal quality > architectural cleanliness > implementation speed and operator friction**

"Smaller diff" is *implementation speed*. It is the **lowest** priority of the four. Ponytail therefore
governs *how* we build each decision, not *which* decision we make. Three calls follow.

### D1 — Phase 2 attaches HiQS as a first-class field, not a sidecar. (Decided 2026-07-14.)

The open question was: expose the ranking on `QueryResult` as a real `hiqs` field (bump the pinned
contract + its test), or stash it on the existing `NEXT_ACTIONS_ATTR` sidecar (smaller diff, contract
untouched)?

**Decision: the first-class `hiqs` field.** The sidecar loses on three counts:

| Principle | Why the sidecar fails |
|---|---|
| **Structured** pillar — *"one shape, clean for people to read and for agents to feed on"* | A `setattr` side channel is not part of the returned shape. An MCP agent consuming `ask()` cannot discover it. That is the opposite of feedable. |
| **#5 Build durable, not band-aid** — *"removes the root cause… not a patch torn out when the obvious next feature lands"* | HiQS **is** the obvious next feature. A sidecar added today is torn out in Phase 4 when HiQS becomes the headline output. That is the definition of a band-aid. |
| **Tie-breaker** — *"Cleanliness vs friction: choose cleanliness; flag friction as a design question, not a shortcut"* | The pinned-contract test is exactly that friction. It is a design question (what does `ask()` promise?), not a reason to route around the contract. |

Bumping the pinned contract is the honest move: `ask()`'s promise genuinely changed — it now returns a
ranked verdict. The test should be updated to assert the *new* contract, not preserved to hide that.

### D2 — The ranking must arrive Attested. (Decided 2026-07-14.)

The **Attested** pillar: *"carries its receipts: source, evidence, confidence. Never a bare verdict."*
A ranked list of bare titles fails the signal bar no matter how good the ranking is. `RankedAction`
already carries `source`, `evidence`, and `why` — Phase 2 must carry those **through** into both the
`ask()` payload and the `_build_prompt()` section, and Phase 4 must render them on `/whats-next`.
A rank number with no basis is not a HiQS output.

### D3 — The dispatch chain gets collapsed, not grown. (Decided 2026-07-14.)

**This corrects the plan's own first draft.** Principle 3 — *"Add a source by registering a collector,
not by editing a dispatch chain"* — and the reject list — *"Adding a source requires editing the query
layer… (Principle 3 violation)"* — both indict `_operator_candidates()`. It is a chain of hand-written
per-source loops. Phase 1 as originally drafted would have made it **longer** (6 arms → 8).

The resolution is *sequencing*, not a bigger Phase 1:

- **Phase 1 grows the chain deliberately** (2 more arms) to prove the signal is real and worth having.
  Abstracting before the instances exist is the speculative-generality Ponytail rung-1 forbids.
- **Phase 3 collapses it** against a `candidates=` provider on the existing `Collector` descriptor —
  a direct mirror of the `semantic_docs=` provider **already** in
  [index_ops.py](../../src/rebalance/ingest/index_ops.py) (`Collector.semantic_docs`,
  `register_collector()`, `_semantic_doc_providers()`). Figma already reaches the semantic index that
  way. This is the **second use of an existing seam, not a new abstraction** — which is why it satisfies
  Principle 6 (*"prefer reusing or extending what exists over adding new"*) and Ponytail simultaneously.

After Phase 3, adding a seventh source means registering a collector with a `candidates=` provider and
touching **no** file in the query layer. That is Principle 3 satisfied, and it is where the net-LOC ≤ 0
target is paid for: eight hand-written loops collapse into one registry walk.

---

## Phase 0 — Discovery (complete)

**Status: complete 2026-07-14.** Findings written back per PDDA's discovery write-back contract.

### What was investigated

Whether any existing pipeline combines GitHub + Calendar + Gmail + Figma + Sleuth, and which signal
actually powers the `/whats-next` page.

### What was found

**1. There is no unified pipeline. There are two, and they disagree.**

| Surface | Entry point | Sources it sees | Sources it misses |
|---|---|---|---|
| Broad synthesis | [querier.py:509](../../src/rebalance/ingest/querier.py#L509) `ask()` | project registry, GitHub activity, GitHub semantic, vault, vault activity, calendar, temporal | **Sleuth, Gmail, Figma** |
| Ranked "what next" | [next_actions.py](../../src/rebalance/ingest/next_actions.py) `rank_next_actions()` | Sleuth, GitHub (items/commits/comments), calendar, vault | **Gmail, Figma** |

Verified from the outside: an `ask()` call returns keys `vault_context`, `github_context`,
`github_semantic_context`, `project_context`, `vault_activity`, `calendar_context`,
`temporal_context` — and no sleuth/email/figma key exists.
[ARCHITECTURE.md](../../ARCHITECTURE.md) concedes this: `_gather_sleuth_context()` is listed as
*future*, and `sleuth_reminders` is "mirrored but not yet gathered."

**2. `/whats-next` is powered by the `next_actions` engine, not by `ask()`.**

[web.py:1436](../../src/rebalance/web.py#L1436) `whatsnext_page()` reads a **precomputed, persisted**
ranking via `load_ranked_next_actions()` — it never ranks inline (only `?refresh=1` recomputes).
The ranking comes from `assemble_day_bundle()` → an `OperatorBundle` with exactly six fields
(`calendar_blocks`, `gh_commits`, `gh_items`, `gh_comments`, `vault_edits`, `sleuth_activity`),
plus a de-duplicated teammate calendar delta. Ranked by **Gemini 2.5-flash**, with a deterministic
local ordering as the offline fallback. Fallback priority in `_operator_candidates()`:
`sleuth(0) > gh_items(1) > calendar(2) > commits(3) > comments(4) > vault(5)`.

**3. Gmail and Figma are synthesis dead ends.** Both are ingested and projected into
`semantic_documents`, so `semantic_query()` and `chat_with_data()` can retrieve them. **No synthesis
surface reads them.** Nothing combines an email or a Figma comment with a GitHub issue to produce a
recommendation.

**4. The code already lies about this.** The module docstring at
[next_actions.py:5](../../src/rebalance/ingest/next_actions.py#L5) claims the bundle is assembled from
"calendar + GitHub + vault + sleuth + **email**". There is no email in `OperatorBundle`, none in
`_operator_candidates()`, and none in the upstream `DayActivity` it reuses. A case-insensitive grep for
`email` and `figma` across `next_actions.py` returns **zero** matches. Phase 1 makes the docstring true
rather than deleting the claim.

**5. Live data reality (this device, 2026-07-14).**

| Table | Rows | Read |
|---|---|---|
| `calendar_events` | 1573 | live |
| `github_items` | 1011 | live |
| `email_messages` | **124** | live — a real signal, currently reaching nothing |
| `sleuth_reminders` | 87 | live |
| `vault_files` | 60 | live |
| `figma_comments` | **0** | **dormant** — opt-in collector, no `figma_file_keys` allow-list configured |

### What it changes

- **Phase 1 is small and worth it.** Gmail is 124 real rows feeding nothing. Wiring it is ~2 dataclass
  fields and ~2 query blocks cloned from the existing sleuth arm.
- **Figma ships dormant, and we say so.** Building a ranking arm for a 0-row opt-in table is
  speculative (Ponytail rung 1). But Figma is an explicit product requirement, and the arm is ~8 lines
  mirroring sleuth — so we build the capability and mark it dormant with a `ponytail:` comment naming
  the trigger (a configured `figma_file_keys` allow-list), rather than pretending it is live.
- **Phase 2's shape is decided by the discovery.** `ask()` must *not* grow its own copy of the ranking
  logic — that is how the two surfaces drifted in the first place. It reads the **persisted** ranking
  (free, no model load), so there is exactly one ranked verdict in the system.
- **The `team=True` seam already exists** (`ask()` stashes next-actions on `NEXT_ACTIONS_ATTR`), but it
  *recomputes* via `rank_next_actions()` and can hit the network. Phase 2 therefore attaches the
  **cached** ranking by default and leaves `team=True` as the explicit recompute path.

---

## Phase 1 — Complete the bundle

**Goal:** all six sources reach the ranker. No new files, no new tables, no new dependency.

**Discuss:**
- Clone the existing `sleuth_activity` arm rather than inventing a new source abstraction — one more
  field in an existing dataclass is cheaper than a plugin seam, and the instances do not exist yet to
  justify one (no unrequested abstractions).
- **This deliberately grows the `_operator_candidates()` dispatch chain from 6 arms to 8, which
  Principle 3 forbids as an end state.** That is accepted *for one phase only*: prove the signal is real
  before abstracting over it. [D3](#d3--the-dispatch-chain-gets-collapsed-not-grown) commits Phase 3 to
  collapsing the chain into a registry provider. Phase 1 must not ship without Phase 3 queued behind it.
- Renumber `rank_key` classes rather than wedging in a float. Boring over clever; it is one function.
- Figma is built but dormant (0 rows). It costs ~8 lines and produces zero candidates until the
  allow-list is configured.
- Every candidate carries `source` + `evidence` + `why` from birth — the **Attested** pillar
  ([D2](#d2--the-ranking-must-arrive-attested-decided-2026-07-14)). The existing arms already do; the two
  new ones must match, not regress.

**Changes:**

1. [pulse.py](../../src/rebalance/ingest/pulse.py) — `DayActivity`: add two fields.
   ```python
   email_activity: list[dict[str, Any]] = field(default_factory=list)
   figma_activity: list[dict[str, Any]] = field(default_factory=list)
   ```
2. [pulse.py](../../src/rebalance/ingest/pulse.py) — `_query_day_activity()`: two `SELECT`s mirroring the
   sleuth block, windowed to `[start, end)` like every other arm.
   - `email_messages` → `message_id, from_name, from_address, subject, snippet, received_at`
   - `figma_comments` → `comment_key, file_key, message, user_handle, created_at`, `WHERE resolved_at IS NULL`
3. [next_actions.py](../../src/rebalance/ingest/next_actions.py) — `OperatorBundle`: same two fields;
   `assemble_day_bundle()` passes them through from the `DayActivity` it already builds.
4. [next_actions.py](../../src/rebalance/ingest/next_actions.py) — `_operator_candidates()`: two loops.
   New deterministic-fallback priority:

   | Class | Source | Why |
   |---|---|---|
   | 0 | sleuth | an open reminder someone is waiting on |
   | 1 | **email (new)** | inbound ask from a human |
   | 2 | gh_items | open issue/PR you own |
   | 3 | calendar | scheduled block |
   | 4 | gh_commits | continue / push? |
   | 5 | gh_comments | thread you engaged on |
   | 6 | **figma (new, dormant)** | unresolved design comment |
   | 7 | vault | recently edited note |

5. Fix the [next_actions.py:5](../../src/rebalance/ingest/next_actions.py#L5) docstring — it already
   claims email; make it true and add figma.

**QA gate — Phase 1:**
- [ ] `pytest tests/` green (no regression against the current 1300+ suite).
- [ ] One new test asserting an `email_messages` row in the day window produces a candidate with
      `source == "email"` (the smallest thing that fails if the wiring breaks).
- [ ] One new test asserting an empty `figma_comments` table yields **zero** figma candidates and does
      not raise — the dormant path is exercised, not assumed.
- [ ] `rebalance doctor` clean.
- [ ] Live check: `/whats-next?refresh=1` renders at least one `source=email` candidate on a device with
      inbox data, OR the absence is explained (no mail in the day window).
- [ ] **Verification summary** recorded here before close.

---

## Phase 2 — One ranked verdict

**Goal:** `ask()` and `/whats-next` read the **same** ranking. Structurally impossible to drift.

**Discuss:**
- `ask()` does **not** get its own ranking logic. It reads the persisted result. Duplicating the ranker
  is precisely the defect this phase exists to remove.
- Use `load_ranked_next_actions()` (cheap cached read, no model load), **not** `rank_next_actions()`
  (recompute, may call Gemini). Making the expensive path the default would tax every `ask()` call.
- `team=True` keeps its existing meaning: force a recompute. Out of scope to change it.
- **The contract question is settled** — see [D1](#d1--phase-2-attaches-hiqs-as-a-first-class-field-not-a-sidecar-decided-2026-07-14).
  The `NEXT_ACTIONS_ATTR` sidecar is **rejected**: it fails the Structured pillar and is a band-aid
  under Principle 5. `ask()`'s promise genuinely changed, so the pinned contract is bumped, not hidden.

**Changes:**

1. [querier.py](../../src/rebalance/ingest/querier.py) — one new gatherer, ~6 lines. It returns the
   **attested** shape (rank + title + source + evidence + why), never bare titles ([D2](#d2--the-ranking-must-arrive-attested-decided-2026-07-14)):
   ```python
   def _gather_hiqs_context(database_path: Path) -> list[dict[str, Any]]:
       """The persisted HiQS ranking — the ONE ranked verdict. Cheap read, never recomputes."""
       from rebalance.ingest.next_actions import load_ranked_next_actions
       return [asdict(a) for a in load_ranked_next_actions(database_path).actions]
   ```
2. [querier.py](../../src/rebalance/ingest/querier.py) — `_build_prompt()`: one labelled section
   (`## HiQS — ranked next actions`) carrying each action's receipts, so the synthesis sees the same
   attested ranked signal the dashboard shows.
3. **`QueryResult` gains a first-class `hiqs` field.** The existing docstring pins the operator-flow
   `QueryResult` as "byte-identical" when `team` is unset. **That pin is deliberately bumped** and its
   test updated to assert the *new* contract — `ask()` now returns a ranked verdict, and the test should
   state that rather than preserve a shape that no longer describes the function. Record the bump in
   `CHANGELOG.md` (it is a visible contract change for MCP callers).

**QA gate — Phase 2:**
- [ ] A test asserts the ranking `ask()` returns is **the same object** the `/whats-next` route reads
      (same persisted rows) — the anti-drift invariant, expressed as a test.
- [ ] A test asserts `ask()` does **not** call `rank_next_actions()` (no recompute, no network) on the
      default path.
- [ ] A test asserts every returned action carries `source` **and** non-empty `evidence` — the
      **Attested** pillar as an executable check, not a promise.
- [ ] `ask()` on a brand-new/never-ranked DB degrades to an empty ranking without raising.
- [ ] The pinned-`QueryResult` test is **updated, not deleted** — it must assert the new shape.
- [ ] `pytest tests/` green · `rebalance doctor` clean.
- [ ] **Verification summary** recorded here before close.

---

## Phase 3 — Ponytail simplification & optimization pass

**Goal:** the consolidation pays for itself. Delete more than Phases 1–2 added, and resolve the
gated/stalled scope inherited from the superseded issues instead of letting it rot.

**Discuss:**
- This is the phase that makes "least amount of new code" a *measured claim*, not a vibe. Net LOC is
  reported, not asserted.
- Inherited gates get a verdict — build, defer, or kill — rather than staying "gated" forever.
- **The headline deliverable is item 0 below** — collapsing the dispatch chain. Everything else in this
  phase is ordinary cleanup; item 0 is what discharges the Principle 3 debt Phase 1 knowingly took on.

**Changes (audit, then act):**

0. **Collapse `_operator_candidates()` into a registry provider — the Principle 3 fix ([D3](#d3--the-dispatch-chain-gets-collapsed-not-grown)).**
   Add a `candidates=` provider to the existing `Collector` descriptor in
   [index_ops.py](../../src/rebalance/ingest/index_ops.py), mirroring the `semantic_docs=` provider that
   already lives there (`Collector.semantic_docs` → `_semantic_doc_providers()` → the semantic stage).
   Each source then **owns** its own candidate shape, registered at `register_collector(...)` time:

   ```python
   # existing seam, second use — not a new abstraction
   register_collector(Collector("email", _email_adapter, candidates=_email_candidates))
   ```

   `_operator_candidates()` becomes a walk over the registry (`_candidate_providers()`), and the eight
   hand-written per-source loops are **deleted**. Acceptance: adding a hypothetical seventh source
   requires **zero** edits to `next_actions.py` or `querier.py` — prove it with a test that registers a
   fake collector and asserts its candidates reach the ranking.

   *Ordering note:* this is deliberately **after** Phases 1–2, not before. The seam is justified by
   eight real instances, not by anticipation — which is what makes it reuse rather than speculation.

1. **Kill the stale `ARCHITECTURE.md` note.** The "future: `_gather_sleuth_context()` … not yet
   gathered" line is resolved by Phase 2. Update the Query Layer section and the Next Actions section
   to describe HiQS as the one pipeline. `audit_modules` gates this — ARCHITECTURE.md is load-bearing.
2. **GH-115 (Zapier) remaining scope → deferred/killed.** Phases 2–3 were "email & calendar ingest via
   Zapier." Native OAuth already supplies both (124 emails, 1573 events). Building a second ingest path
   for signals we already have is the definition of speculative. **Keep** the shipped webhook receiver
   (`POST /api/zapier/ingest`); **delete** the placeholder `zapier_email.py` / `zapier_calendar.py`
   stubs unless they carry logic. Revisit trigger: native OAuth proves unreliable on a device.
3. **GH-116 (velocity) Phase 2 → resolved.** `compute_deep_work_signals()` already ships and is already
   *in* `next_actions.py`. Fold its output in as a candidate arm (it is already at the right seam) or
   record an explicit kill. No third state.
4. **GH-101 (source health) Phase 3 → resolved.** Phases 1–2 shipped (`recent_row_count_7d`, freshness
   status/reason, doctor warnings). Phase 3 was kill-gated on "does Phase 2 catch a real defect in live
   use." Discovery already gives evidence: doctor correctly flagged `figma` as stale/empty — which this
   plan then acted on. Record the verdict.
5. **Duplicate-gatherer audit in `querier.py`.** With the HiQS ranking attached, check whether any
   `_gather_*` function is now redundant work for the prompt. Delete what no longer earns its tokens.
6. **Measure.** Report `git diff --stat` net lines across Phases 1–3.

**QA gate — Phase 3:**
- [ ] **Principle 3 discharged:** a test registers a *fake* collector with a `candidates=` provider and
      asserts its rows reach the ranked output — with **zero** edits to `next_actions.py` / `querier.py`.
      This is the executable form of "extend by addition, not by editing a dispatch chain."
- [ ] **Net LOC across Phases 1–3 is ≤ 0** (deletion pays for the wiring), or the overage is explicitly
      justified in one line here. Report `git diff --stat` against the Phase-0 baseline.
- [ ] Every inherited gate (GH-101 Ph3, GH-115 Ph2–3, GH-116 Ph2) has a recorded verdict —
      **build / defer / kill** — with a revisit trigger. No item left "gated".
- [ ] No behavior regression: `pytest tests/` green · `rebalance doctor` clean · `/whats-next` renders.
- [ ] `audit_modules` clean (ARCHITECTURE.md in sync) · `pdda.sh run` clean.
- [ ] **Verification summary** recorded here before close.

---

## Phase 4 — HiQS surface & brand

**Goal:** the name lands where it is true. HiQS is the *pipeline*, not a sticker.

**Scope decision (2026-07-14):** *label + exactly one new internal seam name.* No rename of existing
packages, modules, DB tables, MCP tools, or the `rebalance ...` CLI — that churn buys no behavior. The
**one** new unified thing earns the name.

**Discuss:**
- GH-119 originally scoped HiQS as a label with an explicit "no code identifier" non-goal. That made
  sense when HiQS was marketing. It is now the system, so the *new* seam is named HiQS and everything
  pre-existing keeps its name. One name, one place, zero migration.

**Changes:**

1. **Code (one seam only):** `HiQSBundle` as the name of the completed six-source bundle in
   `next_actions.py` (alias or rename of `OperatorBundle` — internal, no external caller). Nothing else
   in code changes name.
2. **User-facing:** the `/whats-next` page presents its ranking as **HiQS — High Quality Signals**, with
   the tagline *"Turn workplace noise into high-quality signal."* Each row renders its **receipts**
   (source + evidence + why), not a bare rank — the **Attested** pillar is a UI requirement, not just a
   data one ([D2](#d2--the-ranking-must-arrive-attested-decided-2026-07-14)).
2b. **Fix the casing drift.** [GUIDING-PRINCIPLES.md](../../GUIDING-PRINCIPLES.md) line 3 currently reads
   **"HiQs"** (lowercase `s`) while everything else says **"HiQS"**. Trivial, but it is the north-star
   doc and the brand is now the system name — normalize to `HiQS` repo-wide as part of this pass.
3. **README:** one short section — HiQS is the signal engine; rebalance-OS is the HiQS **Rebalance
   (prioritize)** component (Sleuth = capture, Forge = coordinate; see `https://beta.hiqs.ai`).
4. **ARCHITECTURE.md:** the Query Layer + Next Actions sections name HiQS as the unified pipeline and
   carry the six-source diagram from this doc.
5. Absorbs GH-119's surface inventory. Its Phase 0 "label-lock" is satisfied by this section.

**QA gate — Phase 4:**
- [ ] `rg -i hiqs` shows the name only in: the one code seam, README, `/whats-next`, ARCHITECTURE, and
      `PROJECT/**`. No stray rename of a table, tool, or CLI command.
- [ ] `audit_modules` clean (ARCHITECTURE.md stays in sync — it is load-bearing, PDDA-gated).
- [ ] `pytest tests/` green · `pdda.sh run` clean.
- [ ] **Verification summary** recorded here before close.

---

## What this supersedes

**Nothing already shipped is reverted.** These four issues each landed real code; this plan absorbs
only their *unfinished* scope, which had started to overlap.

| Issue | Doc | Shipped — **keep** | Remaining scope — **absorbed here** |
|---|---|---|---|
| [#101](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/101) | GH-101-SIGNAL-QUALITY-CONTRACT.md | Ph1–2: `recent_row_count_7d` on all 8 sources; freshness `status`/`reason`; doctor warnings | Ph3 (kill-gated) → Phase 3 verdict |
| [#115](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/115) | GH-115-ZAPIER-INGEST.md | Ph1: `POST /api/zapier/ingest`, `GET /api/zapier/health`, Basic-Auth | Ph2–3 (email/calendar via Zapier) → Phase 3 defer/kill; native OAuth already covers both |
| [#116](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/116) | GH-116-VELOCITY-SIGNAL.md | Ph1: `compute_deep_work_signals()`, doctor "deep work" line | Ph2 (fold into ranking) → Phase 3 |
| [#119](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/119) | GH-119-HIQS-LABEL.md | *nothing fired* | entire brand pass → Phase 4, rescoped: HiQS is the system |

Inbox drafts also superseded: `P1-SIGNAL.md` (the original "one operator signal" thesis — this plan is
its execution), `GEMINI-WHATS-NEXT-VAULT.md` (shipped; the ranker and vault file exist),
`EMAIL-INGEST.md` (Phase 1 shipped; its "reaches no consumer" gap is this plan's Phase 1).

**Explicitly NOT superseded:** [GH-102 XYZ ⇄ Rebalance integration](GH-102-XYZ-REBALANCE-INTEGRATION.md)
— a different seam (cross-repo integration, not signal unification). Focus 5 and the health issues are
likewise untouched.

**Naming collision resolved.** `GH-101` carried `codename: HiQS` in its frontmatter while `GH-119`
claimed HiQS as a marketing label for the ranked signal. Both are retired into this doc, which is now
the single owner of the name: **HiQS = the unified six-source ranked work-signal pipeline.**

---
title: "HiQS — unify all six signals into one ranked pipeline"
codename: HiQS
owner: noel@neochro.me
gh_issue: 125
source: "https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/125"
status: "Active (2-WORKING) — created 2026-07-14. Phases 0–3 complete (Phases 1–3 built in Claude Code Cloud, reviewed + corrected + verified against real signal data locally 2026-07-14). Phase 4 (HiQS surface & brand) next."
created: 2026-07-14
updated: 2026-07-14
branch: claude/gh-125-hiqs-pipeline-eo7rzf
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
| **Phases 1–3 shipped and locally verified 2026-07-14.** All six sources now reach one bundle → one ranked verdict → read by every surface. `ask()` exposes it as a first-class `hiqs` field read from the persisted cache ([D1](#d1--phase-2-attaches-hiqs-as-a-first-class-field-not-a-sidecar-decided-2026-07-14)), so no surface computes its own ranking and `/whats-next` and `ask()` cannot show *different* rankings ([precise invariant](#phase-2--one-ranked-verdict) — tightened after QA; "single writer" was an overclaim). The dispatch chain is collapsed into a `candidates=` registry walk — **Principle 3 discharged**, pinned by a fake-collector test ([D3](#d3--the-dispatch-chain-gets-collapsed-not-grown)). Built in Claude Code Cloud (no DB/credentials); **reviewed, corrected, and run against real signal data locally** — which surfaced an upstream Gmail-ingest defect and a signal-quality hole, both now fixed//recorded (see [Local verification](#local-verification-against-real-signal-data-2026-07-14)). `pytest` 1362 passed, 2 pre-existing failures unchanged. | **Phase 4 — HiQS surface & brand.** Also: open a follow-up issue for the [Gmail-ingest header defect](#local-verification-against-real-signal-data-2026-07-14) (119 of 124 rows are contentless shells — out of scope here: GH-125 *consumes* email, it does not ingest it). |

---

## Table of contents

- [North star — decisions made against GUIDING-PRINCIPLES.md](#north-star--decisions-made-against-guiding-principlesmd)
- [Phase 0 — Discovery (complete)](#phase-0--discovery-complete)
- [Phase 1 — Complete the bundle](#phase-1--complete-the-bundle)
- [Phase 2 — One ranked verdict](#phase-2--one-ranked-verdict)
- [Phase 3 — Ponytail simplification & optimization pass](#phase-3--ponytail-simplification--optimization-pass)
- [Phase 4 — HiQS surface & brand](#phase-4--hiqs-surface--brand)
- [Local verification against real signal data](#local-verification-against-real-signal-data-2026-07-14)
- [Decisions recorded during build](#decisions-recorded-during-build)
- [Follow-ups this issue creates](#follow-ups-this-issue-creates-do-not-lose)
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
                                        one ranking — no surface computes its own
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
| `email_messages` | **124** | live — a real signal, currently reaching nothing. ⚠️ **Corrected 2026-07-14 after local verification: only 5 of these 124 rows carry content.** See [Local verification](#local-verification-against-real-signal-data-2026-07-14). |
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
- [x] `pytest tests/` green — 1362 passed, 2 pre-existing failures (`test_pulse_self_repair` ×2)
      confirmed unchanged on `development`, so zero regression.
- [x] Test: an `email_messages` row in the day window produces a `source == "email"` candidate.
- [x] Test: an empty `figma_comments` table yields **zero** figma candidates and does not raise;
      a present **unresolved** comment DOES surface, a **resolved** one does not.
- [x] Test: every ranked action carries `source` + non-empty `evidence` — Attested ([D2](#d2--the-ranking-must-arrive-attested-decided-2026-07-14)).
- [x] **Test (added at local review): a contentless email row is never ranked.** See
      [Local verification](#local-verification-against-real-signal-data-2026-07-14).
- [x] Live check: run against the **real DB**. `_query_day_activity` executes cleanly on the real
      schema (all six guessed column names correct). **Zero `source=email` candidates today, and the
      absence is explained**: the newest content-bearing email in the DB is 2026-05-22 — the Gmail
      collector has landed no usable row in 7 weeks. Not a wiring failure; see below.
- [ ] `rebalance doctor` clean — **PENDING** (deferred to the Phase 4 close).

**Verification summary (2026-07-14).** The two new arms are correct against the real schema and the
real ranker. The email arm is *correctly wired and currently starved* — an upstream ingest defect,
not a HiQS defect. The figma arm is correct-and-idle as designed (0 rows, no allow-list).

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
- [x] A test asserts `ask()` reads the **same persisted rows** the `/whats-next` route writes — the
      anti-drift invariant, expressed as a test (`test_next_actions_parity`, rewritten to the
      structural shared-cache parity: the route writes, `ask()` reads).
- [x] A test asserts `ask()` does **not** call `rank_next_actions()` on the default path — no
      recompute, no network.
- [x] A test asserts every returned action carries `source` **and** non-empty `evidence` — Attested.
- [x] `ask()` on a brand-new / never-ranked DB degrades to an empty ranking without raising.
- [x] The pinned-`QueryResult` test is **updated, not deleted** — `EXPECTED_KEYS` now includes `hiqs`.
      The `NEXT_ACTIONS_ATTR` sidecar is deleted from `querier.py` and `retrieval.py`, as [D1](#d1--phase-2-attaches-hiqs-as-a-first-class-field-not-a-sidecar-decided-2026-07-14) requires.
- [x] `pytest tests/` green.
- [ ] Live `ask()` renders the HiQS section with real Gemini synthesis — **PENDING** (no key configured
      in this environment; the deterministic path is proven).
- [ ] `rebalance doctor` clean — **PENDING** (deferred to the Phase 4 close).

**Verification summary (2026-07-14).** The `team=` parameter is gone from both `ask()` and the MCP
tool — the ranking is now **always** returned, not opt-in. A stale `ask(team=True)` reference in the
`get_next_actions` MCP docstring was caught at local review and corrected (it would have instructed an
agent to pass a removed kwarg).

**Precise invariant — tightened after agy's QA round; the first draft overclaimed.** The drift-proofing
claim is **not** "there is a single writer." agy correctly found **two** writers — the `/whats-next`
route ([web.py:1470](../../src/rebalance/web.py#L1470)) and the scheduled `refresh_index()`
([index_ops.py:1420](../../src/rebalance/ingest/index_ops.py#L1420)) — so any "single writer" phrasing
is simply false. Two writers into one cache is harmless. The invariant that actually buys the
drift-proofing is:

> **No surface computes its own ranking.** There is exactly ONE ranking in the system; every surface
> reads it.

That is what makes two surfaces unable to show *different* rankings. The old failure mode — each
surface deriving its own answer from its own subset of sources — is structurally gone.

What remains, also found by agy, is a **cold-start absence — not a disagreement.** On a never-ranked DB,
`ask()` returns an **empty** ranking while `/whats-next` **bootstraps** the cache by computing one
(`if refresh or not meta.get("row_count")`). This asymmetry is deliberate and is **kept**: `ask()` must
never trigger a network synthesis ([D3](#d3--the-dispatch-chain-gets-collapsed-not-grown)). An empty
answer and a computed answer are not two rankings — they are one ranking and no ranking. Once the first
rank persists, every surface is reading the same rows.

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
- [x] **Principle 3 discharged:** `Phase3RegistryWalkTests` registers a *fake* collector with a
      `candidates=` provider and asserts its rows reach the ranked output — with **zero** edits to
      `next_actions.py` / `querier.py`. This is the keystone artifact of the whole issue.
- [ ] ~~**Net LOC across Phases 1–3 is ≤ 0**~~ — **MISSED. Actual: +519 net (+175 in `src/`).** The
      target assumed two deletions that turned out to be unsafe on inspection; see
      [Decisions recorded during build](#decisions-recorded-during-build). The acceptance criterion is
      recorded as **failed**, not quietly restated — the honest reading is that the *seam* (Principle 3)
      was the real prize and the LOC target was a proxy that mispriced it. Ponytail's own rule is that
      it minimizes the implementation, not the requirements: six sources genuinely needed wiring.
- [x] Every inherited gate has a recorded verdict — **no item left "gated"**:
      GH-101 Ph3 → **resolved** (Ph1–2 shipped; the freshness contract caught the figma/email starvation
      this very phase, which is the evidence its kill-gate asked for) · GH-115 Ph2–3 → **killed**
      (native OAuth already supplies email + calendar; the stubs are KEPT — see below) ·
      GH-116 Ph2 → **killed as a ranker arm** (cross-day scan, incompatible with the single-day
      provider contract; stays observe-only in `doctor`).
- [x] No behavior regression: `pytest tests/` green (1362 passed; the 2 failures are pre-existing on
      `development` and were confirmed by checking out `development` in a worktree and re-running).
- [x] Import-cycle check: `index_ops` ⇄ `next_actions` imports cleanly in **both** orders (the registry
      imports the providers at registration time; the ranker imports `COLLECTORS` lazily inside the walk).
- [ ] `audit_modules` clean — **left RED, deliberately.** See
      [Decisions recorded during build](#decisions-recorded-during-build).
- [ ] `rebalance doctor` clean · `/whats-next` renders — **PENDING** (Phase 4 close).

**Verification summary (2026-07-14).** The headline landed: a seventh source now reaches the ranked
verdict by registering a collector, proven by a test that adds one without touching the ranker. The
net-LOC criterion did **not** land, and is recorded as a miss.

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

## Local verification against real signal data (2026-07-14)

Phases 1–3 were built in Claude Code Cloud, which had **no populated DB and no credentials** — so
every SELECT against `email_messages` / `figma_comments` was written blind. The branch was then pulled
down and run against the real database. Three things came out of it that the sandbox could not have found.

**1. The blind schema guesses were right.** All six columns the email arm selects and all six the figma
arm selects exist on the real tables. `_query_day_activity` executes cleanly against the live schema —
no `OperationalError`, which was the single largest risk of building this without a DB.

**2. ⚠️ The Gmail collector is writing contentless rows — an upstream defect that falsifies this doc's
own Phase 0 premise.** Of the 124 `email_messages` rows, **119 carry no sender, no subject, and no
`received_at`** — only a `message_id`, a `labels_json`, and a `snippet`. Just **5** rows have content,
the newest received **2026-05-22**, seven weeks ago.

| | rows |
|---|---|
| `email_messages` total | 124 |
| …with a usable `received_at` | **5** |
| …contentless shells (no sender, no subject, no timestamp) | **119** |

So Phase 0's headline — *"124 real email rows feeding nothing"* — was **wrong**, and the corrected
claim is weaker: *5 real email rows feeding nothing, plus 119 broken rows*. The consolidation bet
recorded in `CHANGELOG.md` leaned on that number; it is corrected there too. The email arm is
**correctly wired and currently starved**. Wiring it was still right — but the payoff is gated on an
ingest fix, not on this issue.

**This is out of scope here and needs its own issue: GH-125 *consumes* email, it does not ingest it.**

**3. That defect exposed a signal-quality hole in the new email arm — fixed.** The shells are invisible
today *only because* their `received_at` is empty, so the window filter drops them. The day someone
fixes the ingest to populate the timestamp but not the headers, all 119 would land at **tier 1 — above
your open GitHub items** — as *"(no subject) — from unknown sender"*. `email_candidates()` now drops any
row with neither a subject nor a sender, and `test_contentless_email_shell_is_never_ranked` pins it.
A rank with nothing to attest with is precisely the bare verdict [D2](#d2--the-ranking-must-arrive-attested-decided-2026-07-14) forbids.

**Still pending** (needs credentials / a live model): `rebalance doctor`, live `refresh_index()`, the
live `/whats-next` render, and a real Gemini ranking call. Deferred to the Phase 4 close.

---

## Decisions recorded during build

- **Zapier stubs — KEPT (the planned deletion is rejected, with reason).** Phase 3 above proposed
  deleting `zapier_email.py` / `zapier_calendar.py` "unless they carry logic." They carry none — they
  are pure `NotImplementedError` placeholders — **but they are the live dispatch targets of the shipped
  `POST /api/zapier/ingest` receiver**, and `tests/test_zapier_webhook.py` pins the
  `NotImplementedError → 501` contract by patching those exact module functions. Deleting them breaks a
  shipped, tested endpoint that the same phase says to keep. The plan was wrong; the code stays.
- **`compute_deep_work_signals()` (GH-116 Ph2) — KILLED as a ranker arm (explicit, no third state).**
  It remains observe-only behind its `rebalance doctor` line. Reason: it is a **cross-day derived scan**
  (it re-reads `collect_pulse_snapshot` over a lookback window), whereas the `candidates=` provider
  contract is `bundle → rows` over a **single local day**. The bundle carries no lookback context, so
  folding it in would either break the provider contract for every other source or double-count projects
  the GitHub arms already surface. Revisit trigger: if it is ever folded in, it needs its own provider
  contract (`database_path` + lookback) — a deliberate follow-up, not a squeeze into this one.
- **`audit_modules` lockfile — left RED (the Cloud run's re-baseline is REVERTED).** The gate is failing
  on `development` with 23 modules missing from `ARCHITECTURE.md` and 13 from `CHANGELOG.md`. **None of
  them are from GH-125** — this issue adds no new module. The Cloud run made the gate green by running
  `--init` to re-baseline the lockfile, which is the tool's sanctioned reset and *was* disclosed. It is
  still the wrong call here: re-baselining permanently **silences 36 real doc gaps** created by other
  issues, converting a loud red gate into permanent quiet, and it launders unrelated debt through this
  PR. GH-125 does not need that gate green to be correct. The lockfile is reverted to its
  `development` state; the gate stays red exactly as it was; documenting those 36 modules is its own
  piece of work.

---

## QA review — agy, 1 round (2026-07-14)

Driven headless via `relay-xyz` (Path A, `--review-once`). Thread:
`.xyz/relay-system/2026-07-14/gh-125-hiqs-unified-signal-pipeline-qa-review.md`.
**Verdict: PASS**, with four `[Should]` findings. All four were acted on — two were hits on
overclaiming, which is exactly what the review was asked to hunt:

| # | agy's finding | Disposition |
|---|---|---|
| 1 | **"Single writer" is false** — `refresh_index()` also persists the ranked cache, not just the `/whats-next` route. | **ACCEPTED — claim corrected, code unchanged.** Two writers into one cache is harmless; the invariant that buys drift-proofing is *"no surface computes its own ranking"*, not *"one writer"*. Rewritten in [Phase 2](#phase-2--one-ranked-verdict) and in `CHANGELOG.md`. |
| 2 | **Cold-start divergence** — on a never-ranked DB `ask()` returns empty while `/whats-next` recomputes and persists. | **ACCEPTED — documented, behaviour kept.** It is an *absence*, not a disagreement: one ranking and no ranking, never two rankings. `ask()` must never trigger a network synthesis ([D3](#d3--the-dispatch-chain-gets-collapsed-not-grown)), so the asymmetry stays. The "structurally incapable of drifting" phrasing is retired. |
| 3 | **The shell-drop is silent** — freshness reports `ok` whenever rows exist, so a collector writing header-less rows looks healthy while contributing nothing. | **ACCEPTED — code changed.** `email_candidates()` now emits a `logger.warning` naming the dropped count and the cause. A dropped row is an ingest defect, not noise to swallow. This is the review's most valuable finding. |
| 4 | **Email at tier 1 (above open GitHub items) may be notification spam.** | **ACCEPTED as an OPEN QUESTION — deliberately not tuned now.** See follow-up 3. |

---

## Follow-ups this issue creates (do not lose)

| # | What | Why it is not done here |
|---|---|---|
| 1 | ~~**Gmail ingest writes contentless rows**~~ — **RESOLVED 2026-07-14. RCA below.** | Fixed at the write boundary + the 119 shells purged from the live DB. No issue needed. |
| 2 | **`audit_modules` doc debt** — 23 modules missing from ARCHITECTURE.md, 13 from CHANGELOG.md. | Pre-existing on `development`, unrelated to signal unification. Silencing it here would be laundering. |
| 3 | **Is email the right tier-1 signal?** (agy QA finding 4.) Email currently outranks your own open GitHub items. That may be right (an inbound ask from a human *is* usually more urgent than your own backlog) or it may fill the top of the list with newsletters. | **Cannot be answered yet, and tuning it now would be speculation.** The arm is *starved* — 5 usable rows, newest 7 weeks old — so there is no live email volume to tune a rank tier against. **Revisit trigger: once follow-up 1 lands and real mail flows, look at the top of `/whats-next` for a week.** If newsletters dominate, the fix is a relevance filter on the arm (or a tier demotion), not a re-ranker. |
| 4 | **Net-LOC ≤ 0 was missed (+519).** | Recorded as a failed criterion above, not restated. Worth a retro on whether the proxy was the right one. |
| 5 | **⚠️ NEW — source health measures row COUNT, not row QUALITY.** This is the generalizable defect the email RCA exposed, and it is **not** email-specific: freshness reports a source `ok` whenever rows exist. A collector writing *structurally valid but semantically empty* rows therefore looks perfectly healthy forever. That is exactly how 119 dead rows — 96% of a table — hid for three weeks. **Deserves its own GH issue.** | Applies to all eight sources, not to signal unification. Fixing it means teaching the freshness contract (the shipped GH-101 Ph1–2 work) to assert *content*, not just presence. Out of scope here. |

---

## RCA — the email shell corruption (closed 2026-07-14)

**The Gmail OAuth collector was never at fault.** `sync_gmail()` calls the API with `format="metadata"`
and the correct `metadataHeaders`, parses the `Date` header, and falls back to `internalDate`. It is
correct and always was.

| | |
|---|---|
| **What** | 119 of 124 `email_messages` rows (96% of the table) carried a `message_id`, a `snippet` and `labels_json` — but no sender, no subject, no `received_at`. 118 of them were also embedded into `semantic_documents`, polluting semantic search. |
| **When** | A single bulk push on **2026-06-25**. All 119 rows share one identical `synced_at`, which is what proves it was one call and not a slow leak. |
| **How** | `ingest_email_messages()` — the agent-facing MCP push path behind `ingest_gmail_messages`, **not** the OAuth collector — wrote `str(m.get(k) or "")` for every field. A caller whose payload used **different key names** had every unmatched field silently coerced to `""`, and the row was **stored anyway**. Only `message_id`, `snippet` and `labels` matched the expected vocabulary; the three that define a message did not. |
| **Why it hid for 3 weeks** | Source freshness checks whether rows **exist**, not whether they **mean anything**. 124 rows → `ok`. Nothing was ever going to report this. It surfaced only because GH-125 taught the ranker to *read* email and it found nothing rankable. |
| **Fix** | Reject at the write boundary: no sender **and** no subject **and** no timestamp → not a message, not stored. Count returned as `messages_skipped`; the MCP response carries an explicit `warning` naming the expected keys (the caller is an *agent*, so a log line alone would have been just as silent as the original bug). 3 regression tests, including the exact corrupting payload shape. |
| **Cleanup** | The 119 shells and their 118 embeddings purged from the live DB via the existing `delete_semantic_documents()` helper (embeddings + docs + FTS trigger). Verified: 0 shells, 0 orphans, `PRAGMA integrity_check` = ok, 5 real messages intact, all other sources untouched. DB backed up first. |

**Is the RCA complete? Yes — causally.** The one thing not known is *which* caller sent the malformed
payload and what exact key vocabulary it used (the rows are now deleted; a pre-purge backup retains them
if anyone wants forensics). **That does not matter**, because the guard rejects *any* wrong-shape payload
regardless of which one it was — identifying the specific caller would not change a line of the fix. The
email RCA is therefore **closed with no follow-up issue**.

**What DOES warrant an issue is follow-up 5** — the detector gap. The bug was findable in one query at any
point in those three weeks. Nothing looked, because nothing was watching for *empty* rather than *absent*.

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

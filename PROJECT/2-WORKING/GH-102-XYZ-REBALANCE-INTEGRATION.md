---
title: "XYZ ⇄ Rebalance Integration — duel-converged Top-3 seams"
owner: Noel
gh_issue: 102
source: "https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/102"
status: "Active (2-WORKING) — promoted 2026-07-03 on branch `gh-102-xyz-rebalance-integration`. Phase 0 (pre-scope discovery) run against XYZ's GH-75 doc + code; findings written back below. Both consult blockers resolved: `XYZ.json` confirmed completion-only (→ #1 reframed to 'recently-completed'), harness-root enumeration source located. Phase 1 (seam #2) is next and needs no GH-101."
created: 2026-07-02
updated: 2026-07-03
branch: gh-102-xyz-rebalance-integration
doc_type: project
goal: >
  Formalize how the XYZ agent-swarm harness (tick / marathon / relay-automation) and Rebalance
  should interface, per the Top-3 integration seams that two maintainer seats (claude-xyz ⇄
  claude-reb) converged on. Reuse what already exists over net-new infrastructure.
non_goals: >
  Not "XYZ drives Rebalance" — Rebalance self-drives its own marathons natively. Not a shared
  mutable-state coupling. Not building the return path (#3) before the forward collector (#1)
  proves the deep-work signal earns its place in the ranking. GH-88 cross-install pane stays
  XYZ-internal and out of scope here.
related:
  - relay-system/2026-07-02/xyz-rebalance-integration.md
  - PROJECT/2-WORKING/GH-101-SIGNAL-QUALITY-CONTRACT.md
effort: 3
complexity: 3
risk: 2
phases: 5
---

## Status

| Most recently completed | What's next |
|---|---|
| **Promoted to `2-WORKING` + Phase 0 discovery run (2026-07-03).** Cut branch `gh-102-xyz-rebalance-integration`, `git mv`'d here, updated the ROADMAP pointer. **Phase 0 run against XYZ's [GH-75 doc](https://github.com/Claude-AI-Tools-Ventura-County/xyz-3-agents-swarm/issues/75) + code — findings in [§Phase 0 Findings](#phase-0--findings-2026-07-03) below.** Both consult blockers **resolved**: (a) `XYZ.json` is **completion-only** telemetry (fires at terminal exits: `relay-drive.sh:208-217/324-330`, `marathon.sh:95`, `marathon-drive.sh:344-347`) — **#1 reframed to a "recently-completed marathons/sessions" signal**, no XYZ-side emitter needed for v1; (b) enumeration source located (`~/.config/xyz/registry.tsv` install rows), opt-in/dedup is the one remaining Reb-side design call. Bonus: XYZ already writes `XYZ.json` **atomically** (temp+`os.replace` + lock), so the Phase 2 atomic-read concern is XYZ-side-satisfied. | **Start Phase 1 (seam #2 — `xyz-sync check`).** Needs no GH-101. Open in parallel: Phase 1 build on the Reb/XYZ side (committed pin file + reuse the existing `xyz-sync.sh`/`find-harness.sh` drift surface). **Phase 2 stays blocked on GH-101** landing `recent_row_count_7d`+`status`/`reason`. One open Phase 0 sub-decision remains (harness-root opt-in/dedup rule) — lockable during Phase 1. |

---

## Table of contents

- [Thesis & shape](#thesis--shape)
- [Architectural invariants (cross-repo)](#architectural-invariants-cross-repo)
- [The Top-3 seams (reference)](#the-top-3-seams-reference)
- [Phase 0 — Pre-scope spike: lock the XYZ contract & #2 stamp format](#phase-0--pre-scope-spike-lock-the-xyz-contract--2-stamp-format-12h) _(discovery, not run)_
- [Phase 1 — Seam #2: harness release channel (`xyz-sync check`)](#phase-1--seam-2-harness-release-channel-xyz-sync-check) _(the substrate — ships first; blocked on Phase 0)_
- [Phase 2 — Seam #1: `xyz` collector → Rebalance signal plane](#phase-2--seam-1-xyz-collector--rebalance-signal-plane) _(blocked on Phase 1 + GH-101)_
- [Phase 3 — Seam #3: Reb → XYZ lane seeding (return path)](#phase-3--seam-3-reb--xyz-lane-seeding-return-path) _(kill-gated on Phase 2 proving value)_
- [Phase 4 — Outcome-attribution loop (signal sharpening)](#phase-4--outcome-attribution-loop-signal-sharpening) _(kill-gated on Phase 3; observe-first, log-don't-act)_
- [Open questions — what's after Phase 4](#open-questions--whats-after-phase-4)
- [Anti-goals](#anti-goals)
- [Dependencies & provenance](#dependencies--provenance)

---

## Thesis & shape

> **Thesis:** XYZ and Rebalance already carry the substrate for every seam that matters —
> `registry.tsv` stamps installs, GH-75 gives XYZ per-phase `updatedAt`+`health`, and Reb's
> collector registry ([index_ops.py:95](../../src/rebalance/ingest/index_ops.py#L95)) already
> ingests heterogeneous sources. **Integration is shims over existing rails, not new plumbing.**
> Build the cheapest reversible seam first (#2), let the deep-work signal (#1) prove it earns a
> place in the ranking, and only then build the bidirectional return path (#3).

**Owner split (constant across seams):** XYZ owns what it *emits* (state file, heartbeat, stamp,
check tool); Rebalance owns what it *consumes* (collector, signal semantics, health, the update
decision). Neither repo owns shared mutable state — the only coupling is a file one side writes and
the other reads.

**Build order — `#2 → #1 → #3 → (attribution)`, observe-first.** Rationale: #2 is the substrate and is
already the mechanism (nearly free); #1 is the payoff but must prove the deep-work signal is worth
ranking on; #3 is medium-cost net-new and is only justified once #1 shows the forward telemetry is
real; **Phase 4** (outcome-attribution) closes the loop last and only if #3 seeds enough lanes to
correlate — it never jumps ahead of the seams that feed it. Each step is gated on the prior one
*proving itself in live use*, not merely existing.

---

## Architectural invariants (cross-repo)

These hold across **every** phase. A phase that would violate one is *wrong*, not merely risky —
the QA gates below inherit them.

1. **Mutual independence — neither product depends on the other to function.** XYZ runs with no
   Rebalance installed; Rebalance runs with no XYZ installed. The integration is **purely
   additive**: it enriches each side when both are present and is *invisible* when only one is. A
   user who wants only one product installs only that one and loses nothing. This is the top
   constraint — **no seam may make either repo a prerequisite of the other.**
2. **Data-only coupling — no code or build dependency.** Neither repo imports, vendors, or links
   the other's code. The only interface is files/tables one side writes and the other reads
   (`XYZ.json`, `registry.tsv`, `roadmap_signals`). Deleting one repo cannot break the other's
   build, test suite, or `doctor`.
3. **Absence is a normal state, never an error.** A missing `XYZ.json`, an empty `roadmap_signals`,
   or an un-run `xyz-sync check` means "the other product isn't here / isn't active" — surfaced as
   absence, never a crash, a hard-fail, or a degraded-health *false positive*.
4. **Failure isolation.** One side being down, slow, stale, or emitting garbage must not block or
   crash the other. A bad/stale `XYZ.json` degrades to `degraded` (via GH-101) and stops there; the
   fault never propagates into Reb ingest or ranking.
5. **Untrusted-input boundary.** Each side treats the other's emitted file as *untrusted*: parse
   defensively, validate against the locked schema, never `eval`/exec, and tolerate unknown or
   missing fields (forward/backward-compatible, so a schema bump on one side can't break the other —
   this is exactly what #2's release channel exists to make legible).
6. **Single-authority ownership.** Each repo stays the sole source of truth for its own domain — Reb
   owns priorities/ranking, XYZ owns marathon queues/outcomes. Seams copy *intent* across the
   boundary; they never dual-write or co-own a store.

---

## The Top-3 seams (reference)

Each seam states Mechanism · Owner split · Cost · Reversibility (the duel's convergence contract).
These map to Phases 1–3 respectively.

### #1 · `xyz` collector → Rebalance signal plane  *(merged run-monitor + session-health)* → **Phase 2**
- **Mechanism:** XYZ emits `XYZ.json` per harness root (marathon/session state, already carrying GH-75 `updatedAt`+`health`); Rebalance adds one `register_collector("xyz", …)` ([index_ops.py:95](../../src/rebalance/ingest/index_ops.py#L95) pattern) snapshotting it into a table keyed off the GH-101 freshness/degraded fields — no new Reb observability plumbing; DASHBOARD/pulse + "what to do next" read it as a deep-work signal.
- **⚠ Correction (consult 2026-07-03):** today's `XYZ.json` (GH-75) is a **completion log written on terminal exit**, not a per-phase heartbeat. A *live in-flight* deep-work signal is therefore an **XYZ-side prerequisite** (new active-state emitter), not a free read. Phase 0 decides: reframe #1 to "recently-completed marathons" (works on today's file) or require the emitter. Owner split below reflects the *target*, gated on that decision.
- **Owner split:** XYZ owns emitting `XYZ.json` (+ an active-state emitter *if* Phase 0 chooses the live-signal path) / Reb owns the collector + signal semantics + health.
- **Cost:** shim each side (one registration + a reader).
- **Reversibility:** trivial — unregister the collector, stop reading the file.

### #2 · Harness release channel (pinned + manual)  *(the substrate — ship first)* → **Phase 1**
- **Mechanism:** `registry.tsv` already records `source_commit` + `tick_version` per install; add `xyz-sync check` that diffs recorded-vs-shipped commit and warns on drift; updates land manually via PR (matches Reb's `doctor`+`pytest`+`pdda` gate discipline).
- **Owner split:** XYZ owns publishing the stamp + check tool / Reb owns its pin + update decision.
- **Cost:** subcommand only (columns already exist).
- **Reversibility:** trivial — it is already the mechanism.

### #3 · Reb → XYZ lane seeding (the return path)  *(Phase-2, gated behind #1)* → **Phase 3**
- **Mechanism:** Rebalance's ranked "what to do next" emits cross-repo tick lanes (ROADMAP Phase-5 `roadmap_signals`), so Reb *priorities* can seed XYZ marathon queues — bidirectional, not just XYZ→Reb telemetry.
- **Owner split:** Reb owns the emitter / XYZ owns the tick-lane consumer.
- **Cost:** medium — net-new `roadmap_signals` table (Phase-2).
- **Reversibility:** opt-in — drop the emitter.

### Adjacent (deliberately NOT in the shared Top-3)
- **GH-88 cross-install run pane** — XYZ-internal viewer over `registry.tsv` + `.relay-driver.lock`. Reb renders marathon state natively from #1 and does not depend on it. Kept out of the *shared* Top-3 because Reb never consumes it.

---

## Phase 0 — Pre-scope spike: lock the XYZ contract & #2 stamp format (1–2h)

**This is a discovery phase — its findings MUST be written back into this doc before its QA gate can
pass (PDDA discovery contract).** No Rebalance code is written in Phase 0.

**Goal:** remove the two unknowns that block every downstream phase — (a) the exact XYZ→Reb file
contract that seam #1 reads, and (b) the stamp/diff format seam #2 checks — so Phase 1 and Phase 2
build against a locked interface instead of a guessed one.

**Observable checklist:**

- [x] **Name the state file.** `XYZ.json` is the **literal** filename (not a placeholder), a JSON
      array written at the **harness repo root** (the clone that ships `relay-automation/`), **gitignored**
      — see Findings. Record the literal path convention. ✔
- [x] **Pin the `XYZ.json` schema.** 6 fields confirmed (`harness`, `sessionId`, `health`, `title`,
      `description`, `updatedAt`), newest-first array — verbatim example in Findings. ✔
- [x] **⚠ BLOCKER — resolve completion-vs-active-state.** **RESOLVED: completion-only.** `XYZ.json`
      updates only on **terminal exit** (no mid-marathon heartbeat). **Decision: option (a)** — reframe #1
      to a "recently-completed marathons/sessions" signal that works on today's file; **no XYZ-side emitter
      for v1.** Cadence = one record per completed session, freshness read off `updatedAt`. ✔
- [ ] **⚠ BLOCKER — harness-root selection contract.** There are ≥2 install surfaces: machine-local
      installs in `~/.config/xyz/registry.tsv` and vendored `.xyz/` copies with their own `VERSION`
      stamps/rows. "Per harness root" is underspecified. Define the **operator-controlled** enumeration /
      dedupe / opt-in rule for which roots Reb reads, so #1 can't produce duplicate or stale reads with
      blurry ownership.
- [ ] **Lock the #2 stamp format + a *committed* pin home.** Confirm `registry.tsv` carries
      `source_commit` + `tick_version` (verify columns exist). **Note:** `registry.tsv` is *machine-local
      and never committed*, so the Reb-side pin cannot live only there or it isn't reproducible on a
      fresh clone (Principle 10). Decide a **committed** Reb-side pin file (e.g. `.xyz-pin`) that
      `xyz-sync check` / `doctor` diff against the machine-local install. Decide the `xyz-sync check`
      output contract: recorded-vs-shipped diff, warn-on-drift, exit code.
- [x] **Don't duplicate an existing drift surface.** **Decision: reuse/extend.** XYZ already ships
      `find-harness.sh` (warn-on-vendored-drift) + `xyz-sync.sh list/update/delete` (GH-49). Phase 1's
      `xyz-sync check` extends that surface (or scopes to non-vendored installs), does not fork a second
      channel. ✔
- [x] **Confirm the Reb ingestion seam is real.** `register_collector` at
      [index_ops.py:95](../../src/rebalance/ingest/index_ops.py#L95), live registrations L1505–1513,
      dispatched by `refresh_index` [index_ops.py:1095](../../src/rebalance/ingest/index_ops.py#L1095).
      A file-backed `Collector("xyz", _xyz_adapter, requires=…)` is the correct extension point. ✔
- [x] **Confirm GH-101 dependency direction.** #1 keys health off GH-101's `recent_row_count_7d` +
      `status`/`reason`; Phase 2 stays gated on GH-101 Phase 1–2 landing them. ✔

**Exit criteria:**

- **Both blockers resolved:** the completion-vs-active-state decision is recorded (with the #1 reframe
  or the XYZ-emitter requirement), and the harness-root selection contract is written down.
- The emitted filename, schema, and cadence are recorded here as a locked contract (not a guess).
- The `xyz-sync check` output/exit-code contract **and the committed pin home** are recorded.
- The `register_collector` seam is confirmed as the Reb-side extension point — **no new Reb
  observability plumbing required.** If it is not, pause and escalate — do not start Phase 1.
- The precise GH-101 fields #1 depends on are named, confirming the Phase 2 ⟵ GH-101 sequencing.

### Phase 0 — QA checklist

- [x] **Discovery written back.** See [§Phase 0 — Findings](#phase-0--findings-2026-07-03) below —
      each claim grounded with `file:line` (GH-75) or an example payload, CONFIRMED / OPEN per item. ✔
- [x] **No code changed.** Phase 0 was read/decide only; the only change is this doc + the ROADMAP
      pointer. ✔
- [x] **DRY / reuse.** Findings reuse `registry.tsv` columns, the existing `xyz-sync.sh` drift surface,
      and the collector registry — no net-new table or MCP tool proposed for #1/#2. ✔
- [x] **Cross-repo owner split honored.** XYZ owns `XYZ.json` + the stamp/check tool; Reb owns the
      collector + committed pin + read — no shared mutable state. ✔
- [ ] **Doc hygiene.** `utils/pdda/pdda.sh run` clean for this promotion (run at commit time).

#### Phase 0 — Findings (2026-07-03)

Run against XYZ's [GH-75 doc](https://github.com/Claude-AI-Tools-Ventura-County/xyz-3-agents-swarm/issues/75)
(`PROJECT/1-INBOX/GH-75-XYZ-JSON-COMPLETION-TELEMETRY.md`, status **Shipped**) + the harness scripts it
cites. Each claim CONFIRMED against `file:line` in the **xyz-3-agents-swarm** repo, or marked OPEN.

**The two consult blockers — resolved:**

| Item | Verdict | Evidence |
|---|---|---|
| `XYZ.json` is *completion* telemetry, not a per-phase heartbeat | **CONFIRMED** | GH-75 title + design: hooks fire only at terminal exits — `relay-drive.sh:208-209` (green), `:214-217` (orange/escalated), `:324-330` (red/round-cap); `marathon.sh:95` (whole-run); `marathon-drive.sh:344-347` (per-run/swarm). No mid-run emit. |
| → **Decision:** reframe #1 to "recently-completed marathons/sessions" | **DECIDED (option a)** | Works on today's file; no XYZ-side active-state emitter needed for v1. A live in-flight signal is a deferred XYZ follow-on, not a Reb-side blocker. |
| Harness-root **enumeration** source | **CONFIRMED (partial)** | `XYZ.json` lives at each **harness repo root** (never a `--target-root` foreign repo — GH-75 §Location); those roots are the install rows in machine-local `~/.config/xyz/registry.tsv` (`install_dir` / `coordinated_repo`). **OPEN:** the operator opt-in + dedup rule across the two surfaces (machine-local installs vs. vendored `.xyz/`) is the one Phase 0 sub-decision left — lockable during Phase 1. |

**Locked contract facts:**

- **Filename + location:** literal `XYZ.json`, a **newest-first JSON array** at the harness repo root,
  **gitignored** (local, machine-specific — GH-75 §Location + non-goals). Reb reads it; Reb never writes it.
- **Schema (verbatim, GH-75 §Record schema):**
  ```json
  {
    "harness": "relay|marathon|swarm",
    "sessionId": "<relay thread slug, or marathon plan/run id>",
    "health": "green|orange|red",
    "title": "...",
    "description": "...",
    "updatedAt": "2026-07-01T00:00:00Z"
  }
  ```
  `health` = green (all-approved) / orange (relay escalated) / red (halt or round-cap fail).
- **Atomic write — already handled XYZ-side:** GH-75 writes via temp-file + `os.replace()` under an
  `mkdir` advisory lock (GH-72 pattern). So the Phase 2 "read a half-written file" concern is
  **XYZ-satisfied**; Reb's reader still parses defensively (invariant 5) but need not coordinate writes.
- **#2 stamp:** `registry.tsv` carries `source_commit` + `tick_version` per install, **machine-local /
  never committed** → the Reb-side pin must live in a **committed** file (confirms the Phase 1 decision).
  Vendored copies also stamp `.xyz/VERSION` with `source_commit` (GH-49), which `find-harness.sh` /
  `xyz-sync.sh` already diff — **reuse, don't fork** (confirms the no-duplicate-drift decision).

**Impact on the plan:** Phase 2's mechanism is unchanged in shape (one `register_collector` reading a
file) but its *semantics* shift from "active marathon" to "recently-completed session"; the Seam #1
reference + Phase 2 read-surface language already carry this. Nothing contradicts the no-new-table
assumption → no escalation. **Phase 1 is cleared to start; Phase 2 remains gated on GH-101.**

---

## Phase 1 — Seam #2: harness release channel (`xyz-sync check`)

*(the substrate — ships first; blocked on Phase 0)*

Ship the cheapest, most reversible seam first: a manual, pinned release channel so a Reb install
knows when its recorded XYZ harness commit has drifted from what XYZ shipped. This is *already* the
mechanism — the columns exist — so it is a subcommand, not new infrastructure.

**Observable checklist:**

- [ ] **`xyz-sync check` subcommand** reads the install's recorded `source_commit` + `tick_version`
      from `registry.tsv` and diffs against the shipped/current XYZ commit.
- [ ] **Warn-on-drift.** On mismatch, print the recorded-vs-shipped commit pair and a one-line
      "harness drift" warning; exit non-zero (contract locked in Phase 0). On match, exit clean.
- [ ] **No auto-update.** The tool *reports*; updates land manually via PR — matching Reb's
      `doctor` + `pytest` + `pdda` gate discipline. No network fetch that mutates the install.
- [ ] **Reb pin surface — committed, not machine-local.** Reb records its pinned commit in a
      **committed** file (per Phase 0) so a fresh clone is reproducible; `registry.tsv` (machine-local,
      uncommitted) is the *install* side of the diff, not the pin's home. The update decision stays a
      human PR; confirm the pin is where `doctor` can see it.
- [ ] **No duplicate drift channel.** Per Phase 0, `xyz-sync check` reuses/extends the existing
      `find-harness.sh` / `xyz-sync.sh` drift surface or is scoped to non-vendored installs — it does
      not stand up a second, overlapping drift path.
- [ ] **Reversibility proven.** Removing/ignoring the subcommand leaves the install functioning —
      it is a check, not a dependency.

### Phase 1 — QA checklist

- [ ] **Litmus (does the seam earn its place?):** on a deliberately drifted `registry.tsv` row,
      `xyz-sync check` warns and exits non-zero; on an in-sync row it exits clean. A screenshot/log
      of both recorded here.
- [ ] **DRY / reuse.** No new columns added to `registry.tsv` (Phase 0 confirmed `source_commit` +
      `tick_version` already exist); the subcommand only reads.
- [ ] **Observability.** The warning names *which* install and *which* commit pair drifted — legible
      without opening the TSV by hand.
- [ ] **Reversibility.** Unregistering / not running the check returns the system to baseline with
      no residue (matches the seam's "trivial" reversibility claim).
- [ ] **Gate discipline (XYZ side).** XYZ-repo tests green for the new subcommand; the change lands
      via PR, not direct push.
- [ ] **Gate discipline (Reb side, if any Reb glue lands):** `rebalance doctor` clean + `pytest tests/`
      green before any success claim; `utils/pdda/pdda.sh run` clean.

---

## Phase 2 — Seam #1: `xyz` collector → Rebalance signal plane

*(blocked on Phase 1 + on GH-101 shipping the freshness/degraded fields)*

The payoff seam: Reb ingests XYZ marathon/session state as a **deep-work signal** the DASHBOARD /
pulse / "what to do next" surfaces can rank on. One collector registration on the Reb side; one
emitted file on the XYZ side. **Do not start until GH-101 has landed `recent_row_count_7d` +
`status`/`reason`** (Phase 2 keys the collector's health off them).

**Observable checklist:**

- [ ] **XYZ emits `XYZ.json`** per harness root with the locked Phase 0 schema and the signal shape
      Phase 0 chose (completion telemetry, or active-state if the emitter path was taken). Written
      **atomically** (temp file + rename) so Reb's concurrent sync crons never read a half-written file
      and false-flag `degraded`.
- [ ] **`register_collector("xyz", _xyz_adapter, requires=(…))`** added to Reb following the
      existing pattern at [index_ops.py:95](../../src/rebalance/ingest/index_ops.py#L95) /
      registrations L1505–1513; the adapter reads `XYZ.json` and snapshots it into a table.
- [ ] **Health keyed off GH-101 fields.** The snapshot carries freshness/degraded status derived
      from the GH-101 contract fields — a stale/absent `XYZ.json` reads as `degraded`, not silently
      healthy. **No new Reb observability plumbing.**
- [ ] **Read surface.** DASHBOARD/pulse + `get_next_actions` read the snapshot as a deep-work signal —
      phrased to match the Phase 0 shape ("marathon completed in repo X, health Y, Z ago" for the
      completion-telemetry cut; "active marathon, phase Y" only if the active-state emitter was built).
      Do not claim live in-flight state the emitted file doesn't actually carry.
- [ ] **Absent-file behavior.** A harness root with no `XYZ.json` is a legitimate "no active
      marathon" — surfaced as absence, not as an error or a hard-fail.
- [ ] **Reversibility proven.** Unregistering the collector + not reading the file returns Reb to
      baseline; no residual schema dependency.

### Phase 2 — QA checklist

- [ ] **Litmus (real signal, not noise):** a seeded live/fixture `XYZ.json` produces a deep-work
      signal visible in `get_next_actions` / DASHBOARD; a stale one surfaces as `degraded` via the
      GH-101 fields; an absent one surfaces as "no active marathon". All three recorded.
- [ ] **DRY / reuse.** Uses `register_collector` + the GH-101 freshness fields — no parallel health
      system, no new MCP tool. Snapshot table (if any) justified vs. reusing an existing table.
- [ ] **SOLID / owner split.** The adapter only *reads* `XYZ.json`; XYZ owns writing it. No Reb code
      writes into the XYZ harness root.
- [ ] **Observability.** A degraded/absent XYZ signal is legible in `rebalance doctor` output, not
      only inside the ranking internals.
- [ ] **Sequencing honored.** Confirm GH-101 Phase 1–2 fields exist before this ships (the health
      key has a real column to read).
- [ ] **Gate discipline.** New unit test asserts the collector snapshots a seeded `XYZ.json`
      correctly incl. a stale/degraded case; full `pytest tests/` green; `rebalance doctor` clean;
      `utils/pdda/pdda.sh run` clean. Lands via self-mergeable PR (main is protected).

---

## Phase 3 — Seam #3: Reb → XYZ lane seeding (return path)

*(kill-gated on Phase 2 proving the forward signal is real)*

The bidirectional close: Reb's ranked "what to do next" emits cross-repo tick lanes so Reb
*priorities* seed XYZ marathon queues. **Medium cost — net-new `roadmap_signals` table** (ROADMAP
Phase-5, [ROADMAP.md:34-35](../../ROADMAP.md#L34)). Only build if Phase 2 demonstrates the forward
telemetry earns its place in the ranking; otherwise stop — a one-way telemetry link is a complete,
useful outcome on its own.

> **⚠ Correction (consult 2026-07-03) — file projection, not DB coupling.** The `roadmap_signals` table
> is **Reb-internal/canonical**; XYZ must **not** open Reb's SQLite to read it (a DB lock during sync
> would stall XYZ; a dynamic DB path would break it — violating invariants 1 & 2). Reb **exports** a
> read-only projection *file* (e.g. `roadmap_signals.json`) that XYZ consumes — mirror, not migration
> (Principle 2). The cross-repo interface is the file; the table stays behind Reb's boundary.

**Kill-gate (evaluate before writing any Phase 3 code):** has Phase 2's `xyz` deep-work signal
changed a real ranking/next-action decision in live use? **Make this attestable, not a vibe** (Principle
9 / the Attested pillar): declare a concrete **observation window** (e.g. 2 weeks), a **minimum sample**
(e.g. ≥N decisions where the signal was present), and the **receipt surface** the "yes" is read off
(which `doctor`/DASHBOARD/log field). If the bar isn't met, do not build #3 — document the stop and
close the plan at Phase 2.

**Observable checklist:**

- [ ] **`roadmap_signals` emitter (Reb).** Reb's ranked next-actions write cross-repo tick lanes into
      a net-new **Reb-internal** `roadmap_signals` table (ROADMAP Phase-5 note), then **export a
      read-only projection file** (`roadmap_signals.json`) as the cross-repo interface. Additive; does
      not alter existing ranking output.
- [ ] **Tick-lane consumer (XYZ).** XYZ reads the **projection file** (never Reb's SQLite) and seeds
      marathon queues from Reb priorities. XYZ owns the consumer; Reb owns the emitter + the export.
- [ ] **Opt-in.** The emitter is off by default / trivially disabled; dropping it removes the return
      path with no residue.
- [ ] **No shared mutable state.** Reb writes the signal; XYZ reads and decides — neither mutates the
      other's authoritative store.

### Phase 3 — QA checklist

- [ ] **Kill-gate recorded.** The Phase 2 "did the forward signal change a real decision?" evaluation
      is written down with evidence; Phase 3 proceeds only on a documented "yes".
- [ ] **Litmus (round-trip):** a seeded Reb priority appears as a tick lane XYZ can consume; disabling
      the emitter removes it cleanly. Recorded.
- [ ] **DRY / reuse.** `roadmap_signals` is justified as genuinely net-new (Phase 2's forward table
      cannot carry return lanes) rather than duplicated plumbing.
- [ ] **SOLID / reversibility.** Emitter is opt-in and removable; XYZ consumer degrades gracefully
      when the table is empty or absent.
- [ ] **Authority check.** Reb remains the source of truth for priorities; XYZ remains source of
      truth for marathon queues — the seam copies intent, it does not dual-write ownership.
- [ ] **Gate discipline.** Migration for `roadmap_signals` tested; `pytest tests/` green;
      `rebalance doctor` clean; `utils/pdda/pdda.sh run` clean. Lands via PR.

---

## Phase 4 — Outcome-attribution loop (signal sharpening)

*(kill-gated on Phase 3; observe-first, log-don't-act)*

The first leg of a real feedback loop back into Rebalance. Phases 1–3 give Reb *telemetry* (#1) and a
way to *seed* XYZ (#3), but nothing measures **whether the things Reb ranked high actually paid off**
— so Reb never learns what to up- or down-weight, or what to ignore probabilistically. Phase 4 closes
that gap **at the cheapest possible altitude: correlate, log, do not yet act.**

The substrate already exists: #3 records which lanes Reb seeded; #1 already returns each marathon's
**outcome/health** (`XYZ.json`). Phase 4 only adds the *join* between them — an attribution record, not
a learning engine, not a re-ranker.

> **Scope boundary (important):** learning "what to ignore" is **relevance/precision** territory, which
> [GH-101](../2-WORKING/GH-101-SIGNAL-QUALITY-CONTRACT.md) fenced off as *out of v1 by design* (the
> GH-81 partial-relevance class, "Phase 4+"). Phase 4 here is the **observation** that would justify
> crossing that fence — it does **not** cross it. Acting on the attribution (adjusting ranking weights)
> is deliberately deferred to the open question below.

**Kill-gate (evaluate before writing any Phase 4 code):** has Phase 3 seeded enough real lanes, with
observable outcomes returning via #1, that a seeded-vs-outcome correlation is even *computable* on live
data? **Declare the threshold** (e.g. ≥N seeded lanes with terminal outcomes over a stated window), don't
eyeball "enough". If the bar isn't met, do not build Phase 4 — there is nothing yet to attribute.

**Observable checklist:**

- [ ] **Attribution record.** For each lane Reb seeded via #3, join it to the marathon outcome that
      came back via #1 (`completed` / `stalled` / `abandoned` / `churned`, plus GH-75 `health`).
      Additive log — a new lightweight table or an append-only record, **not** a mutation of ranking.
- [ ] **Rank-vs-outcome column.** Record Reb's *original priority/rank* alongside the observed outcome,
      so "high-ranked things that stalled" and "low-ranked things that completed" are both legible.
- [ ] **Read surface, not decision surface.** Surface the correlation in `doctor` / a report only —
      e.g. "8 of 10 top-ranked lanes completed; 2 stalled." No code reads it to change a rank in Phase 4.
- [ ] **Observational sub-variant noted.** If Phase 3 is skipped/delayed, record whether a *weaker*
      attribution is possible off #1 alone (Reb's native ranking vs. whatever XYZ independently ran) —
      observational, not causal. Decide explicitly; don't silently assume #3 is required.
- [ ] **Reversibility proven.** Dropping the attribution record returns Reb to baseline; nothing
      downstream depends on it (because nothing acts on it yet).

### Phase 4 — QA checklist

- [ ] **Litmus (does the attribution carry signal?):** on seeded fixture data, high-ranked-but-stalled
      and low-ranked-but-completed cases both appear in the record and are distinguishable. Recorded here.
- [ ] **Falsifiability / the real gate:** does the correlation, on live data, actually reveal a
      ranking Reb got *wrong*? If after a real observation window it shows no separable signal, **stop
      and document** — the sharpening loop is not paying for itself, and the open-question escalation is
      unjustified. (Mirrors GH-101 §7's "only worth keeping if it catches real defects.")
- [ ] **Scope discipline.** Phase 4 only *logs*. Confirm no code path reads the attribution record to
      alter a rank, weight, or filter — that is the fenced GH-81/Phase-4+ work, not this phase.
- [ ] **DRY / reuse.** Joins existing #1 outcomes + #3 seed records; no new telemetry pipe, no second
      copy of marathon state. The join table (if any) is justified vs. extending an existing record.
- [ ] **Authority check.** Reb still owns ranking; XYZ still owns outcomes. Phase 4 reads both and
      writes only its own attribution log — it does not dual-write either authority.
- [ ] **Gate discipline.** Unit test asserts the join produces correct attribution for a seeded
      high-rank-stall and low-rank-complete pair; `pytest tests/` green; `rebalance doctor` clean;
      `utils/pdda/pdda.sh run` clean. Lands via PR.

---

## Open questions — what's after Phase 4

- **Cross the relevance fence?** If Phase 4's attribution shows a *separable, repeatable* signal
  (Reb systematically over- or under-ranks a class of work), the next step is to **act** on it — feed
  attribution back into ranking weights so Reb learns what to up-weight and what to ignore
  probabilistically/heuristically. This is exactly the **GH-81 partial-relevance class that
  [GH-101](../2-WORKING/GH-101-SIGNAL-QUALITY-CONTRACT.md) scopes to "Phase 4+"** — a genuine
  learning/precision engine, not a shim. **Deliberately unscheduled here.** Revisit only with a
  Phase 4 observation window in hand; whether it lives on this plan, on GH-101's relevance surface, or
  on its own doc is itself part of the question.
- **Heuristic vs. learned weighting.** If we do act, is a hand-tuned heuristic (down-weight a class
  after N stalls) enough, or does it warrant a learned model? Cheapest-that-works first — but the
  attribution record from Phase 4 is the dataset either approach would need, so building it now keeps
  both doors open without committing to either.
- **Attribution window & decay.** How long a lane's outcome stays attributable to a ranking decision
  (a marathon that completes weeks later vs. one abandoned same-day) is undecided; Phase 4 should record
  timestamps so this can be answered from data rather than guessed.

---

## Anti-goals

- **Not a mutual dependency.** Neither repo may become a prerequisite of the other (invariant 1).
  If installing/running one *requires* the other, the seam is wrong — both products must work fully
  standalone, and the integration is invisible when only one is present.
- **Not "XYZ drives Rebalance."** Rebalance self-drives its own marathons natively; #1 is telemetry
  *into* Reb, not control *of* Reb.
- **Not shared mutable state.** Every seam is one side writing a file/table the other reads. No seam
  introduces a store both repos mutate.
- **Not #3-before-#1.** The return path is not built until the forward collector proves the deep-work
  signal earns its place in the ranking (Phase 3 kill-gate).
- **Not new Reb observability plumbing.** #1 rides the existing collector registry + GH-101 health
  fields; #2 rides existing `registry.tsv` columns. Net-new infrastructure is confined to #3's
  `roadmap_signals` table, and only if the kill-gate passes.
- **Not a re-ranker (in this plan).** Phase 4 *observes* whether Reb's rankings paid off; it does not
  act on that observation. Feeding attribution back into ranking weights — learning what to ignore
  probabilistically — is the fenced GH-81/GH-101 "Phase 4+" relevance work, parked in Open Questions,
  not built here.
- **GH-88 cross-install pane stays XYZ-internal** and out of scope — Reb renders marathon state
  natively from #1 and never consumes the pane.

---

## Dependencies & provenance

- **Depends on:** [GH-101 signal-quality contract](../2-WORKING/GH-101-SIGNAL-QUALITY-CONTRACT.md)
  (supplies #1's freshness/degraded health fields — Phase 2 is sequenced after GH-101 Phase 1–2),
  the collector registry (`register_collector` at [index_ops.py:95](../../src/rebalance/ingest/index_ops.py#L95),
  dispatched by `refresh_index` at [index_ops.py:1095](../../src/rebalance/ingest/index_ops.py#L1095)),
  and the ROADMAP Phase-5 `roadmap_signals` note ([ROADMAP.md:34-35](../../ROADMAP.md#L34), for #3).
- **XYZ-side prerequisites:** the emitted state file + per-phase `updatedAt` heartbeat (GH-75), the
  `registry.tsv` `source_commit` + `tick_version` columns (#2), and the tick-lane consumer (#3).
- **Provenance:** [duel thread](../../relay-system/2026-07-02/xyz-rebalance-integration.md) —
  `claude-xyz` ⇄ `claude-reb`, 4 rounds, closed 2026-07-02.
- **QA:** cross-model consult (Codex + agy, 2026-07-03) against the Guiding Principles. Both ran inside
  the XYZ repo, surfacing two blockers this doc couldn't see from the Reb side: `XYZ.json` is completion
  (not heartbeat) telemetry, and Seam #3's table must be a file projection, not direct SQLite coupling.
  Both folded in above; Phase 4 retained (operator decision) despite both advisors suggesting deferral.

## Verification (per ROUTER §7)

`rebalance doctor` clean + `pytest tests/` green before any success claim on a code phase (1–4).
Doc-hygiene: `utils/pdda/pdda.sh run` clean before promoting this doc from `1-INBOX` to `2-WORKING`,
and again after each phase's findings/status write-back.

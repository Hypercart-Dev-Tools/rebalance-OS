---
title: "XYZ ⇄ Rebalance Integration — duel-converged Top-3 seams"
owner: Noel
gh_issue: 102
source: "https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/102"
status: "Proposed (1-INBOX) — captured from the 2026-07-02 dueling-Claudes brainstorm; not yet scoped/started."
created: 2026-07-02
updated: 2026-07-02
branch: development
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
---

## Status

| What was just completed | What's next |
|---|---|
| **Captured 2026-07-02 from the "dueling Claudes" brainstorm** (`relay-system/2026-07-02/xyz-rebalance-integration.md`, 4 rounds, `STATUS: Closed`). Two seats converged on a stable Top-3 + build order; GH [#102](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/102) opened; parked in `ROADMAP.md`. | **Phase 0 (pre-scope):** confirm the `XYZ.json` schema + emit cadence and decide #2's pin/stamp format before any Rebalance collector code. Then promote to `2-WORKING`. Sequenced **after** [GH-101](../2-WORKING/GH-101-SIGNAL-QUALITY-CONTRACT.md) ships (it supplies #1's health fields). |

## Top-3 seams (build order: #2 → #1 → #3, observe-first)

Each seam states Mechanism · Owner split · Cost · Reversibility (the duel's convergence contract).

### #1 · `xyz` collector → Rebalance signal plane  *(merged run-monitor + session-health)*
- **Mechanism:** XYZ emits `XYZ.json` per harness root (marathon/session state, already carrying GH-75 `updatedAt`+`health`); Rebalance adds one `register_collector("xyz", …)` (`src/rebalance/ingest/index_ops.py:95` pattern) snapshotting it into a table keyed off the GH-101 freshness/degraded fields — no new Reb observability plumbing; DASHBOARD/pulse + "what to do next" read it as a deep-work signal.
- **Owner split:** XYZ owns emitting `XYZ.json` + a per-phase `updatedAt` heartbeat / Reb owns the collector + signal semantics + health.
- **Cost:** shim each side (one registration + a reader).
- **Reversibility:** trivial — unregister the collector, stop reading the file.

### #2 · Harness release channel (pinned + manual)  *(the substrate — ship first)*
- **Mechanism:** `registry.tsv` already records `source_commit` + `tick_version` per install; add `xyz-sync check` that diffs recorded-vs-shipped commit and warns on drift; updates land manually via PR (matches Reb's `doctor`+`pytest`+`pdda` gate discipline).
- **Owner split:** XYZ owns publishing the stamp + check tool / Reb owns its pin + update decision.
- **Cost:** subcommand only (columns already exist).
- **Reversibility:** trivial — it is already the mechanism.

### #3 · Reb → XYZ lane seeding (the return path)  *(Phase-2, gated behind #1)*
- **Mechanism:** Rebalance's ranked "what to do next" emits cross-repo tick lanes (ROADMAP Phase-5 `roadmap_signals`), so Reb *priorities* can seed XYZ marathon queues — bidirectional, not just XYZ→Reb telemetry.
- **Owner split:** Reb owns the emitter / XYZ owns the tick-lane consumer.
- **Cost:** medium — net-new `roadmap_signals` table (Phase-2).
- **Reversibility:** opt-in — drop the emitter.

### Adjacent (deliberately NOT in the shared Top-3)
- **GH-88 cross-install run pane** — XYZ-internal viewer over `registry.tsv` + `.relay-driver.lock`. Reb renders marathon state natively from #1 and does not depend on it. Kept out of the *shared* Top-3 because Reb never consumes it.

## Dependencies & provenance

- **Depends on:** [GH-101 signal-quality contract](../2-WORKING/GH-101-SIGNAL-QUALITY-CONTRACT.md) (supplies #1's freshness/degraded health fields), the collector registry (`index_ops.py:95`), and the ROADMAP Phase-5 `roadmap_signals` note (#3).
- **Provenance:** [duel thread](../../relay-system/2026-07-02/xyz-rebalance-integration.md) — `claude-xyz` ⇄ `claude-reb`, 4 rounds, closed 2026-07-02.

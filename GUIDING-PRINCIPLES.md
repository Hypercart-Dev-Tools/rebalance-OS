# Guiding Principles

The north star **rebalance OS**'s goals and implementation decisions answer to. When a design choice
is unclear, the option that better serves these principles wins.

## Purpose

rebalance OS is a **local-first work operating system**: it ingests your work artifacts — Obsidian
vault, GitHub activity and artifacts, recent git history, calendar, email — into one queryable local
store, so any MCP-capable agent can answer questions about *your own* work, surface where your
attention is actually going across projects, and infer what's ready to ship — **without sending
private data to a cloud service**. A second brain over your work first; a sprint and
deploy-readiness planner as the payoff.

## Principles

1. **Local-first, private by default.** Private work — notes, commits, calendar, client repos —
   never leaves the machine. A cloud LLM sees only what the operator explicitly sends. This is the
   non-negotiable that makes the tool usable for client work; any feature that erodes it loses.
2. **One unified local store is the evidence layer.** Every source funnels through the same
   `collect → normalize → store → query` path into local SQLite (+ sqlite-vec). Retrieval and
   recommendations are driven from that indexed store — never from an agent skimming hundreds of live
   issues/PRs.
3. **The local store + live re-probe is the source of truth; every surface is a projection.** The
   web view, the Mac app, a cloud mirror — all are read-only mirrors of canonical local state, not
   parallel copies that can drift. Mirror, not migration.
4. **Signal-agnostic and extensible.** A new source is added by registering a collector
   (`register_collector` in `index_ops.py`), not by editing the dispatch chain. The query and LLM
   layers stay source-agnostic, so the system grows by addition rather than surgery.
5. **Transparent over opaque.** Prioritization and deploy-readiness expose their reasoning —
   computed status, confidence, evidence, blockers — and narrate with an AI summary instead of a
   hard-coded verdict label. The operator can always see *why*.
6. **Incremental and non-destructive.** Every refresh is incremental and upserts by ID; nothing is
   silently re-downloaded from scratch or auto-deleted, and history is kept. The store accretes
   truth, it doesn't overwrite it.
7. **Honest about failure; self-repairing within bounds.** A failing job repairs itself through a
   bounded action menu, then escalates to a filed issue and stops — it never masks a failure as an
   "all fine" state. Destructive actions require explicit operator authorization and are never
   selected autonomously.
8. **Surface attention, don't dictate it.** The point is to show where attention actually went and
   what's ready to ship, so the operator rebalances deliberately. The system informs the decision; it
   doesn't bury it under a label.
9. **Docs are resumable runtime state (PDDA).** Long-running agent work must be stoppable, resumable,
   and handed off from the `PROJECT/**` docs alone — `ROUTER.md` is the front door, `ROADMAP.md`
   points, project docs hold detail, `CHANGELOG.md` logs dated outcomes, and nothing canonical lives
   in two places where it can drift. If reality and the docs disagree, the docs are the bug to fix.
10. **A win counts only once it's verified.** "Done" means the gates were actually run —
    `rebalance doctor`, `pytest tests/`, the PDDA checks — not that the work looks finished. An
    unverified claim of success is itself drift between the system and its record.
11. **Low-friction and portable.** Setup must be cheap (`install.sh`, a single front door, guided
    onboarding) and the contract cheap to obey — or operators and agents will route around it.

## How to apply

When adding a feature or making a tradeoff, ask: *does this keep work local and private, drive from
the one local evidence layer, stay transparent and honest about its own state — and can the claim
that it's done be verified?* If not, reconsider.

# Guiding Principles

North star for **rebalance**, the engine behind HiQs (High Quality Signals). When a choice is unclear, the option that yields higher-quality signals, kept local, wins. ARCHITECTURE.md is the *how*; this is the *why*.

## Purpose

rebalance ingests scattered work artifacts — Obsidian vault, GitHub, calendar, email, and Sleuth/Slack reminders — into one local store any MCP agent can query, so it can answer questions about *your* work, show where attention actually goes, and infer what's ready to ship — **without private data leaving the machine**. A second brain over your work first; a sprint and deploy-readiness planner as the payoff.

## The signal bar

Every output is a signal. A signal is high-quality only when it is all four:

- **Attested** — carries its receipts: source, evidence, confidence. Never a bare verdict.
- **Relevant** — ranked, not dumped. Volume is not value.
- **Fresh** — current, not stale. Refreshes are incremental or safely bounded so nothing rots silently.
- **Structured** — one shape, clean for people to read and for agents to feed on.

Fail a pillar, and the feature, source, or output isn't done.

## How it's built

1. **Local-first, private by default.** Private work never leaves the machine; a cloud LLM sees only what the operator sends. Non-negotiable — it is what makes rebalance usable for client work. Any feature that erodes it loses.
2. **One local store is canonical.** Every source runs `collect → normalize → store → query` into local SQLite (+ sqlite-vec); retrieval drives from that index, never from skimming live issues/PRs. Every surface — web view, Mac app, cloud mirror — is a read-only projection. Mirror, not migration; nothing canonical lives in two places where it can drift.
3. **Signal-agnostic, extend by addition.** Add a source by registering a collector, not by editing a dispatch chain; the query and LLM layers stay source-agnostic. A new source must clear all four pillars before it ships.
4. **Incremental where possible, non-destructive always.** Refreshes prefer delta syncs and upserts by ID. When a source only supports a bounded or full refetch, rebalance re-reads that scope and column-diffs/upserts without auto-deleting history. The store accretes truth; it does not overwrite it.
5. **Build durable, not band-aid.** Features, solutions, and fixes are built for long-term maintainability and durability. A band-aid is wasted work unless a demo strictly needs one.
6. **Honest; the operator decides.** Surface what's ready and where attention went — inform the call, never bury it under a label or act alone. A failing job self-repairs within a bounded menu, then files an issue and stops; it never masks failure as "all fine." Destructive actions require explicit authorization.
7. **Docs are resumable runtime state (PDDA).** Agent work is stoppable, resumable, and handed off from `PROJECT/**` alone — ROUTER points, project docs hold detail, CHANGELOG logs dated outcomes. If reality and the docs disagree, the docs are the bug.
8. **Done means verified.** "Done" is the gates actually run (`rebalance doctor`, `pytest`, PDDA checks), not work that looks finished. An unverified success claim is itself a low-quality signal.
9. **Low-friction and portable.** Setup and the contract stay cheap to obey, or operators and agents route around them.

## Applying this

Adding a feature or weighing a tradeoff, ask: *higher-quality signal — Attested, Relevant, Fresh, Structured — still local, and "done" verifiable?* If any answer is no, reconsider.

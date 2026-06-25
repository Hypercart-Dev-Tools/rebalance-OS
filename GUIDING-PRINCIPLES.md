# Guiding Principles

North star for **rebalance**, the local-first engine behind HiQs (High Quality Signals) — a CLI, MCP server, and scheduled syncs over one local store. When a choice is unclear, the option that yields higher-quality signals, kept local, wins. ARCHITECTURE.md is the *how*; this is the *why*.

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
2. **One local store is canonical.** Every source runs `collect → normalize → store → query` into local SQLite (+ sqlite-vec); retrieval drives from that index, not from skimming live issues/PRs. Every surface — web view, Mac app, cloud mirror — is a read-only projection. Mirror, not migration; nothing canonical lives in two places where it can drift.
3. **Signal-agnostic, extend by addition.** Add a source by registering a collector, not by editing a dispatch chain; the query and LLM layers stay source-agnostic. A new source must clear all four pillars before it ships.
4. **Incremental where possible, non-destructive always.** Refreshes prefer delta syncs and upserts by ID. When a source only supports bounded or full refetch, rebalance re-reads that scope and column-diffs/upserts — never auto-deleting history. The store accretes truth; it does not overwrite it.
5. **Build durable, not band-aid.** Durable means it removes the root cause and the next planned change builds on it — not a patch torn out when the obvious next feature lands. A band-aid is wasted work unless a demo strictly needs one, and a demo band-aid is tagged for removal so it isn't silently inherited.
6. **Least code that clears the bar.** Prefer reusing or extending what exists over adding new; the smallest change that stays secure, performant, maintainable, and durable wins. Net-new code is a cost to justify, not a default — deleting code counts as progress.
7. **Honest; the operator decides.** Surface what's ready and where attention went — inform the call, never bury it under a label or act alone. A failing job self-repairs within a bounded menu, then files an issue and stops; it never masks failure as "all fine." Destructive actions require explicit authorization.
8. **Docs are resumable runtime state (PDDA).** Agent work is stoppable, resumable, and handed off from `PROJECT/**` alone — ROUTER points, project docs hold detail, CHANGELOG logs dated outcomes. If reality and the docs disagree, the docs are the bug.
9. **Done means verified.** "Done" is the gates actually run (`rebalance doctor`, `pytest`, PDDA checks), not work that looks finished. An unverified success claim is itself a low-quality signal.
10. **Low-friction and portable.** Setup and the contract stay cheap to obey, or operators and agents route around them.

## Applying this

Adding a feature or weighing a tradeoff, ask: *higher-quality signal — Attested, Relevant, Fresh, Structured — still local, and "done" verifiable?* If any answer is no, reconsider.

---

## Appendix: AI Doc Review Heuristics

When reviewing any repo doc (roadmap entries, plans, architecture notes, audits, task writeups), apply these. Priority: local-first > signal quality > architectural cleanliness > implementation speed and operator friction.

**Heuristics**

1. **Local-first preserved?** Anything that sends private data off-machine without operator action → reject outright.
2. **Canonical store respected?** Reads/writes route through `refresh_index` / the collector registry, not leaf ingest functions. Bypass needs explicit justification.
3. **New scope classified?** Each scope is exactly one of raw source / derived scan / projection / export, and states whether it's `all`-eligible. If unstated, ask first.
4. **Done verifiable?** Names runnable gates (`rebalance doctor`, `pytest`, PDDA, smoke test). None = low-quality signal.
5. **Drift reduced, not created?** No duplicated docs, no execution detail added to ROADMAP.md, no reinventing a path ARCHITECTURE.md already documents.
6. **Next action singular?** One explicit next step, not buried in prose; status cells non-empty.
7. **Operator control explicit?** No silent retry, auto-repair, or masked failure; destructive ops surface before executing.
8. **Four pillars pass?** Each output is Attested, Relevant, Fresh, Structured. Fail one → not done.

**Tie-breakers**

- **Cleanliness vs friction:** choose cleanliness; flag friction as a design question, not a shortcut.
- **New surface vs reuse:** register a collector over forking a parallel path; if the orchestrator can't accommodate it, surface the gap.
- **Ambitious vs resumable:** a shorter plan an agent can resume cold beats a comprehensive one that buries state in prose.

**Reject or escalate when**

- A write path bypasses `index_ops.py` or a source-owned helper without justification.
- "Done" has no verification step.
- Adding a source requires editing the query layer, LLM synthesis, or MCP transport (Principle 3 violation).
- Hardcoded absolute paths or credentials (instead of resolving via `paths.py`), silent destructive operations, or opaque timing assumptions.
- ROADMAP.md would need execution detail to make the plan legible.
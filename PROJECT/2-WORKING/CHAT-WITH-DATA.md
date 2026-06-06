---
title: Chat with Your Rebalance Data
status: proposed
created: 2026-06-04
updated: 2026-06-05
owner: noel
tool_surface: chat_with_data(query, scope, top_k, skip_synthesis) — new MCP tool, NOT an extension of ask()
depends_on: semantic_index (vec0 ANN), index_ops incremental refresh, semantic_query MCP tool, ask_self code/doc RAG
phases: 0 spike · 1 hybrid retrieval · 2 native code corpus · 3 synthesis · 4 surface/UX
phases_done: 0 (federation spike — 7/10 federated vs 4/10 work-only)
phases_next: Phase 1 — Hybrid retrieval (FTS5 + vec, RRF) to close exact-match misses
decision_gates:
  - Phase 0 recall@k + latency → decide federate-vs-build-native
  - Phase 2 runs only if federation is insufficient or ask_self proves too fragile
non_goals: replacing ask(); a general chatbot; cloud inference; multi-user
---

# Chat with Your Rebalance Data

| ✅ Most recently completed | ▶️ What's next |
|---|---|
| **Phase 0 — Federation spike, complete** *(2026-06-05)*: `chat_with_data` ships (citations-first, RRF merge), wired to a dashboard **Filter\|Ask** search-bar switch via `POST /api/chat`. ask_self federation gated on availability (the mlx-embeddings gotcha → uses the rebalance venv). Eval (`scripts/chat_eval.py`, 10 questions): **federated 7/10 vs work-only 4/10**, ~2.1 s median, and federation surfaces *real code* (`index_ops.py`, `sleuth_reminders.py`) the work corpus never did. **Decision: federation is worth it.** | **Phase 1 — Hybrid retrieval**: add an FTS5 lexical index beside vec0 and fuse (RRF), to close the 3 exact-match misses (`auth_log`, `web.py`/`pulse_server`, `config`/keyring) that semantic-only ranking lost. |

## Table of Contents

- [Thesis & scope](#thesis--scope)
- [What we keep from the source analysis](#what-we-keep-from-the-source-analysis)
- [Architecture decisions](#architecture-decisions)
- [Phase 0 — Federation spike (prove value)](#phase-0--federation-spike-prove-value)
- [Phase 1 — Hybrid retrieval (the decisive fix)](#phase-1--hybrid-retrieval-the-decisive-fix)
- [Phase 2 — Native code corpus (conditional)](#phase-2--native-code-corpus-conditional)
- [Phase 3 — Synthesis layer (opt-in)](#phase-3--synthesis-layer-opt-in)
- [Phase 4 — Surface & UX](#phase-4--surface--ux)
- [Risks](#risks)
- [Appendix A — Source analysis (Codex)](#appendix-a--source-analysis-codex)

## Thesis & scope

Ship a **scoped, hybrid, citations-first** retrieval tool — `chat_with_data` —
that answers questions across rebalance's corpus. One tool, a `scope` selector
(`work` = vault/github/calendar/sleuth/email · `code` = source tree + GitHub
artifacts · `all`), so we don't overload the intentionally-broad `ask()`.

The corpus for **work artifacts already exists** (unified `semantic_documents`
+ `semantic_query`). The two real gaps are: (1) **no code corpus**, and
(2) **retrieval is vector-only**, which fails on exact developer questions
(identifiers, paths, class names, config keys, stack traces). Hybrid retrieval
is the highest-leverage change; the code corpus is the biggest missing surface.

## What we keep from the source analysis

- ✅ Separate tool, not an `ask()` extension — keep the boundary clean.
- ✅ **Hybrid** retrieval (lexical + vector), not ANN-only — *the* decisive call.
- ✅ Citations-first; synthesis optional/off by default (fast, debuggable, grounded).
- ✅ Federate `ask_self` first to ship fast; defer a native code collector.
- ✅ Phase-0 spike with 10 real questions; measure recall + latency before any LLM.
- ✅ Rich code-chunk metadata (path, language, symbol, parent_symbol, imports, git_sha).

Adjusted from the source analysis:

- ⚠️ Federation **inherits ask_self's setup fragility** (gemini key in Secret
  Manager, `ASK_SELF_PATH`, the rebalance venv / mlx-embeddings gotcha). Treat
  ask_self availability as a Phase-0 **hard gate** with rebalance-only fallback.
- ⚠️ Title is "chat with your **data**" — cover the work corpus too (scope=`work`),
  not just code.

## Architecture decisions

- [ ] Tool shape agreed: `chat_with_data(query, scope="all", top_k=8, skip_synthesis=True, repo=None)`.
- [ ] Response contract: always `citations: [{source, path, symbol, preview, score}]`; `answer` only when `skip_synthesis=False`.
- [ ] Ranking: reciprocal-rank fusion (RRF) of lexical + vector result lists.
- [ ] No cloud inference in the retrieval path; synthesis (Phase 3) is opt-in/local-first.

## Phase 0 — Federation spike (prove value)

Goal: a throwaway-quality prototype that proves merged retrieval answers real
questions, with numbers — before building anything durable.

- [x] Add prototype `chat_with_data(query, scope, top_k, skip_synthesis=True)` returning citations only. → `src/rebalance/chat.py`
- [x] Retrieve from `semantic_query` (work corpus) and `ask_self` (code/docs); merge via RRF, dedupe by `(source, path)`.
- [x] **ask_self availability gate**: `ask_self_available()` probes config/env + the wrapper; unreachable → work-only, no hard failure. (Found the mlx-embeddings gotcha — federation runs `ask-self-query.sh` with the **rebalance venv** as `ASK_SELF_PYTHON`.)
- [x] Build a fixed eval set of 10 real questions. → `scripts/chat_eval.py`
- [x] Record per-question recall@k + latency. → scorecard below
- [x] Write results to a short scorecard in this doc.
- [x] **Decision gate** → exact-match misses dominate the gap → **do Phase 1 (hybrid) next**, keep federation.

### Phase 0 scorecard (2026-06-05, top_k=8)

| run | recall@8 | latency median / p95 | sources |
|---|---|---|---|
| work-only (`--scope work`) | **4/10** | 32 ms / 2.3 s* | semantic_index |
| federated (`--scope all`, ask_self) | **7/10** | 2.1 s / 4.2 s | semantic_index + ask_self |

\* work-only first query pays the embed-model load (~2.3 s), then ~30 ms.

Findings: (1) federation ~doubles code recall and surfaces *actual code files*
(`index_ops.py`, `sleuth_reminders.py`, `health_issue_reporter.py`) the
work-only run never returned — its 4 "hits" were coincidental keyword matches in
GitHub PR/issue titles. (2) The 3 federated misses — `auth_log`, `web.py`/
`pulse_server`, `config`/keyring — are exact-identifier/ranking failures, the
canonical semantic-only weakness → motivates Phase 1. (3) Federation latency
(~2 s) is acceptable for an explicit "Ask"; it stays **off by default** for the
dashboard (gated on `ask_self_path` config / `ASK_SELF_PATH` env) so Filter and
work-only Ask stay snappy.

## Phase 1 — Hybrid retrieval (the decisive fix)

Goal: stop losing exact-identifier questions. Add a lexical index beside the
existing vec0 embeddings and fuse.

- [ ] Add an FTS5 virtual table over `semantic_documents` (content + key metadata).
- [ ] Keep FTS in sync with the existing incremental upsert/delete in `semantic_index` (same write path).
- [ ] Implement RRF fusion of ANN results + FTS results in `query()` (flag-guarded; ANN-only remains the fallback).
- [ ] Expose hybrid via `chat_with_data` and (behind a flag) `semantic_query`.
- [ ] Regression eval: the subset of exact-match questions ANN-only fails (paths, class names, config keys, a pasted stack-trace line) — hybrid must beat ANN-only on these.
- [ ] No latency regression beyond an agreed budget on the work corpus.

## Phase 2 — Native code corpus (conditional)

Runs only if Phase 0 shows federation is insufficient, or ask_self proves too
fragile to depend on.

- [ ] Add `"code"` to the allowed `source_type` set in `semantic_index._normalize_sources`.
- [ ] Code collector walks the local source tree; chunk by module / class / function.
- [ ] Populate `metadata_json`: `path, language, symbol, parent_symbol, imports, git_sha`.
- [ ] Wire incremental refresh into `index_ops` (mirrors vault/github: add/update/delete by source_pk).
- [ ] Hybrid retrieval (Phase 1) covers code chunks too.
- [ ] `chat_with_data(scope="code")` returns native results; ask_self federation becomes optional.
- [ ] Eval: code-recall on the Phase-0 question set improves vs federation.

## Phase 3 — Synthesis layer (opt-in)

- [ ] `skip_synthesis=False` composes an answer from retrieved citations only (never ungrounded).
- [ ] Local-first model path (Ollama/MLX); API optional and explicit.
- [ ] Contract enforced: answer always accompanied by citations; refuse to answer when no citations clear a score floor.
- [ ] Eval: faithfulness spot-check (every claim traceable to a cited chunk) on the 10-question set.

## Phase 4 — Surface & UX

- [ ] MCP tool registered + documented (tool list, README, MCP.md).
- [ ] Optional `rebalance chat` CLI (one-shot + REPL).
- [ ] Optional dashboard chat box on the pulse page (reuses the tool).
- [ ] Citations render as clickable `path:symbol` (Obsidian/GitHub deep links where possible).

## Risks

- **Semantic-only trap**: a vector-only code assistant fails on exact-match dev
  questions → mitigated by making Phase 1 (hybrid) precede any synthesis.
- **ask_self fragility**: federation depends on a separately-provisioned RAG →
  gated in Phase 0 with a rebalance-only fallback.
- **Scope creep into `ask()`**: keep `chat_with_data` a distinct, retrieval-first
  surface; do not fold calendar/temporal reasoning into it.
- **Index bloat / latency**: code chunks can dwarf the work corpus → measure
  latency every phase; keep an agreed budget.

## Appendix A — Source analysis (Codex)

> Preserved verbatim — the analysis this plan is derived from.

The repo already has most of the plumbing for a lightweight RAG. index_ops.py, semantic_index.py, and the query surface in ARCHITECTURE.md give you incremental refresh, a unified semantic_documents / semantic_embeddings corpus, and MCP-exposed retrieval via semantic_query. The important gap is that this is not yet a true code corpus. Today the unified index backfills vault, github, and email; it does not index the local source tree itself. So the missing piece is a code collector and a code-specific retrieval path, not a brand-new RAG system.

My recommendation is to keep it lightweight and avoid using querier.py as the primary "talk with your code" entry point. ask() is intentionally broad and mixes project, calendar, vault activity, and temporal context. For code chat, add a separate talk_with_code() tool that searches only code-adjacent sources: local code chunks, GitHub artifacts, and optionally architecture/docs. Also make it hybrid, not vector-only. The current unified search in semantic.py is ANN-only, which is fine for concepts but weak for exact identifiers, file paths, class names, config keys, and stack traces. For code, I would add:
- source_type="code" in semantic_documents, with chunking by module / class / function.
- Rich metadata in metadata_json: path, language, symbol, parent_symbol, imports, maybe git_sha.
- An FTS5 or other lexical index alongside vec0, then rank with a simple hybrid score.
- A response contract that always returns citations as file path + symbol + preview, with synthesis optional by default.

If you want the fastest path to something useful, I would not ingest source code into rebalance first. I would federate the existing external ask_self code index with rebalance's native semantic index and merge the top results. That ships faster and matches the repo's current split: rebalance already owns work-artifact RAG, while ask_self already owns code/document RAG. If the feature proves valuable, then unify later by adding a native code collector to rebalance.

Phase 0 should be a small spike, not a full feature build:
- Add a prototype talk_with_code(query, repo?, top_k?, skip_synthesis=True).
- Retrieve from ask_self plus semantic_query, merge and dedupe by file/path/source.
- Test against 10 real questions: "where is X orchestrated?", "what writes table Y?", "how does refresh flow into semantic index?", "what code owns MCP tool Z?".
- Measure latency and recall before adding any local LLM synthesis.

The main risk is building a semantic-only code assistant and discovering it fails on exact-match developer questions. The infrastructure is already there; the decisive design choice is hybrid retrieval plus a code-specific corpus boundary.

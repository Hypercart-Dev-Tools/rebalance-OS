---
title: Subsystem Refactor Phase 3 Research
status: draft
doc_type: phase-research
owner: Noel Saw
last_updated: 2026-06-10
branch: feat/subsystem-refactor
source_plan: PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md
---

# Subsystem Refactor Phase 3 Research

| Current assessment | Recommended next move |
|---|---|
| Phase 3 is ownership-first work. Parallel implementation before an ownership decision will produce conflicting diffs. | Lock the read-side ownership model first, then let implementation agents work inside that contract. |

## Table of Contents

1. [Executive answer](#executive-answer)
2. [Code-verified findings](#code-verified-findings)
3. [Why parallel implementation would conflict](#why-parallel-implementation-would-conflict)
4. [Ownership options](#ownership-options)
5. [Recommendation](#recommendation)
6. [Phase 0 technical spike](#phase-0-technical-spike)
7. [Merge-back guidance](#merge-back-guidance)

## Executive answer

Yes, I agree with the assessment.

Phase 3 is unusually sensitive to ownership because the repo currently has three overlapping read-side centers:

- `ask()` as the broad, mixed-context orchestrator and synthesis surface.
- `semantic_query()` as the unified semantic retrieval primitive.
- `chat_with_data()` as the newer scoped, citations-first retrieval surface.

That overlap is not just conceptual. It is already encoded in code and docs, and the current contracts pull in different directions. If multiple agents start "cleaning up Phase 3" without a locked ownership decision, they will reasonably make different choices about which surface is canonical.

## Code-verified findings

### 1. `ask()` is currently treated as the broad orchestrator

Evidence:

- `ARCHITECTURE.md:288-320` describes `querier.py::ask()` as the central query-layer orchestrator.
- `src/rebalance/ingest/querier.py:376-450` shows `ask()` gathering project, GitHub, vault, calendar, and temporal context, then optionally synthesizing.
- `src/rebalance/mcp/tools/retrieval.py:85-117` exposes `ask()` directly as an MCP tool with that broad contract.

Implication:

- `ask()` is not just retrieval. It is a mixed structured + semantic + temporal answer surface.
- Any plan that makes `ask()` the universal read primitive will couple retrieval cleanup to planning/synthesis behavior.

### 2. `semantic_query()` is already the unified semantic retrieval primitive

Evidence:

- `src/rebalance/mcp/tools/index.py:191-228` exposes `semantic_query()` and explicitly says to prefer it over `query_notes` and `query_github_context` for one ranked cross-source result set.
- `src/rebalance/ingest/semantic_index.py:671-733` defines the core unified retrieval contract, including source filters, `updated_after`, `repo`, and `hybrid` retrieval.

Implication:

- The repo already has a low-level canonical retrieval candidate.
- It is suitable as a primitive, but not sufficient on its own as the only user-facing read contract because it returns raw document hits rather than a product-shaped answer or citation experience.

### 3. `chat_with_data()` explicitly claims a separate boundary from `ask()`

Evidence:

- `PROJECT/2-WORKING/CHAT-WITH-DATA.md:39-42` says the tool exists so the repo does not overload the intentionally broad `ask()`.
- `PROJECT/2-WORKING/CHAT-WITH-DATA.md:52-54` keeps the boundary explicit: separate tool, hybrid retrieval, citations-first.
- `src/rebalance/chat.py:137-202` implements that shape today: `scope`, `citations`, `used_sources`, `elapsed_ms`, `answer`.

Implication:

- A Phase 3 implementation that folds `chat_with_data()` back into `ask()` would conflict with the current design intent of the chat-with-data workstream.

### 4. Legacy read surfaces still bypass the unified path

Evidence:

- `src/rebalance/mcp/tools/retrieval.py:11-49` still exposes `query_notes()` and `query_github_context()` directly.
- `src/rebalance/cli/query.py:15-128` still exposes vault-only `query`, keyword `search`, and broad `ask`.

Implication:

- Phase 3 is not just about picking one winner. It also needs an explicit facade policy for legacy per-source read surfaces.

### 5. Scope and result-shaping logic is duplicated already

Evidence:

- `src/rebalance/ingest/semantic_index.py:86-110` owns source normalization for unified semantic retrieval.
- `src/rebalance/cli/semantic.py:16-36` re-implements semantic source normalization in the CLI wrapper and explicitly comments that it is mirroring the core contract.
- `src/rebalance/chat.py:22-61` introduces a second source vocabulary (`all`, `work`, `code`) plus its own semantic source mapping and citation result shaping.

Implication:

- Phase 3 has a real DRY problem before any refactor begins.
- If ownership is not locked first, each agent will likely "fix" duplication around a different center.

## Why parallel implementation would conflict

Three reasonable but incompatible implementation instincts already exist:

1. An agent following `ARCHITECTURE.md` will treat `ask()` as the central read-side orchestrator and push other surfaces underneath it.
2. An agent following `CHAT-WITH-DATA.md` will preserve `chat_with_data()` as a separate tool and resist making it an `ask()` extension.
3. An agent following the MCP surface will treat `semantic_query()` as the canonical unified retrieval API and push wrappers toward it.

All three are defensible from the current tree. That is exactly why this phase needs a design decision first.

## Ownership options

### Option A — Make `ask()` the canonical read-side owner

Summary:

- `ask()` becomes the main public read API.
- `semantic_query()` becomes an internal helper.
- `chat_with_data()` is folded into `ask()` behavior or reduced to a thin alias.

Effort:

- High
- Expected refactor size: 4-6 focused days

Primary work:

- Add scope-aware document retrieval and citations contracts to `ask()`.
- Decide how broad structured signals interact with code chat and work-only retrieval.
- Rework MCP and CLI wrappers around the `QueryResult` shape.

Pros:

- One obvious top-level "read answer" entry point.
- Keeps the current architecture doc mostly intact.
- Simplifies mental model for operators who want one big question tool.

Cons:

- Blurs retrieval and synthesis ownership again.
- Fights the explicit chat-with-data direction that says "not an `ask()` extension."
- Makes code/doc chat inherit project, calendar, and temporal coupling unless aggressively re-separated.
- Raises regression risk for dashboard and pulse flows that already depend on `ask()` behaving as a broad planner/orchestrator.

Risks:

- High product-surface regression risk.
- High contract drift risk because `ask()` would need to satisfy both broad-planning and scoped-citations use cases.
- High review risk because behavior changes would be spread across docs, MCP, CLI, and prompt assembly.

### Option B — Make `chat_with_data()` the canonical user-facing read owner

Summary:

- `chat_with_data()` becomes the preferred interactive query surface.
- `semantic_query()` stays as the low-level retrieval primitive underneath it.
- `ask()` is reduced to a specialized synthesis/planning layer or becomes a legacy facade.

Effort:

- Medium-high
- Expected refactor size: 3-5 focused days

Primary work:

- Expose `chat_with_data()` through MCP and likely CLI.
- Finish its contract: source filters, repo behavior, optional synthesis, citations schema.
- Decide what non-document signals stay outside it versus get layered on top.

Pros:

- Best fit for the repo's newer citations-first direction.
- Keeps code/work retrieval cleanly separate from planning-oriented synthesis.
- Aligns well with future interactive surfaces.

Cons:

- `chat_with_data()` is not yet the transport surface the rest of the system is using.
- It does not currently cover project registry, calendar, or temporal reasoning.
- Requires an architecture-doc rewrite because the current docs still treat `ask()` as the central orchestrator.

Risks:

- Medium product-surface regression risk.
- Medium adoption risk because existing callers do not use this surface yet.
- Medium scope-creep risk if the phase tries to make `chat_with_data()` also solve planning and synthesis.

### Option C — Layered ownership split: `semantic_query()` for retrieval, `chat_with_data()` for interactive citations, `ask()` for broad synthesis

Summary:

- `semantic_query()` owns unified semantic retrieval.
- `chat_with_data()` owns the interactive, citations-first retrieval experience.
- `ask()` owns broad mixed-context reasoning and optional synthesis across structured plus semantic signals.
- `query_notes()` and `query_github_context()` remain temporary legacy facades.

Effort:

- Medium
- Expected refactor size: 2-4 focused days

Primary work:

- Extract a shared retrieval helper or adapter so `chat_with_data()` and `ask()` do not independently shape overlapping semantic recall.
- Mark legacy per-source tools as facades and test them that way.
- Normalize source vocabulary in one place and map product scopes to it.

Pros:

- Best fit to the code as it exists today.
- Minimizes blast radius by preserving each surface's intended role.
- Lets Phase 3 fix overlap without forcing a flag-day API collapse.
- Matches the plan's own requirement that no query path depend on a half-migrated abstraction.

Cons:

- Leaves multiple public read surfaces alive.
- Requires discipline in docs and tests so the boundaries remain explicit.
- Still needs a clear rule for where future features land.

Risks:

- Low-medium regression risk.
- Medium governance risk if the ownership table is not enforced in code and tests.
- Medium doc-drift risk if architecture and MCP docs are not updated in the same phase.

## Recommendation

Codex: Recommend Option C.

Reasoning:

- It fits the current code with the least forced rewrite.
- It resolves the ownership ambiguity without undoing the newer `chat_with_data()` work.
- It keeps `semantic_query()` where it is strongest: as the reusable retrieval primitive.
- It keeps `ask()` where it is strongest: as the broad answer/planning surface that can mix semantic recall with structured signals.

Gemini: Recommend Option C.

I strongly agree with the assessment and the recommendation of Option C.

The codebase currently has three distinct read-path abstractions that overlap in functionality but diverge in their product intent. 

Here is why the analysis of the current state and Option C is correct:

1. **`ask()` is too broad to be a low-level primitive:** `ask()` pulls in temporal context (today/tomorrow), calendar events, project registry, and GitHub activity. Making it the universal read primitive (Option A) would force the citations-first `chat_with_data()` to inherit all this heavy, structured planning context, breaking its scoped design.
2. **`chat_with_data()` is a presentation boundary, not a retrieval primitive:** It handles RRF merging, scope aliasing (`work`, `code`), and citation formatting. It relies on underlying retrieval functions to do the heavy lifting.
3. **`semantic_query()` is the correct low-level seam:** It already handles source normalization, freshness filters, and hybrid retrieval. 

Option C cleanly resolves this by layering them logically:
- `semantic_query()`: The unified raw retrieval primitive.
- `chat_with_data()`: The interactive, citations-first presentation layer (using `semantic_query()` under the hood).
- `ask()`: The broad, mixed-context orchestrator that synthesizes structured data (calendar, temporal, registry) alongside semantic recall.

By locking in this contract table first, we avoid the trap of cross-wiring these three surfaces in conflicting ways. Marking `query_notes()` and `query_github_context()` as legacy facades in the MCP tools is also the right move to prevent blast-radius regressions while cleaning up the core.




### Recommended ownership table

| Use case | Canonical owner | Notes |
|---|---|---|
| Raw unified semantic retrieval over indexed documents | `semantic_query()` | Lowest-level public retrieval primitive. Owns `sources`, `updated_after`, `repo`, `hybrid`. |
| Interactive citations-first querying over work/code/all | `chat_with_data()` | Must consume shared retrieval helpers instead of inventing its own semantics. |
| Broad cross-source question answering with project/calendar/temporal context and optional synthesis | `ask()` | Not the canonical retrieval primitive. It is the canonical mixed-context answer surface. |
| Vault-only semantic lookup | `query_notes()` | Legacy facade over older vault-specific index. Keep only for backward compatibility. |
| GitHub-only semantic lookup | `query_github_context()` | Legacy facade over older GitHub-specific corpus. Keep only for backward compatibility. |

### Contract rules to lock before implementation

- `semantic_query()` owns retrieval semantics.
  Source vocabulary, freshness filters, repo filters, hybrid behavior, and raw result shape are defined here.
- `chat_with_data()` owns presentation semantics for interactive retrieval.
  Scope aliases like `work` and `code`, citation formatting, and future opt-in synthesis belong here.
- `ask()` owns broad synthesis/orchestration semantics.
  Project registry, calendar, temporal framing, and planner-style context assembly belong here.
- Legacy source-specific query tools are facades only.
  They can remain for compatibility, but they do not define new read-side behavior.

### What this means for implementation sequencing

- First decide and document the ownership table.
- Then extract shared helpers for:
  - semantic source normalization
  - scope alias mapping
  - semantic-hit-to-citation shaping where applicable
- Then convert wrappers and tests.

Do not start by moving functions between modules. That would optimize structure before the contract is locked.

## Phase 0 technical spike

Keep this spike to 1-2 hours max.

Goal:

- Validate the ownership model against live callers before any code refactor.

Checklist:

- [ ] Trace every current caller of `ask()`, `semantic_query()`, `query_notes()`, `query_github_context()`, and `chat_with_data()`.
- [ ] Confirm which surfaces are operator-facing, dashboard-facing, MCP-facing, and doc-only today.
- [ ] Run 5 representative queries against:
  - `semantic_query()`
  - `ask(skip_synthesis=True)`
  - `chat_with_data()`
- [ ] Compare payload shape, scope behavior, latency, and whether each surface returns structured signals versus document hits.
- [ ] Lock the ownership table in the main Phase 3 plan before opening implementation work to multiple agents.

Decision gate:

- If a live caller depends on `ask()` for scoped citations-first retrieval, pause and revise the recommendation.
- If `chat_with_data()` is still doc-only and no active surface needs it soon, keep Option C but defer transport work until Phase 3b.

## Merge-back guidance

When this draft is merged back into `PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md`, Phase 3 should be tightened around the ownership decision explicitly.

Recommended changes to the main plan:

- Replace "decide which read API is canonical" with the locked ownership table above.
- Add a first-slice statement:
  Phase 3 starts with shared read-contract helpers and facade marking, not module movement.
- Add one compatibility rule:
  legacy query tools may remain only as tested facades over canonical owners, with removal criteria documented in the same phase.
- Add one test requirement:
  contract tests must prove that `semantic_query()` owns retrieval semantics and that `ask()` does not silently redefine them.

## Bottom line

Phase 3 is complex in the specific way you described.

It is not "hard because the code is messy." It is hard because the repo currently presents multiple plausible read-side owners, each supported by different live code and docs. The correct move is to make the ownership decision first, then let agents implement inside that boundary.

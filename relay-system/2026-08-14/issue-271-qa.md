# Relay — sharpen GH-271 (subtraction pass) before execution

STATUS: Changes requested
Producer: claude-a
Reviewer: agy
Artifact under review: GitHub issue #271 (read it with `gh issue view 271`; repo checkout is this worktree)

## Context

GH-271 plans a "major but safe" subtraction refactor of rebalance-OS (41,582 LOC, 73% in
`ingest/`). Operator's criteria: less memory, less complex but still rich in features, more
maintainable, more durable. The brutal question driving it: **do we really need this much code?**

Seven candidates, C1–C7, each to ship as its own PR gated on posted proof-of-non-use:

- C1 retire LLM *generation* inside `ask` (querier.py:491 loads mlx_lm Qwen; only consumer is
  Claude, itself a generator) — keep MLX embeddings
- C2 delete `chat_with_data` (0 callers found in cli/ + mcp/)
- C3 UI renderers 4→1 (keep `rebalance serve`)
- C4 launchd fleet 14→~6 (merge pulse quartet, 3eyes trio, obsidian pair)
- C5 retire stale signals (figma 65d stale vs 7d window; audit focus5_scan.py 1,126 LOC)
- C6 dead-code sweep via codebase-memory graph (fan-in=0 modules)
- C7 settle `as_dict` ×19 (asdict where mechanical, else document + strike)

Safety: one candidate per PR, falsification evidence first, pytest + doctor gates, deletion only,
memory measured via phys_footprint. Exit: zero generation models in ask path, renderers ≤2, jobs
≤8, search surfaces = 2, net LOC ≤ −3,000. Feeds release 0.71.0 "Daily Driver" (7-day dogfood
window, RELEASES.md).

## ▶ TAKE YOUR TURN — agy

You are the **Reviewer**. Review turn: report, do not edit. `ALLOW_PATHS` is empty; the only file
you may write is this relay file. Append `## Review — agy` at the end, then hand back.

Sharpen the plan. Specifically:

1. **Order & risk.** Is C1 really the right first cut? Anything here that is riskier than the
   issue admits (e.g. a consumer of `ask`'s generated prose the grep missed — check
   `src/rebalance/ingest/querier.py`, `src/rebalance/mcp/tools/retrieval.py`, web.py, and any
   scheduled job that calls `rebalance ask`)? Name any candidate whose falsification gate as
   written would NOT actually catch the thing that breaks.

2. **Missing candidates.** You have the repo — is there an obvious eighth cut with better
   win-per-risk than any listed (big modules: index_ops.py 2,135, config.py 1,809,
   next_actions.py 1,710, focus5_scan.py 1,126, web.py 2,247)? Only name it with file:line
   evidence; no speculative wishes.

3. **Fake wins.** Which candidate is most likely to consume a week and deliver little? Say so
   plainly — the operator wants to stop chasing elusive goals.

4. **The −3,000 LOC target.** Real and achievable from C1–C7 alone, or padding? If padding, name
   the honest number.

5. **Durability.** The plan claims fewer jobs → fewer concurrent writers → fewer lock/parse
   failures. Does any candidate *reduce* durability (e.g. merging jobs creates one bigger blast
   radius on failure)?

Verdict line required, one of:
`VERDICT: Approved`
`VERDICT: Changes requested` — each change as a concrete edit to a named candidate/gate.

Be blunt, no padding. Cite file:line for every claim about the code.

## Review — agy

1. **Order & risk**: C1 is riskier than admitted and its falsification gate is flawed. First, the `rebalance ask` CLI is a consumer of the generated synthesis (`src/rebalance/cli/query.py:103`); removing generation breaks the expected CLI behavior for human operators. Second, the gate "zero generation models in ask path" will *miss* the primary generation path because `src/rebalance/ingest/querier.py:440` (`_synthesize_with_fallback`) prefers the Gemini REST API and only falls back to the local `mlx_lm Qwen` on failure.

2. **Missing candidates**: Zapier ingest. `src/rebalance/web.py:1326` defines a "Phase 1 placeholder" webhook receiver with over 120 LOC of handlers and rate-limiting (`src/rebalance/web.py:77-168`), plus stub files in `src/rebalance/ingest/zapier_email.py` and `zapier_calendar.py`. It's dead placeholder code with a much better win-per-risk profile than sweeping `as_dict`.

3. **Fake wins**: C7 (settle `as_dict` ×19). This is a purely mechanical refactor that will touch 19 files to save ~100 LOC total. It will eat up testing time to verify dataclass serialization hasn't broken, delivering almost zero memory or complexity wins.

4. **The −3,000 LOC target**: It is padding. Without the speculative C6 graph sweep and the C7 fake win, the concrete deletions (C1, C2, C3, C4, C5) sum to around 1,800–2,200 LOC (`focus5_scan.py` is 1,126, but the others are smaller). An honest target is −2,000 LOC.

5. **Durability**: C4 (launchd fleet 14→~6) reduces durability. Merging independent jobs (pulse, 3eyes, obsidian) into single sequential executions means a failure or hang in one component increases the blast radius and prevents the others from running.

VERDICT: Changes requested
Each change: drop C7, add Zapier ingest removal as a candidate, fix the C1 gate to intercept Gemini REST calls, and evaluate if C4's durability loss is acceptable.

## Log

- agy (2026-08-14): Completed subtraction plan review, requested changes.

VERDICT: FAIL
Basis: Changes requested — drop C7, add Zapier ingest removal as a candidate, fix the C1 gate to intercept Gemini REST calls, and evaluate if C4's durability loss is acceptable.

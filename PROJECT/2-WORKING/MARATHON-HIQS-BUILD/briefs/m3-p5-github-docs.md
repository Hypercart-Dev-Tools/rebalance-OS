---
title: "M3 p5 — github.py docs(): make issues and PRs searchable"
status: "Brief authored; phase not yet run"
created: 2026-08-03
updated: 2026-08-03
owner: noel
gh_issue: TBA
roadmap_exempt: true
doc_type: project
goal: >
  Marathon phase brief (harness input, not a tracked effort). Builds one module of the HiQS
  v1.0 core against the contract in PROJECT/2-WORKING/HIQS-PROJECT.md, which stays canonical.
---
# M3 p5 — github.py `docs()`: issues and PRs into the search index

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-08-03 from §6.6, after mined queries showed the corpus could not answer them. **Not yet run.** | Runs after `hiqs-m3-p4`. **Blocks operator checkpoint A** — the retrieval eval is not meaningful until this lands. |

**Canonical spec:** `HIQS-PROJECT.md` §6.5 (why), §6.6 (what), §5 rule 2 (attestation), §9
(`docs`). Tie-breakers: `HiQS/GUIDING-PRINCIPLES.md`.

## Why this exists — read this before touching the code

`github.py` ships `fetch` and `candidates` but **no `docs` provider**. GitHub items therefore reach
the ranking and never the search index, so the searchable corpus is the vault alone — **63 markdown
files**.

Questions mined from the operator's own history are overwhelmingly about repos, issues, commits and
branches. Running the Phase 1 retrieval eval in the current state would score both embedding models
on questions whose answers **are not in the index at all**, both would score near zero, and the
vector-leg gate would report *"vectors do not justify torch"* — a permanent dependency decision
resting on a corpus that could not answer the queries. Cluster B, inside the instrument built to
prevent it.

This is a **plan gap, not a defect in p1–p4**. `docs` is optional in the §5 contract and Phase 2
never required it. Nothing already built is wrong; something is missing.

## Build

Add `docs()` to `HiQS/hiqs/sources/github.py` and wire it into `SOURCE`:

- One `Doc` per issue or PR, from **title + body**.
- `id` = `github:<owner>/<repo>#<number>` · `source` = `"github"` · `unit` = the repo.
- `ts` = `activity_at`. **Never `updated_at`** — L20 is explicit that it is bumped by label and
  assignee edits that indicate no real movement, and a stale item must not be able to masquerade
  as fresh.
- `author` and `url` carry their real values; `""` only when the row genuinely lacks them.
- One item is one document. Do not chunk; GitHub bodies are short relative to notes, and the
  existing 2-chunk-per-document cap after RRF already prevents flooding.

## Acceptance

- Issues and PRs are returned by `search()`, alongside vault documents, in one ranked result.
- **`unit` is the repo, and reconciliation is authorised only by `SyncReport.units_ok`** — the same
  rule as vault, with no new deletion path and no exception to §5 rule 2. Prove it: a run where one
  repo's fetch fails leaves that repo's documents completely intact while a sibling repo whose
  fetch succeeded reconciles normally.
- **A closed issue is still retrievable.** Test it explicitly. Half the operator's real questions
  are archaeology — *did we finish that, why was it built that way* — so excluding closed items
  would delete exactly the answers being asked for. `state` rides on the row for the ranker to
  discount; retrieval does not filter on it.
- `ts` comes from `activity_at`, pinned by a test: an item whose only change is a label edit must
  not appear fresher.
- The sole-writer contract still holds — `docs` has exactly one writer, and the AST test still
  sees it (including `async def`).
- Idempotent: two consecutive projections over unchanged items produce zero inserts and zero
  updates.
- **Report the resulting corpus size.** §6.3's n was set against an unknown corpus and the real
  figure changes whether the retrieval eval can resolve anything at all. A count, not an
  impression.

## Do not

- Do not chunk GitHub items by heading. That is a vault-shaped solution to a problem GitHub does
  not have, and it multiplies rows for no retrieval gain.
- Do not filter closed items out of retrieval. See above — it is the single most likely
  "reasonable" change that would silently destroy the eval's value.
- Do not read `updated_at` for `ts` because it is conveniently present. L20 exists because that
  exact substitution already shipped once.
- Do not add comments or review threads in this phase. Titles and bodies first; the corpus effect
  is measurable before deciding whether more volume helps or just adds noise.
- Do not touch the vault source, the projection's reconciliation logic, or the ranking. This phase
  adds a provider; it changes no existing contract.

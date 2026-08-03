---
title: "M3 p4 — reference linking: note text to GitHub item"
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
# M3 p4 — reference linking (note → GitHub item)

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-08-03 from §6.4, added after the operator's seed questions exposed the gap. **Not yet run.** | Runs last in M3. Needs `github_items` populated by p1. |

**Canonical spec:** `HIQS-PROJECT.md` §6.4 (Q2), §5 rule 1 (one writer per table).
Tie-breakers: `HiQS/GUIDING-PRINCIPLES.md`, especially **D5** (structure is a field, not a parse).

## Why this exists

The operator asked: *"What did we decide on with XYZ to phase out the Bash scripts on which GH
issue?"*

That is two joined asks — find the decision (which lives in a note), then name the artifact
carrying it (which lives in GitHub). Retrieval can already surface the note. **Nothing today
carries the edge from that note to the issue**, so the second half of the question is
unanswerable no matter how good retrieval gets.

## Build

In the projection, record GitHub references that appear **literally** in a document's text:

- Bare issue/PR references — `#123` — resolved against the repo the document is associated with.
- Full GitHub URLs — `https://github.com/<owner>/<repo>/issues/123` and the `/pull/` form.
- `owner/repo#123` shorthand.

Store the edge as a **field**, at projection time. Do not re-derive it at query time by scanning
body text — that is D5's exact prohibition, and it is the defect this build already paid for once
when unit membership was recovered by splitting ids on `:`.

A reference is a link, a link is one of the four ATTESTED receipts, and receipts live in fields.

## Acceptance

- A note containing `#123` yields an edge to the corresponding `github_items` row, and a query
  matching that note can return the linked item alongside it.
- **Unresolvable references are dropped, not guessed.** `#123` with no repo context, or pointing
  at an item not in `github_items`, produces **no edge** — never a fabricated one, never a
  placeholder row. An unresolved reference is `unknown`, and `unknown` is a real state (§8).
- **False-positive resistance, tested explicitly.** `#123` inside a fenced code block, inside a
  URL fragment, or in prose like "issue #1 of the newsletter" must not create an edge. Test the
  code-fence case specifically — it is the common one in an engineering vault.
- Idempotent: re-projecting an unchanged note produces zero edge inserts and zero updates.
- Edges are reconciled **within the unit** that produced them, under the same attestation rule as
  every other projected row (§5 rule 2, `SyncReport.units_ok`). A note whose fetch failed keeps
  its existing edges.
- One writer. Whatever table or column holds these edges has exactly one writing function, pinned
  by the same AST sole-writer test that guards `docs` — and that test must see `async def`, which
  it did not until it was fixed in M2.

## Do not

- **No entity extraction, no inference, no LLM.** If the note does not literally name the issue,
  there is no edge. Inferring an unstated link is not v1 work; it is a quality claim with no
  detector, which §2 forbids.
- Do not create a new top-level module for this. It belongs in the projection that already writes
  `docs`.
- Do not let a reference edge influence ranking. It changes what can be **returned together**,
  not what ranks **higher**.
- Do not scan GitHub bodies for vault references in this phase. One direction only — note → item.
  The reverse has a different false-positive profile and no seed question asking for it.

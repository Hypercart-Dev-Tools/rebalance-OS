---
title: "M3 p3 — affinity.py: sibling-project edges that widen search"
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
# M3 p3 — affinity.py: sibling-project edges

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-08-03 from §6.4, added after the operator's seed questions exposed the gap. **Not yet run.** | Runs after `hiqs-m3-p2`. Needs `github_items` populated, so it cannot precede p1. |

**Canonical spec:** `HIQS-PROJECT.md` §6.4 (Q3), §9 (`project_affinity`), §11 (~80 LOC),
§19.2 (disclosure). Tie-breakers: `HiQS/GUIDING-PRINCIPLES.md`.

## Why this exists

The operator asked: *"What tasks did I work on the Binoid repo project?"* — and in their own
words, *"repo queries need affinity repos (same client/related projects) so a broad question can
cast a wider net if an operator does not ask a precise question."*

`projects(name, aliases_json, repos_json)` maps one project to **its own** repos. There is no
notion of a **sibling** project, so a deliberately broad question returns a thin, precise answer.
That reads to the operator as *"not much happened"* when the truth is *"you asked narrowly."*

**This is a recall failure that presents as a content failure** — cluster B, trusting the
measurement instead of the thing measured. It is not a nice-to-have; it is the failure mode the
whole project exists to eliminate, arriving through the retrieval path instead of the health path.

## Build

`HiQS/hiqs/affinity.py` (~80 LOC) plus the `project_affinity` table in `db.py`:

```
project_affinity  project_a, project_b, edge, weight   PK (project_a, project_b, edge)
```

Three edge classes, cheapest and most reliable first:

1. **`same_org`** — two projects whose repos share a GitHub owner. **Free and inference-free:**
   the owner is already on every `github_items.repo` row. No heuristic, no guessing.
2. **`name_token`** — shared significant name tokens, over a generic-token stoplist (`app`, `web`,
   `api`, `tools`, `dev`, `test`, `main`, digits, and similar). Tokens shorter than 3 characters
   never form an edge.
3. **`issue_title`** — a query term appearing in issue titles across sibling repos, per the
   operator's suggestion. This is the only edge that is query-dependent; compute it at query time,
   do not persist it as a row.

Persist edges 1 and 2. Store symmetric pairs **once**, canonicalised so `project_a < project_b`.

Consumed by `search()` as a **post-fusion widening step**, after RRF and after the per-document
cap, never before.

## Acceptance

- **Affinity widens, it never narrows.** Siblings are appended *below* the direct hits. A precise
  query returns **byte-identical** results with affinity on and off — pinned by a test that runs
  both and compares. If widening can reorder or displace a direct hit, it is wrong.
- **Every widened row carries the edge that pulled it in**, so an affinity hit arrives with its
  receipt like any other signal (ATTESTED). A row that cannot say why it is present is a bare
  claim and fails.
- **A bad edge class can be switched off** without re-deriving anything, because `edge` is stored
  per row rather than collapsed into a score.
- **No client or project literal anywhere in the module.** A test greps `affinity.py` for the
  operator's known client and project names and **fails on a hit**. Grouping is derived from data
  at runtime, never from a string in a regex.
- **The broad query beats the narrow one on coverage.** Seed the fixture with two repos in one
  org, query the org's colloquial name, and assert work from both comes back. Record it as a
  coverage figure, not a pass/fail vibe.
- `same_org` alone produces useful edges on the fixture **without** `name_token` enabled — the
  free edge must carry its own weight, so a later decision to drop the heuristic edge is cheap.
- Deterministic and offline. No network. Edges derive from rows already in the database.

## Do not

- **Do not port `src/rebalance/ingest/project_inference.py`.** It works, and it is the source of
  the *idea*, but it is 981 LOC of accreted heuristics and `_owner_group_key()` matches owners
  ending in `team|cbd` — **a client vertical hardcoded into a regex.** That is simultaneously a
  portability failure and exactly the kind of string §19.2 must keep out of a repo that becomes
  public. Take the idea; leave the code. The clean-room import test will reject the import anyway.
- Do not let affinity influence ranking weight. It changes **what is retrieved**, never **how
  retrieved things are ordered**. Ranking is §7's job and has its own detector.
- Do not infer affinity from the vault, note contents, or filesystem layout in this phase. GitHub
  org and name tokens only. More sources means more ways to be confidently wrong, and the eval
  cannot yet tell you which.
- Do not create a config file of hand-maintained project groupings. That is a registry with a
  lifecycle, which §14 already parked with a stated re-add trigger.

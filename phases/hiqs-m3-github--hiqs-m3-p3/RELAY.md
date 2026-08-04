# Marathon Phase hiqs-m3-p3
STATUS: Open
NEXT: codex

<!-- marathon-drive: task=MARATHON-HIQS-M3-P3-TURN builder=codex reviewer=agy round-cap=9 -->

## Phase Brief

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


---

▶ TAKE YOUR TURN (codex — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): HiQS/hiqs/affinity.py,HiQS/hiqs/db.py,HiQS/hiqs/search.py,HiQS/tests/test_affinity.py,HiQS/tests/test_search.py,HiQS/tests/test_db.py
2. Append a build block to this relay file: `### Round N · Builder · codex` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick claim MARATHON-HIQS-M3-P3-TURN --agent codex --paths "phases/hiqs-m3-github--hiqs-m3-p3/RELAY.md,HiQS/hiqs/affinity.py,HiQS/hiqs/db.py,HiQS/hiqs/search.py,HiQS/tests/test_affinity.py,HiQS/tests/test_search.py,HiQS/tests/test_db.py"
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick ping MARATHON-HIQS-M3-P3-TURN --agent codex
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M3-P3-TURN --agent codex --to agy
4. Edit ONLY these paths: phases/hiqs-m3-github--hiqs-m3-p3/RELAY.md and HiQS/hiqs/affinity.py,HiQS/hiqs/db.py,HiQS/hiqs/search.py,HiQS/tests/test_affinity.py,HiQS/tests/test_search.py,HiQS/tests/test_db.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.
5. HAND OFF EXPLICITLY (GH-268): after releasing the token, end your turn by naming who acts next —
   "handing off to agy — agy, take your turn." A turn that ends without that line
   leaves a human guessing whether the relay is waiting on them or has stalled. Do this EVERY round,
   not just the first.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: HiQS/hiqs/affinity.py,HiQS/hiqs/db.py,HiQS/hiqs/search.py,HiQS/tests/test_affinity.py,HiQS/tests/test_search.py,HiQS/tests/test_db.py. REVIEW THE WHOLE FILE, NOT JUST THE DIFF (GH-268): a beta test had this loop reach 'Approved' in two rounds while an independent audit of the same branch found 20 issues (1 critical, 4 high) — every one of them in the pre-existing code the change sat on, which nobody had read. Pre-existing defects in a file you are touching are IN SCOPE; say so explicitly if you find none. DECLARE IT: your review block MUST contain a literal 'swept file: yes' or 'swept file: no' line — without it a reviewer that skipped the sweep is indistinguishable in the transcript from one that did it and found nothing, which is exactly how those 20 issues stayed invisible.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M3-P3-TURN --agent agy --to codex
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick done MARATHON-HIQS-M3-P3-TURN --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/hiqs-m3-github--hiqs-m3-p3/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
5. HAND OFF EXPLICITLY (GH-268): end your turn by naming who acts next — "handing off to codex —
   codex, take your turn" when requesting changes, or "relay closed, no further turn needed" when
   approving. The beta report singled this out: the Reviewer turn did not tell the user to go back to the
   Producer, so the relay looked stalled when it was simply waiting. Do this EVERY round.

### Round 1 · Builder · codex

Implemented the HiQS affinity seam in the permitted files only.

- Added the canonical `project_affinity` schema and local edge rebuild for same-org and optional shared significant-name tokens. Generic and short tokens are excluded; each symmetric pair is persisted once.
- Added query-time issue-title edges, plus `AffinityDoc.affinity_edge` so every widened hit is attested. Stored edge classes can be disabled at query time without recomputation.
- Wired widening after hybrid fusion, per-document cap, and reranking. Direct hits stay untouched and retain their original order; siblings only fill unused result capacity.
- Added schema, derivation, attestation, disabling, query-time, and precise-search parity coverage.

Verification: `PYTHONPATH=HiQS python -m pytest HiQS/tests/test_affinity.py HiQS/tests/test_search.py HiQS/tests/test_db.py -q` → 17 passed.

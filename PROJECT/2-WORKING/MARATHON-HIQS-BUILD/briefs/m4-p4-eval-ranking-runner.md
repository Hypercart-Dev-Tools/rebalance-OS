---
title: "M4 p4 — eval_ranking.py: the runner, not the judgment set"
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
# M4 p4 — eval_ranking.py: the runner, NOT the judgment set

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-08-03 and preflighted — `marathon.sh --dry-run` resolves this phase in execution order. **Not yet run.** | Runs after `hiqs-m4-p3` is approved. **Operator checkpoint B follows M4** — OAuth consent + 20–30 real mornings. |

**Canonical spec:** `HIQS-PROJECT.md` §7.1 (protocol, metrics, four gates), §19.2 (public/private
split), §8.

## READ THIS FIRST — the hard boundary

You are building the **runner**. You must **not** author `eval_ranking.json`, and must not
generate, suggest, or seed snapshots or judgments. §7.1 requires the operator's own top-5 for real
mornings, recorded **before** seeing HiQS's output, across days that have not happened yet. A
model-authored judgment set measures the model's own persuasiveness. If the file is absent, report
loudly and exit non-zero.

## Build

`HiQS/tests/eval_ranking.py` — offline, fixture-backed:
- Metrics: **top-5 overlap**, **pairwise inversion rate**, **obligation coverage** (% of ranked
  items with `owed_by` or `due` populated), **staleness leakage** (% of top-5 whose
  `source_status != "ok"`).
- The four gates, implemented and unit-tested against synthetic scores:
  1. **Floor** — top-5 overlap >= 3/5 average. Fails → Phase 3 does not exit.
  2. **Beats recency** — >= 1 item over a recency-only baseline.
  3. **Obligation coverage** — >= 50%.
  4. **Staleness leakage** — zero top-5 items from an `error` source.
- Writes a `rank.evaluated` event; the recorded SHA spans the committed file **and** the sidecar.
- **Public/private split (§19.2):** committed file carries opaque ids and pairwise judgments; the
  candidate text lives in a gitignored sidecar. Sidecar absent → loud `unknown`, never a silently
  scored subset.

## Acceptance

- Gate arithmetic unit-tested at the boundaries, including the case a review caught: recency at 1/5
  and ranker at 2/5 **passes** gate 2 and **fails** gate 1. That interaction is why the floor exists.
- Reproducible across runs on the same inputs.
- `status.ranking.quality` reads from the written event, not a constant (L22).
- A failing gate blocks; there is **no override flag in the code**. An operator override is a
  recorded decision in the CHANGELOG plus a tenet reword, not a command-line switch.

## Do not

- Do not author snapshots or judgments, even as a fixture that could be mistaken for real. Use
  obviously synthetic ids.
- Do not implement a "close enough" or partial-credit mode.

---
title: "GH-250 marathon scope — why R1, R4 and R5 are not in the plan"
status: "R1 waived, R4 and R5 executed 2026-08-14; exclusions held up in practice"
created: 2026-08-04
updated: 2026-08-14
owner: noel
gh_issue: 250
doc_type: project
goal: >
  Record why three of GH-250's seven items were kept out of the unattended marathon, so the
  exclusion stays a documented decision rather than an omission someone later "fixes".
---

# GH-250 marathon scope — why R1, R4 and R5 are not in the plan

## Status

| What was just completed | What's next |
|---|---|
| All three exclusions were vindicated in practice on 2026-08-14. R4 needed a human window and got one; the run aborted mid-way on a live writer and required judgement to resume, exactly what an unattended agent could not have supplied. R5 shrank from a predicted multi-hour pass to 6,757 documents, as this doc predicted once the writer fix landed. R1 was time-gated as described and was ultimately waived by the operator for wall clock rather than satisfied. | Nothing in this doc. It is a record of a scoping decision, and the decision is closed. It archives with the rest of GH-250 once the issue is closed. |

The request was a marathon that runs **R1 through R7 non-stop**. Three of those seven cannot
honestly live in an unattended chain. This file records why, so the exclusion is a documented
decision rather than an omission someone later "fixes" by adding them back.

## Excluded

### R1 — verify orphan growth is flat  ·  *time-gated, not work-gated*
R1's whole content is "observe production across >=3 `github_sync` cycles." Syncs fire 18x/day,
roughly 80 minutes apart, so the check needs **~4 hours of wall clock** during which nothing can
be done to hurry it. A marathon phase has only two ways to represent that: sleep (burning a turn
budget to do nothing) or assert immediately against one cycle (which is not the check — the bug
only manifests on *re*-sync, exactly the failure mode the regression test had to be designed
around). Neither is honest. R1 is a scheduled observation, so it belongs to a scheduled job.

**Instead:** `p2` ships the invariant as a `doctor` check. Once it is live, R1 is satisfied by
reading `doctor` output after the cycles elapse — no marathon required.

### R4 — execute the reclaim on production  ·  *irreversible, needs a human window*
A `DELETE` of ~2.68M rows followed by `VACUUM` on a 13.4 GB production database is the single
most destructive action in this whole effort. It rewrites the file, needs exclusive access, and
has no undo beyond restore-from-backup. An adversarial review already rejected running it without
a rehearsed runbook (GH-248, 6 blockers). Handing it to an unattended agent — which cannot judge
whether a mid-run anomaly means "keep going" or "stop and restore" — inverts that finding.

**Instead:** `p5` rehearses the identical code path against a throwaway **copy** and proves the
reclaim math, `integrity_check`, and before/after counts. After the marathon, R4 is a human
running an already-rehearsed script inside a maintenance window.

### R5 — backfill missing embeddings  ·  *depends on R4, and self-sabotaging*
R5 cannot start until R4 has landed. It is also a multi-hour MLX embedding pass over ~15–19k
documents — precisely the workload that trips the `job_guard` compressor ceiling (observed
2026-08-04 06:34, 16.9 GB vs a 16.0 GB ceiling, run failed fatally) and the workload behind the
46.9 GB runaway in GH-215. Running it unattended on a box already under desktop memory pressure
would most likely fail mid-way and leave partial state.

**Instead:** after `p1` lands, R5 shrinks dramatically on its own — an idempotent writer stops
re-orphaning 15.5k documents per sync, so the backfill set becomes small and stable instead of a
sawtooth. Re-scope R5 against real numbers once R1 confirms flatness.

## Included

| Phase | GH-250 item | Why it is safe unattended |
|---|---|---|
| `p1` | R7 idempotent writer | Pure code + tests, reviewed, gated on tests |
| `p2` | R6 zero-orphan invariant | Pure code + tests; read-only against the db |
| `p3` | R2 reclaim runbook | A document |
| `p4` | R3 fencing script | Script + tests; restore path is trap-guaranteed and tested |
| `p5` | R4 *rehearsal* | Operates only on a copy; asserts it never touches the live path |

## Ordering note

Phases run **strictly one at a time** (GH-241) — `depends_on` constrains order, it does not create
parallelism. The chain here is genuinely sequential anyway: `p2`'s invariant should be able to
assert the post-`p1` behaviour, and `p5` rehearses the runbook `p3` wrote using the fence `p4`
built.

## Highest-value item

`p1` (R7). The already-merged #249 made the writer *correct*; it is still *wasteful*, re-embedding
~15.5k byte-identical documents every run — roughly 280k needless embedding operations per day,
which is what keeps the MLX pass hot and the compressor ceiling in play. If only one phase ever
runs, it should be this one.

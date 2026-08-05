# Marathon Phase vb2
STATUS: Open
NEXT: agy

<!-- marathon-drive: task=MARATHON-VB2-TURN builder=agy reviewer=codex round-cap=7 -->

## Phase Brief

# p2 — R6: zero-orphan invariant in doctor, sawtooth-aware

> ## ⚠️ Sandbox constraint — do NOT run the full test suite in your turn
>
> Verified 2026-08-04: MLX cannot enumerate a Metal device inside the codex/agy turn sandbox
> (`-s workspace-write`). Any test that performs an MLX device operation **hard-crashes the whole
> Python process with SIGABRT** — `mlx::core::metal::Device::Device()` indexes an empty device
> array, throws an ObjC exception, and aborts. This is NOT catchable: `tests/conftest.py` guards
> only `ImportError`, and an abort bypasses `try/except` entirely. Three crashes in ~4 minutes were
> traced to exactly this (parent process `codex`).
>
> MLX works fine outside the sandbox on this machine (M1 Max, Metal 3), so this is a turn-sandbox
> limitation, not a broken repo.
>
> **Run only this** (the interpreter matters — see below):
> ```
> PYTHONPATH="$PWD/src" /Users/noelsaw/Documents/rebalance-OS/.venv/bin/python -m pytest \\
>   tests/test_github_direct_commits.py tests/test_db_github.py \\
>   tests/test_github_knowledge.py tests/test_github_coverage.py -q
> ```
> Verified clean (33 passed). Add the specific new test file for your phase.
>
> **Why not plain `python`:** your isolated worktree has NO virtualenv — `.venv/` is gitignored,
> so it does not exist there and bare `python` either is not found or cannot import `rebalance`.
> Use the absolute interpreter above. **Do not go looking for a working environment in the real
> repo root** — that is an isolation breach and the shim will fail your turn (it already did once).
>
> **Why `PYTHONPATH="$PWD/src"`:** that venv has rebalance installed *editable*, pointing at the
> MAIN repo's `src/`. Without PYTHONPATH your edits in the worktree are not what gets imported, so
> you would be testing the wrong code and a green run would mean nothing.
>
> Never `pytest tests/` — it collects the MLX suite. As of GH-250 those tests skip cleanly via the
> `requires_metal` marker rather than aborting, but the full suite is still slow and carries
> unrelated pre-existing failures (5 order-dependent in test_hiqs_pipeline.py, 1 in
> test_scheduler_liveness.py). Stick to the scoped command.




## Why this phase exists

The bloat reached **12.19 GB — 92.3% of the database, 99.65% of vectors orphaned** — with no alarm
of any kind. A 92x vectors-per-document ratio should have been loud within a day. Nothing measured
it, so nothing said anything for ~9 days. p1 stops the bleeding; this phase is what makes the next
occurrence of *any* similar defect visible within hours rather than after 10 GB.

## The trap to avoid

GH-248 proposed asserting the ratio `count(github_embeddings) / count(github_documents)` stays
"near 1.0". **Do not implement that.** It is wrong three ways:

- No denominator-zero behaviour (a fresh install has 0 documents).
- It false-positives constantly mid-embed-cycle: coverage is a **sawtooth** (measured 9.7% missing
  at 11:20 and 67.9% at 16:26 the same day). A ratio check would page on healthy operation.
- It conflates two independent failures — orphaned vectors (a corruption) and unembedded documents
  (a backlog). They need different thresholds and different responses.

## What to implement instead

Two separate checks with different severities:

### 1. Orphaned vectors — a HARD invariant, threshold zero
"Every vector's `doc_id` resolves to a live document." This is never legitimately non-zero, so it
needs no tolerance and no time-window smoothing.

```sql
SELECT COUNT(*) FROM github_embeddings e
WHERE NOT EXISTS (SELECT 1 FROM github_documents d WHERE d.id = e.doc_id)
```

Do the same for `semantic_embeddings` vs `semantic_documents` — that path is currently correct, and
this is how it stays correct. Report as **FAIL** when non-zero, with the count and the estimated
wasted bytes (`orphans * dim * 4`).

### 2. Embedding backlog — a soft, sawtooth-aware check
Unembedded documents are normal right after a sync and abnormal only if they *persist*. So do not
alarm on the instantaneous value. Options, in preference order:

- Alarm only if the backlog has been non-zero **and non-decreasing** across N consecutive checks
  (needs a small persisted counter — follow whatever pattern `collector-health` already uses for
  state; do not invent a new store if one exists).
- Failing that, report it as INFO with the raw count and make no pass/fail claim.

Choose one, and state in the relay file why. **An INFO line that never lies is worth more than a
WARN that cries wolf every sync** — a check the operator learns to ignore is worse than no check.

## Also report (INFO, no threshold)

- `github_embeddings` byte size and its share of total database size — the number that would have
  made this defect obvious on day one.
- `freelist_count`, so reclaimable-vs-live space is legible at a glance.

## Where it goes

- Query helpers into `src/rebalance/ingest/db/github.py` (and the semantic equivalent in
  `db/semantic.py`) — never inline SQL in the doctor/CLI layer.
- Wire into the existing `rebalance doctor` check registry, which lives in
  **`src/rebalance/doctor.py`** — that exact file. Do NOT create `src/rebalance/cli/doctor.py`;
  it does not exist and is not the registry. (A previous attempt at this phase was failed by
  containment for editing off-allowlist paths after the allowlist named the wrong file.) **Read how neighbouring checks register,
  format, and set severity, and match it exactly** — do not invent a parallel reporting shape.
- Must be strictly **read-only** and must open the database read-only. `doctor` runs while
  collectors are live; it must never contend for the writer lock.

## Tests — new file `tests/test_github_vector_invariants.py`

1. Clean fixture → orphan check passes, count 0.
2. Hand-insert a vector for a `doc_id` that does not exist → check FAILS, and the message contains
   the count and the wasted-byte estimate.
3. Delete a document out from under a vector → check FAILS (this is the production shape).
4. Backlog check does **not** fail on a freshly-synced-but-unembedded corpus — the sawtooth
   false-positive guard. This is the most important test here; a check that fires on healthy
   operation will be disabled by the operator within a week.
5. Same coverage for the `semantic_*` pair.
6. Assert the checks perform no writes — e.g. run against a read-only connection and confirm no
   exception.

## Definition of done

- `rebalance doctor` fails loudly on a single orphaned vector, in either embedding family.
- It stays quiet through a normal sync-then-embed cycle.
- The size/share of `github_embeddings` is visible in `doctor` output.
- Tests cover both the true-positive and the sawtooth false-positive.


---

▶ TAKE YOUR TURN (agy — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): src/rebalance/ingest/db/github.py,src/rebalance/ingest/db/semantic.py,src/rebalance/doctor.py,tests/test_github_vector_invariants.py
2. Append a build block to this relay file: `### Round N · Builder · agy` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick claim MARATHON-VB2-TURN --agent agy --paths "phases/gh250-vector-bloat-resume--vb2/RELAY.md,src/rebalance/ingest/db/github.py,src/rebalance/ingest/db/semantic.py,src/rebalance/doctor.py,tests/test_github_vector_invariants.py"
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick ping MARATHON-VB2-TURN --agent agy
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-VB2-TURN --agent agy --to codex
4. Edit ONLY these paths: phases/gh250-vector-bloat-resume--vb2/RELAY.md and src/rebalance/ingest/db/github.py,src/rebalance/ingest/db/semantic.py,src/rebalance/doctor.py,tests/test_github_vector_invariants.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.

---

▶ TAKE YOUR TURN (codex — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: src/rebalance/ingest/db/github.py,src/rebalance/ingest/db/semantic.py,src/rebalance/doctor.py,tests/test_github_vector_invariants.py.
1. Append a review block: `### Round N · Reviewer · codex` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-VB2-TURN --agent codex --to agy
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick done MARATHON-VB2-TURN --agent codex
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/gh250-vector-bloat-resume--vb2/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.

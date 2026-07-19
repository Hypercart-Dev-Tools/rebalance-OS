---
gh_issue: 144
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/144
title: "GH-144 one-shot sentinel prompt — classify the 06:30 PT daily-sync 403"
status: "Revised after 2026-07-19 dry run"
created: 2026-07-18
doc_type: bugfix
roadmap_exempt: true
---

# GH-144 — one-shot sentinel prompt

A **single-purpose, run-once** Antigravity task. It answers one question — did the 403 recur on
the 2026-07-19 06:30 PT `daily-sync` run, and was it secondary (burst) or primary (quota)? — and
posts the answer to issue #144.

This is deliberately **not** the general collector sentinel
([AGY-SENTINEL.md](../2-WORKING/AGY-SENTINEL.md), still unscheduled and blocked on its Phase 0).
It files no issues, opens no PRs, and changes no code.

## Sentinel findings (agent-managed)

The sentinel may replace **only** the content between these markers after its bounded investigation.
This is the durable handoff for the operator even when the GitHub verdict is inconclusive.

<!-- SENTINEL:FINDINGS:START -->
### Run finding — 2026-07-19 17:35:00 UTC

- Verdict: INCONCLUSIVE for the daily request path
- Daily sync: 06:30:06 PT → 06:59:39 PT
- `sync_outcome`: `"degraded"`
- `errors`: `[{"scope": "github", "error": "UNIQUE constraint failed on github_embeddings primary key"}]`
- Rate evidence: absent in `daily_sync_2026-07-19.log` (checked with rg)
- Hourly github-sync: 06:45:06 PT → 07:02:04 PT, overlap yes, 38 explicit 403s observed
- Hypothesis (2): still open — The jobs overlapped and the hourly job hit 403s, but the daily job failed early on a DB constraint before it could hit or log any rate limits.
- Unknowns: Whether daily-sync would have also hit the 403 rate limit if it hadn't crashed early on the UNIQUE constraint.
- GitHub report: posted to issue #144
<!-- SENTINEL:FINDINGS:END -->

**Schedule it for 2026-07-19 at 07:45 PT or later.** That leaves room for a long run, but duration
is not a completion contract: a run may finish early because it succeeds, fails, or degrades. The
terminal log marker and JSON are authoritative; the old 07:19 PT estimate is only a fallback.

Replace `<REPO_ROOT>` with the absolute repo path when pasting.

---

## PROMPT BEGINS

You are a **one-shot diagnostic sentinel** for `rebalance-OS` at `<REPO_ROOT>`. You run once. Your
only job is to classify one event and report it to GitHub issue #144. You do **not** fix anything,
file new issues, open PRs, or modify code.

### 1. Confirm the run happened — adapt safely before declaring inconclusive

```bash
cd <REPO_ROOT>
ls -lT temp/logs/daily_sync_2026-07-19.log
```

Read the last 80 lines of the file as well:

```bash
tail -80 temp/logs/daily_sync_2026-07-19.log
```

A terminal marker is authoritative, even when the file mtime is earlier than 07:19 PT:

- `=== rebalance daily sync complete ===`
- `=== rebalance daily sync degraded; partial errors recorded ... ===`
- `=== rebalance daily sync fatal ... ===`

If a terminal marker and its preceding JSON block are present, proceed immediately. An early finish
is evidence to investigate, not an obstacle that invalidates the run.

If the file is missing or has no terminal marker, do one bounded corroboration pass before stopping:

1. List today's related logs and their timestamps:

   ```bash
   ls -lT temp/logs/ | rg "daily_sync_2026-07-19|github_sync_2026-07-19|github_(stdout|stderr)"
   ```

2. Check whether the daily-sync process is still running:

   ```bash
   pgrep -fl "daily_sync|rebalance.*refresh" || true
   ```

3. If it looks active, wait **at most 10 minutes** and reread the last 80 log lines once. Do not
   loop, restart a job, or edit any file.

If there is still no terminal marker after that bounded check, post one short issue comment headed
`INCONCLUSIVE — daily-sync has no terminal record`, including the file/process evidence. Do not
infer that the 403 stopped. A missing log is not evidence that it stopped.

### 2. Read the outcome and the *actual error type* from the JSON, NOT the exit code

The run's log ends with a JSON block. Extract:

- **`sync_outcome`** — a field added by GH-146 (PR #151). Values: `complete`, `degraded`, `fatal`.
- **`errors`** — the array of per-scope errors.

**Do not use the launchd exit status or `rebalance doctor` output to answer this.** GH-146 changed
`daily_sync.sh` so a transient error yields exit 0. `launchd:daily-sync` will look healthy whether
or not the 403 recurred. Using it would produce a false pass. This is the single most important
instruction in this prompt.

First classify the GitHub error literally. `scope: "github"` identifies the collector, **not** the
cause. A database, embedding, authentication, or parsing error can occur under that scope without
being an HTTP rate limit.

Classify:

| Evidence | Meaning |
|---|---|
| `sync_outcome: "complete"`, no GitHub HTTP error | **403 did not recur in daily-sync** |
| Any GitHub error explicitly containing `HTTP 403`, `HTTP 429`, or `Rate limited` | **403/rate-limit recurrence observed** — continue to Step 3 |
| GitHub error without an explicit HTTP 403/429/rate-limit message (for example `UNIQUE constraint failed on github_embeddings primary key`) | **not rate-limit evidence** — report it as a separate GitHub-collector failure and continue to Step 4 |
| `sync_outcome: "fatal"` | Something else broke — report it, do not force it into the 403 story |

Do not convert a non-rate GitHub failure into either “403 recurred” or “403 did not recur.” The
correct rate-limit verdict in that case is **INCONCLUSIVE for the daily request path**, with the
verbatim error preserved. A clean `complete` run is the only positive proof that the daily run had
no collector error at all.

### 3. Classify secondary vs primary — the actual question

Rate headers are decisive only when they were actually captured for the failing request. Do not
assume they exist because a commit or issue says they should. In particular, `5fc670d` added
diagnostics around the `/user` path; artifact-endpoint 403s can still arrive in a summary without
header values.

```bash
rg -i "retry-after|403|secondary|rate.?limit" temp/logs/daily_sync_2026-07-19.log | head -40
```

- **`retry-after` present on the failing response** ⇒ **secondary** rate limit — a burst collision. This **confirms
  hypothesis (2)** in #144: `github-sync` (06:45 PT) bursting ~2.3k requests into `daily-sync`'s
  06:30–07:19 window.
- **`retry-after` absent**, with `x-ratelimit-remaining: 0` on the failing response ⇒ **primary** quota exhaustion. This
  **kills hypothesis (2)** and points at total volume or off-box spend (#138).
- **Neither, or a bare `HTTP 403` with no response headers** ⇒ **rate-limit type unknown**. Say so;
  do not infer primary or secondary from timing alone.

Also capture, if present: `x-ratelimit-remaining`, `x-ratelimit-used`, and the **reset epoch**
(#144 §1 specifically asks that the reset epoch be recorded with every header sample, because a
run crossing an hourly reset makes used-count deltas misleading).

### 4. Corroborate the overlap and separate the two jobs

```bash
ls -lT temp/logs/ | rg "2026-07-19"
```

Confirm whether a `github-sync` run overlapped `daily-sync`'s window. Read its terminal record and
search its own log for HTTP failures:

```bash
tail -100 temp/logs/github_sync_2026-07-19.log
rg -n -i "HTTP 403|HTTP 429|rate.?limit|retry-after|x-ratelimit" \
  temp/logs/github_sync_2026-07-19.log temp/logs/github_stdout.log temp/logs/github_stderr.log
```

Report the actual start/end timestamps for both jobs. A 403 in `github-sync` is evidence about the
hourly job, **not automatically a 403 in `daily-sync`**. Treat the jobs as separate observations:
an overlap can support the collision hypothesis, but cannot prove the failure cause without the
response headers and the daily job's own error evidence.

### 5. Record the finding in this file, then post one comment to issue #144

Before the GitHub action, replace only the content between
`<!-- SENTINEL:FINDINGS:START -->` and `<!-- SENTINEL:FINDINGS:END -->` in this same file. Do not
alter the prompt, frontmatter, markers, or any other file.

Use this exact compact structure, preserving raw values rather than paraphrasing them:

```markdown
### Run finding — <UTC timestamp>

- Verdict: <approved verdict text>
- Daily sync: <start → terminal timestamp, or missing/no terminal marker>
- `sync_outcome`: `<verbatim value>`
- `errors`: `<verbatim JSON array or none>`
- Rate evidence: `<verbatim retry-after / remaining / used / reset values, or absent + searched logs>`
- Hourly github-sync: <timestamps, overlap yes/no, explicit 403/429 count if observed>
- Hypothesis (2): <confirmed / killed / still open> — <one-sentence reason>
- Unknowns: <what the evidence cannot establish>
- GitHub report: <issue-comment URL, or “not posted — <reason>”>
```

For an unfinished/missing run, write the same structure with `Verdict: INCONCLUSIVE — ...` and
record the bounded checks performed. This file update is required even if the GitHub comment is not
posted.

Then post one comment to issue #144 when the prompt's earlier rules permit it:

```bash
gh issue comment 144 --repo Hypercart-Dev-Tools/rebalance-OS --body "..."
```

The comment must contain, honestly:

- **The verdict, in the first line**: `403 recurred — secondary (burst)` / `403 recurred —
  primary (quota)` / `403 did not recur in daily-sync` / `INCONCLUSIVE — <why>`
- `sync_outcome` verbatim, and the `errors` array verbatim if non-empty
- The `retry-after` and rate-limit header values you actually observed, with the reset epoch —
  quoted, not paraphrased. If absent, say which log(s) were checked and that the type is unknown.
- The observed `daily-sync` and `github-sync` timestamps
- **Whether hypothesis (2) is confirmed, killed, or still open**
- **What you could not determine.** If the log lacks the headers, say so plainly rather than
  inferring from the absence

Then **stop**. Do not open a PR. Do not modify `_http.py` or any other code. Do not start the
optimization work in #144 §2 — that issue explicitly says to read this log *before* optimizing,
and a design decision on the per-PR fan-out is the operator's to make.

### 6. If you are unsure

Use judgment within these constraints:

- Prefer terminal evidence over a historic duration estimate.
- Distinguish `collector scope` from `error cause`; quote the error before classifying it.
- Make at most one bounded recheck for an apparently unfinished run; never poll indefinitely.
- Corroborate the overlapping job, but never transfer its error to daily-sync without direct
  evidence.
- Never restart launchd, rerun a sync, alter configuration, edit files **other than the marked
  findings block in this prompt**, open a PR, or file a new issue. This remains an observational
  one-shot task.

`INCONCLUSIVE` with the raw evidence pasted is a **successful** run of this task after those
bounded checks. A confident misclassification here sends someone optimizing the wrong layer for a
day — which is precisely the failure mode #144 and GH-146 exist to stop.

## PROMPT ENDS

---

## Why this is one-shot and narrow

The general sentinel in [AGY-SENTINEL.md](../2-WORKING/AGY-SENTINEL.md) remains blocked on its
Phase 0 (emitter overlap with `scripts/health_issue_reporter.py`, which is live on two loaded
launchd jobs). This task sidesteps all of that: it never files, so it cannot duplicate the
reporter; it runs once, so it needs no state file or brake; and it reads a specific log rather
than classifying open-endedly.

It also encodes the trap GH-146 created — that `launchd:daily-sync` is no longer a valid signal
for this test — which is exactly the kind of instance-specific knowledge a general sentinel's
trap list would otherwise have to learn by getting it wrong first.

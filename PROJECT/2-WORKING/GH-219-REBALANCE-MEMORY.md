---
title: "REBALANCE MEMORY — unified project (8 lanes: instrument → measure → fix → bound → backstop → inventory → cover → detect)"
status: "Planned, not fired. Widened 2026-07-27 from a 5-lane MLX marathon into the single owner of Rebalance memory use, after Codex r1 review (2 Blockers + 3 Shoulds, all accepted). No code written."
created: 2026-07-27
updated: 2026-07-27
owner: noel@neochro.me
branch: marathon/2026-07-27-mlx-memory
issue: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/219
roadmap_exempt: true
goal: >
  End the recurring whole-machine memory starvation on the Mac Studio (three events: 07-25,
  07-26, 07-27) by fixing the allocation that causes it, bounding the damage when that fix is
  wrong, and repairing the two instruments that failed to see it.

  Root cause, identified 2026-07-27: the embedding backend is MLX, not torch. MLX allocates
  Metal buffers charged to `phys_footprint` as `iokit` and never counted in RSS, caches freed
  buffers with an effectively unbounded default limit, and the repo performs no MLX cache
  management anywhere. A single `rebalance-embed` process reaches ~46.9 GB footprint while
  reporting ~0.08 GB RSS.

  This file exists because the five issues are NOT independent: #216 produces the measurement
  that validates #215, #217 must be sized from #216's numbers, #213's ceiling only means the
  right thing once footprint semantics are settled, and #218 repairs the health instrument the
  marathon itself uses as a gate. Firing them in issue-number order would be actively wrong.
---

# REBALANCE MEMORY — unified project (2026-07-27)

**This file is the single owner of Rebalance's memory use.** Anything about how much memory
Rebalance consumes on this device belongs here, or is explicitly named out of scope below. It was
widened from a 5-lane MLX marathon on operator instruction:

> "I want the plan to be wider so the issues with Rebalance's memory use are lumped under a single
> unified project… the goal is to not have this turn into 'one more thing' we have to look at
> after the project is supposed to be completed."

Lanes 0–4 fix the known blowup. **Lanes 5–7 exist so that nothing is left un-owned** — every
Rebalance process gets a budget (5), every memory-consuming path gets a known guard status (6),
and the next recurrence is caught by the system rather than by the operator (7).

Breadth is bought with *measurement*, which is cheap and exhaustive. Depth stays bounded because
*remediation* is conditional on a numeric budget breach. See
[Scope discipline](#scope-discipline--breadth-of-coverage-bounded-depth).

## Why lanes 0–4, and why in this order

The sequence is **instrument → measure → fix → bound → backstop**. Each lane exists to make the
next one verifiable rather than argued.

The ordering constraint is real, not stylistic:

- **#215 is currently INFERRED, not PROVEN.** `mx.get_cache_memory()` has never been sampled
  during a live run — no Metal device is reachable from a sandboxed shell. Landing the fix before
  the measurement means shipping a remedy that cannot be confirmed, for a bug that has already
  survived two misdiagnoses.
- **#217's limit must be sized from data.** A guessed ceiling that fails legitimate passes is how
  safety mechanisms get switched off by the person they annoy.
- **#213's ceiling changes meaning** once it reads footprint instead of RSS — footprint
  legitimately includes Metal, so the existing 35%-of-RAM value is not transferable unexamined.
- **#218 comes first because the marathon leans on `doctor` as a gate**, and doctor currently
  lies about scheduler state in restricted shells. It already cost this investigation a false
  lead. Fix the instrument before using it to certify the work.

## Regression archaeology — what changed in the last 7 days

The first version of this plan did **no** regression analysis. That was a gap: three events
starting 07-25 on a machine that had been fine invites the question "what changed?", and the plan
went straight to mechanism without asking it. Bounded first pass, run 2026-07-27:

**Checked and clear — stated at the width of the evidence, not wider (r1 [Should]):**

- **No direct embedding-path edit found.** Zero commits in the last 7 days touch `embedder.py`,
  `semantic_index.py`, `ingest/_job_guard.py`, `utils/job_guard.py`, or `doctor.py`. 44 commits
  landed in the window; exactly one touched `src/rebalance/ingest/` or `scripts/` at all
  (`0d4b6f0`, 07-23, Anthropic→Gemini key removal).
  **This is NOT "no code regression."** That earlier phrasing over-claimed. The check covers five
  files; it does **not** exclude changes to invocation entry points, launchd environment or
  configuration, or runtime/OS state — all of which can change embedding behaviour without
  touching the embedding path.
- **No embedding-library version change.** MLX 0.31.2 and `mlx_embeddings` 0.1.0 were installed
  **2026-04-24**; MLX has been in the tree since March. This does **not** exclude an OS update, a
  Metal/driver change, or a transitive dependency moving underneath them.

These narrow the search; they do not close it. The two surfaces the earlier draft silently treated
as covered — **invocation entry points** and **launchd env/config** — are now first-class
candidates below.

**Live candidates (INFERRED, not yet tested):**

- **The 3-Eyes fleet rollout, 2026-07-22** — ~12 commits landing `skill-sync`, `selfcheck`,
  `collector-health` and a machine-local registry overlay. The single largest change in the
  window, and 3 days before the first event. `3eyes.skill-sync` now runs **every 120 s** (216
  executions on 07-27 alone). Its own memory is trivial (peak RSS 0.010 GB), so it is not the hog
  — but whether it *triggers* embedding work, or contends with it, is untested.
- **Both scheduler plists were rewritten 2026-07-20 08:16:11** (`vault-sync`, `daily-sync`). The
  fleet was reinstalled 7 days ago. Whether cadence changed at that point is not yet established
  — the current cadence (`vault-sync` hourly at :15, 06:00–23:00) needs comparing against the
  pre-07-20 plists.
- **Corpus growth.** Not yet measured. Both tracked databases (`rebalance.db`,
  `temp/rebalance.ask.db`) are stale from June, so the live embedding index is elsewhere on this
  device and was not located in this pass. Finding it is a prerequisite for testing this
  hypothesis at all.
- **Invocation entry points** (added r1). Embedding passes are reachable from launchd, CLI, MCP
  tool, agent, and interactive shell (`_job_guard.py:12-17`). A change to *who calls* the
  embedding path is invisible to a diff of the embedding path itself — and is a live suspect
  precisely because two of three episodes have no guard record.
- **launchd environment / configuration** (added r1). Not just cadence: `EnvironmentVariables`,
  working directory, and which interpreter the plists resolve. A config change alters runtime
  behaviour with zero code diff.
- **OS / Metal runtime state** (added r1). A macOS update or Metal driver change alters MLX
  allocation behaviour without any package version moving.

**This archaeology is deliberately bounded.** It runs as Lane 0.5 below with a hard timebox. If
the cause is not found inside that box, the marathon proceeds anyway — because #215's fix bounds
the allocation regardless of what started it. Knowing the trigger is valuable; it is not a
prerequisite for stopping the bleeding.

## Lane sequencing

| Order | Issue | Lane | Write-set | Depends on |
|---|---|---|---|---|
| 0 | [#218](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/218) | C (parallel) | `src/rebalance/doctor.py` | — |
| 0.5 | archaeology (no issue) | D (parallel, **timeboxed**) | read-only | — |
| 1 | [#216](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/216) | A | `embedder.py`, `semantic_index.py`, `temp/memory-issues/sys-mem-watch.sh` | — |
| 2 | [#215](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/215) | A | `embedder.py`, `semantic_index.py` | #216 |
| 3 | [#217](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/217) | A | `embedder.py`, `ingest/_job_guard.py` | #216, #215 |
| 4 | [#213](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/213) | B | `utils/job_guard.py` | #215 |
| 5 | fleet inventory & budgets | E (parallel, read-mostly) | inventory table (new file) | — |
| 6 | guard coverage audit | B (after #213) | coverage matrix + guard placement | #213 |
| 7 | standing regression detection | C (after #218) | `src/rebalance/doctor.py` | #218, Lane 5 budgets |

**Collision analysis.** Lane A's three issues all write `embedder.py` and must run strictly
sequentially in one lane — they cannot be parallelised. Lane B (`utils/job_guard.py`) and Lane C
(`doctor.py`) are path-disjoint from Lane A and from each other, so C may run concurrently
throughout and B may start once #215 lands. Note `ingest/_job_guard.py` (the bridge, Lane A) and
`utils/job_guard.py` (the guard, Lane B) are **different files** — no collision, despite the
names.

---

## Lane 0 — #218 · doctor's launchctl false negative

**Goal:** stop doctor reporting a working scheduler fleet as entirely missing.

- [ ] Treat non-zero `returncode` as unavailable (`doctor.py:502-510`)
- [ ] Treat empty/whitespace-only stdout as unavailable, not "zero jobs loaded"
- [ ] Emit exactly one "scheduler state undetermined" finding; **zero** per-job warnings
- [ ] Regression test: available+loaded, available+genuinely missing, unavailable

**Gate:** on a healthy device, zero `scheduler:*` warnings; in a restricted shell, one honest
undetermined line and no reinstall advice.

→ [GH-218-DOCTOR-LAUNCHCTL-FALSE-NEGATIVE.md](../1-INBOX/GH-218-DOCTOR-LAUNCHCTL-FALSE-NEGATIVE.md)

---

## Lane 0.5 — regression archaeology (read-only, **hard timebox**)

**Goal:** find what changed around 07-25, or establish within a fixed budget that it cannot be
found cheaply. No issue; no code changes; read-only.

**Each candidate has a defined minimum evidence bar and a defined not-established outcome
(r1 [Should]).** "Not found" must never be recorded as "ruled out" — the two are different
results and the log must say which.

| # | Candidate | Minimum evidence to CONFIRM | Minimum evidence to EXCLUDE | If neither, record |
|---|---|---|---|---|
| 1 | Live index location + corpus growth | Index path found **and** row/chunk counts at two dates ≥7 days apart | Index found **and** growth <10% over 14 d | `UNOBSERVABLE — index not located in budget` |
| 2 | Scheduler cadence change 07-20 | Pre-/post-07-20 plist diff shows changed interval or calendar set | Diff shows cadence identical | `UNOBSERVABLE — no pre-07-20 plist copy available` |
| 3 | 3-Eyes rollout 07-22 | A 3-Eyes job demonstrably invokes or serialises against an embedding leaf | No 3-Eyes job touches an embedding entry point | `UNOBSERVABLE — trigger relationship not determinable from logs` |
| 4 | Invocation entry points | A non-launchd caller reaching an embedding leaf is identified | All callers enumerated and guarded | `UNOBSERVABLE — caller set not enumerable` |
| 5 | launchd env/config | An `EnvironmentVariables`/interpreter/cwd delta is found | Config byte-identical pre/post | `UNOBSERVABLE` |
| 6 | OS / Metal runtime | An OS or driver update lands in the window | No update in window | `UNOBSERVABLE` |

- [ ] Work candidates in the order above (1 and 4 have the highest expected value)
- [ ] Record a verdict per row in `TRIAGE-LOG.md` — **CONFIRMED / EXCLUDED / UNOBSERVABLE**, never
      a bare "not found"

**Timebox: 90 minutes, non-extendable — and it is a cap on TRIAGE, not a promise to answer all
six.** Six candidates cannot be settled in 90 minutes and the plan does not pretend otherwise
(r1 [Should]). Whatever is still `UNOBSERVABLE` at expiry is written down as such and **stops**.
Anything genuinely worth more time becomes its **own** scoped issue — never an extension of this
lane.

**Explicitly not a blocker.** Lanes 1–4 proceed regardless. #215 bounds the allocation whatever
started it; archaeology only tells us whether something *else* also needs changing. If this lane
finds nothing, the marathon still delivers its acceptance criteria.

→ findings land in `temp/memory-issues/TRIAGE-LOG.md` (device-local)

---

## Lane 1 — #216 · MLX instrumentation (measure before remedy)

**Goal:** make the dominant memory consumer observable, and settle #215's hypothesis with data.

- [ ] Log `mx.get_active_memory()` / `get_cache_memory()` / `get_peak_memory()` every N batches
- [ ] `mx.reset_peak_memory()` per pass so figures are attributable to a run
- [ ] Reuse an existing log surface; do not invent a new one
- [ ] Add `inactive_gb` + `speculative_gb` to `sys-mem-watch.sh`
- [ ] **Emit an invocation-wide run ID and a PID → entry-point record** on every embedding pass
      (r1 [Blocker]) — which caller (launchd job / CLI / MCP tool / agent / shell), which leaf,
      which PID. Without this the two unattributed episodes stay unattributable **by construction**,
      and no amount of per-batch MLX telemetry fixes that.
- [ ] **Confirm or refute #215 in writing** in `temp/memory-issues/TRIAGE-LOG.md`

### Lane 1 decision table — what each outcome triggers (r1 [Blocker])

"Refutation redirects Lane 2" was not a bounded plan. It is now:

| Lane 1 observation | Action |
|---|---|
| `get_cache_memory()` climbs monotonically toward the process peak | #215 **CONFIRMED** → run Lane 2 as written |
| Cache flat, `get_active_memory()` rises to the peak | #215 **REFUTED** → **halt Lane 2 as written.** Record the refutation in `TRIAGE-LOG.md`, close #215 with the evidence, and open a **separately scoped** diagnosis issue. Do **not** improvise a replacement fix inside this marathon. |
| Both flat, peak still ~46.9 GB | The allocation is **not MLX-visible** → halt Lanes 2–3, escalate as above; Lane 4 (#213) may still proceed independently |
| Telemetry cannot be obtained at all | Record `UNOBSERVABLE`; marathon halts pending a decision — do not proceed on the unproven hypothesis |

**Gate:** a full pass emits MLX figures plus run-ID/entry-point attribution at negligible
overhead, and the root cause is settled **CONFIRMED / REFUTED / UNOBSERVABLE** — a refutation is a
success outcome for this lane, and it stops the marathon rather than silently mutating it.

→ [GH-216-MLX-MEMORY-INSTRUMENTATION.md](../1-INBOX/GH-216-MLX-MEMORY-INSTRUMENTATION.md)

---

## Lane 2 — #215 · cap and clear the MLX buffer cache (the fix)

**Goal:** stop the allocation. Blocked on Lane 1's verdict.

- [ ] `mx.set_cache_limit(...)` once at embedding-module level, sized deliberately
- [ ] `mx.clear_cache()` at the end of each batch iteration (`embedder.py:172-186`)
- [ ] Apply to **both** leaves (`embedder.py:105`, `semantic_index.py:613`) — they share one lock
      and one model per `_job_guard.py` "Lock scoping"
- [ ] Measure throughput before/after; record any regression rather than hiding it

**Gate:** a full pass holds peak `phys_footprint` under an explicit documented bound; `free_gb`
never approaches zero; compressor stays single-digit GB.

→ [GH-215-MLX-EMBED-CACHE-LEAK.md](../1-INBOX/GH-215-MLX-EMBED-CACHE-LEAK.md)

---

## Lane 3 — #217 · hard MLX memory limit (bound the damage)

**Goal:** a runaway pass fails the job, not the machine. Sized from Lane 1's numbers.

- [ ] `mx.set_memory_limit(<bytes>)` at embedding-module import
- [ ] Size as a **fraction of physical RAM**, matching `job_guard.py`'s
      `DEFAULT_MAX_RSS_FRACTION = 0.35` convention — do not hardcode 64 GB
- [ ] Environment-overridable, consistent with `REBALANCE_JOB_GUARD_MAX_RSS_GB`
- [ ] Failure surfaces as a clean error naming the limit, the pass, and the batch
- [ ] **Verify the `rebalance-embed` flock is released on the failure path** and a subsequent run
      starts normally (`README.md:254` documents an existing "already running" mode — do not
      trade a memory blowup for a permanently stuck lock)

**Gate:** an over-limit pass fails cleanly and attributably; `free_gb` never approaches zero
during that failure; the next run starts.

→ [GH-217-MLX-HARD-MEMORY-LIMIT.md](../1-INBOX/GH-217-MLX-HARD-MEMORY-LIMIT.md)

---

## Lane 4 — #213 · guard backstop, RSS → footprint

**Goal:** repair the external net. Demoted from "the fix" to "the backstop" by #215.

- [ ] Switch the ceiling metric from tree RSS to `phys_footprint`
- [ ] **Re-size the ceiling** knowing footprint legitimately includes Metal — the current
      35%-of-RAM value is not transferable unexamined
- [ ] Settle whether the available-memory floor is sound, using Lane 1's new
      `inactive_gb`/`speculative_gb` columns

**Gate:** a synthetic over-ceiling job trips and is killed; guarded jobs on a healthy machine do
not trip.

**Carried finding — not a blocker:** the guard's window is far shorter than the leak's.
`guarded_embedding` decorates embedding *leaf* functions, so each call builds a fresh
`MemoryCeiling` with `peak_rss = 0` (PID 1391 wrote three records — 10.7 s / 1.5 s / 35.6 s —
across a 35-minute lifetime). This does **not** block the footprint switch, because footprint is
absolute per-process and a later leaf call reads the accumulated total. It does mean
`job_rss.jsonl` can never show cumulative growth, which is Lane 1's job instead.

→ [GH-213-MEMORY-PRESSURE-DEFENCE.md](../1-INBOX/GH-213-MEMORY-PRESSURE-DEFENCE.md)

---

## Lane 5 — fleet memory inventory & declared budgets

**Goal:** every Rebalance-owned process has a measured baseline and a written budget, so no
process can later surface as "one more thing" that was never looked at.

**Why this is in the project:** the investigation only ever profiled the embedding path. The same
07-27 sample also showed `node` (LM Studio) at 13.1 GB, `mysqld` at 1.5 GB, and the MCP server
holding 1.4 GB — none of which anyone has ever assigned a budget. Without this lane, the first
question after shipping is "what about pulse-server?", and the project reopens.

- [ ] Enumerate every Rebalance-owned process: launchd jobs (14), `pulse-server`, MCP server,
      3-Eyes jobs, ad-hoc CLI/agent entry points
- [ ] Baseline each from `sysmem-proc-*.csv`: typical and peak `phys_footprint` over ≥ 3 days
- [ ] Assign each a **declared budget** and record it in one table in the repo
- [ ] Flag any process already over its budget; **remediate only those** (breadth is measurement,
      depth is conditional)
- [ ] Record non-Rebalance processes (LM Studio, mysqld) in the inventory as **measured, not
      owned** — visible, explicitly out of remediation scope

**Gate:** a committed table covering 100% of Rebalance-owned processes, each with a baseline and a
budget. Over-budget processes are either fixed or have a written waiver with a reason.

**Bounded by:** measurement is exhaustive; remediation touches only budget violators. A process
that is within budget gets a row in the table and nothing else.

---

## Lane 6 — guard coverage audit

**Goal:** know which memory-consuming paths are actually guarded, and close the gaps — so the
"2 of 3 episodes had no guard record" finding is fixed as a *class*, not as two anecdotes.

**Why this is in the project:** GH-172 deliberately placed the guard at library leaves because
runs are agent-spawned as well as launchd-spawned (`_job_guard.py:12-17`). Nobody has since
verified that every leaf is actually covered — and 07-27 produced two 46.9 GB processes with no
`job_rss.jsonl` record at all, despite `record_peak_rss` being documented as writing on every exit
path (`job_guard.py:614-616`). That is either a coverage gap or a recording failure, and both are
systemic.

- [ ] Enumerate every code path that can load a model or embed — not just the two known leaves
- [ ] For each: guarded / unguarded / guarded-but-not-recording
- [ ] Determine whether `record_peak_rss` can be skipped (e.g. `SIGKILL` bypassing `finally`) and
      whether that explains the two missing records
- [ ] Close gaps, or waive in writing with a reason
- [ ] Verify the guard's flock scoping does not itself prevent recording

**Gate:** a written coverage matrix; zero unguarded paths capable of exceeding the 8 GB
per-process bound, or an explicit waiver for each.

**Bounded by:** enumeration and guard placement only. Redesigning the guard's architecture is
**not** in this lane — that is #213's territory.

---

## Lane 7 — standing memory regression detection

**Goal:** the *system* notices the next recurrence, not the operator glancing at Activity Monitor.

**Why this is in the project:** three events were each found after the fact, and the third was
found because the operator screenshotted Activity Monitor. That is not a detection mechanism.
Without this lane the project ships a fix with no way to know it held.

**Deliberately minimal — #213's argument still stands.** That issue argued against building a
sampler → thresholds → classifier → routed-alert pipeline, and it was right. This lane adds a
**threshold check to an existing surface**, not a monitoring subsystem:

- [ ] `doctor` check: read the sampler's most recent day and fail if any bound in the numeric
      table was breached
- [ ] Report the offending process, peak, and timestamp — attributable, not "memory was high"
- [ ] One check, one existing surface, no new daemon, no classifier, no alert routing
- [ ] Verify it would have fired on the 07-25, 07-26 and 07-27 data (replay the existing CSVs)

**Gate:** replaying 07-25/26/27 sampler data trips the check every time; a clean day does not.

**Bounded by:** one `doctor` check against already-collected data. No new collector, no new
scheduled job, no notification infrastructure. If routed alerting is later wanted, that is a
separate issue with its own justification.

---

## Scope discipline — breadth of coverage, bounded depth

Two operator requirements pull in opposite directions, and both are honoured deliberately:

> "I want the plan to be **wider** so the issues with Rebalance's memory use are lumped under a
> single unified project."
>
> "I want to deal with **70–80%** of the problem in this effort and not have this become an
> endless forever project."

The resolution is **wide coverage, shallow depth, hard numeric gates**. Lanes 5–7 exist so that no
Rebalance memory surface is left un-owned and able to return as "one more thing" after this is
declared done. They do **not** license unbounded work: each carries the same numeric budget and
the same stopping rule as the rest.

**Every Rebalance-owned process is in scope for measurement. Only budget violators are in scope
for remediation.** That is the line that keeps breadth from becoming endlessness — inventory is
cheap and total; fixing is expensive and conditional.

### The numeric bounds (r1 [Blocker] — no more vague language)

"Under a documented bound", "never approaches zero" and "single-digit GB" were unmeasurable. On
this 64 GB machine the contract is:

| Metric | Bound | Source |
|---|---|---|
| Peak `phys_footprint`, any single Rebalance process | **≤ 8 GB** | `sysmem-proc-*.csv` |
| Peak **aggregate** Rebalance-attributable footprint (concurrent) | **≤ 16 GB** | `sysmem-proc-*.csv`, summed per sample |
| `free_gb`, every sample | **≥ 4.0 GB** | `sysmem-sys-*.csv` |
| `compressor_gb`, every sample | **≤ 8.0 GB** | `sysmem-sys-*.csv` |
| `swap_used_gb`, every sample | **≤ 12.0 GB** | `sysmem-sys-*.csv` |
| Representative window | **1 full waking day, ≥ 12 embedding passes** | `vault-sync` fires 18× (06:00–23:00) |

Aggregate is measured, not assumed: a fleet of six 3 GB processes violates the machine floor while
every process passes its own bound. That gap is exactly what a per-process-only criterion misses.

**Out of scope — named, so they cannot creep in:**

- The `figma: last refresh advanced 46d` warning (unrelated, pre-existing)
- The `deep work` / `commit coverage` doctor warnings (pre-existing, separate signals)
- Rewriting the scheduler policy table or `SCHEDULER.md`
- Any embedding-pipeline redesign, model change, or throughput optimisation
- The `temp/` gitignore question — device-local logs are fine for now, deliberately deferred
- Making the sampler cross-device
- Non-Rebalance processes (LM Studio's `node` was measured at 13.1 GB on 07-27 — **recorded in the
  inventory, explicitly not remediated here**)

**Stopping rule.** The project is done when every acceptance box below is ticked, even if:

- Lane 0.5 leaves candidates `UNOBSERVABLE`
- The 2 of 3 unattributed 07-27 episodes are *bounded* rather than *identified* (see acceptance)
- Adjacent doctor warnings are still present
- Non-Rebalance processes remain large

**Reopen conditions (r1 [Should] — widened and made numeric).** Scope reopens only when a
*measured* budget breach persists after the lanes land:

1. Any Rebalance process exceeds **8 GB** peak footprint, or the aggregate exceeds **16 GB**
2. Any machine-level bound in the table above is breached during the representative window
3. An embedding entry point is found that no lane instruments or guards

Anything else — an untidy warning, an unidentified 07-25 trigger, a large non-Rebalance process —
does **not** reopen this project. It becomes a new issue with its own scope.

## Project-level acceptance

**Bounds met**
- [ ] Representative window (1 full waking day, ≥ 12 embedding passes) with **zero** breaches of
      any bound in the numeric table
- [ ] Aggregate concurrent Rebalance footprint measured, not inferred, and ≤ 16 GB

**Root cause settled**
- [ ] #215 recorded as **CONFIRMED / REFUTED / UNOBSERVABLE** in `TRIAGE-LOG.md` — never left
      INFERRED
- [ ] Embedding throughput regression, if any, measured and written down

**Attribution closed (r1 [Blocker])**
- [ ] Every embedding pass emits a run ID + entry-point + PID record
- [ ] The 07-27 unattributed episodes are either **identified**, or **bounded** — i.e. the
      instrumentation demonstrably now covers every path capable of reaching that footprint, so a
      recurrence could not go unattributed. Bounding is an acceptable close; silence is not.

**Fleet owned**
- [ ] Every Rebalance-owned process has a measured baseline and a declared budget (Lane 5)
- [ ] Every memory-consuming path's guard status is known and gaps are closed or waived in
      writing (Lane 6)
- [ ] A recurrence is detected by the system rather than by the operator noticing Activity
      Monitor (Lane 7)

**Instruments honest**
- [ ] `rebalance doctor` reports scheduler state correctly in both restricted and normal shells

## Open questions carried into the marathon

- **Only 1 of 3 episodes on 07-27 is confirmed as `rebalance-embed`.** PID 1391 is attributed by
  the guard's own log. PIDs 16871 (01:04) and 2886 (08:21) match on binary, peak (~46.9 GB) and
  RSS profile but have **no `job_rss.jsonl` record at all** — despite `record_peak_rss` being
  documented (`job_guard.py:614-616`) as writing on every exit path. Either they ran unguarded, or
  the guard died without recording. Lane 1 should resolve this; if those episodes are a *second*
  path to the same allocation, Lane 2's fix is incomplete.
- **The episode interval is collapsing** — 01:04, 07:09, 08:21 on 07-27 (gaps ~6 h then ~1 h 12 m)
  against roughly one per day previously. Cause unknown; may simply track vault-sync's hourly
  cadence plus agent/MCP-triggered runs.
- **Embedding passes have many entry points** — launchd, CLI, MCP tool, agent, interactive shell
  (`_job_guard.py:12-17`, the GH-172 finding that put the guard at library leaves). Any fix that
  assumes launchd-only triggering is wrong.

## Evidence

`temp/memory-issues/TRIAGE-LOG.md`, entry `2026-07-27` — full forensics with PROVEN / INFERRED /
UNRESOLVED tags. Note `temp/` is gitignored, so that log is device-local to the Mac Studio.

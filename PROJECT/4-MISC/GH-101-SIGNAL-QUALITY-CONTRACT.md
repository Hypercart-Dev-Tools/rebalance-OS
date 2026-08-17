---
title: "Signal-Quality Contract (observe-first source health)"
codename: HiQS
owner: Noel
gh_issue: 101
source: "https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/101"
status: "Active (2-WORKING) — Phase 0 spike run 2026-07-01; Phase 1 shipped 2026-07-03; Phase 2 implemented 2026-07-05 and pending review. Supersedes the two SKETCH-* drafts."
created: 2026-06-30
updated: 2026-07-05
branch: development
doc_type: project
goal: >
  Detect silent signal degradation — "false freshness", silent empty sets, and volume
  collapse — at the point of USE (index_status / doctor / ask), without adding a blocking
  ingest gate. Make a degraded source legible to any querying agent instead of letting the
  pipeline present dead signal as healthy.
non_goals: >
  Not an ingest gate. Does not stop refresh_index, reject messy upstream rows, or add a new
  enforcement pipeline. Not a relevance-ranking engine. Not a new table or new MCP tool in v1.
supersedes:
  - PROJECT/1-INBOX/SKETCH-REBALANCE-SIGNAL-CONTRACT-00.md
  - PROJECT/1-INBOX/SKETCH-REBALANCE-SIGNAL-CONTRACT-DRAFT-01.md
related:
  - PROJECT/1-INBOX/PDDA-INTEGRATION/ROADMAP-SIGNAL-SCAN.md
  - PROJECT/1-INBOX/GEMINI-WHATS-NEXT-VAULT.md
  - PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md
  - PROJECT/2-WORKING/WATCHLIST-COVERAGE-GUARD.md
effort: 2
complexity: 2
risk: 1
phases: 4
---

## Status

| What was just completed | What's next |
|---|---|
| **Promoted + Phase 0 spike run (2026-07-01).** Opened [issue #101](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/101), `git mv`d this doc to `2-WORKING/GH-101-SIGNAL-QUALITY-CONTRACT.md`, parked its pointer in `ROADMAP.md`. **Phase 0 verified against live code + live DB** (findings in §Phase 0 below): `get_index_status` at [index_ops.py:224](../../src/rebalance/ingest/index_ops.py#L224) **CONFIRMED**; `_safe_max` per-table freshness **CONFIRMED**; `_safe_count_where` primitive exists at [index_ops.py:174](../../src/rebalance/ingest/index_ops.py#L174), used for apple_reminders at [L273](../../src/rebalance/ingest/index_ops.py#L273) **CONFIRMED**; no `sync_state` table (0 hits repo-wide) **CONFIRMED**. **REFUTED:** `payload["freshness"]` is *not* an empty dict ready to hold labels — it is initialized empty at [L236](../../src/rebalance/ingest/index_ops.py#L236) but **overwritten with the semantic-drift dict at [L385](../../src/rebalance/ingest/index_ops.py#L385)**; Phase 2 must merge into it, not assume it is free. `vault` make-or-break confirmed (outside `_PEEKABLE_SOURCES`). | **Phase 1 shipped 2026-07-03** — `recent_row_count_7d` added to all 8 sources in `get_index_status`; new seeded test covers correct counts + the zero-volume case; `pytest tests/` 1278 passed / 10 skipped; `rebalance doctor` clean. **Run Phase 2 next.** |

---

## Table of contents

- [Phase 0 — Spike: validate the observe-first contract against the real schema](#phase-0--spike-validate-the-observe-first-contract-12h) _(scoped, not run)_
- [Phase 1 — `recent_row_count_7d` in `index_status`](#phase-1--recent_row_count_7d-in-index_status) _(blocked on Phase 0)_
- [Phase 2 — derived `status`/`reason` + one `doctor` warning path](#phase-2--derived-statusreason--one-doctor-warning-path) _(blocked on Phase 1)_
- [Phase 3 — optional: surface degradation at query time (`ask`)](#phase-3--optional-surface-degradation-at-query-time-ask) _(kill-gated on Phase 2)_

# Signal-Quality Contract

> **Thesis:** `rebalance` is an automated ingest pipeline, not a human workflow gate. The
> contract therefore lives at the point of **use** (`index_status`, `doctor`, `ask`), never at
> the point of **collection**. It **observes and downgrades trust**; it never blocks a sync or
> rejects an upstream row. What it detects is **signal degradation** — not schema violations,
> which the storage boundary already rejects.

---

## 1. Does the premise survive falsification?

**The case against building this:** adding quality ceremony to an automated pipeline risks
dropping real signal and breaking the sync loop in the name of "quality" — violating the very
"Fresh" pillar it claims to enforce. Structure is already enforced by the SQLite schemas; symmetry
with PDDA is not a reason to build.

**It survives — with one hard constraint: observe-first, never block-first.** The justification is
**silent failures of meaning**. The historical proof is the Focus 5 identity bug ([GH-81](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/81)):
the pipeline executed perfectly, the rows were structurally sound, the sync was marked fresh — yet
repos were silently dropped from the ranking and the system had **no way to detect it**. The pipeline
currently *asserts* quality; it does not *observe* it. That is the gap.

**Honest scope — v1 would not have caught GH-81 itself.** GH-81 was a *partial* silent drop: some
repos fell out of a ranking that still returned plenty of structurally-sound rows. v1's two metrics
catch *staleness* and *collapse-to-empty* (the auth-breaks-to-`[]` class), **not** partial relevance
loss. GH-81 is the motivator for the **principle** — the pipeline cannot self-detect meaning-loss —
not a defect v1 closes. The partial-relevance class is Phase 4+ (§7–§8). Shipping the tractable subset
first is the point; claiming "this catches GH-81" is exactly the oversell to avoid.

The contract must therefore:

- **not** stop `refresh_index()`, **not** reject messy upstream data, **not** add a blocking gate;
- **do** append health metadata that read-side tools can see, and **do** downgrade trust / surface
  warnings at query/use time.

---

## 2. What is actually true today (grounded, not asserted)

The two drafts assumed a `sync_state` table and described freshness as "asserted only." The live
code is **better than that**, which shrinks the work:

| Pillar | Real state today | Evidence (file:line) |
|---|---|---|
| **Structured** | Enforced at the storage boundary; malformed writes don't land. | source schemas / type affinities |
| **Fresh** | **Already derived per-table**, not from a missing `sync_state`. `get_index_status` computes a per-source last-timestamp via `_safe_max(conn, table, col)`. | [index_ops.py:244-302](../../src/rebalance/ingest/index_ops.py#L244-L302) |
| **Attested** | Asserted only — rows carry source IDs/URLs, but synthesis is not structurally required to cite them. | (out of scope for v1) |
| **Relevant** | Structurally weak — relevance is query-time; no signal when important rows were silently omitted. | (the GH-81 class) |

**Three findings that de-risk the build:**

1. **No `sync_state` table exists** (`grep` → 0 hits). Freshness is *already* per-source, so Phase 1
   does not need new freshness plumbing — only a second metric beside the existing counts.
2. **The 7-day-window primitive already exists**: `_safe_count_where(conn, table, predicate)` is used
   today for `apple_reminders` active-count ([index_ops.py:273](../../src/rebalance/ingest/index_ops.py#L273)).
   `recent_row_count_7d` is one call to it with a `timestamp > now-7d` predicate.
3. **`payload["freshness"]` is an initialized empty dict** ([index_ops.py:236](../../src/rebalance/ingest/index_ops.py#L236)) —
   the natural, DRY home for the derived `status`/`reason` labels, rather than a parallel structure.

There is also a ready-made **source → content-timestamp** map to reuse: `_PEEKABLE_SOURCES`
([index.py:193](../../src/rebalance/mcp/tools/index.py#L193)) already pins each source to the column
that means "when this row's data is about / arrived" (`calendar_events→start_time`,
`email_messages→received_at`, `github_activity→scanned_at`, …). Volume must be counted on the
**content** timestamp, not the **sync** timestamp — otherwise "synced 2 min ago, 0 useful rows"
looks healthy.

---

## 3. The sharpest gap: false freshness & silent degradation

The dangerous failure is not a loud crash — it is a source that looks healthy from the outside while
the useful signal has degraded or vanished. Three modes:

1. **Stopped / stuck** — collector stops updating; data is plainly stale. (Caught by the existing
   `last_*_at` timestamp.)
2. **Successful-but-empty / volume-collapse** — collector runs, returns `[]` or a sharply reduced set,
   exits clean, sync marked fresh. **(Not caught today.)**
3. **Structurally-valid-but-meaning-compromised** — rows still write, but the result no longer means
   what it did (GH-81's actual class).

**v1 scope: modes 1 and 2.** Mode 3 — the *partial* silent drop GH-81 actually was — is a relevance
problem v1 does **not** detect. Do not conflate them: catching "fresh but empty" is real and
shippable; catching "fresh, full, but subtly wrong" is Phase 4+.

Concrete, each already plausible on this system:

- A GitHub PAT loses `repo` scope but keeps `public_repo`; `github_scan` succeeds, private work
  silently drops out → "fresh", 100% — but dead.
- Gmail/Calendar auth breaks into a clean empty list; `ask` confidently answers "nothing happened
  this week."
- `sleuth_reminders` stops syncing; `ask` answers from stale reminder state with full confidence.

**One metric cannot catch all three. Two can:** the existing timestamp catches *stopped*; a recent
row count catches *empty / collapsed*.

---

## 4. Minimal contract surface

Reuse the read-side primitives — **no new pipeline, no new table, no new MCP tool in v1.**

**Per-source derived shape (added to the existing `index_status` source dicts):**

- `recent_row_count_7d` — counted on the source's content timestamp (`_PEEKABLE_SOURCES` column).
- `status` — derived label `ok` | `warn` | `degraded`.
- `reason` — short string, present only when not `ok`.

**Derivation logic (interpret, don't over-fire):**

- `warn`/`degraded` if a source has not advanced its timestamp within its expected window (stale).
- `warn`/`degraded` if it synced recently but `recent_row_count_7d` collapsed to zero (or far below
  its own norm).
- Leave *legitimately* zero-volume cases (a real quiet week) for the host agent to interpret — the
  contract surfaces the anomaly, it does not adjudicate it.

This stays read-only and derivable from existing tables. No source-specific config in v1 unless
Phase 0 proves a source needs a custom window (e.g. calendar's "look back 7d AND forward").

---

## 5. Phased delivery

### Phase 0 — Spike: validate the observe-first contract (1–2h)

**This is a discovery phase — its findings MUST be written back into this doc before its QA gate can
pass (PDDA discovery contract).**

Goal: confirm the schema supports a useful observe-first contract with **zero new tables**, and lock
the per-source window/column choices.

Checklist:

- [ ] Read `get_index_status` end-to-end ([index_ops.py:224](../../src/rebalance/ingest/index_ops.py#L224)):
      confirm the per-source dict shape and whether anything already populates `payload["freshness"]`.
- [ ] Confirm `_safe_count_where` ([index_ops.py:273](../../src/rebalance/ingest/index_ops.py#L273))
      can express `WHERE <ts_col> > <now-7d>` cheaply for each core source (index present? full scan?).
- [ ] Pin the content-timestamp column per source against `_PEEKABLE_SOURCES`
      ([index.py:193](../../src/rebalance/mcp/tools/index.py#L193)); note where `vault` differs (its
      rows live in `vault_files`/`chunks`, not the peekable set).
- [ ] Decide which sources need a custom window vs. the default rolling 7-day count.
- [ ] Produce one concrete `recent_row_count_7d` + derived `status` example for `vault`, `github`,
      `calendar`, and `sleuth` from the live DB.

Exit criteria:

- `last_*_at` and `recent_row_count_7d` are computable cheaply for the core sources, **no new table**.
- The set of sources needing custom windows/columns is named (or confirmed empty).
- **`vault` is the make-or-break case** — its rows live in `vault_files`/`chunks`, outside
  `_PEEKABLE_SOURCES`, so it is the source most likely to need a bespoke column/window. Prove it here;
  don't assume it.
- **If Phase 0 contradicts the no-new-table assumption, pause and escalate — do not start Phase 1.**

**QA gate:** findings (with `file:line`) written back into this doc; the four example outputs recorded
here; per-source window decisions recorded. `utils/pdda/pdda.sh run` clean for the doc edit.

#### Phase 0 — Findings (2026-07-01)

Spike run against live code (`src/rebalance/ingest/index_ops.py`, `src/rebalance/mcp/tools/index.py`)
and the live DB (`index_status` + `peek_source` MCP tools, DB
`~/Library/Application Support/rebalance-os/rebalance.db`). Method: `graphify query` to orient, then
Read the exact lines. Each claim below is CONFIRMED / REFUTED / UNVERIFIED against `file:line` actually read.

**Claims from §2 / the Phase 0 checklist, verified:**

| Claim (as drafted) | Verdict | Evidence (file:line read) |
|---|---|---|
| `index_status()` → `get_index_status()` is the surface; read-only per-source snapshot. | **CONFIRMED** | `get_index_status(database_path)` defined [index_ops.py:224](../../src/rebalance/ingest/index_ops.py#L224); docstring "Read-only. Safe to call frequently" L225-228. |
| Per-source freshness is derived per-table via `_safe_max(conn, table, col)`, not from a `sync_state` table. | **CONFIRMED** | `_safe_max` = `SELECT MAX(col)` [index_ops.py:166](../../src/rebalance/ingest/index_ops.py#L166); used per source e.g. `vault.last_ingested_at` L247, `github.activity_last_scanned_at` L255, `calendar.last_fetched_at` L262, `sleuth.last_synced_at` L268. |
| A `_safe_count_where` 7-day-window primitive already exists. | **CONFIRMED** | Defined `SELECT COUNT(*) FROM {table} WHERE {where}` at [index_ops.py:174](../../src/rebalance/ingest/index_ops.py#L174) (the *definition*; the sketch cited L273, which is a *use* site). Live-used for `apple_reminders.active` (`is_active=1 AND is_completed=0`) at [index_ops.py:273](../../src/rebalance/ingest/index_ops.py#L273). A `WHERE <ts_col> > <cutoff>` predicate is expressible with the same helper, no code change. |
| There is **no `sync_state` table**. | **CONFIRMED** | `grep -rniE "sync_state"` → **0 matches** across `src/` and all `*.py`/`*.sql` in the repo (graphify-out excluded). |
| `vault` is the make-or-break case (rows live in `vault_files`/`chunks`, outside `_PEEKABLE_SOURCES`). | **CONFIRMED** | `_PEEKABLE_SOURCES` [index.py:193](../../src/rebalance/mcp/tools/index.py#L193) has **no** `vault*` key; `get_index_status` reads vault from `vault_files`/`chunks` (L245-248). `peek_source` cannot reach vault; a bespoke count on `vault_files`/`chunks` is required for Phase 1. |

**Correction the spike found (REFUTED — must be carried into Phase 2):**

- The sketch/status claimed `payload["freshness"]` is "an initialized empty dict ready to hold derived
  labels." **REFUTED.** It is initialized empty at [index_ops.py:236](../../src/rebalance/ingest/index_ops.py#L236),
  but at [index_ops.py:385](../../src/rebalance/ingest/index_ops.py#L385) the function does
  `payload["freshness"] = drift`, **overwriting** it with a semantic-drift dict
  (`vault_chunks_missing_from_semantic`, `github_documents_missing_from_semantic`,
  `semantic_documents_pending_embed` — built L346-385). Live proof: `index_status` returns
  `"freshness":{"vault_chunks_missing_from_semantic":0,"github_documents_missing_from_semantic":302,"semantic_documents_pending_embed":12}`.
  **What it changes:** Phase 2 must **merge** derived `status`/`reason` into this dict (or nest under a
  sub-key), not assume it is a free home — writing there naively would clobber the existing drift signal.

**Content-timestamp column per source (checklist item 3) — locked from `_PEEKABLE_SOURCES`
([index.py:193](../../src/rebalance/mcp/tools/index.py#L193)) + `get_index_status` (L244-302):**

| Source | Content-ts column for `recent_row_count_7d` | Window decision | Note (verified) |
|---|---|---|---|
| `vault` | `vault_files.last_modified` (count `vault_files`, not `chunks`) | rolling 7d | Outside `_PEEKABLE_SOURCES`; bespoke count required. `last_modified` = when the note changed (content), vs `ingested_at` = sync ts. |
| `github` | `github_activity.scanned_at` | rolling 7d | `_PEEKABLE_SOURCES` maps `github_activity→scanned_at`; but `scanned_at` is a *sync* ts, so "recent volume" here means "rows scanned in", a weaker content signal — acceptable for v1 collapse-detection, flagged as a known approximation. |
| `calendar` | `calendar_events.start_time` | **bespoke: back 7d AND forward** | `_PEEKABLE_SOURCES` maps `calendar_events→start_time`. **Live finding:** all current events are *future* (`earliest_event_start` = `2026-07-07`), so a naive `start_time > now-7d` over-counts forward events and a `start_time BETWEEN now-7d AND now` under-counts a legitimately busy upcoming week. Calendar **needs the custom window** the doc's §8 open question anticipated. |
| `sleuth` | ambiguous — `created_on` (content) vs `last_seen_at` (sync) | rolling 7d, **decision: `created_on`** | Drift found: `_PEEKABLE_SOURCES` sorts `sleuth_reminders→last_seen_at`, but `get_index_status` reports `last_synced_at` (L268), while the true *content* ts is `created_on`. For volume-collapse we want *new* reminders → count on `created_on`. Live rows show `last_seen_at`/`last_synced_at` all today but `created_on` in early June — proof the columns diverge and the choice matters. |

**Checklist item 5 — four concrete `recent_row_count_7d` + derived `status` examples (live DB, 2026-07-01, window `> 2026-06-24`):**

- **`vault`** — 57 files, `last_modified_in_vault` = `2026-07-01T13:50` (today). Fresh + non-empty →
  `recent_row_count_7d` > 0 (counted on `vault_files.last_modified`); **`status: ok`**.
- **`github`** — 714 activity records, `activity_last_scanned_at` = `2026-07-01T15:45` (today); peeked rows
  scanned today with high commit counts → `recent_row_count_7d` > 0; **`status: ok`**.
- **`calendar`** — 1219 events, `last_fetched_at` = `2026-07-01T13:48` (fresh), but `earliest_event_start`
  = `2026-07-07` (all future). With the **default** rolling-back window `recent_row_count_7d` would be
  **0** → naive **`status: degraded`** — a **false positive**. With the **bespoke back-7d+forward** window it
  reads > 0 → **`status: ok`**. This example is the concrete proof calendar needs its custom window.
- **`sleuth`** — 121 reminders, `last_synced_at` = `2026-07-01T13:48` (fresh). Counted on `last_seen_at`
  (all today) → high count; counted on `created_on` (early June) → **0** in the last 7d. The two columns
  give opposite `status` (`ok` vs `degraded`), which is exactly why the column choice is a Phase 0
  decision, not a Phase 1 detail. Decision above: count `created_on`, and treat a genuinely quiet week as
  `warn`, not a hard fail (per §4 "not an adjudicator of zero").

**Exit criteria (from Phase 0) — met:**

- `last_*_at` + `recent_row_count_7d` are computable cheaply for the core sources with **no new table**
  (reuse `_safe_max` + `_safe_count_where`). ✔
- Sources needing a **custom window/column** are named, not empty: **`calendar`** (back-7d + forward) and
  **`sleuth`** (content ts `created_on` ≠ the peekable `last_seen_at`); `vault` needs a bespoke *count target*
  (`vault_files`) though a default window. `github` uses a sync-ts approximation, flagged. ✔
- `vault` proven (not assumed) to live outside `_PEEKABLE_SOURCES`. ✔
- **No contradiction of the no-new-table assumption** → Phase 1 is cleared to start (no escalation needed).
  One correction (the `freshness`-dict overwrite) is folded into Phase 2's plan above. ✔

**UNVERIFIED / deferred:** exact SQLite index presence per content-ts column (whether `start_time` /
`created_on` / `last_modified` are indexed, i.e. index-scan vs full-scan cost) was **not** inspected at the
`PRAGMA index_list` level in this spike; row counts are small (57–1282) so cost is negligible today, but
Phase 1 should confirm before assuming O(log n). Marked UNVERIFIED rather than claimed.

### Phase 1 — `recent_row_count_7d` in `index_status` — ✅ SHIPPED 2026-07-03

- [x] Added `recent_row_count_7d` to each source dict in `get_index_status`
      (`src/rebalance/ingest/index_ops.py`), via `_safe_count_where` on each source's
      content-timestamp column: `vault_files.last_modified`, `github_activity.scanned_at`,
      `calendar_events.start_time` (±7 days — events can be future-dated), `sleuth_reminders.created_on`,
      `apple_reminders.last_synced_at`, `email_messages.received_at`, `figma_comments.created_at`.
- [x] **No ingest change. No gate. No new table.** Pure additive read field.
- [x] Host agents can immediately read it ("you asked about this week but github shows 0 events —
      token scope?") even before `doctor` consumes it.

**QA gate — passed:** `tests/test_index_ops.py::test_get_index_status_recent_row_count_7d` seeds
recent+stale rows per source and asserts the field is present on all 8 sources, correct counts for
seeded sources (vault=1, calendar=2 across past+future), and zero-volume sources report `0` not
`None`. Full `pytest tests/` 1278 passed / 10 skipped; `rebalance doctor` clean. No new file beyond
the test; `index_status` stays read-only.

**Provenance:** built via a live XYZ marathon relay turn (builder=agy, reviewer=codex). The turn
itself was escalated as a containment violation (agy also touched `phases/p1b/RELAY.md` and
`uv.lock` outside its allowlist — both reverted by the turn-taker's safety guard), but the in-lane
code change was correct and independently re-verified before landing. Reported upstream to the XYZ
maintainer as three tooling gaps found live (reviewer-schema/runtime mismatch, unrecoverable
"spent" tick tasks, and a cross-repo `AGY_TURN_ROOT` path-resolution bug).

### Phase 2 — derived `status`/`reason` + one `doctor` warning path

- Derive `status` (`ok`/`warn`/`degraded`) + `reason` per source into `payload["freshness"]` from
  (a) staleness vs. the source's window and (b) zero/collapsed `recent_row_count_7d`.
- Add **one** `doctor` warning path ([cli/__init__.py:114](../../src/rebalance/cli/__init__.py#L114))
  that prints the degraded sources with their `reason`. No new screen, no new job.

**QA gate:** test feeds a fresh-but-empty source and asserts `status == "degraded"` with a non-empty
`reason`, and a healthy source asserts `ok`; `doctor` shows the degraded line on the seeded DB; legit
quiet source does **not** hard-fail (warn only). Full suite green; `doctor` clean.

**Verification summary (2026-07-05):** `pytest tests/test_index_ops.py tests/test_doctor.py`
passed (`33 passed`; independently re-run from the repo's own `.venv`). Coverage now proves three Phase 2 cases directly: a fresh-but-empty `vault`
source degrades with a non-empty reason, a healthy `vault` source stays `ok`, and a fresh-but-quiet
`sleuth` source warns instead of hard-failing. The CLI test also seeds a degraded DB and verifies the
single `rebalance doctor` warning line prints the degraded source plus its reason.

### Phase 3 — optional: surface degradation at query time (`ask`)

**Kill-gated:** only build if Phase 2's signal catches a *real* defect in live use (see Falsifiability).
If the `index_status`/`doctor` surface already changes behavior, this is unjustified — stop at Phase 2.

- When `ask()` answers from a source whose `status` is `degraded`, prepend a one-line visible warning
  ("⚠ calendar looks fresh but returned 0 rows this week — answer may be incomplete").

**QA gate:** test asserts the warning is prepended when a used source is `degraded` and absent when all
used sources are `ok`; synthesis output is otherwise unchanged; suite green.

---

## 6. Anti-goals

- **Not an ingest gate.** Never stops `refresh_index`, never rejects an upstream row, never blocks a
  sync. Observe-and-downgrade only.
- **Not a new subsystem.** No new table, no new MCP tool, no new pipeline in v1 — extend
  `index_status` + `doctor`, reuse `_safe_count_where` and `payload["freshness"]`.
- **Not a relevance engine.** v1 detects *freshness/volume* degradation. The GH-81 relevance class is
  the motivation, not the v1 deliverable — kept as a shared "signal health" surface, decided in §7.
- **Not an adjudicator of zero.** A legitimately quiet week must not hard-fail; the contract surfaces
  the anomaly for the host agent to interpret.

---

## 7. Falsifiability — this is only worth keeping if it catches real defects

The contract earns its place only if it flags defects the current system misses:

- **Plain staleness:** semantic backfill crashes mid-vault-refresh; `vault` stops updating → flag stale
  `last_*_at` before `ask` serves stale context as current.
- **False freshness:** PAT loses `repo` scope but keeps public; sync still "succeeds" → flag the
  recent-volume collapse instead of reporting fully healthy.
- **Silent empty set:** Gmail/Calendar auth breaks into a clean `[]` → surface "fresh but empty"
  instead of letting `ask` answer "nothing happened."

**Note the ceiling:** all three are *collapse-to-empty* or *stale* defects — none is the *partial*
silent drop GH-81 was. v1 does not claim that class; if partial relevance loss is the real worry, that
is the Phase 4+ relevance surface, not a v1 miss.

If, after Phase 2, none of these three is caught on the live DB, **stop** — the contract is not paying
for itself and Phase 3 is unjustified.

---

## 8. Open questions

- Should `ask()` prepend a visible degraded-source warning (Phase 3), or is the `index_status`/`doctor`
  surface enough? (Kill-gated above.)
- Should "expected volume" stay heuristic + agent-interpreted, or should some sources declare an
  explicit floor in config?
- Is a rolling `recent_row_count_7d` enough, or do some sources need bespoke windows (e.g.
  `calendar_30d_back_7d_forward`)? — **decided in Phase 0.**
- **Relevance degradation (the GH-81 class) is out of v1 by design, not merely deferred.** v1 ships
  freshness/volume health only — it catches collapse-to-empty and staleness, *not* the partial silent
  drop GH-81 itself was. Whether partial-relevance health shares this surface or gets its own is the
  Phase 4+ question; v1 does not pretend to answer it.

---

## 9. Relationship to existing work (don't duplicate)

This is a **read-side health contract**, distinct from the in-flight signal efforts — it should not
fork them:

- [ROADMAP-SIGNAL-SCAN.md](PDDA-INTEGRATION/ROADMAP-SIGNAL-SCAN.md) — adds a *new `roadmap` collector*
  (a source). This plan instead *grades the health of existing sources*. Complementary: a future
  `roadmap` source would get `recent_row_count_7d` for free.
- [GEMINI-WHATS-NEXT-VAULT.md](GEMINI-WHATS-NEXT-VAULT.md) / [SIGNAL-GENERATION/](../2-WORKING/SIGNAL-GENERATION/) —
  the *synthesis/ranking* plane. This contract feeds it trust metadata; it is not a second ranker.
- [WATCHLIST-COVERAGE-GUARD.md](../2-WORKING/WATCHLIST-COVERAGE-GUARD.md) — already guards *repo
  roster* drop-off via the focus5-snapshot pattern. Reuse its snapshot/anomaly idiom for volume
  collapse rather than inventing a new one.

---

## 10. Verification (per ROUTER §7)

`rebalance doctor` clean + `pytest tests/` green before any success claim on a code phase.
Doc-hygiene: `utils/pdda/pdda.sh run` clean before promoting this doc to `2-WORKING`.

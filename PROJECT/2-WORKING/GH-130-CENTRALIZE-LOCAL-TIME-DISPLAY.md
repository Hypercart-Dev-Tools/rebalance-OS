---
title: "Centralize UTC→local time display: shared helper + replace raw-UTC user-facing screens with labeled local time"
owner: noel@neochro.me
gh_issue: 130
source: "https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/130"
status: "Active (2-WORKING) — captured and promoted 2026-07-16, starting build same session."
created: 2026-07-16
updated: 2026-07-16
doc_type: project
goal: >
  Add the missing display-formatting layer to the existing `src/rebalance/tz_utils.py` (already the
  single source of truth for local-tz *resolution*, but has no shared local-tz *display* formatter),
  migrate the 5 known ad-hoc UTC→local implementations onto it, and fix the one confirmed user-facing
  screen that shows a raw, unconverted, unlabeled UTC timestamp.
non_goals: >
  No change to how timestamps are stored (SQLite stays UTC ISO-8601). No new timezone-selection UI —
  resolution stays REBALANCE_TZ env > /etc/localtime > UTC (already correct). Not chasing the
  low-confidence web/pulse.html tooltip finding (its generator isn't in tracked source — see Open
  Questions). Not touching the Focus5Float Swift app (confirmed relative-time-only, no raw UTC display).
related:
  - src/rebalance/tz_utils.py
effort: 3
complexity: 2
risk: 2
phases: 3
---

## Status

| What was just completed | What's next |
|---|---|
| **Captured 2026-07-16** from issue #130. Full-repo audit (Python CLI/dashboard, web templates, Focus5Float Swift) found no Jinja templates and no additional raw-UTC display hits beyond the two below; confirmed `src/rebalance/tz_utils.py` already exists as the tz-*resolution* single source of truth (`local_tz()`, `to_local()`, `parse_utc_iso()`) but is missing a shared *display*-formatting layer — that gap is what the 5 ad-hoc implementations independently reinvented. | **Phase 1** — add `format_local()` / `format_relative()` to `tz_utils.py` + tests (the module currently has zero test coverage). |

---

## Table of contents

- [Thesis](#thesis)
- [Context (grounded)](#context-grounded)
- [Phase 1 — Add display formatters to tz_utils.py](#phase-1--add-display-formatters-to-tz_utilspy)
- [Phase 2 — Migrate the 5 ad-hoc implementations](#phase-2--migrate-the-5-ad-hoc-implementations)
- [Phase 3 — Fix the confirmed raw-UTC display bug](#phase-3--fix-the-confirmed-raw-utc-display-bug)
- [Anti-goals](#anti-goals)
- [Open Questions](#open-questions)

---

## Thesis

`tz_utils.py` already solves timezone *resolution* correctly and is reused by 4 files. What's missing
is the *formatting* half — turning a resolved local datetime into a display string — so every call
site reinvented its own parse-guard-convert-format boilerplate instead of sharing one. This is a
**small, additive, low-risk consolidation**: two new functions in an existing module, thin wrappers at
each of the 5 call sites that preserve their *exact current visible output* (same `strftime` patterns,
same fallback behavior), plus one genuinely new fix — a CLI screen that currently shows a bare UTC
string with no conversion and no label at all.

## Context (grounded)

**The existing seam** (`src/rebalance/tz_utils.py`, currently unused for display — only for resolution):
- `local_tz()` (line 17) — REBALANCE_TZ env → `/etc/localtime` → UTC fallback. Used by `calendar_config.py`, `next_actions.py`, `note_builder.py`, `pulse.py`.
- `to_local(dt, tz=None)` (line 44) — treats naive datetimes as UTC, converts to local.
- `parse_utc_iso(value)` (line 54) — parses ISO-8601 (handles trailing-`Z`), assumes UTC if tz-naive.
- **Zero test coverage** on any of these three — a real, pre-existing gap this work will close as a byproduct.

**The 5 ad-hoc display implementations (duplicated parse-guard-convert-format logic):**
1. [`pulse.py:709`](../../src/rebalance/ingest/pulse.py#L709) `_fmt_local(dt_value, tz, *, time_only=False)` — `"%b %-d %-I:%M %p"` or `"%-I:%M %p"`.
2. [`pulse.py:819,824`](../../src/rebalance/ingest/pulse.py#L819) — inline in `_render_section_calendar`, bypasses its own file's `_fmt_local`, same `"%-I:%M %p"` pattern.
3. [`next_actions.py:1619`](../../src/rebalance/ingest/next_actions.py#L1619) `_fmt_local_stamp(iso_utc, tz)` — `"%Y-%m-%d %H:%M %Z"`, falls back to `iso_utc or "unknown"` on parse failure.
4. [`daily_report.py:301`](../../src/rebalance/ingest/daily_report.py#L301) `_event_local_time(event, config)` — takes an **already-parsed** `datetime` (via `parse_calendar_dt`, not ISO text), formats `"%I:%M %p"` then manually `.lstrip("0")`; falls back to `"—"`.
5. [`note_builder.py:496`](../../src/rebalance/ingest/note_builder.py#L496) `_format_generated_at(value)` — `"%Y-%m-%d %H:%M:%S %Z"`, falls back to the raw `value` on parse failure.

**A 6th, related-but-distinct pattern** (relative, not absolute, time — folded in since it's the same
"don't hand-roll a UTC display formatter" problem):
6. [`web.py:473`](../../src/rebalance/web.py#L473) `_rel_time(iso)` — `"{d/h/m}{unit} ago"` compact relative age. Byte-for-byte portable to a shared helper (no tz needed for a delta) — the only **zero-behavior-change** migration in this set.

**The one confirmed raw-UTC display bug** (the actual "replace" target from the issue):
- [`cli/semantic.py:166,171-172`](../../src/rebalance/cli/semantic.py#L166) — `rebalance semantic-search` prints `updated: 2026-07-16 08:04:21` (UTC, `T`→space swapped, **no conversion, no timezone label at all** — ambiguous to a human reading it).

## Phase 1 — Add display formatters to tz_utils.py

**Scope:** two new functions, additive only — nothing existing in `tz_utils.py` changes shape.

**Design:**
```python
def format_local(value: str | datetime | None, fmt: str, *, tz: ZoneInfo | None = None) -> str:
    """Parse `value` (UTC ISO-8601 string, or an already-parsed datetime — naive
    treated as UTC), convert to local tz, and render with the given strftime
    pattern. Returns "" on None/unparseable input so callers choose their own
    fallback text — behavior-preserving for the 5 existing call sites, which
    each have a different fallback string today."""

def format_relative(value: str | datetime | None, *, now: datetime | None = None) -> str:
    """'{d/h/m}{unit} ago' / 'just now' — the exact algorithm currently in
    web.py's _rel_time, hoisted so it has one home and one test."""
```
- `format_local` accepts `str | datetime` (not just ISO text) so it can serve `daily_report.py`, which
  already has a pre-parsed `datetime` in hand via its own specialized `parse_calendar_dt` — no double-parsing.
- Callers keep their own exact `strftime` pattern (passed in), so **no visible-output change** for the
  4 already-correct absolute-time call sites — only the boilerplate (parse/guard/convert) is shared.

**Checklist:**
- [ ] Add `format_local()` and `format_relative()` to `src/rebalance/tz_utils.py`.
- [ ] New `tests/test_tz_utils.py` — cover the 3 *existing* untested functions (`local_tz()` env override + fallback, `to_local()` naive/aware, `parse_utc_iso()` Z-suffix/offset/malformed) **and** the 2 new ones (string input, datetime input, malformed → `""`, DST-boundary case for `format_relative`).

### Phase 1 — QA gate
- [ ] `pytest tests/test_tz_utils.py -v` green.
- [ ] `rebalance doctor` clean (no regression from the new module surface).

## Phase 2 — Migrate the 5 ad-hoc implementations

**Scope:** each of the 5 sites becomes a thin wrapper preserving its exact current fallback + format string. This is a **behavior-preserving refactor**, not a rewrite — the QA gate is "output is byte-identical to before."

**Checklist:**
- [ ] `pulse.py` `_fmt_local` body → `format_local(dt_value, "%-I:%M %p" if time_only else "%b %-d %-I:%M %p", tz=tz)`.
- [ ] `pulse.py:819,824` inline calendar formatting → call `format_local(...)` directly (same pattern, one fewer duplicate).
- [ ] `next_actions.py` `_fmt_local_stamp` → `format_local(iso_utc, "%Y-%m-%d %H:%M %Z", tz=tz) or (iso_utc or "unknown")` (preserves its distinct fallback).
- [ ] `daily_report.py` `_event_local_time` → `format_local(start_dt, "%I:%M %p", tz=ZoneInfo(config.timezone)).lstrip("0") or "—"` (preserves its distinct fallback; passes the already-parsed `datetime`, not re-parsing).
- [ ] `note_builder.py` `_format_generated_at` → `format_local(value, "%Y-%m-%d %H:%M:%S %Z", tz=local_tz()) or value` (preserves its distinct fallback).
- [ ] `web.py` `_rel_time` → delegates to `format_relative()` (exact same algorithm — zero-behavior-change migration).

### Phase 2 — QA gate
- [ ] Full suite green: `pytest tests/`.
- [ ] Targeted diff-read of each migrated function against its pre-migration body to confirm the fallback string is preserved exactly (no silent behavior change on an already-working screen).
- [ ] `rebalance doctor` clean.

## Phase 3 — Fix the confirmed raw-UTC display bug

**Scope:** `cli/semantic.py`'s `rebalance semantic-search` output currently prints a bare, unlabeled,
unconverted UTC string. Replace with an explicit "Local Time" label + the converted local timestamp.

**Checklist:**
- [ ] `cli/semantic.py:166,171-172` — replace `updated_at = (result.get("updated_at") or "")[:19].replace("T", " ")` / `typer.echo(f"   updated: {updated_at}")` with `format_local(result.get("updated_at"), "%Y-%m-%d %H:%M %Z", tz=local_tz())`, echoed as `typer.echo(f"   Local Time: {local_str}")` (only when non-empty — no change to the empty-input no-op behavior).

### Phase 3 — QA gate
- [ ] Manual: `rebalance semantic-search <query>` against real data — confirm output reads "Local Time: 2026-07-16 08:04 PDT" (or the operator's actual tz), not a bare UTC string.
- [ ] `pytest tests/` still green; `rebalance doctor` clean.
- [ ] `CHANGELOG.md` end-of-iteration entry (PDDA flagged the changelog as 1 day stale at capture time).

---

## Anti-goals

- **Not a rewrite.** Each of the 5 migrated call sites keeps its exact current format string and fallback text — this is deduplication of shared boilerplate, not a redesign of what any screen shows.
- **Not touching storage.** SQLite stays UTC ISO-8601 everywhere; only the display layer changes.
- **Not a new timezone-selection UI.** Resolution order (`REBALANCE_TZ` → `/etc/localtime` → UTC) is already correct and unchanged.
- **Not chasing the `web/pulse.html` tooltip** — see Open Questions.
- **Not touching Focus5Float** — confirmed Swift-side is relative-time-only (`RelTime.ago()`), no absolute UTC ever rendered.

## Open Questions

- `web/pulse.html:930-932` has a debug tooltip literally reading `"UTC now: 2026-07-17T02:00:07Z"`. The file is gitignored and its generating source could not be located anywhere in tracked `src/rebalance` (grepped for `system-now`, `UTC now`, `tz-key` — zero hits). The visible main-line text next to it is already correctly local + labeled (`System: Thu Jul 16 · 19:00:07 PDT -07:00 · America/Los_Angeles`), so this may be an intentional debug aid rather than a bug. **Decision needed from the operator**: leave as-is (debug tooltip, arguably fine) or investigate further once the generator is located. Not blocking this plan.

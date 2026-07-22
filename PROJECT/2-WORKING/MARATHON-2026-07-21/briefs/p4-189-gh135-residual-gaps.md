---
title: "MARATHON-2026-07-21 P4 — GH-189 (GH-135 residual gaps)"
status: "Brief authored; phase not yet run"
created: 2026-07-21
updated: 2026-07-21
owner: noel
gh_issue: 189
roadmap_exempt: true
---

# Phase 4 — close GH-135's 2 residual acceptance gaps

Part of **GH-189**. Issue: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/189
Disjoint from every other phase in this marathon. **Artifact:** `src/rebalance/doctor.py`
(health-banner age string, line 1192 at time of writing), `scripts/pulse_web.py`
(`render_repo_pie()`, line 1023, labels built at line 1039).

## The problem

GH-135 (Pulse dashboard consistency refactor, shipped) collapsed the dashboard onto one shared
timestamp helper and one shared row component, but two defects were out of scope for all 4 of its
phases and diagnosed-but-not-fixed in its own acceptance verification:

1. **Bare relative time in the health banner.** `doctor.py:1192` builds
   `f"last scan {health.age_hours / 24:.1f}d ago"` and hands the dashboard a pre-formatted string
   with no absolute anchor. Every other timestamp on the page now goes through
   `format_timestamp()` (absolute + relative suffix, `src/rebalance/tz_utils.py`) — this is the
   one place still emitting a bare relative.
2. **Org prefixes in the repo-pie chart.** `render_repo_pie()` feeds
   `r.get("repo_full_name")` (e.g. `Hypercart-Dev-Tools/rebalance-OS`) straight into the
   `repo-pie-data` JSON payload, and the pie legend displays it verbatim. GH-135's Phase 3 scoped
   org-stripping to `render_recent_activity` (GitHub activity rows) only — the pie chart was
   never touched.

## ⛔ Hard invariants

- **Reuse `format_timestamp()` / `tz_utils.py` for gap 1** — do not build a second ad-hoc
  formatter. Either move the formatting decision into the render layer (have `doctor.py` return
  raw `age_hours`/a timestamp and let `pulse_web.py` format it), or call `format_timestamp()`
  directly wherever the banner string is composed. No new time module (same invariant GH-135 and
  GH-130 established).
- **For gap 2, reuse the org-stripping convention GH-135 Phase 3 already established** for
  `render_recent_activity` (short name in the visible label, full `org/repo` available via a
  title/tooltip attribute) — do not invent a different stripping rule.
- **Two more org-prefix occurrences live inside Sleuth reminder body text — explicitly NOT in
  scope.** That's the reminder's own data content, not a rendered label, and isn't fixable at the
  render layer. Do not touch Sleuth reminder rendering in this phase.
- **Presentation only** — no data-source, collector, route, or API-handler changes (same anti-goal
  as the parent GH-135 work).

## Task

1. Fix `doctor.py`'s health-banner age string to carry (or be paired with) an absolute anchor via
   `format_timestamp()`.
2. Fix `render_repo_pie()` to emit a short repo name in the visible label and the full
   `org/repo` path as a title/tooltip attribute, mirroring `render_recent_activity`'s existing
   pattern.

## Acceptance

- [ ] No bare relative time remains in the health banner — absolute anchor present.
- [ ] Repo-pie legend shows short repo names; full `org/repo` still available (tooltip/title).
- [ ] Sleuth reminder body text is untouched (confirmed out of scope, not silently skipped).
- [ ] `pytest tests/ -k "doctor or pulse_web"` green.
- [ ] `rebalance doctor` clean; page regenerated through `pulse_web.py` and verified live.

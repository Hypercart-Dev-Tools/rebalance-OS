---
title: "GH-146 P4 — deep work stall check uses UTC 'today' against a local-time operator"
status: "Brief authored; phase not yet run"
created: 2026-07-18
updated: 2026-07-18
owner: noel
gh_issue: 146
roadmap_exempt: true
goal: >
  Marathon phase brief (harness input, not a tracked effort). Pin the deep-work stall check's
  "today" to the operator's local day instead of UTC, so it stops reporting every project quiet
  every evening after 5 PM Pacific.
---

# GH-146 P4 — `deep work` stall check uses UTC "today" against a local-time operator

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-07-18; parent capture is `PROJECT/1-INBOX/GH-146-HEALTH-SIGNAL-ACCURACY.md` | Execute as marathon phase `gh146-p4-deep-work-tz` (reviewer: agy) after P3. Takes the marathon from 5 warns → 0. |

## The defect

`src/rebalance/doctor.py:1015`, inside `_check_deep_work_stalls()`:

```python
signals = compute_deep_work_signals(
    db_path,
    datetime.now(timezone.utc).date(),   # <-- "today" in UTC
    lookback_days=7,
)
```

"Today" is computed as the **UTC** date. The operator runs in Pacific time. At 18:59 PDT the UTC
date is already the *next* day — so the check asks "has anything happened on 2026-07-19?" about a
day that began two hours ago, and every project is trivially quiet.

Live evidence, 2026-07-18 at 18:59 local:

```
WARN  deep work — Hypercart-Dev-Tools/rebalance-OS: quiet 2026-07-19 after 2026-07-18 ...;
      Neochrome: quiet 2026-07-19 after 2026-07-18 ...;
      NeochromeTeam/sleuth-app: quiet 2026-07-19 after 2026-07-18 ...;
      Rebalance OS: quiet 2026-07-19 after 2026-07-18 ...;
      Xyz 3 Agents Swarm: quiet 2026-07-19 after 2026-07-18 ...
```

**Five projects, all "quiet", all false.** This fires every evening after 17:00 PDT (00:00 UTC)
and is the single noisiest line in `doctor` output.

## This bug class was already fixed once

GH-129 ("Git Pulse Daily Summary false 'No git activity found today'") was the same defect — its
primary fix was a day-boundary tz pin, shipped 2026-07-14. It was fixed there and missed here.
That is exactly the pattern issue #145 names: *"a second, naive copy of the collector-health rule
lives in the CLI."*

**So the fix must not create a third copy.** Reuse the existing seam.

## What to build

The fix is at the **call site**, not inside `compute_deep_work_signals()`.
`compute_deep_work_signals(database_path, today, lookback_days)` already takes `today` as an
injected parameter — its contract is correct. The caller is passing the wrong value.

- `src/rebalance/tz_utils.py` already exposes **`local_tz()`**. Use it.
- Compute "today" in the operator's local day, e.g. `datetime.now(local_tz()).date()`.
- Do **not** add a new timezone helper, a new config key, or a local copy of the day-boundary
  rule. If `tz_utils` lacks something you need, extend `tz_utils` — do not work around it.

While you are here: `src/rebalance/doctor.py:405` also uses `datetime.now(timezone.utc).date()`.
**Do not fix it in this phase** — it is a different check with its own semantics, and widening the
diff makes the regression harder to attribute. **Report it** in your turn so it can be triaged
separately.

## Acceptance criteria

- At 18:59 local on day N, the check evaluates "today" as day **N**, not N+1.
- A project genuinely quiet for a full local day still WARNs — this phase removes a false alarm,
  it must not remove the true one.
- No new timezone helper is introduced; `tz_utils.local_tz()` is the single source.
- `compute_deep_work_signals()` itself is unchanged (its injected-date contract is correct).

## Tests (required)

Add `tests/test_doctor_deep_work_tz.py`. `tests/` is explicitly in your artifact allowlist; a fix
without a test is not complete.

Cover at minimum:
- **The regression:** freeze local time at 18:59 PDT on day N → the date passed to
  `compute_deep_work_signals` is day N. This assertion must FAIL against the current
  `datetime.now(timezone.utc).date()` and pass after.
- Morning local time (e.g. 09:00 PDT) → still day N (guards against over-correcting).
- A genuinely stalled project still produces a WARN.
- Timezone-invariance: the check's notion of "today" does not change when the process TZ is UTC
  vs the operator's local zone for the same instant.

State in your turn which assertion demonstrates the fail-before/pass-after property.

## Verification — this phase closes the marathon

Run `.venv/bin/python -m rebalance doctor` and report the **total warn count**.

Baseline entering this marathon was **5** warns:
`deep work`, `pulse collector:MBP 16"`, `scheduler:git-pulse-daily-synthesis`,
`launchd:daily-sync`, `launchd:pulse-server`.

P1–P3 target the latter four. This phase targets `deep work`. Target after all four phases: **0**.

Report the actual number honestly. If warns remain, name them — an honest 2 is far more useful
than a claimed 0. Note that `deep work` can only be observed as fixed if the run happens after
17:00 local; if you run earlier, say so rather than claiming a pass you could not see.

## Out of scope

- `scripts/daily_sync.sh` (P1), the launchd/JSON path (P2), device scoping (P3)
- `doctor.py:405` — report, do not fix
- Any change to `compute_deep_work_signals()`
- The collector sentinel loop

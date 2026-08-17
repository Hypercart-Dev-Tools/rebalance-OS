---
title: "GH-146 P3 — Device-scoped checks stop warning on the wrong device"
status: "Complete — phase ran and was approved; GH-146 marathon merged 2026-07-19 via PR #151."
created: 2026-07-18
updated: 2026-07-18
owner: noel
gh_issue: 146
roadmap_exempt: true
goal: >
  Marathon phase brief (harness input, not a tracked effort). Stop device-bound checks from
  warning on machines they do not describe, and prove the marathon's end-to-end warn-count drop.
---

# GH-146 P3 — Device-scoped checks stop warning on the wrong device

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-07-18; parent capture is `PROJECT/1-INBOX/GH-146-HEALTH-SIGNAL-ACCURACY.md` | Execute as marathon phase `gh146-p3-device-scoping` (reviewer: codex) after P2. Final phase — reports the warn-count delta (baseline 8 → target ~1). |

## The defect

Checks bound to a specific machine warn on **every** machine. Observed 2026-07-18 on the Mac
Studio, where nothing is wrong:

| Check | Detail | Reality |
|---|---|---|
| `pulse collector:Noel's MBP 16" M1 Pro` | ALERT — last scan 2.0d ago | A laptop. Not always on. |
| `pulse collector:noel's MacBook Pro 14"` (4/6 runs) | STALE — last scan 7.0h ago | Same. |
| `scheduler:git-pulse-daily-synthesis` (1/6) | scheduled job is not loaded on this device | By design. |

A laptop being closed is not a fault, and the Mac Studio is the wrong place to report it. These
are permanent warns that never clear, so they train the operator — and any automation — to ignore
the health output entirely.

## Depends on P2

P2 edits `src/rebalance/doctor.py` before you. Rebase onto its result; do not revert or duplicate
its changes. Keep your diff tight and additive.

## What to build

Make device-bound checks report against the device they belong to:

- A check for a job that runs on exactly one device should not warn on other devices. Report it
  as **not-applicable / other-device**, or omit it — but do not emit a WARN that implies local
  breakage.
- Staleness thresholds for intermittently-online devices (laptops) should not use the
  always-on-workstation threshold. A laptop 7 hours stale is normal.
- Keep the information available. The goal is that the Mac Studio's health output describes the
  Mac Studio; a fleet view is still legitimate, it just is not this check's job to raise as a
  local warning.

Prefer the registry seam over per-source branching in the health module — adding a per-source
behavior should not require editing the health module (Principle 3). The collector registry
already owns `semantic_docs=` and `candidates=` providers; if device scoping fits that pattern,
use it. If it does not, say why in your turn rather than forcing it.

## Acceptance criteria

- The two `pulse collector:*` laptop checks no longer WARN on the Mac Studio.
- `scheduler:git-pulse-daily-synthesis` no longer WARNs on a device where it is not meant to load.
- A device-bound check **does** still warn on the device it belongs to.
- A genuinely stale always-on collector still warns.
- No non-device-bound check changes behavior.

## Tests (required)

Add `tests/test_doctor_device_scope.py`. `tests/` is explicitly in your artifact allowlist.

Cover at minimum:
- device-bound check evaluated on a foreign device → not a WARN
- same check evaluated on its own device, stale → WARN
- intermittent-device threshold differs from always-on threshold
- non-device-bound check → unchanged

Must fail before, pass after. State which assertion demonstrates that.

## Verification — this is the phase that proves the whole marathon

Run `.venv/bin/python -m rebalance doctor` and report the **total warn count**. Baseline before
GH-146 was **8**. Target after all three phases is roughly **1** (the `email data` 31-day
staleness, which is a real defect and deliberately out of scope).

Report the actual number honestly. If warns remain that this marathon was supposed to clear,
name them — an honest 3 is far more useful than a claimed 1.

## Out of scope

- `scripts/daily_sync.sh` (P1)
- The launchd/JSON reading path (P2)
- The `email data` 31-day staleness — real, separate issue
- The collector sentinel loop

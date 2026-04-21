# Drift Reminder Action Plan

## TOC
- Overview
- Problem Statement
- Phase 0 Spike
- Deliverables
- Signal Model
- Output Contract
- Surfaces
- Configuration
- Risks
- Phases

## Overview

Goal: surface per-repo, per-device "drift" state (dirty worktrees, unpushed commits, stashes) so the operator is reminded — from *any* device — when work left on another machine is going stale.

Positioned primarily as a read-side feature over the unified activity pipeline described in issue #12. The intent is to reuse the pulse capture data the local agent is already writing — but Phase 0 is explicitly allowed to extend the capture pipeline with one lightweight repo-state snapshot if the needed fields aren't already emitted. Any such extension must be minimal (no new subprocess fanout, no network calls) and land in the same JSONL stream.

This plan is intentionally isolated in `/experimental`:
- no auto-commit or auto-push behavior
- no external notification services
- no LLM dependency
- no daemon or always-on process

## Problem Statement

Working across 3 devices and 6-7 projects means uncommitted or unpushed work routinely gets stranded on a machine the operator isn't currently using. GitHub dashboards cannot see this because the work hasn't been pushed. The collection layer already captures the raw signal per-device; what's missing is a cross-device reminder surface that turns that signal into an action.

The highest-value reminder is cross-device: *while sitting at device A, be told that device B has dirty work from 3 days ago*. Same-device "you have uncommitted changes" is just a styled `git status` and has much lower novelty.

## Phase 0 Spike

### Checklist
- [ ] Confirm pulse capture already emits (or can cheaply emit) the fields in Signal Model below
- [ ] Prototype `rebalance drift` as a standalone script reading the latest capture per device from `events/*.jsonl`
- [ ] Render a single markdown summary table grouped by device and severity
- [ ] Validate against a real multi-device scenario (induce dirty + unpushed state on one machine, query from another)
- [ ] Decide thresholds empirically after 1 week of ambient usage
- [ ] Decide which surfaces graduate to phase 1 (sync summary vs shell hook vs daily digest vs system notification)

### Scope

1-2 hour spike to validate:
- capture data is rich enough to compute drift without new collection logic
- cross-device latest-state resolution is unambiguous (one device = one latest row per repo)
- markdown output is useful both as a CLI printout and as a committed report

## Deliverables

### First-pass files
- `experimental/drift-reminder-plan.md`
- `experimental/rebalance_drift.py` (or equivalent) — standalone script
- `experimental/samples/drift-report.md` — example rendered output

### Out of scope for this pass
- shell prompt integration
- macOS/Linux system notifications
- launchd / cron scheduling
- auto-push or auto-stash behavior
- cross-device conflict detection (two devices editing the same branch)
- per-project priority weighting of drift severity

## Signal Model

Each pulse capture emits one row per tracked repo per device:

```json
{
  "device": "<stable device id>",
  "repo_id": "<canonical, stable across devices>",
  "repo_display": "<human-friendly name or path>",
  "branch": "<current branch>",
  "dirty_files": 0,
  "unpushed_commits": 0,
  "stash_count": 0,
  "oldest_dirty_mtime": "<iso8601>",
  "oldest_unpushed_commit_ts": "<iso8601>",
  "newest_unpushed_commit_ts": "<iso8601>",
  "last_capture_ts": "<iso8601>"
}
```

### Repo identity

`repo_id` is the stable join key across devices — basenames can collide (two projects both called `scripts`), so a single writer owns the canonical id and every device's capture resolves to it. Candidate sources, in preference order: GitHub `owner/repo` for repos with a remote, else the git config `remote.origin.url` hash, else a content hash of the first commit. `repo_display` is derived and purely for humans; never used as a key.

### Severity bands (repo state only — device freshness handled separately)

| Band | Rule |
|------|------|
| ok | `dirty_files = 0 AND unpushed_commits = 0 AND stash_count = 0` |
| yellow | `dirty_files > 0 AND now - oldest_dirty_mtime > 24h` |
| orange | `unpushed_commits > 0 AND now - oldest_unpushed_commit_ts > 48h` |
| red | `unpushed_commits > 0 AND now - oldest_unpushed_commit_ts > 7d` (likely forgotten work, not a sleeping laptop) |

The unpushed age signal uses `oldest_unpushed_commit_ts` because the interesting question is *"what's been hanging the longest?"* not *"when did I last touch this?"* A freshly added commit on top of week-old unpushed work should still surface the week-old drift.

### Device freshness (meta-signal, separate from repo bands)

A device that hasn't checked in recently cannot contribute reliable repo state. This is a property of the device, not its repos, so it's surfaced independently:

- `stale_captures` entries in the output list devices with `now - last_capture_ts > stale_capture_warn_hours`
- Repos from stale devices are still shown, but annotated `(device last seen Nh ago)` so the operator knows the state may be out of date
- A sleeping laptop therefore does **not** turn every repo red — it produces one device-level warning instead of dozens of noisy repo-level ones

### Signals deferred

- branch staleness vs origin (behind count)
- rebase/merge in progress
- detached HEAD
- submodule drift
- per-repo priority weighting

These can be layered in later without changing the capture format.

## Output Contract

### JSON

```json
{
  "generated_ts": "<iso8601>",
  "devices": ["mbp-16", "desktop", "work-mbp"],
  "counts": {"ok": 0, "yellow": 0, "orange": 0, "red": 0},
  "drift": [
    {
      "device": "...",
      "repo_id": "owner/repo",
      "repo_display": "repo",
      "branch": "...",
      "band": "orange",
      "reasons": ["3 unpushed commits", "oldest unpushed 52h ago"],
      "dirty_files": 0,
      "unpushed_commits": 3,
      "stash_count": 0,
      "last_capture_ts": "...",
      "device_stale": false
    }
  ],
  "stale_captures": [
    {"device": "...", "hours_since_capture": 192}
  ]
}
```

### Markdown

- summary counts per band
- section per device with severity-sorted repo list
- explicit reason bullets per row
- footer: stale captures (devices that haven't checked in recently — meta-drift)

The markdown format is designed to feed:
- `rebalance sync` end-of-run summary
- committed `reports/drift-YYYY-MM-DD.md`
- shell prompt one-liner (first line of summary)

## Surfaces

Each surface is opt-in, layered, and reads the same JSON output.

1. **`rebalance sync` summary** — always on after phase 1. Zero marginal cost; runs at the end of sync.
2. **Shell prompt / MOTD hook** — opt-in snippet that reads the most recent drift JSON and prints a one-liner. No live query.
3. **Daily committed digest** — `reports/drift-YYYY-MM-DD.md` written by the GitHub Action poller so the report is visible on every device after pull.
4. **System notification** — optional launchd/cron job that runs `rebalance drift --notify-if-red`. Off by default.

## Configuration

Under a `drift:` key in the project config:

```yaml
drift:
  dirty_warn_hours: 24
  unpushed_warn_hours: 48
  stale_alert_days: 7
  stale_capture_warn_hours: 72
  ignore_repos:
    - scratch
    - experiments/*
  ignore_branches:
    - wip/*
```

All thresholds tunable without code changes. `ignore_*` lets the operator mute known-safe drift (scratch repos, long-lived WIP branches).

## Risks

- Capture frequency varies per device; a laptop asleep for a week should not mass-flag every repo. Handled by keeping device freshness out of repo severity bands and surfacing it as a single `stale_captures` meta-signal instead.
- Clock skew across devices could misorder "oldest" calculations. Use capture timestamps from each device's own clock and accept minor skew; don't attempt cross-device time reconciliation.
- Over-notification fatigue. Default to least-intrusive surfaces (sync summary, committed report). Make shell hook and system notification explicit opt-in.
- Operator may legitimately want to leave dirty state on a machine (in-progress experiment). `ignore_branches` + severity bands over-time (not over-count) keep this tolerable; explicit `--mute <repo>` flag available for one-off silencing.
- mtime noise (formatters, checkouts) inflating `dirty_files` counts. Accept; the count matters less than presence + age.

## Phases

### Phase 1 — Spike POC
- [ ] Confirm pulse capture fields (extend if needed; fields are cheap)
- [ ] Implement `rebalance drift` reading latest capture row per (device, repo)
- [ ] Emit JSON and markdown per Output Contract
- [ ] Wire into `rebalance sync` end-of-run summary
- [ ] Commit sample output to `experimental/samples/`
- [ ] Use for 1 week ambient to calibrate default thresholds

### Phase 2 — Ambient visibility
- [ ] Add daily `reports/drift-YYYY-MM-DD.md` generation from the GitHub Action poller
- [ ] Add `ignore_repos` and `ignore_branches` config support
- [ ] Add `--mute <repo>` one-off flag writing to a local mute file
- [ ] Add `stale_captures` meta-signal to surface devices that haven't checked in

### Phase 3 — Opt-in nudges
- [ ] Shell prompt / MOTD snippet (documented, not installed by default)
- [ ] System notification subcommand (`rebalance drift --notify-if-red`)
- [ ] launchd plist / systemd timer examples in `experimental/`

### Phase 4 — Later / deferred
- [ ] Branch-behind-origin detection (requires fetch, not free)
- [ ] Per-project priority weighting of drift
- [ ] Cross-device conflict detection (same branch edited on two devices)
- [ ] Trend view: "drift debt" over time as a time-series in reports

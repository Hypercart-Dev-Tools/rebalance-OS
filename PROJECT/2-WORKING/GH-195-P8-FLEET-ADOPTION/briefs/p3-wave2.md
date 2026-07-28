# P3 — Wave 2: adopt pulse and obsidian (six in-repo agents)

Same shape as Wave 1 (`p2-wave1.md` — read it first, especially the "what adopt means"
and Constraints sections; they apply unchanged). This wave is the routine one: six jobs
that all live in this repo, none of which emit GitHub issues, so there is no #139-class
constraint to reason about.

## The six agents, with their REAL current definitions

| id | current argv | schedule |
|---|---|---|
| `pulse-sync` | `scripts/pulse_sync.sh` | hourly on the hour, 06:00–23:00 (18×) |
| `pulse-web-sync` | `scripts/pulse_web_sync.sh` | :08 and :38 hourly, 06:08–23:38 (36×) |
| `pulse-warning-watch` | `.venv/bin/python scripts/pulse_warning_watch.py --url http://127.0.0.1:8767/ --log …` | :07 :22 :37 :52 (4×/hour) |
| `obsidian-daily-sync` | `utils/obsidian_daily_sync.sh` | daily 18:20 |
| `obsidian-rollover` | `utils/obsidian_rollover.sh` | daily 00:40 |
| `stickies2obsidian` | `/bin/bash utils/stickies-to-obsidian/stickies2obsidian.sh` | StartInterval=300 |

Read each full argv off its plist in `~/Library/LaunchAgents` — the table truncates
`pulse-warning-watch`. Note `com.user.stickies2obsidian` is labelled `com.user.*` but its
script lives **inside this repo**, so it belongs in the committed registry, not the
machine-local overlay. That mismatch between label prefix and script location is exactly
the kind of thing to verify rather than assume.

## Things that need a judgement call

- **`pulse-warning-watch` talks to `http://127.0.0.1:8767/`**, which is served by
  `com.rebalance-os.pulse-server` (status `server`, KeepAlive). A watcher whose target is
  a separately-managed server has an ordering dependency the registry cannot express.
  Record how that is handled — at minimum a comment in the TOML — rather than leaving it
  implicit.
- **`pulse-web-sync` runs 36×/day.** Check whether `[breakers] single_instance` is
  appropriate at that cadence, and whether the P6 deferral semantics (exit 3 = another
  instance holds the lock = deferred, not failed) mean a busy machine handles the overlap
  correctly. This is the highest-frequency job in the fleet; if single-instance conflicts
  are routine for it, say so.
- **Memory ceilings.** Which of these embed? `vault-sync` and `daily-sync` do (GH-175
  finding 2). Check whether any Wave 2 job loads a model, and set `max_rss_gb`
  accordingly — the default per-process contract is ≤8 GB (`job_guard`
  `DEFAULT_MAX_FOOTPRINT_FRACTION = 0.125` on 64 GB). Do not set a ceiling you cannot
  justify.

## Definition of done

- Six `jobs.d/*.toml`, each with `supersedes` naming the label it replaces.
- `commands.allow` entries; `python -m three_eyes validate` passes.
- `python -m three_eyes sync-dashboard` regenerated and committed.
- `utils/3-eyes/tests/test_adoption_wave2.py` asserting: commands resolve, `supersedes`
  present, and **schedules match the live plists exactly** (this is the wave where a
  36×/day job makes a transcription slip easy and expensive).
- `.venv/bin/python -m pytest utils/3-eyes/tests -q` green.

## Constraints

- **No `launchctl`. No `three_eyes install`. No writes to `~/Library/LaunchAgents`.**
- Schedules reproduce the live plists exactly — 36 calendar entries stay 36 entries.
- Do not modify Wave 1's files. If you find a Wave 1 defect, report it in your turn.

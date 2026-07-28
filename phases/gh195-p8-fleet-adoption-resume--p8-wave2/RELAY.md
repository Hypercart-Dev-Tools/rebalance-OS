# Marathon Phase p8-wave2
STATUS: Open
NEXT: codex

<!-- marathon-drive: task=MARATHON-P8-WAVE2-TURN builder=codex reviewer=agy round-cap=5 -->

## Phase Brief

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

## Containment: your filenames are FIXED

The relay containment guard matches allowlisted paths by **exact string**, not by
directory prefix. Any file you create outside the exact list below is treated as an
off-lane edit: your entire turn is discarded and fails with exit 6, however good the
work is. This already happened three times on this phase — the work was correct each
time and thrown away each time.

Create/modify **only** these paths:

- `utils/3-eyes/registry/jobs.d/pulse-sync.toml`
- `utils/3-eyes/registry/jobs.d/pulse-web-sync.toml`
- `utils/3-eyes/registry/jobs.d/pulse-warning-watch.toml`
- `utils/3-eyes/registry/jobs.d/obsidian-daily-sync.toml`
- `utils/3-eyes/registry/jobs.d/obsidian-rollover.toml`
- `utils/3-eyes/registry/jobs.d/stickies2obsidian.toml`
- `utils/3-eyes/registry/commands.allow`
- `utils/3-eyes/tests/test_adoption_wave2.py`
- `utils/3-eyes/DASHBOARD.md`

If the work genuinely requires a file that is not on that list, **do not create it**.
Say so in your turn block and hand back — a turn that reports a blocked requirement is
useful; a turn that gets discarded is not.

Also: `.pytest_cache/` and `.coverage` are now gitignored, so running the test suite is
safe. Do not create scratch files, notes, or scripts anywhere in the tree.


---

▶ TAKE YOUR TURN (codex — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): utils/3-eyes/registry/jobs.d/pulse-sync.toml,utils/3-eyes/registry/jobs.d/pulse-web-sync.toml,utils/3-eyes/registry/jobs.d/pulse-warning-watch.toml,utils/3-eyes/registry/jobs.d/obsidian-daily-sync.toml,utils/3-eyes/registry/jobs.d/obsidian-rollover.toml,utils/3-eyes/registry/jobs.d/stickies2obsidian.toml,utils/3-eyes/registry/commands.allow,utils/3-eyes/tests/test_adoption_wave2.py,utils/3-eyes/DASHBOARD.md
2. Append a build block to this relay file: `### Round N · Builder · codex` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick claim MARATHON-P8-WAVE2-TURN --agent codex --paths "phases/gh195-p8-fleet-adoption-resume--p8-wave2/RELAY.md,utils/3-eyes/registry/jobs.d/pulse-sync.toml,utils/3-eyes/registry/jobs.d/pulse-web-sync.toml,utils/3-eyes/registry/jobs.d/pulse-warning-watch.toml,utils/3-eyes/registry/jobs.d/obsidian-daily-sync.toml,utils/3-eyes/registry/jobs.d/obsidian-rollover.toml,utils/3-eyes/registry/jobs.d/stickies2obsidian.toml,utils/3-eyes/registry/commands.allow,utils/3-eyes/tests/test_adoption_wave2.py,utils/3-eyes/DASHBOARD.md"
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick ping MARATHON-P8-WAVE2-TURN --agent codex
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-P8-WAVE2-TURN --agent codex --to agy
4. Edit ONLY these paths: phases/gh195-p8-fleet-adoption-resume--p8-wave2/RELAY.md and utils/3-eyes/registry/jobs.d/pulse-sync.toml,utils/3-eyes/registry/jobs.d/pulse-web-sync.toml,utils/3-eyes/registry/jobs.d/pulse-warning-watch.toml,utils/3-eyes/registry/jobs.d/obsidian-daily-sync.toml,utils/3-eyes/registry/jobs.d/obsidian-rollover.toml,utils/3-eyes/registry/jobs.d/stickies2obsidian.toml,utils/3-eyes/registry/commands.allow,utils/3-eyes/tests/test_adoption_wave2.py,utils/3-eyes/DASHBOARD.md. Do NOT run git. Do NOT touch any other file — the harness commits for you.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: utils/3-eyes/registry/jobs.d/pulse-sync.toml,utils/3-eyes/registry/jobs.d/pulse-web-sync.toml,utils/3-eyes/registry/jobs.d/pulse-warning-watch.toml,utils/3-eyes/registry/jobs.d/obsidian-daily-sync.toml,utils/3-eyes/registry/jobs.d/obsidian-rollover.toml,utils/3-eyes/registry/jobs.d/stickies2obsidian.toml,utils/3-eyes/registry/commands.allow,utils/3-eyes/tests/test_adoption_wave2.py,utils/3-eyes/DASHBOARD.md.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-P8-WAVE2-TURN --agent agy --to codex
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick done MARATHON-P8-WAVE2-TURN --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/gh195-p8-fleet-adoption-resume--p8-wave2/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.

### Round 1 · Builder · codex

Implemented all six committed Wave 2 registry declarations, their fixed command
allowlist entries, the schedule/supersession contract test, and regenerated
`DASHBOARD.md`. The calendar arrays reproduce the 18 pulse-sync and 36
pulse-web-sync plist entries verbatim; the watcher retains its four minute-only
entries and Stickies retains its 300-second interval.

All six jobs use the established 8 GB guard contract. None of their configured
argv loads a local model (the watcher's Ollama path is optional and absent from
the live plist). `pulse-web-sync` keeps `single_instance`; exit 3 is a deferred
outcome under P6 rather than a breaker failure. The watcher TOML documents its
independent `pulse-server` dependency and the absence of an expressible ordering
edge. `stickies2obsidian` is committed because its executable is in-repo despite
the `com.user.*` incumbent label.

Verified with `PYTHONPATH=. python3 -m three_eyes validate`, dashboard
regeneration, and `PYTHONPATH=. python3 -m pytest tests/test_adoption_wave2.py -q`
(2 passed). This worktree has no `.venv`, so the repository's Python 3.14 was
used for these scoped checks.

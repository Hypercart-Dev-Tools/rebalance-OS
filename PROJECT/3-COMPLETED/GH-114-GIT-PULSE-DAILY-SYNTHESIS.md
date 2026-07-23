---
gh_issue: 114
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/114
title: Multi-device Git Pulse daily synthesis → Obsidian vault
status: "Complete — shipped to development (5c763f8, a3c11fa, 826fde5); utils/git_pulse_daily_synthesis.py and the git-pulse-daily-synthesis skill are live. Issue #114 closed 2026-07-22."
created: 2026-07-05
updated: 2026-07-05
owner: Noel
goal: >
  Manual script + Claude Code Skill that pipes `view.sh --today` output (the
  existing multi-device aggregation layer) through Gemini synthesis and writes
  an idempotent sentinel block to the Obsidian vault's "0. Today's Notes.md".
doc_type: project
effort: 2
complexity: 3
risk: 2
phases: 3
---

# GH-114 — Multi-device Git Pulse Daily Synthesis

## Status

| What was just completed | What's next |
|---|---|
| Phase 0 spike completed; Gemini prompt validated and block collision verified. | Phase 1: Script `utils/git_pulse_daily_synthesis.py` |

Actionable substance from [issue #114](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/114).

## What this is NOT

- Not a replacement for `git-pulse-exec-recap` / `git-pulse-team-recap` skills — those fill narrative
  prose into pre-generated recap files. This is an automated daily pipeline.
- Not a replacement for `obsidian_daily_sync.py` (GH-112) — that covers the rebalance DB pulse
  snapshot (GitHub events, issues, PRs, calendar). This covers the **git-commit** view:
  what code was actually written across all devices today, deduplicated by SHA.
- Not a new collector or registered source — this is a **projection/export** stage that reads
  already-synced data from the sibling repo clone, not a raw source. Must not be registered in
  the `all` token or `COLLECTORS`.
- Not a Principle 2 violation — GUIDING-PRINCIPLES.md says "one local store is canonical" (the
  rebalance DB). This script reads git-pulse TSV files, which hold a *distinct* signal: local git
  commits including unpushed work and cross-device activity not yet visible via the GitHub API.
  That data is not in the rebalance DB. Reading it directly is justified; this distinction must
  be stated in the script's module docstring.

## Data layer (already exists — do NOT reimplement)

`experimental/git-pulse/view.sh --today` already handles:
- reading all per-device `pulse-<device>.md` TSV files from `$sync_repo_dir`
- filtering to today's date
- SHA-deduplication across devices
- structured tabular output (machines, repos, daily activity)

The script shells out to `view.sh --today` and feeds its output as the Gemini prompt payload.
No new TSV parser needed.

## Acceptance criteria

- [ ] Script shells out to `experimental/git-pulse/view.sh --today`; no custom TSV parsing
- [ ] Gemini synthesizes a readable narrative from `view.sh` output; skip + log if Gemini
      unavailable (no fallback)
- [ ] Writes idempotent `<!-- Git Pulse Daily Summary Start/End -->` sentinel block to
      `0. Today's Notes.md` (separate from the GH-112 `<!-- AI Daily Summary -->` block;
      appends after that block if present)
- [ ] `--dry-run` prints the block without writing; `--force` bypasses any time guard
- [ ] Claude Code Skill `.claude/skills/git-pulse-daily-synthesis/SKILL.md` invokes the script
- [ ] Config: `view.sh` sources `~/.config/git-pulse/config.sh` automatically; script inherits
      that path via env or by calling `view.sh` directly. `GIT_PULSE_REPO` env var overrides for
      tests/CI. No new `rbos.config` key, no hardcoded paths.
- [ ] If `view.sh --today` returns no rows, block stamps "no git activity found today" rather
      than skipping silently; if `view.sh` exits non-zero (config missing), script skips cleanly

## Phase 0 — Spike (1–2h)

**Discuss:**
- Run `view.sh --today` on this machine; confirm output is non-empty and well-structured
- Confirm Gemini prompt quality using `view.sh --today` output as payload; test ≤3-commit case
- Verify sentinel block does not collide with GH-112 block; confirm both coexist idempotently
- Test zero-row case: `view.sh --today` returns nothing (no commits yet today)
- Test config-missing case: `~/.config/git-pulse/config.sh` absent — confirm clean skip

**Acceptance:**
- `view.sh --today` runs without error and produces structured multi-device output
- Gemini output is readable at low commit counts (≤3 commits today)
- Two separate sentinel blocks coexist idempotently in `0. Today's Notes.md`
- Zero-row case writes "no git activity found today" block rather than silently skipping
- Config-missing case exits 0 with a logged skip (same posture as GH-112 vault-missing guard)

**Spike findings:**
- `view.sh --today` correctly produces well-structured TSV even when there are 0 commits (it outputs a single header row).
- Gemini output is highly readable and formats nicely with <= 3 commits, naturally grouping by repository.
- Sentinel blocks (`<!-- Git Pulse Daily Summary Start/End -->`) will coexist alongside GH-112 (`<!-- AI Daily Summary Start/End -->`) as long as the block markers differ. The upsert logic from `obsidian_daily_sync.py` can be reused with the updated markers.
- If `view.sh` exits non-zero (config missing), it can be cleanly skipped in Python by checking the `subprocess.run` exit code.
- Zero-row case (only headers) can be detected if the output has <= 1 line. We will write the "no git activity found today" string instead of invoking Gemini.
## Phase 1 — Script (`utils/git_pulse_daily_synthesis.py`)

**Discuss:**
- Single-file script mirroring `obsidian_daily_sync.py` structure: `collect()` → `synthesize()` →
  `build_block()` → `upsert_block()` → `run()`
- Data collection: **shell out to `experimental/git-pulse/view.sh --today`** — captures stdout,
  passes to Gemini. No TSV parsing, no dedup logic to own. Principle 6: least code.
- Config: `view.sh` handles its own config sourcing; script just calls it and reads stdout/exit code.
- Staleness guard: if no pulse file updated in last 24h, stamp block with last-known data time
  or skip with a logged warning. Never write a silent empty summary.
- Late-run guard mirrors GH-112 (skip post-midnight); `--force` bypasses
- Block sentinel: `<!-- Git Pulse Daily Summary Start -->` / `<!-- Git Pulse Daily Summary End -->`
- Block ordering: Git Pulse block appends *after* the AI Daily Summary (GH-112) block if present

**Acceptance:**
- [ ] `--dry-run` prints block; `--force` bypasses guard; exit-0 on clean skip
- [ ] Gemini-only; returns `None` and skips if key missing or call fails
- [ ] Sibling repo absent or config not found → skip cleanly (same "vault is optional" posture)
- [ ] Unit tests: today-filter, SHA-dedup, sentinel block build, idempotent upsert, skip paths,
      staleness-stamp behavior

**QA gate:** `pytest tests/test_git_pulse_daily_synthesis.py` green; `rebalance doctor` clean

## Phase 2 — Claude Code Skill

**Discuss:**
- Skill file: `.claude/skills/git-pulse-daily-synthesis/SKILL.md`
- Invocation: reads `$ARGUMENTS` for optional flags (`--force`, `--dry-run`, `--since-days N`)
- Skill resolves script path relative to repo root; uses `.venv/bin/python`

**Acceptance:**
- [ ] `/git-pulse-daily-synthesis` invokes the script with any passed flags
- [ ] `--dry-run` output printed to user; no vault write
- [ ] Skill doc clearly states it complements (does not replace) `git-pulse-exec-recap`

**QA gate:** Manual smoke test via `/git-pulse-daily-synthesis --dry-run`; vault file unchanged

## Phase 3 — Docs + PDDA close

**Discuss:**
- Update `ARCHITECTURE.md` (new script under `utils/`; scope classification: projection/export)
- Update `SCHEDULER.md` if a launchd job is added later (out of scope for now — manual only)
- Move this doc to `PROJECT/3-COMPLETED/`; update ROADMAP.md

**Acceptance:**
- [ ] `ARCHITECTURE.md` reflects new script with correct scope classification
- [ ] CHANGELOG.md entry added
- [ ] `pdda.sh run` clean

**QA gate:** `pdda.sh run` clean; `CHANGELOG.md` updated

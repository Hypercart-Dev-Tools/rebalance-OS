---
gh_issue: 112
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/112
title: Obsidian Vault Daily Activity Sync
status: Active
created: 2026-07-04
updated: 2026-07-04
owner: Noel
goal: >
  Schedule a new consumer of an existing Gemini pipeline to synthesize
  and append a daily activity summary into the Obsidian vault's Today note
  at 6 PM daily, without overwriting manual notes.
depends_on:
  - utils/obsidian_rollover.sh
  - GEMINI-WHATS-NEXT-VAULT
doc_type: project
effort: 2
complexity: 3
risk: 2
phases: 4
---

# Obsidian Vault Daily Activity Sync

## Status

| What was just completed | What's next |
| --- | --- |
| **All phases shipped 2026-07-04** (via [MARATHON-2026-07-04.md](MARATHON-2026-07-04.md)). Phase 0 spike proven; Phases 1-3 built as one sequential session: `utils/obsidian_daily_sync.py` + 15 unit tests green, launchd job `com.rebalance-os.obsidian-daily-sync` (18:00) installed & registered, live idempotent append to real `0. Today's Notes.md` verified, `ARCHITECTURE.md`/`SCHEDULER.md` updated. | Operator: confirm the first unattended 18:00 fire, then archive to `3-COMPLETED`. |

## Table of contents
- [System Design & Constraints](#system-design--constraints)
- [Phases](#phases)

Schedule a new consumer of an existing pipeline to automatically land a Gemini-synthesized daily activity summary into the Obsidian vault.

**New Write Contract:** This requires a new mixed human/agent ownership write contract for `0. Today's Notes.md`. It cannot simply reuse the existing vault publish path, as the existing writer in `next_actions.py` is overwrite-only for generated files.
**Reuses existing work:** This heavily reuses the Gemini synthesis engine infra shipped in the earlier task [GEMINI-WHATS-NEXT-VAULT.md](GEMINI-WHATS-NEXT-VAULT.md); this task targets the current default model `gemini-3.5-flash`.

## System Design & Constraints

### 1. Input Signal
The exact adapter for the input signal must be the **structured `collect_pulse_snapshot()` output** from `src/rebalance/ingest/pulse.py`. Do NOT consume the rendered markdown from `render_pulse_markdown()`, as doing so would cause the prompt shape, tests, and future parity checks to drift.

### 2. Vault Target & Mixed-Ownership Semantics
- **Target Path:** Must be derived dynamically from the existing rollover module (`utils/obsidian_daily_rollover.py`'s `TODAY_FILE`) or shared config. Do NOT hardcode the literal vault path again.
- **Idempotent Block Updates:** Because this is a manual-notes surface, the script MUST append the Gemini summary using an exact generated block marker (e.g., `<!-- AI Daily Summary Start -->` and `<!-- AI Daily Summary End -->`). Reruns must replace the existing block inside these markers rather than appending a second one.
- **Placement Semantics:** The block should be inserted at the **bottom** of the note to preserve the user's reading order of any manual notes jotted down earlier in the day.

### 3. Scheduling & Rollover Interplay
The new job fires at 6 PM daily, but `utils/obsidian_rollover.sh` fires at 00:00 to move "Today" into "Yesterday".
Launchd's catch-up behavior means a Mac asleep at 6 PM will run the job on next wake (which could be 11:55 PM, or the next morning).
- **Explicit Post-Midnight Rule:** If the job runs *after* midnight (i.e., after the rollover job should have fired), it MUST **skip the run entirely**. Do not attempt to append to `0. Yesterday.md` or pollute the new day's `0. Today's Notes.md`.

### 4. Hard-won Constraints
- **TCC (Full Disk Access):** A directly-launched `python3` under launchd is denied `~/Documents`. The new 6 PM job MUST run through a bash wrapper under launchd to inherit Full Disk Access (copying the pattern from `utils/obsidian_rollover.sh`).
- **Fallback behavior:** The existing Gemini pipeline falls back to local Qwen when the Gemini key/model fails. For this vault surface, **skip and log** if Gemini fails; a Qwen-quality summary is not acceptable for the daily vault note.

## Phases

### Phase 0: Spike
- **Discuss:** Validate critical assumptions before committing to the full build.
- **Acceptance:**
  - Prove the `collect_pulse_snapshot()` output has enough high-quality signal at 6 PM.
  - Prove `gemini-3.5-flash` output quality is acceptable for this surface given the snapshot data.
  - Prove the append/update logic correctly preserves surrounding human notes.
- **Verification:** Sandboxed manual test using live pulse data and a mock vault file.

**Phase 0 Spike Findings (2026-07-04):**
- **Pulse Signal Quality:** The `collect_pulse_snapshot()` structured output provides rich signal. Even at zero commits, the PRs and issues closed across repos generate detailed bullet points.
- **Gemini Quality:** `gemini-3.5-flash` synthesized an excellent, casually informative summary. **Crucial parameter:** `thinking_budget=0` and a large `max_tokens` (e.g. 2048) must be passed to `_synthesize_gemini` to prevent reasoning-model truncation.
- **Safe Block Updates:** By enclosing the payload in HTML comment sentinels (`<!-- AI Daily Summary Start -->`), we proved we can confidently append new summaries to the bottom of the file or idempotently replace existing summaries on re-runs without damaging surrounding human markdown.

### Phase 1: Content Synthesis & Vault Target Logic
- **Discuss:** Implement the prompt for the daily activity summary and wire it to the `collect_pulse_snapshot()` signal. Implement the idempotent block-update logic for `0. Today's Notes.md`.
- **Acceptance:** 
  - Synthesis reads the structured pulse snapshot and uses `gemini-3.5-flash`.
  - Replaces existing AI block or appends safely using exact HTML comment sentinels.
  - Aborts/skips cleanly if Gemini fails (no Qwen fallback written to vault).
- **Verification:** Unit tests for idempotency, sentinel matching, and fallback abort.

### Phase 2: Rollover Interplay & Late Run Handling
- **Discuss:** Implement the explicit post-midnight rule to skip late launchd catch-up runs.
- **Acceptance:** If run after midnight, the job gracefully exits with a log message and does NOT write anything.
- **Verification:** Unit test time-shifted executions to verify the skip behavior.

### Phase 3: Launchd Job & Observability
- **Discuss:** Create the bash wrapper and the 6 PM `launchd` plist to ensure TCC Full Disk Access is inherited. Add structured logging and update docs.
- **Acceptance:** 
  - A `.plist` and `.sh` wrapper exist. 
  - The job uses structured logging (via `_log_job` pattern like in `obsidian_daily_rollover.py`).
  - `ARCHITECTURE.md` and scheduler docs are updated.
- **Verification:** Live macOS `launchctl` load, test execution, and log verification.

## Definition of Done
- Unit tests are green (idempotency, time-shifted skipping, fallback aborts).
- Structured `_log_job` logs are correctly emitted on run and failure.
- `ARCHITECTURE.md` and the scheduler doc reflect the new job.
- Manual dry-run successfully tested against a mock vault.
- One successful live run appending to the real `0. Today's Notes.md` at 6 PM.

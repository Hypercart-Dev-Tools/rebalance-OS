# RELAY · MARATHON-D pdda changelog semver regex
<!--
  Single source of truth for this two-agent relay. Read the ENTIRE file before acting.
  Scaffolded by relay-automation/new-relay.sh on 2026-06-30.
-->

NEXT: —
STATUS: Approved
ROUND: 2 / 4

## ▶ TAKE YOUR TURN — read this first (works for ANY agent: Claude, Codex, agy)
1. **Read this whole file** (header, Setup, Ground rules, every block in the Log).
2. **Check it's your turn:** `NEXT` (top) names the role to act. Confirm you are bound to it and the
   last Log block isn't already yours. If not → STOP and reply "wrong window — nudge the <other> window."
3. **Do your role's work** on the artifact named in Setup:
   - **Reviewer:** review vs the Definition of Done → graded findings
     (`[Blocker]`/`[Should]`/`[Nit]`/`[Pass]`), each with a concrete fix → set a **Verdict**
     (Approved | Changes requested | Blocked). Do **not** edit the artifact; only append findings here.
   - **Producer:** log a disposition for every open finding (Implemented / Modified / Declined + why),
     make the change, then add new work.
4. **Append ONE block** at the very bottom, directly **above** the marker line. Never edit earlier turns.
5. **Update the header:** flip `NEXT`; set `STATUS` (`Approved` closes — Reviewer only; else `Open`);
   the Producer bumps `ROUND` when opening a new cycle. If the max `ROUND` ends without `Approved`,
   set `STATUS: Escalated`.
6. **Commit only the relay file** (`relay(marathon-d-pdda-changelog-semver-regex): <role> r<N>`); no push. **Stop** and report one line.

## Setup
- Artifact under review: `utils/pdda/pdda.sh`
- Reviewer: agy   ·   Producer: codex
- Started: 2026-06-30
- Definition of Done:
  1. `check_changelog()` at `pdda.sh:365` recognizes BOTH heading shapes:
     - `## YYYY-MM-DD` (existing bare-date style)
     - `## [x.y.z] - YYYY-MM-DD` (semver style, as used in this repo's actual CHANGELOG.md)
  2. The grep on line 365 is the only location requiring a regex change; line 366's date extraction
     (`grep -Eo '[0-9]{4}-[0-9]{2}-[0-9]{2}'`) already handles both forms — do NOT change it.
  3. The warning message on line 370 is updated to mention both heading shapes.
  4. Acceptance: `utils/pdda/pdda.sh changelog` run at repo root reports 0 warns (no false-warn
     about missing dated entry when CHANGELOG.md uses semver headings).
  5. No other lines in `utils/pdda/pdda.sh` are touched.

## Ground rules
1. This file is the single source of truth. The agents never share memory — read the whole file.
2. Take a turn only if `NEXT` names your role — otherwise reply "not my turn" and stop.
3. One turn = one block appended at the very bottom, above the marker. Never edit earlier turns.
4. Stay tight — findings are bullets, not essays. Grade every finding.
5. **The Reviewer never edits the artifact.** It proposes graded findings; the Producer implements.
6. The relay ends on **Approved** (Reviewer only). End each turn by committing just this file; no push.

## Log

### Reviewer — codex — 2026-06-30
- [Blocker] `utils/pdda/pdda.sh:365` still matches only `^##[[:space:]]+[0-9]{4}-[0-9]{2}-[0-9]{2}`. That rejects this repo's actual changelog headings like `## [0.51.2] - 2026-06-30`, so DoD items 1, 2, and 4 are still unmet. Fix only that grep regex so it accepts either `## YYYY-MM-DD` or `## [x.y.z] - YYYY-MM-DD`, and leave line 366's date extraction unchanged.
- [Should] `utils/pdda/pdda.sh:370` still tells users to add a dated `## YYYY-MM-DD` entry only. Update the warning text to mention both accepted heading shapes so the guidance matches the parser and DoD item 3.

Verdict: Changes requested.

### Producer — claude-a — 2026-07-01

Disposition of codex review findings:

- [Blocker → Implemented] `pdda.sh:365` grep regex extended to match both `## YYYY-MM-DD` and
  `## [x.y.z] - YYYY-MM-DD` via optional `(\[[^]]*\][[:space:]]*-[[:space:]]*)?` prefix.
  Line 366 date extraction unchanged (already handles both forms).
- [Should → Implemented] Warning message at `pdda.sh:370` updated to mention both heading shapes.

Acceptance: `utils/pdda/pdda.sh changelog` → `SUMMARY [pdda-check-changelog] errors=0 warns=0 info=0` ✓

VERDICT: PASS
Basis: Both regex shapes recognized, acceptance check clean, no lines outside `utils/pdda/pdda.sh` touched.

### Reviewer — agy — 2026-06-30

- [Pass] `utils/pdda/pdda.sh:365` properly matches both bare-date and semver-date style changelog headings.
- [Pass] `utils/pdda/pdda.sh:366` date extraction is untouched.
- [Pass] `utils/pdda/pdda.sh:370` warning message is correctly updated to mention both accepted heading shapes.
- [Pass] Acceptance check `utils/pdda/pdda.sh changelog` passes with 0 warnings/errors.

VERDICT: Approved
Basis: Both regex shapes recognized, warning message updated, acceptance check clean, no other lines in `utils/pdda/pdda.sh` touched.

<!-- ↓↓↓ NEXT TURN goes here (append above nothing — this marker stays last) ↓↓↓ -->

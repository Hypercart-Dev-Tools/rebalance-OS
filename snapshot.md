# 📸 Snapshot — 2026-06-09 23:25 (Tue)

**Session:** P2 Team-Calendar Signal — crash recovery, plan restructure, harness rebuilt on dashboard path
**Project / repo:** rebalance-OS (HiQS) — `PROJECT/2-WORKING/P2-TEAM-CALENDAR-SIGNAL.md` + `temp/ab_team_signal.py`
**Phase:** Phase 0 (Spike + A/B test) — harness complete & dashboard-matched; gate thresholds set
**Status:** All committed and pushed to `development`. Harness rebuilt; only blinding + 5-day completed-day capture + two-judge scoring remain before the gate.

## Git state
- **Branch:** development
- **HEAD:** `269101e` — docs(project): P2 Phase 0 — harness rebuilt on dashboard path, gate thresholds set
- **Working tree:** clean
- **Ahead/behind remote:** in sync with `origin/development`

## Recent findings
- **Crash recovery:** nothing was lost. The crashed session was `dbd2284a….jsonl`; all spike files survived on disk (the `temp/` scripts + the plan doc) and the DB still holds Matt's 122 calendar events alongside 584 `primary`.
- **GitHub mismatch ROOT-CAUSED & FIXED:** the old harness read `github_activity`, a *scan-snapshot* table where `scan_date = scanned_at[:10]` (the **scan-run date, in UTC**) bucketing a rolling ~30-day fetch with bot repos included. The dashboard reads granular `github_commits/items/comments` via `pulse._query_day_activity()` (tz-aware day window + author/bot filter). Harness rebuilt on that function → now matches the dashboard.
- **Git Pulse Sync excluded:** `rebalance-git-pulse` never even reaches `github_commits` (only lived in the snapshot table); added an explicit `NOISE_REPOS` guard anyway.
- **Arm A completed:** Obsidian vault notes + Sleuth reminders (same assembler) + email (per-day `email_messages` query) now in Arm A. Caveat: "vault todos" = recently-modified notes; no checkbox/task table exists.
- **Validation:** re-ran 06-08/09/10. 06-08 full, 06-09 (today) partial, **06-10 (tomorrow) correctly calendar-only** — proves tz windowing and exposed the old "06-10" GitHub rows as a UTC scan-date artifact. → Consequence: generate each day's bundle *after the day completes*.
- **Gate thresholds set** (Noel delegated): conjunctive 3-metric rule — additivity ≥20% (median day) · ≥1 confirmed dropped-ball catch with B-only precision ≥50% · B preferred ≥3/5 days by **both** judges (Noel + LLM) independently. Honest that N≈5 ≠ significance.
- **Doctor:** passed with 2 pre-existing infra warnings (stale collector on MBP 16" M1 Pro; `pulse-server` last exited SIGTERM/-15 — likely the same VS Code crash). Neither blocks.
- Two commits pushed this session: `49428ed` (restructure + capture) → `269101e` (rebuild + thresholds).

## Next steps
1. **Blind the harness output** — relabel ARM A/B → "Option 1 / Option 2" in randomized order (last open 0b item) so judging is unbiased.
2. Generate one bundle **per completed day** across ~5 days (past days only — activity arms are empty for today/future).
3. Run the **blinded two-judge scoring** (Noel + LLM) against the [0e](PROJECT/2-WORKING/P2-TEAM-CALENDAR-SIGNAL.md) gate; append the findings table + go/no-go to the Phase 0 progress log.

## Last response (verbatim)

Both commits are pushed to `development` (`49428ed` → `269101e`). Here's where the four items landed:

| Item | Outcome |
|---|---|
| **1. Exclude Git Pulse Sync** | Done — and it turned out `rebalance-git-pulse` never even reaches `github_commits` (the dashboard's source); it only lived in the coarse `github_activity` snapshot. Added an explicit `NOISE_REPOS` guard anyway. |
| **2. GitHub mismatch** | **Root-caused and fixed.** The harness was reading `github_activity`, where `scan_date = scanned_at[:10]` — the *scan-run date in UTC*, bucketing a rolling ~30-day fetch with bot repos baked in. Rebuilt Arm A on `pulse._query_day_activity()` (the dashboard's own per-day assembler over `github_commits/items/comments`, author/bot-filtered). It now matches your dashboard. |
| **3. Add vault / Sleuth / email** | Done. Vault notes + Sleuth reminders come from the same assembler; email via a per-day `email_messages` query. One honesty caveat folded into the doc: "vault todos" = recently-*modified* notes — there's no checkbox/task table, so true todo parsing is a separate future enhancement. |
| **4. Gate thresholds (delegated)** | Set in [0e](PROJECT/2-WORKING/P2-TEAM-CALENDAR-SIGNAL.md) + the locked decision table: a conjunctive 3-metric rule (additivity ≥20% · ≥1 confirmed catch with B-only precision ≥50% · B preferred ≥3/5 days by *both* judges independently), explicitly honest that N≈5 isn't significance. The stale "Open decisions" section was already deleted last turn. |

**A genuinely useful finding surfaced during validation:** today is 2026-06-09, so **06-10 is tomorrow** — and the corrected harness shows it as *calendar-only* (no commits/vault/Sleuth yet), which is correct. The old "06-10" GitHub numbers were a UTC scan-date artifact. The practical consequence, now noted in the gate: **generate each day's bundle after the day completes**, or the activity arms are empty.

**What's left for the gate** (all tracked in the doc):
1. Blind/randomize the output (relabel ARM A/B → "Option 1/2") — the last open 0b item.
2. Generate ~5 *completed*-day bundles.
3. Run the two-judge (you + LLM) blinded scoring against the 0e gate.

Want me to knock out the blinding next so the harness is judging-ready?

---

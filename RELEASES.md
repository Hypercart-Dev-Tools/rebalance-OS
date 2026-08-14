# Major Releases

Forward-looking planning ledger for major releases — one block per release, minimal fields, blank
line between blocks. Marathon plans and other forward planning cross-reference this doc for
target release names/dates; it is not a history of what shipped (that's CHANGELOG.md — lessons
learned belong there at ship time, not duplicated here). Contract lives in PROJECT/PDDA.md ->
"RELEASES.md — release ledger". Add new fields only when a real need shows up.

Release: 0.69.0
Iterations: 0.69.0-0.69.9
Status: Draft
Target Date: 2026-08-15
Codename: Reclaim
Milestone:
Description: The store tells the truth about its own size — finish GH-250 end to end: observe the writer fix holding across three sync cycles (R1), execute the ~10.2 GiB reclaim behind the runbook (R4), backfill and re-embed what the leak destroyed (R5), and land with doctor's two orphan invariants reporting OK against real data instead of FAIL.
GH_URL:
Front-door reviewed:
Shakedown reviewed:
License file: Yes

Release: 0.70.0
Iterations: 0.70.0-0.70.9
Status: Draft
Target Date: 2026-09-15
Codename: Green Board
Milestone:
Description: A red build means new breakage — empty the GH-178 quarantine (10 real commit-threshold auto-promotion defects, not flakes), fix the working-directory dependence in GH-255, repair the 5 utils/3-eyes CI failures, and end on a development branch whose green run is worth believing.
GH_URL:
Front-door reviewed:
Shakedown reviewed:
License file: Yes

Release: 0.71.0
Iterations: 0.71.0-0.71.9
Status: Draft
Target Date: 2026-10-15
Codename: Daily Driver
Milestone:
Description: The consolidation stops being an argument about code shape and becomes an observed footprint — run rebalance as the daily driver on the 64 GB Mac Studio for one 7-day window. Four exit criteria, each measurable by a named instrument: (1) MLX allocation stays under the GH-217 cap (0.35 x installed RAM, ~22 GB), read from the per-batch active/cache/peak instrumentation GH-216 adds — GH-216 is therefore a hard prerequisite, since that number is unobserved today; (2) no rebalance process — collector or embedder — exceeds 32 GB `phys_footprint`, i.e. half installed RAM, the same constant GH-213 already uses for its swap threshold; this is the regression gate on the ~46 GB spikes in GH-209 (daily-sync/github-sync) and 46.9 GB in GH-215 (rebalance-embed), read from `ps`/`footprint`, needing no new tooling. Note these are two different quantities: GH-217 caps what MLX may allocate, not total process footprint, and conflating them would fail the gate spuriously; (3) zero `database is locked` (GH-222) across the window; (4) `rebalance doctor` reports OK on every day of it. Reset rule: only an in-scope rebalance defect restarts the clock — an unrelated environmental flake does not, or the gate measures luck instead of stability. "The code looks smaller" never substitutes. This is where GH-266 gets to be finished instead of merely tidier.
GH_URL: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/266
Front-door reviewed:
Shakedown reviewed:
License file: Yes

Release: 0.72.0
Iterations: 0.72.0-0.72.9
Status: Draft
Target Date: 2026-11-15
Codename: Punch List
Milestone:
Description: Refinement bounded by what dogfooding actually found, and by nothing else. The defect list is whatever the 0.71.0 window produced, frozen the day that window closes; anything opened after the freeze goes to ROADMAP.md, not here. Exit: every frozen item closed or explicitly deferred with a written reason, then a second 7-day window on the same device with no new defect of a class already fixed. If the frozen list comes back empty, this release is skipped rather than filled — an empty punch list is the success case, not a gap to backfill.
GH_URL:
Front-door reviewed:
Shakedown reviewed:
License file: Yes

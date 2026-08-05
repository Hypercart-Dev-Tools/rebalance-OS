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
License file: No

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
License file: No

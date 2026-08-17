# Major Releases

Forward-looking planning ledger for major releases — one block per release, minimal fields, blank
line between blocks. Marathon plans and other forward planning cross-reference this doc for
target release names/dates; it is not a history of what shipped (that's CHANGELOG.md — lessons
learned belong there at ship time, not duplicated here). Contract lives in PROJECT/PDDA.md ->
"RELEASES.md — release ledger". Add new fields only when a real need shows up.

`Description:` opens with **one sentence of plain prose** naming the arc, then the manifest of GH
issues the release closes. The prose is not decoration: under the public repo's fresh single-commit
history there is no issue tracker to resolve the numbers against, so a bare manifest reads as
pointers to nothing. `Exit:` is the one observable that decides whether it shipped. Both stay on a
single line. Issue state verified 2026-08-14.

> **`#nnn` and `GH-nnn` refer to this project's internal issue tracker.** They are retained as
> historical labels, not links — in the public repository they do not resolve to anything, and that
> is expected. The prose in each `Description:` carries the meaning on its own.

Release: 0.69.0
Iterations: 0.69.0-0.69.9
Status: Shipped 2026-08-14
Target Date: 2026-08-15
Codename: Reclaim
Milestone:
Description: Reclaimed the ~11 GB the vector store had leaked to orphaned embeddings, then re-embedded what was missing. #250 vector bloat — reclaim + backfill + re-embed. Root cause already fixed in PR #249.
Exit: MET 2026-08-14 — doctor reports OK on both orphan-vector invariants (0 github, 0 semantic); store 14.62 GB -> 3.81 GB, live vectors 32,908 unchanged. R1 waived by the operator for wall clock, recorded in the runbook. #250 stays open pending issue closure (api.github.com was unreachable).
GH_URL: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/250
Front-door reviewed:
Shakedown reviewed:
License file: Yes

Release: 0.70.0
Iterations: 0.70.0-0.70.9
Status: Draft
Target Date: 2026-09-15
Codename: Green Board
Milestone:
Description: The first release a stranger can clone and succeed with — published to a new public repository under its own organization, with install, onboarding and secret-scanning proven rather than assumed. #276 release-gate tracker (front-door, shakedown, TruffleHog), #275 README Step 1 hardcodes a Homebrew interpreter (RC blocker), #273 date parsing has two canonical hubs, #242 CLIO suites report a vacuous dual-interpreter pass, #255 working-directory-dependent tests. Scope QA'd by cross-model relay 2026-08-15 (Approved r5); #178 and #225 verified stale and closeable, 3-Eyes excluded by operator decision as diagnostics rather than core.
Exit: A clean clone on a machine that has never run rebalance completes the documented README Getting Started path end to end — install, onboarding, first pulse — with no undocumented step, and `rebalance doctor` then reports no FAIL. Verified on one Apple Silicon host — macOS-first launch by operator decision 2026-08-15; Linux/Windows are documented as work in progress rather than gated, after a Docker pre-flight showed stock Ubuntu images ship no `python3` at all and 22.04 cannot reach the 3.12 floor from its own archive. `/front-door`, `/shakedown` and a full-history TruffleHog scan are gates tracked in #276, evidence retained.
GH_URL: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/275
Front-door reviewed:
Shakedown reviewed:
License file: Yes

Release: 0.71.0
Iterations: 0.71.0-0.71.9
Status: Draft
Target Date: 2026-10-15
Codename: Subtraction
Milestone:
Description: Deletes rather than adds — removes surfaces, renderers and models the product no longer earns, measured as net negative lines. #271 subtraction pass (C1-C8) — absorbs the open GH-266 Phase 4 remnants (stale MCP docs, weakened assertion, TF-IDF keyset pagination). Run as a marathon; plan and per-lane contracts in PROJECT/2-WORKING/GH-271-SUBTRACTION/.
Exit: net LOC <= -2,000 measured; zero local generation models in the ask path; renderers <= 2; launchd jobs <= 9; search surfaces = 2; tests/test_surface_budgets.py green and pinning the post-subtraction counts.
GH_URL: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/271
Front-door reviewed:
Shakedown reviewed:
License file: Yes

Release: 0.72.0
Iterations: 0.72.0-0.72.9
Status: Draft
Target Date: 2026-11-15
Codename: Daily Driver
Milestone:
Description: Proves the product survives a week of real daily use on one machine without intervention; no new features, only evidence. Proof, not new work — consolidates the former 0.71.0 Daily Driver and 0.72.0 Punch List into one milestone. Prerequisites: #216 MLX instrumentation, #217 MLX memory cap. Regression gates only: #209, #210, #213, #215, #222 (closed).
Exit: one 7-day daily-driver window on the 64 GB Mac Studio — MLX allocation under the #217 cap (0.35 x RAM, ~22 GB) read from #216 instrumentation; no rebalance process over 32 GB phys_footprint; zero `database is locked`; doctor OK daily. In-scope defects reset the clock, environmental flakes do not. Defects the window finds are fixed here, scope frozen the day it closes; anything later goes to ROADMAP.md.
GH_URL: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/266
Front-door reviewed:
Shakedown reviewed:
License file: Yes

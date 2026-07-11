**NO FIRSTHAND VERIFICATION CITED** — treat conclusions as conditional (codex's answer carries an unsupported [Pass]/verified/confirmed-style claim with no quoted span or file:line citation nearby, despite the consult PREAMBLE asking advisors to cite evidence.)

> **ATTESTATION**
> Model: gpt-5.4
> Provider: openai
> Sandbox: read-only

Reading additional input from stdin...
OpenAI Codex v0.142.5
--------
workdir: /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
model: gpt-5.4
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019f5224-953f-7bf2-9a2a-ab50a712d9b4
--------
user
You are an INDEPENDENT advisor in a one-shot cross-model consult. Another model is answering the SAME question separately and a coordinator will reconcile both answers, so give your own honest, specific read — do not hedge toward a consensus you cannot see. Read any repo files the question references (cite file:line). Respond with: (1) a short direct ANSWER; (2) graded FINDINGS — [Blocker]/[Should]/[Nit]/[Pass] — where applicable; (3) a one-line RECOMMENDATION. You are ADVISORY ONLY: output your analysis as text; do not rely on writing files (you are running in a throwaway copy).

=== CONSULT QUESTION ===
## QA pass: GH-124 commit-threshold auto-promotion (Phases 1-3, already merged to `development`)

Repo: rebalance-OS. This feature just shipped across three commits on `development`:
- `51a8eae` — Phase 1: `src/rebalance/ingest/project_inference.py` (`sync_commit_threshold_promotions`,
  `_count_operator_commits`, `_repo_to_promoted_row`, `AutoPromoteSummary`, the generalized
  `_is_inference_owned`), config keys in `src/rebalance/ingest/config.py` (`get_auto_promote_config`),
  tests in `tests/test_auto_promote.py`.
- `7d77a51` — Phase 2: `src/rebalance/ingest/auth_log.py` (`log_project_auto_promoted`),
  `src/rebalance/web.py` (`_EVENT_BADGE`/`_SOURCE_BADGE` entries), `scripts/dashboard.py`
  (`fetch_recent_auto_promotion`), `scripts/pulse_web.py` (`render_repo_pie` banner), tests in
  `tests/test_repo_pie_auto_promote.py` and `tests/test_web_auth_log.py`.
- `5a88338` — Phase 3: wiring into `_refresh_github()` in `src/rebalance/ingest/index_ops.py`
  (immediately after the watchlist coverage guard), doc updates (`ARCHITECTURE.md`, `AGENTS.md`,
  `CHANGELOG.md`), `pytest` added as a real dev dependency in `pyproject.toml`, wiring test in
  `tests/test_index_ops.py`.

The full plan and design rationale is in `PROJECT/2-WORKING/GH-124-AUTO-PROMOTE-WATCHED.md` — read it
first for context (the counting contract, identity-resolution rule, provenance markers, suppression
precedence). The plan was itself Codex-reviewed to approval via a 3-round relay before this was built.

**Known live incident (already resolved, described in the plan doc's Phase 3 QA gate):** this
machine's real hourly `com.rebalance-os.github-sync` launchd job picked up the in-flight commits and
executed the feature for real against production data mid-build, auto-promoting 8 real repos. The
operator reviewed and kept them. This is disclosed context, not something to re-flag as a finding
unless you spot a *code* reason it could misfire again in a way not already covered.

## What we need from you

An adversarial correctness pass — assume the plan's design is sound (it was already reviewed) and
instead hunt for **implementation bugs**: places where the code doesn't actually do what the plan/tests
claim, edge cases the tests don't cover, or a real risk in a feature that writes to the operator's
project registry automatically and unattended.

Specifically look hard at:
1. **The commit-counting query** (`_count_operator_commits` in `project_inference.py`) — SQL
   correctness, the `_author_filter_sql`/`CLOUD_AGENT_AUTHORS` reuse from `pulse.py`, and whether
   `COUNT(DISTINCT sha)` actually gives the intended "cumulative all-time, not per-window" semantics
   given how `github_commits` gets populated/pruned elsewhere in the codebase.
2. **The write path** — does `_repo_to_promoted_row` + `_partition_writable_rows` + `sync_db` actually
   guarantee a curated row is never touched, and is the generalized `_is_inference_owned()` correct
   (does it now also affect `_delete_stale_inferred_rows`'s deletion logic for the OTHER marker in a
   way that wasn't intended)?
3. **The `_refresh_github` wiring** — ordering, error handling (is the try/except actually fail-soft
   the way `watchlist_guard`'s is, or could it mask a real error silently), and whether `auto_promote`
   being folded into the return dict could break any existing consumer of that dict's shape.
4. **Anything that could cause an unwanted repeat promotion, a wrong project name collision, or silent
   data loss** given this writes to a real registry unattended on every github refresh from now on.

## Format

Grade every finding `[Blocker]` / `[Should]` / `[Nit]` / `[Pass]`, each with a `file:line` citation.
Do not edit anything — advisory only.
codex
I’m reviewing the plan doc first, then the implementation and tests around the counting query, write path, and `_refresh_github` wiring so I can check code against the stated contract rather than the commit messages.
exec
/bin/zsh -lc "nl -ba PROJECT/2-WORKING/GH-124-AUTO-PROMOTE-WATCHED.md | sed -n '1,260p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
     1	---
     2	gh_issue: 124
     3	source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/124
     4	title: Auto-promote watched repos to active projects
     5	status: "Active (2-WORKING)"
     6	owner: Noel
     7	created: 2026-07-10
     8	updated: 2026-07-10
     9	doc_type: project
    10	goal: >
    11	  A repo the operator has actually committed to should become a confirmed active project
    12	  automatically after a small commit threshold, with no manual "promote" step — surfaced
    13	  non-silently (auth-log alert + repo-pie top item), never overwriting curated registry state.
    14	related:
    15	  - PROJECT/4-MISC/DECOUPLE-OBSIDIAN-AS-SOT.md
    16	  - PROJECT/3-COMPLETED/CLIENT-AUTO-DISCOVERY.md
    17	  - PROJECT/3-COMPLETED/WATCHLIST-COVERAGE-GUARD.md
    18	  - PROJECT/2-WORKING/REPO-HEALTH-AXES.md
    19	  - PROJECT/3-COMPLETED/GH-81-FOCUS5-RANK-VECTOR.md
    20	effort: 3
    21	complexity: 3
    22	risk: 2
    23	phases: 3
    24	---
    25	
    26	# GH-124 — Auto-promote watched repos to active projects
    27	
    28	## Status
    29	
    30	| What was just completed | What's next |
    31	|---|---|
    32	| **Phase 3 shipped — feature complete.** Wired into `_refresh_github()`; `ARCHITECTURE.md`/`AGENTS.md`/`CHANGELOG.md` updated; `pytest` added as a real dev dependency (was silently missing, causing a real auth-log pollution incident this phase — see QA gate). **Confirmed live in production**, not just tests: the real hourly github-sync job auto-promoted 8 real repos mid-build; operator reviewed and kept them. | Cross-model QA pass (consult: Agy + Codex), then final PDDA sweep. |
    33	
    34	## Table of contents
    35	
    36	- [Problem](#problem)
    37	- [What already exists](#what-already-exists)
    38	- [Non-goals](#non-goals)
    39	- [Design decisions (Discuss)](#design-decisions-discuss)
    40	- [Phase 1 — Detection & write path](#phase-1--detection--write-path)
    41	- [Phase 2 — Non-silent surfacing](#phase-2--non-silent-surfacing)
    42	- [Phase 3 — Wiring, config, docs](#phase-3--wiring-config-docs)
    43	- [Open questions](#open-questions)
    44	
    45	## Problem
    46	
    47	Most users will not remember to manually register new repos into Rebalance. A new repo should
    48	become an active project automatically once the owner/operator has pushed 2-3 commits to it — no
    49	manual "promote" step required. Today the only write path into `project_registry` is the onboarding
    50	`/welcome` flow's one-time human-gated "Review & promote" step (`confirm_projects()`,
    51	`write_semantics="confirmation_gated"` per `src/rebalance/ingest/lifecycle.py:110-120`). Anything
    52	discovered after onboarding sits in the "watched" bucket (`list_watched_repos()`) indefinitely.
    53	
    54	**Exception:** forks/stars alone are not activity and must not trigger promotion — only actual
    55	commits pushed by the operator (fork included) count toward the threshold.
    56	
    57	**Not silent:** confirmed in-thread with the operator — promotion must surface via (1) a Rebalance
    58	Log Alert on the web app, and (2) a top item on the repo-activity donut ("Circular Repo graph").
    59	
    60	## What already exists
    61	
    62	- `src/rebalance/ingest/project_inference.py` — `infer_project_registry()` / `sync_inferred_project_registry()`
    63	  already write `machine_owned` rows into `project_registry`, partitioned so curated rows are never
    64	  clobbered (`_partition_writable_rows`). CLI-only (`rebalance ingest infer-project-registry`), not
    65	  wired into `refresh_index()`, no MCP tool. Trigger is "any GitHub activity or ≥2 calendar events" —
    66	  not a commit count, not operator-identity-scoped.
    67	- `PROJECT/4-MISC/DECOUPLE-OBSIDIAN-AS-SOT.md` (2026-05-31, still "In Review") — prior attempt at the
    68	  same problem ("every repo you push to is visible by default"); never closed.
    69	- `PROJECT/3-COMPLETED/CLIENT-AUTO-DISCOVERY.md` (#100) — adjacent (client labeling on already-
    70	  confirmed projects), not repo→project promotion.
    71	- `PROJECT/3-COMPLETED/WATCHLIST-COVERAGE-GUARD.md` (#82) — the inverse alarm (silent removal from
    72	  watched); the `auth_log.log_event` + `_EVENT_BADGE` pattern it uses is the reuse target for Phase 2.
    73	- `PROJECT/2-WORKING/REPO-HEALTH-AXES.md` — open, unresolved question on watched-vs-registry
    74	  filtering.
    75	- `PROJECT/3-COMPLETED/GH-81-FOCUS5-RANK-VECTOR.md` — **cautionary precedent.** GH-81 found that
    76	  filtering by GitHub-author *email* silently drops repos when a different device/email pushed the
    77	  commit, and fixed it by ranking on local-commit reflog recency instead. Any "operator pushed N
    78	  commits" check in this feature risks the exact same failure mode if it keys strictly on author
    79	  email; see [Phase 1 Discuss](#phase-1--detection--write-path).
    80	
    81	## Non-goals
    82	
    83	- No change to the onboarding `/welcome` "Review & promote" flow — this is a parallel, later-arriving
    84	  path, not a replacement.
    85	- No UI for reviewing/undoing an auto-promotion in this plan (an operator can still hand-edit or
    86	  `github_ignored_repos` a mistaken promotion; a dedicated undo affordance is a follow-up if it proves
    87	  needed).
    88	- No change to `infer_project_registry`'s existing activity/calendar trigger — this adds a second,
    89	  commit-count-gated trigger alongside it, not a replacement.
    90	
    91	## Design decisions (Discuss)
    92	
    93	- Reuse the existing `machine_owned` write semantics (`project_inference.py`) rather than inventing a
    94	  second registry-write contract — one write-ownership model, not two. **Why:** `lifecycle.py`
    95	  already documents `machine_owned` as never clobbering curated rows; a second contract would
    96	  duplicate that guarantee and risk drifting from it.
    97	- Gate on commit *count*, not raw activity/calendar signal — a repo with one drive-by commit should
    98	  not out-rank a repo with zero. **Why:** matches the literal ask ("2-3 commits"), and is a clearer,
    99	  more explainable signal to surface in an alert than a fuzzy activity score.
   100	- Non-silent by default (auth-log + repo-pie), never a hard block — matches this repo's flag-don't-
   101	  block calibration principle used throughout PDDA and `WATCHLIST-COVERAGE-GUARD`.
   102	
   103	## Phase 1 — Detection & write path
   104	
   105	**Discuss:**
   106	- **Inline identity-resolution contract** (self-contained). **Build-time refinement (superseding the
   107	  Codex-approved GH-81-ladder draft):** the primary signal is simpler and more grounded than reusing
   108	  GH-81's local-reflog ladder — `github_commits.author_login` (GitHub's own resolved identity per
   109	  commit, populated for every synced repo regardless of local clone presence) matched against
   110	  `github_login` via the exact `_author_filter_sql()` + `CLOUD_AGENT_AUTHORS` primitive already used by
   111	  `pulse.py:56-59` for "commits authored by me." Reusing it (not reinventing a second identity filter)
   112	  also means cloud-agent-authored commits (Claude Code / Codex cloud sessions acting on the operator's
   113	  behalf — the same bots `pulse.py` already counts as "mine") correctly count toward promotion. A
   114	  commit only counts when `_author_filter_sql("author_login")` matches; GH-81's local-reflog signal
   115	  (`focus5_repo_signals.my_local_commit_ts`) is **not required** — most watched repos have no local
   116	  clone under `focus5_scan_roots` at all, so gating on it would starve the common case. (GH-81's third
   117	  rung, `any_commit`, is irrelevant here — it was a ranking-only fallback, never an identity match.)
   118	- Commit threshold and default on/off are config, not a hardcoded constant, following the
   119	  `git_pulse_clio_enabled` naming precedent in `src/rebalance/ingest/config.py`.
   120	- Out of scope for this phase: the alert/dashboard surfacing (Phase 2) and scheduling wiring
   121	  (Phase 3) — this phase only proves the write path fires correctly on a synthetic commit-count
   122	  fixture.
   123	
   124	**Acceptance criteria (Definition of Done):**
   125	- A watched, non-ignored repo with ≥3 distinct-SHA operator commits (all-time, not a rolling window)
   126	  and zero prior `project_registry` row (curated or machine-owned) gets exactly one machine-owned row
   127	  written on the next eligible refresh — deterministically, so two runs against the same DB state
   128	  produce the same outcome.
   129	- A repo in `github_ignored_repos` never promotes, full stop, regardless of commit count.
   130	- A curated row is never created, updated, or deleted by this path (reuses the existing
   131	  `_partition_writable_rows` guarantee).
   132	- Re-running against unchanged state does not duplicate or re-promote a row that already exists.
   133	
   134	Work:
   135	- Add `auto_promote_enabled` (bool, default `true`) and `auto_promote_commit_threshold` (int, default
   136	  `3`) to `src/rebalance/ingest/config.py`, alongside the existing config accessor pattern.
   137	- **Counting contract:** count *distinct full-SHA* commits (not short-SHA — see the canonical-identity
   138	  lesson in `PROJECT/1-INBOX/P1-SQLITE.md:147`, which explicitly warns short SHAs collide across a
   139	  repo's history) authored by the operator identity, **cumulative all-time** for that repo, not a
   140	  rolling window — this is "has the operator meaningfully started this repo," not a recency signal
   141	  (recency is `list_watched_repos`' job already).
   142	- **Identity resolution:** apply `pulse._author_filter_sql("author_login")` against `github_commits`,
   143	  matching `github_login` and `CLOUD_AGENT_AUTHORS` (import/reuse from `pulse.py`, do not duplicate).
   144	- **Row shape / provenance contract:** reuse `_seed_to_project_row`'s exact shape
   145	  (`src/rebalance/ingest/project_inference.py:610-655`) — `status="active"`, `repos=[repo_full_name]`,
   146	  `tags=["auto-promoted", "source:github"]`, `custom_fields.provenance="auto_promoted"`,
   147	  `custom_fields.inference={"generated_by": "commit_threshold_v1", "commit_count": N,
   148	  "threshold": auto_promote_commit_threshold, "promoted_at": <iso ts>}`. Generalize
   149	  `_is_inference_owned()` (`project_inference.py:65-71`) to recognize **both**
   150	  `INFERENCE_GENERATED_BY` and `"commit_threshold_v1"` as machine-owned, so the existing
   151	  curated-collision-skip and stale-row-cleanup logic apply uniformly to auto-promoted rows without a
   152	  parallel implementation.
   153	- **Suppression precedence (durable vs. not):** `github_ignored_repos` is the only durable suppression
   154	  — checked at eval time, always wins. A manually **deleted** machine-owned row is explicitly **not**
   155	  durable suppression: like existing inferred rows (`_delete_stale_inferred_rows`), an auto-promoted
   156	  row is recreated on the next pass if the repo still qualifies. An operator who wants a promotion to
   157	  stick as removed must add the repo to `github_ignored_repos`, not just delete the row — document this
   158	  plainly in the config comment and `ARCHITECTURE.md` so it isn't a surprise.
   159	- New function in `project_inference.py` (or a sibling module if the identity-resolution logic grows
   160	  large): resolve per-repo operator commit counts, filter to repos at/above threshold that are watched
   161	  but **not yet** in `project_registry` (curated or machine-owned), and exclude forks/repos with zero
   162	  operator-authored commits (starring/forking alone is not a commit).
   163	- Write via the existing `machine_owned` partition/write path — no new registry write contract.
   164	
   165	**Phase 1 QA gate:**
   166	- [x] Unit tests: threshold hit / no-hit, fork-with-no-commits excluded, cloud-agent commits counted,
   167	  `github_ignored_repos` excluded, curated row never touched, idempotent re-run, disabled-config no-op,
   168	  no-`github_login` no-op — `tests/test_auto_promote.py`, 9/9 passing.
   169	- [x] `pytest tests/` green (run via `python -m unittest discover`, pytest not installed in this venv).
   170	- [x] `rebalance doctor` clean.
   171	- **Verification summary:** `python -m unittest tests.test_auto_promote` → 9/9 passed. Full suite
   172	  (`python -m unittest discover -s tests`) → identical 16 pre-existing failures with and without this
   173	  change (verified by diffing failing-test names before/after via `git stash`) — zero regressions.
   174	  `rebalance doctor` → "Health check passed with warnings" (all warnings pre-existing/environmental:
   175	  Sleuth publisher staleness, Figma no file keys, Gmail OAuth scope, stale pulse collector, launchd
   176	  exit codes — none related to this change). Unmet: none.
   177	
   178	## Phase 2 — Non-silent surfacing
   179	
   180	**Discuss:**
   181	- Reuse `auth_log.log_event(source, event, detail)` (`src/rebalance/ingest/auth_log.py:129`) +
   182	  `_EVENT_BADGE` (`src/rebalance/web.py:200`) exactly as `WATCHLIST-COVERAGE-GUARD` did for
   183	  `watched_repos_reduced` — one more badge-mapped event, not a new alert subsystem.
   184	- The repo-pie donut is `render_repo_pie()` in `scripts/pulse_web.py:884`, backed by a
   185	  `#repo-pie-data` JSON payload consumed by Chart.js (`initRepoPie()` around line 2513). The "top
   186	  item" annotation is a new field on that payload (e.g. `newly_added: {repo, promoted_at}`), rendered
   187	  as a banner line in the card header — matching the "New repo added: CLIO" callout already mocked in
   188	  the operator's screenshot.
   189	- Out of scope: redesigning the chart itself or adding new chart types — this is one additive
   190	  annotation on an existing card.
   191	
   192	Work:
   193	- Add `project_auto_promoted` to `_EVENT_BADGE` (info/ok-styled badge, e.g. `"✓ project auto-added"`).
   194	- Call `auth_log.log_event("registry", "project_auto_promoted", {"repo": ..., "commit_count": ...,
   195	  "threshold": ...})` at the point Phase 1's write path fires.
   196	- Extend `render_repo_pie()`'s payload with the most-recent auto-promotion inside the display window
   197	  (if any) and render a header banner line, styled like the operator's screenshot mock.
   198	
   199	**Phase 2 QA gate:**
   200	- [x] Render test asserting the `project_auto_promoted` badge renders on `/auth-log`
   201	  (`tests/test_web_auth_log.py::test_project_auto_promoted_renders_ok_badge`, calls the real
   202	  `auth_log_page()` route function).
   203	- [x] Render/unit test asserting the repo-pie banner appears when a fresh promotion exists in-window,
   204	  and is absent otherwise (`tests/test_repo_pie_auto_promote.py`, 3 tests).
   205	- [x] `pytest tests/` green.
   206	- [x] `rebalance doctor` clean.
   207	- [x] Operator litmus (markup-level, not visual — see note): copied the production DB to a scratch
   208	  path, seeded a synthetic `commit_threshold_v1` row, ran the real `scripts/pulse_web.py` page
   209	  generator against it, and grepped the output for the badge — confirmed `New repo added:
   210	  litmus-demo-repo` rendered with the correct CSS class in the real full-page HTML (not just the
   211	  isolated unit test). Scratch DB/HTML deleted after.
   212	- **Verification summary:** `python -m unittest tests.test_repo_pie_auto_promote
   213	  tests.test_web_auth_log` → 6/6 passed. Full suite → identical 16 pre-existing failures (zero
   214	  regressions, verified by diff). `rebalance doctor` → clean, no ERROR/FAIL lines. **Unmet: no visual
   215	  browser screenshot** — this machine has no Chrome/Chromium/headless-browser binary installed, so the
   216	  litmus above is markup-level (real render function, real seeded DB row, grepped output) rather than
   217	  a rendered screenshot. If a visual check matters before shipping, it needs a machine with a browser
   218	  installed.
   219	
   220	## Phase 3 — Wiring, config, docs
   221	
   222	**Discuss:**
   223	- **Decided:** the owning path is `_refresh_github` in `src/rebalance/ingest/index_ops.py` — it calls
   224	  the Phase 1 auto-promotion helper immediately after the existing `WATCHLIST-COVERAGE-GUARD`
   225	  snapshot/diff step, so it rides `refresh_index(scope=["github"])` and `daily_sync.sh`'s existing
   226	  cadence with zero new scheduling surface. Not left open for later re-evaluation; if operating
   227	  experience later shows this cadence is wrong, that is a new issue against the shipped behavior, not
   228	  a re-open of this plan.
   229	
   230	Work:
   231	- Wire Phase 1's detection+write into `_refresh_github` (`index_ops.py`), immediately after the
   232	  watchlist-guard step, per the Discuss decision above.
   233	- Update `ARCHITECTURE.md` (new config keys, the extended `machine_owned` trigger).
   234	- Update `AGENTS.md` if a new MCP-visible behavior needs documenting for future agents.
   235	- `CHANGELOG.md` entry.
   236	
   237	**Phase 3 QA gate:**
   238	- [x] `_refresh_github` wiring test (`tests/test_index_ops.py::test_github_refresh_wires_auto_promote_after_watchlist_guard`).
   239	- [x] Full `pytest tests/` — 2 pre-existing unrelated failures (`test_pulse_self_repair.py`, a git-push
   240	  race, confirmed pre-existing via `git stash`), zero regressions from this work.
   241	- [x] `rebalance doctor` clean.
   242	- [x] `utils/pdda/pdda.sh run` clean.
   243	- [x] Live end-to-end litmus — **happened for real, not as a deliberate step.** Mid-build, this
   244	  machine's real `com.rebalance-os.github-sync` launchd job picked up the Phase 1-3 commits already
   245	  on `development` and executed the feature against the real production DB: **8 real repos
   246	  auto-promoted** (`facebook-for-woocommerce-plugin-fork`, `shipstation-fork`, `xyz-3-agents-swarm`,
   247	  `WP-Code-Check`, `pdda`, `woo-orders-analytics-plugin`, `deckme`, `KISS-woo-fast-search`),
   248	  `promoted_at: 2026-07-11T14:33:31Z`, correctly `machine_owned`, correctly non-clobbering curated
   249	  rows, correctly firing the `project_auto_promoted` auth-log event. Operator reviewed and chose to
   250	  keep them (real data, matches intended behavior). **Process learning, not a code bug:** any commit
   251	  to `development` is live within the hour via the existing hourly github-sync job — there is no
   252	  staging gate. Worth a follow-up decision (separate from this issue) on whether risky ingest-writing
   253	  features need a feature flag before landing on `development`, not just before `main`.
   254	- **Verification summary:** `pytest tests/` → 1350 passed, 10 skipped, 2 pre-existing failures
   255	  (unrelated). `rebalance doctor` → clean. `pdda.sh run` → clean. Unmet: none for this phase's own
   256	  scope; the live-promotion timing gap above is flagged as a process follow-up, not blocking.
   257	  **Also found and fixed during this phase:** test runs via plain `python -m unittest` (pytest wasn't
   258	  installed in this venv) bypass `tests/conftest.py`'s auth-log sandboxing fixture, writing real
   259	  entries into the real `temp/logs/auth_activity.jsonl`. Installed `pytest` (now the real, correct
   260	  verification tool per ROUTER.md) and cleaned up the 17 resulting test-pollution log lines (operator

exec
/bin/zsh -lc "rg -n \"sync_commit_threshold_promotions|_count_operator_commits|_repo_to_promoted_row|_is_inference_owned|_delete_stale_inferred_rows|_partition_writable_rows|get_auto_promote_config|_refresh_github|log_project_auto_promoted|fetch_recent_auto_promotion|render_repo_pie|auto_promote|CLOUD_AGENT_AUTHORS|_author_filter_sql|github_commits|sync_db\\(\" -S src tests scripts ARCHITECTURE.md AGENTS.md CHANGELOG.md pyproject.toml" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
AGENTS.md:74:**Auto-promotion (GH-124).** `refresh_index(scope=["github"])` also auto-promotes a watched-but-unconfirmed repo into `project_registry` (as a `machine_owned` row, never overwriting a curated one) once the operator has authored `auto_promote_commit_threshold` commits to it (default 3; config in `config.py::get_auto_promote_config()`). So `list_projects()` can grow entries you never explicitly confirmed — check `custom_fields.provenance == "auto_promoted"` before assuming a project was hand-curated. Each promotion is surfaced non-silently: a `project_auto_promoted` event on `/auth-log` and a "New repo added" banner on the pulse dashboard's repo-activity chart.
ARCHITECTURE.md:148:                     │                             reviews, commits, checks,       github_commits
ARCHITECTURE.md:272:Project Registry (writer: registry.py::sync_db(), the single low-level upsert)
ARCHITECTURE.md:278:                               machine_owned producers currently call sync_db():
ARCHITECTURE.md:282:                               "commit_threshold_v1", wired into _refresh_github()
ARCHITECTURE.md:284:                               guard). _is_inference_owned() recognizes both markers.
ARCHITECTURE.md:297:  github_commits             — PR commit history
CHANGELOG.md:12:- **Commit-threshold auto-promotion of watched repos** ([GH-124](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/124)) — a watched-but-unconfirmed repo now auto-promotes into `project_registry` once the operator (or a known cloud-agent bot acting on their behalf) has authored `auto_promote_commit_threshold` commits to it (default 3, config `auto_promote_enabled`/`auto_promote_commit_threshold`). Reuses the existing `machine_owned` write contract from activity/calendar inference (never overwrites a curated row), reuses `pulse.py`'s existing author-identity filter against `github_commits` rather than inventing a second one, and wires into `_refresh_github()` immediately after the watchlist coverage guard — no new scheduling surface. Forks/starred repos with zero operator commits never promote; the commit-count gate is the fork filter, no separate detection needed. Every promotion surfaces non-silently: a `project_auto_promoted` badge on `/auth-log` and a "New repo added" banner on the pulse dashboard's repo-activity chart. Plan Codex-reviewed to approval via `relay-xyz` (3 rounds) before build. 20 new tests across detection, surfacing, and orchestrator wiring; full suite verified zero-regression against a pre-change baseline; `rebalance doctor` clean.
CHANGELOG.md:671:- **`include_semantic` parameter removed from `refresh_index` and `_refresh_github`.**
CHANGELOG.md:1822:- Fixed registry `sync_db()` to write JSON (not YAML) into `_json` columns.
tests/test_index_ops.py:10:from rebalance.ingest.index_ops import _refresh_dashboard_note, _refresh_github, refresh_index
tests/test_index_ops.py:18:            result = _refresh_github(
tests/test_index_ops.py:30:    def test_github_refresh_wires_auto_promote_after_watchlist_guard(self) -> None:
tests/test_index_ops.py:32:        # sync_commit_threshold_promotions after the watchlist guard and fold
tests/test_index_ops.py:33:        # its summary into the result under "auto_promote".
tests/test_index_ops.py:68:                    "rebalance.ingest.project_inference.sync_commit_threshold_promotions",
tests/test_index_ops.py:70:                ) as mock_auto_promote,
tests/test_index_ops.py:86:                result = _refresh_github(
tests/test_index_ops.py:90:        mock_auto_promote.assert_called_once_with(db_path)
tests/test_index_ops.py:91:        self.assertEqual(result["auto_promote"]["promoted_count"], 1)
tests/test_index_ops.py:92:        self.assertEqual(result["auto_promote"]["promoted_repos"], ["Acme/widget"])
tests/test_index_ops.py:93:        self.assertEqual(result["auto_promote"]["candidates_evaluated"], 2)
tests/test_repo_pie_auto_promote.py:19:        html = pulse_web.render_repo_pie(
tests/test_repo_pie_auto_promote.py:25:        html = pulse_web.render_repo_pie(
tests/test_repo_pie_auto_promote.py:34:        html = pulse_web.render_repo_pie(
tests/test_db_github.py:187:                conn.execute("SELECT sha FROM github_commits").fetchone()["sha"],
tests/test_db_github.py:265:                conn.execute("SELECT COUNT(*) FROM github_commits").fetchone()[0], 0
scripts/dashboard.py:323:                        SELECT repo_full_name, fetched_at FROM github_commits
scripts/dashboard.py:383:                    FROM github_commits
scripts/dashboard.py:432:def fetch_recent_auto_promotion(days: int = 7) -> dict[str, Any] | None:
scripts/pulse_web.py:47:    fetch_recent_auto_promotion,
scripts/pulse_web.py:885:def _render_repo_pie_new_badge(recent_promotion: dict[str, Any] | None) -> str:
scripts/pulse_web.py:900:def render_repo_pie(
scripts/pulse_web.py:904:    new_badge = _render_repo_pie_new_badge(recent_promotion)
scripts/pulse_web.py:2724:    repo_pie_recent_promotion = fetch_recent_auto_promotion(days=repo_pie_days)
scripts/pulse_web.py:2851:            {render_repo_pie(repo_pie_rows, days=repo_pie_days, recent_promotion=repo_pie_recent_promotion)}
tests/test_calendar_aggregator.py:156:            sync_db(
tests/test_calendar_aggregator.py:197:            sync_db(
tests/test_web_auth_log.py:49:    def test_project_auto_promoted_renders_ok_badge(self) -> None:
tests/test_web_auth_log.py:54:            "event": "project_auto_promoted",
tests/test_github_reconciliation.py:220:                    INSERT INTO github_commits
tests/test_calendar_team_loop_isolation.py:5:_refresh_github loop. A revoked share / 404 / transient 5xx on one teammate
tests/test_next_actions.py:87:        INSERT INTO github_commits
tests/test_phase5_collector_smoke.py:18:    _refresh_github,
tests/test_phase5_collector_smoke.py:211:            r1 = _refresh_github(self.db, token="tok", since_days=7, repos=[], dry_run=True)
tests/test_phase5_collector_smoke.py:212:            r2 = _refresh_github(self.db, token="tok", since_days=7, repos=[], dry_run=True)
tests/test_collector_contracts.py:54:    """github_activity (per-(login,repo,scan_date) scan snapshot) and github_commits
tests/test_client_buckets.py:36:        sync_db(
src/rebalance/web.py:226:    "project_auto_promoted": ("ok",     "✓ project auto-added"),
src/rebalance/mcp/tools/index.py:195:        "github_commits": "committed_at",
src/rebalance/mcp/tools/index.py:216:            source: One of github_activity, github_commits, github_items,
src/rebalance/ingest/github_knowledge.py:266:        "github_commits",
tests/test_auto_promote.py:16:    sync_commit_threshold_promotions,
tests/test_auto_promote.py:27:        INSERT INTO github_commits
tests/test_auto_promote.py:74:        summary = sync_commit_threshold_promotions(self.db_path)
tests/test_auto_promote.py:88:        summary = sync_commit_threshold_promotions(self.db_path)
tests/test_auto_promote.py:98:        summary = sync_commit_threshold_promotions(self.db_path)
tests/test_auto_promote.py:109:        summary = sync_commit_threshold_promotions(self.db_path)
tests/test_auto_promote.py:120:        summary = sync_commit_threshold_promotions(self.db_path)
tests/test_auto_promote.py:129:        sync_db(
tests/test_auto_promote.py:145:        summary = sync_commit_threshold_promotions(self.db_path)
tests/test_auto_promote.py:161:        sync_commit_threshold_promotions(self.db_path)
tests/test_auto_promote.py:162:        sync_commit_threshold_promotions(self.db_path)
tests/test_auto_promote.py:176:            {**config_module._read_config(), "auto_promote_enabled": False}
tests/test_auto_promote.py:179:        summary = sync_commit_threshold_promotions(self.db_path)
tests/test_auto_promote.py:191:            "rebalance.ingest.auth_log.log_project_auto_promoted"
tests/test_auto_promote.py:193:            sync_commit_threshold_promotions(self.db_path)
tests/test_auto_promote.py:206:            "rebalance.ingest.auth_log.log_project_auto_promoted"
tests/test_auto_promote.py:208:            sync_commit_threshold_promotions(self.db_path)
tests/test_auto_promote.py:223:        summary = sync_commit_threshold_promotions(self.db_path)
src/rebalance/ingest/config.py:950:def get_auto_promote_config() -> dict[str, Any]:
src/rebalance/ingest/config.py:954:      - auto_promote_enabled: opt-in flag gating commit-threshold auto-promotion of a
src/rebalance/ingest/config.py:958:      - auto_promote_commit_threshold: minimum distinct-SHA operator commits (all-time,
src/rebalance/ingest/config.py:964:        "auto_promote_enabled": bool(config.get("auto_promote_enabled", True)),
src/rebalance/ingest/config.py:965:        "auto_promote_commit_threshold": int(config.get("auto_promote_commit_threshold", 3)),
src/rebalance/ingest/index_ops.py:729:def _refresh_github(
src/rebalance/ingest/index_ops.py:839:        from rebalance.ingest.project_inference import sync_commit_threshold_promotions
src/rebalance/ingest/index_ops.py:841:        auto_promote_summary = sync_commit_threshold_promotions(database_path)
src/rebalance/ingest/index_ops.py:842:        auto_promote_result: dict[str, Any] = {
src/rebalance/ingest/index_ops.py:843:            "enabled": auto_promote_summary.enabled,
src/rebalance/ingest/index_ops.py:844:            "threshold": auto_promote_summary.threshold,
src/rebalance/ingest/index_ops.py:845:            "candidates_evaluated": auto_promote_summary.candidates_evaluated,
src/rebalance/ingest/index_ops.py:846:            "promoted_count": auto_promote_summary.promoted_count,
src/rebalance/ingest/index_ops.py:849:                for row in auto_promote_summary.promoted
src/rebalance/ingest/index_ops.py:853:        auto_promote_result = {"error": str(e)}
src/rebalance/ingest/index_ops.py:859:        "auto_promote": auto_promote_result,
src/rebalance/ingest/index_ops.py:937:            # Mirror _refresh_github's per-repo isolation.
src/rebalance/ingest/index_ops.py:1507:    return _refresh_github(
src/rebalance/ingest/project_inference.py:65:# (sync_commit_threshold_promotions below). Kept distinct from
src/rebalance/ingest/project_inference.py:67:# but recognized by _is_inference_owned alongside it — both markers share the
src/rebalance/ingest/project_inference.py:73:def _is_inference_owned(custom_fields_json: str | None) -> bool:
src/rebalance/ingest/project_inference.py:666:def _delete_stale_inferred_rows(database_path: Path, project_names: set[str]) -> int:
src/rebalance/ingest/project_inference.py:674:            if _is_inference_owned(row["custom_fields_json"]) and row["name"] not in project_names
src/rebalance/ingest/project_inference.py:683:def _partition_writable_rows(
src/rebalance/ingest/project_inference.py:697:        row["name"] for row in rows if not _is_inference_owned(row["custom_fields_json"])
src/rebalance/ingest/project_inference.py:759:    writable, skipped_curated = _partition_writable_rows(database_path, projects)
src/rebalance/ingest/project_inference.py:760:    updated_count = sync_db(database_path, {"projects": writable})
src/rebalance/ingest/project_inference.py:761:    deleted_count = _delete_stale_inferred_rows(database_path, set(summary.project_names))
src/rebalance/ingest/project_inference.py:779:def _count_operator_commits(conn: Any, repo_full_name: str, github_login: str) -> int:
src/rebalance/ingest/project_inference.py:783:    Reuses ``pulse._author_filter_sql`` against ``github_commits.author_login``
src/rebalance/ingest/project_inference.py:789:    from rebalance.ingest.pulse import CLOUD_AGENT_AUTHORS, _author_filter_sql
src/rebalance/ingest/project_inference.py:791:    author_filter = _author_filter_sql("author_login")
src/rebalance/ingest/project_inference.py:795:        FROM github_commits
src/rebalance/ingest/project_inference.py:798:        (repo_full_name, github_login, *CLOUD_AGENT_AUTHORS),
src/rebalance/ingest/project_inference.py:803:def _repo_to_promoted_row(repo_full_name: str, *, commit_count: int, threshold: int) -> dict[str, Any]:
src/rebalance/ingest/project_inference.py:821:            "provenance": "auto_promoted",
src/rebalance/ingest/project_inference.py:835:    """Result of one ``sync_commit_threshold_promotions`` pass."""
src/rebalance/ingest/project_inference.py:848:def sync_commit_threshold_promotions(database_path: Path) -> AutoPromoteSummary:
src/rebalance/ingest/project_inference.py:856:    operator-authored commit count (see ``_count_operator_commits``) reaches
src/rebalance/ingest/project_inference.py:857:    ``auto_promote_commit_threshold``. A fork or starred-only repo with zero
src/rebalance/ingest/project_inference.py:862:    (``_partition_writable_rows`` / ``sync_db``) — a curated row sharing the
src/rebalance/ingest/project_inference.py:866:    from rebalance.ingest.config import get_auto_promote_config, get_pulse_config
src/rebalance/ingest/project_inference.py:869:    auto_promote_config = get_auto_promote_config()
src/rebalance/ingest/project_inference.py:870:    threshold = auto_promote_config["auto_promote_commit_threshold"]
src/rebalance/ingest/project_inference.py:871:    if not auto_promote_config["auto_promote_enabled"]:
src/rebalance/ingest/project_inference.py:884:            commit_count = _count_operator_commits(conn, repo_full_name, github_login)
src/rebalance/ingest/project_inference.py:887:                    _repo_to_promoted_row(repo_full_name, commit_count=commit_count, threshold=threshold)
src/rebalance/ingest/project_inference.py:890:    writable, skipped_curated = _partition_writable_rows(database_path, promoted_rows)
src/rebalance/ingest/project_inference.py:892:        sync_db(database_path, {"projects": writable})
src/rebalance/ingest/project_inference.py:893:        from rebalance.ingest.auth_log import log_project_auto_promoted
src/rebalance/ingest/project_inference.py:897:            log_project_auto_promoted(
src/rebalance/ingest/github_reconciliation.py:257:                FROM github_commits
src/rebalance/ingest/pulse.py:11:  - GitHub commits:     ``github_commits`` (authored by ``github_login``)
src/rebalance/ingest/pulse.py:46:CLOUD_AGENT_AUTHORS: tuple[str, ...] = (
src/rebalance/ingest/pulse.py:56:def _author_filter_sql(column: str) -> str:
src/rebalance/ingest/pulse.py:58:    placeholders = ", ".join("?" for _ in CLOUD_AGENT_AUTHORS)
src/rebalance/ingest/pulse.py:163:    commit_filter = _author_filter_sql("c.author_login")
src/rebalance/ingest/pulse.py:168:        FROM github_commits c
src/rebalance/ingest/pulse.py:177:        (sql_floor, github_login, *CLOUD_AGENT_AUTHORS),
src/rebalance/ingest/pulse.py:197:    item_filter = _author_filter_sql("author_login")
src/rebalance/ingest/pulse.py:213:        (sql_floor, sql_floor, github_login, *CLOUD_AGENT_AUTHORS),
src/rebalance/ingest/pulse.py:240:    comment_filter = _author_filter_sql("author_login")
src/rebalance/ingest/pulse.py:250:        (sql_floor, github_login, *CLOUD_AGENT_AUTHORS),
src/rebalance/ingest/pulse.py:471:        SELECT repo_full_name, committed_at FROM github_commits
src/rebalance/ingest/diagnose.py:221:                ("github_commits", "commits"),
src/rebalance/ingest/diagnose.py:261:                    "FROM github_commits "
src/rebalance/ingest/auth_log.py:329:def log_project_auto_promoted(
src/rebalance/ingest/auth_log.py:338:    ``project_inference.sync_commit_threshold_promotions``.
src/rebalance/ingest/auth_log.py:340:    _append("registry", "project_auto_promoted", {
src/rebalance/ingest/github_watch.py:11:issues/PRs/commits already flow into ``github_items`` / ``github_commits`` /
src/rebalance/ingest/github_watch.py:245:      - cloud-agent authored commits exist in the window (``github_commits``).
src/rebalance/ingest/github_watch.py:300:            from rebalance.ingest.pulse import CLOUD_AGENT_AUTHORS  # noqa: PLC0415
src/rebalance/ingest/github_watch.py:302:            placeholders = ",".join("?" * len(CLOUD_AGENT_AUTHORS))
src/rebalance/ingest/github_watch.py:304:                f"SELECT 1 FROM github_commits WHERE LOWER(repo_full_name)=? "
src/rebalance/ingest/github_watch.py:307:                (repo, *CLOUD_AGENT_AUTHORS, _cutoff_iso(since_days)[:10]),
src/rebalance/ingest/registry.py:165:def sync_db(database_path: Path, projection: dict[str, Any]) -> int:
src/rebalance/ingest/registry.py:264:    upserted = sync_db(database_path=database_path, projection=projection)
src/rebalance/ingest/db/schema.py:482:        CREATE TABLE IF NOT EXISTS github_commits (
src/rebalance/ingest/db/schema.py:497:        "CREATE INDEX IF NOT EXISTS idx_github_commits_item "
src/rebalance/ingest/db/schema.py:498:        "ON github_commits(repo_full_name, item_type, item_number)"
src/rebalance/ingest/db/github.py:234:    """Insert-or-replace one ``github_commits`` row.
src/rebalance/ingest/db/github.py:241:        INSERT OR REPLACE INTO github_commits
src/rebalance/ingest/db/github.py:365:        DELETE FROM github_commits

codex
I have the plan contract. Next I’m reading the implementation around `project_inference`, `index_ops`, registry writes, and the GitHub commit storage path to see whether the SQL and lifecycle semantics actually match the plan’s “all-time distinct SHA, curated-never-touched” claims.
exec
/bin/zsh -lc "nl -ba src/rebalance/ingest/index_ops.py | sed -n '729,880p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
   729	def _refresh_github(
   730	    database_path: Path,
   731	    *,
   732	    token: str,
   733	    since_days: int,
   734	    repos: list[str],
   735	    dry_run: bool,
   736	) -> dict[str, Any]:
   737	    initial_target_repos = _resolve_repos_for_refresh(database_path, repos)
   738	    external_count = len(
   739	        [r for r in initial_target_repos if r.lower() in {e.lower() for e in _external_repos(database_path)}]
   740	    )
   741	    plan_steps = [
   742	        "sync_pushed_repos()",
   743	        f"github_scan(days={since_days})",
   744	        f"sync_github_repo() x ~{len(initial_target_repos)} repos (after auto-discovery)",
   745	        f"reconcile_watched_repo() x {external_count} external repos (rollup or purge)",
   746	        "embed_github_documents()",
   747	    ]
   748	    if dry_run:
   749	        return {
   750	            "scope": "github",
   751	            "dry_run": True,
   752	            "target_repos": initial_target_repos,
   753	            "steps": plan_steps,
   754	        }
   755	
   756	    from rebalance.ingest.github_scan import (
   757	        filter_ignored_repo_activity,
   758	        scan_github,
   759	        sync_pushed_repos,
   760	        upsert_github_activity,
   761	    )
   762	    from rebalance.ingest.config import get_github_ignored_repos
   763	    from rebalance.ingest.github_knowledge import sync_github_repo
   764	
   765	    # Auto-discovery: fetch /user/repos?sort=pushed and upsert into
   766	    # github_pushed_repos BEFORE resolving target repos, so newly-pushed
   767	    # repos enter the watched set on this refresh rather than the next one.
   768	    pushed_result = sync_pushed_repos(database_path, token=token)
   769	    target_repos = _resolve_repos_for_refresh(database_path, repos)
   770	
   771	    scan_result = scan_github(token=token, days=since_days)
   772	    skipped = filter_ignored_repo_activity(scan_result, get_github_ignored_repos())
   773	    upsert_github_activity(database_path, scan_result)
   774	
   775	    repo_results: list[dict[str, Any]] = []
   776	    for repo in target_repos:
   777	        try:
   778	            r = sync_github_repo(
   779	                database_path=database_path,
   780	                repo_full_name=repo,
   781	                token=token,
   782	                since_days=since_days,
   783	            )
   784	            repo_results.append({
   785	                "repo": repo,
   786	                "branches": r.branches_synced,
   787	                "issues": r.issues_synced,
   788	                "prs": r.prs_synced,
   789	                "comments": r.comments_synced,
   790	                "commits": r.commits_synced,
   791	                "checks": r.checks_synced,
   792	                "docs_built": r.docs_built,
   793	                "elapsed_seconds": r.elapsed_seconds,
   794	            })
   795	        except Exception as e:
   796	            repo_results.append({"repo": repo, "error": str(e)})
   797	
   798	    # External/watched repos: after their artifacts are synced above, reconcile a
   799	    # whole-repo github_activity rollup so everyone's activity surfaces in the
   800	    # org-activity dashboards/reports. Idempotent + bidirectional — a watched repo
   801	    # that's become active local/cloud work has its sentinel rollup purged instead
   802	    # (see github_watch.reconcile_watched_repo) so it never double-counts.
   803	    from rebalance.ingest.github_watch import reconcile_watched_repo
   804	
   805	    external_set = {r.lower() for r in _external_repos(database_path)}
   806	    watched_activity: list[dict[str, Any]] = []
   807	    for repo in target_repos:
   808	        if repo.lower() not in external_set:
   809	            continue
   810	        try:
   811	            watched_activity.append(
   812	                reconcile_watched_repo(
   813	                    database_path, repo, token, since_days=since_days
   814	                )
   815	            )
   816	        except Exception as e:  # noqa: BLE001 — one repo must not abort the run
   817	            watched_activity.append({"repo": repo, "error": str(e)})
   818	
   819	    from rebalance.ingest.github_knowledge import embed_github_documents
   820	
   821	    gh_embed = embed_github_documents(database_path=database_path)
   822	
   823	    # Coverage guard: snapshot the resolved watched set and alarm on a silent
   824	    # reduction. Runs LAST, only on a clean sync (an earlier raise never reaches
   825	    # here), so a truncated mid-failure set can't record a false reduction. Never
   826	    # let the guard break a sync — observability must not reduce reliability.
   827	    try:
   828	        from rebalance.ingest.watchlist_guard import snapshot_and_detect
   829	
   830	        watchlist_guard = snapshot_and_detect(database_path)
   831	    except Exception as e:  # noqa: BLE001
   832	        watchlist_guard = {"error": str(e)}
   833	
   834	    # GH-124: commit-threshold auto-promotion. Immediately after the coverage
   835	    # guard (same "clean sync only, never break a sync" posture) so a repo that
   836	    # just crossed the operator-commit threshold graduates into project_registry
   837	    # on this same refresh rather than waiting for a future one.
   838	    try:
   839	        from rebalance.ingest.project_inference import sync_commit_threshold_promotions
   840	
   841	        auto_promote_summary = sync_commit_threshold_promotions(database_path)
   842	        auto_promote_result: dict[str, Any] = {
   843	            "enabled": auto_promote_summary.enabled,
   844	            "threshold": auto_promote_summary.threshold,
   845	            "candidates_evaluated": auto_promote_summary.candidates_evaluated,
   846	            "promoted_count": auto_promote_summary.promoted_count,
   847	            "promoted_repos": [
   848	                row["custom_fields"]["inference"]["repo_full_name"]
   849	                for row in auto_promote_summary.promoted
   850	            ],
   851	        }
   852	    except Exception as e:  # noqa: BLE001
   853	        auto_promote_result = {"error": str(e)}
   854	
   855	    return {
   856	        "scope": "github",
   857	        "dry_run": False,
   858	        "watchlist_guard": watchlist_guard,
   859	        "auto_promote": auto_promote_result,
   860	        "pushed_repos_sync": {
   861	            "fetched": pushed_result.fetched,
   862	            "inserted": pushed_result.inserted,
   863	            "updated": pushed_result.updated,
   864	            "unchanged": pushed_result.unchanged,
   865	            "skipped_archived": pushed_result.skipped_archived,
   866	            "error": pushed_result.error,
   867	        },
   868	        "github_scan": {
   869	            "login": scan_result.login,
   870	            "events": scan_result.total_events,
   871	            "repos": len(scan_result.repo_activity),
   872	            "skipped_ignored": len(skipped),
   873	        },
   874	        "artifact_sync": repo_results,
   875	        "watched_activity": watched_activity,
   876	        "github_embed": {
   877	            "total": gh_embed.total_docs,
   878	            "embedded": gh_embed.embedded_docs,
   879	            "skipped_unchanged": gh_embed.skipped_unchanged,
   880	            "elapsed_seconds": gh_embed.elapsed_seconds,

exec
/bin/zsh -lc "nl -ba src/rebalance/ingest/project_inference.py | sed -n '1,980p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
     1	from __future__ import annotations
     2	
     3	import json
     4	import re
     5	from collections import Counter, defaultdict
     6	from dataclasses import dataclass, field
     7	from datetime import datetime, timedelta, timezone
     8	from pathlib import Path
     9	from typing import Any
    10	
    11	from rebalance.ingest.calendar_config import (
    12	    OPERATOR_CALENDAR_ID,
    13	    CalendarConfig,
    14	    filter_events,
    15	)
    16	from rebalance.ingest.calendar_helpers import event_duration_minutes, parse_calendar_dt
    17	from rebalance.ingest.config import get_github_ignored_repos
    18	from rebalance.ingest.db import (
    19	    db_connection,
    20	    ensure_calendar_schema,
    21	    ensure_github_schema,
    22	    ensure_project_schema,
    23	)
    24	from rebalance.ingest.project_classifier import normalize_match_text
    25	from rebalance.ingest.registry import sync_db
    26	
    27	_GENERIC_ALIAS_TOKENS = {
    28	    "app",
    29	    "dev",
    30	    "git",
    31	    "github",
    32	    "loop",
    33	    "oct",
    34	    "os",
    35	    "plugin",
    36	    "repo",
    37	    "team",
    38	    "theme",
    39	    "tool",
    40	    "toolkit",
    41	    "tools",
    42	    "universal",
    43	}
    44	_CALENDAR_NOISE_SUBSTRINGS = (
    45	    "blocked off",
    46	    "morning exercise",
    47	    "end of day check in",
    48	    "team call",
    49	)
    50	_CALENDAR_NOISE_EXACT = {
    51	    "15 minute meeting",
    52	    "matt noel jose",
    53	    "verizon store",
    54	}
    55	_CALENDAR_SUFFIX_WORDS = {"weekly", "meetings", "meeting", "website", "deployment", "day", "daily"}
    56	_CLIENT_GAPFILL_UNCERTAIN = {"", "n/a", "na", "none", "null", "unclear", "unknown", "unsure", "?"}
    57	
    58	
    59	# Provenance marker for rows this module owns. Inference may create, update,
    60	# and delete ONLY rows carrying this marker (lifecycle contract:
    61	# write_semantics="machine_owned") — curated registry rows always win.
    62	INFERENCE_GENERATED_BY = "activity_inference_v1"
    63	
    64	# GH-124: a second machine-owned marker for commit-threshold auto-promotion
    65	# (sync_commit_threshold_promotions below). Kept distinct from
    66	# INFERENCE_GENERATED_BY so a promoted row's provenance is self-describing,
    67	# but recognized by _is_inference_owned alongside it — both markers share the
    68	# same machine_owned contract (curated rows never touched, safe to recreate).
    69	COMMIT_THRESHOLD_GENERATED_BY = "commit_threshold_v1"
    70	_MACHINE_OWNED_MARKERS = {INFERENCE_GENERATED_BY, COMMIT_THRESHOLD_GENERATED_BY}
    71	
    72	
    73	def _is_inference_owned(custom_fields_json: str | None) -> bool:
    74	    try:
    75	        custom_fields = json.loads(custom_fields_json) if custom_fields_json else {}
    76	    except json.JSONDecodeError:
    77	        custom_fields = {}
    78	    generated_by = ((custom_fields or {}).get("inference") or {}).get("generated_by")
    79	    return generated_by in _MACHINE_OWNED_MARKERS
    80	
    81	
    82	@dataclass
    83	class InferenceSummary:
    84	    inferred_count: int
    85	    github_backed_count: int
    86	    calendar_only_count: int
    87	    updated_count: int
    88	    deleted_stale_inferred_count: int
    89	    project_names: list[str]
    90	    skipped_curated_count: int = 0
    91	    skipped_curated_names: list[str] = field(default_factory=list)
    92	
    93	
    94	@dataclass
    95	class _ProjectSeed:
    96	    key: str
    97	    display_name: str
    98	    repos: set[str]
    99	    github_score: int = 0
   100	    github_last_active_at: str | None = None
   101	    github_bands: set[str] | None = None
   102	    github_signals: int = 0
   103	    calendar_event_count: int = 0
   104	    calendar_total_minutes: int = 0
   105	    calendar_last_event_at: str | None = None
   106	    calendar_labels: Counter[str] | None = None
   107	    aliases: set[str] | None = None
   108	
   109	    def __post_init__(self) -> None:
   110	        if self.github_bands is None:
   111	            self.github_bands = set()
   112	        if self.calendar_labels is None:
   113	            self.calendar_labels = Counter()
   114	        if self.aliases is None:
   115	            self.aliases = set()
   116	
   117	
   118	# Phase 5: one normalizer across classifier/inference/priority — the
   119	# canonical implementation lives in project_classifier.
   120	_normalize_text = normalize_match_text
   121	
   122	
   123	def _split_tokens(text: str) -> list[str]:
   124	    parts = re.findall(r"[A-Z]+(?=[A-Z][a-z]|\b)|[A-Z]?[a-z]+|\d+", text.replace(".", " "))
   125	    return [part.casefold() for part in parts if part]
   126	
   127	
   128	def _repo_slug_to_title(slug: str) -> str:
   129	    pieces = [piece for piece in re.split(r"[-_.]+", slug.strip()) if piece and piece.casefold() != "md"]
   130	    rendered: list[str] = []
   131	    for piece in pieces:
   132	        if piece.isupper():
   133	            rendered.append(piece)
   134	        elif piece.lower() in {"os", "ai", "wp", "db", "ui", "llm"}:
   135	            rendered.append(piece.upper())
   136	        else:
   137	            rendered.append(piece.capitalize())
   138	    return " ".join(rendered) or slug
   139	
   140	
   141	def _owner_brand_aliases(owner: str) -> list[str]:
   142	    aliases: list[str] = []
   143	    token_groups = _split_tokens(owner)
   144	    if token_groups:
   145	        joined = " ".join(token_groups)
   146	        if joined:
   147	            aliases.append(joined)
   148	        if token_groups[0] not in _GENERIC_ALIAS_TOKENS:
   149	            aliases.append(token_groups[0])
   150	    cleaned = re.sub(r"(team|dev|tools|labs|hq|inc|llc|studio|group)$", "", owner, flags=re.IGNORECASE)
   151	    if cleaned and cleaned.casefold() != owner.casefold():
   152	        cleaned_norm = _normalize_text(cleaned)
   153	        if cleaned_norm:
   154	            aliases.append(cleaned_norm)
   155	    return [alias for alias in aliases if alias]
   156	
   157	
   158	def _build_repo_aliases(repo_full_name: str) -> set[str]:
   159	    owner, _, slug = repo_full_name.partition("/")
   160	    aliases: set[str] = set()
   161	    for raw in [repo_full_name, repo_full_name.replace("-", " "), slug, slug.replace("-", " "), owner]:
   162	        normalized = _normalize_text(raw)
   163	        if normalized:
   164	            aliases.add(normalized)
   165	    for alias in _owner_brand_aliases(owner):
   166	        aliases.add(alias)
   167	    for token in _split_tokens(slug):
   168	        if len(token) >= 3 and token not in _GENERIC_ALIAS_TOKENS and not token.isdigit():
   169	            aliases.add(token)
   170	    return aliases
   171	
   172	
   173	def _choose_display_name(repo_full_name: str) -> str:
   174	    owner, _, slug = repo_full_name.partition("/")
   175	    slug_tokens = [token for token in _split_tokens(slug) if token]
   176	    generic_count = sum(1 for token in slug_tokens if token in _GENERIC_ALIAS_TOKENS or token.isdigit())
   177	    if slug_tokens and generic_count / len(slug_tokens) > 0.6:
   178	        owner_aliases = _owner_brand_aliases(owner)
   179	        if owner_aliases:
   180	            return _repo_slug_to_title(owner_aliases[-1].replace(" ", "-"))
   181	    return _repo_slug_to_title(slug)
   182	
   183	
   184	def _owner_group_key(owner: str) -> str | None:
   185	    cleaned = owner.strip()
   186	    if re.search(r"(team|cbd)$", cleaned, flags=re.IGNORECASE):
   187	        aliases = _owner_brand_aliases(cleaned)
   188	        if aliases:
   189	            return aliases[-1]
   190	    return None
   191	
   192	
   193	def _latest_github_rows(database_path: Path) -> list[dict[str, Any]]:
   194	    ignored = set(get_github_ignored_repos())
   195	    with db_connection(database_path, ensure_github_schema) as conn:
   196	        rows = conn.execute(
   197	            """
   198	            SELECT ga.repo_full_name,
   199	                   ga.commits,
   200	                   ga.pushes,
   201	                   ga.prs_opened,
   202	                   ga.prs_merged,
   203	                   ga.issues_opened,
   204	                   ga.issue_comments,
   205	                   ga.reviews,
   206	                   ga.last_active_at,
   207	                   ga.scanned_at
   208	            FROM github_activity ga
   209	            JOIN (
   210	                SELECT repo_full_name, MAX(scanned_at) AS max_scanned_at
   211	                FROM github_activity
   212	                GROUP BY repo_full_name
   213	            ) latest
   214	              ON latest.repo_full_name = ga.repo_full_name
   215	             AND latest.max_scanned_at = ga.scanned_at
   216	            ORDER BY ga.last_active_at DESC, ga.repo_full_name ASC
   217	            """
   218	        ).fetchall()
   219	
   220	    result: list[dict[str, Any]] = []
   221	    for row in rows:
   222	        repo_full_name = row["repo_full_name"]
   223	        if repo_full_name.casefold() in ignored:
   224	            continue
   225	        result.append(dict(row))
   226	    return result
   227	
   228	
   229	def _load_calendar_events(
   230	    database_path: Path,
   231	    *,
   232	    config: CalendarConfig,
   233	    days_back: int,
   234	    days_forward: int,
   235	) -> list[dict[str, Any]]:
   236	    today = datetime.now(timezone.utc).date()
   237	    min_date = (today - timedelta(days=days_back)).isoformat()
   238	    max_date = (today + timedelta(days=days_forward)).isoformat()
   239	    with db_connection(database_path, ensure_calendar_schema) as conn:
   240	        rows = conn.execute(
   241	            """
   242	            SELECT summary, start_time, end_time
   243	            FROM calendar_events
   244	            WHERE calendar_id = ?
   245	              AND DATE(start_time) BETWEEN ? AND ?
   246	            ORDER BY start_time ASC
   247	            """,
   248	            # Operator rows are canonically stored as 'primary' (see
   249	            # OPERATOR_CALENDAR_ID); config.calendar_id would miss them.
   250	            (OPERATOR_CALENDAR_ID, min_date, max_date),
   251	        ).fetchall()
   252	
   253	    events = [
   254	        {
   255	            "summary": row["summary"] or "",
   256	            "start_time": row["start_time"] or "",
   257	            "end_time": row["end_time"] or "",
   258	        }
   259	        for row in rows
   260	    ]
   261	    return filter_events(events, config.exclude_titles)
   262	
   263	
   264	def _extract_calendar_label(summary: str) -> str | None:
   265	    stripped = summary.strip()
   266	    normalized = _normalize_text(stripped)
   267	    if not normalized:
   268	        return None
   269	    if normalized in _CALENDAR_NOISE_EXACT:
   270	        return None
   271	    if any(token in normalized for token in _CALENDAR_NOISE_SUBSTRINGS):
   272	        return None
   273	
   274	    if " - " in stripped:
   275	        prefix = stripped.split(" - ", 1)[0].strip()
   276	        if prefix:
   277	            return prefix
   278	
   279	    words = stripped.split()
   280	    if len(words) >= 2 and words[1].casefold().strip(":") in _CALENDAR_SUFFIX_WORDS:
   281	        return words[0].strip(":-")
   282	    if len(words) >= 3 and words[2].casefold().strip(":") in _CALENDAR_SUFFIX_WORDS:
   283	        return " ".join(words[:2]).strip(":-")
   284	
   285	    return None
   286	
   287	
   288	def _best_alias_match(summary: str, seeds: dict[str, _ProjectSeed]) -> str | None:
   289	    normalized = f" {_normalize_text(summary)} "
   290	    best_seed: str | None = None
   291	    best_score = (-1, -1)
   292	    for seed in seeds.values():
   293	        for alias in seed.aliases or set():
   294	            if not alias:
   295	                continue
   296	            padded_alias = f" {alias} "
   297	            if padded_alias not in normalized:
   298	                continue
   299	            score = (len(alias.split()), len(alias))
   300	            if score > best_score:
   301	                best_score = score
   302	                best_seed = seed.key
   303	    return best_seed
   304	
   305	
   306	def _parse_event_time(raw: str) -> datetime | None:
   307	    try:
   308	        dt = parse_calendar_dt(raw)
   309	    except Exception:
   310	        return None
   311	    if dt.tzinfo is None:
   312	        return None
   313	    return dt.astimezone(timezone.utc)
   314	
   315	
   316	def _merge_calendar_signal(seed: _ProjectSeed, *, summary: str, start_time: str, end_time: str, label: str | None) -> None:
   317	    seed.calendar_event_count += 1
   318	    seed.calendar_total_minutes += event_duration_minutes(start_time, end_time)
   319	    if label:
   320	        seed.calendar_labels[label] += 1
   321	        normalized_label = _normalize_text(label)
   322	        if normalized_label:
   323	            seed.aliases.add(normalized_label)
   324	    start_dt = _parse_event_time(start_time)
   325	    if start_dt:
   326	        start_iso = start_dt.isoformat()
   327	        if not seed.calendar_last_event_at or start_iso > seed.calendar_last_event_at:
   328	            seed.calendar_last_event_at = start_iso
   329	    normalized_summary = _normalize_text(summary)
   330	    if normalized_summary:
   331	        seed.aliases.add(normalized_summary)
   332	
   333	
   334	def _build_seeds_from_github(database_path: Path) -> dict[str, _ProjectSeed]:
   335	    seeds: dict[str, _ProjectSeed] = {}
   336	    for row in _latest_github_rows(database_path):
   337	        repo_full_name = row["repo_full_name"]
   338	        owner, _, _slug = repo_full_name.partition("/")
   339	        score = (
   340	            row["commits"]
   341	            + row["pushes"]
   342	            + row["prs_opened"]
   343	            + row["prs_merged"]
   344	            + row["issues_opened"]
   345	            + row["issue_comments"]
   346	            + row["reviews"]
   347	        )
   348	        if score <= 0:
   349	            continue
   350	        grouped_key = _owner_group_key(owner)
   351	        seed_key = f"owner:{grouped_key}" if grouped_key else repo_full_name.casefold()
   352	        seed = seeds.get(seed_key)
   353	        if seed is None:
   354	            seed = _ProjectSeed(
   355	                key=seed_key,
   356	                display_name=_repo_slug_to_title(grouped_key.replace(" ", "-")) if grouped_key else _choose_display_name(repo_full_name),
   357	                repos=set(),
   358	                github_score=0,
   359	                github_last_active_at=None,
   360	                github_signals=0,
   361	            )
   362	            seeds[seed.key] = seed
   363	
   364	        seed.repos.add(repo_full_name)
   365	        seed.github_score += score
   366	        seed.github_signals += 1
   367	        if row["last_active_at"] and (
   368	            not seed.github_last_active_at or row["last_active_at"] > seed.github_last_active_at
   369	        ):
   370	            seed.github_last_active_at = row["last_active_at"]
   371	        seed.aliases.update(_build_repo_aliases(repo_full_name))
   372	        if grouped_key:
   373	            seed.aliases.add(grouped_key)
   374	    return seeds
   375	
   376	
   377	def _apply_calendar_signal(
   378	    database_path: Path,
   379	    *,
   380	    seeds: dict[str, _ProjectSeed],
   381	    config: CalendarConfig,
   382	    days_back: int,
   383	    days_forward: int,
   384	) -> None:
   385	    events = _load_calendar_events(
   386	        database_path,
   387	        config=config,
   388	        days_back=days_back,
   389	        days_forward=days_forward,
   390	    )
   391	    for event in events:
   392	        summary = event["summary"]
   393	        label = _extract_calendar_label(summary)
   394	        matched_key = _best_alias_match(summary, seeds)
   395	        if matched_key:
   396	            _merge_calendar_signal(
   397	                seeds[matched_key],
   398	                summary=summary,
   399	                start_time=event["start_time"],
   400	                end_time=event["end_time"],
   401	                label=label,
   402	            )
   403	            continue
   404	
   405	        if not label:
   406	            continue
   407	        normalized_label = _normalize_text(label)
   408	        if not normalized_label or normalized_label in _CALENDAR_NOISE_EXACT:
   409	            continue
   410	
   411	        key = f"calendar:{normalized_label}"
   412	        seed = seeds.get(key)
   413	        if seed is None:
   414	            seed = _ProjectSeed(
   415	                key=key,
   416	                display_name=label.strip(),
   417	                repos=set(),
   418	            )
   419	            seed.aliases.add(normalized_label)
   420	            seeds[key] = seed
   421	        _merge_calendar_signal(
   422	            seed,
   423	            summary=summary,
   424	            start_time=event["start_time"],
   425	            end_time=event["end_time"],
   426	            label=label,
   427	        )
   428	
   429	
   430	def _choose_seed_name(seed: _ProjectSeed) -> str:
   431	    normalized_display = _normalize_text(seed.display_name)
   432	    if normalized_display:
   433	        for label in seed.calendar_labels or Counter():
   434	            normalized_label = _normalize_text(label)
   435	            if f" {normalized_display} " in f" {normalized_label} ":
   436	                return seed.display_name
   437	    if seed.calendar_labels:
   438	        return seed.calendar_labels.most_common(1)[0][0]
   439	    return seed.display_name
   440	
   441	
   442	def _seed_status(seed: _ProjectSeed) -> str:
   443	    latest = seed.calendar_last_event_at or seed.github_last_active_at
   444	    if not latest:
   445	        return "potential"
   446	    try:
   447	        latest_dt = parse_calendar_dt(latest).astimezone(timezone.utc)
   448	    except Exception:
   449	        return "potential"
   450	    age_days = (datetime.now(timezone.utc) - latest_dt).days
   451	    if age_days <= 30:
   452	        return "active"
   453	    if age_days <= 90:
   454	        return "semi_active"
   455	    return "dormant"
   456	
   457	
   458	def _seed_summary(seed: _ProjectSeed) -> str:
   459	    parts: list[str] = []
   460	    if seed.repos:
   461	        repo_count = len(seed.repos)
   462	        parts.append(
   463	            f"GitHub inferred from {repo_count} repo{'s' if repo_count != 1 else ''}"
   464	        )
   465	        if seed.github_score:
   466	            parts[-1] += f" with score {seed.github_score}"
   467	    if seed.calendar_event_count:
   468	        hours = seed.calendar_total_minutes / 60.0
   469	        parts.append(
   470	            f"calendar inferred from {seed.calendar_event_count} event{'s' if seed.calendar_event_count != 1 else ''} ({hours:.1f}h)"
   471	        )
   472	    latest = seed.calendar_last_event_at or seed.github_last_active_at
   473	    if latest:
   474	        parts.append(f"last signal {latest[:10]}")
   475	    return "; ".join(parts)
   476	
   477	
   478	def _infer_client(seed: _ProjectSeed) -> str | None:
   479	    """Owner-as-client: the GitHub owner/org IS the client for the common case.
   480	
   481	    Deterministic, no API key. Calendar-only seeds have no repo owner → None
   482	    (the Gemini gap-fill in Phase 2 fills those). When a seed spans several owners
   483	    (grouped brand), the dominant owner wins.
   484	
   485	    # ponytail: owner-as-client is the free spine. Upgrade to Gemini gap-fill only
   486	    # for the None cases (personal/calendar-only), never the whole field.
   487	    """
   488	    owners = Counter(repo.partition("/")[0] for repo in seed.repos if "/" in repo)
   489	    if not owners:
   490	        return None
   491	    return owners.most_common(1)[0][0]
   492	
   493	
   494	def _project_activity_snippets(seed: _ProjectSeed) -> list[str]:
   495	    snippets: list[str] = []
   496	    repos = sorted(seed.repos)
   497	    if repos:
   498	        snippets.append(f"Repos: {', '.join(repos[:2])}")
   499	        github_bits: list[str] = []
   500	        if seed.github_last_active_at:
   501	            github_bits.append(f"last GitHub activity {seed.github_last_active_at[:10]}")
   502	        if seed.github_score:
   503	            github_bits.append(f"github activity score {seed.github_score}")
   504	        if github_bits:
   505	            snippets.append("; ".join(github_bits))
   506	    if seed.calendar_event_count:
   507	        calendar_bits = [f"{seed.calendar_event_count} calendar event(s)"]
   508	        top_label = (seed.calendar_labels or Counter()).most_common(1)
   509	        if top_label:
   510	            calendar_bits.append(f"top calendar label {top_label[0][0]!r}")
   511	        if seed.calendar_last_event_at:
   512	            calendar_bits.append(f"last calendar event {seed.calendar_last_event_at[:10]}")
   513	        snippets.append("; ".join(calendar_bits))
   514	    return snippets
   515	
   516	
   517	def _build_client_gapfill_prompt(candidates: list[tuple[_ProjectSeed, dict[str, Any]]]) -> str:
   518	    lines = [
   519	        "Infer the client/customer for each project from the evidence below.",
   520	        "Return STRICT JSON only: {\"Project Name\": \"Client Name\" | null}.",
   521	        "Rules:",
   522	        "- Use only explicit evidence from the project name, repos, or activity snippets.",
   523	        "- If the project looks internal, personal, open-source, or the client is not evident, return null.",
   524	        "- Do not guess or explain.",
   525	        "",
   526	        "Projects:",
   527	    ]
   528	    for index, (seed, project) in enumerate(candidates, 1):
   529	        lines.append(f"{index}. project={project['name']}")
   530	        repos = sorted(seed.repos)
   531	        lines.append(f"   repos={repos if repos else []}")
   532	        snippets = _project_activity_snippets(seed)
   533	        if snippets:
   534	            for snippet in snippets:
   535	                lines.append(f"   signal={snippet}")
   536	        else:
   537	            lines.append("   signal=no recent activity snippets")
   538	    return "\n".join(lines)
   539	
   540	
   541	def _strip_json_fence(text: str) -> str:
   542	    stripped = text.strip()
   543	    if stripped.startswith("```"):
   544	        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
   545	        stripped = re.sub(r"\s*```$", "", stripped)
   546	    return stripped.strip()
   547	
   548	
   549	def _normalize_gapfill_client(value: Any) -> str | None:
   550	    if not isinstance(value, str):
   551	        return None
   552	    text = value.strip()
   553	    if text.casefold() in _CLIENT_GAPFILL_UNCERTAIN:
   554	        return None
   555	    return text or None
   556	
   557	
   558	def _parse_client_gapfill_response(
   559	    raw_text: str,
   560	    *,
   561	    project_names: set[str],
   562	) -> dict[str, str | None]:
   563	    try:
   564	        payload = json.loads(_strip_json_fence(raw_text))
   565	    except json.JSONDecodeError:
   566	        return {}
   567	
   568	    if not isinstance(payload, dict):
   569	        return {}
   570	
   571	    expected_by_key = {_normalize_text(name): name for name in project_names}
   572	    parsed: dict[str, str | None] = {}
   573	    for raw_name, raw_client in payload.items():
   574	        if not isinstance(raw_name, str):
   575	            continue
   576	        project_name = expected_by_key.get(_normalize_text(raw_name))
   577	        if not project_name:
   578	            continue
   579	        parsed[project_name] = _normalize_gapfill_client(raw_client)
   580	    return parsed
   581	
   582	
   583	def _gapfill_missing_clients(candidates: list[tuple[_ProjectSeed, dict[str, Any]]]) -> None:
   584	    if not candidates:
   585	        return
   586	
   587	    from rebalance.ingest.config import get_gemini_api_key
   588	    from rebalance.ingest.querier import (
   589	        DEFAULT_GEMINI_MODEL,
   590	        _synthesize_with_fallback,
   591	    )
   592	
   593	    if not get_gemini_api_key():
   594	        return
   595	
   596	    prompt = _build_client_gapfill_prompt(candidates)
   597	    try:
   598	        synthesis, model_used = _synthesize_with_fallback(
   599	            prompt,
   600	            max_tokens=1024,
   601	            thinking_budget=0,
   602	        )
   603	    except Exception:
   604	        return
   605	    if model_used != DEFAULT_GEMINI_MODEL:
   606	        return
   607	
   608	    inferred = _parse_client_gapfill_response(
   609	        synthesis,
   610	        project_names={project["name"] for _, project in candidates},
   611	    )
   612	    for _seed, project in candidates:
   613	        client = inferred.get(project["name"])
   614	        if client:
   615	            project["custom_fields"]["client_inferred"] = client
   616	
   617	
   618	def _seed_to_project_row(seed: _ProjectSeed) -> dict[str, Any]:
   619	    name = _choose_seed_name(seed)
   620	    aliases = sorted(
   621	        {
   622	            alias
   623	            for alias in seed.aliases or set()
   624	            if alias
   625	            and alias != _normalize_text(name)
   626	            and len(alias) >= 2
   627	        }
   628	    )
   629	    calendar_aliases = sorted(label for label in (seed.calendar_labels or Counter()).keys() if label != name)
   630	    tags = ["inferred"]
   631	    if seed.repos:
   632	        tags.append("source:github")
   633	    if seed.calendar_event_count:
   634	        tags.append("source:calendar")
   635	    status = _seed_status(seed)
   636	    if status != "potential":
   637	        tags.append(f"status:{status}")
   638	
   639	    return {
   640	        "name": name,
   641	        "status": status,
   642	        "summary": _seed_summary(seed),
   643	        "value_level": None,
   644	        "priority_tier": None,
   645	        "risk_level": None,
   646	        "repos": sorted(seed.repos),
   647	        "tags": tags,
   648	        "custom_fields": {
   649	            "aliases": aliases,
   650	            "calendar_aliases": calendar_aliases,
   651	            "client_inferred": _infer_client(seed),
   652	            "provenance": "inferred",
   653	            "inference": {
   654	                "generated_by": INFERENCE_GENERATED_BY,
   655	                "github_repo_count": len(seed.repos),
   656	                "github_activity_score": seed.github_score,
   657	                "github_last_active_at": seed.github_last_active_at,
   658	                "calendar_event_count": seed.calendar_event_count,
   659	                "calendar_total_minutes": seed.calendar_total_minutes,
   660	                "calendar_last_event_at": seed.calendar_last_event_at,
   661	            },
   662	        },
   663	    }
   664	
   665	
   666	def _delete_stale_inferred_rows(database_path: Path, project_names: set[str]) -> int:
   667	    with db_connection(database_path, ensure_project_schema) as conn:
   668	        rows = conn.execute(
   669	            "SELECT name, custom_fields_json FROM project_registry"
   670	        ).fetchall()
   671	        stale_names: list[str] = [
   672	            row["name"]
   673	            for row in rows
   674	            if _is_inference_owned(row["custom_fields_json"]) and row["name"] not in project_names
   675	        ]
   676	
   677	        if stale_names:
   678	            conn.executemany("DELETE FROM project_registry WHERE name = ?", [(name,) for name in stale_names])
   679	            conn.commit()
   680	        return len(stale_names)
   681	
   682	
   683	def _partition_writable_rows(
   684	    database_path: Path, projects: list[dict[str, Any]]
   685	) -> tuple[list[dict[str, Any]], list[str]]:
   686	    """Split inferred rows into writable vs. curated-name collisions.
   687	
   688	    A name already present in project_registry WITHOUT the inference marker is
   689	    operator-curated state — inference must not touch it (the registry upsert
   690	    is keyed by name, so writing would clobber the curated row wholesale).
   691	    """
   692	    with db_connection(database_path, ensure_project_schema) as conn:
   693	        rows = conn.execute(
   694	            "SELECT name, custom_fields_json FROM project_registry"
   695	        ).fetchall()
   696	    curated_names = {
   697	        row["name"] for row in rows if not _is_inference_owned(row["custom_fields_json"])
   698	    }
   699	    writable = [p for p in projects if p["name"] not in curated_names]
   700	    skipped = sorted(p["name"] for p in projects if p["name"] in curated_names)
   701	    return writable, skipped
   702	
   703	
   704	def infer_project_registry(
   705	    database_path: Path,
   706	    *,
   707	    calendar_config: CalendarConfig | None = None,
   708	    calendar_days_back: int = 90,
   709	    calendar_days_forward: int = 14,
   710	) -> tuple[list[dict[str, Any]], InferenceSummary]:
   711	    config = calendar_config or CalendarConfig.load()
   712	    seeds = _build_seeds_from_github(database_path)
   713	    _apply_calendar_signal(
   714	        database_path,
   715	        seeds=seeds,
   716	        config=config,
   717	        days_back=calendar_days_back,
   718	        days_forward=calendar_days_forward,
   719	    )
   720	
   721	    projects: list[dict[str, Any]] = []
   722	    gapfill_candidates: list[tuple[_ProjectSeed, dict[str, Any]]] = []
   723	    for seed in seeds.values():
   724	        if not seed.repos and seed.calendar_event_count < 2:
   725	            continue
   726	        project = _seed_to_project_row(seed)
   727	        projects.append(project)
   728	        if project["custom_fields"].get("client_inferred") is None:
   729	            gapfill_candidates.append((seed, project))
   730	    _gapfill_missing_clients(gapfill_candidates)
   731	    projects.sort(key=lambda item: (item["status"] != "active", item["name"].casefold()))
   732	
   733	    summary = InferenceSummary(
   734	        inferred_count=len(projects),
   735	        github_backed_count=sum(1 for item in projects if item["repos"]),
   736	        calendar_only_count=sum(1 for item in projects if not item["repos"]),
   737	        updated_count=0,
   738	        deleted_stale_inferred_count=0,
   739	        project_names=[item["name"] for item in projects],
   740	    )
   741	    return projects, summary
   742	
   743	
   744	def sync_inferred_project_registry(
   745	    database_path: Path,
   746	    *,
   747	    calendar_config: CalendarConfig | None = None,
   748	    calendar_days_back: int = 90,
   749	    calendar_days_forward: int = 14,
   750	) -> InferenceSummary:
   751	    projects, summary = infer_project_registry(
   752	        database_path,
   753	        calendar_config=calendar_config,
   754	        calendar_days_back=calendar_days_back,
   755	        calendar_days_forward=calendar_days_forward,
   756	    )
   757	    # machine_owned contract: write only rows inference owns. Curated rows
   758	    # sharing a name are skipped (reported in the summary), never clobbered.
   759	    writable, skipped_curated = _partition_writable_rows(database_path, projects)
   760	    updated_count = sync_db(database_path, {"projects": writable})
   761	    deleted_count = _delete_stale_inferred_rows(database_path, set(summary.project_names))
   762	    return InferenceSummary(
   763	        inferred_count=summary.inferred_count,
   764	        github_backed_count=summary.github_backed_count,
   765	        calendar_only_count=summary.calendar_only_count,
   766	        updated_count=updated_count,
   767	        deleted_stale_inferred_count=deleted_count,
   768	        project_names=summary.project_names,
   769	        skipped_curated_count=len(skipped_curated),
   770	        skipped_curated_names=skipped_curated,
   771	    )
   772	
   773	
   774	# ---------------------------------------------------------------------------
   775	# GH-124: commit-threshold auto-promotion
   776	# ---------------------------------------------------------------------------
   777	
   778	
   779	def _count_operator_commits(conn: Any, repo_full_name: str, github_login: str) -> int:
   780	    """Count distinct full-SHA commits authored by the operator (or a known
   781	    cloud-agent bot acting on their behalf) in ``repo_full_name``.
   782	
   783	    Reuses ``pulse._author_filter_sql`` against ``github_commits.author_login``
   784	    rather than a raw git-email match — this is GitHub's own resolved identity
   785	    per commit, populated for every synced repo regardless of whether it has a
   786	    local clone. Cumulative all-time count, not a rolling window: this answers
   787	    "has the operator meaningfully started this repo," not "recently active."
   788	    """
   789	    from rebalance.ingest.pulse import CLOUD_AGENT_AUTHORS, _author_filter_sql
   790	
   791	    author_filter = _author_filter_sql("author_login")
   792	    row = conn.execute(
   793	        f"""
   794	        SELECT COUNT(DISTINCT sha) AS n
   795	        FROM github_commits
   796	        WHERE repo_full_name = ? AND {author_filter}
   797	        """,
   798	        (repo_full_name, github_login, *CLOUD_AGENT_AUTHORS),
   799	    ).fetchone()
   800	    return int(row["n"] or 0) if row else 0
   801	
   802	
   803	def _repo_to_promoted_row(repo_full_name: str, *, commit_count: int, threshold: int) -> dict[str, Any]:
   804	    """Build a machine-owned project_registry row for one auto-promoted repo.
   805	
   806	    Shape mirrors ``_seed_to_project_row`` (same table, same optional fields
   807	    left ``None`` for the operator to fill in later) but with a distinct
   808	    provenance marker so an auto-promoted row is self-describing.
   809	    """
   810	    name = repo_full_name.split("/", 1)[-1] or repo_full_name
   811	    return {
   812	        "name": name,
   813	        "status": "active",
   814	        "summary": f"Auto-promoted after {commit_count} operator commit(s) to {repo_full_name}.",
   815	        "value_level": None,
   816	        "priority_tier": None,
   817	        "risk_level": None,
   818	        "repos": [repo_full_name],
   819	        "tags": ["auto-promoted", "source:github"],
   820	        "custom_fields": {
   821	            "provenance": "auto_promoted",
   822	            "inference": {
   823	                "generated_by": COMMIT_THRESHOLD_GENERATED_BY,
   824	                "repo_full_name": repo_full_name,
   825	                "commit_count": commit_count,
   826	                "threshold": threshold,
   827	                "promoted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
   828	            },
   829	        },
   830	    }
   831	
   832	
   833	@dataclass
   834	class AutoPromoteSummary:
   835	    """Result of one ``sync_commit_threshold_promotions`` pass."""
   836	
   837	    enabled: bool
   838	    threshold: int
   839	    candidates_evaluated: int = 0
   840	    promoted: list[dict[str, Any]] = field(default_factory=list)
   841	    skipped_curated_names: list[str] = field(default_factory=list)
   842	
   843	    @property
   844	    def promoted_count(self) -> int:
   845	        return len(self.promoted)
   846	
   847	
   848	def sync_commit_threshold_promotions(database_path: Path) -> AutoPromoteSummary:
   849	    """GH-124: auto-promote a watched repo into ``project_registry`` once the
   850	    operator has authored enough commits to it.
   851	
   852	    Candidate pool = ``get_watched_repos()["auto_discovered"]`` — repos with
   853	    GitHub activity/push signal that are not already in ANY active project's
   854	    ``repos`` (curated or machine-owned), and ``github_ignored_repos`` already
   855	    excluded upstream by ``get_watched_repos``. A candidate promotes once its
   856	    operator-authored commit count (see ``_count_operator_commits``) reaches
   857	    ``auto_promote_commit_threshold``. A fork or starred-only repo with zero
   858	    operator commits never reaches the threshold, so no separate fork
   859	    detection is needed — the commit count IS the filter.
   860	
   861	    Writes only via the existing machine_owned partition/write path
   862	    (``_partition_writable_rows`` / ``sync_db``) — a curated row sharing the
   863	    derived name is skipped, never clobbered, exactly like
   864	    ``sync_inferred_project_registry``.
   865	    """
   866	    from rebalance.ingest.config import get_auto_promote_config, get_pulse_config
   867	    from rebalance.ingest.index_ops import get_watched_repos
   868	
   869	    auto_promote_config = get_auto_promote_config()
   870	    threshold = auto_promote_config["auto_promote_commit_threshold"]
   871	    if not auto_promote_config["auto_promote_enabled"]:
   872	        return AutoPromoteSummary(enabled=False, threshold=threshold)
   873	
   874	    github_login = get_pulse_config().get("github_login")
   875	    if not github_login:
   876	        # No identity to match commits against — nothing is promotable.
   877	        return AutoPromoteSummary(enabled=True, threshold=threshold)
   878	
   879	    candidates = get_watched_repos(database_path)["auto_discovered"]
   880	
   881	    promoted_rows: list[dict[str, Any]] = []
   882	    with db_connection(database_path, ensure_github_schema) as conn:
   883	        for repo_full_name in candidates:
   884	            commit_count = _count_operator_commits(conn, repo_full_name, github_login)
   885	            if commit_count >= threshold:
   886	                promoted_rows.append(
   887	                    _repo_to_promoted_row(repo_full_name, commit_count=commit_count, threshold=threshold)
   888	                )
   889	
   890	    writable, skipped_curated = _partition_writable_rows(database_path, promoted_rows)
   891	    if writable:
   892	        sync_db(database_path, {"projects": writable})
   893	        from rebalance.ingest.auth_log import log_project_auto_promoted
   894	
   895	        for row in writable:
   896	            inference = row["custom_fields"]["inference"]
   897	            log_project_auto_promoted(
   898	                inference["repo_full_name"],
   899	                project_name=row["name"],
   900	                commit_count=inference["commit_count"],
   901	                threshold=inference["threshold"],
   902	            )
   903	
   904	    return AutoPromoteSummary(
   905	        enabled=True,
   906	        threshold=threshold,
   907	        candidates_evaluated=len(candidates),
   908	        promoted=writable,
   909	        skipped_curated_names=skipped_curated,
   910	    )

exec
/bin/zsh -lc "nl -ba src/rebalance/ingest/registry.py | sed -n '1,260p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
     1	from __future__ import annotations
     2	
     3	import json
     4	import re
     5	from pathlib import Path
     6	from typing import Any
     7	
     8	import yaml
     9	from pydantic import BaseModel, Field
    10	
    11	
    12	class Project(BaseModel):
    13	    name: str
    14	    status: str = "active"
    15	    summary: str = ""
    16	    repos: list[str] = Field(default_factory=list)
    17	    # When true, every repo under ``repos`` is an EXTERNAL repo to monitor for
    18	    # everyone's activity (commits/PRs), not the operator's own work. Watched
    19	    # externals enter the watched set and get a whole-repo github_activity rollup
    20	    # (see rebalance.ingest.github_watch). A dedicated "Watched — …" project with
    21	    # external: true is the intended container.
    22	    external: bool = False
    23	    # Where this project entered the system (lifecycle contract, Phase 5):
    24	    # "remote-activity" (GitHub activity discovery), "vault-note" (vault title
    25	    # discovery), "inferred" (activity inference); "local-scan" is reserved for
    26	    # the Phase 6 git-pulse promotion. "" = legacy/operator-entered rows.
    27	    provenance: str = ""
    28	    obsidian_folder: str | None = None
    29	    tags: list[str] = Field(default_factory=list)
    30	    value_level: str | None = None
    31	    priority_tier: int | None = None
    32	    risk_level: str | None = None
    33	    custom_fields: dict[str, Any] = Field(default_factory=dict)
    34	    computed: dict[str, Any] = Field(default_factory=dict)
    35	    last_activity_at: str | None = None  # ISO 8601; used for activity-based filtering
    36	
    37	
    38	class Registry(BaseModel):
    39	    active_projects: list[Project] = Field(default_factory=list)
    40	    # Activity-based potential project segmentation
    41	    most_likely_active_projects: list[Project] = Field(default_factory=list)  # Activity in last 14 days
    42	    semi_active_projects: list[Project] = Field(default_factory=list)  # Activity 15-30 days ago
    43	    dormant_projects: list[Project] = Field(default_factory=list)  # Activity 31+ days ago
    44	    # Legacy fallback for projects without detectable activity
    45	    potential_projects: list[Project] = Field(default_factory=list)
    46	    archived_projects: list[Project] = Field(default_factory=list)
    47	
    48	
    49	YAML_BLOCK_PATTERN = re.compile(r"```ya?ml\s*(.*?)```", re.DOTALL | re.IGNORECASE)
    50	
    51	
    52	def _default_registry_markdown() -> str:
    53	    payload = Registry().model_dump(mode="json")
    54	    yaml_content = yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)
    55	    return f"""# Project Registry
    56	
    57	Canonical project list for rebalance ingest and scoring.
    58	
    59	Sections:
    60	- `active_projects`: currently tracked and scored
    61	- `most_likely_active_projects`: GitHub activity last 14 days
    62	- `semi_active_projects`: GitHub activity 15-30 days ago
    63	- `dormant_projects`: GitHub activity 31+ days ago
    64	- `potential_projects`: candidates with no activity signals (vault-only discoveries)
    65	- `archived_projects`: historical records
    66	
    67	```yaml
    68	{yaml_content}```
    69	"""
    70	
    71	
    72	def _extract_yaml_block(markdown: str) -> dict[str, Any]:
    73	    match = YAML_BLOCK_PATTERN.search(markdown)
    74	    if not match:
    75	        return Registry().model_dump(mode="json")
    76	    block = match.group(1).strip()
    77	    parsed = yaml.safe_load(block) or {}
    78	    if not isinstance(parsed, dict):
    79	        return Registry().model_dump(mode="json")
    80	    return parsed
    81	
    82	
    83	def read_registry(registry_path: Path) -> Registry:
    84	    """Pure read: parse the registry file, or return an empty Registry when
    85	    it doesn't exist. Never touches the filesystem — the right call for
    86	    read-only paths (discovery) where creating the registry file would lie
    87	    to the setup-status contract (`registry_exists` flipping done before any
    88	    confirmation)."""
    89	    if not registry_path.exists():
    90	        return Registry()
    91	    raw = registry_path.read_text(encoding="utf-8")
    92	    parsed = _extract_yaml_block(raw)
    93	    return Registry.model_validate(parsed)
    94	
    95	
    96	def load_registry(registry_path: Path) -> Registry:
    97	    """Read the registry, creating the default file first when missing.
    98	
    99	    Write-path variant: only confirmation-gated flows should call this —
   100	    read-only paths use :func:`read_registry`."""
   101	    if not registry_path.exists():
   102	        registry_path.parent.mkdir(parents=True, exist_ok=True)
   103	        registry_path.write_text(_default_registry_markdown(), encoding="utf-8")
   104	    return read_registry(registry_path)
   105	
   106	
   107	def save_registry(registry_path: Path, registry: Registry) -> None:
   108	    payload = registry.model_dump(mode="json")
   109	    yaml_content = yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)
   110	    content = f"""# Project Registry
   111	
   112	Canonical project list for rebalance ingest and scoring.
   113	
   114	Sections:
   115	- `active_projects`: currently tracked and scored
   116	- `most_likely_active_projects`: GitHub activity last 14 days
   117	- `semi_active_projects`: GitHub activity 15-30 days ago
   118	- `dormant_projects`: GitHub activity 31+ days ago
   119	- `potential_projects`: candidates with no activity signals (vault-only discoveries)
   120	- `archived_projects`: historical records
   121	
   122	```yaml
   123	{yaml_content}```
   124	"""
   125	    registry_path.parent.mkdir(parents=True, exist_ok=True)
   126	    registry_path.write_text(content, encoding="utf-8")
   127	
   128	
   129	def _registry_to_projection(registry: Registry) -> dict[str, Any]:
   130	    projects = []
   131	    for project in registry.active_projects:
   132	        # Persist the typed ``external`` flag inside custom_fields_json so it
   133	        # round-trips through the project_registry table without a schema column
   134	        # (get_projects already decodes custom_fields, and read paths that open
   135	        # via ensure_project_schema without running migrations keep working).
   136	        custom_fields = dict(project.custom_fields)
   137	        if project.external:
   138	            custom_fields["external"] = True
   139	        # Same pattern as ``external``: provenance rides in custom_fields_json
   140	        # so it round-trips through the fixed project_registry columns.
   141	        if project.provenance:
   142	            custom_fields["provenance"] = project.provenance
   143	        projects.append(
   144	            {
   145	                "name": project.name,
   146	                "summary": project.summary,
   147	                "status": project.status,
   148	                "value_level": project.value_level,
   149	                "priority_tier": project.priority_tier,
   150	                "risk_level": project.risk_level,
   151	                "repos": project.repos,
   152	                "obsidian_folder": project.obsidian_folder,
   153	                "tags": project.tags,
   154	                "custom_fields": custom_fields,
   155	            }
   156	        )
   157	    return {"projects": projects}
   158	
   159	
   160	def write_projection(projects_yaml_path: Path, projection: dict[str, Any]) -> None:
   161	    projects_yaml_path.parent.mkdir(parents=True, exist_ok=True)
   162	    projects_yaml_path.write_text(yaml.safe_dump(projection, sort_keys=False, allow_unicode=False), encoding="utf-8")
   163	
   164	
   165	def sync_db(database_path: Path, projection: dict[str, Any]) -> int:
   166	    from rebalance.ingest.db import db_connection, ensure_project_schema
   167	
   168	    rows = projection.get("projects", [])
   169	    with db_connection(database_path, ensure_project_schema) as conn:
   170	        for project in rows:
   171	            conn.execute(
   172	                """
   173	                INSERT INTO project_registry (
   174	                    name, status, summary, value_level, priority_tier, risk_level,
   175	                    repos_json, tags_json, custom_fields_json
   176	                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
   177	                ON CONFLICT(name) DO UPDATE SET
   178	                    status=excluded.status,
   179	                    summary=excluded.summary,
   180	                    value_level=excluded.value_level,
   181	                    priority_tier=excluded.priority_tier,
   182	                    risk_level=excluded.risk_level,
   183	                    repos_json=excluded.repos_json,
   184	                    tags_json=excluded.tags_json,
   185	                    custom_fields_json=excluded.custom_fields_json
   186	                """,
   187	                (
   188	                    project.get("name"),
   189	                    project.get("status"),
   190	                    project.get("summary", ""),
   191	                    project.get("value_level"),
   192	                    project.get("priority_tier"),
   193	                    project.get("risk_level"),
   194	                    json.dumps(project.get("repos", [])),
   195	                    json.dumps(project.get("tags", [])),
   196	                    json.dumps(project.get("custom_fields", {})),
   197	                ),
   198	            )
   199	        conn.commit()
   200	    return len(rows)
   201	
   202	
   203	def _push_from_projection(registry: Registry, projects_yaml_path: Path) -> Registry:
   204	    if not projects_yaml_path.exists():
   205	        return registry
   206	    raw = yaml.safe_load(projects_yaml_path.read_text(encoding="utf-8")) or {}
   207	    projects = raw.get("projects", []) if isinstance(raw, dict) else []
   208	
   209	    transformed: list[Project] = []
   210	    for item in projects:
   211	        if not isinstance(item, dict):
   212	            continue
   213	        custom_fields = dict(item.get("custom_fields", {}) or {})
   214	        external = bool(item.get("external") or custom_fields.pop("external", False))
   215	        # Like external: provenance rides custom_fields in the projection and
   216	        # must be lifted back to the typed field on push, or the round-trip
   217	        # desyncs the model from its custom_fields copy.
   218	        provenance = str(item.get("provenance") or custom_fields.pop("provenance", "") or "")
   219	        transformed.append(
   220	            Project(
   221	                name=str(item.get("name", "")).strip(),
   222	                status=str(item.get("status", "active")),
   223	                summary=str(item.get("summary", "")),
   224	                repos=list(item.get("repos", []) or []),
   225	                external=external,
   226	                provenance=provenance,
   227	                obsidian_folder=item.get("obsidian_folder"),
   228	                tags=list(item.get("tags", []) or []),
   229	                value_level=item.get("value_level"),
   230	                priority_tier=item.get("priority_tier"),
   231	                risk_level=item.get("risk_level"),
   232	                custom_fields=custom_fields,
   233	            )
   234	        )
   235	
   236	    registry.active_projects = transformed
   237	    return registry
   238	
   239	
   240	def sync_registry(mode: str, registry_path: Path, projects_yaml_path: Path, database_path: Path) -> str:
   241	    normalized_mode = mode.strip().lower()
   242	    if normalized_mode not in {"pull", "push", "check"}:
   243	        raise ValueError("mode must be one of: pull, push, check")
   244	
   245	    registry = load_registry(registry_path)
   246	
   247	    if normalized_mode == "push":
   248	        updated_registry = _push_from_projection(registry=registry, projects_yaml_path=projects_yaml_path)
   249	        save_registry(registry_path=registry_path, registry=updated_registry)
   250	        return f"Sync push complete: registry updated from {projects_yaml_path}"
   251	
   252	    projection = _registry_to_projection(registry)
   253	    projection_text = yaml.safe_dump(projection, sort_keys=False, allow_unicode=False)
   254	
   255	    if normalized_mode == "check":
   256	        existing = projects_yaml_path.read_text(encoding="utf-8") if projects_yaml_path.exists() else ""
   257	        status = "in-sync" if existing.strip() == projection_text.strip() else "out-of-sync"
   258	        return (
   259	            f"Sync check: {status}; active_projects={len(registry.active_projects)}; "
   260	            f"potential_projects={len(registry.potential_projects)}"

exec
/bin/zsh -lc "nl -ba src/rebalance/ingest/pulse.py | sed -n '1,260p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
     1	"""Hourly pulse: render today's + yesterday's activity into a markdown
     2	status page and publish it to a private git repo.
     3	
     4	Reusable design — every per-user value (Slack ID, GitHub login, target repo
     5	path, timezone) comes from ``temp/rbos.config``. Other people forking this
     6	repo can populate their own config and point at their own private pulse repo;
     7	no per-user data is hardcoded here.
     8	
     9	Data sources:
    10	  - Vault edits:        ``vault_files.last_modified``
    11	  - GitHub commits:     ``github_commits`` (authored by ``github_login``)
    12	  - GitHub issues/PRs:  ``github_items`` created or updated today by user
    13	  - GitHub comments:    ``github_comments`` posted by user
    14	  - Sleuth reminders:   assigned to the operator OR assigned by the operator
    15	  - Calendar events:    ``calendar_events`` (today's upcoming)
    16	  - Assigned issues:    GitHub search API, fetched fresh each run
    17	"""
    18	
    19	from __future__ import annotations
    20	
    21	import hashlib
    22	import json
    23	import subprocess
    24	import time
    25	import urllib.error
    26	import urllib.parse
    27	import urllib.request
    28	from dataclasses import dataclass, field
    29	from datetime import datetime, timedelta, timezone
    30	from pathlib import Path
    31	from typing import Any
    32	from zoneinfo import ZoneInfo
    33	
    34	from rebalance.repair import RepairFSM, RepairResult, RepairStatus
    35	from rebalance.ingest.agent_tags import classify as classify_source
    36	from rebalance.ingest.calendar_config import OPERATOR_CALENDAR_ID
    37	from rebalance.ingest.calendar_helpers import calendar_dt_utc, normalize_aware_utc
    38	from rebalance.ingest.config import get_github_token, get_pulse_config
    39	from rebalance.ingest.db import db_connection
    40	from rebalance.ingest.slack_users import compact_sleuth_reminder
    41	from rebalance.tz_utils import local_tz, parse_utc_iso
    42	
    43	
    44	# Author logins of known cloud-agent bots. Mirrors agent_tags.py — kept here
    45	# for SQL-side prefiltering so we don't fetch every bot row in the DB.
    46	CLOUD_AGENT_AUTHORS: tuple[str, ...] = (
    47	    "lovable-dev[bot]",
    48	    "lovable[bot]",
    49	    "chatgpt-codex-connector[bot]",
    50	    "codex-bot[bot]",
    51	    "claude[bot]",
    52	    "claude-bot[bot]",
    53	)
    54	
    55	
    56	def _author_filter_sql(column: str) -> str:
    57	    """SQL fragment matching the user OR any cloud-agent bot author."""
    58	    placeholders = ", ".join("?" for _ in CLOUD_AGENT_AUTHORS)
    59	    return f"(LOWER({column}) = LOWER(?) OR {column} IN ({placeholders}))"
    60	
    61	
    62	GITHUB_API_ROOT = "https://api.github.com"
    63	
    64	
    65	# ---------------------------------------------------------------------------
    66	# Time helpers
    67	# ---------------------------------------------------------------------------
    68	
    69	
    70	def _resolve_timezone(name: str | None) -> ZoneInfo:
    71	    if name:
    72	        return ZoneInfo(name)
    73	    return local_tz()
    74	
    75	
    76	def _local_day_bounds(tz: ZoneInfo, now: datetime | None = None) -> tuple[datetime, datetime, datetime]:
    77	    """Return (yesterday_start, today_start, tomorrow_start) in *tz*."""
    78	    now = now or datetime.now(tz)
    79	    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    80	    yesterday_start = today_start - timedelta(days=1)
    81	    tomorrow_start = today_start + timedelta(days=1)
    82	    return yesterday_start, today_start, tomorrow_start
    83	
    84	
    85	def _parse_iso(value: str | None) -> datetime | None:
    86	    return parse_utc_iso(value)
    87	
    88	
    89	def _in_window(value: str | None, start: datetime, end: datetime) -> bool:
    90	    """True if *value* (ISO string with TZ) falls in [start, end)."""
    91	    parsed = parse_utc_iso(value)
    92	    if parsed is None:
    93	        return False
    94	    return start <= parsed < end
    95	
    96	
    97	def _utc_iso_floor(dt: datetime) -> str:
    98	    """Return *dt* as a UTC ISO 8601 string suitable for >= comparisons."""
    99	    return dt.astimezone(timezone.utc).isoformat()
   100	
   101	
   102	# ---------------------------------------------------------------------------
   103	# Data gathering
   104	# ---------------------------------------------------------------------------
   105	
   106	
   107	@dataclass
   108	class DayActivity:
   109	    label: str  # "today" or "yesterday"
   110	    vault_edits: list[dict[str, Any]] = field(default_factory=list)
   111	    gh_commits: list[dict[str, Any]] = field(default_factory=list)
   112	    gh_items: list[dict[str, Any]] = field(default_factory=list)
   113	    gh_comments: list[dict[str, Any]] = field(default_factory=list)
   114	    sleuth_activity: list[dict[str, Any]] = field(default_factory=list)
   115	
   116	
   117	@dataclass
   118	class PulseSnapshot:
   119	    generated_at: datetime
   120	    timezone_name: str
   121	    github_login: str
   122	    today: DayActivity
   123	    yesterday: DayActivity
   124	    today_calendar_upcoming: list[dict[str, Any]]
   125	    assigned_issues: list[dict[str, Any]]  # last 7 days, sorted today-first
   126	    notes: list[str]  # diagnostics / soft-warnings (e.g. "search rate-limited")
   127	    # Whole-repo (all-author) activity today on external/watched repos — the repos
   128	    # the operator monitors but doesn't author. Empty when none are configured.
   129	    watched_repos: list[dict[str, Any]] = field(default_factory=list)
   130	
   131	
   132	def _query_day_activity(
   133	    conn: Any,
   134	    *,
   135	    label: str,
   136	    start: datetime,
   137	    end: datetime,
   138	    github_login: str,
   139	    slack_user_id: str | None,
   140	) -> DayActivity:
   141	    activity = DayActivity(label=label)
   142	
   143	    # Pre-filter by a generous UTC window in SQL, refine in Python by tz-aware compare.
   144	    sql_floor = _utc_iso_floor(start - timedelta(hours=2))
   145	
   146	    rows = conn.execute(
   147	        """
   148	        SELECT rel_path, title, last_modified
   149	        FROM vault_files
   150	        WHERE last_modified >= ?
   151	        ORDER BY last_modified DESC
   152	        """,
   153	        (sql_floor,),
   154	    ).fetchall()
   155	    for r in rows:
   156	        if _in_window(r["last_modified"], start, end):
   157	            activity.vault_edits.append({
   158	                "rel_path": r["rel_path"],
   159	                "title": r["title"] or r["rel_path"],
   160	                "last_modified": r["last_modified"],
   161	            })
   162	
   163	    commit_filter = _author_filter_sql("c.author_login")
   164	    rows = conn.execute(
   165	        f"""
   166	        SELECT c.repo_full_name, c.sha, c.message, c.committed_at, c.html_url,
   167	               c.author_login, gi.head_ref
   168	        FROM github_commits c
   169	        LEFT JOIN github_items gi
   170	          ON gi.repo_full_name = c.repo_full_name
   171	         AND gi.item_type = c.item_type
   172	         AND gi.number = c.item_number
   173	        WHERE c.committed_at >= ?
   174	          AND {commit_filter}
   175	        ORDER BY c.committed_at DESC
   176	        """,
   177	        (sql_floor, github_login, *CLOUD_AGENT_AUTHORS),
   178	    ).fetchall()
   179	    for r in rows:
   180	        if _in_window(r["committed_at"], start, end):
   181	            first_line = (r["message"] or "").splitlines()[0] if r["message"] else ""
   182	            tag = classify_source(
   183	                branch=r["head_ref"],
   184	                author_login=r["author_login"],
   185	                commit_message=r["message"],
   186	            )
   187	            activity.gh_commits.append({
   188	                "repo": r["repo_full_name"],
   189	                "sha": r["sha"][:7] if r["sha"] else "",
   190	                "subject": first_line[:160],
   191	                "committed_at": r["committed_at"],
   192	                "html_url": r["html_url"] or "",
   193	                "author_login": r["author_login"] or "",
   194	                "source_tag": tag,
   195	            })
   196	
   197	    item_filter = _author_filter_sql("author_login")
   198	    rows = conn.execute(
   199	        f"""
   200	        SELECT repo_full_name, item_type, number, title, state, html_url,
   201	               created_at, updated_at, author_login, head_ref, body
   202	        FROM github_items
   203	        WHERE (created_at >= ? OR updated_at >= ?)
   204	          AND (
   205	                {item_filter}
   206	                OR head_ref LIKE 'claude/%'
   207	                OR head_ref LIKE 'codex/%'
   208	                OR head_ref LIKE 'lovable-%'
   209	                OR head_ref LIKE 'lovable/%'
   210	          )
   211	        ORDER BY COALESCE(updated_at, created_at) DESC
   212	        """,
   213	        (sql_floor, sql_floor, github_login, *CLOUD_AGENT_AUTHORS),
   214	    ).fetchall()
   215	    for r in rows:
   216	        created_in = _in_window(r["created_at"], start, end)
   217	        updated_in = _in_window(r["updated_at"], start, end)
   218	        if not (created_in or updated_in):
   219	            continue
   220	        tag = classify_source(
   221	            branch=r["head_ref"],
   222	            author_login=r["author_login"],
   223	            commit_message=r["body"] or "",
   224	        )
   225	        activity.gh_items.append({
   226	            "repo": r["repo_full_name"],
   227	            "item_type": r["item_type"],
   228	            "number": r["number"],
   229	            "title": r["title"] or "",
   230	            "state": r["state"] or "",
   231	            "html_url": r["html_url"] or "",
   232	            "created_at": r["created_at"],
   233	            "updated_at": r["updated_at"],
   234	            "author_login": r["author_login"] or "",
   235	            "head_ref": r["head_ref"] or "",
   236	            "is_new": created_in,
   237	            "source_tag": tag,
   238	        })
   239	
   240	    comment_filter = _author_filter_sql("author_login")
   241	    rows = conn.execute(
   242	        f"""
   243	        SELECT repo_full_name, item_type, item_number, comment_type, body,
   244	               html_url, created_at, author_login
   245	        FROM github_comments
   246	        WHERE created_at >= ?
   247	          AND {comment_filter}
   248	        ORDER BY created_at DESC
   249	        """,
   250	        (sql_floor, github_login, *CLOUD_AGENT_AUTHORS),
   251	    ).fetchall()
   252	    for r in rows:
   253	        if _in_window(r["created_at"], start, end):
   254	            body = (r["body"] or "").strip().replace("\r", "")
   255	            preview = body.split("\n", 1)[0][:160]
   256	            tag = classify_source(
   257	                author_login=r["author_login"],
   258	                commit_message=body,
   259	            )
   260	            activity.gh_comments.append({

exec
/bin/zsh -lc "nl -ba src/rebalance/ingest/db/schema.py | sed -n '470,530p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
   470	            created_at          TEXT,
   471	            updated_at          TEXT,
   472	            fetched_at          TEXT    NOT NULL,
   473	            UNIQUE(repo_full_name, comment_type, github_comment_id) ON CONFLICT REPLACE
   474	        )
   475	    """)
   476	    conn.execute(
   477	        "CREATE INDEX IF NOT EXISTS idx_github_comments_item "
   478	        "ON github_comments(repo_full_name, item_type, item_number)"
   479	    )
   480	
   481	    conn.execute("""
   482	        CREATE TABLE IF NOT EXISTS github_commits (
   483	            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
   484	            repo_full_name      TEXT    NOT NULL,
   485	            item_type           TEXT    NOT NULL,
   486	            item_number         INTEGER NOT NULL,
   487	            sha                 TEXT    NOT NULL,
   488	            author_login        TEXT,
   489	            message             TEXT,
   490	            committed_at        TEXT,
   491	            html_url            TEXT,
   492	            fetched_at          TEXT    NOT NULL,
   493	            UNIQUE(repo_full_name, item_type, item_number, sha) ON CONFLICT REPLACE
   494	        )
   495	    """)
   496	    conn.execute(
   497	        "CREATE INDEX IF NOT EXISTS idx_github_commits_item "
   498	        "ON github_commits(repo_full_name, item_type, item_number)"
   499	    )
   500	
   501	    conn.execute("""
   502	        CREATE TABLE IF NOT EXISTS github_check_runs (
   503	            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
   504	            repo_full_name      TEXT    NOT NULL,
   505	            item_type           TEXT    NOT NULL,
   506	            item_number         INTEGER NOT NULL,
   507	            head_sha            TEXT,
   508	            name                TEXT    NOT NULL,
   509	            status              TEXT,
   510	            conclusion          TEXT,
   511	            details_url         TEXT,
   512	            started_at          TEXT,
   513	            completed_at        TEXT,
   514	            fetched_at          TEXT    NOT NULL,
   515	            UNIQUE(repo_full_name, item_type, item_number, head_sha, name) ON CONFLICT REPLACE
   516	        )
   517	    """)
   518	    conn.execute(
   519	        "CREATE INDEX IF NOT EXISTS idx_github_checks_item "
   520	        "ON github_check_runs(repo_full_name, item_type, item_number)"
   521	    )
   522	
   523	    conn.execute("""
   524	        CREATE TABLE IF NOT EXISTS github_links (
   525	            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
   526	            repo_full_name      TEXT    NOT NULL,
   527	            source_type         TEXT    NOT NULL,
   528	            source_number       INTEGER NOT NULL,
   529	            target_type         TEXT    NOT NULL,
   530	            target_number       INTEGER NOT NULL,

exec
/bin/zsh -lc "nl -ba src/rebalance/ingest/db/github.py | sed -n '220,390p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
   220	    *values*: repo_full_name, source_type, source_number, target_type,
   221	    target_number, link_kind.
   222	    """
   223	    conn.execute(
   224	        """
   225	        INSERT OR REPLACE INTO github_links
   226	            (repo_full_name, source_type, source_number, target_type, target_number, link_kind)
   227	        VALUES (?, ?, ?, ?, ?, ?)
   228	        """,
   229	        values,
   230	    )
   231	
   232	
   233	def upsert_commit(conn: sqlite3.Connection, values: tuple) -> None:
   234	    """Insert-or-replace one ``github_commits`` row.
   235	
   236	    *values*: repo_full_name, item_type, item_number, sha, author_login,
   237	    message, committed_at, html_url, fetched_at.
   238	    """
   239	    conn.execute(
   240	        """
   241	        INSERT OR REPLACE INTO github_commits
   242	            (repo_full_name, item_type, item_number, sha, author_login,
   243	             message, committed_at, html_url, fetched_at)
   244	        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
   245	        """,
   246	        values,
   247	    )
   248	
   249	
   250	def upsert_check_run(conn: sqlite3.Connection, values: tuple) -> None:
   251	    """Insert-or-replace one ``github_check_runs`` row.
   252	
   253	    *values*: repo_full_name, item_type, item_number, head_sha, name, status,
   254	    conclusion, details_url, started_at, completed_at, fetched_at.
   255	    """
   256	    conn.execute(
   257	        """
   258	        INSERT OR REPLACE INTO github_check_runs
   259	            (repo_full_name, item_type, item_number, head_sha, name, status,
   260	             conclusion, details_url, started_at, completed_at, fetched_at)
   261	        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
   262	        """,
   263	        values,
   264	    )
   265	
   266	
   267	def delete_repo_table(
   268	    conn: sqlite3.Connection, table: str, repo_full_name: str
   269	) -> None:
   270	    """Delete every row of *table* for an exact ``repo_full_name`` match.
   271	
   272	    Used to clear branches/labels/milestones/releases before a fresh sync.
   273	    *table* must be a trusted constant — it is interpolated, not bound.
   274	    """
   275	    conn.execute(f"DELETE FROM {table} WHERE repo_full_name = ?", (repo_full_name,))
   276	
   277	
   278	# ---------------------------------------------------------------------------
   279	# Document corpus
   280	# ---------------------------------------------------------------------------
   281	
   282	
   283	def insert_github_document(
   284	    conn: sqlite3.Connection,
   285	    *,
   286	    repo_full_name: str,
   287	    source_type: str,
   288	    source_number: int,
   289	    doc_type: str,
   290	    source_key: str,
   291	    title: str,
   292	    body: str,
   293	    content_hash: str,
   294	    updated_at: str,
   295	    fetched_at: str,
   296	) -> int:
   297	    """Insert one ``github_documents`` row (``embedded_hash`` starts NULL).
   298	
   299	    Returns the new row id. Content hashing is the caller's job — pass the
   300	    precomputed *content_hash*.
   301	    """
   302	    conn.execute(
   303	        """
   304	        INSERT INTO github_documents
   305	            (repo_full_name, source_type, source_number, doc_type, source_key,
   306	             title, body, content_hash, embedded_hash, updated_at, fetched_at)
   307	        VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
   308	        """,
   309	        (
   310	            repo_full_name,
   311	            source_type,
   312	            source_number,
   313	            doc_type,
   314	            source_key,
   315	            title,
   316	            body,
   317	            content_hash,
   318	            updated_at,
   319	            fetched_at,
   320	        ),
   321	    )
   322	    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
   323	
   324	
   325	def delete_item_children(
   326	    conn: sqlite3.Connection,
   327	    repo_full_name: str,
   328	    item_type: str,
   329	    item_number: int,
   330	) -> None:
   331	    """Delete one item's derived rows (documents, embeddings, comments,
   332	    commits, check runs, links) before the item is re-synced."""
   333	    doc_ids = [
   334	        row["id"]
   335	        for row in conn.execute(
   336	            """
   337	            SELECT id
   338	            FROM github_documents
   339	            WHERE repo_full_name = ? AND source_type = ? AND source_number = ?
   340	            """,
   341	            (repo_full_name, item_type, item_number),
   342	        ).fetchall()
   343	    ]
   344	    if doc_ids:
   345	        conn.executemany(
   346	            "DELETE FROM github_embeddings WHERE doc_id = ?",
   347	            [(doc_id,) for doc_id in doc_ids],
   348	        )
   349	    conn.execute(
   350	        """
   351	        DELETE FROM github_documents
   352	        WHERE repo_full_name = ? AND source_type = ? AND source_number = ?
   353	        """,
   354	        (repo_full_name, item_type, item_number),
   355	    )
   356	    conn.execute(
   357	        """
   358	        DELETE FROM github_comments
   359	        WHERE repo_full_name = ? AND item_type = ? AND item_number = ?
   360	        """,
   361	        (repo_full_name, item_type, item_number),
   362	    )
   363	    conn.execute(
   364	        """
   365	        DELETE FROM github_commits
   366	        WHERE repo_full_name = ? AND item_type = ? AND item_number = ?
   367	        """,
   368	        (repo_full_name, item_type, item_number),
   369	    )
   370	    conn.execute(
   371	        """
   372	        DELETE FROM github_check_runs
   373	        WHERE repo_full_name = ? AND item_type = ? AND item_number = ?
   374	        """,
   375	        (repo_full_name, item_type, item_number),
   376	    )
   377	    conn.execute(
   378	        """
   379	        DELETE FROM github_links
   380	        WHERE repo_full_name = ? AND source_type = ? AND source_number = ?
   381	        """,
   382	        (repo_full_name, item_type, item_number),
   383	    )
   384	
   385	
   386	def search_github_documents(
   387	    conn: sqlite3.Connection,
   388	    query_vec: bytes,
   389	    top_k: int,
   390	    repo_full_name: str = "",

exec
/bin/zsh -lc 'rg -n "def get_watched_repos|auto_discovered|project_registry|github_ignored_repos|external_repos|watched" src/rebalance/ingest/index_ops.py src/rebalance/ingest/github_watch.py src/rebalance/ingest/*.py' in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
src/rebalance/ingest/ask_self_scan.py:14:watched repos have a queryable local brain, and on which machine?".
src/rebalance/ingest/ask_self_scan.py:70:    repo_full_name: str | None  # owner/repo — the bridge to watched repos
src/rebalance/ingest/ask_self_scan.py:379:    cross-referenced against the GitHub-identity watched set.
src/rebalance/ingest/ask_self_scan.py:381:    from rebalance.ingest.index_ops import get_watched_repos
src/rebalance/ingest/ask_self_scan.py:384:    watched = {r.lower() for r in get_watched_repos(database_path).get("watched", [])}
src/rebalance/ingest/ask_self_scan.py:392:            "watched": full.lower() in watched if full else False,
src/rebalance/ingest/ask_self_scan.py:401:            "watched": sum(1 for r in enriched if r["watched"]),
src/rebalance/ingest/diagnose.py:2:Repo diagnostics — one tool to answer "is this repo watched?", "why isn't
src/rebalance/ingest/diagnose.py:5:Composes the existing watched-repos / sync-status / ignore-list machinery
src/rebalance/ingest/diagnose.py:20:    get_github_ignored_repos,
src/rebalance/ingest/diagnose.py:145:    """Walk the watched-repos + sync funnel for a single repo and report.
src/rebalance/ingest/diagnose.py:161:    ignored = set(get_github_ignored_repos())
src/rebalance/ingest/diagnose.py:184:    watched = (in_registry or in_recent_activity) and not is_ignored
src/rebalance/ingest/diagnose.py:187:    if not watched:
src/rebalance/ingest/diagnose.py:189:            monitoring_reason = f"{repo_norm} is on github_ignored_repos"
src/rebalance/ingest/diagnose.py:201:            monitoring_reason = "not in watched set"
src/rebalance/ingest/diagnose.py:285:            if not watched:
src/rebalance/ingest/diagnose.py:287:                    "repo is not watched, so its commits are never ingested"
src/rebalance/ingest/diagnose.py:291:                    "repo is watched but has never been synced — "
src/rebalance/ingest/diagnose.py:338:                if not watched:
src/rebalance/ingest/diagnose.py:340:                        "repo is not watched, so its PRs are never ingested"
src/rebalance/ingest/diagnose.py:344:                        "repo is watched but has never been synced — "
src/rebalance/ingest/diagnose.py:351:                        "sync window, or the repo wasn't watched at the time of the "
src/rebalance/ingest/diagnose.py:375:        verdict = "not_watched_ignored"
src/rebalance/ingest/diagnose.py:379:        verdict = "not_watched_inactive_project"
src/rebalance/ingest/diagnose.py:385:    elif not watched:
src/rebalance/ingest/diagnose.py:386:        verdict = "not_watched_no_signal"
src/rebalance/ingest/diagnose.py:388:            f"{repo_norm} is not watched: not in any active project's repos and no "
src/rebalance/ingest/diagnose.py:395:        verdict = "watched_never_synced"
src/rebalance/ingest/diagnose.py:396:        summary = f"{repo_norm} is watched but has never been synced."
src/rebalance/ingest/diagnose.py:399:        verdict = "watched_but_stale"
src/rebalance/ingest/diagnose.py:401:            f"{repo_norm} is watched; last synced {staleness_days} days ago "
src/rebalance/ingest/diagnose.py:406:        verdict = "watched_and_fresh"
src/rebalance/ingest/diagnose.py:408:            f"{repo_norm} is watched; last synced {staleness_days} days ago. "
src/rebalance/ingest/diagnose.py:424:            "watched": watched,
src/rebalance/ingest/config.py:792:    ``github_ignored_repos``, which suppresses GitHub *ingest*.
src/rebalance/ingest/config.py:897:def get_github_ignored_repos() -> list[str]:
src/rebalance/ingest/config.py:900:    value = config.get("github_ignored_repos")
src/rebalance/ingest/config.py:916:def set_github_ignored_repos(repos: list[str]) -> None:
src/rebalance/ingest/config.py:919:    config["github_ignored_repos"] = _normalize_github_repo_list(repos)
src/rebalance/ingest/config.py:926:    existing = get_github_ignored_repos()
src/rebalance/ingest/config.py:930:    set_github_ignored_repos(existing)
src/rebalance/ingest/config.py:937:    existing = get_github_ignored_repos()
src/rebalance/ingest/config.py:940:    set_github_ignored_repos([item for item in existing if item != normalized])
src/rebalance/ingest/config.py:947:    return normalized in set(get_github_ignored_repos())
src/rebalance/ingest/config.py:955:        watched repo into project_registry as a machine_owned row (generated_by
src/rebalance/ingest/config.py:956:        "commit_threshold_v1"). github_ignored_repos always wins regardless of this
src/rebalance/ingest/config.py:959:        cumulative — not a rolling window) before a watched repo auto-promotes.
src/rebalance/ingest/github_watch.py:1:"""External / watched GitHub repos: whole-repo activity rollups + lifecycle reconcile.
src/rebalance/ingest/github_watch.py:3:A *watched* repo is a third-party repo the operator monitors for **everyone's**
src/rebalance/ingest/github_watch.py:5:watched set via the project registry — a project flagged ``external: true`` (see
src/rebalance/ingest/github_watch.py:6::func:`rebalance.ingest.registry.get_external_repos`) — and is artifact-synced by
src/rebalance/ingest/github_watch.py:8:No second ingest path: this module adds the **one** extra step that makes a watched
src/rebalance/ingest/github_watch.py:14:Lifecycle (de-dupe / pause). A watched repo can become *active work* — cloned and
src/rebalance/ingest/github_watch.py:18:own per-login rows existed for the same repo. :func:`reconcile_watched_repo` is
src/rebalance/ingest/github_watch.py:50:# "your work" rows (and the watched-set discovery in _activity_repos) never
src/rebalance/ingest/github_watch.py:51:# collide with — or get inflated by — watched-repo aggregates.
src/rebalance/ingest/github_watch.py:122:def derive_watched_repo_activity(
src/rebalance/ingest/github_watch.py:136:    window-total counts, so the org-activity consumers SUM watched repos on the same
src/rebalance/ingest/github_watch.py:209:def purge_watched_repo_activity(database_path: Path, repo_full_name: str) -> int:
src/rebalance/ingest/github_watch.py:224:# Lifecycle — is this watched repo now "active work"?
src/rebalance/ingest/github_watch.py:227:def watched_repo_is_active_work(
src/rebalance/ingest/github_watch.py:317:def reconcile_watched_repo(
src/rebalance/ingest/github_watch.py:325:    """Idempotently bring one watched repo's rollup into the correct mode.
src/rebalance/ingest/github_watch.py:331:    if watched_repo_is_active_work(database_path, repo, since_days=since_days):
src/rebalance/ingest/github_watch.py:332:        purged = purge_watched_repo_activity(database_path, repo)
src/rebalance/ingest/github_watch.py:334:    summary = derive_watched_repo_activity(
src/rebalance/ingest/index_ops.py:626:    complementary; the union goes into the watched set.
src/rebalance/ingest/index_ops.py:654:def _external_repos(database_path: Path) -> list[str]:
src/rebalance/ingest/index_ops.py:655:    """External/watched repos drawn from the project registry (external: true).
src/rebalance/ingest/index_ops.py:657:    Always-on (not windowed), like ``_project_repos`` — a watched external repo
src/rebalance/ingest/index_ops.py:662:        from rebalance.ingest.registry import get_external_repos
src/rebalance/ingest/index_ops.py:664:        return get_external_repos(database_path)
src/rebalance/ingest/index_ops.py:669:def get_watched_repos(
src/rebalance/ingest/index_ops.py:676:    The merged ``watched`` list = (project_repos ∪ activity_repos ∪
src/rebalance/ingest/index_ops.py:677:    pushed_repos ∪ external_repos) − ignored. Callers (``refresh_index``,
src/rebalance/ingest/index_ops.py:678:    ``list_watched_repos`` MCP tool, the ``raw`` diagnostic) consume the
src/rebalance/ingest/index_ops.py:680:    being synced?". ``external_repos`` are third-party repos monitored for
src/rebalance/ingest/index_ops.py:683:    from rebalance.ingest.config import get_github_ignored_repos
src/rebalance/ingest/index_ops.py:688:    external = _external_repos(database_path)
src/rebalance/ingest/index_ops.py:689:    ignored = sorted(get_github_ignored_repos())
src/rebalance/ingest/index_ops.py:691:    # watched-set sources keep GitHub's original casing. Compare on lowercase
src/rebalance/ingest/index_ops.py:699:    watched: list[str] = []
src/rebalance/ingest/index_ops.py:703:        if repo not in watched:
src/rebalance/ingest/index_ops.py:704:            watched.append(repo)
src/rebalance/ingest/index_ops.py:706:    auto_discovered = sorted(
src/rebalance/ingest/index_ops.py:712:        "watched": watched,
src/rebalance/ingest/index_ops.py:716:        "external_repos": external,
src/rebalance/ingest/index_ops.py:717:        "auto_discovered": auto_discovered,
src/rebalance/ingest/index_ops.py:726:    return get_watched_repos(database_path)["watched"]
src/rebalance/ingest/index_ops.py:739:        [r for r in initial_target_repos if r.lower() in {e.lower() for e in _external_repos(database_path)}]
src/rebalance/ingest/index_ops.py:745:        f"reconcile_watched_repo() x {external_count} external repos (rollup or purge)",
src/rebalance/ingest/index_ops.py:762:    from rebalance.ingest.config import get_github_ignored_repos
src/rebalance/ingest/index_ops.py:767:    # repos enter the watched set on this refresh rather than the next one.
src/rebalance/ingest/index_ops.py:772:    skipped = filter_ignored_repo_activity(scan_result, get_github_ignored_repos())
src/rebalance/ingest/index_ops.py:798:    # External/watched repos: after their artifacts are synced above, reconcile a
src/rebalance/ingest/index_ops.py:800:    # org-activity dashboards/reports. Idempotent + bidirectional — a watched repo
src/rebalance/ingest/index_ops.py:802:    # (see github_watch.reconcile_watched_repo) so it never double-counts.
src/rebalance/ingest/index_ops.py:803:    from rebalance.ingest.github_watch import reconcile_watched_repo
src/rebalance/ingest/index_ops.py:805:    external_set = {r.lower() for r in _external_repos(database_path)}
src/rebalance/ingest/index_ops.py:806:    watched_activity: list[dict[str, Any]] = []
src/rebalance/ingest/index_ops.py:811:            watched_activity.append(
src/rebalance/ingest/index_ops.py:812:                reconcile_watched_repo(
src/rebalance/ingest/index_ops.py:817:            watched_activity.append({"repo": repo, "error": str(e)})
src/rebalance/ingest/index_ops.py:823:    # Coverage guard: snapshot the resolved watched set and alarm on a silent
src/rebalance/ingest/index_ops.py:836:    # just crossed the operator-commit threshold graduates into project_registry
src/rebalance/ingest/index_ops.py:875:        "watched_activity": watched_activity,
src/rebalance/ingest/github_watch.py:1:"""External / watched GitHub repos: whole-repo activity rollups + lifecycle reconcile.
src/rebalance/ingest/github_watch.py:3:A *watched* repo is a third-party repo the operator monitors for **everyone's**
src/rebalance/ingest/github_watch.py:5:watched set via the project registry — a project flagged ``external: true`` (see
src/rebalance/ingest/github_watch.py:6::func:`rebalance.ingest.registry.get_external_repos`) — and is artifact-synced by
src/rebalance/ingest/github_watch.py:8:No second ingest path: this module adds the **one** extra step that makes a watched
src/rebalance/ingest/github_watch.py:14:Lifecycle (de-dupe / pause). A watched repo can become *active work* — cloned and
src/rebalance/ingest/github_watch.py:18:own per-login rows existed for the same repo. :func:`reconcile_watched_repo` is
src/rebalance/ingest/github_watch.py:50:# "your work" rows (and the watched-set discovery in _activity_repos) never
src/rebalance/ingest/github_watch.py:51:# collide with — or get inflated by — watched-repo aggregates.
src/rebalance/ingest/github_watch.py:122:def derive_watched_repo_activity(
src/rebalance/ingest/github_watch.py:136:    window-total counts, so the org-activity consumers SUM watched repos on the same
src/rebalance/ingest/github_watch.py:209:def purge_watched_repo_activity(database_path: Path, repo_full_name: str) -> int:
src/rebalance/ingest/github_watch.py:224:# Lifecycle — is this watched repo now "active work"?
src/rebalance/ingest/github_watch.py:227:def watched_repo_is_active_work(
src/rebalance/ingest/github_watch.py:317:def reconcile_watched_repo(
src/rebalance/ingest/github_watch.py:325:    """Idempotently bring one watched repo's rollup into the correct mode.
src/rebalance/ingest/github_watch.py:331:    if watched_repo_is_active_work(database_path, repo, since_days=since_days):
src/rebalance/ingest/github_watch.py:332:        purged = purge_watched_repo_activity(database_path, repo)
src/rebalance/ingest/github_watch.py:334:    summary = derive_watched_repo_activity(
src/rebalance/ingest/note_builder.py:38:    Return all github_activity rows grouped by GitHub org, with no project_registry filter.
src/rebalance/ingest/note_builder.py:46:    from rebalance.ingest.config import get_github_ignored_repos
src/rebalance/ingest/note_builder.py:51:    ignored = get_github_ignored_repos()
src/rebalance/ingest/auth_log.py:307:def log_watched_repos_reduced(
src/rebalance/ingest/auth_log.py:312:    """A monitored repo dropped out of the watched set with durable-intent
src/rebalance/ingest/auth_log.py:319:    _append("github", "watched_repos_reduced", {
src/rebalance/ingest/auth_log.py:336:    """A watched repo crossed the commit threshold and auto-promoted into
src/rebalance/ingest/auth_log.py:337:    ``project_registry`` as a machine-owned row. Emitted by
src/rebalance/ingest/lifecycle.py:118:            "project_registry table."
src/rebalance/ingest/lifecycle.py:135:        owner="rebalance.ingest.project_inference:sync_inferred_project_registry",
src/rebalance/ingest/lifecycle.py:304:        return False, f"could not read project_registry: {exc}"
src/rebalance/ingest/project_classifier.py:164:    """Load canonical project matchers from project_registry, or config fallback.
src/rebalance/ingest/project_classifier.py:177:            WHERE type = 'table' AND name = 'project_registry'
src/rebalance/ingest/project_classifier.py:186:            FROM project_registry
src/rebalance/ingest/semantic_index.py:13:from rebalance.ingest.config import get_github_ignored_repos, normalize_github_repo_name
src/rebalance/ingest/semantic_index.py:289:    ignored_repos = set(get_github_ignored_repos())
src/rebalance/ingest/github_scan.py:417:        from rebalance.ingest.config import get_github_ignored_repos
src/rebalance/ingest/github_scan.py:418:        ignored_repos = get_github_ignored_repos()
src/rebalance/ingest/github_scan.py:569:    watched set. Idempotent: re-running with the same data yields all-unchanged
src/rebalance/ingest/github_knowledge.py:23:from rebalance.ingest.config import get_github_ignored_repos, normalize_github_repo_name
src/rebalance/ingest/github_knowledge.py:360:    if normalized_repo in set(get_github_ignored_repos()):
src/rebalance/ingest/project_inference.py:17:from rebalance.ingest.config import get_github_ignored_repos
src/rebalance/ingest/project_inference.py:194:    ignored = set(get_github_ignored_repos())
src/rebalance/ingest/project_inference.py:669:            "SELECT name, custom_fields_json FROM project_registry"
src/rebalance/ingest/project_inference.py:678:            conn.executemany("DELETE FROM project_registry WHERE name = ?", [(name,) for name in stale_names])
src/rebalance/ingest/project_inference.py:688:    A name already present in project_registry WITHOUT the inference marker is
src/rebalance/ingest/project_inference.py:694:            "SELECT name, custom_fields_json FROM project_registry"
src/rebalance/ingest/project_inference.py:704:def infer_project_registry(
src/rebalance/ingest/project_inference.py:744:def sync_inferred_project_registry(
src/rebalance/ingest/project_inference.py:751:    projects, summary = infer_project_registry(
src/rebalance/ingest/project_inference.py:804:    """Build a machine-owned project_registry row for one auto-promoted repo.
src/rebalance/ingest/project_inference.py:849:    """GH-124: auto-promote a watched repo into ``project_registry`` once the
src/rebalance/ingest/project_inference.py:852:    Candidate pool = ``get_watched_repos()["auto_discovered"]`` — repos with
src/rebalance/ingest/project_inference.py:854:    ``repos`` (curated or machine-owned), and ``github_ignored_repos`` already
src/rebalance/ingest/project_inference.py:855:    excluded upstream by ``get_watched_repos``. A candidate promotes once its
src/rebalance/ingest/project_inference.py:864:    ``sync_inferred_project_registry``.
src/rebalance/ingest/project_inference.py:867:    from rebalance.ingest.index_ops import get_watched_repos
src/rebalance/ingest/project_inference.py:879:    candidates = get_watched_repos(database_path)["auto_discovered"]
src/rebalance/ingest/registry.py:19:    # externals enter the watched set and get a whole-repo github_activity rollup
src/rebalance/ingest/registry.py:133:        # round-trips through the project_registry table without a schema column
src/rebalance/ingest/registry.py:140:        # so it round-trips through the fixed project_registry columns.
src/rebalance/ingest/registry.py:173:                INSERT INTO project_registry (
src/rebalance/ingest/registry.py:280:    """Fetch projects from the project_registry table.
src/rebalance/ingest/registry.py:298:            "FROM project_registry"
src/rebalance/ingest/registry.py:356:def get_external_repos(database_path: Path) -> list[str]:
src/rebalance/ingest/registry.py:357:    """Return the external/watched repos declared in the project registry.
src/rebalance/ingest/registry.py:362:    source consumed by ``get_watched_repos`` and the watched-repo rollup.
src/rebalance/ingest/index_ops.py:626:    complementary; the union goes into the watched set.
src/rebalance/ingest/index_ops.py:654:def _external_repos(database_path: Path) -> list[str]:
src/rebalance/ingest/index_ops.py:655:    """External/watched repos drawn from the project registry (external: true).
src/rebalance/ingest/index_ops.py:657:    Always-on (not windowed), like ``_project_repos`` — a watched external repo
src/rebalance/ingest/index_ops.py:662:        from rebalance.ingest.registry import get_external_repos
src/rebalance/ingest/index_ops.py:664:        return get_external_repos(database_path)
src/rebalance/ingest/index_ops.py:669:def get_watched_repos(
src/rebalance/ingest/index_ops.py:676:    The merged ``watched`` list = (project_repos ∪ activity_repos ∪
src/rebalance/ingest/index_ops.py:677:    pushed_repos ∪ external_repos) − ignored. Callers (``refresh_index``,
src/rebalance/ingest/index_ops.py:678:    ``list_watched_repos`` MCP tool, the ``raw`` diagnostic) consume the
src/rebalance/ingest/index_ops.py:680:    being synced?". ``external_repos`` are third-party repos monitored for
src/rebalance/ingest/index_ops.py:683:    from rebalance.ingest.config import get_github_ignored_repos
src/rebalance/ingest/index_ops.py:688:    external = _external_repos(database_path)
src/rebalance/ingest/index_ops.py:689:    ignored = sorted(get_github_ignored_repos())
src/rebalance/ingest/index_ops.py:691:    # watched-set sources keep GitHub's original casing. Compare on lowercase
src/rebalance/ingest/index_ops.py:699:    watched: list[str] = []
src/rebalance/ingest/index_ops.py:703:        if repo not in watched:
src/rebalance/ingest/index_ops.py:704:            watched.append(repo)
src/rebalance/ingest/index_ops.py:706:    auto_discovered = sorted(
src/rebalance/ingest/index_ops.py:712:        "watched": watched,
src/rebalance/ingest/index_ops.py:716:        "external_repos": external,
src/rebalance/ingest/index_ops.py:717:        "auto_discovered": auto_discovered,
src/rebalance/ingest/index_ops.py:726:    return get_watched_repos(database_path)["watched"]
src/rebalance/ingest/index_ops.py:739:        [r for r in initial_target_repos if r.lower() in {e.lower() for e in _external_repos(database_path)}]
src/rebalance/ingest/index_ops.py:745:        f"reconcile_watched_repo() x {external_count} external repos (rollup or purge)",
src/rebalance/ingest/index_ops.py:762:    from rebalance.ingest.config import get_github_ignored_repos
src/rebalance/ingest/index_ops.py:767:    # repos enter the watched set on this refresh rather than the next one.
src/rebalance/ingest/index_ops.py:772:    skipped = filter_ignored_repo_activity(scan_result, get_github_ignored_repos())
src/rebalance/ingest/index_ops.py:798:    # External/watched repos: after their artifacts are synced above, reconcile a
src/rebalance/ingest/index_ops.py:800:    # org-activity dashboards/reports. Idempotent + bidirectional — a watched repo
src/rebalance/ingest/index_ops.py:802:    # (see github_watch.reconcile_watched_repo) so it never double-counts.
src/rebalance/ingest/index_ops.py:803:    from rebalance.ingest.github_watch import reconcile_watched_repo
src/rebalance/ingest/index_ops.py:805:    external_set = {r.lower() for r in _external_repos(database_path)}
src/rebalance/ingest/index_ops.py:806:    watched_activity: list[dict[str, Any]] = []
src/rebalance/ingest/index_ops.py:811:            watched_activity.append(
src/rebalance/ingest/index_ops.py:812:                reconcile_watched_repo(
src/rebalance/ingest/index_ops.py:817:            watched_activity.append({"repo": repo, "error": str(e)})
src/rebalance/ingest/index_ops.py:823:    # Coverage guard: snapshot the resolved watched set and alarm on a silent
src/rebalance/ingest/index_ops.py:836:    # just crossed the operator-commit threshold graduates into project_registry
src/rebalance/ingest/index_ops.py:875:        "watched_activity": watched_activity,
src/rebalance/ingest/pulse.py:127:    # Whole-repo (all-author) activity today on external/watched repos — the repos
src/rebalance/ingest/pulse.py:129:    watched_repos: list[dict[str, Any]] = field(default_factory=list)
src/rebalance/ingest/pulse.py:446:def _query_watched_activity(
src/rebalance/ingest/pulse.py:448:    external_repos: list[str],
src/rebalance/ingest/pulse.py:453:    """Whole-repo (all-author) activity for watched external repos in [start, end).
src/rebalance/ingest/pulse.py:459:    if not external_repos:
src/rebalance/ingest/pulse.py:461:    repos_lower = [r.lower() for r in external_repos]
src/rebalance/ingest/pulse.py:536:    # Passively-monitored externals only — a watched repo that's become active
src/rebalance/ingest/pulse.py:538:    # not also appear in the watched section (the same de-dupe the rollup applies).
src/rebalance/ingest/pulse.py:540:        from rebalance.ingest.registry import get_external_repos
src/rebalance/ingest/pulse.py:541:        from rebalance.ingest.github_watch import watched_repo_is_active_work
src/rebalance/ingest/pulse.py:543:        external_repos = [
src/rebalance/ingest/pulse.py:544:            r for r in get_external_repos(database_path)
src/rebalance/ingest/pulse.py:545:            if not watched_repo_is_active_work(database_path, r)
src/rebalance/ingest/pulse.py:548:        external_repos = []
src/rebalance/ingest/pulse.py:549:        notes.append(f"watched_repos skipped: {exc}")
src/rebalance/ingest/pulse.py:560:        watched_repos = _query_watched_activity(
src/rebalance/ingest/pulse.py:561:            conn, external_repos, start=today_start, end=tomorrow_start
src/rebalance/ingest/pulse.py:600:        watched_repos=watched_repos,
src/rebalance/ingest/pulse.py:798:def _render_section_watched(watched: list[dict[str, Any]], tz: ZoneInfo) -> str:
src/rebalance/ingest/pulse.py:799:    if not watched:
src/rebalance/ingest/pulse.py:800:        return "_No external/watched-repo activity today._"
src/rebalance/ingest/pulse.py:802:    for w in watched:
src/rebalance/ingest/pulse.py:842:        _render_section_watched(snapshot.watched_repos, tz),
src/rebalance/ingest/next_actions.py:935:    for watched in getattr(snapshot, "watched_repos", []) or []:
src/rebalance/ingest/next_actions.py:936:        if not in_project(watched.get("repo")):
src/rebalance/ingest/next_actions.py:939:        commits = int(watched.get("commits") or 0)
src/rebalance/ingest/next_actions.py:940:        items = len(watched.get("items") or [])
src/rebalance/ingest/next_actions.py:941:        comments = int(watched.get("comments") or 0)
src/rebalance/ingest/next_actions.py:949:            rows.append(f"{watched.get('repo')} watched activity ({', '.join(counts)})")
src/rebalance/ingest/watchlist_guard.py:1:"""Watch-list coverage guard — snapshot the watched-repos set and alarm on a
src/rebalance/ingest/watchlist_guard.py:4:``get_watched_repos`` (index_ops) is a recomputed union with no persisted
src/rebalance/ingest/watchlist_guard.py:9:    watched set with a *fixed canonical window*, persists one row per repo (with
src/rebalance/ingest/watchlist_guard.py:11:    ``watched_repos_reduced`` event on a *concerning* drop. It prunes snapshots
src/rebalance/ingest/watchlist_guard.py:28:# A repo dropping out of the watched set is only *concerning* when it was held by
src/rebalance/ingest/watchlist_guard.py:34:# since_days=30 while the watched-set windows default to 14; if the snapshot
src/rebalance/ingest/watchlist_guard.py:43:_SNAPSHOT_TABLE = "watched_repos_snapshot"
src/rebalance/ingest/watchlist_guard.py:44:# Map each watched-set bucket list (keys in the get_watched_repos view) to its
src/rebalance/ingest/watchlist_guard.py:48:    ("external_repos", "external"),
src/rebalance/ingest/watchlist_guard.py:61:    """Per watched repo, the set of buckets that resolved it (ignored excluded)."""
src/rebalance/ingest/watchlist_guard.py:62:    watched = set(view.get("watched") or [])
src/rebalance/ingest/watchlist_guard.py:66:            if repo in watched:
src/rebalance/ingest/watchlist_guard.py:75:    Anchored on ``MAX(snapshot_ts)`` over the rows, so an empty watched set
src/rebalance/ingest/watchlist_guard.py:103:    """Resolve the watched set, persist a snapshot, diff against the previous one,
src/rebalance/ingest/watchlist_guard.py:104:    and emit a ``watched_repos_reduced`` event on a concerning reduction.
src/rebalance/ingest/watchlist_guard.py:106:    The single writer of ``watched_repos_snapshot``. Safe to call directly (runs
src/rebalance/ingest/watchlist_guard.py:111:    from rebalance.ingest.config import get_github_ignored_repos
src/rebalance/ingest/watchlist_guard.py:112:    from rebalance.ingest.index_ops import get_watched_repos
src/rebalance/ingest/watchlist_guard.py:114:    view = get_watched_repos(database_path, since_days=CANONICAL_SINCE_DAYS)
src/rebalance/ingest/watchlist_guard.py:116:    curr = set(view.get("watched") or [])
src/rebalance/ingest/watchlist_guard.py:143:        return {"baseline": True, "snapshot_ts": ts, "watched": len(curr)}
src/rebalance/ingest/watchlist_guard.py:148:    ignored_lower = {r.lower() for r in get_github_ignored_repos()}
src/rebalance/ingest/watchlist_guard.py:166:        auth_log.log_watched_repos_reduced(warn_removed, info_churn=info_churn)
src/rebalance/ingest/watchlist_guard.py:171:        "watched": len(curr),

exec
/bin/zsh -lc "nl -ba tests/test_auto_promote.py | sed -n '1,280p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
     1	"""Tests for GH-124 commit-threshold auto-promotion of watched repos."""
     2	
     3	from __future__ import annotations
     4	
     5	import sqlite3
     6	import tempfile
     7	import unittest
     8	from pathlib import Path
     9	from unittest import mock
    10	
    11	from rebalance.ingest import config as config_module
    12	from rebalance.ingest.config import set_github_ignored_repos, set_pulse_config
    13	from rebalance.ingest.db import db_connection, ensure_github_schema, ensure_project_schema
    14	from rebalance.ingest.project_inference import (
    15	    COMMIT_THRESHOLD_GENERATED_BY,
    16	    sync_commit_threshold_promotions,
    17	)
    18	from rebalance.ingest.registry import sync_db
    19	
    20	
    21	def _insert_commit(
    22	    db: Path, *, repo: str, sha: str, author_login: str, committed_at: str = "2026-07-01T00:00:00Z"
    23	) -> None:
    24	    conn = sqlite3.connect(db)
    25	    conn.execute(
    26	        """
    27	        INSERT INTO github_commits
    28	            (repo_full_name, item_type, item_number, sha, author_login, message,
    29	             committed_at, html_url, fetched_at)
    30	        VALUES (?, 'commit', 0, ?, ?, 'msg', ?, ?, ?)
    31	        """,
    32	        (repo, sha, author_login, committed_at, f"https://github.example/{repo}/commit/{sha}", committed_at),
    33	    )
    34	    conn.commit()
    35	    conn.close()
    36	
    37	
    38	def _insert_activity(db: Path, *, repo: str, login: str = "tester") -> None:
    39	    conn = sqlite3.connect(db)
    40	    conn.execute(
    41	        """
    42	        INSERT INTO github_activity
    43	            (login, repo_full_name, scan_date, commits, pushes, prs_opened, prs_merged,
    44	             issues_opened, issue_comments, reviews, last_active_at, scanned_at)
    45	        VALUES (?, ?, '2026-07-01', 3, 3, 0, 0, 0, 0, 0, '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z')
    46	        """,
    47	        (login, repo),
    48	    )
    49	    conn.commit()
    50	    conn.close()
    51	
    52	
    53	class AutoPromoteTests(unittest.TestCase):
    54	    def setUp(self) -> None:
    55	        self._tmp = tempfile.TemporaryDirectory()
    56	        self.addCleanup(self._tmp.cleanup)
    57	        self._orig_path = config_module.CONFIG_PATH
    58	        config_module.CONFIG_PATH = Path(self._tmp.name) / "rbos.config"
    59	        self.db_path = Path(self._tmp.name) / "rebalance.db"
    60	        with db_connection(self.db_path) as conn:
    61	            ensure_github_schema(conn)
    62	            ensure_project_schema(conn)
    63	        set_pulse_config(github_login="tester")
    64	
    65	    def tearDown(self) -> None:
    66	        config_module.CONFIG_PATH = self._orig_path
    67	
    68	    def test_promotes_repo_at_threshold(self) -> None:
    69	        repo = "Acme/widget"
    70	        _insert_activity(self.db_path, repo=repo)
    71	        for i in range(3):
    72	            _insert_commit(self.db_path, repo=repo, sha=f"sha{i}", author_login="tester")
    73	
    74	        summary = sync_commit_threshold_promotions(self.db_path)
    75	
    76	        self.assertTrue(summary.enabled)
    77	        self.assertEqual(summary.promoted_count, 1)
    78	        self.assertEqual(summary.promoted[0]["repos"], [repo])
    79	        marker = summary.promoted[0]["custom_fields"]["inference"]["generated_by"]
    80	        self.assertEqual(marker, COMMIT_THRESHOLD_GENERATED_BY)
    81	
    82	    def test_below_threshold_does_not_promote(self) -> None:
    83	        repo = "Acme/widget"
    84	        _insert_activity(self.db_path, repo=repo)
    85	        for i in range(2):
    86	            _insert_commit(self.db_path, repo=repo, sha=f"sha{i}", author_login="tester")
    87	
    88	        summary = sync_commit_threshold_promotions(self.db_path)
    89	
    90	        self.assertEqual(summary.promoted_count, 0)
    91	
    92	    def test_fork_with_zero_operator_commits_never_promotes(self) -> None:
    93	        repo = "Acme/forked-widget"
    94	        _insert_activity(self.db_path, repo=repo)
    95	        for i in range(5):
    96	            _insert_commit(self.db_path, repo=repo, sha=f"sha{i}", author_login="someone-else")
    97	
    98	        summary = sync_commit_threshold_promotions(self.db_path)
    99	
   100	        self.assertEqual(summary.promoted_count, 0)
   101	
   102	    def test_cloud_agent_commits_count_toward_threshold(self) -> None:
   103	        repo = "Acme/widget"
   104	        _insert_activity(self.db_path, repo=repo)
   105	        _insert_commit(self.db_path, repo=repo, sha="sha0", author_login="tester")
   106	        _insert_commit(self.db_path, repo=repo, sha="sha1", author_login="claude[bot]")
   107	        _insert_commit(self.db_path, repo=repo, sha="sha2", author_login="claude[bot]")
   108	
   109	        summary = sync_commit_threshold_promotions(self.db_path)
   110	
   111	        self.assertEqual(summary.promoted_count, 1)
   112	
   113	    def test_ignored_repo_never_promotes(self) -> None:
   114	        repo = "Acme/widget"
   115	        set_github_ignored_repos([repo])
   116	        _insert_activity(self.db_path, repo=repo)
   117	        for i in range(3):
   118	            _insert_commit(self.db_path, repo=repo, sha=f"sha{i}", author_login="tester")
   119	
   120	        summary = sync_commit_threshold_promotions(self.db_path)
   121	
   122	        self.assertEqual(summary.promoted_count, 0)
   123	
   124	    def test_curated_row_never_touched(self) -> None:
   125	        repo = "Acme/widget"
   126	        _insert_activity(self.db_path, repo=repo)
   127	        for i in range(3):
   128	            _insert_commit(self.db_path, repo=repo, sha=f"sha{i}", author_login="tester")
   129	        sync_db(
   130	            self.db_path,
   131	            {
   132	                "projects": [
   133	                    {
   134	                        "name": "widget",
   135	                        "status": "active",
   136	                        "summary": "hand-curated",
   137	                        "repos": [],
   138	                        "tags": [],
   139	                        "custom_fields": {},
   140	                    }
   141	                ]
   142	            },
   143	        )
   144	
   145	        summary = sync_commit_threshold_promotions(self.db_path)
   146	
   147	        self.assertEqual(summary.promoted_count, 0)
   148	        self.assertIn("widget", summary.skipped_curated_names)
   149	        with db_connection(self.db_path) as conn:
   150	            row = conn.execute(
   151	                "SELECT summary FROM project_registry WHERE name = 'widget'"
   152	            ).fetchone()
   153	        self.assertEqual(row["summary"], "hand-curated")
   154	
   155	    def test_idempotent_rerun_does_not_duplicate(self) -> None:
   156	        repo = "Acme/widget"
   157	        _insert_activity(self.db_path, repo=repo)
   158	        for i in range(3):
   159	            _insert_commit(self.db_path, repo=repo, sha=f"sha{i}", author_login="tester")
   160	
   161	        sync_commit_threshold_promotions(self.db_path)
   162	        sync_commit_threshold_promotions(self.db_path)
   163	
   164	        with db_connection(self.db_path) as conn:
   165	            count = conn.execute(
   166	                "SELECT COUNT(*) AS n FROM project_registry WHERE name = 'widget'"
   167	            ).fetchone()["n"]
   168	        self.assertEqual(count, 1)
   169	
   170	    def test_disabled_is_a_no_op(self) -> None:
   171	        repo = "Acme/widget"
   172	        _insert_activity(self.db_path, repo=repo)
   173	        for i in range(3):
   174	            _insert_commit(self.db_path, repo=repo, sha=f"sha{i}", author_login="tester")
   175	        config_module._write_config(
   176	            {**config_module._read_config(), "auto_promote_enabled": False}
   177	        )
   178	
   179	        summary = sync_commit_threshold_promotions(self.db_path)
   180	
   181	        self.assertFalse(summary.enabled)
   182	        self.assertEqual(summary.promoted_count, 0)
   183	
   184	    def test_promotion_fires_auth_log_alert(self) -> None:
   185	        repo = "Acme/widget"
   186	        _insert_activity(self.db_path, repo=repo)
   187	        for i in range(3):
   188	            _insert_commit(self.db_path, repo=repo, sha=f"sha{i}", author_login="tester")
   189	
   190	        with mock.patch(
   191	            "rebalance.ingest.auth_log.log_project_auto_promoted"
   192	        ) as mocked:
   193	            sync_commit_threshold_promotions(self.db_path)
   194	
   195	        mocked.assert_called_once_with(
   196	            repo, project_name="widget", commit_count=3, threshold=3
   197	        )
   198	
   199	    def test_no_promotion_does_not_fire_auth_log_alert(self) -> None:
   200	        repo = "Acme/widget"
   201	        _insert_activity(self.db_path, repo=repo)
   202	        for i in range(2):
   203	            _insert_commit(self.db_path, repo=repo, sha=f"sha{i}", author_login="tester")
   204	
   205	        with mock.patch(
   206	            "rebalance.ingest.auth_log.log_project_auto_promoted"
   207	        ) as mocked:
   208	            sync_commit_threshold_promotions(self.db_path)
   209	
   210	        mocked.assert_not_called()
   211	
   212	    def test_no_github_login_configured_is_a_no_op(self) -> None:
   213	        # set_pulse_config(github_login=None) is a no-op (None means "leave
   214	        # unchanged"), so clear it directly at the raw-config layer instead.
   215	        config_module._write_config(
   216	            {**config_module._read_config(), "github_login": None}
   217	        )
   218	        repo = "Acme/widget"
   219	        _insert_activity(self.db_path, repo=repo)
   220	        for i in range(3):
   221	            _insert_commit(self.db_path, repo=repo, sha=f"sha{i}", author_login="tester")
   222	
   223	        summary = sync_commit_threshold_promotions(self.db_path)
   224	
   225	        self.assertEqual(summary.promoted_count, 0)
   226	
   227	
   228	if __name__ == "__main__":
   229	    unittest.main()

exec
/bin/zsh -lc "nl -ba src/rebalance/ingest/index_ops.py | sed -n '600,725p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
   600	                  AND login != ?
   601	                  AND (
   602	                    commits + pushes + prs_opened + prs_merged
   603	                    + issues_opened + issue_comments + reviews
   604	                  ) > 0
   605	                ORDER BY repo_full_name
   606	                """,
   607	                (f"-{int(since_days)} days", WATCHED_LOGIN),
   608	            ).fetchall()
   609	            for r in rows:
   610	                repo = (r["repo_full_name"] or "").strip()
   611	                if repo and repo not in repos:
   612	                    repos.append(repo)
   613	    except Exception:
   614	        pass
   615	    return repos
   616	
   617	
   618	def _pushed_repos(database_path: Path, *, since_days: int = 14) -> list[str]:
   619	    """Repos discovered via /user/repos?sort=pushed with a recent pushed_at.
   620	
   621	    Read from the github_pushed_repos table populated by sync_pushed_repos().
   622	    Catches activity that the events feed misses — pushes by collaborators
   623	    on private org repos, pushes dropped by the events API's 300-event
   624	    pagination cap, eventual-consistency gaps, and non-default-branch /
   625	    force-push edge cases. The events feed and this signal are
   626	    complementary; the union goes into the watched set.
   627	    """
   628	    from datetime import datetime, timedelta, timezone
   629	
   630	    repos: list[str] = []
   631	    try:
   632	        cutoff = (
   633	            datetime.now(timezone.utc) - timedelta(days=int(since_days))
   634	        ).isoformat()
   635	        with db_connection(database_path) as conn:
   636	            rows = conn.execute(
   637	                """
   638	                SELECT repo_full_name FROM github_pushed_repos
   639	                WHERE pushed_at >= ?
   640	                  AND archived = 0 AND disabled = 0
   641	                ORDER BY pushed_at DESC
   642	                """,
   643	                (cutoff,),
   644	            ).fetchall()
   645	            for r in rows:
   646	                repo = (r["repo_full_name"] or "").strip()
   647	                if repo and repo not in repos:
   648	                    repos.append(repo)
   649	    except Exception:
   650	        pass
   651	    return repos
   652	
   653	
   654	def _external_repos(database_path: Path) -> list[str]:
   655	    """External/watched repos drawn from the project registry (external: true).
   656	
   657	    Always-on (not windowed), like ``_project_repos`` — a watched external repo
   658	    should be synced every refresh regardless of recent activity, since the point
   659	    is to catch other people's activity the operator's events feed never sees.
   660	    """
   661	    try:
   662	        from rebalance.ingest.registry import get_external_repos
   663	
   664	        return get_external_repos(database_path)
   665	    except Exception:  # noqa: BLE001
   666	        return []
   667	
   668	
   669	def get_watched_repos(
   670	    database_path: Path,
   671	    *,
   672	    since_days: int = 14,
   673	) -> dict[str, list[str]]:
   674	    """Return the canonical view of which repos are monitored.
   675	
   676	    The merged ``watched`` list = (project_repos ∪ activity_repos ∪
   677	    pushed_repos ∪ external_repos) − ignored. Callers (``refresh_index``,
   678	    ``list_watched_repos`` MCP tool, the ``raw`` diagnostic) consume the
   679	    same source of truth so the user can never wonder "what's actually
   680	    being synced?". ``external_repos`` are third-party repos monitored for
   681	    everyone's activity (see ``rebalance.ingest.github_watch``).
   682	    """
   683	    from rebalance.ingest.config import get_github_ignored_repos
   684	
   685	    project = _project_repos(database_path)
   686	    activity = _activity_repos(database_path, since_days=since_days)
   687	    pushed = _pushed_repos(database_path, since_days=since_days)
   688	    external = _external_repos(database_path)
   689	    ignored = sorted(get_github_ignored_repos())
   690	    # Ignored entries are stored lowercased (CLI normalizes on add);
   691	    # watched-set sources keep GitHub's original casing. Compare on lowercase
   692	    # so e.g. an "xpressbase/athenacomply" entry blocks "xpressbase/athenaComply".
   693	    ignored_lower = {r.lower() for r in ignored}
   694	
   695	    project_set = set(project)
   696	    activity_set = set(activity)
   697	    pushed_set = set(pushed)
   698	
   699	    watched: list[str] = []
   700	    for repo in project + external + activity + pushed:
   701	        if repo.lower() in ignored_lower:
   702	            continue
   703	        if repo not in watched:
   704	            watched.append(repo)
   705	
   706	    auto_discovered = sorted(
   707	        repo for repo in (activity_set | pushed_set) - project_set
   708	        if repo.lower() not in ignored_lower
   709	    )
   710	
   711	    return {
   712	        "watched": watched,
   713	        "project_repos": project,
   714	        "activity_repos": activity,
   715	        "pushed_repos": pushed,
   716	        "external_repos": external,
   717	        "auto_discovered": auto_discovered,
   718	        "ignored": ignored,
   719	        "since_days": since_days,
   720	    }
   721	
   722	
   723	def _resolve_repos_for_refresh(database_path: Path, repos: list[str]) -> list[str]:
   724	    if repos:
   725	        return [r.strip() for r in repos if r.strip()]

exec
/bin/zsh -lc "nl -ba scripts/dashboard.py | sed -n '420,470p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
   420	                {ignored_clause}
   421	                GROUP BY repo_full_name
   422	                ORDER BY events DESC
   423	                LIMIT ?
   424	                """,
   425	                tuple(params),
   426	            ).fetchall()
   427	        return [dict(r) for r in rows]
   428	    except Exception:  # noqa: BLE001 — empty DB before first sync
   429	        return []
   430	
   431	
   432	def fetch_recent_auto_promotion(days: int = 7) -> dict[str, Any] | None:
   433	    """GH-124: most recent commit-threshold auto-promotion within the window, if any.
   434	
   435	    Read-only over ``project_registry`` — the repo-pie's "New repo added" top-item
   436	    annotation is this function's only consumer. Returns None when nothing promoted
   437	    in the window (the common case), or a dict with ``repo``/``project_name``/
   438	    ``promoted_at`` for the single most recent promotion.
   439	    """
   440	    try:
   441	        with db_connection(DB_PATH) as conn:
   442	            rows = conn.execute(
   443	                "SELECT name, custom_fields_json FROM project_registry "
   444	                "WHERE custom_fields_json IS NOT NULL"
   445	            ).fetchall()
   446	    except Exception:  # noqa: BLE001 — empty DB before first sync
   447	        return None
   448	
   449	    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
   450	    best: tuple[datetime, dict[str, Any]] | None = None
   451	    for row in rows:
   452	        try:
   453	            custom_fields = json.loads(row["custom_fields_json"])
   454	        except (TypeError, ValueError):
   455	            continue
   456	        inference = (custom_fields or {}).get("inference") or {}
   457	        if inference.get("generated_by") != "commit_threshold_v1":
   458	            continue
   459	        promoted_at = inference.get("promoted_at")
   460	        if not promoted_at:
   461	            continue
   462	        try:
   463	            promoted_dt = datetime.fromisoformat(promoted_at)
   464	        except ValueError:
   465	            continue
   466	        if promoted_dt < cutoff:
   467	            continue
   468	        if best is None or promoted_dt > best[0]:
   469	            best = (promoted_dt, {
   470	                "repo": inference.get("repo_full_name"),

exec
/bin/zsh -lc "nl -ba src/rebalance/ingest/auth_log.py | sed -n '300,350p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
   300	    _append("launchd", "job_failed", detail)
   301	
   302	
   303	# ---------------------------------------------------------------------------
   304	# Watch-list coverage guard
   305	# ---------------------------------------------------------------------------
   306	
   307	def log_watched_repos_reduced(
   308	    removed: list[dict[str, Any]],
   309	    *,
   310	    info_churn: list[str] | None = None,
   311	) -> None:
   312	    """A monitored repo dropped out of the watched set with durable-intent
   313	    coverage (project/external) — a concerning, possibly-silent reduction.
   314	
   315	    *removed* is a list of ``{"repo", "last_buckets"}``; *info_churn* lists repos
   316	    that also dropped but were rolling-window-only (expected aging-out, carried as
   317	    context, not alarmed). Emitted by ``watchlist_guard.snapshot_and_detect``.
   318	    """
   319	    _append("github", "watched_repos_reduced", {
   320	        "removed": removed,
   321	        "info_churn": info_churn or [],
   322	    })
   323	
   324	
   325	# ---------------------------------------------------------------------------
   326	# GH-124: commit-threshold auto-promotion
   327	# ---------------------------------------------------------------------------
   328	
   329	def log_project_auto_promoted(
   330	    repo_full_name: str,
   331	    *,
   332	    project_name: str,
   333	    commit_count: int,
   334	    threshold: int,
   335	) -> None:
   336	    """A watched repo crossed the commit threshold and auto-promoted into
   337	    ``project_registry`` as a machine-owned row. Emitted by
   338	    ``project_inference.sync_commit_threshold_promotions``.
   339	    """
   340	    _append("registry", "project_auto_promoted", {
   341	        "repo": repo_full_name,
   342	        "project_name": project_name,
   343	        "commit_count": commit_count,
   344	        "threshold": threshold,
   345	    })
   346	
   347	
   348	# ---------------------------------------------------------------------------
   349	# Readers
   350	# ---------------------------------------------------------------------------

exec
/bin/zsh -lc "nl -ba tests/test_index_ops.py | sed -n '1,140p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
     1	"""Tests for refresh orchestration options."""
     2	
     3	from __future__ import annotations
     4	
     5	import tempfile
     6	import unittest
     7	from pathlib import Path
     8	from unittest.mock import patch
     9	
    10	from rebalance.ingest.index_ops import _refresh_dashboard_note, _refresh_github, refresh_index
    11	
    12	
    13	class IndexOpsTests(unittest.TestCase):
    14	    def test_github_dry_run_embeds_github_documents(self) -> None:
    15	        # Phase 3: github refresh embeds github_documents (source-table enrichment),
    16	        # but semantic projection is owned by the semantic stage, not this collector.
    17	        with tempfile.TemporaryDirectory() as tmpdir:
    18	            result = _refresh_github(
    19	                Path(tmpdir) / "rebalance.db",
    20	                token="test-token",
    21	                since_days=30,
    22	                repos=["example/repo"],
    23	                dry_run=True,
    24	            )
    25	
    26	        self.assertIn("embed_github_documents()", result["steps"])
    27	        self.assertNotIn("semantic_backfill(source=['github'])", result["steps"])
    28	        self.assertNotIn("semantic_embed(source=['github'])", result["steps"])
    29	
    30	    def test_github_refresh_wires_auto_promote_after_watchlist_guard(self) -> None:
    31	        # GH-124: a real (non-dry-run) github refresh must call
    32	        # sync_commit_threshold_promotions after the watchlist guard and fold
    33	        # its summary into the result under "auto_promote".
    34	        from rebalance.ingest.project_inference import AutoPromoteSummary
    35	
    36	        fake_promoted_row = {
    37	            "name": "widget",
    38	            "custom_fields": {"inference": {"repo_full_name": "Acme/widget"}},
    39	        }
    40	        fake_summary = AutoPromoteSummary(
    41	            enabled=True, threshold=3, candidates_evaluated=2, promoted=[fake_promoted_row]
    42	        )
    43	
    44	        with tempfile.TemporaryDirectory() as tmpdir:
    45	            db_path = Path(tmpdir) / "rebalance.db"
    46	            with (
    47	                patch(
    48	                    "rebalance.ingest.index_ops._resolve_repos_for_refresh",
    49	                    return_value=[],
    50	                ),
    51	                patch(
    52	                    "rebalance.ingest.github_scan.sync_pushed_repos"
    53	                ) as mock_pushed,
    54	                patch("rebalance.ingest.github_scan.scan_github") as mock_scan,
    55	                patch(
    56	                    "rebalance.ingest.github_scan.filter_ignored_repo_activity",
    57	                    return_value=[],
    58	                ),
    59	                patch("rebalance.ingest.github_scan.upsert_github_activity"),
    60	                patch(
    61	                    "rebalance.ingest.github_knowledge.embed_github_documents"
    62	                ) as mock_embed,
    63	                patch(
    64	                    "rebalance.ingest.watchlist_guard.snapshot_and_detect",
    65	                    return_value={"ok": True},
    66	                ),
    67	                patch(
    68	                    "rebalance.ingest.project_inference.sync_commit_threshold_promotions",
    69	                    return_value=fake_summary,
    70	                ) as mock_auto_promote,
    71	            ):
    72	                mock_pushed.return_value.fetched = 0
    73	                mock_pushed.return_value.inserted = 0
    74	                mock_pushed.return_value.updated = 0
    75	                mock_pushed.return_value.unchanged = 0
    76	                mock_pushed.return_value.skipped_archived = 0
    77	                mock_pushed.return_value.error = None
    78	                mock_scan.return_value.login = "tester"
    79	                mock_scan.return_value.total_events = 0
    80	                mock_scan.return_value.repo_activity = []
    81	                mock_embed.return_value.total_docs = 0
    82	                mock_embed.return_value.embedded_docs = 0
    83	                mock_embed.return_value.skipped_unchanged = 0
    84	                mock_embed.return_value.elapsed_seconds = 0.0
    85	
    86	                result = _refresh_github(
    87	                    db_path, token="test-token", since_days=14, repos=[], dry_run=False
    88	                )
    89	
    90	        mock_auto_promote.assert_called_once_with(db_path)
    91	        self.assertEqual(result["auto_promote"]["promoted_count"], 1)
    92	        self.assertEqual(result["auto_promote"]["promoted_repos"], ["Acme/widget"])
    93	        self.assertEqual(result["auto_promote"]["candidates_evaluated"], 2)
    94	
    95	    def test_full_refresh_dry_run_plans_dashboard_note_update(self) -> None:
    96	        with tempfile.TemporaryDirectory() as tmpdir:
    97	            root = Path(tmpdir)
    98	            vault = root / "vault"
    99	            vault.mkdir()
   100	
   101	            with (
   102	                patch("rebalance.ingest.index_ops.get_vault_path", return_value=str(vault)),
   103	                patch("rebalance.ingest.index_ops.get_github_token", return_value="test-token"),
   104	                patch("rebalance.ingest.index_ops.get_watched_repos", return_value={"watched": ["example/repo"]}),
   105	            ):
   106	                result = refresh_index(root / "rebalance.db", scope=["all"], dry_run=True)
   107	
   108	        scopes = [item["scope"] for item in result["results"]]
   109	        self.assertIn("dashboard", scopes)
   110	        dashboard = next(item for item in result["results"] if item["scope"] == "dashboard")
   111	        self.assertTrue(dashboard["dry_run"])
   112	        self.assertIn("write_dashboard_note()", dashboard["steps"])
   113	
   114	    def test_dashboard_note_dry_run_targets_obsidian_dashboard_path(self) -> None:
   115	        with tempfile.TemporaryDirectory() as tmpdir:
   116	            root = Path(tmpdir)
   117	            result = _refresh_dashboard_note(
   118	                root / "rebalance.db",
   119	                vault_path=root / "vault",
   120	                since_days=14,
   121	                dry_run=True,
   122	            )
   123	
   124	        self.assertEqual(result["scope"], "dashboard")
   125	        self.assertTrue(result["dry_run"])
   126	        self.assertTrue(result["output_path"].endswith("Dashboards/rebalanceOS Dashboard.md"))
   127	
   128	    def test_get_index_status_recent_row_count_7d(self) -> None:
   129	        from rebalance.ingest.db import db_connection, run_migrations
   130	        from rebalance.ingest.index_ops import get_index_status
   131	
   132	        with tempfile.TemporaryDirectory() as tmpdir:
   133	            db_path = Path(tmpdir) / "rebalance.db"
   134	
   135	            # Initialize the database schema and migrations
   136	            with db_connection(db_path) as conn:
   137	                run_migrations(conn)
   138	
   139	                # Seed vault (table vault_files)
   140	                # 1 recent modified file, 1 stale modified file

codex
I’m down in the GitHub ingest path now. The key question is whether `github_commits` is actually a durable all-time corpus of operator commits, or just a moving window of PR-linked commits that makes the threshold look cumulative in tests but not in production.
exec
/bin/zsh -lc "nl -ba src/rebalance/ingest/github_reconciliation.py | sed -n '220,320p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
   220	            explicit_by_issue.setdefault(int(row["target_number"]), []).append(
   221	                {"pr": pr, "link_kind": str(row["link_kind"] or "")}
   222	            )
   223	
   224	        issue_comment_rows = [
   225	            dict(row)
   226	            for row in conn.execute(
   227	                """
   228	                SELECT item_number, body
   229	                FROM github_comments
   230	                WHERE repo_full_name = ?
   231	                  AND item_type = 'issue'
   232	                """,
   233	                (repo_full_name,),
   234	            ).fetchall()
   235	        ]
   236	        issue_comments = _group_rows_by_number(issue_comment_rows, "item_number", "body")
   237	
   238	        pr_comment_rows = [
   239	            dict(row)
   240	            for row in conn.execute(
   241	                """
   242	                SELECT item_number, body
   243	                FROM github_comments
   244	                WHERE repo_full_name = ?
   245	                  AND item_type = 'pull_request'
   246	                """,
   247	                (repo_full_name,),
   248	            ).fetchall()
   249	        ]
   250	        pr_comments = _group_rows_by_number(pr_comment_rows, "item_number", "body")
   251	
   252	        pr_commit_rows = [
   253	            dict(row)
   254	            for row in conn.execute(
   255	                """
   256	                SELECT item_number, message
   257	                FROM github_commits
   258	                WHERE repo_full_name = ?
   259	                  AND item_type = 'pull_request'
   260	                """,
   261	                (repo_full_name,),
   262	            ).fetchall()
   263	        ]
   264	        pr_commits = _group_rows_by_number(pr_commit_rows, "item_number", "message")
   265	
   266	        high_confidence: list[IssuePRRecommendation] = []
   267	        medium_confidence: list[IssuePRRecommendation] = []
   268	        matched_issue_numbers: set[int] = set()
   269	
   270	        for issue in open_issues:
   271	            issue_number = int(issue["number"])
   272	            issue_text_parts = [str(issue.get("title") or ""), str(issue.get("body") or "")]
   273	            issue_text_parts.extend(issue_comments.get(issue_number, []))
   274	            issue_text = "\n".join(part for part in issue_text_parts if part)
   275	            issue_pr_refs = {ref for ref in _extract_refs(issue_text) if ref in pr_by_number}
   276	
   277	            candidates: list[IssuePRRecommendation] = []
   278	            for pr in merged_prs:
   279	                pr_number = int(pr["number"])
   280	                title_similarity = _title_similarity(issue["title"], pr["title"])
   281	                pr_text_parts = [str(pr.get("title") or ""), str(pr.get("body") or "")]
   282	                pr_text_parts.extend(pr_comments.get(pr_number, []))
   283	                pr_text_parts.extend(pr_commits.get(pr_number, []))
   284	                pr_text = "\n".join(part for part in pr_text_parts if part)
   285	
   286	                explicit_links = [
   287	                    item for item in explicit_by_issue.get(issue_number, [])
   288	                    if int(item["pr"]["number"]) == pr_number
   289	                ]
   290	                explicit_close = any(link["link_kind"] == "closes" for link in explicit_links)
   291	                explicit_link = bool(explicit_links)
   292	                issue_mentions_pr = pr_number in issue_pr_refs
   293	                branch_issue_match = _head_ref_matches_issue(pr.get("head_ref", ""), issue_number)
   294	                commit_mentions_issue = issue_number in _extract_refs("\n".join(pr_commits.get(pr_number, [])))
   295	                pr_mentions_issue = issue_number in _extract_refs(pr_text)
   296	                same_milestone = bool(
   297	                    issue.get("milestone_title")
   298	                    and issue.get("milestone_title") == pr.get("milestone_title")
   299	                )
   300	
   301	                score = 0.0
   302	                evidence: list[str] = []
   303	
   304	                if explicit_close:
   305	                    score = 0.99
   306	                    evidence.append(
   307	                        f"PR #{pr_number} explicitly uses a closing keyword for issue #{issue_number}."
   308	                    )
   309	                else:
   310	                    if explicit_link:
   311	                        score += 0.35
   312	                        evidence.append(
   313	                            f"PR #{pr_number} explicitly references issue #{issue_number}."
   314	                        )
   315	                    if issue_mentions_pr:
   316	                        score += 0.3
   317	                        evidence.append(
   318	                            f"Issue #{issue_number} text/comments explicitly mention PR #{pr_number}."
   319	                        )
   320	                    if branch_issue_match:

exec
/bin/zsh -lc "nl -ba src/rebalance/ingest/github_knowledge.py | sed -n '1,520p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
     1	"""
     2	GitHub artifact sync, local document corpus construction, and semantic query.
     3	
     4	This is the Phase 1 local-first GitHub knowledge layer:
     5	- sync structured artifacts into SQLite
     6	- build a local GitHub document corpus from issues, PRs, comments, reviews, and commits
     7	- embed that corpus with the same local embedding runtime used for vault notes
     8	- query it semantically without re-scanning GitHub live at answer time
     9	"""
    10	
    11	from __future__ import annotations
    12	
    13	import hashlib
    14	import json
    15	import time
    16	from dataclasses import dataclass
    17	from datetime import datetime, timedelta, timezone
    18	from pathlib import Path
    19	from typing import Any, Callable
    20	from urllib.parse import urlencode
    21	import re
    22	
    23	from rebalance.ingest.config import get_github_ignored_repos, normalize_github_repo_name
    24	from rebalance.ingest.db import db_connection, ensure_github_schema, ensure_semantic_schema
    25	from rebalance.ingest.db import github as gh
    26	from rebalance.ingest.db import semantic as sem
    27	from rebalance.ingest._http import GITHUB_API, GitHubClient, GitHubHTTPError
    28	from rebalance.ingest.embedder import (
    29	    DEFAULT_MODEL as DEFAULT_EMBED_MODEL,
    30	    EMBEDDING_DIM,
    31	    _embed_batch,
    32	    _load_model,
    33	    _vec_to_bytes,
    34	)
    35	from rebalance.ingest.semantic_index import sync_github_documents
    36	DEFAULT_SYNC_DAYS = 90
    37	MIN_EMBED_CHARS = 40
    38	_CLOSES_RE = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)\b", re.IGNORECASE)
    39	_ISSUE_REF_RE = re.compile(r"(?<![/\w])#(\d+)\b")
    40	
    41	JsonFetcher = Callable[[str], Any]
    42	EmbedTexts = Callable[[list[str], str], list[list[float]]]
    43	
    44	
    45	@dataclass
    46	class GitHubKnowledgeSyncResult:
    47	    repo_full_name: str
    48	    branches_synced: int
    49	    issues_synced: int
    50	    prs_synced: int
    51	    comments_synced: int
    52	    commits_synced: int
    53	    checks_synced: int
    54	    docs_built: int
    55	    milestones_synced: int
    56	    labels_synced: int
    57	    releases_synced: int
    58	    elapsed_seconds: float
    59	
    60	
    61	@dataclass
    62	class GitHubEmbedResult:
    63	    total_docs: int
    64	    embedded_docs: int
    65	    skipped_unchanged: int
    66	    model_name: str
    67	    embedding_dim: int
    68	    elapsed_seconds: float
    69	
    70	
    71	@dataclass
    72	class GitHubRepoPurgeResult:
    73	    repo_full_name: str
    74	    dry_run: bool
    75	    row_counts: dict[str, int]
    76	    total_rows: int
    77	    deleted_rows: int
    78	
    79	
    80	def _github_headers(token: str) -> dict[str, str]:
    81	    """Delegate to the shared GitHub client.
    82	
    83	    Retained as a module-level helper because some external callers (tests,
    84	    experimental scripts) imported it before the shared client existed.
    85	    """
    86	    return GitHubClient(token).headers()
    87	
    88	
    89	def _http_get_json(url: str, token: str) -> Any:
    90	    """GET ``url`` as JSON; raise on non-2xx.
    91	
    92	    Thin wrapper over :class:`GitHubClient` so the legacy ``api_get`` callable
    93	    seam in :func:`sync_github_repo` keeps working. New code should construct
    94	    a client once and reuse it.
    95	    """
    96	    try:
    97	        return GitHubClient(token).get_json(url)
    98	    except GitHubHTTPError as exc:
    99	        # Preserve legacy RuntimeError type — tests and callers expect it.
   100	        raise RuntimeError(f"GitHub API request failed: {exc.status} {url}") from exc
   101	
   102	
   103	def _build_url(base_url: str, **params: Any) -> str:
   104	    cleaned = {key: value for key, value in params.items() if value not in ("", None)}
   105	    if not cleaned:
   106	        return base_url
   107	    return f"{base_url}?{urlencode(cleaned, doseq=True)}"
   108	
   109	
   110	def _paginate_list(
   111	    base_url: str,
   112	    api_get: JsonFetcher,
   113	    *,
   114	    stop_updated_before: str = "",
   115	    **params: Any,
   116	) -> list[dict[str, Any]]:
   117	    page = 1
   118	    results: list[dict[str, Any]] = []
   119	    while True:
   120	        data = api_get(_build_url(base_url, per_page=100, page=page, **params))
   121	        if not isinstance(data, list) or not data:
   122	            break
   123	
   124	        stop = False
   125	        for row in data:
   126	            updated_at = str(row.get("updated_at") or "")
   127	            if stop_updated_before and updated_at and updated_at < stop_updated_before:
   128	                stop = True
   129	                break
   130	            results.append(row)
   131	
   132	        if stop or len(data) < 100:
   133	            break
   134	        page += 1
   135	    return results
   136	
   137	
   138	def _cutoff_iso(since_days: int) -> str:
   139	    cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
   140	    return cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
   141	
   142	
   143	def _json_dumps(value: Any) -> str:
   144	    return json.dumps(value, ensure_ascii=False, sort_keys=True)
   145	
   146	
   147	def _content_hash(text: str) -> str:
   148	    return hashlib.sha256(text.encode("utf-8")).hexdigest()
   149	
   150	
   151	def _review_decision(reviews: list[dict[str, Any]]) -> str:
   152	    meaningful = [
   153	        (review.get("submitted_at") or "", review.get("state") or "")
   154	        for review in reviews
   155	        if (review.get("state") or "") in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}
   156	    ]
   157	    if not meaningful:
   158	        return "REVIEW_REQUIRED"
   159	    meaningful.sort(key=lambda item: item[0])
   160	    last_state = meaningful[-1][1]
   161	    return "REVIEW_REQUIRED" if last_state == "DISMISSED" else last_state
   162	
   163	
   164	def _check_rollup(check_runs: list[dict[str, Any]]) -> str:
   165	    if not check_runs:
   166	        return ""
   167	    if any((run.get("status") or "") != "completed" for run in check_runs):
   168	        return "pending"
   169	    conclusions = [(run.get("conclusion") or "").lower() for run in check_runs]
   170	    if any(
   171	        conclusion in {"failure", "timed_out", "cancelled", "startup_failure", "action_required", "stale"}
   172	        for conclusion in conclusions
   173	    ):
   174	        return "failing"
   175	    if all(conclusion in {"success", "neutral", "skipped"} for conclusion in conclusions):
   176	        return "success"
   177	    return "mixed"
   178	
   179	
   180	def _parse_links(text: str) -> list[tuple[str, int]]:
   181	    if not text:
   182	        return []
   183	    closing = {(kind, int(num)) for num in _CLOSES_RE.findall(text) for kind in ["closes"]}
   184	    mentions = {
   185	        ("mentions", int(num))
   186	        for num in _ISSUE_REF_RE.findall(text)
   187	        if ("closes", int(num)) not in closing
   188	    }
   189	    return sorted(closing | mentions, key=lambda item: (item[0], item[1]))
   190	
   191	
   192	def _item_doc_text(item: dict[str, Any]) -> str:
   193	    lines = [f"{item['item_type']} #{item['number']}: {item['title']}"]
   194	    if item.get("milestone_title"):
   195	        lines.append(f"Milestone: {item['milestone_title']}")
   196	    labels = json.loads(item.get("labels_json") or "[]")
   197	    if labels:
   198	        lines.append(f"Labels: {', '.join(labels)}")
   199	    if item.get("state"):
   200	        lines.append(f"State: {item['state']}")
   201	    if item.get("review_decision"):
   202	        lines.append(f"Review: {item['review_decision']}")
   203	    if item.get("check_status"):
   204	        lines.append(f"Checks: {item['check_status']}")
   205	    if item.get("body"):
   206	        lines.extend(["", item["body"]])
   207	    return "\n".join(lines).strip()
   208	
   209	
   210	def _comment_doc_text(item_type: str, item_number: int, comment_type: str, body: str, *, review_state: str = "") -> str:
   211	    prefix = f"{comment_type.replace('_', ' ')} on {item_type} #{item_number}"
   212	    if review_state:
   213	        prefix += f" ({review_state})"
   214	    return f"{prefix}\n\n{body}".strip()
   215	
   216	
   217	def _commit_doc_text(item_type: str, item_number: int, sha: str, message: str) -> str:
   218	    first_line = (message or "").splitlines()[0].strip()
   219	    return f"Commit {sha[:7]} on {item_type} #{item_number}\n\n{first_line}".strip()
   220	
   221	
   222	def _insert_document(
   223	    conn: Any,
   224	    *,
   225	    repo_full_name: str,
   226	    source_type: str,
   227	    source_number: int,
   228	    doc_type: str,
   229	    source_key: str,
   230	    title: str,
   231	    body: str,
   232	    updated_at: str,
   233	    fetched_at: str,
   234	) -> int:
   235	    return gh.insert_github_document(
   236	        conn,
   237	        repo_full_name=repo_full_name,
   238	        source_type=source_type,
   239	        source_number=source_number,
   240	        doc_type=doc_type,
   241	        source_key=source_key,
   242	        title=title,
   243	        body=body,
   244	        content_hash=_content_hash(body),
   245	        updated_at=updated_at,
   246	        fetched_at=fetched_at,
   247	    )
   248	
   249	
   250	def purge_github_repo_data(
   251	    database_path: Path,
   252	    repo_full_name: str,
   253	    *,
   254	    dry_run: bool = False,
   255	) -> GitHubRepoPurgeResult:
   256	    """Delete one repo's GitHub ingest footprint and related semantic rows."""
   257	    normalized_repo = normalize_github_repo_name(repo_full_name)
   258	    table_names = [
   259	        "github_activity",
   260	        "github_branches",
   261	        "github_labels",
   262	        "github_milestones",
   263	        "github_releases",
   264	        "github_items",
   265	        "github_comments",
   266	        "github_commits",
   267	        "github_check_runs",
   268	        "github_links",
   269	        "github_documents",
   270	        "github_repo_meta",
   271	    ]
   272	
   273	    with db_connection(database_path) as conn:
   274	        ensure_github_schema(conn)
   275	        ensure_semantic_schema(conn)
   276	
   277	        row_counts: dict[str, int] = {
   278	            table_name: gh.count_repo_rows(conn, table_name, normalized_repo)
   279	            for table_name in table_names
   280	        }
   281	
   282	        github_doc_ids = gh.github_document_ids(conn, normalized_repo)
   283	        row_counts["github_embeddings"] = gh.count_ids_in(
   284	            conn, "github_embeddings", "doc_id", github_doc_ids
   285	        )
   286	
   287	        semantic_doc_ids = gh.semantic_doc_ids_for_github_repo(conn, normalized_repo)
   288	        row_counts["semantic_documents"] = len(semantic_doc_ids)
   289	        row_counts["semantic_embeddings"] = gh.count_ids_in(
   290	            conn, "semantic_embeddings", "rowid", semantic_doc_ids
   291	        )
   292	
   293	        total_rows = sum(row_counts.values())
   294	        if dry_run:
   295	            return GitHubRepoPurgeResult(
   296	                repo_full_name=normalized_repo,
   297	                dry_run=True,
   298	                row_counts=row_counts,
   299	                total_rows=total_rows,
   300	                deleted_rows=0,
   301	            )
   302	
   303	        if semantic_doc_ids:
   304	            sem.delete_semantic_documents(conn, semantic_doc_ids)
   305	        if github_doc_ids:
   306	            gh.delete_github_embeddings_for_docs(conn, github_doc_ids)
   307	        for table_name in table_names:
   308	            gh.delete_repo_rows(conn, table_name, normalized_repo)
   309	        conn.commit()
   310	
   311	    return GitHubRepoPurgeResult(
   312	        repo_full_name=normalized_repo,
   313	        dry_run=False,
   314	        row_counts=row_counts,
   315	        total_rows=total_rows,
   316	        deleted_rows=total_rows,
   317	    )
   318	
   319	
   320	def sync_github_artifacts(
   321	    database_path: Path,
   322	    repos: list[str],
   323	    *,
   324	    token: str,
   325	    since_days: int = DEFAULT_SYNC_DAYS,
   326	    on_repo_start: Callable[[str], None] | None = None,
   327	    on_repo_result: Callable[[str, GitHubKnowledgeSyncResult], None] | None = None,
   328	) -> None:
   329	    """Source-owned entry point for the GitHub artifact sync across repos.
   330	
   331	    Streaming + fail-fast: ``on_repo_start`` fires before each repo's sync and
   332	    ``on_repo_result`` after, so the caller controls per-repo progress output;
   333	    exceptions propagate (no per-repo swallowing — the loop aborts on first
   334	    failure, preserving today's behavior). CLI `github-sync-artifacts` uses this
   335	    so it no longer imports the leaf sync_github_repo
   336	    (COLLECTOR-PATH-AND-PORTABILITY-AUDIT Phase 2).
   337	    """
   338	    for repo in repos:
   339	        if on_repo_start is not None:
   340	            on_repo_start(repo)
   341	        result = sync_github_repo(
   342	            database_path=database_path,
   343	            repo_full_name=repo,
   344	            token=token,
   345	            since_days=since_days,
   346	        )
   347	        if on_repo_result is not None:
   348	            on_repo_result(repo, result)
   349	
   350	
   351	def sync_github_repo(
   352	    database_path: Path,
   353	    repo_full_name: str,
   354	    token: str,
   355	    *,
   356	    since_days: int = DEFAULT_SYNC_DAYS,
   357	    api_get_json: JsonFetcher | None = None,
   358	) -> GitHubKnowledgeSyncResult:
   359	    normalized_repo = normalize_github_repo_name(repo_full_name)
   360	    if normalized_repo in set(get_github_ignored_repos()):
   361	        raise ValueError(f"GitHub repo is ignored: {normalized_repo}")
   362	
   363	    start = time.monotonic()
   364	    fetched_at = datetime.now(timezone.utc).isoformat()
   365	    cutoff = _cutoff_iso(since_days)
   366	    api_get = api_get_json or (lambda url: _http_get_json(url, token))
   367	    repo_base = f"{GITHUB_API}/repos/{repo_full_name}"
   368	    repo_meta = api_get(repo_base)
   369	
   370	    branches = _paginate_list(f"{repo_base}/branches", api_get)
   371	    labels = _paginate_list(f"{repo_base}/labels", api_get)
   372	    milestones = _paginate_list(f"{repo_base}/milestones", api_get, state="all", sort="due_on", direction="asc")
   373	    releases = _paginate_list(f"{repo_base}/releases", api_get)
   374	    issues = [
   375	        row
   376	        for row in _paginate_list(
   377	            f"{repo_base}/issues",
   378	            api_get,
   379	            state="all",
   380	            sort="updated",
   381	            direction="desc",
   382	            since=cutoff,
   383	        )
   384	        if "pull_request" not in row
   385	    ]
   386	    pull_summaries = _paginate_list(
   387	        f"{repo_base}/pulls",
   388	        api_get,
   389	        stop_updated_before=cutoff,
   390	        state="all",
   391	        sort="updated",
   392	        direction="desc",
   393	    )
   394	
   395	    comments_synced = 0
   396	    commits_synced = 0
   397	    checks_synced = 0
   398	    docs_built = 0
   399	
   400	    with db_connection(database_path, ensure_github_schema) as conn:
   401	        gh.delete_repo_table(conn, "github_branches", repo_full_name)
   402	        gh.delete_repo_table(conn, "github_labels", repo_full_name)
   403	        gh.delete_repo_table(conn, "github_milestones", repo_full_name)
   404	        gh.delete_repo_table(conn, "github_releases", repo_full_name)
   405	
   406	        gh.upsert_repo_meta(
   407	            conn,
   408	            (
   409	                repo_full_name,
   410	                repo_meta.get("default_branch", "") if isinstance(repo_meta, dict) else "",
   411	                repo_meta.get("pushed_at") if isinstance(repo_meta, dict) else None,
   412	                repo_meta.get("updated_at") if isinstance(repo_meta, dict) else None,
   413	                repo_meta.get("open_issues_count") or 0 if isinstance(repo_meta, dict) else 0,
   414	                1 if isinstance(repo_meta, dict) and repo_meta.get("has_issues") else 0,
   415	                1 if isinstance(repo_meta, dict) and repo_meta.get("has_projects") else 0,
   416	                fetched_at,
   417	            ),
   418	        )
   419	
   420	        default_branch = repo_meta.get("default_branch", "") if isinstance(repo_meta, dict) else ""
   421	        for branch in branches:
   422	            gh.upsert_branch(
   423	                conn,
   424	                (
   425	                    repo_full_name,
   426	                    branch.get("name", ""),
   427	                    ((branch.get("commit") or {}).get("sha") or ""),
   428	                    1 if branch.get("protected") else 0,
   429	                    1 if branch.get("name", "") == default_branch else 0,
   430	                    fetched_at,
   431	                ),
   432	            )
   433	
   434	        for label in labels:
   435	            gh.upsert_label(
   436	                conn,
   437	                (
   438	                    repo_full_name,
   439	                    label.get("name", ""),
   440	                    label.get("color", ""),
   441	                    label.get("description", ""),
   442	                    1 if label.get("default") else 0,
   443	                ),
   444	            )
   445	
   446	        for milestone in milestones:
   447	            gh.upsert_milestone(
   448	                conn,
   449	                (
   450	                    repo_full_name,
   451	                    milestone.get("number"),
   452	                    milestone.get("title", ""),
   453	                    milestone.get("description", ""),
   454	                    milestone.get("state", ""),
   455	                    milestone.get("open_issues") or 0,
   456	                    milestone.get("closed_issues") or 0,
   457	                    milestone.get("due_on"),
   458	                    milestone.get("created_at"),
   459	                    milestone.get("updated_at"),
   460	                    milestone.get("closed_at"),
   461	                    milestone.get("html_url", ""),
   462	                ),
   463	            )
   464	
   465	        for release in releases:
   466	            gh.upsert_release(
   467	                conn,
   468	                (
   469	                    repo_full_name,
   470	                    release.get("id"),
   471	                    release.get("tag_name", ""),
   472	                    release.get("name", ""),
   473	                    release.get("target_commitish", ""),
   474	                    1 if release.get("draft") else 0,
   475	                    1 if release.get("prerelease") else 0,
   476	                    release.get("body", "") or "",
   477	                    release.get("created_at"),
   478	                    release.get("published_at"),
   479	                    release.get("html_url", ""),
   480	                ),
   481	            )
   482	
   483	        for issue in issues:
   484	            item_type = "issue"
   485	            item_number = int(issue["number"])
   486	            milestone = issue.get("milestone") or {}
   487	            gh.delete_item_children(conn, repo_full_name, item_type, item_number)
   488	
   489	            item_record = {
   490	                "repo_full_name": repo_full_name,
   491	                "item_type": item_type,
   492	                "number": item_number,
   493	                "node_id": issue.get("node_id", ""),
   494	                "github_id": issue.get("id"),
   495	                "title": issue.get("title", ""),
   496	                "body": issue.get("body", "") or "",
   497	                "state": issue.get("state", ""),
   498	                "state_reason": issue.get("state_reason", ""),
   499	                "author_login": (issue.get("user") or {}).get("login", ""),
   500	                "assignees_json": _json_dumps([a.get("login", "") for a in issue.get("assignees") or []]),
   501	                "labels_json": _json_dumps([l.get("name", "") for l in issue.get("labels") or []]),
   502	                "milestone_number": milestone.get("number"),
   503	                "milestone_title": milestone.get("title", ""),
   504	                "is_draft": 0,
   505	                "is_merged": 0,
   506	                "base_ref": "",
   507	                "head_ref": "",
   508	                "head_sha": "",
   509	                "mergeable_state": "",
   510	                "review_decision": "",
   511	                "check_status": "",
   512	                "requested_reviewers_json": "[]",
   513	                "comments_count": issue.get("comments") or 0,
   514	                "review_comments_count": 0,
   515	                "commits_count": 0,
   516	                "additions": 0,
   517	                "deletions": 0,
   518	                "changed_files": 0,
   519	                "html_url": issue.get("html_url", ""),
   520	                "created_at": issue.get("created_at"),

exec
/bin/zsh -lc "rg -n \"sync_github_repo|delete_item_children\\(|upsert_commit\\(|commits_synced|pull_request/commits|commits_url|since_days|github_commits\" src/rebalance/ingest/github_knowledge.py src/rebalance/ingest/github_scan.py src/rebalance/ingest/github_reconciliation.py src/rebalance/ingest/*.py" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
src/rebalance/ingest/github_reconciliation.py:257:                FROM github_commits
src/rebalance/ingest/github_knowledge.py:52:    commits_synced: int
src/rebalance/ingest/github_knowledge.py:93:    seam in :func:`sync_github_repo` keeps working. New code should construct
src/rebalance/ingest/github_knowledge.py:138:def _cutoff_iso(since_days: int) -> str:
src/rebalance/ingest/github_knowledge.py:139:    cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
src/rebalance/ingest/github_knowledge.py:266:        "github_commits",
src/rebalance/ingest/github_knowledge.py:325:    since_days: int = DEFAULT_SYNC_DAYS,
src/rebalance/ingest/github_knowledge.py:335:    so it no longer imports the leaf sync_github_repo
src/rebalance/ingest/github_knowledge.py:341:        result = sync_github_repo(
src/rebalance/ingest/github_knowledge.py:345:            since_days=since_days,
src/rebalance/ingest/github_knowledge.py:351:def sync_github_repo(
src/rebalance/ingest/github_knowledge.py:356:    since_days: int = DEFAULT_SYNC_DAYS,
src/rebalance/ingest/github_knowledge.py:365:    cutoff = _cutoff_iso(since_days)
src/rebalance/ingest/github_knowledge.py:396:    commits_synced = 0
src/rebalance/ingest/github_knowledge.py:487:            gh.delete_item_children(conn, repo_full_name, item_type, item_number)
src/rebalance/ingest/github_knowledge.py:600:            gh.delete_item_children(conn, repo_full_name, item_type, item_number)
src/rebalance/ingest/github_knowledge.py:769:                gh.upsert_commit(
src/rebalance/ingest/github_knowledge.py:783:                commits_synced += 1
src/rebalance/ingest/github_knowledge.py:844:        commits_synced=commits_synced,
src/rebalance/ingest/github_scan.py:408:    since_days: int,
src/rebalance/ingest/github_scan.py:419:    result = scan_github(token=token, days=since_days)
src/rebalance/ingest/github_scan.py:671:    since_days: int = 14,
src/rebalance/ingest/github_scan.py:679:        since_days:     How many days back to aggregate.
src/rebalance/ingest/github_scan.py:690:    since_date = (datetime.now(timezone.utc) - timedelta(days=since_days)).strftime("%Y-%m-%d")
src/rebalance/ingest/github_reconciliation.py:257:                FROM github_commits
src/rebalance/ingest/diagnose.py:29:# Mirrors github_knowledge.sync_github_repo's default lookback for issues/PRs.
src/rebalance/ingest/diagnose.py:181:    activity_repos_lower = {r.lower() for r in _activity_repos(database_path, since_days=14)}
src/rebalance/ingest/diagnose.py:221:                ("github_commits", "commits"),
src/rebalance/ingest/diagnose.py:261:                    "FROM github_commits "
src/rebalance/ingest/github_knowledge.py:52:    commits_synced: int
src/rebalance/ingest/github_knowledge.py:93:    seam in :func:`sync_github_repo` keeps working. New code should construct
src/rebalance/ingest/github_knowledge.py:138:def _cutoff_iso(since_days: int) -> str:
src/rebalance/ingest/github_knowledge.py:139:    cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
src/rebalance/ingest/github_knowledge.py:266:        "github_commits",
src/rebalance/ingest/github_knowledge.py:325:    since_days: int = DEFAULT_SYNC_DAYS,
src/rebalance/ingest/github_knowledge.py:335:    so it no longer imports the leaf sync_github_repo
src/rebalance/ingest/github_knowledge.py:341:        result = sync_github_repo(
src/rebalance/ingest/github_knowledge.py:345:            since_days=since_days,
src/rebalance/ingest/github_knowledge.py:351:def sync_github_repo(
src/rebalance/ingest/github_knowledge.py:356:    since_days: int = DEFAULT_SYNC_DAYS,
src/rebalance/ingest/github_knowledge.py:365:    cutoff = _cutoff_iso(since_days)
src/rebalance/ingest/github_knowledge.py:396:    commits_synced = 0
src/rebalance/ingest/github_knowledge.py:487:            gh.delete_item_children(conn, repo_full_name, item_type, item_number)
src/rebalance/ingest/github_knowledge.py:600:            gh.delete_item_children(conn, repo_full_name, item_type, item_number)
src/rebalance/ingest/github_knowledge.py:769:                gh.upsert_commit(
src/rebalance/ingest/github_knowledge.py:783:                commits_synced += 1
src/rebalance/ingest/github_knowledge.py:844:        commits_synced=commits_synced,
src/rebalance/ingest/github_scan.py:408:    since_days: int,
src/rebalance/ingest/github_scan.py:419:    result = scan_github(token=token, days=since_days)
src/rebalance/ingest/github_scan.py:671:    since_days: int = 14,
src/rebalance/ingest/github_scan.py:679:        since_days:     How many days back to aggregate.
src/rebalance/ingest/github_scan.py:690:    since_date = (datetime.now(timezone.utc) - timedelta(days=since_days)).strftime("%Y-%m-%d")
src/rebalance/ingest/next_actions.py:1095:    since_days: int = 7,
src/rebalance/ingest/next_actions.py:1150:                    since_days=since_days,
src/rebalance/ingest/next_actions.py:1308:    since_days: int,
src/rebalance/ingest/index_ops.py:48:        (since_days, vault_path, token, repos, ...). Unknown
src/rebalance/ingest/index_ops.py:582:def _activity_repos(database_path: Path, *, since_days: int = 14) -> list[str]:
src/rebalance/ingest/index_ops.py:586:    *since_days*, regardless of whether they appear in the project registry.
src/rebalance/ingest/index_ops.py:607:                (f"-{int(since_days)} days", WATCHED_LOGIN),
src/rebalance/ingest/index_ops.py:618:def _pushed_repos(database_path: Path, *, since_days: int = 14) -> list[str]:
src/rebalance/ingest/index_ops.py:633:            datetime.now(timezone.utc) - timedelta(days=int(since_days))
src/rebalance/ingest/index_ops.py:672:    since_days: int = 14,
src/rebalance/ingest/index_ops.py:686:    activity = _activity_repos(database_path, since_days=since_days)
src/rebalance/ingest/index_ops.py:687:    pushed = _pushed_repos(database_path, since_days=since_days)
src/rebalance/ingest/index_ops.py:719:        "since_days": since_days,
src/rebalance/ingest/index_ops.py:733:    since_days: int,
src/rebalance/ingest/index_ops.py:743:        f"github_scan(days={since_days})",
src/rebalance/ingest/index_ops.py:744:        f"sync_github_repo() x ~{len(initial_target_repos)} repos (after auto-discovery)",
src/rebalance/ingest/index_ops.py:763:    from rebalance.ingest.github_knowledge import sync_github_repo
src/rebalance/ingest/index_ops.py:771:    scan_result = scan_github(token=token, days=since_days)
src/rebalance/ingest/index_ops.py:778:            r = sync_github_repo(
src/rebalance/ingest/index_ops.py:782:                since_days=since_days,
src/rebalance/ingest/index_ops.py:790:                "commits": r.commits_synced,
src/rebalance/ingest/index_ops.py:813:                    database_path, repo, token, since_days=since_days
src/rebalance/ingest/index_ops.py:885:def _refresh_calendar(database_path: Path, *, since_days: int, dry_run: bool) -> dict[str, Any]:
src/rebalance/ingest/index_ops.py:892:        steps = [f"sync_calendar(calendar_id={OPERATOR_CALENDAR_ID!r}, days_back={since_days}) [operator]"]
src/rebalance/ingest/index_ops.py:896:                f" person={tc.person!r}, days_back={since_days})"
src/rebalance/ingest/index_ops.py:905:    logger.info("calendar sync: operator calendar_id=%s days_back=%d", OPERATOR_CALENDAR_ID, since_days)
src/rebalance/ingest/index_ops.py:910:        days_back=since_days,
src/rebalance/ingest/index_ops.py:922:            tc.person, tc.calendar_id, since_days,
src/rebalance/ingest/index_ops.py:929:                days_back=since_days,
src/rebalance/ingest/index_ops.py:1190:    since_days: int,
src/rebalance/ingest/index_ops.py:1219:        since_days=since_days,
src/rebalance/ingest/index_ops.py:1253:    since_days: int = 30,
src/rebalance/ingest/index_ops.py:1334:        "since_days": since_days,
src/rebalance/ingest/index_ops.py:1462:                    since_days=since_days,
src/rebalance/ingest/index_ops.py:1510:        since_days=opts["since_days"],
src/rebalance/ingest/index_ops.py:1517:    return _refresh_calendar(db_path, since_days=opts["since_days"], dry_run=opts["dry_run"])
src/rebalance/ingest/note_builder.py:35:    since_days: int = 14,
src/rebalance/ingest/note_builder.py:49:    since_date = (datetime.now(timezone.utc) - timedelta(days=since_days)).strftime("%Y-%m-%d")
src/rebalance/ingest/note_builder.py:110:    since_days: int
src/rebalance/ingest/note_builder.py:182:    since_days: int,
src/rebalance/ingest/note_builder.py:186:    start_date = target_date - timedelta(days=since_days - 1)
src/rebalance/ingest/note_builder.py:252:    since_days: int,
src/rebalance/ingest/note_builder.py:260:    org_activity = get_all_repo_activity_by_org(database_path, since_days=since_days)
src/rebalance/ingest/note_builder.py:264:        since_days=since_days,
src/rebalance/ingest/note_builder.py:299:        f"{len(org_activity)} org(s) in the last {since_days} days; "
src/rebalance/ingest/note_builder.py:305:        since_days=since_days,
src/rebalance/ingest/note_builder.py:312:            "calendar_since": (target_date - timedelta(days=since_days - 1)).isoformat(),
src/rebalance/ingest/note_builder.py:348:            f"Window: last {payload.since_days} days",
src/rebalance/ingest/note_builder.py:401:        f"window_days: {payload.since_days}",
src/rebalance/ingest/note_builder.py:476:        lines.append(f"- No GitHub activity in the last {payload.since_days} days.")
src/rebalance/ingest/note_builder.py:511:    since_days: int,
src/rebalance/ingest/note_builder.py:523:        since_days=since_days,
src/rebalance/ingest/querier.py:136:    since_days: int = 7,
src/rebalance/ingest/querier.py:141:    cutoff = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()
src/rebalance/ingest/querier.py:184:    since_days: int = 7,
src/rebalance/ingest/querier.py:192:            since_days=since_days,
src/rebalance/ingest/querier.py:514:    since_days: int = 7,
src/rebalance/ingest/querier.py:529:        since_days:     Window for GitHub and vault activity context.
src/rebalance/ingest/querier.py:544:    github_context = _gather_github_context(database_path, repos_map, since_days)
src/rebalance/ingest/querier.py:547:    vault_activity = _gather_vault_activity(database_path, since_days)
src/rebalance/ingest/querier.py:548:    calendar_context = _gather_calendar_context(database_path, days_forward=2, days_back=since_days)
src/rebalance/ingest/github_watch.py:7:the *existing* :func:`rebalance.ingest.github_knowledge.sync_github_repo` pipeline.
src/rebalance/ingest/github_watch.py:11:issues/PRs/commits already flow into ``github_items`` / ``github_commits`` /
src/rebalance/ingest/github_watch.py:84:    since_days: int,
src/rebalance/ingest/github_watch.py:95:    cutoff = _cutoff_iso(since_days)
src/rebalance/ingest/github_watch.py:127:    since_days: int,
src/rebalance/ingest/github_watch.py:133:    ``github_comments`` tables (so :func:`sync_github_repo` must have run first);
src/rebalance/ingest/github_watch.py:143:    cutoff_date = _cutoff_iso(since_days)[:10]
src/rebalance/ingest/github_watch.py:146:        repo, token, since_days=since_days, api_get_json=api_get_json
src/rebalance/ingest/github_watch.py:231:    since_days: int = 14,
src/rebalance/ingest/github_watch.py:245:      - cloud-agent authored commits exist in the window (``github_commits``).
src/rebalance/ingest/github_watch.py:291:                (repo, WATCHED_LOGIN, f"-{int(since_days)} days"),
src/rebalance/ingest/github_watch.py:304:                f"SELECT 1 FROM github_commits WHERE LOWER(repo_full_name)=? "
src/rebalance/ingest/github_watch.py:307:                (repo, *CLOUD_AGENT_AUTHORS, _cutoff_iso(since_days)[:10]),
src/rebalance/ingest/github_watch.py:322:    since_days: int,
src/rebalance/ingest/github_watch.py:331:    if watched_repo_is_active_work(database_path, repo, since_days=since_days):
src/rebalance/ingest/github_watch.py:335:        database_path, repo, token, since_days=since_days, api_get_json=api_get_json
src/rebalance/ingest/watchlist_guard.py:34:# since_days=30 while the watched-set windows default to 14; if the snapshot
src/rebalance/ingest/watchlist_guard.py:114:    view = get_watched_repos(database_path, since_days=CANONICAL_SINCE_DAYS)
src/rebalance/ingest/project_inference.py:783:    Reuses ``pulse._author_filter_sql`` against ``github_commits.author_login``
src/rebalance/ingest/project_inference.py:795:        FROM github_commits
src/rebalance/ingest/pulse.py:11:  - GitHub commits:     ``github_commits`` (authored by ``github_login``)
src/rebalance/ingest/pulse.py:168:        FROM github_commits c
src/rebalance/ingest/pulse.py:471:        SELECT repo_full_name, committed_at FROM github_commits

exec
/bin/zsh -lc "rg -n \"generated_by|activity_inference_v1|commit_threshold_v1|auto_promoted|project_registry\" tests src | sed -n '1,260p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
src/rebalance/doctor.py:313:                "AND name='project_registry'"
src/rebalance/doctor.py:316:                return Check("projects", WARN, "project_registry table not present")
src/rebalance/doctor.py:317:            count = conn.execute("SELECT COUNT(*) FROM project_registry").fetchone()[0]
src/rebalance/doctor.py:319:        return Check("projects", FAIL, f"could not read project_registry: {exc}")
src/rebalance/cli/ingest_cmds.py:78:def ingest_infer_project_registry(
src/rebalance/cli/ingest_cmds.py:82:    dry_run: bool = typer.Option(False, help="Preview inferred project rows without writing to project_registry"),
src/rebalance/cli/ingest_cmds.py:84:    """Infer project_registry rows from the current GitHub and Calendar activity in SQLite."""
src/rebalance/cli/ingest_cmds.py:86:    from rebalance.ingest.project_inference import infer_project_registry, sync_inferred_project_registry
src/rebalance/cli/ingest_cmds.py:96:        projects, summary = infer_project_registry(
src/rebalance/cli/ingest_cmds.py:114:    summary = sync_inferred_project_registry(
tests/test_web_auth_log.py:49:    def test_project_auto_promoted_renders_ok_badge(self) -> None:
tests/test_web_auth_log.py:54:            "event": "project_auto_promoted",
tests/test_next_actions.py:64:        INSERT INTO project_registry
tests/test_auto_promote.py:79:        marker = summary.promoted[0]["custom_fields"]["inference"]["generated_by"]
tests/test_auto_promote.py:151:                "SELECT summary FROM project_registry WHERE name = 'widget'"
tests/test_auto_promote.py:166:                "SELECT COUNT(*) AS n FROM project_registry WHERE name = 'widget'"
tests/test_auto_promote.py:191:            "rebalance.ingest.auth_log.log_project_auto_promoted"
tests/test_auto_promote.py:206:            "rebalance.ingest.auth_log.log_project_auto_promoted"
tests/test_lifecycle_contract.py:282:                    "INSERT INTO project_registry (name, status, summary, value_level,"
tests/test_lifecycle_contract.py:290:                "SELECT * FROM project_registry"
tests/test_lifecycle_contract.py:295:                "SELECT * FROM project_registry"
tests/test_watchlist_guard.py:61:                "INSERT INTO project_registry "
tests/test_watchlist_guard.py:71:            conn.execute("DELETE FROM project_registry WHERE name=?", (name,))
tests/test_health_issue_reporter.py:584:                    "INSERT INTO project_registry (name, status) VALUES ('proj', 'active')"
tests/test_external_watch.py:40:        INSERT INTO project_registry
tests/test_project_inference.py:19:from rebalance.ingest.project_inference import infer_project_registry, sync_inferred_project_registry
tests/test_project_inference.py:141:        projects, summary = infer_project_registry(
tests/test_project_inference.py:194:                INSERT INTO project_registry
tests/test_project_inference.py:208:                    json.dumps({"inference": {"generated_by": "activity_inference_v1"}}),
tests/test_project_inference.py:213:        summary = sync_inferred_project_registry(
tests/test_project_inference.py:221:            names = [row["name"] for row in conn.execute("SELECT name FROM project_registry ORDER BY name").fetchall()]
tests/test_project_inference.py:275:                INSERT INTO project_registry
tests/test_project_inference.py:294:        summary = sync_inferred_project_registry(
tests/test_project_inference.py:307:                "SELECT * FROM project_registry WHERE name = ?", ("Rebalance OS",)
tests/test_project_inference.py:315:        summary2 = sync_inferred_project_registry(
tests/test_project_inference.py:323:                "SELECT COUNT(*) AS c FROM project_registry WHERE summary = ?",
tests/test_doctor.py:82:                    "INSERT INTO project_registry (name, status) VALUES ('demo', 'active')"
tests/test_watched_repos.py:84:                INSERT INTO project_registry
src/rebalance/web.py:226:    "project_auto_promoted": ("ok",     "✓ project auto-added"),
tests/test_project_priority.py:48:                INSERT INTO project_registry
tests/test_dashboard_cli.py:36:            INSERT INTO project_registry
src/rebalance/mcp/tools/onboarding.py:123:        sync to materialize projects.yaml and the SQLite project_registry
src/rebalance/mcp/tools/projects.py:21:        """List projects from the local project_registry table."""
src/rebalance/mcp/tools/index.py:200:        "project_registry": "name",
src/rebalance/mcp/tools/index.py:217:                calendar_events, sleuth_reminders, email_messages, project_registry.
src/rebalance/ingest/note_builder.py:38:    Return all github_activity rows grouped by GitHub org, with no project_registry filter.
src/rebalance/ingest/note_builder.py:402:        "generated_by: rebalance",
src/rebalance/ingest/project_classifier.py:164:    """Load canonical project matchers from project_registry, or config fallback.
src/rebalance/ingest/project_classifier.py:177:            WHERE type = 'table' AND name = 'project_registry'
src/rebalance/ingest/project_classifier.py:186:            FROM project_registry
src/rebalance/ingest/auth_log.py:329:def log_project_auto_promoted(
src/rebalance/ingest/auth_log.py:337:    ``project_registry`` as a machine-owned row. Emitted by
src/rebalance/ingest/auth_log.py:340:    _append("registry", "project_auto_promoted", {
src/rebalance/ingest/config.py:955:        watched repo into project_registry as a machine_owned row (generated_by
src/rebalance/ingest/config.py:956:        "commit_threshold_v1"). github_ignored_repos always wins regardless of this
src/rebalance/ingest/registry.py:133:        # round-trips through the project_registry table without a schema column
src/rebalance/ingest/registry.py:140:        # so it round-trips through the fixed project_registry columns.
src/rebalance/ingest/registry.py:173:                INSERT INTO project_registry (
src/rebalance/ingest/registry.py:280:    """Fetch projects from the project_registry table.
src/rebalance/ingest/registry.py:298:            "FROM project_registry"
src/rebalance/ingest/index_ops.py:836:    # just crossed the operator-commit threshold graduates into project_registry
src/rebalance/ingest/db/schema.py:609:    """Create project_registry table if it doesn't exist."""
src/rebalance/ingest/db/schema.py:611:        CREATE TABLE IF NOT EXISTS project_registry (
src/rebalance/ingest/lifecycle.py:118:            "project_registry table."
src/rebalance/ingest/lifecycle.py:135:        owner="rebalance.ingest.project_inference:sync_inferred_project_registry",
src/rebalance/ingest/lifecycle.py:139:            "custom_fields.inference.generated_by. Maintains only rows it "
src/rebalance/ingest/lifecycle.py:304:        return False, f"could not read project_registry: {exc}"
src/rebalance/ingest/weekly_report.py:110:            "generated_by: rebalance",
src/rebalance/ingest/project_inference.py:62:INFERENCE_GENERATED_BY = "activity_inference_v1"
src/rebalance/ingest/project_inference.py:69:COMMIT_THRESHOLD_GENERATED_BY = "commit_threshold_v1"
src/rebalance/ingest/project_inference.py:78:    generated_by = ((custom_fields or {}).get("inference") or {}).get("generated_by")
src/rebalance/ingest/project_inference.py:79:    return generated_by in _MACHINE_OWNED_MARKERS
src/rebalance/ingest/project_inference.py:654:                "generated_by": INFERENCE_GENERATED_BY,
src/rebalance/ingest/project_inference.py:669:            "SELECT name, custom_fields_json FROM project_registry"
src/rebalance/ingest/project_inference.py:678:            conn.executemany("DELETE FROM project_registry WHERE name = ?", [(name,) for name in stale_names])
src/rebalance/ingest/project_inference.py:688:    A name already present in project_registry WITHOUT the inference marker is
src/rebalance/ingest/project_inference.py:694:            "SELECT name, custom_fields_json FROM project_registry"
src/rebalance/ingest/project_inference.py:704:def infer_project_registry(
src/rebalance/ingest/project_inference.py:744:def sync_inferred_project_registry(
src/rebalance/ingest/project_inference.py:751:    projects, summary = infer_project_registry(
src/rebalance/ingest/project_inference.py:804:    """Build a machine-owned project_registry row for one auto-promoted repo.
src/rebalance/ingest/project_inference.py:821:            "provenance": "auto_promoted",
src/rebalance/ingest/project_inference.py:823:                "generated_by": COMMIT_THRESHOLD_GENERATED_BY,
src/rebalance/ingest/project_inference.py:849:    """GH-124: auto-promote a watched repo into ``project_registry`` once the
src/rebalance/ingest/project_inference.py:864:    ``sync_inferred_project_registry``.
src/rebalance/ingest/project_inference.py:893:        from rebalance.ingest.auth_log import log_project_auto_promoted
src/rebalance/ingest/project_inference.py:897:            log_project_auto_promoted(

exec
/bin/zsh -lc "nl -ba src/rebalance/ingest/github_knowledge.py | sed -n '480,810p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
   480	                ),
   481	            )
   482	
   483	        for issue in issues:
   484	            item_type = "issue"
   485	            item_number = int(issue["number"])
   486	            milestone = issue.get("milestone") or {}
   487	            gh.delete_item_children(conn, repo_full_name, item_type, item_number)
   488	
   489	            item_record = {
   490	                "repo_full_name": repo_full_name,
   491	                "item_type": item_type,
   492	                "number": item_number,
   493	                "node_id": issue.get("node_id", ""),
   494	                "github_id": issue.get("id"),
   495	                "title": issue.get("title", ""),
   496	                "body": issue.get("body", "") or "",
   497	                "state": issue.get("state", ""),
   498	                "state_reason": issue.get("state_reason", ""),
   499	                "author_login": (issue.get("user") or {}).get("login", ""),
   500	                "assignees_json": _json_dumps([a.get("login", "") for a in issue.get("assignees") or []]),
   501	                "labels_json": _json_dumps([l.get("name", "") for l in issue.get("labels") or []]),
   502	                "milestone_number": milestone.get("number"),
   503	                "milestone_title": milestone.get("title", ""),
   504	                "is_draft": 0,
   505	                "is_merged": 0,
   506	                "base_ref": "",
   507	                "head_ref": "",
   508	                "head_sha": "",
   509	                "mergeable_state": "",
   510	                "review_decision": "",
   511	                "check_status": "",
   512	                "requested_reviewers_json": "[]",
   513	                "comments_count": issue.get("comments") or 0,
   514	                "review_comments_count": 0,
   515	                "commits_count": 0,
   516	                "additions": 0,
   517	                "deletions": 0,
   518	                "changed_files": 0,
   519	                "html_url": issue.get("html_url", ""),
   520	                "created_at": issue.get("created_at"),
   521	                "updated_at": issue.get("updated_at"),
   522	                "closed_at": issue.get("closed_at"),
   523	                "merged_at": None,
   524	                "fetched_at": fetched_at,
   525	            }
   526	
   527	            gh.upsert_item(conn, item_record)
   528	
   529	            issue_comments = _paginate_list(f"{repo_base}/issues/{item_number}/comments", api_get)
   530	            for comment in issue_comments:
   531	                body = comment.get("body", "") or ""
   532	                gh.upsert_comment(
   533	                    conn,
   534	                    (
   535	                        repo_full_name,
   536	                        item_type,
   537	                        item_number,
   538	                        "issue_comment",
   539	                        comment.get("id"),
   540	                        (comment.get("user") or {}).get("login", ""),
   541	                        comment.get("author_association", ""),
   542	                        body,
   543	                        "",
   544	                        None,
   545	                        comment.get("html_url", ""),
   546	                        comment.get("created_at"),
   547	                        comment.get("updated_at"),
   548	                        fetched_at,
   549	                    ),
   550	                )
   551	                comments_synced += 1
   552	                if body.strip():
   553	                    _insert_document(
   554	                        conn,
   555	                        repo_full_name=repo_full_name,
   556	                        source_type=item_type,
   557	                        source_number=item_number,
   558	                        doc_type="issue_comment",
   559	                        source_key=f"{repo_full_name}:{item_type}:{item_number}:issue_comment:{comment.get('id')}",
   560	                        title=item_record["title"],
   561	                        body=_comment_doc_text(item_type, item_number, "issue_comment", body),
   562	                        updated_at=comment.get("updated_at") or fetched_at,
   563	                        fetched_at=fetched_at,
   564	                    )
   565	                    docs_built += 1
   566	
   567	            if item_record["body"].strip():
   568	                _insert_document(
   569	                    conn,
   570	                    repo_full_name=repo_full_name,
   571	                    source_type=item_type,
   572	                    source_number=item_number,
   573	                    doc_type="item_body",
   574	                    source_key=f"{repo_full_name}:{item_type}:{item_number}:item",
   575	                    title=item_record["title"],
   576	                    body=_item_doc_text(item_record),
   577	                    updated_at=item_record["updated_at"] or fetched_at,
   578	                    fetched_at=fetched_at,
   579	                )
   580	                docs_built += 1
   581	
   582	        for pull_summary in pull_summaries:
   583	            item_type = "pull_request"
   584	            item_number = int(pull_summary["number"])
   585	            pr = api_get(f"{repo_base}/pulls/{item_number}")
   586	            if not isinstance(pr, dict):
   587	                continue
   588	
   589	            issue_comments = _paginate_list(f"{repo_base}/issues/{item_number}/comments", api_get)
   590	            reviews = _paginate_list(f"{repo_base}/pulls/{item_number}/reviews", api_get)
   591	            review_comments = _paginate_list(f"{repo_base}/pulls/{item_number}/comments", api_get)
   592	            commits = _paginate_list(f"{repo_base}/pulls/{item_number}/commits", api_get)
   593	            check_runs_resp = api_get(_build_url(f"{repo_base}/commits/{pr.get('head', {}).get('sha', '')}/check-runs", per_page=100))
   594	            check_runs = (
   595	                check_runs_resp.get("check_runs", [])
   596	                if isinstance(check_runs_resp, dict)
   597	                else []
   598	            )
   599	            milestone = pr.get("milestone") or {}
   600	            gh.delete_item_children(conn, repo_full_name, item_type, item_number)
   601	
   602	            item_record = {
   603	                "repo_full_name": repo_full_name,
   604	                "item_type": item_type,
   605	                "number": item_number,
   606	                "node_id": pr.get("node_id", ""),
   607	                "github_id": pr.get("id"),
   608	                "title": pr.get("title", ""),
   609	                "body": pr.get("body", "") or "",
   610	                "state": pr.get("state", ""),
   611	                "state_reason": "",
   612	                "author_login": (pr.get("user") or {}).get("login", ""),
   613	                "assignees_json": _json_dumps([a.get("login", "") for a in pr.get("assignees") or []]),
   614	                "labels_json": _json_dumps([l.get("name", "") for l in pr.get("labels") or []]),
   615	                "milestone_number": milestone.get("number"),
   616	                "milestone_title": milestone.get("title", ""),
   617	                "is_draft": 1 if pr.get("draft") else 0,
   618	                "is_merged": 1 if pr.get("merged_at") else 0,
   619	                "base_ref": (pr.get("base") or {}).get("ref", ""),
   620	                "head_ref": (pr.get("head") or {}).get("ref", ""),
   621	                "head_sha": (pr.get("head") or {}).get("sha", ""),
   622	                "mergeable_state": pr.get("mergeable_state", ""),
   623	                "review_decision": _review_decision(reviews),
   624	                "check_status": _check_rollup(check_runs),
   625	                "requested_reviewers_json": _json_dumps([r.get("login", "") for r in pr.get("requested_reviewers") or []]),
   626	                "comments_count": pr.get("comments") or 0,
   627	                "review_comments_count": pr.get("review_comments") or 0,
   628	                "commits_count": pr.get("commits") or 0,
   629	                "additions": pr.get("additions") or 0,
   630	                "deletions": pr.get("deletions") or 0,
   631	                "changed_files": pr.get("changed_files") or 0,
   632	                "html_url": pr.get("html_url", ""),
   633	                "created_at": pr.get("created_at"),
   634	                "updated_at": pr.get("updated_at"),
   635	                "closed_at": pr.get("closed_at"),
   636	                "merged_at": pr.get("merged_at"),
   637	                "fetched_at": fetched_at,
   638	            }
   639	
   640	            gh.upsert_item(conn, item_record)
   641	
   642	            combined_text = "\n".join(filter(None, [item_record["title"], item_record["body"]]))
   643	            for link_kind, issue_number in _parse_links(combined_text):
   644	                gh.upsert_link(
   645	                    conn,
   646	                    (repo_full_name, item_type, item_number, "issue", issue_number, link_kind),
   647	                )
   648	
   649	            for comment in issue_comments:
   650	                body = comment.get("body", "") or ""
   651	                gh.upsert_comment(
   652	                    conn,
   653	                    (
   654	                        repo_full_name,
   655	                        item_type,
   656	                        item_number,
   657	                        "issue_comment",
   658	                        comment.get("id"),
   659	                        (comment.get("user") or {}).get("login", ""),
   660	                        comment.get("author_association", ""),
   661	                        body,
   662	                        "",
   663	                        None,
   664	                        comment.get("html_url", ""),
   665	                        comment.get("created_at"),
   666	                        comment.get("updated_at"),
   667	                        fetched_at,
   668	                    ),
   669	                )
   670	                comments_synced += 1
   671	                if body.strip():
   672	                    _insert_document(
   673	                        conn,
   674	                        repo_full_name=repo_full_name,
   675	                        source_type=item_type,
   676	                        source_number=item_number,
   677	                        doc_type="issue_comment",
   678	                        source_key=f"{repo_full_name}:{item_type}:{item_number}:issue_comment:{comment.get('id')}",
   679	                        title=item_record["title"],
   680	                        body=_comment_doc_text(item_type, item_number, "issue_comment", body),
   681	                        updated_at=comment.get("updated_at") or fetched_at,
   682	                        fetched_at=fetched_at,
   683	                    )
   684	                    docs_built += 1
   685	
   686	            for review in reviews:
   687	                body = review.get("body", "") or ""
   688	                gh.upsert_comment(
   689	                    conn,
   690	                    (
   691	                        repo_full_name,
   692	                        item_type,
   693	                        item_number,
   694	                        "review",
   695	                        review.get("id"),
   696	                        (review.get("user") or {}).get("login", ""),
   697	                        review.get("author_association", ""),
   698	                        body,
   699	                        review.get("state", ""),
   700	                        None,
   701	                        review.get("html_url", ""),
   702	                        review.get("submitted_at"),
   703	                        review.get("submitted_at"),
   704	                        fetched_at,
   705	                    ),
   706	                )
   707	                comments_synced += 1
   708	                if body.strip():
   709	                    _insert_document(
   710	                        conn,
   711	                        repo_full_name=repo_full_name,
   712	                        source_type=item_type,
   713	                        source_number=item_number,
   714	                        doc_type="review",
   715	                        source_key=f"{repo_full_name}:{item_type}:{item_number}:review:{review.get('id')}",
   716	                        title=item_record["title"],
   717	                        body=_comment_doc_text(
   718	                            item_type,
   719	                            item_number,
   720	                            "review",
   721	                            body,
   722	                            review_state=review.get("state", ""),
   723	                        ),
   724	                        updated_at=review.get("submitted_at") or fetched_at,
   725	                        fetched_at=fetched_at,
   726	                    )
   727	                    docs_built += 1
   728	
   729	            for comment in review_comments:
   730	                body = comment.get("body", "") or ""
   731	                gh.upsert_comment(
   732	                    conn,
   733	                    (
   734	                        repo_full_name,
   735	                        item_type,
   736	                        item_number,
   737	                        "review_comment",
   738	                        comment.get("id"),
   739	                        (comment.get("user") or {}).get("login", ""),
   740	                        comment.get("author_association", ""),
   741	                        body,
   742	                        "",
   743	                        comment.get("in_reply_to_id"),
   744	                        comment.get("html_url", ""),
   745	                        comment.get("created_at"),
   746	                        comment.get("updated_at"),
   747	                        fetched_at,
   748	                    ),
   749	                )
   750	                comments_synced += 1
   751	                if body.strip():
   752	                    _insert_document(
   753	                        conn,
   754	                        repo_full_name=repo_full_name,
   755	                        source_type=item_type,
   756	                        source_number=item_number,
   757	                        doc_type="review_comment",
   758	                        source_key=f"{repo_full_name}:{item_type}:{item_number}:review_comment:{comment.get('id')}",
   759	                        title=item_record["title"],
   760	                        body=_comment_doc_text(item_type, item_number, "review_comment", body),
   761	                        updated_at=comment.get("updated_at") or fetched_at,
   762	                        fetched_at=fetched_at,
   763	                    )
   764	                    docs_built += 1
   765	
   766	            for commit in commits:
   767	                sha = commit.get("sha", "")
   768	                message = ((commit.get("commit") or {}).get("message") or "").strip()
   769	                gh.upsert_commit(
   770	                    conn,
   771	                    (
   772	                        repo_full_name,
   773	                        item_type,
   774	                        item_number,
   775	                        sha,
   776	                        ((commit.get("author") or {}).get("login") or ""),
   777	                        message,
   778	                        ((commit.get("commit") or {}).get("author") or {}).get("date"),
   779	                        commit.get("html_url", ""),
   780	                        fetched_at,
   781	                    ),
   782	                )
   783	                commits_synced += 1
   784	                if message:
   785	                    _insert_document(
   786	                        conn,
   787	                        repo_full_name=repo_full_name,
   788	                        source_type=item_type,
   789	                        source_number=item_number,
   790	                        doc_type="commit_message",
   791	                        source_key=f"{repo_full_name}:{item_type}:{item_number}:commit:{sha}",
   792	                        title=item_record["title"],
   793	                        body=_commit_doc_text(item_type, item_number, sha, message),
   794	                        updated_at=((commit.get("commit") or {}).get("author") or {}).get("date") or fetched_at,
   795	                        fetched_at=fetched_at,
   796	                    )
   797	                    docs_built += 1
   798	
   799	            for run in check_runs:
   800	                gh.upsert_check_run(
   801	                    conn,
   802	                    (
   803	                        repo_full_name,
   804	                        item_type,
   805	                        item_number,
   806	                        item_record["head_sha"],
   807	                        run.get("name", ""),
   808	                        run.get("status", ""),
   809	                        run.get("conclusion", ""),
   810	                        run.get("details_url", "") or run.get("html_url", ""),

exec
/bin/zsh -lc "nl -ba src/rebalance/ingest/registry.py | sed -n '260,390p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
   260	            f"potential_projects={len(registry.potential_projects)}"
   261	        )
   262	
   263	    write_projection(projects_yaml_path=projects_yaml_path, projection=projection)
   264	    upserted = sync_db(database_path=database_path, projection=projection)
   265	    return (
   266	        f"Sync pull complete: wrote {projects_yaml_path}, upserted {upserted} rows into "
   267	        f"{database_path}"
   268	    )
   269	
   270	
   271	# ---------------------------------------------------------------------------
   272	# Centralized project DB reader — single source of truth
   273	# ---------------------------------------------------------------------------
   274	
   275	
   276	def get_projects(
   277	    database_path: Path,
   278	    status: str | None = None,
   279	) -> list[dict[str, Any]]:
   280	    """Fetch projects from the project_registry table.
   281	
   282	    Returns a list of dicts with ``repos`` (list), ``tags`` (list), and
   283	    ``custom_fields`` (dict) already decoded from their ``*_json`` columns.
   284	
   285	    This is the **canonical** way to read projects from SQLite.  All callers
   286	    (MCP server, querier, project classifier, etc.) should use this instead
   287	    of writing their own SQL + JSON-parsing logic.
   288	    """
   289	    if not database_path.exists():
   290	        return []
   291	
   292	    from rebalance.ingest.db import db_connection, ensure_project_schema
   293	
   294	    with db_connection(database_path, ensure_project_schema) as conn:
   295	        query = (
   296	            "SELECT name, status, summary, value_level, priority_tier, "
   297	            "risk_level, repos_json, tags_json, custom_fields_json "
   298	            "FROM project_registry"
   299	        )
   300	        params: tuple[Any, ...] = ()
   301	        if status:
   302	            query += " WHERE status = ?"
   303	            params = (status,)
   304	        query += " ORDER BY name ASC"
   305	
   306	        rows = conn.execute(query, params).fetchall()
   307	
   308	    result: list[dict[str, Any]] = []
   309	    for row in rows:
   310	        d = dict(row)
   311	        # Decode *_json columns into native Python types
   312	        for json_col, target_key, default in (
   313	            ("repos_json", "repos", []),
   314	            ("tags_json", "tags", []),
   315	            ("custom_fields_json", "custom_fields", {}),
   316	        ):
   317	            raw = d.pop(json_col, None)
   318	            try:
   319	                d[target_key] = json.loads(raw) if raw else default
   320	            except (json.JSONDecodeError, ValueError):
   321	                d[target_key] = default
   322	        # Lift provenance back to the top level so DB reads match the
   323	        # candidate/Project shape (it is persisted inside custom_fields).
   324	        d["provenance"] = (d["custom_fields"] or {}).get("provenance", "")
   325	        result.append(d)
   326	    return result
   327	
   328	
   329	def effective_client(custom_fields: dict[str, Any] | None) -> str | None:
   330	    """Resolve a project's client curated-first.
   331	
   332	    Curated config ``client`` (operator-set priority rule) always wins; the
   333	    machine-inferred ``client_inferred`` (owner-as-client) is the fallback;
   334	    neither present → None (the ``(unassigned)`` bucket on read).
   335	    """
   336	    cf = custom_fields or {}
   337	    return cf.get("client") or cf.get("client_inferred") or None
   338	
   339	
   340	def get_clients(database_path: Path) -> dict[str, list[str]]:
   341	    """Group project names by effective client. Derived view, not stored state.
   342	
   343	    The "discrete client buckets" the next-action synthesis groups by. No
   344	    ``client_registry`` table exists — clients are an attribute of a project
   345	    (``custom_fields.client`` curated, ``client_inferred`` machine-owned).
   346	    """
   347	    from collections import defaultdict
   348	
   349	    buckets: dict[str, list[str]] = defaultdict(list)
   350	    for project in get_projects(database_path):
   351	        client = effective_client(project.get("custom_fields")) or "(unassigned)"
   352	        buckets[client].append(project["name"])
   353	    return dict(buckets)
   354	
   355	
   356	def get_external_repos(database_path: Path) -> list[str]:
   357	    """Return the external/watched repos declared in the project registry.
   358	
   359	    These are repos from any project flagged ``external: true`` (persisted in
   360	    ``custom_fields_json``) — monitored for everyone's activity, regardless of
   361	    project status. Normalized to ``owner/name`` and de-duplicated. This is the
   362	    source consumed by ``get_watched_repos`` and the watched-repo rollup.
   363	    """
   364	    from rebalance.ingest.config import normalize_github_repo_name
   365	
   366	    repos: list[str] = []
   367	    for project in get_projects(database_path):
   368	        custom_fields = project.get("custom_fields") or {}
   369	        if not custom_fields.get("external"):
   370	            continue
   371	        for repo in project.get("repos") or []:
   372	            try:
   373	                normalized = normalize_github_repo_name(repo)
   374	            except ValueError:
   375	                continue
   376	            if normalized not in repos:
   377	                repos.append(normalized)
   378	    return repos

exec
/bin/zsh -lc "nl -ba tests/test_project_inference.py | sed -n '180,340p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
   180	                    "2026-04-28",
   181	                    10,
   182	                    10,
   183	                    0,
   184	                    0,
   185	                    0,
   186	                    0,
   187	                    0,
   188	                    "2026-04-27T19:11:32Z",
   189	                    "2026-04-28T14:47:36Z",
   190	                ),
   191	            )
   192	            conn.execute(
   193	                """
   194	                INSERT INTO project_registry
   195	                    (name, status, summary, value_level, priority_tier, risk_level,
   196	                     repos_json, tags_json, custom_fields_json)
   197	                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
   198	                """,
   199	                (
   200	                    "Old Project",
   201	                    "active",
   202	                    "",
   203	                    None,
   204	                    None,
   205	                    None,
   206	                    "[]",
   207	                    "[]",
   208	                    json.dumps({"inference": {"generated_by": "activity_inference_v1"}}),
   209	                ),
   210	            )
   211	            conn.commit()
   212	
   213	        summary = sync_inferred_project_registry(
   214	            db_path,
   215	            calendar_config=self._calendar_config(),
   216	        )
   217	        self.assertGreaterEqual(summary.updated_count, 1)
   218	        self.assertEqual(summary.deleted_stale_inferred_count, 1)
   219	
   220	        with db_connection(db_path, ensure_project_schema) as conn:
   221	            names = [row["name"] for row in conn.execute("SELECT name FROM project_registry ORDER BY name").fetchall()]
   222	        self.assertIn("Rebalance OS", names)
   223	        self.assertNotIn("Old Project", names)
   224	
   225	
   226	class CuratedRowProtectionTests(unittest.TestCase):
   227	    """machine_owned contract: inference never creates, updates, or deletes
   228	    a row the operator curated — even on a name collision."""
   229	
   230	    def setUp(self) -> None:
   231	        self._tmp = tempfile.TemporaryDirectory()
   232	        self.addCleanup(self._tmp.cleanup)
   233	        self._orig_path = config_module.CONFIG_PATH
   234	        config_module.CONFIG_PATH = Path(self._tmp.name) / "rbos.config"
   235	
   236	    def tearDown(self) -> None:
   237	        config_module.CONFIG_PATH = self._orig_path
   238	
   239	    def _calendar_config(self) -> CalendarConfig:
   240	        return CalendarConfig(
   241	            calendar_id="primary",
   242	            exclude_titles=[],
   243	            aggregator_skip_words=[],
   244	            timezone="America/Los_Angeles",
   245	            projects=[],
   246	            hours_format="decimal",
   247	        )
   248	
   249	    def test_curated_row_with_colliding_name_is_never_overwritten(self) -> None:
   250	        db_path = Path(self._tmp.name) / "rebalance.db"
   251	        curated_fields = {"aliases": ["rebalance"], "priority_source": "operator"}
   252	        with db_connection(db_path) as conn:
   253	            ensure_github_schema(conn)
   254	            ensure_calendar_schema(conn)
   255	            ensure_project_schema(conn)
   256	            conn.execute(
   257	                """
   258	                INSERT INTO github_activity
   259	                    (login, repo_full_name, scan_date, commits, pushes, prs_opened, prs_merged,
   260	                     issues_opened, issue_comments, reviews, last_active_at, scanned_at)
   261	                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
   262	                """,
   263	                (
   264	                    "tester",
   265	                    "Hypercart-Dev-Tools/rebalance-OS",
   266	                    "2026-04-28",
   267	                    10, 10, 0, 0, 0, 0, 0,
   268	                    "2026-04-27T19:11:32Z",
   269	                    "2026-04-28T14:47:36Z",
   270	                ),
   271	            )
   272	            # Operator-curated row whose name collides with the inferred seed.
   273	            conn.execute(
   274	                """
   275	                INSERT INTO project_registry
   276	                    (name, status, summary, value_level, priority_tier, risk_level,
   277	                     repos_json, tags_json, custom_fields_json)
   278	                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
   279	                """,
   280	                (
   281	                    "Rebalance OS",
   282	                    "active",
   283	                    "CURATED - operator owned",
   284	                    "high",
   285	                    1,
   286	                    None,
   287	                    json.dumps(["Hypercart-Dev-Tools/rebalance-OS"]),
   288	                    json.dumps(["curated"]),
   289	                    json.dumps(curated_fields),
   290	                ),
   291	            )
   292	            conn.commit()
   293	
   294	        summary = sync_inferred_project_registry(
   295	            db_path,
   296	            calendar_config=self._calendar_config(),
   297	        )
   298	
   299	        self.assertIn("Rebalance OS", summary.project_names)  # still inferred...
   300	        self.assertEqual(summary.skipped_curated_names, ["Rebalance OS"])  # ...but skipped
   301	        self.assertEqual(summary.skipped_curated_count, 1)
   302	        self.assertEqual(summary.updated_count, 0)
   303	        self.assertEqual(summary.deleted_stale_inferred_count, 0)
   304	
   305	        with db_connection(db_path, ensure_project_schema) as conn:
   306	            row = conn.execute(
   307	                "SELECT * FROM project_registry WHERE name = ?", ("Rebalance OS",)
   308	            ).fetchone()
   309	        self.assertEqual(row["summary"], "CURATED - operator owned")
   310	        self.assertEqual(row["priority_tier"], 1)
   311	        self.assertEqual(row["value_level"], "high")
   312	        self.assertEqual(json.loads(row["custom_fields_json"]), curated_fields)
   313	
   314	        # Repeat sync is idempotent: curated row still untouched, never deleted.
   315	        summary2 = sync_inferred_project_registry(
   316	            db_path,
   317	            calendar_config=self._calendar_config(),
   318	        )
   319	        self.assertEqual(summary2.skipped_curated_names, ["Rebalance OS"])
   320	        self.assertEqual(summary2.deleted_stale_inferred_count, 0)
   321	        with db_connection(db_path, ensure_project_schema) as conn:
   322	            count = conn.execute(
   323	                "SELECT COUNT(*) AS c FROM project_registry WHERE summary = ?",
   324	                ("CURATED - operator owned",),
   325	            ).fetchone()["c"]
   326	        self.assertEqual(count, 1)

exec
/bin/zsh -lc "nl -ba src/rebalance/ingest/lifecycle.py | sed -n '120,150p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
   120	    ),
   121	    ProjectStage(
   122	        id="persistence",
   123	        title="Persistence",
   124	        owner="rebalance.ingest.registry:sync_registry",
   125	        write_semantics="confirmation_gated",
   126	        description=(
   127	            "Materializes the confirmed registry into projects.yaml and "
   128	            "SQLite. Deterministic projection of confirmed state — runs only "
   129	            "downstream of confirmation or an explicit operator sync command."
   130	        ),
   131	    ),
   132	    ProjectStage(
   133	        id="inference",
   134	        title="Inference",
   135	        owner="rebalance.ingest.project_inference:sync_inferred_project_registry",
   136	        write_semantics="machine_owned",
   137	        description=(
   138	            "Activity-derived project rows, marked by "
   139	            "custom_fields.inference.generated_by. Maintains only rows it "
   140	            "created: curated rows are never created, updated, or deleted by "
   141	            "inference — operator state always wins."
   142	        ),
   143	    ),
   144	    ProjectStage(
   145	        id="prioritization",
   146	        title="Prioritization",
   147	        owner="rebalance.ingest.project_priority:apply_project_priorities",
   148	        write_semantics="read_time_overlay",
   149	        description=(
   150	            "Operator priority rules from temp/rbos.config overlay scores at "

exec
/bin/zsh -lc "nl -ba src/rebalance/ingest/index_ops.py | sed -n '540,605p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
   540	        vault_path=vault_path,
   541	        database_path=database_path,
   542	        exclude_patterns=[".obsidian/*", ".trash/*", "node_modules/*", ".git/*", ".venv/*", "*/.venv/*"],
   543	        dry_run=False,
   544	    )
   545	    embed_result = embed_chunks(database_path=database_path)
   546	
   547	    return {
   548	        "scope": "vault",
   549	        "dry_run": False,
   550	        "ingest": {
   551	            "total_files": ingest_result.total_files,
   552	            "new_files": ingest_result.new_files,
   553	            "updated_files": ingest_result.updated_files,
   554	            "touched_files": ingest_result.touched_files,
   555	            "deleted_files": ingest_result.deleted_files,
   556	            "total_chunks": ingest_result.total_chunks,
   557	            "elapsed_seconds": ingest_result.elapsed_seconds,
   558	        },
   559	        "embed_chunks": {
   560	            "total_chunks": embed_result.total_chunks,
   561	            "embedded": embed_result.embedded_chunks,
   562	            "skipped_unchanged": embed_result.skipped_unchanged,
   563	            "elapsed_seconds": embed_result.elapsed_seconds,
   564	        },
   565	    }
   566	
   567	
   568	def _project_repos(database_path: Path) -> list[str]:
   569	    """Repos drawn from the active project registry (operator-curated)."""
   570	    repos: list[str] = []
   571	    try:
   572	        for project in get_projects(database_path, status="active"):
   573	            for repo in project.get("repos") or []:
   574	                r = repo.strip()
   575	                if r and r not in repos:
   576	                    repos.append(r)
   577	    except Exception:
   578	        pass
   579	    return repos
   580	
   581	
   582	def _activity_repos(database_path: Path, *, since_days: int = 14) -> list[str]:
   583	    """Repos with recent activity according to ``github_activity``.
   584	
   585	    These are repos the user has *actually worked in* on GitHub in the last
   586	    *since_days*, regardless of whether they appear in the project registry.
   587	    Passive events such as starring/watching a repo may create GitHub Events
   588	    API entries, but they must not auto-monitor a repo.
   589	    """
   590	    from rebalance.ingest.github_watch import WATCHED_LOGIN
   591	
   592	    repos: list[str] = []
   593	    try:
   594	        with db_connection(database_path) as conn:
   595	            rows = conn.execute(
   596	                """
   597	                SELECT DISTINCT repo_full_name
   598	                FROM github_activity
   599	                WHERE scan_date >= date('now', ?)
   600	                  AND login != ?
   601	                  AND (
   602	                    commits + pushes + prs_opened + prs_merged
   603	                    + issues_opened + issue_comments + reviews
   604	                  ) > 0
   605	                ORDER BY repo_full_name

exec
/bin/zsh -lc "nl -ba tests/test_watched_repos.py | sed -n '1,220p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
     1	"""Tests for canonical GitHub watched-repo selection."""
     2	
     3	from __future__ import annotations
     4	
     5	import tempfile
     6	import unittest
     7	from pathlib import Path
     8	
     9	from rebalance.ingest import config as config_module
    10	from rebalance.ingest.db import db_connection, ensure_github_schema, ensure_project_schema
    11	from rebalance.ingest.index_ops import get_watched_repos
    12	
    13	
    14	class WatchedReposTests(unittest.TestCase):
    15	    def setUp(self) -> None:
    16	        self._tmp = tempfile.TemporaryDirectory()
    17	        self.addCleanup(self._tmp.cleanup)
    18	        self._orig_config_path = config_module.CONFIG_PATH
    19	        config_module.CONFIG_PATH = Path(self._tmp.name) / "rbos.config"
    20	
    21	    def tearDown(self) -> None:
    22	        config_module.CONFIG_PATH = self._orig_config_path
    23	
    24	    def test_zero_work_activity_does_not_auto_watch_repo(self) -> None:
    25	        db_path = Path(self._tmp.name) / "rebalance.db"
    26	        with db_connection(db_path) as conn:
    27	            ensure_github_schema(conn)
    28	            conn.execute(
    29	                """
    30	                INSERT INTO github_activity
    31	                    (login, repo_full_name, scan_date, commits, pushes, prs_opened, prs_merged,
    32	                     issues_opened, issue_comments, reviews, last_active_at, scanned_at)
    33	                VALUES (?, ?, date('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?)
    34	                """,
    35	                (
    36	                    "tester",
    37	                    "example/starred",
    38	                    0,
    39	                    0,
    40	                    0,
    41	                    0,
    42	                    0,
    43	                    0,
    44	                    0,
    45	                    "2026-05-04T12:00:00Z",
    46	                    "2026-05-04T12:05:00Z",
    47	                ),
    48	            )
    49	            conn.execute(
    50	                """
    51	                INSERT INTO github_activity
    52	                    (login, repo_full_name, scan_date, commits, pushes, prs_opened, prs_merged,
    53	                     issues_opened, issue_comments, reviews, last_active_at, scanned_at)
    54	                VALUES (?, ?, date('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?)
    55	                """,
    56	                (
    57	                    "tester",
    58	                    "example/worked",
    59	                    1,
    60	                    1,
    61	                    0,
    62	                    0,
    63	                    0,
    64	                    0,
    65	                    0,
    66	                    "2026-05-04T13:00:00Z",
    67	                    "2026-05-04T13:05:00Z",
    68	                ),
    69	            )
    70	            conn.commit()
    71	
    72	        watched = get_watched_repos(db_path)
    73	
    74	        self.assertNotIn("example/starred", watched["watched"])
    75	        self.assertNotIn("example/starred", watched["activity_repos"])
    76	        self.assertEqual(watched["watched"], ["example/worked"])
    77	
    78	    def test_active_project_repo_is_watched_even_without_recent_activity(self) -> None:
    79	        db_path = Path(self._tmp.name) / "rebalance.db"
    80	        with db_connection(db_path) as conn:
    81	            ensure_project_schema(conn)
    82	            conn.execute(
    83	                """
    84	                INSERT INTO project_registry
    85	                    (name, status, summary, value_level, priority_tier, risk_level,
    86	                     repos_json, tags_json, custom_fields_json)
    87	                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    88	                """,
    89	                (
    90	                    "Owned Repo",
    91	                    "active",
    92	                    "",
    93	                    None,
    94	                    None,
    95	                    None,
    96	                    '["example/owned"]',
    97	                    "[]",
    98	                    "{}",
    99	                ),
   100	            )
   101	            conn.commit()
   102	
   103	        watched = get_watched_repos(db_path)
   104	
   105	        self.assertEqual(watched["watched"], ["example/owned"])
   106	
   107	
   108	if __name__ == "__main__":
   109	    unittest.main()

exec
/bin/zsh -lc "nl -ba src/rebalance/ingest/config.py | sed -n '940,970p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
   940	    set_github_ignored_repos([item for item in existing if item != normalized])
   941	    return True
   942	
   943	
   944	def is_github_repo_ignored(repo: str) -> bool:
   945	    """Return True when the exact repo is in the operator-local ignore list."""
   946	    normalized = normalize_github_repo_name(repo)
   947	    return normalized in set(get_github_ignored_repos())
   948	
   949	
   950	def get_auto_promote_config() -> dict[str, Any]:
   951	    """Return the auto-promotion config block (GH-124).
   952	
   953	    Keys:
   954	      - auto_promote_enabled: opt-in flag gating commit-threshold auto-promotion of a
   955	        watched repo into project_registry as a machine_owned row (generated_by
   956	        "commit_threshold_v1"). github_ignored_repos always wins regardless of this
   957	        flag. Default: True.
   958	      - auto_promote_commit_threshold: minimum distinct-SHA operator commits (all-time,
   959	        cumulative — not a rolling window) before a watched repo auto-promotes.
   960	        Default: 3.
   961	    """
   962	    config = _read_config()
   963	    return {
   964	        "auto_promote_enabled": bool(config.get("auto_promote_enabled", True)),
   965	        "auto_promote_commit_threshold": int(config.get("auto_promote_commit_threshold", 3)),
   966	    }
   967	
   968	
   969	def get_calendar_ignored_summaries() -> list[str]:
   970	    """Return operator-local calendar event summaries to suppress.

exec
/bin/zsh -lc "rg -n \"auto_promote\" tests | sed -n '1,200p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
tests/test_index_ops.py:30:    def test_github_refresh_wires_auto_promote_after_watchlist_guard(self) -> None:
tests/test_index_ops.py:33:        # its summary into the result under "auto_promote".
tests/test_index_ops.py:70:                ) as mock_auto_promote,
tests/test_index_ops.py:90:        mock_auto_promote.assert_called_once_with(db_path)
tests/test_index_ops.py:91:        self.assertEqual(result["auto_promote"]["promoted_count"], 1)
tests/test_index_ops.py:92:        self.assertEqual(result["auto_promote"]["promoted_repos"], ["Acme/widget"])
tests/test_index_ops.py:93:        self.assertEqual(result["auto_promote"]["candidates_evaluated"], 2)
tests/test_web_auth_log.py:49:    def test_project_auto_promoted_renders_ok_badge(self) -> None:
tests/test_web_auth_log.py:54:            "event": "project_auto_promoted",
tests/test_auto_promote.py:176:            {**config_module._read_config(), "auto_promote_enabled": False}
tests/test_auto_promote.py:191:            "rebalance.ingest.auth_log.log_project_auto_promoted"
tests/test_auto_promote.py:206:            "rebalance.ingest.auth_log.log_project_auto_promoted"

codex
I’ve got two likely correctness seams: the commit corpus is sourced from PR commits inside a windowed sync, and the project-name derivation is a raw repo slug that can collide across owners. I’m checking the exact table constraints and the watched-set casing behavior before I call either one.
exec
/bin/zsh -lc "nl -ba src/rebalance/ingest/github_watch.py | sed -n '227,312p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
   227	def watched_repo_is_active_work(
   228	    database_path: Path,
   229	    repo_full_name: str,
   230	    *,
   231	    since_days: int = 14,
   232	) -> bool:
   233	    """True when *repo* is being worked through any **owned** channel.
   234	
   235	    Any of these means the operator (or a cloud agent acting for them) is actively
   236	    working the repo, so the whole-repo rollup must step aside to avoid double
   237	    counting against the real per-login rows:
   238	
   239	      - a live local clone exists (``focus5_repo_signals`` with a recent
   240	        ``my_last_commit_ts``) — covers the "downloaded and worked on locally" case;
   241	      - the operator has push/collab access (``github_pushed_repos``) — covers cloud
   242	        agents that push (Claude Code cloud / Codex cloud);
   243	      - real per-login activity rows exist in the window (``github_activity`` under a
   244	        non-sentinel login);
   245	      - cloud-agent authored commits exist in the window (``github_commits``).
   246	
   247	    Recomputed every refresh, so when these signals age out the repo reverts to
   248	    external monitoring on its own.
   249	    """
   250	    repo = normalize_github_repo_name(repo_full_name)
   251	    if not database_path.exists():
   252	        return False
   253	
   254	    recent_local_ts = int(
   255	        datetime.now(timezone.utc).timestamp() - _LOCAL_RECENCY_DAYS * 86400
   256	    )
   257	
   258	    with db_connection(database_path, ensure_github_schema) as conn:
   259	        # 1) Live local clone with a recent operator commit.
   260	        try:
   261	            row = conn.execute(
   262	                "SELECT 1 FROM focus5_repo_signals "
   263	                "WHERE LOWER(repo_full_name)=? "
   264	                "AND (my_last_commit_ts IS NOT NULL AND my_last_commit_ts >= ?) "
   265	                "LIMIT 1",
   266	                (repo, recent_local_ts),
   267	            ).fetchone()
   268	            if row:
   269	                return True
   270	        except Exception:  # noqa: BLE001 — focus5 tables may not exist yet
   271	            pass
   272	
   273	        # 2) Operator/collab push access.
   274	        try:
   275	            row = conn.execute(
   276	                "SELECT 1 FROM github_pushed_repos WHERE LOWER(repo_full_name)=? LIMIT 1",
   277	                (repo,),
   278	            ).fetchone()
   279	            if row:
   280	                return True
   281	        except Exception:  # noqa: BLE001
   282	            pass
   283	
   284	        # 3) Real per-login activity in the window (anything but the sentinel).
   285	        try:
   286	            row = conn.execute(
   287	                "SELECT 1 FROM github_activity WHERE LOWER(repo_full_name)=? "
   288	                "AND login != ? AND scan_date >= date('now', ?) "
   289	                "AND (commits+pushes+prs_opened+prs_merged+issues_opened"
   290	                "     +issue_comments+reviews) > 0 LIMIT 1",
   291	                (repo, WATCHED_LOGIN, f"-{int(since_days)} days"),
   292	            ).fetchone()
   293	            if row:
   294	                return True
   295	        except Exception:  # noqa: BLE001
   296	            pass
   297	
   298	        # 4) Cloud-agent authored commits in the window.
   299	        try:
   300	            from rebalance.ingest.pulse import CLOUD_AGENT_AUTHORS  # noqa: PLC0415
   301	
   302	            placeholders = ",".join("?" * len(CLOUD_AGENT_AUTHORS))
   303	            row = conn.execute(
   304	                f"SELECT 1 FROM github_commits WHERE LOWER(repo_full_name)=? "
   305	                f"AND author_login IN ({placeholders}) "
   306	                f"AND substr(committed_at,1,10) >= ? LIMIT 1",
   307	                (repo, *CLOUD_AGENT_AUTHORS, _cutoff_iso(since_days)[:10]),
   308	            ).fetchone()
   309	            if row:
   310	                return True
   311	        except Exception:  # noqa: BLE001
   312	            pass

exec
/bin/zsh -lc "nl -ba src/rebalance/ingest/db/schema.py | sed -n '600,635p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
   600	    conn.commit()
   601	
   602	
   603	# ---------------------------------------------------------------------------
   604	# Project registry schema
   605	# ---------------------------------------------------------------------------
   606	
   607	
   608	def ensure_project_schema(conn: sqlite3.Connection) -> None:
   609	    """Create project_registry table if it doesn't exist."""
   610	    conn.execute("""
   611	        CREATE TABLE IF NOT EXISTS project_registry (
   612	            name TEXT PRIMARY KEY,
   613	            status TEXT,
   614	            summary TEXT,
   615	            value_level TEXT,
   616	            priority_tier INTEGER,
   617	            risk_level TEXT,
   618	            repos_json TEXT,
   619	            tags_json TEXT,
   620	            custom_fields_json TEXT
   621	        )
   622	    """)
   623	    conn.commit()
   624	
   625	
   626	# ---------------------------------------------------------------------------
   627	# Schema versioning
   628	# ---------------------------------------------------------------------------
   629	
   630	# The baseline schema — everything the ensure_*_schema functions above create.
   631	# A database that has run those functions is, by definition, at this version.
   632	# Schema changes from here on are forward-only migration files in db/migrations/
   633	# (applied by db/migrate.py). This number never changes and the ensure_*_schema
   634	# functions stay frozen at the baseline — see db/migrations/README.md.
   635	#

exec
/bin/zsh -lc "rg -n \"INSERT INTO github_activity|CREATE TABLE IF NOT EXISTS github_activity|UNIQUE\\(login, repo_full_name, scan_date\\)|WATCHED_LOGIN\" src/rebalance/ingest/db/schema.py src/rebalance/ingest/github_scan.py src/rebalance/ingest/github_watch.py" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
src/rebalance/ingest/db/schema.py:277:        CREATE TABLE IF NOT EXISTS github_activity (
src/rebalance/ingest/db/schema.py:291:            UNIQUE(login, repo_full_name, scan_date) ON CONFLICT REPLACE
src/rebalance/ingest/github_watch.py:10:``github_activity`` rollup under the sentinel login :data:`WATCHED_LOGIN`. The repo's
src/rebalance/ingest/github_watch.py:52:WATCHED_LOGIN = "__watch__"
src/rebalance/ingest/github_watch.py:130:    """Build a whole-repo ``github_activity`` rollup row under :data:`WATCHED_LOGIN`.
src/rebalance/ingest/github_watch.py:183:                WATCHED_LOGIN,
src/rebalance/ingest/github_watch.py:217:            (WATCHED_LOGIN, repo),
src/rebalance/ingest/github_watch.py:291:                (repo, WATCHED_LOGIN, f"-{int(since_days)} days"),

exec
/bin/zsh -lc "nl -ba src/rebalance/ingest/github_scan.py | sed -n '660,735p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
   660	    result.repo_activity = kept
   661	    return sorted(skipped)
   662	
   663	
   664	# ---------------------------------------------------------------------------
   665	# Balance query — used by MCP tool
   666	# ---------------------------------------------------------------------------
   667	
   668	def get_github_balance(
   669	    database_path: Path,
   670	    project_repos: dict[str, list[str]],
   671	    since_days: int = 14,
   672	) -> list[dict[str, Any]]:
   673	    """
   674	    Return GitHub activity summary per project using the project→repos mapping.
   675	
   676	    Args:
   677	        database_path:  Path to the SQLite database.
   678	        project_repos:  {project_name: [repo_full_name, ...]} mapping.
   679	        since_days:     How many days back to aggregate.
   680	
   681	    Returns:
   682	        List of dicts with project_name, total_commits, prs_opened, prs_merged,
   683	        issues_opened, last_active_at, repos_touched.
   684	    """
   685	    if not database_path.exists():
   686	        return []
   687	
   688	    from rebalance.ingest.db import db_connection, ensure_github_schema
   689	
   690	    since_date = (datetime.now(timezone.utc) - timedelta(days=since_days)).strftime("%Y-%m-%d")
   691	
   692	    with db_connection(database_path, ensure_github_schema) as conn:
   693	        rows = conn.execute(
   694	            """
   695	            SELECT repo_full_name,
   696	                   SUM(commits)       AS commits,
   697	                   SUM(pushes)        AS pushes,
   698	                   SUM(prs_opened)    AS prs_opened,
   699	                   SUM(prs_merged)    AS prs_merged,
   700	                   SUM(issues_opened) AS issues_opened,
   701	                   SUM(issue_comments) AS issue_comments,
   702	                   SUM(reviews)       AS reviews,
   703	                   MAX(last_active_at) AS last_active_at
   704	            FROM github_activity
   705	            WHERE scan_date >= ?
   706	            GROUP BY repo_full_name
   707	            """,
   708	            (since_date,),
   709	        ).fetchall()
   710	
   711	    # Build lookup: repo_full_name → aggregated activity row
   712	    repo_stats: dict[str, dict[str, Any]] = {
   713	        row["repo_full_name"]: dict(row) for row in rows
   714	    }
   715	
   716	    results: list[dict[str, Any]] = []
   717	    for project_name, repos in project_repos.items():
   718	        total_commits = 0
   719	        total_prs_opened = 0
   720	        total_prs_merged = 0
   721	        total_issues = 0
   722	        repos_touched: list[str] = []
   723	        last_active: str | None = None
   724	
   725	        for repo in repos:
   726	            stats = repo_stats.get(repo)
   727	            if not stats:
   728	                continue
   729	            repos_touched.append(repo)
   730	            total_commits += stats.get("commits") or 0
   731	            total_prs_opened += stats.get("prs_opened") or 0
   732	            total_prs_merged += stats.get("prs_merged") or 0
   733	            total_issues += stats.get("issues_opened") or 0
   734	            la = stats.get("last_active_at")
   735	            if la and (last_active is None or la > last_active):

exec
/bin/zsh -lc "rg -n \"auto_promote\\\"|\\['auto_promote'\\]|auto_promote_result|promoted_repos\" src tests scripts | sed -n '1,220p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
tests/test_index_ops.py:33:        # its summary into the result under "auto_promote".
tests/test_index_ops.py:91:        self.assertEqual(result["auto_promote"]["promoted_count"], 1)
tests/test_index_ops.py:92:        self.assertEqual(result["auto_promote"]["promoted_repos"], ["Acme/widget"])
tests/test_index_ops.py:93:        self.assertEqual(result["auto_promote"]["candidates_evaluated"], 2)
src/rebalance/ingest/index_ops.py:842:        auto_promote_result: dict[str, Any] = {
src/rebalance/ingest/index_ops.py:847:            "promoted_repos": [
src/rebalance/ingest/index_ops.py:853:        auto_promote_result = {"error": str(e)}
src/rebalance/ingest/index_ops.py:859:        "auto_promote": auto_promote_result,

exec
/bin/zsh -lc "rg -n \"COUNT\\(DISTINCT sha\\)|substr\\(committed_at|author_login IN|LOWER\\(author_login\\)|repo_full_name = \\?\" tests src | sed -n '1,220p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
exec
/bin/zsh -lc "rg -n \"sync_inferred_project_registry\\(|infer_project_registry\\(\" src tests scripts | sed -n '1,200p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
src/rebalance/ingest/github_readiness.py:88:            WHERE repo_full_name = ? AND title = ?
src/rebalance/ingest/github_readiness.py:99:        WHERE repo_full_name = ? AND state = 'open'
src/rebalance/ingest/github_readiness.py:178:            "SELECT * FROM github_repo_meta WHERE repo_full_name = ?",
src/rebalance/ingest/github_readiness.py:213:                WHERE repo_full_name = ? AND item_type = 'issue' AND milestone_title = ?
src/rebalance/ingest/github_readiness.py:228:                WHERE repo_full_name = ? AND item_type = 'pull_request'
src/rebalance/ingest/github_readiness.py:239:            WHERE repo_full_name = ?
src/rebalance/ingest/github_readiness.py:294:                WHERE repo_full_name = ?
src/rebalance/ingest/github_readiness.py:306:            WHERE repo_full_name = ?
src/rebalance/ingest/github_readiness.py:322:            WHERE repo_full_name = ?
src/rebalance/ingest/github_readiness.py:353:            WHERE repo_full_name = ?
src/rebalance/ingest/github_scan.py:592:                "WHERE repo_full_name = ?",
src/rebalance/ingest/github_scan.py:620:                    "WHERE repo_full_name = ?",
src/rebalance/ingest/github_scan.py:630:                    WHERE repo_full_name = ?
src/rebalance/ingest/project_inference.py:794:        SELECT COUNT(DISTINCT sha) AS n
src/rebalance/ingest/project_inference.py:796:        WHERE repo_full_name = ? AND {author_filter}
src/rebalance/ingest/github_reconciliation.py:152:            "SELECT default_branch FROM github_repo_meta WHERE repo_full_name = ?",
src/rebalance/ingest/github_reconciliation.py:177:                WHERE repo_full_name = ?
src/rebalance/ingest/github_reconciliation.py:191:                WHERE repo_full_name = ?
src/rebalance/ingest/github_reconciliation.py:208:                WHERE repo_full_name = ?
src/rebalance/ingest/github_reconciliation.py:230:                WHERE repo_full_name = ?
src/rebalance/ingest/github_reconciliation.py:244:                WHERE repo_full_name = ?
src/rebalance/ingest/github_reconciliation.py:258:                WHERE repo_full_name = ?
tests/test_github_knowledge.py:294:                    WHERE repo_full_name = ?
tests/test_github_knowledge.py:306:                    WHERE repo_full_name = ?
src/rebalance/ingest/github_watch.py:305:                f"AND author_login IN ({placeholders}) "
src/rebalance/ingest/github_watch.py:306:                f"AND substr(committed_at,1,10) >= ? LIMIT 1",
src/rebalance/ingest/db/github.py:275:    conn.execute(f"DELETE FROM {table} WHERE repo_full_name = ?", (repo_full_name,))
src/rebalance/ingest/db/github.py:339:            WHERE repo_full_name = ? AND source_type = ? AND source_number = ?
src/rebalance/ingest/db/github.py:352:        WHERE repo_full_name = ? AND source_type = ? AND source_number = ?
src/rebalance/ingest/db/github.py:359:        WHERE repo_full_name = ? AND item_type = ? AND item_number = ?
src/rebalance/ingest/db/github.py:366:        WHERE repo_full_name = ? AND item_type = ? AND item_number = ?
src/rebalance/ingest/db/github.py:373:        WHERE repo_full_name = ? AND item_type = ? AND item_number = ?
src/rebalance/ingest/db/github.py:380:        WHERE repo_full_name = ? AND source_type = ? AND source_number = ?
src/rebalance/ingest/db/github.py:424:        sql = base.format(repo_clause=" AND gd.repo_full_name = ?")

 succeeded in 0ms:
tests/test_project_inference.py:141:        projects, summary = infer_project_registry(
tests/test_project_inference.py:213:        summary = sync_inferred_project_registry(
tests/test_project_inference.py:294:        summary = sync_inferred_project_registry(
tests/test_project_inference.py:315:        summary2 = sync_inferred_project_registry(
src/rebalance/cli/ingest_cmds.py:78:def ingest_infer_project_registry(
src/rebalance/cli/ingest_cmds.py:96:        projects, summary = infer_project_registry(
src/rebalance/cli/ingest_cmds.py:114:    summary = sync_inferred_project_registry(
src/rebalance/ingest/project_inference.py:704:def infer_project_registry(
src/rebalance/ingest/project_inference.py:744:def sync_inferred_project_registry(
src/rebalance/ingest/project_inference.py:751:    projects, summary = infer_project_registry(

exec
/bin/zsh -lc "rg -n \"get_projects\\(database_path, status=\\\"active\\\"\\)|status=\\\"active\\\"\" src/rebalance/ingest/*.py src/rebalance/mcp/tools/*.py | sed -n '1,240p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
src/rebalance/mcp/tools/projects.py:14:    projects = get_projects(database_path, status="active")
src/rebalance/ingest/note_builder.py:259:    projects = apply_project_priorities(get_projects(database_path, status="active"))
src/rebalance/ingest/next_actions.py:1024:    active_projects = get_projects(database_path, status="active")
src/rebalance/ingest/index_ops.py:572:        for project in get_projects(database_path, status="active"):

exec
/bin/zsh -lc 'rg -n "def normalize_github_repo_name" -n src/rebalance/ingest/config.py src/rebalance/ingest/*.py' in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
src/rebalance/ingest/config.py:260:def normalize_github_repo_name(repo: str) -> str:
src/rebalance/ingest/config.py:260:def normalize_github_repo_name(repo: str) -> str:

exec
/bin/zsh -lc "nl -ba src/rebalance/ingest/config.py | sed -n '860,940p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
   860	    config = _read_config()
   861	    value = config.get("gmail_ingest_method")
   862	    if isinstance(value, str) and value.strip().lower() in GMAIL_INGEST_METHODS:
   863	        return value.strip().lower()
   864	    return "oauth"
   865	
   866	
   867	# Apple Reminders has no in-DB "default list" flag (the preference lives in an
   868	# app pref outside the SQLite store), so the ingest scope is selected by list
   869	# NAME. Default "Reminders" — the conventional default list — overridable here.
   870	APPLE_REMINDERS_DEFAULT_LIST = "Reminders"
   871	
   872	
   873	def get_apple_reminders_list_name() -> str:
   874	    """Return the Apple Reminders list to ingest (default ``"Reminders"``).
   875	
   876	    Config key: ``apple_reminders_list_name``. Only this one list is synced into
   877	    the ``apple_reminders`` table (see APPLE-REMINDERS-UNIFIED-PLAN Phase 2)."""
   878	    config = _read_config()
   879	    value = config.get("apple_reminders_list_name")
   880	    if isinstance(value, str) and value.strip():
   881	        return value.strip()
   882	    return APPLE_REMINDERS_DEFAULT_LIST
   883	
   884	
   885	def set_gmail_ingest_method(method: str) -> None:
   886	    """Store the Gmail ingest method (``oauth`` or ``mcp``)."""
   887	    normalized = method.strip().lower()
   888	    if normalized not in GMAIL_INGEST_METHODS:
   889	        raise ValueError(
   890	            f"gmail_ingest_method must be one of {GMAIL_INGEST_METHODS}, got {method!r}"
   891	        )
   892	    config = _read_config()
   893	    config["gmail_ingest_method"] = normalized
   894	    _write_config(config)
   895	
   896	
   897	def get_github_ignored_repos() -> list[str]:
   898	    """Return the locally configured GitHub repos to skip across ingest."""
   899	    config = _read_config()
   900	    value = config.get("github_ignored_repos")
   901	    if not isinstance(value, list):
   902	        return []
   903	    normalized: list[str] = []
   904	    for item in value:
   905	        if not isinstance(item, str):
   906	            continue
   907	        try:
   908	            repo = normalize_github_repo_name(item)
   909	        except ValueError:
   910	            continue
   911	        if repo not in normalized:
   912	            normalized.append(repo)
   913	    return sorted(normalized)
   914	
   915	
   916	def set_github_ignored_repos(repos: list[str]) -> None:
   917	    """Store the canonical operator-local GitHub ignore list."""
   918	    config = _read_config()
   919	    config["github_ignored_repos"] = _normalize_github_repo_list(repos)
   920	    _write_config(config)
   921	
   922	
   923	def add_github_ignored_repo(repo: str) -> bool:
   924	    """Add one repo to the operator-local GitHub ignore list."""
   925	    normalized = normalize_github_repo_name(repo)
   926	    existing = get_github_ignored_repos()
   927	    if normalized in existing:
   928	        return False
   929	    existing.append(normalized)
   930	    set_github_ignored_repos(existing)
   931	    return True
   932	
   933	
   934	def remove_github_ignored_repo(repo: str) -> bool:
   935	    """Remove one repo from the operator-local GitHub ignore list."""
   936	    normalized = normalize_github_repo_name(repo)
   937	    existing = get_github_ignored_repos()
   938	    if normalized not in existing:
   939	        return False
   940	    set_github_ignored_repos([item for item in existing if item != normalized])

exec
/bin/zsh -lc "rg -n \"normalized_repo = normalize_github_repo_name\\(|repo_full_name = normalize_github_repo_name\\(|normalize_github_repo_name\\(repo_full_name\\)\" src/rebalance/ingest/*.py src/rebalance/ingest/**/*.py" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
src/rebalance/ingest/github_knowledge.py:257:    normalized_repo = normalize_github_repo_name(repo_full_name)
src/rebalance/ingest/github_knowledge.py:359:    normalized_repo = normalize_github_repo_name(repo_full_name)
src/rebalance/ingest/github_watch.py:139:    repo = normalize_github_repo_name(repo_full_name)
src/rebalance/ingest/github_watch.py:211:    repo = normalize_github_repo_name(repo_full_name)
src/rebalance/ingest/github_watch.py:250:    repo = normalize_github_repo_name(repo_full_name)
src/rebalance/ingest/github_watch.py:330:    repo = normalize_github_repo_name(repo_full_name)
src/rebalance/ingest/config.py:985:    normalized_repo = normalize_github_repo_name(repo)
src/rebalance/ingest/config.py:1013:    normalized_repo = normalize_github_repo_name(repo)
src/rebalance/ingest/github_scan.py:653:        normalized = normalize_github_repo_name(repo_full_name)
src/rebalance/ingest/github_scan.py:653:        normalized = normalize_github_repo_name(repo_full_name)
src/rebalance/ingest/github_watch.py:139:    repo = normalize_github_repo_name(repo_full_name)
src/rebalance/ingest/github_watch.py:211:    repo = normalize_github_repo_name(repo_full_name)
src/rebalance/ingest/github_watch.py:250:    repo = normalize_github_repo_name(repo_full_name)
src/rebalance/ingest/github_watch.py:330:    repo = normalize_github_repo_name(repo_full_name)
src/rebalance/ingest/semantic_index.py:290:    normalized_repo = normalize_github_repo_name(repo_full_name) if repo_full_name.strip() else ""
src/rebalance/ingest/semantic_index.py:290:    normalized_repo = normalize_github_repo_name(repo_full_name) if repo_full_name.strip() else ""
src/rebalance/ingest/github_knowledge.py:257:    normalized_repo = normalize_github_repo_name(repo_full_name)
src/rebalance/ingest/github_knowledge.py:359:    normalized_repo = normalize_github_repo_name(repo_full_name)
src/rebalance/ingest/config.py:985:    normalized_repo = normalize_github_repo_name(repo)
src/rebalance/ingest/config.py:1013:    normalized_repo = normalize_github_repo_name(repo)

exec
/bin/zsh -lc "nl -ba src/rebalance/ingest/config.py | sed -n '248,276p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
   248	    moves them into the secret store, so it is owner-only on disk (the audit
   249	    found it at 0644). launchd jobs run as the owner, so 0600 stays readable.
   250	    See PROJECT/2-WORKING/AUTH-AND-API-KEY-STORAGE-HARDENING.md.
   251	    """
   252	    from . import secret_store  # noqa: PLC0415
   253	
   254	    _ensure_config_dir()
   255	    path = _resolved_config_path()
   256	    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
   257	    secret_store.harden_mode(path, 0o600)  # best-effort; brief 0644 window is acceptable on a single-user box
   258	
   259	
   260	def normalize_github_repo_name(repo: str) -> str:
   261	    """Normalize one GitHub repo identifier to exact lowercased owner/name form."""
   262	    normalized = repo.strip().strip("/")
   263	    if not normalized or not _GITHUB_REPO_RE.fullmatch(normalized):
   264	        raise ValueError(f"Invalid GitHub repo '{repo}'. Expected owner/name.")
   265	    return normalized.lower()
   266	
   267	
   268	def _normalize_github_repo_list(repos: list[str] | tuple[str, ...] | set[str]) -> list[str]:
   269	    normalized: list[str] = []
   270	    for repo in repos:
   271	        item = normalize_github_repo_name(repo)
   272	        if item not in normalized:
   273	            normalized.append(item)
   274	    return sorted(normalized)
   275	
   276	

exec
/bin/zsh -lc "nl -ba src/rebalance/ingest/github_scan.py | sed -n '630,662p'" in /private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566
 succeeded in 0ms:
   630	                    WHERE repo_full_name = ?
   631	                    """,
   632	                    (
   633	                        rec.pushed_at, int(rec.private), int(rec.fork),
   634	                        int(rec.archived), int(rec.disabled),
   635	                        now, rec.repo_full_name,
   636	                    ),
   637	                )
   638	                result.updated += 1
   639	        conn.commit()
   640	
   641	    return result
   642	
   643	
   644	def filter_ignored_repo_activity(result: GitHubScanResult, ignored_repos: list[str]) -> list[str]:
   645	    """Remove ignored repos from a scan result in place and return the skipped set."""
   646	    ignored = {normalize_github_repo_name(repo) for repo in ignored_repos}
   647	    if not ignored:
   648	        return []
   649	
   650	    kept: dict[str, RepoActivity] = {}
   651	    skipped: list[str] = []
   652	    for repo_full_name, activity in result.repo_activity.items():
   653	        normalized = normalize_github_repo_name(repo_full_name)
   654	        if normalized in ignored:
   655	            if normalized not in skipped:
   656	                skipped.append(normalized)
   657	            continue
   658	        kept[repo_full_name] = activity
   659	
   660	    result.repo_activity = kept
   661	    return sorted(skipped)
   662	

codex
**ANSWER**

Not clean. I see **2 blockers** and **2 should-fix issues** in the merged implementation. The biggest problems are that the threshold is **not actually counting “all-time operator commits to the repo”** and that the write key is a **raw repo slug**, which can silently overwrite/promote the wrong project when two repos share the same name.

**FINDINGS**

- [Blocker] The counting query is only as good as `github_commits`, and that table is **not a full all-time repo commit history**. The plan contract says cumulative all-time distinct-SHA operator commits to the repo ([GH-124-AUTO-PROMOTE-WATCHED.md](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/PROJECT/2-WORKING/GH-124-AUTO-PROMOTE-WATCHED.md:125), [GH-124-AUTO-PROMOTE-WATCHED.md](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/PROJECT/2-WORKING/GH-124-AUTO-PROMOTE-WATCHED.md:137)), but `sync_github_repo()` only populates `github_commits` from `GET /pulls/{n}/commits` for PRs returned by a windowed PR sync ([github_knowledge.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/github_knowledge.py:386), [github_knowledge.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/github_knowledge.py:592), [github_knowledge.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/github_knowledge.py:766)). Direct pushes with no PR, and older PR commits never seen inside the sync window, are invisible to `_count_operator_commits()` ([project_inference.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/project_inference.py:779)). The tests mask this because they seed `github_commits` directly instead of flowing through real GitHub sync ([test_auto_promote.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/tests/test_auto_promote.py:21)).

- [Blocker] `_repo_to_promoted_row()` derives the registry `name` from the **repo slug only** (`owner/foo` and `other/foo` both become `foo`) ([project_inference.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/project_inference.py:803)). `project_registry` is keyed by `name` ([schema.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/db/schema.py:611)), and `_partition_writable_rows()` only blocks curated-name collisions, not machine-owned collisions or duplicates within the same promotion batch ([project_inference.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/project_inference.py:683)). `sync_db()` then upserts by `name`, so a second same-slug repo silently overwrites the first row’s `repos_json` / provenance ([registry.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/registry.py:165)). This is the clearest path to wrong-project collisions and silent data loss.

- [Should] Generalizing `_is_inference_owned()` to include `commit_threshold_v1` means `sync_inferred_project_registry()` now treats auto-promoted rows as stale-inference candidates and can delete them ([project_inference.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/project_inference.py:64), [project_inference.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/project_inference.py:666), [project_inference.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/project_inference.py:744)). That creates churn: a CLI/manual inference sync can delete an auto-promoted row, and the next GitHub refresh can re-promote it and fire the auth-log event again. I did not find a test covering this cross-writer interaction.

- [Should] Repo identity handling is inconsistent and case-sensitive in the auto-promote path. The canonical normalizer lowercases owner/name ([config.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/config.py:260)), but `_project_repos()`, `get_watched_repos()` set subtraction, and `_count_operator_commits()` all operate on raw-cased strings ([index_ops.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/index_ops.py:568), [index_ops.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/index_ops.py:669), [project_inference.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/project_inference.py:794)). A repo already present in an active project under one casing can reappear in `auto_discovered` under another, or have its commit history fragmented across case variants.

- [Pass] The curated-row protection itself is real: `_partition_writable_rows()` excludes any existing non-machine-owned `name` before `sync_db()` upserts, so a curated row with the same name is skipped rather than overwritten ([project_inference.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/project_inference.py:683), [registry.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/registry.py:165)). The problem is machine-owned collision handling, not curated overwrite.

- [Pass] The `_refresh_github()` wiring is in the intended place and is fail-soft in the same style as the watchlist guard: it runs after sync + watchlist guard and wraps only the auto-promote block in its own `try/except`, so it won’t abort the GitHub refresh ([index_ops.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/index_ops.py:823)).

**RECOMMENDATION**

Do a follow-up before relying on this unattended: base promotion on a **normalized repo key plus collision-safe project naming**, count from a **true repo-commit corpus or persistent lifetime counter** rather than PR-commit rows, and **separate auto-promote row ownership/cleanup from activity-inference cleanup**.
tokens used
112,761
**ANSWER**

Not clean. I see **2 blockers** and **2 should-fix issues** in the merged implementation. The biggest problems are that the threshold is **not actually counting “all-time operator commits to the repo”** and that the write key is a **raw repo slug**, which can silently overwrite/promote the wrong project when two repos share the same name.

**FINDINGS**

- [Blocker] The counting query is only as good as `github_commits`, and that table is **not a full all-time repo commit history**. The plan contract says cumulative all-time distinct-SHA operator commits to the repo ([GH-124-AUTO-PROMOTE-WATCHED.md](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/PROJECT/2-WORKING/GH-124-AUTO-PROMOTE-WATCHED.md:125), [GH-124-AUTO-PROMOTE-WATCHED.md](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/PROJECT/2-WORKING/GH-124-AUTO-PROMOTE-WATCHED.md:137)), but `sync_github_repo()` only populates `github_commits` from `GET /pulls/{n}/commits` for PRs returned by a windowed PR sync ([github_knowledge.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/github_knowledge.py:386), [github_knowledge.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/github_knowledge.py:592), [github_knowledge.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/github_knowledge.py:766)). Direct pushes with no PR, and older PR commits never seen inside the sync window, are invisible to `_count_operator_commits()` ([project_inference.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/project_inference.py:779)). The tests mask this because they seed `github_commits` directly instead of flowing through real GitHub sync ([test_auto_promote.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/tests/test_auto_promote.py:21)).

- [Blocker] `_repo_to_promoted_row()` derives the registry `name` from the **repo slug only** (`owner/foo` and `other/foo` both become `foo`) ([project_inference.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/project_inference.py:803)). `project_registry` is keyed by `name` ([schema.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/db/schema.py:611)), and `_partition_writable_rows()` only blocks curated-name collisions, not machine-owned collisions or duplicates within the same promotion batch ([project_inference.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/project_inference.py:683)). `sync_db()` then upserts by `name`, so a second same-slug repo silently overwrites the first row’s `repos_json` / provenance ([registry.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/registry.py:165)). This is the clearest path to wrong-project collisions and silent data loss.

- [Should] Generalizing `_is_inference_owned()` to include `commit_threshold_v1` means `sync_inferred_project_registry()` now treats auto-promoted rows as stale-inference candidates and can delete them ([project_inference.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/project_inference.py:64), [project_inference.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/project_inference.py:666), [project_inference.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/project_inference.py:744)). That creates churn: a CLI/manual inference sync can delete an auto-promoted row, and the next GitHub refresh can re-promote it and fire the auth-log event again. I did not find a test covering this cross-writer interaction.

- [Should] Repo identity handling is inconsistent and case-sensitive in the auto-promote path. The canonical normalizer lowercases owner/name ([config.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/config.py:260)), but `_project_repos()`, `get_watched_repos()` set subtraction, and `_count_operator_commits()` all operate on raw-cased strings ([index_ops.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/index_ops.py:568), [index_ops.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/index_ops.py:669), [project_inference.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/project_inference.py:794)). A repo already present in an active project under one casing can reappear in `auto_discovered` under another, or have its commit history fragmented across case variants.

- [Pass] The curated-row protection itself is real: `_partition_writable_rows()` excludes any existing non-machine-owned `name` before `sync_db()` upserts, so a curated row with the same name is skipped rather than overwritten ([project_inference.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/project_inference.py:683), [registry.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/registry.py:165)). The problem is machine-owned collision handling, not curated overwrite.

- [Pass] The `_refresh_github()` wiring is in the intended place and is fail-soft in the same style as the watchlist guard: it runs after sync + watchlist guard and wraps only the auto-promote block in its own `try/except`, so it won’t abort the GitHub refresh ([index_ops.py](/private/var/folders/z0/92pfvhnn06z2_7hnpdb4kkbw0000gn/T/consult-wt-3758-27566/src/rebalance/ingest/index_ops.py:823)).

**RECOMMENDATION**

Do a follow-up before relying on this unattended: base promotion on a **normalized repo key plus collision-safe project naming**, count from a **true repo-commit corpus or persistent lifetime counter** rather than PR-commit rows, and **separate auto-promote row ownership/cleanup from activity-inference cleanup**.

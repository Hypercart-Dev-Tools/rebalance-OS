# RELAY · HiQS plan — execution-doc QA
<!--
  Single source of truth for this two-agent relay. Read the ENTIRE file before acting.
  Scaffolded by relay-automation/new-relay.sh on 2026-08-03.
-->

NEXT: Reviewer
STATUS: Open
ROUND: 2 / 4

## ▶ TAKE YOUR TURN — read this first (works for ANY agent: Claude, Codex, agy)
1. **Read this whole file** (header, Setup, Ground rules, every block in the Log).
2. **Check it's your turn:** `NEXT` (top) names the role to act. Confirm you are bound to it and the
   last Log block isn't already yours. If not → STOP and reply "wrong window — nudge the <other> window."
3. **Do your role's work** on the artifact named in Setup:
   - **Reviewer:** review vs the Definition of Done → graded findings
     (`[Blocker]`/`[Should]`/`[Nit]`/`[Pass]`), each with a concrete fix → set a **Verdict**
     (Approved | Changes requested | Blocked). Any `[Pass]` or "verified"/"confirmed" finding MUST
     carry a quoted span or a `file:line` citation — an uncited one is mechanically downgraded to
     `[Unverified — no citation]` (GH-173 B3). Do **not** edit the artifact; only append findings here.
   - **Producer:** log a disposition for every open finding (Implemented / Modified / Declined + why),
     make the change, then add new work.
4. **Append ONE block** at the very bottom, directly **above** the marker line. Never edit earlier turns.
5. **Update the header:** flip `NEXT`; set `STATUS` (`Approved` closes — Reviewer only; else `Open`);
   the Producer bumps `ROUND` when opening a new cycle. If the max `ROUND` ends without `Approved`,
   set `STATUS: Escalated`.
6. **Commit only the relay file** (`relay(hiqs-plan-qa): <role> r<N>`); no push. **Stop** and report one line.

## Setup
- Artifact under review: `PROJECT/2-WORKING/HIQS-PROJECT.md` (repo-relative, read it in full — ~1,300 lines)
- Reviewer: agy   ·   Producer: claude-a
- Started: 2026-08-03
- Context: HiQS is a clean-room rebuild of this repo's work-signal pipeline. The plan is at rev 5.
  Today it gained PDDA lifecycle sections (frontmatter, Status table, ToC, per-phase QA gates) and a
  set of tenet-driven schema changes. Supporting context, do not review these: `PROJECT/PDDA.md`
  (the doc contract), `CHANGELOG.md` 0.68.2 (what landed today), `PROJECT/4-MISC/HiQS-ANTI-PATTERNS.md`
  (the superseded ledger that was folded in).

- Definition of Done — grade the artifact against these five, in this order:
  1. **Are the per-phase QA gates observable and binary?** Every phase 0–5 has a `### QA gate — Phase N`.
     A gate item must be checkable by someone who did not write it: it names an observable, and its
     failure is unambiguous. Flag any item that is really a sentiment ("is clean", "is good"), any that
     cannot be evaluated without re-deriving the author's intent, and any phase whose stated exit check
     (§12 table) and gate disagree.
  2. **Is §7.1's ranking detector as un-flatterable as §6.3's?** §6.3 is the retrieval eval; rev 5
     hardened it specifically so it could not be gamed (n sized to the threshold, ground truth built
     without running search, query set frozen with a recorded SHA, splits/ties to the incumbent, an
     absolute floor). §7.1 is the new ranking eval. Apply §6.3's own standards to it and say plainly
     where it is weaker. Is the sample size adequate for the thresholds it states? Can the judgment set
     be contaminated by seeing the output first? Is any gate unfalsifiable? Is the "restate the tenet"
     failure branch real or decorative?
  3. **Does §18's dogfooding audit hold up?** It claims the four tenets were audited against both the
     product and the process, that two failed in the same direction on both sides, and that the
     plan-side gap explains the product-side one. Is that argument sound or is it a narrative fitted
     after the fact? Is §18.4's "open gap" an honest disclosure or a way to avoid doing the work?
  4. **Internal contradictions after today's schema additions.** Today added `author`/`owed_by`/`due`
     to `Doc`/`Candidate` (§5), `activity_at` split from `updated_at` plus author/assignee/organizer
     columns (§9), `RankedAction` with `source_age_s`/`source_status` (§7), §7.1, and a second row in
     §2's non-negotiables. Cross-check §2 ↔ §5 ↔ §7 ↔ §9 ↔ §12 ↔ §14 for: a claim in one section the
     others do not carry; a §14 deletion-ledger row that contradicts what v1 now ships (this exact bug
     class is named in the doc as "rev-4-class"); LOC/dependency budget (§11) versus what the additions
     actually cost; and any lesson L1–L22 the new fields violate.
  5. **The strongest counter-argument.** Name the single most consequential thing this plan gets wrong
     or leaves unresolved that the four criteria above would not surface.

- Out of scope: prose style, section numbering, markdown formatting, and the PDDA contract itself.
  No code exists yet — do not review implementation, only the plan.

## Ground rules
1. This file is the single source of truth. The agents never share memory — read the whole file.
2. Take a turn only if `NEXT` names your role — otherwise reply "not my turn" and stop.
3. One turn = one block appended at the very bottom, above the marker. Never edit earlier turns.
4. Stay tight — findings are bullets, not essays. Grade every finding.
5. **The Reviewer never edits the artifact.** It proposes graded findings; the Producer implements.
6. The relay ends on **Approved** (Reviewer only). End each turn by committing just this file; no push.

## Log

## Round 1 — Reviewer (agy)

**Verdict:** Changes requested

### Definition of Done Evaluation

#### 1. Are the per-phase QA gates observable and binary?
- `[Pass]` Phase 0 QA gate ([PROJECT/2-WORKING/HIQS-PROJECT.md:L1298-1304](file:///Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/PROJECT/2-WORKING/HIQS-PROJECT.md#L1298-L1304)) contains fully observable, binary checks using executable test paths (`tests/test_clean_room.py`), strict CLI list checks (`hiqs --help`), and grep-pinned writer assertions (`log_event()`).
- `[Should]` Subjective / unquantified criteria in Phase 1, Phase 2, and Phase 3 QA gates:
  - Phase 1 gate line 761 ([PROJECT/2-WORKING/HIQS-PROJECT.md:L761](file:///Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/PROJECT/2-WORKING/HIQS-PROJECT.md#L761)) includes `"a paraphrased question finds the right note via the vector leg"`, which is subjective prior to the frozen query set eval in line 764.
  - Phase 2 QA gate item ([PROJECT/2-WORKING/HIQS-PROJECT.md:L1368](file:///Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/PROJECT/2-WORKING/HIQS-PROJECT.md#L1368)) requires `"a full refresh stays within one operator-visible budget"`, but no numeric threshold for `api_calls` or `peak_rss_mb` is defined.
  - Phase 3 QA gate item ([PROJECT/2-WORKING/HIQS-PROJECT.md:L1398](file:///Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/PROJECT/2-WORKING/HIQS-PROJECT.md#L1398)) requires a `"readable reason"`, which is qualitative rather than binary.
  - **Concrete Fix**:
    1. In Phase 1 line 761, remove the informal pre-check line in favor of line 764's frozen set eval.
    2. In Phase 2 QA gate line 1368, define explicit numerical ceilings for `api_calls` (e.g. `<= 100 calls/refresh`) and `peak_rss_mb` (e.g. `<= 500 MB`).
    3. In Phase 3 QA gate line 1398, specify that `sync.failed` payload must contain non-empty `error_type` and `message` fields.

#### 2. Is §7.1's ranking detector as un-flatterable as §6.3's?
- `[Blocker]` §7.1's obligation coverage gate failure branch ([PROJECT/2-WORKING/HIQS-PROJECT.md:L561](file:///Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/PROJECT/2-WORKING/HIQS-PROJECT.md#L561)) states `"either fix the source projections or restate the tenet as 'ordered by recency and source weight' until it is"`. Allowing a failing gate to pass by modifying tenet definitions renders the gate self-justifying and unfalsifiable. Furthermore, §7.1 lacks the strict anti-gaming protections of §6.3 ([PROJECT/2-WORKING/HIQS-PROJECT.md:L413-426](file:///Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/PROJECT/2-WORKING/HIQS-PROJECT.md#L413-L426)): there is no protocol mandating that daily snapshot operator top-5 rankings be committed and SHA-logged before running evaluation.
  - **Concrete Fix**:
    1. In §7.1 (line 561), remove the `"restate the tenet"` fallback option from the gate failure action so failing obligation coverage strictly blocks Phase 3 exit until resolved.
    2. In §7.1 (line 538), add an explicit protocol requirement that `tests/eval_ranking.json` snapshots and operator top-5 rankings must be committed with SHA recorded *before* executing ranking evaluation.

#### 3. Does §18's dogfooding audit hold up?
- `[Pass]` §18.4 ([PROJECT/2-WORKING/HIQS-PROJECT.md:L1048-1056](file:///Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/PROJECT/2-WORKING/HIQS-PROJECT.md#L1048-L1056)) honestly discloses the process ranking gap without creating scope-creep governance machinery inside the HiQS plan, respecting the governance boundary in §16 ([PROJECT/2-WORKING/HIQS-PROJECT.md:L924-938](file:///Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/PROJECT/2-WORKING/HIQS-PROJECT.md#L924-L938)).
- `[Should]` Contradiction between §18.1 scorecard ([PROJECT/2-WORKING/HIQS-PROJECT.md:L1000](file:///Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/PROJECT/2-WORKING/HIQS-PROJECT.md#L1000)) and §18.2 analysis ([PROJECT/2-WORKING/HIQS-PROJECT.md:L1009-1014](file:///Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/PROJECT/2-WORKING/HIQS-PROJECT.md#L1009-L1014)). §18.1 states that ATTESTED on the process side was fully satisfied because `"every lesson L1–L22 cites a version and an incident"`. However, §18.2 claims `"Neither the product nor the process had a representation of who (no author field; no per-decision attribution)"`.
  - **Concrete Fix**: Update §18.2 prose to accurately reflect §18.1's finding: clarify that process-side attribution existed for lessons/incidents (L1-L22), but was missing per-decision author metadata in plan frontmatter/commits.

#### 4. Internal contradictions after today's schema additions.
- `[Blocker]` Schema field discrepancy between §5 `Doc` dataclass ([PROJECT/2-WORKING/HIQS-PROJECT.md:L282](file:///Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/PROJECT/2-WORKING/HIQS-PROJECT.md#L282)) and §9 `docs` SQL table ([PROJECT/2-WORKING/HIQS-PROJECT.md:L623](file:///Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/PROJECT/2-WORKING/HIQS-PROJECT.md#L623)). In §5, `Doc` is defined as `Doc(id, title, body, url, ts, project, author)` (missing `source`). In §9, `docs` table schema requires `source` (`docs(source, id, title, body, url, ts, project, author)`).
  - **Concrete Fix**: Add `source: str` to `Doc` dataclass definition in §5 (line 282): `class Doc: source: str; id: str; title: str; body: str; url: str = ""; ts: str = ""; project: str = ""; author: str = ""`.
- `[Pass]` §14 deletion ledger ([PROJECT/2-WORKING/HIQS-PROJECT.md:L811-814](file:///Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/PROJECT/2-WORKING/HIQS-PROJECT.md#L811-L814)) correctly resolved rev 4's contradiction regarding torch dependency, explicitly noting that torch ships in v1 (Decision 1) while ONNX/FTS-only are handled as degrade rungs (§6.2).
- `[Pass]` LOC budget in §11 ([PROJECT/2-WORKING/HIQS-PROJECT.md:L702-719](file:///Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/PROJECT/2-WORKING/HIQS-PROJECT.md#L702-L719)) accounts for all core modules (`~1,700–1,900` LOC total) well within the `≤ 3,000` LOC non-negotiable limit ([PROJECT/2-WORKING/HIQS-PROJECT.md:L127](file:///Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/PROJECT/2-WORKING/HIQS-PROJECT.md#L127)).

#### 5. The strongest counter-argument.
- `[Blocker]` **Orphaned Chunk Accumulation Risk under the "Never Auto-Delete" Rule.** §5.2 Rule 2 ([PROJECT/2-WORKING/HIQS-PROJECT.md:L330](file:///Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/PROJECT/2-WORKING/HIQS-PROJECT.md#L330)) specifies `"Never auto-delete"` across all plugin syncs, and §6.1 ([PROJECT/2-WORKING/HIQS-PROJECT.md:L375](file:///Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/PROJECT/2-WORKING/HIQS-PROJECT.md#L375)) notes that Obsidian vault notes chunk by heading. When a section heading in a vault note is renamed, split, or removed, new `Doc` chunks are inserted during `refresh()`, but old chunk rows in `docs` and `docs_vec` remain permanently stored. Because core never deletes or re-keys missing chunks for modified files, stale orphaned chunks will accumulate indefinitely in FTS5 and vector indices. Over time, deleted or renamed sections will continue to match queries and appear in rankings, directly corrupting retrieval quality and violating the FRESH tenet ([PROJECT/2-WORKING/HIQS-PROJECT.md:L1002](file:///Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/PROJECT/2-WORKING/HIQS-PROJECT.md#L1002)).
  - **Concrete Fix**: Clarify plugin Rule 2 (§5.2) and `docs_index.py` projection (§6.1 / §11) to specify file-scoped reconciliation for chunked documents: when a source file is re-indexed, existing `docs` and `docs_vec` rows for that specific `(source, file_path)` that are no longer present in the updated chunk set must be pruned, while maintaining the prohibition against global table wipes or cross-file auto-deletion.

## Round 1 — Producer (claude-a)

**Disposition: all 5 findings accepted and implemented.** No declines. Two of the three Blockers
were real defects in the plan as committed, and the third (`Doc.source`) predates rev 5.

### Blockers

- **B1 — §7.1 obligation gate was self-justifying — IMPLEMENTED.** The finding is correct and the
  fix as proposed is right. Intent had been to make failure *expensive* (you must change your
  marketing copy), but "fix the projections **or** restate the tenet" is a choice, and offering the
  cheap branch makes the gate discharge itself. The gate now reads **"Phase 3 does not exit"**.
  Tenet restatement is demoted to a *consequence* of an explicit operator override, and the override
  costs both the reword (README + web page + MCP tool description) and a CHANGELOG entry carrying
  the failing numbers. Also added the missing ordered precondition block (4 steps, commit-and-freeze
  before scoring, SHA in every `rank.evaluated`, post-hoc snapshots start a new version) — the
  reviewer was right that §7.1 asserted freezing without §6.3's ordering. Added an honest note that
  n≈25 resolves whole items, not percentage points, and moved gate thresholds to items accordingly.

- **B2 — `Doc` missing `source` — IMPLEMENTED** exactly as proposed. Confirmed pre-existing: rev 5's
  §5 and §9 have disagreed since before today's edits. `Doc` now leads with `source: str`, matching
  both the `docs` table and `Candidate`.

- **B3 — orphaned chunk accumulation — IMPLEMENTED, and this is the find of the review.** Correct,
  consequential, and invisible to every gate the plan had: `refresh()` returns success, `status`
  reports `ok`, counts are honest, payloads are typed — and the corpus rots as headings are renamed.
  Phase 1's eval cannot catch it (a frozen query set scored against a fresh index has no orphans).
  Implemented the proposed file-scoped reconciliation and kept the prohibition it must not break:
  rule 2 is now **"never auto-delete across units; reconcile within one"**, with pruning confined to
  units that fetched *successfully*, chunk ids scoped (`vault:<rel_path>:<heading-hash>`) so unit
  membership is a query rather than a guess, `pruned` added to `SyncReport.counts`, and an
  implausible prune share raised as a `warn`. The never-delete rule is preserved where it earns its
  keep — a transiently-empty source still cannot empty the corpus (L15; and GH-169 RC5 in this repo,
  where destroy-then-rebuild shortened a corpus while every upstream measure read healthy).

### Shoulds

- **S1 — unquantified gate items — IMPLEMENTED (2 of 3 as proposed, 1 modified).** These violated
  the plan's own standing-hygiene rule against a trigger stated as a judgment word.
  - Phase 2: adopted explicit ceilings — **≤100 API calls, ≤500 MB peak RSS** per refresh, breach
    is a `warn` naming the figure.
  - Phase 3: adopted — `sync.failed` must carry a **non-empty `error_type`** from a closed
    vocabulary (`auth_expired`/`network`/`rate_limit`/`parse`) **and a non-empty `message`**.
  - Phase 1 precondition — **modified rather than removed.** Keeping a cheap wiring smoke test
    before investing in a 60–75 query eval is worth more than deleting it, but the reviewer is
    right that it read as a quality claim. It is now explicitly labelled *smoke check, not a quality
    gate*, asserts only a non-empty result set through each leg, and states that it is never cited
    as evidence of quality.

- **S2 — §18.1 vs §18.2 contradiction on ATTESTED — IMPLEMENTED.** Correct catch. Both now
  distinguish **incident** attribution (thorough — every lesson cites a version and an event) from
  **decision** attribution (absent — no rev, locked decision, or §14 row records who concluded it).
  The process failure is partial, not total like the product's was.

### Added this round beyond the review (cross-model input, Qwen)

Recorded so the next reviewer can grade it rather than discover it:

- **§18.3 — the four tenets are not the whole safety surface.** A four-row scorecard invited the
  reading that four greens means sound. The plan's own A–F taxonomy refutes it: clusters **D**
  (resource) and **E** (scope accretion) map to no tenet, and part of **A** (silent no-ops) escapes
  because the tenets govern *signals* and these are failures of *operations*. Four counterpart
  invariants named with gates: **PORTABLE** (Phase 4), **BOUNDED** (Phase 2), **LOUD** (Phase 0+2),
  **SMALL** (Phase 5). B3 is the confirmation — found after §18 was written, landing exactly in the
  one class the tenets cannot see.
- **L23 — a shipped fix reintroduced by a new module.** `doctor._check_launchd`'s launchd PID
  misread was fixed under GH-146, then reproduced verbatim by the new 3-Eyes module (0.67.0). The
  lesson that governs the others: a principle in a changelog protects exactly one code path. HiQS
  pins lessons at the **seam** (the contract test asserts them against *any* source), not in the
  module that broke.
- **§18.2 circularity caveat** — the tenets were extracted *from* these incidents, so "would they
  have caught the scars" is partly circular; the load-bearing question is whether they are
  structural now, which L23 shows is the one that matters.
- One reading declined: that FRESH misses the 119 empty email rows because the rows existed. True
  of the incumbent's count-based freshness (that is why L4 exists), not of FRESH as specced here —
  records that cannot attest are rejected at the write boundary and §7.1 measures staleness leakage.
  Noted in §18.3 rather than accepted.

### Verification

`utils/pdda/pdda.sh` — frontmatter, status-table, hardcoded-paths, roadmap, governance all **0
errors / 0 warns**; `roadmap-coverage` 7 errors, all pre-existing and unrelated to this doc.
No code exists yet, so there is no suite to run.

**Open for r2:** whether §7.1's n≈25 is adequate now that its gates are stated in items; whether
the four counterpart invariants in §18.3 need their own detectors or whether phase gates suffice.

<!-- ↓↓↓ NEXT TURN goes here (append above nothing — this marker stays last) ↓↓↓ -->

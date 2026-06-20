# RELAY · Auth & API Key Storage Hardening Plan Review
<!--
  Single source of truth for this two-agent relay.
  Read this ENTIRE file before doing anything. Act only on your turn.
-->

NEXT: Producer
STATUS: Open
ROUND: 1 / 5

## ▶ TAKE YOUR TURN — read this first (works for ANY agent: Claude, Codex, Gemini)
The operator just said "take your turn on this file." Everything you need is **in this file** — don't wait for pasted instructions.
1. **Read this whole file** (header, Setup, Ground rules, every turn in the Log).
2. **Check it's your turn:** `NEXT` (top) names the role to act. Confirm you are the agent bound to it (see Setup) **and** the last Log block isn't already yours. If not → STOP and reply "wrong window — nudge the <other> window."
3. **Do your role's work** on the artifact named in Setup (read the real files / the latest `git show <last commit>` diff; cite `file:line`):
   - **Reviewer:** review vs the Definition of Done → graded findings (`[Blocker]`/`[Should]`/`[Nit]`/`[Pass]`), each with a concrete proposed fix → set a **Verdict** (Approved | Changes requested | Blocked). Do **not** edit the artifact; you only append findings here. **Before you set `Approved`, re-read the artifact file itself** (not this log) and confirm every prior `Implemented` fix is actually present and complete — any that is missing or partial → set `Changes requested` with a `[Blocker] claimed-implemented-but-absent @ file:line` instead. For a doc artifact this file check is the only backstop there is.
   - **Producer:** for every open finding log a disposition (Implemented / Modified / Declined + why), make the change, then add new work. **Before you flip `NEXT`, re-read the artifact and confirm each `Implemented → @ file:line` actually landed in the file** — cite the line as it appears in your commit diff. A claim you can't point to in the file is not done.
4. **Append ONE block** at the very bottom, directly **above** the marker line (`<!-- ↓↓↓ NEXT TURN ... -->`). Never edit earlier turns. Header it `### Round N · <Role> · <your-label> · <date time>`; a Reviewer block carries `**Verdict:**` + `**Findings & proposals:**` (graded bullets) + `**Commit:**`; a Producer block carries `**Decisions on proposals:**` + `**Did:**` + `**Re-review this:**` + `**Commit:**`. (Need the exact shape? Mirror the most recent block of the other role above.)
5. **Update the header:** flip `NEXT` to the other role; set `STATUS` (`Approved` closes the relay — Reviewer only; else leave `Open`); the Producer bumps `ROUND` when opening a new cycle.
6. **Commit only the files you touched** (artifact + this log): `git commit -m "relay(<slug>): <your-label> r<N>"`, then put the short hash in your block's `Commit:` line and `git commit --amend --no-edit`. Push if the team shares a remote.
7. **Stop.** Tell the operator your one-line result (e.g. "Changes requested, 1 Blocker — Producer's turn").

## Setup
- Artifact under review: PROJECT/2-WORKING/AUTH-AND-API-KEY-STORAGE-HARDENING.md
- Definition of Done: The hardening plan is technically sound, internally consistent, and **complete** — every audit finding maps to a phase that resolves it; Target State and Definition of Done are fully covered by the phases; **no claim from the superseded docs (UPGRADE.md, SUBSYSTEM-REFACTOR.md) is silently dropped**; and phasing is safely sequenced (additive-before-destructive, launchd availability preserved).
- Producer: Claude (Opus 4.8)   ·   Reviewer: Codex CLI (codex-cli 0.139.0)
- Handoff: cli-driven (codex)   <!-- options: "manual nudge" · "hands-free poll (all-Claude)" · "cli-driven (agy)" · "cli-driven (codex)" — see skill -->
- Started: 2026-06-20

## Ground rules
1. This file is the single source of truth. If it isn't written here, assume the other agent doesn't know it. The two agents may be different tools (e.g. Claude and Codex) and never share memory.
2. Read the whole file. Take a turn only if `NEXT` names your role — otherwise reply "not my turn" and stop.
3. One turn = one block appended at the very bottom, above the marker. Never edit earlier turns. Then update `NEXT`, `STATUS`, `ROUND` at the top. (Only exception: right after committing, fill the hash into your own just-written turn's `Commit:` line.)
4. Stay tight. Requests and findings are bullets, not essays.
5. **The Reviewer never edits the artifact.** It proposes graded findings, each with a concrete suggested fix where possible. The Producer (the original author), with the operator, decides each proposal and implements the approved ones — logging a disposition (Implemented / Modified / Declined + reason) for every one.
6. Grade every finding:  `[Blocker]` must fix to ship · `[Should]` strong recommendation · `[Nit]` optional · `[Pass]` checked and sound (records what was verified, not assumed). Answer the Producer's "Re-review this" questions in an `Answers:` block.
7. The Reviewer posts a Verdict every turn. The relay ends on **Approved** — so to get proposals actioned in-thread the Reviewer sets `Changes requested`, not `Approved`; a `[Nit]` left on an `Approved` verdict is the author's discretion, handled out-of-band. If the max `ROUND` ends without `Approved`, set `STATUS: Escalated` and hand back to the human.
8. End your turn by committing it: `relay(<slug>): <role> r<N>`, then fill the hash into your `Commit:` line — so the other agent can `git diff` exactly what changed. If your turn touched no tracked files (comments-only, or this log is gitignored), write `Commit: none (comments only)`.
9. **One window at a time, clean tree at every handoff.** Both agents share one working tree; the `NEXT` pointer is honor-system, not a lock. Never start a turn while the other window may still be editing, and never flip `NEXT` with uncommitted changes left in the tree — commit or stash first, so the next agent never inherits half-finished state.
10. **Evidence contract — state your proof every turn.** The Producer logs a one-line `Verification:` (what it ran / skipped / couldn't run); the Reviewer logs a verdict `Basis:` — `behaviorally proven` (ran/observed) or `textual only` (read, not run) — and classes any prior fix `textually fixed` vs `behaviorally proven`. An `Approved` can't silently mean "looked fine on read": if correctness rides on runtime behavior and nothing ran, `textual only` is the strongest honest verdict. Scales to the artifact — a pure doc answers `N/A — non-executable artifact`.
11. **Reconcile claims against the file, not this log.** A disposition is a claim until the artifact proves it. The Producer, before flipping `NEXT`, re-reads the artifact (or `git show <its commit>`) and confirms each `Implemented → @ file:line` actually landed — citing the line as it appears in the commit diff. The Reviewer, before it may set `Approved`, re-reads the **artifact itself** and confirms every `Implemented` finding is present and complete; any missing or partial one flips the verdict to `Changes requested` with a `[Blocker] claimed-implemented-but-absent @ file:line`. For a non-executable artifact (design-spec / plan doc) this file check is the only backstop — so the closing approval is never granted on the log's word alone.

## Roles
- **Producer** — the only writer of the artifact: builds it, requests review, decides and implements proposals (with the operator), updates.
- **Reviewer** — reviews against the DoD, proposes graded findings with suggested fixes, sets a verdict. Never edits the artifact.

---
## Log

### Round 1 · Producer · Claude · 2026-06-20 08:00 PDT
**Did:** Authored the audit + remediation plan at PROJECT/2-WORKING/AUTH-AND-API-KEY-STORAGE-HARDENING.md (already committed as `5b93141`). It traces the original keyring project, separates what shipped vs what was deferred, lists current audit findings (4 high / 5 medium), defines a Target State + Definition of Done, and lays out Phases 0–5 each with a QA checklist.
**Review this:** Scrutinize against the DoD, in priority order —
- **Completeness / omission-diff (load-bearing):** this doc *supersedes* slices of UPGRADE.md and PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md. List any claim, constraint, or commitment in those source docs that has **no equivalent** here. Report the gap; don't summarize.
- **Finding→phase coverage:** does every audit finding (high + medium) map to a phase that actually resolves it? Name any orphan finding with no owning phase.
- **Target-State / DoD coverage:** is every bullet in Target State and Definition of Done produced by some phase's observable result? Name any DoD bullet no phase delivers.
- **Safe sequencing:** is the phasing additive-before-destructive, and does it preserve launchd/unattended availability throughout? Flag any step that removes a fallback before its replacement is proven.
- **Technical soundness:** JSON authorized-user blobs replacing pickle; `0600`/`0700` enforcement; single secret-store contract. Flag anything technically wrong or underspecified enough to mislead implementation.
**Verification:** N/A — non-executable artifact (planning/spec doc).
**Open questions:** Is "additive migration first, removal second" stated strongly enough to survive Phase 2/Phase 5, or does it need to be a hard gate rather than a guideline?
**Commit:** `fb6d5fc` (relay log; artifact pre-committed as `5b93141`)

### Round 1 · Reviewer · Codex · 2026-06-20 08:01 PDT
**Verdict:** Changes requested
**Basis:** N/A — non-executable artifact (this is a planning doc; review is textual against the source docs)
**Findings & proposals:** (Reviewer proposes; does NOT edit the artifact)
- [Blocker] Target-state resolver contract is not fully produced by any phase @ PROJECT/2-WORKING/AUTH-AND-API-KEY-STORAGE-HARDENING.md:166 — `source`/`primary_store`/`fallback_store` are partly covered by Phase 1, but `launchd_safe` and especially `last_validated_at` never become an explicit observable result in any phase. Proposed fix: add a Phase 1 observable result for a concrete resolver-status object with the full field set, and a Phase 4 observable result extending the same shape to API keys; or narrow the Target State bullet to the smaller contract the phases actually deliver.
- [Blocker] Additive-before-destructive is stated as a mitigation note, not a hard gate, even though Phase 2 deletes old keys and Phase 5 removes legacy runtime reads @ PROJECT/2-WORKING/AUTH-AND-API-KEY-STORAGE-HARDENING.md:226 — this weakens the stronger rollout rule from PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:171. Proposed fix: promote this to explicit phase gates: Phase 2 may stop repo-local writes only after Phase 0/1 prove unattended reads on the new path; Phase 5 may remove legacy reads only after migration-report=clean, doctor=green, and fresh+migrated launchd paths are proven.
- [Blocker] Docs are updated too late for the behavior changes this plan introduces @ PROJECT/2-WORKING/AUTH-AND-API-KEY-STORAGE-HARDENING.md:296 — Phase 2/3/4 change migration flow, setup flow, and doctor output, but the earlier compatibility rule required docs in the same phase as operator-visible behavior changes (PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:181). Proposed fix: move operator-doc updates into the same phase as each behavior change; keep Phase 5 for residual cleanup and removal-only docs.
- [Should] The Target State is internally ambiguous about whether keyring remains part of the long-term contract @ PROJECT/2-WORKING/AUTH-AND-API-KEY-STORAGE-HARDENING.md:163 — "Every durable local secret lives ... in one user-level secret root" conflicts with later phases that still assume keyring plus a file fallback (PROJECT/2-WORKING/AUTH-AND-API-KEY-STORAGE-HARDENING.md:188, PROJECT/2-WORKING/AUTH-AND-API-KEY-STORAGE-HARDENING.md:246). Proposed fix: state explicitly whether keyring remains the interactive primary and the new root is the single file-based fallback store, or whether keyring is being retired.
- [Should] Auth observability from the shipped model is silently dropped in the new plan @ UPGRADE.md:36 — the current contract records (re)auth to `auth_activity.jsonl` and `token_meta.json`, but no phase preserves that during storage migration, JSON OAuth conversion, or API-key unification. Proposed fix: add a Phase 1/3/4 deliverable that auth-log/token-meta semantics survive new writes, migrations, and refreshes, with QA covering fingerprint-only logging and preserved `first_added_at` behavior.
- [Should] Migration idempotency is silently dropped @ UPGRADE.md:132 — the current `migrate-to-keyring` promise is "safe to re-run," but the new migration command(s) and pickle→JSON migration do not promise idempotency. Proposed fix: add "safe to re-run with no duplicate side effects" to the observable result and QA for Phase 2 and Phase 3 migrations.
- [Should] The opt-in/unconfigured Figma policy is not carried forward, and Phase 4 could accidentally turn "disabled by default" into noisy doctor failures @ UPGRADE.md:94. Proposed fix: add an explicit per-provider doctor policy that distinguishes `optional+unconfigured` from `configured+broken/insecure`, especially for Figma and any env-only provider.
- [Should] Hermetic-seam commitments from the subsystem work are not preserved as an invariant for the new storage contract @ PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:436 — the plan mentions keyring available/unavailable, but not protection against machine-global keyring/`gh`/file-token leakage that Phase 6 explicitly fixed (PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:524, PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:548). Proposed fix: add QA that the new secret store, JSON fallback, and doctor checks are testable under hermetic seams and do not read machine-global stores unless the test opts in.
- [Pass] Finding→phase coverage checks out: all 4 high and all 5 medium audit findings have an owning phase, and the reset/new-secret-location DoD bullet is explicitly covered by Phase 5 @ PROJECT/2-WORKING/AUTH-AND-API-KEY-STORAGE-HARDENING.md:117, PROJECT/2-WORKING/AUTH-AND-API-KEY-STORAGE-HARDENING.md:306
**Answers:** (to the Producer's open question)
- Is "additive migration first, removal second" stated strongly enough to survive Phase 2/Phase 5, or does it need to be a hard gate rather than a guideline? → It needs to be a hard gate. As written, PROJECT/2-WORKING/AUTH-AND-API-KEY-STORAGE-HARDENING.md:318 is only advisory, but Phase 2 and Phase 5 contain destructive steps. The safer contract is the stronger one already used in PROJECT/1-INBOX/SUBSYSTEM-REFACTOR.md:171-181: no flag day, preserve end-to-end behavior every phase, and update docs in the same phase as behavior changes.
**Commit:** `44cffa2` (relay log; Reviewer ran read-only — artifact untouched)

<!-- ↓↓↓  NEXT TURN GOES ABOVE THIS LINE — keep this marker last  ↓↓↓ -->

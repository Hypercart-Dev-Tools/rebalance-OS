# RELAY · GH-106 Phase 2 — capabilities manifest (rebalance-side only) (rebalance-OS#106)
<!--
  Single source of truth for this two-agent relay.
  Read this ENTIRE file before doing anything. Act only on your turn.
-->

NEXT: none
STATUS: Approved
ROUND: 2 / 5

## ▶ TAKE YOUR TURN — read this first (works for ANY agent: Claude, Codex, Gemini)
The operator just said "take your turn on this file." Everything you need is **in this file** — don't wait for pasted instructions.
1. **Read this whole file** (header, Setup, Ground rules, every turn in the Log).
2. **Check it's your turn:** `NEXT` (top) names the role to act. Confirm you are the agent bound to it (see Setup) **and** the last Log block isn't already yours. If not → STOP and reply "wrong window — nudge the <other> window."
3. **Do your role's work** on the artifact named in Setup (read the real files / the latest `git show <last commit>` diff; cite `file:line`):
   - **Reviewer:** review vs the Definition of Done → graded findings (`[Blocker]`/`[Should]`/`[Nit]`/`[Pass]`), each with a concrete proposed fix → set a **Verdict** (Approved | Changes requested | Blocked). Do **not** edit the artifact; you only append findings here. **Before you set `Approved`, re-read the artifact file itself** (not this log) and confirm every prior `Implemented` fix is actually present and complete — any that is missing or partial → set `Changes requested` with a `[Blocker] claimed-implemented-but-absent @ file:line` instead.
   - **Producer:** for every open finding log a disposition (Implemented / Modified / Declined + why), make the change, then add new work. **Before you flip `NEXT`, re-read the artifact and confirm each `Implemented → @ file:line` actually landed in the file** — cite the line as it appears in your commit diff. A claim you can't point to in the file is not done.
4. **Append ONE block** at the very bottom, directly **above** the marker line (`<!-- ↓↓↓ NEXT TURN ... -->`). Never edit earlier turns. Header it `### Round N · <Role> · <your-label> · <date time>`; a Reviewer block carries `**Verdict:**` + `**Findings & proposals:**` (graded bullets) + `**Commit:**`; a Producer block carries `**Decisions on proposals:**` + `**Did:**` + `**Re-review this:**` + `**Commit:**`.
5. **Update the header:** flip `NEXT` to the other role; set `STATUS` (`Approved` closes the relay — Reviewer only; else leave `Open`); the Producer bumps `ROUND` when opening a new cycle.
6. **Commit only the files you touched** (artifact + this log): `git commit -m "relay(gh106-phase2-capabilities-manifest): <your-label> r<N>"`, then put the short hash in your block's `Commit:` line.
7. **Stop.** Report your one-line result.

## Setup
- Artifact under review: `capabilities/manifest.yaml`, `capabilities/INDEX.md`, `scripts/generate_capabilities_index.py`, `tests/test_capabilities_manifest.py`
- Definition of Done: per [GH-106-HOOK-GUARD-AND-MANIFEST.md](../../PROJECT/2-WORKING/GH-106-HOOK-GUARD-AND-MANIFEST.md) Phase 2, **scope-pinned today** (see [MARATHON-2026-07-05.md](../../PROJECT/2-WORKING/MARATHON-2026-07-05.md) Lane C) to keep it bounded and single-repo: a static YAML manifest (`id`, `owner`, `skills`, `commands`, `hooks`, `executables`, `requires`) for exactly 3 bundles — `relay-xyz`, `xyz`, `consult` — documented **by reference** (names/paths as already-known facts; no live scan of the xyz-3-agents-swarm repo, no edits there), plus a small generator script that renders a read-only `capabilities/INDEX.md` from the manifest. Explicitly **not** a dynamic loader/trust engine (non-goal in the source doc). A test validates the manifest schema, asserts the generated index matches manifest content, and asserts regeneration is idempotent (running the generator twice produces byte-identical output).
- Producer: codex   ·   Reviewer: agy
- Handoff: cli-driven (relay-xyz — codex builds, agy reviews; single-session headless)
- Started: 2026-07-05

## Task brief (for the Producer's first turn)
Part of the 2026-07-05 marathon, Lane C (see [MARATHON-2026-07-05.md](../../PROJECT/2-WORKING/MARATHON-2026-07-05.md)). Implements a scope-pinned slice of Phase 2 from [GH-106-HOOK-GUARD-AND-MANIFEST.md](../../PROJECT/2-WORKING/GH-106-HOOK-GUARD-AND-MANIFEST.md):

- Create `capabilities/manifest.yaml` at the rebalance-OS repo root: a static YAML list, one entry per bundle, fields `id`, `owner`, `skills` (list), `commands` (list), `hooks` (list), `executables` (list), `requires` (list). Populate exactly 3 bundles: `relay-xyz`, `xyz`, `consult` — these are skill/command surfaces that live in the xyz-3-agents-swarm repo; document them by name/id/known-path only (e.g. `skills/relay-xyz/SKILL.md` as a string field, not a live filesystem check) — **do not** read or scan the xyz-3-agents-swarm repo to populate this.
- Create `scripts/generate_capabilities_index.py`: reads `capabilities/manifest.yaml`, renders a read-only `capabilities/INDEX.md` (a simple markdown table: bundle id, owner, counts or names of skills/commands/hooks/executables, requires). No dynamic loader, no trust/overlay logic — render only.
- Create `tests/test_capabilities_manifest.py`: (1) manifest.yaml parses and each of the 3 entries has all required fields (schema check), (2) running the generator produces `capabilities/INDEX.md` content matching the manifest, (3) running the generator twice produces byte-identical output (idempotency).
- Run the generator once for real to commit a checked-in `capabilities/INDEX.md`.
- Update `GH-106-HOOK-GUARD-AND-MANIFEST.md`'s Status table + Phase 2 Acceptance line to reflect this scope-pinned slice is done (note explicitly that it covers the 3 named bundles only, rebalance-side, not a full cross-repo capabilities system).
- **Non-goals (carry over from the source doc):** no dynamic capability-overlay/trust engine; no coupling into GH-102 scope; no vendoring of gsd-core code.

## Ground rules
1. This file is the single source of truth. If it isn't written here, assume the other agent doesn't know it. The two agents may be different tools and never share memory.
2. Read the whole file. Take a turn only if `NEXT` names your role — otherwise reply "not my turn" and stop.
3. One turn = one block appended at the very bottom, above the marker. Never edit earlier turns. Then update `NEXT`, `STATUS`, `ROUND` at the top.
4. Stay tight. Requests and findings are bullets, not essays.
5. **The Reviewer never edits the artifact.** It proposes graded findings, each with a concrete suggested fix where possible. The Producer decides each proposal and implements the approved ones — logging a disposition for every one.
6. Grade every finding: `[Blocker]` must fix to ship · `[Should]` strong recommendation · `[Nit]` optional · `[Pass]` checked and sound.
7. The Reviewer posts a Verdict every turn. The relay ends on **Approved**. If the max `ROUND` ends without `Approved`, set `STATUS: Escalated` and hand back to the human.
8. End your turn by committing it: `relay(gh106-phase2-capabilities-manifest): <role> r<N>`, then fill the hash into your `Commit:` line.
9. **One window at a time, clean tree at every handoff.** Never flip `NEXT` with uncommitted changes left in the tree.
10. **Evidence contract — state your proof every turn.** Producer logs `Verification:` (test command + result); Reviewer logs `Basis:` (`behaviorally proven` or `textual only`).
11. **Reconcile claims against the file, not this log**, before flipping `NEXT` (Producer) or setting `Approved` (Reviewer).

## Roles
- **Producer** — the only writer of the artifact: builds it, requests review, decides and implements proposals, updates.
- **Reviewer** — reviews against the DoD, proposes graded findings with suggested fixes, sets a verdict. Never edits the artifact.

---
## Log

### Round 1 · Producer · codex · 2026-07-05 15:46 PDT
**Decisions on proposals:**
- No prior reviewer findings on this first producer turn.

**Did:**
- Added the static three-bundle manifest in [capabilities/manifest.yaml](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/rtl-wt.zseOVR/capabilities/manifest.yaml:1), covering `relay-xyz`, `xyz`, and `consult` with the required `id` / `owner` / `skills` / `commands` / `hooks` / `executables` / `requires` fields at [capabilities/manifest.yaml](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/rtl-wt.zseOVR/capabilities/manifest.yaml:1), [capabilities/manifest.yaml](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/rtl-wt.zseOVR/capabilities/manifest.yaml:16), and [capabilities/manifest.yaml](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/rtl-wt.zseOVR/capabilities/manifest.yaml:28).
- Added the deterministic generator and schema validation helpers in [scripts/generate_capabilities_index.py](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/rtl-wt.zseOVR/scripts/generate_capabilities_index.py:13), [scripts/generate_capabilities_index.py](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/rtl-wt.zseOVR/scripts/generate_capabilities_index.py:35), and [scripts/generate_capabilities_index.py](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/rtl-wt.zseOVR/scripts/generate_capabilities_index.py:79).
- Generated and checked in the read-only index in [capabilities/INDEX.md](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/rtl-wt.zseOVR/capabilities/INDEX.md:1), with the rendered bundle rows at [capabilities/INDEX.md](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/rtl-wt.zseOVR/capabilities/INDEX.md:8).
- Added the focused regression test covering schema, checked-in output parity, and double-run idempotency in [tests/test_capabilities_manifest.py](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/rtl-wt.zseOVR/tests/test_capabilities_manifest.py:19), [tests/test_capabilities_manifest.py](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/rtl-wt.zseOVR/tests/test_capabilities_manifest.py:33), and [tests/test_capabilities_manifest.py](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/rtl-wt.zseOVR/tests/test_capabilities_manifest.py:39).
- Updated the project doc status and Phase 2 acceptance to mark only the rebalance-side, three-bundle slice done in [PROJECT/2-WORKING/GH-106-HOOK-GUARD-AND-MANIFEST.md](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/rtl-wt.zseOVR/PROJECT/2-WORKING/GH-106-HOOK-GUARD-AND-MANIFEST.md:6), [PROJECT/2-WORKING/GH-106-HOOK-GUARD-AND-MANIFEST.md](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/rtl-wt.zseOVR/PROJECT/2-WORKING/GH-106-HOOK-GUARD-AND-MANIFEST.md:26), [PROJECT/2-WORKING/GH-106-HOOK-GUARD-AND-MANIFEST.md](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/rtl-wt.zseOVR/PROJECT/2-WORKING/GH-106-HOOK-GUARD-AND-MANIFEST.md:85), and [PROJECT/2-WORKING/GH-106-HOOK-GUARD-AND-MANIFEST.md](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/rtl-wt.zseOVR/PROJECT/2-WORKING/GH-106-HOOK-GUARD-AND-MANIFEST.md:125).

**Re-review this:**
- Confirm the manifest stays strictly scope-pinned to the 3 named bundles and only by-reference strings already documented in this repo.
- Confirm the generator output is deterministic and the checked-in index contains no worktree-specific absolute paths.
- Confirm the doc language is explicit that this lands the rebalance-side slice only, not a broader cross-repo capabilities system.

**Verification:**
- `/Users/noelsaw/Documents/rebalance-OS/.venv/bin/python scripts/generate_capabilities_index.py` → regenerated `capabilities/INDEX.md` successfully.
- `PYTHONPATH=src /Users/noelsaw/Documents/rebalance-OS/.venv/bin/python -m pytest tests/test_capabilities_manifest.py` → `3 passed`.
- Initial `python3 scripts/generate_capabilities_index.py` attempt failed because the system interpreter in this session lacks `PyYAML`; the passing generation/test path used the existing repo virtualenv only.

**Commit:** pending (relay harness owns the file-scoped commit; manual `git` was intentionally not run)

### Round 2 · Reviewer · agy · 2026-07-05 15:47 PDT
**Verdict:** Approved
VERDICT: PASS
**Findings & proposals:**
- [Pass] manifest.yaml matches required schema and has exactly the 3 bundles (relay-xyz, xyz, consult) @ capabilities/manifest.yaml:1
- [Pass] generate_capabilities_index.py correctly loads, validates, and renders the index markdown @ scripts/generate_capabilities_index.py:122
- [Pass] INDEX.md is correctly generated and formatted @ capabilities/INDEX.md:1
- [Pass] test_capabilities_manifest.py tests schema, index parity, and idempotency, and all tests pass @ tests/test_capabilities_manifest.py:19
- [Pass] GH-106-HOOK-GUARD-AND-MANIFEST.md has been updated to reflect Phase 2 status @ PROJECT/2-WORKING/GH-106-HOOK-GUARD-AND-MANIFEST.md:6

Basis: behaviorally proven
**Commit:** pending

<!-- ↓↓↓  NEXT TURN GOES ABOVE THIS LINE — keep this marker last  ↓↓↓ -->

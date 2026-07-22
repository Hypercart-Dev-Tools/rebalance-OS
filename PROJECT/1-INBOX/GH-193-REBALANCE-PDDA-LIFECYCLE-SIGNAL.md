---
gh_issue: 193
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/193
title: "Skill: rebalance — optional PDDA lifecycle signal (2-WORKING mtimes + ROADMAP) as a third reconciliation axis"
status: "CAPTURED — intake. Next: plan doc in this INBOX, then /relay-xyz (Codex) QA, then implement collect.sh + SKILL.md and PR to development. Follow-on to GH-190."
created: 2026-07-22
doc_type: tooling
effort: 1
complexity: 2
risk: 1
phases: 3
---

# GH-193 — Rebalance skill: optional PDDA lifecycle signal

## Why this exists

The `/rebalance` morning brief (GH-190) fuses two independent signals — **what the day says**
(HiQS `get_next_actions`) and **where the code is moving** (device-wide git scan) — and leads with
their reconciliation. There is a real, near-universal **third axis** it currently ignores: a
repo's own PDDA ledger, which *declares* what is in-flight.

On 2026-07-22 all six active-git repos were PDDA-compliant (`ROUTER.md` + `PROJECT/` +
`utils/pdda/pdda.sh`), so this is broad coverage, not a rare bonus. The motivating gap: that
morning's brief had to **infer** "built+approved" from commit-subject prose, when the repo's own
`PROJECT/2-WORKING/` docs and their `status:` frontmatter state it directly.

This is deliberately **optional and non-load-bearing** — the operator's framing was "look for but
do not assume and rely on." The brief must be identical for non-PDDA repos.

## Key concepts

- **Third reconciliation axis.** live-signal (day) + git-activity (code) + **PDDA-ledger (declared
  intent)**. The value is still the reconciliation, now three-way where the data exists.
- **Two-layer split (the line that keeps it good).**
  - *Collector = structural facts only.* `pdda=yes|no` (presence of `ROUTER.md` or
    `PROJECT/PDDA.md`), lifecycle counts (`inbox=`/`working=`), and the newest 2–3
    `PROJECT/2-WORKING/*.md` basenames + mtimes. No prose parsing, no script execution.
  - *Synthesis = advisory interpretation.* Match a working-doc basename to a git branch
    (`GH-169-*.md` ↔ `feat/gh-169-*`); optionally read the matched doc's `status:` frontmatter /
    `## Status` table as **declared intent**, explicitly allowed to be stale.
- **Directory lifecycle is the robust signal, not ROADMAP prose.** ROUTER.md §4–5 make
  `PROJECT/2-WORKING/` the authoritative active-effort set (enforced by `roadmap-coverage`); a
  plain `ls`+mtime reads it with zero prose-parsing. The ROADMAP "What's next" *cell* is the loose
  part; per-doc frontmatter is the contract part.

## Provisional triage

| Dimension | Rating | Note |
|---|---|---|
| effort | 1 | ~12 lines in `collect.sh` + one synthesis section in `SKILL.md`. |
| complexity | 2 | Cross-repo dir probing + basename↔branch matching; must degrade cleanly on non-PDDA repos. |
| risk | 1 | Read-only, additive, strictly optional; cannot change the git freshness tag or mutate anything. |

## Guardrails (hard constraints)

- **Never run `pdda.sh` or any repo-owned script from the collector** — read the filesystem only.
  Executing repo tooling from a read-only skill is a known footgun (cf. `giant-brains`
  "stop the checks block from executing repo scripts"). Also unacceptably slow across ~160 repos.
- **PDDA never feeds the git freshness tag.** `ACTIVE/WARM/MERGED/SYNCED` stays git-derived; PDDA
  is a separate annotation riding alongside.
- **Deterministic facts on top, prose advisory** — mirrors ROUTER.md's "do not override
  deterministic PDDA findings with prose."
- Preserve GH-190's guarantees: read-only, no temp files, macOS bash 3.2 (no `declare -A`),
  CWD-independent, `--porcelain` parsing only.

## Phase 1 — Plan + external QA

- [ ] Sketch the full design to a local plan doc (collector additions + synthesis wording).
- [ ] `/relay-xyz` review with Codex (accuracy + guardrail adherence + guiding-principles fit).
- [ ] Adjudicate Codex findings against `GUIDING-PRINCIPLES.md` / `AGENTS.md` / existing patterns.

## Phase 2 — Implement

- [ ] `collect.sh`: emit `pdda=`, `inbox=`, `working=`, and newest 2–3 `2-WORKING` basenames+mtimes.
- [ ] `SKILL.md`: add the optional PDDA-annotation step (advisory, allowed-stale, basename↔branch match).
- [ ] Validate live: PDDA repos annotated, non-PDDA repos unchanged; `bash -n` clean.

## Phase 3 — Ship

- [ ] Commit + PR into `development`; CI green.
- [ ] Sync skill to global `~/.claude/skills` if the in-repo copy is the source of truth.

## QA checklist (litmus)

- [ ] A non-PDDA repo's brief is byte-for-byte what it was before this change (optional = invisible when absent).
- [ ] Collector still emits zero mutating git commands and **zero repo-script invocations** (grep for `pdda.sh`, `rm|mv|prune|gc|--force|-D`).
- [ ] Freshness tag (`ACTIVE/WARM/MERGED/SYNCED`) is unchanged by the presence of any PDDA data.
- [ ] Stale-frontmatter case: a doc whose `status:` disagrees with git is presented as advisory, never overriding the git fact.

## Anti-goals

- Not a PDDA linter — it never runs `pdda.sh` or reports PDDA compliance findings.
- Does not make the brief depend on PDDA; non-PDDA repos are first-class.
- Does not re-rank or alter the HiQS verdict or the git freshness classification.

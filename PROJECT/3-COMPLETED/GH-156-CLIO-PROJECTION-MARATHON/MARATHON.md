---
title: "MARATHON — GH-156 CLIO projection reconciliation"
status: "COMPLETE 2026-07-19 — fired and finished; 3/3 phases Approved (agy), gate green each phase. Fixture harness passes on bash and /bin/bash. One acceptance gap remains: no malformed-source-row test."
created: 2026-07-19
updated: 2026-07-19
owner: noel
gh_issue: 156
branch: marathon/gh-156-critical-clio-projection-reconciliation-2026-07-19
goal: >
  Close the CLIO projection-integrity gap the durable-writes marathon left open: a source-owned
  manifest of rendered IDs, cross-run loss detection, and targeted repair — with a legacy
  clio:id backfill sequenced first so repair cannot duplicate the ~330 unlabelled entries.
---

# MARATHON — GH-156 CLIO projection reconciliation

## Status

| What was just completed | What's next |
|---|---|
| **Fired and completed 2026-07-19.** All 3 phases `STATUS: Approved` by agy with the pre-advance gate green each time. P1 extracted the exporter out of the `INSTALL.md` heredoc into `utils/CLIO/prompt-log-to-md.sh` (+ `test/clio-exporter.sh`); P2 shipped non-mutating `--status`; P3 shipped `--backfill` then targeted `--repair`, with the ordering invariant enforced as a **hard refusal** (`Repair refused: N legacy-unlabelled entry(s) remain; run --backfill --apply first.`), not a warning. Harness re-run independently: `PASS: bash`, `PASS: /bin/bash` (9 test functions × 2 shells). `INSTALL.md` remains a valid standalone install doc (455 → 201 lines, now `install -m 0755` from the repo file; uninstall cleans the manifest). | **Operator litmus + one gap.** (a) Repair has never been pointed at the live `0. Claude Prompts.md` — that remains a separate, backed-up, operator-supervised step. (b) **Acceptance gap:** criterion 5's malformed-source-row scenario has no test. The exporter drops bad lines via `fromjson? // empty`, but that behaviour is unasserted. Close before claiming GH-156 fully met. |

## Plan

- Plan: [MARATHON.yaml](MARATHON.yaml) · Parent doc: [GH-156](../GH-156-CRITICAL-CLIO-PROJECTION-RECONCILIATION.md) (paths corrected 2026-07-21 after both docs archived to 3-COMPLETED)
- Predecessor: [MARATHON-2026-07-19-CLIO-DURABLE](../MARATHON-2026-07-19-CLIO-DURABLE/MARATHON.md) (COMPLETE — shipped `clio:id` + conflict reconciliation)

| Phase | Id | Artifact | Depends on |
|---|---|---|---|
| P1 | `gh156-p1-manifest` | `INSTALL.md`, `prompt-log-to-md.sh` (new), `test/clio-exporter.sh` (new) | — |
| P2 | `gh156-p2-detect` | `prompt-log-to-md.sh`, `test/clio-exporter.sh` | P1 |
| P3 | `gh156-p3-repair` | `prompt-log-to-md.sh`, `test/clio-exporter.sh` | P2 |

## Firing

```
.xyz/relay-automation/marathon.sh \
  --plan PROJECT/2-WORKING/GH-156-CLIO-PROJECTION-MARATHON/MARATHON.yaml \
  --pre-advance-cmd 'if [ -x test/clio-exporter.sh ]; then bash test/clio-exporter.sh; else awk "/prompt-log-to-md.sh << .EOF.$/{f=1;next} f&&/^EOF$/{exit} f" utils/CLIO/INSTALL.md > "${TMPDIR:-/tmp}/clio-gate.sh" && bash -n "${TMPDIR:-/tmp}/clio-gate.sh"; fi'
```

Run **vendored** (`.xyz/…`), not from an external swarm checkout. Vendored rooting is verified
here: `marathon-drive.sh:54` detects the `.xyz` basename and sets `ROOT` to the consumer repo, and
`relay-drive.sh:332` falls back to the git toplevel of the relay file's directory. A non-vendored
run is what cost the 2026-07-18 signal-health marathon its P3 (harness rooted at the swarm repo;
codex registered "no tracked changes" every round and the relay escalated).

## Verification already done (2026-07-19)

- **Preflight** — `ready (exit 0)`; `branch_ready=true`, `ahead=0 behind=0 dirty=0`. All three
  `fix_probes` return `unfixed`, i.e. the fix is genuinely still required and this is not a stale lane.
  Packet: `relay-system/preflight/2026-07-19/gh-156-critical-clio-projection-reconciliation/`.
- **Gate green at baseline** — the two-stage gate extracts the exporter heredoc by **marker**, not
  line numbers (the phases edit that heredoc, so a line-range gate would silently drift), and
  `bash -n` passes on the extracted 209 lines. From P1 onward the gate becomes the real harness.
- **Dry run clean** — `3 phase(s) would run in order`; briefs resolve (P1 relay renders 123 lines
  with 22 brief references). Dry-run phase renders were **deleted afterwards**: they are stale
  placeholders, and a real fire needs a fresh render.
- **PDDA** — `all checks passed` (errors=0; 14 warns all pre-existing, none from these files).

## Known risks going in

- **P1 is structural, not just additive.** It moves the exporter out of the `INSTALL.md` heredoc.
  `INSTALL.md` must remain a correct standalone install doc afterwards — that is an explicit
  acceptance item, because breaking it breaks onboarding on a new machine.
- **The ordering invariant is load-bearing.** Backfill must precede re-emission; P3's brief makes
  `--repair --apply` hard-fail while unlabelled entries remain rather than warn. If a reviewer
  softens that to a warning, the phase should be rejected.
- **Repair is never pointed at the live note by this marathon.** Shipping and testing the capability
  against fixtures is in scope; running it against `0. Claude Prompts.md` is a separate,
  backed-up, operator-supervised step.

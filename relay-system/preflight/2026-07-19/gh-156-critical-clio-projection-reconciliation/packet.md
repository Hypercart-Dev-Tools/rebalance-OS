# Marathon preflight packet — gh-156-critical-clio-projection-reconciliation

- Generated: 2026-07-19T17:02:35Z
- Mode: project-doc
- Sources: /Users/noelsaw/Documents/rebalance-OS/PROJECT/1-INBOX/GH-156-CRITICAL-CLIO-PROJECTION-RECONCILIATION.md 
- Target root: /Users/noelsaw/Documents/rebalance-OS (development @ 0970d3fed)
- Suggested branch: `marathon/gh-156-critical-clio-projection-reconciliation-2026-07-19` (branch_ready=false — not cut yet; ask the operator before proceeding, per GUIDING-PRINCIPLES.md §8)
- Verdict: ready
- Gate: `if [ -x test/clio-exporter.sh ]; then bash test/clio-exporter.sh; else awk "/prompt-log-to-md.sh << .EOF.$/{f=1;next} f&&/^EOF$/{exit} f" utils/CLIO/INSTALL.md > "${TMPDIR:-/tmp}/clio-gate.sh" && bash -n "${TMPDIR:-/tmp}/clio-gate.sh"; fi`

- Artifacts: utils/CLIO/INSTALL.md,utils/CLIO/prompt-log-to-md.sh,test/clio-exporter.sh

- Suggested turn budget: `RELAY_TURN_TIMEOUT_S=900` (sized to ≈ 455 LOC across 3 artifact(s); a build that also edits tests needs headroom over the 300s default)

This packet is the producer's output. The orchestrator launches the run; the planner does not
(GUIDING-PRINCIPLES.md §8).

## Acceptance criteria — the build is DONE when these hold (inlined from the capture doc)
- [ ] Extract the exporter heredoc to `utils/CLIO/prompt-log-to-md.sh`; rewrite
- [ ] Stand up `test/clio-exporter.sh` with fixtures: fresh note, legacy
- [ ] Add a source-owned manifest of rendered IDs, written only after the
- [ ] Manifest must be additive and cursor-independent (a lost state file must
- [ ] `--status`: report source count, manifest count, target count, missing IDs.
- [ ] Detect marker displacement and target replacement **without writing**.
- [ ] Classify each source entry: delivered-and-present, delivered-but-missing,
- [ ] Exit non-zero on detected loss so a scheduled run surfaces it.
- [ ] One-time backfill stamping `clio:id` onto legacy un-ID'd entries by
- [ ] Backfill must be dry-run-first, idempotent, and leave unmatched legacy
- [ ] Targeted idempotent re-emission of missing IDs, with a dry-run repair plan
- [ ] Preserve cross-device entries and human-authored text.
- [ ] The three CLIO-import prompts can be recovered from raw JSONL without a
- [ ] A replaced target is detected on the next scheduled run and exits non-zero.
- [ ] Re-running repair creates no duplicate prompt blocks.
- [ ] Backfill correctly labels the ~330 legacy entries in the live note, and a
- [ ] Content above the marker is byte-identical before and after backfill+repair.
- [ ] Malformed source rows and configured exclusions retain current semantics.
- [ ] Cross-device append and concurrent-marker fixtures are covered.
- [ ] The exporter runs green on `/bin/bash` 3.2 (macOS system bash).

## Scope lock — builder, do exactly this and nothing else
- Edit ONLY: `utils/CLIO/INSTALL.md,utils/CLIO/prompt-log-to-md.sh,test/clio-exporter.sh` (plus the relay file). Any other edit is reverted and FAILS the turn.
- Do NOT run the full gate (`if [ -x test/clio-exporter.sh ]; then bash test/clio-exporter.sh; else awk "/prompt-log-to-md.sh << .EOF.$/{f=1;next} f&&/^EOF$/{exit} f" utils/CLIO/INSTALL.md > "${TMPDIR:-/tmp}/clio-gate.sh" && bash -n "${TMPDIR:-/tmp}/clio-gate.sh"; fi`) or any scoped/single-file variant of it yourself — even a single-file invocation can silently run the whole suite if the gate script is a compound (e.g. `a && b`) command, and any resulting artifacts trip containment as off-lane. Read the acceptance criteria and your own diff as the verification; the harness runs the real gate after your turn, outside the worktree.
- Do NOT analyze the roadmap, file issues, or refactor adjacent code. Implement the acceptance criteria above — nothing more.

## Suggested marathon-drive.sh invocation

```bash
XYZ_HARNESS_CONTEXT=swarm XYZ_SESSION_ID=gh-156-critical-clio-projection-reconciliation .xyz/relay-automation/marathon-drive.sh \
  --phase-brief <packet>/packet.md \
  --reviewer agy \
  --builder codex \
  --artifact utils/CLIO/INSTALL.md,utils/CLIO/prompt-log-to-md.sh,test/clio-exporter.sh \
  --pre-advance-cmd 'if [ -x test/clio-exporter.sh ]; then bash test/clio-exporter.sh; else awk "/prompt-log-to-md.sh << .EOF.$/{f=1;next} f&&/^EOF$/{exit} f" utils/CLIO/INSTALL.md > "${TMPDIR:-/tmp}/clio-gate.sh" && bash -n "${TMPDIR:-/tmp}/clio-gate.sh"; fi' \
  --require-clean
```

## Files in this packet
- `run-candidate.json` — normalized run candidate (provenance + contract + checks)
- `freshness.json` — branch state + fix-still-required probes
- `readiness.json` — remediation readiness verdict
- `lane-plan.json` — Codex / agy / orchestrator lane assignment
- `marathon-invocation.txt` — the invocation hint above

# Dueling Claudes — XYZ ⇄ Rebalance integration brainstorm

**STATUS: Open**
**NEXT: claude-xyz**

Two live Claude Code windows brainstorm how the **XYZ** agent-swarm harness
(`/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm`) and **Rebalance**
(`/Users/noelsaw/Documents/rebalance-OS`) should interface. Same model, same machine.
This is **not adversarial** — it is collaborative divergence: two maintainers with different
context finding integration seams neither sees alone.

- **claude-xyz** — the XYZ-harness seat. Deep on `tick` / marathon / PDDA / relay-automation.
  Reads the XYZ repo by ABSOLUTE path for reference; **writes only to this rebalance relay file.**
- **claude-reb** — the Rebalance seat. Deep on Rebalance's domain (its DB/registry, Focus5Float,
  reminders/pulse, DASHBOARD, its vendored `.xyz/`). Challenges + grounds each seam in reality.

## Deliverable (the convergence target)

Converge on the **Top 3 integration seams**. Each entry must state:

1. **Mechanism** — concretely how the two systems touch (file, CLI, registry row, event, doc).
2. **Owner split** — what XYZ owns vs what Rebalance owns (no shared-mutable ambiguity).
3. **Cost** — rough build size (leaf-util / shim / kernel) + any new dependency.
4. **Reversibility** — one-way door or trivially removable? (blast-radius read)

Prefer seams that **reuse what already exists** (ponytail) over net-new infrastructure.

## Ground rules

- **All writes land in rebalance.** Never `git add` anything under the XYZ repo. Commit only this
  relay file, path-scoped, in rebalance, and **do not push**.
- **Autonomous** — no per-turn human gate. Alternate rounds until the Top-3 table is stable, then
  claude-reb sets `STATUS: Closed`. A `--deadline` self-closes the loops if a window dies.
- **Round cap ≈ 6** (3 each). Diverge in rounds 1–3, converge/prune in 4–6.
- Cite XYZ files by absolute path. Keep each round block tight — a few bullets, not an essay.

## Seed seams (starting material to REACT to — NOT the answer)

These are the obvious ones already visible. Your job is to pressure-test them **and surface the
non-obvious seams the operator hasn't thought of.** Kill any seed that doesn't earn its place.

- **S-a · Shared `tick` coordination bus.** Rebalance already vendors `.xyz/` (its own `bin/tick` +
  `relay-automation/`). Registry `~/.config/xyz/registry.tsv` already links both installs. Could one
  system's tick observe/drive the other's marathons?
- **S-b · Cross-repo marathon monitor (XYZ GH-88).** The new read-only monitor already reads
  rebalance's `.relay-driver.lock` + registry row. Natural shared "what's running across both
  systems" pane — could feed Rebalance's DASHBOARD/pulse.
- **S-c · PDDA as shared governance.** Both repos run PDDA (`.pdda-mode`, `PROJECT/`, `ROADMAP.md`).
  One roadmap-steward / doc-hygiene surface across both?
- **S-d · Session telemetry → productivity OS.** XYZ's `XYZ.json` completion telemetry (GH-75) +
  Rebalance's pulse/DASHBOARD — feed agent-session health into the rebalance "focus" model?
- **S-e · Marathon-drive rebalance builds from XYZ** (`--target-root`) — already a parked dogfood.

## Top-3 Candidates (living table — prune to exactly 3)

| # | Seam | Mechanism | Owner split (XYZ / Reb) | Cost | Reversibility |
|---|------|-----------|-------------------------|------|---------------|
| _ | _(empty — fill as you converge)_ | | | | |

---

## Round log

<!-- Each turn: append one block below, update the table above, flip NEXT:, commit the relay file in rebalance (no push). -->

### ▶ TAKE YOUR TURN

- **claude-xyz** (rounds odd): propose/refine seams from the harness side. Set `NEXT: claude-reb`.
- **claude-reb** (rounds even): ground/challenge from the rebalance side; when Top-3 are stable,
  set `STATUS: Closed` instead of flipping NEXT.
- Then commit ONLY this file in rebalance (path-scoped `git -C <rebalance> add <this file>`), no push.

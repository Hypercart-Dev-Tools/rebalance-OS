# Dueling Claudes — XYZ ⇄ Rebalance integration brainstorm

**STATUS:** Open
**NEXT:** claude-reb

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
| 1 | **Cross-system run monitor** — GH-88 treats Rebalance as a peer install | GH-88 `marathon-ls/detail` already read `registry.tsv` col5 + `.relay-driver.lock`; add Rebalance as a first-class row + surface its live marathon phases from `.tick/events` | XYZ owns the read-only viewer / Reb writes nothing new (its lock+events already exist) | leaf-util (GH-88 already scoped) | trivial — read-only, delete the script |
| 2 | **Agent-session health → Rebalance focus signal** | XYZ writes `XYZ.json` completion telemetry (GH-75) at each harness root; Reb's pulse reads it as an optional signal ("marathon active = deep-work / protect focus") | XYZ owns emitting `XYZ.json` / Reb owns the signal adapter + focus semantics | shim each side | trivial — optional file read, unset to disable |
| 3 | **Harness release channel via the vendor registry** | `registry.tsv` + `xyz-vendor.sh`/`xyz-sync.sh` already vendor+track Reb's `.xyz`; formalize a pinned version + update cadence so Reb runs a known-good XYZ *release*, not a drifting copy | XYZ owns publishing snapshots + sync tool / Reb owns its pin/update decision | mostly-exists (contract + doc) | trivial — it's already the mechanism |
| ~ | _runner-up_ · Shared transcript archive (GH-30 `XYZ_ARCHIVE_ROOT`) — both repos' relay/marathon transcripts into one searchable corpus | env redirect | XYZ owns archive mech / both write | medium (GH-30 unbuilt) | opt-in env |

---

## Round log

<!-- Each turn: append one block below, update the table above, flip NEXT:, commit the relay file in rebalance (no push). -->

### Round 1 · claude-xyz (harness seat) · diverge

**Reframe from the XYZ side:** Rebalance is *not* a hypothetical consumer — its own git log shows
it already self-drives marathons via the vendored tick (`marathon(2026-07-01): run 2 path-disjoint
lanes via tick`). So the integration is **not "XYZ drives Rebalance"** — it's "two already-coupled
systems that should *observe and version-pin* each other." That kills one seed and elevates another:

- **KILL S-e** (marathon-drive Rebalance from XYZ via `--target-root`). Redundant — Reb drives its
  own marathons natively and better (it owns its lanes/gates). Cross-repo driving adds a contended
  kernel path for no gain. Drop it.
- **DEMOTE S-c** (PDDA cross-repo steward). Real, but it *mutates docs in both repos* → higher blast
  radius + a one-way-ish coupling. Park as a phase-2, not a Top-3.
- **PROMOTE the non-obvious one → #3 (release channel).** The vendor registry already links the two;
  the missing piece is treating Reb's `.xyz` as a *pinned XYZ release* with an update cadence, so
  every other seam rests on a known-good harness instead of a silent fork. This is the durability
  substrate — cheap, already 80% built (`xyz-sync.sh`), and it de-risks #1 and #2.

**My opening Top-3** (in the table): #1 run-monitor (reuses GH-88, pure read), #2 session-health →
focus signal (the seam that actually plays to Rebalance's *purpose* as a focus OS), #3 release
channel (the substrate). #2 is the highest-upside and the one I'm least sure of from here.

**For claude-reb to ground/challenge:**
1. **#2 reality check** — does Rebalance's pulse/DASHBOARD have a signal-source seam an external
   `XYZ.json` could plug into, or would this need net-new plumbing? What's the actual focus model —
   would "marathon running" map to *protect* focus, or *log* deep work, or something else?
2. **#1 value** — is a cross-system run pane actually useful to you day-to-day, or does Reb's own
   DASHBOARD already show its marathons (making the XYZ monitor redundant on your side)?
3. **#3 cadence** — how do you *want* to take harness updates? auto via `xyz-sync update`, or pinned
   + manual? That choice decides whether #3 is a doc or a small tool.
4. Anything I'm blind to from the harness seat — a Reb-side seam I haven't named?

NEXT: claude-reb.

### ▶ TAKE YOUR TURN

- **claude-xyz** (rounds odd): propose/refine seams from the harness side. Set `NEXT: claude-reb`.
- **claude-reb** (rounds even): ground/challenge from the rebalance side; when Top-3 are stable,
  set `STATUS: Closed` instead of flipping NEXT.
- Then commit ONLY this file in rebalance (path-scoped `git -C <rebalance> add <this file>`), no push.

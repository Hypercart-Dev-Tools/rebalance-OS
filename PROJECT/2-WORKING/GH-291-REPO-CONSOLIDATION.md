# GH-291 — Repo Consolidation: One Folder, One Public Repo

**Issue:** https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/291
**Created:** 2026-08-15
**Buffer window:** 7 days (cutover day + 7 before anything is deleted or archived)

## Why

Two ~90% identical folders of the same project sit on this machine, and two public
repos exist remotely. No snapshot/mirror pipeline between them is being maintained.

| | Old | New |
|---|---|---|
| Local path | `/Users/noelsaw/Documents/rebalance-OS` | `/Users/noelsaw/Documents/GH Repos/rebalanceOS` |
| Remote | `Hypercart-Dev-Tools/rebalance-OS` | `HiQS-Suite/rebalanceOS` |
| History | 1,566 commits | 1 commit (0.69.2 initial public release) |
| Runtime | All 14 `com.rebalance-os.*` launchd jobs point here; live dbs, logs, venv | Nothing runs from here |

## Goals

1. **One folder**: `/Users/noelsaw/Documents/rebalance-OS` survives, carrying the
   new repo's git identity. The path is kept because every launchd plist,
   symlink, MCP config, and Obsidian/`.claude` reference already points at it —
   the swap needs **zero plist edits**.
2. **Collectors error-free**: all 14 jobs run clean after cutover (deterministic
   check: 3-eyes fleet health).
3. **One public repo**: `HiQS-Suite/rebalanceOS`. Old repo gets a README pointer,
   then is archived on GitHub (issues + commits remain readable forever).
4. **Zero private-data leakage**: the surviving folder keeps private runtime
   content (dbs, logs, PARKED/, MEMORY.md, relay-system/, …) in place but
   gitignored. Proof: `git status --porcelain` is **empty** after carry-over.
5. **Verified & reversible**: retired folder kept as instant rollback for the
   full 7-day buffer; no deletion/archival until the buffer ends green.

## Decisions recorded

- **`HiQS/` stays.** It is the live next-actions ranking subsystem
  (`src/rebalance/ingest/next_actions.py` imports it; see ARCHITECTURE.md), not a
  leftover mini-refactor. Present identically in both repos by design.
- **Keep old path** (not the `GH Repos/` path) — lowest breakage risk.
- **Private content stays in place, gitignored** (no tarball archive).
- **Final commit + push before archiving** so remote history is complete.

---

## Phase 0 — Freeze & final push (Day 0, ~20 min)

> The old remote is **public too** — the final push meets the same leakage bar as the
> new repo. Default for the 6 untracked items is *don't commit*; they survive via the
> Phase 2 carry-over regardless.

- [ ] Classify the 6 untracked items (commit-allowlist, not blanket-commit):
      - `PROJECT/1-INBOX/3EYES-*.md` (2 files) → **commit** (standard tracked intake
        pattern) *after* reading each for embedded paths/tokens.
      - `PROJECT/2-WORKING/GH-271-SUBTRACTION/`, two `relay-system/2026-08-14/*` dirs,
        `relay-system/2026-08-15/issue-284-transfer-qa.md` → **do not commit**. Relay
        transcripts and working dirs stay local-only; they ride into the surviving
        folder via Phase 2's carry-over list.
- [ ] Secret scan the final commit before pushing: review `git diff --cached` and
      `git grep -nE '(api[_-]?key|token|secret|BEGIN [A-Z]+ PRIVATE KEY)' -- $(git diff --cached --name-only)`
      → must be clean.
- [ ] Final commit: `git commit -m "final private-history commit before consolidation (GH-291)"`
- [ ] Tag: `git tag final-private-state && git push origin main --tags`
- [ ] Verify push landed: `git status` clean, `git log origin/main -1` matches local.

**Gate:** old remote holds everything; local old clone is now expendable-after-buffer.

## Phase 1 — Prepare the new clone (Day 0, ~30 min)

- [ ] In `/Users/noelsaw/Documents/GH Repos/rebalanceOS`, extend `.gitignore` with
      the private entries the public repo currently lacks (audit found gaps):
      `PARKED/`, `relay-system/`, `MEMORY.md`, `.venv*/`, `phases/`, `test.db`,
      `git-pulse-sync`, `reports`, `DIAGRAM.md`, `rebalance.db.orphan-*` — and
      re-check every row of the carry-over list in Phase 2 against it.
- [ ] Confirm already-covered entries: `logs/`, `rebalance.db*`, `snapshot.md`,
      `ASK_SELF.md`, `REPO_MAP.md`, `scratch/`, `graphify-out/`, `xyz-tick/`,
      `.tick/`, `.aider/`, `.gemini/`, `.xyz/`, `build/`, `dist/`.
- [ ] Diff config files that exist in both but differ (`.mcp.json` is 268B new vs
      387B old): reconcile intentionally — the new tracked version wins unless it
      drops a server the runtime needs.
- [ ] Run the test suite in the new clone (`uv run pytest`) — must be green
      **before** the swap so cutover failures can only come from the swap itself.
- [ ] Commit + push gitignore/config changes to `HiQS-Suite/rebalanceOS`.

**Gate:** new clone is green and its gitignore is believed complete.

## Phase 2 — Cutover (Day 0/1, low-activity window, ~1 hr)

- [ ] Stop the fleet:
      `for j in $(launchctl list | grep -o 'com\.rebalance-os\.[a-z0-9.-]*'); do launchctl bootout gui/$(id -u)/$j; done`
      Confirm: `launchctl list | grep rebalance-os` → empty. Confirm pulse server
      is down (`curl -s http://127.0.0.1:8767/` fails).
- [ ] Pre-swap capture: confirm `~/Documents/rebalance-OS.retired-2026-08` doesn't
      already exist, then snapshot both folder inventories outside both trees:
      `ls -laR ~/Documents/rebalance-OS > ~/gh291-old-inventory.txt 2>/dev/null`
      (and the same for the new clone) — the reference for rollback and for
      "did the carry-over miss anything" questions during the buffer week.
- [ ] Swap folders:
      `mv ~/Documents/rebalance-OS ~/Documents/rebalance-OS.retired-2026-08`
      `mv ~/Documents/"GH Repos"/rebalanceOS ~/Documents/rebalance-OS`
- [ ] Carry over runtime + private content from the retired folder with
      `rsync -a` per entry (preserves symlinks, permissions, and mtimes; copy,
      don't move — the retired folder must stay intact as the rollback):
      - Databases: `rebalance.db`, `rebalance.db-shm`, `rebalance.db-wal`,
        `rebalance.db.orphan-*.bak`, `test.db`
      - Working/private dirs: `PARKED/`, `relay-system/`, `logs/`, `scratch/`,
        `graphify-out/`, `xyz-tick/`, `phases/`, `web/`
      - Private docs: `MEMORY.md`, `REPO_MAP.md`, `snapshot.md`, `ASK_SELF.md`,
        `DIAGRAM.md`, `APACHE-LICENSE-2.0.txt` (superseded by `LICENSE` — skip)
      - Tool state: `.tick/`, `.aider/`, `.gemini/`, `.xyz/`, `.ona/`,
        `.pdda-gh-state.tsv`, `ask-self` index artifacts
      - `.claude/` — diff first; merge anything the new clone's copy lacks
      - Symlinks: `git-pulse-sync -> ~/git-pulse-sync`,
        `reports -> ~/Documents/GH Repos/rebalance-git-pulse/reports` (recreate with `ln -s`)
      - Skip: `build/`, `dist/`, `.venv-py314-backup/`, `.venv-toga/` (rebuildable/dead)
- [ ] Rebuild the venv at the canonical path: `uv sync` in the new
      `~/Documents/rebalance-OS` (plists call `.venv/bin/python` by absolute path;
      a fresh venv at the same path is cleaner than copying one).
- [ ] **Leakage gate (Goal 4), two checks — both must pass, a failure is a STOP,
      never a prompt to gitignore an already-tracked file:**
      1. Per-entry manifest proof: every carry-over entry above is ignored AND
         untracked in the public repo —
         `for p in <each entry>; do git check-ignore -q "$p" || echo "NOT IGNORED: $p"; git ls-files --error-unmatch "$p" 2>/dev/null && echo "TRACKED: $p"; done`
         → no output.
      2. Tree proof: `git status --porcelain` prints **nothing** (also catches a
         carried private version silently overwriting a tracked public file).
- [ ] Restart the fleet:
      `for p in ~/Library/LaunchAgents/com.rebalance-os.*.plist; do launchctl bootstrap gui/$(id -u) "$p"; done`

**Gate:** `launchctl list | grep -c com.rebalance-os` = **14**, and no loaded job
shows a non-zero last-exit status:
`launchctl list | awk '$3 ~ /com.rebalance-os/ && $2 != 0 && $2 != "-"'` → empty.
Pulse server answering on 8767.

**Rollback (any time until Phase 4 deletion):** bootout jobs → swap the two folder
names back → bootstrap jobs. Total exposure ~5 minutes.

## Phase 3 — Verify (Day 1 → Day 7)

- [ ] Day 1: build the canonical 14-label manifest once —
      `ls ~/Library/LaunchAgents/com.rebalance-os.*.plist | xargs -n1 basename -s .plist > ~/gh291-labels.txt`
      (must contain 14 lines; this list, not 3-eyes' inventory, is the gate) — then
      kick each so every job runs at least once post-swap:
      `while read L; do launchctl kickstart -k "gui/$(id -u)/$L"; done < ~/gh291-labels.txt`
      Verify per label: exit status 0 in `launchctl list "$L"` and no fresh error in
      its log. Run `/3-eyes` as the second opinion, not the gate.
- [ ] Smoke the surfaces: rebalance MCP server tools respond; `ask_self` query
      works; dashboard renders; vault sync writes to Obsidian; health-check files
      no new path-related issues.
- [ ] Watch for path regressions using the checklist in
      `PROJECT/2-WORKING/COLLECTOR-PATH-AND-PORTABILITY-AUDIT.md` (prior art on
      hardcoded paths).
- [ ] Days 2–7: 3-eyes daily. Any collector error traced to the swap → fix forward
      or roll back. The 3-eyes inbox captures (`3EYES-*.md` in 1-INBOX) are the
      error ledger — buffer ends only when a full week shows no swap-caused entries.

**Gate:** 7 consecutive green days.

## Phase 4 — Retire the old repo (Day 7+)

> **Hard precondition — do not start Phase 4 without it:** the Phase 3 gate is
> complete — 7 consecutive dated green days recorded against the 14-label manifest
> (`~/gh291-labels.txt`), no swap-caused 3EYES captures. Until then, both remotes
> and both local folders stay untouched.

- [ ] README pointer on the old repo (via `gh api` / web — no local clone needed):
      prepend banner — *"⚠️ Archived. Development continues at
      [HiQS-Suite/rebalanceOS](https://github.com/HiQS-Suite/rebalanceOS). Issues
      and history here remain readable."* This is the final commit.
- [ ] Close this issue (#291) with a link to the completed checklist.
- [ ] Archive on GitHub: `gh repo archive Hypercart-Dev-Tools/rebalance-OS`
      (issues, commits, tags all remain readable; repo becomes read-only).
- [ ] Delete the local retired folder:
      `rm -rf ~/Documents/rebalance-OS.retired-2026-08`
      *(only after archive confirmed — this is the point of no local return; remote
      still holds full history via the `final-private-state` tag)*
- [ ] Sweep for stragglers: `~/Documents/GH Repos/` must contain no rebalanceOS
      folder; VS Code workspace / `.claude` additional-directories lists updated
      to drop the `GH Repos/rebalanceOS` path.

**Done when:** one folder (`~/Documents/rebalance-OS`, remote `HiQS-Suite/rebalanceOS`),
14 green jobs, old repo archived with pointer, retired folder gone.

## Risks

| Risk | Mitigation |
|---|---|
| Carried file leaks to public remote | Phase 2 leakage gate (empty porcelain) + Phase 1 gitignore audit |
| Collector breaks on missing private file | Explicit carry-over list; 7-day watch; retired folder intact for diffing |
| `.mcp.json` / `.claude` drift loses a server or hook | Diff-and-reconcile steps in Phases 1–2 |
| Venv path assumptions | Fresh `uv sync` at the canonical path, not a copied venv |
| Something only surfaces after deletion | Full history pushed + tagged remotely before anything local is destroyed |

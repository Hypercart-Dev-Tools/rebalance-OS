# Git Pulse — sync architecture findings & durable fix

**Author:** investigation pass (Claude), 2026-06-13 (rev. 3 — added P2/SIGNAL
intersection + dependency).
**Trigger:** recurring `launchd:pulse-sync` failures + wedged `~/git-pulse-sync`
clone + chronic "sleuth export stale / local clone stuck" doctor warning, on
**Noel's MBP 16" M1 Pro** (`noels-mbp-16-m1-pro`).
**Question posed:** is per-device namespacing the durable, portable, maintainable
fix (not a band-aid)?

> 🔴 **DEPENDENCY — do not start this refactor until [P2 — Team Calendar as a
> Signal (HiQS)](PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md) Phase 1 is merged to `main`.** P2 is
> Phase-1-complete but unmerged (`/code-review ultra` + merge pending) and touches
> the **same files** this refactor does (`sync_snapshot.py`, `index_ops.py`,
> `pulse.py`) plus the privacy-critical export seam. Starting now risks merge
> conflicts and muddies P2's privacy review. The `PULSE_PUSH=false` render-only
> stopgap holds the line meanwhile (and is privacy-safe — it doesn't push). See
> [P2 intersection and dependency](#p2-signal-intersection-and-dependency).

> **Rev. 2 correction:** the active rendered status page is **`README.md`**, not
> `live-pulse.md`. `live-pulse.md` is a **stale leftover** (last written 30h ago)
> from before the publisher switched its target to `README.md` (so it renders on
> the repo home). This changes the recommendation — see [The decision](#the-decision).

---

## TL;DR

- **Two different artifacts are easy to confuse:**
  1. **Per-device collector logs** — `pulse-<device_id>.md` (the `+1`/`+2`/
     `metadata refresh` commits). **Already per-device, already conflict-free.**
     Produced by the git-pulse collector. This is *not* the rendered page.
  2. **The rendered "Live Pulse" status page** — a **single shared file**
     produced by `publish_pulse`. **This** is the thing that conflicts when more
     than one machine writes it. Its live target is now **`README.md`**
     (`live-pulse.md` is a dead leftover).
- **Root cause of the breakage:** the rendered page is a single shared file on a
  rebased `main`. When >1 machine writes it, `pull --rebase` replays a commit
  that edits the *same path* → conflict → the clone wedges.
- **The system has already de-facto chosen "single designated publisher →
  `README.md`":** the always-on **Mac Studio** writes `README.md` hourly,
  conflict-free, *because it's the only writer.* **This laptop's only real bug is
  that it's a stray second publisher** still pointed at the dead `live-pulse.md`,
  pushing into the same churning clone.
- **So the durable choice is now a fork** (was previously framed as just
  "per-device"): **(A) embrace single-publisher → README** (recommended; ~90%
  already in place) vs **(B) per-device rendered pages** (`live-pulse-<id>.md`).
  Per-device is *correct and conflict-free* but only *necessary* if you want each
  machine's own view published; for a single glanceable repo-home page, (A) is
  simpler and already works.
- **The `PULSE_PUSH=false` render-only change we shipped is a band-aid** — keep it
  only as a stopgap; back it out once the fork is decided and implemented.

**Recommendation:** **(A) single-publisher → README**, with a nominated fallback
publisher, unless you specifically want per-machine views (then B). Either way,
stop this laptop from publishing to the dead `live-pulse.md`, and fix the Sleuth
clone refresh (see [Also-fix](#also-fix-related)). Details below.

---

## P2 (SIGNAL) intersection and dependency

Cross-ref: **[P2 — Team Calendar as a Signal (HiQS)](PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md)**.
Reading P2 changed the framing: `rebalance-git-pulse` is **not a vanity status
page** — it is a **privacy-gated, cross-device data bus** that P2 is built on.
Four ways P2 affects this refactor:

1. **Privacy is a hard constraint now (P2 decision #3).** P2 hit a real leak —
   teammate calendar rows were pushed to `rebalance-git-pulse` — fixed with a
   **default-deny export filter** (`WHERE calendar_id='primary'` in
   `export_calendar_snapshot`) + reader scoping. The repo is **private**
   (verified). The rendered page already filters to operator-only (`c3a2bb7`); any
   change here must preserve that. **This is a vote *for* option A:** a single
   publisher = **one place to audit** for a privacy regression; N publishers = N
   leak sites.

2. **The `device_id` reconciliation is NOT trivial — it renames P2's exports.**
   P2 writes per-device sync snapshots to `sync/{calendar,email}/<device_id>.json`
   using `get_device_id()`, which currently emits the `-local` slug — confirmed on
   disk: `noels-mac-studio-local.json`, `noels-macbook-pro-14-local.json`. Fixing
   `get_device_id()` (strip `.local`) would **rename those export files** → a
   coordinated migration, not a one-liner. This also makes **option B** (per-device
   markdown, which keys off device_id) more entangled. Another reason to prefer A.

3. **The git repo is load-bearing for P2 → "drop the git transport" is retracted.**
   P2's Arm A reads Sleuth reminders from the **published git-pulse file**
   (`pulse._query_day_activity()` → the `sync/sleuth` export), and P2's roadmap
   plans to **mine the `rebalance-git-pulse` commit history as a dropped-ball label
   oracle** (diffing snapshots over time). So the radical "render-on-read, drop the
   markdown→git flow" option from earlier is **off the table** for this system.
   The over-engineering critique still holds *only* for the multi-writer contention
   (removable); the git-as-bus itself is justified by P2. Also: avoid drastically
   changing commit cadence/structure that P2 plans to diff.

4. **Sequencing — wait for the P2 Phase 1 merge.** P2 is Phase-1-complete but
   **unmerged** (`/code-review ultra` + merge-to-`main` pending) and touches the
   **same three files** this refactor does (`sync_snapshot.py`, `index_ops.py`,
   `pulse.py`). → **This refactor is BLOCKED until P2 Phase 1 lands on `main`** (see
   the dependency callout up top). Keep `PULSE_PUSH=false` as the stopgap — it's
   privacy-safe (no push, no leak), which is ideal during P2's sensitive window.

**One carve-out that's safe to do now** (low-risk, privacy-neutral, *and*
P2-relevant): the **Sleuth-source freshness fix**. Render-only means this laptop's
`~/git-pulse-sync` never refreshes → its `sync/sleuth` export goes stale → **P2's
Arm A reads stale Sleuth data on this box**. A `git fetch && git reset --hard
origin/main` read-refresh fixes it without touching the publish/export path or
P2's files. Everything else waits for the merge.

**Net:** P2 doesn't change the *direction* (A — single publisher → README; remove
multi-writer contention) — it **reinforces A** (privacy audit surface + device_id
coupling), **retracts the "drop git" option**, and **gates the timing** behind the
P2 Phase 1 merge.

---

## System map (as it actually runs today)

Two **independent** systems write to the **same** private repo
(`Hypercart-Dev-Tools/rebalance-git-pulse`, branch `main`), via **two separate
local clones**:

| | **publish_pulse** (rebalance native) | **git-pulse collector** (legacy/experimental) |
|---|---|---|
| Launchd job | `com.rebalance-os.pulse-sync` → `scripts/pulse_sync.sh`, hourly | `com.user.git-pulse` → `~/bin/git-pulse` (559-line bash) |
| Local clone | `~/git-pulse-sync` (= `pulse_target_path`) | `~/.config/git-pulse/repo` |
| Writes | the **rendered status page** → `pulse_filename` (active publisher: **`README.md`**; this laptop: the dead **`live-pulse.md`**) | **`pulse-<device_id>.md`** (append-only commit log) + `devices/<device_id>.yaml` |
| Namespacing | ❌ **single shared file** per "the rendered page" | ✅ **per-device file** — each device owns its path |
| Sync strategy | write → commit → `push`; on reject → `pull --rebase` → push (bounded FSM) | `pull --rebase` → write → commit → `push`; one retry on race |
| Conflicts? | **Yes** when >1 machine writes the same page file | **No** (each writer owns its file) |
| Also feeds | `~/git-pulse-sync/sync/sleuth/reminders-neochrome.json` = the **Sleuth file-source** this device reads | — |

The collector's per-device design is **conflict-free and already proven here**.
The rendered-page design conflicts only when contended — and today it's *only*
contended because this laptop is a second writer.

### The rendered page: who writes what (forensic evidence)

```
# Active rendered page = README.md (renders on the repo home):
README.md      last commit: 18 min ago  "pulse: 2026-06-13 16:00 EDT update"   (Mac Studio / noelsaw1)
               last 6 "pulse: …" commits ALL touch README.md, hourly, one writer

# Dead leftover:
live-pulse.md  last commit: 30 hours ago "pulse: 2026-06-12 07:00 PDT update"
               this laptop (MBP 16) is still configured pulse_filename = live-pulse.md
```

- Active publisher commits as **`noelsaw1 <noel@neochro.me>`** (the always-on
  Mac Studio; MacBook Pro 14" may share the identity). **This laptop** commits as
  `Noel Saw <…@users.noreply.github.com>`.
- **The "EDT" in subjects is a tz mislabel, not a separate server.** `1a6ef4d`
  says *"14:00 EDT"* but its real commit date is `11:00:30 -0700` (PDT). The label
  is `strftime('… %Z')` from each machine's `pulse_timezone` — i.e. configs
  differ across devices. No CI: the repo has no `.github/workflows/`, so the
  publisher is a *machine* (single point of failure if it's truly the only one).

### Consumers of the rendered page

- **No code reads it** anywhere in `rebalance-OS` (only `pulse.py` writes it).
- The **web dashboard** (`pulse_web.py` → `web/pulse.html`) renders **directly
  from the local SQLite DB**, not from the markdown. Separate, local, no-git.
- So the rendered page is **purely a human-glanceable artifact** — and it's the
  repo's **README landing page**. That strongly suggests *one canonical page* is
  the intent (which is what the Mac Studio→README setup already delivers).

---

## Why the conflict is structural (mechanism)

`publish_pulse` → `_commit_and_push_if_changed` (`src/rebalance/ingest/pulse.py`):

1. write `file_rel`, `git add`, `commit`, `push`.
2. on `! [rejected] … (fetch first)` → bounded `RepairFSM`, preferred action
   `pull_rebase` (`pull --rebase` then push); fallback `abort_rebase`.
3. **`reset_hard` is deliberately excluded** (see in-code comment) — it would
   discard the local commit and report a false "pushed". A designed guard against
   silent data loss.

- **Two machines writing the *same* page file** → rebase replays one onto the
  other's edit of that path → `UU` conflict → FSM gives up `dead`, clone wedged.
  (Exactly what we found: detached HEAD, `UU live-pulse.md`,
  `UU sync/sleuth/reminders-neochrome.json`.)
- **Each machine writing its *own* file** (collector pattern, or per-device
  option B) → rebase replays a commit touching a path no one else owns → clean →
  push succeeds on first retry. The repair code is already correct; it just needs
  non-overlapping files.

---

## The decision

Per-device generation **already exists for the collector logs**. The open
question is only about **the rendered status page**:

### (A) Embrace single-publisher → `README.md`  ·  *recommended*

- **Mac Studio** (always-on) remains the sole rendered-page publisher → `README.md`.
- **Laptops do NOT publish the rendered page** (they keep their per-device
  collector logs). Delete/retire the dead `live-pulse.md`.
- **Pros:** one canonical glance page = the repo home; ~90% already working; no
  N-redundant files; simplest. Matches "README is the landing page" intent.
- **Cons:** only the always-on machine's view is published; if it's offline the
  README goes stale.
- **Mitigation:** nominate a **fallback publisher** (a laptop that publishes only
  if the primary is stale), or move publishing to a cloud/CI cron later for true
  resilience.

### (B) Per-device rendered pages  ·  `live-pulse-<device_id>.md`

- Each device publishes its own `live-pulse-<device_id>.md`; conflict-free;
  `push=True` restored. `README.md` becomes either an aggregator output or one
  device's page.
- **Pros:** every machine's own DB-derived view is visible; no single point of
  failure.
- **Cons:** N status pages; must define README's role (aggregator); requires the
  `device_id` reconciliation below; only worth it if per-machine views matter.

> **Trade:** A optimizes for *one canonical page* (what a README implies). B
> optimizes for *per-machine visibility*. The earlier draft over-recommended B
> before we knew the publisher had already consolidated onto README.

### Wrinkle (needed for B; harmless for A): `device_id` derivation disagrees

```
Python   get_device_id()  (socket.gethostname → slug):   noels-mbp-16-m1-pro-local
Collector canonical_device_id_from_hostname (bash):       noels-mbp-16-m1-pro
```

`get_device_id()` (`sync_snapshot.py:53`) slugifies `socket.gethostname()`, which
returns the `.local` form on macOS (trailing `-local`); the collector strips it.
If we ever namespace per-device (B) or otherwise key off device_id, **reconcile
these** (strip `.local`; ideally one shared derivation) so `pulse-…md`,
`devices/….yaml`, `sync/*/….json`, and any `live-pulse-….md` line up.

---

## Also-fix (related, surfaced during investigation)

- **`~/git-pulse-sync` has no scheduled refresher.** Only the manual
  `setup_sleuth_file_source.sh` runs `git -C ~/git-pulse-sync pull --rebase`;
  `daily_sync.sh` does **not**. Its only de-facto refresh was `publish_pulse`'s
  push-time `pull --rebase`. **Under option A, laptops don't push at all**, so
  their clone never refreshes → the **Sleuth source goes stale** (this is the
  recurring doctor warning). **Required under A:** add an explicit
  **`git fetch && git reset --hard origin/main`** mirror refresh for the Sleuth
  consumer role (a read-mirror that hard-resets can never wedge). Under B the
  push-time pull keeps it fresh, but the explicit mirror is still cleaner.
- **`pulse_timezone` inconsistent across devices** (EDT vs PDT labels). Normalize
  it (or render the label in a fixed tz) for consistent display.
- **Back out the band-aid:** remove `PULSE_PUSH=false` from this laptop's
  `~/Library/LaunchAgents/com.rebalance-os.pulse-sync.plist` once the fork is
  implemented. The `PULSE_PUSH` env hook in `scripts/pulse_sync.sh` (commit
  `72ebd7e`) is fine to keep as an escape hatch.

---

## Immediate fix for this laptop (either A or B)

Right now this laptop renders to the **dead `live-pulse.md`**. Regardless of the
fork:

- **If A:** stop this laptop publishing the rendered page (disable the
  rendered-pulse push here — render-only or unload the job) **and** add the
  read-mirror refresh so its Sleuth source stays fresh. Delete `live-pulse.md`.
- **If B:** set `pulse_filename = live-pulse-noels-mbp-16-m1-pro.md` (after the
  device_id reconciliation) and restore `push=True`.

---

## Recommended implementation order

> ⛔ **Gate:** steps below are BLOCKED until **[P2](PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md)
> Phase 1 is merged to `main`** (shared files + privacy review). The **only** item
> safe to do before the merge is the Sleuth-source read-refresh (carve-out in
> [P2 intersection and dependency](#p2-signal-intersection-and-dependency)).

**If A (recommended):**
1. Confirm Mac Studio is the intended sole publisher (and pick a fallback).
2. Stop rendered-page publishing on laptops; add `fetch + reset --hard` Sleuth
   mirror refresh on every device that consumes the Sleuth file-source.
3. Delete the dead `live-pulse.md`; normalize `pulse_timezone`.
4. (Later, optional) move the single publish to a cloud/CI cron for resilience.

**If B:**
1. Reconcile `get_device_id()` to strip `.local` (add a test).
2. Default `publish_pulse` filename to `live-pulse-<device_id>.md` when unset.
3. Restore `push=True` everywhere; remove the `PULSE_PUSH=false` plist env.
4. Decide README's role (aggregator vs retire); optional CI aggregator.

---

## Open decisions for the operator

- **A vs B** — one canonical README page (A) or per-machine pages (B)?
- **If A:** which machine is primary, and is there a fallback? Cloud/CI later?
- **If B:** README = aggregator output, or retire it?
- **device_id source of truth** (needed for B): one shared derivation, or just
  make Python match the collector?

## Evidence appendix (commands run)

- `git log origin/main --grep "^pulse: " --stat` → last 6 rendered-page commits
  **all touch `README.md`**, hourly, single writer (`noelsaw1`).
- `git log origin/main -1 -- README.md` → 18 min ago; `-- live-pulse.md` → 30h ago
  (dead leftover). Subject tz label ≠ commit tz (`-0700`).
- `get_pulse_config()` on MBP 16 → `pulse_filename = live-pulse.md` (the default).
- `ls ~/git-pulse-sync/.github/workflows` → none (publisher is a machine, not CI).
- `pulse.py:1042-1062` → filename from `pulse_filename`; commit msg uses `%Z`.
- `pulse.py:889-998` → push→`pull_rebase`/`abort_rebase` FSM; `reset_hard`
  excluded by design.
- `~/bin/git-pulse:438,540-551` → collector does `pull --rebase` → push, per-file,
  one retry; the conflict-free precedent.
- `get_device_id()` → `noels-mbp-16-m1-pro-local`; collector → `noels-mbp-16-m1-pro`.
- `grep live-pulse src/ scripts/` → no code consumer; `pulse_web.py` renders from
  SQLite, not the markdown.
- `daily_sync.sh` → no `~/git-pulse-sync` refresh; only
  `setup_sleuth_file_source.sh` pulls it.

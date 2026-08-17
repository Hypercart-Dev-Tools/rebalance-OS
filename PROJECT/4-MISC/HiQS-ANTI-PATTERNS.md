> **Superseded 2026-08-03 — kept as provenance.** Folded into
> [HIQS-PROJECT.md](../2-WORKING/HIQS-PROJECT.md): the six-cluster taxonomy is now
> "The taxonomy — six clusters, one meta-pattern" at the head of that doc's Lessons
> section, and the seven incidents its L1–L15 didn't already cover became L16–L22
> (plus two new plugin rules, §5.7 timeout and §5.8 watermark). Every version
> citation below was re-verified against `CHANGELOG.md` at fold-in time and holds.
> Two corrections were applied during the fold, not carried forward from here:
> cluster C's "124 email rows fed nothing" is the pre-correction figure (0.57.0
> records that only 5 of the 124 carry content — the email arm was wired but
> starved), and cluster C's two-server row is **still live in the incumbent**, not
> history. The plan doc is canonical; edit that, not this.

Grounded in the CHANGELOG, the Rebalance mistakes cluster into six recurring patterns. The dominant one — the meta-mistake that caused the most cumulative damage — is **silent degradation: the system failing while reporting itself healthy.** Everything else is second-order. Here's the full ledger.

## A. Silent failure / silent degradation (the #1 pattern)

- **Empty rows accepted at the write boundary** (0.57.0) — email push-ingest defaulted every missing field to `""`. A caller with different key names landed **119 of 124 rows with no sender, subject, or timestamp**; they sat invisible for **three weeks**. The changelog names the lesson: *"freshness only checks whether rows exist, not whether they mean anything."*
- **Optional dep never installed = silent feature loss** (0.32.0) — the `embeddings` extra wasn't in the venv, so `semantic_documents` never embedded and `ask()`/`semantic_query` quietly degraded to lexical-only. Surfaced as a per-scope error envelope, not a crash. Wrong loader (`mlx-lm` vs `mlx-embeddings`) produces a *"fast, valid-but-empty index."*
- **Retired model silently forcing fallback** (0.49.0) — `gemini-2.0-flash` started 404'ing, silently pushing every synthesis onto local Qwen, surfacing as `<rank>. <title>` placeholder titles.
- **TCC-protected paths failing every machine invisibly** (0.18.2) — sync repos under `~/Documents` made launchd exit 128 on every fire, on every machine, for hours. The Phase 0 spike had flagged this risk only for the *future* SQLite layer, not the live collector.
- **Config whitelist silently dropping keys** (0.26.0) — `get_pulse_config()` returned an explicit-keys dict that no-op'd the first filter iteration.
- **Duplicate migration number silently skipped** (0.32.0, Figma) — a second `0002` would be skipped on a stamped DB and the table never created.

## B. Trusting the wrong signal as truth

- **Health checks misread, not collectors broken** (0.60.0, 0.67.0) — months of *"the collectors are unstable"* traced to the health checks; **6 of 6 investigated findings were misreads, zero were real defects.** Misreads included: asserting a stale `launchctl` exit code as current health, reading only the status column while ignoring a live PID (a running server reported FAILING), and a sandboxed probe returning empty → *"not-loaded"* → false all-clear.
- **Green tile over an unreadable fleet** (0.67.0) — Focus 5 keyed on `failing == 0`, so an *unavailable* probe rendered *"all jobs OK"* while nothing was known.
- **Memory measured with the wrong ruler** (0.68.0, GH-172) — the watchdog read RSS, which on macOS excludes compressed/swapped pages. Two jobs grew to **~46 GB while reporting ~30 MB**; the machine OOM'd and no ceiling could ever trip.
- **Docs' own `status:` field trusted over git** (0.67.1 → 0.67.2) — one correction pass replaced a wrong claim with a second wrong claim because it trusted prose for the merge half. *"A doc's own status field is not evidence."*
- **`updated_at` used as a progress signal** (0.28.3) — it's bumped by label/assignee edits, not real progress.

## C. Drift from duplication

- **Two synthesis surfaces sharing no code** (0.56.1) — broad synthesis saw no Slack/email/Figma; the ranking engine saw no email/Figma; email and design comments reached **no synthesis at all**. *"The product's core claim was only about two-thirds true."* 124 email rows fed nothing.
- **`pulse_server.py` hand-redeclaring a subset of `web.py` routes** (ARCHITECTURE, 0.50.1) — routes added to one were invisible on the other; a KeepAlive daemon served a stale route table until kickstarted. **Bit the Focus 5 app twice.**
- **Hand-written per-source dispatch in the ranker** (0.56.1) — called out as *"a standing violation of 'extend by addition, not by editing a dispatch chain.'"*
- **Five independent UTC-display formatters** (0.59.0) and **five sync scripts with one developer's home directory baked in** (0.29.0).

## D. Environment/resource assumptions

- **No memory guard until the machine died** (0.68.0 → GH-172 guard in README) — single-instance lock + 35% RAM ceiling were retrofits.
- **No HTTP timeout + no `busy_timeout`** (0.25.0) — a stalled `urlopen` after sleep/wake held the SQLite writer; *"database is locked"* cascaded through daily sync, every hourly vault sync, and TUI refresh until a manual kill.
- **Reasoning model eating its own budget** (0.49.1) — gemini-2.5-flash spent ~1,962 of 2,048 tokens on hidden reasoning, emitting 2 of 15 items.
- **Bash 3.2 incompatibility** (0.63.0) — empty-array expansion under `set -u` failed every normal run on macOS `/bin/bash`.

## E. Scope and complexity accretion

- **Net-LOC acceptance criterion missed** (0.57.0) — the HiQS consolidation was budgeted at ≤0 net lines, shipped **+519**, and was recorded as a failed criterion.
- **Governance machinery eating releases** — PDDA hygiene sweeps (0.67.1), `audit_modules`, a 10-job launchd fleet requiring a policy table, conformance tests, and per-job installers (SCHEDULER.md).

## F. Self-reference / feedback loops

- **Generated output ranking itself** (0.49.1) — `Dashboards/What To Do Next.md` was ingested as a "recent vault edit" and ranked in its own list every refresh.
- **`last-run` advancing on a failed scan** (0.18.2) — commits authored during the broken window became invisible to later runs.

**The one takeaway:** nearly every severe incident (empty email, inert embeddings, retired model, 46 GB jobs, green-but-unknown fleet) is the same bug wearing different clothes — *a degraded or broken state that reported itself as healthy.* The durable fix is structural, not per-case: reject unusable records at the write boundary, make `unknown` a first-class state distinct from `ok`, assert row *quality* not row *count*, and never let one surface compute its own truth.
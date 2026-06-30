---
title: "Gemini-reviewed 'What to do next' → fixed vault file"
status: "Queued (intake — not started). Two deliverables captured 2026-06-29."
created: 2026-06-29
updated: 2026-06-29
owner: Noel
goal: >
  Make the daily "what to do next" signal actually Gemini-synthesized (review + rewrite
  the raw ranked candidates with a paid Gemini key), and publish the resulting markdown to
  one fixed file inside the Obsidian vault so it is the calm daily operator surface.
roadmap_exempt: false
---

# Gemini-reviewed "What to do next" → fixed vault file

> **Intake doc — queued, not started.** Captured per Noel's request (2026-06-29) to create two
> queued tasks. This is a follow-on to the shipped next-action engine; it does **not** restart it.

## Cross-links (don't rebuild)

- **Owning engine:** [P2-TEAM-CALENDAR-SIGNAL.md](PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md)
  — the shared `rank_next_actions` core ([next_actions.py](src/rebalance/ingest/next_actions.py)),
  the `/whats-next` route ([web.py](src/rebalance/web.py)), the `ranked_next_actions` precompute
  cache (migration 0006), and the Gemini→Qwen `_synthesize_with_fallback` adapter (decision #5)
  already exist. Both deliverables below extend that engine — they are not a competing plan.
- **Vault-as-dashboard contract:** [P1-SIGNAL.md](PROJECT/1-INBOX/P1-SIGNAL.md) — "generated markdown
  becomes the dashboard; human notes stay human-owned"; single-writer contract for generated files.
- **Gemini key resolver:** `get_gemini_api_key()` ([config.py](src/rebalance/ingest/config.py)) —
  current chain is Python-SDK → `GEMINI_API_KEY`/`GOOGLE_API_KEY` env → `gcloud secrets versions access`.

## Why now (verified state, 2026-06-29)

The "what to do next" pipeline **is** synthesizing daily (cache: 15 ranked actions computed
06:44 PDT), but it ran on the **local `Qwen/Qwen3-0.6B` fallback, not Gemini** — and the output is
degraded: the `title` field comes back as the literal template placeholder `<rank>. <title>` while
`person`/`source`/`evidence`/`why` are populated. So the synthesis quality the design promised
(decision #5, Gemini) is not actually landing in the runtime. These two tasks close that gap and
give the result a stable home in the vault.

---

## Deliverable 1 — Gemini reviews + rewrites the raw "what to do next" synthesis

Take the raw ranked candidates (the deterministic `rank_next_actions` output / current "what to do
today") and have **Gemini** review them and re-write the synthesis into the final operator-facing
list — using the paid key supplied below as a new key source.

- [ ] **Key source:** read the Gemini key from the plaintext file `/Users/noelsaw/secrets/gemini-paid-key.txt`.
      Wire it into the existing `get_gemini_api_key()` chain (e.g. as a new file-path resolver) so the
      whole engine — `/whats-next`, `ask(team=True)`, the precompute hook — benefits, not a one-off.
      Prefer extending the resolver over hardcoding a read in one call site (DRY / decision #5).
- [ ] **Behavior:** Gemini reviews the raw ranked candidates and rewrites them into the final synthesis
      (clean titles, deduped, person-attributed, ordered). The existing deterministic ranked fallback
      MUST remain the guard so a bad/empty Gemini parse never overwrites a good deterministic list
      (this was a prior HIGH finding in P2 — do not regress it).
- [ ] **Acceptance:** `model_used` in the `ranked_next_actions` cache reads a **Gemini** model (not
      `Qwen/Qwen3-0.6B`), and titles are real text — **no `<rank>. <title>` placeholder** survives.

### Open considerations (decide at execution)
- **Security:** `/Users/noelsaw/secrets/gemini-paid-key.txt` is currently `0644` (world-readable) and
  sits under a synced `Documents`-adjacent path. A plaintext key file is a weaker source than the
  existing GSM/keyring path. Consider `chmod 600`, confirm it is gitignored / never committed, and
  decide whether the file is a convenience override or the primary source. **Never log the key.**
- **Paid key cost:** this is the *paid* key (per the filename) — the daily precompute + every
  `?refresh` now spends real tokens. Confirm the run cadence is acceptable (daily precompute is fine;
  guard against a hot-loop on the route).

## Deliverable 2 — Publish that markdown to a fixed vault file

Render the Gemini-rewritten "what to do next" list to **one fixed markdown file** in the Obsidian
vault so it is the calm daily surface (per P1-SIGNAL).

- [ ] **Fixed output path (decided 2026-06-29):**
      `/Users/noelsaw/Documents/Noel Saw/Dashboards/What To Do Next.md`
      (vault root from `temp/rbos.config` `vault_path`; overwrite-in-place, not a dated note).
- [ ] **Writer:** generate it from the **same** `rank_next_actions` output as the route/cache — a new
      render-to-vault sink, not a re-implementation of ranking (DRY parity gate from P2).
- [ ] **Single-writer contract (P1-SIGNAL):** the file is fully generated/owned by rebalance — make
      that explicit (header banner + "generated, do not edit by hand"); do not interleave with
      human-authored notes.
- [ ] **Cadence:** write on the existing daily precompute hook (the 6:30 AM `daily-sync`) and/or on
      `?refresh`, reusing the cache so the vault file matches `/whats-next`.
- [ ] **Privacy:** the list can include person-attributed teammate items — this writes to the **local**
      vault only (not the pushed `git-pulse-sync` repo), so the P2 export-filter invariant is not
      crossed. Confirm no teammate `person` data leaks into any pushed artifact via this path.

---

## Definition of done
- `/whats-next` and the `ranked_next_actions` cache are synthesized by **Gemini** (paid key from the
  file), placeholder titles gone, deterministic fallback intact.
- `Dashboards/What To Do Next.md` exists in the vault, regenerated daily, content-matching the cache.
- `pytest tests/` green and `rebalance doctor` clean before claiming done (ROUTER gate).

## Suggested next step
Promote to `PROJECT/2-WORKING/` (likely as a phase of the SIGNAL-GENERATION track) when work starts,
add the `## Status` table + `<!-- phase-qa -->` checklist, and add a one-line ROADMAP pointer.

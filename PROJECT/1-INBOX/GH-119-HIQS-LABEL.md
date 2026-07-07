---
title: "HiQS marketing label — brand the computed work signal as High Quality Signals"
owner: noel@neochro.me
gh_issue: 119
source: "https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/119"
status: "Proposed (1-INBOX — not yet active). Captured 2026-07-06; queued into MARATHON-2026-07-07. Marketing/label change only — no behavior, package, table, or CLI rename."
created: 2026-07-06
updated: 2026-07-06
doc_type: project
goal: >
  Adopt the HiQS ("High Quality Signals") brand for rebalance-OS's computed / ranked work signal —
  mostly in code comments, plus the README and one or two user-facing surfaces — so the product name
  matches https://beta.hiqs.ai, where this repo is the "Rebalance (prioritize)" component of HiQS
  (Sleuth = capture, Forge = coordinate).
non_goals: >
  Not a rename of packages, modules, DB tables, MCP tools, or the `rebalance ...` CLI. No behavior or
  ranking change. Not a full rebrand of the repo — this is a labeling pass on the *computed signal*,
  applied where a user or reader actually sees it.
related:
  - PROJECT/2-WORKING/GH-102-XYZ-REBALANCE-INTEGRATION.md
  - "https://beta.hiqs.ai"
effort: 2
complexity: 1
risk: 1
phases: 3
---

## Status

| What was just completed | What's next |
|---|---|
| **Captured 2026-07-06** from issue #119. Scope agreed: HiQS = "High Quality Signals"; rebalance-OS is the HiQS **Rebalance (prioritize)** product; tagline *"Turn workplace noise into high-quality signal."* Mostly code comments + README + 1–2 user-facing surfaces. | **Phase 0 (label-lock decision spike)** — lock the canonical wording and the exact surface inventory before editing, so the brand lands consistently. Then Phase 1 (comments) ‖ Phase 2 (user-facing). Queued into [MARATHON-2026-07-07.md](../2-WORKING/MARATHON-2026-07-07.md). |

---

## Table of contents

- [Thesis](#thesis)
- [Phase 0 — Lock the label + surface inventory (decision spike)](#phase-0--lock-the-label--surface-inventory-decision-spike)
- [Phase 1 — Code comments (non-user-facing)](#phase-1--code-comments-non-user-facing)
- [Phase 2 — README + 1–2 user-facing surfaces](#phase-2--readme--12-user-facing-surfaces)
- [Anti-goals](#anti-goals)

---

## Thesis

This is a **label**, not a refactor. The computed/ranked work signal already exists and works; HiQS is
the name we put on it where humans read it. Highest-value, lowest-risk: get the wording consistent
once (Phase 0), sprinkle it in the code comments that explain the signal (Phase 1), and surface it on
the few screens/docs a user actually sees (Phase 2). Zero behavior change; every edit is trivially
reversible.

Ponytail note: this could be one commit. It is phased only so the *user-facing* wording (Phase 2) is
locked and consistent before it ships, not scattered ad-hoc across files.

---

## Phase 0 — Lock the label + surface inventory (decision spike)

**Discovery — findings written back here before the QA gate passes. No code edited in Phase 0.**

**Observable checklist:**

- [ ] **Lock canonical wording.** Confirm the exact string(s): "HiQS", expansion "High Quality
      Signals", tagline "Turn workplace noise into high-quality signal.", and the one-liner placing
      rebalance-OS as the HiQS **Rebalance (prioritize)** component. Record them verbatim here.
- [ ] **Inventory the code-comment sites (Phase 1 targets).** Grep the ranking/signal code
      (`src/rebalance/ingest/next_actions.py`, `src/rebalance/querier.py`, the deep-work signal from
      GH-116) and list the specific docstrings/comments to touch. No behavior lines.
- [ ] **Pick the 1–2 user-facing surfaces (Phase 2 targets).** Choose from: `README.md` (required),
      and one of — DASHBOARD/pulse title, `rebalance doctor` banner, or the web header. Record the pick.
- [ ] **Confirm the non-goals hold.** No package/module/table/MCP-tool/CLI rename appears on either list.

**Exit criteria:** wording locked verbatim, Phase 1 comment sites and Phase 2 surfaces both enumerated
here, non-goals confirmed. If the inventory turns up a rename that changes an interface, stop and
escalate — that is out of scope for a label pass.

### Phase 0 — QA checklist

- [ ] Wording + surface inventory written back into this doc.
- [ ] No code changed (decision only).
- [ ] Non-goals confirmed: nothing on the list renames a package/table/tool/CLI.
- [ ] `utils/pdda/pdda.sh run` clean.

---

## Phase 1 — Code comments (non-user-facing)

**Observable checklist:**

- [ ] Add HiQS framing to the docstrings/comments at the Phase-0-listed signal sites (what the ranked
      signal *is*, in HiQS terms) — comments only, no logic touched.
- [ ] Grep confirms no non-comment line changed in the touched files (diff is comments/docstrings only).

### Phase 1 — QA checklist

- [ ] **Litmus:** `git diff` on Phase 1 files shows only comment/docstring lines.
- [ ] **No behavior change:** `pytest tests/` green (unchanged), `rebalance doctor` clean.
- [ ] **DRY:** wording matches the Phase 0 canonical strings exactly — no drift.
- [ ] `utils/pdda/pdda.sh run` clean.

---

## Phase 2 — README + 1–2 user-facing surfaces

**Observable checklist:**

- [ ] **README.md** introduces HiQS (High Quality Signals) as the name of the computed signal and notes
      rebalance-OS is the HiQS **Rebalance** component (link https://beta.hiqs.ai).
- [ ] The 1–2 chosen user-facing surfaces (Phase 0 pick) reference HiQS in their visible label/header.
- [ ] Wording is byte-identical to the Phase 0 canonical strings across every surface.

### Phase 2 — QA checklist

- [ ] **Litmus (a user sees it):** the HiQS name appears on README + the chosen surface(s); screenshot/
      log recorded.
- [ ] **Consistency:** the same wording on every surface (no "HiQs"/"HIQS"/"Hi-QS" variants).
- [ ] **No behavior change:** `pytest tests/` green; `rebalance doctor` clean.
- [ ] `utils/pdda/pdda.sh run` clean. Lands via self-mergeable PR (main is protected).

---

## Anti-goals

- **Not a repo rename.** Packages, modules, DB tables, MCP tools, and the `rebalance ...` CLI keep their
  names. HiQS is the *signal's* brand, applied where it's read — not a global find-replace.
- **Not a behavior change.** No ranking, scoring, or output changes. If a diff line isn't a comment or a
  visible label, it doesn't belong in this effort.
- **Not a scattergun.** Phase 0 locks the wording and the surface list first; Phases 1–2 only fill it in.

# DASHBOARD.md - Code Quality Compliance
**Last Updated:** 2026-06-10
**Last Audited:** 2026-06-10 — collector-path audit. Rows 3 & 8 and the semantic single-writer contract are now **machine-enforced** in `tests/test_collector_contracts.py` (not a manual tick). See `PROJECT/2-WORKING/COLLECTOR-PATH-AND-PORTABILITY-AUDIT.md`.

---

## How to Use

Each row is a specific code smell mapped to a principle. Mark `[x]` only when you've verified the violation is absent (or deliberately accepted). Reset to `[ ]` each audit cycle.

---

## Compliance Matrix

| # | Principle | Smell | Clear |
|---|-----------|-------|:-----:|
| 1 | YAGNI | `repos_json` / `project_registry` still acting as an admission control gate anywhere in the display layer | [ ] |
| 2 | YAGNI | Priority tiers, onboarding flow, or calendar classifier aliases load-bearing for anything a direct `github_activity` query wouldn't cover | [ ] |
| 3 | YAGNI | `github_commits` / `github_items` tables justifying their existence vs. `github_activity` doing the same job | [x] |
| 4 | DRY | `fetch_org_activity` (scripts/) and `get_all_repo_activity_by_org` (src/) are near-identical — still two copies | [ ] |
| 5 | DRY | Two files named `dashboard.py` with overlapping data-fetch logic | [ ] |
| 6 | DRY | Any SQL query written twice across the display layer for the same data shape | [ ] |
| 7 | SOLID (SRP) | A display/render function also doing data filtering or config resolution | [ ] |
| 8 | SOLID (OCP) | Adding a new ingest source requires touching the display layer (not just adding a sync script) | [ ] |

---

## Notes

_Add findings here during audit. Link to the commit or file:line that resolves each._

**2026-06-10 — collector-path audit → executable contracts.** The mechanizable rows now live as guards in `tests/test_collector_contracts.py` instead of as a checklist nobody runs:

- **Row 3 (RESOLVED, green):** `github_activity` and `github_commits` are *not* redundant — `github_activity` is a per-`(login, repo, scan_date)` scan snapshot; `github_commits` is granular per-commit (`committed_at`). Both kept. → `test_github_activity_and_commits_are_distinct_not_redundant`.
- **Row 8 (guarded, `xfail` until Phase 2):** user-facing CLI/MCP surfaces must not import leaf ingest fns directly → `test_user_surfaces_do_not_import_leaf_ingest_functions`.
- **Semantic single-writer (Decision B, `xfail` until Phase 3):** only the `semantic` stage writes the semantic tables → `test_semantic_projection_is_single_writer`.
- **`all` = raw sources only (Decision A, `xfail` until Phase 1):** → `test_all_expands_to_raw_sources_only`.

Rows 1, 2, 4–7 remain manual smells (not cleanly mechanizable yet); revisit when the Phase 1–2 write-path consolidation lands (rows 4/5/8 should collapse out as duplication is removed).

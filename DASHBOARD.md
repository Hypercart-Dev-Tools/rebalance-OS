# DASHBOARD.md - Code Quality Compliance
**Last Updated:** 2026-05-31
**Last Audited:** _not yet audited_

---

## How to Use

Each row is a specific code smell mapped to a principle. Mark `[x]` only when you've verified the violation is absent (or deliberately accepted). Reset to `[ ]` each audit cycle.

---

## Compliance Matrix

| # | Principle | Smell | Clear |
|---|-----------|-------|:-----:|
| 1 | YAGNI | `repos_json` / `project_registry` still acting as an admission control gate anywhere in the display layer | [ ] |
| 2 | YAGNI | Priority tiers, onboarding flow, or calendar classifier aliases load-bearing for anything a direct `github_activity` query wouldn't cover | [ ] |
| 3 | YAGNI | `github_commits` / `github_items` tables justifying their existence vs. `github_activity` doing the same job | [ ] |
| 4 | DRY | `fetch_org_activity` (scripts/) and `get_all_repo_activity_by_org` (src/) are near-identical — still two copies | [ ] |
| 5 | DRY | Two files named `dashboard.py` with overlapping data-fetch logic | [ ] |
| 6 | DRY | Any SQL query written twice across the display layer for the same data shape | [ ] |
| 7 | SOLID (SRP) | A display/render function also doing data filtering or config resolution | [ ] |
| 8 | SOLID (OCP) | Adding a new ingest source requires touching the display layer (not just adding a sync script) | [ ] |

---

## Notes

_Add findings here during audit. Link to the commit or file:line that resolves each._

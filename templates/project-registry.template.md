# Project Registry

Canonical project list for rebalance ingest and scoring.

Sections:
- `active_projects`: currently tracked and scored
- `most_likely_active_projects`: GitHub activity last 14 days
- `semi_active_projects`: GitHub activity 15-30 days ago
- `dormant_projects`: GitHub activity 31+ days ago
- `potential_projects`: candidates with no activity signals (vault-only discoveries)
- `archived_projects`: historical records

Monitoring external repos: add a project with `external: true` and list the
third-party repos under `repos`. Those repos enter the watched set, get
artifact-synced like any repo, and get a whole-repo activity rollup so
**everyone's** commits/PRs show up in the dashboards, reports, and pulse — not
just your own. If you later clone and work on such a repo locally (or drive it
through a cloud agent), the rollup steps aside automatically so it isn't
double-counted, and it resumes when the work goes quiet.

```yaml
active_projects: []
  # Example — monitor an upstream dependency for everyone's activity:
  # - name: "Watched — upstream deps"
  #   external: true
  #   repos:
  #     - anthropics/anthropic-sdk-python
most_likely_active_projects: []
semi_active_projects: []
dormant_projects: []
potential_projects: []
archived_projects: []
```

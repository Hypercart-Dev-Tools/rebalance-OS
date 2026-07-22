# Machine-local jobs overlay (GH-195)

Jobs in this directory are **machine-specific and gitignored** (`*.toml` here is in
`.gitignore`). This is where an adopted automation lands when its command points at an
**absolute, machine-specific path** outside `rebalance-OS` — e.g. a job that syncs two
of *this* Mac's repos. Such a path must never enter the committed registry, or every
fleet clone's `DASHBOARD.md` would inherit a path that doesn't exist on their machine.

How the split works:

- **Committed & fleet-portable:** `jobs.d/*.toml`, `commands.allow`, `DASHBOARD.md`.
  `dashboard.render()` loads with `include_local=False`, so a local job never drifts
  the dashboard across clones (and CI's `--check` stays deterministic).
- **Machine-local & gitignored:** `jobs.local.d/*.toml`, `commands.local.allow`,
  `CATALOG.md`, `config/runtime.env`. Runtime — `run`, `status`, `list`, `health`,
  `catalog` — loads these (`include_local=True`), so the operator sees and controls
  them. `CATALOG.md` (also gitignored) is where a local job shows up per-machine.

To adopt a cross-repo job:

1. Add its command to `commands.local.allow` (copy `commands.local.allow.example`).
2. Drop a `<job>.toml` here (same schema as `jobs.d/*.toml`).
3. `python -m three_eyes validate` (validates the overlay too).
4. `python -m three_eyes install <job>` (gated) — writes+bootstraps its plist.
5. Retire the old ad-hoc plist so nothing double-schedules the same work.

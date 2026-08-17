# Capabilities Index

> Generated from `capabilities/manifest.yaml` by `scripts/generate_capabilities_index.py`.
> Read-only reference. Edit the manifest, then regenerate this file.

| Bundle | Owner | Skills | Commands | Hooks | Executables | Requires |
|---|---|---|---|---|---|---|
| `relay-xyz` | XYZ | `.xyz/skills/relay-xyz/SKILL.md` | `relay-xyz` | `relay-automation/hooks/relay-xyz-guard.sh` | `relay-automation/relay-drive.sh`<br>`relay-automation/codex-turn.sh`<br>`relay-automation/agy-turn.sh` | `path-scoped artifact under review`<br>`clean git handoff discipline` |
| `xyz` | XYZ | `skills/xyz/SKILL.md` | `xyz` | — | `bin/tick` | `non-overlapping path claims`<br>`shared .tick event log` |
| `consult` | XYZ | `skills/consult/SKILL.md` | `consult` | — | `relay-automation/consult.sh` | `throwaway git worktree isolation` |

Manifest source: [capabilities/manifest.yaml](capabilities/manifest.yaml).

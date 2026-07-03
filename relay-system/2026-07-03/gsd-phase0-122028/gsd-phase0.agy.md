### 1. Direct Answer
The Phase 0 inventory shows that **gsd-core** is a mature, spec-driven framework built around a 5-step loop (Discuss → Plan → Execute → Verify → Ship) managed by fresh-context subagents to prevent context rot. Its skills, agents, commands, and hooks compose declaratively via a modular **capability** abstraction layer. In contrast, **Rebalance** relies on document-centric, manually attested PDDA checklist files (`utils/pdda/pdda.sh`) and global `snapshot.md` files for state, while **XYZ** (`.xyz/`) implements concurrent execution via a file-based, lock-secured lane/claim model (`tick`).

---

### 2. Graded Findings

*   **[Should]** Adopt the core pattern of **fresh-context subagents** for heavy tasks (discuss/plan/execute/verify) in **Rebalance** to protect the main orchestrator session from context rot and ensure deterministic agent behavior.
    *   *gsd-core source:* [docs/explanation/context-engineering.md:26](file:///Users/noelsaw/Documents/GH%20Repos/gsd-core/docs/explanation/context-engineering.md#L26), [docs/explanation/multi-agent-orchestration.md:21-26](file:///Users/noelsaw/Documents/GH%20Repos/gsd-core/docs/explanation/multi-agent-orchestration.md#L21-L26)
    *   *Rebalance counterpart:* None (or ad-hoc [ask_self.md:1-62](file:///Users/noelsaw/Documents/rebalance-OS/.claude/commands/ask_self.md#L1-L62)).
*   **[Should]** Adapt gsd-core's **declarative capability overlay model** (`capability.json` manifests) to bundle and register custom skills, agents, and hooks in **Rebalance/XYZ**, replacing our flat, unstructured skill/command folders.
    *   *gsd-core source:* [docs/explanation/capability-overlay-model.md:18-21](file:///Users/noelsaw/Documents/GH%20Repos/gsd-core/docs/explanation/capability-overlay-model.md#L18-L21), [capabilities/nyquist/capability.json:1-51](file:///Users/noelsaw/Documents/GH%20Repos/gsd-core/capabilities/nyquist/capability.json#L1-L51)
    *   *Rebalance counterpart:* Flat [.claude/skills/](file:///Users/noelsaw/Documents/rebalance-OS/.claude/skills) directory and [.xyz/skills/](file:///Users/noelsaw/Documents/rebalance-OS/.xyz/skills) directory.
*   **[Nit]** Align the structure of `ROADMAP.md` and planning checkpoints with gsd-core's `.planning/` conventions to improve automated state parsing.
    *   *gsd-core source:* [docs/ARCHITECTURE.md:609-660](file:///Users/noelsaw/Documents/GH%20Repos/gsd-core/docs/ARCHITECTURE.md#L609-L660)
    *   *Rebalance counterpart:* Root-level [ROADMAP.md](file:///Users/noelsaw/Documents/rebalance-OS/ROADMAP.md) and [PDDA-INSTALL.md:105](file:///Users/noelsaw/Documents/rebalance-OS/utils/pdda/PDDA-INSTALL.md#L105).
*   **[Pass]** Verification of MIT license constraints confirms free reuse of patterns and ideas, with attribution required only for verbatim text/code copies.
    *   *gsd-core source:* [LICENSE:1](file:///Users/noelsaw/Documents/GH%20Repos/gsd-core/LICENSE#L1), [docs/explanation/the-phase-loop.md:29-31](file:///Users/noelsaw/Documents/GH%20Repos/gsd-core/docs/explanation/the-phase-loop.md#L29-L31)

---

### 3. Recommendation
**Promote the review doc to `2-WORKING` and launch parallel subagents to grade Family A and Family B patterns.**

---

### 4. Grounded Catalog (Consult Question Deliverables)

#### Part 1: Family A Inventory (Phase Loop & Context Engineering)
1.  **The 5-Step Loop (Discuss → Plan → Execute → Verify → Ship):** Work flows linearly through explicit gates: Discuss (captures decisions in `CONTEXT.md`), Plan (decomposes tasks into wave-based `PLAN.md` files), Execute (dispatches atomic tasks to executors), Verify (writes a `VERIFICATION.md` auditing reqs), and Ship (updates state and archives).
    *   *Source:* [docs/explanation/the-phase-loop.md:12](file:///Users/noelsaw/Documents/GH%20Repos/gsd-core/docs/explanation/the-phase-loop.md#L12) ("Discuss → (UI design) → Plan → Execute → Verify → Ship"), [the-phase-loop.md:23-59](file:///Users/noelsaw/Documents/GH%20Repos/gsd-core/docs/explanation/the-phase-loop.md#L23-L59).
2.  **STATE.md / CONTEXT.md Artifacts:** Durable filesystem state stored in Markdown files under `.planning/`. `STATE.md` represents the "living memory" of the project state, while `CONTEXT.md` stores user preferences and technical decisions.
    *   *Source:* [docs/ARCHITECTURE.md:616](file:///Users/noelsaw/Documents/GH%20Repos/gsd-core/docs/ARCHITECTURE.md#L616) (STATE.md), [docs/ARCHITECTURE.md:635](file:///Users/noelsaw/Documents/GH%20Repos/gsd-core/docs/ARCHITECTURE.md#L635) (CONTEXT.md), [docs/ARCHITECTURE.md:609-660](file:///Users/noelsaw/Documents/GH%20Repos/gsd-core/docs/ARCHITECTURE.md#L609-L660) (Layout).
3.  **Fresh-Context Subagents:** Spawns specialized agents (e.g., `gsd-executor`, `gsd-planner`) with a clean 200k context window and a narrow subset of local files to prevent token accumulation and cognitive degradation (context rot).
    *   *Source:* [docs/explanation/context-engineering.md:26-44](file:///Users/noelsaw/Documents/GH%20Repos/gsd-core/docs/explanation/context-engineering.md#L26-L44), [docs/explanation/multi-agent-orchestration.md:21-26](file:///Users/noelsaw/Documents/GH%20Repos/gsd-core/docs/explanation/multi-agent-orchestration.md#L21-L26).
4.  **Parallel Execution Waves:** Groups plans into dependency-based "waves" (Wave 1: no dependencies, Wave 2: depends on Wave 1). Runs independent plans concurrently inside parallel git worktrees.
    *   *Source:* [docs/explanation/multi-agent-orchestration.md:88-104](file:///Users/noelsaw/Documents/GH%20Repos/gsd-core/docs/explanation/multi-agent-orchestration.md#L88-L104), [gsd-core/workflows/execute-phase.md:440-454](file:///Users/noelsaw/Documents/GH%20Repos/gsd-core/gsd-core/workflows/execute-phase.md#L440-L454).
5.  **Verify-Before-Done Gate:** Runs a verifier agent checking requirement and decision coverage to generate a `VERIFICATION.md` report and fix-plans for deviations before the phase is closed.
    *   *Source:* [docs/explanation/the-phase-loop.md:51-56](file:///Users/noelsaw/Documents/GH%20Repos/gsd-core/docs/explanation/the-phase-loop.md#L51-L56), [capabilities/nyquist/capability.json:32-47](file:///Users/noelsaw/Documents/GH%20Repos/gsd-core/capabilities/nyquist/capability.json#L32-L47).

#### Part 2: Family B Inventory (Architecture & Composition)
*   **Skill ↔ Agent ↔ Command ↔ Hook Composition:**
    *   *Traced Example (`execute-phase`)*:
        *   **Skill**: [skills/gsd-execute-phase/SKILL.md:1-66](file:///Users/noelsaw/Documents/GH%20Repos/gsd-core/skills/gsd-execute-phase/SKILL.md#L1-L66) is the developer/LLM entry point.
        *   **Command**: [commands/gsd/execute-phase.md:1-66](file:///Users/noelsaw/Documents/GH%20Repos/gsd-core/commands/gsd/execute-phase.md#L1-L66) exposes `/gsd:execute-phase` to the runtime shell.
        *   **Workflow**: [gsd-core/workflows/execute-phase.md:1-1708](file:///Users/noelsaw/Documents/GH%20Repos/gsd-core/gsd-core/workflows/execute-phase.md#L1-L1708) contains the orchestrator logic (init, checkpointing, worktree branch gates).
        *   **Agent**: [agents/gsd-executor.md:1-812](file:///Users/noelsaw/Documents/GH%20Repos/gsd-core/agents/gsd-executor.md#L1-L812) is the specialized subagent configuration spawned to execute single plans.
        *   **Capability**: [capabilities/nyquist/capability.json:1-51](file:///Users/noelsaw/Documents/GH%20Repos/gsd-core/capabilities/nyquist/capability.json#L1-L51) registers modular hooks into the loop.
        *   **Hooks**: Runtime event hooks register GSD scripts to monitor headroom and check for injections dynamically ([docs/how-to/install-on-your-runtime.md:45-59](file:///Users/noelsaw/Documents/GH%20Repos/gsd-core/docs/how-to/install-on-your-runtime.md#L45-L59)).
*   **What the `capabilities/` layer actually does:**
    *   It is a **real declarative abstraction layer**. It defines modular features (dependencies, runtime compatibility, hooks, loop points, config keys, and gates) that are dynamically merged at runtime by `loadRegistry` into a unified command and skill catalog without hardcoding them into the loop engine ([docs/explanation/capability-overlay-model.md:16-41](file:///Users/noelsaw/Documents/GH%20Repos/gsd-core/docs/explanation/capability-overlay-model.md#L16-L41)).

#### Part 3: Counterpart Map

| gsd-core Pattern | Rebalance / XYZ Counterpart | Citation (Rebalance / Global) | Comparison / Gap |
| :--- | :--- | :--- | :--- |
| **5-Step Loop** | PDDA Document Lifecycle | [GSD-CORE-PATTERN-REVIEW.md:6-10](file:///Users/noelsaw/Documents/rebalance-OS/PROJECT/1-INBOX/GSD-CORE-PATTERN-REVIEW.md#L6-L10), [utils/pdda/pdda.sh:566-624](file:///Users/noelsaw/Documents/rebalance-OS/utils/pdda/pdda.sh#L566-L624) | PDDA moves files from `1-INBOX` → `2-WORKING` → `3-COMPLETED` manually or via script, but lacks automated orchestrator workflows and agent gating. |
| **STATE.md / CONTEXT.md** | `ROADMAP.md` & PDDA frontmatter | Root [ROADMAP.md](file:///Users/noelsaw/Documents/rebalance-OS/ROADMAP.md), [PDDA-INSTALL.md:105-108](file:///Users/noelsaw/Documents/rebalance-OS/utils/pdda/PDDA-INSTALL.md#L105-L108) | Rebalance consolidates roadmap and phase-checklists inside single document files instead of separate, isolated planning state files. |
| **Fresh-Context Subagents** | Custom `ask_self` command & Agent tool | [.claude/commands/ask_self.md:1-62](file:///Users/noelsaw/Documents/rebalance-OS/.claude/commands/ask_self.md#L1-L62) | Rebalance uses subagents ad-hoc but lacks a strict context budget, isolation worktrees, or structured hand-back formats like `SUMMARY.md`. |
| **Parallel Execution Waves** | XYZ concurrent lanes (`tick` CLI) | [.xyz/skills/xyz/SKILL.md:4-11](file:///Users/noelsaw/Documents/rebalance-OS/.xyz/skills/xyz/SKILL.md#L4-L11), [.xyz/src/project.js:589-631](file:///Users/noelsaw/Documents/rebalance-OS/.xyz/src/project.js#L589-L631) | XYZ uses a shared event log and mutex locks (`tick`) for path-scoped concurrent editing. gsd-core coordinates parallel subagent worktrees centrally via an orchestrator DAG. |
| **Verify-Before-Done Gate** | PDDA checklists & `phase-qa` / `loose-ends` | [GSD-CORE-PATTERN-REVIEW.md:260-266](file:///Users/noelsaw/Documents/rebalance-OS/PROJECT/1-INBOX/GSD-CORE-PATTERN-REVIEW.md#L260-L266), [02-plan/phase-qa/SKILL.md:229-242](file:///Users/noelsaw/Documents/GH%20Repos/giant-brains-claude-skills/02-plan/phase-qa/SKILL.md#L229-L242) | Rebalance relies on human-attested checklists (e.g. DRY/SOLID tests) injected by `phase-qa`. gsd-core uses automated verifier subagents checking requirements. |
| **Modular Hook System** | Project hooks & `relay-xyz-guard` | [.xyz/relay-automation/hooks/relay-xyz-guard.sh:1-4495](file:///Users/noelsaw/Documents/rebalance-OS/.xyz/relay-automation/hooks/relay-xyz-guard.sh), [pdda-edit-doc-hook.sh:1-2444](file:///Users/noelsaw/Documents/rebalance-OS/utils/pdda/pdda-edit-doc-hook.sh) | Rebalance uses flat, file-mapped hooks. gsd-core has runtime-level hooks for compaction, stop, and file changes bridged dynamically via a capability registry. |

#### Part 4: License + Spillover
*   **License Check**: `LICENSE:1` is `MIT License` ("Copyright (c) 2026 Open GSD"). Verbally: Patterns/ideas are free to reuse without attribution; verbatim file/text copies must retain the MIT license + copyright notice.
*   **GH-102 Spillover Note**: The gsd-core installer ([docs/how-to/install-on-your-runtime.md:11](file:///Users/noelsaw/Documents/GH%20Repos/gsd-core/docs/how-to/install-on-your-runtime.md#L11)) handles runtime-specific config transformations (e.g., rewriting hyphen slashes to colon namespaces for Gemini, converting TOML structures for Codex), which acts as a robust reference for building a cross-runtime release channel for XYZ and Rebalance.

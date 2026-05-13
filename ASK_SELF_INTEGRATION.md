---
title: Integrate ask-self into This Repo
last_updated: 2026-05-11
audience: integrating agent (Claude Code / VS Code agent / Cursor / etc.) in another repo
---

<!--
Revision history:
- 2026-05-11: Add concrete local-provider JSON snippets, make the first smoke-test ingest explicitly use `--mode all`, and note that bundled templates should already exclude generated ask-self docs by default.
- 2026-05-11: Clarify current CLI surfaces and registry behavior: separate true Python entry points from supporting files, treat the root `ask_self_harness.json` as a repo-specific Python example rather than a neutral template, document portable-mode `--no-register`, and call out the `--db-path` vs `--target*` query conflict.
- 2026-05-10: Generalize validation-checklist examples beyond WordPress (GraphQL/tRPC, Redis/keychain/localStorage, Node/Python route registration, node_modules/.venv exclusions). Clarify the "hand-edit and detach" consequence.
- 2026-05-10: Add post-ingest validation checklist for the generated ARCHITECTURE.md narrative.
- 2026-05-10: Introduce three-mode index placement model (local-only / shared baseline / portable).
- 2026-05-10: Initial restructure with provider-mode table, Swift detection, agent-facing lead-in.
-->


# Task: Integrate ask-self into This Repo

## For the integrating agent

You are reading this from another repo and your job is to wire **ask-self** — an external, repo-grounded RAG tool — into that repo. You are **not** modifying ask-self itself.

The deliverable is a thin local integration layer in the target repo:

- a local harness config (`ask_self/ask_self_harness.json`)
- local system instructions (`ask_self/ask_self_system_instructions.json`)
- two wrapper scripts (`scripts/ask-self-ingest.sh`, `scripts/ask-self-query.sh`) that call the external ask-self install through Python
- `.gitignore`, README, and `AGENTS.md` updates so humans and future agents discover the tool

Before doing anything, jump to **Detection Step** and **Before You Start** to inspect the target repo and the external ask-self entry points. If anything in the repo kind, GitHub identity, PR ingestion, or fully-local mode is ambiguous, **ask** before finalizing.

## Background

ask-self ingests a repo, chunks source and documentation intelligently, stores embeddings in a per-repo SQLite database, and lets you query that indexed corpus with natural-language questions.

Canonical ask-self repo:

- Location: `/path/to/ask-self` (override via `ASK_SELF_PATH`)
- Python entry points used by the target-repo wrappers (at the repo root, not nested under `ask_self/`):
  - `ask_self_ingest.py`
  - `ask_self_query.py`
- Supporting files you should inspect while integrating:
  - `ask_self_harness.py`
   - `ask_self_registry.py`
  - `ask_self_system_instructions.json`
- Harness templates / examples (also at repo root):
  - `wp_theme_harness.json`
  - `wp_plugin_harness.json`
  - `js_ts_generic_harness.json`
   - `ask_self_harness.json` (Python-first example; in this repo it is the repo's own tuned harness, not a neutral drop-in template)
- Global CLI: `bin/ask-self` exposes `ask-self ask|ingest|register|dashboard|warm-cache`. The wrapper scripts in the target repo still invoke the Python entry points directly so they can pin `--harness-config` to the local file. Treat `bin/ask-self` as an internal convenience, not the integration contract.
- Shared registry: `temp/rag/ask_self_registry.json`
- Internal runtime defaults may still assume `ask_self/ask_self_harness.json` and `ask_self/ask_self_system_instructions.json`, so external wrappers must always pass an explicit `--harness-config`.

ask-self is intentionally multi-repo. Each target repo gets a thin local integration layer (harness, system instructions, wrappers, agent guidance) and a per-repo SQLite index.

### Credential resolution (Gemini)

In order:

1. `GOOGLE_API_KEY`
2. `GOOGLE_API_KEY_FILE` or `ASK_SELF_GOOGLE_API_KEY_FILE` (raw key file or env-style file)
3. `gcloud secrets versions access latest` when `GOOGLE_API_KEY_SECRET_NAME` or `ASK_SELF_GOOGLE_API_KEY_SECRET` is set
   - optional project override: `GOOGLE_API_KEY_SECRET_PROJECT` or `ASK_SELF_GOOGLE_API_KEY_SECRET_PROJECT`

Recommend Google Secret Manager over a committed or long-lived local file.

### Provider configuration: retrieval vs synthesis

ask-self splits embeddings (retrieval) and answer generation (synthesis) into two independent providers. This matters for offline / cost-controlled setups.

Embedding provider (`embedding.provider` in the harness):

- `gemini` (default) — requires a Gemini API key
- `qwen-local` — runs `sentence-transformers` locally; no API key needed for ingest or retrieval. Install requirement: `pip install sentence-transformers`. Common model: `Qwen/Qwen3-Embedding-0.6B` at `dim: 1024`.

Synthesis provider (`synthesis.provider` in the harness, optional block):

- `gemini` (default) — requires a Gemini API key
- `ollama` — talks to a local Ollama daemon (default endpoint `http://localhost:11434`, default model `qwen3:8b`)
- `openai_compatible` — talks to any OpenAI-compatible local server (default endpoint `http://localhost:8080/v1`)
- `local` is accepted as a friendly alias for `ollama`

Resulting modes:

| Mode | `embedding.provider` | Synthesis | Needs Gemini key? |
|---|---|---|---|
| Default | `gemini` | `gemini` | yes |
| Local retrieval only | `qwen-local` | n/a (`--retrieval-only`) | no |
| Fully local | `qwen-local` | `ollama` or `openai_compatible` | no |
| Hybrid | `qwen-local` | `gemini` | yes (for synthesis only) |

CLI gates on the query path:

- `--retrieval-only` skips synthesis and returns the retrieved context as the answer
- `--local-only` refuses to run if either retrieval or synthesis would touch a remote API given the current harness — useful as a hard sanity check

Ingest does **not** require `GOOGLE_API_KEY` when `embedding.provider = "qwen-local"`. The check fires only when the provider is `gemini`.

The architecture-narrative generator (the "How it fits together" section in `ARCHITECTURE.md`) also honors `synthesis.provider`. With a local synthesis backend configured, the entire ingest path can run with no Gemini key.

Concrete fully-local harness snippet:

```json
{
   "embedding": {
      "provider": "qwen-local",
      "model": "Qwen/Qwen3-Embedding-0.6B",
      "dim": 1024
   },
   "synthesis": {
      "provider": "ollama",
      "model": "qwen3:8b"
   }
}
```

If you only want local retrieval, keep the `embedding` block above and either omit `synthesis` entirely or leave it on Gemini and query with `--retrieval-only`. When switching to `qwen-local`, set `model` and `dim` explicitly; if you only change `provider`, the current defaults remain Gemini-oriented (`gemini-embedding-001`, `dim: 768`).

### Index placement modes

ask-self supports three placement modes for the per-repo SQLite vector DB. **Ask the user which mode they want before finalizing** — defaults are fine for most repos but the choice has real size / privacy / staleness implications.

| Mode | DB location | Committed? | Query default | Best for |
|---|---|---|---|---|
| **Local-only** (default) | `temp/rag/*.sqlite` | no | fresh local index, generated per-user | most repos; per-user / per-branch indexes |
| **Shared baseline** | `ask_self/index/<repo>-shared.sqlite` | yes (lightweight) | fresh local index when present; baseline via explicit `--db-path` | onboarding speed; agent startup; teams that still expect each dev to re-ingest |
| **Portable** | `ask_self/index/<repo>.sqlite` | yes (full) | the committed DB; teammates clone and query immediately, no ingest needed | small / mid repos where teammates should not have to run ingest at all |

Tradeoffs to surface explicitly when proposing **portable**:

- **Size**: vector DBs run hundreds of MB to GBs depending on chunk count. Recommend Git LFS for any DB above ~100 MB. Run `du -sh ask_self/index/` before each commit.
- **Embedding lock-in**: anyone refreshing the DB needs the same `embedding.provider` + `model` + `dim` as the one that built it. **Strongly recommend `qwen-local`** for portable mode so no teammate needs a Gemini API key just to regenerate.
- **Privacy**: embeddings encode the indexed source text and are partially reconstructable. For public repos or repos with restricted-distribution code, a committed DB effectively exposes everything indexed. Surface this risk to the user before choosing portable.
- **Staleness**: committed DBs go stale as fast as the code changes. Add a "last ingested" line to the README and a one-liner refresh command. Consider a CI job that regenerates on `main`.
- **Sidecar files**: ask-self derives `<db-stem>__embed_cache.sqlite` and `<db-stem>__events.jsonl` alongside the DB. **Do not commit these in any mode**; gitignore them by name.

## Goal

Wire ask-self into **this repo** so I can:

1. Run ingest to build or refresh a RAG index of this repo.
2. Run query to ask grounded questions with citations.
3. Register this repo's local/full working index in the shared ask-self registry when the chosen placement mode uses one. Do **not** register committed shared-baseline or portable DBs.
4. Make future AI coding agents discover ask-self automatically through `AGENTS.md` and any existing parallel agent-instruction files.

## Detection Step

Before writing files, inspect the repo and determine which harness template is the best starting point.

Heuristics:

- Tree dominated by `.md` files or primarily docs/notes layout → **Markdown/Docs project**, start from `markdown_harness.json`
- `style.css` plus `theme.json`, or a theme-like layout under `wp-content/themes/` → **WordPress theme**, start from `wp_theme_harness.json`
- A root-level PHP file with a `Plugin Name:` header, or a plugin-style `readme.txt` → **WordPress plugin**, start from `wp_plugin_harness.json`
- `package.json` with TS, React, Next, Vite, Supabase, or similar signals → **JS/TS project**, start from `js_ts_generic_harness.json`
- `Package.swift`, `Project.swift`/Tuist manifests, or a tree dominated by `.swift` files → **Swift project**, derive from `js_ts_generic_harness.json` and route `.swift` sources to the Swift chunker (set `chunker: "swift"` on the relevant source bucket; ask-self ships a Swift top-level-declaration chunker)
- `pyproject.toml`, `setup.py`, `requirements.txt`, or a clearly Python-first repo → derive from the root `ask_self_harness.json` example, but treat it as a worked Python config rather than a neutral template and replace repo-specific patterns immediately
- Ambiguous → ask before finalizing

Also inspect:

- top-level layout via `ls -la`
- whether `ask_self/` already exists in the target repo
- whether `temp/rag/` already exists
- current `.gitignore`
- `composer.json`, `package.json`, `pyproject.toml`, etc.
- existing agent files: `AGENTS.md`, `CLAUDE.md`, `.cursorrules`, `.augment/`

## Requirements

### 1. Keep ask-self external

Do **not** vendor, copy, symlink, or submodule ask-self into the target repo.

The integration is a thin local layer that points to the external ask-self install via:

- `ASK_SELF_PATH` (default: `/path/to/ask-self`)
- optionally `ASK_SELF_PYTHON` if the external checkout should run under a specific interpreter

Allow both to be overridden through the environment.

### 2. Create a local `ask_self/` directory in the target repo

This local folder is the integration layer for the target repo, not a vendored copy of ask-self.

Create:

- `ask_self/ask_self_harness.json`
- `ask_self/ask_self_system_instructions.json`
- `ask_self/index/` (tracked) if the repo uses **shared baseline** or **portable** mode (see Index Placement Notes); skip otherwise

#### `ask_self/ask_self_harness.json`

Copy the most appropriate template from the external ask-self repo and tune it to the actual target repo.

For Python-first repos, the root `ask_self_harness.json` is still the closest starting point, but it is a repo-local example in this repository. Replace its repo-specific include/exclude patterns, GitHub metadata, ingest command, and doc/source buckets immediately instead of treating it as a drop-in generic template.

Update at minimum:

- `repo_label`
- `repo_kind`
- `db_filename`
- `tenancy_env_var`
- `ingest_command`
- `github.owner`
- `github.repo`
- `shared_index`

Tune carefully:

- `docs.include_patterns`
- `docs.exclude_patterns`
- `source.include_patterns`
- `source.exclude_patterns`
- `classification_rules`

Set deliberately if relevant:

- `embedding.provider` (`gemini` or `qwen-local`), plus `model` and `dim` to match the chosen embedder
- `embedding.requests_per_minute` and `embedding.tokens_per_minute` (set to `0` to explicitly disable throttling; both `None` falls back to defaults)
- `synthesis.provider` if the repo wants fully-local answers (`ollama` or `openai_compatible`); leave unset for default Gemini synthesis

Important:

- Verify regexes against real files before finalizing.
- Do not guess patterns that match nothing.
- Exclude generated ask-self docs from future ingests:
  - `ASK_SELF.md`
  - `ARCHITECTURE-BAK.md`
- Bundled upstream templates should already exclude those by default. Preserve those excludes when hand-tuning the harness instead of re-adding them from memory.
- Decide deliberately whether `ARCHITECTURE.md` itself should be indexed.
- For Swift sources, set `chunker: "swift"` on the relevant source bucket so chunks land on top-level declaration boundaries instead of generic text windows.
- For **shared baseline** mode, set `shared_index.enabled: true` and point `shared_index.path` at a tracked location such as `ask_self/index/<repo>-shared.sqlite`. `shared_index.prefer_for_query` may remain in older harnesses, but the default query happy path no longer auto-selects the shared index.
- For **portable** mode, you don't need `shared_index` — the committed DB at `ask_self/index/<repo>.sqlite` is the canonical query target via wrapper-injected `--db-path`. Set `embedding.provider = "qwen-local"` so teammates can refresh without a Gemini key.

#### `ask_self/ask_self_system_instructions.json`

Copy the current canonical file from the external ask-self repo and make the smallest repo-identity edit needed, typically in `base_system`. Everything else should stay close to upstream unless the repo genuinely needs different answer behavior.

### 3. Create thin wrapper scripts

Create:

- `scripts/ask-self-ingest.sh`
- `scripts/ask-self-query.sh`

(Or use the repo's existing script location if there is a stronger local convention.)

Each wrapper should:

- resolve `ASK_SELF_PATH` (default `/path/to/ask-self`)
- resolve `ASK_SELF_PYTHON` if provided; otherwise prefer `"$ASK_SELF_PATH/.venv/bin/python"` when it exists; otherwise fall back to `python3`
- fail loudly if the external repo or entry points are missing
- invoke the external entry points through Python, not as executable scripts:
  - `"$PYTHON_BIN" "$ASK_SELF_PATH/ask_self_ingest.py"`
  - `"$PYTHON_BIN" "$ASK_SELF_PATH/ask_self_query.py"`
- pass `--harness-config` pointing at the target repo's local `ask_self/ask_self_harness.json`
- pass through additional CLI args unchanged

Keep the wrapper logic simple so it can later swap from path-based invocation to a packaged CLI with minimal edits.

No dedicated local `register` wrapper is required. Normal local-only ingests register automatically unless `--no-register` is passed. Shared-baseline ingests already skip registry updates via `--shared-index`. Portable committed DBs should not be registered at all.

Wrapper behavior by mode:

- **Local-only**: wrappers pass nothing extra. Query uses the harness-defined temp DB path.
- **Shared baseline**: wrappers pass nothing extra by default. The shared DB is an explicit/manual target via the user-supplied `--db-path`. (The default query happy path does not auto-fall-back to it.)
- **Portable**: the **query** wrapper injects `--db-path "$REPO_ROOT/ask_self/index/<repo>.sqlite"` so a fresh clone can query immediately with no ingest. Users override by passing their own `--db-path` (argparse is last-wins). Because `ask_self_query.py` rejects `--db-path` combined with `--target`, `--targets`, or `--all-targets`, that wrapper is intentionally pinned to the repo's committed DB; use the external ask-self CLI directly for cross-repo registry queries. The **ingest** wrapper writes to the same path by default and should also inject `--no-register`, because committed portable DBs are not registry entries.

Index path discipline, kept explicit:

- full local working indexes belong under `temp/rag/*.sqlite` and stay gitignored
- shared baseline indexes belong in a tracked path such as `ask_self/index/<repo>-shared.sqlite`
- portable indexes belong in a tracked path such as `ask_self/index/<repo>.sqlite`
- do not collapse these into the same path; they serve different purposes and have different commit/refresh expectations

Registration discipline, kept explicit:

- local/full working indexes register by default unless `--no-register` is passed
- `--shared-index` already disables registry updates for shared baselines
- portable committed DBs should always be built with `--no-register`
- if a team wants both portable clone-and-query behavior **and** a registry-visible working index, build them as two separate DB targets rather than reusing the committed portable DB

### 4. Update `.gitignore`

Always ignore:

- `temp/rag/`
- `temp/ask-self-rag.env`
- any other target-repo temp artifacts produced by ask-self
- the per-DB sidecar files everywhere they appear: `*__embed_cache.sqlite`, `*__events.jsonl`

By placement mode:

- **Local-only**: that's it — `ask_self/index/` does not exist
- **Shared baseline** / **Portable**: do **not** ignore `ask_self/index/*.sqlite`; that's the committed DB. Do still ignore the sidecars (`ask_self/index/*__embed_cache.sqlite`, `ask_self/index/*__events.jsonl`).

Do not over-broaden ignores if the repo already uses `temp/` for unrelated tracked content.

### 5. Update README

Add a short section (e.g. `Code Intelligence` or `Querying this Repo`) covering:

- one-sentence explainer of ask-self
- how to query: `./scripts/ask-self-query.sh "your question here"`
- how to ingest (refresh the index): `./scripts/ask-self-ingest.sh`
- note that `ASK_SELF_PATH` can be overridden
- credential options: `GOOGLE_API_KEY`, `GOOGLE_API_KEY_FILE`, Google Secret Manager via `GOOGLE_API_KEY_SECRET_NAME` — or "none required" if the harness is configured for fully-local retrieval + synthesis
- if the repo is set up for fully-local mode: how to invoke it (e.g. `./scripts/ask-self-query.sh --local-only "question"`) and what the local synthesis backend is (Ollama / OpenAI-compatible)

Mode-specific additions:

- **Local-only**: note that each developer must run `./scripts/ask-self-ingest.sh` once before querying; the index lives under `temp/rag/` and is gitignored
- **Shared baseline**: note how to publish — `./scripts/ask-self-ingest.sh --shared-index --mode all` — and that the default query path still prefers a fresh local index; pass `--db-path ask_self/index/<repo>-shared.sqlite` to hit the shared one explicitly
- **Portable**: state that no setup is required to query — clone and run. Add a "last ingested" line (date + git SHA) that gets updated when the DB is refreshed. Include the refresh command (`./scripts/ask-self-ingest.sh`) and call out the embedding provider (`qwen-local`, requires `pip install sentence-transformers` only when refreshing). If the DB is large, mention the Git LFS requirement.

Optional but useful in all modes: a one-line note that indexes reflect the last ingest, not current uncommitted changes.

### 6. Update `AGENTS.md` and parallel agent files

This is the highest-leverage deliverable because it determines whether future agents discover ask-self early.

#### If `AGENTS.md` already exists

- Read it first.
- Match its tone and heading style.
- Append a new section without restructuring existing content.
- Place it near the top if the file structure permits, ideally after high-level repo overview and before deep coding conventions.

#### If `AGENTS.md` does not exist

- Create one.
- Keep it focused on agent-relevant repo context and available tools.

#### Also update parallel files only if they already exist or the repo clearly uses them

- `CLAUDE.md`
- `.cursorrules`
- `.augment/` convention files

Do not create these from scratch unless the repo already signals that tooling.

#### Required AGENTS content

Adapt to the repo's tone, but include all of this:

- what ask-self is and why an agent should use it
- exact command: `./scripts/ask-self-query.sh "your question here"`
- when to use it:
  - session-start orientation
  - unfamiliar subsystems
  - pronoun-heavy user references such as "that helper" or "the auth flow"
  - cross-file behavior questions
- when not to use it:
  - trivial single-file reads
  - tight edit-test loops
  - questions about current uncommitted state
- staleness note: the index reflects the last ingest; a committed shared index is a baseline and may lag active branch work
- override note: `ASK_SELF_PATH`

Strong preferred phrasing:

> Before grep-spelunking or asking the user to re-explain repo context, query ask-self first.

### 7. Do not modify the external ask-self repo

All integration changes belong in the target repo, not in `/path/to/ask-self`.

## Constraints

- no committed symlinks
- no submodule
- no vendored ask-self copy
- harness include patterns must match real files
- harness exclude patterns must not silently exclude the entire repo
- `AGENTS.md` edits must be append-only relative to existing content

## Before You Start

1. Inspect the target repo:
   - `ls -la`
   - top-level directories
   - `package.json`, `composer.json`, `pyproject.toml`, `requirements.txt`, `Package.swift`
   - existing agent files
2. Read the harness template from the external ask-self repo root:
   - `/path/to/ask-self/markdown_harness.json`
   - `/path/to/ask-self/wp_theme_harness.json`
   - `/path/to/ask-self/wp_plugin_harness.json`
   - `/path/to/ask-self/js_ts_generic_harness.json`
   - `/path/to/ask-self/ask_self_harness.json` (repo-local Python example, not a neutral generic template)
3. Read the external entry points directly:
   - `/path/to/ask-self/ask_self_ingest.py`
   - `/path/to/ask-self/ask_self_query.py`
4. Confirm relevant CLI flags and runtime requirements:
   - Ingest: `--db-path`, `--harness-config`, `--mode`, `--no-prs`, `--no-register`, `--no-architecture-md`, `--shared-index`, `--cache-path`, `--no-cache`, `--events-file`, `--no-events`, `--dashboard`, `--embed-rpm`, `--embed-tpm`
   - Query: `--harness-config`, `--db-path`, `--retrieval-only`, `--local-only`, `--json`, `--target`, `--targets`, `--all-targets`
   - Credential resolution: `GOOGLE_API_KEY`, `GOOGLE_API_KEY_FILE`, `GOOGLE_API_KEY_SECRET_NAME` (+ `gcloud` for Secret Manager)
   - Local providers: `sentence-transformers` for `qwen-local` embeddings; a running Ollama daemon or OpenAI-compatible server for local synthesis
5. Ask before finalizing if any of these are ambiguous:
   - repo kind
   - whether PR ingestion should be enabled
   - whether `github.owner` and `github.repo` should be filled in
   - whether the repo wants Gemini, hybrid, or fully-local provider mode
   - **index placement mode**: local-only (default), shared baseline, or portable — flag the size / privacy / staleness tradeoffs before defaulting to portable
   - whether existing agent docs imply a specific tone or placement

## Architecture Doc Notes

If the target repo uses ask-self's automatic architecture generation, be aware of the current behavior:

- ingest writes `ARCHITECTURE.md` by default unless `--no-architecture-md` is used
- generated docs carry an ask-self ownership marker
- if an existing `ARCHITECTURE.md` is ask-self-managed: it is renamed to `ARCHITECTURE-BAK.md` and a fresh `ARCHITECTURE.md` is written
- if an existing `ARCHITECTURE.md` is **not** ask-self-managed: ask-self falls back to writing `ASK_SELF.md`
- the generated doc includes a file inventory, symbol index, dependency map, freshness block, and a "How it fits together" narrative
- the narrative uses the configured `synthesis.provider` — Gemini by default, Ollama / OpenAI-compatible when local synthesis is configured
- if the narrative call truncates: ask-self retries once with a compact prompt, then falls back to a deterministic local narrative rather than leaving the section blank

Make sure the harness excludes do not cause those generated docs to recursively pollute the index unless that is explicitly wanted.

### Validate the generated narrative before reporting ingest as done

The "How it fits together" section is LLM-generated and can confidently say wrong things. ask-self's synthesis prompt now bakes in discipline rules (no inventing names, keep parallel API surfaces separate, name routes/hooks literally, distinguish wiring from state ownership, don't infer storage from UI flow), but the integrating agent is the last line of defense before the doc is committed. **Read the generated `ARCHITECTURE.md` and grep-check the narrative against the source** before declaring the integration complete.

Recurring synthesis failure modes to scan for:

1. **Parallel API surfaces conflated.** If the repo has multiple API paradigms (legacy + REST, v1 + v2, GraphQL + REST, classic + block checkout, XML-RPC + JSON, `api/v1/*` + `trpc/*`), the narrative must keep them separate. Grep for distinct namespace declarations / route prefixes / hook prefixes / GraphQL schema files; if the doc says "the export system" but the source has both `woocommerce_api_*` and `wc-shipstation/v1/*` (or both `/api/v1/orders` and a tRPC `orders.list` procedure), that's a miss.
2. **Wiring class named as state owner.** Bootstrap / main / plugin-init / container / DI-root classes wire dependencies but rarely own persistent runtime state. Where do auth keys, status mappings, mode flags actually live? Verify by grepping for the actual write — `update_option` / `update_post_meta` (WP), `INSERT` / `UPDATE` against a DB, `redis.set` / `client.hset` (Redis), `localStorage.setItem` / `sessionStorage.setItem` (browser), `fs.writeFile` / `Path.write_text`, `keychain.set` / Secret Manager calls — not by trusting where things are *referenced*.
3. **Storage inferred from UI flow.** If the doc claims "credentials are stored when the user fills out the modal", trace the form-submit handler to the actual write. Auth UI is not the same surface as auth persistence — credentials might end up in `woocommerce_api_keys` (WP), a secrets-manager API, or an OS keychain, while only a reference ID lives in `wp_options` / local DB / app config.
4. **Class scope inferred from class name.** A class named `Checkout` (WP) may register hooks across classic checkout, block checkout, AJAX, admin, email, and export; a class named `AuthController` (Node/Python) may register routes well outside `/auth/*`. Enumerate the actual surface — `add_action` / `add_filter` (WP), `app.get` / `router.post` / `@app.route` / FastAPI router includes (web frameworks), `addEventListener` / event-emitter `.on()` (JS), GraphQL resolver bindings — before trusting the narrative's scope claim.
5. **Routes/hooks described in generic prose.** "Various endpoints", "several hooks", "multiple actions", "a number of listeners" are red flags for hedging or hallucination. The narrative should name routes / hooks / events literally — if it doesn't, replace or remove.
6. **Compatibility bridges missing.** Classes or methods that translate legacy → new (look for `legacy`, `fire_legacy_*`, `_compat`, `v1_to_v2`, deprecated-route handlers, GraphQL-to-REST shims) are architecturally load-bearing because they explain why old integrations still affect the new surface. Their absence from the narrative is a quality signal.
7. **Statistics treated as repo-wide.** Numbers in the doc come from the *indexed* set after exclusions, not the working tree. They should be labelled as such. If the doc says "the repo has N source files" but the harness excludes `vendor/`, `node_modules/`, `.venv/`, `dist/`, `build/`, or similar, fix the wording or check the harness.
8. **Subsystem-spanning sentences.** Any sentence joining two subsystems (XML + REST, GraphQL + REST, auth UI + auth enforcement, controller + util, frontend store + backend persistence) is high-risk. Verify both halves against the source before accepting.

If you find issues, choose one:

- **Harness fix + re-ingest**: most synthesis misses trace back to the harness picking the wrong files or excluding the right ones. Adjust `source.include_patterns` / `source.exclude_patterns`, re-run ingest, and confirm the narrative improves.
- **Hand-edit and detach**: edit `ARCHITECTURE.md` directly and remove the `<!-- ask_self:managed architecture_doc_v1 -->` marker. Future ingests will detect a non-managed file and write to `ASK_SELF.md` instead of overwriting your edits. Consequence: the manual `ARCHITECTURE.md` is no longer auto-refreshed, so it freezes at the moment you detached it; future ingests' fresh narratives land in `ASK_SELF.md`. If you want the hand-edited doc to remain available to ask-self queries, confirm it's matched by the harness `docs.include_patterns` — otherwise it'll be invisible to the RAG.
- **Skip the doc entirely**: pass `--no-architecture-md` on ingest if the synthesis quality is bad enough to be net-negative. This skips the whole file (deterministic skeleton included) — there is currently no "skeleton only, no narrative" flag.
- **Upstream feedback**: if the failure mode is general (not repo-specific) and the discipline rules in the synthesis prompt aren't catching it, open an issue against ask-self with a minimal repro so the prompt can be tightened.

## Index Placement Notes

See the **Index placement modes** table in Background for the high-level shape. Operational notes per mode:

### Local-only (default)

- DB lives at `temp/rag/<repo>.sqlite`, gitignored
- Each developer runs `./scripts/ask-self-ingest.sh` once before querying
- Wrappers pass no extra `--db-path` — the harness-defined temp path is the query target
- Best fit for the majority of repos

### Shared baseline

- DB lives at `ask_self/index/<repo>-shared.sqlite`, committed, kept intentionally lightweight
- Build / refresh with `./scripts/ask-self-ingest.sh --shared-index --mode all`
- The default query happy path still prefers a fresh local temp index; pass `--db-path ask_self/index/<repo>-shared.sqlite` to hit the shared one explicitly
- Do **not** register the shared index in the multi-repo registry (registry entries are for local/full working indexes)
- Do **not** commit sibling cache/events files (`<db-stem>__embed_cache.sqlite`, `<db-stem>__events.jsonl`)
- Expect it to be somewhat stale between refreshes

### Portable

- DB lives at `ask_self/index/<repo>.sqlite`, committed, full coverage
- Query wrapper injects `--db-path ask_self/index/<repo>.sqlite` so a fresh clone queries immediately, no ingest required
- Ingest wrapper writes to the same path (use `--db-path` or pin `db_filename` in the harness) and injects `--no-register`
- Use `embedding.provider = "qwen-local"` so teammates can refresh without a Gemini key
- Add a "last ingested: <date> @ <git SHA>" line to the README (or to a tracked `ask_self/index/STATUS.md`) and update it on each refresh
- Run `du -sh ask_self/index/` before committing. Above ~100 MB, set up [Git LFS](https://git-lfs.com) for `ask_self/index/*.sqlite` and document the `git lfs install` step in the README
- Do **not** register the portable index in the multi-repo registry
- Do **not** commit sibling cache/events files
- **Privacy check**: confirm with the user that everything indexed is OK to ship with the repo (especially if the repo is public). Embeddings encode source text and are partially reconstructable
- Consider a CI workflow that regenerates the portable DB on `main` so it doesn't drift
- Because the portable query wrapper is pinned with `--db-path`, use the external ask-self CLI rather than the local wrapper for registry-targeted `--target` / `--targets` / `--all-targets` queries

## Migrating Older Integrations

If the target repo already has an older ask-self integration, do not rebuild it from scratch blindly. Normalize it to the current model:

- keep or add a local integration folder at `ask_self/` with `ask_self_harness.json` and `ask_self_system_instructions.json`
- keep full local working indexes in `temp/rag/*.sqlite`; that remains the right place for fresh per-user or per-branch ingests
- decide which **index placement mode** the repo should be on (local-only / shared baseline / portable) and configure accordingly — ask the user before promoting a repo from local-only to a committed-DB mode
- if the repo wants a committed team baseline, add a `shared_index` block and place that light shared index in a tracked path such as `ask_self/index/<repo>-shared.sqlite`
- if the repo wants portable mode, switch `embedding.provider` to `qwen-local` (if not already), point the ingest DB at `ask_self/index/<repo>.sqlite`, and have the query wrapper inject `--db-path` at that path
- in portable mode, make the ingest wrapper inject `--no-register`; committed portable DBs are not registry entries
- update legacy wrappers so they always pass `--harness-config`, resolve `ASK_SELF_PYTHON` or `"$ASK_SELF_PATH/.venv/bin/python"`, and invoke ask-self through Python
- if a harness sets `embedding.requests_per_minute: 0` or `tokens_per_minute: 0` expecting that to disable throttling: this now works as intended (`0` is treated as "explicitly disabled"; only `None`/missing falls back to defaults)
- keep `temp/rag/` gitignored; do not newly ignore `ask_self/index/*.sqlite` if the repo intends to commit a shared baseline or portable index. Always gitignore the per-DB sidecars (`*__embed_cache.sqlite`, `*__events.jsonl`)
- if an older repo previously committed an index under `temp/rag/`, move that practice to `ask_self/index/` instead and regenerate with either `./scripts/ask-self-ingest.sh --shared-index --mode all` (shared baseline) or `./scripts/ask-self-ingest.sh` writing to `ask_self/index/<repo>.sqlite` (portable)
- if an older repo only had local temp indexes and no committed DB, that is still valid; adding a committed mode is optional
- do not register any committed DB (shared or portable) in the multi-repo registry; registry entries are for local/full working indexes

## Future-Proofing

`bin/ask-self` already provides a `ask-self ask|ingest|register|dashboard|warm-cache` CLI internally, but external integrations still call the Python entry points directly so they can pass `--harness-config`. If ask-self ships a published CLI that accepts an explicit harness path (or `ASK_SELF_HARNESS` env), the migration is:

- keep local harness files
- keep local system instructions
- keep README and AGENTS guidance
- swap only the wrapper invocation layer

Structure the wrapper scripts to make this swap small and obvious.

## Deliverables Checklist

- [ ] `ask_self/ask_self_harness.json`
- [ ] `ask_self/ask_self_system_instructions.json`
- [ ] tracked `ask_self/index/` directory only if the repo uses shared baseline or portable mode
- [ ] committed DB at `ask_self/index/<repo>-shared.sqlite` (shared baseline) or `ask_self/index/<repo>.sqlite` (portable), with Git LFS configured when > ~100 MB
- [ ] `scripts/ask-self-ingest.sh`
- [ ] `scripts/ask-self-query.sh` — injects `--db-path` to the portable DB when portable mode is in use
- [ ] registration behavior is mode-correct: local/full working indexes register automatically unless disabled; committed shared/portable DBs never register
- [ ] `.gitignore` entries for ask-self artifacts (plus sidecars `*__embed_cache.sqlite`, `*__events.jsonl` everywhere)
- [ ] README section for ingest/query usage (covering credential mode: Gemini / hybrid / fully-local AND placement mode: local-only / shared / portable)
- [ ] `AGENTS.md` updated or created
- [ ] parallel agent files updated only if they already exist
- [ ] verification: list 5 to 10 sample files matched by the harness
- [ ] smoke test: run `./scripts/ask-self-ingest.sh --mode all` and report output or first failure
- [ ] **read the generated `ARCHITECTURE.md` and run the validation checklist** (see Architecture Doc Notes → "Validate the generated narrative") before declaring the integration complete

## Order of Operations

1. Detect repo kind and inventory files.
2. Ask about any ambiguities before finalizing:
   - repo kind, GitHub identity, PR ingestion
   - **credential mode**: Gemini / hybrid / fully-local
   - **index placement mode**: local-only (default) / shared baseline / portable — surface the size / privacy / staleness tradeoffs before defaulting to portable
3. Create the local harness and verify its patterns against real files.
4. Set `embedding.provider` / `synthesis.provider` per the chosen credential mode. For portable, force `embedding.provider = "qwen-local"`.
5. Configure the chosen index placement mode: `shared_index` block for shared baseline; harness `db_filename` + wrapper-injected `--db-path` for portable.
6. Set registration behavior for that mode: local/full working indexes register by default; shared baselines skip registry updates via `--shared-index`; portable committed DBs inject `--no-register`.
7. Add wrapper scripts and local system instructions. Portable mode: query wrapper injects `--db-path` to the committed DB and ingest injects `--no-register`.
8. Update `.gitignore` per the mode (ignore sidecars always; ignore `ask_self/index/*.sqlite` only in local-only mode).
9. Update README, including a mode-appropriate setup section and (portable) the "last ingested" line.
10. Update `AGENTS.md` and any existing parallel agent files.
11. Run an initial smoke test with `./scripts/ask-self-ingest.sh --mode all` so the generated `ARCHITECTURE.md` sees the full code+docs corpus, not just the default docs-only ingest path. For portable mode, also confirm `du -sh ask_self/index/` is reasonable and set up Git LFS if > ~100 MB before committing.

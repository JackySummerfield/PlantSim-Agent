# Roadmap — PlantSim-Agent

**Status:** v0.1.1 released · v0.2 in planning · Last updated: 2026-06-30

This roadmap describes **what** lands **when**. For functional detail see [`spec.md`](./spec.md); for the design decisions behind these features see [`architecture.md`](./architecture.md).

Releases follow [Semantic Versioning](https://semver.org/). `v0.x` releases are **pre-1.0** and may break public surfaces between minor versions, though we will document migrations.

---

## v0.1.x — Foundations ✅ shipped

**Theme:** make all three workflows usable end-to-end against a real Plant Simulation project, with citation-grounded answers.

### v0.1.0 — initial release (tag `v0.1.0`, 2026-06-30)

#### Phase 1 — Repository & specification scaffolding ✅
- [x] Directory skeleton, `.gitignore`, `.gitattributes`, `LICENSE`
- [x] `README.md`, `CHANGELOG.md`
- [x] `docs/spec.md`, `docs/architecture.md`, `docs/roadmap.md`
- [x] `docs/kb-build-guide.md` (end-to-end PDF → indexed KB procedure)
- [x] Self-authored references migrated into `kb_minimal/` (`simtalk-api-index.md`, `simtalk-syntax-quick-ref.md`, `modeling-standards.md`, `knowledge-base-map.md`)
- [x] Initial git commit

#### Phase 2 — MCP server (core capability) ✅
- [x] `pyproject.toml`, FastMCP entry, `uvx`-compatible packaging
- [x] `storage/base.py` abstract `Index` + `storage/sqlite.py` FTS5 implementation
- [x] Help indexer: `help_md_to_fts.py` for the markdown half; PDF→markdown lives in `scripts/convert_help_pdf.py` (markitdown + clean + code-tag) — deliberately kept outside the MCP package so the runtime stays light, see [`docs/kb-build-guide.md`](./kb-build-guide.md)
- [x] `.psfm` indexer: `psfm_parser.py` + `psfm_indexer.py` (objects, code_units, flow_edges, Origin-inheritance resolution)
- [x] MCP tools: `search_help`, `get_api`, `find_method`, `find_callers`, `get_object_graph`, `search_code`, `validate_simtalk` (regex rules ST001-ST004)
- [x] `pytest` suite covering each tool with fixture data (122 tests at v0.1.0; real-corpus smoke against a large-scale logistics `.psfm` project)
- [x] W3.1 chapter-aware `pts_help_fullmd` indexer (entry_name two-stage lookup; 4944 docs)
- [x] P0 `did_you_mean` suggestions on miss (storage layer + dict return shape for `get_api` / `find_method`)

#### Phase 3 — Agents and skills ✅
- [x] `agents/plantsim-copilot.agent.md` — orchestrator with intent routing + mandatory citation-review loop
- [x] `agents/citation-reviewer.agent.md` — anchor-first, JSON-verdict subagent (`user-invocable: false`)
- [x] `skills/plantsim-kb-qa/` — Q&A cascade with `**Sources:**` contract; refuses on miss
- [x] `skills/plantsim-code-author/` — Symbol-Lookup-Cascade + API-Evidence-Table + Refuse-to-Guess
- [x] `skills/plantsim-project-analyst/` — four sub-procedures (locate / trace / map / audit); Inheritance Audit always-on

#### Phase 4 — Installation, evaluation, documentation ✅
- [x] `scripts/install.ps1` — symlink agents into `~/.copilot/` (with Developer-Mode pre-check)
- [x] ~~`scripts/install.sh` (Linux/macOS parity)~~ — **skipped**: Plant Simulation is Windows-only, so a Linux/macOS install path has no closed loop (the agent has no value without the PS host)
- [x] `plantsim-copilot-mcp init` wizard (+ `scripts/build_kb.py` shim) — interactive & `--non-interactive` modes; writes `config.toml`, optional `--build` invokes existing indexers
- [x] Evaluation set: 20 Q&A questions with hand-graded ground truth (`tests/eval/qa_questions.yaml`, all 20 passing against `kb_minimal/`)
- [x] Citation-reviewer recall test: 10 deliberately uncited responses (`tests/eval/citation_recall.yaml`, all 10 passing against pure-Python regex port)
- [x] Cold-install test — `tests/cold_install/test_cold_install.py` (3 automated subprocess tests) + [`docs/cold-install.md`](./cold-install.md) (7-step manual gate for VS Code integration, including the MCP-server registration step filled in by `v0.1.0`)

#### Phase 5 — Public release ✅
- [x] GitHub repository public, tag `v0.1.0` (pushed 2026-06-30)
- [x] Release notes (`docs/release-notes/v0.1.0.md`) + announcement drafts (`docs/release-notes/v0.1.0-announcement.md`)
- [ ] **Announcement on Plant Simulation Community / LinkedIn / PSWiki** — still pending

### v0.1.1 — One-command MCP registration (tag `v0.1.1`, 2026-06-30) ✅

Quality-of-life patch addressing the v0.1.0 cold-install pain point (locate `mcp.json` per OS, hand-merge JSON without clobbering siblings, figure out the right `command` value).

- [x] **`plantsim-copilot-mcp register-vscode` subcommand** — locates VS Code's user-level `mcp.json` per OS, merges the `plantsim-copilot-mcp` entry idempotently, backs up the previous file before overwrite, refuses `--force`-less clobber
- [x] `install.ps1` calls `register-vscode` automatically at the end of symlink setup (non-fatal skip if the console script isn't on PATH yet)
- [x] README quick-start step 4 collapsed from a 30-line JSON snippet to one command; the manual JSON variant moved to [`docs/manual-mcp.md`](./manual-mcp.md)
- [x] Test count 122 → 141 (22 new tests for `register_vscode`)

### Post-v0.1.1 patches ✅

- [x] **kb-build-guide rewrite** (commit `816c260`) — new `scripts/convert_help_pdf.py` (markitdown + clean + code-tag pipeline); end-to-end procedure from PDF download to verified KB; docling kept as optional high-quality path
- [x] **Security fix: skills no longer symlinked globally** (commit `028a204`) — skills now live only in the repo and are loaded by the orchestrator via `read_file` from `~/.copilot/plantsim-agent/skills/`. Prevents skill-only invocations that would bypass the orchestrator's mandatory `citation-reviewer` dispatch. **Existing v0.1.0 installs still have stale skill symlinks under `~/.copilot/skills/plantsim-*`; harmless but cleanable with `scripts/uninstall.ps1`.**

---

## v0.2 — Quality

**Theme:** lift retrieval quality, tighten code validation, allow safe modifications.

- [ ] **`list_section(file_path)` MCP tool** — enumerate all `[SimTalk]` sub-entries inside an indexed help file
  - **Motivation:** v0.1 leaves a coverage gap for "list every API in *chapter X*" questions (e.g. *"What string functions does SimTalk provide?"*). `get_api` needs a name; `search_help` returns ranked snippets, not an exhaustive list. The agent's only recourse today is to bypass MCP and grep the raw markdown, which only works inside VS Code with the repo cloned — breaking the portability guarantee MCP exists to provide.
  - **Shape:** `list_section(file_path: str, kind: str = "simtalk") → [{entry_name, section, line}]`. Backed by the existing `docs_meta.entry_name` column, no re-indexing required.
  - **Acceptance:** Agent can answer *"List all string-manipulation functions"* using only MCP tool calls, with a `**Sources:**` block whose link targets are all verifiable against the index.
- [ ] **Vector retrieval** via the existing `Index` abstraction
  - Candidate stacks: `sentence-transformers` + `sqlite-vec`, or `lancedb`
  - Hybrid mode: BM25 candidates → embedding rerank
  - Decision recorded as ADR in `docs/decisions/`
- [ ] **Deeper `validate_simtalk`**
  - Tokeniser → minimal AST for the SimTalk subset
  - Catches: undeclared variables, type mismatches, unreachable branches
  - Replaces v0.1 regex rules (regex rules kept as a fallback)
- [ ] **`.psfm` write-back**
  - YAML round-trip safety (preserve comments, formatting, key order)
  - Mandatory git-clean or backup precondition
  - New MCP tool: `apply_patch(file, patch)` and `replace_method_body(path, new_body)`
  - Any generated SimTalk must carry the W2-style **API Evidence Table** — same `citation-reviewer` contract (no architecture change; reviewer already covers W3 from v0.1)
- [ ] **Call-graph Mermaid output** for `get_object_graph`

---

## v0.3 — Reach

**Theme:** broader audience, lower friction.

- [ ] **Non-Copilot model backends** — for users who want to point the agent at OpenAI / Anthropic / Azure / local Ollama with their own keys (likely requires forking to a non-Copilot agent runtime such as Cline or custom CLI)
- [ ] **VS Code extension packaging** — ship agents + skills + MCP wiring as a single `.vsix`
- [ ] **Cross-version Help support** — explicit version tagging so a user can have multiple Plant Simulation versions (2404, 2504, 2604) indexed side-by-side
- [ ] **Community templates** — a `templates/` library of common modelling patterns (shift logger, throughput collector, AGV dispatcher) contributed by the community

---

## v1.0 criteria

`v1.0` is reached when:

1. End-to-end install on a clean machine takes ≤ 5 minutes.
2. KB Q&A benchmark ≥ 90 % on a 50-question set across all three workflows.
3. No known data-loss bugs in `.psfm` write-back.
4. At least one external contributor (not the original author) has merged a non-trivial PR.
5. The public README has been reviewed by ≥ 3 practising Plant Simulation engineers.

---

## Things we are deliberately not promising

- A web UI or hosted SaaS version
- Real-time call-graph editing inside Plant Simulation
- Auto-generation of full Plant Simulation models from text descriptions (the W2 scope stops at SimTalk snippets and methods, not whole-model authoring)
- 3D layout / animation generation

# Roadmap — PlantSim-Agent

**Status:** Draft v0.1 · Last updated: 2026-06-29

This roadmap describes **what** lands **when**. For functional detail see [`spec.md`](./spec.md); for the design decisions behind these features see [`architecture.md`](./architecture.md).

Releases follow [Semantic Versioning](https://semver.org/). `v0.x` releases are **pre-1.0** and may break public surfaces between minor versions, though we will document migrations.

---

## v0.1 — Foundations (current release in progress)

**Theme:** make all three workflows usable end-to-end against a real Plant Simulation project, with citation-grounded answers.

### Phase 1 — Repository & specification scaffolding ✅ in progress
- [x] Directory skeleton, `.gitignore`, `.gitattributes`, `LICENSE`
- [x] `README.md`, `CHANGELOG.md`
- [x] `docs/spec.md`, `docs/architecture.md`, `docs/roadmap.md`
- [ ] `docs/kb-build-guide.md` (stub for v0.1; full procedure when indexer lands)
- [ ] Migrate self-authored references from existing skill into `kb_minimal/`
- [ ] Initial git commit

### Phase 2 — MCP server (core capability)
- [x] `pyproject.toml`, FastMCP entry, `uvx`-compatible packaging
- [x] `storage/base.py` abstract `Index` + `storage/sqlite.py` FTS5 implementation
- [ ] Help indexer: `help_pdf_to_md.py` (markitdown), `help_md_to_fts.py` ([x] md→fts; [ ] pdf→md)
- [ ] `.psfm` indexer: `psfm_parser.py`, `psfm_indexer.py` with caller graph
- [x] MCP tools: `search_help`, `get_api`, `find_method`, `find_callers`, `get_object_graph`, `search_code`, `validate_simtalk` (regex-level rules: ST001-ST004)
- [x] `pytest` suite covering each tool with fixture data (110 tests, real-corpus smoke against `TCDC_KongMing_PS2504.psfm`)
- [x] W3.1 chapter-aware `pts_help_fullmd` indexer (entry_name two-stage lookup; 4944 docs)
- [x] P0 `did_you_mean` suggestions on miss (storage layer + dict return shape for `get_api` / `find_method`)

### Phase 3 — Agents and skills
- [x] `agents/plantsim-copilot.agent.md` — orchestrator with intent routing + mandatory citation-review loop
- [x] `agents/citation-reviewer.agent.md` — anchor-first, JSON-verdict subagent (`user-invocable: false`)
- [x] `skills/plantsim-kb-qa/` — Q&A cascade with `**Sources:**` contract; refuses on miss
- [x] `skills/plantsim-code-author/` — Symbol-Lookup-Cascade + API-Evidence-Table + Refuse-to-Guess
- [x] `skills/plantsim-project-analyst/` — four sub-procedures (locate / trace / map / audit); Inheritance Audit always-on

### Phase 4 — Installation, evaluation, documentation
- [x] `scripts/install.ps1` — symlink agents & skills into `~/.copilot/` (with Developer-Mode pre-check)
- [ ] `scripts/install.sh` (Linux/macOS parity)
- [x] `plantsim-copilot-mcp init` wizard (+ `scripts/build_kb.py` shim) — interactive & `--non-interactive` modes; writes `config.toml`, optional `--build` invokes existing indexers
- [x] Evaluation set: 20 Q&A questions with hand-graded ground truth (`tests/eval/qa_questions.yaml`, all 20 passing against `kb_minimal/`)
- [x] Citation-reviewer recall test: 10 deliberately uncited responses (`tests/eval/citation_recall.yaml`, all 10 passing against pure-Python regex port)
- [x] Cold-install test — `tests/cold_install/test_cold_install.py` (3 automated subprocess tests) + [`docs/cold-install.md`](./cold-install.md) (7-step manual gate for VS Code integration)

### Phase 5 — Public release
- [ ] GitHub repository public, tag `v0.1.0`
- [ ] Release notes
- [ ] Announcement on Plant Simulation Community / LinkedIn / PSWiki

---

## v0.2 — Quality

**Theme:** lift retrieval quality, tighten code validation, allow safe modifications.

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

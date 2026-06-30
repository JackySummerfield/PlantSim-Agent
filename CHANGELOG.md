# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

<!-- 日常 push 到 main 的改动写在这里，攒够一个里程碑再打 tag 发 release -->

### Added
- `list_section` MCP tool — enumerate help KB entries by chapter/kind/query filters
- `smart_lookup` MCP tool — one-shot cascade (exact → suggestion → FTS) replaces
  the multi-call `get_api` → `search_help` pattern. Credit cost ~80% lower.
- `scripts/convert_help_pdf.py` — all-in-one PDF→markdown conversion (markitdown + clean + code-tag)

### Changed
- `plantsim-kb-qa` skill: cascade rewritten to use `smart_lookup` (1–2 calls) instead
  of manual `get_api` → `search_help` loop (5–10 calls)
- `install.ps1`: skills no longer symlinked to `~/.copilot/skills/` (security fix —
  prevents bypassing citation-reviewer by invoking skills directly)
- `docs/kb-build-guide.md`: rewritten with end-to-end procedure from PDF download to KB
- Orchestrator agent: skill path updated to `~/.copilot/plantsim-agent/skills/`

### Fixed
- Removed broken `/memories/doc-conversion-lessons.md` link from kb-build-guide

## [0.1.1] - 2026-06-30

QoL patch release. Reduces the cold-install path from "edit `mcp.json`
by hand" to a single `plantsim-copilot-mcp register-vscode` command —
called automatically by `install.ps1`. No breaking changes; the
manual JSON config is still supported and documented.

### Added
- `plantsim-copilot-mcp register-vscode` subcommand
  ([`mcp/plantsim_mcp/register_vscode.py`](mcp/plantsim_mcp/register_vscode.py))
  — discovers VS Code's user-level `mcp.json` per OS (Windows
  `%APPDATA%\Code\User`, macOS `~/Library/Application Support/Code/User`,
  Linux `~/.config/Code/User`), idempotently merges the
  `plantsim-copilot-mcp` server entry without clobbering siblings,
  and creates a timestamped `.bak-*` backup before overwriting.
  Flags: `--target <path>`, `--command <abs-path>`, `--absolute`,
  `--force`, `--dry-run`. Exit code 2 on a conflict-without-force so
  CI / install scripts can detect the case.
- `scripts/install.ps1` — now calls `plantsim-copilot-mcp register-vscode`
  at the end of its symlink setup if the console-script is on `PATH`;
  prints a non-fatal hint when it isn't (typical first-run before
  `pip install -e mcp/`).
- [`docs/manual-mcp.md`](docs/manual-mcp.md) — fallback page for users
  who need to edit `mcp.json` by hand (corporate VS Code variants,
  custom user data dirs, project-level `.vscode/mcp.json`, etc.).
- 22 new unit tests in
  [`mcp/tests/test_register_vscode.py`](mcp/tests/test_register_vscode.py)
  covering per-OS path discovery, PATH lookup with absolute-path
  fallback, fresh-write / merge-into-existing / idempotent re-run /
  conflict-without-force / `--force` overwrite / dry-run / malformed
  JSON. Test count: 119 → 141.

### Changed
- `README.md` and `README.en.md` — quick-start step 4 collapsed from
  ~30 lines of manual JSON snippet to a single `register-vscode`
  command, with the manual variant linked out to `docs/manual-mcp.md`.

## [0.1.0] - 2026-06-29

First public release. Covers KB Q&A, SimTalk code authoring, and read-only `.psfm` project analysis with mandatory citation auditing.

### Added
#### Phase 2 — W2 `.psfm` indexer + project tools (commit `e2b94f8`)
- `plantsim_mcp.indexers.psfm_indexer` — walks `.psfm` folder, parses YAML object/method definitions, resolves `Origin` inheritance chains, extracts `flow_edges` from `Predecessor`/`Successor` references
- `plantsim_mcp.storage.project.ProjectStore` — SQLite schema with `objects`, `code_units` (FTS5 over SimTalk bodies), and `flow_edges` tables
- MCP tools: `find_method` (returns parent + overriding children), `find_callers` (identifier-aware FTS), `search_code` (free-text FTS over SimTalk), `get_object_graph` (inheritance + material-flow neighbourhood)
- `plantsim-copilot-mcp build-project --psfm <path>` CLI subcommand

#### Phase 2 — W3 `validate_simtalk` + `get_api` + build-kb CLI (commit `6ecfdd0`)
- `plantsim_mcp.validators.simtalk_rules` — first regex rule pack: `ST001` (.move() ignored, warning), `ST002` (untyped locals → `any`, info), `ST003` (undeclared loop var, warning), `ST004` (column-number table access, info)
- MCP tool: `validate_simtalk(source=..., uuid=..., ignore_rules=...)` — lints inline source or an indexed Method body
- MCP tool: `get_api(name, top_k)` — precise lookup by section title (`<Name> [SimTalk]`)
- `plantsim-copilot-mcp build-kb --root <dir>` CLI — multi-root markdown indexer (kb_minimal + kb_local merged)

#### Phase 2 — W3.1 chapter-aware fullmd indexer (commit `2ca244e`)
- `plantsim_mcp.indexers.pts_help_fullmd_indexer` — handles the H5/H6 entry pattern inside `pts_help_2504_fullmd/ChXX.md`, extracts a structured `entry_name` per section (`Stop`, `Capacity`, `Active`…)
- `docs_meta.entry_name TEXT COLLATE NOCASE` schema column + index; auto-migrates legacy DBs via `_migrate_add_entry_name`
- `SQLiteFTSIndex.find_by_section()` now does a two-stage lookup: exact `entry_name` match → LIKE prefix fallback, so `get_api("Capacity")` returns the `[text box]` UI control even though the LIKE pattern targets `[SimTalk]`
- `build-kb --fullmd-src --chapters` CLI flags; default chapters `(11, 12, 13, 15)`
- `Config.paths.fullmd_src` + `fullmd_chapters` config fields
- Real corpus grew from 625 → 4944 docs (4319 fullmd entries, 3014 distinct `entry_name`s)

#### P0 — `did_you_mean` suggestions + kb-qa cascade skill (commit `325951e`)
- `SQLiteFTSIndex.suggest_entry_names(query, limit)` — two-stage: case-insensitive prefix LIKE → `difflib.get_close_matches` fuzzy fallback
- `ProjectStore.suggest_object_names(query, class_type, limit)` — same shape, optionally class-filtered
- `get_api` and `find_method` return shape changed to `dict` `{query, hits, did_you_mean}`; `did_you_mean` populated only when `hits == []`
- New skill `skills/plantsim-kb-qa/SKILL.md` — mandatory cascade `get_api → did_you_mean retry → search_help → REFUSE`, with a Sources contract and a hard-rule against training-data answers
- Test count: 81 → 110 (added: psfm indexer/tools, fullmd indexer, validator, get_api real-corpus, suggestion fallbacks)

#### Phase 3 — Skills (commit `c0d1d87`)
- `skills/plantsim-code-author/SKILL.md` — Symbol-Lookup-Cascade via MCP, always-on rules (10 mandatory + 11 anti-patterns), API Evidence Table contract, Refuse-to-Guess hard stop with cascade trace
- `skills/plantsim-project-analyst/SKILL.md` — read-only project analysis with four sub-procedures (Locate / Trace / Map / Audit) and always-on Inheritance Audit

#### Phase 3 — Agents
- `agents/citation-reviewer.agent.md` — read-only subagent (`user-invocable: false`). Regex anchor checks per workflow (W1 `**Sources:**`, W2 `API Evidence Table`, W3 file-path links), forbidden-source phrase scan, Refuse-to-Guess discipline check. Returns a single JSON verdict (`ok` / `missing_citations` / `suspicious_citations` / `malformed_refusal`).
- `agents/plantsim-copilot.agent.md` — user-facing orchestrator (`user-invocable: true`). Intent routing to the correct skill, mandatory citation-reviewer dispatch after every skilled reply, failure-mode escape hatches for missing indexes and refused answers. Tools: `search`, `edit`, `agent`, `plantsim-copilot-mcp/*`.

#### Phase 4 — `init` wizard for KB build / config
- `plantsim_mcp.build_kb_wizard` — interactive setup that gathers KB roots, optional PTS Help fullmd source + chapter list, default `.psfm` project, and index output directory, then writes `~/.plantsim-agent/config.toml` (hand-rolled TOML — stdlib `tomllib` is read-only)
- New CLI subcommand `plantsim-copilot-mcp init` (registered alongside `serve` / `build-kb` / `build-project`). Supports `--non-interactive` with a full flag set (`--kb-root` repeatable, `--fullmd-src`, `--chapters`, `--project`, `--index-dir`, `--config`, `--force`, `--build`) so cold-install and CI can drive it unattended.
- `scripts/build_kb.py` — repo-clone shim that imports the same wizard; runs without `pip install -e mcp/`.
- 9 new tests in `tests/test_build_kb_wizard.py` covering TOML render/round-trip, `--non-interactive` minimal / full / custom-config-path / custom-index-dir / `--build` paths, and rejection of missing `--kb-root`. Test count: 110 → 119.
- README quick-start updated; `docs/kb-build-guide.md` rewritten to document Option A (interactive + non-interactive) as the supported path.

#### Phase 4 — Evaluation suites
- `tests/eval/qa_questions.yaml` — 20 hand-written natural-language questions; each entry pins the expected `file_path` (and optionally `section`) substrings that the underlying MCP tool must surface in the top-K hits. All 20 pass against an isolated index built from `kb_minimal/`.
- `tests/eval/citation_recall.yaml` — 10 fixture response bodies covering the four reviewer verdicts across W1 / W2 / W3 workflows (anchor-OK / missing / suspicious-phrase / malformed-refusal).
- `tests/eval/run_eval.py` — pure-Python runner. (1) Builds an isolated `help.db` from `kb_minimal/`, then calls `search_help` / `get_api` directly and scores recall. (2) Implements the citation-reviewer's regex contract in `review()` and grades each fixture. Importable so tests can call `run_qa_suite()` / `run_citation_suite()` and assert.
- `tests/eval/test_eval_pytest.py` + `tests/eval/conftest.py` — opt-in pytest wrapper gated on `--run-eval`. The unit-test suite (`pytest mcp/`) stays at 119 passing and is unaffected.
- Current score: **20/20 QA + 10/10 citation = 30/30 green**.

#### Phase 4 — Cold-install verification
- `tests/cold_install/test_cold_install.py` — 3 subprocess-based smoke tests, each under a fresh `PLANTSIM_AGENT_HOME` tmp dir:
  1. `plantsim-copilot-mcp init --non-interactive --kb-root <kb_minimal> --build` produces a valid `config.toml` + `help.db` with ≥ 50 indexed docs and the config is round-trippable through `config.load()`.
  2. `plantsim-copilot-mcp serve` boots and survives a brief idle window — proxy for "imports clean, FastMCP initialised, no missing deps".
  3. Without `--force`, re-running `init --non-interactive` against an existing config exits non-zero and does NOT overwrite (regression guard against silent config loss in CI / cold installs).
- **Fix uncovered by test #3**: `build_kb_wizard.cmd_init()` now refuses to overwrite an existing config in `--non-interactive` mode unless `--force` is set, returning exit code 2. Previously non-interactive mode silently clobbered any pre-existing config.
- `docs/cold-install.md` — 7-step manual gate for the parts an in-process test cannot cover: fresh venv, `pip install -e mcp/`, VS Code agent discovery, citation-reviewer dispatch on a real Copilot turn. Run before tagging each release.
- Test count: 119 → 122 (3 cold-install tests added).

### Changed
- `mcp/plantsim_mcp/server.py` — return type hints + docstrings updated for `get_api`/`find_method` dict shape
- `mcp/scripts/smoke_psfm.py` — parameterised via `$PLANTSIM_SMOKE_PROJECT` / CLI args (no hard-coded paths); adapted to new dict return shapes. Verified on a large logistics `.psfm` model (25,463 objects, 7,698 edges, 4 real SimTalk lint issues found).
- Repository relocated out of OneDrive to `~/.copilot/plantsim-agent/` to avoid cloud-sync corruption of `.git/`
- `.gitignore` rewritten: removed stale `pts_ai/` references; added `kb_local/*` rule

### Fixed
- Schema-migration ordering bug — `CREATE INDEX idx_meta_entry_name` had been declared inside `_SCHEMA` and ran before `ALTER TABLE ADD COLUMN entry_name` on legacy DBs (`sqlite3.OperationalError: no such column`). Index creation now lives inside `_migrate_add_entry_name()` after the ALTER.

### Phase 1 baseline (initial scaffolding, commit `21b3654`)
- Directory skeleton, `.gitignore`, `.gitattributes`, MIT `LICENSE`
- `README.md` (bilingual zh/en), spec/architecture/roadmap docs
- `kb_minimal/` self-authored sample KB
- `kb_local/` placeholder + gitignored
- `scripts/install.ps1` / `uninstall.ps1` — symlink agents & skills into `~/.copilot/`
- MCP server skeleton: FastMCP entry `plantsim-copilot-mcp`, `Config` loader, `Index` ABC + SQLite FTS5 implementation, `help_md_to_fts` indexer, `search_help` tool, 23 baseline tests

[Unreleased]: https://github.com/JackySummerfield/plantsim-agent/compare/HEAD


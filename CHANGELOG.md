# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

### Changed
- `mcp/plantsim_mcp/server.py` — return type hints + docstrings updated for `get_api`/`find_method` dict shape
- `mcp/scripts/smoke_psfm_kongming.py` — adapted to new dict return shapes; verified against real `TCDC_KongMing_PS2504.psfm` (25,463 objects, 7,698 edges, 4 real SimTalk lint issues found in `InitPalletJackFleet`)
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


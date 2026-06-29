# plantsim-copilot-mcp

The Python MCP server that backs **[PlantSim-Agent](../README.md)**. See [`../docs/architecture.md`](../docs/architecture.md) for the big picture.

## What's in this package

| Module | Role |
|--------|------|
| `plantsim_mcp.server` | FastMCP entry point — `plantsim-copilot-mcp` console script with `init` / `serve` / `build-kb` / `build-project` subcommands |
| `plantsim_mcp.config` | TOML config loader (`~/.plantsim-agent/config.toml`) |
| `plantsim_mcp.build_kb_wizard` | Interactive + `--non-interactive` setup wizard backing `plantsim-copilot-mcp init` |
| `plantsim_mcp.storage.base` | `Index` abstract base class — seam for v0.2 vector store |
| `plantsim_mcp.storage.sqlite` | SQLite + FTS5 implementation (v0.1) |
| `plantsim_mcp.storage.project` | `.psfm` project store (objects, code_units, flow_edges) |
| `plantsim_mcp.indexers.help_md_to_fts` | Walk a markdown KB, split by `##`/`###`, write to an `Index` |
| `plantsim_mcp.indexers.pts_help_fullmd_indexer` | Chapter-aware indexer for `pts_help_2504_fullmd/ChXX.md` |
| `plantsim_mcp.indexers.psfm_indexer` | Walk a `.psfm` folder, resolve inheritance, extract flow edges |
| `plantsim_mcp.tools.search_help` | W1 — Documentation Q&A |
| `plantsim_mcp.tools.get_api` | W1 — Precise SimTalk API lookup with `did_you_mean` |
| `plantsim_mcp.tools.find_method` / `find_callers` / `search_code` / `get_object_graph` | W3 — `.psfm` project analysis |
| `plantsim_mcp.tools.validate_simtalk` | W2 — SimTalk lint (ST001-ST004) |

## Dev install

```powershell
cd mcp
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

## Run the server (stdio)

```powershell
plantsim-copilot-mcp
```

The server reads `~/.plantsim-agent/config.toml` for KB / index paths. You can point it elsewhere with the `PLANTSIM_AGENT_HOME` environment variable — useful for tests and dev setups.

## Build the help index

```toml
# ~/.plantsim-agent/config.toml
[paths]
help_kb_roots = [
    "C:/Users/me/.copilot/plantsim-agent/kb_minimal",
    "C:/Users/me/.copilot/plantsim-agent/kb_local/pts_help_2504",
]
index_dir = "C:/Users/me/.plantsim-agent/indices"
```

```powershell
plantsim-copilot-mcp init --non-interactive --kb-root ../kb_minimal --build
```

See [`../docs/kb-build-guide.md`](../docs/kb-build-guide.md) for the full wizard reference (interactive + flag-driven modes).

## Roadmap

v0.1.0 ships all seven planned MCP tools. v0.2 will lift retrieval quality (vector + hybrid rerank) and add `.psfm` write-back with mandatory citation auditing. See [`../docs/roadmap.md`](../docs/roadmap.md).

# plantsim-copilot-mcp

The Python MCP server that backs **[PlantSim-Agent](../README.md)**. See [`../docs/architecture.md`](../docs/architecture.md) for the big picture.

## What's in this package

| Module | Role |
|--------|------|
| `plantsim_mcp.server` | FastMCP entry point — `plantsim-copilot-mcp` console script |
| `plantsim_mcp.config` | TOML config loader (`~/.plantsim-agent/config.toml`) |
| `plantsim_mcp.storage.base` | `Index` abstract base class — seam for v0.2 vector store |
| `plantsim_mcp.storage.sqlite` | SQLite + FTS5 implementation (v0.1) |
| `plantsim_mcp.indexers.help_md_to_fts` | Walk a markdown KB, split by `##`/`###`, write to an `Index` |
| `plantsim_mcp.tools.search_help` | W1 — Documentation Q&A search tool |

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

## Roadmap

This package is being built incrementally; see [`../docs/roadmap.md`](../docs/roadmap.md). The v0.1 slice currently committed covers only `search_help`; the remaining tools (`get_api`, `find_method`, `find_callers`, `get_object_graph`, `search_code`, `validate_simtalk`) land in subsequent commits.

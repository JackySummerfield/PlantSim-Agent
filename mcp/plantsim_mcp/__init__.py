"""plantsim-mcp — MCP server for PlantSim-Agent.

This package exposes tools that an MCP-aware client (e.g. GitHub Copilot)
can use to search a locally-indexed Plant Simulation Help knowledge base
and to query a user's `.psfm` project.

Public surface is intentionally small — most code lives behind
`server.main`, which `pyproject.toml` exposes as the `plantsim-copilot-mcp`
console script.
"""

__version__ = "0.1.0"

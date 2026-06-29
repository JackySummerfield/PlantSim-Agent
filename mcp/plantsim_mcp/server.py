"""FastMCP server entry point.

This module is what ``pyproject.toml``'s ``plantsim-copilot-mcp``
console script invokes. It wires the (currently small) set of tools
into a :class:`FastMCP` instance and runs it on stdio.

The server is *thin*: every tool's logic lives in
``plantsim_mcp.tools.<name>``, and this module is only responsible for
schema registration. Keeping it thin makes the tool functions trivial
to unit-test without bringing FastMCP into the test loop.
"""

from __future__ import annotations

from typing import Any

from . import __version__
from .config import Config, load
from .tools import search_help as _search_help


def build_server(config: Config | None = None) -> Any:
    """Construct (but do not run) the FastMCP server.

    The function lazily imports :mod:`fastmcp` so that test code and
    one-off scripts can import :mod:`plantsim_mcp.server` without
    requiring FastMCP to be installed.
    """
    from fastmcp import FastMCP  # type: ignore[import-not-found]

    cfg = config or load()
    mcp = FastMCP(name="plantsim-copilot-mcp", version=__version__)

    @mcp.tool()
    def search_help(query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Search the local PTS Help knowledge base (FTS5).

        Args:
            query: Natural-language question or keyword phrase.
            top_k: Maximum number of results (default 5).
        """
        return _search_help.search_help(query=query, top_k=top_k, config=cfg)

    return mcp


def main() -> None:
    """Console-script entry point — runs the server on stdio."""
    server = build_server()
    server.run()


if __name__ == "__main__":  # pragma: no cover
    main()

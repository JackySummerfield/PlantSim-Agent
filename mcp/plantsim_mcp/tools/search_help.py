"""``search_help`` MCP tool — natural-language Q&A over the indexed KB.

This is the W1 (Documentation Q&A) entry point. The tool opens the
SQLite help index at the path resolved from
:mod:`plantsim_mcp.config`, runs an FTS5 search, and returns
serialisable hit records suitable for the agent to render with
citations.
"""

from __future__ import annotations

from typing import Any

from ..config import Config, load
from ..storage.sqlite import SQLiteFTSIndex


def search_help(query: str, top_k: int = 5, config: Config | None = None) -> list[dict[str, Any]]:
    """Search the help knowledge base.

    Parameters
    ----------
    query:
        Natural-language query (e.g. ``"Buffer numMU on blocked station"``).
    top_k:
        Maximum number of hits to return. Defaults to 5.
    config:
        Optional pre-loaded :class:`~plantsim_mcp.config.Config`. When
        omitted the function loads from the default location each call;
        the server passes a cached config to avoid re-parsing.

    Returns
    -------
    list of dict
        Each item has keys ``file_path``, ``section``, ``snippet``,
        ``score``. The agent uses ``file_path`` + ``section`` to build
        the ``**Sources:**`` citation block; ``snippet`` is highlighted
        with ``[[...]]`` around matched terms.

    Raises
    ------
    FileNotFoundError
        If the help index does not exist yet (user has not run
        ``build_kb``). Tool callers should surface this with the
        ``kb-build-guide.md`` link rather than a generic error.
    """
    cfg = config or load()
    db_path = cfg.paths.help_db
    if not db_path.exists():
        raise FileNotFoundError(
            f"Help index not found at {db_path}. "
            "Run `plantsim-copilot-mcp build-kb` to create it. "
            "See docs/kb-build-guide.md."
        )

    if top_k <= 0:
        return []

    with SQLiteFTSIndex(db_path) as idx:
        hits = idx.search(query, top_k=top_k)

    return [
        {
            "file_path": h.file_path,
            "section": h.section,
            "snippet": h.snippet,
            "score": h.score,
        }
        for h in hits
    ]

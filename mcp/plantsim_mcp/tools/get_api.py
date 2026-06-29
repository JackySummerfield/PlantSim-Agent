"""``get_api`` MCP tool — precise SimTalk API lookup.

Where :func:`~plantsim_mcp.tools.search_help.search_help` runs a
natural-language FTS5 query (good for "how do I…?"), this tool is the
short answer to "what does ``<Name>`` do?". It scans the help index's
``section`` column for entries titled ``<Name> [SimTalk]`` and returns
them in order of section length so ``Active [SimTalk]`` outranks the
disambiguated ``Active [SimTalk] - fluid objects`` variants.
"""

from __future__ import annotations

from typing import Any

from ..config import Config, load
from ..storage.sqlite import SQLiteFTSIndex


def get_api(name: str, top_k: int = 5, config: Config | None = None) -> list[dict[str, Any]]:
    """Look up a SimTalk identifier in the help knowledge base.

    Parameters
    ----------
    name:
        The SimTalk identifier (case-sensitive, no qualifier). E.g.
        ``"move"``, ``"Buffer"``, ``"StatNumOut"``.
    top_k:
        Maximum results (default 5). Multiple results are common —
        e.g. ``Active`` has variants per object class.
    config:
        Optional pre-loaded :class:`~plantsim_mcp.config.Config`.

    Returns
    -------
    list of dict
        Each entry: ``file_path``, ``section``, ``snippet`` (first ~240
        chars of the section body). Empty when nothing matches.

    Raises
    ------
    FileNotFoundError
        If the help index has not been built.
    """
    cfg = config or load()
    db_path = cfg.paths.help_db
    if not db_path.exists():
        raise FileNotFoundError(
            f"Help index not found at {db_path}. "
            "Run `plantsim-copilot-mcp build-kb` to create it."
        )

    if not name.strip() or top_k <= 0:
        return []

    with SQLiteFTSIndex(db_path) as idx:
        hits = idx.find_by_section(name, top_k=top_k)

    return [
        {
            "file_path": h.file_path,
            "section": h.section,
            "snippet": h.snippet,
        }
        for h in hits
    ]

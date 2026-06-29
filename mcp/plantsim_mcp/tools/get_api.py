"""``get_api`` MCP tool — precise SimTalk API lookup.

Where :func:`~plantsim_mcp.tools.search_help.search_help` runs a
natural-language FTS5 query (good for "how do I…?"), this tool is the
short answer to "what does ``<Name>`` do?". It scans the help index's
``section`` column for entries titled ``<Name> [SimTalk]`` and returns
them in order of section length so ``Active [SimTalk]`` outranks the
disambiguated ``Active [SimTalk] - fluid objects`` variants.

When no exact entry matches, the tool falls back to
:meth:`~plantsim_mcp.storage.sqlite.SQLiteFTSIndex.suggest_entry_names`
to populate ``did_you_mean`` so the calling LLM has a concrete next
step instead of guessing from training data.
"""

from __future__ import annotations

from typing import Any

from ..config import Config, load
from ..storage.sqlite import SQLiteFTSIndex


def get_api(
    name: str, top_k: int = 5, config: Config | None = None
) -> dict[str, Any]:
    """Look up a SimTalk identifier in the help knowledge base.

    Parameters
    ----------
    name:
        The SimTalk identifier (case-insensitive). E.g. ``"move"``,
        ``"Buffer"``, ``"StatNumOut"``.
    top_k:
        Maximum exact hits (default 5). Multiple results are common —
        e.g. ``Active`` has variants per object class.
    config:
        Optional pre-loaded :class:`~plantsim_mcp.config.Config`.

    Returns
    -------
    dict
        ``{"query": str, "hits": list[dict], "did_you_mean": list[str]}``.

        * ``hits`` — each item ``{"file_path", "section", "snippet"}``
          (snippet is the first ~240 chars of the section body). Empty
          when nothing matches.
        * ``did_you_mean`` — populated **only when** ``hits`` is empty;
          up to 5 nearby entry names (prefix + fuzzy). Empty list when
          we genuinely have nothing to offer.

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
        return {"query": name, "hits": [], "did_you_mean": []}

    with SQLiteFTSIndex(db_path) as idx:
        hits = idx.find_by_section(name, top_k=top_k)
        suggestions: list[str] = []
        if not hits:
            suggestions = idx.suggest_entry_names(name, limit=5)

    return {
        "query": name,
        "hits": [
            {
                "file_path": h.file_path,
                "section": h.section,
                "snippet": h.snippet,
            }
            for h in hits
        ],
        "did_you_mean": suggestions,
    }

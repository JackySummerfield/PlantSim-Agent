"""``list_section`` MCP tool — enumerate entries in the help index.

Complements :func:`~plantsim_mcp.tools.get_api.get_api` (which needs an
exact name) and :func:`~plantsim_mcp.tools.search_help.search_help`
(which returns ranked snippets, not exhaustive lists).

``list_section`` answers the "list all X" class of questions:

* "What string functions does SimTalk provide?"
* "List all attributes of the Buffer object"
* "Show me every [SimTalk] entry in chapter 12"

It queries the ``docs_meta`` table (``entry_name`` / ``section`` /
``file_path`` columns) and returns a compact list of entries that match
the given ``file_path`` prefix and optional ``kind`` filter.
"""

from __future__ import annotations

from typing import Any

from ..config import Config, load
from ..storage.sqlite import SQLiteFTSIndex


def list_section(
    file_path: str = "",
    kind: str = "",
    query: str = "",
    top_k: int = 200,
    config: Config | None = None,
) -> dict[str, Any]:
    """List entries in the help index matching the given filters.

    Parameters
    ----------
    file_path:
        Prefix filter on ``docs_meta.file_path``. E.g. ``"Ch12"`` to
        list everything from chapter 12. Empty string means no filter.
    kind:
        Bracket-tag filter on ``docs_meta.section``. E.g. ``"SimTalk"``
        to only return entries whose section contains ``[SimTalk]``.
        Common values: ``"SimTalk"``, ``"text box"``, ``"drop-down list"``.
        Empty string means no filter.
    query:
        Optional substring filter on ``entry_name`` (case-insensitive).
        E.g. ``"str"`` to find string-related functions. Empty means all.
    top_k:
        Maximum number of results (default 200). Increase if you need
        an exhaustive list of a large chapter.
    config:
        Optional pre-loaded :class:`~plantsim_mcp.config.Config`.

    Returns
    -------
    dict
        ``{"filters": {...}, "count": int, "entries": [...]}``.

        * ``entries`` — each item ``{"entry_name", "section", "file_path"}``,
          sorted alphabetically by ``entry_name``.
        * ``count`` — total matching entries (may exceed ``top_k``; in
          that case, ``entries`` is truncated and the caller knows to
          narrow down).

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

    with SQLiteFTSIndex(db_path) as idx:
        conn = idx._require_conn()

        # Build query dynamically
        conditions: list[str] = ["entry_name IS NOT NULL"]
        params: list[Any] = []

        if file_path.strip():
            conditions.append("file_path LIKE ?")
            params.append(f"%{file_path.strip()}%")

        if kind.strip():
            conditions.append("section LIKE ?")
            params.append(f"%[{kind.strip()}]%")

        if query.strip():
            conditions.append("entry_name LIKE ? COLLATE NOCASE")
            params.append(f"%{query.strip()}%")

        where_clause = " AND ".join(conditions)

        # Get total count
        count_sql = f"SELECT COUNT(*) FROM docs_meta WHERE {where_clause}"
        total = conn.execute(count_sql, params).fetchone()[0]

        # Get entries
        select_sql = (
            f"SELECT DISTINCT entry_name, section, file_path "
            f"FROM docs_meta WHERE {where_clause} "
            f"ORDER BY entry_name COLLATE NOCASE, length(section) "
            f"LIMIT ?"
        )
        cur = conn.execute(select_sql, params + [top_k])
        entries = [
            {
                "entry_name": row[0],
                "section": row[1],
                "file_path": row[2],
            }
            for row in cur.fetchall()
        ]

    return {
        "filters": {
            "file_path": file_path or None,
            "kind": kind or None,
            "query": query or None,
        },
        "count": total,
        "entries": entries,
    }

"""``search_code`` MCP tool — full-text search over SimTalk bodies.

Thin wrapper around :meth:`ProjectStore.search_code`. Use this when
``find_method`` / ``find_callers`` are too name-specific and the user
wants to grep, e.g. "every method that writes to ``FleetResults``" or
"every method using ``str_to_obj``".
"""

from __future__ import annotations

from typing import Any

from ..config import Config
from ._project_common import open_project_store


def search_code(
    query: str,
    top_k: int = 20,
    config: Config | None = None,
) -> list[dict[str, Any]]:
    """Full-text search the SimTalk corpus.

    Parameters
    ----------
    query:
        FTS5 phrase or keyword. Punctuation in user input is escaped
        by the underlying store; tokens are AND-combined.
    top_k:
        Maximum hits to return (default 20).
    config:
        Optional pre-loaded :class:`~plantsim_mcp.config.Config`.

    Returns
    -------
    list of dict
        Each entry: ``uuid``, ``name``, ``class_type``, ``file_path``,
        ``doc_index``, ``snippet`` (BM25-ranked), ``score``.
    """
    if not query.strip():
        return []

    with open_project_store(config) as store:
        hits = store.search_code(query, top_k=top_k)

    return [
        {
            "uuid": obj.uuid,
            "name": obj.name,
            "class_type": obj.class_type,
            "file_path": obj.file_path,
            "doc_index": obj.doc_index,
            "snippet": snippet,
            "score": score,
        }
        for obj, snippet, score in hits
    ]

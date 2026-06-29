"""``find_callers`` MCP tool — who calls / references a SimTalk identifier.

This uses the FTS5 ``code_units`` index to find every method body that
mentions the given identifier. It is intentionally a *textual* search
— SimTalk has no formal callee resolution that survives outside the
running engine — so the agent should treat hits as candidates to
review, not as proof of an invocation.
"""

from __future__ import annotations

import re
from typing import Any

from ..config import Config
from ._project_common import open_project_store


# Identifier-like names; SimTalk names follow Pascal-ish rules
# (letters, digits, underscore; must start with a letter/underscore).
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def find_callers(
    name: str,
    top_k: int = 20,
    config: Config | None = None,
) -> list[dict[str, Any]]:
    """Find SimTalk method bodies that mention ``name``.

    Parameters
    ----------
    name:
        The identifier (method, attribute, table) to look for. Must
        be a plain identifier — punctuation is rejected to avoid
        accidental wildcard searches.
    top_k:
        Maximum hits to return (default 20).
    config:
        Optional pre-loaded :class:`~plantsim_mcp.config.Config`.

    Returns
    -------
    list of dict
        Each entry: ``uuid``, ``name``, ``class_type``, ``file_path``,
        ``doc_index``, ``snippet`` (with ``[[name]]`` highlight),
        ``score``. The list excludes the definition itself when the
        callee name matches the caller name exactly.
    """
    if not _IDENT_RE.match(name or ""):
        return []

    with open_project_store(config) as store:
        hits = store.search_code(name, top_k=top_k)

    out: list[dict[str, Any]] = []
    for obj, snippet, score in hits:
        if obj.name == name and obj.class_type == "Method":
            # Skip the method's own definition.
            continue
        out.append(
            {
                "uuid": obj.uuid,
                "name": obj.name,
                "class_type": obj.class_type,
                "file_path": obj.file_path,
                "doc_index": obj.doc_index,
                "snippet": snippet,
                "score": score,
            }
        )
    return out

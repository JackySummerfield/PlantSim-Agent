"""``find_method`` MCP tool — locate a Method by name.

Returns the method's defining object plus any **overriding children**
(objects whose ``Origin`` points at the found method). This is the
key inheritance-awareness feature: when the user asks "where is
``InitFleet``?", they should see (a) the parent definition
they can edit, and (b) the children that override it, because those
children will *not* pick up the parent's changes.

When no method matches exactly, ``did_you_mean`` carries up to 5
nearby Method names (prefix + fuzzy), so the calling LLM can retry
without falling back to training-data guesses.
"""

from __future__ import annotations

from typing import Any

from ..config import Config
from ..storage.project import ObjectRow
from ._project_common import open_project_store


def _row_to_dict(row: ObjectRow) -> dict[str, Any]:
    return {
        "uuid": row.uuid,
        "name": row.name,
        "class_type": row.class_type,
        "origin_uuid": row.origin_uuid,
        "file_path": row.file_path,
        "doc_index": row.doc_index,
        "has_body": row.has_body,
    }


def find_method(
    name: str,
    include_overrides: bool = True,
    config: Config | None = None,
) -> dict[str, Any]:
    """Find every Method named ``name`` and (optionally) its overriding children.

    Parameters
    ----------
    name:
        The method's ``Name`` field (case-sensitive — matches PTS).
    include_overrides:
        When True (default), also return objects whose ``origin_uuid``
        matches a hit (i.e. children that override this method).
    config:
        Optional pre-loaded :class:`~plantsim_mcp.config.Config`.

    Returns
    -------
    dict
        ``{"query": str, "hits": list[dict], "did_you_mean": list[str]}``.

        Each ``hits`` entry carries ``role`` = ``"definition"`` (the
        matching method) or ``"override"`` (a child that overrides it).
        Overrides include ``parent_uuid`` so the agent can show the
        inheritance link explicitly.

        ``did_you_mean`` is populated **only when** ``hits`` is empty —
        up to 5 nearby Method names from the project store.

    Raises
    ------
    FileNotFoundError
        If the project index has not been built.
    """
    if not name.strip():
        return {"query": name, "hits": [], "did_you_mean": []}

    with open_project_store(config) as store:
        all_matches = store.find_by_name(name, class_type="Method")

        # A match whose origin_uuid points to another in-project Method of
        # the same name is treated as an override, not a definition. It
        # will re-appear under its parent via children_of below, so we
        # filter it out of the primary list to avoid duplicates.
        defs: list[ObjectRow] = []
        for m in all_matches:
            if m.origin_uuid:
                parent = store.get_by_uuid(m.origin_uuid)
                if parent and parent.name == name and parent.class_type == "Method":
                    continue
            defs.append(m)

        hits: list[dict[str, Any]] = []
        for d in defs:
            payload = _row_to_dict(d)
            payload["role"] = "definition"
            hits.append(payload)
            if include_overrides:
                for child in store.children_of(d.uuid):
                    payload_c = _row_to_dict(child)
                    payload_c["role"] = "override"
                    payload_c["parent_uuid"] = d.uuid
                    hits.append(payload_c)

        suggestions: list[str] = []
        if not hits:
            suggestions = store.suggest_object_names(
                name, class_type="Method", limit=5
            )

    return {
        "query": name,
        "hits": hits,
        "did_you_mean": suggestions,
    }

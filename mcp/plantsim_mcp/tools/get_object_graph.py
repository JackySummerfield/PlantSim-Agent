"""``get_object_graph`` MCP tool — local neighbourhood for an object.

Given a name or UUID, return a small graph describing how the object
fits into the model:

* its **inheritance** parent (``origin_uuid``) and children
* its material-flow **predecessors** and **successors**

This is the answer to "what touches this object?" — the closest thing
to a Plant Simulation IDE's "Show predecessors / successors" feature
that we can offer over text.
"""

from __future__ import annotations

from typing import Any

from ..config import Config
from ..storage.project import ObjectRow, ProjectStore
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


def _resolve(
    store: ProjectStore, *, uuid: str | None, name: str | None
) -> ObjectRow | None:
    if uuid:
        return store.get_by_uuid(uuid)
    if name:
        rows = store.find_by_name(name)
        if not rows:
            return None
        # Prefer a root definition (no Origin, or Origin pointing to an
        # external library UUID not in this project) over an in-project
        # override, so the centre node is the one the user most likely
        # wants to inspect / edit.
        for r in rows:
            if r.origin_uuid is None:
                return r
            if store.get_by_uuid(r.origin_uuid) is None:
                return r  # Origin points outside the project (Siemens library)
        return rows[0]
    return None


def _hydrate(store: ProjectStore, uuids: list[str]) -> list[dict[str, Any]]:
    if not uuids:
        return []
    found = {r.uuid: r for r in store.get_many_by_uuid(uuids)}
    out: list[dict[str, Any]] = []
    for uid in uuids:
        if uid in found:
            out.append(_row_to_dict(found[uid]))
        else:
            # UUIDs unknown to the objects table (e.g. Siemens library
            # origins) are still surfaced as stubs so the agent knows
            # the link exists even if the target is out of scope.
            out.append(
                {
                    "uuid": uid,
                    "name": None,
                    "class_type": "<external>",
                    "origin_uuid": None,
                    "file_path": None,
                    "doc_index": 0,
                    "has_body": False,
                }
            )
    return out


def get_object_graph(
    name: str | None = None,
    uuid: str | None = None,
    config: Config | None = None,
) -> dict[str, Any]:
    """Return a small graph centred on the given object.

    One of ``name`` or ``uuid`` must be supplied. ``uuid`` is preferred
    when both are passed.

    Returns a dict with keys:

    * ``object`` — the centre node, or ``None`` if not found
    * ``parent`` — the inheritance parent (resolved from
      ``origin_uuid``), or ``None``
    * ``children`` — objects whose ``origin_uuid`` is the centre's UUID
    * ``predecessors`` — material-flow upstream
    * ``successors`` — material-flow downstream

    Raises
    ------
    FileNotFoundError
        If the project index has not been built.
    ValueError
        If neither ``name`` nor ``uuid`` was supplied.
    """
    if not uuid and not name:
        raise ValueError("get_object_graph requires either 'name' or 'uuid'")

    with open_project_store(config) as store:
        centre = _resolve(store, uuid=uuid, name=name)
        if centre is None:
            return {
                "object": None, "parent": None, "children": [],
                "predecessors": [], "successors": [],
            }

        parent_list = _hydrate(store, [centre.origin_uuid]) if centre.origin_uuid else []
        children = [_row_to_dict(c) for c in store.children_of(centre.uuid)]
        preds = _hydrate(store, store.predecessors_of(centre.uuid))
        succs = _hydrate(store, store.successors_of(centre.uuid))

    return {
        "object": _row_to_dict(centre),
        "parent": parent_list[0] if parent_list else None,
        "children": children,
        "predecessors": preds,
        "successors": succs,
    }

"""Parse a ``.psfm`` project folder into structured records.

The parser is **two-pass by design**, matching the inheritance-heavy
nature of Plant Simulation projects:

1. **Pass 1 — UUID map**: stream every ``*.yaml`` file (including the
   often-huge multi-document ``$.yaml`` files inside scene instance
   folders) and emit one :class:`ObjectRow` per YAML document. No
   bodies are inspected. This pass is cheap even on projects with
   1000+ files because PyYAML's ``safe_load_all`` is a streaming
   generator.

2. **Pass 2 — Bodies & edges**: re-iterate the docs we already saw,
   but only **harvest content from docs that carry it** — i.e. that
   define ``Program``, ``$CustomAttributes`` with inline methods, or
   ``$Predecessors`` / ``$Successors`` graph edges. Pure-inheritance
   children (Origin link only, no override) are skipped, which is
   what the user explicitly asked for: "if a child only inherits, you
   don't need to deeply parse it — just link to the parent".

The parser does not touch SQLite; it yields plain dataclass records
that an indexer can write through :class:`ProjectStore`. This keeps
the parser testable without a database.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..storage.project import CodeUnit, FlowEdge, ObjectRow

log = logging.getLogger(__name__)


@dataclass
class ParseResult:
    """Aggregate output of :func:`parse_project`."""

    objects: list[ObjectRow] = field(default_factory=list)
    code_units: list[CodeUnit] = field(default_factory=list)
    edges: list[FlowEdge] = field(default_factory=list)
    files_scanned: int = 0
    docs_scanned: int = 0
    skipped: list[tuple[str, str]] = field(default_factory=list)
    """Files we couldn't parse, as (relative_path, error)."""


# ---------------------------------------------------------------------------
# Pass 1 — cheap doc iteration
# ---------------------------------------------------------------------------


def _safe_load_all(text: str, file_label: str) -> Iterator[dict | None]:
    """Wrap ``yaml.safe_load_all`` so a malformed doc skips, not crashes."""
    try:
        for doc in yaml.safe_load_all(text):
            yield doc
    except yaml.YAMLError as exc:
        log.warning("YAML parse error in %s: %s", file_label, exc)


def _is_object_doc(doc: object) -> bool:
    """A 'real' object doc is a non-empty mapping with InternalClassType."""
    return isinstance(doc, dict) and "InternalClassType" in doc


def _doc_uuid(doc: dict) -> str | None:
    return doc.get("UUID") if isinstance(doc.get("UUID"), str) else None


def _doc_name(doc: dict) -> str | None:
    # Top-level files use Name; multi-doc child entries use $ObjectName.
    name = doc.get("Name") or doc.get("$ObjectName")
    return name if isinstance(name, str) else None


def _doc_origin(doc: dict) -> str | None:
    val = doc.get("Origin")
    return val if isinstance(val, str) else None


def _doc_has_body(doc: dict) -> bool:
    """Does this doc carry inspectable content beyond the inheritance link?"""
    if "Program" in doc and doc.get("Program"):
        return True
    if "$CustomAttributes" in doc and doc.get("$CustomAttributes"):
        return True
    if "$Predecessors" in doc and doc.get("$Predecessors"):
        return True
    if "$Successors" in doc and doc.get("$Successors"):
        return True
    # Frames are inherently meaningful (parent classes); we always
    # treat them as bodies even without code.
    if doc.get("InternalClassType") == "Frame":
        return True
    return False


# ---------------------------------------------------------------------------
# Pass 2 — body / edge extraction
# ---------------------------------------------------------------------------


def _harvest_program(doc: dict) -> str | None:
    """Extract the SimTalk body from a Method doc, or ``None``."""
    prog = doc.get("Program")
    if isinstance(prog, str) and prog.strip():
        return prog
    return None


def _harvest_custom_attribute_methods(
    doc: dict, parent_uuid: str
) -> Iterator[tuple[str, str, str]]:
    """Yield ``(synthetic_uuid, name, body)`` for inline methods.

    ``$CustomAttributes`` can carry method bodies inline (e.g. a
    Buffer's ``OnEntrance``). We surface them so ``search_code`` and
    ``find_method`` see them, but assign them synthetic UUIDs
    (``"<parent>::<attr_name>"``) since they don't have their own.
    """
    attrs = doc.get("$CustomAttributes")
    if not isinstance(attrs, list):
        return
    for attr in attrs:
        if not isinstance(attr, dict):
            continue
        if attr.get("DataType") != "method":
            continue
        body = attr.get("Value")
        if not isinstance(body, str) or not body.strip():
            continue
        name = attr.get("Name") or "<inline>"
        synth_uuid = f"{parent_uuid}::{name}"
        yield synth_uuid, name, body


def _harvest_edges(doc: dict, src_uuid: str) -> Iterator[FlowEdge]:
    """Yield material-flow graph edges declared on this object."""
    for kind_key, kind in (("$Predecessors", "predecessor"), ("$Successors", "successor")):
        edges = doc.get(kind_key)
        if not isinstance(edges, list):
            continue
        for edge in edges:
            target_uuid: str | None = None
            if isinstance(edge, str):
                target_uuid = edge
            elif isinstance(edge, dict):
                # entries look like { $Succ: <uuid>, Origin: ..., UUID: ... }
                target_uuid = edge.get("$Succ") or edge.get("$Pred") or edge.get("UUID")
            if isinstance(target_uuid, str):
                if kind == "successor":
                    yield FlowEdge(src_uuid=src_uuid, dst_uuid=target_uuid, kind=kind)
                else:
                    yield FlowEdge(src_uuid=target_uuid, dst_uuid=src_uuid, kind=kind)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def parse_project(project_root: Path) -> ParseResult:
    """Parse every ``.yaml`` file under ``project_root`` into a :class:`ParseResult`.

    ``project_root`` should point at the ``*.psfm`` folder (the one
    containing ``Models/``, ``InformationFlow/`` etc.). The parser
    walks the entire tree.
    """
    root = Path(project_root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Project root does not exist or is not a directory: {root}")

    result = ParseResult()
    inline_method_parents: dict[str, str] = {}  # synth_uuid -> parent file_path

    for yaml_path in sorted(root.rglob("*.yaml")):
        rel = yaml_path.relative_to(root).as_posix()
        result.files_scanned += 1
        try:
            text = yaml_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            result.skipped.append((rel, f"read error: {exc}"))
            continue

        for doc_idx, doc in enumerate(_safe_load_all(text, rel)):
            if not _is_object_doc(doc):
                continue
            assert isinstance(doc, dict)  # for mypy
            result.docs_scanned += 1

            uuid = _doc_uuid(doc)
            if not uuid:
                # Defensive — every real PTS object has a UUID.
                continue

            class_type = doc.get("InternalClassType")
            assert isinstance(class_type, str)
            has_body = _doc_has_body(doc)

            result.objects.append(
                ObjectRow(
                    uuid=uuid,
                    name=_doc_name(doc),
                    class_type=class_type,
                    origin_uuid=_doc_origin(doc),
                    file_path=rel,
                    doc_index=doc_idx,
                    has_body=has_body,
                )
            )

            if not has_body:
                continue

            # Methods: extract Program body
            if class_type == "Method":
                body = _harvest_program(doc)
                if body:
                    result.code_units.append(
                        CodeUnit(uuid=uuid, name=_doc_name(doc), body=body)
                    )

            # Inline-method $CustomAttributes
            for synth_uuid, attr_name, body in _harvest_custom_attribute_methods(doc, uuid):
                inline_method_parents[synth_uuid] = rel
                result.objects.append(
                    ObjectRow(
                        uuid=synth_uuid,
                        name=attr_name,
                        class_type="Method",
                        origin_uuid=uuid,  # the host object is the "parent"
                        file_path=rel,
                        doc_index=doc_idx,
                        has_body=True,
                    )
                )
                result.code_units.append(
                    CodeUnit(uuid=synth_uuid, name=attr_name, body=body)
                )

            # Material-flow edges
            for edge in _harvest_edges(doc, uuid):
                result.edges.append(edge)

    log.info(
        "parsed %d files, %d docs, %d objects, %d code units, %d edges",
        result.files_scanned,
        result.docs_scanned,
        len(result.objects),
        len(result.code_units),
        len(result.edges),
    )
    return result

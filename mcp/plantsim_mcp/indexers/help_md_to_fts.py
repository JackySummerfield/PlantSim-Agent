"""Walk a markdown tree, split by headings, write into an Index.

This is the workhorse for W1 (Documentation Q&A): given a directory of
``.md`` files (either the user's converted PTS Help or our own
``kb_minimal/`` sample), produce one :class:`~plantsim_mcp.storage.base.Doc`
per ``##`` / ``###`` section so the FTS5 search returns *section-grained*
hits rather than whole-file hits.

Splitting rules:

* Top-level ``#`` headings start a fresh page; everything before the
  first heading is attached to a synthetic ``"(preamble)"`` section so
  no content is lost.
* ``##`` and ``###`` headings each open a new section; lower levels
  (``####``+) stay inside their parent section.
* Fenced code blocks (``` ``` ```) are kept intact; a ``#`` inside a
  code block does **not** split a section.

Doc ids are ``"<rel_path>#<section_slug>"`` with a numeric suffix added
on collision; ids are stable across re-indexing as long as headings
don't move.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from ..storage.base import Doc, Index

_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*#*\s*$")
_FENCE_RE = re.compile(r"^(\s*)(```+|~~~+)")
_SLUG_NONWORD = re.compile(r"[^\w\-]+", re.UNICODE)


def _slugify(text: str) -> str:
    text = text.strip().lower().replace(" ", "-")
    text = _SLUG_NONWORD.sub("", text)
    return text or "section"


def _iter_sections(text: str) -> Iterator[tuple[str, str]]:
    """Yield ``(section_title, body)`` pairs for one markdown file."""
    lines = text.splitlines()
    current_title = "(preamble)"
    current_body: list[str] = []
    in_fence = False
    fence_marker: str | None = None

    for line in lines:
        fence_match = _FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group(2)[:3]
            if not in_fence:
                in_fence = True
                fence_marker = marker
            elif fence_marker and line.lstrip().startswith(fence_marker):
                in_fence = False
                fence_marker = None
            current_body.append(line)
            continue

        if not in_fence:
            heading = _HEADING_RE.match(line)
            if heading and len(heading.group(1)) <= 3:
                # Flush previous section if it has any non-blank content
                body_text = "\n".join(current_body).strip()
                if body_text or current_title != "(preamble)":
                    yield current_title, body_text
                current_title = heading.group(2).strip()
                current_body = []
                continue

        current_body.append(line)

    body_text = "\n".join(current_body).strip()
    if body_text or current_title != "(preamble)":
        yield current_title, body_text


def iter_docs(root: Path) -> Iterator[Doc]:
    """Yield Doc records for every ``.md`` file under ``root``.

    File paths in the produced docs are relative to ``root`` so the
    index survives moves of the parent directory.
    """
    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"KB root does not exist or is not a directory: {root}")

    for md_path in sorted(root.rglob("*.md")):
        rel = md_path.relative_to(root).as_posix()
        text = md_path.read_text(encoding="utf-8", errors="replace")
        seen_ids: dict[str, int] = {}
        for section, body in _iter_sections(text):
            slug = _slugify(section)
            base_id = f"{rel}#{slug}"
            collisions = seen_ids.get(base_id, 0)
            seen_ids[base_id] = collisions + 1
            doc_id = base_id if collisions == 0 else f"{base_id}-{collisions + 1}"
            if not body and section == "(preamble)":
                continue
            yield Doc(
                doc_id=doc_id,
                file_path=rel,
                section=section,
                content=body,
            )


def build(root: Path, index: Index) -> int:
    """Index every markdown file under ``root`` into ``index``.

    Returns the number of docs written. Caller is responsible for
    opening / closing the index (use ``with index:`` for the common case).
    """
    return index.add_docs(iter_docs(root))

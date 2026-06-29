"""Chapter-aware indexer for the PTS Help ``_full_docling_code_tagged.md``.

Where :mod:`plantsim_mcp.indexers.help_md_to_fts` walks a directory of
``.md`` files and splits each by ``##``/``###`` headings, this indexer
operates on a single large markdown file (~9 MB) produced by docling
from the official PTS Help PDF. That file holds ~4400 deeply-nested
reference entries (one per object property / SimTalk method / UI
control) at ``#####`` and ``######`` levels.

What the indexer does:

* Auto-detects chapter boundaries from ``^# <N>\\.`` headings.
* For each requested chapter (default 11/12/13/15), walks H5/H6
  headings using an ancestor stack.
* **Skips** purely-organisational headings:
    - ``\\_`` / ``_`` prefix (e.g. ``\\_Attributes of the Controls``)
    - body-label headings that leaked from docling (``See also`` etc.)
* For each real entry, emits one :class:`~plantsim_mcp.storage.base.Doc`:
    - ``section``  = heading text verbatim (e.g. ``"Stop [SimTalk] - Source"``)
    - ``entry_name`` = the part before the first ``[`` (e.g. ``"Stop"``)
    - ``content``  = body lines from the heading up to (but not including)
                     the next heading at the same-or-shallower level
    - ``doc_id``   = deterministic ``"{label}::{relpath}#L{lineno}"``

Chapter coverage:

==  =================================  ~entries
11  Objects Reference Help             3171
12  SimTalk Reference                  328
13  3D Reference Help                  413
15  Add-Ins Reference Help             487
==  =================================  ~entries
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from pathlib import Path

from ..storage.base import Doc, Index

# Default chapters to index. Configurable via the CLI / config.
DEFAULT_CHAPTERS: tuple[int, ...] = (11, 12, 13, 15)

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_CHAPTER_RE = re.compile(r"^#\s+(\d+)\.\s+(.+?)\s*$")

# Labels that appear inside a reference entry's body. docling occasionally
# promotes one of these to a real heading; we skip those nodes.
_BODY_LABELS = frozenset(
    {
        "remarks",
        "type",
        "syntax",
        "assignment value",
        "example",
        "examples",
        "simtalk",
        "see also",
        "note",
        "tip",
        "properties",
        "parameters",
        "return value",
        "default value",
    }
)


def _strip_underscore_prefix(s: str) -> str:
    """Return ``s`` with a leading ``\\_`` / ``_`` peeled (if any)."""
    s2 = s.lstrip()
    if s2.startswith(r"\_"):
        return s2[2:].lstrip()
    if s2.startswith("_"):
        return s2[1:].lstrip()
    return s


def _is_categorical(heading: str) -> bool:
    """True if the heading is a categorical grouping, not a real entry."""
    stripped = heading.lstrip()
    if stripped.startswith((r"\_", "_")):
        return True
    if stripped.lower() in _BODY_LABELS:
        return True
    return False


def _extract_entry_name(heading: str) -> str:
    """Return the canonical entry name (text before first ``[``).

    Examples::

        "Stop [SimTalk] - Source"        -> "Stop"
        "Capacity [text box] - Exporter" -> "Capacity"
        "Predefined Names"               -> "Predefined Names"
        "Material Active [check box] - MUs" -> "Material Active"
    """
    text = _strip_underscore_prefix(heading).strip()
    bracket = text.find("[")
    if bracket > 0:
        return text[:bracket].rstrip()
    return text


def _iter_chapter_entries(
    lines: list[str], chapters: Iterable[int]
) -> Iterator[tuple[int, int, str, list[tuple[int, str]]]]:
    """Yield ``(line_no, level, heading_text, ancestor_chain)`` for H5/H6
    headings inside the requested chapter numbers.

    ``ancestor_chain`` is the list of ``(level, text)`` headings above
    the current entry, root-first (excluding the H1 chapter banner).
    """
    wanted = set(chapters)
    in_chapter = False
    stack: list[tuple[int, str]] = []  # (level, text)

    for i, raw in enumerate(lines):
        m = _HEADING_RE.match(raw)
        if not m:
            continue
        level = len(m.group(1))
        text = m.group(2)

        if level == 1:
            chap = _CHAPTER_RE.match(raw)
            if chap and int(chap.group(1)) in wanted:
                in_chapter = True
                stack = [(1, text)]
                continue
            in_chapter = False
            stack = []
            continue

        if not in_chapter:
            continue

        # Maintain ancestor stack
        while stack and stack[-1][0] >= level:
            stack.pop()

        if level in (5, 6):
            yield i + 1, level, text, list(stack)

        stack.append((level, text))


def _body_until_next_heading(
    lines: list[str], start_idx0: int, current_level: int
) -> str:
    """Return the body text between ``start_idx0`` (the heading line)
    and the next heading at level ``<= current_level``.

    The heading line itself is excluded; body lines are joined verbatim
    so fenced code blocks survive.
    """
    out: list[str] = []
    n = len(lines)
    for j in range(start_idx0 + 1, n):
        m = _HEADING_RE.match(lines[j])
        if m and len(m.group(1)) <= current_level:
            break
        out.append(lines[j])
    return "\n".join(out).rstrip()


def iter_fullmd_docs(
    src: Path,
    label: str | None = None,
    chapters: Iterable[int] = DEFAULT_CHAPTERS,
) -> Iterator[Doc]:
    """Yield :class:`Doc` records for every reference entry in ``src``.

    Parameters
    ----------
    src:
        Path to the docling-produced markdown file (typically
        ``_full_docling_code_tagged.md``).
    label:
        Stable short name embedded in ``doc_id`` / ``file_path``.
        Defaults to ``src.parent.name`` so the source folder
        (``pts_help_2504_fullmd``) becomes the prefix.
    chapters:
        Chapter numbers to include (default 11/12/13/15).
    """
    src = src.resolve()
    if not src.is_file():
        raise FileNotFoundError(f"fullmd source file not found: {src}")

    text = src.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    eff_label = label or src.parent.name
    rel = src.name  # single file — no relative path inside the source folder

    seen_ids: dict[str, int] = {}
    for line_no, level, heading, _ancestors in _iter_chapter_entries(lines, chapters):
        if _is_categorical(heading):
            continue
        entry_name = _extract_entry_name(heading)
        if not entry_name:
            continue
        body = _body_until_next_heading(lines, line_no - 1, level)
        if not body:
            continue  # Skip empty stubs

        base_id = f"{eff_label}::{rel}#L{line_no}"
        coll = seen_ids.get(base_id, 0)
        seen_ids[base_id] = coll + 1
        doc_id = base_id if coll == 0 else f"{base_id}-{coll + 1}"

        yield Doc(
            doc_id=doc_id,
            file_path=f"{eff_label}/{rel}",
            section=heading.strip(),
            content=body,
            entry_name=entry_name,
        )


def build_fullmd(
    src: Path,
    index: Index,
    chapters: Iterable[int] = DEFAULT_CHAPTERS,
    label: str | None = None,
) -> int:
    """Index reference entries from a fullmd file into ``index``.

    Returns the number of docs written. The caller owns the index
    lifecycle (use ``with index:``).
    """
    return index.add_docs(iter_fullmd_docs(src, label=label, chapters=chapters))

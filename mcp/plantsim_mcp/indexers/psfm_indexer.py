"""Glue between :func:`parse_project` and :class:`ProjectStore`.

This module is the indexer's *only* job: drive the parser, then write
the records into the project DB. Kept separate so users (or tests)
can inspect the :class:`ParseResult` without a database round-trip.
"""

from __future__ import annotations

from pathlib import Path

from ..storage.project import ProjectStore
from .psfm_parser import ParseResult, parse_project


def build_project_index(project_root: Path, store: ProjectStore) -> ParseResult:
    """Parse ``project_root`` and write everything into ``store``.

    The store is **rebuilt from scratch** — old data is dropped. Use a
    fresh store path if you want incremental indexing in the future.
    """
    result = parse_project(project_root)
    store.rebuild()
    store.add_objects(result.objects)
    store.add_code_units(result.code_units)
    store.add_edges(result.edges)
    return result

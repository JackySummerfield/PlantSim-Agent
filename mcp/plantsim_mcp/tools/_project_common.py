"""Shared helpers for project-DB tools.

Centralises the "open the project DB or raise a helpful error" pattern
so every tool gives the same actionable message when the user has not
yet built the index.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from ..config import Config, load
from ..storage.project import ProjectStore


@contextmanager
def open_project_store(config: Config | None = None) -> Iterator[ProjectStore]:
    """Yield an opened :class:`ProjectStore`, or raise with a build-kb hint."""
    cfg = config or load()
    db_path = cfg.paths.project_db
    if not db_path.exists():
        raise FileNotFoundError(
            f"Project index not found at {db_path}. "
            "Run `plantsim-copilot-mcp build-project --project <path-to-.psfm>` "
            "to create it."
        )
    with ProjectStore(db_path) as store:
        yield store

"""Abstract index interface.

Indexers populate an :class:`Index`; tools query one. The v0.1
implementation is SQLite FTS5; the same interface is intended to back a
vector-store implementation in v0.2.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class Doc:
    """A single indexable document chunk.

    A ``Doc`` represents one searchable unit — for help content this is
    typically a markdown section under a single ``##``/``###`` heading.

    Attributes
    ----------
    doc_id:
        Stable identifier. The indexer is responsible for choosing
        ids that survive a rebuild (e.g. ``"<rel_path>#<section_slug>"``).
    file_path:
        Source file the chunk came from. Relative to the KB root is
        preferred so indices survive moves of the parent directory.
    section:
        Heading or section name, used in citations and snippet display.
    content:
        Plain-text body of the chunk; the index tokenises this.
    """

    doc_id: str
    file_path: str
    section: str
    content: str


@dataclass(frozen=True)
class Hit:
    """A single search result.

    ``score`` is implementation-defined (BM25 for FTS5, cosine for vector
    stores). Smaller-is-better for BM25 raw scores from SQLite, so tools
    that surface scores to the user should normalise.
    """

    doc_id: str
    file_path: str
    section: str
    snippet: str
    score: float


class Index(ABC):
    """Storage-agnostic interface for indexers and query tools.

    Implementations must be safe to ``open`` repeatedly against the same
    backing store (idempotent), and ``close`` must release any handles.
    Methods are synchronous; the MCP layer wraps them with async glue.
    """

    @abstractmethod
    def open(self) -> None:
        """Open the backing store, creating schema if needed."""

    @abstractmethod
    def close(self) -> None:
        """Release any underlying handles."""

    @abstractmethod
    def add_docs(self, docs: Iterable[Doc]) -> int:
        """Add or replace docs. Returns count actually written."""

    @abstractmethod
    def delete_all(self) -> None:
        """Remove every doc — used by ``--rebuild`` flows."""

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> list[Hit]:
        """Return up to ``top_k`` ranked hits for ``query``."""

    @abstractmethod
    def count(self) -> int:
        """Return the number of indexed docs."""

    def __enter__(self) -> Index:
        self.open()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

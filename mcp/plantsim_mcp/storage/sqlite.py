"""SQLite + FTS5 implementation of :class:`~plantsim_mcp.storage.base.Index`.

We use a contentless FTS5 virtual table for the searchable columns and a
sidecar ``docs_meta`` table for ``file_path`` / ``section`` so we can show
proper citations without storing duplicate copies of the body.

Schema::

    CREATE TABLE docs_meta (
        doc_id     TEXT PRIMARY KEY,
        file_path  TEXT NOT NULL,
        section    TEXT NOT NULL
    );

    CREATE VIRTUAL TABLE docs_fts USING fts5(
        doc_id     UNINDEXED,
        content,
        tokenize = 'unicode61 remove_diacritics 2'
    );

FTS5 ships with stdlib SQLite on every supported Windows / macOS / Linux
Python build, so no extension loading is required.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path

from .base import Doc, Hit, Index

_SCHEMA = """
CREATE TABLE IF NOT EXISTS docs_meta (
    doc_id     TEXT PRIMARY KEY,
    file_path  TEXT NOT NULL,
    section    TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
    doc_id     UNINDEXED,
    content,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""


def _escape_fts(query: str) -> str:
    """Wrap each whitespace-separated token in double quotes.

    FTS5 treats ``-``, ``.``, ``(``, etc. as operators; for the v0.1
    natural-language Q&A use case we simply quote each token. This makes
    queries phrase-style on each token and trades a little recall for
    robustness against punctuation in user queries.
    """
    parts = []
    for token in query.split():
        cleaned = token.replace('"', '""').strip()
        if cleaned:
            parts.append(f'"{cleaned}"')
    if not parts:
        return '""'
    return " ".join(parts)


class SQLiteFTSIndex(Index):
    """File-backed FTS5 index.

    Parameters
    ----------
    db_path:
        Path to the SQLite file. ``":memory:"`` is supported for tests.
    """

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None

    # ---- lifecycle ----------------------------------------------------

    def open(self) -> None:
        if self._conn is not None:
            return
        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ---- helpers ------------------------------------------------------

    def _require_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Index is not open. Use `with index:` or call .open() first.")
        return self._conn

    # ---- writes -------------------------------------------------------

    def add_docs(self, docs: Iterable[Doc]) -> int:
        conn = self._require_conn()
        rows = list(docs)
        if not rows:
            return 0
        cur = conn.cursor()
        # Replace-on-conflict semantics for stable doc_ids
        cur.executemany(
            "INSERT OR REPLACE INTO docs_meta(doc_id, file_path, section) VALUES (?, ?, ?)",
            [(d.doc_id, d.file_path, d.section) for d in rows],
        )
        # FTS5 has no upsert; delete-then-insert keyed on doc_id.
        cur.executemany(
            "DELETE FROM docs_fts WHERE doc_id = ?",
            [(d.doc_id,) for d in rows],
        )
        cur.executemany(
            "INSERT INTO docs_fts(doc_id, content) VALUES (?, ?)",
            [(d.doc_id, d.content) for d in rows],
        )
        conn.commit()
        return len(rows)

    def delete_all(self) -> None:
        conn = self._require_conn()
        conn.execute("DELETE FROM docs_meta")
        conn.execute("DELETE FROM docs_fts")
        conn.commit()

    # ---- reads --------------------------------------------------------

    def search(self, query: str, top_k: int = 5) -> list[Hit]:
        conn = self._require_conn()
        if not query.strip():
            return []
        fts_query = _escape_fts(query)
        # bm25() returns lower-is-better; we negate so higher score = better
        # for caller-friendliness and align with vector-store conventions.
        cur = conn.execute(
            """
            SELECT
                f.doc_id,
                m.file_path,
                m.section,
                snippet(docs_fts, 1, '[[', ']]', '...', 16) AS snippet,
                bm25(docs_fts) AS score
            FROM docs_fts f
            JOIN docs_meta m ON m.doc_id = f.doc_id
            WHERE docs_fts MATCH ?
            ORDER BY score
            LIMIT ?
            """,
            (fts_query, top_k),
        )
        return [
            Hit(
                doc_id=row[0],
                file_path=row[1],
                section=row[2],
                snippet=row[3],
                score=-row[4],
            )
            for row in cur.fetchall()
        ]

    def count(self) -> int:
        conn = self._require_conn()
        return conn.execute("SELECT COUNT(*) FROM docs_meta").fetchone()[0]

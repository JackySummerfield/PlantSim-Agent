"""SQLite + FTS5 implementation of :class:`~plantsim_mcp.storage.base.Index`.

We use a contentless FTS5 virtual table for the searchable columns and a
sidecar ``docs_meta`` table for ``file_path`` / ``section`` so we can show
proper citations without storing duplicate copies of the body.

Schema::

    CREATE TABLE docs_meta (
        doc_id     TEXT PRIMARY KEY,
        file_path  TEXT NOT NULL,
        section    TEXT NOT NULL,
        entry_name TEXT          -- nullable; canonical API/UI entry name
    );
    CREATE INDEX idx_meta_entry_name ON docs_meta(entry_name COLLATE NOCASE);

    CREATE VIRTUAL TABLE docs_fts USING fts5(
        doc_id     UNINDEXED,
        content,
        tokenize = 'unicode61 remove_diacritics 2'
    );

The ``entry_name`` column (added in W3.1) lets the fullmd indexer
record the canonical entry name (e.g. ``"Stop"`` for section
``"Stop [SimTalk] - Source"``) for exact-match lookups that bypass
both FTS tokenisation and the LIKE prefix's `[SimTalk]`-only bias.

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
    section    TEXT NOT NULL,
    entry_name TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
    doc_id     UNINDEXED,
    content,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""


def _migrate_add_entry_name(conn: sqlite3.Connection) -> None:
    """Ensure ``docs_meta.entry_name`` column + its index exist.

    Older indices (pre-W3.1) created ``docs_meta`` without the column;
    SQLite's ``ALTER TABLE ADD COLUMN`` is cheap and non-destructive.
    The index is created here (rather than in ``_SCHEMA``) because the
    ``CREATE INDEX`` would reference a non-existent column on a legacy
    DB if it ran before the ``ALTER TABLE``.
    """
    cols = {row[1] for row in conn.execute("PRAGMA table_info(docs_meta)").fetchall()}
    if "entry_name" not in cols:
        conn.execute("ALTER TABLE docs_meta ADD COLUMN entry_name TEXT")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_meta_entry_name "
        "ON docs_meta(entry_name COLLATE NOCASE)"
    )
    conn.commit()


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
        _migrate_add_entry_name(self._conn)
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
            "INSERT OR REPLACE INTO docs_meta(doc_id, file_path, section, entry_name) "
            "VALUES (?, ?, ?, ?)",
            [(d.doc_id, d.file_path, d.section, d.entry_name) for d in rows],
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

    def find_by_section(self, name: str, top_k: int = 10) -> list[Hit]:
        """Find docs whose entry/section matches ``name``.

        High-precision API lookup path used by
        :func:`~plantsim_mcp.tools.get_api.get_api`. Two-stage lookup:

        1. **Exact match** on the canonical ``entry_name`` column
           (case-insensitive, populated by the fullmd indexer). This
           catches *all* kinds — SimTalk methods, attributes, UI
           controls — for a given identifier, regardless of the
           bracket-suffix variant.
        2. **Fallback prefix LIKE** on ``section`` (``"<name> [SimTalk]%"``)
           for older indices where ``entry_name`` is not populated.

        Results are de-duplicated by ``doc_id`` and sorted shortest-
        section-first so generic entries outrank disambiguators like
        ``Active [SimTalk] - fluid objects``.
        """
        conn = self._require_conn()
        if not name.strip():
            return []

        seen: set[str] = set()
        out: list[Hit] = []

        # Stage 1: exact entry_name (case-insensitive) — covers any kind.
        cur = conn.execute(
            """
            SELECT m.doc_id, m.file_path, m.section,
                   substr(f.content, 1, 240) AS snippet
            FROM docs_meta m
            JOIN docs_fts f ON m.doc_id = f.doc_id
            WHERE m.entry_name = ? COLLATE NOCASE
            ORDER BY length(m.section), m.section
            LIMIT ?
            """,
            (name, top_k),
        )
        for row in cur.fetchall():
            if row[0] not in seen:
                seen.add(row[0])
                out.append(
                    Hit(
                        doc_id=row[0],
                        file_path=row[1],
                        section=row[2],
                        snippet=row[3],
                        score=0.0,
                    )
                )

        if len(out) >= top_k:
            return out[:top_k]

        # Stage 2: legacy LIKE on section ("<name> [SimTalk]%").
        like = f"{name} [SimTalk]%"
        remaining = top_k - len(out)
        cur = conn.execute(
            """
            SELECT m.doc_id, m.file_path, m.section,
                   substr(f.content, 1, 240) AS snippet
            FROM docs_meta m
            JOIN docs_fts f ON m.doc_id = f.doc_id
            WHERE m.section LIKE ?
            ORDER BY length(m.section), m.section
            LIMIT ?
            """,
            (like, remaining + len(seen)),  # over-fetch so de-dup still fills top_k
        )
        for row in cur.fetchall():
            if row[0] in seen:
                continue
            seen.add(row[0])
            out.append(
                Hit(
                    doc_id=row[0],
                    file_path=row[1],
                    section=row[2],
                    snippet=row[3],
                    score=0.0,
                )
            )
            if len(out) >= top_k:
                break
        return out

    def suggest_entry_names(self, query: str, limit: int = 5) -> list[str]:
        """Return up to ``limit`` entry names similar to ``query``.

        Two-stage suggestion:

        1. **Prefix match** on ``entry_name`` (case-insensitive). Catches
           common typos at the tail (``Stop`` → ``StopAtDestination``).
        2. **Fuzzy match** via :func:`difflib.get_close_matches` over the
           full distinct-name list. Catches mid-string typos
           (``Stoped`` → ``Stop``).

        Returns an empty list when the index has no ``entry_name`` data
        (i.e. pre-W3.1 indices that only ran the legacy prose indexer).
        """
        if not query.strip() or limit <= 0:
            return []
        conn = self._require_conn()

        # Stage 1: prefix (skip exact-equal matches; those are real hits,
        # not suggestions).
        cur = conn.execute(
            """
            SELECT DISTINCT entry_name FROM docs_meta
            WHERE entry_name LIKE ? COLLATE NOCASE
              AND entry_name <> ? COLLATE NOCASE
              AND entry_name IS NOT NULL
            ORDER BY length(entry_name), entry_name
            LIMIT ?
            """,
            (f"{query}%", query, limit),
        )
        out: list[str] = [r[0] for r in cur.fetchall()]
        if len(out) >= limit:
            return out

        # Stage 2: fuzzy. Pull the full distinct-name list (typically a
        # few thousand short strings → cheap to scan with difflib).
        from difflib import get_close_matches

        all_names = [
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT entry_name FROM docs_meta "
                "WHERE entry_name IS NOT NULL"
            ).fetchall()
        ]
        # Case-insensitive: lowercase the corpus, keep a map back to the
        # original casing.
        lower_to_orig: dict[str, str] = {}
        for n in all_names:
            lower_to_orig.setdefault(n.lower(), n)
        close = get_close_matches(
            query.lower(), list(lower_to_orig.keys()), n=limit * 2, cutoff=0.6
        )
        seen = {n.lower() for n in out}
        for c in close:
            orig = lower_to_orig[c]
            if orig.lower() in seen:
                continue
            out.append(orig)
            seen.add(orig.lower())
            if len(out) >= limit:
                break
        return out[:limit]

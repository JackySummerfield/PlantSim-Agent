"""Project-level storage: objects + code_units + edges + inheritance.

This is a sibling of :class:`SQLiteFTSIndex` (which is help-KB only). The
``.psfm`` project lives in a separate ``project.db`` because its schema
is richer than the simple FTS5-only KB:

* ``objects`` — every object discovered in the project, keyed by UUID.
* ``code_units`` — virtual FTS5 table of SimTalk bodies (Methods +
  inline-method ``$CustomAttributes``).
* ``flow_edges`` — material-flow ``$Predecessors`` / ``$Successors``
  + call edges inferred from SimTalk bodies (v0.2 add: today we record
  the body and let ``find_callers`` query FTS5 directly, which is
  cheaper than computing a full call graph up-front).
* ``inheritance`` — flat ``child_uuid → parent_uuid`` mapping (denormal-
  ised from ``objects.origin_uuid``) for fast child lookup.

Single-writer assumption: indexers re-create the DB from scratch
(``rebuild`` flag). Concurrent writers are not supported.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


_SCHEMA = """
CREATE TABLE IF NOT EXISTS objects (
    uuid          TEXT PRIMARY KEY,
    name          TEXT,
    class_type    TEXT NOT NULL,
    origin_uuid   TEXT,
    file_path     TEXT NOT NULL,    -- relative to .psfm root
    doc_index     INTEGER NOT NULL DEFAULT 0,
    has_body      INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_objects_name        ON objects(name);
CREATE INDEX IF NOT EXISTS idx_objects_class       ON objects(class_type);
CREATE INDEX IF NOT EXISTS idx_objects_origin      ON objects(origin_uuid);
CREATE INDEX IF NOT EXISTS idx_objects_name_class  ON objects(name, class_type);

CREATE TABLE IF NOT EXISTS inheritance (
    child_uuid    TEXT NOT NULL,
    parent_uuid   TEXT NOT NULL,
    PRIMARY KEY (child_uuid, parent_uuid)
);
CREATE INDEX IF NOT EXISTS idx_inh_parent ON inheritance(parent_uuid);

CREATE VIRTUAL TABLE IF NOT EXISTS code_units USING fts5(
    uuid       UNINDEXED,
    name       UNINDEXED,
    body,
    tokenize = 'unicode61 remove_diacritics 2'
);

CREATE TABLE IF NOT EXISTS flow_edges (
    src_uuid   TEXT NOT NULL,
    dst_uuid   TEXT NOT NULL,
    kind       TEXT NOT NULL,        -- 'predecessor' | 'successor'
    PRIMARY KEY (src_uuid, dst_uuid, kind)
);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON flow_edges(dst_uuid, kind);
"""


@dataclass(frozen=True)
class ObjectRow:
    uuid: str
    name: str | None
    class_type: str
    origin_uuid: str | None
    file_path: str
    doc_index: int = 0
    has_body: bool = False


@dataclass(frozen=True)
class CodeUnit:
    uuid: str
    name: str | None
    body: str


@dataclass(frozen=True)
class FlowEdge:
    src_uuid: str
    dst_uuid: str
    kind: str  # 'predecessor' | 'successor'


def _row(r: tuple) -> ObjectRow:
    return ObjectRow(
        uuid=r[0],
        name=r[1],
        class_type=r[2],
        origin_uuid=r[3],
        file_path=r[4],
        doc_index=r[5],
        has_body=bool(r[6]),
    )


class ProjectStore:
    """SQLite-backed store for a ``.psfm`` project index.

    Use as a context manager::

        with ProjectStore(db_path) as store:
            store.rebuild()  # drops + recreates schema
            store.add_objects(rows)
            store.add_code_units(units)
            store.add_edges(edges)
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

    def __enter__(self) -> ProjectStore:
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _conn_req(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("ProjectStore not open; use 'with' or call .open()")
        return self._conn

    # ---- writes -------------------------------------------------------

    def rebuild(self) -> None:
        """Drop all data and recreate schema."""
        conn = self._conn_req()
        conn.executescript(
            """
            DROP TABLE IF EXISTS objects;
            DROP TABLE IF EXISTS inheritance;
            DROP TABLE IF EXISTS code_units;
            DROP TABLE IF EXISTS flow_edges;
            """
        )
        conn.executescript(_SCHEMA)
        conn.commit()

    def add_objects(self, rows: Iterable[ObjectRow]) -> int:
        conn = self._conn_req()
        batch = list(rows)
        if not batch:
            return 0
        conn.executemany(
            """
            INSERT OR REPLACE INTO objects
                (uuid, name, class_type, origin_uuid, file_path, doc_index, has_body)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    r.uuid,
                    r.name,
                    r.class_type,
                    r.origin_uuid,
                    r.file_path,
                    r.doc_index,
                    1 if r.has_body else 0,
                )
                for r in batch
            ],
        )
        conn.executemany(
            "INSERT OR IGNORE INTO inheritance(child_uuid, parent_uuid) VALUES (?, ?)",
            [(r.uuid, r.origin_uuid) for r in batch if r.origin_uuid],
        )
        conn.commit()
        return len(batch)

    def add_code_units(self, units: Iterable[CodeUnit]) -> int:
        conn = self._conn_req()
        batch = list(units)
        if not batch:
            return 0
        conn.executemany(
            "DELETE FROM code_units WHERE uuid = ?",
            [(u.uuid,) for u in batch],
        )
        conn.executemany(
            "INSERT INTO code_units(uuid, name, body) VALUES (?, ?, ?)",
            [(u.uuid, u.name, u.body) for u in batch],
        )
        conn.commit()
        return len(batch)

    def add_edges(self, edges: Iterable[FlowEdge]) -> int:
        conn = self._conn_req()
        batch = list(edges)
        if not batch:
            return 0
        conn.executemany(
            "INSERT OR IGNORE INTO flow_edges(src_uuid, dst_uuid, kind) VALUES (?, ?, ?)",
            [(e.src_uuid, e.dst_uuid, e.kind) for e in batch],
        )
        conn.commit()
        return len(batch)

    # ---- reads --------------------------------------------------------

    def count_objects(self) -> int:
        return self._conn_req().execute("SELECT COUNT(*) FROM objects").fetchone()[0]

    def count_code_units(self) -> int:
        return self._conn_req().execute("SELECT COUNT(*) FROM code_units").fetchone()[0]

    def count_edges(self) -> int:
        return self._conn_req().execute("SELECT COUNT(*) FROM flow_edges").fetchone()[0]

    def find_by_name(
        self, name: str, class_type: str | None = None
    ) -> list[ObjectRow]:
        conn = self._conn_req()
        # Root definitions (origin_uuid IS NULL) sort first, then by file path
        # so callers get a stable order independent of insertion order.
        if class_type:
            cur = conn.execute(
                """
                SELECT uuid, name, class_type, origin_uuid, file_path, doc_index, has_body
                FROM objects WHERE name = ? AND class_type = ?
                ORDER BY (origin_uuid IS NOT NULL), file_path, doc_index
                """,
                (name, class_type),
            )
        else:
            cur = conn.execute(
                """
                SELECT uuid, name, class_type, origin_uuid, file_path, doc_index, has_body
                FROM objects WHERE name = ?
                ORDER BY (origin_uuid IS NOT NULL), file_path, doc_index
                """,
                (name,),
            )
        return [_row(r) for r in cur.fetchall()]

    def children_of(self, parent_uuid: str) -> list[ObjectRow]:
        cur = self._conn_req().execute(
            """
            SELECT uuid, name, class_type, origin_uuid, file_path, doc_index, has_body
            FROM objects WHERE origin_uuid = ?
            """,
            (parent_uuid,),
        )
        return [_row(r) for r in cur.fetchall()]

    def get_by_uuid(self, uuid: str) -> ObjectRow | None:
        cur = self._conn_req().execute(
            """
            SELECT uuid, name, class_type, origin_uuid, file_path, doc_index, has_body
            FROM objects WHERE uuid = ?
            """,
            (uuid,),
        )
        row = cur.fetchone()
        return _row(row) if row else None

    def get_many_by_uuid(self, uuids: list[str]) -> list[ObjectRow]:
        if not uuids:
            return []
        placeholders = ",".join("?" for _ in uuids)
        cur = self._conn_req().execute(
            f"SELECT uuid, name, class_type, origin_uuid, file_path, doc_index, has_body "
            f"FROM objects WHERE uuid IN ({placeholders})",
            uuids,
        )
        return [_row(r) for r in cur.fetchall()]

    def search_code(
        self, query: str, top_k: int = 20
    ) -> list[tuple[ObjectRow, str, float]]:
        """Full-text search SimTalk bodies; returns (object, snippet, score)."""
        if not query.strip():
            return []
        from .sqlite import _escape_fts  # reuse the helper

        fts_query = _escape_fts(query)
        cur = self._conn_req().execute(
            """
            SELECT
                c.uuid,
                snippet(code_units, 2, '[[', ']]', '...', 12) AS snippet,
                bm25(code_units) AS score,
                o.name, o.class_type, o.origin_uuid, o.file_path, o.doc_index, o.has_body
            FROM code_units c
            JOIN objects o ON o.uuid = c.uuid
            WHERE code_units MATCH ?
            ORDER BY score
            LIMIT ?
            """,
            (fts_query, top_k),
        )
        out: list[tuple[ObjectRow, str, float]] = []
        for r in cur.fetchall():
            obj = ObjectRow(
                uuid=r[0],
                name=r[3],
                class_type=r[4],
                origin_uuid=r[5],
                file_path=r[6],
                doc_index=r[7],
                has_body=bool(r[8]),
            )
            out.append((obj, r[1], -r[2]))
        return out

    def get_body(self, uuid: str) -> str | None:
        cur = self._conn_req().execute(
            "SELECT body FROM code_units WHERE uuid = ?", (uuid,)
        )
        row = cur.fetchone()
        return row[0] if row else None

    def predecessors_of(self, uuid: str) -> list[str]:
        cur = self._conn_req().execute(
            "SELECT src_uuid FROM flow_edges WHERE dst_uuid = ? AND kind = 'predecessor'",
            (uuid,),
        )
        return [r[0] for r in cur.fetchall()]

    def successors_of(self, uuid: str) -> list[str]:
        cur = self._conn_req().execute(
            "SELECT dst_uuid FROM flow_edges WHERE src_uuid = ? AND kind = 'successor'",
            (uuid,),
        )
        return [r[0] for r in cur.fetchall()]

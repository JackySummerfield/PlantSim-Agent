"""Tests for the storage layer."""

from __future__ import annotations

from pathlib import Path

import pytest

from plantsim_mcp.storage.base import Doc
from plantsim_mcp.storage.sqlite import SQLiteFTSIndex, _escape_fts


def _make_docs() -> list[Doc]:
    return [
        Doc(
            doc_id="Buffer.md#numMU",
            file_path="Buffer.md",
            section="numMU",
            content="numMU returns the current number of MUs in the buffer.",
        ),
        Doc(
            doc_id="Buffer.md#capacity",
            file_path="Buffer.md",
            section="capacity",
            content="capacity is the maximum number of MUs the buffer can hold.",
        ),
        Doc(
            doc_id="FlowControl.md#strategy",
            file_path="FlowControl.md",
            section="strategy",
            content="The default distribution strategy is cyclic.",
        ),
    ]


def test_open_creates_schema_and_counts_zero(tmp_path: Path) -> None:
    with SQLiteFTSIndex(tmp_path / "x.db") as idx:
        assert idx.count() == 0


def test_add_and_count(tmp_path: Path) -> None:
    with SQLiteFTSIndex(tmp_path / "x.db") as idx:
        n = idx.add_docs(_make_docs())
        assert n == 3
        assert idx.count() == 3


def test_search_returns_relevant_hit(tmp_path: Path) -> None:
    with SQLiteFTSIndex(tmp_path / "x.db") as idx:
        idx.add_docs(_make_docs())
        hits = idx.search("numMU", top_k=5)
        assert hits
        assert hits[0].section == "numMU"
        assert "[[numMU]]" in hits[0].snippet  # FTS5 snippet highlighting


def test_search_empty_query_returns_empty(tmp_path: Path) -> None:
    with SQLiteFTSIndex(tmp_path / "x.db") as idx:
        idx.add_docs(_make_docs())
        assert idx.search("   ", top_k=5) == []


def test_search_respects_top_k(tmp_path: Path) -> None:
    with SQLiteFTSIndex(tmp_path / "x.db") as idx:
        idx.add_docs(_make_docs())
        hits = idx.search("MUs", top_k=1)
        assert len(hits) == 1


def test_add_is_idempotent_on_same_id(tmp_path: Path) -> None:
    with SQLiteFTSIndex(tmp_path / "x.db") as idx:
        idx.add_docs(_make_docs())
        idx.add_docs(_make_docs())  # second pass — same ids
        assert idx.count() == 3


def test_delete_all(tmp_path: Path) -> None:
    with SQLiteFTSIndex(tmp_path / "x.db") as idx:
        idx.add_docs(_make_docs())
        idx.delete_all()
        assert idx.count() == 0
        assert idx.search("numMU") == []


def test_query_with_punctuation_does_not_crash(tmp_path: Path) -> None:
    with SQLiteFTSIndex(tmp_path / "x.db") as idx:
        idx.add_docs(_make_docs())
        # Punctuation is normally an FTS5 operator; _escape_fts should
        # neutralise it.
        hits = idx.search("Buffer.numMU()", top_k=5)
        # Either zero hits or sane hits — main contract is "no crash".
        assert isinstance(hits, list)


def test_requires_open_before_use(tmp_path: Path) -> None:
    idx = SQLiteFTSIndex(tmp_path / "x.db")
    with pytest.raises(RuntimeError):
        idx.count()


def test_escape_fts_quotes_tokens() -> None:
    assert _escape_fts("foo bar") == '"foo" "bar"'
    assert _escape_fts("") == '""'
    assert _escape_fts("a.b.c") == '"a.b.c"'


# ---------------------------------------------------------------------------
# find_by_section: two-stage lookup (entry_name then LIKE on section)
# ---------------------------------------------------------------------------


def _make_mixed_docs() -> list[Doc]:
    """Mix legacy docs (no entry_name) with fullmd-style docs."""
    return [
        # fullmd-style: has entry_name set
        Doc(
            doc_id="fm::file.md#L100",
            file_path="fullmd/file.md",
            section="Stop [SimTalk] - Source",
            content="Sets the simulation time at which Source stops producing.",
            entry_name="Stop",
        ),
        Doc(
            doc_id="fm::file.md#L200",
            file_path="fullmd/file.md",
            section="Stop [SimTalk] - Drain",
            content="Sets the time at which a Drain stops.",
            entry_name="Stop",
        ),
        Doc(
            doc_id="fm::file.md#L300",
            file_path="fullmd/file.md",
            section="Capacity [text box] - Source",
            content="Defines the capacity exposed in the dialog.",
            entry_name="Capacity",
        ),
        # legacy-style: no entry_name, falls back to LIKE
        Doc(
            doc_id="legacy::buffer.md#move",
            file_path="legacy/buffer.md",
            section="move [SimTalk]",
            content="Moves the front MU to the target.",
            entry_name=None,
        ),
    ]


def test_find_by_section_uses_entry_name_first(tmp_path: Path) -> None:
    with SQLiteFTSIndex(tmp_path / "x.db") as idx:
        idx.add_docs(_make_mixed_docs())
        hits = idx.find_by_section("Stop", top_k=5)
    sections = sorted(h.section for h in hits)
    assert sections == ["Stop [SimTalk] - Drain", "Stop [SimTalk] - Source"]


def test_find_by_section_case_insensitive_entry_name(tmp_path: Path) -> None:
    with SQLiteFTSIndex(tmp_path / "x.db") as idx:
        idx.add_docs(_make_mixed_docs())
        hits = idx.find_by_section("stop", top_k=5)
    assert {h.section for h in hits} == {
        "Stop [SimTalk] - Source",
        "Stop [SimTalk] - Drain",
    }


def test_find_by_section_returns_ui_control_via_entry_name(tmp_path: Path) -> None:
    """LIKE fallback would NOT match '[text box]'; entry_name does."""
    with SQLiteFTSIndex(tmp_path / "x.db") as idx:
        idx.add_docs(_make_mixed_docs())
        hits = idx.find_by_section("Capacity", top_k=5)
    assert [h.section for h in hits] == ["Capacity [text box] - Source"]


def test_find_by_section_falls_back_to_like(tmp_path: Path) -> None:
    """Legacy doc with no entry_name still found via LIKE pattern."""
    with SQLiteFTSIndex(tmp_path / "x.db") as idx:
        idx.add_docs(_make_mixed_docs())
        hits = idx.find_by_section("move", top_k=5)
    assert [h.section for h in hits] == ["move [SimTalk]"]


def test_find_by_section_dedup_across_stages(tmp_path: Path) -> None:
    """A doc matched by entry_name must not appear twice if it would
    also match the LIKE fallback."""
    docs = [
        Doc(
            doc_id="d1",
            file_path="x.md",
            section="move [SimTalk]",
            content="Body.",
            entry_name="move",  # matches stage 1 AND stage 2
        ),
    ]
    with SQLiteFTSIndex(tmp_path / "x.db") as idx:
        idx.add_docs(docs)
        hits = idx.find_by_section("move", top_k=5)
    assert len(hits) == 1


def test_find_by_section_empty_name(tmp_path: Path) -> None:
    with SQLiteFTSIndex(tmp_path / "x.db") as idx:
        idx.add_docs(_make_mixed_docs())
        assert idx.find_by_section("", top_k=5) == []


def test_legacy_db_without_entry_name_migrates(tmp_path: Path) -> None:
    """An older docs_meta without the entry_name column gets ALTERed
    on open() and still works."""
    import sqlite3

    db = tmp_path / "old.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE docs_meta (
            doc_id    TEXT PRIMARY KEY,
            file_path TEXT NOT NULL,
            section   TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE docs_fts USING fts5(
            doc_id UNINDEXED, content,
            tokenize = 'unicode61 remove_diacritics 2'
        );
        """
    )
    conn.execute(
        "INSERT INTO docs_meta VALUES (?, ?, ?)",
        ("old1", "legacy.md", "move [SimTalk]"),
    )
    conn.execute(
        "INSERT INTO docs_fts(doc_id, content) VALUES (?, ?)",
        ("old1", "Legacy doc body."),
    )
    conn.commit()
    conn.close()

    with SQLiteFTSIndex(db) as idx:
        # Migration ran on open; column now exists.
        # Legacy LIKE path still works for entries without entry_name.
        hits = idx.find_by_section("move", top_k=5)
        assert [h.section for h in hits] == ["move [SimTalk]"]
        # And we can now insert new fullmd-style docs into the same DB.
        idx.add_docs(
            [
                Doc(
                    doc_id="new1",
                    file_path="fm/file.md",
                    section="Stop [SimTalk] - Source",
                    content="New body.",
                    entry_name="Stop",
                )
            ]
        )
        assert idx.find_by_section("Stop", top_k=5)[0].section == "Stop [SimTalk] - Source"


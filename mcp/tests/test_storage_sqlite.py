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

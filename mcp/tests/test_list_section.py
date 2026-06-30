"""Tests for the ``list_section`` MCP tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from plantsim_mcp.config import Config, Paths
from plantsim_mcp.storage.base import Doc
from plantsim_mcp.storage.sqlite import SQLiteFTSIndex
from plantsim_mcp.tools.list_section import list_section


@pytest.fixture()
def populated_db(tmp_path: Path) -> Config:
    """Create a help.db with sample docs spanning two 'chapters'."""
    db_path = tmp_path / "help.db"
    docs = [
        Doc(
            doc_id="ch12::str_to_num#L100",
            file_path="Ch12_SimTalk/methods.md",
            section="strToNum [SimTalk]",
            content="Converts a string to a number.",
            entry_name="strToNum",
        ),
        Doc(
            doc_id="ch12::to_str#L200",
            file_path="Ch12_SimTalk/methods.md",
            section="to_str [SimTalk]",
            content="Converts any value to its string representation.",
            entry_name="to_str",
        ),
        Doc(
            doc_id="ch12::strlen#L300",
            file_path="Ch12_SimTalk/methods.md",
            section="strLen [SimTalk]",
            content="Returns the length of a string.",
            entry_name="strLen",
        ),
        Doc(
            doc_id="ch11::buffer_cap#L50",
            file_path="Ch11_Objects/Buffer.md",
            section="Capacity [text box] - Buffer",
            content="Sets the maximum number of MUs the buffer can hold.",
            entry_name="Capacity",
        ),
        Doc(
            doc_id="ch11::buffer_active#L80",
            file_path="Ch11_Objects/Buffer.md",
            section="Active [SimTalk] - Buffer",
            content="Returns or sets whether the buffer is active.",
            entry_name="Active",
        ),
        Doc(
            doc_id="ch11::source_active#L90",
            file_path="Ch11_Objects/Source.md",
            section="Active [SimTalk] - Source",
            content="Returns or sets whether the source is active.",
            entry_name="Active",
        ),
    ]
    with SQLiteFTSIndex(db_path) as idx:
        idx.add_docs(docs)

    return Config(paths=Paths(index_dir=tmp_path))


def test_list_all_entries(populated_db: Config) -> None:
    result = list_section(config=populated_db)
    assert result["count"] == 6
    assert len(result["entries"]) == 6


def test_filter_by_file_path(populated_db: Config) -> None:
    result = list_section(file_path="Ch12", config=populated_db)
    assert result["count"] == 3
    assert all("Ch12" in e["file_path"] for e in result["entries"])


def test_filter_by_kind_simtalk(populated_db: Config) -> None:
    result = list_section(kind="SimTalk", config=populated_db)
    # strToNum, to_str, strLen, Active (Buffer), Active (Source) = 5
    assert result["count"] == 5
    assert all("[SimTalk]" in e["section"] for e in result["entries"])


def test_filter_by_kind_text_box(populated_db: Config) -> None:
    result = list_section(kind="text box", config=populated_db)
    assert result["count"] == 1
    assert result["entries"][0]["entry_name"] == "Capacity"


def test_filter_by_query_substring(populated_db: Config) -> None:
    result = list_section(query="str", config=populated_db)
    # strToNum, to_str, strLen = 3
    assert result["count"] == 3
    names = {e["entry_name"] for e in result["entries"]}
    assert names == {"strToNum", "to_str", "strLen"}


def test_combined_filters(populated_db: Config) -> None:
    result = list_section(file_path="Ch11", kind="SimTalk", config=populated_db)
    assert result["count"] == 2
    names = {e["entry_name"] for e in result["entries"]}
    assert names == {"Active"}  # both Buffer and Source "Active" entries


def test_top_k_truncation(populated_db: Config) -> None:
    result = list_section(top_k=2, config=populated_db)
    assert result["count"] == 6  # total is still 6
    assert len(result["entries"]) == 2  # but only 2 returned


def test_no_matches(populated_db: Config) -> None:
    result = list_section(query="nonexistent_xyz", config=populated_db)
    assert result["count"] == 0
    assert result["entries"] == []


def test_missing_db_raises(tmp_path: Path) -> None:
    cfg = Config(paths=Paths(index_dir=tmp_path / "nope"))
    with pytest.raises(FileNotFoundError, match="Help index not found"):
        list_section(config=cfg)


def test_entries_sorted_alphabetically(populated_db: Config) -> None:
    result = list_section(config=populated_db)
    names = [e["entry_name"] for e in result["entries"]]
    assert names == sorted(names, key=str.casefold)

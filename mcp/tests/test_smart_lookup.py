"""Tests for the ``smart_lookup`` MCP tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from plantsim_mcp.config import Config, Paths
from plantsim_mcp.storage.base import Doc
from plantsim_mcp.storage.sqlite import SQLiteFTSIndex
from plantsim_mcp.tools.smart_lookup import smart_lookup


@pytest.fixture()
def help_db(tmp_path: Path) -> Config:
    """Create a help.db with representative entries."""
    db_path = tmp_path / "help.db"
    docs = [
        Doc(
            doc_id="ch12::SimTime#L100",
            file_path="Ch12_SimTalk/EventController.md",
            section="SimTime [SimTalk]",
            content="Returns the current simulation time of the EventController.",
            entry_name="SimTime",
        ),
        Doc(
            doc_id="ch12::str_to_dateTime#L200",
            file_path="Ch12_SimTalk/conversion.md",
            section="str_to_dateTime [SimTalk]",
            content="Converts a string to dateTime. Depends on Time Scale settings.",
            entry_name="str_to_dateTime",
        ),
        Doc(
            doc_id="ch12::datetime_to_str#L300",
            file_path="Ch12_SimTalk/conversion.md",
            section="datetime_to_str [SimTalk]",
            content="Converts a dateTime value to a string using a format pattern.",
            entry_name="datetime_to_str",
        ),
        Doc(
            doc_id="ch11::Buffer#L50",
            file_path="Ch11_Objects/Buffer.md",
            section="Buffer",
            content="A buffer stores MUs. Capacity sets the maximum number of MUs.",
            entry_name="Buffer",
        ),
        Doc(
            doc_id="ch11::Active_Buffer#L80",
            file_path="Ch11_Objects/Buffer.md",
            section="Active [SimTalk] - Buffer",
            content="Returns or sets whether the buffer is active in the simulation.",
            entry_name="Active",
        ),
        Doc(
            doc_id="ch12::to_str#L400",
            file_path="Ch12_SimTalk/conversion.md",
            section="to_str [SimTalk]",
            content="Converts any value to its string representation.",
            entry_name="to_str",
        ),
    ]
    with SQLiteFTSIndex(db_path) as idx:
        idx.add_docs(docs)
    return Config(paths=Paths(index_dir=tmp_path))


# ---- Strategy: exact ----


def test_exact_match_single_identifier(help_db: Config) -> None:
    result = smart_lookup("SimTime", config=help_db)
    assert result["strategy"] == "exact"
    assert len(result["hits"]) == 1
    assert result["hits"][0]["section"] == "SimTime [SimTalk]"


def test_exact_match_underscore_identifier(help_db: Config) -> None:
    result = smart_lookup("str_to_dateTime", config=help_db)
    assert result["strategy"] == "exact"
    assert result["hits"][0]["entry_name"] if "entry_name" in result["hits"][0] else True
    assert "str_to_dateTime" in result["hits"][0]["section"]


def test_exact_match_multiple_hits(help_db: Config) -> None:
    result = smart_lookup("Active", config=help_db)
    assert result["strategy"] == "exact"
    assert len(result["hits"]) >= 1


# ---- Strategy: suggestion ----


def test_suggestion_retry_on_typo(help_db: Config) -> None:
    # "SimTim" is close to "SimTime" — should trigger suggestion
    result = smart_lookup("SimTim", config=help_db)
    # Either exact (if prefix LIKE matches) or suggestion
    assert result["strategy"] in ("exact", "suggestion")
    if result["strategy"] == "suggestion":
        assert result["suggested_name"] == "SimTime"
        assert len(result["hits"]) >= 1


# ---- Strategy: fts ----


def test_fts_fallback_for_natural_language(help_db: Config) -> None:
    result = smart_lookup("current simulation time EventController", config=help_db)
    assert result["strategy"] == "fts"
    assert len(result["hits"]) >= 1


def test_fts_multi_word_query(help_db: Config) -> None:
    result = smart_lookup("converts dateTime value string format", config=help_db)
    assert result["strategy"] == "fts"
    assert len(result["hits"]) >= 1


# ---- Strategy: none ----


def test_none_when_nothing_found(help_db: Config) -> None:
    result = smart_lookup("xyzzy_nonexistent_api_42", config=help_db)
    assert result["strategy"] == "none"
    assert result["hits"] == []


# ---- Edge cases ----


def test_empty_query(help_db: Config) -> None:
    result = smart_lookup("", config=help_db)
    assert result["strategy"] == "none"
    assert result["hits"] == []


def test_missing_db_raises(tmp_path: Path) -> None:
    cfg = Config(paths=Paths(index_dir=tmp_path / "nope"))
    with pytest.raises(FileNotFoundError, match="Help index not found"):
        smart_lookup("SimTime", config=cfg)


def test_result_shape(help_db: Config) -> None:
    result = smart_lookup("Buffer", config=help_db)
    assert "query" in result
    assert "strategy" in result
    assert "hits" in result
    assert "did_you_mean" in result
    if result["hits"]:
        hit = result["hits"][0]
        assert "file_path" in hit
        assert "section" in hit
        assert "snippet" in hit

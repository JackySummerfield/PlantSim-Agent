"""Tests for the ``get_api`` MCP tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from plantsim_mcp.config import Config, Paths
from plantsim_mcp.indexers.help_md_to_fts import build
from plantsim_mcp.storage.base import Doc
from plantsim_mcp.storage.sqlite import SQLiteFTSIndex
from plantsim_mcp.tools.get_api import get_api


@pytest.fixture
def api_kb(tmp_path: Path) -> Config:
    """Index a tiny KB whose sections mimic the PTS Help SimTalk API convention."""
    db_path = tmp_path / "help.db"
    docs = [
        Doc(
            doc_id="d1",
            file_path="Methods/Buffer.md",
            section="move [SimTalk]",
            content="Moves the front MU to the target. Returns boolean.",
        ),
        Doc(
            doc_id="d2",
            file_path="Methods/MaterialFlow.md",
            section="move [SimTalk] - material flow objects",
            content="Variant of move for material-flow objects.",
        ),
        Doc(
            doc_id="d3",
            file_path="Attributes/Buffer.md",
            section="numMU [SimTalk]",
            content="Current number of MUs in the buffer.",
        ),
        Doc(
            doc_id="d4",
            file_path="Intro/Overview.md",
            section="Introduction",
            content="Just a general overview, no SimTalk tag.",
        ),
    ]
    with SQLiteFTSIndex(db_path) as idx:
        idx.add_docs(docs)

    paths = Paths(index_dir=tmp_path)
    # help_db property derives from index_dir / 'help.db'
    cfg = Config(paths=paths)
    return cfg


def test_get_api_exact_match(api_kb: Config) -> None:
    result = get_api("numMU", config=api_kb)
    assert result["query"] == "numMU"
    hits = result["hits"]
    assert len(hits) == 1
    assert hits[0]["section"] == "numMU [SimTalk]"
    assert "Current number" in hits[0]["snippet"]
    # No suggestions when we have real hits
    assert result["did_you_mean"] == []


def test_get_api_returns_all_variants(api_kb: Config) -> None:
    result = get_api("move", config=api_kb)
    sections = [h["section"] for h in result["hits"]]
    # Shortest-first ordering: bare entry outranks the disambiguator
    assert sections == ["move [SimTalk]", "move [SimTalk] - material flow objects"]


def test_get_api_unknown(api_kb: Config) -> None:
    result = get_api("doesNotExist", config=api_kb)
    assert result["hits"] == []
    # No close match in this tiny corpus → empty suggestions is fine
    assert result["did_you_mean"] == []


def test_get_api_empty_name(api_kb: Config) -> None:
    result = get_api("", config=api_kb)
    assert result["hits"] == []
    assert result["did_you_mean"] == []


def test_get_api_missing_db(tmp_path: Path) -> None:
    paths = Paths(index_dir=tmp_path / "nope")
    cfg = Config(paths=paths)
    with pytest.raises(FileNotFoundError):
        get_api("move", config=cfg)


def test_get_api_suggests_on_typo(tmp_path: Path) -> None:
    """A misspelled lookup should produce ``did_you_mean`` suggestions.

    Uses the fullmd indexer's ``entry_name`` field directly, since the
    legacy prose indexer (used by ``api_kb``) does not populate it.
    """
    from plantsim_mcp.storage.base import Doc
    from plantsim_mcp.storage.sqlite import SQLiteFTSIndex

    db_path = tmp_path / "help.db"
    docs = [
        Doc(
            doc_id="e1",
            file_path="ch11.md",
            section="11.3 Stop [SimTalk]",
            content="Stops a moving MU.",
            entry_name="Stop",
        ),
        Doc(
            doc_id="e2",
            file_path="ch11.md",
            section="11.4 StopAtDestination [SimTalk]",
            content="Stops when destination is reached.",
            entry_name="StopAtDestination",
        ),
        Doc(
            doc_id="e3",
            file_path="ch11.md",
            section="11.5 Stopped [SimTalk]",
            content="Boolean: is the MU stopped.",
            entry_name="Stopped",
        ),
    ]
    with SQLiteFTSIndex(db_path) as idx:
        idx.add_docs(docs)

    cfg = Config(paths=Paths(index_dir=tmp_path))

    # Typo: "Stoped" (one letter short of "Stopped") → fuzzy fallback
    result = get_api("Stoped", config=cfg)
    assert result["hits"] == []
    assert "Stopped" in result["did_you_mean"]
    # Case-insensitive prefix should also surface Stop/StopAtDestination
    assert any(s.startswith("Stop") for s in result["did_you_mean"])


def test_get_api_suggests_on_wrong_case(tmp_path: Path) -> None:
    """find_by_section already does case-insensitive matching, but the
    section title includes a chapter prefix so legacy prose-only sections
    might miss. Verify a case-mismatched query still surfaces via
    suggestions when no exact match exists.
    """
    from plantsim_mcp.storage.base import Doc
    from plantsim_mcp.storage.sqlite import SQLiteFTSIndex

    db_path = tmp_path / "help.db"
    with SQLiteFTSIndex(db_path) as idx:
        idx.add_docs(
            [
                Doc(
                    doc_id="x1",
                    file_path="ch11.md",
                    section="11.3 Stop [SimTalk]",
                    content="Stops a moving MU.",
                    entry_name="Stop",
                ),
            ]
        )
    cfg = Config(paths=Paths(index_dir=tmp_path))

    # "stp" is too far for fuzzy (cutoff 0.6) and no prefix match → empty.
    # But "sto" should hit prefix "Stop" via suggest_entry_names.
    # Note: find_by_section already accepts case-insensitive entry_name
    # matches, so "stop" returns a real hit, not a suggestion. To trigger
    # the suggestion path we need a non-matching but similar query.
    result = get_api("Stopz", config=cfg)
    assert result["hits"] == []
    assert "Stop" in result["did_you_mean"]


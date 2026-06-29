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
    hits = get_api("numMU", config=api_kb)
    assert len(hits) == 1
    assert hits[0]["section"] == "numMU [SimTalk]"
    assert "Current number" in hits[0]["snippet"]


def test_get_api_returns_all_variants(api_kb: Config) -> None:
    hits = get_api("move", config=api_kb)
    sections = [h["section"] for h in hits]
    # Shortest-first ordering: bare entry outranks the disambiguator
    assert sections == ["move [SimTalk]", "move [SimTalk] - material flow objects"]


def test_get_api_unknown(api_kb: Config) -> None:
    assert get_api("doesNotExist", config=api_kb) == []


def test_get_api_empty_name(api_kb: Config) -> None:
    assert get_api("", config=api_kb) == []


def test_get_api_missing_db(tmp_path: Path) -> None:
    paths = Paths(index_dir=tmp_path / "nope")
    cfg = Config(paths=paths)
    with pytest.raises(FileNotFoundError):
        get_api("move", config=cfg)

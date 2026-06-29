"""Tests for the ``search_help`` tool wrapper."""

from __future__ import annotations

from pathlib import Path

import pytest

from plantsim_mcp.config import Config, Paths
from plantsim_mcp.indexers import help_md_to_fts
from plantsim_mcp.storage.sqlite import SQLiteFTSIndex
from plantsim_mcp.tools.search_help import search_help


def _build_index(kb_root: Path, db_path: Path) -> None:
    with SQLiteFTSIndex(db_path) as idx:
        help_md_to_fts.build(kb_root, idx)


def test_search_help_returns_serialisable_dicts(sample_kb: Path, tmp_path: Path) -> None:
    db_path = tmp_path / "indices" / "help.db"
    db_path.parent.mkdir()
    _build_index(sample_kb, db_path)

    cfg = Config(paths=Paths(help_kb_roots=(sample_kb,), index_dir=db_path.parent))
    results = search_help("numMU", top_k=3, config=cfg)

    assert isinstance(results, list)
    assert results
    first = results[0]
    assert set(first.keys()) == {"file_path", "section", "snippet", "score"}
    assert first["section"] == "numMU"
    assert isinstance(first["score"], float)


def test_search_help_missing_index_raises(tmp_path: Path) -> None:
    cfg = Config(paths=Paths(index_dir=tmp_path / "indices"))
    with pytest.raises(FileNotFoundError) as exc:
        search_help("anything", config=cfg)
    assert "build-kb" in str(exc.value)


def test_search_help_top_k_zero_returns_empty(sample_kb: Path, tmp_path: Path) -> None:
    db_path = tmp_path / "indices" / "help.db"
    db_path.parent.mkdir()
    _build_index(sample_kb, db_path)

    cfg = Config(paths=Paths(help_kb_roots=(sample_kb,), index_dir=db_path.parent))
    assert search_help("numMU", top_k=0, config=cfg) == []

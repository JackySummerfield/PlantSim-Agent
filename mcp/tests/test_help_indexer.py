"""Tests for the help-markdown indexer."""

from __future__ import annotations

from pathlib import Path

from plantsim_mcp.indexers import help_md_to_fts
from plantsim_mcp.storage.sqlite import SQLiteFTSIndex


def test_iter_docs_splits_by_section(sample_kb: Path) -> None:
    docs = list(help_md_to_fts.iter_docs(sample_kb))
    sections = {d.section for d in docs}
    # We expect at least these from the fixture
    assert {"Attributes", "numMU", "capacity", "Methods", "move", "Strategy"} <= sections


def test_iter_docs_uses_relative_paths(sample_kb: Path) -> None:
    docs = list(help_md_to_fts.iter_docs(sample_kb))
    for d in docs:
        # File paths must be relative and use forward slashes
        assert not d.file_path.startswith("/")
        assert "\\" not in d.file_path
        assert d.file_path.endswith(".md")


def test_iter_docs_skips_empty_preamble(sample_kb: Path) -> None:
    docs = list(help_md_to_fts.iter_docs(sample_kb))
    # No empty-content preamble docs survive
    preambles = [d for d in docs if d.section == "(preamble)" and not d.content]
    assert preambles == []


def test_build_writes_to_index(sample_kb: Path, tmp_path: Path) -> None:
    with SQLiteFTSIndex(tmp_path / "help.db") as idx:
        n = help_md_to_fts.build(sample_kb, idx)
        assert n > 0
        hits = idx.search("numMU", top_k=3)
        assert hits
        assert hits[0].section == "numMU"
        assert hits[0].file_path == "Buffer.md"


def test_doc_ids_are_unique(sample_kb: Path) -> None:
    docs = list(help_md_to_fts.iter_docs(sample_kb))
    ids = [d.doc_id for d in docs]
    assert len(ids) == len(set(ids))


def test_nonexistent_root_raises(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(FileNotFoundError):
        list(help_md_to_fts.iter_docs(tmp_path / "does-not-exist"))


def test_fenced_code_block_does_not_split_section(tmp_path: Path) -> None:
    root = tmp_path / "kb"
    root.mkdir()
    (root / "code.md").write_text(
        "## Section A\n\nIntro\n\n```\n# this is code, not a heading\nfoo\n```\n\nMore text.\n",
        encoding="utf-8",
    )
    docs = list(help_md_to_fts.iter_docs(root))
    section_a = [d for d in docs if d.section == "Section A"]
    assert len(section_a) == 1
    assert "this is code" in section_a[0].content
    assert "More text" in section_a[0].content

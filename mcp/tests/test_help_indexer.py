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


def test_iter_docs_uses_labelled_paths(sample_kb: Path) -> None:
    docs = list(help_md_to_fts.iter_docs(sample_kb, label="kb_minimal"))
    for d in docs:
        # Labelled file paths: "<label>/<rel>", forward-slash only
        assert d.file_path.startswith("kb_minimal/")
        assert "\\" not in d.file_path
        assert d.file_path.endswith(".md")
        assert d.doc_id.startswith("kb_minimal::")


def test_iter_docs_default_label_is_root_basename(sample_kb: Path) -> None:
    docs = list(help_md_to_fts.iter_docs(sample_kb))
    assert all(d.file_path.startswith(f"{sample_kb.name}/") for d in docs)


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
        assert hits[0].file_path.endswith("Buffer.md")


def test_build_multi_root_aggregates(sample_kb: Path, tmp_path: Path) -> None:
    other = tmp_path / "kb_local"
    other.mkdir()
    (other / "Local.md").write_text(
        "## Internal\n\nCompany-internal standard about throughput.\n",
        encoding="utf-8",
    )
    with SQLiteFTSIndex(tmp_path / "help.db") as idx:
        n = help_md_to_fts.build([sample_kb, other], idx)
        assert n > 0
        # Hits from both roots are reachable
        assert idx.search("numMU", top_k=3)
        company_hits = idx.search("Company-internal throughput", top_k=3)
        assert company_hits
        assert any("kb_local" in h.file_path for h in company_hits)


def test_build_multi_root_skips_missing(sample_kb: Path, tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    with SQLiteFTSIndex(tmp_path / "help.db") as idx:
        n = help_md_to_fts.build([sample_kb, missing], idx)
        assert n > 0  # sample_kb still indexed


def test_build_multi_root_label_isolation(tmp_path: Path) -> None:
    # Two roots with same filename + same section shouldn't clobber each other
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "Buffer.md").write_text("## numMU\n\nDef from A.\n", encoding="utf-8")
    (b / "Buffer.md").write_text("## numMU\n\nDef from B.\n", encoding="utf-8")
    with SQLiteFTSIndex(tmp_path / "help.db") as idx:
        n = help_md_to_fts.build([a, b], idx)
        assert n == 2
        assert idx.count() == 2


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

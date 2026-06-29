"""Tests for the SimTalk validation rules + tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from plantsim_mcp.config import Config, Paths
from plantsim_mcp.indexers.psfm_indexer import build_project_index
from plantsim_mcp.rules import RULES, validate
from plantsim_mcp.storage.project import ProjectStore
from plantsim_mcp.tools.validate_simtalk import validate_simtalk


# ---------------------------------------------------------------------------
# Rule-level tests — direct on `validate(source)`
# ---------------------------------------------------------------------------


def test_outdated_names_flagged() -> None:
    src = "var x : object := freeEntry\n"
    issues = [i for i in validate(src) if i.rule_id == "ST001"]
    assert len(issues) == 1
    assert "freeEntry" in issues[0].message
    assert "EntranceFree" in issues[0].message
    assert issues[0].line == 1


def test_outdated_names_skips_strings_and_comments() -> None:
    src = (
        '-- legacy: freeEntry replaced by EntranceFree\n'
        'var msg : string := "freeEntry was the old name"\n'
        'print(msg)\n'
    )
    issues = [i for i in validate(src) if i.rule_id == "ST001"]
    assert issues == []


def test_outdated_names_block_comment_spanning_lines() -> None:
    src = (
        "/*\n"
        " * freeEntry is deprecated\n"
        " */\n"
        "var ok : boolean := EntranceFree\n"
    )
    issues = [i for i in validate(src) if i.rule_id == "ST001"]
    assert issues == []


def test_move_return_ignored_flagged() -> None:
    src = "Station1.Mu.move(Station2)\n"
    issues = [i for i in validate(src) if i.rule_id == "ST002"]
    assert len(issues) == 1
    assert issues[0].line == 1


def test_move_return_captured_not_flagged() -> None:
    src = (
        "var ok : boolean\n"
        "ok := Station1.Mu.move(Station2)\n"
        "if Station1.Mu.move(Station2) = false\n"
        "    debug\n"
        "end\n"
    )
    issues = [i for i in validate(src) if i.rule_id == "ST002"]
    assert issues == []


def test_move_attribute_access_not_flagged() -> None:
    # `Table.move[1,2]` is column access, not a method call.
    src = "var v : any := Table.move[1, 2]\n"
    issues = [i for i in validate(src) if i.rule_id == "ST002"]
    assert issues == []


def test_var_untyped_flagged() -> None:
    src = "var counter := 0\n"
    issues = [i for i in validate(src) if i.rule_id == "ST003"]
    assert len(issues) == 1
    assert "counter" in issues[0].message


def test_var_typed_not_flagged() -> None:
    src = (
        "var counter : integer := 0\n"
        "var name : string := \"x\"\n"
        "for var i : integer := 1 to 10\n"
        "    counter += 1\n"
        "next\n"
    )
    issues = [i for i in validate(src) if i.rule_id == "ST003"]
    assert issues == []


def test_simtalk_1_decl_flagged() -> None:
    src = (
        "is var x : integer\n"
        "is var y : real\n"
        "is real z\n"
    )
    issues = [i for i in validate(src) if i.rule_id == "ST004"]
    assert len(issues) == 3


def test_validate_returns_sorted_issues() -> None:
    src = (
        "var counter := 0\n"               # ST003
        "Station1.Mu.move(Station2)\n"     # ST002
        "freeEntry\n"                      # ST001
    )
    issues = validate(src)
    # Sort key is (line, column, rule_id) — order matches source order.
    assert [i.line for i in issues] == [1, 2, 3]
    assert [i.rule_id for i in issues] == ["ST003", "ST002", "ST001"]


def test_ignore_rules_filters() -> None:
    src = "var counter := 0\nStation1.Mu.move(Station2)\n"
    issues = validate(src, ignore_rules=["ST002"])
    assert all(i.rule_id != "ST002" for i in issues)
    assert any(i.rule_id == "ST003" for i in issues)


def test_rule_registry_complete() -> None:
    assert set(RULES.keys()) == {"ST001", "ST002", "ST003", "ST004"}


# ---------------------------------------------------------------------------
# MCP-tool wrapper tests
# ---------------------------------------------------------------------------


def test_validate_simtalk_inline_source() -> None:
    out = validate_simtalk(source="var counter := 0\n")
    assert out
    assert out[0]["rule_id"] == "ST003"
    assert "fix_hint" in out[0]


def test_validate_simtalk_requires_source_or_uuid() -> None:
    with pytest.raises(ValueError):
        validate_simtalk()


def test_validate_simtalk_by_uuid_against_indexed_project(
    tmp_path: Path, sample_psfm: Path
) -> None:
    """End-to-end: build project DB, validate a Method by UUID."""
    paths = Paths(index_dir=tmp_path / "idx")
    cfg = Config(paths=paths)
    with ProjectStore(cfg.paths.project_db) as store:
        build_project_index(sample_psfm, store)

    # 33333... is the parent Station Init Method (Program body present)
    issues = validate_simtalk(
        uuid="33333333-3333-3333-3333-333333333333", config=cfg
    )
    # The body contains `root.PalletCapacity := 20` + `InitPalletJackFleet.executeIn(0)`
    # No untyped var, no .move, no outdated names — should be clean.
    assert issues == []


def test_validate_simtalk_by_uuid_missing_body(tmp_path: Path, sample_psfm: Path) -> None:
    paths = Paths(index_dir=tmp_path / "idx")
    cfg = Config(paths=paths)
    with ProjectStore(cfg.paths.project_db) as store:
        build_project_index(sample_psfm, store)
    with pytest.raises(KeyError):
        # UUID exists but no body (a Variable, not a Method)
        validate_simtalk(uuid="22222222-2222-2222-2222-222222222222", config=cfg)


def test_validate_simtalk_db_missing(tmp_path: Path) -> None:
    cfg = Config(paths=Paths(index_dir=tmp_path / "nope"))
    with pytest.raises(FileNotFoundError):
        validate_simtalk(uuid="any", config=cfg)

"""Tests for the CLI subcommands (build-kb, build-project)."""

from __future__ import annotations

from pathlib import Path

import pytest

from plantsim_mcp.server import main


def test_cli_build_kb_with_root(tmp_path: Path, sample_kb: Path, capsys, monkeypatch) -> None:
    """`build-kb --root <dir>` indexes a KB even with no config file."""
    # Force PLANTSIM_AGENT_HOME so the index_dir falls under tmp_path.
    monkeypatch.setenv("PLANTSIM_AGENT_HOME", str(tmp_path))
    rc = main(["build-kb", "--root", str(sample_kb)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "docs written" in out
    # The expected DB path now exists
    assert (tmp_path / "indices" / "help.db").exists()


def test_cli_build_kb_missing_root(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.setenv("PLANTSIM_AGENT_HOME", str(tmp_path))
    rc = main(["build-kb", "--root", str(tmp_path / "does-not-exist")])
    assert rc == 2
    err = capsys.readouterr().err
    assert "KB root not found" in err


def test_cli_build_kb_no_root_no_config(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.setenv("PLANTSIM_AGENT_HOME", str(tmp_path))
    rc = main(["build-kb"])
    assert rc == 2
    assert "nothing to index" in capsys.readouterr().err


def test_cli_build_kb_with_fullmd_src(tmp_path: Path, capsys, monkeypatch) -> None:
    """`build-kb --fullmd-src <file> --chapters 11` indexes a fullmd source."""
    monkeypatch.setenv("PLANTSIM_AGENT_HOME", str(tmp_path))
    src = tmp_path / "fullmd" / "_full_docling_code_tagged.md"
    src.parent.mkdir()
    src.write_text(
        "# 11. Objects Reference Help\n\n"
        "## Material Flow Objects\n\n"
        "### Source\n\n"
        "#### Attributes\n\n"
        "##### Stop [SimTalk] - Source\n\n"
        "Body for Stop.\n",
        encoding="utf-8",
    )
    rc = main(
        [
            "build-kb",
            "--fullmd-src",
            str(src),
            "--chapters",
            "11",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "fullmd source" in out
    assert "chapters=11" in out
    assert (tmp_path / "indices" / "help.db").exists()


def test_cli_build_kb_missing_fullmd_src(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.setenv("PLANTSIM_AGENT_HOME", str(tmp_path))
    rc = main(["build-kb", "--fullmd-src", str(tmp_path / "nope.md")])
    assert rc == 2
    assert "fullmd source not found" in capsys.readouterr().err


def test_cli_build_project_with_path(
    tmp_path: Path, sample_psfm: Path, capsys, monkeypatch
) -> None:
    monkeypatch.setenv("PLANTSIM_AGENT_HOME", str(tmp_path))
    rc = main(["build-project", "--project", str(sample_psfm)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "objects=" in out
    assert (tmp_path / "indices" / "project.db").exists()


def test_cli_build_project_missing(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.setenv("PLANTSIM_AGENT_HOME", str(tmp_path))
    rc = main(["build-project", "--project", str(tmp_path / "nope.psfm")])
    assert rc == 2
    assert "project path not found" in capsys.readouterr().err

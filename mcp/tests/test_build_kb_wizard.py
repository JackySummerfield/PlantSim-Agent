"""Tests for the ``plantsim-copilot-mcp init`` wizard."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from plantsim_mcp import build_kb_wizard
from plantsim_mcp.build_kb_wizard import (
    WizardAnswers,
    cmd_init,
    render_config_toml,
    write_config,
)
from plantsim_mcp.config import load


# ---------------------------------------------------------------------------
# Pure helpers — TOML rendering / writing
# ---------------------------------------------------------------------------


def test_render_minimal_config(tmp_path: Path) -> None:
    ans = WizardAnswers(index_dir=tmp_path / "indices")
    toml = render_config_toml(ans)
    assert "[paths]" in toml
    assert "index_dir" in toml
    # No empty arrays for unset fields
    assert "help_kb_roots" not in toml
    assert "fullmd_src" not in toml
    assert "default_project" not in toml


def test_render_full_config(tmp_path: Path) -> None:
    kb1 = tmp_path / "kb1"
    kb1.mkdir()
    kb2 = tmp_path / "kb2"
    kb2.mkdir()
    fullmd = tmp_path / "full.md"
    fullmd.write_text("# stub", encoding="utf-8")
    project = tmp_path / "p.psfm"
    project.mkdir()

    ans = WizardAnswers(
        help_kb_roots=[kb1, kb2],
        fullmd_src=fullmd,
        fullmd_chapters=[11, 12],
        default_project=project,
        index_dir=tmp_path / "indices",
    )
    toml = render_config_toml(ans)
    # All paths present and forward-slashed (TOML basic strings)
    assert "kb1" in toml and "kb2" in toml
    assert "full.md" in toml
    assert "p.psfm" in toml
    assert "fullmd_chapters = [11, 12]" in toml
    # No backslashes leaked from Windows paths
    assert "\\" not in toml


def test_round_trip_via_load(tmp_path: Path) -> None:
    """Render → write → load yields a Config matching the wizard answers."""
    kb = tmp_path / "kb"
    kb.mkdir()
    full = tmp_path / "full.md"
    full.write_text("# stub", encoding="utf-8")
    ans = WizardAnswers(
        help_kb_roots=[kb],
        fullmd_src=full,
        fullmd_chapters=[11, 13],
        default_project=None,
        index_dir=tmp_path / "indices",
    )
    cfg_path = tmp_path / "config.toml"
    write_config(ans, cfg_path)

    cfg = load(cfg_path)
    assert cfg.source == cfg_path
    assert cfg.paths.help_kb_roots == (kb,)
    assert cfg.paths.fullmd_src == full
    assert cfg.paths.fullmd_chapters == (11, 13)
    assert cfg.paths.index_dir == (tmp_path / "indices")
    assert cfg.paths.default_project is None


# ---------------------------------------------------------------------------
# Non-interactive CLI flow
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ``PLANTSIM_AGENT_HOME`` at a temp dir so the wizard doesn't
    write to the user's real ``~/.plantsim-agent``."""
    home = tmp_path / "agent_home"
    home.mkdir()
    monkeypatch.setenv("PLANTSIM_AGENT_HOME", str(home))
    return home


def _make_args(**overrides: Any) -> Any:
    """Build an argparse.Namespace-like object for cmd_init."""
    import argparse

    base = {
        "config": None,
        "force": False,
        "non_interactive": True,
        "kb_root": None,
        "fullmd_src": None,
        "chapters": None,
        "project": None,
        "index_dir": None,
        "build": False,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def test_non_interactive_writes_minimal_config(
    isolated_home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    kb = tmp_path / "kb"
    kb.mkdir()
    (kb / "a.md").write_text("# stub\nbody", encoding="utf-8")

    args = _make_args(kb_root=[str(kb)], build=False)
    rc = cmd_init(args)
    assert rc == 0

    cfg_path = isolated_home / "config.toml"
    assert cfg_path.is_file()
    cfg = load(cfg_path)
    assert cfg.paths.help_kb_roots == (kb.resolve(),)
    # No build was requested → no help.db
    assert not (isolated_home / "indices" / "help.db").exists()


def test_non_interactive_with_build(
    isolated_home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    kb = tmp_path / "kb"
    kb.mkdir()
    (kb / "intro.md").write_text(
        "# Intro\n\n## Section A\nFirst paragraph about Buffers.\n",
        encoding="utf-8",
    )

    args = _make_args(kb_root=[str(kb)], build=True)
    rc = cmd_init(args)
    assert rc == 0

    help_db = isolated_home / "indices" / "help.db"
    assert help_db.is_file(), "wizard --build should have created help.db"

    # Sanity: the FTS index should actually contain a doc.
    from plantsim_mcp.storage.sqlite import SQLiteFTSIndex

    with SQLiteFTSIndex(help_db) as idx:
        assert idx.count() > 0


def test_non_interactive_rejects_missing_kb_root(
    isolated_home: Path, tmp_path: Path
) -> None:
    args = _make_args(kb_root=[str(tmp_path / "does_not_exist")])
    with pytest.raises(SystemExit) as exc:
        cmd_init(args)
    assert "not a directory" in str(exc.value)


def test_non_interactive_custom_config_path(
    isolated_home: Path, tmp_path: Path
) -> None:
    kb = tmp_path / "kb"
    kb.mkdir()
    custom = tmp_path / "subdir" / "my_config.toml"
    args = _make_args(kb_root=[str(kb)], config=str(custom))
    rc = cmd_init(args)
    assert rc == 0
    assert custom.is_file()


def test_non_interactive_overrides_index_dir(
    isolated_home: Path, tmp_path: Path
) -> None:
    kb = tmp_path / "kb"
    kb.mkdir()
    custom_idx = tmp_path / "custom_indices"
    args = _make_args(kb_root=[str(kb)], index_dir=str(custom_idx))
    rc = cmd_init(args)
    assert rc == 0
    cfg = load(isolated_home / "config.toml")
    assert cfg.paths.index_dir == custom_idx.resolve()


def test_render_chapters_round_trip(tmp_path: Path) -> None:
    """Issue check: chapter list survives the render → load round trip."""
    full = tmp_path / "full.md"
    full.write_text("# x", encoding="utf-8")
    ans = WizardAnswers(
        fullmd_src=full,
        fullmd_chapters=[15],
        index_dir=tmp_path / "idx",
    )
    cfg_path = tmp_path / "config.toml"
    write_config(ans, cfg_path)
    cfg = load(cfg_path)
    assert cfg.paths.fullmd_chapters == (15,)

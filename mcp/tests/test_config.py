"""Tests for configuration loading."""

from __future__ import annotations

from pathlib import Path

from plantsim_mcp import config as cfg_mod


def test_load_missing_returns_defaults(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PLANTSIM_AGENT_HOME", str(tmp_path))
    cfg = cfg_mod.load()
    assert cfg.source is None
    assert cfg.paths.help_kb_root is None
    assert cfg.paths.index_dir == tmp_path / "indices"


def test_load_parses_toml(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PLANTSIM_AGENT_HOME", str(tmp_path))
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        '[paths]\n'
        f'help_kb_root = "{(tmp_path / "kb").as_posix()}"\n'
        f'index_dir    = "{(tmp_path / "idx").as_posix()}"\n',
        encoding="utf-8",
    )
    cfg = cfg_mod.load()
    assert cfg.source == config_path
    assert cfg.paths.help_kb_root == tmp_path / "kb"
    assert cfg.paths.index_dir == tmp_path / "idx"
    assert cfg.paths.help_db == tmp_path / "idx" / "help.db"


def test_agent_home_respects_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PLANTSIM_AGENT_HOME", str(tmp_path))
    assert cfg_mod.agent_home() == tmp_path.resolve()

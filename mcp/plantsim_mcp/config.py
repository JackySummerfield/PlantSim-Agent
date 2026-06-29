"""Configuration loading for plantsim-mcp.

Configuration lives in a single TOML file at
``~/.plantsim-agent/config.toml`` (path overridable via the
``PLANTSIM_AGENT_HOME`` environment variable).

A typical file looks like::

    [paths]
    help_kb_root    = "C:/Users/me/my-pts-help/markdown"
    index_dir       = "C:/Users/me/.plantsim-agent/indices"
    default_project = ""   # optional .psfm path

For development, when no config file is present we fall back to safe
defaults under ``$PLANTSIM_AGENT_HOME`` so the server still starts and
gives a clear error from each tool rather than crashing on import.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib  # type: ignore[import-not-found]
else:  # pragma: no cover - exercised on 3.10 only
    import tomli as tomllib  # type: ignore[no-redef]


CONFIG_FILENAME = "config.toml"


def agent_home() -> Path:
    """Return ``~/.plantsim-agent`` (or ``$PLANTSIM_AGENT_HOME`` if set)."""
    override = os.environ.get("PLANTSIM_AGENT_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".plantsim-agent"


@dataclass(frozen=True)
class Paths:
    """Filesystem paths used by indexers and tools."""

    help_kb_root: Path | None = None
    """Root of the user's PTS Help markdown tree (input to indexer)."""

    index_dir: Path = field(default_factory=lambda: agent_home() / "indices")
    """Directory holding generated SQLite indices (``help.db``, ``project.db``)."""

    default_project: Path | None = None
    """Optional default ``.psfm`` project; tools may require an explicit path otherwise."""

    @property
    def help_db(self) -> Path:
        return self.index_dir / "help.db"

    @property
    def project_db(self) -> Path:
        return self.index_dir / "project.db"


@dataclass(frozen=True)
class Config:
    paths: Paths = field(default_factory=Paths)
    source: Path | None = None
    """Path to the loaded config file, ``None`` if defaults were used."""


def _coerce_path(value: object) -> Path | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise TypeError(f"expected string path, got {type(value).__name__}: {value!r}")
    return Path(value).expanduser()


def load(config_path: Path | None = None) -> Config:
    """Load configuration from disk.

    ``config_path`` overrides the default ``~/.plantsim-agent/config.toml``
    location. Missing files yield a default :class:`Config` instance.
    """
    target = config_path or (agent_home() / CONFIG_FILENAME)
    if not target.exists():
        return Config()

    with open(target, "rb") as fh:
        data = tomllib.load(fh)

    paths_section = data.get("paths", {}) if isinstance(data, dict) else {}
    paths = Paths(
        help_kb_root=_coerce_path(paths_section.get("help_kb_root")),
        index_dir=_coerce_path(paths_section.get("index_dir"))
        or (agent_home() / "indices"),
        default_project=_coerce_path(paths_section.get("default_project")),
    )
    return Config(paths=paths, source=target)

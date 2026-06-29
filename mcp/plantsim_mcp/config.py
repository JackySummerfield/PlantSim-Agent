"""Configuration loading for plantsim-mcp.

Configuration lives in a single TOML file at
``~/.plantsim-agent/config.toml`` (path overridable via the
``PLANTSIM_AGENT_HOME`` environment variable).

A typical file looks like::

    [paths]
    # One or more roots; later entries override earlier ones on doc_id
    # collision, so user-private knowledge wins over the public sample.
    help_kb_roots = [
        "C:/Users/me/.copilot/plantsim-agent/kb_minimal",
        "C:/Users/me/.copilot/plantsim-agent/kb_local/pts_help_2504",
    ]
    index_dir       = "C:/Users/me/.plantsim-agent/indices"
    default_project = ""   # optional .psfm path

The single-string ``help_kb_root`` form is still accepted for
backward compatibility and is interpreted as a one-element list.

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

    help_kb_roots: tuple[Path, ...] = ()
    """Roots of markdown KB trees (e.g. ``kb_minimal``, ``kb_local/pts_help_2504``).

    The indexer aggregates docs across all roots; ``help_kb_root`` (single
    path) is also accepted and folded into this tuple for back-compat.
    """

    index_dir: Path = field(default_factory=lambda: agent_home() / "indices")
    """Directory holding generated SQLite indices (``help.db``, ``project.db``)."""

    default_project: Path | None = None
    """Optional default ``.psfm`` project; tools may require an explicit path otherwise."""

    @property
    def help_kb_root(self) -> Path | None:
        """First configured KB root, for tools/scripts that want a single path."""
        return self.help_kb_roots[0] if self.help_kb_roots else None

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


def _coerce_path_list(value: object) -> tuple[Path, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        path = _coerce_path(value)
        return (path,) if path else ()
    if isinstance(value, (list, tuple)):
        out: list[Path] = []
        for item in value:
            p = _coerce_path(item)
            if p:
                out.append(p)
        return tuple(out)
    raise TypeError(f"expected list of string paths, got {type(value).__name__}: {value!r}")


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

    # `help_kb_roots` (preferred) takes precedence; fall back to the
    # legacy `help_kb_root` single string.
    roots = _coerce_path_list(paths_section.get("help_kb_roots"))
    if not roots:
        roots = _coerce_path_list(paths_section.get("help_kb_root"))

    paths = Paths(
        help_kb_roots=roots,
        index_dir=_coerce_path(paths_section.get("index_dir"))
        or (agent_home() / "indices"),
        default_project=_coerce_path(paths_section.get("default_project")),
    )
    return Config(paths=paths, source=target)

"""FastMCP server entry point.

This module is what ``pyproject.toml``'s ``plantsim-copilot-mcp``
console script invokes. It wires the (currently small) set of tools
into a :class:`FastMCP` instance and runs it on stdio.

The server is *thin*: every tool's logic lives in
``plantsim_mcp.tools.<name>``, and this module is only responsible for
schema registration. Keeping it thin makes the tool functions trivial
to unit-test without bringing FastMCP into the test loop.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .config import Config, load
from .tools import find_callers as _find_callers
from .tools import find_method as _find_method
from .tools import get_api as _get_api
from .tools import get_object_graph as _get_object_graph
from .tools import search_code as _search_code
from .tools import search_help as _search_help
from .tools import validate_simtalk as _validate_simtalk


def build_server(config: Config | None = None) -> Any:
    """Construct (but do not run) the FastMCP server.

    The function lazily imports :mod:`fastmcp` so that test code and
    one-off scripts can import :mod:`plantsim_mcp.server` without
    requiring FastMCP to be installed.
    """
    from fastmcp import FastMCP  # type: ignore[import-not-found]

    cfg = config or load()
    mcp = FastMCP(name="plantsim-copilot-mcp", version=__version__)

    @mcp.tool()
    def search_help(query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Search the local PTS Help knowledge base (FTS5).

        Args:
            query: Natural-language question or keyword phrase.
            top_k: Maximum number of results (default 5).
        """
        return _search_help.search_help(query=query, top_k=top_k, config=cfg)

    @mcp.tool()
    def find_method(
        name: str, include_overrides: bool = True
    ) -> list[dict[str, Any]]:
        """Find a SimTalk Method by name in the indexed .psfm project.

        Returns the parent definition plus any overriding children
        (so the caller can audit inheritance impact before editing).

        Args:
            name: Method's Name field (case-sensitive).
            include_overrides: When True (default), also return children
                whose Origin points at this method.
        """
        return _find_method.find_method(
            name=name, include_overrides=include_overrides, config=cfg
        )

    @mcp.tool()
    def find_callers(name: str, top_k: int = 20) -> list[dict[str, Any]]:
        """Find SimTalk method bodies that mention the given identifier.

        Args:
            name: Plain identifier (letters/digits/underscore only).
            top_k: Maximum hits (default 20).
        """
        return _find_callers.find_callers(name=name, top_k=top_k, config=cfg)

    @mcp.tool()
    def search_code(query: str, top_k: int = 20) -> list[dict[str, Any]]:
        """Full-text search across all SimTalk bodies in the project.

        Args:
            query: FTS5 keyword phrase.
            top_k: Maximum hits (default 20).
        """
        return _search_code.search_code(query=query, top_k=top_k, config=cfg)

    @mcp.tool()
    def get_object_graph(
        name: str | None = None, uuid: str | None = None
    ) -> dict[str, Any]:
        """Return the inheritance + material-flow neighbourhood of an object.

        Args:
            name: Object Name (used when uuid is not supplied).
            uuid: Exact UUID (preferred when both are given).
        """
        return _get_object_graph.get_object_graph(name=name, uuid=uuid, config=cfg)

    @mcp.tool()
    def validate_simtalk(
        source: str | None = None,
        uuid: str | None = None,
        ignore_rules: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Lint a SimTalk method body for SimTalk 2.0 best-practice issues.

        Supply either inline ``source`` or a ``uuid`` of an indexed Method.
        Returns issues with rule_id, severity, line/column, message, and a
        fix_hint where applicable.

        Args:
            source: Raw SimTalk source. Wins if both are provided.
            uuid: UUID of an indexed Method body to validate.
            ignore_rules: Rule IDs to skip (e.g. ["ST003"]).
        """
        return _validate_simtalk.validate_simtalk(
            source=source, uuid=uuid, ignore_rules=ignore_rules, config=cfg
        )

    @mcp.tool()
    def get_api(name: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Precise SimTalk API lookup against the help KB.

        Returns help-doc sections titled "<Name> [SimTalk]" (with any
        disambiguator suffix). For natural-language questions use
        search_help instead.

        Args:
            name: SimTalk identifier (case-sensitive).
            top_k: Maximum entries to return (default 5).
        """
        return _get_api.get_api(name=name, top_k=top_k, config=cfg)

    return mcp


def _cmd_build_project(args: argparse.Namespace) -> int:
    """Build / rebuild the project index DB."""
    from .indexers.psfm_indexer import build_project_index
    from .storage.project import ProjectStore

    cfg = load()
    project_path = (
        Path(args.project).resolve() if args.project else cfg.paths.default_project
    )
    if project_path is None:
        print(
            "error: no --project given and no [paths].default_project in config",
            file=sys.stderr,
        )
        return 2
    if not project_path.is_dir():
        print(f"error: project path not found: {project_path}", file=sys.stderr)
        return 2

    db_path = cfg.paths.project_db
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    with ProjectStore(db_path) as store:
        result = build_project_index(project_path, store)
    print(
        f"indexed {project_path} -> {db_path}\n"
        f"  files={result.files_scanned}  docs={result.docs_scanned}\n"
        f"  objects={len(result.objects)}  code_units={len(result.code_units)}  "
        f"edges={len(result.edges)}  skipped={len(result.skipped)}"
    )
    return 0


def _cmd_build_kb(args: argparse.Namespace) -> int:
    """Build / rebuild the help KB index from configured roots."""
    from .indexers.help_md_to_fts import build
    from .storage.sqlite import SQLiteFTSIndex

    cfg = load()
    if args.root:
        roots = [Path(r).resolve() for r in args.root]
    else:
        roots = list(cfg.paths.help_kb_roots)
    if not roots:
        print(
            "error: no --root given and no [paths].help_kb_roots in config",
            file=sys.stderr,
        )
        return 2
    missing = [r for r in roots if not r.is_dir()]
    if missing:
        for r in missing:
            print(f"error: KB root not found: {r}", file=sys.stderr)
        return 2

    db_path = cfg.paths.help_db
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    with SQLiteFTSIndex(db_path) as idx:
        idx.delete_all()
        written = build(roots, idx)
    print(
        f"indexed {len(roots)} root(s) -> {db_path}\n"
        f"  docs written: {written}"
    )
    for r in roots:
        print(f"  - {r}")
    return 0


def _cmd_serve(_args: argparse.Namespace) -> int:
    build_server().run()
    return 0


def main(argv: list[str] | None = None) -> int:
    """Console-script entry point.

    Subcommands:
      * ``serve`` (default) — run the MCP server on stdio
      * ``build-kb [--root <md-dir>]`` — index a markdown KB
      * ``build-project --project <path>`` — index a ``.psfm`` folder
    """
    parser = argparse.ArgumentParser(prog="plantsim-copilot-mcp")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("serve", help="run MCP server on stdio (default)")

    bp = sub.add_parser("build-project", help="index a .psfm project folder")
    bp.add_argument(
        "--project",
        default=None,
        help="path to .psfm folder (overrides config.paths.default_project)",
    )

    bk = sub.add_parser("build-kb", help="index the help knowledge base")
    bk.add_argument(
        "--root",
        action="append",
        default=None,
        help="markdown KB root (repeat for multiple). "
        "Overrides config.paths.help_kb_roots.",
    )

    args = parser.parse_args(argv)
    if args.cmd == "build-project":
        return _cmd_build_project(args)
    if args.cmd == "build-kb":
        return _cmd_build_kb(args)
    return _cmd_serve(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

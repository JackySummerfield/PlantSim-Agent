"""Repo-clone shim — runs the same wizard as ``plantsim-copilot-mcp init``.

Use this when you have the repo checked out and want to avoid installing
the console-script entry point first:

    python scripts/build_kb.py            # interactive
    python scripts/build_kb.py --help     # see non-interactive flags

The real implementation lives in :mod:`plantsim_mcp.build_kb_wizard` so
both entry points share one source of truth.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from a fresh clone without `pip install -e mcp/`.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_MCP_SRC = _REPO_ROOT / "mcp"
if str(_MCP_SRC) not in sys.path:
    sys.path.insert(0, str(_MCP_SRC))

from plantsim_mcp.build_kb_wizard import add_init_subparser, cmd_init  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="build_kb.py",
        description="Interactive wizard to configure and build the "
        "plantsim-copilot-mcp knowledge base.",
    )
    sub = parser.add_subparsers(dest="cmd")
    add_init_subparser(sub)
    # Make `init` the default subcommand so plain `python scripts/build_kb.py` works.
    args = parser.parse_args((argv if argv is not None else sys.argv[1:]) or ["init"])
    return cmd_init(args)


if __name__ == "__main__":
    sys.exit(main())

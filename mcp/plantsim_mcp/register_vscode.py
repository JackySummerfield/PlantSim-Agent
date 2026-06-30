"""Register this MCP server in VS Code's user-level ``mcp.json``.

This is the last manual step in the cold-install path. Without this
module, the user has to find the right ``mcp.json`` location for their
OS, parse the JSON, merge a ``servers.plantsim-copilot-mcp`` entry
without clobbering whatever else they have, and pick the right
``command`` value depending on whether the console-script is on
``PATH``. With this module, they run ``plantsim-copilot-mcp
register-vscode`` and it does all of the above idempotently.

Design notes
------------
* **Per-OS defaults** — Windows ``%APPDATA%\\Code\\User\\mcp.json``,
  macOS ``~/Library/Application Support/Code/User/mcp.json``, Linux
  ``~/.config/Code/User/mcp.json``. Override with ``--target``.
* **JSON, not JSONC** — VS Code accepts comments in some config files,
  but the user-level ``mcp.json`` format documented by Microsoft is
  plain JSON. If the user's file contains comments we surface a clear
  error and ask them to strip them or pass ``--target`` to a different
  file.
* **Idempotent** — re-running with the same arguments is a no-op when
  the existing entry already matches. A different existing entry under
  the same key is replaced only with ``--force``; otherwise we report
  the conflict and exit non-zero.
* **Backup** — any time we overwrite an existing file we first copy it
  to ``<file>.bak-<timestamp>``.
* **Preserves siblings** — other servers and any other top-level keys
  (``inputs``, ``env``, …) are kept verbatim.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

SERVER_NAME = "plantsim-copilot-mcp"


# ---------------------------------------------------------------------------
# Path discovery
# ---------------------------------------------------------------------------


def default_mcp_json_path(system: str | None = None) -> Path:
    """Return the conventional user-level ``mcp.json`` path for this OS.

    ``system`` may be passed for testing (one of ``"Windows"``,
    ``"Darwin"``, ``"Linux"``); defaults to :func:`platform.system`.

    Raises :class:`RuntimeError` on platforms we don't know about.
    """
    sysname = (system or platform.system()).lower()
    home = Path.home()
    if sysname.startswith("win"):
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else home / "AppData" / "Roaming"
        return base / "Code" / "User" / "mcp.json"
    if sysname == "darwin":
        return home / "Library" / "Application Support" / "Code" / "User" / "mcp.json"
    if sysname == "linux":
        return home / ".config" / "Code" / "User" / "mcp.json"
    raise RuntimeError(f"unsupported OS for VS Code mcp.json discovery: {sysname!r}")


# ---------------------------------------------------------------------------
# Command resolution
# ---------------------------------------------------------------------------


def resolve_command(explicit: str | None = None, *, prefer_absolute: bool = False) -> str:
    """Pick the ``command`` value to write into ``mcp.json``.

    Order:

    1. ``explicit`` (from ``--command``) if given.
    2. If ``plantsim-copilot-mcp`` is on PATH, return either the bare
       name (default) or its absolute path (``prefer_absolute=True``).
    3. Otherwise, return the bare name and let the caller warn the
       user — they'll need to fix it manually.
    """
    if explicit:
        return explicit

    found = shutil.which(SERVER_NAME)
    if not found:
        return SERVER_NAME

    if prefer_absolute:
        return found

    return SERVER_NAME


# ---------------------------------------------------------------------------
# JSON merge
# ---------------------------------------------------------------------------


def make_server_entry(command: str) -> dict[str, Any]:
    """The canonical entry we write under ``servers[SERVER_NAME]``."""
    return {
        "type": "stdio",
        "command": command,
        "args": ["serve"],
    }


def _load_existing(path: Path) -> dict[str, Any]:
    """Read an existing ``mcp.json``. Empty file → empty doc."""
    if not path.exists() or path.stat().st_size == 0:
        return {}
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"could not parse existing {path} as JSON: {exc.msg} (line {exc.lineno}). "
            "If it contains comments, strip them or pass --target to a different file."
        ) from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"{path} is valid JSON but not an object — refusing to merge")
    return data


def merge_entry(
    existing: dict[str, Any],
    server_name: str,
    entry: dict[str, Any],
    *,
    force: bool = False,
) -> tuple[dict[str, Any], str]:
    """Merge ``entry`` into ``existing`` under ``servers.<server_name>``.

    Returns ``(merged, status)`` where status is one of:

    * ``"added"`` — the entry didn't exist
    * ``"updated"`` — it existed, was different, and ``force`` was set
    * ``"unchanged"`` — it already matched the desired entry
    * ``"conflict"`` — it existed and differed but ``force`` was off;
      ``merged`` is returned unchanged in that case.
    """
    merged = dict(existing)  # shallow copy — we'll deep-write `servers`
    servers = dict(merged.get("servers") or {})

    current = servers.get(server_name)
    if current == entry:
        # Already correct — but ensure we still expose the same structure
        # in case `servers` key was missing entirely (rare on empty docs).
        merged["servers"] = servers
        return merged, "unchanged"

    if current is None:
        servers[server_name] = entry
        merged["servers"] = servers
        return merged, "added"

    if not force:
        merged["servers"] = servers  # untouched
        return merged, "conflict"

    servers[server_name] = entry
    merged["servers"] = servers
    return merged, "updated"


def _write_with_backup(path: Path, data: dict[str, Any]) -> Path | None:
    """Write ``data`` as pretty JSON to ``path``. Backup the old file.

    Returns the backup path if one was created, else ``None``.
    """
    backup: Path | None = None
    if path.exists():
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = path.with_suffix(path.suffix + f".bak-{stamp}")
        shutil.copy2(path, backup)

    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    path.write_text(serialized, encoding="utf-8")
    return backup


# ---------------------------------------------------------------------------
# Top-level orchestration
# ---------------------------------------------------------------------------


def register(
    target: Path | None = None,
    *,
    command: str | None = None,
    force: bool = False,
    prefer_absolute: bool = False,
    dry_run: bool = False,
    out=sys.stdout,
) -> int:
    """Resolve the target, build the entry, merge, and write.

    Returns a shell-style exit code (0 = OK, non-zero on conflict /
    error). The caller is responsible for trapping :class:`RuntimeError`.
    """
    path = target or default_mcp_json_path()
    cmd = resolve_command(command, prefer_absolute=prefer_absolute)
    entry = make_server_entry(cmd)

    print(f"VS Code mcp.json : {path}", file=out)
    print(f"server name      : {SERVER_NAME}", file=out)
    print(f"command          : {cmd}", file=out)

    existing = _load_existing(path)
    merged, status = merge_entry(existing, SERVER_NAME, entry, force=force)

    if status == "unchanged":
        print(f"\nNo change — '{SERVER_NAME}' already configured correctly.", file=out)
        return 0

    if status == "conflict":
        current = (existing.get("servers") or {}).get(SERVER_NAME)
        print(
            f"\nConflict: '{SERVER_NAME}' already exists in {path} "
            "but does not match the desired entry.",
            file=out,
        )
        print("  current : " + json.dumps(current, ensure_ascii=False), file=out)
        print("  desired : " + json.dumps(entry, ensure_ascii=False), file=out)
        print(
            "\nRerun with --force to overwrite, "
            "or edit the file manually if you have a custom setup.",
            file=out,
        )
        return 2

    # added / updated → write
    if dry_run:
        print(f"\n[dry-run] would write ({status}):", file=out)
        print(json.dumps(merged, indent=2, ensure_ascii=False), file=out)
        return 0

    backup = _write_with_backup(path, merged)
    if backup is not None:
        print(f"\nBackup saved to {backup}", file=out)
    print(f"\n{status.capitalize()} '{SERVER_NAME}' in {path}", file=out)
    print(
        "\nReload VS Code (Ctrl+Shift+P -> 'Developer: Reload Window') "
        "to pick up the new MCP server.",
        file=out,
    )

    if cmd == SERVER_NAME and shutil.which(SERVER_NAME) is None:
        print(
            f"\nWARNING: '{SERVER_NAME}' was not found on PATH. "
            "If VS Code can't find it on launch, rerun with "
            "`register-vscode --absolute` to write the absolute path "
            "instead, or use --command <abs-path-to-exe>.",
            file=out,
        )

    return 0


# ---------------------------------------------------------------------------
# argparse glue (mirrors build_kb_wizard.add_init_subparser)
# ---------------------------------------------------------------------------


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``register-vscode`` subcommand on ``argparse``."""
    p = subparsers.add_parser(
        "register-vscode",
        help="add this MCP server to VS Code's user-level mcp.json",
    )
    p.add_argument(
        "--target",
        default=None,
        help="path to mcp.json (default: platform user config dir)",
    )
    p.add_argument(
        "--command",
        default=None,
        help="explicit value for the 'command' field "
        "(default: 'plantsim-copilot-mcp' or its absolute path with --absolute)",
    )
    p.add_argument(
        "--absolute",
        action="store_true",
        help="if the console-script is on PATH, write its absolute path "
        "instead of the bare name",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="overwrite an existing server entry that differs from the desired one",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="print the merged config but don't write to disk",
    )


def cmd_register_vscode(args: argparse.Namespace) -> int:
    """argparse dispatcher for the ``register-vscode`` subcommand."""
    target = Path(args.target).expanduser() if args.target else None
    try:
        return register(
            target=target,
            command=args.command,
            force=args.force,
            prefer_absolute=args.absolute,
            dry_run=args.dry_run,
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

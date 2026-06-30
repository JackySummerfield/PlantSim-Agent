"""Tests for the ``plantsim-copilot-mcp register-vscode`` subcommand."""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

import pytest

from plantsim_mcp import register_vscode
from plantsim_mcp.register_vscode import (
    SERVER_NAME,
    cmd_register_vscode,
    default_mcp_json_path,
    make_server_entry,
    merge_entry,
    register,
    resolve_command,
)


# ---------------------------------------------------------------------------
# default_mcp_json_path — platform discovery
# ---------------------------------------------------------------------------


def test_default_mcp_json_path_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPDATA", r"C:\Users\someone\AppData\Roaming")
    p = default_mcp_json_path("Windows")
    assert p.parts[-3:] == ("Code", "User", "mcp.json")


def test_default_mcp_json_path_darwin() -> None:
    p = default_mcp_json_path("Darwin")
    assert p.parts[-5:] == ("Library", "Application Support", "Code", "User", "mcp.json")


def test_default_mcp_json_path_linux() -> None:
    p = default_mcp_json_path("Linux")
    assert p.parts[-4:] == (".config", "Code", "User", "mcp.json")


def test_default_mcp_json_path_unknown() -> None:
    with pytest.raises(RuntimeError, match="unsupported OS"):
        default_mcp_json_path("Plan9")


# ---------------------------------------------------------------------------
# resolve_command — PATH lookup with fallback
# ---------------------------------------------------------------------------


def test_resolve_command_explicit_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(register_vscode.shutil, "which", lambda _name: "/should/not/use")
    assert resolve_command("/my/custom/path") == "/my/custom/path"


def test_resolve_command_bare_when_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(register_vscode.shutil, "which", lambda _name: "/usr/local/bin/plantsim-copilot-mcp")
    assert resolve_command() == SERVER_NAME


def test_resolve_command_absolute_when_requested(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        register_vscode.shutil, "which", lambda _name: "/usr/local/bin/plantsim-copilot-mcp"
    )
    assert resolve_command(prefer_absolute=True) == "/usr/local/bin/plantsim-copilot-mcp"


def test_resolve_command_fallback_when_not_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(register_vscode.shutil, "which", lambda _name: None)
    assert resolve_command() == SERVER_NAME  # bare name; caller warns


# ---------------------------------------------------------------------------
# merge_entry — pure-function semantics
# ---------------------------------------------------------------------------


def _entry() -> dict:
    return make_server_entry("plantsim-copilot-mcp")


def test_merge_into_empty_doc_adds_entry() -> None:
    merged, status = merge_entry({}, SERVER_NAME, _entry())
    assert status == "added"
    assert merged["servers"][SERVER_NAME] == _entry()


def test_merge_preserves_sibling_servers() -> None:
    existing = {
        "servers": {
            "some-other-server": {"type": "stdio", "command": "foo", "args": []},
        },
        "inputs": [{"id": "x", "type": "promptString"}],
    }
    merged, status = merge_entry(existing, SERVER_NAME, _entry())
    assert status == "added"
    assert "some-other-server" in merged["servers"]
    assert merged["inputs"] == existing["inputs"]
    assert merged["servers"][SERVER_NAME] == _entry()


def test_merge_idempotent_when_already_correct() -> None:
    existing = {"servers": {SERVER_NAME: _entry()}}
    merged, status = merge_entry(existing, SERVER_NAME, _entry())
    assert status == "unchanged"
    assert merged == existing


def test_merge_conflict_without_force() -> None:
    existing = {
        "servers": {
            SERVER_NAME: {"type": "stdio", "command": "old-cmd", "args": ["serve"]},
        }
    }
    merged, status = merge_entry(existing, SERVER_NAME, _entry())
    assert status == "conflict"
    # untouched
    assert merged["servers"][SERVER_NAME]["command"] == "old-cmd"


def test_merge_overwrite_with_force() -> None:
    existing = {
        "servers": {
            SERVER_NAME: {"type": "stdio", "command": "old-cmd", "args": ["serve"]},
        }
    }
    merged, status = merge_entry(existing, SERVER_NAME, _entry(), force=True)
    assert status == "updated"
    assert merged["servers"][SERVER_NAME] == _entry()


# ---------------------------------------------------------------------------
# register() — end-to-end with tmp_path
# ---------------------------------------------------------------------------


def test_register_writes_fresh_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(register_vscode.shutil, "which", lambda _name: "/fake/plantsim-copilot-mcp")
    target = tmp_path / "mcp.json"
    out = io.StringIO()
    rc = register(target=target, out=out)
    assert rc == 0
    data = json.loads(target.read_text())
    assert data["servers"][SERVER_NAME] == make_server_entry(SERVER_NAME)
    assert "Reload VS Code" in out.getvalue()


def test_register_merges_into_existing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(register_vscode.shutil, "which", lambda _name: "/fake/plantsim-copilot-mcp")
    target = tmp_path / "mcp.json"
    target.write_text(
        json.dumps(
            {
                "servers": {
                    "another-server": {"type": "stdio", "command": "x", "args": []},
                }
            }
        ),
        encoding="utf-8",
    )
    rc = register(target=target, out=io.StringIO())
    assert rc == 0
    data = json.loads(target.read_text())
    assert "another-server" in data["servers"]
    assert SERVER_NAME in data["servers"]


def test_register_idempotent_second_run_is_no_op(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(register_vscode.shutil, "which", lambda _name: "/fake/plantsim-copilot-mcp")
    target = tmp_path / "mcp.json"
    register(target=target, out=io.StringIO())
    first_text = target.read_text()
    # Second run: also OK, same content, no new backup
    out2 = io.StringIO()
    rc = register(target=target, out=out2)
    assert rc == 0
    assert "No change" in out2.getvalue()
    assert target.read_text() == first_text


def test_register_conflict_exits_2_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(register_vscode.shutil, "which", lambda _name: "/fake/plantsim-copilot-mcp")
    target = tmp_path / "mcp.json"
    target.write_text(
        json.dumps(
            {"servers": {SERVER_NAME: {"type": "stdio", "command": "OLD", "args": []}}}
        ),
        encoding="utf-8",
    )
    out = io.StringIO()
    rc = register(target=target, out=out)
    assert rc == 2
    assert "Conflict" in out.getvalue()
    # File untouched
    data = json.loads(target.read_text())
    assert data["servers"][SERVER_NAME]["command"] == "OLD"


def test_register_force_overwrites(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(register_vscode.shutil, "which", lambda _name: "/fake/plantsim-copilot-mcp")
    target = tmp_path / "mcp.json"
    target.write_text(
        json.dumps(
            {"servers": {SERVER_NAME: {"type": "stdio", "command": "OLD", "args": []}}}
        ),
        encoding="utf-8",
    )
    rc = register(target=target, force=True, out=io.StringIO())
    assert rc == 0
    data = json.loads(target.read_text())
    assert data["servers"][SERVER_NAME] == make_server_entry(SERVER_NAME)
    # Backup created
    backups = list(target.parent.glob("mcp.json.bak-*"))
    assert len(backups) == 1
    assert json.loads(backups[0].read_text())["servers"][SERVER_NAME]["command"] == "OLD"


def test_register_dry_run_does_not_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(register_vscode.shutil, "which", lambda _name: "/fake/plantsim-copilot-mcp")
    target = tmp_path / "mcp.json"
    out = io.StringIO()
    rc = register(target=target, dry_run=True, out=out)
    assert rc == 0
    assert not target.exists()
    assert "[dry-run]" in out.getvalue()


def test_register_malformed_json_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(register_vscode.shutil, "which", lambda _name: "/fake/plantsim-copilot-mcp")
    target = tmp_path / "mcp.json"
    target.write_text("// jsonc comment\n{\"servers\": {}}\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="could not parse"):
        register(target=target, out=io.StringIO())


# ---------------------------------------------------------------------------
# argparse callback
# ---------------------------------------------------------------------------


def test_cmd_register_vscode_translates_args(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(register_vscode.shutil, "which", lambda _name: "/fake/plantsim-copilot-mcp")
    target = tmp_path / "mcp.json"
    args = argparse.Namespace(
        target=str(target),
        command=None,
        absolute=False,
        force=False,
        dry_run=False,
    )
    rc = cmd_register_vscode(args)
    assert rc == 0
    assert target.exists()


def test_cmd_register_vscode_returns_1_on_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr(register_vscode.shutil, "which", lambda _name: "/fake/plantsim-copilot-mcp")
    target = tmp_path / "mcp.json"
    target.write_text("not valid json", encoding="utf-8")
    args = argparse.Namespace(
        target=str(target),
        command=None,
        absolute=False,
        force=False,
        dry_run=False,
    )
    rc = cmd_register_vscode(args)
    assert rc == 1
    assert "ERROR" in capsys.readouterr().err

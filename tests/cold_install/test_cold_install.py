"""Cold-install smoke test (Phase 4 #3).

This is a *workflow* test, not a tool test. It runs the same wizard a
fresh user would run on a clean machine and verifies the resulting
artifacts work end-to-end. It complements (does not replace) the unit
tests in :mod:`mcp/tests/` and the eval suites in :mod:`tests/eval/`.

What it verifies
----------------
1. ``plantsim-copilot-mcp init --non-interactive --build`` runs as a
   subprocess, writes a syntactically valid ``config.toml`` and a
   non-empty ``help.db``.
2. The MCP server process starts under ``serve`` and survives at least
   a brief stdin idle without crashing (a proxy for "imports clean,
   FastMCP initialised, no missing deps").
3. The same config is round-trippable through
   :func:`plantsim_mcp.config.load`.

What it does NOT verify
-----------------------
- That the wizard works in a *separate Python interpreter* (e.g. a
  brand-new venv with no editable install). For that level of
  isolation see [`docs/cold-install.md`](../../docs/cold-install.md)
  for the manual gate.
- Full MCP JSON-RPC tool invocation — the tools themselves are
  exercised by the unit-test suite and the eval runner.

Both checks are deliberately quick (~3s combined) so this can run on
every commit alongside the regular pytest job.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

# Resolve the repo root for both kb_minimal/ access and the
# python -m plantsim_mcp.server invocation.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_KB_MINIMAL = _REPO_ROOT / "kb_minimal"
_MCP_SRC = _REPO_ROOT / "mcp"


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ``PLANTSIM_AGENT_HOME`` at a fresh empty directory."""
    home = tmp_path / "agent_home"
    home.mkdir()
    monkeypatch.setenv("PLANTSIM_AGENT_HOME", str(home))
    return home


def _python_with_mcp() -> list[str]:
    """Build a subprocess argv that runs ``plantsim_mcp.server`` reliably.

    Uses the current ``sys.executable`` and prepends ``mcp/`` to
    PYTHONPATH so the subprocess finds the package even without an
    editable install.
    """
    return [sys.executable, "-m", "plantsim_mcp.server"]


def _subprocess_env(home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PLANTSIM_AGENT_HOME"] = str(home)
    # Prepend mcp/ src so a fresh subprocess imports the dev tree.
    py_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(_MCP_SRC) + (os.pathsep + py_path if py_path else "")
    )
    # Suppress Python output buffering for cleaner failure diagnostics.
    env["PYTHONUNBUFFERED"] = "1"
    return env


# ---------------------------------------------------------------------------
# 1. Wizard pipeline end-to-end
# ---------------------------------------------------------------------------


def test_init_non_interactive_with_build(isolated_home: Path) -> None:
    """init --non-interactive --build produces a config + index."""
    result = subprocess.run(
        [
            *_python_with_mcp(),
            "init",
            "--non-interactive",
            "--kb-root",
            str(_KB_MINIMAL),
            "--build",
            "--force",
        ],
        env=_subprocess_env(isolated_home),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, (
        f"init exited {result.returncode}\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )

    cfg_path = isolated_home / "config.toml"
    db_path = isolated_home / "indices" / "help.db"
    assert cfg_path.is_file(), "wizard should write config.toml"
    assert db_path.is_file(), "--build should produce help.db"
    assert db_path.stat().st_size > 16_000, (
        "help.db is suspiciously small — indexer ran but wrote no docs"
    )

    # Sanity: the writer's output must be machine-parseable by load().
    sys.path.insert(0, str(_MCP_SRC))
    try:
        from plantsim_mcp.config import load
        from plantsim_mcp.storage.sqlite import SQLiteFTSIndex

        cfg = load()
        assert cfg.paths.index_dir == (isolated_home / "indices").resolve()
        assert cfg.paths.help_kb_roots == (_KB_MINIMAL.resolve(),)
        with SQLiteFTSIndex(db_path) as idx:
            assert idx.count() > 50, (
                f"help.db has only {idx.count()} docs — kb_minimal should "
                "produce 90+"
            )
    finally:
        if str(_MCP_SRC) in sys.path:
            sys.path.remove(str(_MCP_SRC))


# ---------------------------------------------------------------------------
# 2. Server starts cleanly
# ---------------------------------------------------------------------------


def test_serve_starts_without_crashing(isolated_home: Path) -> None:
    """``plantsim-copilot-mcp serve`` starts and stays alive briefly.

    A bootstrapping smoke test: if any import is broken or FastMCP
    fails to register the tools, the process exits immediately and we
    can detect that via ``poll()`` after a short sleep.
    """
    # Pre-seed config + index so serve has something to point at.
    seed = subprocess.run(
        [
            *_python_with_mcp(),
            "init",
            "--non-interactive",
            "--kb-root",
            str(_KB_MINIMAL),
            "--build",
            "--force",
        ],
        env=_subprocess_env(isolated_home),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert seed.returncode == 0, seed.stderr

    # Launch serve in the background, then quickly verify it's alive.
    proc = subprocess.Popen(
        [*_python_with_mcp(), "serve"],
        env=_subprocess_env(isolated_home),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        # Give the process a brief window to import + register tools.
        # FastMCP's stdio server blocks waiting for JSON-RPC, so a
        # clean import means it should still be running here.
        time.sleep(0.8)
        ret = proc.poll()
        assert ret is None, (
            f"serve exited prematurely with code {ret}\n"
            f"stderr:\n{proc.stderr.read().decode(errors='replace') if proc.stderr else ''}"  # type: ignore[union-attr]
        )
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


# ---------------------------------------------------------------------------
# 3. Overwrite protection — defends against accidental config loss
# ---------------------------------------------------------------------------


def test_init_refuses_to_clobber_without_force(isolated_home: Path) -> None:
    """Without --force, init should NOT silently overwrite a config."""
    # First run — seeds config.toml.
    first = subprocess.run(
        [
            *_python_with_mcp(),
            "init",
            "--non-interactive",
            "--kb-root",
            str(_KB_MINIMAL),
        ],
        env=_subprocess_env(isolated_home),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert first.returncode == 0, first.stderr

    cfg_path = isolated_home / "config.toml"
    original = cfg_path.read_text(encoding="utf-8")

    # Second run without --force: must exit non-zero, must NOT overwrite.
    second = subprocess.run(
        [
            *_python_with_mcp(),
            "init",
            "--non-interactive",
            "--kb-root",
            str(_KB_MINIMAL),
            "--index-dir",
            str(isolated_home / "different_indices"),
        ],
        env=_subprocess_env(isolated_home),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert second.returncode != 0, (
        "init without --force should fail when config exists"
    )
    assert cfg_path.read_text(encoding="utf-8") == original, (
        "config.toml was overwritten despite the absence of --force"
    )

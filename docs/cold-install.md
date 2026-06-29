# Cold-Install Verification

This page is the **release gate** for "fresh user can install PlantSim-Agent and use it from VS Code Copilot Chat". The automated test in [`tests/cold_install/`](../tests/cold_install/) covers the wizard + server boot pipeline, but cannot prove that the agents and skills load correctly inside a real Copilot session. Run this checklist before tagging a release.

## Why both?

| Verification | Covered by |
|---|---|
| Wizard runs in subprocess, writes valid config & index | [`tests/cold_install/test_cold_install.py`](../tests/cold_install/test_cold_install.py) (automatic) |
| `serve` boots without crashing | same file (automatic) |
| Wizard refuses to clobber config without `--force` | same file (automatic) |
| **Brand-new Python venv finds all deps** | manual (this doc) |
| **VS Code discovers `plantsim-copilot` agent** | manual (this doc) |
| **Citation-reviewer fires on a real Copilot turn** | manual (this doc) |
| **Bilingual install message is correct** | manual (this doc) |

## Prerequisites

- A test machine **or** an isolated VS Code profile (`code --user-data-dir C:\tmp\vscode-cold`)
- Python 3.10+ on PATH
- Git
- GitHub Copilot extension (latest)

## Steps

### 1. Clone into the recommended location

```powershell
git clone https://github.com/<owner>/plantsim-agent.git $HOME/.copilot/plantsim-agent
cd $HOME/.copilot/plantsim-agent
```

Verify:
- [ ] Clone succeeds without auth or SSL errors
- [ ] No CRLF/LF warnings on Windows (LF expected; the wizard tests check this)

### 2. Create a fresh virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e mcp/
```

Verify:
- [ ] `pip install -e mcp/` completes without errors
- [ ] `pip show plantsim-copilot-mcp` shows the expected version
- [ ] `plantsim-copilot-mcp --help` lists the four subcommands: `serve`, `init`, `build-project`, `build-kb`

### 3. Run the install script

```powershell
.\scripts\install.ps1
```

Verify:
- [ ] Symlinks under `~/.copilot/agents/` exist for `plantsim-copilot.agent.md` and `citation-reviewer.agent.md`
- [ ] Symlinks under `~/.copilot/skills/` exist for `plantsim-kb-qa/`, `plantsim-code-author/`, `plantsim-project-analyst/`
- [ ] Editing a file under `~/.copilot/plantsim-agent/agents/` is reflected in `~/.copilot/agents/` (symlink, not copy)

### 4. Build the knowledge base

```powershell
plantsim-copilot-mcp init --non-interactive --kb-root .\kb_minimal --build
```

Verify:
- [ ] Exit code 0
- [ ] `~/.plantsim-agent/config.toml` exists with `[paths]` section
- [ ] `~/.plantsim-agent/indices/help.db` exists and is at least 100 KB
- [ ] Re-running the same command without `--force` exits non-zero and does NOT overwrite

### 5. Register the MCP server in VS Code

VS Code 1.99+ reads MCP servers from a user-level `mcp.json`. Create or merge into:

- **Windows:** `%APPDATA%\Code\User\mcp.json`
- **macOS:** `~/Library/Application Support/Code/User/mcp.json`
- **Linux:** `~/.config/Code/User/mcp.json`

```json
{
  "servers": {
    "plantsim-copilot-mcp": {
      "type": "stdio",
      "command": "plantsim-copilot-mcp",
      "args": ["serve"]
    }
  }
}
```

Notes:
- The server name **must** be `plantsim-copilot-mcp` — the orchestrator agent's `tools: [..., 'plantsim-copilot-mcp/*']` whitelist depends on it.
- If `plantsim-copilot-mcp` isn't on the PATH VS Code inherits (common when the package lives in a conda/venv that VS Code wasn't launched from), substitute the absolute path to the executable, e.g. `"command": "C:\\ProgramData\\miniforge3\\Scripts\\plantsim-copilot-mcp.exe"`. Find it with `(Get-Command plantsim-copilot-mcp).Source`.
- Prefer the user-level file over `<workspace>/.vscode/mcp.json` so the agent works in every workspace.

Smoke-test from the terminal (optional but quick) — the server should reply to `initialize` and `tools/list`:

```powershell
@'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}
{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}
{"jsonrpc":"2.0","id":2,"method":"tools/list"}
'@ | plantsim-copilot-mcp serve
```

Verify:
- [ ] `Ctrl+Shift+P` → `MCP: List Servers` shows `plantsim-copilot-mcp` with status **Started**
- [ ] `tools/list` returns all 7 tools (`search_help`, `get_api`, `find_method`, `find_callers`, `search_code`, `get_object_graph`, `validate_simtalk`)
- [ ] No "server failed to start" error in the Copilot Output panel

### 6. Reload VS Code and exercise the agent

```powershell
# In the VS Code command palette:
> Developer: Reload Window
```

Then open Copilot Chat and ask:

> @plantsim-copilot 怎么用 SimTalk 检查 Buffer 是否满？

Verify:
- [ ] The chat shows `@plantsim-copilot` in the agent picker
- [ ] The reply ends with a `**Sources:**` block listing at least one bullet with a path-like link
- [ ] (Optional, may require a follow-up turn) The orchestrator silently dispatches `citation-reviewer` — you can see this in the Copilot model trace if enabled

### 7. Cleanup

```powershell
deactivate
Remove-Item -Recurse -Force .venv
.\scripts\uninstall.ps1   # removes the symlinks
Remove-Item -Recurse -Force $HOME/.plantsim-agent
```

## When something fails

- **`pip install -e mcp/` fails** → check `mcp/pyproject.toml` for misspelled deps; rerun with `pip install -e mcp/ -v` to see the full pip log.
- **`init --build` fails** → confirm `kb_minimal/` is present and contains `.md` files; rerun the wizard with `--non-interactive` removed to see the interactive prompts.
- **VS Code does not see the agent** → `Get-ChildItem ~/.copilot/agents -Force` to confirm the symlink is alive; check the symlink target with `Get-Item path | Select-Object Target`.
- **`@plantsim-copilot` reply has no Sources block** → check the agent file at `~/.copilot/agents/plantsim-copilot.agent.md` is the symlink (not a stale copy); reload the window again.

## Sign-off

Once all boxes are ticked on a clean machine, attach a short note to the release PR:

> Cold-install verified on `<OS / Python version / VS Code build>` at `<commit hash>`. All 7 sections pass.

# Manual MCP Server Registration

Most users don't need this file — `plantsim-copilot-mcp register-vscode`
(or `install.ps1`, which calls it for you) handles VS Code MCP server
registration in one shot. This page is a fallback for the cases that
need manual configuration:

- VS Code installed in a non-default location (custom user data dir, portable mode)
- Corporate VS Code variants that lock down the user config dir
- You're sharing a project-level `.vscode/mcp.json` with your team and don't want a user-level entry
- The auto-register command keeps hitting `--force`-conflict errors because of an in-house tweaked entry

## Where the file lives

| OS | Path |
|---|---|
| Windows | `%APPDATA%\Code\User\mcp.json` |
| macOS | `~/Library/Application Support/Code/User/mcp.json` |
| Linux | `~/.config/Code/User/mcp.json` |

For project-level configuration use `<workspace>/.vscode/mcp.json`; the
schema is the same.

## The required entry

Add this block under `servers`. **The key must be exactly
`plantsim-copilot-mcp`** — the orchestrator agent's
`plantsim-copilot-mcp/*` tool whitelist depends on the name:

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

## When VS Code can't find the command

This is the most common failure mode: you `pip install -e mcp/`'d into
a conda env or venv, but VS Code was launched from a shell that doesn't
have that environment activated, so `plantsim-copilot-mcp` is not on
its PATH.

Either rerun the auto-registration with an absolute path:

```powershell
plantsim-copilot-mcp register-vscode --absolute --force
```

…or set `command` to the absolute path yourself. Find it with:

```powershell
# Windows / PowerShell
(Get-Command plantsim-copilot-mcp).Source

# macOS / Linux
which plantsim-copilot-mcp
```

Then in `mcp.json`:

```json
{
  "servers": {
    "plantsim-copilot-mcp": {
      "type": "stdio",
      "command": "C:\\ProgramData\\miniforge3\\Scripts\\plantsim-copilot-mcp.exe",
      "args": ["serve"]
    }
  }
}
```

> **Windows JSON note**: backslashes in the absolute path must be
> escaped (`\\`). Or use forward slashes (`C:/ProgramData/...`),
> which VS Code also accepts.

## Verifying it works

1. Reload VS Code: `Ctrl+Shift+P` → `Developer: Reload Window`
2. Open Copilot Chat → agent picker → you should see `PlantSim-Agent`
3. Ask: `/plantsim-copilot ping the MCP server` — the agent should
   answer with a Sources block, proving the tools loaded
4. If anything fails, check VS Code's MCP output channel:
   `View → Output → MCP: plantsim-copilot-mcp`

## Rolling back

If a registration goes wrong, the auto-register command always backs
up the previous `mcp.json` to
`mcp.json.bak-<YYYYMMDD-HHMMSS>` in the same folder before writing.
Restore by deleting the new file and renaming the backup.

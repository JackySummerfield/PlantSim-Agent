<#
.SYNOPSIS
    Install plantsim-agent into the local VS Code Copilot customization tree by symlink.

.DESCRIPTION
    VS Code Copilot looks for custom agents at ~/.copilot/agents/*.agent.md
    and custom skills at ~/.copilot/skills/<name>/SKILL.md. This script creates
    symbolic links from those well-known locations into this repository's
    agents/ and skills/ directories so you can edit in the repo and have
    changes take effect immediately, with no copy step.

.PARAMETER Force
    If a target already exists as a regular file or directory (not a symlink),
    move it aside as <name>.bak-<timestamp> before creating the link.

.PARAMETER WhatIf
    Show what would happen without making any changes.

.NOTES
    Requires either Windows Developer Mode enabled (Settings > Privacy & Security >
    For developers > Developer Mode) OR running from an elevated PowerShell.
    The script pre-checks this and exits with clear guidance if neither is available.

    Idempotent: rerun safely after pulling new agents/skills.
#>

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# ---------- Locate repo root (the parent of scripts/) ----------
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot  = Split-Path -Parent $scriptDir
$repoAgents = Join-Path $repoRoot 'agents'
$repoSkills = Join-Path $repoRoot 'skills'

# ---------- Determine VS Code Copilot home ----------
$copilotHome = Join-Path $HOME '.copilot'
$targetAgents = Join-Path $copilotHome 'agents'
$targetSkills = Join-Path $copilotHome 'skills'

Write-Host ""
Write-Host "Repo root        : $repoRoot"
Write-Host "Copilot home     : $copilotHome"
Write-Host ""

# ---------- Sanity checks ----------
if (-not (Test-Path $repoAgents)) {
    throw "Missing $repoAgents. Are you running this from a plantsim-agent clone?"
}
if (-not (Test-Path $repoSkills)) {
    throw "Missing $repoSkills. Are you running this from a plantsim-agent clone?"
}

# ---------- Pre-check: can this session create symlinks? ----------
# Windows requires either Developer Mode enabled OR an elevated (admin) shell.
function Test-CanCreateSymlinks {
    # Admin?
    try {
        $current = [Security.Principal.WindowsIdentity]::GetCurrent()
        $principal = New-Object Security.Principal.WindowsPrincipal($current)
        if ($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
            return @{ Ok = $true; Reason = 'admin' }
        }
    } catch { }

    # Developer Mode enabled?
    $key = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock'
    try {
        $val = Get-ItemProperty -Path $key -Name 'AllowDevelopmentWithoutDevLicense' -ErrorAction Stop
        if ($val.AllowDevelopmentWithoutDevLicense -eq 1) {
            return @{ Ok = $true; Reason = 'devmode' }
        }
    } catch { }

    return @{ Ok = $false; Reason = 'none' }
}

$symlinkCheck = Test-CanCreateSymlinks
if (-not $symlinkCheck.Ok) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host " Cannot create symbolic links in this session." -ForegroundColor Red
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Windows requires ONE of the following to create symlinks:"
    Write-Host ""
    Write-Host "  Option A (recommended) : Enable Developer Mode" -ForegroundColor Cyan
    Write-Host "    Settings -> Privacy & Security -> For developers -> Developer Mode: On"
    Write-Host "    (No admin needed; persists across sessions.)"
    Write-Host ""
    Write-Host "    Or via PowerShell as admin (one-time):"
    Write-Host "      reg add ""HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock"" /t REG_DWORD /f /v AllowDevelopmentWithoutDevLicense /d 1" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  Option B : Run this script from an elevated PowerShell" -ForegroundColor Cyan
    Write-Host "    Right-click PowerShell -> Run as administrator, then rerun install.ps1"
    Write-Host ""
    throw "Symlink creation not permitted. See instructions above."
}
Write-Host "Symlink permission: OK ($($symlinkCheck.Reason))" -ForegroundColor DarkGray

# Ensure the two destination dirs exist (real dirs, not symlinks).
foreach ($dir in @($targetAgents, $targetSkills)) {
    if (-not (Test-Path $dir)) {
        if ($PSCmdlet.ShouldProcess($dir, 'mkdir')) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
            Write-Host "Created $dir" -ForegroundColor DarkGray
        }
    }
}

# ---------- Helper: create or refresh a symlink ----------
function New-RepoLink {
    param(
        [Parameter(Mandatory)] [string]$LinkPath,
        [Parameter(Mandatory)] [string]$SourcePath,
        [string]$Kind = 'File'   # 'File' or 'Directory'
    )

    $sourceFull = (Resolve-Path -LiteralPath $SourcePath).Path

    if (Test-Path -LiteralPath $LinkPath) {
        $existing = Get-Item -LiteralPath $LinkPath -Force
        $isLink = ($existing.Attributes.ToString() -match 'ReparsePoint')

        if ($isLink) {
            $currentTarget = $existing.Target
            if ($currentTarget -is [array]) { $currentTarget = $currentTarget[0] }
            try {
                $currentFull = (Resolve-Path -LiteralPath $currentTarget -ErrorAction Stop).Path
            } catch {
                $currentFull = $currentTarget
            }

            if ($currentFull -ieq $sourceFull) {
                Write-Host "  [skip] $($existing.Name) already linked correctly" -ForegroundColor DarkGray
                return
            }

            Write-Host "  [refresh] $($existing.Name)  (was -> $currentTarget)" -ForegroundColor Yellow
            if ($PSCmdlet.ShouldProcess($LinkPath, 'remove stale symlink')) {
                Remove-Item -LiteralPath $LinkPath -Force -Recurse
            }
        }
        else {
            if (-not $Force) {
                Write-Warning ("Target exists and is NOT a symlink: $LinkPath`n" +
                               "  Rerun with -Force to back it up as .bak-<timestamp>, or remove it manually.")
                return
            }
            $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
            $backup = "$LinkPath.bak-$stamp"
            Write-Host "  [backup] $($existing.Name) -> $(Split-Path -Leaf $backup)" -ForegroundColor Yellow
            if ($PSCmdlet.ShouldProcess($LinkPath, "rename to $backup")) {
                Rename-Item -LiteralPath $LinkPath -NewName (Split-Path -Leaf $backup)
            }
        }
    }

    if ($PSCmdlet.ShouldProcess($LinkPath, "symlink -> $sourceFull")) {
        try {
            New-Item -ItemType SymbolicLink -Path $LinkPath -Target $sourceFull -Force | Out-Null
            Write-Host "  [link]  $(Split-Path -Leaf $LinkPath)  ->  $sourceFull" -ForegroundColor Green
        } catch {
            $msg = $_.Exception.Message
            if ($msg -match 'privilege|administrator|access') {
                throw "Cannot create symlink (need Developer Mode or admin). Enable: Settings > Privacy & Security > For developers > Developer Mode. Original error: $msg"
            }
            throw
        }
    }
}

# ---------- Link agents ----------
Write-Host "Agents:" -ForegroundColor Cyan
$agentFiles = @(Get-ChildItem -LiteralPath $repoAgents -Filter '*.agent.md' -File -ErrorAction SilentlyContinue)
if ($agentFiles.Count -eq 0) {
    Write-Host "  (none in repo yet — will be added in Phase 3)" -ForegroundColor DarkGray
}
foreach ($f in $agentFiles) {
    New-RepoLink -LinkPath (Join-Path $targetAgents $f.Name) -SourcePath $f.FullName -Kind 'File'
}

# ---------- Link skills ----------
Write-Host ""
Write-Host "Skills:" -ForegroundColor Cyan
$skillDirs = @(Get-ChildItem -LiteralPath $repoSkills -Directory -ErrorAction SilentlyContinue)
if ($skillDirs.Count -eq 0) {
    Write-Host "  (none in repo yet — will be added in Phase 3)" -ForegroundColor DarkGray
}
foreach ($d in $skillDirs) {
    New-RepoLink -LinkPath (Join-Path $targetSkills $d.Name) -SourcePath $d.FullName -Kind 'Directory'
}

# ---------- Register MCP server in VS Code's user mcp.json ----------
Write-Host ""
Write-Host "VS Code MCP registration:" -ForegroundColor Cyan
$mcpCmd = Get-Command 'plantsim-copilot-mcp' -ErrorAction SilentlyContinue
if ($null -ne $mcpCmd) {
    if ($PSCmdlet.ShouldProcess('VS Code mcp.json', 'register plantsim-copilot-mcp')) {
        try {
            & plantsim-copilot-mcp register-vscode
        }
        catch {
            Write-Warning "register-vscode failed: $($_.Exception.Message)"
            Write-Host "  You can rerun it manually: plantsim-copilot-mcp register-vscode --force" -ForegroundColor DarkGray
        }
    }
}
else {
    Write-Host "  [skip] 'plantsim-copilot-mcp' not on PATH yet." -ForegroundColor Yellow
    Write-Host "         Run 'pip install -e mcp/' first, then re-run this script," -ForegroundColor DarkGray
    Write-Host "         or execute 'plantsim-copilot-mcp register-vscode' manually." -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "Done. Reload VS Code to pick up new agents/skills." -ForegroundColor Green

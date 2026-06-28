<#
.SYNOPSIS
    Remove the symlinks that install.ps1 created in ~/.copilot/agents and ~/.copilot/skills.

.DESCRIPTION
    Only removes entries that are symlinks pointing INTO this repository.
    Regular files, directories, or links pointing elsewhere are left alone.

.PARAMETER WhatIf
    Show what would happen without making any changes.
#>

[CmdletBinding(SupportsShouldProcess = $true)]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot  = Split-Path -Parent $scriptDir
$repoRootFull = (Resolve-Path -LiteralPath $repoRoot).Path

$targetAgents = Join-Path $HOME '.copilot\agents'
$targetSkills = Join-Path $HOME '.copilot\skills'

Write-Host ""
Write-Host "Repo root        : $repoRootFull"
Write-Host ""

function Remove-RepoLink {
    param([Parameter(Mandatory)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) { return }
    $item = Get-Item -LiteralPath $Path -Force
    $isLink = ($item.Attributes.ToString() -match 'ReparsePoint')
    if (-not $isLink) {
        Write-Host "  [keep] $($item.Name) is not a symlink" -ForegroundColor DarkGray
        return
    }
    $target = $item.Target
    if ($target -is [array]) { $target = $target[0] }
    try {
        $targetFull = (Resolve-Path -LiteralPath $target -ErrorAction Stop).Path
    } catch {
        $targetFull = $target
    }
    if ($targetFull -like "$repoRootFull*") {
        if ($PSCmdlet.ShouldProcess($Path, 'remove symlink')) {
            Remove-Item -LiteralPath $Path -Force -Recurse
            Write-Host "  [unlink] $($item.Name)" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  [keep] $($item.Name) -> $target (not in this repo)" -ForegroundColor DarkGray
    }
}

Write-Host "Agents:" -ForegroundColor Cyan
if (Test-Path $targetAgents) {
    foreach ($i in Get-ChildItem -LiteralPath $targetAgents -Force) {
        Remove-RepoLink -Path $i.FullName
    }
} else { Write-Host "  (no $targetAgents)" -ForegroundColor DarkGray }

Write-Host ""
Write-Host "Skills:" -ForegroundColor Cyan
if (Test-Path $targetSkills) {
    foreach ($i in Get-ChildItem -LiteralPath $targetSkills -Force) {
        Remove-RepoLink -Path $i.FullName
    }
} else { Write-Host "  (no $targetSkills)" -ForegroundColor DarkGray }

Write-Host ""
Write-Host "Done." -ForegroundColor Green

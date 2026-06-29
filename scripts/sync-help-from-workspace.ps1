<#
.SYNOPSIS
    Sync converted PTS Help markdown from your conversion workspace into kb_local/.

.DESCRIPTION
    Re-running PTS Help PDF -> Markdown conversion (markitdown / marker / docling)
    typically produces output in a separate workspace; this script mirrors that
    output into `kb_local/pts_help_<version>/` inside the repo so the MCP
    indexer keeps working without you editing config.toml.

    `kb_local/` is gitignored, so the synced files never reach GitHub.

    Default source is taken from the `PLANTSIM_HELP_SOURCE` environment
    variable; you can also pass `-Source` explicitly.

.PARAMETER Source
    Folder holding the converted markdown tree (recursive). If omitted,
    falls back to `$env:PLANTSIM_HELP_SOURCE`.

.PARAMETER Version
    PTS version label used for the destination subdir. Default: 2504.

.PARAMETER Mirror
    Pass this switch to remove destination files that are no longer in the
    source (true mirror). Without it, the script is purely additive.

.EXAMPLE
    $env:PLANTSIM_HELP_SOURCE = 'D:\work\pts_help_2504_md'
    .\scripts\sync-help-from-workspace.ps1
    Additive sync from the env-var source to kb_local\pts_help_2504\.

.EXAMPLE
    .\scripts\sync-help-from-workspace.ps1 -Version 2604 -Source "C:/work/pts_help_2604_md" -Mirror
    Sync a new PTS 2604 conversion, removing stale files in the destination.

.NOTES
    Requires robocopy (ships with Windows). Run from the repo root.
#>
[CmdletBinding()]
param(
    [string]$Source = $env:PLANTSIM_HELP_SOURCE,
    [string]$Version = "2504",
    [switch]$Mirror
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($Source)) {
    throw "Provide -Source <path> or set `$env:PLANTSIM_HELP_SOURCE to the converted markdown folder."
}

$repoRoot = (Resolve-Path "$PSScriptRoot\..").Path
$dest = Join-Path $repoRoot "kb_local\pts_help_$Version"

if (-not (Test-Path -LiteralPath $Source -PathType Container)) {
    throw "Source folder not found: $Source"
}

Write-Host "Source  : $Source"
Write-Host "Dest    : $dest"
Write-Host "Mode    : $(if ($Mirror) { 'mirror (will delete extras)' } else { 'additive' })"
Write-Host ""

$args = @($Source, $dest, '*.md', '/E', '/NFL', '/NDL', '/NJH', '/NJS', '/NP', '/NC')
if ($Mirror) { $args += '/PURGE' }

robocopy @args | Out-Host
$rc = $LASTEXITCODE

# robocopy exit codes 0..7 are success / informational. >= 8 means error.
if ($rc -ge 8) {
    throw "robocopy failed with exit code $rc"
}

$count = (Get-ChildItem -LiteralPath $dest -Recurse -File -Filter '*.md' | Measure-Object).Count
Write-Host ""
Write-Host "OK - $count markdown files in $dest"
Write-Host "Next: rebuild the index, e.g."
Write-Host "  python -c 'from plantsim_mcp.config import load; from plantsim_mcp.indexers import help_md_to_fts; from plantsim_mcp.storage.sqlite import SQLiteFTSIndex; cfg=load(); idx=SQLiteFTSIndex(cfg.paths.help_db); idx.open(); idx.delete_all(); help_md_to_fts.build(list(cfg.paths.help_kb_roots), idx); idx.close()'"

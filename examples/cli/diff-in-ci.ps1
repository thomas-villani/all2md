<#
.SYNOPSIS
    Semantic, cross-format document diff as a CI gate (PowerShell).
.EXAMPLE
    ./diff-in-ci.ps1 old.docx new.pdf
.NOTES
    Exits 1 if the documents differ in content, 0 if equivalent.
    Requires all2md on PATH.
#>
param(
    [Parameter(Mandatory = $true)][string]$Old,
    [Parameter(Mandatory = $true)][string]$New
)
$ErrorActionPreference = "Stop"

# 1. Human-readable unified diff for the build log.
all2md diff $Old $New --format unified --color auto

# 2. Machine-readable JSON: count change hunks and fail the build if any.
#    Note: identical documents produce *empty* output (no JSON), so guard for it.
$json = (all2md diff $Old $New --format json | Out-String)
if ([string]::IsNullOrWhiteSpace($json)) {
    $hunks = 0
} else {
    $hunks = @(($json | ConvertFrom-Json).hunks).Count
}
Write-Output "Change hunks: $hunks"
if ($hunks -gt 0) {
    Write-Error "Documents differ -- failing CI gate."
    exit 1
}
Write-Output "Documents are equivalent."

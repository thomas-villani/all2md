<#
.SYNOPSIS
    Convert a whole folder of mixed documents to Markdown (PowerShell).
.EXAMPLE
    ./batch-convert.ps1 ./docs ./converted
.NOTES
    Requires all2md on PATH.
#>
param(
    [Parameter(Mandatory = $true)][string]$InputDir,
    [string]$OutputDir = "./converted"
)
$ErrorActionPreference = "Stop"

# 1. Built-in batch: recurse, mirror structure, skip individual failures.
all2md $InputDir --output-dir $OutputDir --recursive --skip-errors --preserve-structure
Write-Output "Converted tree into $OutputDir/"

# 2. Collate every document in the tree into ONE Markdown file.
all2md $InputDir --recursive --collate --out "$OutputDir/combined.md"
Write-Output "Wrote combined corpus to $OutputDir/combined.md"

# 3. Hand-rolled parallel fan-out with ForEach-Object -Parallel (PowerShell 7+),
#    when you want control over per-file flags or concurrency.
Get-ChildItem $InputDir -Recurse -File -Include *.pdf, *.docx, *.html |
    ForEach-Object -Parallel {
        all2md $_.FullName --out "$($_.FullName).md"
    } -ThrottleLimit 4
Write-Output "Parallel conversion complete (one .md next to each source)."

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

# 3. Parallel conversion with the built-in worker pool. --parallel N spins up N
#    workers; no need to hand-roll ForEach-Object -Parallel (which also re-resolves
#    all2md in each runspace). With --output-dir the tree structure is mirrored.
all2md $InputDir --output-dir $OutputDir --recursive --parallel 4 --skip-errors --preserve-structure
Write-Output "Parallel conversion complete (mirrored under $OutputDir/)."

# 3b. Only reach for a hand-rolled fan-out when you need per-file flags that the
#     batch engine can't express uniformly:
#   Get-ChildItem $InputDir -Recurse -File -Include *.pdf, *.docx, *.html |
#       ForEach-Object -Parallel { all2md $_.FullName --out "$($_.FullName).md" } -ThrottleLimit 4

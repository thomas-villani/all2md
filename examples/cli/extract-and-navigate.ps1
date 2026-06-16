<#
.SYNOPSIS
    Read big documents cheaply: outline first, then extract section/lines (PowerShell).
.EXAMPLE
    ./extract-and-navigate.ps1 manual.pdf
.NOTES
    Requires all2md on PATH.
#>
param(
    [Parameter(Mandatory = $true)][string]$Document
)
$ErrorActionPreference = "Stop"

# 1. Table of contents only -- a tiny, cheap map of the document.
Write-Output "### Outline"
all2md $Document --outline

# 2. Outline annotated with line numbers, so you know exactly what to extract.
Write-Output "### Outline with line numbers"
all2md $Document --outline --line-numbers

# 3. Extract a section by heading name (1-indexed pattern match).
Write-Output "### Extract a named section"
all2md $Document --extract "Introduction"

# 4. Extract an exact line range (numbers come from --line-numbers above).
Write-Output "### Extract a line range"
all2md $Document --extract "line:1-20"

# 5. Full content WITH line numbers -- cheap, addressable context for an agent.
Write-Output "### Numbered full text (first 30 lines)"
all2md $Document --line-numbers | Select-Object -First 30

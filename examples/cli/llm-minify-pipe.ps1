<#
.SYNOPSIS
    Shrink a document to token-lean text before sending it to an LLM (PowerShell).
.EXAMPLE
    ./llm-minify-pipe.ps1 big-report.pdf
.NOTES
    Requires all2md on PATH.
#>
param(
    [Parameter(Mandatory = $true)][string]$Document
)
$ErrorActionPreference = "Stop"

# 1. Compact Markdown (default mode).
all2md llm-minify $Document --out "minified.md"
Write-Output "Wrote minified.md"

# 2. Compare sizes -- see how much you saved.
$full = (all2md $Document | Measure-Object -Word).Words
$lean = (all2md llm-minify $Document | Measure-Object -Word).Words
Write-Output "Words: full=$full  minified=$lean"

# 3. Most aggressive: plain text, links/images/formatting stripped.
all2md llm-minify $Document --aggressive --out "minified.txt"

# 4. Pipe straight into an LLM CLI. Replace `your-llm` with your tool of choice:
#    all2md llm-minify $Document | your-llm "Summarize the key points:"

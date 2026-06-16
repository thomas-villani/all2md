<#
.SYNOPSIS
    The everyday all2md CLI moves: convert, redirect, pipe (PowerShell).
.EXAMPLE
    ./convert-and-pipe.ps1 document.pdf
.NOTES
    Requires all2md on PATH (pip install all2md).
#>
param(
    [Parameter(Mandatory = $true)][string]$Document
)
$ErrorActionPreference = "Stop"
$stem = [System.IO.Path]::GetFileNameWithoutExtension($Document)

# 1. Convert to Markdown, redirect to a file.
all2md $Document | Set-Content "$stem.md"
Write-Output "Wrote $stem.md"

# 2. Any-to-any: pick the output format with --to, write with --out.
all2md $Document --to html --out "$stem.html"
all2md $Document --to rst  --out "$stem.rst"
Write-Output "Wrote $stem.html and $stem.rst"

# 3. Read from stdin with '-'. PowerShell pipes text cleanly but mangles binary,
#    so pipe text formats this way; for binary (PDF/DOCX) prefer the file argument
#    (step 1), or use cmd's byte-safe redirection:
#        cmd /c "all2md - < `"$Document`""
if ($Document -match '\.(md|markdown|txt|html?|rst|csv|json|xml)$') {
    Get-Content $Document -Raw | all2md - | Select-Object -First 20
} else {
    Write-Output "(stdin pipe demo skipped for binary input; use the file argument or cmd redirection)"
}

# 4. Extract embedded images/attachments to a folder instead of inlining them.
all2md $Document --attachment-mode save --attachment-output-dir "./$stem-assets" `
    --out "$stem-with-assets.md"
Write-Output "Saved attachments under ./$stem-assets/"

# 5. Pipe converted Markdown into another tool (here: a word count).
$words = (all2md $Document | Measure-Object -Word).Words
Write-Output "Word count: $words"

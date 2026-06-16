<#
.SYNOPSIS
    Rank-search a folder of documents; post-process JSON with ConvertFrom-Json (PowerShell).
.EXAMPLE
    ./search-corpus.ps1 "attachment handling" ./docs
.NOTES
    Requires all2md on PATH. No jq needed -- PowerShell parses JSON natively.
#>
param(
    [Parameter(Mandatory = $true)][string]$Query,
    [Parameter(Mandatory = $true, ValueFromRemainingArguments = $true)][string[]]$Paths
)
$ErrorActionPreference = "Stop"

# 1. Human-readable ranked results.
Write-Output "### Top matches"
all2md search $Query @Paths --keyword --top-k 5

# 2. JSON results parsed into objects: score + source + section per hit.
Write-Output "### As score / source / section"
$hits = all2md search $Query @Paths --keyword --json --top-k 5 | ConvertFrom-Json
$hits | ForEach-Object {
    $section = if ($_.chunk_metadata.section_heading) { $_.chunk_metadata.section_heading } else { "-" }
    "{0:N3}`t{1}`t{2}" -f $_.score, $_.chunk_metadata.document_path, $section
}

# 3. Just the matching files, de-duplicated -- a retrieval shortlist.
Write-Output "### Matching files"
all2md search $Query @Paths --keyword --json --top-k 10 |
    ConvertFrom-Json |
    ForEach-Object { $_.chunk_metadata.document_path } |
    Sort-Object -Unique

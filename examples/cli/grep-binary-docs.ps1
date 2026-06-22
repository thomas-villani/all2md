<#
.SYNOPSIS
    Grep INSIDE binary documents (PDF, DOCX, PPTX, ...) that plain grep can't read (PowerShell).
.EXAMPLE
    ./grep-binary-docs.ps1 "revenue" ./reports
.NOTES
    Requires all2md on PATH.
#>
param(
    [Parameter(Mandatory = $true)][string]$Pattern,
    [Parameter(Mandatory = $true, ValueFromRemainingArguments = $true)][string[]]$Paths
)
$ErrorActionPreference = "Stop"

# 1. Case-insensitive match with line numbers and 2 lines of context.
all2md grep $Pattern @Paths -i -n -C 2

# 2. Recurse a directory tree (every supported document under it):
#    all2md grep --recursive $Pattern ./docs

# 3. Treat the pattern as a regular expression:
#    all2md grep --regex "TODO|FIXME" @Paths -n

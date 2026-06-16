<#
.SYNOPSIS
    Assemble grounded LLM context from a document corpus, in pure PowerShell.
.DESCRIPTION
    Retrieves the most relevant chunks (with provenance) for a question and
    formats them into a prompt you can pipe to any LLM CLI. For a full Python
    RAG example that also calls the model, see ../llm/search_to_llm_rag.py.
.EXAMPLE
    ./rag-ingest.ps1 "How do attachments work?" ./docs
.NOTES
    Requires all2md on PATH.
#>
param(
    [Parameter(Mandatory = $true)][string]$Question,
    [Parameter(Mandatory = $true, ValueFromRemainingArguments = $true)][string[]]$Paths
)
$ErrorActionPreference = "Stop"

# 1. Retrieve top-k chunks and format them into a citation-numbered context block.
$hits = all2md search $Question @Paths --keyword --json --top-k 5 | ConvertFrom-Json
$i = 0
$context = ($hits | ForEach-Object {
    $i++
    $loc = $_.chunk_metadata.document_path
    if ($_.chunk_metadata.section_heading) { $loc += " -> " + $_.chunk_metadata.section_heading }
    "[$i] ($loc)`n$($_.text)`n"
}) -join "`n"

# 2. Build the final grounded prompt.
$prompt = @"
Context passages:

$context

Answer using ONLY the context above, citing passages by their [number].
Question: $Question
"@

Write-Output $prompt

# 3. Send it to your LLM of choice (uncomment and adapt):
#    $prompt | your-llm

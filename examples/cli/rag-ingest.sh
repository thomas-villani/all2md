#!/usr/bin/env bash
#
# rag-ingest.sh -- assemble grounded LLM context from a document corpus, in pure
# shell. Retrieves the most relevant chunks (with provenance) for a question and
# formats them into a prompt you can pipe to any LLM CLI.
#
# For a full Python RAG example that also calls the model, see
# ../llm/search_to_llm_rag.py.
#
# Usage:
#   ./rag-ingest.sh "<question>" <dir-or-files...>
#
# Requires: all2md and jq on PATH.
set -euo pipefail

QUESTION="${1:?Usage: rag-ingest.sh \"<question>\" <paths...>}"
shift
PATHS=("$@")
[ "${#PATHS[@]}" -gt 0 ] || { echo "Provide at least one path." >&2; exit 1; }

# 1. Retrieve top-k chunks as JSON and format them into a citation-numbered
#    context block. Each passage keeps its source path and section heading.
#    The `gsub` strips the `<<...>>` match-highlight markers so they don't leak
#    into the LLM prompt.
CONTEXT=$(all2md search "$QUESTION" "${PATHS[@]}" --keyword --json --top-k 5 \
  | jq -r 'to_entries | .[] |
      "[\(.key + 1)] (\(.value.chunk_metadata.document_path)\(if .value.chunk_metadata.section_heading then " -> " + .value.chunk_metadata.section_heading else "" end))\n\(.value.text | gsub("<<|>>";""))\n"')

# 2. Build the final grounded prompt.
PROMPT="Context passages:

$CONTEXT

Answer using ONLY the context above, citing passages by their [number].
Question: $QUESTION"

echo "$PROMPT"

# 3. Send it to your LLM of choice (uncomment and adapt):
#    echo "$PROMPT" | your-llm

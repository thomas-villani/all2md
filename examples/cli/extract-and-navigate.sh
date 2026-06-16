#!/usr/bin/env bash
#
# extract-and-navigate.sh -- read big documents cheaply: outline first, then
# pull only the section/lines you need. Ideal for feeding just the relevant
# slice of a large document to an LLM.
#
# Usage:
#   ./extract-and-navigate.sh <document>
#
# Requires: all2md on PATH.
set -euo pipefail

DOC="${1:?Usage: extract-and-navigate.sh <document>}"

# 1. Table of contents only -- a tiny, cheap map of the document.
echo "### Outline"
all2md "$DOC" --outline

# 2. Outline annotated with line numbers, so you know exactly what to extract.
echo "### Outline with line numbers"
all2md "$DOC" --outline --line-numbers

# 3. Extract a section by heading name (1-indexed pattern match).
echo "### Extract a named section"
all2md "$DOC" --extract "Introduction" || echo "(no 'Introduction' section)"

# 4. Extract an exact line range (numbers come from --line-numbers above).
echo "### Extract a line range"
all2md "$DOC" --extract "line:1-20"

# 5. Full content WITH line numbers -- handy as cheap, addressable context for
#    an agent that will later ask for specific ranges.
echo "### Numbered full text (first 30 lines)"
all2md "$DOC" --line-numbers | head -n 30

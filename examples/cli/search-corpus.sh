#!/usr/bin/env bash
#
# search-corpus.sh -- rank-search a folder of documents and post-process the
# JSON results with jq. all2md's search chunks documents structure-aware and
# returns provenance (source file + section) with every hit.
#
# Usage:
#   ./search-corpus.sh "<query>" <dir-or-files...>
#
# Requires: all2md and jq on PATH.
set -euo pipefail

QUERY="${1:?Usage: search-corpus.sh \"<query>\" <paths...>}"
shift
PATHS=("$@")
[ "${#PATHS[@]}" -gt 0 ] || { echo "Provide at least one path to search." >&2; exit 1; }

# 1. Human-readable ranked results (rich terminal output).
echo "### Top matches"
all2md search "$QUERY" "${PATHS[@]}" --keyword --top-k 5

# 2. JSON results piped to jq: print score + source + section for each hit.
echo "### As score / source / section (via jq)"
all2md search "$QUERY" "${PATHS[@]}" --keyword --json --top-k 5 \
  | jq -r '.[] | "\(.score | (.*1000|round/1000))\t\(.chunk_metadata.document_path)\t\(.chunk_metadata.section_heading // "-")"'

# 3. Just the source files that matched, de-duplicated -- a retrieval shortlist.
echo "### Matching files"
all2md search "$QUERY" "${PATHS[@]}" --keyword --json --top-k 10 \
  | jq -r '.[].chunk_metadata.document_path' | sort -u

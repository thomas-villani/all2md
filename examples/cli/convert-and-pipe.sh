#!/usr/bin/env bash
#
# convert-and-pipe.sh -- the everyday all2md CLI moves: convert, redirect, pipe.
#
# Usage:
#   ./convert-and-pipe.sh <document>
#
# Requires: all2md on PATH (pip install all2md).
set -euo pipefail

DOC="${1:?Usage: convert-and-pipe.sh <document>}"
stem="$(basename "${DOC%.*}")"

# 1. Convert to Markdown on stdout, redirect to a file.
all2md "$DOC" > "${stem}.md"
echo "Wrote ${stem}.md"

# 2. Any-to-any: pick the output format with --to, write with --out.
all2md "$DOC" --to html --out "${stem}.html"
all2md "$DOC" --to rst  --out "${stem}.rst"
echo "Wrote ${stem}.html and ${stem}.rst"

# 3. Read from stdin with '-' (binary formats like PDF/DOCX auto-detect from
#    their magic bytes). This lets all2md sit in the middle of a pipeline.
cat "$DOC" | all2md - | head -n 20

# 4. Extract embedded images/attachments to a folder instead of inlining them.
all2md "$DOC" --attachment-mode save --attachment-output-dir "./${stem}-assets" \
  --out "${stem}-with-assets.md"
echo "Saved attachments under ./${stem}-assets/"

# 5. Pipe converted Markdown straight into another tool (here: a word count).
echo "Word count: $(all2md "$DOC" | wc -w)"

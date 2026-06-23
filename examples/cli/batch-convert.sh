#!/usr/bin/env bash
#
# batch-convert.sh -- convert a whole folder of mixed documents to Markdown.
#
# Usage:
#   ./batch-convert.sh <input-dir> [output-dir]
#
# Requires: all2md on PATH.
set -euo pipefail

IN="${1:?Usage: batch-convert.sh <input-dir> [output-dir]}"
OUT="${2:-./converted}"

# 1. Built-in batch: recurse the tree, mirror its structure under OUT, and keep
#    going if a single file fails. This is the simplest and most robust option.
all2md "$IN" --output-dir "$OUT" --recursive --skip-errors --preserve-structure
echo "Converted tree into $OUT/"

# 2. Collate every document in the tree into ONE Markdown file.
all2md "$IN" --recursive --collate --out "$OUT/combined.md"
echo "Wrote combined corpus to $OUT/combined.md"

# 3. Parallel conversion with the built-in worker pool. --parallel N spins up N
#    workers; no need to hand-roll find + xargs. With --output-dir the tree
#    structure is mirrored; without it, a .md is written next to each source.
all2md "$IN" --output-dir "$OUT" --recursive --parallel 4 --skip-errors --preserve-structure
echo "Parallel conversion complete (mirrored under $OUT/)."

# 3b. Only reach for a hand-rolled fan-out when you need per-file flags that the
#     batch engine can't express uniformly:
#   find "$IN" -type f \( -name '*.pdf' -o -name '*.docx' -o -name '*.html' \) -print0 \
#     | xargs -0 -P 4 -I {} sh -c 'all2md "$1" --out "$1.md"' _ {}

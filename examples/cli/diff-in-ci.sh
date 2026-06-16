#!/usr/bin/env bash
#
# diff-in-ci.sh -- semantic, cross-format diff as a CI gate. all2md compares the
# *content* of two documents (even across formats, e.g. .docx vs .pdf), not raw
# bytes -- so reformatting or re-exporting doesn't show up as a change.
#
# Usage:
#   ./diff-in-ci.sh <old> <new>
#
# Exit code: 0 if content matches, 1 if it differs (suitable for CI).
# Requires: all2md and jq on PATH.
set -euo pipefail

OLD="${1:?Usage: diff-in-ci.sh <old> <new>}"
NEW="${2:?Usage: diff-in-ci.sh <old> <new>}"

# 1. Human-readable unified diff for the build log.
all2md diff "$OLD" "$NEW" --format unified --color auto || true

# 2. Machine-readable JSON: count the change hunks and fail the build if any.
#    Note: identical documents produce *empty* output (no JSON), so guard for it.
json="$(all2md diff "$OLD" "$NEW" --format json)"
if [ -z "$json" ]; then
  hunks=0
else
  hunks="$(printf '%s' "$json" | jq '.hunks | length')"
fi
echo "Change hunks: $hunks"
if [ "$hunks" -gt 0 ]; then
  echo "Documents differ -- failing CI gate." >&2
  exit 1
fi
echo "Documents are equivalent."

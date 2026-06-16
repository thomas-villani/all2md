#!/usr/bin/env bash
#
# grep-binary-docs.sh -- grep INSIDE documents that plain grep can't read
# (PDF, DOCX, PPTX, ...). all2md converts on the fly, then searches the text.
#
# Usage:
#   ./grep-binary-docs.sh "<pattern>" <files-or-dir...>
#
# Requires: all2md on PATH.
set -euo pipefail

PATTERN="${1:?Usage: grep-binary-docs.sh \"<pattern>\" <paths...>}"
shift
PATHS=("$@")
[ "${#PATHS[@]}" -gt 0 ] || { echo "Provide at least one file or directory." >&2; exit 1; }

# 1. Case-insensitive match with line numbers and 2 lines of context.
all2md grep "$PATTERN" "${PATHS[@]}" -i -n -C 2

# 2. Recurse a directory tree (every supported document under it).
#    all2md grep -r "$PATTERN" docs/

# 3. Treat the pattern as a regular expression.
#    all2md grep --regex "TODO|FIXME" "${PATHS[@]}" -n

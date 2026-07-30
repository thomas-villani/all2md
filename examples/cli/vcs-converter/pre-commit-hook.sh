#!/bin/bash
# Pre-commit hook for automatic document conversion
#
# Converts staged binary documents (DOCX, PPTX, PDF) to markdown before commit,
# making them git-friendly and easier to diff.
#
# Installation:
#   cp pre-commit-hook.sh .git/hooks/pre-commit
#   chmod +x .git/hooks/pre-commit

set -euo pipefail

CONVERTER_SCRIPT="${CONVERTER_SCRIPT:-.vcs-converter/vcs_converter.py}"

# Only formats all2md can parse. Legacy .doc/.ppt are deliberately absent:
# they can never convert, so including them made this hook abort every commit
# in any repository that contained one.
BINARY_EXTENSIONS=("docx" "pptx" "pdf")

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Resolve an interpreter rather than assuming `python` exists -- on many
# systems (and most Linux distributions) only `python3` is on PATH.
if [ -n "${PYTHON:-}" ]; then
    :
elif command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
elif command -v python >/dev/null 2>&1; then
    PYTHON=python
else
    echo -e "${RED}Error: no python interpreter found (set PYTHON=/path/to/python)${NC}"
    exit 1
fi

echo "Running VCS document converter pre-commit hook..."

if [ ! -f "$CONVERTER_SCRIPT" ]; then
    echo -e "${RED}Error: VCS converter script not found at $CONVERTER_SCRIPT${NC}"
    exit 1
fi

if ! "$PYTHON" -c "import all2md" >/dev/null 2>&1; then
    echo -e "${RED}Error: all2md is not installed for $PYTHON${NC}"
    echo "  pip install 'all2md[all]'"
    exit 1
fi

# Collect staged documents. -z plus a NUL-delimited read keeps paths with
# spaces or non-ASCII characters intact.
staged_binaries=()
while IFS= read -r -d '' file; do
    for ext in "${BINARY_EXTENSIONS[@]}"; do
        shopt -s nocasematch
        if [[ "$file" == *."$ext" ]]; then
            staged_binaries+=("$file")
            shopt -u nocasematch
            break
        fi
        shopt -u nocasematch
    done
done < <(git diff --cached --name-only --diff-filter=ACM -z)

if [ ${#staged_binaries[@]} -eq 0 ]; then
    echo -e "${GREEN}No binary documents to convert${NC}"
    exit 0
fi

echo -e "${YELLOW}Found ${#staged_binaries[@]} binary document(s) to convert${NC}"

conversion_failed=0
for file in "${staged_binaries[@]}"; do
    echo "Converting: $file"

    # --staged converts what is about to be committed, not what happens to be
    # on disk. With `git add -p` or an unstaged edit those differ, and
    # converting the working tree would commit markdown describing content that
    # was never committed.
    if ! generated=$("$PYTHON" "$CONVERTER_SCRIPT" to-md "$file" --staged); then
        echo -e "${RED}Failed to convert: $file${NC}"
        conversion_failed=1
        continue
    fi

    # Stage exactly the files this conversion produced (the converter prints
    # them on stdout), rather than blanket-adding the output directory and
    # sweeping unrelated stale output into the commit.
    while IFS= read -r path; do
        # Strip a trailing CR: on Windows, Python's print() emits \r\n and the
        # bare \r survives into the pathspec, so `git add` fails on a path that
        # is plainly there.
        path="${path%$'\r'}"
        [ -n "$path" ] && git add -- "$path"
    done <<< "$generated"
done

if [ $conversion_failed -eq 1 ]; then
    echo -e "${RED}Some conversions failed. Commit aborted.${NC}"
    exit 1
fi

echo -e "${GREEN}Document conversion complete${NC}"
exit 0

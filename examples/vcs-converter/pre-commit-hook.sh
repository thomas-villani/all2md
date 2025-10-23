#!/bin/bash
# Pre-commit hook for automatic document conversion
#
# This hook automatically converts binary documents (DOCX, PPTX, PDF) to
# markdown before commit, making them git-friendly and easier to diff.
#
# Installation:
#   cp pre-commit-hook.sh .git/hooks/pre-commit
#   chmod +x .git/hooks/pre-commit

set -e

# Configuration
CONVERTER_SCRIPT="examples/vcs-converter/vcs_converter.py"
PYTHON="${PYTHON:-python}"
BINARY_EXTENSIONS=("docx" "pptx" "pdf" "doc" "ppt")

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "Running VCS document converter pre-commit hook..."

# Check if converter script exists
if [ ! -f "$CONVERTER_SCRIPT" ]; then
    echo -e "${RED}Error: VCS converter script not found at $CONVERTER_SCRIPT${NC}"
    exit 1
fi

# Get list of staged binary documents
staged_binaries=()
for ext in "${BINARY_EXTENSIONS[@]}"; do
    while IFS= read -r file; do
        if [ -n "$file" ]; then
            staged_binaries+=("$file")
        fi
    done < <(git diff --cached --name-only --diff-filter=ACM | grep -i "\.$ext$" || true)
done

# If no binary documents staged, exit successfully
if [ ${#staged_binaries[@]} -eq 0 ]; then
    echo -e "${GREEN}No binary documents to convert${NC}"
    exit 0
fi

echo -e "${YELLOW}Found ${#staged_binaries[@]} binary document(s) to convert${NC}"

# Convert each staged binary document
conversion_failed=0
for file in "${staged_binaries[@]}"; do
    echo "Converting: $file"
    if ! $PYTHON "$CONVERTER_SCRIPT" to-md "$file"; then
        echo -e "${RED}Failed to convert: $file${NC}"
        conversion_failed=1
    fi
done

# Exit if any conversion failed
if [ $conversion_failed -eq 1 ]; then
    echo -e "${RED}Some conversions failed. Commit aborted.${NC}"
    exit 1
fi

# Stage the generated markdown and metadata files
echo "Staging generated markdown files..."
git add .vcs-docs/ 2>/dev/null || true

echo -e "${GREEN}Document conversion complete${NC}"
exit 0

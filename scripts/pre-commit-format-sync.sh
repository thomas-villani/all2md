#!/bin/bash
# Pre-commit hook to validate DocumentFormat Literal synchronization
#
# This script validates that the DocumentFormat Literal in constants.py
# matches the registered formats in the converter registry.
#
# Installation:
#   ln -s ../../scripts/pre-commit-format-sync.sh .git/hooks/pre-commit
#
# Or add to .pre-commit-config.yaml:
#   - repo: local
#     hooks:
#       - id: format-sync
#         name: Validate DocumentFormat synchronization
#         entry: scripts/pre-commit-format-sync.sh
#         language: script
#         files: 'src/all2md/(constants\.py|parsers/.*\.py|renderers/.*\.py)'
#         pass_filenames: false

set -e

echo "Checking DocumentFormat Literal synchronization..."

# Run the validation script
python scripts/update_document_formats.py --validate

if [ $? -eq 0 ]; then
    echo "✓ DocumentFormat Literal is in sync with registry"
    exit 0
else
    echo ""
    echo "ERROR: DocumentFormat Literal is out of sync!"
    echo ""
    echo "Auto-fixing by running update script..."
    python scripts/update_document_formats.py --update

    if [ $? -eq 0 ]; then
        # Stage the updated constants.py file
        git add src/all2md/constants.py
        echo ""
        echo "✓ constants.py has been updated and staged"
        echo "  Proceeding with commit..."
        exit 0
    else
        echo "ERROR: Failed to update constants.py"
        exit 1
    fi
fi

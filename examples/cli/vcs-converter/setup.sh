#!/bin/bash
# Setup script for VCS Document Converter
# This script helps you set up the VCS converter in your repository

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "========================================="
echo "VCS Document Converter Setup"
echo "========================================="
echo ""

# Check if in git repository
if [ ! -d ".git" ]; then
    echo "Error: Not in a git repository"
    echo "Please run this script from the root of your git repository"
    exit 1
fi

echo "Found git repository at: $(pwd)"
echo ""

# Ask if user wants to install the hook
read -p "Install pre-commit hook for automatic conversion? [Y/n] " install_hook
install_hook=${install_hook:-Y}

if [[ $install_hook =~ ^[Yy]$ ]]; then
    echo "Installing pre-commit hook..."
    python "$SCRIPT_DIR/install_hook.py"
    echo ""
fi

# Ask about .gitignore
echo "Git ignore strategy:"
echo "  1. Track both binary and markdown (recommended)"
echo "  2. Track only markdown (exclude binaries)"
echo "  3. Skip .gitignore setup"
echo ""
read -p "Choose option [1/2/3]: " gitignore_choice

case $gitignore_choice in
    1)
        echo "Adding markdown tracking to .gitignore..."
        if ! grep -q ".vcs-docs/" .gitignore 2>/dev/null; then
            echo "" >> .gitignore
            echo "# VCS Document Converter" >> .gitignore
            echo "!.vcs-docs/" >> .gitignore
            echo "~$*.docx" >> .gitignore
            echo "~$*.pptx" >> .gitignore
            echo ".~*.docx" >> .gitignore
            echo ".~*.pptx" >> .gitignore
            echo "*.tmp" >> .gitignore
            echo "Added .vcs-docs tracking to .gitignore"
        else
            echo ".vcs-docs already in .gitignore"
        fi
        ;;
    2)
        echo "Adding binary exclusions to .gitignore..."
        {
            echo ""
            echo "# VCS Document Converter - Track markdown only"
            echo "*.docx"
            echo "*.pptx"
            echo "*.pdf"
            echo "!.vcs-docs/"
            echo "~$*.docx"
            echo "~$*.pptx"
        } >> .gitignore
        echo "Added binary exclusions to .gitignore"
        ;;
    3)
        echo "Skipping .gitignore setup"
        ;;
    *)
        echo "Invalid choice, skipping .gitignore setup"
        ;;
esac

echo ""

# Ask about config file
read -p "Create vcs-converter.config.json? [Y/n] " create_config
create_config=${create_config:-Y}

if [[ $create_config =~ ^[Yy]$ ]]; then
    if [ -f "vcs-converter.config.json" ]; then
        echo "vcs-converter.config.json already exists, skipping"
    else
        cp "$SCRIPT_DIR/vcs-converter.config.json" .
        echo "Created vcs-converter.config.json"
    fi
fi

echo ""

# Scan for existing documents
echo "Scanning for binary documents..."
python "$SCRIPT_DIR/vcs_converter.py" scan

echo ""

# Ask if user wants to convert now
read -p "Convert all existing documents now? [y/N] " convert_now
convert_now=${convert_now:-N}

if [[ $convert_now =~ ^[Yy]$ ]]; then
    echo "Converting documents..."
    python "$SCRIPT_DIR/vcs_converter.py" batch
    echo ""
    echo "Conversion complete!"
    echo ""
    echo "You may want to commit the generated markdown:"
    echo "  git add .vcs-docs/"
    echo "  git commit -m 'Add markdown versions of documents'"
fi

echo ""
echo "========================================="
echo "Setup Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Edit your documents as usual"
echo "  2. Commit normally - conversion happens automatically"
echo "  3. Review changes with: git diff .vcs-docs/"
echo ""
echo "For more information, see:"
echo "  - Quick start: $SCRIPT_DIR/QUICKSTART.md"
echo "  - Full docs: $SCRIPT_DIR/README.md"
echo ""
echo "To run the demo:"
echo "  python $SCRIPT_DIR/demo.py"
echo ""

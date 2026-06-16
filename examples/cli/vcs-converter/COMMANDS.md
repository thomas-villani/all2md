# Command Reference

Quick reference for all VCS converter commands.

## Main Converter Commands

### Convert Single Document
```bash
python vcs_converter.py to-md document.docx
```

### Convert All Documents
```bash
python vcs_converter.py batch
python vcs_converter.py batch --force  # Force reconversion
python vcs_converter.py batch --root /path/to/dir  # Specific directory
```

### Convert Markdown Back to Binary
```bash
python vcs_converter.py to-binary .vcs-docs/document.vcs.md
python vcs_converter.py to-binary .vcs-docs/document.vcs.md --output custom.docx
```

### Scan Repository
```bash
python vcs_converter.py scan
python vcs_converter.py scan --root /path/to/dir
```

### Clean Generated Files
```bash
python vcs_converter.py clean
```

### Use Custom Config
```bash
python vcs_converter.py --config my-config.json batch
```

## Hook Installation

### Install Pre-commit Hook
```bash
python install_hook.py
```

### Manual Hook Installation
```bash
cp pre-commit-hook.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

### Disable Hook Temporarily
```bash
git commit --no-verify
```

## Setup

### Interactive Setup
```bash
bash setup.sh
```

### Manual Setup Steps
```bash
# 1. Copy example to your repo
cp -r examples/vcs-converter /path/to/repo/.vcs-converter

# 2. Install hook
python .vcs-converter/install_hook.py

# 3. Update .gitignore
cat .vcs-converter/.gitignore.template >> .gitignore

# 4. Create config
cp .vcs-converter/vcs-converter.config.json .

# 5. Convert existing docs
python .vcs-converter/vcs_converter.py batch
```

## Git Commands

### View Document Changes
```bash
git diff .vcs-docs/document.vcs.md
```

### Stage Generated Files
```bash
git add .vcs-docs/
```

### Commit Both Binary and Markdown
```bash
git add document.docx .vcs-docs/
git commit -m "Update document"
```

### View History
```bash
git log -p .vcs-docs/document.vcs.md
```

### Show Specific Version
```bash
git show HEAD~1:.vcs-docs/document.vcs.md
```

## Demo

### Run Full Demo
```bash
python demo.py
```

### Test Conversion
```bash
# The demo creates sample documents and shows:
# - Basic conversion
# - Batch processing
# - Bidirectional conversion
# - Git workflow simulation
```

## Troubleshooting Commands

### Verify Installation
```bash
python vcs_converter.py --help
python install_hook.py
ls -la .git/hooks/pre-commit
```

### Test Hook
```bash
# Create/modify a document
touch test.docx

# Test hook manually
.git/hooks/pre-commit
```

### Debug Conversion
```bash
python -v vcs_converter.py to-md document.docx
```

### Check File Format
```bash
file document.docx
```

## Advanced Usage

### Convert Specific File Types Only
```bash
find . -name "*.docx" -exec python vcs_converter.py to-md {} \;
```

### Batch Convert with Error Handling
```bash
for file in docs/*.docx; do
    python vcs_converter.py to-md "$file" || echo "Failed: $file"
done
```

### Compare Binary vs Markdown
```bash
# Convert twice and compare
python vcs_converter.py to-md document.docx
python vcs_converter.py to-binary .vcs-docs/document.vcs.md --output recreated.docx
diff -q document.docx recreated.docx
```

## Configuration

### Create Config File
```bash
cat > vcs-converter.config.json << EOF
{
  "markdown_dir": ".vcs-docs",
  "track_metadata": true,
  "preserve_images": true,
  "line_width": 80
}
EOF
```

### Use Environment Variables
```bash
export PYTHON=python3
.git/hooks/pre-commit
```

## Integration Examples

### Pre-commit Framework
```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: vcs-converter
        name: Convert documents
        entry: python .vcs-converter/vcs_converter.py batch
        language: system
        pass_filenames: false
```

### GitHub Actions
```yaml
# .github/workflows/docs.yml
- name: Convert documents
  run: python .vcs-converter/vcs_converter.py batch

- name: Check for changes
  run: git diff --exit-code .vcs-docs/
```

### Makefile
```makefile
.PHONY: convert-docs
convert-docs:
	python .vcs-converter/vcs_converter.py batch

.PHONY: clean-docs
clean-docs:
	python .vcs-converter/vcs_converter.py clean
```

## Quick Reference Card

```
# Setup
bash setup.sh                              # Interactive setup
python install_hook.py                     # Install hook

# Daily Use
git commit -am "message"                   # Auto-converts if hook installed
python vcs_converter.py to-md file.docx    # Manual convert

# Review
git diff .vcs-docs/file.vcs.md            # See changes
cat .vcs-docs/file.vcs.md                 # Read markdown

# Maintenance
python vcs_converter.py scan               # List binary docs
python vcs_converter.py batch --force      # Reconvert all
python vcs_converter.py clean              # Remove generated files

# Demo
python demo.py                             # See it in action
```

## Keyboard Shortcuts (if using Git GUI)

Most Git GUIs will show `.vcs-docs/` files in diffs automatically. Look for:
- "View file diff" - Shows markdown changes
- "Show history" - Shows document evolution
- "Blame/Annotate" - Shows who changed what

## Exit Codes

- `0` - Success
- `1` - Error (check logs)

## Help

```bash
python vcs_converter.py --help
python vcs_converter.py batch --help
python vcs_converter.py to-md --help
python vcs_converter.py to-binary --help
```

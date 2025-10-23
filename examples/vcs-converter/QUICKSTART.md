# Quick Start Guide

Get up and running with VCS Document Converter in 5 minutes.

## Installation

```bash
# Install all2md
pip install all2md

# Clone or copy this example to your repository
cp -r examples/vcs-converter /path/to/your/repo/.vcs-converter
cd /path/to/your/repo
```

## Try It Out (30 seconds)

```bash
# Convert a document
python .vcs-converter/vcs_converter.py to-md your-document.docx

# View the markdown
cat .vcs-docs/your-document.vcs.md

# Convert it back
python .vcs-converter/vcs_converter.py to-binary .vcs-docs/your-document.vcs.md
```

## Enable Automatic Conversion (1 minute)

```bash
# Install the pre-commit hook
python .vcs-converter/install_hook.py

# Now conversion happens automatically on commit
git add document.docx
git commit -m "Update document"  # Automatically creates .vcs-docs/document.vcs.md
```

## What Just Happened?

1. **to-md**: Converted your binary document to markdown
2. **Generated files**:
   - `.vcs-docs/document.vcs.md` - Readable markdown version
   - `.vcs-docs/document.vcs.json` - Metadata for reconstruction
3. **to-binary**: Converted markdown back to the original format

## Next Steps

### Track in Git

Add to `.gitignore`:
```bash
# Track both markdown and binary (recommended)
!.vcs-docs/

# Or exclude binaries, track only markdown
*.docx
*.pptx
*.pdf
!.vcs-docs/
```

Commit:
```bash
git add .vcs-docs/
git commit -m "Add markdown versions of documents"
```

### See Changes

```bash
# Make a change to your document
# Convert again
python .vcs-converter/vcs_converter.py to-md your-document.docx

# See exactly what changed
git diff .vcs-docs/your-document.vcs.md
```

### Convert All Documents

```bash
# Scan repository
python .vcs-converter/vcs_converter.py scan

# Convert everything
python .vcs-converter/vcs_converter.py batch
```

## Common Workflows

### Daily Work (Hook Enabled)

```bash
# Edit your documents normally
# Commit as usual - markdown is created automatically
git add document.docx
git commit -m "Updated Q4 projections"
```

### Manual Control

```bash
# Convert specific file
python .vcs-converter/vcs_converter.py to-md report.docx

# Review the markdown
git diff .vcs-docs/report.vcs.md

# Commit both
git add report.docx .vcs-docs/
git commit -m "Update report"
```

### Review Changes

```bash
# Pull changes from teammate
git pull

# See what they changed (in readable text!)
git log -p .vcs-docs/shared-doc.vcs.md
```

## Troubleshooting

### "Command not found"

```bash
# Use full path
python /path/to/.vcs-converter/vcs_converter.py to-md document.docx
```

### "Hook not running"

```bash
# Check installation
ls -la .git/hooks/pre-commit

# Reinstall
python .vcs-converter/install_hook.py

# Or commit without hook to test
git commit --no-verify
```

### "Conversion failed"

```bash
# Check document format
file document.docx

# Try with verbose output
python -v .vcs-converter/vcs_converter.py to-md document.docx
```

## Getting Help

- Read the full [README.md](README.md)
- Check [CONTRIBUTING.md](CONTRIBUTING.md) for development
- Run the demo: `python .vcs-converter/demo.py`
- File issues in the all2md repository

## Tips

1. Start with one document to test
2. Use the hook for convenience
3. Review markdown in PRs instead of binary diffs
4. Keep backups until you're comfortable
5. Use meaningful commit messages for document changes

That's it! You're ready to make your documents git-friendly.

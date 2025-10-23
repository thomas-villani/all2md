## Version Control System (VCS) Document Converter

**Location:** `examples/vcs-converter/`

**Difficulty:** Hard

### Description

Make binary documents (DOCX, PPTX, PDF) git-friendly by automatically converting them to markdown for version control. This example shows a production-ready workflow for tracking document changes in plain text while maintaining the ability to reconstruct the original binary formats.

### Features

- Convert binary formats to markdown for git tracking
- Pre-commit hook integration for automatic conversion
- Track document changes in text format with meaningful diffs
- Bidirectional sync (markdown ↔ binary)
- Preserve formatting metadata
- Diff-friendly output optimized for code review
- Batch processing entire repositories
- Configurable behavior via JSON config

### Use Cases

- **Document Version Control**: Track changes to documentation over time with meaningful diffs
- **Collaborative Editing**: Multiple people editing documents with proper merge conflict resolution
- **Change Tracking**: See exactly what changed without opening binary files
- **Compliance/Auditing**: Maintain detailed change history for regulatory requirements
- **Code Review**: Review document changes as part of pull request workflow

### Quick Start

```bash
# Install in your repository
cp -r examples/vcs-converter /path/to/your/repo/.vcs-converter
cd /path/to/your/repo

# Convert a document
python .vcs-converter/vcs_converter.py to-md document.docx

# View the readable markdown
cat .vcs-docs/document.vcs.md

# Install automatic conversion on commit
python .vcs-converter/install_hook.py
```

### What You'll Learn

- **Batch Processing**: Efficiently process multiple files in a repository
- **Git Integration**: Seamless integration with git workflow and hooks
- **Bidirectional Conversion**: Using both parsers and renderers
- **AST Manipulation**: Extracting and preserving metadata from document AST
- **Multiple Format Support**: Handling DOCX, PPTX, and PDF formats
- **CLI Design**: Building a professional command-line tool with argparse
- **Configuration Management**: Using JSON config files for customization

### Files

- `vcs_converter.py` - Main CLI tool for conversion
- `demo.py` - Interactive demo of all features
- `install_hook.py` - Pre-commit hook installer
- `pre-commit-hook.sh` - Bash git hook script
- `README.md` - Complete documentation
- `QUICKSTART.md` - 5-minute getting started guide
- `CONTRIBUTING.md` - Development guide

### Sample Workflow

```bash
# Day-to-day usage with hook installed
vim report.docx
git add report.docx
git commit -m "Update Q4 projections"
# Hook automatically creates .vcs-docs/report.vcs.md

# Review changes
git diff .vcs-docs/report.vcs.md

# Reconstruct binary from markdown
python .vcs-converter/vcs_converter.py to-binary .vcs-docs/report.vcs.md
```

### Advanced Features

- Configurable markdown directory
- Metadata preservation in separate JSON files
- Optional full AST storage for perfect reconstruction
- Exclude patterns for temporary files
- Force reconversion option
- Repository scanning
- Clean operation to remove all generated files

### Documentation

See the full [README.md](vcs-converter/README.md) for:
- Detailed installation instructions
- Three different workflow strategies
- CI/CD integration examples
- Troubleshooting guide
- Best practices

### Showcases

- Batch processing and repository scanning
- Git hook integration
- Bidirectional format conversion
- AST serialization and metadata
- Multiple output formats
- CLI tool design
- Production-ready error handling

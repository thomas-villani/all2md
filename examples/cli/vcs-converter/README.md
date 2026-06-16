# Version Control System Document Converter

Make binary documents (DOCX, PPTX, PDF) git-friendly by automatically converting them to markdown for version control.

## Overview

Binary document formats like DOCX, PPTX, and PDF are difficult to version control effectively:
- Git can't show meaningful diffs
- Merge conflicts are impossible to resolve
- File history is opaque
- Collaboration is challenging

This tool solves these problems by maintaining parallel markdown versions of your binary documents that are:
- **Diff-friendly**: See exactly what changed between versions
- **Merge-friendly**: Resolve conflicts in plain text
- **Human-readable**: Review changes without opening applications
- **Bidirectional**: Convert back to binary when needed

## Features

- Convert binary formats (DOCX, PPTX, PDF) to markdown for git tracking
- Pre-commit hook integration for automatic conversion
- Track document changes in text format
- Bidirectional sync (markdown <-> binary)
- Preserve formatting metadata
- Diff-friendly output with configurable line width
- Batch processing for entire repositories
- Configurable behavior via JSON config file

## Use Cases

1. **Document Version Control**: Track changes to documentation over time
2. **Collaborative Editing**: Multiple people editing documents with proper merge conflict resolution
3. **Change Tracking**: See exactly what changed in a document without opening it
4. **Compliance/Auditing**: Maintain detailed change history for regulatory requirements
5. **Code Review**: Review document changes as part of pull request workflow

## Installation

### Prerequisites

```bash
pip install all2md
```

### Setup in Your Repository

1. Copy the example to your repository:
```bash
cp -r examples/vcs-converter /path/to/your/repo/.vcs-converter
cd /path/to/your/repo
```

2. Install the pre-commit hook (optional but recommended):
```bash
python .vcs-converter/install_hook.py
```

3. Add to your `.gitignore` (choose your strategy):
```bash
# Option A: Track both binary and markdown (recommended for most cases)
cat .vcs-converter/.gitignore.template >> .gitignore

# Option B: Track only markdown (exclude binaries)
# Edit .gitignore to exclude *.docx, *.pptx, *.pdf
```

## Usage

### Automatic Conversion (Pre-commit Hook)

Once the hook is installed, documents are automatically converted when you commit:

```bash
# Edit your document
vim report.docx

# Commit as usual - conversion happens automatically
git add report.docx
git commit -m "Update quarterly report"

# Both report.docx and .vcs-docs/report.vcs.md are committed
```

### Manual Conversion

#### Convert a Single Document

```bash
python .vcs-converter/vcs_converter.py to-md document.docx
```

This creates:
- `.vcs-docs/document.vcs.md` - The markdown version
- `.vcs-docs/document.vcs.json` - Metadata for reconstruction

#### Batch Convert All Documents

```bash
# Convert all binary documents in repository
python .vcs-converter/vcs_converter.py batch

# Force reconversion even if markdown exists
python .vcs-converter/vcs_converter.py batch --force
```

#### Convert Markdown Back to Binary

```bash
python .vcs-converter/vcs_converter.py to-binary .vcs-docs/document.vcs.md
```

This recreates the original binary format using the stored metadata.

#### Scan for Binary Documents

```bash
python .vcs-converter/vcs_converter.py scan
```

#### Clean Generated Files

```bash
python .vcs-converter/vcs_converter.py clean
```

## Configuration

Create a `vcs-converter.config.json` file in your repository root:

```json
{
  "markdown_dir": ".vcs-docs",
  "track_metadata": true,
  "preserve_images": true,
  "line_width": 80,
  "store_ast": false,
  "exclude_patterns": [
    "*.tmp.docx",
    "~$*.docx",
    "**/build/**",
    "**/dist/**"
  ],
  "auto_commit_markdown": false,
  "diff_friendly": true
}
```

### Configuration Options

- `markdown_dir`: Directory for generated markdown (default: `.vcs-docs`)
- `track_metadata`: Store metadata for reconstruction (default: `true`)
- `preserve_images`: Extract and preserve images (default: `true`)
- `line_width`: Maximum line width for markdown (default: `80`)
- `store_ast`: Store full AST for perfect reconstruction (default: `false`)
- `exclude_patterns`: Glob patterns for files to exclude
- `auto_commit_markdown`: Automatically stage markdown files (default: `false`)
- `diff_friendly`: Optimize output for git diff (default: `true`)

## Workflows

### Workflow 1: Track Both Binary and Markdown

Best for: Most use cases, especially when non-technical collaborators need the binary files.

```bash
# 1. Edit document normally
# 2. Commit triggers automatic conversion
git add report.docx
git commit -m "Update report"

# 3. Both files are committed and tracked
# 4. Reviewers can diff the markdown to see changes
```

**Pros:**
- Works for all collaborators
- No risk of losing binary formatting
- Easy to share final documents

**Cons:**
- Larger repository size
- Some redundancy

### Workflow 2: Track Only Markdown

Best for: Technical teams, markdown-native workflows, minimizing repository size.

```bash
# 1. Add binary extensions to .gitignore
echo "*.docx" >> .gitignore
echo "*.pptx" >> .gitignore
echo "*.pdf" >> .gitignore

# 2. Commit only markdown versions
git add .vcs-docs/
git commit -m "Update documentation"

# 3. Recreate binary when needed
python .vcs-converter/vcs_converter.py to-binary .vcs-docs/report.vcs.md
```

**Pros:**
- Smaller repository
- Full git diff/merge capabilities
- Faster clone times

**Cons:**
- Need to regenerate binaries
- Requires all collaborators to use the tool

### Workflow 3: Hybrid Approach

Track markdown for documents under active development, commit binaries only for releases.

```bash
# During development
git add .vcs-docs/
git commit -m "WIP: Update report"

# At release
python .vcs-converter/vcs_converter.py to-binary .vcs-docs/report.vcs.md
git add report.docx
git tag v1.0
```

## How It Works

### Conversion Process

1. **Binary to Markdown**:
   - Uses `all2md` library to parse binary format
   - Extracts document structure and content
   - Preserves formatting metadata in separate JSON file
   - Generates diff-friendly markdown output

2. **Markdown to Binary**:
   - Reads markdown and metadata
   - Reconstructs document structure
   - Uses `all2md` renderers to create binary format
   - Preserves original formatting where possible

### Metadata Storage

The `.vcs.json` files store:
- Source file format
- Document metadata (title, author, etc.)
- Formatting information
- Optional: Full AST for perfect reconstruction

### Directory Structure

```
your-repo/
├── docs/
│   └── report.docx                 # Original binary
├── .vcs-docs/                      # Generated markdown
│   └── docs/
│       ├── report.vcs.md          # Markdown version
│       └── report.vcs.json        # Metadata
└── .git/
    └── hooks/
        └── pre-commit              # Auto-conversion hook
```

## Advanced Usage

### Custom Configuration Per Project

Create `.vcs-converter/config.json` in your repo:

```bash
python .vcs-converter/vcs_converter.py batch --config .vcs-converter/config.json
```

### Selective Conversion

Convert only specific file types:

```bash
# Convert only DOCX files
find . -name "*.docx" -exec python .vcs-converter/vcs_converter.py to-md {} \;
```

### Integration with CI/CD

```yaml
# .github/workflows/docs-check.yml
name: Document Check
on: [pull_request]

jobs:
  check-docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Install dependencies
        run: pip install all2md
      - name: Convert documents
        run: python .vcs-converter/vcs_converter.py batch
      - name: Check for changes
        run: |
          if [[ `git status --porcelain` ]]; then
            echo "Error: Markdown versions are out of sync"
            git diff
            exit 1
          fi
```

### Pre-commit Framework Integration

For teams using the `pre-commit` framework:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: vcs-converter
        name: Convert binary documents
        entry: python .vcs-converter/vcs_converter.py batch
        language: system
        pass_filenames: false
```

## Troubleshooting

### Hook Not Running

```bash
# Verify hook is installed
ls -l .git/hooks/pre-commit

# Check permissions
chmod +x .git/hooks/pre-commit

# Test hook manually
.git/hooks/pre-commit
```

### Conversion Failures

```bash
# Enable debug logging
PYTHONPATH=. python -v .vcs-converter/vcs_converter.py to-md document.docx

# Check document format
file document.docx
```

### Merge Conflicts in Markdown

Markdown conflicts can be resolved like code:

```bash
# 1. Git will mark conflicts in .vcs-docs/*.vcs.md
# 2. Edit the markdown to resolve
# 3. Regenerate binary if needed
python .vcs-converter/vcs_converter.py to-binary .vcs-docs/document.vcs.md

# 4. Mark as resolved
git add .vcs-docs/document.vcs.md document.docx
git commit
```

### Large Binary Files

For large documents, consider:

```json
{
  "store_ast": false,
  "preserve_images": false,
  "line_width": 120
}
```

## Limitations

- **Format Fidelity**: Complex formatting may not round-trip perfectly
- **Macros/Scripts**: Document macros and scripts are not preserved
- **Embedded Objects**: Some embedded objects may not convert
- **Version-Specific Features**: Features specific to newer format versions may be lost

## Best Practices

1. **Commit Often**: Smaller changes = easier diffs
2. **Meaningful Messages**: Describe document changes in commit messages
3. **Review Markdown**: Use markdown diffs during code review
4. **Test Round-trips**: Verify binary reconstruction before important releases
5. **Keep Binaries**: For production documents, commit both versions
6. **Exclude Temps**: Always exclude Office temp files (`.~lock`, `~$`, etc.)

## Examples

### Example 1: Technical Documentation

```bash
# Setup
python .vcs-converter/install_hook.py

# Edit your docs
vim user-guide.docx

# Commit
git add user-guide.docx
git commit -m "Add troubleshooting section to user guide"

# Reviewer sees readable diff
git diff HEAD~1 .vcs-docs/user-guide.vcs.md
```

### Example 2: Contract Review

```bash
# Convert existing contracts
python .vcs-converter/vcs_converter.py batch

# Commit baseline
git add .vcs-docs/
git commit -m "Add baseline contract versions"

# After edits
git diff .vcs-docs/contract.vcs.md  # Shows exact changes in plain text
```

### Example 3: Presentation Collaboration

```bash
# Team member 1
vim presentation.pptx
git commit -am "Add Q4 results slides"

# Team member 2 (pulls changes)
git pull
# Reviews changes in .vcs-docs/presentation.vcs.md
# Opens presentation.pptx with changes incorporated
```

## Technical Details

This example showcases several `all2md` features:

1. **Batch Processing**: Processing multiple files efficiently
2. **Git Integration**: Seamless integration with git workflow
3. **Bidirectional Conversion**: Both parsing and rendering capabilities
4. **AST Manipulation**: Using the AST for metadata extraction
5. **Multiple Format Support**: Handling DOCX, PPTX, and PDF

## Contributing

Improvements welcome:
- Additional format support
- Better metadata handling
- Performance optimizations
- Git LFS integration
- Better conflict resolution strategies

## License

This example is part of the all2md project and follows the same license.

## See Also

- [all2md documentation](https://github.com/thomas-villani/all2md)
- [Git hooks documentation](https://git-scm.com/book/en/v2/Customizing-Git-Git-Hooks)
- [Pre-commit framework](https://pre-commit.com/)

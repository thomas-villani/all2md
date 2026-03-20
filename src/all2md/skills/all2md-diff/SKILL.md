---
name: all2md-diff
description: "Use this skill when the user wants to compare two documents or see what changed between document versions. Triggers: comparing documents, diffing files, 'what changed', version comparison, finding differences between documents. Works across formats — compare a PDF against a Word doc, or two versions of an HTML page."
metadata:
  author: all2md
  version: "1.0"
---

# Comparing Documents with all2md

## Overview

`all2md diff` compares any two documents regardless of format. It converts both to Markdown, then produces a unified diff. Compare a PDF against a Word doc, two versions of an HTML page, or any combination of supported formats.

## CLI Quick Reference

### Basic Diff

```bash
# Compare two documents (unified diff output)
all2md diff original.docx modified.docx

# Compare PDFs
all2md diff v1.pdf v2.pdf

# Compare HTML files
all2md diff page-old.html page-new.html
```

### Cross-Format Diff

Documents don't need to be the same format — all2md converts both to Markdown first:

```bash
# Compare PDF against Word doc
all2md diff document.pdf document.docx

# Compare HTML against Markdown
all2md diff page.html content.md
```

### Output Formats

```bash
# Default: unified diff (colored terminal output)
all2md diff original.docx modified.docx

# HTML diff (visual side-by-side comparison)
all2md diff original.pdf modified.pdf --format html -o diff.html

# JSON diff (machine-readable)
all2md diff v1.docx v2.docx --format json -o changes.json
```

### Diff Options

```bash
# Ignore whitespace differences
all2md diff original.md modified.md --ignore-whitespace

# Change context lines (default: 3)
all2md diff original.docx modified.docx --context 5
all2md diff original.docx modified.docx -C 0  # no context
```

### Diff Granularity

```bash
# Paragraph-level (default)
all2md diff v1.docx v2.docx --granularity block

# Sentence-level
all2md diff v1.docx v2.docx --granularity sentence

# Word-level
all2md diff v1.docx v2.docx --granularity word
```

### Stdin

```bash
# Diff with stdin
echo "<p>Version 1</p>" | all2md diff - version2.html
cat old.pdf | all2md diff - new.pdf
```

### Color Control

```bash
# Force color (for piping to tools that support ANSI)
all2md diff v1.pdf v2.pdf --color always

# Disable color (for piping to plain text tools)
all2md diff v1.pdf v2.pdf --color never
```

## Tips

- Cross-format diff works because both documents are converted to Markdown before comparison
- Use `--format html -o diff.html` for a visual comparison you can open in a browser
- Use `--granularity word` for the most detailed diff output
- Use `-C 0` for changes-only output without surrounding context

---
name: all2md-view-diff
description: "Use this skill when the user wants to view, preview, or compare documents. Triggers: viewing a document in the browser, previewing conversion output, comparing two document versions, diffing files of any format, generating HTML previews with themes. Use when the user says 'show me', 'view', 'preview', 'compare', 'diff', or 'what changed'."
metadata:
  author: all2md
  version: "1.0"
---

# Viewing and Comparing Documents with all2md

## View Command — Browser Preview

The `view` command converts any document to themed HTML and opens it in the default browser.

```bash
# Basic view (opens in browser, temp file auto-deleted)
all2md view document.pdf
all2md view report.docx
all2md view slides.pptx

# Keep the HTML file
all2md view document.pdf --keep
all2md view document.pdf --keep output.html

# With table of contents
all2md view document.pdf --toc

# Read from stdin
cat document.pdf | all2md view -
curl https://example.com/doc.pdf | all2md view -
```

### Themes

```bash
# Built-in themes
all2md view document.pdf --theme minimal
all2md view document.pdf --theme dark
all2md view document.pdf --theme newspaper
all2md view document.pdf --theme docs
all2md view document.pdf --theme sidebar

# Dark mode (shorthand)
all2md view document.pdf --dark

# Custom HTML template
all2md view document.pdf --theme my-template.html
```

### Extract and View Sections

```bash
# View specific section
all2md view document.pdf --extract "Chapter 3"

# View heading range
all2md view document.pdf --extract "#:2-5"
```

## Diff Command — Document Comparison

Compare any two documents (any format) with unified diff output, similar to `diff -u`.

```bash
# Basic diff (unified format, colored terminal output)
all2md diff original.docx modified.docx

# HTML diff output (visual side-by-side)
all2md diff original.pdf modified.pdf --format html -o diff.html

# JSON diff output (machine-readable)
all2md diff v1.docx v2.docx --format json -o changes.json
```

### Diff Options

```bash
# Ignore whitespace differences
all2md diff original.md modified.md --ignore-whitespace

# Change context lines (default: 3)
all2md diff original.docx modified.docx --context 5
all2md diff original.docx modified.docx -C 0  # no context

# Change diff granularity
all2md diff v1.docx v2.docx --granularity block     # paragraph-level
all2md diff v1.docx v2.docx --granularity sentence   # sentence-level
all2md diff v1.docx v2.docx --granularity word        # word-level

# Color control
all2md diff v1.pdf v2.pdf --color always
all2md diff v1.pdf v2.pdf --color never  # for piping
```

### Cross-Format Diff

Documents don't need to be the same format — all2md converts both to Markdown first, then diffs:

```bash
# Compare PDF against Word doc
all2md diff document.pdf document.docx

# Compare HTML against Markdown
all2md diff page.html content.md

# Diff with stdin
echo "<p>Version 1</p>" | all2md diff - version2.html
cat old.pdf | all2md diff - new.pdf
```

### HTML Diff Output

The HTML diff format produces a visual comparison suitable for viewing in a browser:

```bash
# Generate and view diff
all2md diff v1.docx v2.docx --format html -o diff.html

# Without context lines (changes only)
all2md diff v1.docx v2.docx --format html --no-context -o diff.html
```

## HTTP Server — On-Demand Viewing

For repeated viewing, run the built-in server:

```bash
# Start server (browse to http://localhost:8000)
all2md serve --root-dir ./documents

# Custom port and theme
all2md serve --port 9000 --theme docs --root-dir ./documents

# Allow file uploads
all2md serve --allow-upload --root-dir ./documents
```

The server provides directory listings and on-demand conversion of any document.

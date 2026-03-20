---
name: all2md-grep
description: "Use this skill when you need to search for a pattern or text inside documents. Triggers: searching inside PDFs, grepping Word documents, finding text in PowerPoint slides, pattern matching in non-plaintext files. Use when the user says 'find in this PDF', 'search this document for', 'grep', or when you need to locate specific content inside a document file without converting the whole thing."
metadata:
  author: all2md
  version: "1.0"
---

# Grep Documents with all2md

## Overview

`all2md grep` works like `grep` but on any document format — PDF, DOCX, PPTX, HTML, XLSX, and more. It converts documents to text on-the-fly, then searches for your pattern.

## CLI Quick Reference

### Basic Usage

```bash
# Search a single document
all2md grep "revenue" report.pdf
all2md grep "TODO" specification.docx
all2md grep "deadline" slides.pptx

# Search multiple files
all2md grep "pattern" *.pdf
all2md grep "confidential" ./contracts/*.docx

# Recursive search through directory
all2md grep "pattern" ./documents -r
```

### Flags

```bash
# Case-insensitive
all2md grep -i "important" document.pdf

# Show line numbers
all2md grep -n "section 4" document.pdf

# Count matches
all2md grep -c "warning" *.pdf

# Invert match (lines NOT matching)
all2md grep -v "draft" report.docx

# Context lines (before/after/both)
all2md grep -B 2 "error" document.pdf
all2md grep -A 3 "conclusion" document.pdf
all2md grep -C 2 "important" document.pdf
```

### Output Formats

```bash
# Default: terminal output with highlighted matches
all2md grep "pattern" document.pdf

# JSON output (machine-readable)
all2md grep "pattern" *.pdf --output json
```

### Stdin

```bash
# Pipe document content
cat document.pdf | all2md grep "pattern" -
curl https://example.com/report.pdf | all2md grep "revenue" -
```

## Python API

The simplest approach is convert-then-search:

```python
from all2md import to_markdown
from pathlib import Path
import re

# Search a single document
text = to_markdown("document.pdf")
for i, line in enumerate(text.splitlines(), 1):
    if re.search(r"pattern", line, re.IGNORECASE):
        print(f"{i}: {line}")

# Search across multiple documents
for pdf_file in Path("./documents").glob("*.pdf"):
    text = to_markdown(pdf_file)
    if "search term" in text.lower():
        print(f"Found in: {pdf_file}")
```

## Tips

- `grep` is best for quick pattern matching across a few files
- For ranked relevance results across many documents, use `all2md search` instead (see `all2md-search` skill)
- Both commands work with any format all2md can read (40+ formats)
- Use `--output json` when you need structured results for scripting

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

# Treat the pattern as a regular expression
all2md grep -e "error|warning|fatal" document.pdf

# Context lines (before/after/both)
all2md grep -B 2 "error" document.pdf
all2md grep -A 3 "conclusion" document.pdf
all2md grep -C 2 "important" document.pdf

# Truncate very long matching lines
all2md grep -M 200 "pattern" document.pdf
```

### Output Formats

```bash
# Default: plain terminal output with matching lines
all2md grep "pattern" document.pdf

# Rich-formatted output with highlighted matches
all2md grep "pattern" *.pdf --rich
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
- Use `-e`/`--regex` to match with a regular expression instead of a literal string

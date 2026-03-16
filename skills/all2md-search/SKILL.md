---
name: all2md-search
description: "Use this skill when the user wants to search, grep, or find content inside documents. Triggers: searching for text in PDFs, Word docs, or other non-plaintext files; grepping across document collections; building search indexes over document libraries; semantic or keyword search across files. Use when the user says 'find in', 'search for', 'grep', or wants to locate information inside documents."
metadata:
  author: all2md
  version: "1.0"
---

# Searching Documents with all2md

## Grep — Pattern Matching in Documents

Works like `grep` but on any document format (PDF, DOCX, PPTX, HTML, etc.). Converts documents to text on-the-fly, then searches.

```bash
# Search a single document
all2md grep "revenue" report.pdf
all2md grep "TODO" specification.docx

# Search multiple files
all2md grep "deadline" *.pdf
all2md grep "confidential" ./contracts/*.docx

# Case-insensitive
all2md grep -i "important" document.pdf

# Show context lines
all2md grep -B 2 -A 2 "error" logfile.pdf

# Count matches
all2md grep -c "warning" *.pdf

# Show line numbers
all2md grep -n "section 4" document.pdf

# Invert match (lines NOT matching)
all2md grep -v "draft" report.docx

# Output as JSON
all2md grep "pattern" *.pdf --output json
```

### Grep from Stdin

```bash
cat document.pdf | all2md grep "pattern" -
curl https://example.com/report.pdf | all2md grep "revenue" -
```

## Search — Advanced Document Search

Full-featured search with keyword, BM25, semantic, and hybrid modes.

```bash
# Keyword search across documents
all2md search "machine learning" ./papers/*.pdf

# BM25 ranking (better relevance)
all2md search "quarterly results" ./reports --mode bm25

# Semantic search (meaning-based, not just keyword matching)
all2md search "how to configure authentication" ./docs --semantic

# Hybrid search (combines keyword + semantic)
all2md search "error handling" ./codebase --mode hybrid

# Limit results
all2md search "budget" ./finance --top-k 5

# Show context snippets
all2md search "performance" ./reports --show-snippet
```

### Persistent Search Index

For repeated searches over the same documents, build a persistent index:

```bash
# Build and persist index
all2md search "first query" ./documents --index-dir ./search-index

# Subsequent searches reuse the index (fast)
all2md search "second query" ./documents --index-dir ./search-index
all2md search "third query" ./documents --index-dir ./search-index
```

### Search Output Formats

```bash
# Rich terminal output (default)
all2md search "query" ./docs --output rich

# Plain text
all2md search "query" ./docs --output plain

# JSON (for programmatic use)
all2md search "query" ./docs --output json
```

### Tuning

```bash
# Adjust chunk size for indexing
all2md search "query" ./docs --chunk-size 500

# Show progress during indexing
all2md search "query" ./large-collection --progress
```

## Python API

```python
from all2md import to_markdown

# Simple approach: convert then search in Python
for pdf_file in Path("./documents").glob("*.pdf"):
    text = to_markdown(pdf_file)
    if "search term" in text.lower():
        print(f"Found in: {pdf_file}")
```

## Tips

- `grep` is best for quick pattern matching across a few files
- `search` with `--mode bm25` is best for relevance-ranked results
- `search --semantic` requires embedding support but finds meaning-based matches
- Use `--index-dir` when searching the same collection repeatedly
- Both commands work with any format all2md can read (40+ formats)

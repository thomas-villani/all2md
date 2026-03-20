---
name: all2md-search
description: "Use this skill when you need ranked, semantic, or full-text search across a collection of documents. Triggers: searching across many documents, finding the most relevant documents, semantic search, keyword ranking, building search indexes. Use when the user says 'search these documents', 'find the most relevant', 'semantic search', or when simple grep isn't enough and you need ranked results."
metadata:
  author: all2md
  version: "1.0"
---

# Advanced Document Search with all2md

## Overview

`all2md search` provides ranked search across document collections using keyword, BM25, semantic, and hybrid search modes. For simple pattern matching in individual files, use `all2md grep` instead.

## CLI Quick Reference

### Basic Search

```bash
# Keyword search across documents
all2md search "machine learning" ./papers/*.pdf

# Search a directory
all2md search "quarterly results" ./reports
```

### Search Modes

```bash
# Keyword search (default)
all2md search "query" ./documents --mode keyword

# BM25 ranking (better relevance scoring)
all2md search "quarterly results" ./reports --mode bm25

# Semantic search (meaning-based, not just keyword matching)
all2md search "how to configure authentication" ./docs --semantic

# Hybrid search (combines keyword + semantic)
all2md search "error handling" ./codebase --mode hybrid
```

### Result Control

```bash
# Limit number of results
all2md search "budget" ./finance --top-k 5

# Show context snippets around matches
all2md search "performance" ./reports --show-snippet
```

### Persistent Search Index

For repeated searches over the same documents, build a persistent index:

```bash
# Build and persist index (first search creates it)
all2md search "first query" ./documents --index-dir ./search-index

# Subsequent searches reuse the index (fast)
all2md search "second query" ./documents --index-dir ./search-index
all2md search "third query" ./documents --index-dir ./search-index
```

### Chunk Size Tuning

```bash
# Adjust chunk size for indexing (default: 500 tokens)
all2md search "query" ./docs --chunk-size 500

# Smaller chunks for more granular results
all2md search "query" ./docs --chunk-size 200

# Show progress during indexing
all2md search "query" ./large-collection --progress
```

### Output Formats

```bash
# Rich terminal output (default)
all2md search "query" ./docs --output rich

# Plain text
all2md search "query" ./docs --output plain

# JSON (for programmatic use)
all2md search "query" ./docs --output json
```

## Python API

```python
from all2md import to_markdown
from pathlib import Path

# Simple approach: convert then search in Python
for pdf_file in Path("./documents").glob("*.pdf"):
    text = to_markdown(pdf_file)
    if "search term" in text.lower():
        print(f"Found in: {pdf_file}")
```

## When to Use Search vs Grep

| Use case | Tool |
|----------|------|
| Find exact pattern in one file | `all2md grep` |
| Find pattern across a few files | `all2md grep` |
| Rank results by relevance | `all2md search` |
| Find semantically similar content | `all2md search --semantic` |
| Repeated searches over same docs | `all2md search --index-dir` |

## Tips

- `--mode bm25` gives better results than keyword for natural language queries
- `--semantic` requires the `search` extra: `pip install all2md[search]`
- Use `--index-dir` to avoid re-indexing when searching the same collection repeatedly
- Use `--output json` for structured results in scripts and pipelines
- Both search and grep work with any format all2md can read (40+ formats)

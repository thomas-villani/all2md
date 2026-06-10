# Advanced Document Search with all2md

## Contents
- [CLI Quick Reference](#cli-quick-reference) — search modes, result control, persistent index, chunk tuning, output formats
- [Python API](#python-api)
- [When to Use Search vs Grep](#when-to-use-search-vs-grep)
- [Tips](#tips)

## Overview

`all2md search` provides ranked search across document collections using keyword (BM25), vector (semantic), and hybrid search modes. For simple pattern matching in individual files, use `all2md grep` instead.

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
# Keyword search with BM25 ranking (default)
all2md search "quarterly results" ./reports --keyword

# Vector / semantic search (meaning-based, not just keyword matching)
all2md search "how to configure authentication" ./docs --vector

# Hybrid search (combines keyword + vector)
all2md search "error handling" ./codebase --hybrid

# Equivalent explicit form
all2md search "query" ./documents --mode keyword   # or --mode vector / --mode hybrid / --mode grep
```

### Result Control

```bash
# Limit number of results
all2md search "budget" ./finance --top-k 5

# Grep mode with surrounding context lines (-A/-B/-C)
all2md search "performance" ./reports --mode grep -C 2
```

### Persistent Search Index

For repeated searches over the same documents, build a persistent index:

```bash
# Build and persist index to disk (first search creates it)
all2md search "first query" ./documents --index-dir ./search-index --persist

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
# Plain text (default)
all2md search "query" ./docs

# Rich terminal output
all2md search "query" ./docs --rich

# JSON (for programmatic use)
all2md search "query" ./docs --json
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
| Find semantically similar content | `all2md search --vector` |
| Repeated searches over same docs | `all2md search --index-dir` |

## Tips

- `--keyword` uses BM25 ranking — a good default for natural language queries
- `--vector` (semantic) requires the `search` extra: `pip install all2md[search]`
- Use `--index-dir ... --persist` to avoid re-indexing when searching the same collection repeatedly
- Use `--json` for structured results in scripts and pipelines
- Both search and grep work with any format all2md can read (40+ formats)

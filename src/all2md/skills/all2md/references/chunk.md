# Chunk Documents with all2md

## Overview

`all2md chunk` splits any supported document into chunks for RAG / LLM pipelines and emits them as **JSONL** (one chunk per line) by default. Unlike flat-text chunkers, each chunk carries AST-derived **provenance** — its section heading/level and, where the format records it, the source page span — so downstream answers can cite where a passage came from.

## CLI Quick Reference

### Basic Usage

```bash
# Semantic chunks (section-bounded real-token windows) as JSONL
all2md chunk report.pdf --strategy semantic --max-tokens 512 --overlap 64

# One chunk per section, written to a file
all2md chunk handbook.docx --strategy section --out chunks.jsonl

# Read from stdin
cat page.html | all2md chunk - --strategy paragraph
```

### Strategies

Coarse — one chunk per semantic boundary:

```bash
all2md chunk doc.md --strategy heading   # split at H1
all2md chunk doc.md --strategy section   # one chunk per heading/section
all2md chunk doc.md --strategy auto      # pick a sensible boundary automatically
```

Fine — windowed within each section, up to `--max-tokens`:

```bash
all2md chunk doc.md --strategy semantic    # default: real-token windows
all2md chunk doc.md --strategy token       # split on token boundaries
all2md chunk doc.md --strategy sentence
all2md chunk doc.md --strategy paragraph
all2md chunk doc.md --strategy word
all2md chunk doc.md --strategy line
all2md chunk doc.md --strategy char
all2md chunk doc.md --strategy code        # respect function/class blocks
```

### Size & Structure Flags

```bash
# Bound chunk size and overlap (overlap is coerced to 0 for coarse strategies)
all2md chunk doc.md --max-tokens 256 --overlap 32 --min-tokens 20

# Limit how deep section detection descends
all2md chunk doc.md --max-heading-level 2

# Drop the pre-heading preamble; don't prepend the heading line to each chunk
all2md chunk doc.md --no-include-preamble --no-heading-merge
```

### Output Formats

```bash
all2md chunk doc.md                    # jsonl (default), one object per line
all2md chunk doc.md --format json      # a single JSON array
all2md chunk doc.md --format pretty     # human-readable listing
all2md chunk doc.md --out chunks.jsonl  # write to a file instead of stdout
```

### Tables, Images & Attachments

Chunks are built from each section's rendered Markdown, so tables/images/code blocks
show up as their Markdown form. Fine strategies split by token budget and can cut a
table mid-row — these flags control that:

```bash
# Keep each table or fenced code block whole (its own chunk; may exceed --max-tokens)
all2md chunk report.pdf --avoid-table-split --avoid-code-split

# Strip noisy node types before chunking (aliases images/tables/code accepted)
all2md chunk report.pdf --drop-elements image,table

# Long base64 data: URIs are elided to a placeholder by default; keep them raw with:
all2md chunk report.pdf --no-elide-data-uris

# Control how the converter handles images, e.g. avoid huge base64 blobs
all2md chunk report.pdf --attachment-mode skip   # skip | alt_text | save | base64
```

`all2md chunk` also reads converter settings from a config file (the same `[pdf]`,
`[html]`, and top-level keys as `all2md`/`view`/`serve`), with `--config`/`--no-config`.
`--attachment-mode` overrides the config value.

### Tokenizer

Real BPE token counting — and the `semantic`/`token`/`char` strategies that split *on* token boundaries — need `tiktoken`:

```bash
pip install all2md[chunk]
```

Count-only strategies (`sentence`/`word`/`line`/`paragraph`/`section`/`heading`/`auto`) fall back to a whitespace approximation when `tiktoken` is absent. Force a backend:

```bash
all2md chunk doc.md --strategy paragraph --token-counter whitespace
all2md chunk doc.md --strategy semantic  --token-counter tiktoken
```

## JSONL Schema

Each line is a flat object with these keys:

`chunk_id`, `index`, `text`, `token_count`, `token_counter`, `strategy`, `document_id`, `document_path`, `section_heading`, `section_level`, `section_index`, `page`, `page_end`, `source_line_start`, `source_line_end`, `char_start`, `char_end`, `char_basis`, `prev_chunk_id`, `next_chunk_id`.

Notes:
- `char_start`/`char_end` index into the chunk's rendered **section text** (`char_basis="section_text"`), not the original binary.
- `page`/`page_end` are populated only for formats that track pages (PDF and similar); otherwise `null`.
- `section_index` is `-1` for preamble / pre-heading content.
- `prev_chunk_id`/`next_chunk_id` chain chunks in reading order within a document.

## Python API

```python
from all2md import to_ast
from all2md.chunking import chunk_ast

doc = to_ast("report.pdf")
chunks = chunk_ast(
    doc,
    strategy="semantic",
    max_tokens=512,
    overlap=64,
    document_id="report",
    document_path="report.pdf",
)
for c in chunks:
    print(c.chunk_id, c.section_heading, c.page, c.token_count)
    # c.to_dict() gives the same flat object emitted as JSONL
```

## Tips

- `semantic` (the default) is the best general-purpose RAG strategy: it keeps chunks inside section boundaries and windows them by real tokens.
- Use `section`/`heading` when you want exactly one chunk per logical unit and don't need a hard token cap.
- Pass several inputs at once (`all2md chunk *.md`); `document_id` and `chunk_id` keep chunks from different files distinct.
- For building and querying a persistent index instead of raw chunks, see the `all2md-search` skill (`all2md search`).

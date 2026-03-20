---
name: all2md-read
description: "Use this skill when you need to read, extract text from, or parse a document file. Triggers: reading PDFs, Word docs, PowerPoint, Excel, HTML, emails, images, or any other document format; extracting text or tables; getting the markdown content of a file; parsing document structure. Use when the user says 'read this', 'what does this say', 'extract text', or provides a document file."
metadata:
  author: all2md
  version: "1.0"
---

# Reading Documents with all2md

## Overview

`all2md` reads any document and outputs clean Markdown. It supports 40+ input formats including PDF, DOCX, PPTX, HTML, XLSX, EML, images, notebooks, and 200+ programming languages.

## CLI Quick Reference

### Basic Usage

```bash
# Convert any document to Markdown (stdout)
all2md document.pdf
all2md report.docx
all2md slides.pptx
all2md page.html
all2md data.xlsx
all2md notebook.ipynb

# Save to file
all2md document.pdf -o document.md

# Read from stdin
cat document.pdf | all2md -

# Force input format when auto-detect fails
all2md ambiguous_file --format pdf
```

### PDF Options

```bash
# Specific pages
all2md document.pdf --pdf-pages "1-3,5,10-15"

# Table detection
all2md document.pdf --pdf-detect-tables

# OCR for scanned documents
all2md scanned.pdf --pdf-ocr-enabled --pdf-ocr-mode auto

# Combined
all2md document.pdf --pdf-pages "1-5" --pdf-detect-tables --pdf-ocr-enabled
```

### DOCX Options

```bash
# Preserve formatting hints
all2md report.docx --docx-preserve-formatting

# Extract comments and tracked changes
all2md report.docx --docx-extract-comments
```

### HTML Options

```bash
# Extract title as heading
all2md page.html --html-extract-title

# Download and save images
all2md page.html --attachment-mode save --attachment-output-dir ./images

# Embed images as base64
all2md page.html --attachment-mode base64
```

### Email Options

```bash
# Include attachment content
all2md message.eml --eml-include-attachments

# Detect email chains
all2md thread.eml --eml-detect-chains
```

### Excel and Notebooks

```bash
# Specific sheet
all2md data.xlsx --xlsx-sheet "Sheet2"

# Notebook with outputs
all2md notebook.ipynb --ipynb-include-outputs
```

### Section Extraction

```bash
# Extract by heading name
all2md document.pdf --extract "Introduction"

# Extract by heading index range
all2md document.pdf --extract "#:1-3"

# Show document outline / table of contents
all2md document.pdf --outline
```

### Batch Processing

```bash
# Convert entire directory recursively
all2md ./documents -r -o ./markdown

# Parallel processing
all2md ./documents -r --parallel 4 --output-dir ./converted

# Combine multiple files into one
all2md *.pdf --collate -o combined.md
```

## Python API

### Simple Conversion

```python
from all2md import to_markdown

# From file path
markdown = to_markdown("document.pdf")

# With options
markdown = to_markdown("document.pdf", pages="1-3", flavor="gfm")

# From bytes
markdown = to_markdown(pdf_bytes)

# From stdin
import sys
markdown = to_markdown(sys.stdin.buffer)
```

### AST Access

```python
from all2md import to_ast

# Parse to AST for programmatic access
doc = to_ast("document.pdf")

# Access document structure
for node in doc.children:
    print(node.type, node.text_content[:50])
```

### With Parser Options

```python
from all2md import to_markdown
from all2md.options.pdf import PdfOptions
from all2md.options.markdown import MarkdownRendererOptions

pdf_opts = PdfOptions(pages="1-5", detect_tables=True)
md_opts = MarkdownRendererOptions(flavor="gfm")

markdown = to_markdown(
    "document.pdf",
    parser_options=pdf_opts,
    renderer_options=md_opts,
)
```

### With Transforms

```python
from all2md import to_markdown

# Apply transforms during conversion
markdown = to_markdown(
    "document.pdf",
    transforms=["remove-images", "heading-offset"],
)
```

## Supported Input Formats

**Documents**: PDF, DOCX, PPTX, HTML, MHTML, EPUB, ODT, ODP, ODS, RTF
**Email**: EML, MBOX, MSG, PST, OST
**Data**: XLSX, CSV, TSV, JSON, YAML, TOML, INI
**Markup**: Markdown, reStructuredText, AsciiDoc, LaTeX, Org-Mode, MediaWiki, Textile
**Notebooks**: Jupyter (.ipynb)
**Code**: 200+ programming languages
**Other**: FB2, CHM, OpenAPI, ZIP/TAR/7Z archives

Run `all2md list-formats` to see all formats with dependency status.

## Tips

- Use `--verbose` or `--trace` for debugging conversion issues
- Use `all2md check-deps` to verify optional dependencies are installed
- Format-specific CLI flags follow the pattern `--<format>-<option>` (e.g., `--pdf-pages`, `--docx-preserve-formatting`)
- All CLI options support environment variables: `ALL2MD_<OPTION>` (e.g., `ALL2MD_PDF_OCR_ENABLED=true`)

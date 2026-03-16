---
name: all2md-convert
description: "Use this skill whenever you need to read, extract, or convert document content. Triggers: reading PDFs, Word docs, PowerPoint, Excel, HTML, emails, or 200+ other formats; converting documents to Markdown; converting Markdown to DOCX/HTML/PDF/PPTX; converting between any two supported formats; extracting text, tables, or sections from documents. If the user mentions a document file or asks you to produce one, use this skill."
metadata:
  author: all2md
  version: "1.0"
---

# Document Conversion with all2md

## Overview

`all2md` converts documents between 40+ formats using an AST-based pipeline. It works as both a CLI tool and a Python library. The core workflow is: **parse** any document into an AST, optionally **transform** it, then **render** to any output format.

## CLI Quick Reference

### Read Any Document (to Markdown)

```bash
# Basic conversion (outputs to stdout)
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

### Convert Between Formats

```bash
# Markdown to Word
all2md report.md --output-format docx -o report.docx

# Markdown to HTML
all2md report.md --output-format html -o report.html

# Markdown to PowerPoint
all2md slides.md --output-format pptx -o slides.pptx

# PDF to HTML (any-to-any via AST)
all2md document.pdf --output-format html -o document.html

# HTML to Word
all2md page.html --output-format docx -o page.docx
```

### Extract Sections

```bash
# By heading name
all2md document.pdf --extract "Introduction"

# By heading index range
all2md document.pdf --extract "#:1-3"

# Show document outline / table of contents
all2md document.pdf --outline
```

### Format-Specific Options

```bash
# PDF: specific pages, OCR, table detection
all2md document.pdf --pdf-pages "1-3,5" --pdf-detect-tables
all2md scanned.pdf --pdf-ocr-enabled --pdf-ocr-mode auto

# DOCX: preserve formatting, extract comments
all2md report.docx --docx-preserve-formatting --docx-extract-comments

# HTML: extract title, handle images
all2md page.html --html-extract-title
all2md page.html --attachment-mode save --attachment-output-dir ./images

# Email: include attachments
all2md message.eml --eml-include-attachments
```

### Batch Processing

```bash
# Convert entire directory
all2md ./documents -r -o ./markdown

# Parallel processing
all2md ./documents -r --parallel 4 --output-dir ./converted

# Split large document by headings
all2md large.pdf --split-by h1 --output-dir ./chapters

# Combine multiple files
all2md *.pdf --collate -o combined.md

# Watch for changes and auto-convert
all2md ./docs -r --watch --output-dir ./output
```

## Python API

### Simple Conversion

```python
from all2md import to_markdown

# File path
markdown = to_markdown("document.pdf")

# With options
markdown = to_markdown("document.pdf", pages="1-3", flavor="gfm")

# From bytes or file-like objects
markdown = to_markdown(pdf_bytes)

import sys
markdown = to_markdown(sys.stdin.buffer)
```

### Convert Between Formats

```python
from all2md import convert, from_markdown

# Any format to any format
convert("input.pdf", "output.docx", target_format="docx")
convert("input.html", "output.md")  # default target is markdown

# Markdown to other formats
from_markdown("report.md", "docx", output="report.docx")
from_markdown("slides.md", "pptx", output="slides.pptx")
from_markdown(markdown_string, "html", output="page.html")
```

### AST Manipulation

```python
from all2md import to_ast, from_ast

# Parse to AST for programmatic access
doc = to_ast("document.pdf")

# Render AST to any format
markdown = from_ast(doc, "markdown")
from_ast(doc, "docx", output="output.docx")
from_ast(doc, "html", output="output.html")
```

### With Parser/Renderer Options

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

### AST Transforms

```python
from all2md import to_markdown

# Apply transforms by name or instance
markdown = to_markdown(
    "document.pdf",
    transforms=[
        "remove-images",       # Strip images
        "heading-offset",      # Shift heading levels
        "normalize-whitespace",
    ],
)
```

## Supported Formats

### Input (Parsers)
**Documents**: PDF, DOCX, PPTX, HTML, MHTML, EPUB, ODT, ODP, ODS, RTF
**Email**: EML, MBOX, MSG, PST, OST
**Data**: XLSX, CSV, TSV, JSON, YAML, TOML, INI
**Markup**: Markdown, reStructuredText, AsciiDoc, LaTeX, Org-Mode, MediaWiki, Textile
**Notebooks**: Jupyter (.ipynb)
**Code**: 200+ programming languages
**Other**: FB2, EPUB, CHM, OpenAPI, ZIP/TAR/7Z archives

### Output (Renderers)
**Documents**: Markdown, HTML, DOCX, PPTX, EPUB, PDF
**Markup**: RST, AsciiDoc, Org-Mode, MediaWiki, Textile, LaTeX
**Data**: JSON, YAML, TOML, INI, CSV, PlainText

Run `all2md list-formats` to see all formats with dependency status.
Run `all2md list-formats <format>` for details on a specific format.

## Configuration

```bash
# Generate config template
all2md config generate > .all2md.toml

# Use config file
all2md document.pdf --config .all2md.toml

# Use presets
all2md document.pdf --preset quality    # Best output quality
all2md document.pdf --preset fast       # Speed optimized
all2md document.pdf --preset minimal    # Minimal dependencies
```

Config files are auto-discovered from `.all2md.toml` or `.all2md.json` in the current or home directory.

## Tips

- Use `--verbose` or `--trace` for debugging conversion issues
- Use `all2md check-deps` to verify optional dependencies are installed
- Use `all2md list-transforms` to see available AST transforms
- Format-specific CLI flags follow the pattern `--<format>-<option>` (e.g., `--pdf-pages`, `--docx-preserve-formatting`)
- All CLI options support environment variables: `ALL2MD_<OPTION>` (e.g., `ALL2MD_PDF_OCR_ENABLED=true`)

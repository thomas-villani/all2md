# Reading Documents with all2md

## Contents
- [CLI Quick Reference](#cli-quick-reference) — PDF, DOCX, HTML, email, Excel, and notebook options; section extraction; line-range navigation; batch processing
- [Python API](#python-api) — `to_markdown`, `to_ast`, parser/renderer options, transforms
- [Supported Input Formats](#supported-input-formats)
- [Tips](#tips)

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

# Table detection (on by default; pick the strategy)
all2md document.pdf --pdf-table-detection-mode both

# OCR for scanned documents
all2md scanned.pdf --pdf-ocr-enabled --pdf-ocr-mode auto

# Combined
all2md document.pdf --pdf-pages "1-5" --pdf-table-detection-mode both --pdf-ocr-enabled
```

### DOCX Options

```bash
# Include comments in the output
all2md report.docx --docx-include-comments

# Choose where comments appear (inline or as footnotes)
all2md report.docx --docx-include-comments --docx-comments-position inline
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
# Save attachments to a directory
all2md message.eml --eml-attachment-mode save --eml-attachment-output-dir ./attachments

# Keep the raw email headers in the output
all2md message.eml --eml-preserve-raw-headers
```

### Excel and Notebooks

```bash
# Specific sheet(s) — names or regex, comma-separated (default: all)
all2md data.xlsx --xlsx-sheets "Sheet2"

# Notebook without cell outputs (outputs are included by default)
all2md notebook.ipynb --ipynb-no-include-outputs
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

### Navigating by Line Number

When you don't want the whole document, map it first, then pull only the
range you need. Line numbers refer to the full Markdown conversion and are
consistent across all three commands below.

```bash
# 1. Outline annotated with the line each heading sits on
all2md document.pdf --outline --line-numbers      # or -ln

# 2. Pull an exact line range (1-based, inclusive)
all2md document.pdf --extract line:42-87

# 3. Same range, keeping the original line numbers for further refinement
all2md document.pdf --extract line:42-87 --line-numbers

# Number every line of a full conversion (cat -n style)
all2md document.pdf --line-numbers
```

`line:` ranges accept a single line (`line:42`), a closed range (`line:42-87`),
an open-ended range (`line:42-`), or several (`line:1-10,42-87`). This is the
most token-efficient way to read just the relevant part of a large document.

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

pdf_opts = PdfOptions(pages="1-5", table_detection_mode="both")
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
- Format-specific CLI flags follow the pattern `--<format>-<option>` (e.g., `--pdf-pages`, `--docx-include-comments`)
- All CLI options support environment variables: `ALL2MD_<OPTION>` (e.g., `ALL2MD_PDF_OCR_ENABLED=true`)

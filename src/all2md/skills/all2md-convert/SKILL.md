---
name: all2md-convert
description: "Use this skill when you need to convert a document from one format to another (not just reading to markdown). Triggers: converting PDF to Word, HTML to DOCX, DOCX to PDF, any-to-any format conversion, changing file formats, reformatting documents. Use when the user says 'convert to', 'change format', 'save as', or needs a document in a different format."
metadata:
  author: all2md
  version: "1.0"
---

# Format Conversion with all2md

## Overview

`all2md` converts between 40+ document formats using an AST-based pipeline. Any input format can be converted to any output format: parse → (optional transform) → render.

## CLI Quick Reference

### Common Conversions

```bash
# PDF to Word
all2md document.pdf --output-format docx -o document.docx

# HTML to Word
all2md page.html --output-format docx -o page.docx

# Word to PDF
all2md report.docx --output-format pdf -o report.pdf

# Word to HTML
all2md report.docx --output-format html -o report.html

# Markdown to Word
all2md report.md --output-format docx -o report.docx

# Markdown to HTML
all2md report.md --output-format html -o report.html

# Markdown to PowerPoint
all2md slides.md --output-format pptx -o slides.pptx

# Any-to-any via AST
all2md input.epub --output-format rst -o output.rst
```

### Output Format Options

```bash
# HTML output options
all2md doc.pdf --output-format html --html-standalone -o doc.html

# DOCX output options
all2md doc.md --output-format docx --docx-template custom.docx -o doc.docx

# PDF output options
all2md doc.md --output-format pdf --pdf-page-size letter -o doc.pdf
```

### AST Transforms During Conversion

```bash
# Remove images during conversion
all2md doc.pdf --output-format docx --transform remove-images -o doc.docx

# Shift heading levels
all2md doc.html --output-format md --transform heading-offset -o doc.md

# Chain multiple transforms
all2md doc.pdf --output-format html --transform remove-images --transform heading-offset -o doc.html
```

### List Available Formats and Transforms

```bash
# See all supported formats with dependency status
all2md list-formats

# Details for a specific format
all2md list-formats pdf

# See all available AST transforms
all2md list-transforms
```

## Python API

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

### AST Pipeline

```python
from all2md import to_ast, from_ast

# Parse to AST
doc = to_ast("document.pdf")

# Apply transforms
from all2md.transforms import apply_transforms
doc = apply_transforms(doc, ["remove-images", "heading-offset"])

# Render to any format
from_ast(doc, "docx", output="output.docx")
from_ast(doc, "html", output="output.html")
from_ast(doc, "markdown", output="output.md")
```

### With Options

```python
from all2md import convert
from all2md.options.pdf import PdfOptions
from all2md.options.docx_render import DocxRendererOptions

convert(
    "input.pdf",
    "output.docx",
    target_format="docx",
    parser_options=PdfOptions(pages="1-5", detect_tables=True),
    renderer_options=DocxRendererOptions(),
)
```

## Supported Output Formats

**Documents**: Markdown, HTML, DOCX, PPTX, EPUB, PDF
**Markup**: RST, AsciiDoc, Org-Mode, MediaWiki, Textile, LaTeX
**Data**: JSON, YAML, TOML, INI, CSV, PlainText

Run `all2md list-formats` to see all formats with dependency status.

## Tips

- Use `all2md list-formats` to check which optional dependencies are installed
- Format-specific output options follow the pattern `--<format>-<option>`
- The AST pipeline means any input can go to any output — you're not limited to predefined pairs
- Use `--verbose` to see the parse → transform → render pipeline steps

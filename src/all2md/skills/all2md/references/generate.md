# Generating Documents with all2md

## Contents
- [CLI Quick Reference](#cli-quick-reference) — DOCX, PDF, PPTX, EPUB, HTML, templates, static sites, ArXiv, batch
- [Python API](#python-api) — `from_markdown`, renderer options, AST pipeline, ArXiv packaging
- [Tips](#tips)

## Overview

`all2md` creates polished documents from Markdown content — Word reports, PDF deliverables, PowerPoint slides, EPUB ebooks, static sites, and ArXiv submissions. Write in Markdown, render to any output format.

## CLI Quick Reference

### Generate Documents from Markdown

```bash
# Markdown to Word document
all2md report.md --output-format docx -o report.docx

# Markdown to PDF
all2md report.md --output-format pdf -o report.pdf

# Markdown to HTML (standalone page is the default)
all2md report.md --output-format html -o report.html

# Markdown to PowerPoint slides
all2md slides.md --output-format pptx -o presentation.pptx

# Markdown to EPUB
all2md book.md --output-format epub -o book.epub

# Markdown to LaTeX
all2md paper.md --output-format latex -o paper.tex

# Markdown to reStructuredText
all2md docs.md --output-format rst -o docs.rst
```

### DOCX Generation Options

```bash
# Use a custom template
all2md report.md --output-format docx --docx-renderer-template-path company.docx -o report.docx
```

### PDF Generation Options

```bash
# Page size
all2md report.md --output-format pdf --pdf-renderer-page-size letter -o report.pdf
all2md report.md --output-format pdf --pdf-renderer-page-size a4 -o report.pdf
```

### PPTX Generation Options

```bash
# Generate slides (headings become slide titles)
all2md slides.md --output-format pptx -o presentation.pptx
```

### EPUB Generation Options

```bash
# Generate ebook
all2md book.md --output-format epub -o book.epub
```

### HTML Standalone Pages

```bash
# Self-contained HTML with embedded styles (standalone is the default)
all2md report.md --output-format html -o report.html

# Emit only the content fragment instead of a full page
all2md report.md --output-format html --html-renderer-no-standalone -o fragment.html
```

### Template Rendering

```bash
# Render with Jinja2 template
all2md data.md --output-format jinja --jinja-renderer-template-file template.html -o output.html
```

### Static Site Generation

```bash
# Generate a documentation site (Hugo)
all2md generate-site ./docs --output-dir site --generator hugo

# Generate a Jekyll site instead
all2md generate-site ./docs --output-dir site --generator jekyll
```

### ArXiv Packaging

```bash
# Create ArXiv-ready LaTeX submission
all2md arxiv paper.md -o submission.tar.gz

# With bibliography
all2md arxiv paper.md -o submission.tar.gz --bib references.bib

# With options
all2md arxiv paper.md -o submission.tar.gz --document-class article --figure-format pdf
```

### Batch Generation

```bash
# Convert all Markdown files in a directory
all2md ./docs -r --output-format html --output-dir ./site

# Parallel generation
all2md ./chapters -r --output-format docx --parallel 4 --output-dir ./word-docs
```

## Python API

### Generate from Markdown

```python
from all2md import from_markdown

# Markdown file to Word
from_markdown("report.md", "docx", output="report.docx")

# Markdown string to HTML
html = from_markdown(markdown_text, "html")

# Markdown to PowerPoint
from_markdown("slides.md", "pptx", output="slides.pptx")

# Markdown to PDF
from_markdown("report.md", "pdf", output="report.pdf")
```

### With Renderer Options

```python
from all2md import from_markdown
from all2md.options.docx_render import DocxRendererOptions

opts = DocxRendererOptions()
from_markdown("report.md", "docx", output="report.docx", renderer_options=opts)
```

### AST Pipeline

```python
from all2md import to_ast, from_ast

# Parse Markdown to AST
doc = to_ast("content.md")

# Apply transforms
from all2md.transforms import apply
doc = apply(doc, ["heading-offset", "add-heading-ids"])

# Render to target format
from_ast(doc, "docx", output="output.docx")
from_ast(doc, "pdf", output="output.pdf")
from_ast(doc, "epub", output="output.epub")
```

### ArXiv Packaging

```python
from all2md import to_ast
from all2md.options.arxiv import ArxivPackagerOptions
from all2md.packagers.arxiv import ArxivPackager

doc = to_ast("paper.md")
options = ArxivPackagerOptions(document_class="article", figure_format="pdf")
packager = ArxivPackager(options=options)
result = packager.package(doc, "submission.tar.gz", bib_file="references.bib")
```

## Tips

- Use Markdown headings to structure slides (each `# Heading` becomes a new slide in PPTX)
- HTML output is a self-contained, offline-ready page by default; pass `--html-renderer-no-standalone` for just the content fragment
- The ArXiv packager automatically extracts figures and generates proper LaTeX
- Use `all2md list-formats` to check which output renderers are available
- Use `all2md check-deps` to verify dependencies for your target format

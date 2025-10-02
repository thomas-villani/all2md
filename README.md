# all2md

[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://badge.fury.io/py/all2md.svg)](https://badge.fury.io/py/all2md)

A Python document conversion library for rapid, lightweight transformation of various document formats to Markdown. Designed specifically for LLMs and document processing pipelines.

## Features

 **Rapid Conversion** - Lightweight and fast document processing

- **Smart Detection** - Automatic format detection from content and filenames
- **Multiple Formats** - Support for 15+ document formats plus 200+ text formats
- **Highly Configurable** - Extensive options for customizing Markdown output
- **Image Handling** - Download, embed as base64, or skip images entirely
- **CLI & API** - Use from command line or integrate into Python applications
- **Modular Design** - Optional dependencies per format to keep installs lightweight

## Supported Formats

### Documents
- **PDF** - Advanced parsing with table detection using PyMuPDF
- **Word (DOCX)** - Full formatting preservation including tables and images
- **PowerPoint (PPTX)** - Slide-by-slide extraction with notes and content
- **HTML/MHTML** - Web content with configurable element handling
- **Email (EML)** - Email parsing with attachment support and chain detection
- **EPUB** - E-book chapter extraction with metadata
- **RTF** - Rich Text Format with styling preservation
- **OpenDocument (ODT/ODP)** - LibreOffice/OpenOffice documents

### Data & Other
- **Excel (XLSX)** - Spreadsheets converted to Markdown tables
- **CSV/TSV** - Tabular data with proper table formatting
- **Jupyter Notebooks (IPYNB)** - Code cells, outputs, and markdown cells
- **Images (PNG/JPEG/GIF)** - Embedded as base64 or downloaded
- **200+ text formats** - Source code, configs, markup files, and more

## Quick Start

### Installation

```bash
# Basic installation
pip install all2md

# Install with all format support
pip install all2md[all]

# Install specific formats only
pip install all2md[pdf,docx,html]
```

### Command Line Usage

```bash
# Convert any document to markdown
all2md document.pdf

# Save output to file
all2md document.docx --out output.md

# Download images to a directory
all2md document.html --attachment-mode download --attachment-output-dir ./images

# Convert with custom formatting
all2md document.pdf --emphasis-symbol "_" --bullet-symbols "",,"

# Apply AST transforms
all2md document.pdf --transform remove-images

# Multiple transforms (order matters)
all2md document.pdf --transform heading-offset --transform remove-images

# List available transforms
all2md list-transforms
```

### Python API

```python
from all2md import to_markdown

# Simple conversion
markdown = to_markdown('document.pdf')
print(markdown)

# With options
from all2md import to_markdown, PdfOptions

options = PdfOptions(
    pages=[0, 1, 2],  # First 3 pages only
    attachment_mode='download',
    attachment_output_dir='./images'
)
markdown = to_markdown('document.pdf', options=options)

# From file object
with open('document.docx', 'rb') as f:
    markdown = to_markdown(f, format='docx')

# With AST transforms
from all2md.transforms import RemoveImagesTransform, HeadingOffsetTransform

markdown = to_markdown(
    'document.pdf',
    transforms=[
        RemoveImagesTransform(),
        HeadingOffsetTransform(offset=1)
    ]
)
```

## Documentation

- **[Full Documentation](https://all2md.readthedocs.io/)** - Complete guide and API reference
- **[Quick Start Guide](https://all2md.readthedocs.io/en/latest/quickstart.html)** - Get up and running in 5 minutes
- **[AST Transforms Guide](https://all2md.readthedocs.io/en/latest/transforms.html)** - Create custom document transforms
- **[Configuration Options](https://all2md.readthedocs.io/en/latest/options.html)** - Detailed options for each format
- **[Troubleshooting](https://all2md.readthedocs.io/en/latest/troubleshooting.html)** - Common issues and solutions

## Installation Options

### Basic Installation
```bash
pip install all2md
```
Includes support for: HTML, CSV/TSV, text files, images

### Format-Specific Installation
```bash
# PDF support
pip install all2md[pdf]

# Word documents
pip install all2md[docx]

# PowerPoint presentations
pip install all2md[pptx]

# Email files
pip install all2md[eml]

# EPUB e-books
pip install all2md[epub]

# OpenDocument formats
pip install all2md[odf]

# RTF documents
pip install all2md[rtf]

# All formats
pip install all2md[all]
```

### Development Installation
```bash
git clone https://github.com/thomas.villani/all2md.git
cd all2md
pip install -e .[dev,all]
```

## Examples

### PDF Processing with Table Detection
```python
from all2md import to_markdown, PdfOptions

# Advanced PDF processing
options = PdfOptions(
    pages=[0, 1, 2],  # Process first 3 pages
    table_detection=True,  # Enable table detection
    include_page_numbers=True,  # Add page numbers
    attachment_mode='base64'  # Embed images as base64
)

markdown = to_markdown('report.pdf', options=options)
```

### Word Document with Custom Formatting
```python
from all2md import to_markdown, DocxOptions, MarkdownOptions

# Custom markdown formatting
md_options = MarkdownOptions(
    emphasis_symbol='_',  # Use underscores for emphasis
    bullet_symbols=['"', '', ''],  # Custom bullet points
    use_hash_headings=True  # Use # headings instead of underlines
)

options = DocxOptions(
    markdown_options=md_options,
    attachment_mode='download',
    attachment_output_dir='./doc_images'
)

markdown = to_markdown('document.docx', options=options)
```

### Batch Processing
```python
import os
from all2md import to_markdown

# Process all PDFs in a directory
pdf_dir = './documents'
output_dir = './markdown_output'

for filename in os.listdir(pdf_dir):
    if filename.endswith('.pdf'):
        input_path = os.path.join(pdf_dir, filename)
        output_path = os.path.join(output_dir, f"{filename}.md")

        markdown = to_markdown(input_path)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown)

        print(f"Converted {filename} -> {output_path}")
```

### AST Transforms
```python
from all2md import to_markdown
from all2md.transforms import (
    RemoveImagesTransform,
    HeadingOffsetTransform,
    AddHeadingIdsTransform,
    RemoveBoilerplateTextTransform
)

# Apply multiple transforms to clean up a document
transforms = [
    RemoveBoilerplateTextTransform(),  # Remove common boilerplate
    RemoveImagesTransform(),  # Strip all images
    HeadingOffsetTransform(offset=1),  # Shift headings down one level
    AddHeadingIdsTransform(id_prefix='doc-')  # Add IDs for anchors
]

markdown = to_markdown('report.pdf', transforms=transforms)

# Create custom transforms
from all2md.ast.transforms import NodeTransformer
from all2md.ast import Link

class LinkRewriterTransform(NodeTransformer):
    """Rewrite internal links to external URLs."""

    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url

    def visit_link(self, node: Link) -> Link:
        node = super().visit_link(node)
        if node.url.startswith('/docs/'):
            return Link(
                url=self.base_url + node.url,
                content=node.content,
                title=node.title,
                metadata=node.metadata
            )
        return node

# Use custom transform
markdown = to_markdown(
    'document.html',
    transforms=[LinkRewriterTransform('https://example.com')]
)
```

## Requirements

- **Python 3.12+**
- Format-specific dependencies are installed automatically with optional extras
- See [Installation Guide](https://all2md.readthedocs.io/en/latest/installation.html) for details

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details on:

- Setting up the development environment
- Running tests and quality checks
- Submitting pull requests
- Reporting issues

### Development Setup
```bash
# Clone repository
git clone https://github.com/thomas.villani/all2md.git
cd all2md

# Install in development mode
pip install -e .[dev,all]

# Run tests
pytest

# Run linting and type checking
ruff check src/
mypy src/
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

**Thomas Villani, Ph.D.**
- Email: thomas.villani@gmail.com
- GitHub: [@thomas.villani](https://github.com/thomas.villani)

## Acknowledgments

- Built on top of excellent libraries like PyMuPDF, python-docx, BeautifulSoup4, and many others
- Inspired by the need for fast, reliable document conversion for LLM workflows
- Thanks to the Python community for the fantastic ecosystem of document processing tools

---

**all2md** - Making document conversion simple, fast, and reliable for modern workflows.
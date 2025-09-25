# all2md

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Documentation](https://img.shields.io/badge/docs-available-brightgreen.svg)](https://all2md.readthedocs.io/)

**all2md** is a comprehensive Python library for bidirectional document conversion between various file formats and Markdown. It provides intelligent content extraction and formatting preservation for PDF, Word, PowerPoint, HTML, email, Excel, images, and 200+ text file formats.

## Features

### **Bidirectional Conversion**
- **Format-to-Markdown**: Convert documents to clean, structured Markdown
- **Markdown-to-Format**: Generate professional documents from Markdown

### **Comprehensive Format Support**
- **Documents**: PDF, DOCX, PPTX, HTML, EML
- **Spreadsheets**: XLSX, CSV, TSV
- **Images**: PNG, JPEG, GIF (embedded as base64)
- **Text Files**: 200+ formats including source code, configs, markup

### **Intelligent Processing**
- Advanced PDF parsing with table detection using PyMuPDF
- Word document processing with formatting preservation
- PowerPoint slide-by-slide extraction
- Email chain parsing with thread reconstruction
- HTML processing with configurable conversion options

### <� **Key Capabilities**
- Table structure preservation with Markdown table syntax
- Image embedding as base64 data URIs
- Text formatting preservation (bold, italic, lists, headers)
- Automatic file type detection and routing
- Robust error handling for malformed content

## Installation

### Requirements
- **Python 3.12+**
- Optional dependencies are installed automatically per format

### Install from PyPI
```bash
pip install all2md
```

### Install for Development
```bash
git clone https://github.com/username/all2md.git
cd all2md
pip install -e .
```

## Quick Start

### Basic Usage

```python
from all2md import parse_file

# Convert any supported file to Markdown
with open('document.pdf', 'rb') as f:
    markdown_content = parse_file(f, 'document.pdf')
    print(markdown_content)
```

### With MIME Type Detection

```python
content, mimetype = parse_file(file_obj, filename, return_mimetype=True)
print(f"Detected type: {mimetype}")
print(content)
```

### Format-Specific Examples

#### PDF to Markdown

```python
from all2md.converters.pdf2markdown import pdf_to_markdown
from io import BytesIO

with open('report.pdf', 'rb') as f:
    filestream = BytesIO(f.read())
    markdown = pdf_to_markdown(filestream)
    print(markdown)
```

#### Word Document to Markdown

```python
from all2md.converters.docx2markdown import docx_to_markdown

with open('document.docx', 'rb') as f:
    markdown = docx_to_markdown(f, convert_images_to_base64=True)
    print(markdown)
```

#### Email Chain Processing

```python
from all2md.converters.eml2markdown import eml_to_markdown

# Get structured data
messages = eml_to_markdown('conversation.eml')
for msg in messages:
    print(f"From: {msg['from']}")
    print(f"Subject: {msg['subject']}")
    print(f"Date: {msg['date']}")

# Get Markdown format
markdown = eml_to_markdown('conversation.eml', as_markdown=True)
print(markdown)
```

#### PowerPoint to Markdown

```python
from all2md.converters.pptx2markdown import pptx_to_markdown

with open('presentation.pptx', 'rb') as f:
    markdown = pptx_to_markdown(f)
    print(markdown)
```

#### HTML to Markdown

```python
from all2md.converters.html2markdown import HTMLToMarkdown

converter = HTMLToMarkdown(
    hash_headings=True,
    emphasis_symbol="*",
    bullet_symbols="*-+"
)

html = '<h1>Title</h1><p>Content with <strong>bold</strong> text.</p>'
markdown = converter.convert(html)
print(markdown)
```

### Reverse Conversion (Markdown to Format)

#### Markdown to Word Document

```python
from all2md.markdown2docx import markdown_to_docx

markdown_text = """
# My Document

This is **bold** text with a [link](https://example.com).

## Table Example

| Name | Value |
|------|-------|
| Item | 123   |
"""

doc = markdown_to_docx(markdown_text)
doc.save('output.docx')
```

#### PDF to Images

```python
from all2md.pdf2image import pdf_to_images

# Convert to image list
images = pdf_to_images('document.pdf', fmt='png', zoom=2.0)

# Get base64 encoded for web use
images_b64 = pdf_to_images('document.pdf', as_base64=True)
```

## Supported File Types

| Category | Formats | Extensions |
|----------|---------|------------|
| **Documents** | PDF, Word, PowerPoint, HTML, Email | `.pdf`, `.docx`, `.pptx`, `.html`, `.eml` |
| **Spreadsheets** | Excel, CSV, TSV | `.xlsx`, `.csv`, `.tsv` |
| **Images** | PNG, JPEG, GIF | `.png`, `.jpg`, `.jpeg`, `.gif` |
| **Text** | 200+ formats | `.txt`, `.md`, `.json`, `.xml`, `.py`, `.js`, etc. |

### Programming Languages Supported
Python, JavaScript, Java, C/C++, C#, Go, Rust, Ruby, PHP, Swift, Kotlin, TypeScript, and many more.

## API Reference

### Core Functions

#### `parse_file(file, filename, return_mimetype=False)`
Main entry point for file conversion.

**Parameters:**
- `file` (IO): File-like object to parse
- `filename` (str): Filename for MIME type detection
- `return_mimetype` (bool): Return MIME type with content

**Returns:**
- `str`: Markdown content, or `tuple[str, str]` if `return_mimetype=True`

### Module-Specific Functions

- **`pdf2markdown.pdf_to_markdown(doc, pages=None)`** - Advanced PDF conversion
- **`docx2markdown.docx_to_markdown(docx_file, convert_images_to_base64=False)`** - Word conversion
- **`pptx2markdown.pptx_to_markdown(pptx_file)`** - PowerPoint conversion
- **`emlfile.parse_email_chain(eml_file, as_markdown=False)`** - Email processing
- **`html2markdown.HTMLToMarkdown.convert(html)`** - HTML conversion
- **`pdf2image.pdf_to_images(pdf_file, **options)`** - PDF to image conversion

## Configuration

### HTML Converter Options
```python
converter = HTMLToMarkdown(
    hash_headings=True,        # Use # headers vs underline style
    extract_title=False,       # Extract <title> from HTML
    emphasis_symbol="*",       # * or _ for emphasis
    bullet_symbols="*-+",      # Bullet characters to cycle
    remove_images=False        # Strip images from output
)
```

### PDF Processing Options
```python
# Page range selection
markdown = pdf_to_markdown(doc, pages=[0, 1, 2])  # First 3 pages

# Image conversion options
images = pdf_to_images(
    pdf_file,
    zoom=2.0,              # Resolution multiplier
    fmt='jpeg',            # 'jpeg' or 'png'
    first_page=1,          # Start page (1-indexed)
    last_page=5,           # End page
    as_base64=True         # Return base64 strings
)
```

## Development

### Setup Development Environment
```bash
git clone https://github.com/username/all2md.git
cd all2md
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .[dev]
```

### Code Quality Tools
```bash
# Linting and formatting
ruff check src/
ruff format src/

# Type checking
mypy src/

# Using virtual environment commands
.venv/Scripts/python.exe -m ruff check
.venv/Scripts/python.exe -m mypy src/
```

### Running Tests
```bash
pytest tests/
```

## Dependencies

### Core Dependencies
- **PyMuPDF (e1.26.4)** - PDF processing and table detection
- **python-docx (e1.2.0)** - Word document handling
- **python-pptx (e1.0.2)** - PowerPoint processing
- **beautifulsoup4 (e4.13.5)** - HTML parsing
- **pandas (e2.3.2)** - Spreadsheet processing

### Optional Dependencies
Dependencies are automatically installed when needed for specific formats.

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Areas for Contribution
- Additional file format support
- Performance optimizations
- Test coverage improvements
- Documentation enhancements
- Bug fixes and feature requests

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and updates.

## Support

- **Documentation**: [Read the Docs](https://all2md.readthedocs.io/)
- **Issues**: [GitHub Issues](https://github.com/username/all2md/issues)
- **Discussions**: [GitHub Discussions](https://github.com/username/all2md/discussions)

---

**all2md** - Making document conversion simple and reliable.
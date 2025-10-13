# `all2md`: The Universal Document Conversion Library

[![PyPI version](https://img.shields.io/pypi/v/all2md.svg)](https://pypi.org/project/all2md/)
[![Build Status](https://img.shields.io/travis/com/thomas.villani/all2md.svg)](https://travis-ci.com/thomas.villani/all2md)
[![Code Coverage](https://img.shields.io/codecov/c/github/thomas.villani/all2md.svg)](https://codecov.io/gh/thomas.villani/all2md)
[![License](https://img.shields.io/pypi/l/all2md.svg)](https://opensource.org/licenses/MIT)
[![Python Versions](https://img.shields.io/pypi/pyversions/all2md.svg)](https://pypi.org/project/all2md/)

**Rapid, lightweight conversion of various document formats to and from markdown for LLMs.**

`all2md` provides a unified, extensible framework for converting diverse document formats into clean, consistent Markdown. It's designed to be the bridge between complex binary files (like `.docx`, `.pdf`, `.pptx`) and the plain-text world of Large Language Models (LLMs), enabling seamless ingestion and generation of documents.

## The Problem

LLMs excel at processing and generating structured text, with Markdown being a near-perfect format. However, most human-created documents are stored in formats like Microsoft Word, PDF, or PowerPoint. Feeding these directly to an LLM is often inefficient or impossible. Existing converters can be inconsistent, producing messy or hard-to-parse output.

## The Solution

`all2md` solves this by providing a robust, two-way conversion pipeline.

1.  **Ingestion:** Convert any supported document into a clean, standardized Markdown representation.
2.  **Transformation:** Programmatically clean, modify, or analyze the content *before* it reaches the LLM using a powerful transform pipeline.
3.  **Generation:** Convert LLM-generated Markdown *back* into rich document formats like `.docx` or `.pdf`.

This approach makes Markdown the universal intermediate format, simplifying document processing workflows for AI applications.

## Key Features

-   **Comprehensive Format Support**: Convert between dozens of formats, including PDF, DOCX, PPTX, HTML, EML, EPUB, XLSX, IPYNB, RST, Org-Mode, ZIP archives, and over 200 source code languages.
-   **Bidirectional Conversion**: Not just to Markdown! Convert from Markdown to formats like DOCX, PDF, and HTML.
-   **AST-Based Pipeline**: At its core, `all2md` uses an Abstract Syntax Tree (AST) to represent documents, enabling powerful and consistent manipulation across all formats.
-   **Advanced PDF Parsing**: Intelligent table detection, multi-column layout analysis, header/footer removal, and robust text extraction powered by PyMuPDF.
-   **Extensible Plugin System**: Easily add support for new file formats (converters) or create custom document manipulations (transforms) using a simple entry-point system.
-   **Powerful CLI**: A full-featured command-line interface with multi-file processing, parallel execution, directory watching, stdin/stdout piping, and dynamic, format-specific options.
-   **Highly Configurable**: Fine-tune every aspect of the conversion process using clean, type-safe `dataclass` options for each format.
-   **Security-Conscious**: Built-in protections against Server-Side Request Forgery (SSRF) when fetching remote resources and security validation for archives like ZIP, DOCX, and EPUB.
-   **Smart Dependency Management**: Core library is dependency-free. Install support for formats only as you need them.

## Supported Formats

`all2md` uses a modular system where dependencies are only required for the formats you need to process.

| Format                        | File Extensions                               | Input (Parse) | Output (Render) | Dependencies Extra |
| ----------------------------- | --------------------------------------------- | :-----------: | :-------------: | ------------------ |
| **PDF**                       | `.pdf`                                        |       ✅       |        ✅      | `pdf`, `pdf_render`|
| **Word Document**             | `.docx`                                       |       ✅       |        ✅      | `docx`             |
| **PowerPoint Presentation**   | `.pptx`                                       |       ✅       |        ✅      | `pptx`             |
| **HTML**                      | `.html`, `.htm`                               |       ✅       |        ✅      | `html`             |
| **MHTML Web Archive**         | `.mhtml`, `.mht`                              |       ✅       |       (N/A)    | `html`             |
| **Email Message**             | `.eml`, `.msg`                                |       ✅       |       (N/A)    | (built-in)         |
| **Jupyter Notebook**          | `.ipynb`                                      |       ✅       |       (N/A)    | (built-in)         |
| **EPUB E-book**               | `.epub`                                       |       ✅       |        ✅      | `epub`             |
| **OpenDocument Text**         | `.odt`                                        |       ✅       |       (N/A)    | `odf`              |
| **OpenDocument Presentation** | `.odp`                                        |       ✅       |       (N/A)    | `odf`              |
| **Excel Spreadsheet**         | `.xlsx`                                       |       ✅       |       (N/A)    | `spreadsheet`      |
| **CSV / TSV**                 | `.csv`, `.tsv`                                |       ✅       |       (N/A)    | (built-in)         |
| **Rich Text Format**          | `.rtf`                                        |       ✅       |       (N/A)    | `rtf`              |
| **reStructuredText**          | `.rst`                                        |       ✅       |        ✅      | `markdown`         |
| **Org-Mode**                  | `.org`                                        |       ✅       |        ✅      | `org`              |
| **Source Code**               | 200+ extensions (`.py`, `.js`, etc.)          |       ✅       |       (N/A)    | (built-in)         |
| **ZIP Archive**               | `.zip`                                        |       ✅       |       (N/A)    | (built-in)         |

## Installation

The core library has no dependencies. You can install it and add support for formats as needed.

**1. Basic Installation**

```bash
pip install all2md
```

**2. Installation with Extras**

Install support for only the formats you need. You can combine multiple extras.

```bash
# Install support for PDF, DOCX, and HTML
pip install "all2md[pdf,docx,html]"

# Install support for spreadsheets and ODF documents
pip install "all2md[spreadsheet,odf]"
```

**3. Full Installation**

To install all optional dependencies for all supported formats:

```bash
pip install "all2md[all]"
```

**4. Check Dependencies**

You can check the status of optional dependencies at any time using the built-in CLI command:

```bash
all2md check-deps
```

## Command-Line Usage

`all2md` provides a powerful command-line interface for quick conversions and scripting.

**Basic Conversion**

```bash
# Convert a PDF and print to stdout
all2md document.pdf

# Convert a Word document to a file
all2md report.docx -o report.md
```

**Multi-File and Directory Processing**

```bash
# Convert all DOCX files in a directory to an output folder
all2md ./reports/*.docx --output-dir ./markdown_reports

# Recursively convert an entire directory
all2md ./source_docs --recursive --output-dir ./converted_docs

# Preserve the source directory structure in the output
all2md ./source_docs -r -o ./converted_docs --preserve-structure
```

**Advanced Processing**

```bash
# Process files in parallel using 4 worker processes
all2md ./large_docs -r -o ./output -p 4

# Watch a directory for changes and convert automatically
all2md ./watched_folder -r -o ./output --watch

# Pipe content from stdin
cat report.html | all2md - > report.md
curl https://example.com | all2md - --format html > example.md
```

**Format-Specific Options**

All conversion options are available as CLI flags. Use `--help` to see them all.

```bash
# Convert only pages 1-3 and 5 from a PDF
all2md report.pdf --pdf-pages "1-3,5"

# Convert an HTML file, extracting the <title> as the main heading
all2md page.html --html-extract-title

# Convert a DOCX and download images to a folder
all2md document.docx --attachment-mode download --attachment-output-dir ./images
```

**Using Transforms**

Apply AST transforms directly from the CLI.

```bash
# Remove all images from a document
all2md report.docx -t remove-images

# Offset all heading levels (e.g., H1 -> H2, H2 -> H3)
all2md chapter.docx -t "heading-offset --offset 1"

# List all available transforms
all2md list-transforms
```

## Python API Usage

Integrate `all2md` directly into your Python applications for programmatic control.

**Simple Conversion**

The `to_markdown()` function is the easiest way to get started.

```python
from all2md import to_markdown

# Convert a file to Markdown
markdown_content = to_markdown('document.pdf')
print(markdown_content)
```

**Using Configuration Options**

Fine-tune the conversion by passing `Options` objects or keyword arguments.

```python
from all2md import to_markdown, PdfOptions, MarkdownOptions

# Use an options object for type safety and clarity
pdf_opts = PdfOptions(pages="1-3,5", attachment_mode="base64")
md_opts = MarkdownOptions(flavor="gfm", emphasis_symbol="_")

markdown_content = to_markdown(
    'report.pdf',
    parser_options=pdf_opts,
    renderer_options=md_opts
)

# Alternatively, pass options as keyword arguments
markdown_content = to_markdown(
    'report.pdf',
    pages="1-3,5",          # PdfOptions
    attachment_mode="base64", # BaseParserOptions
    flavor="gfm",             # MarkdownOptions
    emphasis_symbol="_"       # MarkdownOptions
)
```

**Bidirectional Conversion**

Use the `convert()` function for conversions between any two supported formats.

```python
from all2md import convert

# Convert Markdown to DOCX
convert("input.md", "output.docx", target_format="docx")

# Convert HTML to PDF
convert("page.html", "page.pdf", target_format="pdf")
```

**Working with the AST**

For advanced use cases, you can work directly with the Abstract Syntax Tree (AST).

```python
from all2md import to_ast, from_ast
from all2md.ast import Document, Heading, Text

# 1. Parse a document into an AST
doc: Document = to_ast("document.pdf")

# 2. Manipulate the AST
# Example: Add a new heading to the beginning
new_heading = Heading(level=1, content=[Text(content="New Title")])
doc.children.insert(0, new_heading)

# 3. Render the modified AST back to markdown
markdown_output = from_ast(doc, target_format="markdown")
```

**Using AST Transforms**

The `transforms` module provides a powerful way to manipulate the AST.

```python
from all2md import to_ast
from all2md.transforms import render, HeadingOffsetTransform, RemoveImagesTransform

# Parse to AST
doc = to_ast("report.docx")

# Apply a list of transforms before rendering
# Transforms can be class instances or registered string names
markdown_output = render(
    doc,
    transforms=[
        RemoveImagesTransform(),          # An instance
        "add-heading-ids",                # A registered name
        HeadingOffsetTransform(offset=1)  # An instance with parameters
    ]
)
```

## Extensibility: The Plugin System

`all2md` is built to be extended. You can add your own converters and transforms by leveraging Python's entry points.

-   **Custom Converters**: Create a parser for a new file format by defining a `ConverterMetadata` object and registering it under the `all2md.converters` entry point.
-   **Custom Transforms**: Create new AST manipulations by subclassing `NodeTransformer`, defining a `TransformMetadata` object, and registering it under the `all2md.transforms` entry point.

## Contributing

Contributions are welcome! Please feel free to submit a pull request, open an issue, or suggest new features.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

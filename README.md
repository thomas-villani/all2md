# `all2md`: The Universal Document Conversion Library

[![PyPI version](https://img.shields.io/pypi/v/all2md.svg)](https://pypi.org/project/all2md/)
[![CI](https://github.com/thomas-villani/all2md/actions/workflows/ci.yml/badge.svg)](https://github.com/thomas-villani/all2md/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/thomas-villani/all2md/graph/badge.svg)](https://codecov.io/gh/thomas-villani/all2md)
[![Documentation](https://img.shields.io/badge/docs-readthedocs-blue.svg)](https://all2md.readthedocs.io/)
[![License](https://img.shields.io/pypi/l/all2md.svg)](https://opensource.org/licenses/MIT)
[![Python Versions](https://img.shields.io/pypi/pyversions/all2md.svg)](https://pypi.org/project/all2md/)

**Universal Python document conversion library with native AI assistant integration**

all2md is a comprehensive document converter that transforms PDFs, Office files, HTML, emails, spreadsheets, and 40+ other formats into clean Markdown — and back again. Built on an AST-based architecture, it provides powerful programmatic document processing for Python applications, CLI workflows, data pipelines, and AI assistants.

📖 **[Read the Documentation](https://all2md.readthedocs.io/)** | 🚀 **[Quick Start](#quick-start)** | 🎯 **[Use Cases](#use-case-scenarios)**

## Quick Start

Get started with all2md in less than 30 seconds:

```bash
# Install with PDF support
pip install "all2md[pdf]"

# Convert any document to Markdown
all2md document.pdf

# Convert to a file
all2md report.docx -o report.md

# Use in Python
python -c "from all2md import to_markdown; print(to_markdown('document.pdf'))"
```

That's it! For more formats, install the dependencies you need: `all2md[docx,html,xlsx]` or `all2md[all]` for everything.

**Want to integrate with AI assistants?** See the [MCP Server](#mcp-server-for-ai-assistants) section below.

## Essential CLI Commands Cheatsheet

Beyond basic conversion, all2md provides powerful commands for working with any document format:

```bash
# View documents in terminal with rich formatting (like fancy cat)
all2md doc.pdf --rich

# Rapidly convert Markdown to DOCX, PDF, or other formats
all2md report.md --out report.docx
all2md notes.md --out presentation.pptx

# View any document in your web browser with instant HTML preview
all2md view document.pdf
all2md view spreadsheet.xlsx --theme docs

# Extract specific sections by heading name
all2md doc.pdf --extract "Introduction"
all2md view report.docx --extract "Q3 Results"

# Grep through any document type (PDF, DOCX, etc.)
all2md grep "search term" documents/*.pdf
all2md grep -i "case insensitive" report.docx

# Keyword and vector search across document collections
all2md search "machine learning" ./research_papers/
all2md search "project timeline" --semantic ./docs/

# Pipe and chain commands with stdin/stdout support (use '-' for stdin)
curl https://example.com/doc.pdf | all2md - | grep "important"
cat report.html | all2md - --format html --rich
all2md document.docx | wc -w  # Count words in any document

# All file commands support stdin via '-'
echo "<h1>Quick Note</h1>" | all2md view -            # View from stdin
cat doc.pdf | all2md grep "search term" -            # Search stdin content
echo "<p>Version 1</p>" | all2md diff - version2.html # Diff with stdin
```

These commands work with all supported formats - treat PDFs, Word docs, and spreadsheets like plain text files. Full stdin/stdout support means you can pipe, chain, and integrate all2md into any workflow.

## The Problem

Modern document workflows require converting between multiple file formats - PDFs to Markdown for analysis, Word documents to HTML for web publishing, spreadsheets to readable text for processing. Existing solutions often require multiple tools with inconsistent APIs, produce messy output, or lack programmatic control. Converting back from Markdown to rich formats is even harder.

## The Solution

`all2md` provides a unified, bidirectional conversion pipeline built on a powerful Abstract Syntax Tree (AST) architecture:

1.  **Parse:** Convert any supported document into a consistent AST representation
2.  **Transform:** Programmatically clean, modify, or analyze the content using a powerful transform pipeline
3.  **Render:** Output to Markdown, or convert directly to other rich formats like DOCX, PDF, or HTML

This AST-based approach enables:
- **Consistent conversions** across all formats
- **Bidirectional workflows** (Markdown ↔ DOCX/PDF/HTML)
- **Programmatic control** with a clean Python API
- **Perfect for AI workflows** - Feed documents to LLMs and convert their Markdown responses back to rich formats

## Why all2md?

While tools like Pandoc excel at document conversion, all2md is designed specifically for Python developers, AI/LLM workflows, and programmatic document processing. Here's when to use all2md:

**Choose all2md when you need:**
- **Python-Native Integration** - First-class Python API designed for embedding in applications, not just CLI usage
- **AI Assistant Integration** - Built-in MCP server for direct Claude Desktop, ChatGPT, and other AI model integration
- **AST-Based Transforms** - Powerful document manipulation pipeline for cleaning, modifying, and analyzing content programmatically
- **Lightweight Dependencies** - Install only what you need;
- **Extensibility** - Simple plugin system using Python entry points to add custom formats and transforms
- **Modern Python** - Built for Python 3.10+ with type hints, dataclasses, and contemporary patterns

**Choose Pandoc when you need:**
- Maximum format support (100+ formats)
- Scholarly document features (citations, bibliographies)
- Standalone binary with no runtime dependencies
- Battle-tested stability (15+ years of development)

**Use both together:** all2md complements Pandoc in Python projects. Use all2md for LLM preprocessing, programmatic workflows, and AI integration, then hand off to Pandoc for specialized academic formats if needed.

## Key Features

-   **Comprehensive Format Support**: Convert between dozens of formats, including PDF, DOCX, PPTX, HTML, EML, EPUB, XLSX, IPYNB, RST, Org-Mode, ZIP archives, and over 200 source code languages.
-   **Bidirectional Conversion**: Not just to Markdown! Convert from Markdown to formats like DOCX, PDF, and HTML.
-   **Document Comparison**: Built-in `diff` command that works like Unix `diff` but for any document format. Compare PDFs, Word docs, or mixed formats with text-based, symmetric comparison.
-   **Custom Template Rendering**: Use Jinja2 templates to create any text-based output format (DocBook XML, YAML, ANSI terminal, custom markup) without writing Python code.
-   **MCP Server**: Built-in Model Context Protocol (MCP) server for direct AI assistant integration. Enable Claude, ChatGPT, and other AI models to read and convert documents directly.
-   **AST-Based Pipeline**: At its core, `all2md` uses an Abstract Syntax Tree (AST) to represent documents, enabling powerful and consistent manipulation across all formats.
-   **Advanced PDF Parsing**: Intelligent table detection, multi-column layout analysis, header/footer removal, OCR support for scanned documents, and robust text extraction powered by PyMuPDF.
-   **Extensible Plugin System**: Easily add support for new file formats (converters) or create custom document manipulations (transforms) using a simple entry-point system.
-   **Powerful CLI**: A full-featured command-line interface with multi-file processing, parallel execution, directory watching, stdin/stdout piping, and dynamic, format-specific options.
-   **Highly Configurable**: Fine-tune every aspect of the conversion process using clean, type-safe `dataclass` options for each format.
-   **Security-Conscious**: Built-in protections against Server-Side Request Forgery (SSRF) when fetching remote resources and security validation for archives like ZIP, DOCX, and EPUB.
-   **Smart Dependency Management**: Core library is dependency-free. Install support for formats only as you need them.
all2md is built around four core strengths that make it ideal for modern document processing workflows:

### 1. AST-Based Architecture

Unlike direct format-to-format converters, all2md uses an intermediate Abstract Syntax Tree:

- Consistent document representation across all formats
- Enables powerful transforms (remove images, offset headings, rewrite links, etc.)
- Makes bidirectional conversion possible and reliable
- Allows custom output formats via Jinja2 templates (DocBook XML, YAML, ANSI terminal, etc.)
- Facilitates complex document analysis and manipulation

### 2. Production-Ready Python API

Designed for embedding in applications, not just CLI usage:

- Clean, typed API with comprehensive options classes for every format
- Progress callbacks for long-running conversions
- Bidirectional conversion between any supported formats
- AST manipulation for advanced document processing
- Transform pipeline for systematic document modification
- Extensive documentation with examples for every format

### 3. Powerful CLI Features

Beyond basic conversion, the CLI includes advanced features for production workflows:

- **Watch Mode** - Automatically convert files as they change
- **Parallel Processing** - Multi-worker processing for large document sets
- **Static Site Generation** - Built-in SSG with 5 themes (dark, docs, minimal, newspaper, sidebar)
- **Quick Preview** - `all2md view` command for instant HTML preview
- **Config Management** - Generate, validate, and manage conversion configs
- **Format Discovery** - `all2md list-formats` shows all supported formats and dependencies
- **Agent-Friendly** - Clean, intuitive interface that AI agents can use directly without MCP integration

### 4. MCP Server for AI Integration

Built-in Model Context Protocol (MCP) server enables direct integration with AI assistants like Claude Desktop. No wrapper scripts or external tools needed.

- Direct document reading in Claude Desktop and other MCP-compatible AI tools
- Smart auto-detection of file paths, data URIs, base64, and plain text
- Section extraction for targeted reading
- Vision model support with embedded images
- Security-first design with file allowlists and network controls

See [MCP Server for AI Assistants](#mcp-server-for-ai-assistants) section below for setup.

### Additional Strengths

-   **Comprehensive Format Support** - 40+ input formats and 25+ output formats including PDF, DOCX, PPTX, HTML, EML, EPUB, XLSX, IPYNB, RST, Org-Mode, ZIP archives, and over 200 source code languages
-   **Advanced PDF Parsing** - Intelligent table detection, multi-column layout analysis, header/footer removal, OCR support for scanned documents, powered by PyMuPDF
-   **Highly Configurable** - Fine-tune every aspect of conversion using clean, type-safe dataclass options for each format
-   **Security-Conscious** - Built-in SSRF protection, archive validation (ZIP bombs, path traversal), and sandboxed HTML rendering
-   **Smart Dependency Management** - Core library has no dependencies; install only what you need

## MCP Server for AI Assistants

`all2md` includes a built-in MCP (Model Context Protocol) server that allows AI assistants like Claude to directly read and convert documents:

```bash
# Install with MCP support
pip install "all2md[mcp]"

# Start MCP server with temporary workspace
all2md-mcp --temp --enable-from-md
```

**Key features:**
- **Smart Auto-Detection**: Automatically detect source type (file path, data URI, base64, or plain text)
- **Section Extraction**: Extract specific sections by heading name for targeted reading
- **Simplified API**: Just 2-3 parameters per tool with server-level configuration
- **Security First**: File allowlists, network controls, and path validation
- **vLLM Image Support**: Optionally embed images as base64 for vision-enabled models

Configure in Claude Desktop (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "all2md": {
      "command": "all2md-mcp",
      "args": ["--temp", "--enable-from-md"]
    }
  }
}
```

See the [MCP documentation](https://all2md.readthedocs.io/en/latest/mcp.html) for full details.

## Supported Formats

`all2md` uses a modular system where dependencies are only required for the formats you need to process.

| Format                        | File Extensions                               | Input (Parse) | Output (Render) | Dependencies Extra |
| ----------------------------- | --------------------------------------------- | :-----------: | :-------------: | ------------------ |
| **PDF**                       | `.pdf`                                        |       ✅       |        ✅      | `pdf`, `pdf_render`|
| **Word Document**             | `.docx`                                       |       ✅       |        ✅      | `docx`             |
| **PowerPoint Presentation**   | `.pptx`                                       |       ✅       |        ✅      | `pptx`             |
| **HTML**                      | `.html`, `.htm`                               |       ✅       |        ✅      | `html`             |
| **MHTML Web Archive**         | `.mhtml`, `.mht`                              |       ✅       |       (N/A)    | `html`             |
| **Email Message**             | `.eml`                                        |       ✅       |       (N/A)    | (built-in)         |
| **MBOX Mailbox Archive**      | `.mbox`, `.mbx`                               |       ✅       |       (N/A)    | (built-in)         |
| **Outlook Message/Archive**   | `.msg`, `.pst`, `.ost`                        |       ✅       |       (N/A)    | `outlook`          |
| **Jupyter Notebook**          | `.ipynb`                                      |       ✅       |        ✅      | (built-in)         |
| **EPUB E-book**               | `.epub`                                       |       ✅       |        ✅      | `epub`             |
| **FictionBook 2.0 (FB2)**     | `.fb2`, `.fb2.zip`                            |       ✅       |       (N/A)    | (built-in)         |
| **CHM (Compiled HTML Help)** | `.chm`                                        |       ✅       |       (N/A)    | `chm`              |
| **OpenDocument Text**         | `.odt`                                        |       ✅       |        ✅      | `odf`              |
| **OpenDocument Presentation** | `.odp`                                        |       ✅       |        ✅      | `odf`              |
| **OpenDocument Spreadsheet**  | `.ods`                                        |       ✅       |       (N/A)    | `odf`              |
| **Excel Spreadsheet**         | `.xlsx`                                       |       ✅       |       (N/A)    | `xlsx`             |
| **CSV / TSV**                 | `.csv`, `.tsv`                                |       ✅       |        ✅      | (built-in)         |
| **Rich Text Format**          | `.rtf`                                        |       ✅       |        ✅      | `rtf`              |
| **LaTeX**                     | `.tex`, `.latex`                              |       ✅       |        ✅      | `latex`            |
| **AsciiDoc**                  | `.adoc`, `.asciidoc`, `.asc`                  |       ✅       |        ✅      | (built-in)         |
| **reStructuredText**          | `.rst`                                        |       ✅       |        ✅      | `rst`              |
| **Org-Mode**                  | `.org`                                        |       ✅       |        ✅      | `org`              |
| **MediaWiki**                 | `.wiki`, `.mediawiki`                         |       ✅       |        ✅      | `wiki`             |
| **Textile**                   | `.textile`                                    |       ✅       |        ✅      | (built-in)         |
| **OpenAPI/Swagger**           | `.yaml`, `.yml`, `.json`                      |       ✅       |       (N/A)    | `openapi`          |
| **Plain Text**                | `.txt`, `.text`                               |       ✅       |        ✅      | (built-in)         |
| **Source Code**               | 200+ extensions (`.py`, `.js`, etc.)          |       ✅       |       (N/A)    | (built-in)         |
| **Archive Formats**           | `.tar`, `.tgz`, `.7z`, `.rar`, etc.           |       ✅       |       (N/A)    | (built-in)         |
| **ZIP Archive**               | `.zip`                                        |       ✅       |       (N/A)    | (built-in)         |
| **Jinja2 Templates (Custom)** | User-defined (`.jinja2`, `.j2`)               |       ❌       |        ✅      | `jinja2`           |

> **💡 New!** Create custom output formats using Jinja2 templates without writing Python code. See [Template Guide](https://all2md.readthedocs.io/en/latest/templates.html) and [examples/jinja-templates/](examples/jinja-templates/) for DocBook XML, YAML, ANSI terminal, and more.

## Installation

The core library has no dependencies. You can install it and add support for formats as needed.

**1. Basic Installation**

```bash
pip install all2md
```

**2. System-Wide CLI Installation (Recommended for CLI users)**

Install the CLI globally using [uv](https://docs.astral.sh/uv/) for instant access from anywhere:

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all2md CLI system-wide with all dependencies
uv tool install "all2md[all]"

# Or install with specific formats
uv tool install "all2md[pdf,docx,html]"

# Now use all2md from anywhere
all2md document.pdf
```

This gives you the `all2md` command globally without activating virtual environments.

**3. Installation with Extras**

Install support for only the formats you need. You can combine multiple extras.

```bash
# Install support for PDF, DOCX, and HTML
pip install "all2md[pdf,docx,html]"

# Install support for spreadsheets and ODF documents
pip install "all2md[xlsx,odf]"

# Install PDF support with OCR for scanned documents
pip install "all2md[pdf,ocr]"

# Install support for Outlook MSG files
pip install "all2md[outlook]"

# Note: PST/OST support requires additional manual installation
# pip install libpff-python  # For PST/OST files (platform-specific)
```

**4. Full Installation**

To install all optional dependencies for all supported formats:

```bash
pip install "all2md[all]"
```

**5. Check Dependencies**

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

# Convert a scanned PDF using OCR (requires Tesseract)
all2md scanned.pdf --ocr-enabled --ocr-mode auto --ocr-languages eng

# Convert an HTML file, extracting the <title> as the main heading
all2md page.html --html-extract-title

# Convert a DOCX and download images to a folder
all2md document.docx --attachment-mode save --attachment-output-dir ./images

# Convert an MBOX mailbox, limiting to 100 messages
all2md archive.mbox --mbox-max-messages 100

# Convert an Outlook PST file with folder filtering
all2md outlook.pst --outlook-folder-filter "Inbox" "Sent Items"
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

**Additional CLI Commands**

The CLI includes several utility commands for discovery and productivity:

```bash
# List all supported formats with their dependencies
all2md list-formats

# Check which optional dependencies are installed
all2md check-deps

# Quick HTML preview with themes (dark, docs, minimal, newspaper, sidebar)
all2md document.pdf view --theme docs

# Generate a static website from markdown files
all2md generate-site ./content --output ./site --theme newspaper

# Config management - generate, show, or validate config files
all2md config generate > all2md.toml
all2md config show
all2md config validate all2md.toml
```

**Static Site Generation**

all2md includes a built-in static site generator for creating documentation sites and blogs from Markdown:

```bash
# Generate a site from markdown files with frontmatter support
all2md generate-site ./content --output ./public --theme docs

# The generator supports:
# - Markdown with YAML frontmatter (title, date, author, etc.)
# - Multiple built-in themes
# - Automatic navigation generation
# - Blog-style post listings
# - Custom styling via CSS
```

See [examples/flask_markdown_site.py](examples/flask_markdown_site.py) for a complete Flask integration example.

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
from all2md import to_markdown, PdfOptions, MarkdownRendererOptions

# Use an options object for type safety and clarity
pdf_opts = PdfOptions(pages="1-3,5", attachment_mode="base64")
md_opts = MarkdownRendererOptions(flavor="gfm", emphasis_symbol="_")

markdown_content = to_markdown(
    'report.pdf',
    parser_options=pdf_opts,
    renderer_options=md_opts
)

# Convert a scanned PDF with OCR
from all2md.options.common import OCROptions

ocr_opts = OCROptions(enabled=True, mode="auto", languages="eng", dpi=300)
pdf_opts_with_ocr = PdfOptions(ocr=ocr_opts)
markdown_content = to_markdown('scanned.pdf', parser_options=pdf_opts_with_ocr)

# Alternatively, pass options as keyword arguments
markdown_content = to_markdown(
    'report.pdf',
    pages="1-3,5",  # PdfOptions
    attachment_mode="base64",  # BaseParserOptions
    flavor="gfm",  # MarkdownRendererOptions
    emphasis_symbol="_"  # MarkdownRendererOptions
)

# Convert an MBOX mailbox with message filtering
from all2md.options.mbox import MboxOptions
import datetime

mbox_opts = MboxOptions(
    max_messages=100,
    date_range_start=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
    output_structure="hierarchical"
)
markdown_content = to_markdown('archive.mbox', parser_options=mbox_opts)

# Convert an Outlook PST file with folder filtering
from all2md.options.outlook import OutlookOptions

outlook_opts = OutlookOptions(
    folder_filter=["Inbox", "Sent Items"],
    skip_folders=["Deleted Items", "Junk Email"],
    max_messages=500
)
markdown_content = to_markdown('mailbox.pst', parser_options=outlook_opts)
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

See [examples/simpledoc-plugin/](examples/simpledoc-plugin/) for a complete plugin example and [examples/watermark-plugin/](examples/watermark-plugin/) for a transform plugin.

## Use Case Scenarios

all2md is designed to serve multiple audiences with different needs:

### For Python Developers

**Scenario:** You're building a documentation system, content management tool, or data pipeline that needs to handle multiple document formats.

```python
from all2md import to_markdown, convert
from all2md.transforms import render, RemoveImagesTransform

# Convert uploaded documents to markdown for storage
def process_upload(file_path):
    markdown = to_markdown(file_path)
    # Store in database or file system
    return markdown

# Build a document converter API
def convert_document(input_path, output_format):
    convert(input_path, f"output.{output_format}", target_format=output_format)

# Clean documents for display
def clean_for_web(doc_path):
    from all2md import to_ast
    doc = to_ast(doc_path)
    return render(doc, transforms=["remove-images", "sanitize-html"])
```

**Examples:** [batch_converter.py](examples/batch_converter.py), [document_sanitizer.py](examples/document_sanitizer.py)

### For AI/LLM Developers

**Scenario:** You're building LLM applications that need to ingest documents, process them, and generate new documents.

```python
# Setup MCP server for Claude Desktop integration
# Add to claude_desktop_config.json:
{
  "mcpServers": {
    "all2md": {
      "command": "all2md-mcp",
      "args": ["--temp", "--enable-from-md"]
    }
  }
}

# Or use programmatically in your LLM pipeline
from all2md import to_markdown, convert

# 1. Ingest: Convert documents to markdown for LLM processing
document_text = to_markdown("research_paper.pdf")

# 2. Process: Send to LLM, get markdown response
llm_response = your_llm_call(document_text)

# 3. Generate: Convert LLM output back to rich format
with open("output.md", "w") as f:
    f.write(llm_response)
convert("output.md", "final_report.docx", target_format="docx")
```

**Examples:** [llm_translation_demo.py](examples/llm_translation_demo.py), [study_guide_generator.py](examples/study_guide_generator.py)

### For CLI Users & DevOps

**Scenario:** You need to batch process documents, integrate conversions into scripts, or monitor directories for new documents.

```bash
# Watch a directory and convert new documents automatically
all2md ./incoming -r -o ./processed --watch

# Batch process with parallel workers
all2md ./documents/*.pdf -o ./markdown --parallel 8

# Integrate into CI/CD pipeline
for doc in ./docs/*.docx; do
  all2md "$doc" -o "./output/$(basename "$doc" .docx).md"
done

# Generate documentation site from markdown files
all2md generate-site ./docs --output ./public --theme docs

# Quick preview before committing
all2md README.md view --theme minimal
```

**Examples:** [vcs-converter/](examples/vcs-converter/) (Git pre-commit hook integration)

### For Data Scientists

**Scenario:** You're extracting data from PDFs, spreadsheets, and documents for analysis or feeding into ML pipelines.

```python
from all2md import to_markdown, to_ast
from all2md.ast import Document, Table

# Extract tables from PDFs for analysis
def extract_tables(pdf_path):
    doc = to_ast(pdf_path)
    tables = [node for node in doc.walk() if isinstance(node, Table)]
    return tables

# Process email archives for NLP
def process_email_archive(mbox_path):
    from all2md.options.mbox import MboxOptions
    opts = MboxOptions(
        output_structure="flat",
        extract_metadata=True
    )
    emails = to_markdown(mbox_path, parser_options=opts)
    return emails

# Extract code examples from documentation
def extract_code_blocks(doc_path):
    doc = to_ast(doc_path)
    from all2md.ast import CodeBlock
    code_blocks = [node for node in doc.walk() if isinstance(node, CodeBlock)]
    return code_blocks
```

**Examples:** [api_doc_extractor.py](examples/api_doc_extractor.py), [code_example_generator.py](examples/code_example_generator.py)

## Frequently Asked Questions

**Q: How is all2md different from Pandoc?**

A: all2md is Python-native with a focus on programmatic use, LLM integration, and extensibility. Pandoc is more comprehensive for scholarly documents but is Haskell-based and CLI-focused. Use all2md for Python projects and AI workflows; use Pandoc for academic publishing. They complement each other well.

**Q: Can I convert back from Markdown to Word/PDF?**

A: Yes! all2md supports bidirectional conversion. Use `convert("input.md", "output.docx", target_format="docx")` or the CLI: `all2md input.md -o output.pdf --to pdf`.

**Q: What's the best format for feeding documents to LLMs?**

A: Markdown with the `gfm` (GitHub Flavored Markdown) flavor. It's structured, consistent, and well-understood by LLMs. Use `to_markdown(file, flavor="gfm")`.

**Q: How do I add support for a new file format?**

A: Create a parser class, define a `ConverterMetadata` object, and register it via `all2md.converters` entry point in your `pyproject.toml`. See [examples/simpledoc-plugin/](examples/simpledoc-plugin/) for a complete example.

**Q: Does all2md work with scanned PDFs?**

A: Yes! Install with OCR support: `pip install "all2md[pdf,ocr]"` and use `--ocr-enabled` flag or `OCROptions(enabled=True)` in Python. Requires Tesseract to be installed on your system.

**Q: Can I customize the output format beyond Markdown?**

A: Yes! Use Jinja2 templates to create any text-based output format. See [examples/jinja-templates/](examples/jinja-templates/) for examples of DocBook XML, YAML, ANSI terminal output, and more.

**Q: Is all2md production-ready?**

A: Yes! Version 1.0.0 is stable and production-ready. The library includes comprehensive tests, extensive documentation, and is actively maintained.

**Q: How do I handle large document batches efficiently?**

A: Use parallel processing: `all2md ./docs -r -o ./output --parallel 8` or in Python use multiprocessing with `to_markdown()` calls. For very large batches, consider the watch mode for incremental processing.

## Getting Help

- **Documentation:** [Read the full documentation on ReadTheDocs](https://all2md.readthedocs.io/)
- **Examples:** Browse [15+ examples](examples/) organized by complexity and use case
- **Issues:** Report bugs or request features on [GitHub Issues](https://github.com/thomas-villani/all2md/issues)

## Contributing

Contributions are welcome! We appreciate bug reports, feature requests, documentation improvements, and code contributions.

**Ways to contribute:**
- Report bugs or suggest features via [GitHub Issues](https://github.com/thomas-villani/all2md/issues)
- Improve documentation or add examples
- Add support for new file formats via the plugin system
- Create new AST transforms
- Fix bugs or improve existing converters

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

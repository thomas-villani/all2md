Library Overview
================

all2md is designed as a comprehensive yet lightweight document conversion library optimized for modern workflows, particularly LLM preprocessing and document analysis pipelines. This overview covers the library's architecture, design principles, and core capabilities.

Design Philosophy
-----------------

Lightweight by Default
~~~~~~~~~~~~~~~~~~~~~~~

all2md uses optional dependencies to keep the base installation minimal. Only install what you need:

* **Base installation**: ~5MB (HTML, text, CSV support)
* **Full installation**: ~50MB (all formats)
* **Selective installation**: Choose only the formats you use

Intelligent Format Detection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The library uses a multi-layered format detection strategy:

1. **Filename extension analysis** (most reliable)
2. **MIME type detection** (secondary verification)
3. **Content-based magic bytes** (for file objects without names)
4. **Fallback to plain text** (graceful degradation)

This ensures accurate conversion even when file extensions are missing or incorrect.

Consistent API Design
~~~~~~~~~~~~~~~~~~~~~

All conversions use the same simple interface:

.. code-block:: python

   from all2md import to_markdown

   # Works for any supported format
   markdown = to_markdown(input_file, options=format_options)

Format-specific complexity is handled internally while maintaining API consistency.

Architecture Overview
---------------------

Core Components
~~~~~~~~~~~~~~~

.. code-block:: text

   all2md/
   ├── __init__.py           # Main entry point and format detection
   ├── __main__.py          # Entry point for CLI (python -m all2md)
   ├── constants.py         # Default values and configuration
   ├── exceptions.py        # Custom exception hierarchy
   ├── options.py           # Configuration dataclasses
   ├── converter_registry.py # Registry system for converters
   ├── converter_metadata.py # Metadata and dependency management
   ├── cli/                 # Command-line interface package
   │   ├── __init__.py      # CLI package initialization
   │   ├── custom_actions.py       # Core CLI actions and commands
   │   ├── builder.py       # Argument parser construction
   │   └── processors.py    # File processing and batch operations
   ├── ast/                 # Abstract Syntax Tree module
   │   ├── __init__.py      # AST public API
   │   ├── nodes.py         # AST node definitions
   │   ├── visitors.py      # Visitor pattern for traversal
   │   ├── transforms.py    # AST transformation utilities
   │   ├── builder.py       # AST construction helpers
   │   └── serialization.py # JSON serialization
   ├── parsers/             # Format parsers (input → AST)
   │   ├── __init__.py
   │   ├── base.py          # Base parser class
   │   ├── pdf.py           # PDF → AST
   │   ├── docx.py          # DOCX → AST
   │   ├── html.py          # HTML → AST
   │   ├── eml.py           # Email → AST
   │   ├── pptx.py          # PowerPoint → AST
   │   ├── ipynb.py         # Jupyter → AST
   │   ├── epub.py          # EPUB → AST
   │   ├── odt.py           # ODT (text) → AST
   │   ├── odp.py           # ODP (presentation) → AST
   │   ├── mhtml.py         # MHTML → AST
   │   ├── rtf.py           # RTF → AST
   │   ├── rst.py           # reStructuredText → AST
   │   ├── org.py           # Org-Mode → AST
   │   ├── markdown.py      # Markdown → AST
   │   ├── sourcecode.py    # Source code → AST
   │   ├── xlsx.py          # Excel → AST
   │   ├── ods_spreadsheet.py # ODS spreadsheet → AST
   │   └── csv.py           # CSV/TSV → AST
   ├── renderers/           # Format renderers (AST → output)
   │   ├── __init__.py
   │   ├── base.py          # Base renderer class
   │   ├── markdown.py      # AST → Markdown
   │   ├── docx.py          # AST → DOCX
   │   ├── html.py          # AST → HTML
   │   ├── pdf.py           # AST → PDF
   │   ├── epub.py          # AST → EPUB
   │   ├── pptx.py          # AST → PowerPoint
   │   └── rst.py           # AST → reStructuredText
   └── utils/               # Shared utilities
       ├── __init__.py
       ├── inputs.py        # Input validation and handling
       ├── attachments.py   # Image and attachment processing
       ├── metadata.py      # Document metadata extraction
       ├── security.py      # Security utilities
       ├── flavors.py       # Markdown flavor support
       └── network_security.py # Network and SSRF protection

The Main Entry Point
~~~~~~~~~~~~~~~~~~~~~

The ``to_markdown()`` function in ``__init__.py`` acts as the orchestrator:

.. code-block:: python

   def to_markdown(
       input: Union[str, Path, IO[bytes], bytes],
       *,
       options: Optional[BaseOptions] = None,
       format: DocumentFormat = "auto",
       **kwargs
   ) -> str:
       # 1. Input normalization (file path → file object)
       # 2. Format detection (if format="auto")
       # 3. Options processing and merging
       # 4. Route to appropriate converter
       # 5. Return clean Markdown string

General Format Conversion
~~~~~~~~~~~~~~~~~~~~~~~~~~

For conversions between any supported formats (not just to Markdown), use the ``convert()`` function:

.. code-block:: python

   from all2md import convert
   from all2md.options import PdfOptions, MarkdownOptions

   # Convert PDF to Markdown (returns str when no output specified)
   markdown = convert("document.pdf", target_format="markdown")

   # Convert PDF to DOCX (writes to file)
   convert("document.pdf", "output.docx")

   # Convert Markdown to HTML with options
   convert(
       source="report.md",
       output="report.html",
       target_format="html",
       renderer_options=HtmlRendererOptions(...)
   )

   # Convert with AST transforms
   convert(
       source="input.docx",
       output="output.pdf",
       transforms=["remove-images", "heading-offset"],
       parser_options=DocxOptions(...),
       renderer_options=PdfRendererOptions(...)
   )

**Key Features:**

* **Auto-detection**: Both source and target formats detected automatically
* **Transform pipeline**: Apply AST transforms between parsing and rendering
* **Flexible I/O**: Supports file paths, file objects, and bytes
* **Return behavior**: Returns str/bytes if no output specified, None if output written to file

See :doc:`bidirectional` for detailed examples of Markdown-to-DOCX/HTML/PDF conversions.

Format Detection Pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~

The library uses a registry-based detection system (``ConverterRegistry.detect_format``) that employs multiple detection strategies in priority order to ensure accurate format identification:

1. **Explicit hint**: When format is explicitly specified, bypass detection
2. **Filename extension**: Analyze file extension for immediate format identification
3. **MIME type detection**: Use ``mimetypes.guess_type()`` for secondary verification
4. **Magic bytes/content detectors**: Examine file headers and content patterns for files without reliable names
5. **Fallback to plain text**: Graceful degradation when no specific format is detected

This registry-based approach maximizes accuracy while providing graceful degradation for edge cases. Each converter registers its supported extensions, MIME types, and content detection patterns with the central registry, making the system easily extensible for new formats.

**Inspecting Format Support:**

You can use the ``list-formats`` CLI command to explore which formats are supported and check which dependencies are available in your environment:

.. code-block:: bash

   # List all supported formats with their status
   all2md list-formats

   # Show details about a specific format
   all2md list-formats pdf

   # Show only formats with available dependencies
   all2md list-formats --available-only

This is particularly useful when diagnosing format detection issues or verifying that required dependencies are installed. See :doc:`troubleshooting` for common format detection issues and solutions.

AST Architecture
~~~~~~~~~~~~~~~~

all2md includes a powerful Abstract Syntax Tree (AST) module that separates document parsing from rendering. This enables:

* **Advanced document analysis**: Extract structure, count elements, generate statistics
* **Programmatic transformation**: Modify documents before rendering
* **Multiple output formats**: Render same AST to different Markdown flavors
* **Persistent storage**: Save/load document structure as JSON

**Two Conversion Paths:**

1. **Direct Path**: ``to_markdown()`` - Document → Markdown (faster, simpler)
2. **AST Path**: ``to_ast()`` - Document → AST → Markdown (flexible, powerful)

.. code-block:: python

   from all2md import to_markdown, to_ast
   from all2md.renderers.markdown import MarkdownRenderer
   from all2md.utils.flavors import GFMFlavor

   # Direct conversion (simple)
   markdown = to_markdown('document.pdf')

   # AST conversion (advanced)
   doc_ast = to_ast('document.pdf')

   # Analyze structure
   from all2md.ast import NodeVisitor, Heading
   class HeadingExtractor(NodeVisitor):
       def __init__(self):
           self.headings = []
       def visit_heading(self, node: Heading):
           self.headings.append(node)

   extractor = HeadingExtractor()
   doc_ast.accept(extractor)
   print(f"Found {len(extractor.headings)} headings")

   # Transform AST
   from all2md.ast import HeadingLevelTransformer
   transformer = HeadingLevelTransformer(offset=1)
   transformed = transformer.transform(doc_ast)

   # Render to GitHub Flavored Markdown
   renderer = MarkdownRenderer(flavor=GFMFlavor())
   gfm_markdown = renderer.render(transformed)

**AST Node Types:**

* **Block nodes**: Document, Heading, Paragraph, CodeBlock, Table, List, etc.
* **Inline nodes**: Text, Strong, Emphasis, Link, Image, Code, etc.
* **Structural**: TableRow, TableCell, ListItem, BlockQuote

**Key AST Capabilities:**

* **Visitors**: Traverse AST to extract information (``NodeVisitor``)
* **Transformers**: Modify AST nodes (``NodeTransformer``)
* **Serialization**: Save/load as JSON (``ast_to_json``, ``json_to_ast``)
* **Builders**: Construct complex structures (``TableBuilder``, ``ListBuilder``)
* **Flavors**: Render to CommonMark, GFM, or custom dialects
* **Bidirectional conversion**: Render AST to DOCX, HTML, or PDF

For complete AST documentation, see :doc:`ast_guide`. For bidirectional conversion examples (Markdown to DOCX/HTML/PDF), see :doc:`bidirectional`.

Converter Architecture
~~~~~~~~~~~~~~~~~~~~~~

Each converter module follows a consistent pattern:

.. code-block:: python

   def format_to_markdown(
       input_data: Union[IO, str],
       options: Optional[FormatOptions] = None
   ) -> str:
       """
       1. Validate input and options
       2. Parse document structure
       3. Extract content with formatting
       4. Handle attachments (images, etc.)
       5. Generate clean Markdown
       6. Apply post-processing
       """

Options System
--------------

Hierarchical Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~

The options system uses a two-level hierarchy:

1. **Format-specific options** (``PdfOptions``, ``DocxOptions``, etc.)
2. **Common Markdown options** (``MarkdownOptions``)

.. code-block:: python

   @dataclass
   class PdfOptions:
       pages: Optional[list[int]] = None
       table_detection: bool = True
       attachment_mode: AttachmentMode = "skip"
       # ... PDF-specific settings

       markdown_options: Optional[MarkdownOptions] = None

   @dataclass
   class MarkdownOptions:
       emphasis_symbol: EmphasisSymbol = "*"
       bullet_symbols: list[str] = field(default_factory=lambda: ["*", "-", "+"])
       use_hash_headings: bool = True
       # ... common Markdown formatting options

Flexible Option Merging
~~~~~~~~~~~~~~~~~~~~~~~

Options can be provided in multiple ways and are merged intelligently:

.. code-block:: python

   # Method 1: Pre-configured options object
   options = PdfOptions(pages=[0, 1, 2], attachment_mode='download')
   markdown = to_markdown('doc.pdf', options=options)

   # Method 2: Keyword arguments (creates options object)
   markdown = to_markdown('doc.pdf', pages=[0, 1, 2], attachment_mode='download')

   # Method 3: Mixed (kwargs override options)
   markdown = to_markdown('doc.pdf', options=options, attachment_mode='base64')

The merger prioritizes keyword arguments over pre-configured options, allowing flexible overrides.

Format-Specific Capabilities
-----------------------------

PDF Processing
~~~~~~~~~~~~~~

**Advanced Features:**
- Table detection using PyMuPDF's table extraction
- Multi-column layout handling
- Header and footer detection
- Image extraction and placement
- Page-specific processing

**Technology:** PyMuPDF (fitz) for robust PDF parsing

.. code-block:: python

   from all2md.options import PdfOptions

   options = PdfOptions(
       pages=[0, 1, 2],                    # Process specific pages
       table_detection=True,               # Enable table parsing
       header_detection=True,              # Detect document headers
       column_detection=True,              # Handle multi-column layouts
       attachment_mode='download',         # Download images locally
       attachment_output_dir='./images'    # Image output directory
   )

Word Documents (DOCX)
~~~~~~~~~~~~~~~~~~~~~

**Advanced Features:**
- Full formatting preservation (bold, italic, underline)
- Table structure extraction
- Image and shape handling
- Style-based header detection
- List structure preservation

**Technology:** python-docx for comprehensive DOCX parsing

.. code-block:: python

   from all2md.options import DocxOptions

   options = DocxOptions(
       preserve_tables=True,               # Maintain table structure
       extract_images=True,                # Process embedded images
       style_mapping=True,                 # Map Word styles to Markdown
       attachment_mode='base64'            # Embed images as base64
   )

PowerPoint (PPTX)
~~~~~~~~~~~~~~~~~

**Advanced Features:**
- Slide-by-slide extraction
- Notes and comments processing
- Shape and text box handling
- Chart and diagram extraction
- Speaker notes inclusion

**Technology:** python-pptx for presentation parsing

HTML Documents
~~~~~~~~~~~~~~

**Advanced Features:**
- Semantic HTML conversion
- Table structure preservation
- Image and media handling with secure remote fetching
- Link processing
- Custom element mapping
- Comprehensive network security controls

**Technology:** BeautifulSoup4 for robust HTML parsing, httpx for secure HTTP requests

**Network Security:**

HTML processing includes sophisticated network security features to prevent SSRF attacks and control remote resource access. For comprehensive security information, see :doc:`security` and :doc:`threat_model`:

.. code-block:: python

   from all2md.options import HtmlOptions
   from all2md.options import NetworkFetchOptions

   # Secure configuration for web applications
   secure_options = HtmlOptions(
       network=NetworkFetchOptions(
           allow_remote_fetch=True,       # Enable remote fetching
           allowed_hosts=["example.com", "cdn.example.com"],  # Whitelist specific hosts
           require_https=True,            # Force HTTPS for all requests
           network_timeout=5.0,           # 5-second timeout
           max_remote_asset_bytes=2 * 1024 * 1024  # 2MB image limit
       ),
       attachment_mode="download",
       attachment_output_dir="./secure_images"
   )

   # Process HTML with strict security controls
   markdown = to_markdown("webpage.html", options=secure_options)

**Global Network Disable:**

For maximum security in sensitive environments, use the ``ALL2MD_DISABLE_NETWORK`` environment variable to globally block all network operations:

.. code-block:: bash

   # Disable all network operations globally
   export ALL2MD_DISABLE_NETWORK=1
   all2md webpage.html  # Will skip all remote resources

.. code-block:: python

   import os
   os.environ['ALL2MD_DISABLE_NETWORK'] = '1'

   # All network requests will be blocked regardless of options
   markdown = to_markdown("webpage.html", network=NetworkFetchOptions(allow_remote_fetch=True))  # Still blocked

**Security Features:**

- **Host validation**: Only allow requests to explicitly whitelisted domains
- **HTTPS enforcement**: Reject HTTP requests when ``require_https=True``
- **Size limits**: Prevent DoS via large downloads with ``max_image_size_bytes``
- **Timeout protection**: Prevent hanging requests with configurable timeouts
- **SSRF prevention**: Built-in protection against Server-Side Request Forgery attacks

Email (EML)
~~~~~~~~~~~

**Advanced Features:**
- Multi-part message handling
- Attachment extraction
- Reply chain detection
- Header processing
- HTML and plain text part selection

**Technology:** Built-in Python email libraries

Jupyter Notebooks
~~~~~~~~~~~~~~~~~

**Advanced Features:**
- Code cell preservation with syntax highlighting
- Output cell processing (text, images, HTML)
- Markdown cell pass-through
- Execution count tracking
- Metadata preservation

Error Handling and Recovery
---------------------------

Exception Hierarchy
~~~~~~~~~~~~~~~~~~~

.. code-block:: text

   All2MdError (base)
   ├── ValidationError
   │   └── PageRangeError
   ├── FileError
   │   ├── FileNotFoundError
   │   ├── FileAccessError
   │   └── MalformedFileError
   ├── FormatError
   ├── ParsingError
   │   └── PasswordProtectedError
   ├── RenderingError
   │   └── OutputWriteError
   ├── TransformError
   ├── SecurityError
   │   ├── NetworkSecurityError
   │   └── ZipFileSecurityError
   └── DependencyError

Graceful Degradation
~~~~~~~~~~~~~~~~~~~~

The library handles errors gracefully:

.. code-block:: python

   from all2md.exceptions import DependencyError, All2MdError

   try:
       markdown = to_markdown('document.pdf')
   except DependencyError as e:
       print(f"Missing dependency: {e}")
       print("Install with: pip install all2md[pdf]")
   except All2MdError as e:
       print(f"Conversion failed: {e}")
       # Fallback to text extraction or alternative processing

Progress Callbacks
------------------

For long-running conversions, progress callbacks provide real-time updates to enable UI updates, logging, or progress bars in applications that embed all2md.

Basic Usage
~~~~~~~~~~~

Pass a callback function to any conversion function:

.. code-block:: python

   from all2md import to_markdown, ProgressEvent

   def my_progress_handler(event: ProgressEvent):
       print(f"[{event.event_type}] {event.message}")
       if event.total > 0:
           percentage = (event.current / event.total) * 100
           print(f"  Progress: {percentage:.1f}%")

   markdown = to_markdown("document.pdf", progress=my_progress_handler)

Progress Event Types
~~~~~~~~~~~~~~~~~~~~~

The ``ProgressEvent`` dataclass includes:

* **started** - Conversion has begun
* **page_done** - A page/section has been processed (PDF, PPTX)
* **table_detected** - Table structure detected (PDF)
* **finished** - Conversion completed successfully
* **error** - An error occurred during processing

.. code-block:: python

   @dataclass
   class ProgressEvent:
       event_type: Literal["started", "page_done", "table_detected", "finished", "error"]
       message: str
       current: int = 0      # Current progress position
       total: int = 0        # Total items to process
       metadata: dict = {}   # Event-specific data

Event-Specific Handling
~~~~~~~~~~~~~~~~~~~~~~~

Different event types provide different metadata:

.. code-block:: python

   def detailed_handler(event: ProgressEvent):
       if event.event_type == "started":
           print(f"Starting: {event.message}")

       elif event.event_type == "page_done":
           print(f"  Page {event.current}/{event.total} complete")

       elif event.event_type == "table_detected":
           table_count = event.metadata.get('table_count', 0)
           page = event.metadata.get('page', '?')
           print(f"  Found {table_count} tables on page {page}")

       elif event.event_type == "finished":
           print(f"Complete: {event.message}")

       elif event.event_type == "error":
           error = event.metadata.get('error', 'Unknown')
           print(f"  ERROR: {error}")

   markdown = to_markdown("large_document.pdf", progress=detailed_handler)

GUI Integration
~~~~~~~~~~~~~~~

Progress callbacks are especially useful for GUI applications:

.. code-block:: python

   import tkinter as tk
   from tkinter import ttk
   from all2md import to_markdown, ProgressEvent

   class ConverterApp:
       def __init__(self, root):
           self.root = root
           self.progress = ttk.Progressbar(root, length=300, mode='determinate')
           self.progress.pack()
           self.status = tk.Label(root, text="Ready")
           self.status.pack()

       def progress_callback(self, event: ProgressEvent):
           if event.total > 0:
               value = (event.current / event.total) * 100
               self.progress['value'] = value
           self.status['text'] = event.message
           self.root.update_idletasks()

       def convert(self, filepath):
           return to_markdown(filepath, progress=self.progress_callback)

Error Handling in Callbacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Progress callbacks are fail-safe - exceptions in the callback are caught and logged without interrupting conversion:

.. code-block:: python

   def potentially_failing_callback(event: ProgressEvent):
       # Even if this raises an exception, conversion continues
       risky_operation(event)

   # Conversion will complete successfully even if callback fails
   markdown = to_markdown("document.pdf", progress=potentially_failing_callback)

API Support
~~~~~~~~~~~

All conversion functions support progress callbacks:

.. code-block:: python

   from all2md import to_markdown, to_ast, convert, from_markdown

   # All support the progress parameter
   markdown = to_markdown("doc.pdf", progress=callback)
   ast_doc = to_ast("doc.pdf", progress=callback)
   convert("doc.pdf", "output.docx", progress=callback)
   from_markdown("input.md", "html", progress=callback)

Dependency Management
---------------------

Optional Dependencies
~~~~~~~~~~~~~~~~~~~~~

Each format's dependencies are isolated:

.. code-block:: python

   # PDF converter
   try:
       import fitz  # PyMuPDF
   except ImportError:
       raise ImportError("PyMuPDF required for PDF processing")

   # Word converter
   try:
       from docx import Document
   except ImportError:
       raise ImportError("python-docx required for DOCX processing")

This allows partial installations and clear error messages for missing dependencies. See :doc:`installation` for complete dependency installation instructions.

Programmatic Dependency Management
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For automated setups, CI/CD pipelines, or installation scripts, all2md provides programmatic dependency checking:

.. code-block:: python

   from all2md.dependencies import (
       check_all_dependencies,
       get_missing_dependencies,
       generate_install_command,
       print_dependency_report
   )

   # Check all format dependencies
   # Returns: dict[format_name -> dict[package_name -> is_installed]]
   results = check_all_dependencies()
   for format_name, packages in results.items():
       all_installed = all(packages.values())
       status = "✓ Available" if all_installed else "✗ Missing dependencies"
       print(f"{format_name}: {status}")
       if not all_installed:
           missing = [pkg for pkg, installed in packages.items() if not installed]
           print(f"  Missing: {', '.join(missing)}")

   # Check specific format dependencies
   # Returns: list[(package_name, version_spec)]
   missing_pdf = get_missing_dependencies('pdf')
   if missing_pdf:
       print(f"PDF missing: {missing_pdf}")
   else:
       print("PDF conversion available")

   # Generate installation command from missing packages
   # Takes list[(package_name, version_spec)] and returns pip command
   if missing_pdf:
       cmd = generate_install_command(missing_pdf)
       print(f"Install with: {cmd}")
       # Output: pip install "package_name>=version"

   # Print a comprehensive dependency report
   report = print_dependency_report()
   print(report)

**Automated Setup Script:**

.. code-block:: python

   """
   Automated all2md setup and validation script.
   """
   from all2md.dependencies import (
       check_all_dependencies,
       get_missing_dependencies,
       generate_install_command
   )
   import subprocess
   import sys

   def check_and_install_format(format_name):
       """Check and install dependencies for a specific format."""
       missing = get_missing_dependencies(format_name)

       if not missing:
           print(f"✓ {format_name}: All dependencies available")
           return True

       print(f"✗ {format_name}: Missing {len(missing)} package(s)")
       cmd = generate_install_command(missing)
       print(f"  Installing: {cmd}")

       try:
           subprocess.check_call(cmd.split())
           print(f"  ✓ Installation successful")
           return True
       except subprocess.CalledProcessError as e:
           print(f"  ✗ Installation failed: {e}")
           return False

   def main():
       """Main setup routine."""
       required_formats = ['pdf', 'docx', 'html']

       print("Checking all2md dependencies...")
       success = True

       for fmt in required_formats:
           if not check_and_install_format(fmt):
               success = False

       if success:
           print("\n✓ All required formats ready")
       else:
           print("\n✗ Some dependencies failed to install")
           sys.exit(1)

   if __name__ == '__main__':
       main()

**CI/CD Pipeline Integration:**

.. code-block:: python

   """
   CI/CD pre-flight check for all2md capabilities.
   """
   from all2md.dependencies import check_all_dependencies, get_missing_dependencies
   import json
   import sys

   def ci_dependency_check():
       """Check dependencies and output results for CI."""
       results = check_all_dependencies()

       # Generate CI-friendly report
       available_formats = []
       missing_formats = []

       for format_name, packages in results.items():
           all_installed = all(packages.values())
           if all_installed:
               available_formats.append(format_name)
           else:
               missing_pkgs = [pkg for pkg, installed in packages.items() if not installed]
               missing_formats.append({
                   'format': format_name,
                   'missing_packages': missing_pkgs
               })

       report = {
           'available_formats': available_formats,
           'missing_formats': missing_formats,
           'total_formats': len(results),
           'ready': len(missing_formats) == 0
       }

       # Output JSON for parsing by CI tools
       print(json.dumps(report, indent=2))

       # Exit with error code if not ready
       if not report['ready']:
           print("\n❌ Some dependencies are missing", file=sys.stderr)
           sys.exit(1)
       else:
           print("\n✅ All dependencies available")
           sys.exit(0)

   if __name__ == '__main__':
       ci_dependency_check()

**Recommended Approach for CI/CD:**

For most use cases, it's recommended to use pip extras directly rather than programmatic dependency management:

.. code-block:: bash

   # Install specific formats
   pip install all2md[pdf,docx,html]

   # Install all formats
   pip install all2md[all]

**Conditional Feature Loading:**

.. code-block:: python

   """
   Application that adapts based on available formats.
   """
   from all2md import to_markdown
   from all2md.dependencies import check_all_dependencies

   class DocumentConverter:
       """Converter that adapts to available dependencies."""

       def __init__(self):
           self.supported_formats = self._detect_formats()

       def _detect_formats(self):
           """Detect which formats are available."""
           results = check_all_dependencies()
           # Return formats where all packages are installed
           return [
               fmt for fmt, packages in results.items()
               if all(packages.values())
           ]

       def convert(self, filepath, format='auto'):
           """Convert file with fallback handling."""
           if format != 'auto' and format not in self.supported_formats:
               raise ValueError(
                   f"Format '{format}' not available. "
                   f"Supported: {', '.join(self.supported_formats)}"
               )

           return to_markdown(filepath, source_format=format)

   # Usage
   converter = DocumentConverter()
   print(f"Supported formats: {converter.supported_formats}")

   if 'pdf' in converter.supported_formats:
       result = converter.convert('document.pdf')
   else:
       print("PDF support not available")

Performance Considerations
--------------------------

Memory Efficiency
~~~~~~~~~~~~~~~~~

- **Streaming processing** for large files where possible
- **Lazy loading** of format-specific modules
- **Memory-aware** image processing with configurable limits

Processing Speed
~~~~~~~~~~~~~~~~

- **Direct format APIs** instead of external tools
- **Minimal dependencies** for faster import times
- **Caching** for repeated operations where beneficial

Extensibility
-------------

Adding New Formats
~~~~~~~~~~~~~~~~~~

The architecture makes it straightforward to add new formats through the plugin system. See :doc:`plugins` for complete plugin development guide.

**Plugin Development Overview:**

1. Create parser module extending ``BaseParser``
2. Define format detection logic (extensions, MIME types, magic bytes)
3. Create custom options dataclass
4. Register via entry points

.. code-block:: python

   # converters/newformat2markdown.py
   def newformat_to_markdown(input_data, options=None):
       # Implementation here
       pass

   # Add to __init__.py format detection and routing

Custom Options
~~~~~~~~~~~~~~

New option classes inherit from ``BaseOptions``:

.. code-block:: python

   @dataclass
   class NewFormatOptions(BaseOptions):
       custom_setting: bool = True
       markdown_options: Optional[MarkdownOptions] = None

Integration Patterns
--------------------

For more practical examples and patterns, see :doc:`recipes`.

Batch Processing
~~~~~~~~~~~~~~~~

For complete CLI batch processing options, see :doc:`cli`.

.. code-block:: python

   from pathlib import Path
   from all2md import to_markdown

   def process_directory(input_dir, output_dir, file_pattern="*"):
       input_path = Path(input_dir)
       output_path = Path(output_dir)
       output_path.mkdir(exist_ok=True)

       for file_path in input_path.glob(file_pattern):
           if file_path.is_file():
               try:
                   markdown = to_markdown(str(file_path))
                   output_file = output_path / f"{file_path.stem}.md"

                   with open(output_file, 'w', encoding='utf-8') as f:
                       f.write(markdown)

                   print(f"✓ {file_path.name} -> {output_file.name}")

               except Exception as e:
                   print(f"✗ {file_path.name}: {e}")

Web Service Integration
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from flask import Flask, request, jsonify
   from all2md import to_markdown
   import tempfile

   app = Flask(__name__)

   @app.route('/convert', methods=['POST'])
   def convert_document():
       if 'file' not in request.files:
           return jsonify({'error': 'No file provided'}), 400

       file = request.files['file']

       try:
           # Save uploaded file temporarily
           with tempfile.NamedTemporaryFile() as tmp:
               file.save(tmp.name)
               markdown = to_markdown(tmp.name)

           return jsonify({'markdown': markdown})

       except Exception as e:
           return jsonify({'error': str(e)}), 500

This overview provides the foundation for understanding all2md's capabilities. For specific usage examples, see the :doc:`formats` guide, and for complete configuration options, visit the :doc:`options` reference.
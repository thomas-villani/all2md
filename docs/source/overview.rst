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
   markdown = to_markdown(input_file, parser_options=format_options)

Format-specific complexity is handled internally while maintaining API consistency.

Architecture Overview
---------------------

Core Components
~~~~~~~~~~~~~~~

.. code-block:: text

   all2md/
   ├── ast/                 # Abstract Syntax Tree module
   │   ├── __init__.py      # AST public API
   │   ├── builder.py       # AST construction helpers
   │   ├── document_utils.py # Document manipulation utilities
   │   ├── nodes.py         # AST node definitions
   │   ├── serialization.py # JSON serialization
   │   ├── transforms.py    # AST transformation utilities
   │   ├── utils.py         # AST utility functions
   │   └── visitors.py      # Visitor pattern for traversal
   ├── cli/                 # Command-line interface package
   │   ├── __init__.py      # CLI package initialization
   │   ├── builder.py       # Argument parser construction
   │   ├── commands.py      # CLI command implementations
   │   ├── config.py        # Configuration management
   │   ├── custom_actions.py # Custom argparse actions
   │   ├── help_formatter.py # Help text formatting
   │   ├── packaging.py     # Package metadata
   │   ├── presets.py       # Configuration presets
   │   ├── processors.py    # File processing and batch operations
   │   ├── progress.py      # Progress display
   │   ├── timing.py        # Performance timing
   │   ├── validation.py    # Input validation
   │   └── watch.py         # File watching for auto-conversion
   ├── mcp/                 # Model Context Protocol server and tools
   │   ├── __init__.py      # MCP package initialization
   │   ├── __main__.py      # MCP server entry point
   │   ├── config.py        # MCP configuration
   │   ├── document_tools.py # Document conversion tools
   │   ├── schemas.py       # MCP schema definitions
   │   ├── security.py      # MCP security utilities
   │   ├── server.py        # MCP server implementation
   │   └── tools.py         # MCP tool definitions
   ├── options/             # Format-specific options dataclasses
   ├── parsers/             # Input format → AST converters
   ├── renderers/           # AST → output format renderers
   ├── transforms/          # AST transform pipeline and registry
   ├── utils/               # Shared utilities (attachments, metadata, security, etc.)
   ├── __init__.py         # Public API exports
   ├── __main__.py         # Entry point for CLI (python -m all2md)
   ├── api.py              # Core conversion functions
   ├── constants.py        # Default values and configuration
   ├── converter_metadata.py # Metadata and dependency management
   ├── converter_registry.py # Registry system for converters
   ├── dependencies.py     # Dependency checking utilities
   ├── exceptions.py       # Custom exception hierarchy
   ├── logging_utils.py    # Logging configuration
   └── progress.py         # Progress callback system

Primary Conversion Functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The library provides several core conversion functions in ``api.py``. The ``to_markdown()`` function is the primary convenience function for converting documents to Markdown:

.. code-block:: python

   def to_markdown(
       source: Union[str, Path, IO[bytes], bytes],
       *,
       parser_options: Optional[BaseParserOptions] = None,
       renderer_options: Optional[MarkdownRendererOptions] = None,
       source_format: DocumentFormat = "auto",
       flavor: Optional[str] = None,
       transforms: Optional[list] = None,
       hooks: Optional[dict] = None,
       progress_callback: Optional[ProgressCallback] = None,
       remote_input_options: Optional[RemoteInputOptions] = None,
       **kwargs: Any
   ) -> str:
       # 1. Format detection (if source_format="auto")
       # 2. Parse document to AST using appropriate parser
       # 3. Apply transforms to AST (if specified)
       # 4. Render AST to Markdown
       # 5. Return clean Markdown string

General Format Conversion
~~~~~~~~~~~~~~~~~~~~~~~~~~

For conversions between any supported formats (not just to Markdown), use the ``convert()`` function:

.. code-block:: python

   from all2md import convert
   from all2md.options import PdfOptions, MarkdownRendererOptions

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

See :doc:`python_api` for detailed examples of Markdown-to-DOCX/HTML/PDF conversions.

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

   # Direct conversion (simple)
   markdown = to_markdown('document.pdf')

   # AST conversion (advanced)
   doc_ast = to_ast('document.pdf')

   # Analyze structure using extract_nodes
   from all2md.ast.transforms import extract_nodes
   from all2md.ast.nodes import Heading

   headings = extract_nodes(doc_ast, Heading)
   print(f"Found {len(headings)} headings")

   # Transform AST
   from all2md.ast.transforms import HeadingLevelTransformer
   transformer = HeadingLevelTransformer(offset=1)
   transformed = transformer.transform(doc_ast)

   # Render to GitHub Flavored Markdown
   from all2md.options import MarkdownRendererOptions
   renderer = MarkdownRenderer(options=MarkdownRendererOptions(flavor="gfm"))
   gfm_markdown = renderer.render_to_string(transformed)

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

For complete AST documentation, see :doc:`ast_guide`. For bidirectional conversion examples (Markdown to DOCX/HTML/PDF), see :doc:`python_api`.

Converter Architecture
~~~~~~~~~~~~~~~~~~~~~~

The library uses a **registry-based architecture** with class-based parsers and renderers:

**Parser Classes**

All parsers extend ``BaseParser`` and implement the ``parse()`` method to convert documents to AST:

.. code-block:: python

   from all2md.parsers.base import BaseParser
   from all2md.ast import Document
   from all2md.options.base import BaseParserOptions

   class CustomParser(BaseParser):
       """Parser for a custom document format."""

       def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
           """Parse input document into AST representation.

           1. Validate and normalize input
           2. Load document using format-specific library
           3. Extract metadata
           4. Build AST from document structure
           5. Return Document node
           """
           # Implementation here
           return Document(children=[...])

       def extract_metadata(self, document: Any) -> DocumentMetadata:
           """Extract format-specific metadata."""
           # Implementation here
           return DocumentMetadata(...)

**Converter Registration**

Each parser module registers itself with ``ConverterMetadata`` that describes its capabilities:

.. code-block:: python

   from all2md.converter_metadata import ConverterMetadata

   CONVERTER_METADATA = ConverterMetadata(
       format_name="pdf",
       extensions=[".pdf"],
       mime_types=["application/pdf"],
       magic_bytes=[(b"%PDF", 0)],
       parser_class=PdfToAstConverter,
       renderer_class="all2md.renderers.pdf.PdfRenderer",
       parser_options_class="PdfOptions",
       renderer_options_class="PdfRendererOptions",
       parser_required_packages=[("pymupdf", "fitz", ">=1.26.4")],
       renderer_required_packages=[("reportlab", "reportlab", ">=4.0.0")],
   )

**Dynamic Discovery**

The ``ConverterRegistry`` automatically discovers and registers converters at runtime:

.. code-block:: python

   from all2md.converter_registry import registry

   # Auto-discover converters from parsers/ and renderers/ directories
   registry.auto_discover()

   # Get parser for a format
   parser_class = registry.get_parser("pdf")
   parser = parser_class(options=PdfOptions(...))
   ast_doc = parser.parse("document.pdf")

   # Get renderer for output format
   renderer_class = registry.get_renderer("docx")
   renderer = renderer_class(options=DocxRendererOptions(...))
   output = renderer.render(ast_doc)

This registry-based design enables:

* **Pluggable architecture**: Add new formats via entry points without modifying core code
* **Priority-based selection**: Multiple converters can register for the same format with different priorities
* **Lazy loading**: Converters are only imported when needed
* **Dynamic capability detection**: Check format support at runtime based on available dependencies

Options System
--------------

Hierarchical Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~

Options are expressed as frozen dataclasses so configurations are explicit, type safe, and composable. Each converter builds on three layers:

1. **``BaseParserOptions``** shared fields (metadata extraction, attachment limits)
2. **Mixins and nested helpers** such as ``AttachmentOptionsMixin``, ``NetworkFetchOptions``, and ``LocalFileAccessOptions`` that add security controls for binary assets
3. **Format-specific parser options** (``PdfOptions``, ``HtmlOptions``, ``ZipOptions``…) paired with renderer configuration like ``MarkdownRendererOptions`` via the ``renderer_options`` argument

.. code-block:: python

   from all2md import to_markdown
   from all2md.options import HtmlOptions, MarkdownRendererOptions, NetworkFetchOptions

   html_network = NetworkFetchOptions(
       allow_remote_fetch=False,
       require_https=True,
       allowed_hosts=["docs.example.com"],
   )

   html_options = HtmlOptions(
       extract_title=True,
       network=html_network,
   )

   markdown_defaults = MarkdownRendererOptions(
       emphasis_symbol="_",
       flavor="gfm",
   )

   hardened_markdown = to_markdown(
       "page.html",
       parser_options=html_options,
       renderer_options=markdown_defaults.create_updated(link_style="reference"),
   )

   secure_variant = html_options.create_updated(strip_dangerous_elements=True)

All CLI flags are generated from these dataclasses (nesting included), so ``HtmlOptions.network.require_https`` maps to ``--html-network-require-https`` and also honours the ``ALL2MD_HTML_NETWORK_REQUIRE_HTTPS`` environment variable. See :doc:`options` for the full reference and :doc:`environment_variables` for naming rules.

Flexible Option Merging
~~~~~~~~~~~~~~~~~~~~~~~

Options can be provided in multiple ways and are merged intelligently:

.. code-block:: python

   # Method 1: Pre-configured options object
   options = PdfOptions(pages=[0, 1, 2], attachment_mode='download')
   markdown = to_markdown('doc.pdf', parser_options=options)

   # Method 2: Keyword arguments (creates options object)
   markdown = to_markdown('doc.pdf', pages=[0, 1, 2], attachment_mode='download')

   # Method 3: Mixed (kwargs override options)
   markdown = to_markdown('doc.pdf', parser_options=options, attachment_mode='base64')

The merger prioritises keyword arguments over pre-configured options, allowing flexible overrides. CLI flags, presets, configuration files, and environment variables all feed into the same dataclasses, ensuring consistent behaviour regardless of entrypoint.

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
       pages="1-3",                        # Process specific pages
       table_detection_mode="both",        # Use PyMuPDF + ruling detection
       enable_table_fallback_detection=True,
       detect_columns=True,
       auto_trim_headers_footers=True,
       attachment_mode='download',         # Download images locally
       attachment_output_dir='./images'
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
       include_comments=True,              # Include review comments
       include_footnotes=True,             # Keep footnotes/endnotes
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

**Technology:** BeautifulSoup4 for robust HTML parsing, httpx for secure HTTP requests, optional readability-lxml for article extraction

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
   markdown = to_markdown("webpage.html", parser_options=secure_options)

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

   markdown = to_markdown("document.pdf", progress_callback=my_progress_handler)

Progress Event Types
~~~~~~~~~~~~~~~~~~~~~

The ``ProgressEvent`` dataclass includes:

* **started** - Conversion has begun
* **item_done** - An item/page/section has been processed
* **detected** - A structure was detected (e.g., table, column)
* **finished** - Conversion completed successfully
* **error** - An error occurred during processing

.. code-block:: python

   @dataclass
   class ProgressEvent:
       event_type: Literal["started", "item_done", "detected", "finished", "error"]
       message: str
       current: int = 0      # Current progress position
       total: int = 0        # Total items to process
       metadata: dict = {}   # Event-specific data

.. note::

   Legacy event types ``"page_done"`` and ``"table_detected"`` are deprecated but still supported for backwards compatibility. Use ``"item_done"`` and ``"detected"`` instead

Event-Specific Handling
~~~~~~~~~~~~~~~~~~~~~~~

Different event types provide different metadata:

.. code-block:: python

   def detailed_handler(event: ProgressEvent):
       if event.event_type == "started":
           print(f"Starting: {event.message}")

       elif event.event_type == "item_done":
           item = event.metadata.get('item_type', 'step')
           print(f"  {item.title()} {event.current}/{event.total} complete")

       elif event.event_type == "detected":
           detection_type = event.metadata.get('detected_type', 'structure')
           print(f"  Detected {detection_type}: {event.message}")

       elif event.event_type == "finished":
           print(f"Complete: {event.message}")

       elif event.event_type == "error":
           error = event.metadata.get('error', 'Unknown')
           print(f"  ERROR: {error}")

   markdown = to_markdown("large_document.pdf", progress_callback=detailed_handler)

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
           return to_markdown(filepath, progress_callback=self.progress_callback)

Error Handling in Callbacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Progress callbacks are fail-safe - exceptions in the callback are caught and logged without interrupting conversion:

.. code-block:: python

   def potentially_failing_callback(event: ProgressEvent):
       # Even if this raises an exception, conversion continues
       risky_operation(event)

   # Conversion will complete successfully even if callback fails
   markdown = to_markdown("document.pdf", progress_callback=potentially_failing_callback)

API Support
~~~~~~~~~~~

All conversion functions support progress callbacks:

.. code-block:: python

   from all2md import to_markdown, to_ast, convert, from_markdown

   # All support the progress_callback parameter
   markdown = to_markdown("doc.pdf", progress_callback=callback)
   ast_doc = to_ast("doc.pdf", progress_callback=callback)
   convert("doc.pdf", "output.docx", progress_callback=callback)
   from_markdown("input.md", "html", progress_callback=callback)

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
       raise DependencyError("pdf", [("pymupdf", ">=1.23.0")])

   # Word converter
   try:
       from docx import Document
   except ImportError:
       raise DependencyError("docx", [("python-docx", ">=1.2.0"])

This allows partial installations and clear error messages for missing dependencies. See :doc:`installation` for complete dependency installation instructions.

.. todo: improve the following section by improving the get_missing_dependencies command.

Programmatic Dependency Management
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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


**Dynamic Format Discovery with Converter Registry:**

The ``ConverterRegistry`` provides dynamic awareness of registered parsers and renderers, including their dependencies and capabilities:

.. code-block:: python

   """
   Application that adapts based on available formats using the converter registry.
   """
   from all2md import to_markdown
   from all2md.converter_registry import registry

   class DocumentConverter:
       """Converter that dynamically detects format support via the registry."""

       def __init__(self):
           # Discover all registered converters
           registry.auto_discover()
           self.supported_formats = self._detect_formats()

       def _detect_formats(self):
           """Detect which formats have available dependencies."""
           available_formats = []

           # Get all registered formats
           for format_name in registry.list_formats():
               # Check if dependencies are available
               missing = registry.check_dependencies(format_name, operation="parse")
               if not missing:
                   available_formats.append(format_name)

           return available_formats

       def get_format_info(self, format_name: str):
           """Get detailed information about a format."""
           metadata_list = registry.get_format_info(format_name)
           if not metadata_list:
               return None

           # Return info from highest priority converter
           metadata = metadata_list[0]
           return {
               'extensions': metadata.extensions,
               'mime_types': metadata.mime_types,
               'has_parser': metadata.parser_class is not None,
               'has_renderer': metadata.renderer_class is not None,
           }

       def convert(self, filepath, format='auto'):
           """Convert file with dynamic format detection and fallback handling."""
           if format != 'auto':
               # Check if explicitly requested format is available
               if format not in self.supported_formats:
                   missing = registry.check_dependencies(format, operation="parse")
                   if missing:
                       missing_pkgs = ', '.join(missing[format])
                       raise ValueError(
                           f"Format '{format}' requires missing dependencies: {missing_pkgs}. "
                           f"Available formats: {', '.join(self.supported_formats)}"
                       )

           return to_markdown(filepath, source_format=format)

   # Usage
   converter = DocumentConverter()
   print(f"Supported formats: {', '.join(converter.supported_formats)}")

   # Check specific format availability
   if 'pdf' in converter.supported_formats:
       result = converter.convert('document.pdf')
       print("PDF conversion successful")
   else:
       print("PDF support not available - install with: pip install all2md[pdf]")

   # Get format details
   pdf_info = converter.get_format_info('pdf')
   if pdf_info:
       print(f"PDF extensions: {pdf_info['extensions']}")
       print(f"PDF MIME types: {pdf_info['mime_types']}")

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

   from all2md.options import BaseParserOptions, MarkdownRendererOptions

   @dataclass
   class NewFormatOptions(BaseParserOptions):
       custom_setting: bool = True

   @dataclass
   class NewFormatRendererOptions(MarkdownRendererOptions):
       enable_custom_feature: bool = False

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

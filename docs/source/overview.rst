Library Overview
================

all2md is a comprehensive yet lightweight document conversion library optimized for modern workflows, particularly LLM preprocessing and document analysis pipelines. This page covers the design principles and core capabilities from a *user's* perspective.

.. note::

   Looking for internals — data flow, the converter registry, AST node hierarchy, extension points, testing, and performance design? See :doc:`architecture`.

Design Philosophy
-----------------

Lightweight by Default
~~~~~~~~~~~~~~~~~~~~~~~

all2md uses optional dependencies to keep the base installation minimal. Only install what you need:

* **Base installation**: ~5MB (HTML, text, CSV support)
* **Full installation**: ~50MB (all formats)
* **Selective installation**: Choose only the formats you use

See :doc:`installation` for the complete list of extras.

Intelligent Format Detection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The library uses a multi-layered format detection strategy:

1. **Filename extension analysis** (most reliable)
2. **MIME type detection** (secondary verification)
3. **Content-based magic bytes** (for file objects without names)
4. **Fallback to plain text** (graceful degradation)

This ensures accurate conversion even when file extensions are missing or incorrect.

Consistent API Design
~~~~~~~~~~~~~~~~~~~~~~~

All conversions use the same simple interface:

.. code-block:: python

   from all2md import to_markdown

   # Works for any supported format
   markdown = to_markdown(input_file, parser_options=format_options)

Format-specific complexity is handled internally while maintaining API consistency.

Converting Documents
--------------------

Primary Conversion Functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The library provides several core conversion functions in ``api.py``. The ``to_markdown()`` function is the primary convenience function for converting documents to Markdown:

.. code-block:: python

   def to_markdown(
       source: Union[str, Path, IO[bytes], bytes, Document],
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
~~~~~~~~~~~~~~~~~~~~~~~~~~~

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

Format Detection
~~~~~~~~~~~~~~~~~

Detection runs in priority order to ensure accurate format identification:

1. **Explicit hint**: When format is explicitly specified, bypass detection
2. **Filename extension**: Analyze file extension for immediate format identification
3. **MIME type detection**: Use ``mimetypes.guess_type()`` for secondary verification
4. **Magic bytes/content detectors**: Examine file headers and content patterns for files without reliable names
5. **Fallback to plain text**: Graceful degradation when no specific format is detected

You can use the ``list-formats`` CLI command to explore which formats are supported and check which dependencies are available in your environment:

.. code-block:: bash

   # List all supported formats with their status
   all2md list-formats

   # Show details about a specific format
   all2md list-formats pdf

   # Show only formats with available dependencies
   all2md list-formats --available-only

This is particularly useful when diagnosing format detection issues or verifying that required dependencies are installed. See :doc:`troubleshooting` for common detection issues, and :doc:`architecture` for how the registry-based detection system works internally.

Working with the AST
~~~~~~~~~~~~~~~~~~~~~~

all2md parses every document into an Abstract Syntax Tree (AST) before rendering. Going through the AST directly (instead of straight to Markdown) enables:

* **Advanced document analysis**: Extract structure, count elements, generate statistics
* **Programmatic transformation**: Modify documents before rendering
* **Multiple output formats**: Render the same AST to different Markdown flavors or to DOCX/HTML/PDF
* **Persistent storage**: Save/load document structure as JSON

**Two Conversion Paths:**

1. **Direct Path**: ``to_markdown()`` — Document → Markdown (faster, simpler)
2. **AST Path**: ``to_ast()`` — Document → AST → Markdown (flexible, powerful)

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

   # Render to GitHub Flavored Markdown
   from all2md.options import MarkdownRendererOptions
   renderer = MarkdownRenderer(options=MarkdownRendererOptions(flavor="gfm"))
   gfm_markdown = renderer.render_to_string(doc_ast)

For the complete node hierarchy and traversal/transformation APIs, see :doc:`ast_guide`. For the architectural picture of how parsing, the AST, and rendering fit together, see :doc:`architecture`.

Format-Specific Capabilities
----------------------------

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
       attachment_mode='save',         # Download images locally
       attachment_output_dir='./images'
   )

Word Documents (DOCX)
~~~~~~~~~~~~~~~~~~~~~~

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
       max_asset_size_bytes=2 * 1024 * 1024,  # 2MB cap per asset
       network=NetworkFetchOptions(
           allow_remote_fetch=True,       # Enable remote fetching
           allowed_hosts=["example.com", "cdn.example.com"],  # Whitelist specific hosts
           require_https=True,            # Force HTTPS for all requests
           network_timeout=5.0,           # 5-second timeout
       ),
       attachment_mode="save",
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
- **Size limits**: Prevent DoS via large downloads with ``max_asset_size_bytes``
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

For the full matrix of supported input/output formats and their dependencies, see :doc:`formats`.

Configuring Conversions
-----------------------

Options are expressed as frozen dataclasses so configurations are explicit, type safe, and composable. Pass a format-specific parser options object (plus an optional renderer options object) to any conversion function:

.. code-block:: python

   from all2md import to_markdown
   from all2md.options import HtmlOptions, MarkdownRendererOptions, NetworkFetchOptions

   html_options = HtmlOptions(
       extract_title=True,
       network=NetworkFetchOptions(
           allow_remote_fetch=False,
           require_https=True,
           allowed_hosts=["docs.example.com"],
       ),
   )

   markdown = to_markdown(
       "page.html",
       parser_options=html_options,
       renderer_options=MarkdownRendererOptions(emphasis_symbol="_", flavor="gfm"),
   )

Options can also be provided as keyword arguments, which are merged with (and override) a pre-configured options object:

.. code-block:: python

   # Method 1: Pre-configured options object
   options = PdfOptions(pages=[0, 1, 2], attachment_mode='save')
   markdown = to_markdown('doc.pdf', parser_options=options)

   # Method 2: Keyword arguments (creates options object)
   markdown = to_markdown('doc.pdf', pages=[0, 1, 2], attachment_mode='save')

   # Method 3: Mixed (kwargs override options)
   markdown = to_markdown('doc.pdf', parser_options=options, attachment_mode='base64')

All CLI flags are generated from these dataclasses (nesting included), so ``HtmlOptions.network.require_https`` maps to ``--html-network-require-https`` and also honours the ``ALL2MD_HTML_NETWORK_REQUIRE_HTTPS`` environment variable.

* :doc:`options` — the complete option reference for every format
* :doc:`configuration` — config files, presets, and precedence rules
* :doc:`environment_variables` — environment-variable naming conventions
* :doc:`architecture` — the options hierarchy and how the cascade is implemented

Error Handling and Recovery
---------------------------

Exception Hierarchy
~~~~~~~~~~~~~~~~~~~

.. code-block:: text

   All2MdError (base)
   ├── ValidationError
   │   ├── InvalidOptionsError
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
   │   ├── ZipFileSecurityError
   │   └── ArchiveSecurityError
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

Each format's third-party packages are isolated behind an optional extra, so partial installations work and missing dependencies produce a clear ``DependencyError`` with the exact install command. See :doc:`installation` for the full list of extras.

For automated setups, all2md can also report dependency state programmatically (``check_all_dependencies``, ``get_missing_dependencies``, ``generate_install_command``) and introspect the converter registry at runtime — see :doc:`architecture` for those APIs.

Extending all2md
----------------

all2md's registry-based architecture makes it straightforward to add new formats, renderers, and transforms via Python entry points — without modifying core code. The extension points (custom parsers, custom renderers, custom transforms, and element hooks) are documented in :doc:`architecture`, with a step-by-step walkthrough in :doc:`plugins`.

Integration Patterns
--------------------

all2md drops into batch pipelines and web services with a few lines of code.
Rather than duplicate them here, see the dedicated guides:

* :doc:`recipes` — batch directory processing, parallelism, and error handling
* :doc:`integrations` — Flask, FastAPI, Django, and AWS Lambda examples
* :doc:`cli` — the complete command-line batch/watch/bundle options

This overview covers all2md's user-facing capabilities. For specific format examples see the :doc:`formats` guide, for complete configuration options visit the :doc:`options` reference, and for the system's internal design see :doc:`architecture`.

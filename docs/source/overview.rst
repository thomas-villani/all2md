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
   │   ├── actions.py       # Core CLI actions and commands
   │   ├── builder.py       # Argument parser construction
   │   └── processors.py    # File processing and batch operations
   ├── converters/          # Format-specific conversion modules
   │   ├── __init__.py
   │   ├── pdf2markdown.py
   │   ├── docx2markdown.py
   │   ├── html2markdown.py
   │   ├── eml2markdown.py
   │   ├── pptx2markdown.py
   │   ├── ipynb2markdown.py
   │   ├── epub2markdown.py
   │   ├── odf2markdown.py
   │   ├── mhtml2markdown.py
   │   ├── rtf2markdown.py
   │   └── spreadsheet2markdown.py
   └── utils/               # Shared utilities
       ├── __init__.py
       ├── inputs.py        # Input validation and handling
       ├── attachments.py   # Image and attachment processing
       ├── metadata.py      # Document metadata extraction
       ├── security.py      # Security utilities
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

Format Detection Pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~

The library uses a registry-based detection system (``ConverterRegistry.detect_format``) that employs multiple detection strategies in priority order to ensure accurate format identification:

1. **Explicit hint**: When format is explicitly specified, bypass detection
2. **Filename extension**: Analyze file extension for immediate format identification
3. **MIME type detection**: Use ``mimetypes.guess_type()`` for secondary verification
4. **Magic bytes/content detectors**: Examine file headers and content patterns for files without reliable names
5. **Fallback to plain text**: Graceful degradation when no specific format is detected

This registry-based approach maximizes accuracy while providing graceful degradation for edge cases. Each converter registers its supported extensions, MIME types, and content detection patterns with the central registry, making the system easily extensible for new formats.

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

   from all2md import PdfOptions

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

   from all2md import DocxOptions

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

HTML processing includes sophisticated network security features to prevent SSRF attacks and control remote resource access:

.. code-block:: python

   from all2md import HtmlOptions

   # Secure configuration for web applications
   secure_options = HtmlOptions(
       allow_remote_fetch=True,           # Enable remote fetching
       allowed_hosts=["example.com", "cdn.example.com"],  # Whitelist specific hosts
       require_https=True,                # Force HTTPS for all requests
       network_timeout=5.0,               # 5-second timeout
       max_image_size_bytes=2 * 1024 * 1024,  # 2MB image limit
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
   markdown = to_markdown("webpage.html", allow_remote_fetch=True)  # Still blocked

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

.. code-block:: python

   MarkdownConversionError        # Base conversion error
   ├── FormatError               # Unsupported format
   ├── InputError                # Invalid input parameters
   └── ImportError               # Missing dependencies

Graceful Degradation
~~~~~~~~~~~~~~~~~~~~

The library handles errors gracefully:

.. code-block:: python

   try:
       markdown = to_markdown('document.pdf')
   except ImportError as e:
       print(f"Missing dependency: {e}")
       print("Install with: pip install all2md[pdf]")
   except MarkdownConversionError as e:
       print(f"Conversion failed: {e}")
       # Fallback to text extraction or alternative processing

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

This allows partial installations and clear error messages for missing dependencies.

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

The architecture makes it straightforward to add new formats:

1. Create converter module in ``converters/``
2. Add format detection logic
3. Create options dataclass
4. Register in main entry point

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
-------------------

Batch Processing
~~~~~~~~~~~~~~~~

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
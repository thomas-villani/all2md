Configuration Options
=====================

This reference documents all configuration options available in all2md. Options are organized by dataclass and control conversion behavior for different document formats.

.. contents::
   :local:
   :depth: 2

Overview
--------

all2md uses dataclass-based configuration to provide type-safe, well-documented options for each conversion module. Each converter has its own options class, plus shared classes for common functionality.

Options Hierarchy
~~~~~~~~~~~~~~~~~~

The all2md options system uses a clear inheritance structure that separates universal settings from format-specific configurations:

.. code-block:: text

   BaseOptions (universal attachment/metadata options)
   ├── PdfOptions (PDF-specific options)
   ├── DocxOptions (Word document options)
   ├── HtmlOptions (HTML conversion options)
   ├── PptxOptions (PowerPoint options)
   ├── EmlOptions (Email processing options)
   ├── RtfOptions (Rich Text Format options)
   ├── IpynbOptions (Jupyter Notebook options)
   ├── OdfOptions (OpenDocument options)
   ├── EpubOptions (EPUB e-book options)
   ├── MhtmlOptions (MHTML web archive options)
   └── SpreadsheetOptions (Excel/CSV/TSV options)

   MarkdownOptions (common Markdown formatting - used by all format options)

**How it works:**

1. **BaseOptions** provides universal settings that all converters use, including:

   - Attachment handling (``attachment_mode``, ``attachment_output_dir``)
   - Metadata extraction (``extract_metadata``)
   - Network security settings (``max_download_bytes``)

2. **Format-specific Options** (e.g., ``PdfOptions``, ``HtmlOptions``) inherit from ``BaseOptions`` and add their own specialized settings:

   - PDF: page selection, header detection, table parsing
   - HTML: content sanitization, network security
   - PowerPoint: slide numbering, notes inclusion

3. **MarkdownOptions** contains common Markdown formatting settings and can be embedded in any format-specific options via the ``markdown_options`` field:

   - Text formatting (emphasis symbols, bullet styles)
   - Special character handling

**Options Merging Logic:**

When you pass both an ``options`` object and individual ``**kwargs`` to ``to_markdown()``, the kwargs override the options object settings. This allows you to use a base configuration and selectively override specific values.

Using Options
~~~~~~~~~~~~~

**Python API:**

.. code-block:: python

   from all2md import to_markdown, PdfOptions, MarkdownOptions

   # Create custom Markdown formatting
   md_options = MarkdownOptions(
       emphasis_symbol="_",
       bullet_symbols="•◦▪"
   )

   # Create PDF-specific options
   pdf_options = PdfOptions(
       pages=[0, 1, 2],
       attachment_mode="download",
       markdown_options=md_options
   )

   # Convert with options
   result = to_markdown("document.pdf", options=pdf_options)

**Command Line Interface:**

.. code-block:: bash

   # Options map to CLI arguments with prefixes
   all2md document.pdf --pdf-pages "1,2,3" --attachment-mode download --markdown-emphasis-symbol "_"

**Environment Variables:**

All CLI options also support environment variable defaults. Use the pattern ``ALL2MD_<OPTION_NAME>`` where option names are converted to uppercase with hyphens and dots replaced by underscores:

.. code-block:: bash

   # Set defaults via environment variables
   export ALL2MD_ATTACHMENT_MODE="download"
   export ALL2MD_PDF_PAGES="1,2,3"
   export ALL2MD_MARKDOWN_EMPHASIS_SYMBOL="_"

   # CLI arguments override environment variables
   all2md document.pdf  # Uses environment defaults

See the :doc:`cli` reference for complete environment variable documentation.

Boolean Options Quick Reference
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Many options are boolean flags that default to ``True``. In code, you set them directly. On the CLI, you use the ``--<prefix>-no-<option>`` pattern to **disable** them.

**Common Boolean Options Cheat Sheet:**

.. list-table::
   :header-rows: 1
   :widths: 30 15 25 30

   * - Option Field (Python)
     - Default
     - CLI Flag to Enable
     - CLI Flag to Disable
   * - ``MarkdownOptions.use_hash_headings``
     - ``True``
     - (default)
     - ``--markdown-no-use-hash-headings``
   * - ``PdfOptions.detect_columns``
     - ``True``
     - (default)
     - ``--pdf-no-detect-columns``
   * - ``PdfOptions.merge_hyphenated_words``
     - ``True``
     - (default)
     - ``--pdf-no-merge-hyphenated-words``
   * - ``PdfOptions.enable_table_fallback_detection``
     - ``True``
     - (default)
     - ``--pdf-no-enable-table-fallback-detection``
   * - ``HtmlOptions.detect_table_alignment``
     - ``True``
     - (default)
     - ``--html-no-detect-table-alignment``
   * - ``HtmlOptions.preserve_nested_structure``
     - ``True``
     - (default)
     - ``--html-no-preserve-nested-structure``
   * - ``PptxOptions.include_notes``
     - ``True``
     - (default)
     - ``--pptx-no-include-notes``
   * - ``EmlOptions.include_headers``
     - ``True``
     - (default)
     - ``--eml-no-include-headers``
   * - ``EmlOptions.preserve_thread_structure``
     - ``True``
     - (default)
     - ``--eml-no-preserve-thread-structure``
   * - ``OdfOptions.preserve_tables``
     - ``True``
     - (default)
     - ``--odf-no-preserve-tables``
   * - ``EpubOptions.merge_chapters``
     - ``True``
     - (default)
     - ``--epub-no-merge-chapters``
   * - ``EpubOptions.include_toc``
     - ``True``
     - (default)
     - ``--epub-no-include-toc``

**Pattern Explanation:**

* **Python API**: Set boolean directly: ``PdfOptions(detect_columns=False)``
* **CLI Default=True**: Use ``--<prefix>-no-<field-name>`` to disable: ``--pdf-no-detect-columns``
* **CLI Default=False**: Use ``--<prefix>-<field-name>`` to enable (less common)

**Examples:**

.. code-block:: python

   # Python: Explicitly disable column detection
   from all2md import PdfOptions

   options = PdfOptions(
       detect_columns=False,
       merge_hyphenated_words=False,
       enable_table_fallback_detection=True  # Leave this enabled
   )

.. code-block:: bash

   # CLI: Disable column detection and hyphenation merging
   all2md document.pdf --pdf-no-detect-columns --pdf-no-merge-hyphenated-words

   # CLI: Disable hash headings (use underline style)
   all2md document.docx --markdown-no-use-hash-headings

   # CLI: Disable speaker notes in PowerPoint
   all2md presentation.pptx --pptx-no-include-notes

**Why the "no-" pattern?**

This pattern (called "negative flags" or "disable flags") is used because:

1. It makes the default behavior clear - the base flag name describes what's enabled by default
2. It follows Unix conventions (e.g., ``--no-color``, ``--no-verify``)
3. It prevents ambiguity - ``--pdf-detect-columns`` could mean "enable" or just state the option name

Shared Options Classes
----------------------

BaseOptions
~~~~~~~~~~~

Universal options inherited by all format-specific options classes.

.. autoclass:: all2md.options.BaseOptions
   :noindex:

**CLI Prefix:** (no prefix - universal options)

**Key Options:**

* ``attachment_mode``: How to handle images/attachments (skip, alt_text, download, base64)
* ``attachment_output_dir``: Directory for downloaded attachments
* ``extract_metadata``: Extract document metadata as YAML front matter


MarkdownOptions
~~~~~~~~~~~~~~~

Common Markdown formatting options used across all conversion modules.

.. autoclass:: all2md.options.MarkdownOptions
   :noindex:

**CLI Prefix:** ``--markdown-``

**Key Options:**

* ``use_hash_headings``: Use ``#`` syntax for headings instead of underlines (default: ``True``)

  - **CLI:** ``--markdown-no-use-hash-headings`` to disable (use underline-style headings)

**Example:**

.. code-block:: python

   from all2md.options import MarkdownOptions

   options = MarkdownOptions(
       escape_special=True,           # Escape Markdown special characters
       emphasis_symbol="*",           # Use asterisks for emphasis
       bullet_symbols="*-+",          # Bullet symbols for nested lists
       use_hash_headings=True,        # Use # syntax for headings (default)
       list_indent_width=4,           # Spaces per list level
       underline_mode="html",         # How to handle underlined text
       superscript_mode="html",       # How to handle superscript
       subscript_mode="html"          # How to handle subscript
   )


NetworkFetchOptions
~~~~~~~~~~~~~~~~~~~

Network security configuration for controlling remote resource fetching.

.. autoclass:: all2md.options.NetworkFetchOptions
   :noindex:

**Key Features:**

* **SSRF Protection:** Controls remote resource fetching to prevent server-side request forgery
* **Host Allowlisting:** Restrict fetching to specific trusted domains
* **HTTPS Enforcement:** Require secure connections for all remote requests
* **Size Limits:** Control maximum download size to prevent resource exhaustion
* **Timeout Controls:** Set network timeout limits

**Key Defaults:**

* ``max_remote_asset_bytes``: 20971520 (20MB) - Maximum size for remote asset downloads

**Example:**

.. code-block:: python

   from all2md.options import NetworkFetchOptions

   network_options = NetworkFetchOptions(
       allow_remote_fetch=True,          # Enable remote fetching
       allowed_hosts=["cdn.example.com", "images.example.org"],  # Trusted hosts only
       require_https=True,               # Force HTTPS
       network_timeout=10.0,             # 10 second timeout
       max_remote_asset_bytes=5*1024*1024  # 5MB max download (default: 20MB)
   )

.. note::

   List fields like ``allowed_hosts`` should be passed as Python lists in code. For CLI usage with multiple values, use JSON configuration files:

   .. code-block:: json

      {
        "html.network.allowed_hosts": ["cdn.example.com", "images.example.org"]
      }

   .. code-block:: bash

      all2md webpage.html --options-json config.json

LocalFileAccessOptions
~~~~~~~~~~~~~~~~~~~~~~

Local file system access configuration for controlling access to local files.

.. autoclass:: all2md.options.LocalFileAccessOptions
   :noindex:

**Key Features:**

* **Local File Control:** Enable/disable access to local files via file:// URLs
* **Directory Allowlisting:** Specify allowed/denied directories for local access
* **Working Directory Access:** Control access to current working directory
* **Security Boundaries:** Prevent unauthorized file system access

**Example:**

.. code-block:: python

   from all2md.options import LocalFileAccessOptions

   local_options = LocalFileAccessOptions(
       allow_local_files=True,           # Enable local file access
       local_file_allowlist=["/safe/dir", "/images"], # Allowed directories
       local_file_denylist=["/etc", "/home"],         # Blocked directories
       allow_cwd_files=True              # Allow current directory access
   )

Format-Specific Options
-----------------------

PdfOptions
~~~~~~~~~~

Configuration for PDF document conversion with advanced parsing features.

.. autoclass:: all2md.options.PdfOptions
   :noindex:

**CLI Prefix:** ``--pdf-``

**Key Features:**

* **Page Selection:** Convert specific pages or ranges
* **Header Detection:** Configurable header/footer detection with font size analysis
* **Layout Processing:** Multi-column detection and reading order
* **Table Detection:** Advanced table structure recognition
* **Image Handling:** Embedded image extraction and processing

**Example:**

.. code-block:: python

   from all2md.options import PdfOptions

   options = PdfOptions(
       pages=[0, 1, 2],                    # First 3 pages only
       password="secret",                  # For encrypted PDFs
       header_percentile_threshold=75,     # Top 25% font sizes as headers
       detect_columns=True,                # Multi-column layout
       enable_table_fallback_detection=True, # Heuristic table detection
       attachment_mode="base64"            # Embed images as base64
   )

DocxOptions
~~~~~~~~~~~

Configuration for Microsoft Word document conversion.

.. autoclass:: all2md.options.DocxOptions
   :noindex:

**CLI Prefix:** ``--docx-``

**Example:**

.. code-block:: python

   from all2md.options import DocxOptions

   options = DocxOptions(
       preserve_tables=True,           # Maintain table formatting
       attachment_mode="download",     # Download embedded images
       attachment_output_dir="./images"
   )

HtmlOptions
~~~~~~~~~~~

Configuration for HTML document conversion with security and network features.

.. autoclass:: all2md.options.HtmlOptions
   :noindex:

**CLI Prefix:** ``--html-``

**Key Features:**

* **Content Security:** Strip dangerous elements, control local file access
* **Network Security:** SSRF protection, allowed hosts, HTTPS requirements
* **Format Control:** Table alignment, nested structure preservation
* **URL Processing:** Base URL resolution for relative links

**Example:**

.. code-block:: python

   from all2md.options import HtmlOptions, NetworkFetchOptions, MarkdownOptions

   # Create MarkdownOptions for hash headings
   md_options = MarkdownOptions(use_hash_headings=True)

   options = HtmlOptions(
       extract_title=True,             # Extract HTML title
       strip_dangerous_elements=True,  # Remove script/style tags
       detect_table_alignment=True,    # Auto-detect table alignment (default)
       network=NetworkFetchOptions(
           allow_remote_fetch=False,   # Block network requests (SSRF protection)
           max_remote_asset_bytes=20*1024*1024  # 20MB default
       ),
       markdown_options=md_options,    # Pass Markdown formatting options
       attachment_mode="download"      # Download images locally
   )

.. note::

   **Deprecated Field:** The ``links_as`` field in ``HtmlOptions`` is deprecated and not used by the HTML converter. To control link style (inline vs reference), use ``MarkdownOptions.link_style`` instead:

   .. code-block:: python

      # Correct way to set link style
      md_opts = MarkdownOptions(link_style="reference")
      html_opts = HtmlOptions(markdown_options=md_opts)

      # Not used (deprecated)
      html_opts = HtmlOptions(links_as="reference")  # This has no effect

PptxOptions
~~~~~~~~~~~

Configuration for Microsoft PowerPoint presentation conversion.

.. autoclass:: all2md.options.PptxOptions
   :noindex:

**CLI Prefix:** ``--pptx-``

**Example:**

.. code-block:: python

   from all2md.options import PptxOptions

   options = PptxOptions(
       include_slide_numbers=True,     # Include slide numbers
       include_notes=True,             # Include speaker notes
       attachment_mode="base64"        # Embed images
   )

EmlOptions
~~~~~~~~~~

Configuration for email message processing with advanced parsing features.

.. autoclass:: all2md.options.EmlOptions
   :noindex:

**CLI Prefix:** ``--eml-``

**Key Features:**

* **Header Processing:** Configurable header inclusion and normalization
* **Thread Management:** Reply chain detection and structure preservation
* **URL Cleaning:** Remove security wrapper URLs from links
* **Date Formatting:** Multiple date format modes (ISO 8601, locale, custom)
* **HTML Conversion:** Optional HTML-to-Markdown conversion for HTML parts

**Example:**

.. code-block:: python

   from all2md.options import EmlOptions

   options = EmlOptions(
       include_headers=True,           # Include email headers
       date_format_mode="iso8601",     # ISO 8601 date format
       clean_quotes=True,              # Clean quoted content
       detect_reply_separators=True,   # Detect "On <date> wrote:" patterns
       clean_wrapped_urls=True,        # Remove URL defense wrappers
       url_wrappers=["safelinks.protection.outlook.com"],  # Custom URL wrapper patterns
       convert_html_to_markdown=True   # Convert HTML parts to Markdown
   )

.. note::

   For list fields like ``url_wrappers``, use JSON configuration for multiple custom patterns:

   .. code-block:: json

      {
        "eml.url_wrappers": [
          "safelinks.protection.outlook.com",
          "urldefense.com",
          "scanner.example.com"
        ]
      }

SpreadsheetOptions
~~~~~~~~~~~~~~~~~~

Configuration for Excel, CSV, and TSV file processing.

.. autoclass:: all2md.options.SpreadsheetOptions
   :noindex:

**CLI Prefix:** ``--spreadsheet-``

**Key Features:**

* **Multi-sheet Support:** Process specific sheets or all sheets in XLSX files
* **Size Limiting:** Configurable row and column limits for large datasets
* **Format Detection:** Automatic CSV/TSV dialect detection
* **Formula Handling:** Choose between stored values or formula display in XLSX

**Example:**

.. code-block:: python

   from all2md.options import SpreadsheetOptions

   options = SpreadsheetOptions(
       sheets=["Sheet1", "Data"],      # Process specific sheets
       include_sheet_titles=True,      # Add sheet name headers
       render_formulas=True,           # Use stored values (not formulas)
       max_rows=1000,                  # Limit rows per sheet
       max_cols=20,                    # Limit columns
       detect_csv_dialect=True         # Auto-detect CSV format
   )

Other Format Options
--------------------

RtfOptions
~~~~~~~~~~

Configuration for Rich Text Format documents.

.. autoclass:: all2md.options.RtfOptions
   :noindex:

**CLI Prefix:** ``--rtf-``

Currently inherits all options from BaseOptions without additional RTF-specific settings.

IpynbOptions
~~~~~~~~~~~~

Configuration for Jupyter Notebook conversion.

.. autoclass:: all2md.options.IpynbOptions
   :noindex:

**CLI Prefix:** ``--ipynb-``

**Key Options:**

* ``truncate_long_outputs``: Limit cell output length
* ``truncate_output_message``: Message to show when truncating

**Example:**

.. code-block:: python

   from all2md.options import IpynbOptions

   options = IpynbOptions(
       truncate_long_outputs=50,       # Limit to 50 lines
       truncate_output_message="... (output truncated) ...",
       attachment_mode="base64"        # Embed plots as base64
   )

OdfOptions
~~~~~~~~~~

Configuration for OpenDocument Text and Presentation files.

.. autoclass:: all2md.options.OdfOptions
   :noindex:

**CLI Prefix:** ``--odf-``

**Example:**

.. code-block:: python

   from all2md.options import OdfOptions

   options = OdfOptions(
       preserve_tables=True,           # Maintain table formatting
       attachment_mode="download"      # Download embedded images
   )

EpubOptions
~~~~~~~~~~~

Configuration for EPUB e-book processing.

.. autoclass:: all2md.options.EpubOptions
   :noindex:

**CLI Prefix:** ``--epub-``

**Example:**

.. code-block:: python

   from all2md.options import EpubOptions

   options = EpubOptions(
       merge_chapters=True,            # Continuous document
       include_toc=True,               # Generate table of contents
       attachment_mode="base64"        # Embed illustrations
   )

MhtmlOptions
~~~~~~~~~~~~

Configuration for MHTML web archive processing.

.. autoclass:: all2md.options.MhtmlOptions
   :noindex:

**CLI Prefix:** ``--mhtml-``

**Key Features:**

* **Local File Security:** Control access to local files via file:// URLs
* **Directory Allowlists:** Specify allowed/denied directories for local access

**Example:**

.. code-block:: python

   from all2md.options import MhtmlOptions

   options = MhtmlOptions(
       local_files=LocalFileAccessOptions(
           allow_local_files=False,    # Block local file access
           allow_cwd_files=True        # Allow current directory
       ),
       attachment_mode="download"      # Download embedded resources
   )

Advanced Usage
--------------

Combining Options
~~~~~~~~~~~~~~~~~

You can combine different option types for complex conversions:

.. code-block:: python

   from all2md import to_markdown
   from all2md.options import PdfOptions, MarkdownOptions

   # Custom Markdown formatting
   md_opts = MarkdownOptions(
       emphasis_symbol="_",
       bullet_symbols="•◦▪"
   )

   # PDF options with custom Markdown and page separators
   pdf_opts = PdfOptions(
       pages=[1, 2, 3, 4, 5],
       detect_columns=True,
       enable_table_fallback_detection=True,
       attachment_mode="download",
       attachment_output_dir="./pdf_images",
       page_separator_template="=== PAGE {page_num} ===",
       include_page_numbers=True,
       markdown_options=md_opts
   )

   result = to_markdown("complex_document.pdf", options=pdf_opts)

Security Configuration with Nested Options
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The new nested options structure provides better organization for security settings:

.. code-block:: python

   from all2md import to_markdown
   from all2md.options import HtmlOptions, NetworkFetchOptions, LocalFileAccessOptions

   # Configure network security
   network_opts = NetworkFetchOptions(
       allow_remote_fetch=True,
       allowed_hosts=["cdn.example.com", "images.example.org"],
       require_https=True,
       network_timeout=5.0,
       max_remote_asset_bytes=2*1024*1024  # 2MB limit
   )

   # Configure local file access
   local_opts = LocalFileAccessOptions(
       allow_local_files=False,  # Block local file access for security
       allow_cwd_files=True      # Allow current directory only
   )

   # HTML options with security configuration
   html_opts = HtmlOptions(
       extract_title=True,
       strip_dangerous_elements=True,
       network=network_opts,
       local_files=local_opts,
       attachment_mode="download",
       attachment_output_dir="./safe_downloads"
   )

   result = to_markdown("webpage.html", options=html_opts)

JSON Configuration
~~~~~~~~~~~~~~~~~~

Options can be loaded from JSON files for reusable configurations:

.. code-block:: json

   {
     "attachment_mode": "download",
     "attachment_output_dir": "./attachments",
     "markdown.emphasis_symbol": "_",
     "pdf.detect_columns": true,
     "pdf.pages": [1, 2, 3],
     "pdf.enable_table_fallback_detection": true,
     "html.strip_dangerous_elements": true,
     "html.network.allow_remote_fetch": false,
     "pptx.include_slide_numbers": true
   }

.. code-block:: bash

   # Use JSON configuration
   all2md document.pdf --options-json config.json

Immutable Options
~~~~~~~~~~~~~~~~~

All options classes are frozen dataclasses for thread safety. Use ``create_updated()`` to modify:

.. code-block:: python

   from all2md.options import PdfOptions

   # Original options
   options = PdfOptions(pages=[1, 2])

   # Create updated version
   new_options = options.create_updated(
       pages=[1, 2, 3, 4],
       attachment_mode="base64"
   )

   # Original options unchanged
   print(options.pages)      # [1, 2]
   print(new_options.pages)  # [1, 2, 3, 4]

JSON Configuration Deep Dive
-----------------------------

Complete JSON Configuration Examples
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

JSON configuration files provide a reusable way to specify complex options:

**Basic JSON Configuration:**

.. code-block:: json

   {
     "attachment_mode": "download",
     "attachment_output_dir": "./images",
     "extract_metadata": true,
     "markdown.emphasis_symbol": "_",
     "markdown.use_hash_headings": true
   }

.. code-block:: bash

   all2md document.pdf --options-json config.json

**Format-Specific Configuration:**

.. code-block:: json

   {
     "pdf.pages": [0, 1, 2, 3, 4],
     "pdf.detect_columns": true,
     "pdf.enable_table_fallback_detection": true,
     "pdf.merge_hyphenated_words": true,
     "attachment_mode": "base64"
   }

.. code-block:: bash

   all2md report.pdf --options-json pdf-config.json

Nested Options in JSON
~~~~~~~~~~~~~~~~~~~~~~~

Nested dataclass options use dot notation in JSON:

**Network Security Configuration:**

.. code-block:: json

   {
     "html.network.allow_remote_fetch": true,
     "html.network.allowed_hosts": ["cdn.example.com", "images.example.org"],
     "html.network.require_https": true,
     "html.network.network_timeout": 5.0,
     "html.network.max_remote_asset_bytes": 2097152
   }

**Local File Security Configuration:**

.. code-block:: json

   {
     "html.local_files.allow_local_files": false,
     "html.local_files.allow_cwd_files": true,
     "mhtml.local_files.local_file_allowlist": ["/safe/dir", "/public/images"],
     "mhtml.local_files.local_file_denylist": ["/etc", "/home"]
   }

**Combined Security Configuration:**

.. code-block:: json

   {
     "html.strip_dangerous_elements": true,
     "html.network.allow_remote_fetch": true,
     "html.network.allowed_hosts": ["trusted-cdn.com"],
     "html.network.require_https": true,
     "html.local_files.allow_local_files": false,
     "attachment_mode": "skip"
   }

Multi-Value Fields (Lists)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Lists like ``allowed_hosts`` or ``pages`` are specified as JSON arrays:

.. code-block:: json

   {
     "pdf.pages": [0, 1, 2, 3, 4, 5],
     "html.network.allowed_hosts": [
       "cdn.jsdelivr.net",
       "unpkg.com",
       "fonts.googleapis.com"
     ],
     "spreadsheet.sheets": ["Summary", "Data", "Analysis"],
     "eml.url_wrappers": [
       "safelinks.protection.outlook.com",
       "urldefense.com",
       "scanner.example.org"
     ]
   }

Complete Multi-Format Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A comprehensive configuration for multiple formats:

.. code-block:: json

   {
     "attachment_mode": "download",
     "attachment_output_dir": "./extracted_media",
     "extract_metadata": true,

     "markdown.emphasis_symbol": "_",
     "markdown.bullet_symbols": "•◦▪",
     "markdown.use_hash_headings": true,

     "pdf.detect_columns": true,
     "pdf.enable_table_fallback_detection": true,
     "pdf.merge_hyphenated_words": true,
     "pdf.header_percentile_threshold": 75,

     "html.strip_dangerous_elements": true,
     "html.detect_table_alignment": true,
     "html.network.allow_remote_fetch": true,
     "html.network.allowed_hosts": ["cdn.example.com"],
     "html.network.require_https": true,
     "html.local_files.allow_local_files": false,

     "docx.preserve_tables": true,

     "pptx.include_slide_numbers": true,
     "pptx.include_notes": true,

     "eml.include_headers": true,
     "eml.clean_quotes": true,
     "eml.convert_html_to_markdown": true,

     "spreadsheet.include_sheet_titles": true,
     "spreadsheet.max_rows": 1000,
     "spreadsheet.max_cols": 50
   }

Save this as ``comprehensive-config.json`` and use:

.. code-block:: bash

   all2md document.pdf --options-json comprehensive-config.json
   all2md webpage.html --options-json comprehensive-config.json
   all2md spreadsheet.xlsx --options-json comprehensive-config.json

Environment Variables Guide
----------------------------

Overview
~~~~~~~~

All CLI options can be set via environment variables using the pattern:

.. code-block:: text

   ALL2MD_<OPTION_NAME>

Where ``<OPTION_NAME>`` is the option with:

* Uppercase letters
* Hyphens and dots replaced by underscores
* Format prefixes included for format-specific options

Precedence Order
~~~~~~~~~~~~~~~~

Configuration values are resolved in this order (later overrides earlier):

1. **Environment variables** (lowest priority)
2. **JSON configuration files** (``--options-json``)
3. **Command-line arguments** (highest priority)

.. code-block:: bash

   # Environment variable sets default
   export ALL2MD_ATTACHMENT_MODE="base64"

   # JSON config overrides environment
   echo '{"attachment_mode": "download"}' > config.json

   # CLI argument overrides everything
   all2md doc.pdf --options-json config.json --attachment-mode skip
   # Result: attachment_mode = "skip"

Universal Options
~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Attachment handling
   export ALL2MD_ATTACHMENT_MODE="download"
   export ALL2MD_ATTACHMENT_OUTPUT_DIR="./images"
   export ALL2MD_ATTACHMENT_BASE_URL="https://example.com"

   # Metadata extraction
   export ALL2MD_EXTRACT_METADATA="true"

   # Format override
   export ALL2MD_FORMAT="pdf"

Markdown Options
~~~~~~~~~~~~~~~~

Use ``ALL2MD_MARKDOWN_`` prefix:

.. code-block:: bash

   export ALL2MD_MARKDOWN_EMPHASIS_SYMBOL="_"
   export ALL2MD_MARKDOWN_BULLET_SYMBOLS="•◦▪"
   export ALL2MD_MARKDOWN_USE_HASH_HEADINGS="true"
   export ALL2MD_MARKDOWN_ESCAPE_SPECIAL="false"
   export ALL2MD_MARKDOWN_LIST_INDENT_WIDTH="4"

PDF Options
~~~~~~~~~~~

Use ``ALL2MD_PDF_`` prefix:

.. code-block:: bash

   export ALL2MD_PDF_PAGES="0,1,2,3,4"
   export ALL2MD_PDF_DETECT_COLUMNS="true"
   export ALL2MD_PDF_ENABLE_TABLE_FALLBACK_DETECTION="true"
   export ALL2MD_PDF_MERGE_HYPHENATED_WORDS="true"
   export ALL2MD_PDF_HEADER_PERCENTILE_THRESHOLD="75"

HTML Options
~~~~~~~~~~~~

Use ``ALL2MD_HTML_`` prefix:

.. code-block:: bash

   export ALL2MD_HTML_STRIP_DANGEROUS_ELEMENTS="true"
   export ALL2MD_HTML_EXTRACT_TITLE="true"
   export ALL2MD_HTML_DETECT_TABLE_ALIGNMENT="true"

Nested Options (Network Security)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For nested dataclass options, extend the prefix with the nested field name:

.. code-block:: bash

   # HtmlOptions.network.* fields
   export ALL2MD_HTML_NETWORK_ALLOW_REMOTE_FETCH="true"
   export ALL2MD_HTML_NETWORK_ALLOWED_HOSTS="cdn.example.com,images.example.org"
   export ALL2MD_HTML_NETWORK_REQUIRE_HTTPS="true"
   export ALL2MD_HTML_NETWORK_NETWORK_TIMEOUT="10.0"
   export ALL2MD_HTML_NETWORK_MAX_REMOTE_ASSET_BYTES="5242880"

Nested Options (Local File Security)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # HtmlOptions.local_files.* fields
   export ALL2MD_HTML_LOCAL_FILES_ALLOW_LOCAL_FILES="false"
   export ALL2MD_HTML_LOCAL_FILES_ALLOW_CWD_FILES="true"
   export ALL2MD_HTML_LOCAL_FILES_LOCAL_FILE_ALLOWLIST="/safe/dir,/public"
   export ALL2MD_HTML_LOCAL_FILES_LOCAL_FILE_DENYLIST="/etc,/home"

Other Format Options
~~~~~~~~~~~~~~~~~~~~

**PowerPoint:**

.. code-block:: bash

   export ALL2MD_PPTX_INCLUDE_SLIDE_NUMBERS="true"
   export ALL2MD_PPTX_INCLUDE_NOTES="false"

**Email:**

.. code-block:: bash

   export ALL2MD_EML_INCLUDE_HEADERS="true"
   export ALL2MD_EML_CLEAN_QUOTES="true"
   export ALL2MD_EML_CONVERT_HTML_TO_MARKDOWN="true"
   export ALL2MD_EML_DATE_FORMAT_MODE="iso8601"

**Spreadsheet:**

.. code-block:: bash

   export ALL2MD_SPREADSHEET_INCLUDE_SHEET_TITLES="true"
   export ALL2MD_SPREADSHEET_MAX_ROWS="1000"
   export ALL2MD_SPREADSHEET_MAX_COLS="50"
   export ALL2MD_SPREADSHEET_RENDER_FORMULAS="true"

**Jupyter Notebooks:**

.. code-block:: bash

   export ALL2MD_IPYNB_TRUNCATE_LONG_OUTPUTS="100"
   export ALL2MD_IPYNB_TRUNCATE_OUTPUT_MESSAGE="... output truncated ..."

List-Valued Environment Variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For options that accept lists (like ``allowed_hosts`` or ``pages``), use comma-separated values:

.. code-block:: bash

   # Pages as comma-separated numbers
   export ALL2MD_PDF_PAGES="0,1,2,3,4,5"

   # Hosts as comma-separated domains
   export ALL2MD_HTML_NETWORK_ALLOWED_HOSTS="cdn.example.com,images.example.org,fonts.googleapis.com"

   # Sheets as comma-separated names
   export ALL2MD_SPREADSHEET_SHEETS="Summary,Data,Analysis"

   # File paths as comma-separated paths
   export ALL2MD_HTML_LOCAL_FILES_LOCAL_FILE_ALLOWLIST="/var/www/images,/opt/app/public"

Boolean Environment Variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Boolean values can be specified as:

* ``"true"``, ``"True"``, ``"1"``, ``"yes"``, ``"on"`` → ``True``
* ``"false"``, ``"False"``, ``"0"``, ``"no"``, ``"off"`` → ``False``

.. code-block:: bash

   # All equivalent ways to enable a boolean option
   export ALL2MD_HTML_STRIP_DANGEROUS_ELEMENTS="true"
   export ALL2MD_HTML_STRIP_DANGEROUS_ELEMENTS="True"
   export ALL2MD_HTML_STRIP_DANGEROUS_ELEMENTS="1"
   export ALL2MD_HTML_STRIP_DANGEROUS_ELEMENTS="yes"

   # All equivalent ways to disable a boolean option
   export ALL2MD_PDF_DETECT_COLUMNS="false"
   export ALL2MD_PDF_DETECT_COLUMNS="False"
   export ALL2MD_PDF_DETECT_COLUMNS="0"
   export ALL2MD_PDF_DETECT_COLUMNS="no"

Complete Environment Variable Example
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Production configuration via environment variables:

.. code-block:: bash

   #!/bin/bash
   # production-config.sh

   # Universal settings
   export ALL2MD_ATTACHMENT_MODE="skip"
   export ALL2MD_EXTRACT_METADATA="false"

   # Markdown formatting
   export ALL2MD_MARKDOWN_EMPHASIS_SYMBOL="_"
   export ALL2MD_MARKDOWN_USE_HASH_HEADINGS="true"

   # PDF processing
   export ALL2MD_PDF_DETECT_COLUMNS="true"
   export ALL2MD_PDF_ENABLE_TABLE_FALLBACK_DETECTION="true"
   export ALL2MD_PDF_MERGE_HYPHENATED_WORDS="true"

   # HTML security (strict)
   export ALL2MD_HTML_STRIP_DANGEROUS_ELEMENTS="true"
   export ALL2MD_HTML_NETWORK_ALLOW_REMOTE_FETCH="false"
   export ALL2MD_HTML_LOCAL_FILES_ALLOW_LOCAL_FILES="false"

   # PowerPoint
   export ALL2MD_PPTX_INCLUDE_SLIDE_NUMBERS="true"
   export ALL2MD_PPTX_INCLUDE_NOTES="false"

   # Now run all2md with these defaults
   all2md "$@"

Usage:

.. code-block:: bash

   # Source configuration
   source production-config.sh

   # Or use directly
   ./production-config.sh document.pdf --out output.md

Development vs Production Configurations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Development (permissive):**

.. code-block:: bash

   # dev-config.sh
   export ALL2MD_ATTACHMENT_MODE="download"
   export ALL2MD_ATTACHMENT_OUTPUT_DIR="./dev-images"
   export ALL2MD_HTML_NETWORK_ALLOW_REMOTE_FETCH="true"
   export ALL2MD_HTML_NETWORK_ALLOWED_HOSTS=""  # All hosts allowed
   export ALL2MD_HTML_LOCAL_FILES_ALLOW_LOCAL_FILES="true"
   export ALL2MD_EXTRACT_METADATA="true"

**Production (strict):**

.. code-block:: bash

   # prod-config.sh
   export ALL2MD_ATTACHMENT_MODE="skip"
   export ALL2MD_HTML_NETWORK_ALLOW_REMOTE_FETCH="false"
   export ALL2MD_HTML_LOCAL_FILES_ALLOW_LOCAL_FILES="false"
   export ALL2MD_HTML_STRIP_DANGEROUS_ELEMENTS="true"
   export ALL2MD_EXTRACT_METADATA="false"

   # Global network disable for safety
   export ALL2MD_DISABLE_NETWORK="1"

Docker Environment Example
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use environment variables in Docker:

.. code-block:: dockerfile

   # Dockerfile
   FROM python:3.12
   RUN pip install all2md[pdf,html,docx]

   # Set production defaults
   ENV ALL2MD_ATTACHMENT_MODE=skip
   ENV ALL2MD_HTML_NETWORK_ALLOW_REMOTE_FETCH=false
   ENV ALL2MD_HTML_STRIP_DANGEROUS_ELEMENTS=true

.. code-block:: bash

   # docker-compose.yml
   services:
     all2md:
       image: all2md:latest
       environment:
         - ALL2MD_ATTACHMENT_MODE=skip
         - ALL2MD_HTML_NETWORK_ALLOW_REMOTE_FETCH=false
         - ALL2MD_HTML_STRIP_DANGEROUS_ELEMENTS=true
       volumes:
         - ./documents:/documents

Debugging Configuration
~~~~~~~~~~~~~~~~~~~~~~~

Check which configuration values are active:

.. code-block:: bash

   # Show all ALL2MD_* environment variables
   env | grep ^ALL2MD_

   # Test with verbose output (if supported)
   all2md document.pdf --debug

   # Override for single invocation
   ALL2MD_ATTACHMENT_MODE=base64 all2md document.pdf

Migration Guide
---------------

Options Refactoring Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The all2md options system has been improved to provide better organization and reduce redundancy. Here's how to migrate from the old field names to the new structure:

Field Name Changes
^^^^^^^^^^^^^^^^^^

**PDF Options:**

.. code-block:: python

   # Old
   PdfOptions(table_fallback_detection=True)

   # New
   PdfOptions(enable_table_fallback_detection=True)

**PowerPoint Options:**

.. code-block:: python

   # Old
   PptxOptions(slide_numbers=True)

   # New
   PptxOptions(include_slide_numbers=True)

**Markdown Options - Page Separators:**

.. code-block:: python

   # Old (page separators in MarkdownOptions)
   MarkdownOptions(
       page_separator="-----",
       page_separator_format="Page {page_num}",
       include_page_numbers=True
   )

   # New (page separators moved to format-specific options)
   PdfOptions(
       page_separator_template="Page {page_num}",
       include_page_numbers=True
   )

   # For PowerPoint slides
   PptxOptions(
       page_separator_template="--- Slide {page_num} ---"
   )

Network Security Options
^^^^^^^^^^^^^^^^^^^^^^^^^

Network and local file security options are now organized in nested dataclasses:

.. code-block:: python

   # Old
   HtmlOptions(
       allow_remote_fetch=True,
       allowed_hosts=["example.com"],
       require_https=True,
       network_timeout=10.0,
       max_image_size_bytes=1024*1024
   )

   # New
   HtmlOptions(
       network=NetworkFetchOptions(
           allow_remote_fetch=True,
           allowed_hosts=["example.com"],
           require_https=True,
           network_timeout=10.0,
           max_remote_asset_bytes=1024*1024  # Renamed for clarity
       )
   )

**Local File Access:**

.. code-block:: python

   # Old
   MhtmlOptions(
       allow_local_files=False,
       local_file_allowlist=["/safe/dir"],
       local_file_denylist=["/etc"],
       allow_cwd_files=True
   )

   # New
   MhtmlOptions(
       local_files=LocalFileAccessOptions(
           allow_local_files=False,
           local_file_allowlist=["/safe/dir"],
           local_file_denylist=["/etc"],
           allow_cwd_files=True
       )
   )

**Email Size Limits:**

.. code-block:: python

   # Old
   EmlOptions(max_attachment_size_bytes=50*1024*1024)

   # New
   EmlOptions(max_email_attachment_bytes=50*1024*1024)

CLI Argument Changes
^^^^^^^^^^^^^^^^^^^^

Command-line arguments have been updated to reflect the new structure:

.. code-block:: bash

   # Old
   all2md document.pdf --pdf-table-fallback-detection
   all2md slides.pptx --pptx-slide-numbers
   all2md --markdown-page-separator "---" --markdown-include-page-numbers

   # New
   all2md document.pdf --pdf-enable-table-fallback-detection
   all2md slides.pptx --pptx-include-slide-numbers
   all2md --markdown-page-separator-template "--- Page {page_num} ---"

**Nested Options in CLI:**

.. code-block:: bash

   # CLI usage
   all2md webpage.html --html-network-allow-remote-fetch --html-network-require-https

Benefits of the New Structure
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* **Better Organization:** Related options are grouped together in logical dataclasses
* **Reduced Redundancy:** Eliminated duplicate fields across different option classes
* **Clearer Naming:** More consistent and descriptive field names
* **Enhanced Security:** Network and file access options are clearly separated
* **Improved CLI:** Arguments are properly grouped and easier to discover

For complete CLI usage examples, see the :doc:`cli` reference.
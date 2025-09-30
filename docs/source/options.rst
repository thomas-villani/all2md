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
   - Page separators and numbering
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
   all2md document.pdf --pdf-pages "0,1,2" --attachment-mode download --markdown-emphasis-symbol "_"

**Environment Variables:**

All CLI options also support environment variable defaults. Use the pattern ``ALL2MD_<OPTION_NAME>`` where option names are converted to uppercase with hyphens and dots replaced by underscores:

.. code-block:: bash

   # Set defaults via environment variables
   export ALL2MD_ATTACHMENT_MODE="download"
   export ALL2MD_PDF_PAGES="0,1,2"
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
       page_separator_template="-----", # Page separator template
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
       bullet_symbols="•◦▪",
       page_separator_template="=== PAGE {page_num} =="
   )

   # PDF options with custom Markdown
   pdf_opts = PdfOptions(
       pages=[0, 1, 2, 3, 4],
       detect_columns=True,
       enable_table_fallback_detection=True,
       attachment_mode="download",
       attachment_output_dir="./pdf_images",
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
     "pdf.pages": [0, 1, 2],
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
   options = PdfOptions(pages=[0, 1])

   # Create updated version
   new_options = options.create_updated(
       pages=[0, 1, 2, 3],
       attachment_mode="base64"
   )

   # Original options unchanged
   print(options.pages)      # [0, 1]
   print(new_options.pages)  # [0, 1, 2, 3]

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

   # Old
   MarkdownOptions(
       page_separator="-----",
       page_separator_format="Page {page_num}",
       include_page_numbers=True
   )

   # New
   MarkdownOptions(
       page_separator_template="Page {page_num}"  # Unified template
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
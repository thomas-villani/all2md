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

Base Options Classes
--------------------

MarkdownOptions
~~~~~~~~~~~~~~~

Common Markdown formatting options used across all conversion modules.

.. autoclass:: all2md.options.MarkdownOptions
   :members:
   :undoc-members:
   :show-inheritance:

**CLI Prefix:** ``--markdown-``

**Example:**

.. code-block:: python

   from all2md.options import MarkdownOptions

   options = MarkdownOptions(
       escape_special=True,           # Escape Markdown special characters
       emphasis_symbol="*",           # Use asterisks for emphasis
       bullet_symbols="*-+",          # Bullet symbols for nested lists
       page_separator="-----",        # Page separator text
       include_page_numbers=False,    # Include page numbers in separators
       list_indent_width=4,           # Spaces per list level
       underline_mode="html",         # How to handle underlined text
       superscript_mode="html",       # How to handle superscript
       subscript_mode="html"          # How to handle subscript
   )

BaseOptions
~~~~~~~~~~~

Universal options inherited by all format-specific options classes.

.. autoclass:: all2md.options.BaseOptions
   :members:
   :undoc-members:
   :show-inheritance:

**CLI Prefix:** (no prefix - universal options)

**Key Options:**

* ``attachment_mode``: How to handle images/attachments (skip, alt_text, download, base64)
* ``attachment_output_dir``: Directory for downloaded attachments
* ``extract_metadata``: Extract document metadata as YAML front matter

Format-Specific Options
------------------------

PdfOptions
~~~~~~~~~~

Configuration for PDF document conversion with advanced parsing features.

.. autoclass:: all2md.options.PdfOptions
   :members:
   :undoc-members:
   :show-inheritance:

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
       table_fallback_detection=True,      # Heuristic table detection
       attachment_mode="base64"            # Embed images as base64
   )

DocxOptions
~~~~~~~~~~~

Configuration for Microsoft Word document conversion.

.. autoclass:: all2md.options.DocxOptions
   :members:
   :undoc-members:
   :show-inheritance:

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
   :members:
   :undoc-members:
   :show-inheritance:

**CLI Prefix:** ``--html-``

**Key Features:**

* **Content Security:** Strip dangerous elements, control local file access
* **Network Security:** SSRF protection, allowed hosts, HTTPS requirements
* **Format Control:** Table alignment, nested structure preservation
* **URL Processing:** Base URL resolution for relative links

**Example:**

.. code-block:: python

   from all2md.options import HtmlOptions

   options = HtmlOptions(
       use_hash_headings=True,         # Use # syntax for headers
       extract_title=True,             # Extract HTML title
       strip_dangerous_elements=True,  # Remove script/style tags
       allow_remote_fetch=False,       # Block network requests (SSRF protection)
       attachment_mode="download"      # Download images locally
   )

PptxOptions
~~~~~~~~~~~

Configuration for Microsoft PowerPoint presentation conversion.

.. autoclass:: all2md.options.PptxOptions
   :members:
   :undoc-members:
   :show-inheritance:

**CLI Prefix:** ``--pptx-``

**Example:**

.. code-block:: python

   from all2md.options import PptxOptions

   options = PptxOptions(
       slide_numbers=True,             # Include slide numbers
       include_notes=True,             # Include speaker notes
       attachment_mode="base64"        # Embed images
   )

EmlOptions
~~~~~~~~~~

Configuration for email message processing with advanced parsing features.

.. autoclass:: all2md.options.EmlOptions
   :members:
   :undoc-members:
   :show-inheritance:

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
       convert_html_to_markdown=True   # Convert HTML parts to Markdown
   )

SpreadsheetOptions
~~~~~~~~~~~~~~~~~~

Configuration for Excel, CSV, and TSV file processing.

.. autoclass:: all2md.options.SpreadsheetOptions
   :members:
   :undoc-members:
   :show-inheritance:

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
   :members:
   :undoc-members:
   :show-inheritance:

**CLI Prefix:** ``--rtf-``

Currently inherits all options from BaseOptions without additional RTF-specific settings.

IpynbOptions
~~~~~~~~~~~~

Configuration for Jupyter Notebook conversion.

.. autoclass:: all2md.options.IpynbOptions
   :members:
   :undoc-members:
   :show-inheritance:

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
   :members:
   :undoc-members:
   :show-inheritance:

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
   :members:
   :undoc-members:
   :show-inheritance:

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
   :members:
   :undoc-members:
   :show-inheritance:

**CLI Prefix:** ``--mhtml-``

**Key Features:**

* **Local File Security:** Control access to local files via file:// URLs
* **Directory Allowlists:** Specify allowed/denied directories for local access

**Example:**

.. code-block:: python

   from all2md.options import MhtmlOptions

   options = MhtmlOptions(
       allow_local_files=False,        # Block local file access
       allow_cwd_files=True,           # Allow current directory
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
       page_separator="=== PAGE {} ===",
       include_page_numbers=True
   )

   # PDF options with custom Markdown
   pdf_opts = PdfOptions(
       pages=[0, 1, 2, 3, 4],
       detect_columns=True,
       table_fallback_detection=True,
       attachment_mode="download",
       attachment_output_dir="./pdf_images",
       markdown_options=md_opts
   )

   result = to_markdown("complex_document.pdf", options=pdf_opts)

JSON Configuration
~~~~~~~~~~~~~~~~~~

Options can be loaded from JSON files for reusable configurations:

.. code-block:: json

   {
     "attachment_mode": "download",
     "attachment_output_dir": "./attachments",
     "markdown_emphasis_symbol": "_",
     "pdf_detect_columns": true,
     "pdf_pages": [0, 1, 2],
     "html_strip_dangerous_elements": true
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

For complete CLI usage examples, see the :doc:`cli` reference.
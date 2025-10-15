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

   BaseParserOptions (universal attachment/metadata options)
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
   ├── ZipOptions (ZIP archive options)
   ├── XlsxOptions (Excel XLSX options)
   ├── OdsSpreadsheetOptions (OpenDocument Spreadsheet options)
   └── CsvOptions (CSV/TSV options)

   MarkdownOptions (common Markdown formatting - used by all format options)

**How it works:**

1. **BaseParserOptions** provides universal settings that all converters use, including:

   - Attachment handling (``attachment_mode``, ``attachment_output_dir``)
   - Metadata extraction (``extract_metadata``)
   - Network security settings (``max_download_bytes``)

2. **Format-specific Options** (e.g., ``PdfOptions``, ``HtmlOptions``) inherit from ``BaseParserOptions`` and add their own specialized settings:

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
       pages=[1, 2, 3],
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
   from all2md.options import PdfOptions

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

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

Generated Reference
-------------------

This section is generated automatically from the options dataclasses.

ASCIIDOC Options
~~~~~~~~~~~~~~~~


ASCIIDOC Parser Options
^^^^^^^^^^^^^^^^^^^^^^^

Configuration options for AsciiDoc-to-AST parsing.

This dataclass contains settings specific to parsing AsciiDoc documents
into AST representation using a custom parser.

Parameters
----------
parse_attributes : bool, default True
    Whether to parse document attributes (:name: value syntax).
    When True, attributes are collected and can be referenced.
parse_admonitions : bool, default True
    Whether to parse admonition blocks ([NOTE], [IMPORTANT], etc.).
    When True, admonitions are converted to appropriate AST nodes.
parse_includes : bool, default False
    Whether to process include directives (include::file[]).
    SECURITY: Disabled by default to prevent file system access.
strict_mode : bool, default False
    Whether to raise errors on invalid AsciiDoc syntax.
    When False, attempts to recover gracefully.
resolve_attribute_refs : bool, default True
    Whether to resolve attribute references ({name}) in text.
    When True, {name} is replaced with attribute value.

**attachment_mode**

   How to handle attachments/images

   :Type: ``AttachmentMode``
   :CLI flag: ``--asciidoc-attachment-mode``
   :Default: ``'alt_text'``
   :Choices: ``skip``, ``alt_text``, ``download``, ``base64``
   :Importance: core

**alt_text_mode**

   How to render alt-text content when using alt_text attachment mode

   :Type: ``AltTextMode``
   :CLI flag: ``--asciidoc-alt-text-mode``
   :Default: ``'default'``
   :Choices: ``default``, ``plain_filename``, ``strict_markdown``, ``footnote``
   :Importance: core

**attachment_output_dir**

   Directory to save attachments when using download mode

   :Type: ``str | None``
   :CLI flag: ``--asciidoc-attachment-output-dir``
   :Default: ``None``
   :Importance: advanced

**attachment_base_url**

   Base URL for resolving attachment references

   :Type: ``str | None``
   :CLI flag: ``--asciidoc-attachment-base-url``
   :Default: ``None``
   :Importance: advanced

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--asciidoc-extract-metadata``
   :Default: ``False``
   :Importance: core

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--asciidoc-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**attachment_filename_template**

   Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}

   :Type: ``str``
   :CLI flag: ``--asciidoc-attachment-filename-template``
   :Default: ``'{stem}_{type}{seq}.{ext}'``
   :Importance: advanced

**attachment_overwrite**

   File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'

   :Type: ``Literal['unique', 'overwrite', 'skip']``
   :CLI flag: ``--asciidoc-attachment-overwrite``
   :Default: ``'unique'``
   :Choices: ``unique``, ``overwrite``, ``skip``
   :Importance: advanced

**attachment_deduplicate_by_hash**

   Avoid saving duplicate attachments by content hash

   :Type: ``bool``
   :CLI flag: ``--asciidoc-attachment-deduplicate-by-hash``
   :Default: ``False``
   :Importance: advanced

**attachments_footnotes_section**

   Section title for footnote-style attachment references (None to disable)

   :Type: ``str | None``
   :CLI flag: ``--asciidoc-attachments-footnotes-section``
   :Default: ``'Attachments'``
   :Importance: advanced

**parse_attributes**

   Parse document attributes

   :Type: ``bool``
   :CLI flag: ``--asciidoc-no-parse-attributes``
   :Default: ``True``
   :Importance: core

**parse_admonitions**

   Parse admonition blocks ([NOTE], [IMPORTANT], etc.)

   :Type: ``bool``
   :CLI flag: ``--asciidoc-no-parse-admonitions``
   :Default: ``True``
   :Importance: core

**parse_includes**

   Process include directives (SECURITY: disabled by default)

   :Type: ``bool``
   :CLI flag: ``--asciidoc-parse-includes``
   :Default: ``False``
   :Importance: security

**strict_mode**

   Raise errors on invalid AsciiDoc syntax

   :Type: ``bool``
   :CLI flag: ``--asciidoc-strict-mode``
   :Default: ``False``
   :Importance: advanced

**resolve_attribute_refs**

   Resolve attribute references ({name}) in text

   :Type: ``bool``
   :CLI flag: ``--asciidoc-no-resolve-attributes``
   :Default: ``True``
   :Importance: advanced

**attribute_missing_policy**

   Policy for undefined attribute references: keep literal, use blank, or warn

   :Type: ``Literal['keep', 'blank', 'warn']``
   :CLI flag: ``--asciidoc-attribute-missing-policy``
   :Default: ``'keep'``
   :Choices: ``keep``, ``blank``, ``warn``
   :Importance: advanced

**support_unconstrained_formatting**

   Support unconstrained formatting (e.g., **b**old for mid-word)

   :Type: ``bool``
   :CLI flag: ``--asciidoc-no-unconstrained-formatting``
   :Default: ``True``
   :Importance: advanced

**table_header_detection**

   How to detect table headers: always first-row, use block attributes, or auto-detect

   :Type: ``Literal['first-row', 'attribute-based', 'auto']``
   :CLI flag: ``--asciidoc-table-header-detection``
   :Default: ``'attribute-based'``
   :Choices: ``first-row``, ``attribute-based``, ``auto``
   :Importance: core

**honor_hard_breaks**

   Honor explicit line breaks (trailing space + plus)

   :Type: ``bool``
   :CLI flag: ``--asciidoc-no-honor-hard-breaks``
   :Default: ``True``
   :Importance: advanced

ASCIIDOC Renderer Options
^^^^^^^^^^^^^^^^^^^^^^^^^

Configuration options for AST-to-AsciiDoc rendering.

This dataclass contains settings for rendering AST documents as
AsciiDoc output.

Parameters
----------
list_indent : int, default 2
    Number of spaces for nested list indentation.
use_attributes : bool, default True
    Whether to include document attributes in output.
    When True, renders :name: value attributes at document start.
preserve_comments : bool, default False
    Whether to include // comments in rendered output.
line_length : int, default 0
    Target line length for wrapping text (0 = no wrapping).
html_passthrough_mode : {"pass-through", "escape", "drop", "sanitize"}, default "pass-through"
    How to handle HTMLBlock and HTMLInline nodes:
    - "pass-through": Pass through unchanged (use only with trusted content)
    - "escape": HTML-escape the content
    - "drop": Remove HTML content entirely
    - "sanitize": Remove dangerous elements/attributes (requires bleach for best results)

**fail_on_resource_errors**

   Raise RenderingError on resource failures (images, etc.) instead of logging warnings

   :Type: ``bool``
   :CLI flag: ``--asciidoc-renderer-fail-on-resource-errors``
   :Default: ``False``
   :Importance: advanced

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--asciidoc-renderer-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**list_indent**

   Spaces for nested list indentation

   :Type: ``int``
   :CLI flag: ``--asciidoc-renderer-list-indent``
   :Default: ``2``

**use_attributes**

   Include document attributes in output

   :Type: ``bool``
   :CLI flag: ``--asciidoc-renderer-no-use-attributes``
   :Default: ``True``
   :Importance: core

**preserve_comments**

   Include comments in rendered output

   :Type: ``bool``
   :CLI flag: ``--asciidoc-renderer-preserve-comments``
   :Default: ``False``
   :Importance: core

**line_length**

   Target line length for wrapping (0 = no wrapping)

   :Type: ``int``
   :CLI flag: ``--asciidoc-renderer-line-length``
   :Default: ``0``
   :Importance: core

**html_passthrough_mode**

   How to handle raw HTML content: pass-through, escape, drop, or sanitize

   :Type: ``Literal['pass-through', 'escape', 'drop', 'sanitize']``
   :CLI flag: ``--asciidoc-renderer-html-passthrough-mode``
   :Default: ``'escape'``
   :Choices: ``pass-through``, ``escape``, ``drop``, ``sanitize``
   :Importance: security

AST Options
~~~~~~~~~~~


AST Parser Options
^^^^^^^^^^^^^^^^^^

Options for parsing JSON AST documents.

Parameters
----------
validate_schema : bool, default = True
    Whether to validate the schema version during parsing
strict_mode : bool, default = False
    Whether to fail on unknown node types or attributes

**attachment_mode**

   How to handle attachments/images

   :Type: ``AttachmentMode``
   :CLI flag: ``--ast-attachment-mode``
   :Default: ``'alt_text'``
   :Choices: ``skip``, ``alt_text``, ``download``, ``base64``
   :Importance: core

**alt_text_mode**

   How to render alt-text content when using alt_text attachment mode

   :Type: ``AltTextMode``
   :CLI flag: ``--ast-alt-text-mode``
   :Default: ``'default'``
   :Choices: ``default``, ``plain_filename``, ``strict_markdown``, ``footnote``
   :Importance: core

**attachment_output_dir**

   Directory to save attachments when using download mode

   :Type: ``str | None``
   :CLI flag: ``--ast-attachment-output-dir``
   :Default: ``None``
   :Importance: advanced

**attachment_base_url**

   Base URL for resolving attachment references

   :Type: ``str | None``
   :CLI flag: ``--ast-attachment-base-url``
   :Default: ``None``
   :Importance: advanced

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--ast-extract-metadata``
   :Default: ``False``
   :Importance: core

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--ast-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**attachment_filename_template**

   Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}

   :Type: ``str``
   :CLI flag: ``--ast-attachment-filename-template``
   :Default: ``'{stem}_{type}{seq}.{ext}'``
   :Importance: advanced

**attachment_overwrite**

   File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'

   :Type: ``Literal['unique', 'overwrite', 'skip']``
   :CLI flag: ``--ast-attachment-overwrite``
   :Default: ``'unique'``
   :Choices: ``unique``, ``overwrite``, ``skip``
   :Importance: advanced

**attachment_deduplicate_by_hash**

   Avoid saving duplicate attachments by content hash

   :Type: ``bool``
   :CLI flag: ``--ast-attachment-deduplicate-by-hash``
   :Default: ``False``
   :Importance: advanced

**attachments_footnotes_section**

   Section title for footnote-style attachment references (None to disable)

   :Type: ``str | None``
   :CLI flag: ``--ast-attachments-footnotes-section``
   :Default: ``'Attachments'``
   :Importance: advanced

**validate_schema**

   :Type: ``bool``
   :CLI flag: ``--ast-validate-schema``
   :Default: ``True``

**strict_mode**

   :Type: ``bool``
   :CLI flag: ``--ast-strict-mode``
   :Default: ``False``

AST Renderer Options
^^^^^^^^^^^^^^^^^^^^

Options for rendering documents to JSON AST format.

Parameters
----------
indent : int or None, default = 2
    Number of spaces for JSON indentation. None for compact output.
ensure_ascii : bool, default = False
    Whether to escape non-ASCII characters in JSON output
sort_keys : bool, default = False
    Whether to sort JSON object keys alphabetically

Examples
--------
Compact JSON output:
    >>> options = AstJsonRendererOptions(indent=None)

Pretty-printed JSON with sorted keys:
    >>> options = AstJsonRendererOptions(indent=2, sort_keys=True)

ASCII-only output:
    >>> options = AstJsonRendererOptions(ensure_ascii=True)

**fail_on_resource_errors**

   Raise RenderingError on resource failures (images, etc.) instead of logging warnings

   :Type: ``bool``
   :CLI flag: ``--ast-renderer-fail-on-resource-errors``
   :Default: ``False``
   :Importance: advanced

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--ast-renderer-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**indent**

   :Type: ``int | None``
   :CLI flag: ``--ast-renderer-indent``
   :Default: ``2``

**ensure_ascii**

   :Type: ``bool``
   :CLI flag: ``--ast-renderer-ensure-ascii``
   :Default: ``False``

**sort_keys**

   :Type: ``bool``
   :CLI flag: ``--ast-renderer-sort-keys``
   :Default: ``False``

CHM Options
~~~~~~~~~~~


CHM Parser Options
^^^^^^^^^^^^^^^^^^

Configuration options for CHM-to-Markdown conversion.

This dataclass contains settings specific to Microsoft Compiled HTML Help (CHM)
document processing, including page handling, table of contents generation, and
HTML parsing configuration.

Parameters
----------
include_toc : bool, default True
    Whether to generate and prepend a Markdown Table of Contents from the CHM's
    internal TOC structure at the start of the document.
merge_pages : bool, default True
    Whether to merge all pages into a single continuous document. If False,
    pages are separated with thematic breaks.
html_options : HtmlOptions or None, default None
    Options for parsing HTML content within the CHM file. If None, uses default
    HTML parsing options.

**attachment_mode**

   How to handle attachments/images

   :Type: ``AttachmentMode``
   :CLI flag: ``--chm-attachment-mode``
   :Default: ``'alt_text'``
   :Choices: ``skip``, ``alt_text``, ``download``, ``base64``
   :Importance: core

**alt_text_mode**

   How to render alt-text content when using alt_text attachment mode

   :Type: ``AltTextMode``
   :CLI flag: ``--chm-alt-text-mode``
   :Default: ``'default'``
   :Choices: ``default``, ``plain_filename``, ``strict_markdown``, ``footnote``
   :Importance: core

**attachment_output_dir**

   Directory to save attachments when using download mode

   :Type: ``str | None``
   :CLI flag: ``--chm-attachment-output-dir``
   :Default: ``None``
   :Importance: advanced

**attachment_base_url**

   Base URL for resolving attachment references

   :Type: ``str | None``
   :CLI flag: ``--chm-attachment-base-url``
   :Default: ``None``
   :Importance: advanced

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--chm-extract-metadata``
   :Default: ``False``
   :Importance: core

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--chm-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**attachment_filename_template**

   Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}

   :Type: ``str``
   :CLI flag: ``--chm-attachment-filename-template``
   :Default: ``'{stem}_{type}{seq}.{ext}'``
   :Importance: advanced

**attachment_overwrite**

   File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'

   :Type: ``Literal['unique', 'overwrite', 'skip']``
   :CLI flag: ``--chm-attachment-overwrite``
   :Default: ``'unique'``
   :Choices: ``unique``, ``overwrite``, ``skip``
   :Importance: advanced

**attachment_deduplicate_by_hash**

   Avoid saving duplicate attachments by content hash

   :Type: ``bool``
   :CLI flag: ``--chm-attachment-deduplicate-by-hash``
   :Default: ``False``
   :Importance: advanced

**attachments_footnotes_section**

   Section title for footnote-style attachment references (None to disable)

   :Type: ``str | None``
   :CLI flag: ``--chm-attachments-footnotes-section``
   :Default: ``'Attachments'``
   :Importance: advanced

**include_toc**

   Generate and prepend a Markdown Table of Contents from CHM TOC

   :Type: ``bool``
   :CLI flag: ``--chm-no-include-toc``
   :Default: ``True``
   :Importance: core

**merge_pages**

   Merge all pages into a single continuous document

   :Type: ``bool``
   :CLI flag: ``--chm-no-merge-pages``
   :Default: ``True``
   :Importance: core

**html_options**

   :Type: ``HtmlOptions | None``
   :CLI flag: ``--chm-html-options``
   :Default: ``None``

CSV Options
~~~~~~~~~~~


CSV Parser Options
^^^^^^^^^^^^^^^^^^

Configuration options for CSV/TSV conversion.

This dataclass contains settings specific to delimiter-separated value
file processing, including dialect detection and data limits.

Parameters
----------
detect_csv_dialect : bool, default True
    Enable csv.Sniffer-based dialect detection (ignored if csv_delimiter is set).
csv_delimiter : str | None, default None
    Override CSV/TSV delimiter (e.g., ',', '\\t', ';', '|').
    When set, disables dialect detection.
csv_quotechar : str | None, default None
    Override quote character (e.g., '"', "'").
    When set, uses this for quoting.
csv_escapechar : str | None, default None
    Override escape character (e.g., '\\\\').
    When set, uses this for escaping.
csv_doublequote : bool | None, default None
    Enable/disable double quoting (two quote chars = one literal quote).
    When set, overrides dialect's doublequote setting.
has_header : bool, default True
    Whether the first row contains column headers.
    When False, generates generic headers (Column 1, Column 2, etc.).
max_rows : int | None, default None
    Maximum number of data rows per table (excluding header). None = unlimited.
max_cols : int | None, default None
    Maximum number of columns per table. None = unlimited.
truncation_indicator : str, default "..."
    Appended note when rows/columns are truncated.
header_case : str, default "preserve"
    Transform header case: preserve, title, upper, or lower.
skip_empty_rows : bool, default True
    Whether to skip completely empty rows.
strip_whitespace : bool, default False
    Whether to strip leading/trailing whitespace from all cells.
dialect_sample_size : int, default 4096
    Number of bytes to sample for csv.Sniffer dialect detection.
    Larger values may improve detection for heavily columnated files
    but increase memory usage during detection.

**attachment_mode**

   How to handle attachments/images

   :Type: ``AttachmentMode``
   :CLI flag: ``--csv-attachment-mode``
   :Default: ``'alt_text'``
   :Choices: ``skip``, ``alt_text``, ``download``, ``base64``
   :Importance: core

**alt_text_mode**

   How to render alt-text content when using alt_text attachment mode

   :Type: ``AltTextMode``
   :CLI flag: ``--csv-alt-text-mode``
   :Default: ``'default'``
   :Choices: ``default``, ``plain_filename``, ``strict_markdown``, ``footnote``
   :Importance: core

**attachment_output_dir**

   Directory to save attachments when using download mode

   :Type: ``str | None``
   :CLI flag: ``--csv-attachment-output-dir``
   :Default: ``None``
   :Importance: advanced

**attachment_base_url**

   Base URL for resolving attachment references

   :Type: ``str | None``
   :CLI flag: ``--csv-attachment-base-url``
   :Default: ``None``
   :Importance: advanced

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--csv-extract-metadata``
   :Default: ``False``
   :Importance: core

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--csv-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**attachment_filename_template**

   Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}

   :Type: ``str``
   :CLI flag: ``--csv-attachment-filename-template``
   :Default: ``'{stem}_{type}{seq}.{ext}'``
   :Importance: advanced

**attachment_overwrite**

   File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'

   :Type: ``Literal['unique', 'overwrite', 'skip']``
   :CLI flag: ``--csv-attachment-overwrite``
   :Default: ``'unique'``
   :Choices: ``unique``, ``overwrite``, ``skip``
   :Importance: advanced

**attachment_deduplicate_by_hash**

   Avoid saving duplicate attachments by content hash

   :Type: ``bool``
   :CLI flag: ``--csv-attachment-deduplicate-by-hash``
   :Default: ``False``
   :Importance: advanced

**attachments_footnotes_section**

   Section title for footnote-style attachment references (None to disable)

   :Type: ``str | None``
   :CLI flag: ``--csv-attachments-footnotes-section``
   :Default: ``'Attachments'``
   :Importance: advanced

**detect_csv_dialect**

   Enable csv.Sniffer-based dialect detection (ignored if csv_delimiter is set)

   :Type: ``bool``
   :CLI flag: ``--csv-no-detect-csv-dialect``
   :Default: ``True``
   :Importance: advanced

**dialect_sample_size**

   Number of bytes to sample for dialect detection

   :Type: ``int``
   :CLI flag: ``--csv-dialect-sample-size``
   :Default: ``4096``
   :Importance: advanced

**csv_delimiter**

   Override CSV/TSV delimiter (e.g., ',', '\t', ';', '|')

   :Type: ``Optional[str]``
   :CLI flag: ``--csv-csv-delimiter``
   :Default: ``None``
   :Importance: core

**csv_quotechar**

   Override quote character (e.g., '"', "'")

   :Type: ``Optional[str]``
   :CLI flag: ``--csv-csv-quotechar``
   :Default: ``None``
   :Importance: advanced

**csv_escapechar**

   Override escape character (e.g., '\\')

   :Type: ``Optional[str]``
   :CLI flag: ``--csv-csv-escapechar``
   :Default: ``None``
   :Importance: advanced

**csv_doublequote**

   Enable/disable double quoting (two quote chars = one literal quote)

   :Type: ``Optional[bool]``
   :CLI flag: ``--csv-csv-doublequote``
   :Default: ``None``
   :Importance: advanced

**has_header**

   Whether first row contains column headers

   :Type: ``bool``
   :CLI flag: ``--csv-no-has-header``
   :Default: ``True``
   :Importance: core

**max_rows**

   Maximum rows per table (None = unlimited)

   :Type: ``Optional[int]``
   :CLI flag: ``--csv-max-rows``
   :Default: ``None``
   :Importance: advanced

**max_cols**

   Maximum columns per table (None = unlimited)

   :Type: ``Optional[int]``
   :CLI flag: ``--csv-max-cols``
   :Default: ``None``
   :Importance: advanced

**truncation_indicator**

   Note appended when rows/columns are truncated

   :Type: ``str``
   :CLI flag: ``--csv-truncation-indicator``
   :Default: ``'...'``
   :Importance: advanced

**header_case**

   Transform header case: preserve, title, upper, or lower

   :Type: ``HeaderCaseOption``
   :CLI flag: ``--csv-header-case``
   :Default: ``'preserve'``
   :Choices: ``preserve``, ``title``, ``upper``, ``lower``
   :Importance: core

**skip_empty_rows**

   Skip completely empty rows

   :Type: ``bool``
   :CLI flag: ``--csv-no-skip-empty-rows``
   :Default: ``True``
   :Importance: core

**strip_whitespace**

   Strip leading/trailing whitespace from all cells

   :Type: ``bool``
   :CLI flag: ``--csv-strip-whitespace``
   :Default: ``False``
   :Importance: core

DOCX Options
~~~~~~~~~~~~


DOCX Parser Options
^^^^^^^^^^^^^^^^^^^

Configuration options for DOCX-to-Markdown conversion.

This dataclass contains settings specific to Word document processing,
including image handling and formatting preferences.

Parameters
----------
preserve_tables : bool, default True
    Whether to preserve table formatting in Markdown.

Examples
--------
Convert with base64 image embedding:
    >>> options = DocxOptions(attachment_mode="base64")

**attachment_mode**

   How to handle attachments/images

   :Type: ``AttachmentMode``
   :CLI flag: ``--docx-attachment-mode``
   :Default: ``'alt_text'``
   :Choices: ``skip``, ``alt_text``, ``download``, ``base64``
   :Importance: core

**alt_text_mode**

   How to render alt-text content when using alt_text attachment mode

   :Type: ``AltTextMode``
   :CLI flag: ``--docx-alt-text-mode``
   :Default: ``'default'``
   :Choices: ``default``, ``plain_filename``, ``strict_markdown``, ``footnote``
   :Importance: core

**attachment_output_dir**

   Directory to save attachments when using download mode

   :Type: ``str | None``
   :CLI flag: ``--docx-attachment-output-dir``
   :Default: ``None``
   :Importance: advanced

**attachment_base_url**

   Base URL for resolving attachment references

   :Type: ``str | None``
   :CLI flag: ``--docx-attachment-base-url``
   :Default: ``None``
   :Importance: advanced

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--docx-extract-metadata``
   :Default: ``False``
   :Importance: core

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--docx-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**attachment_filename_template**

   Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}

   :Type: ``str``
   :CLI flag: ``--docx-attachment-filename-template``
   :Default: ``'{stem}_{type}{seq}.{ext}'``
   :Importance: advanced

**attachment_overwrite**

   File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'

   :Type: ``Literal['unique', 'overwrite', 'skip']``
   :CLI flag: ``--docx-attachment-overwrite``
   :Default: ``'unique'``
   :Choices: ``unique``, ``overwrite``, ``skip``
   :Importance: advanced

**attachment_deduplicate_by_hash**

   Avoid saving duplicate attachments by content hash

   :Type: ``bool``
   :CLI flag: ``--docx-attachment-deduplicate-by-hash``
   :Default: ``False``
   :Importance: advanced

**attachments_footnotes_section**

   Section title for footnote-style attachment references (None to disable)

   :Type: ``str | None``
   :CLI flag: ``--docx-attachments-footnotes-section``
   :Default: ``'Attachments'``
   :Importance: advanced

**preserve_tables**

   Preserve table formatting in Markdown

   :Type: ``bool``
   :CLI flag: ``--docx-no-preserve-tables``
   :Default: ``True``
   :Importance: core

**include_footnotes**

   Include footnotes in output

   :Type: ``bool``
   :CLI flag: ``--docx-no-include-footnotes``
   :Default: ``True``
   :Importance: core

**include_endnotes**

   Include endnotes in output

   :Type: ``bool``
   :CLI flag: ``--docx-no-include-endnotes``
   :Default: ``True``
   :Importance: core

**include_comments**

   Include document comments in output

   :Type: ``bool``
   :CLI flag: ``--docx-include-comments``
   :Default: ``False``
   :Importance: core

**comments_position**

   Render comments inline or at document end

   :Type: ``Literal['inline', 'footnotes']``
   :CLI flag: ``--docx-comments-position``
   :Default: ``'footnotes'``
   :Choices: ``inline``, ``footnotes``
   :Importance: advanced

**comment_mode**

   How to render comments: html (HTML comments), blockquote (quoted blocks), ignore (skip)

   :Type: ``Literal['html', 'blockquote', 'ignore']``
   :CLI flag: ``--docx-comment-mode``
   :Default: ``'blockquote'``
   :Choices: ``html``, ``blockquote``, ``ignore``
   :Importance: advanced

**include_image_captions**

   Include image captions/descriptions in output

   :Type: ``bool``
   :CLI flag: ``--docx-no-include-image-captions``
   :Default: ``True``
   :Importance: advanced

**list_numbering_style**

   List numbering style: detect, decimal, lowerroman, upperroman, loweralpha, upperalpha

   :Type: ``Literal['detect', 'decimal', 'lowerroman', 'upperroman', 'loweralpha', 'upperalpha']``
   :CLI flag: ``--docx-list-numbering-style``
   :Default: ``'detect'``
   :Choices: ``detect``, ``decimal``, ``lowerroman``, ``upperroman``, ``loweralpha``, ``upperalpha``
   :Importance: advanced

DOCX Renderer Options
^^^^^^^^^^^^^^^^^^^^^

Configuration options for rendering AST to DOCX format.

This dataclass contains settings specific to Word document generation,
including fonts, styles, and formatting preferences.

Parameters
----------
default_font : str, default "Calibri"
    Default font name for body text.
default_font_size : int, default 11
    Default font size in points for body text.
heading_font_sizes : dict[int, int] or None, default None
    Font sizes for heading levels 1-6. If None, uses built-in Word heading styles.
use_styles : bool, default True
    Whether to use built-in Word styles vs direct formatting.
table_style : str or None, default "Light Grid Accent 1"
    Built-in table style name. If None, uses plain table formatting.
code_font : str, default "Courier New"
    Font name for code blocks and inline code.
code_font_size : int, default 10
    Font size for code blocks and inline code.
preserve_formatting : bool, default True
    Whether to preserve text formatting (bold, italic, etc.).
template_path : str or None, default None
    Path to .docx template file. When specified, the renderer uses the template's
    styles (headings, body text, etc.) instead of creating a blank document. This
    is powerful for corporate environments where documents must adopt specific style
    guidelines defined in a template.
network : NetworkFetchOptions, default NetworkFetchOptions()
    Network security settings for fetching remote images. By default,
    remote image fetching is disabled (allow_remote_fetch=False).
    Set network.allow_remote_fetch=True to enable secure remote image fetching
    with the same security guardrails as PPTX renderer.

**fail_on_resource_errors**

   Raise RenderingError on resource failures (images, etc.) instead of logging warnings

   :Type: ``bool``
   :CLI flag: ``--docx-renderer-fail-on-resource-errors``
   :Default: ``False``
   :Importance: advanced

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--docx-renderer-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**default_font**

   Default font for body text

   :Type: ``str``
   :CLI flag: ``--docx-renderer-default-font``
   :Default: ``'Calibri'``
   :Importance: core

**default_font_size**

   Default font size in points

   :Type: ``int``
   :CLI flag: ``--docx-renderer-default-font-size``
   :Default: ``11``
   :Importance: core

**heading_font_sizes**

   Font sizes for heading levels 1-6 as JSON object (e.g., '{"1": 24, "2": 18}')

   :Type: ``UnionType[dict[int, int], NoneType]``
   :CLI flag: ``--docx-renderer-heading-font-sizes``
   :Default: ``None``
   :Importance: advanced

**use_styles**

   Use built-in Word styles vs direct formatting

   :Type: ``bool``
   :CLI flag: ``--docx-renderer-no-use-styles``
   :Default: ``True``
   :Importance: advanced

**table_style**

   Built-in table style name (None = plain formatting)

   :Type: ``UnionType[str, NoneType]``
   :CLI flag: ``--docx-renderer-table-style``
   :Default: ``'Light Grid Accent 1'``
   :Importance: advanced

**code_font**

   Font for code blocks and inline code

   :Type: ``str``
   :CLI flag: ``--docx-renderer-code-font``
   :Default: ``'Courier New'``
   :Importance: core

**code_font_size**

   Font size for code

   :Type: ``int``
   :CLI flag: ``--docx-renderer-code-font-size``
   :Default: ``10``
   :Importance: core

**preserve_formatting**

   Preserve text formatting (bold, italic, etc.)

   :Type: ``bool``
   :CLI flag: ``--docx-renderer-no-preserve-formatting``
   :Default: ``True``
   :Importance: core

**template_path**

   Path to .docx template file for styles (None = default blank document)

   :Type: ``UnionType[str, NoneType]``
   :CLI flag: ``--docx-renderer-template-path``
   :Default: ``None``
   :Importance: core

Network Options
+++++++++++++++

Network security options for remote resource fetching.

This dataclass contains settings that control how remote resources
(images, CSS, etc.) are fetched, including security constraints
to prevent SSRF attacks.

Parameters
----------
allow_remote_fetch : bool, default False
    Whether to allow fetching remote URLs for images and other resources.
    When False, prevents SSRF attacks by blocking all network requests.
allowed_hosts : list[str] | None, default None
    List of allowed hostnames or CIDR blocks for remote fetching.
    If None, all hosts are allowed (subject to other security constraints).
require_https : bool, default False
    Whether to require HTTPS for all remote URL fetching.
network_timeout : float, default 10.0
    Timeout in seconds for remote URL fetching.
max_requests_per_second : float, default 10.0
    Maximum number of network requests per second (rate limiting).
max_concurrent_requests : int, default 5
    Maximum number of concurrent network requests.

Notes
-----
Asset size limits are inherited from BaseParserOptions.max_asset_size_bytes.

**allow_remote_fetch**

   Allow fetching remote URLs for images and other resources. When False, prevents SSRF attacks by blocking all network requests.

   :Type: ``bool``
   :CLI flag: ``--docx-renderer-network-allow-remote-fetch``
   :Default: ``False``
   :Importance: security

**allowed_hosts**

   List of allowed hostnames or CIDR blocks for remote fetching. If None, all hosts are allowed (subject to other security constraints).

   :Type: ``UnionType[list[str], NoneType]``
   :CLI flag: ``--docx-renderer-network-allowed-hosts``
   :Default: ``None``
   :Importance: security

**require_https**

   Require HTTPS for all remote URL fetching

   :Type: ``bool``
   :CLI flag: ``--docx-renderer-network-no-require-https``
   :Default: ``True``
   :Importance: security

**require_head_success**

   Require HEAD request success before remote URL fetching

   :Type: ``bool``
   :CLI flag: ``--docx-renderer-network-no-require-head-success``
   :Default: ``True``
   :Importance: security

**network_timeout**

   Timeout in seconds for remote URL fetching

   :Type: ``float``
   :CLI flag: ``--docx-renderer-network-network-timeout``
   :Default: ``10.0``
   :Importance: security

**max_redirects**

   Maximum number of HTTP redirects to follow

   :Type: ``int``
   :CLI flag: ``--docx-renderer-network-max-redirects``
   :Default: ``5``
   :Importance: security

**allowed_content_types**

   Allowed content-type prefixes for remote resources (e.g., 'image/', 'text/')

   :Type: ``UnionType[tuple[str, ...], NoneType]``
   :CLI flag: ``--docx-renderer-network-allowed-content-types``
   :Default: ``('image/',)``
   :CLI action: ``append``
   :Importance: security

**max_requests_per_second**

   Maximum number of network requests per second (rate limiting)

   :Type: ``float``
   :CLI flag: ``--docx-renderer-network-max-requests-per-second``
   :Default: ``10.0``
   :Importance: security

**max_concurrent_requests**

   Maximum number of concurrent network requests

   :Type: ``int``
   :CLI flag: ``--docx-renderer-network-max-concurrent-requests``
   :Default: ``5``
   :Importance: security

EML Options
~~~~~~~~~~~


EML Parser Options
^^^^^^^^^^^^^^^^^^

Configuration options for EML-to-Markdown conversion.

This dataclass contains settings specific to email message processing,
including robust parsing, date handling, quote processing, and URL cleaning.

Parameters
----------
include_headers : bool, default True
    Whether to include email headers (From, To, Subject, Date) in output.
preserve_thread_structure : bool, default True
    Whether to maintain email thread/reply chain structure.
date_format_mode : {"iso8601", "locale", "strftime"}, default "strftime"
    How to format dates in output:
    - "iso8601": Use ISO 8601 format (2023-01-01T10:00:00Z)
    - "locale": Use system locale-aware formatting
    - "strftime": Use custom strftime pattern
date_strftime_pattern : str, default "%m/%d/%y %H:%M"
    Custom strftime pattern when date_format_mode is "strftime".
convert_html_to_markdown : bool, default False
    Whether to convert HTML content to Markdown
    When True, HTML parts are converted to Markdown; when False, HTML is preserved as-is.
clean_quotes : bool, default True
    Whether to clean and normalize quoted content ("> " prefixes, etc.).
detect_reply_separators : bool, default True
    Whether to detect common reply separators like "On <date>, <name> wrote:".
normalize_headers : bool, default True
    Whether to normalize header casing and whitespace.
preserve_raw_headers : bool, default False
    Whether to preserve both raw and decoded header values.
clean_wrapped_urls : bool, default True
    Whether to clean URL defense/safety wrappers from links.
url_wrappers : list[str], default from constants
    List of URL wrapper domains to clean (urldefense.com, safelinks, etc.).

Examples
--------
Convert email with ISO 8601 date formatting:
    >>> options = EmlOptions(date_format_mode="iso8601")

Convert with HTML-to-Markdown conversion enabled:
    >>> options = EmlOptions(convert_html_to_markdown=True)

Disable quote cleaning and URL unwrapping:
    >>> options = EmlOptions(clean_quotes=False, clean_wrapped_urls=False)

**attachment_mode**

   How to handle attachments/images

   :Type: ``AttachmentMode``
   :CLI flag: ``--eml-attachment-mode``
   :Default: ``'alt_text'``
   :Choices: ``skip``, ``alt_text``, ``download``, ``base64``
   :Importance: core

**alt_text_mode**

   How to render alt-text content when using alt_text attachment mode

   :Type: ``AltTextMode``
   :CLI flag: ``--eml-alt-text-mode``
   :Default: ``'default'``
   :Choices: ``default``, ``plain_filename``, ``strict_markdown``, ``footnote``
   :Importance: core

**attachment_output_dir**

   Directory to save attachments when using download mode

   :Type: ``str | None``
   :CLI flag: ``--eml-attachment-output-dir``
   :Default: ``None``
   :Importance: advanced

**attachment_base_url**

   Base URL for resolving attachment references

   :Type: ``str | None``
   :CLI flag: ``--eml-attachment-base-url``
   :Default: ``None``
   :Importance: advanced

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--eml-extract-metadata``
   :Default: ``False``
   :Importance: core

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--eml-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**attachment_filename_template**

   Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}

   :Type: ``str``
   :CLI flag: ``--eml-attachment-filename-template``
   :Default: ``'{stem}_{type}{seq}.{ext}'``
   :Importance: advanced

**attachment_overwrite**

   File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'

   :Type: ``Literal['unique', 'overwrite', 'skip']``
   :CLI flag: ``--eml-attachment-overwrite``
   :Default: ``'unique'``
   :Choices: ``unique``, ``overwrite``, ``skip``
   :Importance: advanced

**attachment_deduplicate_by_hash**

   Avoid saving duplicate attachments by content hash

   :Type: ``bool``
   :CLI flag: ``--eml-attachment-deduplicate-by-hash``
   :Default: ``False``
   :Importance: advanced

**attachments_footnotes_section**

   Section title for footnote-style attachment references (None to disable)

   :Type: ``str | None``
   :CLI flag: ``--eml-attachments-footnotes-section``
   :Default: ``'Attachments'``
   :Importance: advanced

**include_headers**

   Include email headers (From, To, Subject, Date) in output

   :Type: ``bool``
   :CLI flag: ``--eml-no-include-headers``
   :Default: ``True``
   :Importance: core

**preserve_thread_structure**

   Maintain email thread/reply chain structure

   :Type: ``bool``
   :CLI flag: ``--eml-no-preserve-thread-structure``
   :Default: ``True``
   :Importance: core

**date_format_mode**

   Date formatting mode: iso8601, locale, or strftime

   :Type: ``DateFormatMode``
   :CLI flag: ``--eml-date-format-mode``
   :Default: ``'strftime'``
   :Importance: core

**date_strftime_pattern**

   Custom strftime pattern for date formatting

   :Type: ``str``
   :CLI flag: ``--eml-date-strftime-pattern``
   :Default: ``'%m/%d/%y %H:%M'``
   :Importance: advanced

**convert_html_to_markdown**

   Convert HTML content to Markdown

   :Type: ``bool``
   :CLI flag: ``--eml-convert-html-to-markdown``
   :Default: ``False``
   :Importance: core

**clean_quotes**

   Clean and normalize quoted content

   :Type: ``bool``
   :CLI flag: ``--eml-clean-quotes``
   :Default: ``True``
   :Importance: core

**detect_reply_separators**

   Detect common reply separators

   :Type: ``bool``
   :CLI flag: ``--eml-detect-reply-separators``
   :Default: ``True``
   :Importance: core

**normalize_headers**

   Normalize header casing and whitespace

   :Type: ``bool``
   :CLI flag: ``--eml-normalize-headers``
   :Default: ``True``
   :Importance: advanced

**preserve_raw_headers**

   Preserve both raw and decoded header values

   :Type: ``bool``
   :CLI flag: ``--eml-preserve-raw-headers``
   :Default: ``False``
   :Importance: advanced

**clean_wrapped_urls**

   Clean URL defense/safety wrappers from links

   :Type: ``bool``
   :CLI flag: ``--eml-clean-wrapped-urls``
   :Default: ``True``
   :Importance: security

**url_wrappers**

   :Type: ``list[str] | None``
   :CLI flag: ``--eml-url-wrappers``
   :Default factory: ``EmlOptions.<lambda>``

**html_network**

   Network security settings for HTML part conversion

   :Type: ``NetworkFetchOptions``
   :CLI flag: ``--eml-html-network``
   :Default factory: ``NetworkFetchOptions``

**sort_order**

   Email chain sort order: 'asc' (oldest first) or 'desc' (newest first)

   :Type: ``Literal['asc', 'desc']``
   :CLI flag: ``--eml-sort-order``
   :Default: ``'asc'``
   :Choices: ``asc``, ``desc``
   :Importance: advanced

**subject_as_h1**

   Include subject line as H1 heading

   :Type: ``bool``
   :CLI flag: ``--eml-no-subject-as-h1``
   :Default: ``True``
   :Importance: core

**include_attach_section_heading**

   Include heading before attachments section

   :Type: ``bool``
   :CLI flag: ``--eml-no-include-attach-section-heading``
   :Default: ``True``
   :Importance: advanced

**attach_section_title**

   Title for attachments section heading

   :Type: ``str``
   :CLI flag: ``--eml-attach-section-title``
   :Default: ``'Attachments'``
   :Importance: advanced

**include_html_parts**

   Include HTML content parts from emails

   :Type: ``bool``
   :CLI flag: ``--eml-no-include-html-parts``
   :Default: ``True``
   :Importance: core

**include_plain_parts**

   Include plain text content parts from emails

   :Type: ``bool``
   :CLI flag: ``--eml-no-include-plain-parts``
   :Default: ``True``
   :Importance: core

EPUB Options
~~~~~~~~~~~~


EPUB Parser Options
^^^^^^^^^^^^^^^^^^^

Configuration options for EPUB-to-Markdown conversion.

This dataclass contains settings specific to EPUB document processing,
including chapter handling, table of contents generation, and image handling.

Parameters
----------
merge_chapters : bool, default True
    Whether to merge chapters into a single continuous document. If False,
    a separator is placed between chapters.
include_toc : bool, default True
    Whether to generate and prepend a Markdown Table of Contents.

**attachment_mode**

   How to handle attachments/images

   :Type: ``AttachmentMode``
   :CLI flag: ``--epub-attachment-mode``
   :Default: ``'alt_text'``
   :Choices: ``skip``, ``alt_text``, ``download``, ``base64``
   :Importance: core

**alt_text_mode**

   How to render alt-text content when using alt_text attachment mode

   :Type: ``AltTextMode``
   :CLI flag: ``--epub-alt-text-mode``
   :Default: ``'default'``
   :Choices: ``default``, ``plain_filename``, ``strict_markdown``, ``footnote``
   :Importance: core

**attachment_output_dir**

   Directory to save attachments when using download mode

   :Type: ``str | None``
   :CLI flag: ``--epub-attachment-output-dir``
   :Default: ``None``
   :Importance: advanced

**attachment_base_url**

   Base URL for resolving attachment references

   :Type: ``str | None``
   :CLI flag: ``--epub-attachment-base-url``
   :Default: ``None``
   :Importance: advanced

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--epub-extract-metadata``
   :Default: ``False``
   :Importance: core

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--epub-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**attachment_filename_template**

   Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}

   :Type: ``str``
   :CLI flag: ``--epub-attachment-filename-template``
   :Default: ``'{stem}_{type}{seq}.{ext}'``
   :Importance: advanced

**attachment_overwrite**

   File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'

   :Type: ``Literal['unique', 'overwrite', 'skip']``
   :CLI flag: ``--epub-attachment-overwrite``
   :Default: ``'unique'``
   :Choices: ``unique``, ``overwrite``, ``skip``
   :Importance: advanced

**attachment_deduplicate_by_hash**

   Avoid saving duplicate attachments by content hash

   :Type: ``bool``
   :CLI flag: ``--epub-attachment-deduplicate-by-hash``
   :Default: ``False``
   :Importance: advanced

**attachments_footnotes_section**

   Section title for footnote-style attachment references (None to disable)

   :Type: ``str | None``
   :CLI flag: ``--epub-attachments-footnotes-section``
   :Default: ``'Attachments'``
   :Importance: advanced

**merge_chapters**

   Merge chapters into a single continuous document

   :Type: ``bool``
   :CLI flag: ``--epub-no-merge-chapters``
   :Default: ``True``
   :Importance: core

**include_toc**

   Generate and prepend a Markdown Table of Contents

   :Type: ``bool``
   :CLI flag: ``--epub-no-include-toc``
   :Default: ``True``
   :Importance: core

**html_options**

   :Type: ``HtmlOptions | None``
   :CLI flag: ``--epub-html-options``
   :Default: ``None``

EPUB Renderer Options
^^^^^^^^^^^^^^^^^^^^^

Configuration options for rendering AST to EPUB format.

This dataclass contains settings specific to EPUB generation from AST,
including chapter splitting strategies, metadata, and EPUB structure.

Parameters
----------
chapter_split_mode : {"separator", "heading", "auto"}, default "auto"
    How to split the AST into chapters:
    - "separator": Split on ThematicBreak nodes (mirrors parser behavior)
    - "heading": Split on specific heading level
    - "auto": Try separator first, fallback to heading-based splitting
chapter_split_heading_level : int, default 1
    Heading level to use for chapter splits when using heading mode.
    Level 1 (H1) typically represents chapter boundaries.
title : str or None, default None
    EPUB book title. If None, extracted from document metadata.
author : str or None, default None
    EPUB book author. If None, extracted from document metadata.
language : str, default "en"
    EPUB book language code (ISO 639-1).
identifier : str or None, default None
    Unique identifier (ISBN, UUID, etc.). Auto-generated if None.
chapter_title_template : str, default "Chapter {num}"
    Template for auto-generated chapter titles. Supports {num} placeholder.
use_heading_as_chapter_title : bool, default True
    Use first heading in chapter as chapter title in NCX/navigation.
generate_toc : bool, default True
    Generate table of contents (NCX and nav.xhtml files).
include_cover : bool, default False
    Include cover image in EPUB package.
cover_image_path : str or None, default None
    Path to cover image file. Only used if include_cover=True.

**fail_on_resource_errors**

   Raise RenderingError on resource failures (images, etc.) instead of logging warnings

   :Type: ``bool``
   :CLI flag: ``--epub-renderer-fail-on-resource-errors``
   :Default: ``False``
   :Importance: advanced

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--epub-renderer-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**chapter_split_mode**

   Chapter splitting strategy: separator, heading, or auto

   :Type: ``Literal['separator', 'heading', 'auto']``
   :CLI flag: ``--epub-renderer-chapter-split-mode``
   :Default: ``'auto'``
   :Choices: ``separator``, ``heading``, ``auto``
   :Importance: core

**chapter_split_heading_level**

   Heading level for chapter splits (H1 = level 1)

   :Type: ``int``
   :CLI flag: ``--epub-renderer-chapter-split-heading-level``
   :Default: ``1``
   :Importance: advanced

**title**

   EPUB book title (None = use document metadata)

   :Type: ``UnionType[str, NoneType]``
   :CLI flag: ``--epub-renderer-title``
   :Default: ``None``
   :Importance: core

**author**

   EPUB book author (None = use document metadata)

   :Type: ``UnionType[str, NoneType]``
   :CLI flag: ``--epub-renderer-author``
   :Default: ``None``
   :Importance: core

**language**

   EPUB language code (ISO 639-1)

   :Type: ``str``
   :CLI flag: ``--epub-renderer-language``
   :Default: ``'en'``
   :Importance: core

**identifier**

   Unique identifier (ISBN, UUID, etc.)

   :Type: ``UnionType[str, NoneType]``
   :CLI flag: ``--epub-renderer-identifier``
   :Default: ``None``
   :Importance: advanced

**chapter_title_template**

   Template for auto-generated chapter titles

   :Type: ``str``
   :CLI flag: ``--epub-renderer-chapter-title-template``
   :Default: ``'Chapter {num}'``
   :Importance: advanced

**use_heading_as_chapter_title**

   Use first heading as chapter title in navigation

   :Type: ``bool``
   :CLI flag: ``--epub-renderer-no-use-heading-as-chapter-title``
   :Default: ``True``
   :Importance: core

**generate_toc**

   Generate table of contents (NCX and nav.xhtml)

   :Type: ``bool``
   :CLI flag: ``--epub-renderer-no-generate-toc``
   :Default: ``True``
   :Importance: core

**include_cover**

   Include cover image in EPUB

   :Type: ``bool``
   :CLI flag: ``--epub-renderer-include-cover``
   :Default: ``False``
   :Importance: core

**cover_image_path**

   Path to cover image file

   :Type: ``UnionType[str, NoneType]``
   :CLI flag: ``--epub-renderer-cover-image-path``
   :Default: ``None``
   :Importance: advanced

HTML Options
~~~~~~~~~~~~


HTML Parser Options
^^^^^^^^^^^^^^^^^^^

Configuration options for HTML-to-Markdown conversion.

This dataclass contains settings specific to HTML document processing,
including heading styles, title extraction, image handling, content
sanitization, and advanced formatting options.

Parameters
----------
extract_title : bool, default False
    Whether to extract and use the HTML <title> element.
convert_nbsp : bool, default False
    Whether to convert non-breaking spaces (&nbsp;) to regular spaces in the output.
strip_dangerous_elements : bool, default False
    Whether to remove potentially dangerous HTML elements (script, style, etc.).
detect_table_alignment : bool, default True
    Whether to automatically detect table column alignment from CSS/attributes.
preserve_nested_structure : bool, default True
    Whether to maintain proper nesting for blockquotes and other elements.
allowed_attributes : tuple[str, ...] | dict[str, tuple[str, ...]] | None, default None
    Whitelist of allowed HTML attributes. Supports two modes:
    - Global allowlist: tuple of attribute names applied to all elements
    - Per-element allowlist: dict mapping element names to tuples of allowed attributes
base_url : str or None, default None
    Base URL for resolving relative hrefs in <a> tags. This is separate from
    attachment_base_url (used for images/assets). Allows precise control over
    navigational link URLs vs. resource URLs.

Examples
--------
Convert and extract page title:
    >>> options = HtmlOptions(extract_title=True)

Convert with content sanitization:
    >>> options = HtmlOptions(strip_dangerous_elements=True, convert_nbsp=True)

Use global attribute allowlist:
    >>> options = HtmlOptions(allowed_attributes=('class', 'id', 'href', 'src'))

Use per-element attribute allowlist:
    >>> options = HtmlOptions(allowed_attributes={
    ...     'img': ('src', 'alt', 'title'),
    ...     'a': ('href', 'title'),
    ...     'div': ('class', 'id')
    ... })

**attachment_mode**

   How to handle attachments/images

   :Type: ``AttachmentMode``
   :CLI flag: ``--html-attachment-mode``
   :Default: ``'alt_text'``
   :Choices: ``skip``, ``alt_text``, ``download``, ``base64``
   :Importance: core

**alt_text_mode**

   How to render alt-text content when using alt_text attachment mode

   :Type: ``AltTextMode``
   :CLI flag: ``--html-alt-text-mode``
   :Default: ``'default'``
   :Choices: ``default``, ``plain_filename``, ``strict_markdown``, ``footnote``
   :Importance: core

**attachment_output_dir**

   Directory to save attachments when using download mode

   :Type: ``str | None``
   :CLI flag: ``--html-attachment-output-dir``
   :Default: ``None``
   :Importance: advanced

**attachment_base_url**

   Base URL for resolving attachment references

   :Type: ``str | None``
   :CLI flag: ``--html-attachment-base-url``
   :Default: ``None``
   :Importance: advanced

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--html-extract-metadata``
   :Default: ``False``
   :Importance: core

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--html-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**attachment_filename_template**

   Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}

   :Type: ``str``
   :CLI flag: ``--html-attachment-filename-template``
   :Default: ``'{stem}_{type}{seq}.{ext}'``
   :Importance: advanced

**attachment_overwrite**

   File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'

   :Type: ``Literal['unique', 'overwrite', 'skip']``
   :CLI flag: ``--html-attachment-overwrite``
   :Default: ``'unique'``
   :Choices: ``unique``, ``overwrite``, ``skip``
   :Importance: advanced

**attachment_deduplicate_by_hash**

   Avoid saving duplicate attachments by content hash

   :Type: ``bool``
   :CLI flag: ``--html-attachment-deduplicate-by-hash``
   :Default: ``False``
   :Importance: advanced

**attachments_footnotes_section**

   Section title for footnote-style attachment references (None to disable)

   :Type: ``str | None``
   :CLI flag: ``--html-attachments-footnotes-section``
   :Default: ``'Attachments'``
   :Importance: advanced

**extract_title**

   Extract and use HTML <title> element as main heading

   :Type: ``bool``
   :CLI flag: ``--html-extract-title``
   :Default: ``False``
   :Importance: core

**convert_nbsp**

   Convert non-breaking spaces (&nbsp;) to regular spaces

   :Type: ``bool``
   :CLI flag: ``--html-convert-nbsp``
   :Default: ``False``
   :Importance: core

**strip_dangerous_elements**

   Remove potentially dangerous HTML elements (script, style, etc.)

   :Type: ``bool``
   :CLI flag: ``--html-strip-dangerous-elements``
   :Default: ``False``
   :Importance: security

**detect_table_alignment**

   Automatically detect table column alignment from CSS/attributes

   :Type: ``bool``
   :CLI flag: ``--html-no-detect-table-alignment``
   :Default: ``True``
   :Importance: core

**network**

   Network security settings for remote resource fetching

   :Type: ``NetworkFetchOptions``
   :CLI flag: ``--html-network``
   :Default factory: ``NetworkFetchOptions``

**local_files**

   Local file access security settings

   :Type: ``LocalFileAccessOptions``
   :CLI flag: ``--html-local-files``
   :Default factory: ``LocalFileAccessOptions``

**preserve_nested_structure**

   Maintain proper nesting for blockquotes and other elements

   :Type: ``bool``
   :CLI flag: ``--html-no-preserve-nested-structure``
   :Default: ``True``
   :Importance: core

**strip_comments**

   Remove HTML comments from output

   :Type: ``bool``
   :CLI flag: ``--html-no-strip-comments``
   :Default: ``True``
   :Importance: core

**collapse_whitespace**

   Collapse multiple spaces/newlines into single spaces

   :Type: ``bool``
   :CLI flag: ``--html-no-collapse-whitespace``
   :Default: ``True``
   :Importance: core

**br_handling**

   How to handle <br> tags: 'newline' or 'space'

   :Type: ``Literal['newline', 'space']``
   :CLI flag: ``--html-br-handling``
   :Default: ``'newline'``
   :Choices: ``newline``, ``space``
   :Importance: advanced

**allowed_elements**

   Whitelist of allowed HTML elements (if set, only these are processed)

   :Type: ``tuple[str, ...] | None``
   :CLI flag: ``--html-allowed-elements``
   :Default: ``None``
   :CLI action: ``append``
   :Importance: security

**allowed_attributes**

   Whitelist of allowed HTML attributes. Can be a tuple of attribute names (global allowlist) or a dict mapping element names to tuples of allowed attributes (per-element allowlist). Examples: ('class', 'id') or {'img': ('src', 'alt', 'title'), 'a': ('href', 'title')}

   :Type: ``tuple[str, ...] | dict[str, tuple[str, ...]] | None``
   :CLI flag: ``--html-allowed-attributes``
   :Default: ``None``
   :CLI action: ``append``
   :Importance: security

**figure_rendering**

   How to render <figure> elements: blockquote, image_with_caption, html

   :Type: ``Literal['blockquote', 'image_with_caption', 'html']``
   :CLI flag: ``--html-figure-rendering``
   :Default: ``'blockquote'``
   :Choices: ``blockquote``, ``image_with_caption``, ``html``
   :Importance: advanced

**details_rendering**

   How to render <details>/<summary> elements: blockquote, html, ignore

   :Type: ``Literal['blockquote', 'html', 'ignore']``
   :CLI flag: ``--html-details-rendering``
   :Default: ``'blockquote'``
   :Choices: ``blockquote``, ``html``, ``ignore``
   :Importance: advanced

**extract_microdata**

   Extract microdata and structured data to metadata

   :Type: ``bool``
   :CLI flag: ``--html-no-extract-microdata``
   :Default: ``True``
   :Importance: advanced

**base_url**

   Base URL for resolving relative hrefs in <a> tags (separate from attachment_base_url for images)

   :Type: ``str | None``
   :CLI flag: ``--html-base-url``
   :Default: ``None``
   :Importance: advanced

HTML Renderer Options
^^^^^^^^^^^^^^^^^^^^^

Configuration options for rendering AST to HTML format.

This dataclass contains settings specific to HTML generation,
including document structure, styling, templating, and feature toggles.

Parameters
----------
standalone : bool, default True
    Generate complete HTML document with <html>, <head>, <body> tags.
    If False, generates only the content fragment.
    Ignored when template_mode is not None.
css_style : {"inline", "embedded", "external", "none"}, default "embedded"
    How to include CSS styles:
    - "inline": Add style attributes to elements
    - "embedded": Include <style> block in <head>
    - "external": Reference external CSS file
    - "none": No styling
css_file : str or None, default None
    Path to external CSS file (used when css_style="external").
include_toc : bool, default False
    Generate table of contents from headings.
syntax_highlighting : bool, default True
    Add language classes to code blocks for syntax highlighting.
escape_html : bool, default True
    Escape HTML special characters in text content.
math_renderer : {"mathjax", "katex", "none"}, default "mathjax"
    Math rendering library to use for MathML/LaTeX math:
    - "mathjax": Include MathJax CDN script
    - "katex": Include KaTeX CDN script
    - "none": Render math as plain text
html_passthrough_mode : {"pass-through", "escape", "drop", "sanitize"}, default "pass-through"
    How to handle HTMLBlock and HTMLInline nodes:
    - "pass-through": Pass through unchanged (use only with trusted content)
    - "escape": HTML-escape the content
    - "drop": Remove HTML content entirely
    - "sanitize": Remove dangerous elements/attributes (requires bleach for best results)
language : str, default "en"
    Document language code (ISO 639-1) for the <html lang="..."> attribute.
    Can be overridden by document metadata.
template_mode : {"inject", "replace", "jinja"} or None, default None
    Template mode for rendering HTML:
    - None: Use standalone mode (default behavior)
    - "inject": Inject content into existing HTML file at selector
    - "replace": Replace placeholders in template file
    - "jinja": Use Jinja2 template engine with full context
    When set, standalone is ignored.
template_file : str or None, default None
    Path to template file (required when template_mode is not None).
template_selector : str, default "#content"
    CSS selector for injection target (used with template_mode="inject").
injection_mode : {"append", "prepend", "replace"}, default "replace"
    How to inject content at selector (used with template_mode="inject"):
    - "append": Add content after existing content
    - "prepend": Add content before existing content
    - "replace": Replace existing content
content_placeholder : str, default "{CONTENT}"
    Placeholder string to replace with content (used with template_mode="replace").
css_class_map : dict[str, str | list[str]] or None, default None
    Map AST node type names to custom CSS classes.
    Example: {"Heading": "article-heading", "CodeBlock": ["code", "highlight"]}
allow_remote_scripts : bool, default False
    Allow loading remote scripts (e.g., MathJax/KaTeX from CDN).
    Default is False for security - requires explicit opt-in for CDN usage.
    When False and math_renderer != 'none', will raise a warning.
csp_enabled : bool, default False
    Add Content-Security-Policy meta tag to standalone HTML documents.
    Helps prevent XSS attacks by restricting resource loading.
csp_policy : str or None, default (secure policy)
    Custom Content-Security-Policy header value.
    If None, uses default: "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';"

Examples
--------
Inject into existing HTML:
    >>> options = HtmlRendererOptions(
    ...     template_mode="inject",
    ...     template_file="layout.html",
    ...     template_selector="#main-content"
    ... )

Replace placeholders:
    >>> options = HtmlRendererOptions(
    ...     template_mode="replace",
    ...     template_file="template.html",
    ...     content_placeholder="{CONTENT}"
    ... )

Use Jinja2 template:
    >>> options = HtmlRendererOptions(
    ...     template_mode="jinja",
    ...     template_file="article.html"
    ... )

Custom CSS classes:
    >>> options = HtmlRendererOptions(
    ...     css_class_map={"Heading": "prose-heading", "CodeBlock": "code-block"}
    ... )

**fail_on_resource_errors**

   Raise RenderingError on resource failures (images, etc.) instead of logging warnings

   :Type: ``bool``
   :CLI flag: ``--html-renderer-fail-on-resource-errors``
   :Default: ``False``
   :Importance: advanced

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--html-renderer-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**standalone**

   Generate complete HTML document (vs content fragment)

   :Type: ``bool``
   :CLI flag: ``--html-renderer-no-standalone``
   :Default: ``True``
   :Importance: core

**css_style**

   CSS inclusion method: inline, embedded, external, or none

   :Type: ``Literal['inline', 'embedded', 'external', 'none']``
   :CLI flag: ``--html-renderer-css-style``
   :Default: ``'embedded'``
   :Choices: ``inline``, ``embedded``, ``external``, ``none``
   :Importance: core

**css_file**

   Path to external CSS file (when css_style='external')

   :Type: ``UnionType[str, NoneType]``
   :CLI flag: ``--html-renderer-css-file``
   :Default: ``None``
   :Importance: advanced

**include_toc**

   Generate table of contents from headings

   :Type: ``bool``
   :CLI flag: ``--html-renderer-include-toc``
   :Default: ``False``
   :Importance: core

**syntax_highlighting**

   Add language classes for syntax highlighting

   :Type: ``bool``
   :CLI flag: ``--html-renderer-no-syntax-highlighting``
   :Default: ``True``
   :Importance: core

**escape_html**

   Escape HTML special characters in text

   :Type: ``bool``
   :CLI flag: ``--html-renderer-no-escape-html``
   :Default: ``True``
   :Importance: security

**math_renderer**

   Math rendering library: mathjax, katex, or none

   :Type: ``Literal['mathjax', 'katex', 'none']``
   :CLI flag: ``--html-renderer-math-renderer``
   :Default: ``'mathjax'``
   :Choices: ``mathjax``, ``katex``, ``none``
   :Importance: core

**html_passthrough_mode**

   How to handle raw HTML content: pass-through, escape, drop, or sanitize

   :Type: ``Literal['pass-through', 'escape', 'drop', 'sanitize']``
   :CLI flag: ``--html-renderer-html-passthrough-mode``
   :Default: ``'escape'``
   :Choices: ``pass-through``, ``escape``, ``drop``, ``sanitize``
   :Importance: security

**language**

   Document language code (ISO 639-1) for HTML lang attribute

   :Type: ``str``
   :CLI flag: ``--html-renderer-language``
   :Default: ``'en'``
   :Importance: advanced

**template_mode**

   Template mode: inject, replace, jinja, or none

   :Type: ``Literal['inject', 'replace', 'jinja'] | None``
   :CLI flag: ``--html-renderer-template-mode``
   :Default: ``None``
   :Choices: ``inject``, ``replace``, ``jinja``
   :Importance: advanced

**template_file**

   Path to template file (required when template_mode is set)

   :Type: ``UnionType[str, NoneType]``
   :CLI flag: ``--html-renderer-template-file``
   :Default: ``None``
   :Importance: advanced

**template_selector**

   CSS selector for injection target (template_mode='inject')

   :Type: ``str``
   :CLI flag: ``--html-renderer-template-selector``
   :Default: ``'#content'``
   :Importance: advanced

**injection_mode**

   How to inject content: append, prepend, or replace

   :Type: ``Literal['append', 'prepend', 'replace']``
   :CLI flag: ``--html-renderer-injection-mode``
   :Default: ``'replace'``
   :Choices: ``append``, ``prepend``, ``replace``
   :Importance: advanced

**content_placeholder**

   Placeholder to replace with content (template_mode='replace')

   :Type: ``str``
   :CLI flag: ``--html-renderer-content-placeholder``
   :Default: ``'{CONTENT}'``
   :Importance: advanced

**css_class_map**

   Map AST node types to custom CSS classes as JSON (e.g., '{"Heading": "prose-heading"}')

   :Type: ``UnionType[dict[str, UnionType[str, list[str]]], NoneType]``
   :CLI flag: ``--html-renderer-css-class-map``
   :Default: ``None``
   :Importance: advanced

**allow_remote_scripts**

   Allow loading remote scripts (e.g., MathJax/KaTeX CDN). Default is False for security - opt-in required for CDN usage.

   :Type: ``bool``
   :CLI flag: ``--html-renderer-allow-remote-scripts``
   :Default: ``False``
   :Importance: security

**csp_enabled**

   Add Content-Security-Policy meta tag to standalone HTML documents

   :Type: ``bool``
   :CLI flag: ``--html-renderer-csp-enabled``
   :Default: ``False``
   :Importance: security

**csp_policy**

   Custom Content-Security-Policy header value. If None, uses default secure policy.

   :Type: ``UnionType[str, NoneType]``
   :CLI flag: ``--html-renderer-csp-policy``
   :Default: ``"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';"``
   :Importance: security

IPYNB Options
~~~~~~~~~~~~~


IPYNB Parser Options
^^^^^^^^^^^^^^^^^^^^

Configuration options for IPYNB-to-Markdown conversion.

This dataclass contains settings specific to Jupyter Notebook processing,
including output handling and image conversion preferences.

Parameters
----------
include_inputs : bool, default True
    Whether to include cell input (source code) in output.
include_outputs : bool, default True
    Whether to include cell outputs in the markdown.
show_execution_count : bool, default False
    Whether to show execution counts for code cells.
output_types : list[str] or None, default ["stream", "execute_result", "display_data"]
    Types of outputs to include. Valid types: "stream", "execute_result", "display_data", "error".
    If None, includes all output types.
image_format : str, default "png"
    Preferred image format for notebook outputs. Options: "png", "jpeg".
image_quality : int, default 85
    JPEG quality setting (1-100) when converting images to JPEG format.
truncate_long_outputs : int or None, default DEFAULT_TRUNCATE_OUTPUT_LINES
    Maximum number of lines for text outputs before truncating.
    If None, outputs are not truncated.
truncate_output_message : str or None, default DEFAULT_TRUNCATE_OUTPUT_MESSAGE
    The message to place to indicate truncated output.

**attachment_mode**

   How to handle attachments/images

   :Type: ``AttachmentMode``
   :CLI flag: ``--ipynb-attachment-mode``
   :Default: ``'alt_text'``
   :Choices: ``skip``, ``alt_text``, ``download``, ``base64``
   :Importance: core

**alt_text_mode**

   How to render alt-text content when using alt_text attachment mode

   :Type: ``AltTextMode``
   :CLI flag: ``--ipynb-alt-text-mode``
   :Default: ``'default'``
   :Choices: ``default``, ``plain_filename``, ``strict_markdown``, ``footnote``
   :Importance: core

**attachment_output_dir**

   Directory to save attachments when using download mode

   :Type: ``str | None``
   :CLI flag: ``--ipynb-attachment-output-dir``
   :Default: ``None``
   :Importance: advanced

**attachment_base_url**

   Base URL for resolving attachment references

   :Type: ``str | None``
   :CLI flag: ``--ipynb-attachment-base-url``
   :Default: ``None``
   :Importance: advanced

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--ipynb-extract-metadata``
   :Default: ``False``
   :Importance: core

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--ipynb-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**attachment_filename_template**

   Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}

   :Type: ``str``
   :CLI flag: ``--ipynb-attachment-filename-template``
   :Default: ``'{stem}_{type}{seq}.{ext}'``
   :Importance: advanced

**attachment_overwrite**

   File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'

   :Type: ``Literal['unique', 'overwrite', 'skip']``
   :CLI flag: ``--ipynb-attachment-overwrite``
   :Default: ``'unique'``
   :Choices: ``unique``, ``overwrite``, ``skip``
   :Importance: advanced

**attachment_deduplicate_by_hash**

   Avoid saving duplicate attachments by content hash

   :Type: ``bool``
   :CLI flag: ``--ipynb-attachment-deduplicate-by-hash``
   :Default: ``False``
   :Importance: advanced

**attachments_footnotes_section**

   Section title for footnote-style attachment references (None to disable)

   :Type: ``str | None``
   :CLI flag: ``--ipynb-attachments-footnotes-section``
   :Default: ``'Attachments'``
   :Importance: advanced

**include_inputs**

   Include cell input (source code) in output

   :Type: ``bool``
   :CLI flag: ``--ipynb-no-include-inputs``
   :Default: ``True``
   :Importance: core

**include_outputs**

   Include cell outputs in the markdown

   :Type: ``bool``
   :CLI flag: ``--ipynb-no-include-outputs``
   :Default: ``True``
   :Importance: core

**show_execution_count**

   Show execution counts for code cells

   :Type: ``bool``
   :CLI flag: ``--ipynb-show-execution-count``
   :Default: ``False``
   :Importance: advanced

**output_types**

   Types of outputs to include (stream, execute_result, display_data, error)

   :Type: ``tuple[str, ...] | None``
   :CLI flag: ``--ipynb-output-types``
   :Default: ``('stream', 'execute_result', 'display_data')``
   :CLI action: ``append``
   :Importance: core

**image_format**

   Preferred image format for notebook outputs (png, jpeg)

   :Type: ``str``
   :CLI flag: ``--ipynb-image-format``
   :Default: ``'png'``
   :Importance: advanced

**image_quality**

   JPEG quality setting (1-100) for image conversion

   :Type: ``int``
   :CLI flag: ``--ipynb-image-quality``
   :Default: ``85``
   :Importance: advanced

**truncate_long_outputs**

   :Type: ``int | None``
   :CLI flag: ``--ipynb-truncate-long-outputs``
   :Default: ``None``

**truncate_output_message**

   :Type: ``str | None``
   :CLI flag: ``--ipynb-truncate-output-message``
   :Default: ``'\n... (output truncated) ...\n'``

LATEX Options
~~~~~~~~~~~~~


LATEX Parser Options
^^^^^^^^^^^^^^^^^^^^

Configuration options for LaTeX-to-AST parsing.

This dataclass contains settings specific to parsing LaTeX documents
into AST representation using pylatexenc library.

Parameters
----------
parse_preamble : bool, default True
    Whether to parse document preamble for metadata.
    When True, extracts \title, \author, \date, etc.
parse_math : bool, default True
    Whether to parse math environments into MathBlock/MathInline nodes.
    When True, preserves LaTeX math notation in AST.
parse_custom_commands : bool, default False
    Whether to attempt parsing custom LaTeX commands.
    SECURITY: Disabled by default to prevent unexpected behavior.
strict_mode : bool, default False
    Whether to raise errors on invalid LaTeX syntax.
    When False, attempts to recover gracefully.
encoding : str, default "utf-8"
    Text encoding to use when reading LaTeX files.
preserve_comments : bool, default False
    Whether to preserve LaTeX comments in the AST.
    When True, comments are stored in node metadata.

**attachment_mode**

   How to handle attachments/images

   :Type: ``AttachmentMode``
   :CLI flag: ``--latex-attachment-mode``
   :Default: ``'alt_text'``
   :Choices: ``skip``, ``alt_text``, ``download``, ``base64``
   :Importance: core

**alt_text_mode**

   How to render alt-text content when using alt_text attachment mode

   :Type: ``AltTextMode``
   :CLI flag: ``--latex-alt-text-mode``
   :Default: ``'default'``
   :Choices: ``default``, ``plain_filename``, ``strict_markdown``, ``footnote``
   :Importance: core

**attachment_output_dir**

   Directory to save attachments when using download mode

   :Type: ``str | None``
   :CLI flag: ``--latex-attachment-output-dir``
   :Default: ``None``
   :Importance: advanced

**attachment_base_url**

   Base URL for resolving attachment references

   :Type: ``str | None``
   :CLI flag: ``--latex-attachment-base-url``
   :Default: ``None``
   :Importance: advanced

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--latex-extract-metadata``
   :Default: ``False``
   :Importance: core

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--latex-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**attachment_filename_template**

   Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}

   :Type: ``str``
   :CLI flag: ``--latex-attachment-filename-template``
   :Default: ``'{stem}_{type}{seq}.{ext}'``
   :Importance: advanced

**attachment_overwrite**

   File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'

   :Type: ``Literal['unique', 'overwrite', 'skip']``
   :CLI flag: ``--latex-attachment-overwrite``
   :Default: ``'unique'``
   :Choices: ``unique``, ``overwrite``, ``skip``
   :Importance: advanced

**attachment_deduplicate_by_hash**

   Avoid saving duplicate attachments by content hash

   :Type: ``bool``
   :CLI flag: ``--latex-attachment-deduplicate-by-hash``
   :Default: ``False``
   :Importance: advanced

**attachments_footnotes_section**

   Section title for footnote-style attachment references (None to disable)

   :Type: ``str | None``
   :CLI flag: ``--latex-attachments-footnotes-section``
   :Default: ``'Attachments'``
   :Importance: advanced

**parse_preamble**

   Parse document preamble for metadata

   :Type: ``bool``
   :CLI flag: ``--latex-no-parse-preamble``
   :Default: ``True``
   :Importance: core

**parse_math**

   Parse math environments into AST math nodes

   :Type: ``bool``
   :CLI flag: ``--latex-no-parse-math``
   :Default: ``True``
   :Importance: core

**parse_custom_commands**

   Parse custom LaTeX commands (SECURITY: disabled by default)

   :Type: ``bool``
   :CLI flag: ``--latex-parse-custom-commands``
   :Default: ``False``
   :Importance: security

**strict_mode**

   Raise errors on invalid LaTeX syntax

   :Type: ``bool``
   :CLI flag: ``--latex-strict-mode``
   :Default: ``False``
   :Importance: advanced

**encoding**

   Text encoding for reading LaTeX files

   :Type: ``str``
   :CLI flag: ``--latex-encoding``
   :Default: ``'utf-8'``
   :Importance: advanced

**preserve_comments**

   Preserve LaTeX comments in AST

   :Type: ``bool``
   :CLI flag: ``--latex-preserve-comments``
   :Default: ``False``
   :Importance: advanced

LATEX Renderer Options
^^^^^^^^^^^^^^^^^^^^^^

Configuration options for AST-to-LaTeX rendering.

This dataclass contains settings for rendering AST documents as
LaTeX output suitable for compilation with pdflatex/xelatex.

Parameters
----------
document_class : str, default "article"
    LaTeX document class to use (article, report, book, etc.).
include_preamble : bool, default True
    Whether to generate a complete document with preamble.
    When False, generates only document body (for inclusion).
packages : list[str], default ["amsmath", "graphicx", "hyperref"]
    LaTeX packages to include in preamble.
math_mode : {"inline", "display"}, default "display"
    Preferred math rendering mode for ambiguous cases.
line_width : int, default 0
    Target line width for text wrapping (0 = no wrapping).
escape_special : bool, default True
    Whether to escape special LaTeX characters ($, %, &, etc.).
    Only disable if input is already LaTeX-safe.
use_unicode : bool, default True
    Whether to allow Unicode characters in output.
    When False, uses LaTeX escapes for special characters.

**fail_on_resource_errors**

   Raise RenderingError on resource failures (images, etc.) instead of logging warnings

   :Type: ``bool``
   :CLI flag: ``--latex-renderer-fail-on-resource-errors``
   :Default: ``False``
   :Importance: advanced

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--latex-renderer-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**document_class**

   LaTeX document class (article, report, book, etc.)

   :Type: ``str``
   :CLI flag: ``--latex-renderer-document-class``
   :Default: ``'article'``
   :Importance: core

**include_preamble**

   Generate complete document with preamble

   :Type: ``bool``
   :CLI flag: ``--latex-renderer-no-include-preamble``
   :Default: ``True``
   :Importance: core

**packages**

   LaTeX packages to include in preamble

   :Type: ``list[str]``
   :CLI flag: ``--latex-renderer-packages``
   :Default factory: ``LatexRendererOptions.<lambda>``
   :Importance: advanced

**math_mode**

   Preferred math rendering mode

   :Type: ``Literal['inline', 'display']``
   :CLI flag: ``--latex-renderer-math-mode``
   :Default: ``'display'``
   :Choices: ``inline``, ``display``
   :Importance: core

**line_width**

   Target line width for wrapping (0 = no wrapping)

   :Type: ``int``
   :CLI flag: ``--latex-renderer-line-width``
   :Default: ``0``
   :Importance: advanced

**escape_special**

   Escape special LaTeX characters

   :Type: ``bool``
   :CLI flag: ``--latex-renderer-no-escape-special``
   :Default: ``True``
   :Importance: security

**use_unicode**

   Allow Unicode characters in output

   :Type: ``bool``
   :CLI flag: ``--latex-renderer-no-use-unicode``
   :Default: ``True``
   :Importance: advanced

MARKDOWN Options
~~~~~~~~~~~~~~~~


MARKDOWN Parser Options
^^^^^^^^^^^^^^^^^^^^^^^

Configuration options for Markdown-to-AST parsing.

This dataclass contains settings specific to parsing Markdown documents
into AST representation, supporting various Markdown flavors and extensions.

Parameters
----------
flavor : {"gfm", "commonmark", "multimarkdown", "pandoc", "kramdown", "markdown_plus"}, default "gfm"
    Markdown flavor to parse. Determines which extensions are enabled.
parse_tables : bool, default True
    Whether to parse table syntax (GFM pipe tables).
parse_footnotes : bool, default True
    Whether to parse footnote references and definitions.
parse_math : bool, default True
    Whether to parse inline ($...$) and block ($$...$$) math.
parse_task_lists : bool, default True
    Whether to parse task list checkboxes (- [ ] and - [x]).
parse_definition_lists : bool, default True
    Whether to parse definition lists (term : definition).
parse_strikethrough : bool, default True
    Whether to parse strikethrough syntax (~~text~~).
strict_parsing : bool, default False
    Whether to raise errors on invalid/ambiguous markdown syntax.
    When False, attempts to recover gracefully.
preserve_html : bool, default True
    Whether to preserve raw HTML in the AST (HTMLBlock/HTMLInline nodes).
    When False, HTML is stripped.

**attachment_mode**

   How to handle attachments/images

   :Type: ``AttachmentMode``
   :CLI flag: ``--markdown-attachment-mode``
   :Default: ``'alt_text'``
   :Choices: ``skip``, ``alt_text``, ``download``, ``base64``
   :Importance: core

**alt_text_mode**

   How to render alt-text content when using alt_text attachment mode

   :Type: ``AltTextMode``
   :CLI flag: ``--markdown-alt-text-mode``
   :Default: ``'default'``
   :Choices: ``default``, ``plain_filename``, ``strict_markdown``, ``footnote``
   :Importance: core

**attachment_output_dir**

   Directory to save attachments when using download mode

   :Type: ``str | None``
   :CLI flag: ``--markdown-attachment-output-dir``
   :Default: ``None``
   :Importance: advanced

**attachment_base_url**

   Base URL for resolving attachment references

   :Type: ``str | None``
   :CLI flag: ``--markdown-attachment-base-url``
   :Default: ``None``
   :Importance: advanced

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--markdown-extract-metadata``
   :Default: ``False``
   :Importance: core

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--markdown-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**attachment_filename_template**

   Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}

   :Type: ``str``
   :CLI flag: ``--markdown-attachment-filename-template``
   :Default: ``'{stem}_{type}{seq}.{ext}'``
   :Importance: advanced

**attachment_overwrite**

   File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'

   :Type: ``Literal['unique', 'overwrite', 'skip']``
   :CLI flag: ``--markdown-attachment-overwrite``
   :Default: ``'unique'``
   :Choices: ``unique``, ``overwrite``, ``skip``
   :Importance: advanced

**attachment_deduplicate_by_hash**

   Avoid saving duplicate attachments by content hash

   :Type: ``bool``
   :CLI flag: ``--markdown-attachment-deduplicate-by-hash``
   :Default: ``False``
   :Importance: advanced

**attachments_footnotes_section**

   Section title for footnote-style attachment references (None to disable)

   :Type: ``str | None``
   :CLI flag: ``--markdown-attachments-footnotes-section``
   :Default: ``'Attachments'``
   :Importance: advanced

**flavor**

   Markdown flavor to parse (determines enabled extensions)

   :Type: ``FlavorType``
   :CLI flag: ``--markdown-flavor``
   :Default: ``'gfm'``
   :Choices: ``gfm``, ``commonmark``, ``multimarkdown``, ``pandoc``, ``kramdown``, ``markdown_plus``
   :Importance: core

**parse_tables**

   Parse table syntax (GFM pipe tables)

   :Type: ``bool``
   :CLI flag: ``--markdown-no-parse-tables``
   :Default: ``True``
   :Importance: core

**parse_footnotes**

   Parse footnote references and definitions

   :Type: ``bool``
   :CLI flag: ``--markdown-no-parse-footnotes``
   :Default: ``True``
   :Importance: core

**parse_math**

   Parse inline and block math ($...$ and $$...$$)

   :Type: ``bool``
   :CLI flag: ``--markdown-no-parse-math``
   :Default: ``True``
   :Importance: core

**parse_task_lists**

   Parse task list checkboxes (- [ ] and - [x])

   :Type: ``bool``
   :CLI flag: ``--markdown-no-parse-task-lists``
   :Default: ``True``
   :Importance: core

**parse_definition_lists**

   Parse definition lists (term : definition)

   :Type: ``bool``
   :CLI flag: ``--markdown-no-parse-definition-lists``
   :Default: ``True``
   :Importance: core

**parse_strikethrough**

   Parse strikethrough syntax (~~text~~)

   :Type: ``bool``
   :CLI flag: ``--markdown-no-parse-strikethrough``
   :Default: ``True``
   :Importance: core

**strict_parsing**

   Raise errors on invalid markdown syntax (vs. graceful recovery)

   :Type: ``bool``
   :CLI flag: ``--markdown-strict-parsing``
   :Default: ``False``
   :Importance: advanced

**preserve_html**

   Preserve raw HTML in AST (HTMLBlock/HTMLInline nodes)

   :Type: ``bool``
   :CLI flag: ``--markdown-no-preserve-html``
   :Default: ``True``
   :Importance: security

MARKDOWN Renderer Options
^^^^^^^^^^^^^^^^^^^^^^^^^

Markdown rendering options for converting AST to Markdown text.

When a flavor is specified, default values for unsupported_table_mode and
unsupported_inline_mode are automatically set to flavor-appropriate values
unless explicitly overridden. This is handled via the __new__ method to
apply flavor-aware defaults before instance creation.

This dataclass contains settings that control how Markdown output is
formatted and structured. These options are used by multiple conversion
modules to ensure consistent Markdown generation.

Parameters
----------
escape_special : bool, default True
    Whether to escape special Markdown characters in text content.
    When True, characters like \*, \_, #, [, ], (, ), \\ are escaped
    to prevent unintended formatting.
emphasis_symbol : {"\*", "\_"}, default "\*"
    Symbol to use for emphasis/italic formatting in Markdown.
bullet_symbols : str, default "\*-+"
    Characters to cycle through for nested bullet lists.
list_indent_width : int, default 4
    Number of spaces to use for each level of list indentation.
underline_mode : {"html", "markdown", "ignore"}, default "html"
    How to handle underlined text:
    - "html": Use <u>text</u> tags
    - "markdown": Use __text__ (non-standard)
    - "ignore": Strip underline formatting
superscript_mode : {"html", "markdown", "ignore"}, default "html"
    How to handle superscript text:
    - "html": Use <sup>text</sup> tags
    - "markdown": Use ^text^ (non-standard)
    - "ignore": Strip superscript formatting
subscript_mode : {"html", "markdown", "ignore"}, default "html"
    How to handle subscript text:
    - "html": Use <sub>text</sub> tags
    - "markdown": Use ~text~ (non-standard)
    - "ignore": Strip subscript formatting
use_hash_headings : bool, default True
    Whether to use # syntax for headings instead of underline style.
    When True, generates "# Heading" style. When False, generates
    "Heading\n=======" style for level 1 and "Heading\n-------" for levels 2+.
flavor : {"gfm", "commonmark", "markdown_plus"}, default "gfm"
    Markdown flavor/dialect to use for output:
    - "gfm": GitHub Flavored Markdown (tables, strikethrough, task lists)
    - "commonmark": Strict CommonMark specification
    - "markdown_plus": All extensions enabled (footnotes, definition lists, etc.)
unsupported_table_mode : {"drop", "ascii", "force", "html"}, default "force"
    How to handle tables when the selected flavor doesn't support them:
    - "drop": Skip table entirely
    - "ascii": Render as ASCII art table
    - "force": Render as pipe table anyway (may not be valid for flavor)
    - "html": Render as HTML <table>
unsupported_inline_mode : {"plain", "force", "html"}, default "plain"
    How to handle inline elements unsupported by the selected flavor:
    - "plain": Render content without the unsupported formatting
    - "force": Use markdown syntax anyway (may not be valid for flavor)
    - "html": Use HTML tags (e.g., <u> for underline)
heading_level_offset : int, default 0
    Shift all heading levels by this amount (positive or negative).
    Useful when collating multiple documents into a parent document with existing structure.
code_fence_char : {"`", "~"}, default "`"
    Character to use for code fences (backtick or tilde).
code_fence_min : int, default 3
    Minimum length for code fences (typically 3).
collapse_blank_lines : bool, default True
    Collapse multiple consecutive blank lines into at most 2 (normalizing whitespace).
link_style : {"inline", "reference"}, default "inline"
    Link style to use:
    - "inline": [text](url) style links
    - "reference": [text][ref] style with reference definitions at end
reference_link_placement : {"end_of_document", "after_block"}, default "end_of_document"
    Where to place reference link definitions when using reference-style links:
    - "end_of_document": All reference definitions at document end (current behavior)
    - "after_block": Reference definitions placed after each block-level element
autolink_bare_urls : bool, default False
    Automatically convert bare URLs (e.g., http://example.com) found in Text nodes
    into Markdown autolinks (<http://example.com>). Ensures all URLs are clickable.
table_pipe_escape : bool, default True
    Whether to escape pipe characters (|) in table cell content.
math_mode : {"latex", "mathml", "html"}, default "latex"
    Preferred math representation for flavors that support math. When the
    requested representation is unavailable on a node, the renderer falls
    back to any available representation while preserving flavor
    constraints.
html_sanitization : {"pass-through", "escape", "drop", "sanitize"}, default "escape"
    How to handle raw HTML content in markdown (HTMLBlock and HTMLInline nodes):
    - "pass-through": Pass HTML through unchanged (use only with trusted content)
    - "escape": HTML-escape the content to show as text (secure default)
    - "drop": Remove HTML content entirely
    - "sanitize": Remove dangerous elements/attributes (requires bleach for best results)
    Note: This does not affect fenced code blocks with language="html", which are
    always rendered as code and are already safe.

**fail_on_resource_errors**

   Raise RenderingError on resource failures (images, etc.) instead of logging warnings

   :Type: ``bool``
   :CLI flag: ``--markdown-renderer-fail-on-resource-errors``
   :Default: ``False``
   :Importance: advanced

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--markdown-renderer-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**escape_special**

   Escape special Markdown characters (e.g. asterisks) in text content

   :Type: ``bool``
   :CLI flag: ``--markdown-renderer-no-escape-special``
   :Default: ``True``
   :Importance: core

**emphasis_symbol**

   Symbol to use for emphasis/italic formatting

   :Type: ``Literal['*', '_']``
   :CLI flag: ``--markdown-renderer-emphasis-symbol``
   :Default: ``'*'``
   :Choices: ``*``, ``_``
   :Importance: core

**bullet_symbols**

   Characters to cycle through for nested bullet lists

   :Type: ``str``
   :CLI flag: ``--markdown-renderer-bullet-symbols``
   :Default: ``'*-+'``
   :Importance: advanced

**list_indent_width**

   Number of spaces to use for each level of list indentation

   :Type: ``int``
   :CLI flag: ``--markdown-renderer-list-indent-width``
   :Default: ``4``
   :Importance: advanced

**underline_mode**

   How to handle underlined text

   :Type: ``Literal['html', 'markdown', 'ignore']``
   :CLI flag: ``--markdown-renderer-underline-mode``
   :Default: ``'html'``
   :Choices: ``html``, ``markdown``, ``ignore``
   :Importance: advanced

**superscript_mode**

   How to handle superscript text

   :Type: ``Literal['html', 'markdown', 'ignore']``
   :CLI flag: ``--markdown-renderer-superscript-mode``
   :Default: ``'html'``
   :Choices: ``html``, ``markdown``, ``ignore``
   :Importance: advanced

**subscript_mode**

   How to handle subscript text

   :Type: ``Literal['html', 'markdown', 'ignore']``
   :CLI flag: ``--markdown-renderer-subscript-mode``
   :Default: ``'html'``
   :Choices: ``html``, ``markdown``, ``ignore``
   :Importance: advanced

**use_hash_headings**

   Use # syntax for headings instead of underline style

   :Type: ``bool``
   :CLI flag: ``--markdown-renderer-no-use-hash-headings``
   :Default: ``True``
   :Importance: core

**flavor**

   Markdown flavor/dialect to use for output

   :Type: ``Literal['gfm', 'commonmark', 'multimarkdown', 'pandoc', 'kramdown', 'markdown_plus']``
   :CLI flag: ``--markdown-renderer-flavor``
   :Default: ``'gfm'``
   :Choices: ``gfm``, ``commonmark``, ``multimarkdown``, ``pandoc``, ``kramdown``, ``markdown_plus``
   :Importance: core

**unsupported_table_mode**

   How to handle tables when flavor doesn't support them: drop (skip entirely), ascii (render as ASCII art), force (render as pipe tables anyway), html (render as HTML table)

   :Type: ``Literal['drop', 'ascii', 'force', 'html'] | object``
   :CLI flag: ``--markdown-renderer-unsupported-table-mode``
   :Default: ``<object object at 0x7fb9cf8a8a90>``
   :Choices: ``drop``, ``ascii``, ``force``, ``html``
   :Importance: advanced

**unsupported_inline_mode**

   How to handle inline elements unsupported by flavor: plain (render content without formatting), force (use markdown syntax anyway), html (use HTML tags)

   :Type: ``Literal['plain', 'force', 'html'] | object``
   :CLI flag: ``--markdown-renderer-unsupported-inline-mode``
   :Default: ``<object object at 0x7fb9cf8a8a90>``
   :Choices: ``plain``, ``force``, ``html``
   :Importance: advanced

**pad_table_cells**

   Pad table cells with spaces for visual alignment in source

   :Type: ``bool``
   :CLI flag: ``--markdown-renderer-pad-table-cells``
   :Default: ``False``
   :Importance: advanced

**prefer_setext_headings**

   Prefer setext-style headings (underlines) for h1 and h2

   :Type: ``bool``
   :CLI flag: ``--markdown-renderer-prefer-setext-headings``
   :Default: ``False``
   :Importance: advanced

**max_line_width**

   Maximum line width for wrapping (None for no limit)

   :Type: ``UnionType[int, NoneType]``
   :CLI flag: ``--markdown-renderer-max-line-width``
   :Default: ``None``
   :Importance: advanced

**table_alignment_default**

   Default alignment for table columns without explicit alignment

   :Type: ``str``
   :CLI flag: ``--markdown-renderer-table-alignment-default``
   :Default: ``'left'``
   :Choices: ``left``, ``center``, ``right``
   :Importance: advanced

**heading_level_offset**

   Shift all heading levels by this amount (useful when collating docs)

   :Type: ``int``
   :CLI flag: ``--markdown-renderer-heading-level-offset``
   :Default: ``0``
   :Importance: advanced

**code_fence_char**

   Character to use for code fences (backtick or tilde)

   :Type: ``Literal['`', '~']``
   :CLI flag: ``--markdown-renderer-code-fence-char``
   :Default: ``'`'``
   :Choices: `````, ``~``
   :Importance: advanced

**code_fence_min**

   Minimum length for code fences (typically 3)

   :Type: ``int``
   :CLI flag: ``--markdown-renderer-code-fence-min``
   :Default: ``3``
   :Importance: advanced

**collapse_blank_lines**

   Collapse multiple blank lines into at most 2 (normalize whitespace)

   :Type: ``bool``
   :CLI flag: ``--markdown-renderer-no-collapse-blank-lines``
   :Default: ``True``
   :Importance: core

**link_style**

   Link style: inline [text](url) or reference [text][ref]

   :Type: ``Literal['inline', 'reference']``
   :CLI flag: ``--markdown-renderer-link-style``
   :Default: ``'inline'``
   :Choices: ``inline``, ``reference``
   :Importance: core

**reference_link_placement**

   Where to place reference link definitions: end_of_document or after_block

   :Type: ``Literal['end_of_document', 'after_block']``
   :CLI flag: ``--markdown-renderer-reference-link-placement``
   :Default: ``'end_of_document'``
   :Choices: ``end_of_document``, ``after_block``
   :Importance: advanced

**autolink_bare_urls**

   Convert bare URLs in text to Markdown autolinks (<http://...>)

   :Type: ``bool``
   :CLI flag: ``--markdown-renderer-autolink-bare-urls``
   :Default: ``False``
   :Importance: core

**table_pipe_escape**

   Escape pipe characters in table cells

   :Type: ``bool``
   :CLI flag: ``--markdown-renderer-no-table-pipe-escape``
   :Default: ``True``
   :Importance: core

**math_mode**

   Preferred math representation: latex, mathml, or html

   :Type: ``Literal['latex', 'mathml', 'html']``
   :CLI flag: ``--markdown-renderer-math-mode``
   :Default: ``'latex'``
   :Choices: ``latex``, ``mathml``, ``html``
   :Importance: core

**metadata_frontmatter**

   Render document metadata as YAML frontmatter

   :Type: ``bool``
   :CLI flag: ``--markdown-renderer-metadata-frontmatter``
   :Default: ``False``
   :Importance: core

**metadata_format**

   Format for metadata frontmatter: yaml, toml, or json

   :Type: ``Literal['yaml', 'toml', 'json']``
   :CLI flag: ``--markdown-renderer-metadata-format``
   :Default: ``'yaml'``
   :Choices: ``yaml``, ``toml``, ``json``
   :Importance: advanced

**html_sanitization**

   How to handle raw HTML content in markdown: pass-through (allow HTML as-is), escape (show as text), drop (remove entirely), sanitize (remove dangerous elements). Default is 'escape' for security. Does not affect code blocks.

   :Type: ``Literal['pass-through', 'escape', 'drop', 'sanitize']``
   :CLI flag: ``--markdown-renderer-html-sanitization``
   :Default: ``'escape'``
   :Choices: ``pass-through``, ``escape``, ``drop``, ``sanitize``
   :Importance: security

MEDIAWIKI Options
~~~~~~~~~~~~~~~~~


MEDIAWIKI Renderer Options
^^^^^^^^^^^^^^^^^^^^^^^^^^

Configuration options for MediaWiki rendering.

This dataclass contains settings for rendering AST documents as
MediaWiki markup, suitable for Wikipedia and other MediaWiki-based wikis.

Parameters
----------
use_html_for_unsupported : bool, default True
    Whether to use HTML tags as fallback for unsupported elements.
    When True, unsupported formatting uses HTML tags (e.g., <u>underline</u>).
    When False, unsupported formatting is stripped.
image_thumb : bool, default True
    Whether to render images as thumbnails.
    When True, images use |thumb option in MediaWiki syntax.
    When False, images are rendered at full size.
html_passthrough_mode : {"pass-through", "escape", "drop", "sanitize"}, default "pass-through"
    How to handle HTMLBlock and HTMLInline nodes:
    - "pass-through": Pass through unchanged (use only with trusted content)
    - "escape": HTML-escape the content
    - "drop": Remove HTML content entirely
    - "sanitize": Remove dangerous elements/attributes (requires bleach for best results)

Examples
--------
Basic MediaWiki rendering:
    >>> from all2md.ast import Document, Heading, Text
    >>> from all2md.renderers.mediawiki import MediaWikiRenderer
    >>> from all2md.options.mediawiki import MediaWikiOptions
    >>> doc = Document(children=[
    ...     Heading(level=1, content=[Text(content="Title")])
    ... ])
    >>> options = MediaWikiOptions()
    >>> renderer = MediaWikiRenderer(options)
    >>> wiki_text = renderer.render_to_string(doc)

**fail_on_resource_errors**

   Raise RenderingError on resource failures (images, etc.) instead of logging warnings

   :Type: ``bool``
   :CLI flag: ``--mediawiki-renderer-fail-on-resource-errors``
   :Default: ``False``
   :Importance: advanced

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--mediawiki-renderer-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**use_html_for_unsupported**

   Use HTML tags for unsupported elements

   :Type: ``bool``
   :CLI flag: ``--mediawiki-renderer-no-use-html-for-unsupported``
   :Default: ``True``
   :Importance: core

**image_thumb**

   Render images as thumbnails

   :Type: ``bool``
   :CLI flag: ``--mediawiki-renderer-no-image-thumb``
   :Default: ``True``
   :Importance: core

**html_passthrough_mode**

   How to handle raw HTML content: pass-through, escape, drop, or sanitize

   :Type: ``Literal['pass-through', 'escape', 'drop', 'sanitize']``
   :CLI flag: ``--mediawiki-renderer-html-passthrough-mode``
   :Default: ``'pass-through'``
   :Choices: ``pass-through``, ``escape``, ``drop``, ``sanitize``
   :Importance: security

MHTML Options
~~~~~~~~~~~~~


MHTML Parser Options
^^^^^^^^^^^^^^^^^^^^

Configuration options for MHTML-to-Markdown conversion.

This dataclass contains settings specific to MHTML file processing,
primarily for handling embedded assets like images and local file security.

Parameters
----------
Inherited from HtmlOptions

**attachment_mode**

   How to handle attachments/images

   :Type: ``AttachmentMode``
   :CLI flag: ``--mhtml-attachment-mode``
   :Default: ``'alt_text'``
   :Choices: ``skip``, ``alt_text``, ``download``, ``base64``
   :Importance: core

**alt_text_mode**

   How to render alt-text content when using alt_text attachment mode

   :Type: ``AltTextMode``
   :CLI flag: ``--mhtml-alt-text-mode``
   :Default: ``'default'``
   :Choices: ``default``, ``plain_filename``, ``strict_markdown``, ``footnote``
   :Importance: core

**attachment_output_dir**

   Directory to save attachments when using download mode

   :Type: ``str | None``
   :CLI flag: ``--mhtml-attachment-output-dir``
   :Default: ``None``
   :Importance: advanced

**attachment_base_url**

   Base URL for resolving attachment references

   :Type: ``str | None``
   :CLI flag: ``--mhtml-attachment-base-url``
   :Default: ``None``
   :Importance: advanced

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--mhtml-extract-metadata``
   :Default: ``False``
   :Importance: core

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--mhtml-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**attachment_filename_template**

   Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}

   :Type: ``str``
   :CLI flag: ``--mhtml-attachment-filename-template``
   :Default: ``'{stem}_{type}{seq}.{ext}'``
   :Importance: advanced

**attachment_overwrite**

   File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'

   :Type: ``Literal['unique', 'overwrite', 'skip']``
   :CLI flag: ``--mhtml-attachment-overwrite``
   :Default: ``'unique'``
   :Choices: ``unique``, ``overwrite``, ``skip``
   :Importance: advanced

**attachment_deduplicate_by_hash**

   Avoid saving duplicate attachments by content hash

   :Type: ``bool``
   :CLI flag: ``--mhtml-attachment-deduplicate-by-hash``
   :Default: ``False``
   :Importance: advanced

**attachments_footnotes_section**

   Section title for footnote-style attachment references (None to disable)

   :Type: ``str | None``
   :CLI flag: ``--mhtml-attachments-footnotes-section``
   :Default: ``'Attachments'``
   :Importance: advanced

**extract_title**

   Extract and use HTML <title> element as main heading

   :Type: ``bool``
   :CLI flag: ``--mhtml-extract-title``
   :Default: ``False``
   :Importance: core

**convert_nbsp**

   Convert non-breaking spaces (&nbsp;) to regular spaces

   :Type: ``bool``
   :CLI flag: ``--mhtml-convert-nbsp``
   :Default: ``False``
   :Importance: core

**strip_dangerous_elements**

   Remove potentially dangerous HTML elements (script, style, etc.)

   :Type: ``bool``
   :CLI flag: ``--mhtml-strip-dangerous-elements``
   :Default: ``False``
   :Importance: security

**detect_table_alignment**

   Automatically detect table column alignment from CSS/attributes

   :Type: ``bool``
   :CLI flag: ``--mhtml-no-detect-table-alignment``
   :Default: ``True``
   :Importance: core

**network**

   Network security settings for remote resource fetching

   :Type: ``NetworkFetchOptions``
   :CLI flag: ``--mhtml-network``
   :Default factory: ``NetworkFetchOptions``

**local_files**

   Local file access security settings

   :Type: ``LocalFileAccessOptions``
   :CLI flag: ``--mhtml-local-files``
   :Default factory: ``LocalFileAccessOptions``

**preserve_nested_structure**

   Maintain proper nesting for blockquotes and other elements

   :Type: ``bool``
   :CLI flag: ``--mhtml-no-preserve-nested-structure``
   :Default: ``True``
   :Importance: core

**strip_comments**

   Remove HTML comments from output

   :Type: ``bool``
   :CLI flag: ``--mhtml-no-strip-comments``
   :Default: ``True``
   :Importance: core

**collapse_whitespace**

   Collapse multiple spaces/newlines into single spaces

   :Type: ``bool``
   :CLI flag: ``--mhtml-no-collapse-whitespace``
   :Default: ``True``
   :Importance: core

**br_handling**

   How to handle <br> tags: 'newline' or 'space'

   :Type: ``Literal['newline', 'space']``
   :CLI flag: ``--mhtml-br-handling``
   :Default: ``'newline'``
   :Choices: ``newline``, ``space``
   :Importance: advanced

**allowed_elements**

   Whitelist of allowed HTML elements (if set, only these are processed)

   :Type: ``tuple[str, ...] | None``
   :CLI flag: ``--mhtml-allowed-elements``
   :Default: ``None``
   :CLI action: ``append``
   :Importance: security

**allowed_attributes**

   Whitelist of allowed HTML attributes. Can be a tuple of attribute names (global allowlist) or a dict mapping element names to tuples of allowed attributes (per-element allowlist). Examples: ('class', 'id') or {'img': ('src', 'alt', 'title'), 'a': ('href', 'title')}

   :Type: ``tuple[str, ...] | dict[str, tuple[str, ...]] | None``
   :CLI flag: ``--mhtml-allowed-attributes``
   :Default: ``None``
   :CLI action: ``append``
   :Importance: security

**figure_rendering**

   How to render <figure> elements: blockquote, image_with_caption, html

   :Type: ``Literal['blockquote', 'image_with_caption', 'html']``
   :CLI flag: ``--mhtml-figure-rendering``
   :Default: ``'blockquote'``
   :Choices: ``blockquote``, ``image_with_caption``, ``html``
   :Importance: advanced

**details_rendering**

   How to render <details>/<summary> elements: blockquote, html, ignore

   :Type: ``Literal['blockquote', 'html', 'ignore']``
   :CLI flag: ``--mhtml-details-rendering``
   :Default: ``'blockquote'``
   :Choices: ``blockquote``, ``html``, ``ignore``
   :Importance: advanced

**extract_microdata**

   Extract microdata and structured data to metadata

   :Type: ``bool``
   :CLI flag: ``--mhtml-no-extract-microdata``
   :Default: ``True``
   :Importance: advanced

**base_url**

   Base URL for resolving relative hrefs in <a> tags (separate from attachment_base_url for images)

   :Type: ``str | None``
   :CLI flag: ``--mhtml-base-url``
   :Default: ``None``
   :Importance: advanced

ODP Options
~~~~~~~~~~~


ODP Parser Options
^^^^^^^^^^^^^^^^^^

Configuration options for ODP-to-Markdown conversion.

This dataclass contains settings specific to OpenDocument Presentation (ODP)
processing, including slide selection, numbering, and notes.

Parameters
----------
preserve_tables : bool, default True
    Whether to preserve table formatting in Markdown.
include_slide_numbers : bool, default False
    Whether to include slide numbers in the output.
include_notes : bool, default True
    Whether to include speaker notes in the conversion.
page_separator_template : str, default "---"
    Template for slide separators. Supports placeholders: {page_num}, {total_pages}.
slides : str or None, default None
    Slide selection (e.g., "1,3-5,8" for slides 1, 3-5, and 8).

**attachment_mode**

   How to handle attachments/images

   :Type: ``AttachmentMode``
   :CLI flag: ``--odp-attachment-mode``
   :Default: ``'alt_text'``
   :Choices: ``skip``, ``alt_text``, ``download``, ``base64``
   :Importance: core

**alt_text_mode**

   How to render alt-text content when using alt_text attachment mode

   :Type: ``AltTextMode``
   :CLI flag: ``--odp-alt-text-mode``
   :Default: ``'default'``
   :Choices: ``default``, ``plain_filename``, ``strict_markdown``, ``footnote``
   :Importance: core

**attachment_output_dir**

   Directory to save attachments when using download mode

   :Type: ``str | None``
   :CLI flag: ``--odp-attachment-output-dir``
   :Default: ``None``
   :Importance: advanced

**attachment_base_url**

   Base URL for resolving attachment references

   :Type: ``str | None``
   :CLI flag: ``--odp-attachment-base-url``
   :Default: ``None``
   :Importance: advanced

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--odp-extract-metadata``
   :Default: ``False``
   :Importance: core

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--odp-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**attachment_filename_template**

   Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}

   :Type: ``str``
   :CLI flag: ``--odp-attachment-filename-template``
   :Default: ``'{stem}_{type}{seq}.{ext}'``
   :Importance: advanced

**attachment_overwrite**

   File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'

   :Type: ``Literal['unique', 'overwrite', 'skip']``
   :CLI flag: ``--odp-attachment-overwrite``
   :Default: ``'unique'``
   :Choices: ``unique``, ``overwrite``, ``skip``
   :Importance: advanced

**attachment_deduplicate_by_hash**

   Avoid saving duplicate attachments by content hash

   :Type: ``bool``
   :CLI flag: ``--odp-attachment-deduplicate-by-hash``
   :Default: ``False``
   :Importance: advanced

**attachments_footnotes_section**

   Section title for footnote-style attachment references (None to disable)

   :Type: ``str | None``
   :CLI flag: ``--odp-attachments-footnotes-section``
   :Default: ``'Attachments'``
   :Importance: advanced

**page_separator_template**

   Template for page/slide separators. Supports placeholders: {page_num}, {total_pages}. This string is inserted between pages/slides

   :Type: ``str``
   :CLI flag: ``--odp-page-separator-template``
   :Default: ``'-----'``
   :Importance: advanced

**preserve_tables**

   Preserve table formatting in Markdown

   :Type: ``bool``
   :CLI flag: ``--odp-no-preserve-tables``
   :Default: ``True``
   :Importance: core

**include_slide_numbers**

   Include slide numbers in output

   :Type: ``bool``
   :CLI flag: ``--odp-include-slide-numbers``
   :Default: ``False``
   :Importance: core

**include_notes**

   Include speaker notes from slides

   :Type: ``bool``
   :CLI flag: ``--odp-no-include-notes``
   :Default: ``True``
   :Importance: core

**slides**

   Slide selection (e.g., '1,3-5,8' for slides 1, 3-5, and 8)

   :Type: ``str | None``
   :CLI flag: ``--odp-slides``
   :Default: ``None``
   :Importance: core

ODS Options
~~~~~~~~~~~


ODS Parser Options
^^^^^^^^^^^^^^^^^^

Configuration options for ODS spreadsheet conversion.

This dataclass inherits all spreadsheet options from SpreadsheetParserOptions
and adds ODS-specific options.

Parameters
----------
has_header : bool, default True
    Whether the first row contains column headers.

See SpreadsheetParserOptions for complete documentation of inherited options.

**attachment_mode**

   How to handle attachments/images

   :Type: ``AttachmentMode``
   :CLI flag: ``--ods-attachment-mode``
   :Default: ``'alt_text'``
   :Choices: ``skip``, ``alt_text``, ``download``, ``base64``
   :Importance: core

**alt_text_mode**

   How to render alt-text content when using alt_text attachment mode

   :Type: ``AltTextMode``
   :CLI flag: ``--ods-alt-text-mode``
   :Default: ``'default'``
   :Choices: ``default``, ``plain_filename``, ``strict_markdown``, ``footnote``
   :Importance: core

**attachment_output_dir**

   Directory to save attachments when using download mode

   :Type: ``str | None``
   :CLI flag: ``--ods-attachment-output-dir``
   :Default: ``None``
   :Importance: advanced

**attachment_base_url**

   Base URL for resolving attachment references

   :Type: ``str | None``
   :CLI flag: ``--ods-attachment-base-url``
   :Default: ``None``
   :Importance: advanced

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--ods-extract-metadata``
   :Default: ``False``
   :Importance: core

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--ods-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**attachment_filename_template**

   Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}

   :Type: ``str``
   :CLI flag: ``--ods-attachment-filename-template``
   :Default: ``'{stem}_{type}{seq}.{ext}'``
   :Importance: advanced

**attachment_overwrite**

   File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'

   :Type: ``Literal['unique', 'overwrite', 'skip']``
   :CLI flag: ``--ods-attachment-overwrite``
   :Default: ``'unique'``
   :Choices: ``unique``, ``overwrite``, ``skip``
   :Importance: advanced

**attachment_deduplicate_by_hash**

   Avoid saving duplicate attachments by content hash

   :Type: ``bool``
   :CLI flag: ``--ods-attachment-deduplicate-by-hash``
   :Default: ``False``
   :Importance: advanced

**attachments_footnotes_section**

   Section title for footnote-style attachment references (None to disable)

   :Type: ``str | None``
   :CLI flag: ``--ods-attachments-footnotes-section``
   :Default: ``'Attachments'``
   :Importance: advanced

**sheets**

   Sheet names to include (list or regex pattern). default = all sheets

   :Type: ``Union[list[str], str, None]``
   :CLI flag: ``--ods-sheets``
   :Default: ``None``
   :Importance: core

**include_sheet_titles**

   Prepend each sheet with '## {sheet_name}' heading

   :Type: ``bool``
   :CLI flag: ``--ods-no-include-sheet-titles``
   :Default: ``True``
   :Importance: core

**render_formulas**

   Use stored cell values (True) or show formulas (False)

   :Type: ``bool``
   :CLI flag: ``--ods-no-render-formulas``
   :Default: ``True``
   :Importance: core

**max_rows**

   Maximum rows per table (None = unlimited)

   :Type: ``Optional[int]``
   :CLI flag: ``--ods-max-rows``
   :Default: ``None``
   :Importance: advanced

**max_cols**

   Maximum columns per table (None = unlimited)

   :Type: ``Optional[int]``
   :CLI flag: ``--ods-max-cols``
   :Default: ``None``
   :Importance: advanced

**truncation_indicator**

   Note appended when rows/columns are truncated

   :Type: ``str``
   :CLI flag: ``--ods-truncation-indicator``
   :Default: ``'...'``
   :Importance: advanced

**preserve_newlines_in_cells**

   Preserve line breaks within cells as <br> tags

   :Type: ``bool``
   :CLI flag: ``--ods-preserve-newlines-in-cells``
   :Default: ``False``

**trim_empty**

   Trim empty rows/columns: none, leading, trailing, or both

   :Type: ``Literal['none', 'leading', 'trailing', 'both']``
   :CLI flag: ``--ods-trim-empty``
   :Default: ``'trailing'``
   :Choices: ``none``, ``leading``, ``trailing``, ``both``
   :Importance: core

**header_case**

   Transform header case: preserve, title, upper, or lower

   :Type: ``HeaderCaseOption``
   :CLI flag: ``--ods-header-case``
   :Default: ``'preserve'``
   :Choices: ``preserve``, ``title``, ``upper``, ``lower``
   :Importance: core

**chart_mode**

   Chart handling mode: 'data' (extract as tables) or 'skip' (ignore charts, default)

   :Type: ``Literal['data', 'skip']``
   :CLI flag: ``--ods-chart-mode``
   :Default: ``'skip'``
   :Choices: ``data``, ``skip``
   :Importance: advanced

**merged_cell_mode**

   Merged cell handling: 'spans' (use colspan/rowspan), 'flatten' (empty strings), or 'skip'

   :Type: ``Literal['spans', 'flatten', 'skip']``
   :CLI flag: ``--ods-merged-cell-mode``
   :Default: ``'flatten'``
   :Choices: ``spans``, ``flatten``, ``skip``
   :Importance: advanced

**has_header**

   Whether the first row contains column headers

   :Type: ``bool``
   :CLI flag: ``--ods-no-has-header``
   :Default: ``True``
   :Importance: core

ODT Options
~~~~~~~~~~~


ODT Parser Options
^^^^^^^^^^^^^^^^^^

Configuration options for ODT-to-Markdown conversion.

This dataclass contains settings specific to OpenDocument Text (ODT)
processing, including table preservation, footnotes, and comments.

Parameters
----------
preserve_tables : bool, default True
    Whether to preserve table formatting in Markdown.
preserve_comments : bool, default False
    Whether to include document comments in output.
include_footnotes : bool, default True
    Whether to include footnotes in output.
include_endnotes : bool, default True
    Whether to include endnotes in output.

**attachment_mode**

   How to handle attachments/images

   :Type: ``AttachmentMode``
   :CLI flag: ``--odt-attachment-mode``
   :Default: ``'alt_text'``
   :Choices: ``skip``, ``alt_text``, ``download``, ``base64``
   :Importance: core

**alt_text_mode**

   How to render alt-text content when using alt_text attachment mode

   :Type: ``AltTextMode``
   :CLI flag: ``--odt-alt-text-mode``
   :Default: ``'default'``
   :Choices: ``default``, ``plain_filename``, ``strict_markdown``, ``footnote``
   :Importance: core

**attachment_output_dir**

   Directory to save attachments when using download mode

   :Type: ``str | None``
   :CLI flag: ``--odt-attachment-output-dir``
   :Default: ``None``
   :Importance: advanced

**attachment_base_url**

   Base URL for resolving attachment references

   :Type: ``str | None``
   :CLI flag: ``--odt-attachment-base-url``
   :Default: ``None``
   :Importance: advanced

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--odt-extract-metadata``
   :Default: ``False``
   :Importance: core

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--odt-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**attachment_filename_template**

   Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}

   :Type: ``str``
   :CLI flag: ``--odt-attachment-filename-template``
   :Default: ``'{stem}_{type}{seq}.{ext}'``
   :Importance: advanced

**attachment_overwrite**

   File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'

   :Type: ``Literal['unique', 'overwrite', 'skip']``
   :CLI flag: ``--odt-attachment-overwrite``
   :Default: ``'unique'``
   :Choices: ``unique``, ``overwrite``, ``skip``
   :Importance: advanced

**attachment_deduplicate_by_hash**

   Avoid saving duplicate attachments by content hash

   :Type: ``bool``
   :CLI flag: ``--odt-attachment-deduplicate-by-hash``
   :Default: ``False``
   :Importance: advanced

**attachments_footnotes_section**

   Section title for footnote-style attachment references (None to disable)

   :Type: ``str | None``
   :CLI flag: ``--odt-attachments-footnotes-section``
   :Default: ``'Attachments'``
   :Importance: advanced

**preserve_tables**

   Preserve table formatting in Markdown

   :Type: ``bool``
   :CLI flag: ``--odt-no-preserve-tables``
   :Default: ``True``
   :Importance: core

**preserve_comments**

   Include document comments in output

   :Type: ``bool``
   :CLI flag: ``--odt-preserve-comments``
   :Default: ``False``
   :Importance: advanced

**include_footnotes**

   Include footnotes in output

   :Type: ``bool``
   :CLI flag: ``--odt-no-include-footnotes``
   :Default: ``True``
   :Importance: core

**include_endnotes**

   Include endnotes in output

   :Type: ``bool``
   :CLI flag: ``--odt-no-include-endnotes``
   :Default: ``True``
   :Importance: core

ORG Options
~~~~~~~~~~~


ORG Parser Options
^^^^^^^^^^^^^^^^^^

Configuration options for Org-Mode-to-AST parsing.

This dataclass contains settings specific to parsing Org-Mode documents
into AST representation using orgparse.

Parameters
----------
parse_drawers : bool, default True
    Whether to parse Org drawers (e.g., :PROPERTIES:, :LOGBOOK:).
    When True, drawer contents are preserved in metadata.
    When False, drawers are ignored.
parse_properties : bool, default True
    Whether to parse Org properties within drawers.
    When True, properties are extracted and stored in metadata.
parse_tags : bool, default True
    Whether to parse heading tags (e.g., :work:urgent:).
    When True, tags are extracted and stored in heading metadata.
todo_keywords : list[str], default ["TODO", "DONE"]
    List of TODO keywords to recognize in headings.
    Common keywords: TODO, DONE, IN-PROGRESS, WAITING, CANCELLED, etc.

Examples
--------
Basic usage:
    >>> options = OrgParserOptions()
    >>> parser = OrgParser(options)

Custom TODO keywords:
    >>> options = OrgParserOptions(
    ...     todo_keywords=["TODO", "IN-PROGRESS", "DONE", "CANCELLED"]
    ... )

**attachment_mode**

   How to handle attachments/images

   :Type: ``AttachmentMode``
   :CLI flag: ``--org-attachment-mode``
   :Default: ``'alt_text'``
   :Choices: ``skip``, ``alt_text``, ``download``, ``base64``
   :Importance: core

**alt_text_mode**

   How to render alt-text content when using alt_text attachment mode

   :Type: ``AltTextMode``
   :CLI flag: ``--org-alt-text-mode``
   :Default: ``'default'``
   :Choices: ``default``, ``plain_filename``, ``strict_markdown``, ``footnote``
   :Importance: core

**attachment_output_dir**

   Directory to save attachments when using download mode

   :Type: ``str | None``
   :CLI flag: ``--org-attachment-output-dir``
   :Default: ``None``
   :Importance: advanced

**attachment_base_url**

   Base URL for resolving attachment references

   :Type: ``str | None``
   :CLI flag: ``--org-attachment-base-url``
   :Default: ``None``
   :Importance: advanced

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--org-extract-metadata``
   :Default: ``False``
   :Importance: core

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--org-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**attachment_filename_template**

   Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}

   :Type: ``str``
   :CLI flag: ``--org-attachment-filename-template``
   :Default: ``'{stem}_{type}{seq}.{ext}'``
   :Importance: advanced

**attachment_overwrite**

   File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'

   :Type: ``Literal['unique', 'overwrite', 'skip']``
   :CLI flag: ``--org-attachment-overwrite``
   :Default: ``'unique'``
   :Choices: ``unique``, ``overwrite``, ``skip``
   :Importance: advanced

**attachment_deduplicate_by_hash**

   Avoid saving duplicate attachments by content hash

   :Type: ``bool``
   :CLI flag: ``--org-attachment-deduplicate-by-hash``
   :Default: ``False``
   :Importance: advanced

**attachments_footnotes_section**

   Section title for footnote-style attachment references (None to disable)

   :Type: ``str | None``
   :CLI flag: ``--org-attachments-footnotes-section``
   :Default: ``'Attachments'``
   :Importance: advanced

**parse_drawers**

   Parse Org drawers (e.g., :PROPERTIES:, :LOGBOOK:)

   :Type: ``bool``
   :CLI flag: ``--org-no-parse-drawers``
   :Default: ``True``
   :Importance: core

**parse_properties**

   Parse Org properties within drawers

   :Type: ``bool``
   :CLI flag: ``--org-no-parse-properties``
   :Default: ``True``
   :Importance: core

**parse_tags**

   Parse heading tags (e.g., :work:urgent:)

   :Type: ``bool``
   :CLI flag: ``--org-no-parse-tags``
   :Default: ``True``
   :Importance: core

**todo_keywords**

   List of TODO keywords to recognize

   :Type: ``list[str]``
   :CLI flag: ``--org-todo-keywords``
   :Default factory: ``OrgParserOptions.<lambda>``
   :Importance: core

ORG Renderer Options
^^^^^^^^^^^^^^^^^^^^

Configuration options for AST-to-Org-Mode rendering.

This dataclass contains settings for rendering AST documents as
Org-Mode output.

Parameters
----------
heading_style : {"stars"}, default "stars"
    Style for rendering headings. Currently only "stars" is supported
    (e.g., * Level 1, ** Level 2, *** Level 3).
preserve_drawers : bool, default False
    Whether to preserve drawer content in rendered output.
    When True, drawers stored in metadata are rendered back.
preserve_properties : bool, default True
    Whether to preserve properties in rendered output.
    When True, properties stored in metadata are rendered in :PROPERTIES: drawer.
preserve_tags : bool, default True
    Whether to preserve heading tags in rendered output.
    When True, tags stored in metadata are rendered (e.g., :work:urgent:).
todo_keywords : list[str], default ["TODO", "DONE"]
    List of TODO keywords that may appear in headings.
    Used for validation and rendering.

Notes
-----
**Heading Rendering:**
    Headings are rendered with stars (*, **, ***, etc.) based on level.
    TODO states and tags are preserved if present in metadata.

**TODO States:**
    If a heading has metadata["org_todo_state"], it's rendered before the heading text.
    Example: * TODO Write documentation

**Tags:**
    If preserve_tags is True and metadata["org_tags"] exists, tags are rendered.
    Example: * Heading :work:urgent:

**Properties:**
    If preserve_properties is True and metadata["org_properties"] exists,
    a :PROPERTIES: drawer is rendered under the heading.

**fail_on_resource_errors**

   Raise RenderingError on resource failures (images, etc.) instead of logging warnings

   :Type: ``bool``
   :CLI flag: ``--org-renderer-fail-on-resource-errors``
   :Default: ``False``
   :Importance: advanced

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--org-renderer-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**heading_style**

   Style for rendering headings

   :Type: ``Literal['stars']``
   :CLI flag: ``--org-renderer-heading-style``
   :Default: ``'stars'``
   :Choices: ``stars``
   :Importance: advanced

**preserve_drawers**

   Preserve drawer content in rendered output

   :Type: ``bool``
   :CLI flag: ``--org-renderer-no-preserve-drawers``
   :Default: ``False``
   :Importance: advanced

**preserve_properties**

   Preserve properties in rendered output

   :Type: ``bool``
   :CLI flag: ``--org-renderer-no-preserve-properties``
   :Default: ``True``
   :Importance: core

**preserve_tags**

   Preserve heading tags in rendered output

   :Type: ``bool``
   :CLI flag: ``--org-renderer-no-preserve-tags``
   :Default: ``True``
   :Importance: core

**todo_keywords**

   List of TODO keywords

   :Type: ``list[str]``
   :CLI flag: ``--org-renderer-todo-keywords``
   :Default factory: ``OrgRendererOptions.<lambda>``
   :Importance: core

PDF Options
~~~~~~~~~~~


PDF Parser Options
^^^^^^^^^^^^^^^^^^

Configuration options for PDF-to-Markdown conversion.

This dataclass contains settings specific to PDF document processing,
including page selection, image handling, and formatting preferences.

Parameters
----------
pages : list[int], str, or None, default None
    Pages to convert (1-based indexing, like "page 1, page 2").
    Can be a list [1, 2, 3] or string range "1-3,5,10-".
    If None, converts all pages.
password : str or None, default None
    Password for encrypted PDF documents.

# Header detection parameters
header_sample_pages : int | list[int] | None, default None
    Pages to sample for header font size analysis. If None, samples all pages.
header_percentile_threshold : float, default 75
    Percentile threshold for header detection (e.g., 75 = top 25% of font sizes).
header_min_occurrences : int, default 3
    Minimum occurrences of a font size to consider it for headers.
header_size_allowlist : list[float] | None, default None
    Specific font sizes to always treat as headers.
header_size_denylist : list[float] | None, default None
    Font sizes to never treat as headers.
header_use_font_weight : bool, default True
    Consider bold/font weight when detecting headers.
header_use_all_caps : bool, default True
    Consider all-caps text as potential headers.
header_font_size_ratio : float, default 1.2
    Minimum ratio between header and body text font size.
header_max_line_length : int, default 100
    Maximum character length for text to be considered a header.
header_debug_output : bool, default False
    Enable debug output for header detection analysis. When enabled,
    stores font size distribution and classification decisions for inspection.

# Reading order and layout parameters
detect_columns : bool, default True
    Enable multi-column layout detection.
merge_hyphenated_words : bool, default True
    Merge words split by hyphens at line breaks.
handle_rotated_text : bool, default True
    Process rotated text blocks.
column_gap_threshold : float, default 20
    Minimum gap between columns in points.
column_detection_mode : str, default "auto"
    Column detection strategy: "auto" (heuristic-based), "force_single" (disable detection),
    "force_multi" (force multi-column), or "disabled" (same as force_single).
use_column_clustering : bool, default False
    Use k-means clustering on x-coordinates for more robust column detection.
    Alternative to gap heuristics, better for layouts with irregular column positions.

# Table detection parameters
enable_table_fallback_detection : bool, default True
    Use heuristic fallback if PyMuPDF table detection fails.
detect_merged_cells : bool, default True
    Attempt to identify merged cells in tables.
table_ruling_line_threshold : float, default 0.5
    Threshold for detecting table ruling lines (0.0-1.0, ratio of line length to page size).
table_fallback_extraction_mode : str, default "grid"
    Table extraction mode for ruling line fallback: "none" (detect only, don't extract),
    "grid" (grid-based cell segmentation), or "text_clustering" (future: text position clustering).

link_overlap_threshold : float, default 70.0
    Percentage overlap required for link detection (0-100). Lower values detect links
    with less overlap but may incorrectly link non-link text. Higher values reduce
    false positives but may miss valid links.

image_placement_markers : bool, default True
    Add markers showing image positions.
include_image_captions : bool, default True
    Try to extract image captions.

include_page_numbers : bool, default False
    Include page numbers in output (automatically added to separator).
page_separator_template : str, default "-----"
    Template for page separators between pages.
    Supports placeholders: {page_num}, {total_pages}.

table_detection_mode : str, default "both"
    Table detection strategy: "pymupdf", "ruling", "both", or "none".
image_format : str, default "png"
    Output format for extracted images: "png" or "jpeg".
image_quality : int, default 90
    JPEG quality (1-100, only used when image_format="jpeg").

trim_headers_footers : bool, default False
    Remove repeated headers and footers from pages.
auto_trim_headers_footers : bool, default False
    Automatically detect and remove repeating headers/footers. When enabled,
    analyzes content across pages to identify repeating header/footer patterns
    and automatically sets header_height/footer_height values. Takes precedence
    over manually specified header_height/footer_height.
header_height : int, default 0
    Height in points to trim from top of page (requires trim_headers_footers).
footer_height : int, default 0
    Height in points to trim from bottom of page (requires trim_headers_footers).
skip_image_extraction : bool, default False
    Skip all image extraction for text-only conversion (improves performance for large PDFs).
lazy_image_processing : bool, default False
    Placeholder for future lazy image loading support (currently no effect).

Notes
-----
For large PDFs (hundreds of pages), consider using skip_image_extraction=True if you only need
text content. This significantly reduces memory pressure by avoiding image decoding.
Parallel processing (CLI --parallel flag) can further improve throughput for multi-file batches,
but note that each worker process imports dependencies anew, adding startup overhead.

Examples
--------
Convert only pages 1-3 with base64 images:
    >>> options = PdfOptions(pages=[1, 2, 3], attachment_mode="base64")
    >>> # Or using string range:
    >>> options = PdfOptions(pages="1-3", attachment_mode="base64")

Convert with custom page separators:
    >>> options = PdfOptions(
    ...     page_separator_template="--- Page {page_num} of {total_pages} ---",
    ...     include_page_numbers=True
    ... )

Configure header detection with debug output:
    >>> options = PdfOptions(
    ...     header_sample_pages=[1, 2, 3],
    ...     header_percentile_threshold=80,
    ...     header_use_all_caps=True,
    ...     header_debug_output=True  # Enable debug analysis
    ... )

Use k-means clustering for robust column detection:
    >>> options = PdfOptions(
    ...     use_column_clustering=True,
    ...     column_gap_threshold=25
    ... )

Configure link detection sensitivity:
    >>> options = PdfOptions(
    ...     link_overlap_threshold=80.0  # Stricter link detection
    ... )

Enable table ruling line extraction:
    >>> options = PdfOptions(
    ...     table_detection_mode="ruling",
    ...     table_fallback_extraction_mode="grid"
    ... )

**attachment_mode**

   How to handle attachments/images

   :Type: ``AttachmentMode``
   :CLI flag: ``--pdf-attachment-mode``
   :Default: ``'alt_text'``
   :Choices: ``skip``, ``alt_text``, ``download``, ``base64``
   :Importance: core

**alt_text_mode**

   How to render alt-text content when using alt_text attachment mode

   :Type: ``AltTextMode``
   :CLI flag: ``--pdf-alt-text-mode``
   :Default: ``'default'``
   :Choices: ``default``, ``plain_filename``, ``strict_markdown``, ``footnote``
   :Importance: core

**attachment_output_dir**

   Directory to save attachments when using download mode

   :Type: ``str | None``
   :CLI flag: ``--pdf-attachment-output-dir``
   :Default: ``None``
   :Importance: advanced

**attachment_base_url**

   Base URL for resolving attachment references

   :Type: ``str | None``
   :CLI flag: ``--pdf-attachment-base-url``
   :Default: ``None``
   :Importance: advanced

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--pdf-extract-metadata``
   :Default: ``False``
   :Importance: core

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--pdf-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**attachment_filename_template**

   Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}

   :Type: ``str``
   :CLI flag: ``--pdf-attachment-filename-template``
   :Default: ``'{stem}_{type}{seq}.{ext}'``
   :Importance: advanced

**attachment_overwrite**

   File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'

   :Type: ``Literal['unique', 'overwrite', 'skip']``
   :CLI flag: ``--pdf-attachment-overwrite``
   :Default: ``'unique'``
   :Choices: ``unique``, ``overwrite``, ``skip``
   :Importance: advanced

**attachment_deduplicate_by_hash**

   Avoid saving duplicate attachments by content hash

   :Type: ``bool``
   :CLI flag: ``--pdf-attachment-deduplicate-by-hash``
   :Default: ``False``
   :Importance: advanced

**attachments_footnotes_section**

   Section title for footnote-style attachment references (None to disable)

   :Type: ``str | None``
   :CLI flag: ``--pdf-attachments-footnotes-section``
   :Default: ``'Attachments'``
   :Importance: advanced

**page_separator_template**

   Template for page/slide separators. Supports placeholders: {page_num}, {total_pages}. This string is inserted between pages/slides

   :Type: ``str``
   :CLI flag: ``--pdf-page-separator-template``
   :Default: ``'-----'``
   :Importance: advanced

**pages**

   Pages to convert. Supports ranges: '1-3,5,10-' or list like [1,2,3]. Always 1-based.

   :Type: ``UnionType[list[int], str, NoneType]``
   :CLI flag: ``--pdf-pages``
   :Default: ``None``
   :Importance: core

**password**

   Password for encrypted PDF documents

   :Type: ``UnionType[str, NoneType]``
   :CLI flag: ``--pdf-password``
   :Default: ``None``
   :Importance: security

**header_sample_pages**

   Pages to sample for header detection (single page or comma-separated list)

   :Type: ``UnionType[int, list[int], NoneType]``
   :CLI flag: ``--pdf-header-sample-pages``
   :Default: ``None``
   :Importance: advanced

**header_percentile_threshold**

   Percentile threshold for header detection

   :Type: ``float``
   :CLI flag: ``--pdf-header-percentile-threshold``
   :Default: ``75``
   :Importance: advanced

**header_min_occurrences**

   Minimum occurrences of a font size to consider for headers

   :Type: ``int``
   :CLI flag: ``--pdf-header-min-occurrences``
   :Default: ``5``
   :Importance: advanced

**header_size_allowlist**

   Specific font sizes (in points) to always treat as headers

   :Type: ``UnionType[list[float], NoneType]``
   :CLI flag: ``--pdf-header-size-allowlist``
   :Default: ``None``
   :Importance: advanced

**header_size_denylist**

   Font sizes (in points) to never treat as headers

   :Type: ``UnionType[list[float], NoneType]``
   :CLI flag: ``--pdf-header-size-denylist``
   :Default: ``None``
   :Importance: advanced

**header_use_font_weight**

   Consider bold/font weight when detecting headers

   :Type: ``bool``
   :CLI flag: ``--pdf-no-header-use-font-weight``
   :Default: ``True``
   :Importance: advanced

**header_use_all_caps**

   Consider all-caps text as potential headers

   :Type: ``bool``
   :CLI flag: ``--pdf-no-header-use-all-caps``
   :Default: ``True``
   :Importance: advanced

**header_font_size_ratio**

   Minimum ratio between header and body text font size

   :Type: ``float``
   :CLI flag: ``--pdf-header-font-size-ratio``
   :Default: ``1.2``
   :Importance: advanced

**header_max_line_length**

   Maximum character length for text to be considered a header

   :Type: ``int``
   :CLI flag: ``--pdf-header-max-line-length``
   :Default: ``100``
   :Importance: advanced

**header_debug_output**

   Enable debug output for header detection analysis (stores font size distribution)

   :Type: ``bool``
   :CLI flag: ``--pdf-header-debug-output``
   :Default: ``False``
   :Importance: advanced

**detect_columns**

   Enable multi-column layout detection

   :Type: ``bool``
   :CLI flag: ``--pdf-no-detect-columns``
   :Default: ``True``
   :Importance: core

**merge_hyphenated_words**

   Merge words split by hyphens at line breaks

   :Type: ``bool``
   :CLI flag: ``--pdf-no-merge-hyphenated-words``
   :Default: ``True``
   :Importance: core

**handle_rotated_text**

   Process rotated text blocks

   :Type: ``bool``
   :CLI flag: ``--pdf-no-handle-rotated-text``
   :Default: ``True``
   :Importance: advanced

**column_gap_threshold**

   Minimum gap between columns in points

   :Type: ``float``
   :CLI flag: ``--pdf-column-gap-threshold``
   :Default: ``20``
   :Importance: advanced

**column_detection_mode**

   Column detection strategy: 'auto', 'force_single', 'force_multi', 'disabled'

   :Type: ``Literal['auto', 'force_single', 'force_multi', 'disabled']``
   :CLI flag: ``--pdf-column-detection-mode``
   :Default: ``'auto'``
   :Choices: ``auto``, ``force_single``, ``force_multi``, ``disabled``
   :Importance: advanced

**use_column_clustering**

   Use k-means clustering for more robust column detection (alternative to gap heuristics)

   :Type: ``bool``
   :CLI flag: ``--pdf-use-column-clustering``
   :Default: ``False``
   :Importance: advanced

**enable_table_fallback_detection**

   Use heuristic fallback if PyMuPDF table detection fails

   :Type: ``bool``
   :CLI flag: ``--pdf-no-enable-table-fallback-detection``
   :Default: ``True``
   :Importance: advanced

**detect_merged_cells**

   Attempt to identify merged cells in tables

   :Type: ``bool``
   :CLI flag: ``--pdf-no-detect-merged-cells``
   :Default: ``True``
   :Importance: advanced

**table_ruling_line_threshold**

   Threshold for detecting table ruling lines (0.0-1.0)

   :Type: ``float``
   :CLI flag: ``--pdf-table-ruling-line-threshold``
   :Default: ``0.5``
   :Importance: advanced

**table_fallback_extraction_mode**

   Table extraction mode for ruling line fallback: 'none', 'grid', 'text_clustering'

   :Type: ``Literal['none', 'grid', 'text_clustering']``
   :CLI flag: ``--pdf-table-fallback-extraction-mode``
   :Default: ``'grid'``
   :Choices: ``none``, ``grid``, ``text_clustering``
   :Importance: advanced

**image_placement_markers**

   Add markers showing image positions

   :Type: ``bool``
   :CLI flag: ``--pdf-no-image-placement-markers``
   :Default: ``True``
   :Importance: core

**include_image_captions**

   Try to extract image captions

   :Type: ``bool``
   :CLI flag: ``--pdf-no-include-image-captions``
   :Default: ``True``
   :Importance: core

**include_page_numbers**

   Include page numbers in output (e.g., 'Page 1/10')

   :Type: ``bool``
   :CLI flag: ``--pdf-include-page-numbers``
   :Default: ``False``
   :Importance: core

**table_detection_mode**

   Table detection strategy: 'pymupdf', 'ruling', 'both', or 'none'

   :Type: ``Literal['pymupdf', 'ruling', 'both', 'none']``
   :CLI flag: ``--pdf-table-detection-mode``
   :Default: ``'both'``
   :Choices: ``pymupdf``, ``ruling``, ``both``, ``none``
   :Importance: core

**image_format**

   Output format for extracted images: 'png' or 'jpeg'

   :Type: ``Literal['png', 'jpeg']``
   :CLI flag: ``--pdf-image-format``
   :Default: ``'png'``
   :Choices: ``png``, ``jpeg``
   :Importance: advanced

**image_quality**

   JPEG quality (1-100, only used when image_format='jpeg')

   :Type: ``int``
   :CLI flag: ``--pdf-image-quality``
   :Default: ``90``
   :Importance: advanced

**trim_headers_footers**

   Remove repeated headers and footers from pages

   :Type: ``bool``
   :CLI flag: ``--pdf-trim-headers-footers``
   :Default: ``False``
   :Importance: core

**auto_trim_headers_footers**

   Automatically detect and remove repeating headers/footers (overrides manual header_height/footer_height)

   :Type: ``bool``
   :CLI flag: ``--pdf-auto-trim-headers-footers``
   :Default: ``False``
   :Importance: advanced

**header_height**

   Height in points to trim from top of page (requires trim_headers_footers)

   :Type: ``int``
   :CLI flag: ``--pdf-header-height``
   :Default: ``0``
   :Importance: advanced

**footer_height**

   Height in points to trim from bottom of page (requires trim_headers_footers)

   :Type: ``int``
   :CLI flag: ``--pdf-footer-height``
   :Default: ``0``
   :Importance: advanced

**link_overlap_threshold**

   Percentage overlap required for link detection (0-100). Lower values detect links with less overlap.

   :Type: ``float``
   :CLI flag: ``--pdf-link-overlap-threshold``
   :Default: ``70.0``
   :Importance: advanced

**skip_image_extraction**

   Completely skip image extraction for text-only conversion (improves performance for large PDFs)

   :Type: ``bool``
   :CLI flag: ``--pdf-skip-image-extraction``
   :Default: ``False``
   :Importance: advanced

**lazy_image_processing**

   Placeholder for future lazy image loading support. Note: Full implementation would require paginator interface for streaming large PDFs. Currently has no effect.

   :Type: ``bool``
   :CLI flag: ``--pdf-lazy-image-processing``
   :Default: ``False``
   :Importance: advanced

PDF Renderer Options
^^^^^^^^^^^^^^^^^^^^

Configuration options for rendering AST to PDF format.

This dataclass contains settings specific to PDF generation using ReportLab,
including page layout, fonts, margins, and formatting preferences.

Parameters
----------
page_size : {"letter", "a4", "legal"}, default "letter"
    Page size for the PDF document.
margin_top : float, default 72.0
    Top margin in points (72 points = 1 inch).
margin_bottom : float, default 72.0
    Bottom margin in points.
margin_left : float, default 72.0
    Left margin in points.
margin_right : float, default 72.0
    Right margin in points.
font_name : str, default "Helvetica"
    Default font for body text. Standard PDF fonts: Helvetica, Times-Roman, Courier.
font_size : int, default 11
    Default font size in points for body text.
heading_fonts : dict[int, tuple[str, int]] or None, default None
    Font specifications for headings as {level: (font_name, font_size)}.
    If None, uses scaled versions of default font.
code_font : str, default "Courier"
    Monospace font for code blocks and inline code.
line_spacing : float, default 1.2
    Line spacing multiplier (1.0 = single spacing).
include_page_numbers : bool, default True
    Add page numbers to footer.
include_toc : bool, default False
    Generate table of contents from headings.
network : NetworkFetchOptions, default NetworkFetchOptions()
    Network security settings for fetching remote images. By default,
    remote image fetching is disabled (allow_remote_fetch=False).
    Set network.allow_remote_fetch=True to enable secure remote image fetching
    with the same security guardrails as PPTX renderer.

**fail_on_resource_errors**

   Raise RenderingError on resource failures (images, etc.) instead of logging warnings

   :Type: ``bool``
   :CLI flag: ``--pdf-renderer-fail-on-resource-errors``
   :Default: ``False``
   :Importance: advanced

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--pdf-renderer-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**page_size**

   Page size: letter, a4, or legal

   :Type: ``Literal['letter', 'a4', 'legal']``
   :CLI flag: ``--pdf-renderer-page-size``
   :Default: ``'letter'``
   :Choices: ``letter``, ``a4``, ``legal``
   :Importance: core

**margin_top**

   Top margin in points (72pt = 1 inch)

   :Type: ``float``
   :CLI flag: ``--pdf-renderer-margin-top``
   :Default: ``72.0``
   :Importance: advanced

**margin_bottom**

   Bottom margin in points

   :Type: ``float``
   :CLI flag: ``--pdf-renderer-margin-bottom``
   :Default: ``72.0``
   :Importance: advanced

**margin_left**

   Left margin in points

   :Type: ``float``
   :CLI flag: ``--pdf-renderer-margin-left``
   :Default: ``72.0``
   :Importance: advanced

**margin_right**

   Right margin in points

   :Type: ``float``
   :CLI flag: ``--pdf-renderer-margin-right``
   :Default: ``72.0``
   :Importance: advanced

**font_name**

   Default font (Helvetica, Times-Roman, Courier)

   :Type: ``str``
   :CLI flag: ``--pdf-renderer-font-name``
   :Default: ``'Helvetica'``
   :Importance: core

**font_size**

   Default font size in points

   :Type: ``int``
   :CLI flag: ``--pdf-renderer-font-size``
   :Default: ``12``
   :Importance: core

**heading_fonts**

   Heading font specs as JSON (e.g., '{"1": ["Helvetica-Bold", 24]}')

   :Type: ``UnionType[dict[int, tuple[str, int]], NoneType]``
   :CLI flag: ``--pdf-renderer-heading-fonts``
   :Default: ``None``
   :Importance: advanced

**code_font**

   Monospace font for code

   :Type: ``str``
   :CLI flag: ``--pdf-renderer-code-font``
   :Default: ``'Courier'``
   :Importance: core

**line_spacing**

   Line spacing multiplier (1.0 = single)

   :Type: ``float``
   :CLI flag: ``--pdf-renderer-line-spacing``
   :Default: ``1.2``
   :Importance: advanced

**include_page_numbers**

   Add page numbers to footer

   :Type: ``bool``
   :CLI flag: ``--pdf-renderer-no-page-numbers``
   :Default: ``True``
   :Importance: core

**include_toc**

   Generate table of contents

   :Type: ``bool``
   :CLI flag: ``--pdf-renderer-include-toc``
   :Default: ``False``
   :Importance: core

Network Options
+++++++++++++++

Network security options for remote resource fetching.

This dataclass contains settings that control how remote resources
(images, CSS, etc.) are fetched, including security constraints
to prevent SSRF attacks.

Parameters
----------
allow_remote_fetch : bool, default False
    Whether to allow fetching remote URLs for images and other resources.
    When False, prevents SSRF attacks by blocking all network requests.
allowed_hosts : list[str] | None, default None
    List of allowed hostnames or CIDR blocks for remote fetching.
    If None, all hosts are allowed (subject to other security constraints).
require_https : bool, default False
    Whether to require HTTPS for all remote URL fetching.
network_timeout : float, default 10.0
    Timeout in seconds for remote URL fetching.
max_requests_per_second : float, default 10.0
    Maximum number of network requests per second (rate limiting).
max_concurrent_requests : int, default 5
    Maximum number of concurrent network requests.

Notes
-----
Asset size limits are inherited from BaseParserOptions.max_asset_size_bytes.

**allow_remote_fetch**

   Allow fetching remote URLs for images and other resources. When False, prevents SSRF attacks by blocking all network requests.

   :Type: ``bool``
   :CLI flag: ``--pdf-renderer-network-allow-remote-fetch``
   :Default: ``False``
   :Importance: security

**allowed_hosts**

   List of allowed hostnames or CIDR blocks for remote fetching. If None, all hosts are allowed (subject to other security constraints).

   :Type: ``UnionType[list[str], NoneType]``
   :CLI flag: ``--pdf-renderer-network-allowed-hosts``
   :Default: ``None``
   :Importance: security

**require_https**

   Require HTTPS for all remote URL fetching

   :Type: ``bool``
   :CLI flag: ``--pdf-renderer-network-no-require-https``
   :Default: ``True``
   :Importance: security

**require_head_success**

   Require HEAD request success before remote URL fetching

   :Type: ``bool``
   :CLI flag: ``--pdf-renderer-network-no-require-head-success``
   :Default: ``True``
   :Importance: security

**network_timeout**

   Timeout in seconds for remote URL fetching

   :Type: ``float``
   :CLI flag: ``--pdf-renderer-network-network-timeout``
   :Default: ``10.0``
   :Importance: security

**max_redirects**

   Maximum number of HTTP redirects to follow

   :Type: ``int``
   :CLI flag: ``--pdf-renderer-network-max-redirects``
   :Default: ``5``
   :Importance: security

**allowed_content_types**

   Allowed content-type prefixes for remote resources (e.g., 'image/', 'text/')

   :Type: ``UnionType[tuple[str, ...], NoneType]``
   :CLI flag: ``--pdf-renderer-network-allowed-content-types``
   :Default: ``('image/',)``
   :CLI action: ``append``
   :Importance: security

**max_requests_per_second**

   Maximum number of network requests per second (rate limiting)

   :Type: ``float``
   :CLI flag: ``--pdf-renderer-network-max-requests-per-second``
   :Default: ``10.0``
   :Importance: security

**max_concurrent_requests**

   Maximum number of concurrent network requests

   :Type: ``int``
   :CLI flag: ``--pdf-renderer-network-max-concurrent-requests``
   :Default: ``5``
   :Importance: security

PLAINTEXT Options
~~~~~~~~~~~~~~~~~


PLAINTEXT Parser Options
^^^^^^^^^^^^^^^^^^^^^^^^

Base class for all parser options.

This class serves as the foundation for format-specific parser options.
Parsers convert source documents into AST representation.

Parameters
----------
attachment_mode : AttachmentMode
    How to handle attachments/images during parsing
alt_text_mode : AltTextMode
    How to render alt-text content
extract_metadata : bool
    Whether to extract document metadata

Notes
-----
Subclasses should define format-specific parsing options as frozen dataclass fields.

**attachment_mode**

   How to handle attachments/images

   :Type: ``Literal['skip', 'alt_text', 'download', 'base64']``
   :CLI flag: ``--plaintext-attachment-mode``
   :Default: ``'alt_text'``
   :Choices: ``skip``, ``alt_text``, ``download``, ``base64``
   :Importance: core

**alt_text_mode**

   How to render alt-text content when using alt_text attachment mode

   :Type: ``Literal['default', 'plain_filename', 'strict_markdown', 'footnote']``
   :CLI flag: ``--plaintext-alt-text-mode``
   :Default: ``'default'``
   :Choices: ``default``, ``plain_filename``, ``strict_markdown``, ``footnote``
   :Importance: core

**attachment_output_dir**

   Directory to save attachments when using download mode

   :Type: ``UnionType[str, NoneType]``
   :CLI flag: ``--plaintext-attachment-output-dir``
   :Default: ``None``
   :Importance: advanced

**attachment_base_url**

   Base URL for resolving attachment references

   :Type: ``UnionType[str, NoneType]``
   :CLI flag: ``--plaintext-attachment-base-url``
   :Default: ``None``
   :Importance: advanced

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--plaintext-extract-metadata``
   :Default: ``False``
   :Importance: core

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--plaintext-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**attachment_filename_template**

   Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}

   :Type: ``str``
   :CLI flag: ``--plaintext-attachment-filename-template``
   :Default: ``'{stem}_{type}{seq}.{ext}'``
   :Importance: advanced

**attachment_overwrite**

   File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'

   :Type: ``Literal['unique', 'overwrite', 'skip']``
   :CLI flag: ``--plaintext-attachment-overwrite``
   :Default: ``'unique'``
   :Choices: ``unique``, ``overwrite``, ``skip``
   :Importance: advanced

**attachment_deduplicate_by_hash**

   Avoid saving duplicate attachments by content hash

   :Type: ``bool``
   :CLI flag: ``--plaintext-attachment-deduplicate-by-hash``
   :Default: ``False``
   :Importance: advanced

**attachments_footnotes_section**

   Section title for footnote-style attachment references (None to disable)

   :Type: ``UnionType[str, NoneType]``
   :CLI flag: ``--plaintext-attachments-footnotes-section``
   :Default: ``'Attachments'``
   :Importance: advanced

PLAINTEXT Renderer Options
^^^^^^^^^^^^^^^^^^^^^^^^^^

Configuration options for plain text rendering.

This dataclass contains settings for rendering AST documents as
plain, unformatted text. All formatting (bold, italic, headings, etc.)
is stripped, leaving only the text content.

Parameters
----------
max_line_width : int or None, default 80
    Maximum line width for wrapping text. Set to None to disable wrapping.
    When enabled, long lines will be wrapped at word boundaries.
table_cell_separator : str, default " | "
    Separator string to use between table cells.
include_table_headers : bool, default True
    Whether to include table headers in the output.
    When False, only table body rows are rendered.
paragraph_separator : str, default "\n\n"
    Separator string to use between paragraphs and block elements.
list_item_prefix : str, default "- "
    Prefix to use for list items (both ordered and unordered).
preserve_code_blocks : bool, default True
    Whether to preserve code block content with original formatting.
    When False, code blocks are treated like regular paragraphs.

Examples
--------
Basic plain text rendering:
    >>> from all2md.ast import Document, Paragraph, Text
    >>> from all2md.renderers.plaintext import PlainTextRenderer
    >>> from all2md.options import PlainTextOptions
    >>> doc = Document(children=[
    ...     Paragraph(content=[Text(content="Hello world")])
    ... ])
    >>> options = PlainTextOptions(max_line_width=None)
    >>> renderer = PlainTextRenderer(options)
    >>> text = renderer.render_to_string(doc)

**fail_on_resource_errors**

   Raise RenderingError on resource failures (images, etc.) instead of logging warnings

   :Type: ``bool``
   :CLI flag: ``--plaintext-renderer-fail-on-resource-errors``
   :Default: ``False``
   :Importance: advanced

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--plaintext-renderer-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**max_line_width**

   Maximum line width for wrapping (None = no wrapping)

   :Type: ``UnionType[int, NoneType]``
   :CLI flag: ``--plaintext-renderer-max-line-width``
   :Default: ``80``
   :Importance: core

**table_cell_separator**

   Separator between table cells

   :Type: ``str``
   :CLI flag: ``--plaintext-renderer-table-cell-separator``
   :Default: ``' | '``
   :Importance: advanced

**include_table_headers**

   Include table headers in output

   :Type: ``bool``
   :CLI flag: ``--plaintext-renderer-no-include-table-headers``
   :Default: ``True``
   :Importance: core

**paragraph_separator**

   Separator between paragraphs

   :Type: ``str``
   :CLI flag: ``--plaintext-renderer-paragraph-separator``
   :Default: ``'\n\n'``
   :Importance: advanced

**list_item_prefix**

   Prefix for list items

   :Type: ``str``
   :CLI flag: ``--plaintext-renderer-list-item-prefix``
   :Default: ``'- '``
   :Importance: advanced

**preserve_code_blocks**

   Preserve code block formatting

   :Type: ``bool``
   :CLI flag: ``--plaintext-renderer-no-preserve-code-blocks``
   :Default: ``True``
   :Importance: core

PPTX Options
~~~~~~~~~~~~


PPTX Parser Options
^^^^^^^^^^^^^^^^^^^

Configuration options for PPTX-to-Markdown conversion.

This dataclass contains settings specific to PowerPoint presentation
processing, including slide numbering and image handling.

Parameters
----------
include_slide_numbers : bool, default False
    Whether to include slide numbers in the output.
include_notes : bool, default True
    Whether to include speaker notes in the conversion.

Examples
--------
Convert with slide numbers and base64 images:
    >>> options = PptxOptions(include_slide_numbers=True, attachment_mode="base64")

Convert slides only (no notes):
    >>> options = PptxOptions(include_notes=False)

**attachment_mode**

   How to handle attachments/images

   :Type: ``AttachmentMode``
   :CLI flag: ``--pptx-attachment-mode``
   :Default: ``'alt_text'``
   :Choices: ``skip``, ``alt_text``, ``download``, ``base64``
   :Importance: core

**alt_text_mode**

   How to render alt-text content when using alt_text attachment mode

   :Type: ``AltTextMode``
   :CLI flag: ``--pptx-alt-text-mode``
   :Default: ``'default'``
   :Choices: ``default``, ``plain_filename``, ``strict_markdown``, ``footnote``
   :Importance: core

**attachment_output_dir**

   Directory to save attachments when using download mode

   :Type: ``str | None``
   :CLI flag: ``--pptx-attachment-output-dir``
   :Default: ``None``
   :Importance: advanced

**attachment_base_url**

   Base URL for resolving attachment references

   :Type: ``str | None``
   :CLI flag: ``--pptx-attachment-base-url``
   :Default: ``None``
   :Importance: advanced

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--pptx-extract-metadata``
   :Default: ``False``
   :Importance: core

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--pptx-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**attachment_filename_template**

   Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}

   :Type: ``str``
   :CLI flag: ``--pptx-attachment-filename-template``
   :Default: ``'{stem}_{type}{seq}.{ext}'``
   :Importance: advanced

**attachment_overwrite**

   File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'

   :Type: ``Literal['unique', 'overwrite', 'skip']``
   :CLI flag: ``--pptx-attachment-overwrite``
   :Default: ``'unique'``
   :Choices: ``unique``, ``overwrite``, ``skip``
   :Importance: advanced

**attachment_deduplicate_by_hash**

   Avoid saving duplicate attachments by content hash

   :Type: ``bool``
   :CLI flag: ``--pptx-attachment-deduplicate-by-hash``
   :Default: ``False``
   :Importance: advanced

**attachments_footnotes_section**

   Section title for footnote-style attachment references (None to disable)

   :Type: ``str | None``
   :CLI flag: ``--pptx-attachments-footnotes-section``
   :Default: ``'Attachments'``
   :Importance: advanced

**page_separator_template**

   Template for page/slide separators. Supports placeholders: {page_num}, {total_pages}. This string is inserted between pages/slides

   :Type: ``str``
   :CLI flag: ``--pptx-page-separator-template``
   :Default: ``'-----'``
   :Importance: advanced

**include_slide_numbers**

   Include slide numbers in output

   :Type: ``bool``
   :CLI flag: ``--pptx-include-slide-numbers``
   :Default: ``False``
   :Importance: core

**include_notes**

   Include speaker notes from slides

   :Type: ``bool``
   :CLI flag: ``--pptx-no-include-notes``
   :Default: ``True``
   :Importance: core

**slides**

   Slide selection (e.g., '1,3-5,8' for slides 1, 3-5, and 8)

   :Type: ``str | None``
   :CLI flag: ``--pptx-slides``
   :Default: ``None``
   :Importance: core

**charts_mode**

   Chart conversion mode: 'data' (default, tables only), 'mermaid' (diagrams only), or 'both' (tables + diagrams)

   :Type: ``Literal['data', 'mermaid', 'both']``
   :CLI flag: ``--pptx-charts-mode``
   :Default: ``'data'``
   :Choices: ``data``, ``mermaid``, ``both``
   :Importance: advanced

**include_titles_as_h2**

   Include slide titles as H2 headings

   :Type: ``bool``
   :CLI flag: ``--pptx-no-include-titles-as-h2``
   :Default: ``True``
   :Importance: core

**strict_list_detection**

   Use strict list detection (XML-only, no heuristics). When True, only paragraphs with explicit list formatting in XML are treated as lists. When False (default), uses XML detection with heuristic fallbacks for unformatted lists.

   :Type: ``bool``
   :CLI flag: ``--pptx-strict-list-detection``
   :Default: ``False``
   :Importance: advanced

PPTX Renderer Options
^^^^^^^^^^^^^^^^^^^^^

Configuration options for rendering AST to PPTX format.

This dataclass contains settings specific to PowerPoint presentation
generation from AST, including slide splitting strategies and layout.

Parameters
----------
slide_split_mode : {"separator", "heading", "auto"}, default "auto"
    How to split the AST into slides:
    - "separator": Split on ThematicBreak nodes (mirrors parser behavior)
    - "heading": Split on specific heading level
    - "auto": Try separator first, fallback to heading-based splitting
slide_split_heading_level : int, default 2
    Heading level to use for slide splits when using heading mode.
    Level 2 (H2) is typical (H1 might be document title).
default_layout : str, default "Title and Content"
    Default slide layout name from template.
title_slide_layout : str, default "Title Slide"
    Layout name for the first slide.
use_heading_as_slide_title : bool, default True
    Use first heading in slide content as slide title.
template_path : str or None, default None
    Path to .pptx template file. If None, uses default blank template.
default_font : str, default "Calibri"
    Default font for slide content.
default_font_size : int, default 18
    Default font size in points for body text.
title_font_size : int, default 44
    Font size for slide titles.
list_number_spacing : int, default 1
    Number of spaces after the number prefix in ordered lists (e.g., "1. " has 1 space).
    Affects visual consistency of manually numbered lists.
list_indent_per_level : float, default 0.5
    Indentation per nesting level for lists, in inches.
    Controls horizontal spacing for nested lists. Note that actual indentation
    behavior may vary across PowerPoint templates.
network : NetworkFetchOptions, default NetworkFetchOptions()
    Network security options for fetching remote images in slides.

Notes
-----
**List Rendering Limitations:**

python-pptx has limited support for automatic list numbering. This renderer
uses manual numbering for ordered lists by adding number prefixes (e.g., "1. ")
as text runs. The following options provide some control over list formatting:

- ``list_number_spacing``: Controls spacing after numbers
- ``list_indent_per_level``: Controls nesting indentation

However, deeper nesting and exact spacing behavior can be inconsistent across
different PowerPoint templates. These limitations are inherent to python-pptx's
API and the complexity of PowerPoint's list formatting system.

**Unordered Lists in Text Boxes:**

For unordered lists, bullets are explicitly enabled via OOXML manipulation
to ensure they appear in both text boxes and content placeholders. Text boxes
do not enable bullets by default, unlike content placeholders.

**fail_on_resource_errors**

   Raise RenderingError on resource failures (images, etc.) instead of logging warnings

   :Type: ``bool``
   :CLI flag: ``--pptx-renderer-fail-on-resource-errors``
   :Default: ``False``
   :Importance: advanced

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--pptx-renderer-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**slide_split_mode**

   Slide splitting strategy: separator, heading, or auto

   :Type: ``Literal['separator', 'heading', 'auto']``
   :CLI flag: ``--pptx-renderer-slide-split-mode``
   :Default: ``'auto'``
   :Choices: ``separator``, ``heading``, ``auto``
   :Importance: core

**slide_split_heading_level**

   Heading level for slide splits (H2 = level 2)

   :Type: ``int``
   :CLI flag: ``--pptx-renderer-slide-split-heading-level``
   :Default: ``2``
   :Importance: advanced

**default_layout**

   Default slide layout name

   :Type: ``str``
   :CLI flag: ``--pptx-renderer-default-layout``
   :Default: ``'Title and Content'``
   :Importance: advanced

**title_slide_layout**

   Layout for first slide

   :Type: ``str``
   :CLI flag: ``--pptx-renderer-title-slide-layout``
   :Default: ``'Title Slide'``
   :Importance: advanced

**use_heading_as_slide_title**

   Use first heading as slide title

   :Type: ``bool``
   :CLI flag: ``--pptx-renderer-no-use-heading-as-slide-title``
   :Default: ``True``
   :Importance: core

**template_path**

   Path to .pptx template file (None = default)

   :Type: ``UnionType[str, NoneType]``
   :CLI flag: ``--pptx-renderer-template-path``
   :Default: ``None``
   :Importance: core

**default_font**

   Default font for slide content

   :Type: ``str``
   :CLI flag: ``--pptx-renderer-default-font``
   :Default: ``'Calibri'``
   :Importance: core

**default_font_size**

   Default font size for body text

   :Type: ``int``
   :CLI flag: ``--pptx-renderer-default-font-size``
   :Default: ``18``
   :Importance: core

**title_font_size**

   Font size for slide titles

   :Type: ``int``
   :CLI flag: ``--pptx-renderer-title-font-size``
   :Default: ``44``
   :Importance: advanced

**list_number_spacing**

   Number of spaces after number prefix in ordered lists

   :Type: ``int``
   :CLI flag: ``--pptx-renderer-list-number-spacing``
   :Default: ``1``
   :Importance: advanced

**list_indent_per_level**

   Indentation per nesting level for lists (in inches)

   :Type: ``float``
   :CLI flag: ``--pptx-renderer-list-indent-per-level``
   :Default: ``0.5``
   :Importance: advanced

**network**

   Network security options for fetching remote images

   :Type: ``NetworkFetchOptions``
   :CLI flag: ``--pptx-renderer-network``
   :Default factory: ``NetworkFetchOptions``

RST Options
~~~~~~~~~~~


RST Parser Options
^^^^^^^^^^^^^^^^^^

Configuration options for reStructuredText-to-AST parsing.

This dataclass contains settings specific to parsing reStructuredText documents
into AST representation using docutils.

Parameters
----------
parse_directives : bool, default True
    Whether to parse RST directives (code-block, image, note, etc.).
    When True, directives are converted to appropriate AST nodes.
    When False, directives are preserved as code blocks.
strict_mode : bool, default False
    Whether to raise errors on invalid RST syntax.
    When False, attempts to recover gracefully.
preserve_raw_directives : bool, default False
    Whether to preserve unknown directives as code blocks.
    When True, unknown directives become CodeBlock nodes.
    When False, they are processed through docutils default handling.

**attachment_mode**

   How to handle attachments/images

   :Type: ``AttachmentMode``
   :CLI flag: ``--rst-attachment-mode``
   :Default: ``'alt_text'``
   :Choices: ``skip``, ``alt_text``, ``download``, ``base64``
   :Importance: core

**alt_text_mode**

   How to render alt-text content when using alt_text attachment mode

   :Type: ``AltTextMode``
   :CLI flag: ``--rst-alt-text-mode``
   :Default: ``'default'``
   :Choices: ``default``, ``plain_filename``, ``strict_markdown``, ``footnote``
   :Importance: core

**attachment_output_dir**

   Directory to save attachments when using download mode

   :Type: ``str | None``
   :CLI flag: ``--rst-attachment-output-dir``
   :Default: ``None``
   :Importance: advanced

**attachment_base_url**

   Base URL for resolving attachment references

   :Type: ``str | None``
   :CLI flag: ``--rst-attachment-base-url``
   :Default: ``None``
   :Importance: advanced

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--rst-extract-metadata``
   :Default: ``False``
   :Importance: core

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--rst-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**attachment_filename_template**

   Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}

   :Type: ``str``
   :CLI flag: ``--rst-attachment-filename-template``
   :Default: ``'{stem}_{type}{seq}.{ext}'``
   :Importance: advanced

**attachment_overwrite**

   File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'

   :Type: ``Literal['unique', 'overwrite', 'skip']``
   :CLI flag: ``--rst-attachment-overwrite``
   :Default: ``'unique'``
   :Choices: ``unique``, ``overwrite``, ``skip``
   :Importance: advanced

**attachment_deduplicate_by_hash**

   Avoid saving duplicate attachments by content hash

   :Type: ``bool``
   :CLI flag: ``--rst-attachment-deduplicate-by-hash``
   :Default: ``False``
   :Importance: advanced

**attachments_footnotes_section**

   Section title for footnote-style attachment references (None to disable)

   :Type: ``str | None``
   :CLI flag: ``--rst-attachments-footnotes-section``
   :Default: ``'Attachments'``
   :Importance: advanced

**parse_directives**

   Parse RST directives (code-block, image, etc.)

   :Type: ``bool``
   :CLI flag: ``--rst-no-parse-directives``
   :Default: ``True``
   :Importance: core

**strict_mode**

   Raise errors on invalid RST syntax (vs. graceful recovery)

   :Type: ``bool``
   :CLI flag: ``--rst-strict-mode``
   :Default: ``False``
   :Importance: advanced

**preserve_raw_directives**

   Preserve unknown directives as code blocks

   :Type: ``bool``
   :CLI flag: ``--rst-preserve-raw-directives``
   :Default: ``False``
   :Importance: advanced

RST Renderer Options
^^^^^^^^^^^^^^^^^^^^

Configuration options for AST-to-reStructuredText rendering.

This dataclass contains settings for rendering AST documents as
reStructuredText output.

Parameters
----------
heading_chars : str, default "=-~^*"
    Characters to use for heading underlines from h1 to h5.
    First character is for level 1, second for level 2, etc.
table_style : {"grid", "simple"}, default "grid"
    Table rendering style:
    - "grid": Grid tables with +---+ borders
    - "simple": Simple tables with === separators
code_directive_style : {"double_colon", "directive"}, default "directive"
    Code block rendering style:
    - "double_colon": Use ``:: literal blocks``
    - "directive": Use ``.. code-block:: directive``
line_length : int, default 80
    Target line length for wrapping text.
hard_line_break_mode : {"line_block", "raw"}, default "line_block"
    How to render hard line breaks:
    - "line_block": Use RST line block syntax (``\n| ``), the standard approach
    - "raw": Use plain newline (``\n``), less faithful but simpler in complex containers

Notes
-----
**Text Escaping:**
    Special RST characters (asterisks, underscores, backticks, brackets, pipes, colons,
    angle brackets) are automatically escaped in text nodes to prevent unintended formatting.

**Line Breaks:**
    Hard line breaks behavior depends on the ``hard_line_break_mode`` option:

    - **line_block mode (default)**: Uses RST line block syntax (``| ``). This is the
      standard RST approach for preserving line structure. May be surprising inside
      complex containers like lists and block quotes as it changes semantic structure.
    - **raw mode**: Uses plain newlines. Less faithful to RST semantics but simpler
      in complex containers. May not preserve visual line breaks in all RST processors.

    Soft line breaks always render as spaces, consistent with RST paragraph semantics.

    **Recommendation**: Use "raw" mode if line blocks cause formatting issues in
    lists or nested structures. Use "line_block" (default) for maximum RST fidelity.

**Unsupported Features:**
    - **Strikethrough**: RST has no native strikethrough syntax. Content renders as plain text.
    - **Underline**: RST has no native underline syntax. Content renders as plain text.
    - **Superscript/Subscript**: Rendered using RST role syntax (``:sup:`` and ``:sub:``).

**Table Limitations:**
    Both grid and simple table styles do not support multi-line content within cells.
    Cell content must be single-line text. Complex cell content (multiple paragraphs,
    nested lists) will be rendered inline, which may cause formatting issues.

**fail_on_resource_errors**

   Raise RenderingError on resource failures (images, etc.) instead of logging warnings

   :Type: ``bool``
   :CLI flag: ``--rst-renderer-fail-on-resource-errors``
   :Default: ``False``
   :Importance: advanced

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--rst-renderer-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**heading_chars**

   Characters for heading underlines (h1-h5)

   :Type: ``str``
   :CLI flag: ``--rst-renderer-heading-chars``
   :Default: ``'=-~^*'``
   :Importance: advanced

**table_style**

   Table rendering style

   :Type: ``Literal['grid', 'simple']``
   :CLI flag: ``--rst-renderer-table-style``
   :Default: ``'grid'``
   :Choices: ``grid``, ``simple``
   :Importance: core

**code_directive_style**

   Code block rendering style

   :Type: ``Literal['double_colon', 'directive']``
   :CLI flag: ``--rst-renderer-code-directive-style``
   :Default: ``'directive'``
   :Choices: ``double_colon``, ``directive``
   :Importance: core

**line_length**

   Target line length for wrapping

   :Type: ``int``
   :CLI flag: ``--rst-renderer-line-length``
   :Default: ``80``
   :Importance: advanced

**hard_line_break_mode**

   Hard line break rendering mode: line_block (use | syntax) or raw (plain newline)

   :Type: ``Literal['line_block', 'raw']``
   :CLI flag: ``--rst-renderer-hard-line-break-mode``
   :Default: ``'line_block'``
   :Choices: ``line_block``, ``raw``
   :Importance: advanced

RTF Options
~~~~~~~~~~~


RTF Parser Options
^^^^^^^^^^^^^^^^^^

Configuration options for RTF-to-Markdown conversion.

This dataclass contains settings specific to Rich Text Format processing,
primarily for handling embedded images and other attachments.

Parameters
----------
Inherited from `BaseParserOptions`

**attachment_mode**

   How to handle attachments/images

   :Type: ``AttachmentMode``
   :CLI flag: ``--rtf-attachment-mode``
   :Default: ``'alt_text'``
   :Choices: ``skip``, ``alt_text``, ``download``, ``base64``
   :Importance: core

**alt_text_mode**

   How to render alt-text content when using alt_text attachment mode

   :Type: ``AltTextMode``
   :CLI flag: ``--rtf-alt-text-mode``
   :Default: ``'default'``
   :Choices: ``default``, ``plain_filename``, ``strict_markdown``, ``footnote``
   :Importance: core

**attachment_output_dir**

   Directory to save attachments when using download mode

   :Type: ``str | None``
   :CLI flag: ``--rtf-attachment-output-dir``
   :Default: ``None``
   :Importance: advanced

**attachment_base_url**

   Base URL for resolving attachment references

   :Type: ``str | None``
   :CLI flag: ``--rtf-attachment-base-url``
   :Default: ``None``
   :Importance: advanced

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--rtf-extract-metadata``
   :Default: ``False``
   :Importance: core

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--rtf-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**attachment_filename_template**

   Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}

   :Type: ``str``
   :CLI flag: ``--rtf-attachment-filename-template``
   :Default: ``'{stem}_{type}{seq}.{ext}'``
   :Importance: advanced

**attachment_overwrite**

   File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'

   :Type: ``Literal['unique', 'overwrite', 'skip']``
   :CLI flag: ``--rtf-attachment-overwrite``
   :Default: ``'unique'``
   :Choices: ``unique``, ``overwrite``, ``skip``
   :Importance: advanced

**attachment_deduplicate_by_hash**

   Avoid saving duplicate attachments by content hash

   :Type: ``bool``
   :CLI flag: ``--rtf-attachment-deduplicate-by-hash``
   :Default: ``False``
   :Importance: advanced

**attachments_footnotes_section**

   Section title for footnote-style attachment references (None to disable)

   :Type: ``str | None``
   :CLI flag: ``--rtf-attachments-footnotes-section``
   :Default: ``'Attachments'``
   :Importance: advanced

SOURCECODE Options
~~~~~~~~~~~~~~~~~~


SOURCECODE Parser Options
^^^^^^^^^^^^^^^^^^^^^^^^^

Configuration options for source code to Markdown conversion.

This dataclass contains settings specific to source code file processing,
including language detection, formatting options, and output customization.

Parameters
----------
detect_language : bool, default True
    Whether to automatically detect programming language from file extension.
    When enabled, uses file extension to determine appropriate syntax highlighting
    language identifier for the Markdown code block.
language_override : str or None, default None
    Manual override for the language identifier. When provided, this language
    will be used instead of automatic detection. Useful for files with
    non-standard extensions or when forcing a specific syntax highlighting.
include_filename : bool, default False
    Whether to include the original filename as a comment at the top of the
    code block. The comment style is automatically chosen based on the
    detected or specified language.

**attachment_mode**

   How to handle attachments/images

   :Type: ``AttachmentMode``
   :CLI flag: ``--sourcecode-attachment-mode``
   :Default: ``'alt_text'``
   :Choices: ``skip``, ``alt_text``, ``download``, ``base64``
   :Importance: core

**alt_text_mode**

   How to render alt-text content when using alt_text attachment mode

   :Type: ``AltTextMode``
   :CLI flag: ``--sourcecode-alt-text-mode``
   :Default: ``'default'``
   :Choices: ``default``, ``plain_filename``, ``strict_markdown``, ``footnote``
   :Importance: core

**attachment_output_dir**

   Directory to save attachments when using download mode

   :Type: ``str | None``
   :CLI flag: ``--sourcecode-attachment-output-dir``
   :Default: ``None``
   :Importance: advanced

**attachment_base_url**

   Base URL for resolving attachment references

   :Type: ``str | None``
   :CLI flag: ``--sourcecode-attachment-base-url``
   :Default: ``None``
   :Importance: advanced

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--sourcecode-extract-metadata``
   :Default: ``False``
   :Importance: core

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--sourcecode-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**attachment_filename_template**

   Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}

   :Type: ``str``
   :CLI flag: ``--sourcecode-attachment-filename-template``
   :Default: ``'{stem}_{type}{seq}.{ext}'``
   :Importance: advanced

**attachment_overwrite**

   File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'

   :Type: ``Literal['unique', 'overwrite', 'skip']``
   :CLI flag: ``--sourcecode-attachment-overwrite``
   :Default: ``'unique'``
   :Choices: ``unique``, ``overwrite``, ``skip``
   :Importance: advanced

**attachment_deduplicate_by_hash**

   Avoid saving duplicate attachments by content hash

   :Type: ``bool``
   :CLI flag: ``--sourcecode-attachment-deduplicate-by-hash``
   :Default: ``False``
   :Importance: advanced

**attachments_footnotes_section**

   Section title for footnote-style attachment references (None to disable)

   :Type: ``str | None``
   :CLI flag: ``--sourcecode-attachments-footnotes-section``
   :Default: ``'Attachments'``
   :Importance: advanced

**detect_language**

   Automatically detect programming language from file extension

   :Type: ``bool``
   :CLI flag: ``--sourcecode-no-detect-language``
   :Default: ``True``
   :Importance: core

**language_override**

   Override language identifier for syntax highlighting

   :Type: ``Optional[str]``
   :CLI flag: ``--sourcecode-language``
   :Default: ``None``
   :Importance: core

**include_filename**

   Include filename as comment in code block

   :Type: ``bool``
   :CLI flag: ``--sourcecode-include-filename``
   :Default: ``False``
   :Importance: advanced

XLSX Options
~~~~~~~~~~~~


XLSX Parser Options
^^^^^^^^^^^^^^^^^^^

Configuration options for XLSX spreadsheet conversion.

This dataclass inherits all spreadsheet options from SpreadsheetParserOptions.
Currently, XLSX has no format-specific options beyond the base spreadsheet options.

See SpreadsheetParserOptions for complete documentation of available options.

**attachment_mode**

   How to handle attachments/images

   :Type: ``AttachmentMode``
   :CLI flag: ``--xlsx-attachment-mode``
   :Default: ``'alt_text'``
   :Choices: ``skip``, ``alt_text``, ``download``, ``base64``
   :Importance: core

**alt_text_mode**

   How to render alt-text content when using alt_text attachment mode

   :Type: ``AltTextMode``
   :CLI flag: ``--xlsx-alt-text-mode``
   :Default: ``'default'``
   :Choices: ``default``, ``plain_filename``, ``strict_markdown``, ``footnote``
   :Importance: core

**attachment_output_dir**

   Directory to save attachments when using download mode

   :Type: ``str | None``
   :CLI flag: ``--xlsx-attachment-output-dir``
   :Default: ``None``
   :Importance: advanced

**attachment_base_url**

   Base URL for resolving attachment references

   :Type: ``str | None``
   :CLI flag: ``--xlsx-attachment-base-url``
   :Default: ``None``
   :Importance: advanced

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--xlsx-extract-metadata``
   :Default: ``False``
   :Importance: core

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--xlsx-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**attachment_filename_template**

   Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}

   :Type: ``str``
   :CLI flag: ``--xlsx-attachment-filename-template``
   :Default: ``'{stem}_{type}{seq}.{ext}'``
   :Importance: advanced

**attachment_overwrite**

   File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'

   :Type: ``Literal['unique', 'overwrite', 'skip']``
   :CLI flag: ``--xlsx-attachment-overwrite``
   :Default: ``'unique'``
   :Choices: ``unique``, ``overwrite``, ``skip``
   :Importance: advanced

**attachment_deduplicate_by_hash**

   Avoid saving duplicate attachments by content hash

   :Type: ``bool``
   :CLI flag: ``--xlsx-attachment-deduplicate-by-hash``
   :Default: ``False``
   :Importance: advanced

**attachments_footnotes_section**

   Section title for footnote-style attachment references (None to disable)

   :Type: ``str | None``
   :CLI flag: ``--xlsx-attachments-footnotes-section``
   :Default: ``'Attachments'``
   :Importance: advanced

**sheets**

   Sheet names to include (list or regex pattern). default = all sheets

   :Type: ``Union[list[str], str, None]``
   :CLI flag: ``--xlsx-sheets``
   :Default: ``None``
   :Importance: core

**include_sheet_titles**

   Prepend each sheet with '## {sheet_name}' heading

   :Type: ``bool``
   :CLI flag: ``--xlsx-no-include-sheet-titles``
   :Default: ``True``
   :Importance: core

**render_formulas**

   Use stored cell values (True) or show formulas (False)

   :Type: ``bool``
   :CLI flag: ``--xlsx-no-render-formulas``
   :Default: ``True``
   :Importance: core

**max_rows**

   Maximum rows per table (None = unlimited)

   :Type: ``Optional[int]``
   :CLI flag: ``--xlsx-max-rows``
   :Default: ``None``
   :Importance: advanced

**max_cols**

   Maximum columns per table (None = unlimited)

   :Type: ``Optional[int]``
   :CLI flag: ``--xlsx-max-cols``
   :Default: ``None``
   :Importance: advanced

**truncation_indicator**

   Note appended when rows/columns are truncated

   :Type: ``str``
   :CLI flag: ``--xlsx-truncation-indicator``
   :Default: ``'...'``
   :Importance: advanced

**preserve_newlines_in_cells**

   Preserve line breaks within cells as <br> tags

   :Type: ``bool``
   :CLI flag: ``--xlsx-preserve-newlines-in-cells``
   :Default: ``False``

**trim_empty**

   Trim empty rows/columns: none, leading, trailing, or both

   :Type: ``Literal['none', 'leading', 'trailing', 'both']``
   :CLI flag: ``--xlsx-trim-empty``
   :Default: ``'trailing'``
   :Choices: ``none``, ``leading``, ``trailing``, ``both``
   :Importance: core

**header_case**

   Transform header case: preserve, title, upper, or lower

   :Type: ``HeaderCaseOption``
   :CLI flag: ``--xlsx-header-case``
   :Default: ``'preserve'``
   :Choices: ``preserve``, ``title``, ``upper``, ``lower``
   :Importance: core

**chart_mode**

   Chart handling mode: 'data' (extract as tables) or 'skip' (ignore charts, default)

   :Type: ``Literal['data', 'skip']``
   :CLI flag: ``--xlsx-chart-mode``
   :Default: ``'skip'``
   :Choices: ``data``, ``skip``
   :Importance: advanced

**merged_cell_mode**

   Merged cell handling: 'spans' (use colspan/rowspan), 'flatten' (empty strings), or 'skip'

   :Type: ``Literal['spans', 'flatten', 'skip']``
   :CLI flag: ``--xlsx-merged-cell-mode``
   :Default: ``'flatten'``
   :Choices: ``spans``, ``flatten``, ``skip``
   :Importance: advanced

ZIP Options
~~~~~~~~~~~


ZIP Parser Options
^^^^^^^^^^^^^^^^^^

Configuration options for ZIP archive to Markdown conversion.

This dataclass contains settings specific to ZIP/archive processing,
including file filtering, directory structure handling, and attachment extraction.

Parameters
----------
include_patterns : list[str] or None, default None
    Glob patterns for files to include (e.g., ['*.pdf', '*.docx']).
    If None, all parseable files are included.
exclude_patterns : list[str] or None, default None
    Glob patterns for files to exclude (e.g., ['__MACOSX/*', '.DS_Store']).
max_depth : int or None, default None
    Maximum directory depth to traverse. None means unlimited.
create_section_headings : bool, default True
    Whether to create section headings for each extracted file.
preserve_directory_structure : bool, default True
    Whether to include directory path in section headings.
flatten_structure : bool, default False
    Whether to flatten directory structure (ignore paths in output).
extract_resource_files : bool, default True
    Whether to extract non-parseable files (images, CSS, etc.) to attachment directory.
skip_empty_files : bool, default True
    Whether to skip files with no content or that fail to parse.
include_resource_manifest : bool, default True
    Whether to include a manifest table of extracted resources at the end of the document.

**attachment_mode**

   How to handle attachments/images

   :Type: ``AttachmentMode``
   :CLI flag: ``--zip-attachment-mode``
   :Default: ``'alt_text'``
   :Choices: ``skip``, ``alt_text``, ``download``, ``base64``
   :Importance: core

**alt_text_mode**

   How to render alt-text content when using alt_text attachment mode

   :Type: ``AltTextMode``
   :CLI flag: ``--zip-alt-text-mode``
   :Default: ``'default'``
   :Choices: ``default``, ``plain_filename``, ``strict_markdown``, ``footnote``
   :Importance: core

**attachment_output_dir**

   Directory to save attachments when using download mode

   :Type: ``str | None``
   :CLI flag: ``--zip-attachment-output-dir``
   :Default: ``None``
   :Importance: advanced

**attachment_base_url**

   Base URL for resolving attachment references

   :Type: ``str | None``
   :CLI flag: ``--zip-attachment-base-url``
   :Default: ``None``
   :Importance: advanced

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--zip-extract-metadata``
   :Default: ``False``
   :Importance: core

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--zip-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**attachment_filename_template**

   Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}

   :Type: ``str``
   :CLI flag: ``--zip-attachment-filename-template``
   :Default: ``'{stem}_{type}{seq}.{ext}'``
   :Importance: advanced

**attachment_overwrite**

   File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'

   :Type: ``Literal['unique', 'overwrite', 'skip']``
   :CLI flag: ``--zip-attachment-overwrite``
   :Default: ``'unique'``
   :Choices: ``unique``, ``overwrite``, ``skip``
   :Importance: advanced

**attachment_deduplicate_by_hash**

   Avoid saving duplicate attachments by content hash

   :Type: ``bool``
   :CLI flag: ``--zip-attachment-deduplicate-by-hash``
   :Default: ``False``
   :Importance: advanced

**attachments_footnotes_section**

   Section title for footnote-style attachment references (None to disable)

   :Type: ``str | None``
   :CLI flag: ``--zip-attachments-footnotes-section``
   :Default: ``'Attachments'``
   :Importance: advanced

**include_patterns**

   Glob patterns for files to include

   :Type: ``Optional[list[str]]``
   :CLI flag: ``--zip-include``
   :Default: ``None``
   :Importance: core

**exclude_patterns**

   Glob patterns for files to exclude

   :Type: ``Optional[list[str]]``
   :CLI flag: ``--zip-exclude``
   :Default: ``None``
   :Importance: core

**max_depth**

   Maximum directory depth to traverse

   :Type: ``Optional[int]``
   :CLI flag: ``--zip-max-depth``
   :Default: ``None``
   :Importance: advanced

**create_section_headings**

   Create section headings for each file

   :Type: ``bool``
   :CLI flag: ``--zip-no-section-headings``
   :Default: ``True``
   :Importance: core

**preserve_directory_structure**

   Include directory path in section headings

   :Type: ``bool``
   :CLI flag: ``--zip-no-preserve-directory``
   :Default: ``True``
   :Importance: core

**flatten_structure**

   Flatten directory structure in output

   :Type: ``bool``
   :CLI flag: ``--zip-flatten``
   :Default: ``False``
   :Importance: advanced

**extract_resource_files**

   Extract non-parseable files to attachment directory

   :Type: ``bool``
   :CLI flag: ``--zip-no-extract-resources``
   :Default: ``True``
   :Importance: core

**skip_empty_files**

   Skip files with no content or parse failures

   :Type: ``bool``
   :CLI flag: ``--zip-no-skip-empty``
   :Default: ``True``
   :Importance: advanced

**include_resource_manifest**

   Include manifest table of extracted resources

   :Type: ``bool``
   :CLI flag: ``--zip-no-resource-manifest``
   :Default: ``True``
   :Importance: advanced

Shared Options
~~~~~~~~~~~~~~


Base Parser Options
^^^^^^^^^^^^^^^^^^^

Base class for all parser options.

This class serves as the foundation for format-specific parser options.
Parsers convert source documents into AST representation.

Parameters
----------
attachment_mode : AttachmentMode
    How to handle attachments/images during parsing
alt_text_mode : AltTextMode
    How to render alt-text content
extract_metadata : bool
    Whether to extract document metadata

Notes
-----
Subclasses should define format-specific parsing options as frozen dataclass fields.

**attachment_mode**

   How to handle attachments/images

   :Type: ``Literal['skip', 'alt_text', 'download', 'base64']``
   :CLI flag: ``--attachment-mode``
   :Default: ``'alt_text'``
   :Choices: ``skip``, ``alt_text``, ``download``, ``base64``
   :Importance: core

**alt_text_mode**

   How to render alt-text content when using alt_text attachment mode

   :Type: ``Literal['default', 'plain_filename', 'strict_markdown', 'footnote']``
   :CLI flag: ``--alt-text-mode``
   :Default: ``'default'``
   :Choices: ``default``, ``plain_filename``, ``strict_markdown``, ``footnote``
   :Importance: core

**attachment_output_dir**

   Directory to save attachments when using download mode

   :Type: ``UnionType[str, NoneType]``
   :CLI flag: ``--attachment-output-dir``
   :Default: ``None``
   :Importance: advanced

**attachment_base_url**

   Base URL for resolving attachment references

   :Type: ``UnionType[str, NoneType]``
   :CLI flag: ``--attachment-base-url``
   :Default: ``None``
   :Importance: advanced

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--extract-metadata``
   :Default: ``False``
   :Importance: core

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**attachment_filename_template**

   Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}

   :Type: ``str``
   :CLI flag: ``--attachment-filename-template``
   :Default: ``'{stem}_{type}{seq}.{ext}'``
   :Importance: advanced

**attachment_overwrite**

   File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'

   :Type: ``Literal['unique', 'overwrite', 'skip']``
   :CLI flag: ``--attachment-overwrite``
   :Default: ``'unique'``
   :Choices: ``unique``, ``overwrite``, ``skip``
   :Importance: advanced

**attachment_deduplicate_by_hash**

   Avoid saving duplicate attachments by content hash

   :Type: ``bool``
   :CLI flag: ``--attachment-deduplicate-by-hash``
   :Default: ``False``
   :Importance: advanced

**attachments_footnotes_section**

   Section title for footnote-style attachment references (None to disable)

   :Type: ``UnionType[str, NoneType]``
   :CLI flag: ``--attachments-footnotes-section``
   :Default: ``'Attachments'``
   :Importance: advanced

Base Renderer Options
^^^^^^^^^^^^^^^^^^^^^

Base class for all renderer options.

This class serves as the foundation for format-specific renderer options.
Renderers convert AST documents into various output formats (Markdown, DOCX, PDF, etc.).

Parameters
----------
fail_on_resource_errors : bool, default=False
    Whether to raise RenderingError when resource loading fails (e.g., images).
    If False (default), warnings are logged but rendering continues.
    If True, rendering stops immediately on resource errors.
max_asset_size_bytes : int
    Maximum allowed size in bytes for any single asset (images, downloads, etc.)

Notes
-----
Subclasses should define format-specific rendering options as frozen dataclass fields.

**fail_on_resource_errors**

   Raise RenderingError on resource failures (images, etc.) instead of logging warnings

   :Type: ``bool``
   :CLI flag: ``--renderer-fail-on-resource-errors``
   :Default: ``False``
   :Importance: advanced

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--renderer-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

Markdown Options
^^^^^^^^^^^^^^^^

Markdown rendering options for converting AST to Markdown text.

When a flavor is specified, default values for unsupported_table_mode and
unsupported_inline_mode are automatically set to flavor-appropriate values
unless explicitly overridden. This is handled via the __new__ method to
apply flavor-aware defaults before instance creation.

This dataclass contains settings that control how Markdown output is
formatted and structured. These options are used by multiple conversion
modules to ensure consistent Markdown generation.

Parameters
----------
escape_special : bool, default True
    Whether to escape special Markdown characters in text content.
    When True, characters like \*, \_, #, [, ], (, ), \\ are escaped
    to prevent unintended formatting.
emphasis_symbol : {"\*", "\_"}, default "\*"
    Symbol to use for emphasis/italic formatting in Markdown.
bullet_symbols : str, default "\*-+"
    Characters to cycle through for nested bullet lists.
list_indent_width : int, default 4
    Number of spaces to use for each level of list indentation.
underline_mode : {"html", "markdown", "ignore"}, default "html"
    How to handle underlined text:
    - "html": Use <u>text</u> tags
    - "markdown": Use __text__ (non-standard)
    - "ignore": Strip underline formatting
superscript_mode : {"html", "markdown", "ignore"}, default "html"
    How to handle superscript text:
    - "html": Use <sup>text</sup> tags
    - "markdown": Use ^text^ (non-standard)
    - "ignore": Strip superscript formatting
subscript_mode : {"html", "markdown", "ignore"}, default "html"
    How to handle subscript text:
    - "html": Use <sub>text</sub> tags
    - "markdown": Use ~text~ (non-standard)
    - "ignore": Strip subscript formatting
use_hash_headings : bool, default True
    Whether to use # syntax for headings instead of underline style.
    When True, generates "# Heading" style. When False, generates
    "Heading\n=======" style for level 1 and "Heading\n-------" for levels 2+.
flavor : {"gfm", "commonmark", "markdown_plus"}, default "gfm"
    Markdown flavor/dialect to use for output:
    - "gfm": GitHub Flavored Markdown (tables, strikethrough, task lists)
    - "commonmark": Strict CommonMark specification
    - "markdown_plus": All extensions enabled (footnotes, definition lists, etc.)
unsupported_table_mode : {"drop", "ascii", "force", "html"}, default "force"
    How to handle tables when the selected flavor doesn't support them:
    - "drop": Skip table entirely
    - "ascii": Render as ASCII art table
    - "force": Render as pipe table anyway (may not be valid for flavor)
    - "html": Render as HTML <table>
unsupported_inline_mode : {"plain", "force", "html"}, default "plain"
    How to handle inline elements unsupported by the selected flavor:
    - "plain": Render content without the unsupported formatting
    - "force": Use markdown syntax anyway (may not be valid for flavor)
    - "html": Use HTML tags (e.g., <u> for underline)
heading_level_offset : int, default 0
    Shift all heading levels by this amount (positive or negative).
    Useful when collating multiple documents into a parent document with existing structure.
code_fence_char : {"`", "~"}, default "`"
    Character to use for code fences (backtick or tilde).
code_fence_min : int, default 3
    Minimum length for code fences (typically 3).
collapse_blank_lines : bool, default True
    Collapse multiple consecutive blank lines into at most 2 (normalizing whitespace).
link_style : {"inline", "reference"}, default "inline"
    Link style to use:
    - "inline": [text](url) style links
    - "reference": [text][ref] style with reference definitions at end
reference_link_placement : {"end_of_document", "after_block"}, default "end_of_document"
    Where to place reference link definitions when using reference-style links:
    - "end_of_document": All reference definitions at document end (current behavior)
    - "after_block": Reference definitions placed after each block-level element
autolink_bare_urls : bool, default False
    Automatically convert bare URLs (e.g., http://example.com) found in Text nodes
    into Markdown autolinks (<http://example.com>). Ensures all URLs are clickable.
table_pipe_escape : bool, default True
    Whether to escape pipe characters (|) in table cell content.
math_mode : {"latex", "mathml", "html"}, default "latex"
    Preferred math representation for flavors that support math. When the
    requested representation is unavailable on a node, the renderer falls
    back to any available representation while preserving flavor
    constraints.
html_sanitization : {"pass-through", "escape", "drop", "sanitize"}, default "escape"
    How to handle raw HTML content in markdown (HTMLBlock and HTMLInline nodes):
    - "pass-through": Pass HTML through unchanged (use only with trusted content)
    - "escape": HTML-escape the content to show as text (secure default)
    - "drop": Remove HTML content entirely
    - "sanitize": Remove dangerous elements/attributes (requires bleach for best results)
    Note: This does not affect fenced code blocks with language="html", which are
    always rendered as code and are already safe.

**fail_on_resource_errors**

   Raise RenderingError on resource failures (images, etc.) instead of logging warnings

   :Type: ``bool``
   :CLI flag: ``--markdown-fail-on-resource-errors``
   :Default: ``False``
   :Importance: advanced

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--markdown-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**escape_special**

   Escape special Markdown characters (e.g. asterisks) in text content

   :Type: ``bool``
   :CLI flag: ``--markdown-no-escape-special``
   :Default: ``True``
   :Importance: core

**emphasis_symbol**

   Symbol to use for emphasis/italic formatting

   :Type: ``Literal['*', '_']``
   :CLI flag: ``--markdown-emphasis-symbol``
   :Default: ``'*'``
   :Choices: ``*``, ``_``
   :Importance: core

**bullet_symbols**

   Characters to cycle through for nested bullet lists

   :Type: ``str``
   :CLI flag: ``--markdown-bullet-symbols``
   :Default: ``'*-+'``
   :Importance: advanced

**list_indent_width**

   Number of spaces to use for each level of list indentation

   :Type: ``int``
   :CLI flag: ``--markdown-list-indent-width``
   :Default: ``4``
   :Importance: advanced

**underline_mode**

   How to handle underlined text

   :Type: ``Literal['html', 'markdown', 'ignore']``
   :CLI flag: ``--markdown-underline-mode``
   :Default: ``'html'``
   :Choices: ``html``, ``markdown``, ``ignore``
   :Importance: advanced

**superscript_mode**

   How to handle superscript text

   :Type: ``Literal['html', 'markdown', 'ignore']``
   :CLI flag: ``--markdown-superscript-mode``
   :Default: ``'html'``
   :Choices: ``html``, ``markdown``, ``ignore``
   :Importance: advanced

**subscript_mode**

   How to handle subscript text

   :Type: ``Literal['html', 'markdown', 'ignore']``
   :CLI flag: ``--markdown-subscript-mode``
   :Default: ``'html'``
   :Choices: ``html``, ``markdown``, ``ignore``
   :Importance: advanced

**use_hash_headings**

   Use # syntax for headings instead of underline style

   :Type: ``bool``
   :CLI flag: ``--markdown-no-use-hash-headings``
   :Default: ``True``
   :Importance: core

**flavor**

   Markdown flavor/dialect to use for output

   :Type: ``Literal['gfm', 'commonmark', 'multimarkdown', 'pandoc', 'kramdown', 'markdown_plus']``
   :CLI flag: ``--markdown-flavor``
   :Default: ``'gfm'``
   :Choices: ``gfm``, ``commonmark``, ``multimarkdown``, ``pandoc``, ``kramdown``, ``markdown_plus``
   :Importance: core

**unsupported_table_mode**

   How to handle tables when flavor doesn't support them: drop (skip entirely), ascii (render as ASCII art), force (render as pipe tables anyway), html (render as HTML table)

   :Type: ``Literal['drop', 'ascii', 'force', 'html'] | object``
   :CLI flag: ``--markdown-unsupported-table-mode``
   :Default: ``<object object at 0x7fb9cf8a8a90>``
   :Choices: ``drop``, ``ascii``, ``force``, ``html``
   :Importance: advanced

**unsupported_inline_mode**

   How to handle inline elements unsupported by flavor: plain (render content without formatting), force (use markdown syntax anyway), html (use HTML tags)

   :Type: ``Literal['plain', 'force', 'html'] | object``
   :CLI flag: ``--markdown-unsupported-inline-mode``
   :Default: ``<object object at 0x7fb9cf8a8a90>``
   :Choices: ``plain``, ``force``, ``html``
   :Importance: advanced

**pad_table_cells**

   Pad table cells with spaces for visual alignment in source

   :Type: ``bool``
   :CLI flag: ``--markdown-pad-table-cells``
   :Default: ``False``
   :Importance: advanced

**prefer_setext_headings**

   Prefer setext-style headings (underlines) for h1 and h2

   :Type: ``bool``
   :CLI flag: ``--markdown-prefer-setext-headings``
   :Default: ``False``
   :Importance: advanced

**max_line_width**

   Maximum line width for wrapping (None for no limit)

   :Type: ``UnionType[int, NoneType]``
   :CLI flag: ``--markdown-max-line-width``
   :Default: ``None``
   :Importance: advanced

**table_alignment_default**

   Default alignment for table columns without explicit alignment

   :Type: ``str``
   :CLI flag: ``--markdown-table-alignment-default``
   :Default: ``'left'``
   :Choices: ``left``, ``center``, ``right``
   :Importance: advanced

**heading_level_offset**

   Shift all heading levels by this amount (useful when collating docs)

   :Type: ``int``
   :CLI flag: ``--markdown-heading-level-offset``
   :Default: ``0``
   :Importance: advanced

**code_fence_char**

   Character to use for code fences (backtick or tilde)

   :Type: ``Literal['`', '~']``
   :CLI flag: ``--markdown-code-fence-char``
   :Default: ``'`'``
   :Choices: `````, ``~``
   :Importance: advanced

**code_fence_min**

   Minimum length for code fences (typically 3)

   :Type: ``int``
   :CLI flag: ``--markdown-code-fence-min``
   :Default: ``3``
   :Importance: advanced

**collapse_blank_lines**

   Collapse multiple blank lines into at most 2 (normalize whitespace)

   :Type: ``bool``
   :CLI flag: ``--markdown-no-collapse-blank-lines``
   :Default: ``True``
   :Importance: core

**link_style**

   Link style: inline [text](url) or reference [text][ref]

   :Type: ``Literal['inline', 'reference']``
   :CLI flag: ``--markdown-link-style``
   :Default: ``'inline'``
   :Choices: ``inline``, ``reference``
   :Importance: core

**reference_link_placement**

   Where to place reference link definitions: end_of_document or after_block

   :Type: ``Literal['end_of_document', 'after_block']``
   :CLI flag: ``--markdown-reference-link-placement``
   :Default: ``'end_of_document'``
   :Choices: ``end_of_document``, ``after_block``
   :Importance: advanced

**autolink_bare_urls**

   Convert bare URLs in text to Markdown autolinks (<http://...>)

   :Type: ``bool``
   :CLI flag: ``--markdown-autolink-bare-urls``
   :Default: ``False``
   :Importance: core

**table_pipe_escape**

   Escape pipe characters in table cells

   :Type: ``bool``
   :CLI flag: ``--markdown-no-table-pipe-escape``
   :Default: ``True``
   :Importance: core

**math_mode**

   Preferred math representation: latex, mathml, or html

   :Type: ``Literal['latex', 'mathml', 'html']``
   :CLI flag: ``--markdown-math-mode``
   :Default: ``'latex'``
   :Choices: ``latex``, ``mathml``, ``html``
   :Importance: core

**metadata_frontmatter**

   Render document metadata as YAML frontmatter

   :Type: ``bool``
   :CLI flag: ``--markdown-metadata-frontmatter``
   :Default: ``False``
   :Importance: core

**metadata_format**

   Format for metadata frontmatter: yaml, toml, or json

   :Type: ``Literal['yaml', 'toml', 'json']``
   :CLI flag: ``--markdown-metadata-format``
   :Default: ``'yaml'``
   :Choices: ``yaml``, ``toml``, ``json``
   :Importance: advanced

**html_sanitization**

   How to handle raw HTML content in markdown: pass-through (allow HTML as-is), escape (show as text), drop (remove entirely), sanitize (remove dangerous elements). Default is 'escape' for security. Does not affect code blocks.

   :Type: ``Literal['pass-through', 'escape', 'drop', 'sanitize']``
   :CLI flag: ``--markdown-html-sanitization``
   :Default: ``'escape'``
   :Choices: ``pass-through``, ``escape``, ``drop``, ``sanitize``
   :Importance: security

Network Fetch Options
^^^^^^^^^^^^^^^^^^^^^

Network security options for remote resource fetching.

This dataclass contains settings that control how remote resources
(images, CSS, etc.) are fetched, including security constraints
to prevent SSRF attacks.

Parameters
----------
allow_remote_fetch : bool, default False
    Whether to allow fetching remote URLs for images and other resources.
    When False, prevents SSRF attacks by blocking all network requests.
allowed_hosts : list[str] | None, default None
    List of allowed hostnames or CIDR blocks for remote fetching.
    If None, all hosts are allowed (subject to other security constraints).
require_https : bool, default False
    Whether to require HTTPS for all remote URL fetching.
network_timeout : float, default 10.0
    Timeout in seconds for remote URL fetching.
max_requests_per_second : float, default 10.0
    Maximum number of network requests per second (rate limiting).
max_concurrent_requests : int, default 5
    Maximum number of concurrent network requests.

Notes
-----
Asset size limits are inherited from BaseParserOptions.max_asset_size_bytes.

**allow_remote_fetch**

   Allow fetching remote URLs for images and other resources. When False, prevents SSRF attacks by blocking all network requests.

   :Type: ``bool``
   :CLI flag: ``--network-allow-remote-fetch``
   :Default: ``False``
   :Importance: security

**allowed_hosts**

   List of allowed hostnames or CIDR blocks for remote fetching. If None, all hosts are allowed (subject to other security constraints).

   :Type: ``UnionType[list[str], NoneType]``
   :CLI flag: ``--network-allowed-hosts``
   :Default: ``None``
   :Importance: security

**require_https**

   Require HTTPS for all remote URL fetching

   :Type: ``bool``
   :CLI flag: ``--network-no-require-https``
   :Default: ``True``
   :Importance: security

**require_head_success**

   Require HEAD request success before remote URL fetching

   :Type: ``bool``
   :CLI flag: ``--network-no-require-head-success``
   :Default: ``True``
   :Importance: security

**network_timeout**

   Timeout in seconds for remote URL fetching

   :Type: ``float``
   :CLI flag: ``--network-network-timeout``
   :Default: ``10.0``
   :Importance: security

**max_redirects**

   Maximum number of HTTP redirects to follow

   :Type: ``int``
   :CLI flag: ``--network-max-redirects``
   :Default: ``5``
   :Importance: security

**allowed_content_types**

   Allowed content-type prefixes for remote resources (e.g., 'image/', 'text/')

   :Type: ``UnionType[tuple[str, ...], NoneType]``
   :CLI flag: ``--network-allowed-content-types``
   :Default: ``('image/',)``
   :CLI action: ``append``
   :Importance: security

**max_requests_per_second**

   Maximum number of network requests per second (rate limiting)

   :Type: ``float``
   :CLI flag: ``--network-max-requests-per-second``
   :Default: ``10.0``
   :Importance: security

**max_concurrent_requests**

   Maximum number of concurrent network requests

   :Type: ``int``
   :CLI flag: ``--network-max-concurrent-requests``
   :Default: ``5``
   :Importance: security

Local File Access Options
^^^^^^^^^^^^^^^^^^^^^^^^^

Local file access security options.

This dataclass contains settings that control access to local files
via file:// URLs and similar mechanisms.

Parameters
----------
allow_local_files : bool, default False
    Whether to allow access to local files via file:// URLs.
local_file_allowlist : list[str] | None, default None
    List of directories allowed for local file access.
    Only applies when allow_local_files=True.
local_file_denylist : list[str] | None, default None
    List of directories denied for local file access.
allow_cwd_files : bool, default False
    Whether to allow local files from current working directory and subdirectories.

**allow_local_files**

   Allow access to local files via file:// URLs (security setting)

   :Type: ``bool``
   :CLI flag: ``--local-allow-local-files``
   :Default: ``False``
   :Importance: security

**local_file_allowlist**

   List of directories allowed for local file access (when allow_local_files=True)

   :Type: ``UnionType[list[str], NoneType]``
   :CLI flag: ``--local-local-file-allowlist``
   :Default: ``None``
   :Importance: security

**local_file_denylist**

   List of directories denied for local file access

   :Type: ``UnionType[list[str], NoneType]``
   :CLI flag: ``--local-local-file-denylist``
   :Default: ``None``
   :Importance: security

**allow_cwd_files**

   Allow local files from current working directory and subdirectories

   :Type: ``bool``
   :CLI flag: ``--local-allow-cwd-files``
   :Default: ``False``
   :Importance: security

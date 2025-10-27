Configuration Options
=====================

all2md exposes every converter knob as an immutable dataclass. The command line, environment variables, presets,
and Python API all hydrate the same option objects, so behaviour stays consistent regardless of entry point.

Overview
--------

The options stack is intentionally layered:

1. :class:`~all2md.options.base.BaseParserOptions` — shared attachment policy, metadata extraction, asset limits
2. Nested security helpers such as :class:`~all2md.options.common.NetworkFetchOptions` and
   :class:`~all2md.options.common.LocalFileAccessOptions`
3. Format-specific options (``PdfOptions``, ``HtmlOptions``, ``ZipOptions``, …) which may embed
   :class:`~all2md.options.markdown.MarkdownRendererOptions` or renderer counterparts

Because every class inherits from ``CloneFrozenMixin`` you can derive safe variants without mutating originals:

.. code-block:: python

   from all2md.options import HtmlOptions, NetworkFetchOptions

   hardened_network = NetworkFetchOptions(
       allow_remote_fetch=False,
       require_https=True,
       allowed_hosts=["docs.example.com"],
   )

   html_options = HtmlOptions(
       extract_title=True,
       network=hardened_network,
   )

   secure_variant = html_options.create_updated(markdown_options=html_options.markdown_options.create_updated(
       flavor="gfm",
   ))

CLI flag mapping follows the field path. For example ``HtmlOptions.network.require_https`` becomes
``--html-network-require-https`` (and the env var ``ALL2MD_HTML_NETWORK_REQUIRE_HTTPS``). Nested collections such as
``ZipOptions.include_patterns`` accept multiple values via repeated flags or comma-separated lists.

Options Map
-----------

The table below shows where to look for the most commonly tuned converters.

.. list-table::
   :header-rows: 1
   :widths: 25 30 45

   * - Format / Feature
     - Options Class
     - Highlights
   * - PDF documents
     - ``PdfOptions``
     - Page selection, table/ruling detection, column heuristics, attachment templating
   * - Microsoft Office (DOCX/PPTX)
     - ``DocxOptions`` / ``PptxOptions``
     - Style preservation, image extraction, slide numbering, speaker notes
   * - Web content
     - ``HtmlOptions`` / ``MhtmlOptions``
     - Network security, sanitisation presets, Markdown flavour bridging
   * - Email threads
     - ``EmlOptions``
     - Header preservation, thread stitching, inline attachment handling
   * - EPUB / eBook containers
     - ``EpubOptions``
     - Chapter merging, TOC generation, CSS asset limits
   * - Spreadsheets & tabular data
     - ``XlsxOptions`` / ``OdsSpreadsheetOptions`` / ``CsvOptions``
     - Sheet filtering, row/column caps, truncation indicators
   * - Archives / batch processing
     - ``ZipOptions``
     - Include/exclude patterns, directory depth limits, section heading layout
   * - Markdown rendering
     - ``MarkdownRendererOptions`` / ``MarkdownParserOptions``
     - Flavour defaults (GFM/CommonMark/etc), table handling, HTML passthrough policy

Using Options
-------------

Python API
~~~~~~~~~~

Pass an options object directly or let ``to_markdown`` assemble one from keyword arguments. Nested dataclasses are
constructed automatically from matching kwargs.

.. code-block:: python

   from all2md import to_markdown
   from all2md.options import HtmlOptions

   markdown = to_markdown(
       "page.html",
       options=HtmlOptions(
           extract_title=True,
           network=dict(
               allow_remote_fetch=False,
               allowed_hosts=["docs.example.com"],
               require_https=True,
           ),
       ),
   )

   # Kwargs override existing settings
   hardened = markdown = to_markdown(
       "page.html",
       options=HtmlOptions(),
       allow_remote_fetch=False,
   )

Command Line
~~~~~~~~~~~~

CLI flags mirror the dataclass field names. Format-specific options use prefixes like ``--pdf-*`` or ``--html-*``.
Nested fields join their parents with dashes:

.. code-block:: bash

   # Harden HTML fetching and customise Markdown output
   all2md site.mhtml \
     --html-network-allow-remote-fetch false \
     --html-network-allowed-hosts docs.example.com \
     --html-network-require-https \
     --markdown-flavor gfm

   # ZIP archives with include/exclude filters
   all2md archive.zip \
     --zip-include "docs/**/*.md" \
     --zip-exclude "**/__pycache__/**" \
     --zip-create-section-headings

Environment Variables
~~~~~~~~~~~~~~~~~~~~~

Any CLI flag can be expressed as ``ALL2MD_<DESTINATION>``. Dashes and dots become underscores. Booleans recognise
``true/false`` (or ``1/0``). Example shell snippet:

.. code-block:: bash

   export ALL2MD_ATTACHMENT_MODE=download
   export ALL2MD_PDF_PAGES="1-3,10"
   export ALL2MD_HTML_NETWORK_REQUIRE_HTTPS=true
   export ALL2MD_MARKDOWN_FLAVOR=gfm

   all2md report.pdf  # picks up defaults, still overrideable via CLI

Boolean Defaults Cheat Sheet
----------------------------

Options that default to ``True`` use ``--<prefix>-no-<field>`` on the CLI. This keeps the positive form in Python while
following common ``--no-*`` conventions in shell scripts.

.. list-table::
   :header-rows: 1
   :widths: 32 16 23 29

   * - Dataclass field
     - Default
     - CLI to enable
     - CLI to disable
   * - ``MarkdownRendererOptions.use_hash_headings``
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
   * - ``HtmlOptions.preserve_nested_structure``
     - ``True``
     - (default)
     - ``--html-no-preserve-nested-structure``
   * - ``HtmlOptions.detect_table_alignment``
     - ``True``
     - (default)
     - ``--html-no-detect-table-alignment``
   * - ``PptxOptions.include_notes``
     - ``True``
     - (default)
     - ``--pptx-no-include-notes``
   * - ``EmlOptions.include_headers``
     - ``True``
     - (default)
     - ``--eml-no-include-headers``
   * - ``EpubOptions.merge_chapters``
     - ``True``
     - (default)
     - ``--epub-no-merge-chapters``
   * - ``OdtOptions.preserve_tables``
     - ``True``
     - (default)
     - ``--odt-no-preserve-tables``

For booleans that default to ``False`` simply use the positive flag (e.g. ``--html-strip-dangerous-elements``). The
full list—including renderer toggles and security helpers—is maintained in the generated :doc:`options` reference.

Generated Reference
-------------------

This section is generated automatically from the options dataclasses.

ARCHIVE Options
~~~~~~~~~~~~~~~


ARCHIVE Parser Options
^^^^^^^^^^^^^^^^^^^^^^

Configuration options for archive (TAR/7Z/RAR) to Markdown conversion.

This dataclass contains settings specific to archive processing,
including file filtering, directory structure handling, and attachment extraction.
Inherits attachment handling from AttachmentOptionsMixin for extracting embedded
resources.

**attachment_mode**

   How to handle attachments/images

   :Type: ``AttachmentMode``
   :CLI flag: ``--archive-attachment-mode``
   :Default: ``'alt_text'``
   :Choices: ``skip``, ``alt_text``, ``download``, ``base64``
   :Importance: core

**alt_text_mode**

   How to render alt-text content when using alt_text attachment mode

   :Type: ``AltTextMode``
   :CLI flag: ``--archive-alt-text-mode``
   :Default: ``'default'``
   :Choices: ``default``, ``plain_filename``, ``strict_markdown``, ``footnote``
   :Importance: advanced

**attachment_output_dir**

   Directory to save attachments when using download mode

   :Type: ``str | None``
   :CLI flag: ``--archive-attachment-output-dir``
   :Default: ``None``
   :Importance: advanced

**attachment_base_url**

   Base URL for resolving attachment references

   :Type: ``str | None``
   :CLI flag: ``--archive-attachment-base-url``
   :Default: ``None``
   :Importance: advanced

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--archive-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**attachment_filename_template**

   Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}

   :Type: ``str``
   :CLI flag: ``--archive-attachment-filename-template``
   :Default: ``'{stem}_{type}{seq}.{ext}'``
   :Importance: advanced

**attachment_overwrite**

   File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'

   :Type: ``Literal['unique', 'overwrite', 'skip']``
   :CLI flag: ``--archive-attachment-overwrite``
   :Default: ``'unique'``
   :Choices: ``unique``, ``overwrite``, ``skip``
   :Importance: advanced

**attachment_deduplicate_by_hash**

   Avoid saving duplicate attachments by content hash

   :Type: ``bool``
   :CLI flag: ``--archive-attachment-deduplicate-by-hash``
   :Default: ``False``
   :Importance: advanced

**attachments_footnotes_section**

   Section title for footnote-style attachment references (None to disable)

   :Type: ``str | None``
   :CLI flag: ``--archive-attachments-footnotes-section``
   :Default: ``'Attachments'``
   :Importance: advanced

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--archive-extract-metadata``
   :Default: ``False``
   :Importance: core

**include_patterns**

   Glob patterns for files to include

   :Type: ``list[str] | None``
   :CLI flag: ``--archive-include``
   :Default: ``None``
   :Importance: advanced

**exclude_patterns**

   Glob patterns for files to exclude

   :Type: ``list[str] | None``
   :CLI flag: ``--archive-exclude``
   :Default: ``None``
   :Importance: advanced

**max_depth**

   Maximum directory depth to traverse

   :Type: ``int | None``
   :CLI flag: ``--archive-max-depth``
   :Default: ``None``
   :Importance: advanced

**create_section_headings**

   Create section headings for each file

   :Type: ``bool``
   :CLI flag: ``--archive-no-section-headings``
   :Default: ``True``
   :Importance: core

**preserve_directory_structure**

   Include directory path in section headings

   :Type: ``bool``
   :CLI flag: ``--archive-no-preserve-directory``
   :Default: ``True``
   :Importance: advanced

**flatten_structure**

   Flatten directory structure in output

   :Type: ``bool``
   :CLI flag: ``--archive-flatten``
   :Default: ``False``
   :Importance: advanced

**extract_resource_files**

   Extract non-parseable files to attachment directory

   :Type: ``bool``
   :CLI flag: ``--archive-no-extract-resources``
   :Default: ``True``
   :Importance: advanced

**resource_file_extensions**

   File extensions to treat as resources (None=use defaults, []=parse all)

   :Type: ``list[str] | None``
   :CLI flag: ``--archive-resource-extensions``
   :Default: ``None``
   :Importance: advanced

**skip_empty_files**

   Skip files with no content or parse failures

   :Type: ``bool``
   :CLI flag: ``--archive-no-skip-empty``
   :Default: ``True``
   :Importance: advanced

**include_resource_manifest**

   Include manifest table of extracted resources

   :Type: ``bool``
   :CLI flag: ``--archive-no-resource-manifest``
   :Default: ``True``
   :Importance: advanced

**enable_parallel_processing**

   Enable parallel processing for large archives (opt-in)

   :Type: ``bool``
   :CLI flag: ``--archive-parallel``
   :Default: ``False``
   :Importance: advanced

**max_workers**

   Maximum worker processes for parallel processing (None=auto-detect CPU cores)

   :Type: ``int | None``
   :CLI flag: ``--archive-max-workers``
   :Default: ``None``
   :Importance: advanced

**parallel_threshold**

   Minimum number of files to enable parallel processing

   :Type: ``int``
   :CLI flag: ``--archive-parallel-threshold``
   :Default: ``10``
   :Importance: advanced

ASCIIDOC Options
~~~~~~~~~~~~~~~~


ASCIIDOC Parser Options
^^^^^^^^^^^^^^^^^^^^^^^

Configuration options for AsciiDoc-to-AST parsing.

This dataclass contains settings specific to parsing AsciiDoc documents
into AST representation using a custom parser.

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--asciidoc-extract-metadata``
   :Default: ``False``
   :Importance: core

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

**parse_table_spans**

   Parse table colspan/rowspan syntax (e.g., 2+|cell)

   :Type: ``bool``
   :CLI flag: ``--asciidoc-no-parse-table-spans``
   :Default: ``True``
   :Importance: advanced

**strip_comments**

   Strip comments (// syntax) instead of preserving as Comment nodes

   :Type: ``bool``
   :CLI flag: ``--asciidoc-strip-comments``
   :Default: ``False``
   :Importance: core

ASCIIDOC Renderer Options
^^^^^^^^^^^^^^^^^^^^^^^^^

Configuration options for AST-to-AsciiDoc rendering.

This dataclass contains settings for rendering AST documents as
AsciiDoc output.

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

**metadata_policy**

   Metadata rendering policy controlling which fields appear in output

   :Type: ``MetadataRenderPolicy``
   :CLI flag: ``--asciidoc-renderer-metadata-policy``
   :Default factory: ``MetadataRenderPolicy``
   :Importance: advanced

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

   :Type: ``HtmlPassthroughMode``
   :CLI flag: ``--asciidoc-renderer-html-passthrough-mode``
   :Default: ``'escape'``
   :Choices: ``pass-through``, ``escape``, ``drop``, ``sanitize``
   :Importance: security

**comment_mode**

   How to render Comment and CommentInline nodes: comment (// comments), note (NOTE admonitions), ignore (skip comment nodes entirely). Controls presentation of source document comments.

   :Type: ``AsciiDocCommentMode``
   :CLI flag: ``--asciidoc-renderer-comment-mode``
   :Default: ``'comment'``
   :Choices: ``comment``, ``note``, ``ignore``
   :Importance: core

AST Options
~~~~~~~~~~~


AST Parser Options
^^^^^^^^^^^^^^^^^^

Options for parsing JSON AST documents.

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--ast-extract-metadata``
   :Default: ``False``
   :Importance: core

**validate_schema**

   Validate schema version during parsing

   :Type: ``bool``
   :CLI flag: ``--ast-no-validate-schema``
   :Default: ``True``
   :Importance: core

**strict_mode**

   Fail on unknown node types or attributes

   :Type: ``bool``
   :CLI flag: ``--ast-strict-mode``
   :Default: ``False``
   :Importance: advanced

AST Renderer Options
^^^^^^^^^^^^^^^^^^^^

Options for rendering documents to JSON AST format.

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

**metadata_policy**

   Metadata rendering policy controlling which fields appear in output

   :Type: ``MetadataRenderPolicy``
   :CLI flag: ``--ast-renderer-metadata-policy``
   :Default factory: ``MetadataRenderPolicy``
   :Importance: advanced

**indent**

   JSON indentation spaces (None for compact)

   :Type: ``int | None``
   :CLI flag: ``--ast-renderer-indent``
   :Default: ``2``
   :Importance: core

**ensure_ascii**

   Escape non-ASCII characters in JSON

   :Type: ``bool``
   :CLI flag: ``--ast-renderer-ensure-ascii``
   :Default: ``False``
   :Importance: advanced

**sort_keys**

   Sort JSON object keys alphabetically

   :Type: ``bool``
   :CLI flag: ``--ast-renderer-sort-keys``
   :Default: ``False``
   :Importance: advanced

BBCODE Options
~~~~~~~~~~~~~~


BBCODE Parser Options
^^^^^^^^^^^^^^^^^^^^^

Configuration options for BBCode-to-AST parsing.

This dataclass contains settings specific to parsing BBCode documents
from bulletin boards and forums into AST representation.

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--bbcode-extract-metadata``
   :Default: ``False``
   :Importance: core

**strict_mode**

   Raise errors on malformed BBCode syntax

   :Type: ``bool``
   :CLI flag: ``--bbcode-strict-mode``
   :Default: ``False``
   :Importance: advanced

**unknown_tag_mode**

   How to handle unknown BBCode tags: preserve, strip, or escape

   :Type: ``Literal['preserve', 'strip', 'escape']``
   :CLI flag: ``--bbcode-unknown-tag-mode``
   :Default: ``'strip'``
   :Choices: ``preserve``, ``strip``, ``escape``
   :Importance: core

**parse_color_size**

   Preserve color and size attributes in metadata

   :Type: ``bool``
   :CLI flag: ``--bbcode-no-parse-color-size``
   :Default: ``True``
   :Importance: advanced

**parse_alignment**

   Preserve text alignment (center, left, right)

   :Type: ``bool``
   :CLI flag: ``--bbcode-no-parse-alignment``
   :Default: ``True``
   :Importance: advanced

**html_passthrough_mode**

   How to handle embedded HTML: pass-through, escape, drop, or sanitize

   :Type: ``Literal['pass-through', 'escape', 'drop', 'sanitize']``
   :CLI flag: ``--bbcode-html-passthrough-mode``
   :Default: ``'escape'``
   :Choices: ``pass-through``, ``escape``, ``drop``, ``sanitize``
   :Importance: security

CHM Options
~~~~~~~~~~~


CHM Parser Options
^^^^^^^^^^^^^^^^^^

Configuration options for CHM-to-Markdown conversion.

This dataclass contains settings specific to Microsoft Compiled HTML Help (CHM)
document processing, including page handling, table of contents generation, and
HTML parsing configuration. Inherits attachment handling from AttachmentOptionsMixin
for embedded images and resources.

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
   :Importance: advanced

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

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--chm-extract-metadata``
   :Default: ``False``
   :Importance: core

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
   :Importance: advanced

CSV Options
~~~~~~~~~~~


CSV Parser Options
^^^^^^^^^^^^^^^^^^

Configuration options for CSV/TSV conversion.

This dataclass contains settings specific to delimiter-separated value
file processing, including dialect detection and data limits.

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--csv-extract-metadata``
   :Default: ``False``
   :Importance: core

**detect_csv_dialect**

   Enable csv.Sniffer-based dialect detection (ignored if delimiter is set)

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

**delimiter**

   Override CSV/TSV delimiter (e.g., ',', '\t', ';', '|')

   :Type: ``UnionType[str, NoneType]``
   :CLI flag: ``--csv-delimiter``
   :Default: ``None``
   :Importance: core

**quote_char**

   Override quote character (e.g., '"', "'")

   :Type: ``UnionType[str, NoneType]``
   :CLI flag: ``--csv-quote-char``
   :Default: ``None``
   :Importance: advanced

**escape_char**

   Override escape character (e.g., '\\')

   :Type: ``UnionType[str, NoneType]``
   :CLI flag: ``--csv-escape-char``
   :Default: ``None``
   :Importance: advanced

**double_quote**

   Enable/disable double quoting (two quote chars = one literal quote)

   :Type: ``UnionType[bool, NoneType]``
   :CLI flag: ``--csv-double-quote``
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

   :Type: ``UnionType[int, NoneType]``
   :CLI flag: ``--csv-max-rows``
   :Default: ``None``
   :Importance: advanced

**max_cols**

   Maximum columns per table (None = unlimited)

   :Type: ``UnionType[int, NoneType]``
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

   :Type: ``Literal['preserve', 'title', 'upper', 'lower']``
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

CSV Renderer Options
^^^^^^^^^^^^^^^^^^^^

Configuration options for CSV rendering from AST.

This dataclass contains settings for rendering AST table nodes to CSV format,
including table selection, multi-table handling, and CSV dialect options.

**fail_on_resource_errors**

   Raise RenderingError on resource failures (images, etc.) instead of logging warnings

   :Type: ``bool``
   :CLI flag: ``--csv-renderer-fail-on-resource-errors``
   :Default: ``False``
   :Importance: advanced

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--csv-renderer-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**metadata_policy**

   Metadata rendering policy controlling which fields appear in output

   :Type: ``MetadataRenderPolicy``
   :CLI flag: ``--csv-renderer-metadata-policy``
   :Default factory: ``MetadataRenderPolicy``
   :Importance: advanced

**table_index**

   Which table to export (0-indexed, None = all tables)

   :Type: ``int | None``
   :CLI flag: ``--csv-renderer-table-index``
   :Default: ``0``
   :Importance: core

**table_heading**

   Select table after heading matching this text (case-insensitive)

   :Type: ``str | None``
   :CLI flag: ``--csv-renderer-table-heading``
   :Default: ``None``
   :Importance: core

**multi_table_mode**

   How to handle multiple tables: first, all, or error

   :Type: ``Literal['first', 'all', 'error']``
   :CLI flag: ``--csv-renderer-multi-table-mode``
   :Default: ``'first'``
   :Choices: ``first``, ``all``, ``error``
   :Importance: core

**table_separator**

   Separator between tables when multi_table_mode='all'

   :Type: ``str``
   :CLI flag: ``--csv-renderer-table-separator``
   :Default: ``'\n\n'``
   :Importance: advanced

**delimiter**

   CSV field delimiter (e.g., ',', '\t', ';')

   :Type: ``str``
   :CLI flag: ``--csv-renderer-delimiter``
   :Default: ``','``
   :Importance: core

**quoting**

   CSV quoting style

   :Type: ``Literal['minimal', 'all', 'nonnumeric', 'none']``
   :CLI flag: ``--csv-renderer-quoting``
   :Default: ``'minimal'``
   :Choices: ``minimal``, ``all``, ``nonnumeric``, ``none``
   :Importance: core

**include_table_headings**

   Include heading comments before tables in multi-table mode

   :Type: ``bool``
   :CLI flag: ``--csv-renderer-include-table-headings``
   :Default: ``False``
   :Importance: advanced

**line_terminator**

   Line ending style ('\n' or '\r\n')

   :Type: ``str``
   :CLI flag: ``--csv-renderer-line-terminator``
   :Default: ``'\n'``
   :Importance: advanced

**handle_merged_cells**

   How to handle merged cells

   :Type: ``Literal['repeat', 'blank', 'placeholder']``
   :CLI flag: ``--csv-renderer-handle-merged-cells``
   :Default: ``'repeat'``
   :Choices: ``repeat``, ``blank``, ``placeholder``
   :Importance: advanced

**quote_char**

   Character used for quoting fields

   :Type: ``str``
   :CLI flag: ``--csv-renderer-quote-char``
   :Default: ``'"'``
   :Importance: advanced

**escape_char**

   Character used for escaping (None uses doubling)

   :Type: ``str | None``
   :CLI flag: ``--csv-renderer-escape-char``
   :Default: ``None``
   :Importance: advanced

**include_bom**

   Include UTF-8 BOM for Excel compatibility

   :Type: ``bool``
   :CLI flag: ``--csv-renderer-include-bom``
   :Default: ``False``
   :Importance: advanced

DOCX Options
~~~~~~~~~~~~


DOCX Parser Options
^^^^^^^^^^^^^^^^^^^

Configuration options for DOCX-to-Markdown conversion.

This dataclass contains settings specific to Word document processing,
including image handling and formatting preferences. Inherits attachment
handling from AttachmentOptionsMixin for embedded images and media.

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
   :Importance: advanced

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

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--docx-extract-metadata``
   :Default: ``False``
   :Importance: core

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

   Where to place Comment nodes in the AST: inline (CommentInline nodes at reference points) or footnotes (Comment block nodes appended at end)

   :Type: ``Literal['inline', 'footnotes']``
   :CLI flag: ``--docx-comments-position``
   :Default: ``'footnotes'``
   :Choices: ``inline``, ``footnotes``
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

**code_style_names**

   List of paragraph style names to treat as code blocks (supports partial matching)

   :Type: ``list[str]``
   :CLI flag: ``--docx-code-style-names``
   :Default factory: ``DocxOptions.<lambda>``
   :Importance: advanced

DOCX Renderer Options
^^^^^^^^^^^^^^^^^^^^^

Configuration options for rendering AST to DOCX format.

This dataclass contains settings specific to Word document generation,
including fonts, styles, and formatting preferences.

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

**metadata_policy**

   Metadata rendering policy controlling which fields appear in output

   :Type: ``MetadataRenderPolicy``
   :CLI flag: ``--docx-renderer-metadata-policy``
   :Default factory: ``MetadataRenderPolicy``
   :Importance: advanced

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

**comment_mode**

   How to render Comment and CommentInline nodes: native (Word comments API), visible (text paragraphs with attribution), ignore (skip comment nodes entirely). Controls presentation of comments from DOCX source files and other format annotations.

   :Type: ``Literal['native', 'visible', 'ignore']``
   :CLI flag: ``--docx-renderer-comment-mode``
   :Default: ``'native'``
   :Choices: ``native``, ``visible``, ``ignore``
   :Importance: core

DOKUWIKI Options
~~~~~~~~~~~~~~~~


DOKUWIKI Parser Options
^^^^^^^^^^^^^^^^^^^^^^^

Configuration options for DokuWiki-to-AST parsing.

This dataclass contains settings specific to parsing DokuWiki markup documents
into AST representation using custom regex-based parsing.

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--dokuwiki-extract-metadata``
   :Default: ``False``
   :Importance: core

**parse_plugins**

   Parse plugin syntax (e.g., <WRAP>) or strip them

   :Type: ``bool``
   :CLI flag: ``--dokuwiki-parse-plugins``
   :Default: ``False``
   :Importance: core

**strip_comments**

   Strip comments from output

   :Type: ``bool``
   :CLI flag: ``--dokuwiki-no-strip-comments``
   :Default: ``True``
   :Importance: core

**parse_interwiki**

   Parse interwiki links (e.g., [[wp>Article]])

   :Type: ``bool``
   :CLI flag: ``--dokuwiki-no-parse-interwiki``
   :Default: ``True``
   :Importance: core

**html_passthrough_mode**

   How to handle inline HTML: pass-through, escape, drop, or sanitize

   :Type: ``Literal['pass-through', 'escape', 'drop', 'sanitize']``
   :CLI flag: ``--dokuwiki-html-passthrough-mode``
   :Default: ``'escape'``
   :Choices: ``pass-through``, ``escape``, ``drop``, ``sanitize``
   :Importance: security

DOKUWIKI Renderer Options
^^^^^^^^^^^^^^^^^^^^^^^^^

Configuration options for DokuWiki rendering.

This dataclass contains settings for rendering AST documents as
DokuWiki markup, suitable for DokuWiki-based wikis.

**fail_on_resource_errors**

   Raise RenderingError on resource failures (images, etc.) instead of logging warnings

   :Type: ``bool``
   :CLI flag: ``--dokuwiki-renderer-fail-on-resource-errors``
   :Default: ``False``
   :Importance: advanced

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--dokuwiki-renderer-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**metadata_policy**

   Metadata rendering policy controlling which fields appear in output

   :Type: ``MetadataRenderPolicy``
   :CLI flag: ``--dokuwiki-renderer-metadata-policy``
   :Default factory: ``MetadataRenderPolicy``
   :Importance: advanced

**use_html_for_unsupported**

   Use HTML tags for unsupported elements

   :Type: ``bool``
   :CLI flag: ``--dokuwiki-renderer-no-use-html-for-unsupported``
   :Default: ``True``
   :Importance: core

**monospace_fence**

   Use <code> tags instead of '' for inline code

   :Type: ``bool``
   :CLI flag: ``--dokuwiki-renderer-monospace-fence``
   :Default: ``False``
   :Importance: core

**html_passthrough_mode**

   How to handle raw HTML content: pass-through, escape, drop, or sanitize

   :Type: ``HtmlPassthroughMode``
   :CLI flag: ``--dokuwiki-renderer-html-passthrough-mode``
   :Default: ``'pass-through'``
   :Choices: ``pass-through``, ``escape``, ``drop``, ``sanitize``
   :Importance: security

**comment_mode**

   Comment rendering mode: html, visible, or ignore

   :Type: ``DokuWikiCommentMode``
   :CLI flag: ``--dokuwiki-renderer-comment-mode``
   :Default: ``'html'``
   :Choices: ``html``, ``visible``, ``ignore``
   :Importance: core

EML Options
~~~~~~~~~~~


EML Parser Options
^^^^^^^^^^^^^^^^^^

Configuration options for EML-to-Markdown conversion.

This dataclass contains settings specific to email message processing,
including robust parsing, date handling, quote processing, and URL cleaning.
Inherits attachment handling from AttachmentOptionsMixin for email attachments.

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
   :Importance: advanced

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

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--eml-extract-metadata``
   :Default: ``False``
   :Importance: core

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
   :Importance: advanced

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
   :Importance: advanced

**detect_reply_separators**

   Detect common reply separators

   :Type: ``bool``
   :CLI flag: ``--eml-detect-reply-separators``
   :Default: ``True``
   :Importance: advanced

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

   URL wrappers (e.g. 'urldefense') to strip from links

   :Type: ``list[str] | None``
   :CLI flag: ``--eml-url-wrappers``
   :Default factory: ``EmlOptions.<lambda>``
   :Importance: security

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
   :Importance: advanced

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
   :Importance: advanced

**include_plain_parts**

   Include plain text content parts from emails

   :Type: ``bool``
   :CLI flag: ``--eml-include-plain-parts``
   :Default: ``False``
   :Importance: advanced

EPUB Options
~~~~~~~~~~~~


EPUB Parser Options
^^^^^^^^^^^^^^^^^^^

Configuration options for EPUB-to-Markdown conversion.

This dataclass contains settings specific to EPUB document processing,
including chapter handling, table of contents generation, and image handling.
Inherits attachment handling from AttachmentOptionsMixin for embedded images.

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
   :Importance: advanced

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

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--epub-extract-metadata``
   :Default: ``False``
   :Importance: core

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

**metadata_policy**

   Metadata rendering policy controlling which fields appear in output

   :Type: ``MetadataRenderPolicy``
   :CLI flag: ``--epub-renderer-metadata-policy``
   :Default factory: ``MetadataRenderPolicy``
   :Importance: advanced

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

   :Type: ``str | None``
   :CLI flag: ``--epub-renderer-title``
   :Default: ``None``
   :Importance: core

**author**

   EPUB book author (None = use document metadata)

   :Type: ``str | None``
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

   :Type: ``str | None``
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

   :Type: ``str | None``
   :CLI flag: ``--epub-renderer-cover-image-path``
   :Default: ``None``
   :Importance: advanced

**network**

   Network security options for fetching remote images

   :Type: ``NetworkFetchOptions``
   :CLI flag: ``--epub-renderer-network``
   :Default factory: ``NetworkFetchOptions``
   :Importance: security

FB2 Options
~~~~~~~~~~~


FB2 Parser Options
^^^^^^^^^^^^^^^^^^

Configuration options for FB2-to-AST conversion.

Inherits attachment handling from AttachmentOptionsMixin for embedded images
in FictionBook 2.0 ebooks.

**attachment_mode**

   How to handle attachments/images

   :Type: ``AttachmentMode``
   :CLI flag: ``--fb2-attachment-mode``
   :Default: ``'alt_text'``
   :Choices: ``skip``, ``alt_text``, ``download``, ``base64``
   :Importance: core

**alt_text_mode**

   How to render alt-text content when using alt_text attachment mode

   :Type: ``AltTextMode``
   :CLI flag: ``--fb2-alt-text-mode``
   :Default: ``'default'``
   :Choices: ``default``, ``plain_filename``, ``strict_markdown``, ``footnote``
   :Importance: advanced

**attachment_output_dir**

   Directory to save attachments when using download mode

   :Type: ``str | None``
   :CLI flag: ``--fb2-attachment-output-dir``
   :Default: ``None``
   :Importance: advanced

**attachment_base_url**

   Base URL for resolving attachment references

   :Type: ``str | None``
   :CLI flag: ``--fb2-attachment-base-url``
   :Default: ``None``
   :Importance: advanced

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--fb2-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**attachment_filename_template**

   Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}

   :Type: ``str``
   :CLI flag: ``--fb2-attachment-filename-template``
   :Default: ``'{stem}_{type}{seq}.{ext}'``
   :Importance: advanced

**attachment_overwrite**

   File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'

   :Type: ``Literal['unique', 'overwrite', 'skip']``
   :CLI flag: ``--fb2-attachment-overwrite``
   :Default: ``'unique'``
   :Choices: ``unique``, ``overwrite``, ``skip``
   :Importance: advanced

**attachment_deduplicate_by_hash**

   Avoid saving duplicate attachments by content hash

   :Type: ``bool``
   :CLI flag: ``--fb2-attachment-deduplicate-by-hash``
   :Default: ``False``
   :Importance: advanced

**attachments_footnotes_section**

   Section title for footnote-style attachment references (None to disable)

   :Type: ``str | None``
   :CLI flag: ``--fb2-attachments-footnotes-section``
   :Default: ``'Attachments'``
   :Importance: advanced

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--fb2-extract-metadata``
   :Default: ``False``
   :Importance: core

**include_notes**

   Include bodies/sections marked as notes in the output

   :Type: ``bool``
   :CLI flag: ``--fb2-no-include-notes``
   :Default: ``True``
   :Importance: core

**notes_section_title**

   Heading text used when appending collected notes

   :Type: ``str``
   :CLI flag: ``--fb2-notes-section-title``
   :Default: ``'Notes'``
   :Importance: advanced

**fallback_encodings**

   Additional encodings to try if XML parsing fails

   :Type: ``tuple[str, ...]``
   :CLI flag: ``--fb2-fallback-encodings``
   :Default: ``('utf-8', 'windows-1251', 'koi8-r')``
   :Importance: advanced

HTML Options
~~~~~~~~~~~~


HTML Parser Options
^^^^^^^^^^^^^^^^^^^

Configuration options for HTML-to-Markdown conversion.

This dataclass contains settings specific to HTML document processing,
including heading styles, title extraction, image handling, content
sanitization, and advanced formatting options. Inherits attachment
handling from AttachmentOptionsMixin for images and embedded media.

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
   :Importance: advanced

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

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--html-extract-metadata``
   :Default: ``False``
   :Importance: core

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

**strip_framework_attributes**

   Remove JavaScript framework attributes (x-*, v-*, ng-*, hx-*, etc.) that can execute code in framework contexts. Only needed if output HTML will be rendered in browsers with these frameworks installed.

   :Type: ``bool``
   :CLI flag: ``--html-strip-framework-attributes``
   :Default: ``False``
   :Importance: security

**detect_table_alignment**

   Automatically detect table column alignment from CSS/attributes

   :Type: ``bool``
   :CLI flag: ``--html-no-detect-table-alignment``
   :Default: ``True``
   :Importance: advanced

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

**strip_comments**

   Remove HTML comments from output

   :Type: ``bool``
   :CLI flag: ``--html-no-strip-comments``
   :Default: ``True``
   :Importance: advanced

**collapse_whitespace**

   Collapse multiple spaces/newlines into single spaces

   :Type: ``bool``
   :CLI flag: ``--html-no-collapse-whitespace``
   :Default: ``True``
   :Importance: advanced

**extract_readable**

   Extract main article content by stripping navigation and other non-readable content using readability-lxml

   :Type: ``bool``
   :CLI flag: ``--html-extract-readable``
   :Default: ``False``
   :Importance: advanced

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

   Whitelist of allowed HTML attributes. Can be a tuple of attribute names (global allowlist) or a dict mapping element names to tuples of allowed attributes (per-element allowlist). Examples: ('class', 'id') or {'img': ('src', 'alt', 'title'), 'a': ('href', 'title')}. CLI note: For complex dict structures, pass as JSON string: --allowed-attributes '{"img": ["src", "alt"], "a": ["href"]}'

   :Type: ``tuple[str, ...] | dict[str, tuple[str, ...]] | None``
   :CLI flag: ``--html-allowed-attributes``
   :Default: ``None``
   :CLI action: ``append``
   :Importance: security

**figures_parsing**

   How to parse <figure> elements: blockquote, paragraph, image_with_caption, caption_only, html, skip

   :Type: ``Literal['blockquote', 'paragraph', 'image_with_caption', 'caption_only', 'html', 'skip']``
   :CLI flag: ``--html-figures-parsing``
   :Default: ``'blockquote'``
   :Choices: ``blockquote``, ``paragraph``, ``image_with_caption``, ``caption_only``, ``html``, ``skip``
   :Importance: advanced

**details_parsing**

   How to render <details>/<summary> elements: blockquote, html, skip

   :Type: ``Literal['blockquote', 'paragraph', 'html', 'skip']``
   :CLI flag: ``--html-details-parsing``
   :Default: ``'blockquote'``
   :Choices: ``blockquote``, ``html``, ``skip``
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

**html_parser**

   BeautifulSoup parser to use: 'html.parser' (built-in, fast, may differ from browsers), 'html5lib' (standards-compliant, slower, matches browser behavior), 'lxml' (fast, requires C library). For security-critical applications, consider 'html5lib' for more consistent parsing.

   :Type: ``Literal['html.parser', 'html5lib', 'lxml']``
   :CLI flag: ``--html-html-parser``
   :Default: ``'html.parser'``
   :Choices: ``html.parser``, ``html5lib``, ``lxml``
   :Importance: advanced

HTML Renderer Options
^^^^^^^^^^^^^^^^^^^^^

Configuration options for rendering AST to HTML format.

This dataclass contains settings specific to HTML generation,
including document structure, styling, templating, and feature toggles.

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

**metadata_policy**

   Metadata rendering policy controlling which fields appear in output

   :Type: ``MetadataRenderPolicy``
   :CLI flag: ``--html-renderer-metadata-policy``
   :Default factory: ``MetadataRenderPolicy``
   :Importance: advanced

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

   :Type: ``str | None``
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

   :Type: ``HtmlPassthroughMode``
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

   :Type: ``str | None``
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

   :Type: ``dict[str, str | list[str]] | None``
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
   :Default: ``True``
   :Importance: security

**csp_policy**

   Custom Content-Security-Policy header value. If None, uses default secure policy.

   :Type: ``str | None``
   :CLI flag: ``--html-renderer-csp-policy``
   :Default: ``"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';"``
   :Importance: security

**comment_mode**

   How to render Comment and CommentInline nodes: native (HTML comments <!-- -->), visible (visible <div>/<span> elements), ignore (skip comment nodes entirely). Controls presentation of comments from DOCX, HTML parsers, and other formats with annotations.

   :Type: ``HtmlCommentMode``
   :CLI flag: ``--html-renderer-comment-mode``
   :Default: ``'native'``
   :Choices: ``native``, ``visible``, ``ignore``
   :Importance: core

IPYNB Options
~~~~~~~~~~~~~


IPYNB Parser Options
^^^^^^^^^^^^^^^^^^^^

Configuration options for IPYNB-to-Markdown conversion.

This dataclass contains settings specific to Jupyter Notebook processing,
including output handling and image conversion preferences. Inherits
attachment handling from AttachmentOptionsMixin for notebook output images.

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
   :Importance: advanced

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

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--ipynb-extract-metadata``
   :Default: ``False``
   :Importance: core

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

**skip_empty_cells**

   Skip cells with no content (preserves round-trip fidelity when False)

   :Type: ``bool``
   :CLI flag: ``--ipynb-no-skip-empty-cells``
   :Default: ``True``
   :Importance: advanced

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

IPYNB Renderer Options
^^^^^^^^^^^^^^^^^^^^^^

Configuration options for rendering AST documents to Jupyter notebooks.

These options control notebook metadata inference, attachment handling, and
preservation of notebook-specific metadata to support near round-tripping
between AST and .ipynb formats.

**fail_on_resource_errors**

   Raise RenderingError on resource failures (images, etc.) instead of logging warnings

   :Type: ``bool``
   :CLI flag: ``--ipynb-renderer-fail-on-resource-errors``
   :Default: ``False``
   :Importance: advanced

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--ipynb-renderer-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**metadata_policy**

   Metadata rendering policy controlling which fields appear in output

   :Type: ``MetadataRenderPolicy``
   :CLI flag: ``--ipynb-renderer-metadata-policy``
   :Default factory: ``MetadataRenderPolicy``
   :Importance: advanced

**nbformat**

   Major notebook format version (auto = preserve from source)

   :Type: ``int | Literal['auto']``
   :CLI flag: ``--ipynb-renderer-nbformat``
   :Default: ``4``
   :Choices: ``auto``, ``4``, ``5``
   :Importance: advanced

**nbformat_minor**

   Minor notebook format revision (auto = preserve from source)

   :Type: ``int | Literal['auto']``
   :CLI flag: ``--ipynb-renderer-nbformat-minor``
   :Default: ``'auto'``
   :Importance: advanced

**default_language**

   Fallback programming language for language_info

   :Type: ``str``
   :CLI flag: ``--ipynb-renderer-default-language``
   :Default: ``'python'``
   :Importance: core

**default_kernel_name**

   Fallback kernelspec name when inference fails

   :Type: ``str``
   :CLI flag: ``--ipynb-renderer-default-kernel-name``
   :Default: ``'python3'``
   :Importance: core

**default_kernel_display_name**

   Fallback kernelspec display name when inference fails

   :Type: ``str``
   :CLI flag: ``--ipynb-renderer-default-kernel-display-name``
   :Default: ``'Python 3'``
   :Importance: core

**infer_language_from_document**

   Infer language from Document metadata before using defaults

   :Type: ``bool``
   :CLI flag: ``--ipynb-renderer-infer-language-from-document``
   :Default: ``True``
   :Importance: advanced

**infer_kernel_from_document**

   Infer kernelspec information from Document metadata when present

   :Type: ``bool``
   :CLI flag: ``--ipynb-renderer-infer-kernel-from-document``
   :Default: ``True``
   :Importance: advanced

**include_trusted_metadata**

   Preserve cell.metadata.trusted values in output notebook

   :Type: ``bool``
   :CLI flag: ``--ipynb-renderer-include-trusted-metadata``
   :Default: ``False``
   :Importance: advanced

**include_ui_metadata**

   Preserve UI metadata like collapsed/scrolled/widget state

   :Type: ``bool``
   :CLI flag: ``--ipynb-renderer-include-ui-metadata``
   :Default: ``False``
   :Importance: advanced

**preserve_unknown_metadata**

   Retain unrecognized metadata keys instead of dropping them

   :Type: ``bool``
   :CLI flag: ``--ipynb-renderer-preserve-unknown-metadata``
   :Default: ``True``
   :Importance: advanced

**inline_attachments**

   Embed attachments directly inside notebook cells

   :Type: ``bool``
   :CLI flag: ``--ipynb-renderer-inline-attachments``
   :Default: ``True``
   :Importance: core

**markdown_options**

   Override markdown renderer configuration for markdown cells

   :Type: ``MarkdownRendererOptions | None``
   :CLI flag: ``--ipynb-renderer-markdown-options``
   :Default: ``None``
   :Importance: advanced

JINJA Options
~~~~~~~~~~~~~


JINJA Renderer Options
^^^^^^^^^^^^^^^^^^^^^^

Configuration options for Jinja2 template-based rendering.

This dataclass contains settings for rendering AST documents using custom
Jinja2 templates. Templates have full access to the document AST and can
produce any text-based output format (XML, YAML, custom markup, etc.).

**fail_on_resource_errors**

   Raise RenderingError on resource failures (images, etc.) instead of logging warnings

   :Type: ``bool``
   :CLI flag: ``--jinja-renderer-fail-on-resource-errors``
   :Default: ``False``
   :Importance: advanced

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--jinja-renderer-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**metadata_policy**

   Metadata rendering policy controlling which fields appear in output

   :Type: ``MetadataRenderPolicy``
   :CLI flag: ``--jinja-renderer-metadata-policy``
   :Default factory: ``MetadataRenderPolicy``
   :Importance: advanced

**template_file**

   Path to Jinja2 template file

   :Type: ``str | None``
   :CLI flag: ``--jinja-renderer-template-file``
   :Default: ``None``
   :Importance: core

**template_string**

   Inline Jinja2 template string

   :Type: ``str | None``
   :CLI flag: ``--jinja-renderer-template-string``
   :Default: ``None``
   :Importance: core

**template_dir**

   Directory for template includes/extends

   :Type: ``str | None``
   :CLI flag: ``--jinja-renderer-template-dir``
   :Default: ``None``
   :Importance: advanced

**escape_strategy**

   Default escaping strategy for output format

   :Type: ``Literal['xml', 'html', 'latex', 'yaml', 'markdown', 'none', 'custom'] | None``
   :CLI flag: ``--jinja-renderer-escape-strategy``
   :Default: ``None``
   :Choices: ``xml``, ``html``, ``latex``, ``yaml``, ``markdown``, ``none``, ``custom``
   :Importance: core

**custom_escape_function**

   Custom escape function (for escape_strategy='custom')

   :Type: ``Callable[[str], str] | None``
   :CLI flag: ``--jinja-renderer-custom-escape-function``
   :Default: ``None``
   :Importance: advanced

**autoescape**

   Enable Jinja2 autoescape using escape_strategy

   :Type: ``bool``
   :CLI flag: ``--jinja-renderer-autoescape``
   :Default: ``False``
   :Importance: core

**enable_render_filter**

   Enable |render filter for nodes

   :Type: ``bool``
   :CLI flag: ``--jinja-renderer-no-enable-render-filter``
   :Default: ``True``
   :Importance: core

**enable_escape_filters**

   Enable escape filters (escape_xml, etc.)

   :Type: ``bool``
   :CLI flag: ``--jinja-renderer-no-enable-escape-filters``
   :Default: ``True``
   :Importance: core

**enable_traversal_helpers**

   Enable AST traversal helpers (get_headings, etc.)

   :Type: ``bool``
   :CLI flag: ``--jinja-renderer-no-enable-traversal-helpers``
   :Default: ``True``
   :Importance: core

**default_render_format**

   Default format for |render filter

   :Type: ``Literal['markdown', 'plain', 'html']``
   :CLI flag: ``--jinja-renderer-default-render-format``
   :Default: ``'markdown'``
   :Choices: ``markdown``, ``plain``, ``html``
   :Importance: advanced

**extra_context**

   Additional template context variables

   :Type: ``dict[str, Any] | None``
   :CLI flag: ``--jinja-renderer-extra-context``
   :Default: ``None``
   :Importance: advanced

**strict_undefined**

   Raise errors for undefined template variables

   :Type: ``bool``
   :CLI flag: ``--jinja-renderer-no-strict-undefined``
   :Default: ``True``
   :Importance: core

LATEX Options
~~~~~~~~~~~~~


LATEX Parser Options
^^^^^^^^^^^^^^^^^^^^

Configuration options for LaTeX-to-AST parsing.

This dataclass contains settings specific to parsing LaTeX documents
into AST representation using pylatexenc library.

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--latex-extract-metadata``
   :Default: ``False``
   :Importance: core

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

**metadata_policy**

   Metadata rendering policy controlling which fields appear in output

   :Type: ``MetadataRenderPolicy``
   :CLI flag: ``--latex-renderer-metadata-policy``
   :Default factory: ``MetadataRenderPolicy``
   :Importance: advanced

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

**comment_mode**

   How to render Comment and CommentInline nodes: percent (%% comments), todonotes (\todo{}), marginnote (\marginpar{}), ignore (skip comment nodes entirely). Controls presentation of source document comments.

   :Type: ``LatexCommentMode``
   :CLI flag: ``--latex-renderer-comment-mode``
   :Default: ``'percent'``
   :Choices: ``percent``, ``todonotes``, ``marginnote``, ``ignore``
   :Importance: core

MARKDOWN Options
~~~~~~~~~~~~~~~~


MARKDOWN Parser Options
^^^^^^^^^^^^^^^^^^^^^^^

Configuration options for Markdown-to-AST parsing.

This dataclass contains settings specific to parsing Markdown documents
into AST representation, supporting various Markdown flavors and extensions.

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--markdown-extract-metadata``
   :Default: ``False``
   :Importance: core

**flavor**

   Markdown flavor to parse (determines enabled extensions)

   :Type: ``Literal['gfm', 'commonmark', 'multimarkdown', 'pandoc', 'kramdown', 'markdown_plus']``
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

**html_handling**

   How to handle HTML when preserve_html=False: drop (remove entirely), sanitize (clean dangerous content)

   :Type: ``str``
   :CLI flag: ``--markdown-html-handling``
   :Default: ``'drop'``
   :Choices: ``drop``, ``sanitize``
   :Importance: security

**parse_frontmatter**

   Parse YAML/TOML/JSON frontmatter at document start

   :Type: ``bool``
   :CLI flag: ``--markdown-no-parse-frontmatter``
   :Default: ``True``
   :Importance: core

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

**metadata_policy**

   Metadata rendering policy controlling which fields appear in output

   :Type: ``MetadataRenderPolicy``
   :CLI flag: ``--markdown-renderer-metadata-policy``
   :Default factory: ``MetadataRenderPolicy``
   :Importance: advanced

**escape_special**

   Escape special Markdown characters (e.g. asterisks) in text content

   :Type: ``bool``
   :CLI flag: ``--markdown-renderer-no-escape-special``
   :Default: ``True``
   :Importance: core

**emphasis_symbol**

   Symbol to use for emphasis/italic formatting

   :Type: ``EmphasisSymbol``
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

   :Type: ``UnderlineMode``
   :CLI flag: ``--markdown-renderer-underline-mode``
   :Default: ``'html'``
   :Choices: ``html``, ``markdown``, ``ignore``
   :Importance: advanced

**superscript_mode**

   How to handle superscript text

   :Type: ``SuperscriptMode``
   :CLI flag: ``--markdown-renderer-superscript-mode``
   :Default: ``'html'``
   :Choices: ``html``, ``markdown``, ``ignore``
   :Importance: advanced

**subscript_mode**

   How to handle subscript text

   :Type: ``SubscriptMode``
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

   :Type: ``FlavorType``
   :CLI flag: ``--markdown-renderer-flavor``
   :Default: ``'gfm'``
   :Choices: ``gfm``, ``commonmark``, ``multimarkdown``, ``pandoc``, ``kramdown``, ``markdown_plus``
   :Importance: core

**strict_flavor_validation**

   Raise errors on flavor-incompatible options instead of just warnings. When True, validate_flavor_compatibility warnings become ValueError exceptions.

   :Type: ``bool``
   :CLI flag: ``--markdown-renderer-strict-flavor-validation``
   :Default: ``False``
   :Importance: advanced

**unsupported_table_mode**

   How to handle tables when flavor doesn't support them: drop (skip entirely), ascii (render as ASCII art), force (render as pipe tables anyway), html (render as HTML table)

   :Type: ``UnsupportedTableMode | object``
   :CLI flag: ``--markdown-renderer-unsupported-table-mode``
   :Default: ``<object object at 0x0000027755B10A10>``
   :Choices: ``drop``, ``ascii``, ``force``, ``html``
   :Importance: advanced

**unsupported_inline_mode**

   How to handle inline elements unsupported by flavor: plain (render content without formatting), force (use markdown syntax anyway), html (use HTML tags)

   :Type: ``UnsupportedInlineMode | object``
   :CLI flag: ``--markdown-renderer-unsupported-inline-mode``
   :Default: ``<object object at 0x0000027755B10A10>``
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

   :Type: ``int | None``
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

   :Type: ``CodeFenceChar``
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

   :Type: ``LinkStyleType``
   :CLI flag: ``--markdown-renderer-link-style``
   :Default: ``'inline'``
   :Choices: ``inline``, ``reference``
   :Importance: core

**reference_link_placement**

   Where to place reference link definitions: end_of_document or after_block

   :Type: ``ReferenceLinkPlacement``
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

   :Type: ``MathMode``
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

   :Type: ``MetadataFormatType``
   :CLI flag: ``--markdown-renderer-metadata-format``
   :Default: ``'yaml'``
   :Choices: ``yaml``, ``toml``, ``json``
   :Importance: advanced

**html_sanitization**

   How to handle raw HTML content in markdown: pass-through (allow HTML as-is), escape (show as text), drop (remove entirely), sanitize (remove dangerous elements). Default is 'escape' for security. Does not affect code blocks.

   :Type: ``HtmlPassthroughMode``
   :CLI flag: ``--markdown-renderer-html-sanitization``
   :Default: ``'escape'``
   :Choices: ``pass-through``, ``escape``, ``drop``, ``sanitize``
   :Importance: security

**comment_mode**

   How to render Comment and CommentInline nodes: html (HTML comments <!-- -->), blockquote (quoted blocks with attribution), ignore (skip comment nodes entirely). Controls presentation of comments from DOCX, HTML, and other formats that support annotations.

   :Type: ``CommentMode``
   :CLI flag: ``--markdown-renderer-comment-mode``
   :Default: ``'blockquote'``
   :Choices: ``html``, ``blockquote``, ``ignore``
   :Importance: core

MBOX Options
~~~~~~~~~~~~


MBOX Parser Options
^^^^^^^^^^^^^^^^^^^

Configuration options for MBOX-to-Markdown conversion.

This dataclass contains settings specific to mailbox archive processing,
extending EmlOptions with mailbox-specific features like format detection,
message filtering, and folder handling.

**attachment_mode**

   How to handle attachments/images

   :Type: ``AttachmentMode``
   :CLI flag: ``--mbox-attachment-mode``
   :Default: ``'alt_text'``
   :Choices: ``skip``, ``alt_text``, ``download``, ``base64``
   :Importance: core

**alt_text_mode**

   How to render alt-text content when using alt_text attachment mode

   :Type: ``AltTextMode``
   :CLI flag: ``--mbox-alt-text-mode``
   :Default: ``'default'``
   :Choices: ``default``, ``plain_filename``, ``strict_markdown``, ``footnote``
   :Importance: advanced

**attachment_output_dir**

   Directory to save attachments when using download mode

   :Type: ``str | None``
   :CLI flag: ``--mbox-attachment-output-dir``
   :Default: ``None``
   :Importance: advanced

**attachment_base_url**

   Base URL for resolving attachment references

   :Type: ``str | None``
   :CLI flag: ``--mbox-attachment-base-url``
   :Default: ``None``
   :Importance: advanced

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--mbox-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**attachment_filename_template**

   Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}

   :Type: ``str``
   :CLI flag: ``--mbox-attachment-filename-template``
   :Default: ``'{stem}_{type}{seq}.{ext}'``
   :Importance: advanced

**attachment_overwrite**

   File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'

   :Type: ``Literal['unique', 'overwrite', 'skip']``
   :CLI flag: ``--mbox-attachment-overwrite``
   :Default: ``'unique'``
   :Choices: ``unique``, ``overwrite``, ``skip``
   :Importance: advanced

**attachment_deduplicate_by_hash**

   Avoid saving duplicate attachments by content hash

   :Type: ``bool``
   :CLI flag: ``--mbox-attachment-deduplicate-by-hash``
   :Default: ``False``
   :Importance: advanced

**attachments_footnotes_section**

   Section title for footnote-style attachment references (None to disable)

   :Type: ``str | None``
   :CLI flag: ``--mbox-attachments-footnotes-section``
   :Default: ``'Attachments'``
   :Importance: advanced

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--mbox-extract-metadata``
   :Default: ``False``
   :Importance: core

**include_headers**

   Include email headers (From, To, Subject, Date) in output

   :Type: ``bool``
   :CLI flag: ``--mbox-no-include-headers``
   :Default: ``True``
   :Importance: core

**preserve_thread_structure**

   Maintain email thread/reply chain structure

   :Type: ``bool``
   :CLI flag: ``--mbox-no-preserve-thread-structure``
   :Default: ``True``
   :Importance: core

**date_format_mode**

   Date formatting mode: iso8601, locale, or strftime

   :Type: ``DateFormatMode``
   :CLI flag: ``--mbox-date-format-mode``
   :Default: ``'strftime'``
   :Importance: advanced

**date_strftime_pattern**

   Custom strftime pattern for date formatting

   :Type: ``str``
   :CLI flag: ``--mbox-date-strftime-pattern``
   :Default: ``'%m/%d/%y %H:%M'``
   :Importance: advanced

**convert_html_to_markdown**

   Convert HTML content to Markdown

   :Type: ``bool``
   :CLI flag: ``--mbox-convert-html-to-markdown``
   :Default: ``False``
   :Importance: core

**clean_quotes**

   Clean and normalize quoted content

   :Type: ``bool``
   :CLI flag: ``--mbox-clean-quotes``
   :Default: ``True``
   :Importance: advanced

**detect_reply_separators**

   Detect common reply separators

   :Type: ``bool``
   :CLI flag: ``--mbox-detect-reply-separators``
   :Default: ``True``
   :Importance: advanced

**normalize_headers**

   Normalize header casing and whitespace

   :Type: ``bool``
   :CLI flag: ``--mbox-normalize-headers``
   :Default: ``True``
   :Importance: advanced

**preserve_raw_headers**

   Preserve both raw and decoded header values

   :Type: ``bool``
   :CLI flag: ``--mbox-preserve-raw-headers``
   :Default: ``False``
   :Importance: advanced

**clean_wrapped_urls**

   Clean URL defense/safety wrappers from links

   :Type: ``bool``
   :CLI flag: ``--mbox-clean-wrapped-urls``
   :Default: ``True``
   :Importance: security

**url_wrappers**

   URL wrappers (e.g. 'urldefense') to strip from links

   :Type: ``list[str] | None``
   :CLI flag: ``--mbox-url-wrappers``
   :Default factory: ``EmlOptions.<lambda>``
   :Importance: security

**html_network**

   Network security settings for HTML part conversion

   :Type: ``NetworkFetchOptions``
   :CLI flag: ``--mbox-html-network``
   :Default factory: ``NetworkFetchOptions``

**sort_order**

   Email chain sort order: 'asc' (oldest first) or 'desc' (newest first)

   :Type: ``Literal['asc', 'desc']``
   :CLI flag: ``--mbox-sort-order``
   :Default: ``'asc'``
   :Choices: ``asc``, ``desc``
   :Importance: advanced

**subject_as_h1**

   Include subject line as H1 heading

   :Type: ``bool``
   :CLI flag: ``--mbox-no-subject-as-h1``
   :Default: ``True``
   :Importance: advanced

**include_attach_section_heading**

   Include heading before attachments section

   :Type: ``bool``
   :CLI flag: ``--mbox-no-include-attach-section-heading``
   :Default: ``True``
   :Importance: advanced

**attach_section_title**

   Title for attachments section heading

   :Type: ``str``
   :CLI flag: ``--mbox-attach-section-title``
   :Default: ``'Attachments'``
   :Importance: advanced

**include_html_parts**

   Include HTML content parts from emails

   :Type: ``bool``
   :CLI flag: ``--mbox-no-include-html-parts``
   :Default: ``True``
   :Importance: advanced

**include_plain_parts**

   Include plain text content parts from emails

   :Type: ``bool``
   :CLI flag: ``--mbox-include-plain-parts``
   :Default: ``False``
   :Importance: advanced

**mailbox_format**

   Mailbox format type (auto, mbox, maildir, mh, babyl, mmdf)

   :Type: ``MailboxFormatType``
   :CLI flag: ``--mbox-mailbox-format``
   :Default: ``'auto'``
   :Importance: core

**output_structure**

   Output structure: 'flat' (sequential) or 'hierarchical' (preserve folders)

   :Type: ``OutputStructureMode``
   :CLI flag: ``--mbox-output-structure``
   :Default: ``'flat'``
   :Choices: ``flat``, ``hierarchical``
   :Importance: core

**max_messages**

   Maximum number of messages to process (None for unlimited)

   :Type: ``int | None``
   :CLI flag: ``--mbox-max-messages``
   :Default: ``None``
   :Importance: advanced

**date_range_start**

   Only process messages on or after this date

   :Type: ``datetime.datetime | None``
   :CLI flag: ``--mbox-date-range-start``
   :Default: ``None``
   :Importance: advanced

**date_range_end**

   Only process messages on or before this date

   :Type: ``datetime.datetime | None``
   :CLI flag: ``--mbox-date-range-end``
   :Default: ``None``
   :Importance: advanced

**folder_filter**

   For maildir, only process these folders (None for all)

   :Type: ``list[str] | None``
   :CLI flag: ``--mbox-folder-filter``
   :Default: ``None``
   :Importance: advanced

**preserve_folder_metadata**

   Include folder name in message metadata

   :Type: ``bool``
   :CLI flag: ``--mbox-no-preserve-folder-metadata``
   :Default: ``True``
   :Importance: advanced

MEDIAWIKI Options
~~~~~~~~~~~~~~~~~


MEDIAWIKI Parser Options
^^^^^^^^^^^^^^^^^^^^^^^^

Configuration options for MediaWiki-to-AST parsing.

This dataclass contains settings specific to parsing MediaWiki/WikiText documents
into AST representation using mwparserfromhell.

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--mediawiki-extract-metadata``
   :Default: ``False``
   :Importance: core

**parse_templates**

   Parse templates or strip them

   :Type: ``bool``
   :CLI flag: ``--mediawiki-parse-templates``
   :Default: ``False``
   :Importance: core

**parse_tags**

   Parse parser tags (e.g., <ref>, <nowiki>)

   :Type: ``bool``
   :CLI flag: ``--mediawiki-no-parse-tags``
   :Default: ``True``
   :Importance: core

**strip_comments**

   Strip HTML comments from output

   :Type: ``bool``
   :CLI flag: ``--mediawiki-no-strip-comments``
   :Default: ``True``
   :Importance: core

**html_passthrough_mode**

   How to handle inline HTML: pass-through, escape, drop, or sanitize

   :Type: ``Literal['pass-through', 'escape', 'drop', 'sanitize']``
   :CLI flag: ``--mediawiki-html-passthrough-mode``
   :Default: ``'escape'``
   :Choices: ``pass-through``, ``escape``, ``drop``, ``sanitize``
   :Importance: security

MEDIAWIKI Renderer Options
^^^^^^^^^^^^^^^^^^^^^^^^^^

Configuration options for MediaWiki rendering.

This dataclass contains settings for rendering AST documents as
MediaWiki markup, suitable for Wikipedia and other MediaWiki-based wikis.

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

**metadata_policy**

   Metadata rendering policy controlling which fields appear in output

   :Type: ``MetadataRenderPolicy``
   :CLI flag: ``--mediawiki-renderer-metadata-policy``
   :Default factory: ``MetadataRenderPolicy``
   :Importance: advanced

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

**image_caption_mode**

   How to render image captions: auto (use alt_text as caption), alt_only, caption_only

   :Type: ``MediaWikiImageCaptionMode``
   :CLI flag: ``--mediawiki-renderer-image-caption-mode``
   :Default: ``'alt_only'``
   :Choices: ``auto``, ``alt_only``, ``caption_only``
   :Importance: core

**html_passthrough_mode**

   How to handle raw HTML content: pass-through, escape, drop, or sanitize

   :Type: ``HtmlPassthroughMode``
   :CLI flag: ``--mediawiki-renderer-html-passthrough-mode``
   :Default: ``'pass-through'``
   :Choices: ``pass-through``, ``escape``, ``drop``, ``sanitize``
   :Importance: security

**comment_mode**

   Comment rendering mode: html, visible, or ignore

   :Type: ``MediaWikiCommentMode``
   :CLI flag: ``--mediawiki-renderer-comment-mode``
   :Default: ``'html'``
   :Choices: ``html``, ``visible``, ``ignore``
   :Importance: core

MHTML Options
~~~~~~~~~~~~~


MHTML Parser Options
^^^^^^^^^^^^^^^^^^^^

Configuration options for MHTML-to-Markdown conversion.

This dataclass contains settings specific to MHTML file processing,
primarily for handling embedded assets like images and local file security.

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
   :Importance: advanced

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

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--mhtml-extract-metadata``
   :Default: ``False``
   :Importance: core

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

**strip_framework_attributes**

   Remove JavaScript framework attributes (x-*, v-*, ng-*, hx-*, etc.) that can execute code in framework contexts. Only needed if output HTML will be rendered in browsers with these frameworks installed.

   :Type: ``bool``
   :CLI flag: ``--mhtml-strip-framework-attributes``
   :Default: ``False``
   :Importance: security

**detect_table_alignment**

   Automatically detect table column alignment from CSS/attributes

   :Type: ``bool``
   :CLI flag: ``--mhtml-no-detect-table-alignment``
   :Default: ``True``
   :Importance: advanced

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

**strip_comments**

   Remove HTML comments from output

   :Type: ``bool``
   :CLI flag: ``--mhtml-no-strip-comments``
   :Default: ``True``
   :Importance: advanced

**collapse_whitespace**

   Collapse multiple spaces/newlines into single spaces

   :Type: ``bool``
   :CLI flag: ``--mhtml-no-collapse-whitespace``
   :Default: ``True``
   :Importance: advanced

**extract_readable**

   Extract main article content by stripping navigation and other non-readable content using readability-lxml

   :Type: ``bool``
   :CLI flag: ``--mhtml-extract-readable``
   :Default: ``False``
   :Importance: advanced

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

   Whitelist of allowed HTML attributes. Can be a tuple of attribute names (global allowlist) or a dict mapping element names to tuples of allowed attributes (per-element allowlist). Examples: ('class', 'id') or {'img': ('src', 'alt', 'title'), 'a': ('href', 'title')}. CLI note: For complex dict structures, pass as JSON string: --allowed-attributes '{"img": ["src", "alt"], "a": ["href"]}'

   :Type: ``tuple[str, ...] | dict[str, tuple[str, ...]] | None``
   :CLI flag: ``--mhtml-allowed-attributes``
   :Default: ``None``
   :CLI action: ``append``
   :Importance: security

**figures_parsing**

   How to parse <figure> elements: blockquote, paragraph, image_with_caption, caption_only, html, skip

   :Type: ``Literal['blockquote', 'paragraph', 'image_with_caption', 'caption_only', 'html', 'skip']``
   :CLI flag: ``--mhtml-figures-parsing``
   :Default: ``'blockquote'``
   :Choices: ``blockquote``, ``paragraph``, ``image_with_caption``, ``caption_only``, ``html``, ``skip``
   :Importance: advanced

**details_parsing**

   How to render <details>/<summary> elements: blockquote, html, skip

   :Type: ``Literal['blockquote', 'paragraph', 'html', 'skip']``
   :CLI flag: ``--mhtml-details-parsing``
   :Default: ``'blockquote'``
   :Choices: ``blockquote``, ``html``, ``skip``
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

**html_parser**

   BeautifulSoup parser to use: 'html.parser' (built-in, fast, may differ from browsers), 'html5lib' (standards-compliant, slower, matches browser behavior), 'lxml' (fast, requires C library). For security-critical applications, consider 'html5lib' for more consistent parsing.

   :Type: ``Literal['html.parser', 'html5lib', 'lxml']``
   :CLI flag: ``--mhtml-html-parser``
   :Default: ``'html.parser'``
   :Choices: ``html.parser``, ``html5lib``, ``lxml``
   :Importance: advanced

ODP Options
~~~~~~~~~~~


ODP Parser Options
^^^^^^^^^^^^^^^^^^

Configuration options for ODP-to-Markdown conversion.

This dataclass contains settings specific to OpenDocument Presentation (ODP)
processing, including slide selection, numbering, and notes.

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
   :Importance: advanced

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

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--odp-extract-metadata``
   :Default: ``False``
   :Importance: core

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

ODP Renderer Options
^^^^^^^^^^^^^^^^^^^^

Configuration options for rendering AST to ODP format.

This dataclass contains settings specific to OpenDocument Presentation
generation from AST, including slide splitting strategies and layout.

**fail_on_resource_errors**

   Raise RenderingError on resource failures (images, etc.) instead of logging warnings

   :Type: ``bool``
   :CLI flag: ``--odp-renderer-fail-on-resource-errors``
   :Default: ``False``
   :Importance: advanced

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--odp-renderer-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**metadata_policy**

   Metadata rendering policy controlling which fields appear in output

   :Type: ``MetadataRenderPolicy``
   :CLI flag: ``--odp-renderer-metadata-policy``
   :Default factory: ``MetadataRenderPolicy``
   :Importance: advanced

**slide_split_mode**

   Slide splitting strategy: separator, heading, or auto

   :Type: ``Literal['separator', 'heading', 'auto']``
   :CLI flag: ``--odp-renderer-slide-split-mode``
   :Default: ``'auto'``
   :Choices: ``separator``, ``heading``, ``auto``
   :Importance: core

**slide_split_heading_level**

   Heading level for slide splits (H2 = level 2)

   :Type: ``int``
   :CLI flag: ``--odp-renderer-slide-split-heading-level``
   :Default: ``2``
   :Importance: advanced

**default_layout**

   Default slide layout name

   :Type: ``str``
   :CLI flag: ``--odp-renderer-default-layout``
   :Default: ``'Default'``
   :Importance: advanced

**title_slide_layout**

   Layout for first slide

   :Type: ``str``
   :CLI flag: ``--odp-renderer-title-slide-layout``
   :Default: ``'Title'``
   :Importance: advanced

**use_heading_as_slide_title**

   Use first heading as slide title

   :Type: ``bool``
   :CLI flag: ``--odp-renderer-no-use-heading-as-slide-title``
   :Default: ``True``
   :Importance: core

**template_path**

   Path to .odp template file (None = default)

   :Type: ``str | None``
   :CLI flag: ``--odp-renderer-template-path``
   :Default: ``None``
   :Importance: core

**default_font**

   Default font for slide content

   :Type: ``str``
   :CLI flag: ``--odp-renderer-default-font``
   :Default: ``'Liberation Sans'``
   :Importance: core

**default_font_size**

   Default font size for body text

   :Type: ``int``
   :CLI flag: ``--odp-renderer-default-font-size``
   :Default: ``18``
   :Importance: core

**title_font_size**

   Font size for slide titles

   :Type: ``int``
   :CLI flag: ``--odp-renderer-title-font-size``
   :Default: ``44``
   :Importance: advanced

**network**

   Network security options for fetching remote images

   :Type: ``NetworkFetchOptions``
   :CLI flag: ``--odp-renderer-network``
   :Default factory: ``NetworkFetchOptions``

**include_notes**

   Include speaker notes in rendered slides

   :Type: ``bool``
   :CLI flag: ``--odp-renderer-no-include-notes``
   :Default: ``True``
   :Importance: core

**comment_mode**

   Comment rendering mode: native, visible, or ignore

   :Type: ``OdpCommentMode``
   :CLI flag: ``--odp-renderer-comment-mode``
   :Default: ``'native'``
   :Choices: ``native``, ``visible``, ``ignore``
   :Importance: core

ODS Options
~~~~~~~~~~~


ODS Parser Options
^^^^^^^^^^^^^^^^^^

Configuration options for ODS spreadsheet conversion.

This dataclass inherits all spreadsheet options from SpreadsheetParserOptions
and adds ODS-specific options.

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
   :Importance: advanced

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

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--ods-extract-metadata``
   :Default: ``False``
   :Importance: core

**sheets**

   Sheet names to include (list or regex pattern). default = all sheets

   :Type: ``list[str] | str | None``
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

   :Type: ``int | None``
   :CLI flag: ``--ods-max-rows``
   :Default: ``None``
   :Importance: advanced

**max_cols**

   Maximum columns per table (None = unlimited)

   :Type: ``int | None``
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
Inherits attachment handling from AttachmentOptionsMixin for embedded images.

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
   :Importance: advanced

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

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--odt-extract-metadata``
   :Default: ``False``
   :Importance: core

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

ODT Renderer Options
^^^^^^^^^^^^^^^^^^^^

Configuration options for rendering AST to ODT format.

This dataclass contains settings specific to OpenDocument Text generation,
including fonts, styles, and formatting preferences.

**fail_on_resource_errors**

   Raise RenderingError on resource failures (images, etc.) instead of logging warnings

   :Type: ``bool``
   :CLI flag: ``--odt-renderer-fail-on-resource-errors``
   :Default: ``False``
   :Importance: advanced

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--odt-renderer-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**metadata_policy**

   Metadata rendering policy controlling which fields appear in output

   :Type: ``MetadataRenderPolicy``
   :CLI flag: ``--odt-renderer-metadata-policy``
   :Default factory: ``MetadataRenderPolicy``
   :Importance: advanced

**default_font**

   Default font for body text

   :Type: ``str``
   :CLI flag: ``--odt-renderer-default-font``
   :Default: ``'Liberation Sans'``
   :Importance: core

**default_font_size**

   Default font size in points

   :Type: ``int``
   :CLI flag: ``--odt-renderer-default-font-size``
   :Default: ``11``
   :Importance: core

**heading_font_sizes**

   Font sizes for heading levels 1-6 as JSON object (e.g., '{"1": 24, "2": 18}')

   :Type: ``dict[int, int] | None``
   :CLI flag: ``--odt-renderer-heading-font-sizes``
   :Default: ``None``
   :Importance: advanced

**use_styles**

   Use built-in ODT styles vs direct formatting

   :Type: ``bool``
   :CLI flag: ``--odt-renderer-no-use-styles``
   :Default: ``True``
   :Importance: advanced

**code_font**

   Font for code blocks and inline code

   :Type: ``str``
   :CLI flag: ``--odt-renderer-code-font``
   :Default: ``'Liberation Mono'``
   :Importance: core

**code_font_size**

   Font size for code

   :Type: ``int``
   :CLI flag: ``--odt-renderer-code-font-size``
   :Default: ``10``
   :Importance: core

**preserve_formatting**

   Preserve text formatting (bold, italic, etc.)

   :Type: ``bool``
   :CLI flag: ``--odt-renderer-no-preserve-formatting``
   :Default: ``True``
   :Importance: core

**template_path**

   Path to .odt template file for styles (None = default blank document)

   :Type: ``str | None``
   :CLI flag: ``--odt-renderer-template-path``
   :Default: ``None``
   :Importance: core

**network**

   Network security settings for remote image fetching

   :Type: ``NetworkFetchOptions``
   :CLI flag: ``--odt-renderer-network``
   :Default factory: ``NetworkFetchOptions``

**comment_mode**

   How to render Comment and CommentInline nodes: native (ODT annotations), visible (text paragraphs with attribution), ignore (skip comment nodes entirely). Controls presentation of comments from ODT source files and other format annotations.

   :Type: ``OdtCommentMode``
   :CLI flag: ``--odt-renderer-comment-mode``
   :Default: ``'native'``
   :Choices: ``native``, ``visible``, ``ignore``
   :Importance: core

OPENAPI Options
~~~~~~~~~~~~~~~


OPENAPI Parser Options
^^^^^^^^^^^^^^^^^^^^^^

Options for parsing OpenAPI/Swagger specification documents.

This dataclass contains settings specific to parsing OpenAPI specifications
into AST representation, supporting both OpenAPI 3.x and Swagger 2.0 formats.

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--openapi-extract-metadata``
   :Default: ``False``
   :Importance: core

**include_servers**

   Include server information section

   :Type: ``bool``
   :CLI flag: ``--openapi-no-include-servers``
   :Default: ``True``
   :Importance: core

**include_schemas**

   Include schema/model definitions section

   :Type: ``bool``
   :CLI flag: ``--openapi-no-include-schemas``
   :Default: ``True``
   :Importance: core

**include_examples**

   Include request/response examples as code blocks

   :Type: ``bool``
   :CLI flag: ``--openapi-no-include-examples``
   :Default: ``True``
   :Importance: core

**group_by_tag**

   Group API paths by tags

   :Type: ``bool``
   :CLI flag: ``--openapi-no-group-by-tag``
   :Default: ``True``
   :Importance: core

**max_schema_depth**

   Maximum nesting depth for schema properties (prevents circular refs)

   :Type: ``int``
   :CLI flag: ``--openapi-max-schema-depth``
   :Default: ``3``
   :Importance: advanced

**code_block_language**

   Language identifier for code block examples

   :Type: ``str``
   :CLI flag: ``--openapi-code-block-language``
   :Default: ``'json'``
   :Choices: ``json``, ``yaml``, ``text``
   :Importance: advanced

**validate_spec**

   Validate OpenAPI spec using jsonschema (requires jsonschema package)

   :Type: ``bool``
   :CLI flag: ``--openapi-validate-spec``
   :Default: ``False``
   :Importance: advanced

**include_deprecated**

   Include deprecated operations and parameters

   :Type: ``bool``
   :CLI flag: ``--openapi-no-include-deprecated``
   :Default: ``True``
   :Importance: core

**expand_refs**

   Expand $ref references inline or keep as links

   :Type: ``bool``
   :CLI flag: ``--openapi-no-expand-refs``
   :Default: ``True``
   :Importance: advanced

ORG Options
~~~~~~~~~~~


ORG Parser Options
^^^^^^^^^^^^^^^^^^

Configuration options for Org-Mode-to-AST parsing.

This dataclass contains settings specific to parsing Org-Mode documents
into AST representation using orgparse.

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--org-extract-metadata``
   :Default: ``False``
   :Importance: core

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

**parse_scheduling**

   Parse SCHEDULED and DEADLINE timestamps

   :Type: ``bool``
   :CLI flag: ``--org-no-parse-scheduling``
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

**metadata_policy**

   Metadata rendering policy controlling which fields appear in output

   :Type: ``MetadataRenderPolicy``
   :CLI flag: ``--org-renderer-metadata-policy``
   :Default factory: ``MetadataRenderPolicy``
   :Importance: advanced

**heading_style**

   Style for rendering headings

   :Type: ``OrgHeadingStyle``
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

**comment_mode**

   How to render Comment and CommentInline nodes: comment (# comments), drawer (:COMMENT: drawer), ignore (skip comment nodes entirely). Controls presentation of source document comments.

   :Type: ``OrgCommentMode``
   :CLI flag: ``--org-renderer-comment-mode``
   :Default: ``'comment'``
   :Choices: ``comment``, ``drawer``, ``ignore``
   :Importance: core

OUTLOOK Options
~~~~~~~~~~~~~~~


OUTLOOK Parser Options
^^^^^^^^^^^^^^^^^^^^^^

Configuration options for Outlook-to-Markdown conversion.

This dataclass contains settings specific to Outlook format processing (MSG, PST, OST),
extending EmlOptions with Outlook-specific features like folder filtering,
PST/OST archive handling, and advanced message selection.

**attachment_mode**

   How to handle attachments/images

   :Type: ``AttachmentMode``
   :CLI flag: ``--outlook-attachment-mode``
   :Default: ``'alt_text'``
   :Choices: ``skip``, ``alt_text``, ``download``, ``base64``
   :Importance: core

**alt_text_mode**

   How to render alt-text content when using alt_text attachment mode

   :Type: ``AltTextMode``
   :CLI flag: ``--outlook-alt-text-mode``
   :Default: ``'default'``
   :Choices: ``default``, ``plain_filename``, ``strict_markdown``, ``footnote``
   :Importance: advanced

**attachment_output_dir**

   Directory to save attachments when using download mode

   :Type: ``str | None``
   :CLI flag: ``--outlook-attachment-output-dir``
   :Default: ``None``
   :Importance: advanced

**attachment_base_url**

   Base URL for resolving attachment references

   :Type: ``str | None``
   :CLI flag: ``--outlook-attachment-base-url``
   :Default: ``None``
   :Importance: advanced

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--outlook-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**attachment_filename_template**

   Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}

   :Type: ``str``
   :CLI flag: ``--outlook-attachment-filename-template``
   :Default: ``'{stem}_{type}{seq}.{ext}'``
   :Importance: advanced

**attachment_overwrite**

   File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'

   :Type: ``Literal['unique', 'overwrite', 'skip']``
   :CLI flag: ``--outlook-attachment-overwrite``
   :Default: ``'unique'``
   :Choices: ``unique``, ``overwrite``, ``skip``
   :Importance: advanced

**attachment_deduplicate_by_hash**

   Avoid saving duplicate attachments by content hash

   :Type: ``bool``
   :CLI flag: ``--outlook-attachment-deduplicate-by-hash``
   :Default: ``False``
   :Importance: advanced

**attachments_footnotes_section**

   Section title for footnote-style attachment references (None to disable)

   :Type: ``str | None``
   :CLI flag: ``--outlook-attachments-footnotes-section``
   :Default: ``'Attachments'``
   :Importance: advanced

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--outlook-extract-metadata``
   :Default: ``False``
   :Importance: core

**include_headers**

   Include email headers (From, To, Subject, Date) in output

   :Type: ``bool``
   :CLI flag: ``--outlook-no-include-headers``
   :Default: ``True``
   :Importance: core

**preserve_thread_structure**

   Maintain email thread/reply chain structure

   :Type: ``bool``
   :CLI flag: ``--outlook-no-preserve-thread-structure``
   :Default: ``True``
   :Importance: core

**date_format_mode**

   Date formatting mode: iso8601, locale, or strftime

   :Type: ``DateFormatMode``
   :CLI flag: ``--outlook-date-format-mode``
   :Default: ``'strftime'``
   :Importance: advanced

**date_strftime_pattern**

   Custom strftime pattern for date formatting

   :Type: ``str``
   :CLI flag: ``--outlook-date-strftime-pattern``
   :Default: ``'%m/%d/%y %H:%M'``
   :Importance: advanced

**convert_html_to_markdown**

   Convert HTML content to Markdown

   :Type: ``bool``
   :CLI flag: ``--outlook-convert-html-to-markdown``
   :Default: ``False``
   :Importance: core

**clean_quotes**

   Clean and normalize quoted content

   :Type: ``bool``
   :CLI flag: ``--outlook-clean-quotes``
   :Default: ``True``
   :Importance: advanced

**detect_reply_separators**

   Detect common reply separators

   :Type: ``bool``
   :CLI flag: ``--outlook-detect-reply-separators``
   :Default: ``True``
   :Importance: advanced

**normalize_headers**

   Normalize header casing and whitespace

   :Type: ``bool``
   :CLI flag: ``--outlook-normalize-headers``
   :Default: ``True``
   :Importance: advanced

**preserve_raw_headers**

   Preserve both raw and decoded header values

   :Type: ``bool``
   :CLI flag: ``--outlook-preserve-raw-headers``
   :Default: ``False``
   :Importance: advanced

**clean_wrapped_urls**

   Clean URL defense/safety wrappers from links

   :Type: ``bool``
   :CLI flag: ``--outlook-clean-wrapped-urls``
   :Default: ``True``
   :Importance: security

**url_wrappers**

   URL wrappers (e.g. 'urldefense') to strip from links

   :Type: ``list[str] | None``
   :CLI flag: ``--outlook-url-wrappers``
   :Default factory: ``EmlOptions.<lambda>``
   :Importance: security

**html_network**

   Network security settings for HTML part conversion

   :Type: ``NetworkFetchOptions``
   :CLI flag: ``--outlook-html-network``
   :Default factory: ``NetworkFetchOptions``

**sort_order**

   Email chain sort order: 'asc' (oldest first) or 'desc' (newest first)

   :Type: ``Literal['asc', 'desc']``
   :CLI flag: ``--outlook-sort-order``
   :Default: ``'asc'``
   :Choices: ``asc``, ``desc``
   :Importance: advanced

**subject_as_h1**

   Include subject line as H1 heading

   :Type: ``bool``
   :CLI flag: ``--outlook-no-subject-as-h1``
   :Default: ``True``
   :Importance: advanced

**include_attach_section_heading**

   Include heading before attachments section

   :Type: ``bool``
   :CLI flag: ``--outlook-no-include-attach-section-heading``
   :Default: ``True``
   :Importance: advanced

**attach_section_title**

   Title for attachments section heading

   :Type: ``str``
   :CLI flag: ``--outlook-attach-section-title``
   :Default: ``'Attachments'``
   :Importance: advanced

**include_html_parts**

   Include HTML content parts from emails

   :Type: ``bool``
   :CLI flag: ``--outlook-no-include-html-parts``
   :Default: ``True``
   :Importance: advanced

**include_plain_parts**

   Include plain text content parts from emails

   :Type: ``bool``
   :CLI flag: ``--outlook-include-plain-parts``
   :Default: ``False``
   :Importance: advanced

**output_structure**

   Output structure: 'flat' (sequential) or 'hierarchical' (preserve folders)

   :Type: ``OutputStructureMode``
   :CLI flag: ``--outlook-output-structure``
   :Default: ``'flat'``
   :Choices: ``flat``, ``hierarchical``
   :Importance: core

**max_messages**

   Maximum number of messages to process (None for unlimited)

   :Type: ``int | None``
   :CLI flag: ``--outlook-max-messages``
   :Default: ``None``
   :Importance: advanced

**date_range_start**

   Only process messages on or after this date

   :Type: ``datetime.datetime | None``
   :CLI flag: ``--outlook-date-range-start``
   :Default: ``None``
   :Importance: advanced

**date_range_end**

   Only process messages on or before this date

   :Type: ``datetime.datetime | None``
   :CLI flag: ``--outlook-date-range-end``
   :Default: ``None``
   :Importance: advanced

**folder_filter**

   For PST/OST, only process these folders (None for all)

   :Type: ``list[str] | None``
   :CLI flag: ``--outlook-folder-filter``
   :Default: ``None``
   :Importance: advanced

**skip_folders**

   For PST/OST, skip these folders (empty list to process all)

   :Type: ``list[str] | None``
   :CLI flag: ``--outlook-skip-folders``
   :Default factory: ``OutlookOptions.<lambda>``
   :Importance: advanced

**include_subfolders**

   Include messages from subfolders when processing a folder (PST/OST)

   :Type: ``bool``
   :CLI flag: ``--outlook-no-include-subfolders``
   :Default: ``True``
   :Importance: advanced

**preserve_folder_metadata**

   Include folder name in message metadata

   :Type: ``bool``
   :CLI flag: ``--outlook-no-preserve-folder-metadata``
   :Default: ``True``
   :Importance: advanced

PDF Options
~~~~~~~~~~~


PDF Parser Options
^^^^^^^^^^^^^^^^^^

Configuration options for PDF-to-Markdown conversion.

This dataclass contains settings specific to PDF document processing,
including page selection, image handling, and formatting preferences.

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
   :Importance: advanced

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

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--pdf-extract-metadata``
   :Default: ``False``
   :Importance: core

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

Ocr Options
+++++++++++

Configuration options for OCR (Optical Character Recognition).

This dataclass contains settings for detecting and extracting text from
images using Tesseract OCR engine. Can be used by any parser that needs
to extract text from images (PDF scanned pages, standalone images, etc.).

**enabled**

   Enable OCR for image-based content

   :Type: ``bool``
   :CLI flag: ``--pdf-ocr-enabled``
   :Default: ``False``
   :Importance: core

**mode**

   OCR mode: 'auto' (detect when needed), 'force' (always), 'off' (disable)

   :Type: ``Literal['auto', 'force', 'off']``
   :CLI flag: ``--pdf-ocr-mode``
   :Default: ``'auto'``
   :Choices: ``auto``, ``force``, ``off``
   :Importance: core

**languages**

   Tesseract language code(s), e.g. 'eng', 'fra', 'eng+fra', or ['eng', 'fra']

   :Type: ``UnionType[str, list[str]]``
   :CLI flag: ``--pdf-ocr-languages``
   :Default: ``'eng'``
   :Importance: core

**auto_detect_language**

   Attempt to auto-detect document language (requires `langdetect`)

   :Type: ``bool``
   :CLI flag: ``--pdf-ocr-auto-detect-language``
   :Default: ``False``
   :Importance: advanced

**dpi**

   DPI for rendering images for OCR (150-600 recommended)

   :Type: ``int``
   :CLI flag: ``--pdf-ocr-dpi``
   :Default: ``300``
   :Importance: advanced

**text_threshold**

   Minimum characters to consider content text-based (for auto mode)

   :Type: ``int``
   :CLI flag: ``--pdf-ocr-text-threshold``
   :Default: ``50``
   :Importance: advanced

**image_area_threshold**

   Image area ratio (0.0-1.0) to trigger OCR (for auto mode)

   :Type: ``float``
   :CLI flag: ``--pdf-ocr-image-area-threshold``
   :Default: ``0.5``
   :Importance: advanced

**preserve_existing_text**

   Preserve existing text when applying OCR (combine vs replace)

   :Type: ``bool``
   :CLI flag: ``--pdf-ocr-preserve-existing-text``
   :Default: ``False``
   :Importance: advanced

**tesseract_config**

   Custom Tesseract configuration flags (advanced)

   :Type: ``str``
   :CLI flag: ``--pdf-ocr-tesseract-config``
   :Default: ``''``
   :Importance: advanced

PDF Renderer Options
^^^^^^^^^^^^^^^^^^^^

Configuration options for rendering AST to PDF format.

This dataclass contains settings specific to PDF generation using ReportLab,
including page layout, fonts, margins, and formatting preferences.

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

**metadata_policy**

   Metadata rendering policy controlling which fields appear in output

   :Type: ``MetadataRenderPolicy``
   :CLI flag: ``--pdf-renderer-metadata-policy``
   :Default factory: ``MetadataRenderPolicy``
   :Importance: advanced

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

**comment_mode**

   Comment rendering mode: visible or ignore

   :Type: ``Literal['visible', 'ignore']``
   :CLI flag: ``--pdf-renderer-comment-mode``
   :Default: ``'ignore'``
   :Choices: ``visible``, ``ignore``
   :Importance: core

PLAINTEXT Options
~~~~~~~~~~~~~~~~~


PLAINTEXT Parser Options
^^^^^^^^^^^^^^^^^^^^^^^^

Base class for all parser options.

This class serves as the foundation for format-specific parser options.
Parsers convert source documents into AST representation.

For parsers that handle attachments (images, downloads, etc.), also inherit
from AttachmentOptionsMixin to get attachment-related configuration fields.

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--plaintext-extract-metadata``
   :Default: ``False``
   :Importance: core

PLAINTEXT Renderer Options
^^^^^^^^^^^^^^^^^^^^^^^^^^

Configuration options for plain text rendering.

This dataclass contains settings for rendering AST documents as
plain, unformatted text. All formatting (bold, italic, headings, etc.)
is stripped, leaving only the text content.

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

**metadata_policy**

   Metadata rendering policy controlling which fields appear in output

   :Type: ``MetadataRenderPolicy``
   :CLI flag: ``--plaintext-renderer-metadata-policy``
   :Default factory: ``MetadataRenderPolicy``
   :Importance: advanced

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

**preserve_blank_lines**

   Preserve consecutive blank lines in output

   :Type: ``bool``
   :CLI flag: ``--plaintext-renderer-no-preserve-blank-lines``
   :Default: ``True``
   :Importance: core

**comment_mode**

   Comment rendering mode: visible or ignore

   :Type: ``Literal['visible', 'ignore']``
   :CLI flag: ``--plaintext-renderer-comment-mode``
   :Default: ``'ignore'``
   :Choices: ``visible``, ``ignore``
   :Importance: core

PPTX Options
~~~~~~~~~~~~


PPTX Parser Options
^^^^^^^^^^^^^^^^^^^

Configuration options for PPTX-to-Markdown conversion.

This dataclass contains settings specific to PowerPoint presentation
processing, including slide numbering and image handling.

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
   :Importance: advanced

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

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--pptx-extract-metadata``
   :Default: ``False``
   :Importance: core

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

**comment_mode**

   How to parse speaker notes: content (regular nodes with H3 heading), comment (Comment AST nodes with metadata), or ignore (skip entirely)

   :Type: ``PptxParserCommentMode``
   :CLI flag: ``--pptx-comment-mode``
   :Default: ``'content'``
   :Choices: ``content``, ``comment``, ``ignore``
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

**metadata_policy**

   Metadata rendering policy controlling which fields appear in output

   :Type: ``MetadataRenderPolicy``
   :CLI flag: ``--pptx-renderer-metadata-policy``
   :Default factory: ``MetadataRenderPolicy``
   :Importance: advanced

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

   :Type: ``str | None``
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

**table_left**

   Left position for tables in inches

   :Type: ``float``
   :CLI flag: ``--pptx-renderer-table-left``
   :Default: ``0.5``
   :Importance: advanced

**table_top**

   Top position for tables in inches

   :Type: ``float``
   :CLI flag: ``--pptx-renderer-table-top``
   :Default: ``2.0``
   :Importance: advanced

**table_width**

   Width for tables in inches

   :Type: ``float``
   :CLI flag: ``--pptx-renderer-table-width``
   :Default: ``9.0``
   :Importance: advanced

**table_height_per_row**

   Height per row for tables in inches

   :Type: ``float``
   :CLI flag: ``--pptx-renderer-table-height-per-row``
   :Default: ``0.5``
   :Importance: advanced

**image_left**

   Left position for images in inches

   :Type: ``float``
   :CLI flag: ``--pptx-renderer-image-left``
   :Default: ``1.0``
   :Importance: advanced

**image_top**

   Top position for images in inches

   :Type: ``float``
   :CLI flag: ``--pptx-renderer-image-top``
   :Default: ``2.5``
   :Importance: advanced

**image_width**

   Width for images in inches

   :Type: ``float``
   :CLI flag: ``--pptx-renderer-image-width``
   :Default: ``4.0``
   :Importance: advanced

**network**

   Network security options for fetching remote images

   :Type: ``NetworkFetchOptions``
   :CLI flag: ``--pptx-renderer-network``
   :Default factory: ``NetworkFetchOptions``

**include_notes**

   Include speaker notes in rendered slides

   :Type: ``bool``
   :CLI flag: ``--pptx-renderer-no-include-notes``
   :Default: ``True``
   :Importance: core

**comment_mode**

   Comment rendering mode: speaker_notes, visible, or ignore

   :Type: ``PptxCommentMode``
   :CLI flag: ``--pptx-renderer-comment-mode``
   :Default: ``'speaker_notes'``
   :Choices: ``speaker_notes``, ``visible``, ``ignore``
   :Importance: core

**force_textbox_bullets**

   Enable bullets via OOXML for text boxes (disable for strict templates)

   :Type: ``bool``
   :CLI flag: ``--pptx-renderer-no-force-textbox-bullets``
   :Default: ``True``
   :Importance: advanced

RST Options
~~~~~~~~~~~


RST Parser Options
^^^^^^^^^^^^^^^^^^

Configuration options for reStructuredText-to-AST parsing.

This dataclass contains settings specific to parsing reStructuredText documents
into AST representation using docutils.

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--rst-extract-metadata``
   :Default: ``False``
   :Importance: core

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

**strip_comments**

   Strip comments from output

   :Type: ``bool``
   :CLI flag: ``--rst-no-strip-comments``
   :Default: ``False``
   :Importance: core

RST Renderer Options
^^^^^^^^^^^^^^^^^^^^

Configuration options for AST-to-reStructuredText rendering.

This dataclass contains settings for rendering AST documents as
reStructuredText output.

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

**metadata_policy**

   Metadata rendering policy controlling which fields appear in output

   :Type: ``MetadataRenderPolicy``
   :CLI flag: ``--rst-renderer-metadata-policy``
   :Default factory: ``MetadataRenderPolicy``
   :Importance: advanced

**heading_chars**

   Characters for heading underlines (h1-h5)

   :Type: ``str``
   :CLI flag: ``--rst-renderer-heading-chars``
   :Default: ``'=-~^*'``
   :Importance: advanced

**table_style**

   Table rendering style

   :Type: ``RstTableStyle``
   :CLI flag: ``--rst-renderer-table-style``
   :Default: ``'grid'``
   :Choices: ``grid``, ``simple``
   :Importance: core

**code_directive_style**

   Code block rendering style

   :Type: ``RstCodeStyle``
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

   :Type: ``RstLineBreakMode``
   :CLI flag: ``--rst-renderer-hard-line-break-mode``
   :Default: ``'line_block'``
   :Choices: ``line_block``, ``raw``
   :Importance: advanced

**hard_line_break_fallback_in_containers**

   Automatically fallback to raw mode for line breaks inside lists/blockquotes

   :Type: ``bool``
   :CLI flag: ``--rst-renderer-no-hard-line-break-fallback-in-containers``
   :Default: ``True``
   :Importance: advanced

**comment_mode**

   How to render Comment and CommentInline nodes: comment (.. comments), note (.. note:: directive), ignore (skip comment nodes entirely). Controls presentation of source document comments.

   :Type: ``RstCommentMode``
   :CLI flag: ``--rst-renderer-comment-mode``
   :Default: ``'comment'``
   :Choices: ``comment``, ``note``, ``ignore``
   :Importance: core

RTF Options
~~~~~~~~~~~


RTF Parser Options
^^^^^^^^^^^^^^^^^^

Configuration options for RTF-to-Markdown conversion.

This dataclass contains settings specific to Rich Text Format processing,
including handling of embedded images and other attachments. Inherits
attachment handling from AttachmentOptionsMixin.

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
   :Importance: advanced

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

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--rtf-extract-metadata``
   :Default: ``False``
   :Importance: core

RTF Renderer Options
^^^^^^^^^^^^^^^^^^^^

Configuration options for rendering AST documents to RTF.

**fail_on_resource_errors**

   Raise RenderingError on resource failures (images, etc.) instead of logging warnings

   :Type: ``bool``
   :CLI flag: ``--rtf-renderer-fail-on-resource-errors``
   :Default: ``False``
   :Importance: advanced

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--rtf-renderer-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**metadata_policy**

   Metadata rendering policy controlling which fields appear in output

   :Type: ``MetadataRenderPolicy``
   :CLI flag: ``--rtf-renderer-metadata-policy``
   :Default factory: ``MetadataRenderPolicy``
   :Importance: advanced

**font_family**

   Base font family for the entire RTF document

   :Type: ``Literal['roman', 'swiss']``
   :CLI flag: ``--rtf-renderer-font-family``
   :Default: ``'roman'``
   :Choices: ``roman``, ``swiss``
   :Importance: core

**bold_headings**

   Render heading content in bold

   :Type: ``bool``
   :CLI flag: ``--rtf-renderer-no-bold-headings``
   :Default: ``True``
   :Importance: core

**comment_mode**

   Comment rendering mode: bracketed or ignore

   :Type: ``RtfCommentMode``
   :CLI flag: ``--rtf-renderer-comment-mode``
   :Default: ``'bracketed'``
   :Choices: ``bracketed``, ``ignore``
   :Importance: core

SOURCECODE Options
~~~~~~~~~~~~~~~~~~


SOURCECODE Parser Options
^^^^^^^^^^^^^^^^^^^^^^^^^

Configuration options for source code to Markdown conversion.

This dataclass contains settings specific to source code file processing,
including language detection, formatting options, and output customization.

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--sourcecode-extract-metadata``
   :Default: ``False``
   :Importance: core

**detect_language**

   Automatically detect programming language from file extension

   :Type: ``bool``
   :CLI flag: ``--sourcecode-no-detect-language``
   :Default: ``True``
   :Importance: core

**language_override**

   Override language identifier for syntax highlighting

   :Type: ``UnionType[str, NoneType]``
   :CLI flag: ``--sourcecode-language``
   :Default: ``None``
   :Importance: core

**include_filename**

   Include filename as comment in code block

   :Type: ``bool``
   :CLI flag: ``--sourcecode-include-filename``
   :Default: ``False``
   :Importance: advanced

TEXTILE Options
~~~~~~~~~~~~~~~


TEXTILE Parser Options
^^^^^^^^^^^^^^^^^^^^^^

Configuration options for Textile-to-AST parsing.

This dataclass contains settings specific to parsing Textile documents
into AST representation using the textile library.

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--textile-extract-metadata``
   :Default: ``False``
   :Importance: core

**strict_mode**

   Raise errors on invalid Textile syntax

   :Type: ``bool``
   :CLI flag: ``--textile-strict-mode``
   :Default: ``False``
   :Importance: advanced

**html_passthrough_mode**

   How to handle inline HTML: pass-through, escape, drop, or sanitize

   :Type: ``Literal['pass-through', 'escape', 'drop', 'sanitize']``
   :CLI flag: ``--textile-html-passthrough-mode``
   :Default: ``'escape'``
   :Choices: ``pass-through``, ``escape``, ``drop``, ``sanitize``
   :Importance: security

TEXTILE Renderer Options
^^^^^^^^^^^^^^^^^^^^^^^^

Configuration options for AST-to-Textile rendering.

This dataclass contains settings for rendering AST documents as
Textile markup output.

**fail_on_resource_errors**

   Raise RenderingError on resource failures (images, etc.) instead of logging warnings

   :Type: ``bool``
   :CLI flag: ``--textile-renderer-fail-on-resource-errors``
   :Default: ``False``
   :Importance: advanced

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--textile-renderer-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**metadata_policy**

   Metadata rendering policy controlling which fields appear in output

   :Type: ``MetadataRenderPolicy``
   :CLI flag: ``--textile-renderer-metadata-policy``
   :Default factory: ``MetadataRenderPolicy``
   :Importance: advanced

**use_extended_blocks**

   Use extended block notation (bc., bq., etc.)

   :Type: ``bool``
   :CLI flag: ``--textile-renderer-no-extended-blocks``
   :Default: ``True``
   :Importance: core

**line_length**

   Target line length for wrapping (0 = no wrapping)

   :Type: ``int``
   :CLI flag: ``--textile-renderer-line-length``
   :Default: ``0``
   :Importance: core

**html_passthrough_mode**

   How to handle raw HTML content: pass-through, escape, drop, or sanitize

   :Type: ``HtmlPassthroughMode``
   :CLI flag: ``--textile-renderer-html-passthrough-mode``
   :Default: ``'escape'``
   :Choices: ``pass-through``, ``escape``, ``drop``, ``sanitize``
   :Importance: security

**comment_mode**

   Comment rendering mode: html, blockquote, or ignore

   :Type: ``TextileCommentMode``
   :CLI flag: ``--textile-renderer-comment-mode``
   :Default: ``'html'``
   :Choices: ``html``, ``blockquote``, ``ignore``
   :Importance: core

WEBARCHIVE Options
~~~~~~~~~~~~~~~~~~


WEBARCHIVE Parser Options
^^^^^^^^^^^^^^^^^^^^^^^^^

Configuration options for WebArchive-to-Markdown conversion.

This dataclass contains settings specific to Safari WebArchive file processing,
including options for handling embedded resources and nested frames.

**attachment_mode**

   How to handle attachments/images

   :Type: ``AttachmentMode``
   :CLI flag: ``--webarchive-attachment-mode``
   :Default: ``'alt_text'``
   :Choices: ``skip``, ``alt_text``, ``download``, ``base64``
   :Importance: core

**alt_text_mode**

   How to render alt-text content when using alt_text attachment mode

   :Type: ``AltTextMode``
   :CLI flag: ``--webarchive-alt-text-mode``
   :Default: ``'default'``
   :Choices: ``default``, ``plain_filename``, ``strict_markdown``, ``footnote``
   :Importance: advanced

**attachment_output_dir**

   Directory to save attachments when using download mode

   :Type: ``str | None``
   :CLI flag: ``--webarchive-attachment-output-dir``
   :Default: ``None``
   :Importance: advanced

**attachment_base_url**

   Base URL for resolving attachment references

   :Type: ``str | None``
   :CLI flag: ``--webarchive-attachment-base-url``
   :Default: ``None``
   :Importance: advanced

**max_asset_size_bytes**

   Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)

   :Type: ``int``
   :CLI flag: ``--webarchive-max-asset-size-bytes``
   :Default: ``52428800``
   :Importance: security

**attachment_filename_template**

   Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}

   :Type: ``str``
   :CLI flag: ``--webarchive-attachment-filename-template``
   :Default: ``'{stem}_{type}{seq}.{ext}'``
   :Importance: advanced

**attachment_overwrite**

   File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'

   :Type: ``Literal['unique', 'overwrite', 'skip']``
   :CLI flag: ``--webarchive-attachment-overwrite``
   :Default: ``'unique'``
   :Choices: ``unique``, ``overwrite``, ``skip``
   :Importance: advanced

**attachment_deduplicate_by_hash**

   Avoid saving duplicate attachments by content hash

   :Type: ``bool``
   :CLI flag: ``--webarchive-attachment-deduplicate-by-hash``
   :Default: ``False``
   :Importance: advanced

**attachments_footnotes_section**

   Section title for footnote-style attachment references (None to disable)

   :Type: ``str | None``
   :CLI flag: ``--webarchive-attachments-footnotes-section``
   :Default: ``'Attachments'``
   :Importance: advanced

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--webarchive-extract-metadata``
   :Default: ``False``
   :Importance: core

**extract_title**

   Extract and use HTML <title> element as main heading

   :Type: ``bool``
   :CLI flag: ``--webarchive-extract-title``
   :Default: ``False``
   :Importance: core

**convert_nbsp**

   Convert non-breaking spaces (&nbsp;) to regular spaces

   :Type: ``bool``
   :CLI flag: ``--webarchive-convert-nbsp``
   :Default: ``False``
   :Importance: core

**strip_dangerous_elements**

   Remove potentially dangerous HTML elements (script, style, etc.)

   :Type: ``bool``
   :CLI flag: ``--webarchive-strip-dangerous-elements``
   :Default: ``False``
   :Importance: security

**strip_framework_attributes**

   Remove JavaScript framework attributes (x-*, v-*, ng-*, hx-*, etc.) that can execute code in framework contexts. Only needed if output HTML will be rendered in browsers with these frameworks installed.

   :Type: ``bool``
   :CLI flag: ``--webarchive-strip-framework-attributes``
   :Default: ``False``
   :Importance: security

**detect_table_alignment**

   Automatically detect table column alignment from CSS/attributes

   :Type: ``bool``
   :CLI flag: ``--webarchive-no-detect-table-alignment``
   :Default: ``True``
   :Importance: advanced

**network**

   Network security settings for remote resource fetching

   :Type: ``NetworkFetchOptions``
   :CLI flag: ``--webarchive-network``
   :Default factory: ``NetworkFetchOptions``

**local_files**

   Local file access security settings

   :Type: ``LocalFileAccessOptions``
   :CLI flag: ``--webarchive-local-files``
   :Default factory: ``LocalFileAccessOptions``

**strip_comments**

   Remove HTML comments from output

   :Type: ``bool``
   :CLI flag: ``--webarchive-no-strip-comments``
   :Default: ``True``
   :Importance: advanced

**collapse_whitespace**

   Collapse multiple spaces/newlines into single spaces

   :Type: ``bool``
   :CLI flag: ``--webarchive-no-collapse-whitespace``
   :Default: ``True``
   :Importance: advanced

**extract_readable**

   Extract main article content by stripping navigation and other non-readable content using readability-lxml

   :Type: ``bool``
   :CLI flag: ``--webarchive-extract-readable``
   :Default: ``False``
   :Importance: advanced

**br_handling**

   How to handle <br> tags: 'newline' or 'space'

   :Type: ``Literal['newline', 'space']``
   :CLI flag: ``--webarchive-br-handling``
   :Default: ``'newline'``
   :Choices: ``newline``, ``space``
   :Importance: advanced

**allowed_elements**

   Whitelist of allowed HTML elements (if set, only these are processed)

   :Type: ``tuple[str, ...] | None``
   :CLI flag: ``--webarchive-allowed-elements``
   :Default: ``None``
   :CLI action: ``append``
   :Importance: security

**allowed_attributes**

   Whitelist of allowed HTML attributes. Can be a tuple of attribute names (global allowlist) or a dict mapping element names to tuples of allowed attributes (per-element allowlist). Examples: ('class', 'id') or {'img': ('src', 'alt', 'title'), 'a': ('href', 'title')}. CLI note: For complex dict structures, pass as JSON string: --allowed-attributes '{"img": ["src", "alt"], "a": ["href"]}'

   :Type: ``tuple[str, ...] | dict[str, tuple[str, ...]] | None``
   :CLI flag: ``--webarchive-allowed-attributes``
   :Default: ``None``
   :CLI action: ``append``
   :Importance: security

**figures_parsing**

   How to parse <figure> elements: blockquote, paragraph, image_with_caption, caption_only, html, skip

   :Type: ``Literal['blockquote', 'paragraph', 'image_with_caption', 'caption_only', 'html', 'skip']``
   :CLI flag: ``--webarchive-figures-parsing``
   :Default: ``'blockquote'``
   :Choices: ``blockquote``, ``paragraph``, ``image_with_caption``, ``caption_only``, ``html``, ``skip``
   :Importance: advanced

**details_parsing**

   How to render <details>/<summary> elements: blockquote, html, skip

   :Type: ``Literal['blockquote', 'paragraph', 'html', 'skip']``
   :CLI flag: ``--webarchive-details-parsing``
   :Default: ``'blockquote'``
   :Choices: ``blockquote``, ``html``, ``skip``
   :Importance: advanced

**extract_microdata**

   Extract microdata and structured data to metadata

   :Type: ``bool``
   :CLI flag: ``--webarchive-no-extract-microdata``
   :Default: ``True``
   :Importance: advanced

**base_url**

   Base URL for resolving relative hrefs in <a> tags (separate from attachment_base_url for images)

   :Type: ``str | None``
   :CLI flag: ``--webarchive-base-url``
   :Default: ``None``
   :Importance: advanced

**html_parser**

   BeautifulSoup parser to use: 'html.parser' (built-in, fast, may differ from browsers), 'html5lib' (standards-compliant, slower, matches browser behavior), 'lxml' (fast, requires C library). For security-critical applications, consider 'html5lib' for more consistent parsing.

   :Type: ``Literal['html.parser', 'html5lib', 'lxml']``
   :CLI flag: ``--webarchive-html-parser``
   :Default: ``'html.parser'``
   :Choices: ``html.parser``, ``html5lib``, ``lxml``
   :Importance: advanced

**extract_subresources**

   Extract embedded resources (images, CSS, JS) from WebSubresources

   :Type: ``bool``
   :CLI flag: ``--webarchive-extract-subresources``
   :Default: ``False``
   :Importance: core

**handle_subframes**

   Process nested iframe content from WebSubframeArchives

   :Type: ``bool``
   :CLI flag: ``--webarchive-no-handle-subframes``
   :Default: ``True``
   :Importance: core

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
   :Importance: advanced

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

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--xlsx-extract-metadata``
   :Default: ``False``
   :Importance: core

**sheets**

   Sheet names to include (list or regex pattern). default = all sheets

   :Type: ``list[str] | str | None``
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

   :Type: ``int | None``
   :CLI flag: ``--xlsx-max-rows``
   :Default: ``None``
   :Importance: advanced

**max_cols**

   Maximum columns per table (None = unlimited)

   :Type: ``int | None``
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
Inherits attachment handling from AttachmentOptionsMixin for extracting embedded
resources.

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
   :Importance: advanced

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

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--zip-extract-metadata``
   :Default: ``False``
   :Importance: core

**include_patterns**

   Glob patterns for files to include

   :Type: ``list[str] | None``
   :CLI flag: ``--zip-include``
   :Default: ``None``
   :Importance: core

**exclude_patterns**

   Glob patterns for files to exclude

   :Type: ``list[str] | None``
   :CLI flag: ``--zip-exclude``
   :Default: ``None``
   :Importance: core

**max_depth**

   Maximum directory depth to traverse

   :Type: ``int | None``
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

**resource_file_extensions**

   File extensions to treat as resources (None=use defaults, []=parse all)

   :Type: ``list[str] | None``
   :CLI flag: ``--zip-resource-extensions``
   :Default: ``None``
   :Importance: advanced

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

**enable_parallel_processing**

   Enable parallel processing for large archives (opt-in)

   :Type: ``bool``
   :CLI flag: ``--zip-parallel``
   :Default: ``False``
   :Importance: advanced

**max_workers**

   Maximum worker processes for parallel processing (None=auto-detect CPU cores)

   :Type: ``int | None``
   :CLI flag: ``--zip-max-workers``
   :Default: ``None``
   :Importance: advanced

**parallel_threshold**

   Minimum number of files to enable parallel processing

   :Type: ``int``
   :CLI flag: ``--zip-parallel-threshold``
   :Default: ``10``
   :Importance: advanced

Shared Options
~~~~~~~~~~~~~~


Base Parser Options
^^^^^^^^^^^^^^^^^^^

Base class for all parser options.

This class serves as the foundation for format-specific parser options.
Parsers convert source documents into AST representation.

For parsers that handle attachments (images, downloads, etc.), also inherit
from AttachmentOptionsMixin to get attachment-related configuration fields.

**extract_metadata**

   Extract document metadata as YAML front matter

   :Type: ``bool``
   :CLI flag: ``--extract-metadata``
   :Default: ``False``
   :Importance: core

Base Renderer Options
^^^^^^^^^^^^^^^^^^^^^

Base class for all renderer options.

This class serves as the foundation for format-specific renderer options.
Renderers convert AST documents into various output formats (Markdown, DOCX, PDF, etc.).

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

**metadata_policy**

   Metadata rendering policy controlling which fields appear in output

   :Type: ``MetadataRenderPolicy``
   :CLI flag: ``--renderer-metadata-policy``
   :Default factory: ``MetadataRenderPolicy``
   :Importance: advanced

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

**metadata_policy**

   Metadata rendering policy controlling which fields appear in output

   :Type: ``MetadataRenderPolicy``
   :CLI flag: ``--markdown-metadata-policy``
   :Default factory: ``MetadataRenderPolicy``
   :Importance: advanced

**escape_special**

   Escape special Markdown characters (e.g. asterisks) in text content

   :Type: ``bool``
   :CLI flag: ``--markdown-no-escape-special``
   :Default: ``True``
   :Importance: core

**emphasis_symbol**

   Symbol to use for emphasis/italic formatting

   :Type: ``EmphasisSymbol``
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

   :Type: ``UnderlineMode``
   :CLI flag: ``--markdown-underline-mode``
   :Default: ``'html'``
   :Choices: ``html``, ``markdown``, ``ignore``
   :Importance: advanced

**superscript_mode**

   How to handle superscript text

   :Type: ``SuperscriptMode``
   :CLI flag: ``--markdown-superscript-mode``
   :Default: ``'html'``
   :Choices: ``html``, ``markdown``, ``ignore``
   :Importance: advanced

**subscript_mode**

   How to handle subscript text

   :Type: ``SubscriptMode``
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

   :Type: ``FlavorType``
   :CLI flag: ``--markdown-flavor``
   :Default: ``'gfm'``
   :Choices: ``gfm``, ``commonmark``, ``multimarkdown``, ``pandoc``, ``kramdown``, ``markdown_plus``
   :Importance: core

**strict_flavor_validation**

   Raise errors on flavor-incompatible options instead of just warnings. When True, validate_flavor_compatibility warnings become ValueError exceptions.

   :Type: ``bool``
   :CLI flag: ``--markdown-strict-flavor-validation``
   :Default: ``False``
   :Importance: advanced

**unsupported_table_mode**

   How to handle tables when flavor doesn't support them: drop (skip entirely), ascii (render as ASCII art), force (render as pipe tables anyway), html (render as HTML table)

   :Type: ``UnsupportedTableMode | object``
   :CLI flag: ``--markdown-unsupported-table-mode``
   :Default: ``<object object at 0x0000027755B10A10>``
   :Choices: ``drop``, ``ascii``, ``force``, ``html``
   :Importance: advanced

**unsupported_inline_mode**

   How to handle inline elements unsupported by flavor: plain (render content without formatting), force (use markdown syntax anyway), html (use HTML tags)

   :Type: ``UnsupportedInlineMode | object``
   :CLI flag: ``--markdown-unsupported-inline-mode``
   :Default: ``<object object at 0x0000027755B10A10>``
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

   :Type: ``int | None``
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

   :Type: ``CodeFenceChar``
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

   :Type: ``LinkStyleType``
   :CLI flag: ``--markdown-link-style``
   :Default: ``'inline'``
   :Choices: ``inline``, ``reference``
   :Importance: core

**reference_link_placement**

   Where to place reference link definitions: end_of_document or after_block

   :Type: ``ReferenceLinkPlacement``
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

   :Type: ``MathMode``
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

   :Type: ``MetadataFormatType``
   :CLI flag: ``--markdown-metadata-format``
   :Default: ``'yaml'``
   :Choices: ``yaml``, ``toml``, ``json``
   :Importance: advanced

**html_sanitization**

   How to handle raw HTML content in markdown: pass-through (allow HTML as-is), escape (show as text), drop (remove entirely), sanitize (remove dangerous elements). Default is 'escape' for security. Does not affect code blocks.

   :Type: ``HtmlPassthroughMode``
   :CLI flag: ``--markdown-html-sanitization``
   :Default: ``'escape'``
   :Choices: ``pass-through``, ``escape``, ``drop``, ``sanitize``
   :Importance: security

**comment_mode**

   How to render Comment and CommentInline nodes: html (HTML comments <!-- -->), blockquote (quoted blocks with attribution), ignore (skip comment nodes entirely). Controls presentation of comments from DOCX, HTML, and other formats that support annotations.

   :Type: ``CommentMode``
   :CLI flag: ``--markdown-comment-mode``
   :Default: ``'blockquote'``
   :Choices: ``html``, ``blockquote``, ``ignore``
   :Importance: core

Network Fetch Options
^^^^^^^^^^^^^^^^^^^^^

Network security options for remote resource fetching.

This dataclass contains settings that control how remote resources
(images, CSS, etc.) are fetched, including security constraints
to prevent SSRF attacks.

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
